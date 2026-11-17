"""Card MW-014, part 2: the notify command runs after an ask file is written, never blocks, and logs the outcome.
Synthetic task roots and a synthetic program only; no task data."""
import json
import sys
import time

import pytest

import _mw014
from _engine import jsonl, task_root
from _keys_md import section_rows, unquote
from _mw014 import post, write_ask
import asks
import dispatch
import profiles
from _engine import make_profile

QUESTION = "Which option? $(touch x) & echo"


@pytest.fixture
def prog(tmp_path):
    """A synthetic notify program: it writes its arguments, joined by `|`, to the file named by its first argument."""
    script = tmp_path / "notify_fixture.py"
    script.write_text("import sys\nopen(sys.argv[1], 'w', encoding='utf-8').write('|'.join(sys.argv[2:]))\n",
                      encoding="utf-8")
    out = tmp_path / "notified.txt"
    command = f'"{sys.executable}" "{script.as_posix()}" "{out.as_posix()}" "{{file}}" "{{line}}"'
    return command, out


def _root(tmp_path, command):
    return task_root(tmp_path, notify={"command": command} if command else {})


def test_the_command_runs_with_the_file_and_the_line_filled(tmp_path, prog):
    """Checks: after an ask file is written the engine runs notify.command once, with {file} the ask file and {line} its one line, which stays one argument and is never read by a shell (E7)."""
    command, out = prog
    root = _root(tmp_path, command)
    path = write_ask(root, "t", question=QUESTION, default="keep A", deadline="2099-01-01T10:00")
    v = post(root, "t")
    assert v.kind == "log"
    assert v.reason_id == "notify-sent"
    file_arg, line_arg = out.read_text(encoding="utf-8").split("|", 1)
    assert file_arg.replace("\\", "/") == path.as_posix() or file_arg.replace("\\", "/").endswith("mkway/asks/t_ask.md")
    assert line_arg == f"{QUESTION} | default: keep A | deadline: 2099-01-01T10:00"
    assert not (root / "x").exists()


def test_nothing_runs_without_a_command_or_for_other_files(tmp_path, prog):
    """Checks: with no notify.command nothing runs and nothing is logged; with one, a write of a sources file, of a file outside the asks folder, or by a tool that does not write runs nothing either (E7)."""
    command, out = prog
    bare = _root(tmp_path / "bare", None)
    write_ask(bare, "t")
    # a notification for every write of the task would fail here
    assert post(bare, "t").kind == "allow"
    assert not out.exists()
    root = _root(tmp_path, command)
    write_ask(root, "t")
    assert post(root, path="mkway/asks/t_sources.md").kind == "allow"
    assert post(root, path="work/x.md").kind == "allow"
    assert post(root, path="mkway/asks/sub/t_ask.md").kind == "allow"
    assert not out.exists()


@pytest.mark.parametrize("command", [
    "this-program-does-not-exist-mw014 {file}",
    f'"{sys.executable}" -c "import sys; sys.exit(3)" {{file}}',
])
def test_a_failing_command_is_logged_and_never_blocks(tmp_path, command):
    """Checks: a program that is not found or exits with a code other than 0 gives a log verdict notify-failed, never a refusal, and the owner record of the ask is still written (E8)."""
    root = _root(tmp_path, command)
    write_ask(root, "t")
    v = post(root, "t", session="s4")
    assert v.kind == "log"
    assert v.reason_id == "notify-failed"
    assert v.message
    assert asks.owners(root / "mkway" / "state") == {"t": "s4"}


def test_a_slow_command_is_stopped_at_the_limit(tmp_path, monkeypatch):
    """Checks: a command that runs past the limit is stopped and logged notify-failed, so it cannot hold the session (E8: the command has 10 seconds, asks.NOTIFY_SECONDS; the test shortens the limit)."""
    assert asks.NOTIFY_SECONDS == 10
    monkeypatch.setattr(asks, "NOTIFY_SECONDS", 1)
    root = _root(tmp_path, f'"{sys.executable}" -c "import time; time.sleep(30)"')
    write_ask(root, "t")
    started = time.time()
    v = post(root, "t")
    assert v.reason_id == "notify-failed"
    assert "1" in v.message
    assert time.time() - started < 15


def test_the_post_group_runs_the_notify_entry_and_writes_the_log_row(tmp_path, prog):
    """Checks: through the dispatcher and the real manifest a PostToolUse of a Write to an ask file runs owner_ask.notify, which logs notify-sent or notify-failed, prints nothing and exits 0, and goes off with the switch gates.owner_ask.on false (E7 E8)."""
    command, out = prog
    root = _root(tmp_path, command)
    write_ask(root, "t")
    payload = {"session_id": "s1", "hook_event_name": "PostToolUse", "tool_name": "Write",
               "tool_input": {"file_path": "mkway/asks/t_ask.md", "content": "x"},
               "tool_response": {"filePath": "mkway/asks/t_ask.md", "success": True}}
    env = {"CLAUDE_PROJECT_DIR": str(root), "CLAUDECODE": "1"}
    res = dispatch.run("PostToolUse", "post", json.dumps(payload), env=env)
    assert res.exit_code == 0
    assert res.stdout == ""
    assert out.exists()
    rows = [(r["gate"], r["reason_id"], r["kind"]) for r in jsonl(root / "mkway" / "state" / "refusals.jsonl")]
    assert rows == [("owner_ask.notify", "notify-sent", "log")]
    profile = json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))
    profile["notify"] = {"command": "this-program-does-not-exist-mw014 {file}"}
    (root / "mkway" / "profile.json").write_text(json.dumps(profile), encoding="utf-8")
    assert dispatch.run("PostToolUse", "post", json.dumps(payload), env=env).exit_code == 0
    assert jsonl(root / "mkway" / "state" / "refusals.jsonl")[-1]["reason_id"] == "notify-failed"
    profile["gates"] = {"owner_ask": {"on": False}}
    (root / "mkway" / "profile.json").write_text(json.dumps(profile), encoding="utf-8")
    before = len(jsonl(root / "mkway" / "state" / "refusals.jsonl"))
    dispatch.run("PostToolUse", "post", json.dumps(payload), env=env)
    assert len(jsonl(root / "mkway" / "state" / "refusals.jsonl")) == before


def test_the_manifest_entry_of_the_notify_step():
    """Checks: the manifest has owner_ask.notify with its gate, group, event, matcher, function and onFailure none, a timeout above the command's 10 s, and its reasons (E7)."""
    entries = {e["name"]: e for e in json.loads(
        (_mw014.Path(asks.__file__).parent / "manifest.json").read_text(encoding="utf-8"))["entries"]}
    e = entries["owner_ask.notify"]
    assert (e["gate"], e["group"], e["event"], e["matcher"], e["function"], e["onFailure"]) == (
        "owner_ask", "post", "PostToolUse", "Write|Edit|MultiEdit", "gate_owner_ask:check", "none")
    assert e["timeout"] > 10
    assert e["status"] == "on"
    assert e["on_failure_reason"]
    assert set(e["reason_ids"]) == {"notify-sent", "notify-failed", "ask-record-failed"}


@pytest.mark.parametrize("value, ok", [({"command": "x {file}"}, True), ({"command": ""}, False),
                                       ({"command": 5}, False), ({"other": "x"}, False)])
def test_the_schema_and_the_accessor_for_notify_command(value, ok):
    """Catches: a command that is not text, which the engine would try to run (E19: notify.command is a non-empty string; any other key of notify is a profile error; the accessor gives the stripped command, or None when it is missing or unusable)."""
    assert (profiles.validate(make_profile(notify=value)) == []) is ok
    assert profiles.notify_command(make_profile(notify=value)) == ("x {file}" if ok else None)
    assert profiles.notify_command({}) is None
    assert profiles.notify_command(None) is None
    assert profiles.notify_command({"notify": {"command": "  go {file}  "}}) == "go {file}"


def test_keys_md_has_a_line_for_notify_command():
    """Checks: KEYS.md has an in schema now line for notify.command with the placeholders {file} and {line} and the default none (E19)."""
    rows = {unquote(r[0]): r for r in section_rows("Added keys")}
    row = rows["notify.command"]
    assert row[1] == "in schema now"
    assert row[2] == "`notify.command`"
    assert "MW-014" in row[4]
    assert "{file}" in row[3]
    assert "{line}" in row[3]
    assert "none" in row[3]
