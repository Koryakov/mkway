"""Card MW-020, rows E1 and E2: the profile keys `deliverables.paths` and `deliverables.require_base`, their defaults,
the schema and the KEYS lines. Synthetic values only."""
import copy
import json

from _engine import FIXTURES, REPO, make_profile
from _keys_md import section_rows, unquote
import profiles
import schema_check


def _good():
    return json.loads((FIXTURES / "profile_depth2.json").read_text(encoding="utf-8"))


def test_the_schema_takes_the_two_deliverables_keys():
    """E1: both keys are non-empty lists of non-empty globs; a string for a list, an empty list, an empty or non-string
    item and a key the schema does not know are refused with the key path in the error; the empty group is valid.
    Catches: a key a profile can set with a value the command cannot use."""
    good = _good()
    full = dict(good, deliverables={"paths": ["out/*.md"], "require_base": ["out/base-*.md"]})
    assert schema_check.check(full) == []
    assert schema_check.check(dict(good, deliverables={})) == []
    assert schema_check.check(dict(good, deliverables={"paths": ["out/*.md"]})) == []
    for bad in ({"paths": []}, {"paths": [""]}, {"paths": "out/*.md"}, {"paths": [3]}, {"require_base": []},
                {"require_base": [""]}, {"require_base": "x"}, {"nope": 1}):
        errors = schema_check.check(dict(good, deliverables=copy.deepcopy(bad)))
        assert errors and all(e.startswith("deliverables") for e in errors), (bad, errors)


def test_the_accessor_defaults_to_none_and_tolerates_a_bad_value():
    """E1: `profiles.deliverable_settings` gives two lists; a missing or unusable value is an empty list, so a command
    never fails on a bad key and the engine invents no path. Catches: a default folder the engine makes up."""
    off = {"paths": [], "require_base": []}
    assert profiles.deliverable_settings({}) == off and profiles.deliverable_settings(None) == off
    assert profiles.deliverable_settings(make_profile(deliverables={})) == off
    own = make_profile(deliverables={"paths": ["a/*.md"], "require_base": ["a/b-*.md"]})
    assert profiles.deliverable_settings(own) == {"paths": ["a/*.md"], "require_base": ["a/b-*.md"]}
    for bad in ({"paths": [], "require_base": "x"}, {"paths": [""], "require_base": [3]}, "text", [], None):
        assert profiles.deliverable_settings(make_profile(deliverables=bad)) == off, bad
    assert profiles.validate(own) == []


def test_keys_md_has_a_line_for_each_key_with_its_default():
    """E2: both keys are lines of the «Added keys» table of KEYS.md, «in schema now» with their own schema path, the
    default named (none) and the card. Catches: a key with no default written down."""
    rows = {unquote(r[0]): r for r in section_rows("Added keys")}
    for key in ("deliverables.paths", "deliverables.require_base"):
        assert rows[key][1:3] == ["in schema now", f"`{key}`"], key
        assert "none" in rows[key][3] and "MW-020" in rows[key][4], key
    assert (REPO / "engine" / "KEYS.md").is_file()
