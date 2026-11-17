"""Commit checks (card MW-006), part 2. MW-034 removed the record of the paths a session wrote and the rule «own changes
only» (`ride-in-file`): these tests now pin that no recorder exists and that nothing is written. Synthetic task roots
only; the gate is called with the dispatcher's own context."""
import json

from _engine import task_root
import dispatch


def _run(root, group, tool, tool_input, session="s1"):
    payload = {"session_id": session, "hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input,
               "cwd": str(root)}
    return dispatch.run("PreToolUse", group, json.dumps(payload), env={"CLAUDE_PROJECT_DIR": str(root)})


def test_the_recorder_and_the_ride_in_rule_are_gone():
    """Checks: the manifest and gate_commit hold no recorder, reason id or touch function (E4, E8 of MW-034)."""
    # part 2, changed by MW-034 E8: the recorder and the ride-in-file rule are gone; the one commit_files entry stays
    import gate_commit
    entries = dispatch.load_manifest(dispatch.ENGINE_DIR)
    names = [e["name"] for e in entries]
    assert "touched.edit" not in names
    assert "touched.shell" not in names
    reasons = {r for e in entries for r in e["reason_ids"]}
    assert "touch-record-failed" not in reasons
    assert "ride-in-file" not in reasons
    assert [e["name"] for e in entries if e["gate"] == "commit_files"] == ["commit_files"]
    assert not hasattr(gate_commit, "touch")
    assert not hasattr(gate_commit, "touched")


def test_an_allowed_write_leaves_no_record_file(tmp_path):
    """Checks: an allowed write by the edit tool or the shell leaves no touched.jsonl (E5, E8 of MW-034)."""
    # part 2, changed by MW-034 E8: the recorder is not written by the generated hooks any more
    root = task_root(tmp_path, paths={"exempt": ["src/**"]})
    assert _run(root, "edit", "Edit", {"file_path": "src/x.py"}).exit_code == 0
    assert _run(root, "shell", "Bash", {"command": "echo x > src/y.txt"}).exit_code == 0
    assert not (root / "mkway" / "state" / "touched.jsonl").exists()
