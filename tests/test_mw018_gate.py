"""Card MW-018, parts 5 and 6, rows E12 to E15: the lock target of the inbox and the gate `message` on SendMessage. The
gate judges the sender's side only: the body is exactly one ping line, the row exists and is the sender's, the ping is
the first for that row. It never reads the `to` field. Form gate: watch mode first. Synthetic roots only."""
import json

import pytest

from _engine import cli, gate_call, make_profile, write_profile
from _mw018 import id_of, lines, profile_of, send, state, world
import dispatch
import gate_lock
import gate_message
import gatemode
import install
import leads
import locks


def ping(root, session, text, **extra):
    """The gate's verdict for a SendMessage call by `session` with this body."""
    tool_input = dict({"to": "somebody", "message": text}, **extra)
    return gate_call(gate_message.check, root, tool="SendMessage", tool_input=tool_input, session=session)


def pings(root):
    return lines(state(root) / "pings.jsonl")


@pytest.fixture
def sent(tmp_path):
    """A world in which lead-a has sent an order to build-a1 (row `mine`) and lead-b a question to lead-a (row `theirs`)."""
    root = world(tmp_path)
    code, out, err = send(root, "lead-a", "build-a1", "order", "build the thing")
    assert code == 0, err
    mine = id_of(out)
    code, out, err = send(root, "lead-b", "lead-a", "question", "a question", name="other.txt")
    assert code == 0, err
    return root, mine, id_of(out)


# --- E10: the lock target of the inbox ---------------------------------------------------------------------------

def test_the_engine_default_lock_target_inbox_is_in_defaults_json_and_closed(tmp_path):
    """Checks: defaults.json holds the inbox lock target at the profile's state folder, closed like every lock, and a profile target of the same name does not replace it (E12)."""
    data = json.loads((dispatch.ENGINE_DIR / "defaults.json").read_text(encoding="utf-8"))
    assert data["locks"]["targets"] == [{"name": "inbox", "paths": ["<state.dir>/inbox/**", "<state.dir>/pings.jsonl"]}]
    root = world(tmp_path)
    profile = profile_of(root)
    (target,) = [t for t in locks.targets(root, profile) if t.name == "inbox"]
    assert target.entries == ["mkway/state/inbox/**", "mkway/state/pings.jsonl"]
    assert not target.built_in
    assert not locks.is_open(root, profile, "inbox")
    moved = dict(profile, state={"dir": "var/st"}, locks={"targets": [{"name": "inbox", "paths": ["elsewhere/**"]}]})
    (target,) = [t for t in locks.targets(root, moved) if t.name == "inbox"]
    assert target.entries == ["var/st/inbox/**", "var/st/pings.jsonl"]


_INBOX_PATHS = ("mkway/state/inbox/build-a1.jsonl", "mkway/state/inbox/new-file.jsonl", "mkway/state/pings.jsonl")


def _closed_cases():
    """The refused writes: an edit tool into each inbox path, and a shell write of each kind into each path."""
    cases = []
    for path in _INBOX_PATHS:
        cases.append(("Write", {"file_path": path, "content": "{}"}, "lock-closed-edit", path))
    for path in _INBOX_PATHS:
        for command in (f"echo '{{}}' >> {path}", f"cp row.json {path}"):
            cases.append(("Bash", {"command": command}, "lock-closed-shell", command))
    return cases


@pytest.mark.parametrize("tool, tool_input, reason_id, label", [
    pytest.param(*case, id=case[3]) for case in _closed_cases()])
def test_a_hand_written_inbox_row_or_ping_is_refused_by_the_lock(tmp_path, tool, tool_input, reason_id, label):
    """Catches: an edit tool or a shell write into the inbox or the pings file that the lock gate lets through (E12)."""
    root = world(tmp_path)
    verdict = gate_call(gate_lock.check, root, tool=tool, tool_input=tool_input, session="free-1")
    assert verdict.kind == "refuse", label
    assert verdict.reason_id == reason_id, label
    plain = gate_call(gate_lock.check, root, tool="Bash", session="free-1", tool_input={
        "command": "python mkway/engine/mkway.py send --to lead-a --kind question --file body.txt"})
    assert plain.kind == "allow"


# --- E11: the gate -----------------------------------------------------------------------------------------------


# --- E12: wiring -------------------------------------------------------------------------------------------------

def _entries():
    return [e for e in dispatch.load_manifest(dispatch.ENGINE_DIR) if e.get("gate") == "message"]


def _run(root, tool_input, session="lead-a", manifest=None):
    payload = {"session_id": session, "hook_event_name": "PreToolUse", "tool_name": "SendMessage",
               "tool_input": tool_input, "cwd": str(root)}
    return dispatch.run("PreToolUse", "message", json.dumps(payload), env={"CLAUDE_PROJECT_DIR": str(root)},
                        manifest=manifest or _entries())


def test_the_check_warns_when_the_settings_lack_the_sendmessage_entry(tmp_path):
    """Checks: mkway check prints a message gate line, present with the SendMessage hook entry and a warning naming mkway install without it (E15)."""
    from test_install import clean_env, make_light_source, make_task, mkway
    src = make_light_source(tmp_path)
    task = make_task(tmp_path, vcs="none")
    env = {k: v for k, v in clean_env(tmp_path).items() if k != "CLAUDECODE"}
    assert mkway(task, env, "install", "--from", str(src), "--vcs", "none").returncode == 0
    proc = mkway(task, env, "check")
    assert "message gate: the SendMessage hook entry is present" in proc.stdout, proc.stdout + proc.stderr
    settings = task / ".claude" / "settings.json"
    data = json.loads(settings.read_text(encoding="utf-8"))
    data["hooks"]["PreToolUse"] = [g for g in data["hooks"]["PreToolUse"] if g.get("matcher") != "SendMessage"]
    settings.write_text(json.dumps(data), encoding="utf-8")
    proc = mkway(task, env, "check")
    line = [x for x in proc.stdout.splitlines() if x.startswith("message gate:")]
    assert len(line) == 1
    assert "warning" in line[0]
    assert "SendMessage" in line[0]
    assert "mkway install" in line[0]
    assert proc.returncode == 0, proc.stdout
