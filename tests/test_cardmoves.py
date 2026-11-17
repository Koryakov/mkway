"""The cards tool, completed (card MW-003, deliverable 4; R15 A1-A3, A7, A11; R19, R19c; v3.1). Synthetic task roots
only; `cli(..., session=True)` runs a command as a session's shell does, else as the owner's own terminal."""
import json
import re

import pytest

from _engine import REPO, cli, jsonl, task_root
import records
import register

TEMPLATE = REPO / "cards" / "_TEMPLATE" / "CARD.md"


def _profile(root):
    return json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))


def _row(root, card_id):
    return register.find(register.read(root, _profile(root)), card_id)


def _card_file(root, card_id):
    (folder,) = [p for p in (root / "mkway" / "cards").iterdir() if p.name.startswith(card_id + "-")]
    return folder / "CARD.md"


def set_paths(root, card_id, value):
    path = _card_file(root, card_id)
    text = re.sub(r"^\| \*\*Paths\*\* \|.*\|$", f"| **Paths** | {value} |", path.read_text(encoding="utf-8"),
                  flags=re.M)
    path.write_text(text, encoding="utf-8")


def set_tests(root, card_id, cells):
    """Replace the Acceptance rows with one row per Test cell."""
    path = _card_file(root, card_id)
    text = path.read_text(encoding="utf-8")
    head = "| # | Item | Was | Must be | Test |\n|---|---|---|---|---|\n"
    start = text.index(head) + len(head)
    end = text.index("\n\n", start)
    rows = "".join(f"| E{i} | x | a | b | {c} |\n" for i, c in enumerate(cells, 1))
    path.write_text(text[:start] + rows.rstrip("\n") + text[end:], encoding="utf-8")


@pytest.fixture
def task(tmp_path):
    root = task_root(tmp_path, test_roots=["tests"], cards={"verdicts": "off"})  # MW-068: this file judges the close rule of the Test cells only
    (root / "tests").mkdir()
    (root / "tests" / "test_a.py").write_text("def test_one():\n    pass\n\n\ndef test_two(x):\n    pass\n",
                                              encoding="utf-8")
    (root / "other").mkdir()
    (root / "other" / "test_b.py").write_text("def test_b():\n    pass\n", encoding="utf-8")
    assert cli(root, "card", "new", "First", session=True)[0] == 0
    return root


def _reason(out_err):
    m = re.search(r"mkway: ([a-z-]+):", out_err)
    return m.group(1) if m else None


def _refuse_close(task, cell):
    """One Test cell that card close and card set closed both refuse with close-row-without-test."""
    set_tests(task, "CARD-001", ["tests/test_a.py::test_one", cell])
    for args in (("card", "close", "CARD-001"), ("card", "set", "CARD-001", "closed")):
        code, out, err = cli(task, *args)
        assert code != 0, (cell, args)
        assert _reason(err) == "close-row-without-test", (cell, args)
    assert _row(task, "CARD-001")["status"] == "open"


def _refuse_wide(task, entry):
    """One Paths entry that card open refuses as too wide, the card staying proposed."""
    set_paths(task, "CARD-001", entry)
    code, _out, err = cli(task, "card", "open", "CARD-001")
    assert code != 0, entry
    assert _reason(err) == "card-paths-too-wide", entry
    assert _row(task, "CARD-001")["status"] == "proposed", entry


def test_status_chain(task):
    """Catches: a chain that lets proposed go to waiting, or a pause the session can lift that the owner set (E21: a session's card new is proposed, and any move the chain does not allow is card-bad-move with one refusal row)."""
    assert _row(task, "CARD-001")["status"] == "proposed"
    code, out, err = cli(task, "card", "set", "CARD-001", "waiting", session=True)
    assert code != 0
    assert _reason(err) == "card-bad-move"
    assert "proposed" in err
    assert "open" in err
    assert [r["reason_id"] for r in jsonl(task / "mkway" / "state" / "refusals.jsonl")] == ["card-bad-move"]
    assert cli(task, "card", "open", "CARD-001")[0] == 0
    assert _row(task, "CARD-001")["status"] == "open"
    assert cli(task, "card", "set", "CARD-001", "waiting", session=True)[0] == 0
    assert _row(task, "CARD-001")["status"] == "waiting"
    assert cli(task, "card", "set", "CARD-001", "open", session=True)[0] == 0
    assert _row(task, "CARD-001")["status"] == "open"
    assert cli(task, "card", "set", "CARD-001", "waiting")[0] == 0
    assert _row(task, "CARD-001")["status"] == "waiting-owner"
    code, _out, err = cli(task, "card", "set", "CARD-001", "proposed")
    assert code != 0
    assert _reason(err) == "card-bad-move"
    code, _out, err = cli(task, "card", "set", "CARD-001", "waiting-owner")
    assert code != 0
    assert _reason(err) == "card-bad-move"
    code, _out, err = cli(task, "card", "set", "CARD-001", "nonsense")
    assert code != 0
    assert _reason(err) == "card-bad-move"
    assert cli(task, "card", "open", "CARD-001")[0] == 0
    assert _row(task, "CARD-001")["status"] == "open"


def test_take_and_release_commands(task):
    """Catches: a release that writes a record for a card no one holds, or a short -f that slips past the gate's --force match (E22: card take and card release print the mkway-ok line, a release of a card no one holds exits 0 with a note, and the owner's card release with --force frees a held card)."""
    state = task / "mkway" / "state"
    code, out, _ = cli(task, "card", "take", "CARD-001", session=True)
    assert code == 0
    assert "mkway-ok take CARD-001 " in out
    records.append(state, "s1", "take", "CARD-001")
    code, out, _ = cli(task, "card", "release", "CARD-002", session=True)
    assert code != 0 or "no one holds" in out
    before = records.rows(state)
    assert cli(task, "card", "new", "Second")[0] == 0
    code, out, _ = cli(task, "card", "release", "CARD-002", session=True)
    assert code == 0
    assert "no one holds CARD-002" in out
    assert "mkway-ok" not in out
    assert len(records.rows(state)) == len(before) + 1  # only the owner's `new` row
    assert cli(task, "card", "release", "CARD-001", "-f")[0] != 0
    code, out, _ = cli(task, "card", "release", "CARD-001", "--force")
    assert code == 0
    assert records.holders(state) == {}
    assert records.rows(state)[-1]["by"] == "owner"
    assert cli(task, "card", "take", "CARD-404", session=True)[0] != 0


def test_close_rule(task):
    """Catches: a close of a card whose tests do not exist, or a rule that holds for card close only (E23: card close and card set closed refuse while an Acceptance row's Test cell is empty or names a node that is not there; changed by MW-003 list item 14, R45)."""
    assert cli(task, "card", "open", "CARD-001")[0] == 0
    set_paths(task, "CARD-001", "`src/a.py`")
    _refuse_close(task, "")
    _refuse_close(task, "tests/test_a.py::test_missing")
    _refuse_close(task, "other/test_b.py::test_b")
    _refuse_close(task, "tests/nofile.py::test_one")
    _refuse_close(task, "checked by reading")
    rows = jsonl(task / "mkway" / "state" / "refusals.jsonl")
    assert len(rows) == 10
    assert {r["reason_id"] for r in rows} == {"close-row-without-test"}
    set_tests(task, "CARD-001", ["tests/test_a.py::test_one; tests/test_a.py::test_two[a b-1]",
                                 "`tests/test_a.py::test_two`"])  # changed by list item 14: `; ` and full node ids
    assert cli(task, "card", "close", "CARD-001")[0] == 0
    assert _row(task, "CARD-001")["status"] == "closed"
    assert cli(task, "card", "new", "Docs")[0] == 0
    assert cli(task, "card", "open", "CARD-002")[0] == 0
    set_paths(task, "CARD-002", "`README.md`")
    (task / "README.md").write_text("synthetic\n", encoding="utf-8")
    set_tests(task, "CARD-002", ["checked by reading: README.md"])  # changed by list item 14: name the file read
    assert cli(task, "card", "set", "CARD-002", "closed")[0] == 0


def test_open_records_paths(task):
    """Checks: card open records the Paths once, at the first open from proposed, and a reopen does not widen them (E24: normalised, joined by `; `; a card set open from waiting records none, in light mode either, changed by MW-003 close-fix 10 and batch 3, H1)."""
    set_paths(task, "CARD-001", "`src/a.py`, `./lib/`")
    assert cli(task, "card", "open", "CARD-001")[0] == 0
    assert _row(task, "CARD-001")["paths"] == "src/a.py; lib"
    set_paths(task, "CARD-001", "`src/b.py`")
    assert cli(task, "card", "set", "CARD-001", "waiting", session=True)[0] == 0
    assert cli(task, "card", "set", "CARD-001", "open", session=True)[0] == 0
    assert _row(task, "CARD-001")["paths"] == "src/a.py; lib"
    assert cli(task, "card", "open", "CARD-001")[0] == 0
    assert _row(task, "CARD-001") == dict(_row(task, "CARD-001"), status="open", paths="src/a.py; lib")
    p = _profile(task)
    p["cards"] = {"owner_moves": []}
    (task / "mkway" / "profile.json").write_text(json.dumps(p), encoding="utf-8")
    # changed by MW-003 batch 3 (H1, R54): a `card set <id> open` never records Paths, in light mode too; the paths
    # are recorded at the first open from `proposed` only (close-fix 10, A(c))
    set_paths(task, "CARD-001", "`src/c.py`")
    assert cli(task, "card", "set", "CARD-001", "open", session=True)[0] == 0
    assert _row(task, "CARD-001")["paths"] == "src/a.py; lib"


def test_paths_too_wide(task):
    """Catches: a card that names the whole repository as its scope (E24: at card open an entry is too wide, card-paths-too-wide, when it is empty after the normaliser, a dot, a slash, a star, a globstar, a glob matching every path, or a test_roots root, with or without a trailing slash or slash globstar)."""
    _refuse_wide(task, "`.`")
    _refuse_wide(task, "`/`")
    _refuse_wide(task, "`*`")
    _refuse_wide(task, "`**`")
    _refuse_wide(task, "`**/*`")
    _refuse_wide(task, "`/**`")
    _refuse_wide(task, "`*/**`")
    _refuse_wide(task, "`tests`")
    _refuse_wide(task, "`tests/`")
    _refuse_wide(task, "`tests/**`")
    _refuse_wide(task, "`./`")
    _refuse_wide(task, "`src/a.py`, `**`")
    set_paths(task, "CARD-001", "`tests/test_a.py`, `src/**`")
    assert cli(task, "card", "open", "CARD-001")[0] == 0


def test_template_lines():
    """Checks: the template holds the contradiction line and the no-re-run line under the Log heading, and a new card is proposed (E25: the line that points to the checklist file is cut)."""
    text = TEMPLATE.read_text(encoding="utf-8")
    flat = " ".join(text.split())
    assert ("When two requirements contradict: `card set <id> waiting`, a Log line that names both, then the ask."
            in flat)
    log = text.split("## 8. Log", 1)[1]
    assert "No re-run of a check or an agent round without a new input named in the Log row." in " ".join(log.split())
    assert "reader checklist" not in text
    assert "| **Status** | proposed |" in text


def test_register_columns_come_from_the_profile(tmp_path):
    """Checks: the register's column names come from the profile, the engine default being Id, Title, Status, Paths, Folder (E26, R18, deliverable 5)."""
    root = task_root(tmp_path, register={"columns": ["Key", "Name", "State", "Scope", "Where"]})
    assert cli(root, "card", "new", "First")[0] == 0
    text = (root / "mkway" / "cards" / "REGISTER.md").read_text(encoding="utf-8")
    assert "| Key | Name | State | Scope | Where |" in text
    assert register.find(register.read(root, _profile(root)), "CARD-001")["status"] == "proposed"
    assert register.DEFAULT_COLUMNS == ["Id", "Title", "Status", "Paths", "Folder"]
