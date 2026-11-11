"""The owner-ask stop gate (card MW-007, part 2): a final reply with a line that starts with the profile's marker must
have written an ask file since the last user message. Synthetic task roots and synthetic transcripts only. The gate
module is imported inside each test, so a missing module fails that test and not the collection of the file."""
import importlib
import json

import pytest

from _engine import gate_call, jsonl, task_root
import dispatch

USER = {"type": "user", "message": {"content": "a question"}}
TOOL_RESULT_USER = {"type": "user", "message": {"content": [{"type": "tool_result", "content": "ok"}]}}


def _gate():
    return importlib.import_module("gate_owner_ask")


def _text(text):
    return {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}


def _tool(name, path):
    return {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": name,
                                                          "input": {"file_path": path, "content": "x"}}]}}


def _transcript(tmp_path, entries):
    path = tmp_path / "transcript.jsonl"
    path.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n", encoding="utf-8")
    return str(path)


def _stop(root, tmp_path, entries, last=None, active=False, profile=None):
    hook_input = {"hook_event_name": "Stop", "stop_hook_active": active,
                  "transcript_path": _transcript(tmp_path, entries)}
    if last is not None:
        hook_input["last_assistant_message"] = last
    return gate_call(_gate().check, root, tool=None, event="Stop", hook_input=hook_input, profile=profile)


def _id(verdict):
    return verdict.reason_id if verdict.kind == "refuse" else "allow"


@pytest.fixture
def task(tmp_path):
    root = task_root(tmp_path / "t")
    (root / "mkway" / "asks").mkdir(parents=True)
    (root / "mkway" / "asks" / "t_ask.md").write_text("an ask\n", encoding="utf-8")
    return root


def _wrote(root, tool="Write", name="t"):
    return _tool(tool, str(root / "mkway" / "asks" / f"{name}_ask.md"))


def test_a_reply_without_the_marker_is_never_blocked(task, tmp_path):
    """E11 (part 2): a final reply with no marker line passes, whatever the turn did; a marker in the middle of a
    line is no marker. Catches: a gate that blocks ordinary replies, or one that reads the marker as a word."""
    assert _id(_stop(task, tmp_path, [USER, _text("Info: done.")])) == "allow"
    assert _id(_stop(task, tmp_path, [USER], last="See the Request: above.")) == "allow"
    assert _id(_stop(task, tmp_path, [USER], last="no ask here\nsecond line")) == "allow"
    assert _id(_stop(task, tmp_path, [USER], last="")) == "allow"


def test_a_marker_line_needs_an_ask_written_in_this_turn(task, tmp_path):
    """E11 (part 2): a reply with a line that starts with `Request:` (after spaces, or after `**`; on any line of the
    reply) is blocked `ask-not-written` unless this turn, after the last real user message, wrote the ask file; an
    ask written before that message does not count; a tool result is not a user message; a user message with a text
    block is. Catches: an ask that goes to the owner with no ask file, or an old ask file that covers a new ask."""
    ask = _text("Request: yes or no?")
    v = _stop(task, tmp_path, [USER, ask])
    assert v.kind == "refuse" and v.reason_id == "ask-not-written"
    assert "Request:" in v.message and "mkway/asks/<name>_ask.md" in v.message
    assert _id(_stop(task, tmp_path, [USER, _wrote(task), ask])) == "allow"
    assert _id(_stop(task, tmp_path, [_wrote(task), USER, ask])) == "ask-not-written"
    assert _id(_stop(task, tmp_path, [USER, _wrote(task), TOOL_RESULT_USER, ask])) == "allow"
    text_block_user = {"type": "user", "message": {"content": [{"type": "text", "text": "and then?"}]}}
    assert _id(_stop(task, tmp_path, [USER, _wrote(task), text_block_user, ask])) == "ask-not-written"
    for last in ("**Request:** x", "  Request: x", "First line.\nRequest: x\nlast line"):
        assert _id(_stop(task, tmp_path, [USER], last=last)) == "ask-not-written", last
    assert _id(_stop(task, tmp_path, [USER, _wrote(task)], last="Request: x")) == "allow"


def test_stop_hook_active_never_blocks(task, tmp_path):
    """E11 (part 2): with `stop_hook_active` the gate never blocks, so one block cannot trap a session in a loop.
    Catches: a Stop hook that keeps a session from ever finishing."""
    assert _id(_stop(task, tmp_path, [USER, _text("Request: x")], active=True)) == "allow"


def test_only_a_real_ask_file_counts_as_written(task, tmp_path):
    """E12 (part 2): Write, Edit and MultiEdit of an ask file count; a Read does not; a write to another file or
    folder does not; an ask write whose file is not on disk (the edit gate refused it) does not.
    Catches: a session that passes the stop gate with a refused write, or with a write to a look-alike path."""
    ask = _text("Request: x")
    for tool in ("Write", "Edit", "MultiEdit"):
        assert _id(_stop(task, tmp_path, [USER, _wrote(task, tool), ask])) == "allow", tool
    assert _id(_stop(task, tmp_path, [USER, _wrote(task, "Read"), ask])) == "ask-not-written"
    for other in ("notes/t_ask.md", "mkway/asks/t_check.md", "mkway/asks/t_sources.md", "mkway/asks/sub/t_ask.md"):
        assert _id(_stop(task, tmp_path, [USER, _tool("Write", str(task / other)), ask])) == "ask-not-written", other
    assert _id(_stop(task, tmp_path, [USER, _wrote(task, name="gone"), ask])) == "ask-not-written"


def test_marker_and_folder_come_from_the_profile(tmp_path):
    """E13 (part 2): `owner_ask.markers` replaces the marker (the default `Request:` is then no marker, every listed
    string is one); `owner_ask.dir` moves the folder an ask file must be in. Catches: a marker or a folder that is
    hard-coded in the gate."""
    root = task_root(tmp_path / "t", owner_ask={"dir": "notes/asks", "markers": ["Ask:", "Q:"]})
    (root / "notes" / "asks").mkdir(parents=True)
    (root / "notes" / "asks" / "t_ask.md").write_text("an ask\n", encoding="utf-8")
    assert _id(_stop(root, tmp_path, [USER], last="Request: x")) == "allow"
    for last in ("Ask: x", "Q: x"):
        v = _stop(root, tmp_path, [USER], last=last)
        assert v.reason_id == "ask-not-written" and "notes/asks/<name>_ask.md" in v.message, last
    written = _tool("Write", str(root / "notes" / "asks" / "t_ask.md"))
    assert _id(_stop(root, tmp_path, [USER, written], last="Q: x")) == "allow"
    elsewhere = _tool("Write", str(root / "mkway" / "asks" / "t_ask.md"))
    assert _id(_stop(root, tmp_path, [USER, elsewhere], last="Q: x")) == "ask-not-written"


def test_a_missing_or_broken_transcript_does_not_crash_the_gate(task, tmp_path):
    """E14 (part 2): with no readable transcript the gate still reads `last_assistant_message`; a marker line is then
    blocked (nothing proves an ask was written) and the text says the transcript could not be read; with no marker
    it allows; bad lines in a transcript are skipped; with neither a message nor a transcript there is nothing to
    check. Catches: a gate that crashes on a hostile transcript, or blocks a reply that has no marker."""
    gone = {"hook_event_name": "Stop", "stop_hook_active": False, "transcript_path": str(tmp_path / "gone.jsonl")}
    v = gate_call(_gate().check, task, tool=None, event="Stop", hook_input=dict(gone, last_assistant_message="Request: x"))
    assert v.kind == "refuse" and v.reason_id == "ask-not-written" and "transcript could not be read" in v.message
    assert gate_call(_gate().check, task, tool=None, event="Stop",
                     hook_input=dict(gone, last_assistant_message="Info: x")).kind == "allow"
    assert gate_call(_gate().check, task, tool=None, event="Stop", hook_input=gone).kind == "allow"
    assert gate_call(_gate().check, task, tool=None, event="Stop", hook_input=None).kind == "allow"
    path = tmp_path / "bad.jsonl"
    path.write_text("not json\n" + json.dumps(USER) + "\n{broken\n" + json.dumps(_wrote(task)) + "\n"
                    + json.dumps(_text("Request: x")) + "\n", encoding="utf-8")
    assert gate_call(_gate().check, task, tool=None, event="Stop",
                     hook_input={"stop_hook_active": False, "transcript_path": str(path)}).kind == "allow"


def test_the_stop_gate_runs_in_the_stop_group_and_has_a_switch(task, tmp_path):
    """E15 (part 2): through the dispatcher and the real manifest, the `stop` group blocks the reply (top-level
    `decision: block`, the tag `[mkway owner_ask.stop ask-not-written]`, a row in the refusal log) and lets it
    through once the ask is written; `gates.owner_ask.on: false` turns it off; the same switch covers both entries.
    Catches: a gate that is written but not wired, or whose Stop entry gets no hook input."""
    payload = {"session_id": "s1", "hook_event_name": "Stop", "stop_hook_active": False,
               "transcript_path": _transcript(tmp_path, [USER]), "last_assistant_message": "Request: x"}
    env = {"CLAUDE_PROJECT_DIR": str(task), "CLAUDECODE": "1"}
    res = dispatch.run("Stop", "stop", json.dumps(payload), env=env)
    assert res.exit_code == 0
    out = json.loads(res.stdout)
    assert out["decision"] == "block" and "[mkway owner_ask.stop ask-not-written]" in out["reason"]
    assert [(r["gate"], r["reason_id"]) for r in jsonl(task / "mkway" / "state" / "refusals.jsonl")] == [
        ("owner_ask.stop", "ask-not-written")]
    payload["transcript_path"] = _transcript(tmp_path, [USER, _wrote(task)])
    assert dispatch.run("Stop", "stop", json.dumps(payload), env=env).stdout == ""
    payload["transcript_path"] = _transcript(tmp_path, [USER])
    profile = json.loads((task / "mkway" / "profile.json").read_text(encoding="utf-8"))
    profile["gates"] = {"owner_ask": {"on": False}}
    (task / "mkway" / "profile.json").write_text(json.dumps(profile), encoding="utf-8")
    assert dispatch.run("Stop", "stop", json.dumps(payload), env=env).stdout == ""
