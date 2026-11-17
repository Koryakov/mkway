"""Card MW-019, part 2 (the write gate and the record) and the Stop reminder, through the real manifest. The decision
cases moved to `tests/core/test_ask_decide.py` and `tests/shell/test_outbox_facts.py` (card MW-065; see
cards/MW-065-ask-core/case_map.md); the wiring cases stay: the manifest entries of the outbox check, and the one deny and
the Stop reminder through the dispatcher. Synthetic roots only."""
import json

import pytest

import dispatch
from _mw019 import (OUT, SUFFIX, check_text, make_root, refusal_rows, sha_of, valid_file, write_doc)
from pathlib import Path


@pytest.fixture
def task(tmp_path):
    root = make_root(tmp_path)
    write_doc(root)  # outbox/a.md
    return root


def _good(root):
    return check_text(sha_of(Path(root) / f"{OUT}/a.md"))


def _manifest(name):
    entries = json.loads((dispatch.ENGINE_DIR / "manifest.json").read_text(encoding="utf-8"))["entries"]
    return [e for e in entries if e["name"] == name]


WRONG = "0" * 64


def test_the_manifest_entries_of_the_outbox_check():
    """Catches: a gate that is written but not wired (E16: the three outbox_check entries are loaded manifest entries on gate_outbox check, and the dispatcher runs only an entry with a function and reasons)."""
    (pre_e,), (post_e,), (stop_e,) = (_manifest(n) for n in ("outbox_check.pre", "outbox_check.post",
                                                              "outbox_check.stop"))
    assert [(e["function"], e["status"], e["default_on"]) for e in (pre_e, post_e, stop_e)] == [
        ("gate_outbox:check", "on", True)] * 3
    assert all(e["default_on"] is True for e in (pre_e, post_e, stop_e))
    assert (pre_e["group"], pre_e["event"], pre_e["matcher"], pre_e["class"]) == (
        "edit", "PreToolUse", "Edit|Write|MultiEdit", "integrity")  # changed by MW-115 (decision: MW115-D1)
    assert pre_e["reason_ids"] == ["check-sha-mismatch", "verdict-file-by-command"]  # changed by MW-080 (decision: R196)
    assert (post_e["group"], post_e["event"], post_e["matcher"], post_e["class"]) == (
        "post", "PostToolUse", "Edit|Write|MultiEdit", "integrity")
    assert post_e["reason_ids"] == ["check-record-failed"]
    assert (stop_e["group"], stop_e["event"], stop_e["class"]) == ("stop", "Stop", "integrity")
    assert stop_e["reason_ids"] == ["outbox-changed-after-check", "verdict-not-enforced"]  # MW-068, decision: R179
    names = [e["name"] for e in json.loads((dispatch.ENGINE_DIR / "manifest.json").read_text(encoding="utf-8"))[
        "entries"]]
    assert names.index("lock.edit") < names.index("outbox_check.pre")


def test_the_dispatcher_refuses_a_stale_check_write(task):
    """Catches: a gate that works alone and not when wired (E16: a Write of a check with a wrong sha is denied through the dispatcher with the real entries, the right sha passes, and the Stop group reminds once)."""
    manifest = _manifest("outbox_check.pre") + _manifest("outbox_check.stop")
    env = {"CLAUDE_PROJECT_DIR": str(task), "CLAUDECODE": "1"}
    rel = f"{OUT}/a.md{SUFFIX}"
    payload = {"session_id": "s1", "hook_event_name": "PreToolUse", "tool_name": "Write", "cwd": str(task),
               "tool_input": {"file_path": rel, "content": check_text(WRONG)}}
    res = dispatch.run("PreToolUse", "edit", json.dumps(payload), env=env, manifest=manifest)
    out = json.loads(res.stdout)["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny"
    assert "[mkway outbox_check.pre check-sha-mismatch]" in out["permissionDecisionReason"]
    assert [(r["gate"], r["reason_id"]) for r in refusal_rows(task)] == [("outbox_check.pre", "check-sha-mismatch")]
    payload["tool_input"]["content"] = _good(task)
    assert dispatch.run("PreToolUse", "edit", json.dumps(payload), env=env, manifest=manifest).stdout == ""
    valid_file(task, "b.md")
    write_doc(task, "b.md", "Changed after its check.\n", when=400)
    stop_payload = {"session_id": "s1", "hook_event_name": "Stop", "cwd": str(task)}
    first = dispatch.run("Stop", "stop", json.dumps(stop_payload), env=env, manifest=manifest)
    assert "outbox-changed-after-check" in first.stdout
    again = dispatch.run("Stop", "stop", json.dumps(stop_payload), env=env, manifest=manifest)
    assert "outbox-changed-after-check" not in again.stdout
