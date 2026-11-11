"""Card MW-019, part 1 (keys): the three outbox keys in the schema, the accessor, the KEYS lines. Synthetic values only."""
import pytest

from _keys_md import section_rows, unquote
from _mw019 import make_root, profile_of  # noqa: F401  (puts the engine on the path)
import profiles
import schema_check

GOOD = {"dir": "outbox", "checkers": ["critic", "verifier"], "id_patterns_file": "tools/ids.txt"}


def _profile(outbox):
    return {"vcs": "none", "bundle": {"root": "mkway"}, "gates": {}, "state": {"dir": "mkway/state"},
            "python": {"command": "python"}, "outbox": outbox}


def test_the_schema_takes_the_outbox_keys_and_refuses_bad_values():
    """E1: `outbox.dir` and `outbox.id_patterns_file` are repo-relative paths, `outbox.checkers` is a non-empty list of
    non-empty strings; an absolute or climbing path, an empty list, an empty or non-string item, a string for the list
    and a key the schema does not know are refused with the key path in the error; the empty group stays valid.
    Catches: a key the profile can set with a value the gate cannot use, or a group that still refuses every key."""
    assert schema_check.check(_profile(GOOD)) == []
    assert schema_check.check(_profile({})) == []
    assert schema_check.check(_profile({"dir": "outbox"})) == []
    bad = [({"dir": "/abs"}, "outbox.dir"), ({"dir": "../up"}, "outbox.dir"), ({"dir": ""}, "outbox.dir"),
           ({"dir": 3}, "outbox.dir"), ({"id_patterns_file": "C:/x"}, "outbox.id_patterns_file"),
           ({"id_patterns_file": ""}, "outbox.id_patterns_file"), ({"checkers": []}, "outbox.checkers"),
           ({"checkers": [""]}, "outbox.checkers[0]"), ({"checkers": [1]}, "outbox.checkers[0]"),
           ({"checkers": "critic"}, "outbox.checkers"), ({"customer_ids": ["x"]}, "outbox.customer_ids")]
    for value, key in bad:
        errors = schema_check.check(_profile(value))
        assert any(e.split(":", 1)[0] == key for e in errors), (value, errors)


def test_the_accessor_defaults_and_tolerates_a_bad_value():
    """E1: `profiles.outbox_settings` gives `dir` and `patterns_file` as posix repo-relative paths and `checkers` as a
    list; every missing or unusable value is none or an empty list, so a gate never fails on a bad key and a profile
    that names no checker has no valid check. Catches: a default folder or a default checker the engine invents."""
    assert profiles.outbox_settings({}) == {"dir": None, "checkers": [], "patterns_file": None}
    assert profiles.outbox_settings({"outbox": {}}) == {"dir": None, "checkers": [], "patterns_file": None}
    got = profiles.outbox_settings({"outbox": {"dir": "out\\box/", "checkers": ["critic"],
                                               "id_patterns_file": "tools\\ids.txt"}})
    assert got == {"dir": "out/box", "checkers": ["critic"], "patterns_file": "tools/ids.txt"}
    for junk in ({"dir": "/abs", "checkers": [], "id_patterns_file": 5}, {"dir": 7, "checkers": ["a", ""]},
                 {"dir": "..", "checkers": "critic"}, "not an object", None):
        got = profiles.outbox_settings({"outbox": junk})
        assert got == {"dir": None, "checkers": [], "patterns_file": None}, junk
    assert profiles.outbox_settings("not a profile") == {"dir": None, "checkers": [], "patterns_file": None}


@pytest.mark.parametrize("number, key, path", [
    (24, "outbox.dir", "outbox.dir"), (25, "outbox.id_patterns_file", "outbox.id_patterns_file"),
    (26, "outbox.checkers", "outbox.checkers"), (30, "customer_ids", "outbox.id_patterns_file")])
def test_keys_md_has_a_line_for_each_outbox_key(number, key, path):
    """E2: rows 24, 25, 26 and 30 of the profile keys are «in schema now» with the schema path they map to and a reason
    that states the default; row 30 says the key folds into `outbox.id_patterns_file`; the engine ships no patterns.
    Catches: a key in the schema that KEYS.md still calls later, or a folded key with no trace of where it went."""
    rows = {int(r[0]): r for r in section_rows("Profile keys")}
    _num, name, verdict, schema_path, reason = rows[number]
    assert unquote(name) == key and verdict == "in schema now" and unquote(schema_path) == path
    assert "default" in reason.lower()
    if number == 30:
        assert "`outbox.id_patterns_file`" in reason and "folds" in reason
    if number == 25:
        assert "never holds" in reason
