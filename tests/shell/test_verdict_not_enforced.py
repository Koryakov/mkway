"""Card MW-068 (ruling R179), layer shell: where `outbox.checkers` is missing the close passes and says so, in the close
output, in the verdict record and at the lead's Stop; a fresh install writes the key. Real files, synthetic sessions."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/: the shared helpers and `_engine`
from _engine import agent_file, gate_call, task_root  # noqa: E402
import gate_outbox  # noqa: E402
import leads  # noqa: E402
import profiles  # noqa: E402
import verdicts  # noqa: E402

NODE = "tests/test_a.py::test_one"
WARNING = "blind verdict not enforced: outbox.checkers missing in profile"


def _root(tmp_path, **over):
    root = task_root(tmp_path, **over)
    (root / "tests").mkdir()
    (root / "tests" / "test_a.py").write_text("def test_one():\n    pass\n", encoding="utf-8")
    return root


def _stop(root, session):
    return gate_call(gate_outbox.check, root, tool=None, event="Stop", session=session, tool_input=None)


def _lead(root, session):
    profile = json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))
    leads.register_lead(profiles.shared_state_dir(root, profile), session)


def test_a_missing_key_lets_a_card_with_no_verdict_file_pass_the_shell_check(tmp_path):
    """Catches: the shell refusing `verdict-missing` (or `verdict-unproven`) where the profile names no checker."""
    root = _root(tmp_path)
    assert verdicts.problem(root, "CARD-001", [NODE], "", root / "mkway" / "state", []) is None


def test_a_set_key_refuses_the_same_card(tmp_path):
    """Catches: a card with the key set and no verdict file refused as verdict-missing, the nearest deny of the test above."""
    root = _root(tmp_path)
    # only the key differs from the test above
    agent_file(root, "critic", "Read, Grep")  # MW-071, decision: R180: the checker needs a read-only definition
    assert verdicts.problem(root, "CARD-001", [NODE], "", root / "mkway" / "state", ["critic"])[0] == "verdict-missing"


def test_the_warning_is_for_a_card_naming_a_node_and_a_profile_with_no_checker():
    """Catches: no warning where the check is not enforced, or a warning where it is."""
    assert verdicts.warning([NODE], []) == WARNING
    assert verdicts.warning([NODE], ["critic"]) is None
    assert verdicts.warning([], []) is None


def test_the_verdict_record_names_the_card_and_the_warning(tmp_path):
    """Catches: a close that passes unenforced and leaves no record of it."""
    root = _root(tmp_path)
    profile = json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))
    verdicts.record_not_enforced(root, profile, "CARD-001")
    rows = [json.loads(x) for x in (root / "mkway" / "state" / "outbox_checks.jsonl").read_text(encoding="utf-8").splitlines()]
    (found,) = [r for r in rows if r.get("kind") == "verdict-not-enforced"]
    assert (found["card"], found["text"]) == ("CARD-001", WARNING)


def test_a_lead_is_warned_at_stop_while_the_key_is_missing(tmp_path):
    """Checks: the lead is warned at its Stop while the key is missing."""
    root = _root(tmp_path)
    _lead(root, "lead-1")
    verdict = _stop(root, "lead-1")
    assert (verdict.kind, verdict.reason_id, WARNING in verdict.message) == ("warn", "verdict-not-enforced", True)
    # it repeats at every Stop
    verdict = _stop(root, "lead-1")
    assert (verdict.kind, verdict.reason_id, WARNING in verdict.message) == ("warn", "verdict-not-enforced", True)


def test_a_session_that_is_no_lead_is_not_warned_at_stop(tmp_path):
    """Catches: the warning shown to every session, not the lead's."""
    root = _root(tmp_path)
    assert _stop(root, "builder-1").kind == "allow"


def test_the_lead_warning_stops_when_the_key_is_set(tmp_path):
    """Checks: the nearest allow of the lead's warning, only the key differs, so no warning outlives the key."""
    root = _root(tmp_path, outbox={"checkers": ["critic"]})
    _lead(root, "lead-1")
    assert _stop(root, "lead-1").kind == "allow"


def test_the_lead_warning_stops_when_the_check_is_off(tmp_path):
    """Catches: a warning about a check the profile switched off."""
    root = _root(tmp_path, cards={"verdicts": "off"})
    _lead(root, "lead-1")
    assert _stop(root, "lead-1").kind == "allow"
