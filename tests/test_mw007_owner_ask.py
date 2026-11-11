"""Questions to the owner (card MW-007): the profile keys, the edit gate, the stop gate, the start block and the
README section. Synthetic task roots only; no task data."""
import copy
import json

from _engine import FIXTURES, REPO, make_profile
from _keys_md import section_rows, unquote
import profiles
import schema_check

NOW = "in schema now"


def _good():
    return json.loads((FIXTURES / "profile_depth2.json").read_text(encoding="utf-8"))


def test_owner_ask_keys_are_in_the_schema():
    """E1 (part 3): the schema takes `owner_ask.dir` (a repo-relative path), `owner_ask.markers` and
    `owner_ask.sources` (non-empty lists of non-empty strings; a source name holds no space and no colon, because it
    is written before a colon in a quote line); an unknown key under `owner_ask` is profile-invalid.
    Catches: a key the gates read that the schema refuses, or a value that breaks the line shapes."""
    good = _good()
    full = dict(good, owner_ask={"dir": "notes/asks", "markers": ["Request:", "Ask:"],
                                 "sources": ["review", "canon"]})
    assert schema_check.check(full) == []
    assert schema_check.check(dict(good, owner_ask={})) == []
    for bad in ({"dir": "/abs"}, {"dir": ""}, {"dir": "../up"}, {"dir": 5}, {"markers": []}, {"markers": [""]},
                {"markers": "Request:"}, {"sources": []}, {"sources": [""]}, {"sources": ["two words"]},
                {"sources": ["colon:"]}, {"nope": 1}):
        errors = schema_check.check(dict(good, owner_ask=copy.deepcopy(bad)))
        assert errors and all(e.startswith("owner_ask") for e in errors), (bad, errors)


def test_owner_ask_defaults_and_overrides():
    """E2 (part 3): with no `owner_ask` in the profile the settings are the defaults: the folder `asks` inside the
    bundle, the marker `Request:`, the source `review`; the profile's own values replace them; a value that is not
    usable falls back to the default, as `state.dir` does, so a gate never crashes on a bad key.
    Catches: a default that is hard-coded in a gate, or an override that is ignored."""
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
    for bad in ({"dir": "/abs", "markers": [], "sources": [""]}, {"dir": 5, "markers": "Request:", "sources": 1},
                {"markers": ["", 3]}, "text", []):
        assert profiles.owner_ask(make_profile(owner_ask=bad)) == default, bad
    assert profiles.validate(own) == []  # the profile above, with its own `owner_ask` values


def test_owner_ask_keys_are_lines_of_keys_md_with_their_defaults():
    """E3 (part 3): each key is a line of the «Added keys» table of KEYS.md, «in schema now» with its own schema path
    and its default named. Catches: a key with no default written down, which would make the default a hard-coded
    value that nobody can find."""
    rows = {unquote(r[0]): r for r in section_rows("Added keys")}
    for key in ("owner_ask.dir", "owner_ask.markers", "owner_ask.sources"):
        assert rows[key][1:3] == [NOW, f"`{key}`"], key
    assert "`<bundle.root>/asks`" in rows["owner_ask.dir"][3]
    assert "`Request:`" in rows["owner_ask.markers"][3]
    assert "`ledger`" in rows["owner_ask.sources"][3]  # changed by MW-008 (E17): the default is the ledger
    assert (REPO / "engine" / "KEYS.md").is_file()
