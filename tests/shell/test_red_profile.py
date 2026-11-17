"""Card MW-072: the profile switch `tests.red_proof.mode`, and the manifest's four reason ids."""
import json
from pathlib import Path

import pytest

import _engine  # noqa: F401  (puts the engine folder on the import path)
import profiles
import schema_check

MANIFEST = Path(__file__).resolve().parents[2] / "engine" / "manifest.json"
IDS = {"red-not-proven", "red-ids-still-red", "red-not-recorded", "test-without-red-proof"}


def profile(**tests):
    return {"vcs": "none", "bundle": {"root": "mkway"}, "gates": {}, "state": {"dir": "mkway/state"},
            "python": {"command": "python"}, "tests": tests}


@pytest.mark.parametrize("mode", ["trip", "watch"])
def test_the_mode_switch_accepts_trip_and_watch(mode):
    """Checks: the two modes of the gate are in the schema."""
    assert schema_check.check(profile(red_proof={"mode": mode})) == []


@pytest.mark.parametrize("mode", ["off", ""])
def test_the_mode_switch_rejects_other_values(mode):
    """Catches: a switch that takes any word, so a typo would turn the gate off without a sign."""
    errors = schema_check.check(profile(red_proof={"mode": mode}))
    assert any("tests.red_proof.mode" in e for e in errors), errors


@pytest.mark.parametrize("given, expected", [({}, "trip"), ({"tests": {"red_proof": {"mode": "watch"}}}, "watch"),
                                              ({"tests": {"red_proof": {"mode": "off"}}}, "trip"),
                                              ({"tests": {"red_proof": 3}}, "trip")])
def test_the_mode_defaults_to_trip_and_an_unusable_value_is_trip(given, expected):
    """Checks: a missing or unusable switch is trip, so the gate never turns itself off."""
    assert profiles.red_proof_mode(given) == expected


def test_the_manifest_declares_the_four_reason_ids():
    """Catches: a reason id the gate returns that the manifest does not declare, which the dispatcher refuses to load."""
    entries = json.loads(MANIFEST.read_text(encoding="utf-8"))["entries"]
    gate = next(e for e in entries if e["name"] == "commit_tests")
    assert IDS <= set(gate["reason_ids"])


# ---- card MW-090: the key `tests.red_proof.decision_pattern` and the five case_map reason ids ----------------------------
CASE_MAP_IDS = {"case-map-no-decision", "case-map-unknown-left", "case-map-unknown-right", "case-map-merge",
                "case-map-malformed"}
README = Path(__file__).resolve().parents[2] / "README.md"


@pytest.mark.parametrize("value", ["", "DEC-[0-9]+"], ids=["empty", "pattern"])
def test_the_decision_pattern_key_accepts_a_string(value):
    """Checks: the pattern of the decisions a commit message may name is a string, and the empty string is allowed (no decision)."""
    assert schema_check.check(profile(red_proof={"decision_pattern": value})) == []


@pytest.mark.parametrize("value", [3, True, ["x"]], ids=["number", "bool", "list"])
def test_the_decision_pattern_key_rejects_a_value_that_is_not_a_string(value):
    """Catches: a pattern key that takes any value, so a typo would hide behind the fail-closed default."""
    errors = schema_check.check(profile(red_proof={"decision_pattern": value}))
    assert any("tests.red_proof.decision_pattern" in e and "string" in e for e in errors), errors


@pytest.mark.parametrize("given, expected", [
    ({}, ""), ({"tests": {"red_proof": {"decision_pattern": "DEC-[0-9]+"}}}, "DEC-[0-9]+"),
    ({"tests": {"red_proof": {"decision_pattern": 3}}}, ""), ({"tests": {"red_proof": 3}}, ""),
    ({"tests": {"red_proof": {"mode": "watch"}}}, "")], ids=["missing", "string", "not_a_string", "not_an_object", "other_key"])
def test_the_decision_pattern_defaults_to_empty_and_an_unusable_value_is_empty(given, expected):
    """Checks: a missing or unusable key reads as the empty pattern, which is no decision (fail closed)."""
    assert profiles.red_proof_decision_pattern(given) == expected


@pytest.mark.engine_repo
def test_the_readme_names_the_decision_pattern_key_and_not_one_setting():
    """Catches: a README that still says the red proof has one setting after the second key was added."""
    text = " ".join(README.read_text(encoding="utf-8").split())  # a sentence may break across lines
    assert "`tests.red_proof.decision_pattern`" in text
    assert "`tests.red_proof` has one setting" not in text


def test_the_manifest_declares_the_five_case_map_reason_ids():
    """Catches: a case_map reason id the gate returns that the manifest does not declare, which the dispatcher logs as undeclared."""
    entries = json.loads(MANIFEST.read_text(encoding="utf-8"))["entries"]
    gate = next(e for e in entries if e["name"] == "commit_tests")
    assert CASE_MAP_IDS <= set(gate["reason_ids"])
