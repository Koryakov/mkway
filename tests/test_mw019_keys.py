"""Card MW-019, part 1 (keys): the three outbox keys in the schema, the accessor, the KEYS lines. Synthetic values only."""
import pytest

from _keys_md import section_rows, unquote
from _mw019 import make_root, profile_of  # noqa: F401  (puts the engine on the path)
import profiles
import schema_check

GOOD = {"dir": "outbox", "checkers": ["critic", "verifier"], "id_patterns_file": "tools/ids.txt"}
NOTHING = {"dir": None, "checkers": [], "patterns_file": None}


def _profile(outbox):
    return {"vcs": "none", "bundle": {"root": "mkway"}, "gates": {}, "state": {"dir": "mkway/state"},
            "python": {"command": "python"}, "outbox": outbox}


def _bad_outbox(name, tmp_path):
    """The bad outbox value of one case; the absolute values are built from tmp_path."""
    absolute = tmp_path.as_posix()
    leading = "/" + tmp_path.relative_to(tmp_path.anchor).as_posix()
    values = {
        "dir-absolute": {"dir": absolute},
        "dir-leading-slash": {"dir": leading},
        "dir-climbing": {"dir": "../up"},
        "dir-empty": {"dir": ""},
        "dir-number": {"dir": 3},
        "patterns-absolute": {"id_patterns_file": f"{absolute}/x"},
        "patterns-leading-slash": {"id_patterns_file": f"{leading}/x"},
        "patterns-empty": {"id_patterns_file": ""},
        "checkers-empty": {"checkers": []},
        "checkers-empty-item": {"checkers": [""]},
        "checkers-number-item": {"checkers": [1]},
        "checkers-text": {"checkers": "critic"},
        "unknown-key": {"customer_ids": ["x"]},
    }
    return values[name]


def _junk_outbox(name, tmp_path):
    """The unusable outbox value of one case; the absolute value is built from tmp_path."""
    leading = "/" + tmp_path.relative_to(tmp_path.anchor).as_posix()
    values = {
        "mixed-absolute": {"dir": leading, "checkers": [], "id_patterns_file": 5},
        "mixed-drive": {"dir": tmp_path.as_posix(), "checkers": [], "id_patterns_file": 5},
        "mixed-types": {"dir": 7, "checkers": ["a", ""]},
        "climbing-text": {"dir": "..", "checkers": "critic"},
        "not-an-object": "not an object",
        "none": None,
    }
    return values[name]


BAD_OUTBOX = [
    pytest.param("dir-absolute", "outbox.dir", id="dir-absolute"),
    pytest.param("dir-leading-slash", "outbox.dir", id="dir-leading-slash"),
    pytest.param("dir-climbing", "outbox.dir", id="dir-climbing"),
    pytest.param("dir-empty", "outbox.dir", id="dir-empty"),
    pytest.param("dir-number", "outbox.dir", id="dir-number"),
    pytest.param("patterns-absolute", "outbox.id_patterns_file", id="patterns-absolute"),
    pytest.param("patterns-leading-slash", "outbox.id_patterns_file", id="patterns-leading-slash"),
    pytest.param("patterns-empty", "outbox.id_patterns_file", id="patterns-empty"),
    pytest.param("checkers-empty", "outbox.checkers", id="checkers-empty"),
    pytest.param("checkers-empty-item", "outbox.checkers[0]", id="checkers-empty-item"),
    pytest.param("checkers-number-item", "outbox.checkers[0]", id="checkers-number-item"),
    pytest.param("checkers-text", "outbox.checkers", id="checkers-text"),
    pytest.param("unknown-key", "outbox.customer_ids", id="unknown-key"),
]
JUNK_OUTBOX = [
    pytest.param("mixed-absolute", id="mixed-absolute"),
    pytest.param("mixed-drive", id="mixed-drive"),
    pytest.param("mixed-types", id="mixed-types"),
    pytest.param("climbing-text", id="climbing-text"),
    pytest.param("not-an-object", id="not-an-object"),
    pytest.param("none", id="none"),
]
KEYS_MD_ROWS = [
    pytest.param(24, "outbox.dir", "outbox.dir", (), id="row-24-dir"),
    pytest.param(25, "outbox.id_patterns_file", "outbox.id_patterns_file", ("never holds",), id="row-25-patterns"),
    pytest.param(26, "outbox.checkers", "outbox.checkers", (), id="row-26-checkers"),
    pytest.param(30, "customer_ids", "outbox.id_patterns_file",
                 ("`outbox.id_patterns_file`", "folds"), id="row-30-folded"),
]


@pytest.mark.parametrize("name, key", BAD_OUTBOX)
def test_the_schema_takes_the_outbox_keys_and_refuses_bad_values(name, key, tmp_path):
    """Catches: a key the profile can set with a value the gate cannot use, or a group that still refuses every key (E1: outbox.dir and outbox.id_patterns_file are repo-relative paths, outbox.checkers a non-empty list of non-empty strings; an absolute or climbing path, an empty list, an empty or non-string item, a string for the list and a key the schema does not know are refused with the key path in the error; the empty group stays valid)."""
    assert schema_check.check(_profile(GOOD)) == []
    assert schema_check.check(_profile({})) == []
    assert schema_check.check(_profile({"dir": "outbox"})) == []
    errors = schema_check.check(_profile(_bad_outbox(name, tmp_path)))
    assert any(e.split(":", 1)[0] == key for e in errors), (name, errors)


@pytest.mark.parametrize("name", JUNK_OUTBOX)
def test_the_accessor_defaults_and_tolerates_a_bad_value(name, tmp_path):
    """Checks: the accessor gives the defaults and tolerates a bad value (E1: profiles.outbox_settings gives dir and patterns_file as posix repo-relative paths and checkers as a list; every missing or unusable value is none or an empty list, so a gate never fails on a bad key and a profile that names no checker has no valid check)."""
    assert profiles.outbox_settings({}) == NOTHING
    assert profiles.outbox_settings({"outbox": {}}) == NOTHING
    got = profiles.outbox_settings({"outbox": {"dir": "out\\box/", "checkers": ["critic"],
                                               "id_patterns_file": "tools\\ids.txt"}})
    assert got == {"dir": "out/box", "checkers": ["critic"], "patterns_file": "tools/ids.txt"}
    junk = _junk_outbox(name, tmp_path)
    assert profiles.outbox_settings({"outbox": junk}) == NOTHING, junk
    assert profiles.outbox_settings("not a profile") == NOTHING


@pytest.mark.parametrize("number, key, path, extras", KEYS_MD_ROWS)
def test_keys_md_has_a_line_for_each_outbox_key(number, key, path, extras):
    """Checks: rows 24, 25, 26 and 30 of the profile keys are in schema now, each with the schema path it maps to and a reason that states the default; row 30 says the key folds into outbox.id_patterns_file; the engine ships no patterns (E2)."""
    rows = {int(r[0]): r for r in section_rows("Profile keys")}
    _num, name, verdict, schema_path, reason = rows[number]
    assert unquote(name) == key
    assert verdict == "in schema now"
    assert unquote(schema_path) == path
    assert "default" in reason.lower()
    assert all(text in reason for text in extras)
