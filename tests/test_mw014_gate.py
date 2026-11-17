"""Card MW-014, part 1: the ask file carries its fields, one open ask per session, the pop-up question tool is off. The
decision cases moved to `tests/core/test_ask_decide.py` and `tests/shell/test_ask_facts.py` (card MW-065; see
cards/MW-065-ask-core/case_map.md); the wiring case stays: the real manifest refuses the pop-up tool before the search
gate. Synthetic task roots only; no task data."""
import json

from _engine import jsonl, task_root
import dispatch


def test_the_dispatcher_refuses_the_pop_up_tool_before_the_search_gate(tmp_path):
    """Catches: a pop-up question gate that is written but not wired to the tool, so the real manifest does not refuse AskUserQuestion (E6)."""
    task = task_root(tmp_path)
    payload = {"session_id": "s1", "hook_event_name": "PreToolUse", "tool_name": "AskUserQuestion",
               "tool_input": {"questions": []}}
    env = {"CLAUDE_PROJECT_DIR": str(task), "CLAUDECODE": "1"}
    res = dispatch.run("PreToolUse", "edit", json.dumps(payload), env=env)
    out = json.loads(res.stdout)["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny"
    assert "[mkway owner_ask.edit ask-tool-off]" in out["permissionDecisionReason"]
    assert [(r["gate"], r["reason_id"]) for r in jsonl(task / "mkway" / "state" / "refusals.jsonl")] == [
        ("owner_ask.edit", "ask-tool-off")]
    profile = json.loads((task / "mkway" / "profile.json").read_text(encoding="utf-8"))
    profile["owner_ask"] = {"tool_allowed": True}
    (task / "mkway" / "profile.json").write_text(json.dumps(profile), encoding="utf-8")
    res = dispatch.run("PreToolUse", "edit", json.dumps(payload), env=env)  # no transcript: the search gate only logs
    assert "ask-tool-off" not in res.stdout
    assert jsonl(task / "mkway" / "state" / "refusals.jsonl")[-1]["reason_id"] == "search-unverified"
