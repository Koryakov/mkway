"""The decision ledger file and `mkway ledger add` (card MW-008, part 1). Synthetic task roots only; no task data. The
module is imported inside each test, so a missing module fails that test and not the collection of the file."""
import datetime
import importlib
import json
import re

import pytest

from _engine import cli, task_root

HEADER = "| id | date | card | topic | quote | by | source | asked | replaces | status | note |"
ADD = ("ledger", "add", "--card", "CARD-001", "--topic", "naming of the folder", "--quote", "use the short form",
       "--source", "chat of the day")


def _ledger():
    return importlib.import_module("ledger")


def _profile(root):
    return json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))


def _file(root):
    return root / "mkway" / "ledger" / "ledger.md"


def _rows(root):
    return _ledger().read(root, _profile(root))


@pytest.fixture
def task(tmp_path):
    return task_root(tmp_path)


def test_ledger_add_appends_a_well_formed_row(task):
    """Checks: a new row has the eleven columns and the file keeps its heading, and an add appends without rewriting. E1 part 1"""
    # with no ledger file, ledger add creates <bundle.root>/ledger/ledger.md with the heading ## Ledger and the header row
    # of the format, and appends one row: today's date, id D-1, the card, topic, quote and source as given, by = owner,
    # status in force, the other cells empty. A second add appends a second row and leaves the first line of the file as
    # it was; --status sets the status.
    code, out, err = cli(task, *ADD, session=True)
    assert code == 0, err
    today = datetime.date.today().isoformat()
    lines = _file(task).read_text(encoding="utf-8").splitlines()
    assert lines[0] == "## Ledger"
    assert HEADER in lines
    assert lines[lines.index(HEADER) + 1].startswith("|---")
    assert lines[-1] == (f"| D-1 | {today} | CARD-001 | naming of the folder | use the short form | session:unknown "
                         f"| chat of the day |  |  | in force |  |")
    assert "D-1" in out
    first = _file(task).read_text(encoding="utf-8")
    code, _out, err = cli(task, "ledger", "add", "--card", "CARD-002", "--topic", "t2", "--quote", "q2",
                          "--source", "s2", "--status", "superseded", session=True)
    assert code == 0, err
    second = _file(task).read_text(encoding="utf-8")
    assert second.startswith(first)
    assert second.count("\n") == first.count("\n") + 1
    rows = _rows(task)
    assert [r["id"] for r in rows] == ["D-1", "D-2"]
    assert rows[0] == {"id": "D-1", "date": today, "card": "CARD-001", "topic": "naming of the folder",
                       "quote": "use the short form", "by": "session:unknown", "source": "chat of the day", "asked": "",
                       "replaces": "", "status": "in force", "note": ""}
    assert rows[1]["status"] == "superseded"
    assert rows[1]["card"] == "CARD-002"


def test_a_row_is_added_inside_the_table_when_other_text_follows_it(task):
    """Checks: a new row is added at the end of the table, and the text the owner wrote after it is kept. E1 part 1"""
    # a ledger file that has text after its table (a section the owner wrote) gets the new row at the end of the table,
    # and the text after it is kept.
    cli(task, *ADD, session=True)
    path = _file(task)
    path.write_text(path.read_text(encoding="utf-8") + "\n## Notes\n\nkept text\n", encoding="utf-8", newline="\n")
    code, _out, err = cli(task, "ledger", "add", "--card", "C", "--topic", "t", "--quote", "q", "--source", "s")
    assert code == 0, err
    text = path.read_text(encoding="utf-8")
    assert text.endswith("\n## Notes\n\nkept text\n")
    assert [r["id"] for r in _rows(task)] == ["D-1", "D-2"]
    assert text.index("| D-2 |") < text.index("## Notes")


def test_ledger_ids_follow_the_default_and_the_profile_pattern(tmp_path):
    """Checks: the new id follows the highest id of the file, or the profile's own pattern when it is set. E2 part 1"""
    # without ids.decision_row the id is D-n, one above the highest D-n already in the file (an id of another form is not
    # counted). With the key set, ids that match it are counted, and the new id is written in the form of the file's ids,
    # or, in an empty file, the form the pattern allows (here three digits).
    task = task_root(tmp_path, name="plain")
    cli(task, *ADD, session=True)
    path = _file(task)
    path.write_text(path.read_text(encoding="utf-8") + "| D-7 | 2026-01-01 | C | t | q | owner | s |  |  | in force |  |\n"
                    "| X-99 | 2026-01-01 | C | t | q | owner | s |  |  | in force |  |\n", encoding="utf-8",
                    newline="\n")
    cli(task, "ledger", "add", "--card", "C", "--topic", "t", "--quote", "q", "--source", "s")
    assert [r["id"] for r in _rows(task)] == ["D-1", "D-7", "X-99", "D-8"]
    keyed = task_root(tmp_path, name="keyed", ids={"card_prefix": "CARD", "decision_row": r"^DEC-\d{3}$"})
    results = [cli(keyed, *ADD) for _ in range(2)]
    assert [code for code, _out, _err in results] == [0, 0], results
    assert [r["id"] for r in _rows(keyed)[-2:]] == ["DEC-001", "DEC-002"]
    path = _file(keyed)
    path.write_text(path.read_text(encoding="utf-8") + "| DEC-041 | 2026-01-01 | C | t | q | owner | s |  |  | in force |  |\n"
                    "| Z-500 | 2026-01-01 | C | t | q | owner | s |  |  | in force |  |\n", encoding="utf-8", newline="\n")
    cli(keyed, *ADD)
    assert _rows(keyed)[-1]["id"] == "DEC-042"


def test_ledger_add_is_never_owner_only_and_a_bad_argument_is_a_usage_error(task):
    """Catches: an add that refuses a session, refuses on content, or writes a half row. E3 part 1"""
    # a session and the owner's terminal may both add a row, whatever the card, topic or quote says (a card that is not in
    # the register, an existing quote, no open card: nothing refuses it). A missing or empty argument, or a status with a
    # pipe or a line break, is a usage error (exit 2) and writes nothing.
    results = [cli(task, *ADD, session=session) for session in (True, False)]
    assert all(code == 0 for code, _out, _err in results)
    assert all("owner-only" not in err for _code, _out, err in results)
    assert len(_rows(task)) == 2
    before = _file(task).read_text(encoding="utf-8")
    bad = [("ledger", "add", "--card", "C", "--topic", "t", "--quote", "q"),
           ("ledger", "add", "--card", "C", "--topic", "t", "--source", "s"),
           ("ledger", "add", "--card", "", "--topic", "t", "--quote", "q", "--source", "s"),
           ("ledger", "add", "--card", "C", "--topic", "  ", "--quote", "q", "--source", "s"),
           ("ledger", "add", "--card", "C", "--topic", "t", "--quote", "", "--source", "s"),
           ("ledger", "add", "--card", "C", "--topic", "t", "--quote", "q", "--source", ""),
           ("ledger", "add", "--card", "C", "--topic", "t", "--quote", "q", "--source", "s", "--status", "a|b"),
           ("ledger", "add", "--card", "C", "--topic", "t", "--quote", "q", "--source", "s", "--status", "a\nb"),
           ("ledger", "add", "--card", "C", "--topic", "t", "--quote", "q", "--source", "s", "--status", ""),
           ("ledger",), ("ledger", "remove")]
    codes = [cli(task, *args, session=True)[0] for args in bad]
    assert codes == [2] * len(bad), codes
    assert _file(task).read_text(encoding="utf-8") == before


def test_a_quote_with_a_pipe_survives_a_round_trip(task):
    """Checks: a pipe in the quote is escaped and read back, and a line break becomes one space, with the cells in place. E4 part 1"""
    # a quote with a pipe is written escaped (the table keeps its columns) and read back with the pipe; a line break in a
    # quote or a topic is written, and read back, as one space; the cells around it do not move.
    code, _out, err = cli(task, "ledger", "add", "--card", "C", "--topic", "a\nb", "--quote", "left | right\nnext",
                          "--source", "s", session=True)
    assert code == 0, err
    row = _file(task).read_text(encoding="utf-8").splitlines()[-1]
    assert "left \\| right next" in row
    assert len(re.split(r"(?<!\\)\|", row)) == 13  # an empty part, the eleven cells, an empty part
    got = _rows(task)[0]
    assert got["quote"] == "left | right next"
    assert got["topic"] == "a b"
    assert got["source"] == "s"
    assert got["status"] == "in force"
    assert got["note"] == ""


def test_quote_file_gives_the_quote_of_the_row(task):
    """Catches: a quote typed again by hand, a command that removes the file, or a row written from a bad file. E25 R120"""
    # ledger add --quote-file <path> takes the quote from the file, as written: a pipe and a line break follow the same
    # cell rule as --quote; the file is not deleted; --quote and --quote-file together, a missing file and an empty file
    # are usage errors (exit 2) that write nothing.
    quote = _file(task).parent / "quote.txt"
    quote.parent.mkdir(parents=True, exist_ok=True)
    quote.write_text("left | right\nnext", encoding="utf-8")
    code, _out, err = cli(task, "ledger", "add", "--card", "C", "--topic", "t", "--quote-file", str(quote),
                          "--source", "s", session=True)
    assert code == 0, err
    assert _rows(task)[0]["quote"] == "left | right next"
    assert quote.read_text(encoding="utf-8") == "left | right\nnext"
    before = _file(task).read_text(encoding="utf-8")
    empty = quote.with_name("empty.txt")
    empty.write_text("\n", encoding="utf-8")
    codes = [cli(task, "ledger", "add", "--card", "C", "--topic", "t", "--source", "s", *extra, session=True)[0]
             for extra in (("--quote", "q", "--quote-file", str(quote)), ("--quote-file", str(quote.with_name("none.txt"))),
                           ("--quote-file", str(empty)))]
    assert codes == [2, 2, 2], codes
    assert _file(task).read_text(encoding="utf-8") == before


@pytest.mark.parametrize("content,want", [
    pytest.param(b"use the short form\n", "use the short form", id="one-newline"),
    pytest.param(b"use the short form\r\n", "use the short form", id="crlf"),
    pytest.param(b"use the short form\n\n", "use the short form\n", id="second-newline-kept"),
    pytest.param(b"  use the short form  ", "  use the short form  ", id="spaces-kept"),
])
def test_quote_file_loses_one_trailing_newline_only(task, content, want):
    """Checks: the quote of a file loses one trailing line break and nothing more, and the row takes it. E26 R120"""
    # the quote is the file content with one trailing line break stripped (\n or \r\n); a second line break and the white
    # space around the text stay in the content (the row cell then trims them as for --quote).
    quote = _file(task).parent / "quote.txt"
    quote.parent.mkdir(parents=True, exist_ok=True)
    quote.write_bytes(content)
    assert _ledger().quote_from_file(str(quote)) == want, content
    quote.write_bytes(b"use the short form\n")
    code, _out, err = cli(task, "ledger", "add", "--card", "C", "--topic", "t", "--quote-file", str(quote),
                          "--source", "s", session=True)
    assert code == 0, err
    assert _rows(task)[0]["quote"] == "use the short form"
