"""The search gate (card MW-008, part 3): a question to the owner needs a search record of this session that is newer
than the last real user message. Synthetic task roots and synthetic transcripts only; no task data. The gate module is
imported inside each test, so a missing module fails that test and not the collection of the file."""
import datetime
import importlib
import json

import pytest

from _engine import gate_call, jsonl, task_root
import dispatch

BASE = datetime.datetime(2026, 11, 10, 12, 0, 0, tzinfo=datetime.timezone.utc)
TEXT = "run `mkway search <words>` first, then ask"


def _at(seconds):
    return (BASE + datetime.timedelta(seconds=seconds)).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _user(seconds, content="a question"):
    return {"type": "user", "message": {"content": content}, "timestamp": _at(seconds)}


def _tool_result(seconds):
    return {"type": "user", "message": {"content": [{"type": "tool_result", "content": "ok"}]},
            "timestamp": _at(seconds)}


def _assistant(seconds):
    return {"type": "assistant", "message": {"content": [{"type": "text", "text": "working"}]},
            "timestamp": _at(seconds)}


def _gate():
    return importlib.import_module("gate_search")


def _transcript(tmp_path, entries):
    path = tmp_path / "transcript.jsonl"
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    return str(path)


def _record(root, seconds, session="s1", kind="search", value="S-1"):
    row = {"session_id": session, "kind": kind, "value": value, "time": _at(seconds).replace("Z", "+00:00"),
           "by": "session"}
    with open(root / "mkway" / "state" / "records.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def _ask(root, tmp_path, entries, tool="AskUserQuestion", tool_input=None, session="s1", profile=None):
    hook_input = {"hook_event_name": "PreToolUse", "transcript_path": _transcript(tmp_path, entries)}
    return gate_call(_gate().check, root, tool=tool, tool_input=tool_input or {"questions": []}, session=session,
                     hook_input=hook_input, profile=profile)


def _id(verdict):
    return verdict.reason_id if verdict.kind != "allow" else "allow"


@pytest.fixture
def task(tmp_path):
    # changed by MW-014 (E5): the pop-up tool is off by default; these rows are about the search gate, so it is allowed
    return task_root(tmp_path / "t", questions={"files": ["notes/questions/**", "mkway/q_*.md"]},
                     owner_ask={"tool_allowed": True})


def test_a_question_needs_a_search_of_this_turn(task, tmp_path):
    """E12 (part 3): `AskUserQuestion` with no search record of this session is refused `search-missing`, and the
    text says to run `mkway search <words>` first, then ask; with a record after the last user message it passes. Other
    record kinds are not a search. Catches: a question that goes to the owner before any search."""
    entries = [_user(0), _assistant(10)]
    v = _ask(task, tmp_path, entries)
    assert v.kind == "refuse" and v.reason_id == "search-missing"
    assert TEXT in v.message
    _record(task, 20, kind="take", value="CARD-001")
    assert _id(_ask(task, tmp_path, entries)) == "search-missing"
    _record(task, 30)
    assert _id(_ask(task, tmp_path, entries)) == "allow"


def test_only_a_record_newer_than_the_last_user_message_counts(task, tmp_path):
    """E13 (part 3): a search record from before the last real user message does not count; another session's record
    does not count; a tool result is not a user message, so a search followed by tool results still counts; a new
    user message after the search makes the next question need a new search; with no user message in the transcript
    any record of the session counts. Catches: a search of an earlier turn that lets this turn's question through."""
    _record(task, -30)
    assert _id(_ask(task, tmp_path, [_user(0), _assistant(5)])) == "search-missing"
    _record(task, 30, session="other")
    assert _id(_ask(task, tmp_path, [_user(0), _assistant(5)])) == "search-missing"
    _record(task, 20)
    turn = [_user(0), _assistant(10), _tool_result(25), _assistant(26), _tool_result(40)]
    assert _id(_ask(task, tmp_path, turn)) == "allow"
    assert _id(_ask(task, tmp_path, turn + [_user(100, [{"type": "text", "text": "next question"}])])) \
        == "search-missing"
    assert _id(_ask(task, tmp_path, [_assistant(5)])) == "allow"


def test_a_write_to_a_question_file_is_gated(task, tmp_path):
    """E14 (part 3): a Write, Edit or MultiEdit of a path that matches a glob of `questions.files` is gated like the
    question (any spelling of the path); a write to another path passes; so does a tool that does not write; with no
    `questions.files` in the profile no write is gated, though `AskUserQuestion` still is.
    Catches: a question file written with no search, or a gate that blocks every write."""
    entries = [_user(0)]
    for tool in ("Write", "Edit", "MultiEdit"):
        for path in ("notes/questions/q1.md", "./notes/questions/sub/q1.md", "mkway/q_a.md",
                     str(task / "notes" / "questions" / "q1.md"), "notes\\questions\\q1.md"):
            v = _ask(task, tmp_path, entries, tool=tool, tool_input={"file_path": path, "content": "x"})
            assert v.kind == "refuse" and v.reason_id == "search-missing", (tool, path)
    for path in ("notes/other.md", "mkway/asks/t_ask.md", "mkway/q.md", "src/questions/q1.md"):
        assert _id(_ask(task, tmp_path, entries, tool="Write", tool_input={"file_path": path})) == "allow", path
    assert _id(_ask(task, tmp_path, entries, tool="Read", tool_input={"file_path": "notes/questions/q1.md"})) == "allow"
    assert _id(_ask(task, tmp_path, entries, tool="Write", tool_input=None)) == "allow"
    bare = task_root(tmp_path / "bare")
    assert _id(_ask(bare, tmp_path, entries, tool="Write", tool_input={"file_path": "notes/questions/q1.md"})) \
        == "allow"
    assert _id(_ask(bare, tmp_path, entries)) == "search-missing"
    _record(task, 10)
    assert _id(_ask(task, tmp_path, entries, tool="Write", tool_input={"file_path": "notes/questions/q1.md"})) \
        == "allow"


def test_the_gate_fails_open_with_a_log_row(task, tmp_path):
    """E15 (part 3): when the turn boundary cannot be read (no transcript, a folder in its place, a user message with
    no time, a session with no id) the gate allows and returns a `log` verdict `search-unverified`, never a refusal
    and never an exception. Catches: a gate that blocks every question when its own reading fails."""
    _record(task, 30)
    unreadable = [{"hook_event_name": "PreToolUse"}, {"transcript_path": str(tmp_path)},
                  {"transcript_path": str(tmp_path / "none.jsonl")}]
    for hook_input in unreadable:
        v = gate_call(_gate().check, task, tool="AskUserQuestion", tool_input={}, session="s1", hook_input=hook_input)
        assert v.kind == "log" and v.reason_id == "search-unverified", hook_input
    no_time = [{"type": "user", "message": {"content": "a question"}}]
    v = _ask(task, tmp_path, no_time)
    assert v.kind == "log" and v.reason_id == "search-unverified"
    v = _ask(task, tmp_path, [_user(0)], session=None)
    assert v.kind == "log" and v.reason_id == "search-unverified"


def test_the_search_gate_runs_in_the_edit_group_and_has_a_switch(task, tmp_path):
    """E16 (part 3): through the dispatcher and the real manifest, the `edit` group refuses a question with no search
    (`[mkway search search-missing]`, a row in the refusal log) and passes it after a search; an unreadable transcript
    passes with a `log` row `search-unverified` and no output; `gates.search.on: false` turns the gate off. Catches: a
    gate that is written but not wired, or has no switch."""
    transcript = _transcript(tmp_path, [_user(0)])
    payload = {"session_id": "s1", "hook_event_name": "PreToolUse", "tool_name": "AskUserQuestion",
               "tool_input": {"questions": []}, "transcript_path": transcript}
    env = {"CLAUDE_PROJECT_DIR": str(task), "CLAUDECODE": "1"}
    res = dispatch.run("PreToolUse", "edit", json.dumps(payload), env=env)
    assert res.exit_code == 0
    out = json.loads(res.stdout)["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny"
    assert "[mkway search search-missing]" in out["permissionDecisionReason"] and TEXT in out["permissionDecisionReason"]
    log = task / "mkway" / "state" / "refusals.jsonl"
    assert [(r["gate"], r["reason_id"], r["kind"]) for r in jsonl(log)] == [("search", "search-missing", "refuse")]
    _record(task, 30)
    assert dispatch.run("PreToolUse", "edit", json.dumps(payload), env=env).stdout == ""
    payload["transcript_path"] = str(tmp_path / "none.jsonl")
    assert dispatch.run("PreToolUse", "edit", json.dumps(payload), env=env).stdout == ""
    assert [(r["gate"], r["reason_id"], r["kind"]) for r in jsonl(log)][-1] == ("search", "search-unverified", "log")
    (task / "mkway" / "state" / "records.jsonl").unlink()
    payload["transcript_path"] = transcript
    profile = json.loads((task / "mkway" / "profile.json").read_text(encoding="utf-8"))
    profile["gates"] = {"search": {"on": False}}
    (task / "mkway" / "profile.json").write_text(json.dumps(profile), encoding="utf-8")
    assert dispatch.run("PreToolUse", "edit", json.dumps(payload), env=env).stdout == ""
