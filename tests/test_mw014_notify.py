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
    """E7: after an ask file is written the engine runs `notify.command` once, with `{file}` the path of the ask file and
    `{line}` its one line (the question, the default and the deadline); the line stays ONE argument and is never read
    by a shell. Catches: a notification that names no file, a line split at its spaces, or a question text that runs
    as a command."""
    command, out = prog
    root = _root(tmp_path, command)
    path = write_ask(root, "t", question=QUESTION, default="keep A", deadline="2099-01-01T10:00")
    v = post(root, "t")
    assert v.kind == "log" and v.reason_id == "notify-sent"
    file_arg, line_arg = out.read_text(encoding="utf-8").split("|", 1)
    assert file_arg.replace("\\", "/") == path.as_posix() or file_arg.replace("\\", "/").endswith("mkway/asks/t_ask.md")
    assert line_arg == f"{QUESTION} | default: keep A | deadline: 2099-01-01T10:00"
    assert not (root / "x").exists()


def test_nothing_runs_without_a_command_or_for_other_files(tmp_path, prog):
    """E7: with no `notify.command` (the default) nothing runs and nothing is logged; with one, a write of a sources
    file, of a file outside the asks folder, or by a tool that does not write runs nothing either.
    Catches: a notification for every write of the task."""
    command, out = prog
    bare = _root(tmp_path / "bare", None)
    write_ask(bare, "t")
    assert post(bare, "t").kind == "allow" and not out.exists()
    root = _root(tmp_path, command)
    write_ask(root, "t")
    for path in ("mkway/asks/t_sources.md", "work/x.md", "mkway/asks/sub/t_ask.md"):
        assert post(root, path=path).kind == "allow", path
    assert not out.exists()


@pytest.mark.parametrize("command", [
    "this-program-does-not-exist-mw014 {file}",
    f'"{sys.executable}" -c "import sys; sys.exit(3)" {{file}}',
])
def test_a_failing_command_is_logged_and_never_blocks(tmp_path, command):
    """E8: a program that is not found or exits with a code other than 0 gives a `log` verdict `notify-failed` (never a
    refusal), and the owner record of the ask is still written. Catches: a missing notify program that blocks the
    session's own write, or a failure nobody can see in the log."""
    root = _root(tmp_path, command)
    write_ask(root, "t")
    v = post(root, "t", session="s4")
    assert v.kind == "log" and v.reason_id == "notify-failed" and v.message
    assert asks.owners(root / "mkway" / "state") == {"t": "s4"}


def test_a_slow_command_is_stopped_at_the_limit(tmp_path, monkeypatch):
    """E8: the command has 10 seconds (`asks.NOTIFY_SECONDS`); one that runs longer is stopped and logged
    `notify-failed` (the test shortens the limit). Catches: a notify program that holds the session for minutes."""
    assert asks.NOTIFY_SECONDS == 10
    monkeypatch.setattr(asks, "NOTIFY_SECONDS", 1)
    root = _root(tmp_path, f'"{sys.executable}" -c "import time; time.sleep(30)"')
    write_ask(root, "t")
    started = time.time()
    v = post(root, "t")
    assert v.reason_id == "notify-failed" and "1" in v.message
    assert time.time() - started < 15


def test_the_post_group_runs_the_notify_entry_and_writes_the_log_row(tmp_path, prog):
    """E7 E8: through the dispatcher and the real manifest, a PostToolUse of a Write to an ask file runs the entry
    `owner_ask.notify`: the command runs, the refusal log gets a `notify-sent` row (kind log) and a failed command
    gets `notify-failed`; the hook prints nothing and exits 0; the switch `gates.owner_ask.on: false` turns it off.
    Catches: a step that is written but not wired to the hook."""
    command, out = prog
    root = _root(tmp_path, command)
    write_ask(root, "t")
    payload = {"session_id": "s1", "hook_event_name": "PostToolUse", "tool_name": "Write",
               "tool_input": {"file_path": "mkway/asks/t_ask.md", "content": "x"},
               "tool_response": {"filePath": "mkway/asks/t_ask.md", "success": True}}
    env = {"CLAUDE_PROJECT_DIR": str(root), "CLAUDECODE": "1"}
    res = dispatch.run("PostToolUse", "post", json.dumps(payload), env=env)
    assert res.exit_code == 0 and res.stdout == ""
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
    """E7: the manifest has `owner_ask.notify`: gate `owner_ask`, group `post`, event PostToolUse, matcher
    `Write|Edit|MultiEdit`, function `gate_owner_ask:check`, `onFailure: none`, a timeout above the command's 10 s, and
    the reasons `notify-sent`, `notify-failed`, `ask-record-failed`. Catches: a notify step that can block a write."""
    entries = {e["name"]: e for e in json.loads(
        (_mw014.Path(asks.__file__).parent / "manifest.json").read_text(encoding="utf-8"))["entries"]}
    e = entries["owner_ask.notify"]
    assert (e["gate"], e["group"], e["event"], e["matcher"], e["function"], e["onFailure"]) == (
        "owner_ask", "post", "PostToolUse", "Write|Edit|MultiEdit", "gate_owner_ask:check", "none")
    assert e["timeout"] > 10 and e["status"] == "on" and e["on_failure_reason"]
    assert set(e["reason_ids"]) == {"notify-sent", "notify-failed", "ask-record-failed"}


@pytest.mark.parametrize("value, ok", [({"command": "x {file}"}, True), ({"command": ""}, False),
                                       ({"command": 5}, False), ({"other": "x"}, False)])
def test_the_schema_and_the_accessor_for_notify_command(value, ok):
    """E19: `notify.command` is a non-empty string; any other key of `notify` is a profile error; the accessor gives the
    stripped command, or None when it is missing or unusable (nothing then runs). Catches: a command that is not
    text, which the engine would try to run."""
    assert (profiles.validate(make_profile(notify=value)) == []) is ok
    assert profiles.notify_command(make_profile(notify=value)) == ("x {file}" if ok else None)
    assert profiles.notify_command({}) is None and profiles.notify_command(None) is None
    assert profiles.notify_command({"notify": {"command": "  go {file}  "}}) == "go {file}"


def test_keys_md_has_a_line_for_notify_command():
    """E19: KEYS.md has an «in schema now» line for `notify.command` with the placeholders `{file}` and `{line}` and the
    default (none). Catches: a key in the schema that the keys list does not know."""
    rows = {unquote(r[0]): r for r in section_rows("Added keys")}
    row = rows["notify.command"]
    assert row[1] == "in schema now" and row[2] == "`notify.command`" and "MW-014" in row[4]
    assert "{file}" in row[3] and "{line}" in row[3] and "none" in row[3]
