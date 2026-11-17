"""Card MW-134 (ruling R348a): the default of `tests.red_proof.decision_pattern` lives in one place, `profiles.red_proof_decision_pattern`,
so every caller sees the same pattern. A key that is present stays as written, an empty one included (an explicit off); a missing key
falls back to the ledger's id form when the root has a ledger file, and to the empty pattern when it has none. Synthetic roots only."""
import re
from pathlib import Path

import _engine  # noqa: F401  (puts the engine folder on the import path)
import ledger
import profiles

KEYS = Path(__file__).resolve().parents[2] / "engine" / "KEYS.md"
KEY = "tests.red_proof.decision_pattern"


def profile(red_proof=None, decision_row=None) -> dict:
    out = {"vcs": "none", "bundle": {"root": "mkway"}, "gates": {}, "state": {"dir": "mkway/state"},
           "python": {"command": "python"}, "tests": {}}
    if red_proof is not None:
        out["tests"]["red_proof"] = red_proof
    if decision_row is not None:
        out["ids"] = {"decision_row": decision_row}
    return out


def with_ledger(tmp_path, given):
    """A root that has a ledger file (one row), the profile `given`."""
    ledger.add(tmp_path, given, card="C", topic="t", quote="q", source="s", by="session:x")
    return tmp_path


def test_a_missing_key_in_a_root_with_a_ledger_takes_the_ledgers_default_id_form(tmp_path):
    """Catches: a root with a ledger and no key, where no commit message can name a decision (the live case)."""
    given = profile()
    root = with_ledger(tmp_path, given)
    assert profiles.red_proof_decision_pattern(given, root) == ledger.DEFAULT_ID


def test_a_missing_key_in_a_root_with_a_ledger_takes_the_decision_row_pattern_of_the_profile(tmp_path):
    """Checks: `ids.decision_row`, the form of the root's own decision ids, comes before the ledger's default form."""
    given = profile(decision_row=r"DEC-\d+")
    root = with_ledger(tmp_path, given)
    assert profiles.red_proof_decision_pattern(given, root) == r"DEC-\d+"


def test_a_missing_key_in_a_root_with_no_ledger_file_is_empty(tmp_path):
    """Checks: with no ledger file there is nothing to name, so the pattern is empty as before."""
    assert profiles.red_proof_decision_pattern(profile(), tmp_path) == ""


def test_a_present_key_wins_over_the_default(tmp_path):
    """Catches: a default that overrides the pattern the profile wrote."""
    given = profile(red_proof={"decision_pattern": "DEC-[0-9]+"})
    root = with_ledger(tmp_path, given)
    assert profiles.red_proof_decision_pattern(given, root) == "DEC-[0-9]+"


def test_a_present_empty_key_stays_off_in_a_root_with_a_ledger(tmp_path):
    """Catches: an explicit empty pattern (the owner's off) read as missing and replaced by the default."""
    given = profile(red_proof={"decision_pattern": ""})
    root = with_ledger(tmp_path, given)
    assert profiles.red_proof_decision_pattern(given, root) == ""


def test_the_pattern_with_no_root_is_what_the_profile_says_as_before():
    """Checks: a caller that has no root (the older call form) sees the key or the empty string."""
    assert profiles.red_proof_decision_pattern(profile()) == ""
    assert profiles.red_proof_decision_pattern(profile(red_proof={"decision_pattern": "X-[0-9]+"})) == "X-[0-9]+"


def test_the_keys_row_of_the_decision_pattern_states_the_default_and_the_whole_id_rule():
    """Checks: KEYS.md names the order (key, ids.decision_row with a ledger, the ledger's default form, empty with no ledger), that an empty key stays off, and that ids match whole (R348a 4)."""
    (row,) = [line for line in KEYS.read_text(encoding="utf-8").splitlines() if line.startswith(f"| `{KEY}`")]
    flat = " ".join(row.split())
    for words in ("ids.decision_row", "D-", "ledger", "stays off", "whole"):
        assert words in flat, words
    assert not re.search(r"default empty \(not in `defaults.json`\)", flat)
