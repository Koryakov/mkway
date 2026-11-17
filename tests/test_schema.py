"""Branch-profile schema and its checker (card MW-001, rows E19-E22). Synthetic profiles only."""
import copy
import json
import sys
from pathlib import Path

import pytest

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


def _broken_cases():
    """Each broken profile with the key its error must name, in a fixed order."""
    good = _load("profile_depth2.json")
    cases = []
    p = copy.deepcopy(good); del p["bundle"]["root"]; cases.append(pytest.param(p, "bundle.root", id="bundle-root-missing"))
    p = copy.deepcopy(good); p["python"]["command"] = 3; cases.append(pytest.param(p, "python.command", id="python-command-number"))
    # changed by MW-003 (D-8): `items` left the schema, so an items key is refused by its name
    p = copy.deepcopy(good); p["items"] = {"card_id_pattern": "x"}; cases.append(pytest.param(p, "items.card_id_pattern", id="items-refused"))
    p = copy.deepcopy(good); p["ledger"] = {"file": "x.md"}; cases.append(pytest.param(p, "ledger.file", id="ledger-file"))
    p = copy.deepcopy(good); p["gates"]["alpha"] = {"on": "yes"}; cases.append(pytest.param(p, "gates.alpha.on", id="gate-on-word"))
    p = copy.deepcopy(good); p["bundle"]["root"] = "../outside"; cases.append(pytest.param(p, "bundle.root", id="bundle-root-outside"))
    p = copy.deepcopy(good); p["product_checks"][0].pop("command"); cases.append(pytest.param(p, "product_checks[0].command", id="product-check-command-missing"))
    return cases


def test_depth2_profile_passes():
    """Checks: the synthetic profile with its bundle at depth 2 passes (E19)."""
    profile = _load("profile_depth2.json")
    assert len(profile["bundle"]["root"].split("/")) == 2
    assert schema_check.check_file(FIXTURES / "profile_depth2.json") == []


def test_depth3_profile_passes():
    """Checks: the synthetic profile with its bundle at depth 3 passes (E20)."""
    profile = _load("profile_depth3.json")
    assert len(profile["bundle"]["root"].split("/")) == 3
    assert schema_check.check_file(FIXTURES / "profile_depth3.json") == []


@pytest.mark.parametrize("profile, key", _broken_cases())
def test_broken_profile_fails_naming_key(profile, key):
    """Catches: a broken profile that passes, or an error that does not name its key (E21)."""
    errors = schema_check.check(profile)
    assert errors, key
    assert any(e.split(":", 1)[0] == key for e in errors), (key, errors)
    broken = FIXTURES / "profile_broken.json"
    assert schema_check.main([str(broken)]) == 1


@pytest.mark.parametrize("group", [pytest.param(g, id=g) for g in sorted(LATER_GROUPS)])
def test_schema_declares_the_q2_groups(group):
    """Checks: the 11 Q2 groups are declared; each later group is optional and accepts only an empty object (E22)."""
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
                                 "wake",  # changed by MW-078 (decisions: R191, R193): the inbox waiter
                                 "leads", "rules", "deliverables",
                                 "messaging", "sessions",  # MW-076: the sessions file of the launcher
                                 "lock_gate"}  # MW-014 (E19); MW-017 (E20); MW-021 (E1); MW-018 (E16): `messaging`;
    # MW-020 (E1): `deliverables`; MW-031: `lock_gate` (names added to the git built-in list)
    required = set(schema.get("required", []))
    assert not (LATER_GROUPS & required)
    assert "user" not in required
    good = _load("profile_depth2.json")
    p = copy.deepcopy(good)
    p[group] = {}
    assert schema_check.check(p) == [], group
    p[group] = {"anything": 1}
    assert schema_check.check(p), group
