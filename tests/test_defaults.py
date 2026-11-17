"""Engine defaults (card MW-001, rows E17-E18).

The 31 engine-default keys of the port map (section 3.2): each is in engine/defaults.json with its value, or marked in
engine/KEYS.md as «later (...)» or «not established (...)», never both.
"""
import json
from pathlib import Path

import pytest

from _keys_md import section_rows, unquote

REPO = Path(__file__).resolve().parents[1]
DEFAULTS = REPO / "engine" / "defaults.json"

EXPECTED = {
    "bash_speed_guard": ["marker", "sleep_limit_seconds"],
    "quality_gate": ["operators", "compare", "max_mutants", "budget_seconds", "workers", "cpu_reserve", "temp_dir",
                     "max_equivalent", "mutant_timeout_min", "mutant_timeout_factor", "listed_max",
                     "equivalent_prefix", "acceptance_heading"],
    "st_tests": ["budget_seconds", "startup_margin_seconds", "shared_run_max_cmdline"],
    "outbox_check": ["check_suffix", "artifact_hosts", "write_tools", "shell_tools", "lines"],
    "decision_search": ["log_env", "cache_env", "noise_dir_names", "noise_files", "noise_suffixes", "formats",
                        "language", "texts"],
    "lock_gate": ["git_builtins"],  # MW-003 close-fix 8 (R90): an engine constant, not from the port map
    "locks": ["targets"],  # MW-018 (E10): the engine default lock target `inbox`; the key is in the schema too
    "wake": ["mode", "deadline_seconds", "poll_seconds"],  # MW-078: the inbox waiter; the keys are in the schema too
    "paths": ["outside_writable"],  # MW-103 (R255b), R274-D1: the default writable folders outside the repository, for every session; in the schema too
}
NL_LATER = "later (natural-language content; needs an owner read)"
KEYS = [pytest.param(c, k, id=f"{c}.{k}") for c, keys in EXPECTED.items() for k in keys]


def _defaults():
    data = json.loads(DEFAULTS.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_")}


def _marks():
    return {(unquote(r[0]), unquote(r[1])): r[2] for r in section_rows("Engine defaults")}


@pytest.mark.parametrize("config, key", KEYS)
def test_every_default_key_is_placed_once(config, key):
    """Checks: the key is in defaults.json or marked later or not established in KEYS.md, never both (E17)."""
    # the 31 port-map keys and the engine constant of MW-003 close-fix 8, each in defaults.json or marked in KEYS.md
    expected = {(c, k) for c, keys in EXPECTED.items() for k in keys}
    assert len(expected) == 37  # changed by MW-018: `locks.targets`; MW-078: the three `wake` keys; MW-103: `leads.outside_writable`
    defaults = _defaults()
    in_json = {(c, k) for c, group in defaults.items() for k in group}
    marks = _marks()
    assert set(marks) == expected, "KEYS.md must list each of the 32 keys once"
    assert in_json <= expected, sorted(in_json - expected)
    verdict = marks[(config, key)]
    assert ((config, key) in in_json) == (verdict == "in defaults.json"), key
    assert verdict == "in defaults.json" or verdict.startswith(("later (", "not established (")), key


MAP_TYPES = {  # the port map's types for the 23 keys of the 18 configs (section 3.2); the 8 decision_search types are taken from the pin values
    ("bash_speed_guard", "marker"): str, ("bash_speed_guard", "sleep_limit_seconds"): int,
    ("quality_gate", "operators"): list, ("quality_gate", "compare"): dict,
    ("quality_gate", "max_mutants"): int, ("quality_gate", "budget_seconds"): int, ("quality_gate", "workers"): int,
    ("quality_gate", "cpu_reserve"): int, ("quality_gate", "max_equivalent"): int,
    ("quality_gate", "mutant_timeout_min"): int, ("quality_gate", "mutant_timeout_factor"): int,
    ("quality_gate", "listed_max"): int, ("quality_gate", "temp_dir"): type(None),
    ("quality_gate", "equivalent_prefix"): str, ("quality_gate", "acceptance_heading"): str,
    ("st_tests", "budget_seconds"): int, ("st_tests", "startup_margin_seconds"): int,
    ("st_tests", "shared_run_max_cmdline"): int,
    ("outbox_check", "check_suffix"): str, ("outbox_check", "artifact_hosts"): list,
    ("outbox_check", "write_tools"): list, ("outbox_check", "shell_tools"): list, ("outbox_check", "lines"): list,
    ("decision_search", "log_env"): str, ("decision_search", "cache_env"): str,
    ("decision_search", "noise_dir_names"): list, ("decision_search", "noise_files"): list,
    ("decision_search", "noise_suffixes"): list, ("decision_search", "formats"): dict,
    ("decision_search", "language"): dict, ("decision_search", "texts"): dict,
    ("lock_gate", "git_builtins"): list, ("locks", "targets"): list,
    ("wake", "mode"): str, ("wake", "deadline_seconds"): int, ("wake", "poll_seconds"): int,
    ("paths", "outside_writable"): list,
}


@pytest.mark.parametrize("config, key", KEYS)
def test_defaults_read_at_pin_have_map_types(config, key):
    """Checks: after the pin read the key is not not-established, and a value in defaults.json has the map type (E24)."""
    assert set(MAP_TYPES) == {(c, k) for c, keys in EXPECTED.items() for k in keys}
    assert not [k for k, v in _marks().items() if v.startswith("not established")]
    verdict = _marks()[(config, key)]
    assert not verdict.startswith("not established")
    assert verdict != "in defaults.json" or key in _defaults().get(config, {}), (config, key)
    value = _defaults().get(config, {}).get(key)
    assert verdict != "in defaults.json" or type(value) is MAP_TYPES[(config, key)], (config, key)


@pytest.mark.parametrize("key", ["language", "texts"])
def test_natural_language_defaults_are_later(key):
    """Checks: `language` and `texts` are not copied; they are «later (natural-language content; needs an owner read)» (E18)."""
    assert _marks()[("decision_search", key)] == NL_LATER
    assert key not in _defaults().get("decision_search", {})
