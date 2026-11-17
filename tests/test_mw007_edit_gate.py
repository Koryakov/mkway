"""The owner-ask edit gate through the real manifest (card MW-007, part 1). The decision cases moved to
`tests/core/test_ask_decide.py` and `tests/shell/test_ask_facts.py` (card MW-065; see cards/MW-065-ask-core/case_map.md);
the wiring case stays: the one deny and the switch of the gate through the dispatcher. Synthetic task roots only."""
import json

from _engine import jsonl, task_root
import _mw014
import dispatch

SUBSTANCE = "kind: substance\nreview: 0 contradictions\n> review: :27 «a verbatim line of the source»\n"


def _sources(root, name, text, folder="mkway/asks"):
    d = root / folder
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}_sources.md").write_text(text, encoding="utf-8", newline="")


def test_the_edit_gate_runs_in_the_edit_group_and_has_a_switch(tmp_path):
    """Catches: a gate written but not wired, or with no switch (E10 part 1: the edit group refuses an ask with no sources through the dispatcher and the real manifest, passes it with sources, and gates.owner_ask.on false turns it off)."""
    task = task_root(tmp_path, paths={"exempt": ["mkway/asks/**"]}, owner_ask={"sources": ["review"]})  # MW-008
    payload = {"session_id": "s1", "hook_event_name": "PreToolUse", "tool_name": "Write",
               "tool_input": {"file_path": "mkway/asks/t_ask.md", "content": _mw014.ask_text()}}  # MW-014 (E3)
    env = {"CLAUDE_PROJECT_DIR": str(task), "CLAUDECODE": "1"}
    res = dispatch.run("PreToolUse", "edit", json.dumps(payload), env=env)
    assert res.exit_code == 0
    out = json.loads(res.stdout)["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny"
    # a deny that names the reason id and leaves a row in the refusal log
    assert "[mkway owner_ask.edit ask-sources-missing]" in out["permissionDecisionReason"]
    assert [(r["gate"], r["reason_id"]) for r in jsonl(task / "mkway" / "state" / "refusals.jsonl")] == [
        ("owner_ask.edit", "ask-sources-missing")]
    _sources(task, "t", SUBSTANCE)
    assert dispatch.run("PreToolUse", "edit", json.dumps(payload), env=env).stdout == ""
    (task / "mkway" / "asks" / "t_sources.md").unlink()
    profile = json.loads((task / "mkway" / "profile.json").read_text(encoding="utf-8"))
    # the profile switch turns the gate off
    profile["gates"] = {"owner_ask": {"on": False}}
    (task / "mkway" / "profile.json").write_text(json.dumps(profile), encoding="utf-8")
    assert dispatch.run("PreToolUse", "edit", json.dumps(payload), env=env).stdout == ""
