"""Card MW-113, step 2 (way-out tests, K7, the owner-ask lane). One test for each refusal of the ask lane that had no
way-out test: it runs the refusal, then runs exactly what the refusal text names as the fix, and asserts the same call
is allowed. In process, on synthetic task roots; no task data. The engine gap this lane shows (G7) is marked
xfail with the reason, and the engine is not changed."""
import datetime
import json

import pytest

from _engine import cli, task_root
from _mw014 import FAR, PAST, ask_text, write_ask, write_sources
from _mw017 import lead_root, register_lead, session_run
import dispatch

SESSION_SOURCES = "kind: session\nchecked: ListAgents\n"
BASE = datetime.datetime(2026, 11, 10, 12, 0, 0, tzinfo=datetime.timezone.utc)


def _status(root, name="t"):
    text = (root / "mkway" / "asks" / f"{name}_ask.md").read_text(encoding="utf-8")
    return [line for line in text.splitlines() if line.startswith("status:")]


# ---- the ask commands (asks.py): `mkway ask default` and `mkway ask answered` ------------------------------------------

def test_the_way_out_of_ask_deadline_not_passed_is_to_wait_for_the_deadline(tmp_path):
    """Checks: the default of a reversible ask is refused while the deadline is ahead; once the deadline has passed the
    same command takes the default and sets status default-taken (the refusal says: keep waiting)."""
    task = task_root(tmp_path)
    write_ask(task, "t", deadline=FAR)
    code, _out, err = cli(task, "ask", "default", "t", session=True)
    assert (code, "ask-deadline-not-passed" in err, _status(task)) == (1, True, ["status: open"])
    write_ask(task, "t", deadline=PAST)  # the deadline passes
    code, _out, err = cli(task, "ask", "default", "t", session=True)
    assert code == 0, err
    assert _status(task) == ["status: default-taken"]


def test_the_way_out_of_ask_no_default_is_the_owners_answer(tmp_path):
    """Checks: an ask past its deadline with `default: none` is refused (it stays waiting, there is no default to take);
    the owner's answer, recorded with `ask answered`, closes the ask."""
    task = task_root(tmp_path)
    write_ask(task, "t", deadline=PAST, default="none")
    code, _out, err = cli(task, "ask", "default", "t", session=True)
    assert (code, "ask-no-default" in err, _status(task)) == (1, True, ["status: open"])
    code, _out, err = cli(task, "ask", "answered", "t", "--quote", "Take B.", session=False)
    assert code == 0, err
    assert _status(task) == ["status: answered"]


def test_the_way_out_of_ask_not_open_is_a_new_open_ask(tmp_path):
    """Checks: the default of an ask that is already answered is refused and changes nothing; a new ask file with
    status open takes its default through the same command."""
    task = task_root(tmp_path)
    write_ask(task, "old", deadline=PAST, status="answered")
    code, _out, err = cli(task, "ask", "default", "old", session=True)
    assert (code, "ask-not-open" in err, _status(task, "old")) == (1, True, ["status: answered"])
    write_ask(task, "new", deadline=PAST)
    code, _out, err = cli(task, "ask", "default", "new", session=True)
    assert code == 0, err
    assert _status(task, "new") == ["status: default-taken"]


def test_the_way_out_of_ask_not_reversible_is_the_owners_answer(tmp_path):
    """Checks: the default of a `reversible: no` ask is refused even past the deadline (it stays waiting, the owner
    decides); the owner's answer, recorded with `ask answered`, closes the ask."""
    task = task_root(tmp_path)
    write_ask(task, "t", deadline=PAST, reversible="no")
    code, _out, err = cli(task, "ask", "default", "t", session=True)
    assert (code, "ask-not-reversible" in err, _status(task)) == (1, True, ["status: open"])
    code, _out, err = cli(task, "ask", "answered", "t", "--quote", "Take B.", session=False)
    assert code == 0, err
    assert _status(task) == ["status: answered"]


def test_the_way_out_of_ask_unknown_is_an_id_that_mkway_asks_lists(tmp_path):
    """Checks: an id that is no ask file is refused; `mkway asks` lists the real id and the same command takes the
    default of that ask."""
    task = task_root(tmp_path)
    write_ask(task, "t", deadline=PAST)
    code, _out, err = cli(task, "ask", "default", "nope", session=True)
    assert (code, "ask-unknown" in err) == (1, True)
    code, out, err = cli(task, "asks", session=True)
    assert code == 0, err
    assert "t" in out.split()
    code, _out, err = cli(task, "ask", "default", "t", session=True)
    assert code == 0, err
    assert _status(task) == ["status: default-taken"]


# ---- the hook rows: the real dispatcher, the real manifest ---------------------------------------------------------------

def _hook(root, payload, group):
    """One call through the dispatcher with the real manifest: (decision, reason text). The decision is the hook's own
    `permissionDecision` (deny) or `decision` (block); an empty answer, or one with neither, is allow. An id that only a
    watch or warn line holds is not a deny."""
    env = {"CLAUDE_PROJECT_DIR": str(root), "CLAUDECODE": "1"}
    res = dispatch.run(payload["hook_event_name"], group, json.dumps(payload), env=env)
    if not res.stdout.strip():
        return "allow", ""
    out = json.loads(res.stdout)
    inner = out.get("hookSpecificOutput") or {}
    return (inner.get("permissionDecision") or out.get("decision") or "allow",
            inner.get("permissionDecisionReason") or out.get("reason") or "")


def _lead(tmp_path):
    root = lead_root(tmp_path)
    register_lead(root, "lead-a")  # a lead may write the asks folder, so no other gate answers first
    return root


def _write_ask(root, name="t"):
    payload = {"session_id": "lead-a", "hook_event_name": "PreToolUse", "tool_name": "Write", "cwd": str(root),
               "tool_input": {"file_path": f"mkway/asks/{name}_ask.md", "content": ask_text()}}
    return _hook(root, payload, "edit")


def _denied(got, entry, reason):
    return got[0] == "deny" and f"[mkway {entry} {reason}]" in got[1]


def test_the_way_out_of_ask_sources_missing_is_the_sources_file(tmp_path):
    """Checks: through the dispatcher, an ask written with no sources file beside it is denied ask-sources-missing; with
    the sources file written (kind and its lines) the same write is allowed."""
    root = _lead(tmp_path)
    assert _denied(_write_ask(root), "owner_ask.edit", "ask-sources-missing")
    write_sources(root, "t", SESSION_SOURCES)
    assert _write_ask(root) == ("allow", "")


def test_the_way_out_of_ask_sources_kind_is_the_kind_line(tmp_path):
    """Checks: through the dispatcher, a sources file with no `kind:` line is denied ask-sources-kind; with the line
    `kind: session` and its `checked:` line the same write is allowed."""
    root = _lead(tmp_path)
    write_sources(root, "t", "the sources, with no kind line\n")
    assert _denied(_write_ask(root), "owner_ask.edit", "ask-sources-kind")
    write_sources(root, "t", SESSION_SOURCES)
    assert _write_ask(root) == ("allow", "")


def test_the_way_out_of_ask_sources_lines_is_the_line_of_the_kind(tmp_path):
    """Checks: through the dispatcher, a sources file of kind session without its `checked: ListAgents` line is denied
    ask-sources-lines; with that line added the same write is allowed."""
    root = _lead(tmp_path)
    write_sources(root, "t", "kind: session\n")
    assert _denied(_write_ask(root), "owner_ask.edit", "ask-sources-lines")
    write_sources(root, "t", SESSION_SOURCES)
    assert _write_ask(root) == ("allow", "")


def test_the_way_out_of_ask_tool_off_is_the_ask_file_route(tmp_path):
    """Checks: through the dispatcher, the pop-up question tool is denied ask-tool-off and the text names the file route;
    an ask file with its sources file, written as the text says, is allowed."""
    root = _lead(tmp_path)
    payload = {"session_id": "lead-a", "hook_event_name": "PreToolUse", "tool_name": "AskUserQuestion", "cwd": str(root),
               "tool_input": {"questions": []}}
    got = _hook(root, payload, "edit")
    assert _denied(got, "owner_ask.edit", "ask-tool-off")
    assert "mkway/asks/<name>_ask.md" in got[1]
    write_sources(root, "t", SESSION_SOURCES)
    assert _write_ask(root) == ("allow", "")


# ---- the owner-ask stop gate ----------------------------------------------------------------------------------------------

USER = {"type": "user", "message": {"content": "a question"}}
ASKED = {"type": "assistant", "message": {"content": [{"type": "text", "text": "Request: choose one"}]}}


def _wrote(path):
    return {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Write",
                                                          "input": {"file_path": path, "content": "x"}}]}}


def _stop(root, tmp_path, entries):
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    payload = {"session_id": "s1", "hook_event_name": "Stop", "cwd": str(root), "stop_hook_active": False,
               "transcript_path": str(transcript), "last_assistant_message": "Request: choose one\n"}
    return _hook(root, payload, "stop")


def test_the_way_out_of_ask_not_written_is_to_write_the_ask_file(tmp_path):
    """Checks: through the dispatcher, a final reply with a `Request:` line and no ask file written is blocked
    ask-not-written; with the ask file and its sources file written to the asks folder the same reply is allowed."""
    root = task_root(tmp_path / "t")
    got = _stop(root, tmp_path, [USER, ASKED])
    assert (got[0], "ask-not-written" in got[1]) == ("block", True)
    path = write_ask(root, "t")  # the ask file and its sources file, on disk
    assert _stop(root, tmp_path, [USER, _wrote(str(path)), ASKED])[0] == "allow"


# ---- the search gate ------------------------------------------------------------------------------------------------------

def _question(root, tmp_path):
    transcript = tmp_path / "transcript.jsonl"
    when = BASE.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    transcript.write_text(json.dumps({"type": "user", "message": {"content": "a question"}, "timestamp": when}) + "\n",
                          encoding="utf-8")
    payload = {"session_id": "s1", "hook_event_name": "PreToolUse", "tool_name": "AskUserQuestion", "cwd": str(root),
               "transcript_path": str(transcript), "tool_input": {"questions": []}}
    return _hook(root, payload, "edit")


def test_the_way_out_of_search_missing_is_a_search_before_the_question(tmp_path):
    """Checks: through the dispatcher, a question with no search record after the last user message is denied
    search-missing; after the session runs `mkway search <words>` (the real command and its post step) the same question
    is allowed. The pop-up tool is switched on in the profile, so the search gate is the one that answers."""
    root = task_root(tmp_path / "t", owner_ask={"tool_allowed": True})
    assert _denied(_question(root, tmp_path), "search", "search-missing")
    code, _out, err = session_run(root, "s1", "search", "nothing")
    assert code == 0, err
    assert _question(root, tmp_path) == ("allow", "")


# ---- G7: an ask file written by a shell command ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="engine gap G7: the edit gate has no shell matcher, so an ask file written with a shell "
                          "redirect skips the sources and fields check; closing card: not established, a fix card on the owner's word")
def test_an_ask_file_written_by_a_shell_command_is_judged(tmp_path):
    """Catches: an ask that skips the sources and fields check by being written with a shell redirect instead of Write,
    Edit or MultiEdit. Today the shell write is allowed, so this test fails and is marked xfail (engine gap G7, see the
    card MW-113 Log). The control in the same root proves the harness: a Write of an ask file without sources is denied
    (the hook's deny decision, not only the id in a line). The shell write must be denied the same way."""
    root = _lead(tmp_path)
    control = _write_ask(root, "g7c")
    if not _denied(control, "owner_ask.edit", "ask-sources-missing"):  # a broken harness must not read as the gap
        raise RuntimeError(f"the control Write was not denied: {control!r}")
    payload = {"session_id": "lead-a", "hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": str(root),
               "tool_input": {"command": "printf 'a question' > mkway/asks/g7_ask.md"}}
    got = _hook(root, payload, "shell")
    assert got[0] == "deny", got
    assert "ask-sources-missing" in got[1], got
