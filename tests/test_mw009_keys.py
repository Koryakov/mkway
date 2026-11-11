"""Deletes (card MW-009), part P1: the profile keys `delete.max_backup_mb` and `delete.sql_allowed`, their defaults
and their KEYS.md lines. Synthetic values only."""
import copy
import json

from _engine import FIXTURES, REPO, make_profile
from _keys_md import section_rows, unquote
import profiles
import schema_check

NOW = "in schema now"


def _good():
    return json.loads((FIXTURES / "profile_depth2.json").read_text(encoding="utf-8"))


def test_delete_keys_are_in_the_schema():
    """E1 (part 1): the schema takes `delete.max_backup_mb` (a number above 0) and `delete.sql_allowed` (a boolean);
    an unknown key under `delete` is profile-invalid. Catches: a key the gate reads that the schema refuses, or a
    value that would break the size check."""
    good = _good()
    full = dict(good, delete={"max_backup_mb": 100, "sql_allowed": True})
    assert schema_check.check(full) == []
    assert schema_check.check(dict(good, delete={})) == []
    assert schema_check.check(dict(good, delete={"max_backup_mb": 0.5})) == []
    for bad in ({"max_backup_mb": 0}, {"max_backup_mb": -1}, {"max_backup_mb": "big"}, {"max_backup_mb": True},
                {"sql_allowed": "yes"}, {"sql_allowed": 1}, {"nope": 1}):
        errors = schema_check.check(dict(good, delete=copy.deepcopy(bad)))
        assert errors and all(e.startswith("delete") for e in errors), (bad, errors)


def test_delete_defaults_and_overrides():
    """E2 (part 1): with no `delete` in the profile the settings are the defaults: 5120 MB and SQL not allowed; the
    profile's own values replace them; an unusable value falls back to the default, so a gate never crashes on a bad
    key. Catches: a default hard-coded in the gate, or an override that is ignored."""
    default = {"max_backup_mb": 5120, "sql_allowed": False}
    assert profiles.delete_settings(make_profile()) == default
    assert profiles.delete_settings(None) == default
    assert profiles.delete_settings(make_profile(delete={})) == default
    own = make_profile(delete={"max_backup_mb": 64, "sql_allowed": True})
    assert profiles.delete_settings(own) == {"max_backup_mb": 64, "sql_allowed": True}
    assert profiles.delete_settings(make_profile(delete={"max_backup_mb": 2.5}))["max_backup_mb"] == 2.5
    assert profiles.delete_settings(make_profile(delete={"sql_allowed": True})) == {
        "max_backup_mb": 5120, "sql_allowed": True}
    for bad in ({"max_backup_mb": 0, "sql_allowed": "yes"}, {"max_backup_mb": True, "sql_allowed": 1},
                {"max_backup_mb": -3}, {"max_backup_mb": "9"}, "text", []):
        assert profiles.delete_settings(make_profile(delete=bad)) == default, bad
    assert profiles.validate(own) == []  # the profile above, with its own `delete` values


def test_delete_keys_are_lines_of_keys_md_with_their_defaults():
    """E3 (part 1): each key is a line of the «Added keys» table of KEYS.md, «in schema now» with its own schema path
    and its default named. Catches: a key with no default written down, which would make the default a hard-coded
    value that nobody can find."""
    rows = {unquote(r[0]): r for r in section_rows("Added keys")}
    for key in ("delete.max_backup_mb", "delete.sql_allowed"):
        assert rows[key][1:3] == [NOW, f"`{key}`"], key
    assert "`5120`" in rows["delete.max_backup_mb"][3]
    assert "`false`" in rows["delete.sql_allowed"][3]
    assert (REPO / "engine" / "KEYS.md").is_file()
