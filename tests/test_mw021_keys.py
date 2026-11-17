"""Card MW-021, rows E1 to E3: the profile keys `rules.cards` and `rules.test_for`, their defaults, the schema, the KEYS
lines and the manifest reason. Synthetic values only."""
import copy
import json

import pytest

from _engine import FIXTURES, REPO, make_profile
from _keys_md import section_rows, unquote
import profiles
import schema_check


def _good():
    return json.loads((FIXTURES / "profile_depth2.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("bad", [
    pytest.param({"cards": []}, id="cards-empty"),
    pytest.param({"cards": [""]}, id="cards-empty-glob"),
    pytest.param({"cards": "rules/*.md"}, id="cards-not-list"),
    pytest.param({"cards": [3]}, id="cards-not-string"),
    pytest.param({"test_for": "tests/one.py"}, id="test-for-no-id"),
    pytest.param({"test_for": ""}, id="test-for-empty"),
    pytest.param({"test_for": 5}, id="test-for-number"),
    pytest.param({"nope": 1}, id="unknown-key"),
])
def test_the_schema_takes_the_two_rules_keys(bad):
    """Catches: a test path with no id in it (every card would share one test file) or an empty glob list that matches nothing. E1"""
    # rules.cards is a non-empty list of non-empty globs; rules.test_for is a string that holds {id}; an unknown key under
    # rules is profile-invalid.
    good = _good()
    full = dict(good, rules={"cards": ["rules/*.md"], "test_for": "tests/rules/{id}/test_{id}.py"})
    assert schema_check.check(full) == []
    assert schema_check.check(dict(good, rules={})) == []
    errors = schema_check.check(dict(good, rules=copy.deepcopy(bad)))
    assert errors
    assert all(e.startswith("rules") for e in errors), (bad, errors)


@pytest.mark.parametrize("bad", [
    pytest.param({"cards": [], "test_for": "x"}, id="cards-empty"),
    pytest.param({"cards": "a", "test_for": 5}, id="wrong-types"),
    pytest.param({"cards": [""], "test_for": "no id"}, id="empty-glob-no-id"),
    pytest.param("text", id="text"),
    pytest.param([], id="empty-list"),
])
def test_the_settings_default_to_off_and_tolerate_a_bad_value(bad):
    """Checks: the settings default to off with no usable rules, and a bad value falls back to off. E2"""
    # with no rules the settings are empty and the check is off; the check is on only when both keys are usable; an
    # unusable value falls back to off, so a gate never fails on a bad key.
    import rules
    off = {"cards": [], "test_for": None}
    assert rules.settings(make_profile()) == off
    assert rules.settings(None) == off
    assert rules.settings(make_profile(rules={})) == off
    own = make_profile(rules={"cards": ["a/*.md"], "test_for": "t/{id}.py"})
    assert rules.settings(own) == {"cards": ["a/*.md"], "test_for": "t/{id}.py"}
    assert rules.active(own)
    assert not rules.active(make_profile(rules={"cards": ["a/*.md"]}))
    assert not rules.active(make_profile(rules={"test_for": "t/{id}.py"}))
    assert not rules.active(make_profile(rules=bad)), bad
    assert profiles.validate(own) == []


@pytest.mark.parametrize("key", [
    pytest.param("rules.cards", id="cards"),
    pytest.param("rules.test_for", id="test-for"),
])
def test_keys_md_has_a_line_for_each_key_with_its_default(key):
    """Checks: each key has a line in the Added keys table of KEYS.md that names its default. E3"""
    # both keys are lines of the Added keys table of KEYS.md, in schema now with their own schema path, the default named
    # and the card.
    rows = {unquote(r[0]): r for r in section_rows("Added keys")}
    assert rows[key][1:3] == ["in schema now", f"`{key}`"], key
    assert "none" in rows[key][3], key
    assert "MW-021" in rows[key][4], key
    assert "{id}" in rows["rules.test_for"][3] + rows["rules.test_for"][4]
    assert (REPO / "engine" / "KEYS.md").is_file()
