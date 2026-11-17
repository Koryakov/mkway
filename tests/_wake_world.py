"""Card MW-078: helpers for the inbox waiter tests. Not a test module. Synthetic roots and session ids only.

A world is a synthetic task root whose profile has a short deadline and poll (`wake.deadline_seconds` 3,
`wake.poll_seconds` 1), registered leads and builders made through the real commands, and rows written into inboxes.
`Clock` drives `waiter.run` in process with no real waiting; `Pool` starts the real command as a process and kills
what a failed test leaves behind."""
import io
import json
import subprocess
import sys
import time
from pathlib import Path

from _engine import ENGINE
from _mw017 import lead_root, new_card, profile_of, register_lead, session_run, state
import leads
import messages
import profiles

DEADLINE, POLL = 3, 1
HEARTBEAT = "no new rows, end the turn\n"
FIRST = "m-20261112000000-aaaaaa"  # the id of the one synthetic row of most cases
SECOND = "m-20261112000001-bbbbbb"
LINE = ("m-20261112000000-aaaaaa result from build-1: result ready "
        "(`mkway inbox m-20261112000000-aaaaaa`, then `mkway ack m-20261112000000-aaaaaa`)\n")  # the line of `row()`


def waiter_root(tmp_path, shared=None, **wake):
    """A task root with a short deadline; `shared` (a folder inside the temp folder) sets `state.shared_dir`."""
    over = {"wake": {"deadline_seconds": DEADLINE, "poll_seconds": POLL, **wake}}
    if shared is not None:
        over["state"] = {"dir": "mkway/state", "shared_dir": str(shared)}
    return lead_root(tmp_path, **over)


def shared_of(root) -> Path:
    return profiles.shared_state_dir(root, profile_of(root))


def make_lead(root, session):
    register_lead(root, session)


def make_builder(root, lead, builder) -> str:
    """A card the lead ordered, taken by `builder`; returns the card id."""
    card = new_card(root, lead, "Work")
    code, _out, err = session_run(root, builder, "card", "take", card)
    assert code == 0, err
    return card


def release(root, builder, card):
    code, _out, err = session_run(root, builder, "card", "release", card)
    assert code == 0, err


def row(sender="build-1", to="lead-1", body="result ready", kind="result", ident=FIRST):
    return {"id": ident, "from": sender, "to": to, "kind": kind, "reply_to": None,
            "ts": "2026-11-12T00:00:00.000+00:00", "ack_ts": None, "body": body}


def put(root, r):
    """Append a row to the recipient's inbox, in the shared state folder."""
    messages.append_row(shared_of(root), r)


def pid_file(root, session) -> Path:
    return state(root) / "wake" / f"{session}.pid"


def woken_file(root, session) -> Path:
    return state(root) / "wake" / f"{session}.woken"


def stop_payload(session) -> str:
    return json.dumps({"session_id": session, "hook_event_name": "Stop", "cwd": "", "stop_hook_active": False})


class Clock:
    """A clock that never waits: `sleep(s)` moves `now()` on by `s` and runs the step planned for that tick."""

    def __init__(self, plan=None):
        self.t = 0.0
        self.ticks = 0
        self.plan = plan or {}

    def now(self) -> float:
        return self.t

    def sleep(self, seconds) -> None:
        self.t += seconds
        self.ticks += 1
        self.plan.get(self.ticks, lambda: None)()


def run_here(root, session, clock=None, pid=4242, stdin=None):
    """`waiter.run` in this process with a `Clock`; returns (exit code, what it wrote to stderr)."""
    import waiter
    out = io.StringIO()
    clock = clock or Clock()
    code = waiter.run(stdin if stdin is not None else stop_payload(session), root, profile_of(root),
                      clock=clock.now, sleep=clock.sleep, err=out, pid=lambda: pid)
    return code, out.getvalue()


# ---- the real process --------------------------------------------------------------------------------------------

def wait_for(check, seconds=10.0) -> bool:
    """A bounded poll for a state that a process is to reach: True when `check()` holds before the time is up."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if check():
            return True
        time.sleep(0.05)
    return bool(check())


def pid_text(root, session) -> str:
    try:
        return pid_file(root, session).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


class Pool:
    """Real `mkway.py hook-wait` processes. `start` hands the Stop payload on stdin and returns the process."""

    def __init__(self):
        self.procs = []

    def spawn(self, command, payload, cwd=None, env=None) -> subprocess.Popen:
        proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, encoding="utf-8", cwd=cwd, env=env)
        proc.stdin.write(payload)
        proc.stdin.close()
        proc.stdin = None  # `communicate` has nothing to flush
        self.procs.append(proc)
        return proc

    def start(self, root, session) -> subprocess.Popen:
        command = [sys.executable, "-I", "-X", "utf8", str(ENGINE / "mkway.py"), "hook-wait", "--root", str(root)]
        return self.spawn(command, stop_payload(session))

    def kill_all(self) -> None:
        for proc in self.procs:
            if proc.poll() is None:
                proc.kill()
            proc.communicate()


def finish(proc, seconds=20):
    """(exit code, stdout, stderr) of a process that ends on its own."""
    out, err = proc.communicate(timeout=seconds)
    return proc.returncode, out, err
