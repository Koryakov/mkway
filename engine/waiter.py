"""The inbox waiter (card MW-078): the process behind the Stop handler `mkway hook-wait`, installed with `asyncRewake`.

When a session stops, nothing tells it that a row reached its inbox. The waiter fills that gap: Claude Code runs it in
the background after a Stop, and a hook that exits 2 wakes the idle session with its stderr as a system reminder. The
decisions are in `core_wake`; this module reads the facts (the inbox, the pid file, the woken ids, who the session is),
sleeps between looks and exits.

- Exit 0, nothing printed: the session is none of those that wait (a lead, the holder of a card, the last holder of a
  card that is released and not closed), `wake.mode` is `off`, the input or the profile is unusable, or a newer waiter of
  this session took over (its pid is now in the pid file; the older one never kills anything, it only leaves).
- Exit 2 with the line of the oldest unacked row addressed to the session and written by another session; the row id is
  kept in `<state.dir>/wake/<session>.woken`, so it wakes the session once.
- Exit 2 with `no new rows, end the turn` at `wake.deadline_seconds`: the session wakes, does nothing and stops, and the
  Stop arms a new waiter.

The inbox is read from `profiles.shared_state_dir`; the pid file and the woken ids are in the root's own state folder.
"""
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import replace
from pathlib import Path

import core_wake as core
import leads
import messages
import paths
import profiles
import records
import register

WAKE_DIR = "wake"


def _files(state, session):
    folder = Path(state) / WAKE_DIR
    return folder / f"{session}.pid", folder / f"{session}.woken"


def _read_pid(path):
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return None


def _write_pid(path, pid: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(pid + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _drop_pid(path, pid: str) -> None:
    """Remove the pid file only while it still names this waiter: a newer waiter's file stays."""
    if _read_pid(path) == pid:
        try:
            path.unlink()
        except OSError:
            pass


def _woken(path) -> tuple:
    try:
        return tuple(line.strip() for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip())
    except OSError:
        return ()


def _add_woken(path, row_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(row_id + "\n")


def _session_of(text):
    try:
        data = json.loads(text)
    except ValueError:
        return None
    sid = data.get("session_id") if isinstance(data, dict) else None
    return sid if isinstance(sid, str) and sid.strip() else None


def _plain_id(shared, session) -> bool:
    try:
        leads.inbox_path(shared, session)
    except leads.LeadError:
        return False
    return True


def _roles(root, profile, shared, session) -> dict:
    """The facts that say whether this session waits: lead (`leads.json`), holder of a card (`messages.role_of`), last
    holder of a card that is released and not closed (the take and release records). Any failure reads as none."""
    try:
        if leads.is_lead(shared, session):
            return {"is_lead": True}
        closed = register.closed_ids(root, profile)
        role = messages.role_of(root, profile, shared, session)
        if role.card and role.card not in closed:
            return {"holds_card": True}
        state = profiles.state_dir(root, profile)
        rows = records.rows(state)
        last = any(core.last_holder(rows, row["id"], False) == session
                   for row in register.read(root, profile) if row.get("status") != "closed")
        return {"last_holder_unclosed": last}
    except Exception:
        return {}


def _row_of(row: dict, session: str) -> core.Row:
    return core.Row(id=row.get("id"), writer=row.get("from"), to=row.get("to") or session,
                    acked=row.get("ack_ts") is not None)


def run(stdin_text, root, profile, *, env=None, clock=time.monotonic, sleep=time.sleep, err=None, pid=os.getpid) -> int:
    """One waiter, from the Stop payload to its exit code (see the module text). `clock`, `sleep`, `err` and `pid` are
    the process's own unless a test gives others."""
    err = sys.stderr if err is None else err
    session = _session_of(stdin_text)
    if session is None:
        return 0
    settings = profiles.wake_settings(profile)
    shared = profiles.shared_state_dir(root, profile)
    safe = _plain_id(shared, session)
    facts = core.Facts(session=session, mode=settings["mode"], safe_id=safe)
    if settings["mode"] == core.MODE_ON and safe:
        facts = replace(facts, **_roles(root, profile, shared, session))
    if not core.armed(facts):
        return 0
    pid_file, woken_file = _files(profiles.state_dir(root, profile), session)
    mine = str(pid())
    _write_pid(pid_file, mine)
    deadline = clock() + settings["deadline_seconds"]
    try:
        while True:
            if _read_pid(pid_file) != mine:
                return 0  # a newer waiter of this session took over
            inbox = leads.inbox_rows(shared, session)
            verdict = core.decide(replace(facts, rows=tuple(_row_of(r, session) for r in inbox),
                                          woken=_woken(woken_file), now=clock(), deadline=deadline))
            if verdict.kind == core.WAKE:
                _add_woken(woken_file, verdict.row_id)
                row = next(r for r in inbox if r.get("id") == verdict.row_id)
                err.write(messages.item_line(row) + "\n")
                return 2
            if verdict.kind == core.HEARTBEAT:
                err.write(core.HEARTBEAT_LINE + "\n")
                return 2
            sleep(min(settings["poll_seconds"], deadline - clock()))
    finally:
        _drop_pid(pid_file, mine)


def _vcs_hint(profile_arg):
    if not profile_arg:
        return None
    try:
        return json.loads(Path(profile_arg).read_text(encoding="utf-8")).get("vcs")
    except Exception:
        return None


def main(stdin_text, root_arg, profile_arg, env) -> int:
    """`mkway hook-wait`: find the root and the profile as the hook dispatcher does, then wait. An unusable root or
    profile is exit 0: the waiter never blocks and never fails a Stop."""
    try:
        root = paths.find_root(env=env, root_arg=root_arg, vcs=_vcs_hint(profile_arg))
    except paths.RootNotFound:
        return 0
    profile, errors = profiles.load(paths.profile_path(root, profile_arg))
    if errors:
        return 0
    return run(stdin_text, root, profile, env=env)
