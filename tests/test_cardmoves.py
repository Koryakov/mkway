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
    root = task_root(tmp_path, test_roots=["tests"])
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


def test_status_chain(task):
    """E21 (R15 A1, R19c): a session's `card new` is `proposed`; a session sets `waiting` only from `open`; a
    `waiting` set from the owner's terminal is written `waiting-owner`; the owner's `card open` opens from
    `proposed` and `waiting-owner`; any move the chain does not allow is `card-bad-move`, naming the current status
    and the allowed moves, with one refusal row. Catches: a chain that lets `proposed` go to `waiting`, or a pause
    the session can lift that the owner set."""
    assert _row(task, "CARD-001")["status"] == "proposed"
    code, out, err = cli(task, "card", "set", "CARD-001", "waiting", session=True)
    assert code != 0 and _reason(err) == "card-bad-move"
    assert "proposed" in err and "open" in err
    assert [r["reason_id"] for r in jsonl(task / "mkway" / "state" / "refusals.jsonl")] == ["card-bad-move"]
    assert cli(task, "card", "open", "CARD-001")[0] == 0
    assert _row(task, "CARD-001")["status"] == "open"
    assert cli(task, "card", "set", "CARD-001", "waiting", session=True)[0] == 0
    assert _row(task, "CARD-001")["status"] == "waiting"
    assert cli(task, "card", "set", "CARD-001", "open", session=True)[0] == 0
    assert _row(task, "CARD-001")["status"] == "open"
    assert cli(task, "card", "set", "CARD-001", "waiting")[0] == 0
    assert _row(task, "CARD-001")["status"] == "waiting-owner"
    for bad in ("proposed", "waiting-owner", "nonsense"):
        code, _out, err = cli(task, "card", "set", "CARD-001", bad)
        assert code != 0 and _reason(err) == "card-bad-move", bad
    assert cli(task, "card", "open", "CARD-001")[0] == 0
    assert _row(task, "CARD-001")["status"] == "open"


def test_take_and_release_commands(task):
    """E22 (R15 A2, v3.1): `card take` and `card release` print the session's `mkway-ok` line; a release of a card no
    one holds exits 0 with a note and changes nothing; the owner's `card release <id> --force` frees a held card.
    The CLI accepts only the long form `--force`. Catches: a release that writes a record for a card no one holds,
    or a short `-f` that slips past the gate's `--force` match."""
    state = task / "mkway" / "state"
    code, out, _ = cli(task, "card", "take", "CARD-001", session=True)
    assert code == 0 and "mkway-ok take CARD-001 " in out
    records.append(state, "s1", "take", "CARD-001")
    code, out, _ = cli(task, "card", "release", "CARD-002", session=True)
    assert code != 0 or "no one holds" in out
    before = records.rows(state)
    assert cli(task, "card", "new", "Second")[0] == 0
    code, out, _ = cli(task, "card", "release", "CARD-002", session=True)
    assert code == 0 and "no one holds CARD-002" in out and "mkway-ok" not in out
    assert len(records.rows(state)) == len(before) + 1  # only the owner's `new` row
    assert cli(task, "card", "release", "CARD-001", "-f")[0] != 0
    code, out, _ = cli(task, "card", "release", "CARD-001", "--force")
    assert code == 0
    assert records.holders(state) == {}
    assert records.rows(state)[-1]["by"] == "owner"
    assert cli(task, "card", "take", "CARD-404", session=True)[0] != 0


def test_close_rule(task):
    """E23 (R15 A3; C-05): `card close` and `card set <id> closed` refuse while an Acceptance row's Test cell is
    empty or names a node whose file is not under `test_roots` or holds no `def <name>(` (`[...]` ignored); the
    command exits non-zero, prints the reason id and writes one refusal row. Changed by MW-003 list item 14 (R45):
    one cell form, a `; ` list of full node ids or `checked by reading: <path>` on any card; a bare `checked by
    reading` refuses. Catches: a close of a card whose tests do not exist, or a rule that holds for `card close`
    only."""
    assert cli(task, "card", "open", "CARD-001")[0] == 0
    bad = ["", "tests/test_a.py::test_missing", "other/test_b.py::test_b", "tests/nofile.py::test_one",
           "checked by reading"]
    set_paths(task, "CARD-001", "`src/a.py`")
    for cell in bad:
        set_tests(task, "CARD-001", ["tests/test_a.py::test_one", cell])
        for args in (("card", "close", "CARD-001"), ("card", "set", "CARD-001", "closed")):
            code, out, err = cli(task, *args)
            assert code != 0 and _reason(err) == "close-row-without-test", (cell, args)
        assert _row(task, "CARD-001")["status"] == "open"
    rows = jsonl(task / "mkway" / "state" / "refusals.jsonl")
    assert len(rows) == 2 * len(bad) and {r["reason_id"] for r in rows} == {"close-row-without-test"}
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
    """E24 (v3.1, R18): `card open` records the card's `Paths` in the register's `Paths` column, normalised, joined
    by `; `; `card open` on an open card changes no status and does not record them again (changed by MW-003
    close-fix 10, A(c): Paths are recorded once, at the first open from `proposed`); a `card set <id> open` from
    `waiting` does not, in light mode either (changed by batch 3, H1). Catches: a session that widens its own scope
    by a reopen."""
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
    """E24 (v3.1): at `card open` an entry is too wide (`card-paths-too-wide`) when it is empty after the normaliser,
    `.`, `/`, `*`, `**`, a glob matching every path, or a `test_roots` root, with or without a trailing `/` or
    `/**`. Catches: a card that names the whole repository as its scope."""
    for entry in ("`.`", "`/`", "`*`", "`**`", "`**/*`", "`/**`", "`*/**`", "`tests`", "`tests/`", "`tests/**`",
                  "`./`", "`src/a.py`, `**`"):
        set_paths(task, "CARD-001", entry)
        code, _out, err = cli(task, "card", "open", "CARD-001")
        assert code != 0 and _reason(err) == "card-paths-too-wide", entry
        assert _row(task, "CARD-001")["status"] == "proposed"
    set_paths(task, "CARD-001", "`tests/test_a.py`, `src/**`")
    assert cli(task, "card", "open", "CARD-001")[0] == 0


def test_template_lines():
    """E25 (R15 A7, R19, D-4): the card template holds the contradiction line and, under the Log heading, the
    no-re-run line; the line that points to the checklist file is cut until MW-004 ships it; a new card is `proposed`.
    Catches: a template that still points to a missing checklist."""
    text = TEMPLATE.read_text(encoding="utf-8")
    flat = " ".join(text.split())
    assert ("When two requirements contradict: `card set <id> waiting`, a Log line that names both, then the ask."
            in flat)
    log = text.split("## 8. Log", 1)[1]
    assert "No re-run of a check or an agent round without a new input named in the Log row." in " ".join(log.split())
    assert "reader checklist" not in text
    assert "| **Status** | proposed |" in text


def test_register_columns_come_from_the_profile(tmp_path):
    """E26 (R18; deliverable 5): the register's column names are profile strings (`register.columns`); the engine's
    default is Id, Title, Status, Paths, Folder. Catches: an engine that writes or reads a literal column name."""
    root = task_root(tmp_path, register={"columns": ["Key", "Name", "State", "Scope", "Where"]})
    assert cli(root, "card", "new", "First")[0] == 0
    text = (root / "mkway" / "cards" / "REGISTER.md").read_text(encoding="utf-8")
    assert "| Key | Name | State | Scope | Where |" in text
    assert register.find(register.read(root, _profile(root)), "CARD-001")["status"] == "proposed"
    assert register.DEFAULT_COLUMNS == ["Id", "Title", "Status", "Paths", "Folder"]
