"""Branch-profile schema and its checker (card MW-001, rows E19-E22). Synthetic profiles only."""
import copy
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "engine"))

import schema_check  # noqa: E402

SCHEMA = REPO / "engine" / "profile.schema.json"
FIXTURES = REPO / "fixtures" / "synthetic"
GROUPS = {"bundle", "items", "ledger", "locks", "gates", "product_checks", "handback", "ids", "state", "outbox",
          "python"}
LATER_GROUPS = {"ledger", "locks", "handback", "outbox", "items"}  # MW-003 (D-8): items is later


def _load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_depth2_profile_passes():
    """E19: the synthetic profile with its bundle at depth 2 passes."""
    profile = _load("profile_depth2.json")
    assert len(profile["bundle"]["root"].split("/")) == 2
    assert schema_check.check_file(FIXTURES / "profile_depth2.json") == []


def test_depth3_profile_passes():
    """E20: the synthetic profile with its bundle at depth 3 passes."""
    profile = _load("profile_depth3.json")
    assert len(profile["bundle"]["root"].split("/")) == 3
    assert schema_check.check_file(FIXTURES / "profile_depth3.json") == []


def test_broken_profile_fails_naming_key():
    """E21: a broken profile fails, and each error names the key."""
    good = _load("profile_depth2.json")
    cases = []
    p = copy.deepcopy(good); del p["bundle"]["root"]; cases.append((p, "bundle.root"))
    p = copy.deepcopy(good); p["python"]["command"] = 3; cases.append((p, "python.command"))
    # changed by MW-003 (D-8): `items` left the schema, so an items key is refused by its name
    p = copy.deepcopy(good); p["items"] = {"card_id_pattern": "x"}; cases.append((p, "items.card_id_pattern"))
    p = copy.deepcopy(good); p["ledger"] = {"file": "x.md"}; cases.append((p, "ledger.file"))
    p = copy.deepcopy(good); p["gates"]["alpha"] = {"on": "yes"}; cases.append((p, "gates.alpha.on"))
    p = copy.deepcopy(good); p["bundle"]["root"] = "../outside"; cases.append((p, "bundle.root"))
    p = copy.deepcopy(good); p["product_checks"][0].pop("command"); cases.append((p, "product_checks[0].command"))
    for profile, key in cases:
        errors = schema_check.check(profile)
        assert errors, key
        assert any(e.split(":", 1)[0] == key for e in errors), (key, errors)
    broken = FIXTURES / "profile_broken.json"
    assert schema_check.main([str(broken)]) == 1


def test_schema_declares_the_q2_groups():
    """E22: the 11 Q2 groups are declared; the later groups are optional and accept only an empty object."""
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    declared = set(schema["properties"])
    assert GROUPS <= declared
    # the per-machine slot; `vcs` (changed by MW-002, E19: exact); the MW-003 groups (changed by MW-003, E32)
    # changed by MW-007 (E1): the ask gate's group `owner_ask`
    # changed by MW-004 (E10): the `agents` group
    # changed by MW-006 (E1): the commit gate's group `commit`
    # changed by MW-005 (E1): the commit gate's group `tests`
    # changed by MW-009 (E1): the delete gate's group `delete`
    assert declared - GROUPS == {"user", "vcs", "cards", "register", "paths", "test_roots", "test_env", "knowledge",
                                 "questions", "owner_ask", "agents", "commit", "tests", "delete", "notify",
                                 "leads", "rules", "deliverables",
                                 "messaging"}  # MW-014 (E19); MW-017 (E20); MW-021 (E1); MW-018 (E16): `messaging`;
    # MW-020 (E1): `deliverables`
    required = set(schema.get("required", []))
    assert not (LATER_GROUPS & required)
    assert "user" not in required
    good = _load("profile_depth2.json")
    for group in LATER_GROUPS:
        p = copy.deepcopy(good); p[group] = {}
        assert schema_check.check(p) == [], group
        p[group] = {"anything": 1}
        assert schema_check.check(p), group
