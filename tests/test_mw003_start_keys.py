"""The start line's card lines, `gate off`, the profile keys of card MW-003 and the plan defects (deliverables 4, 9,
11; R15 A9, A10; R23). Synthetic task roots only."""
import copy
import json

from _engine import FIXTURES, REPO, cli, jsonl, task_root
from _keys_md import section_rows, unquote
import records
import schema_check
import startline


def _profile(root):
    return json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))


def _start(root, session="s9", env=None):
    return startline.render(root, root / "mkway" / "profile.json", _profile(root), [], [],
                            {"CLAUDECODE": "1"} if env is None else env, session=session)


def test_start_line_lists_cards_and_the_refusal_rule(tmp_path):
    """E29 (R15 A9, A10): the start line names this session's taken card and every card that is not `closed`, with
    its status, and carries «a refusal is reported, never worked around». Catches: a start line that hides an open
    card or the session's own card."""
    root = task_root(tmp_path)
    for title in ("One", "Two", "Three"):
        assert cli(root, "card", "new", title)[0] == 0
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
    assert "CARD-001 open" in cards and "CARD-002 proposed" in cards and "CARD-003" not in cards
    assert "a refusal is reported, never worked around" in lines


def test_start_line_lists_status_changes_with_their_record(tmp_path):
    """E29 (R19a decided limit): the start line lists the cards whose status changed since the owner's last re-seal,
    with the command record behind each change; a change with no record is marked `(no record)`. Catches: a
    hand-edited and resealed status that passes unseen. Changed by MW-003 batch 3 (M1): the baseline is the owner's
    `card resync`, not the last start, so the forge is the register and its seal written together, and a second start
    still lists the changes until the next re-seal."""
    from test_mw003_batch3 import forge_status
    root = task_root(tmp_path)
    assert cli(root, "card", "new", "One")[0] == 0
    assert cli(root, "card", "new", "Two")[0] == 0
    assert cli(root, "card", "resync")[0] == 0
    assert cli(root, "card", "open", "CARD-001")[0] == 0
    forge_status(root, "CARD-002", "proposed", "open")
    for _ in range(2):
        (changes,) = [x for x in _start(root).splitlines() if x.startswith("card changes since")]
        assert "CARD-001 proposed -> open (open by owner)" in changes
        assert "CARD-002 proposed -> open (no record)" in changes
    assert cli(root, "card", "resync")[0] == 0
    (again,) = [x for x in _start(root).splitlines() if x.startswith("card changes since")]
    assert again.endswith("none")


def test_start_line_warns_when_the_session_signal_is_missing(tmp_path):
    """E30 (R23): inside a hook the start line warns `session-signal-missing` when `CLAUDECODE` is
    absent from the environment, and writes one warn row; with the signal present it says nothing.
    Catches: an engine that silently takes every session command for the owner's when the platform stops setting
    the signal (C44 is a second layer only; the shell gate's text check stays the guard)."""
    root = task_root(tmp_path)
    assert not any("session-signal-missing" in x for x in _start(root).splitlines())
    lines = _start(root, env={}).splitlines()
    (line,) = [x for x in lines if "session-signal-missing" in x]
    assert "CLAUDECODE" in line
    rows = jsonl(root / "mkway" / "state" / "refusals.jsonl")
    assert [(r["gate"], r["reason_id"], r["kind"]) for r in rows] == [("start", "session-signal-missing", "warn")]


def test_gate_off_is_the_owners_profile_switch(tmp_path):
    """E31 (deliverable 9): the owner's `mkway gate off <name>` writes `gates.<name>.on: false` in the profile and
    names `mkway install` (the hook entries change); an unknown gate name fails. Catches: a switch that writes the
    hook entries but not the tracked profile."""
    root = task_root(tmp_path)
    code, out, err = cli(root, "gate", "off", "lock")
    assert code == 0, err
    assert _profile(root)["gates"]["lock"] == {"on": False}
    assert "mkway install" in out
    assert cli(root, "gate", "off", "nosuch")[0] != 0


def test_profile_keys_of_mw003():
    """E32 (deliverables 4, 5, 7, 8; R19a): the schema takes `cards.owner_moves` (statuses; default open and
    closed), `cards.approver` (only `owner-only` in v1; an unknown value is profile-invalid), `register.columns`
    (five strings), `locks.targets[]`, `paths.docs`, `paths.exempt`, `test_roots`, `test_env`, `knowledge.files`
    and `questions.files`; each is a line of KEYS.md with its default. Catches: a key the engine reads that the
    schema refuses, or an approver value that silently turns into another mode."""
    good = json.loads((FIXTURES / "profile_depth2.json").read_text(encoding="utf-8"))
    full = dict(good, cards={"owner_moves": ["open", "closed"], "approver": "owner-only"},
                register={"columns": ["Id", "Title", "Status", "Paths", "Folder"]},
                locks={"targets": [{"name": "rules", "paths": ["rules/**"]}]},
                paths={"docs": ["*.md"], "exempt": ["notes/**"]}, test_roots=["tests"], test_env=["X_ENV"],
                knowledge={"files": ["docs/k.md"]}, questions={"files": ["questions/*.md"]})
    assert schema_check.check(full) == []
    for key, bad in (("cards", {"approver": "other-session"}), ("cards", {"owner_moves": ["shut"]}),
                     ("register", {"columns": ["Id", "Title"]}), ("locks", {"targets": [{"paths": ["x"]}]}),
                     ("test_roots", ["/abs"])):
        p = copy.deepcopy(full)
        p[key] = bad
        assert schema_check.check(p), (key, bad)
    rows = {unquote(r[0]): r for r in section_rows("Added keys")}
    for key in ("cards.owner_moves", "cards.approver", "register.columns", "locks.targets", "paths.docs",
                "paths.exempt", "test_env", "questions.files"):
        assert rows[key][1] == "in schema now", key
    assert '`["open","closed"]`' in rows["cards.owner_moves"][3] and "`owner-only`" in rows["cards.approver"][3]


def test_plan_defects_d2_and_d8():
    """E33 (R15 A13, D-2, D-8): the card layout is fixed in the engine, so the `items.*` keys leave the schema (a
    profile that sets them is invalid) and are «later» in KEYS.md; KEYS.md says MW-005 makes install register
    `product_checks[]`. Catches: a second, unused source for the card layout."""
    good = json.loads((FIXTURES / "profile_depth2.json").read_text(encoding="utf-8"))
    assert "items" not in good
    errors = schema_check.check(dict(good, items={"register_file": "x.md"}))
    assert any(e.startswith("items.register_file") for e in errors)
    profile_rows = {unquote(r[1]): r for r in section_rows("Profile keys")}
    for key in ("card.id_pattern", "card.path_glob", "register.file"):
        assert profile_rows[key][2] == "later (stays a knot)", key
    assert "MW-005" in profile_rows["product_checks"][4]
    assert "items" not in json.loads((REPO / "engine" / "profile.schema.json").read_text(encoding="utf-8"))[
        "required"]
