"""The owner-ask stop gate through the real manifest (card MW-007, part 2). The decision cases moved to
`tests/core/test_ask_decide.py` and `tests/shell/test_ask_facts.py` (card MW-065; see cards/MW-065-ask-core/case_map.md);
the wiring case stays: the block, the log row and the switch of the gate through the dispatcher. Synthetic task roots and
synthetic transcripts only."""
import json

import pytest

from _engine import jsonl, task_root
import dispatch

USER = {"type": "user", "message": {"content": "a question"}}


def _tool(name, path):
    return {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": name,
                                                          "input": {"file_path": path, "content": "x"}}]}}


def _transcript(tmp_path, entries):
    path = tmp_path / "transcript.jsonl"
    path.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n", encoding="utf-8")
    return str(path)


@pytest.fixture
def task(tmp_path):
    root = task_root(tmp_path / "t")
    (root / "mkway" / "asks").mkdir(parents=True)
    (root / "mkway" / "asks" / "t_ask.md").write_text("an ask\n", encoding="utf-8")
    return root


def _wrote(root, tool="Write", name="t"):
    return _tool(tool, str(root / "mkway" / "asks" / f"{name}_ask.md"))


def test_the_stop_gate_runs_in_the_stop_group_and_has_a_switch(task, tmp_path):
    """Catches: a gate that is written but not wired, or whose Stop entry gets no hook input, through the real manifest. E15 part 2"""
    # through the dispatcher and the real manifest, the stop group blocks the reply (top-level decision: block, the tag
    # [mkway owner_ask.stop ask-not-written], a row in the refusal log) and lets it through once the ask is written;
    # gates.owner_ask.on: false turns it off; the same switch covers both entries.
    payload = {"session_id": "s1", "hook_event_name": "Stop", "stop_hook_active": False,
               "transcript_path": _transcript(tmp_path, [USER]), "last_assistant_message": "Request: x"}
    env = {"CLAUDE_PROJECT_DIR": str(task), "CLAUDECODE": "1"}
    res = dispatch.run("Stop", "stop", json.dumps(payload), env=env)
    assert res.exit_code == 0
    out = json.loads(res.stdout)
    assert out["decision"] == "block"
    assert "[mkway owner_ask.stop ask-not-written]" in out["reason"]
    assert [(r["gate"], r["reason_id"]) for r in jsonl(task / "mkway" / "state" / "refusals.jsonl")] == [
        ("owner_ask.stop", "ask-not-written")]
    payload["transcript_path"] = _transcript(tmp_path, [USER, _wrote(task)])
    assert dispatch.run("Stop", "stop", json.dumps(payload), env=env).stdout == ""
    payload["transcript_path"] = _transcript(tmp_path, [USER])
    profile = json.loads((task / "mkway" / "profile.json").read_text(encoding="utf-8"))
    profile["gates"] = {"owner_ask": {"on": False}}
    (task / "mkway" / "profile.json").write_text(json.dumps(profile), encoding="utf-8")
    assert dispatch.run("Stop", "stop", json.dumps(payload), env=env).stdout == ""
