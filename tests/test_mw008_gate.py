"""The search gate through the real manifest (card MW-008, part 3). The decision cases moved to
`tests/core/test_ask_decide.py` and `tests/shell/test_ask_facts.py` (card MW-065; see cards/MW-065-ask-core/case_map.md);
the wiring case stays: the one deny, the fail-open log row and the switch of the gate through the dispatcher. Synthetic
task roots and synthetic transcripts only."""
import datetime
import json

import pytest

from _engine import jsonl, task_root
import dispatch

BASE = datetime.datetime(2026, 11, 10, 12, 0, 0, tzinfo=datetime.timezone.utc)
TEXT = "run `mkway search <words>` first, then ask"


def _at(seconds):
    return (BASE + datetime.timedelta(seconds=seconds)).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _user(seconds, content="a question"):
    return {"type": "user", "message": {"content": content}, "timestamp": _at(seconds)}


def _transcript(tmp_path, entries):
    path = tmp_path / "transcript.jsonl"
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    return str(path)


def _record(root, seconds, session="s1", kind="search", value="S-1"):
    row = {"session_id": session, "kind": kind, "value": value, "time": _at(seconds).replace("Z", "+00:00"),
           "by": "session"}
    with open(root / "mkway" / "state" / "records.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


@pytest.fixture
def task(tmp_path):
    # changed by MW-014 (E5): the pop-up tool is off by default; these rows are about the search gate, so it is allowed
    return task_root(tmp_path / "t", questions={"files": ["notes/questions/**", "mkway/q_*.md"]},
                     owner_ask={"tool_allowed": True})


def test_the_search_gate_runs_in_the_edit_group_and_has_a_switch(task, tmp_path):
    """Catches: a search gate that is written but not wired, or has no switch: a question with no search is refused (E16)."""
    transcript = _transcript(tmp_path, [_user(0)])
    payload = {"session_id": "s1", "hook_event_name": "PreToolUse", "tool_name": "AskUserQuestion",
               "tool_input": {"questions": []}, "transcript_path": transcript}
    env = {"CLAUDE_PROJECT_DIR": str(task), "CLAUDECODE": "1"}
    res = dispatch.run("PreToolUse", "edit", json.dumps(payload), env=env)
    assert res.exit_code == 0
    out = json.loads(res.stdout)["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny"
    assert "[mkway search search-missing]" in out["permissionDecisionReason"]
    assert TEXT in out["permissionDecisionReason"]
    log = task / "mkway" / "state" / "refusals.jsonl"
    assert [(r["gate"], r["reason_id"], r["kind"]) for r in jsonl(log)] == [("search", "search-missing", "refuse")]
    _record(task, 30)
    assert dispatch.run("PreToolUse", "edit", json.dumps(payload), env=env).stdout == ""
    # an unreadable transcript passes with a log row search-unverified and no output
    payload["transcript_path"] = str(tmp_path / "none.jsonl")
    assert dispatch.run("PreToolUse", "edit", json.dumps(payload), env=env).stdout == ""
    assert [(r["gate"], r["reason_id"], r["kind"]) for r in jsonl(log)][-1] == ("search", "search-unverified", "log")
    (task / "mkway" / "state" / "records.jsonl").unlink()
    payload["transcript_path"] = transcript
    # gates.search.on false turns the gate off
    profile = json.loads((task / "mkway" / "profile.json").read_text(encoding="utf-8"))
    profile["gates"] = {"search": {"on": False}}
    (task / "mkway" / "profile.json").write_text(json.dumps(profile), encoding="utf-8")
    assert dispatch.run("PreToolUse", "edit", json.dumps(payload), env=env).stdout == ""
