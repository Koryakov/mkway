"""The start line's card lines, `gate off`, the profile keys of card MW-003 and the plan defects (deliverables 4, 9,
11; R15 A9, A10; R23). Synthetic task roots only."""
import copy
import json

import pytest

from _engine import FIXTURES, REPO, cli, jsonl, task_root
from _keys_md import section_rows, unquote
from _mw094_forge import forge_status
import records
import schema_check
import startline

BAD_MW003 = (
    pytest.param("cards", {"approver": "other-session"}, id="approver-other-session"),
    pytest.param("cards", {"owner_moves": ["shut"]}, id="owner-moves-shut"),
    pytest.param("register", {"columns": ["Id", "Title"]}, id="register-columns-short"),
    pytest.param("locks", {"targets": [{"paths": ["x"]}]}, id="locks-target-without-name"),
)


def _profile(root):
    return json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))


def _start(root, session="s9", env=None):
    return startline.render(root, root / "mkway" / "profile.json", _profile(root), [], [],
                            {"CLAUDECODE": "1"} if env is None else env, session=session)


def _new_cards(root, titles):
    """One card per title, through the real command."""
    for title in titles:
        assert cli(root, "card", "new", title)[0] == 0


def _changes(root):
    """The one `card changes since` line of the start block."""
    (line,) = [x for x in _start(root).splitlines() if x.startswith("card changes since")]
    return line


def _assert_in_schema(rows, keys):
    """Each key is a KEYS.md line marked in schema now."""
    for key in keys:
        assert rows[key][1] == "in schema now", key


def _assert_later(rows, keys):
    """Each key is a KEYS.md line marked later (stays a knot)."""
    for key in keys:
        assert rows[key][2] == "later (stays a knot)", key


def test_start_line_lists_cards_and_the_refusal_rule(tmp_path):
    """Catches: a start line that hides an open card or the session's own card (E29, R15 A9, A10)."""
    root = task_root(tmp_path)
    _new_cards(root, ("One", "Two", "Three"))
    assert cli(root, "card", "open", "CARD-001")[0] == 0
    p = _profile(root)
    p["cards"] = {"owner_moves": []}
    (root / "mkway" / "profile.json").write_text(json.dumps(p), encoding="utf-8")
    (root / "mkway" / "cards" / "CARD-003-three" / "CARD.md").write_text(
        (root / "mkway" / "cards" / "CARD-003-three" / "CARD.md").read_text(encoding="utf-8").replace(
            "| E1 | item id | value today | value after the change | tests/test_x.py::test_y |",
            "| E1 | doc | a | b | checked by reading: mkway/profile.json |"), encoding="utf-8")  # list item 14
    assert cli(root, "card", "close", "CARD-003")[0] == 0
    records.append(root / "mkway" / "state", "s9", "take", "CARD-001")
    lines = _start(root).splitlines()
    (cards,) = [x for x in lines if x.startswith("cards:")]
    assert "this session holds CARD-001 (open)" in cards
    assert "CARD-001 open" in cards
    assert "CARD-002 proposed" in cards
    assert "CARD-003" not in cards
    assert "a refusal is reported, never worked around" in lines


def test_start_line_lists_status_changes_with_their_record(tmp_path):
    """Catches: a hand-edited and resealed status that passes unseen; the baseline is the owner's `card resync`, not the last start (E29, R19a decided limit; M1)."""
    root = task_root(tmp_path)
    _new_cards(root, ("One", "Two"))
    assert cli(root, "card", "resync")[0] == 0
    assert cli(root, "card", "open", "CARD-001")[0] == 0
    forge_status(root, "CARD-002", "proposed", "open")
    changes = _changes(root)
    assert "CARD-001 proposed -> open (open by owner)" in changes
    assert "CARD-002 proposed -> open (no record)" in changes
    changes = _changes(root)  # a second start still lists the change until the next re-seal
    assert "CARD-001 proposed -> open (open by owner)" in changes
    assert "CARD-002 proposed -> open (no record)" in changes
    assert cli(root, "card", "resync")[0] == 0
    assert _changes(root).endswith("none")


def test_start_line_warns_when_the_session_signal_is_missing(tmp_path):
    """Catches: an engine that silently takes every session command for the owner's when the platform stops setting the signal (E30, R23; C44)."""
    root = task_root(tmp_path)
    assert not any("session-signal-missing" in x for x in _start(root).splitlines())
    lines = _start(root, env={}).splitlines()
    (line,) = [x for x in lines if "session-signal-missing" in x]
    assert "CLAUDECODE" in line
    rows = jsonl(root / "mkway" / "state" / "refusals.jsonl")
    assert [(r["gate"], r["reason_id"], r["kind"]) for r in rows] == [("start", "session-signal-missing", "warn")]


def test_gate_off_is_the_owners_profile_switch(tmp_path):
    """Catches: a switch that writes the hook entries but not the tracked profile (E31, deliverable 9)."""
    root = task_root(tmp_path)
    code, out, err = cli(root, "gate", "off", "lock")
    assert code == 0, err
    assert _profile(root)["gates"]["lock"] == {"on": False}
    assert "mkway install" in out
    assert cli(root, "gate", "off", "nosuch")[0] != 0


@pytest.mark.parametrize("key, bad", BAD_MW003)
def test_profile_keys_of_mw003(key, bad):
    """Catches: a key the engine reads that the schema refuses, or an approver value that silently turns into another mode (E32, deliverables 4, 5, 7, 8; R19a)."""
    good = json.loads((FIXTURES / "profile_depth2.json").read_text(encoding="utf-8"))
    full = dict(good, cards={"owner_moves": ["open", "closed"], "approver": "owner-only"},
                register={"columns": ["Id", "Title", "Status", "Paths", "Folder"]},
                locks={"targets": [{"name": "rules", "paths": ["rules/**"]}]},
                paths={"docs": ["*.md"], "exempt": ["notes/**"]}, test_roots=["tests"], test_env=["X_ENV"],
                knowledge={"files": ["docs/k.md"]}, questions={"files": ["questions/*.md"]})
    assert schema_check.check(full) == []
    p = copy.deepcopy(full)
    p[key] = bad
    assert schema_check.check(p), (key, bad)
    rows = {unquote(r[0]): r for r in section_rows("Added keys")}
    _assert_in_schema(rows, ("cards.owner_moves", "cards.approver", "register.columns", "locks.targets", "paths.docs",
                             "paths.exempt", "test_env", "questions.files"))
    assert '`["open","closed"]`' in rows["cards.owner_moves"][3]
    assert "`owner-only`" in rows["cards.approver"][3]


# the two absolute forms schema_check refuses (engine/schema_check.py: a drive form and a leading-slash form), both from tmp_path
ABSOLUTE_FORMS = [
    pytest.param(lambda p: str(p), id="drive-form"),
    pytest.param(lambda p: "/" + p.relative_to(p.anchor).as_posix(), id="leading-slash-form"),
]


@pytest.mark.parametrize("make", ABSOLUTE_FORMS)
def test_profile_keys_of_mw003_absolute_test_root(tmp_path, make):
    """Catches: an absolute test_roots entry that the schema accepts."""
    good = json.loads((FIXTURES / "profile_depth2.json").read_text(encoding="utf-8"))
    assert schema_check.check(dict(good, test_roots=[make(tmp_path)]))


def test_plan_defects_d2_and_d8():
    """Catches: a second, unused source for the card layout (E33, R15 A13, D-2, D-8)."""
    good = json.loads((FIXTURES / "profile_depth2.json").read_text(encoding="utf-8"))
    assert "items" not in good
    errors = schema_check.check(dict(good, items={"register_file": "x.md"}))
    assert any(e.startswith("items.register_file") for e in errors)
    profile_rows = {unquote(r[1]): r for r in section_rows("Profile keys")}
    _assert_later(profile_rows, ("card.id_pattern", "card.path_glob", "register.file"))
    assert "MW-005" in profile_rows["product_checks"][4]
    assert "items" not in json.loads((REPO / "engine" / "profile.schema.json").read_text(encoding="utf-8"))[
        "required"]
