"""Deletes (card MW-009), part P1: the profile keys `delete.max_backup_mb` and `delete.sql_allowed` and their defaults.
Synthetic values only. The KEYS.md line check (E3) is a document check and moved out (card MW-064, case_map.md)."""
import copy
import json

import pytest

from _engine import FIXTURES, make_profile
import profiles
import schema_check


def _good():
    return json.loads((FIXTURES / "profile_depth2.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "bad",
    [
        pytest.param({"max_backup_mb": 0}, id="zero-mb"),
        pytest.param({"max_backup_mb": -1}, id="negative-mb"),
        pytest.param({"max_backup_mb": "big"}, id="text-mb"),
        pytest.param({"max_backup_mb": True}, id="bool-mb"),
        pytest.param({"sql_allowed": "yes"}, id="text-sql"),
        pytest.param({"sql_allowed": 1}, id="int-sql"),
        pytest.param({"nope": 1}, id="unknown-key"),
    ],
)
def test_delete_keys_are_in_the_schema(bad):
    """Catches: a key the gate reads that the schema refuses, or a value that would break the size check (E1, part 1)."""
    good = _good()
    full = dict(good, delete={"max_backup_mb": 100, "sql_allowed": True})
    assert schema_check.check(full) == []
    assert schema_check.check(dict(good, delete={})) == []
    assert schema_check.check(dict(good, delete={"max_backup_mb": 0.5})) == []
    errors = schema_check.check(dict(good, delete=copy.deepcopy(bad)))
    assert errors, (bad, errors)
    assert all(e.startswith("delete") for e in errors), (bad, errors)


@pytest.mark.parametrize(
    "bad",
    [
        pytest.param({"max_backup_mb": 0, "sql_allowed": "yes"}, id="zero-mb-text-sql"),
        pytest.param({"max_backup_mb": True, "sql_allowed": 1}, id="bool-mb-int-sql"),
        pytest.param({"max_backup_mb": -3}, id="negative-mb"),
        pytest.param({"max_backup_mb": "9"}, id="text-mb"),
        pytest.param("text", id="text-profile"),
        pytest.param([], id="list-profile"),
    ],
)
def test_delete_defaults_and_overrides(bad):
    """Checks: the defaults apply, the profile's own values replace them, and an unusable value falls back to the default, so a gate never crashes on a bad key (E2, part 1)."""
    default = {"max_backup_mb": 5120, "sql_allowed": False}
    assert profiles.delete_settings(make_profile()) == default
    assert profiles.delete_settings(None) == default
    assert profiles.delete_settings(make_profile(delete={})) == default
    own = make_profile(delete={"max_backup_mb": 64, "sql_allowed": True})
    assert profiles.delete_settings(own) == {"max_backup_mb": 64, "sql_allowed": True}
    assert profiles.delete_settings(make_profile(delete={"max_backup_mb": 2.5}))["max_backup_mb"] == 2.5
    assert profiles.delete_settings(make_profile(delete={"sql_allowed": True})) == {
        "max_backup_mb": 5120, "sql_allowed": True}
    assert profiles.delete_settings(make_profile(delete=bad)) == default
    assert profiles.validate(own) == []  # the profile above, with its own `delete` values

