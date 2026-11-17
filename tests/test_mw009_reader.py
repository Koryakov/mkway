"""Deletes (card MW-009), part P2: the manifest entry of the delete gate. The reader and refusal cases moved to the
table and shell tests (card MW-064, cards/MW-064-delete-core/case_map.md); this wiring check of the engine's own
manifest stays."""
import json

from _engine import REPO

REASONS = {"delete-target-unknown", "delete-too-large", "delete-backup-failed", "delete-wildcard",
           "delete-outside-root", "delete-sql", "delete-uncommitted", "owner-only-command"}


def test_the_manifest_has_the_delete_gate_after_the_commit_gate():
    """Catches: a delete gate that is written but not wired, or one that fails open. E14 (part 2): the manifest entry, reason ids and its place after commit_files."""
    import importlib
    entries = json.loads((REPO / "engine" / "manifest.json").read_text(encoding="utf-8"))["entries"]
    names = [e["name"] for e in entries]
    entry = entries[names.index("delete")]
    assert (entry["gate"], entry["group"], entry["event"], entry["matcher"], entry["function"]) == (
        "delete", "shell", "PreToolUse", "Bash|PowerShell", "gate_delete:check")
    assert entry["onFailure"] == "block"
    assert entry["status"] == "on"
    assert entry["default_on"] is True
    assert entry["on_failure_reason"]
    assert set(entry["reason_ids"]) == REASONS
    assert names.index("delete") > names.index("commit_files")
    assert callable(getattr(importlib.import_module("gate_delete"), "check"))
