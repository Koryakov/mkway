"""Card MW-052: how the commit gate is wired to the dispatcher: the manifest entry declares every reason the gate can
return, the gate runs in the shell group, and its refusal carries the tag and a row. Synthetic task roots only, real
throwaway git repositories. Moved from MW-006 E23 and MW-021 E6. One test id is one case."""
import json

from _commit_fixture import make_task, stage, work
from _engine import jsonl
import dispatch

REASONS = {"file-not-in-card", "junk-file-staged", "ignored-file-staged", "data-file-staged", "file-too-large",
           "commit-message-card", "commit-unreadable", "register-tampered", "rule-without-test",
           "verdict-unproven", "verdict-stale",
           "file-outside-root"}  # from the card rows; verdict-unproven by MW-102 (R254); verdict-stale by MW-117 (MW117-D2); file-outside-root by MW-140 (R358)
TESTS_OFF = {"commit_tests": {"on": False}}  # the test gate runs after `commit_files` in the same group


def _task(tmp_path, **over):
    root = make_task(tmp_path, card_paths="", **over)
    work(root, "src/a.py")
    stage(root, "src/a.py")
    return root


def _run(root, tool, tool_input, session="s1"):
    payload = {"session_id": session, "hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input,
               "cwd": str(root)}
    # changed by MW-110 (decision MW110-D2): a launched session carries the launcher's variable, equal to its own id
    return dispatch.run("PreToolUse", "shell", json.dumps(payload),
                        env={"CLAUDE_PROJECT_DIR": str(root), "MKWAY_SESSION_ID": session})


def _entry():
    return {e["name"]: e for e in dispatch.load_manifest(dispatch.ENGINE_DIR)}["commit_files"]


def test_the_manifest_entry_is_the_commit_gate_in_the_shell_group():
    """Catches: a gate that is not run for a shell command, or an entry that is not `commit_files` in the shell group on PreToolUse for Bash and PowerShell, with function `gate_commit:check`, `onFailure: block` and on by default (mw006_e23)."""
    e = _entry()
    assert (e["gate"], e["group"], e["event"], e["matcher"], e["function"], e["onFailure"], e["status"],
            e["default_on"]) == ("commit_files", "shell", "PreToolUse", "Bash|PowerShell", "gate_commit:check",
                                 "block", "on", True)


def test_the_manifest_declares_exactly_the_reasons_the_core_can_return():
    """Catches: a reason the gate returns that the entry does not declare, so the dispatcher would log it as undeclared; the entry declares the ten reason ids of the cards and no other, and says why it blocks (mw006_e23, mw021 e6)."""
    e = _entry()
    assert set(e["reason_ids"]) == REASONS
    assert e["on_failure_reason"].strip()
    assert "\n" not in e["on_failure_reason"]


def test_the_manifest_entry_is_of_the_integrity_class():
    """Catches: an integrity gate that falls out of the integrity class, as the raw manifest names it (mw006_e23)."""
    raw = json.loads((dispatch.ENGINE_DIR / "manifest.json").read_text(encoding="utf-8"))["entries"]
    assert {r["name"]: r for r in raw}["commit_files"]["class"] == "integrity"


def test_the_gate_refuses_through_the_dispatcher_with_its_tag_and_a_switch(tmp_path):
    """Catches: a refusal that reaches the dispatcher untagged or leaves no row; a message that names no card is refused through the real dispatcher with the tag `[mkway commit_files commit-message-card]`, and a row is written (mw006_e23)."""
    root = _task(tmp_path, gates=TESTS_OFF)
    out = json.loads(_run(root, "Bash", {"command": "git commit -m 'add the thing'"}).stdout)["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny"
    assert out["permissionDecisionReason"].startswith("[mkway commit_files commit-message-card] ")
    rows = [r for r in jsonl(root / "mkway" / "state" / "refusals.jsonl") if r["gate"] == "commit_files"]
    assert [(r["reason_id"], r["kind"]) for r in rows] == [("commit-message-card", "refuse")]


def test_a_commit_that_names_its_card_passes_silently_through_the_dispatcher(tmp_path):
    """Checks: the nearest allow of the refusal above, the same commit with the card id in its message, passes silently and is neither blocked nor noisy (mw006_e23)."""
    root = _task(tmp_path, gates=TESTS_OFF)
    res = _run(root, "Bash", {"command": "git commit -m 'CARD-001 add the thing'"})
    assert (res.exit_code, res.stdout) == (0, "")


def test_powershell_is_gated_too(tmp_path):
    """Catches: a second shell that escapes the commit gate; a PowerShell commit that names no card is refused (mw006_e23)."""
    root = _task(tmp_path, gates=TESTS_OFF)
    res = _run(root, "PowerShell", {"command": "git commit -m 'add the thing'"})
    assert json.loads(res.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_the_switch_turns_the_gate_off(tmp_path):
    """Catches: a switch that does not switch, where `gates.commit_files.on: false` leaves the commit that names no card unrefused (mw006_e23)."""
    root = _task(tmp_path, gates={"commit_files": {"on": False}, **TESTS_OFF})
    assert _run(root, "Bash", {"command": "git commit -m 'add the thing'"}).stdout == ""
