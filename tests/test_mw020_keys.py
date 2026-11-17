"""Card MW-020, rows E1 and E2: the profile keys `deliverables.paths` and `deliverables.require_base`, their defaults,
the schema and the KEYS lines. Synthetic values only."""
import copy
import json

import pytest

from _engine import FIXTURES, REPO, make_profile
from _keys_md import section_rows, unquote
import profiles
import schema_check

BAD_DELIVERABLES = (
    pytest.param({"paths": []}, id="paths-empty-list"),
    pytest.param({"paths": [""]}, id="paths-empty-item"),
    pytest.param({"paths": "out/*.md"}, id="paths-string"),
    pytest.param({"paths": [3]}, id="paths-number-item"),
    pytest.param({"require_base": []}, id="require-base-empty-list"),
    pytest.param({"require_base": [""]}, id="require-base-empty-item"),
    pytest.param({"require_base": "x"}, id="require-base-string"),
    pytest.param({"nope": 1}, id="unknown-key"),
)
BAD_SETTINGS = (
    pytest.param({"paths": [], "require_base": "x"}, id="paths-empty-require-base-string"),
    pytest.param({"paths": [""], "require_base": [3]}, id="paths-empty-item-require-base-number"),
    pytest.param("text", id="text"),
    pytest.param([], id="list"),
    pytest.param(None, id="none"),
)
DELIVERABLE_KEYS = (
    pytest.param("deliverables.paths", id="paths"),
    pytest.param("deliverables.require_base", id="require-base"),
)


def _good():
    return json.loads((FIXTURES / "profile_depth2.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("bad", BAD_DELIVERABLES)
def test_the_schema_takes_the_two_deliverables_keys(bad):
    """Catches: a key a profile can set with a value the command cannot use (E1)."""
    good = _good()
    full = dict(good, deliverables={"paths": ["out/*.md"], "require_base": ["out/base-*.md"]})
    assert schema_check.check(full) == []
    assert schema_check.check(dict(good, deliverables={})) == []
    assert schema_check.check(dict(good, deliverables={"paths": ["out/*.md"]})) == []
    errors = schema_check.check(dict(good, deliverables=copy.deepcopy(bad)))
    assert errors
    assert all(e.startswith("deliverables") for e in errors), (bad, errors)


@pytest.mark.parametrize("bad", BAD_SETTINGS)
def test_the_accessor_defaults_to_none_and_tolerates_a_bad_value(bad):
    """Checks: the accessor returns no default folder, and a bad key reads as the off settings (E1)."""
    off = {"paths": [], "require_base": []}
    assert profiles.deliverable_settings({}) == off
    assert profiles.deliverable_settings(None) == off
    assert profiles.deliverable_settings(make_profile(deliverables={})) == off
    own = make_profile(deliverables={"paths": ["a/*.md"], "require_base": ["a/b-*.md"]})
    assert profiles.deliverable_settings(own) == {"paths": ["a/*.md"], "require_base": ["a/b-*.md"]}
    assert profiles.validate(own) == []
    assert profiles.deliverable_settings(make_profile(deliverables=bad)) == off, bad


@pytest.mark.parametrize("key", DELIVERABLE_KEYS)
def test_keys_md_has_a_line_for_each_key_with_its_default(key):
    """Checks: each key has its line in KEYS.md with its default written down (E2)."""
    rows = {unquote(r[0]): r for r in section_rows("Added keys")}
    assert rows[key][1:3] == ["in schema now", f"`{key}`"], key
    assert "none" in rows[key][3], key
    assert "MW-020" in rows[key][4], key
    assert (REPO / "engine" / "KEYS.md").is_file()
