"""Questions to the owner (card MW-007): the profile keys, the edit gate, the stop gate, the start block and the
README section. Synthetic task roots only; no task data."""
import copy
import json

import pytest

from _engine import FIXTURES, REPO, make_profile
from _keys_md import section_rows, unquote
import profiles
import schema_check

NOW = "in schema now"
BAD_OWNER_ASKS = (
    pytest.param({"dir": ""}, id="dir-empty"),
    pytest.param({"dir": "../up"}, id="dir-up"),
    pytest.param({"dir": 5}, id="dir-number"),
    pytest.param({"markers": []}, id="markers-empty-list"),
    pytest.param({"markers": [""]}, id="markers-empty-item"),
    pytest.param({"markers": "Request:"}, id="markers-string"),
    pytest.param({"sources": []}, id="sources-empty-list"),
    pytest.param({"sources": [""]}, id="sources-empty-item"),
    pytest.param({"sources": ["two words"]}, id="sources-with-space"),
    pytest.param({"sources": ["colon:"]}, id="sources-with-colon"),
    pytest.param({"nope": 1}, id="unknown-key"),
)
BAD_SETTINGS = (
    pytest.param({"dir": 5, "markers": "Request:", "sources": 1}, id="dir-number-markers-string-sources-number"),
    pytest.param({"markers": ["", 3]}, id="markers-empty-and-number"),
    pytest.param("text", id="text"),
    pytest.param([], id="list"),
)
DEFAULT_TEXTS = (
    pytest.param("owner_ask.dir", "`<bundle.root>/asks`", id="dir-default"),
    pytest.param("owner_ask.markers", "`Request:`", id="markers-default"),
    pytest.param("owner_ask.sources", "`ledger`", id="sources-default"),  # changed by MW-008 (E17): the default is the ledger
)


def _good():
    return json.loads((FIXTURES / "profile_depth2.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("bad", BAD_OWNER_ASKS)
def test_owner_ask_keys_are_in_the_schema(bad):
    """Catches: a key the gates read that the schema refuses, or a value that breaks the line shapes (E1 part 3)."""
    good = _good()
    full = dict(good, owner_ask={"dir": "notes/asks", "markers": ["Request:", "Ask:"],
                                 "sources": ["review", "canon"]})
    assert schema_check.check(full) == []
    assert schema_check.check(dict(good, owner_ask={})) == []
    errors = schema_check.check(dict(good, owner_ask=copy.deepcopy(bad)))
    assert errors
    assert all(e.startswith("owner_ask") for e in errors), (bad, errors)


# the two absolute forms schema_check refuses (engine/schema_check.py: a drive form and a leading-slash form), both from tmp_path
ABSOLUTE_FORMS = [
    pytest.param(lambda p: str(p), id="drive-form"),
    pytest.param(lambda p: "/" + p.relative_to(p.anchor).as_posix(), id="leading-slash-form"),
]


@pytest.mark.parametrize("make", ABSOLUTE_FORMS)
def test_owner_ask_dir_that_is_absolute_is_refused_by_the_schema(tmp_path, make):
    """Catches: an absolute owner_ask.dir that the schema lets through."""
    errors = schema_check.check(dict(_good(), owner_ask={"dir": make(tmp_path)}))
    assert errors
    assert all(e.startswith("owner_ask") for e in errors), errors


@pytest.mark.parametrize("bad", BAD_SETTINGS)
def test_owner_ask_defaults_and_overrides(bad):
    """Checks: the defaults a gate uses, and that an override replaces each of them (E2 part 3)."""
    default = {"dir": "mkway/asks", "markers": ["Request:"], "sources": ["ledger"],  # changed by MW-008 (E17)
               "max_open": 1, "tool_allowed": False}  # changed by MW-014 (E19)
    assert profiles.owner_ask(make_profile()) == default
    assert profiles.owner_ask(None) == default
    assert profiles.owner_ask(make_profile(owner_ask={})) == default
    deep = make_profile(bundle={"root": "tools/mk"})
    assert profiles.owner_ask(deep)["dir"] == "tools/mk/asks"
    own = make_profile(owner_ask={"dir": "notes\\asks/", "markers": ["Ask:", "Q:"], "sources": ["canon", "review"]})
    assert profiles.owner_ask(own) == {"dir": "notes/asks", "markers": ["Ask:", "Q:"],
                                       "sources": ["canon", "review"], "max_open": 1, "tool_allowed": False}
    only_dir = make_profile(owner_ask={"dir": "x/y"})
    assert profiles.owner_ask(only_dir) == {"dir": "x/y", "markers": ["Request:"], "sources": ["ledger"],  # MW-008
                                            "max_open": 1, "tool_allowed": False}  # MW-014
    assert profiles.owner_ask(make_profile(owner_ask=bad)) == default, bad
    assert profiles.validate(own) == []  # the profile above, with its own `owner_ask` values


@pytest.mark.parametrize("make", ABSOLUTE_FORMS)
def test_owner_ask_dir_that_is_absolute_reads_as_the_default(tmp_path, make):
    """Checks: an absolute owner_ask.dir reads as the default folder, so a gate never uses it."""
    default = {"dir": "mkway/asks", "markers": ["Request:"], "sources": ["ledger"], "max_open": 1, "tool_allowed": False}
    assert profiles.owner_ask(make_profile(owner_ask={"dir": make(tmp_path), "markers": [], "sources": [""]})) == default


@pytest.mark.parametrize("key, default_text", DEFAULT_TEXTS)
def test_owner_ask_keys_are_lines_of_keys_md_with_their_defaults(key, default_text):
    """Checks: each key has its line in KEYS.md with its default written down (E3 part 3)."""
    rows = {unquote(r[0]): r for r in section_rows("Added keys")}
    assert rows[key][1:3] == [NOW, f"`{key}`"], key
    assert default_text in rows[key][3], key
    assert (REPO / "engine" / "KEYS.md").is_file()
