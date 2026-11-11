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
    """E1 (part 1): with no ledger file, `ledger add` creates `<bundle.root>/ledger/ledger.md` with the heading
    `## Ledger` and the header row of the format, and appends one row: today's date, id `D-1`, the card, topic, quote
    and source as given, `by` = `owner`, status `in force`, the other cells empty. A second add appends a second row
    and leaves the first line of the file as it was; `--status` sets the status. Catches: a row with a wrong column,
    a lost heading, or an add that rewrites what was there."""
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
    assert second.startswith(first) and second.count("\n") == first.count("\n") + 1
    rows = _rows(task)
    assert [r["id"] for r in rows] == ["D-1", "D-2"]
    assert rows[0] == {"id": "D-1", "date": today, "card": "CARD-001", "topic": "naming of the folder",
                       "quote": "use the short form", "by": "session:unknown", "source": "chat of the day", "asked": "",
                       "replaces": "", "status": "in force", "note": ""}
    assert rows[1]["status"] == "superseded" and rows[1]["card"] == "CARD-002"


def test_a_row_is_added_inside_the_table_when_other_text_follows_it(task):
    """E1 (part 1): a ledger file that has text after its table (a section the owner wrote) gets the new row at the end
    of the table, and the text after it is kept. Catches: a row appended after a note, outside the table."""
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
    """E2 (part 1): without `ids.decision_row` the id is `D-<n>`, one above the highest `D-<n>` already in the file
    (an id of another form is not counted). With the key set, ids that match it are counted, and the new id is written
    in the form of the file's ids, or, in an empty file, the form the pattern allows (here three digits).
    Catches: an id that repeats, restarts, or does not match the profile's own pattern."""
    task = task_root(tmp_path, name="plain")
    cli(task, *ADD, session=True)
    path = _file(task)
    path.write_text(path.read_text(encoding="utf-8") + "| D-7 | 2026-01-01 | C | t | q | owner | s |  |  | in force |  |\n"
                    "| X-99 | 2026-01-01 | C | t | q | owner | s |  |  | in force |  |\n", encoding="utf-8",
                    newline="\n")
    cli(task, "ledger", "add", "--card", "C", "--topic", "t", "--quote", "q", "--source", "s")
    assert [r["id"] for r in _rows(task)] == ["D-1", "D-7", "X-99", "D-8"]
    keyed = task_root(tmp_path, name="keyed", ids={"card_prefix": "CARD", "decision_row": r"^DEC-\d{3}$"})
    for expected in ("DEC-001", "DEC-002"):
        code, _out, err = cli(keyed, *ADD)
        assert code == 0, err
        assert _rows(keyed)[-1]["id"] == expected
    path = _file(keyed)
    path.write_text(path.read_text(encoding="utf-8") + "| DEC-041 | 2026-01-01 | C | t | q | owner | s |  |  | in force |  |\n"
                    "| Z-500 | 2026-01-01 | C | t | q | owner | s |  |  | in force |  |\n", encoding="utf-8", newline="\n")
    cli(keyed, *ADD)
    assert _rows(keyed)[-1]["id"] == "DEC-042"


def test_ledger_add_is_never_owner_only_and_a_bad_argument_is_a_usage_error(task):
    """E3 (part 1): a session and the owner's terminal may both add a row, whatever the card, topic or quote says (a
    card that is not in the register, an existing quote, no open card: nothing refuses it). A missing or empty
    argument, or a status with a pipe or a line break, is a usage error (exit 2) and writes nothing.
    Catches: an add that refuses a session, refuses on content, or writes a half row."""
    for session in (True, False):
        code, _out, err = cli(task, *ADD, session=session)
        assert code == 0 and "owner-only" not in err, (session, err)
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
    for args in bad:
        code, _out, _err = cli(task, *args, session=True)
        assert code == 2, args
    assert _file(task).read_text(encoding="utf-8") == before


def test_a_quote_with_a_pipe_survives_a_round_trip(task):
    """E4 (part 1): a quote with a pipe is written escaped (the table keeps its columns) and read back with the pipe;
    a line break in a quote or a topic is written, and read back, as one space; the cells around it do not move.
    Catches: a pipe that splits the quote into two cells, or a line break that ends the row."""
    code, _out, err = cli(task, "ledger", "add", "--card", "C", "--topic", "a\nb", "--quote", "left | right\nnext",
                          "--source", "s", session=True)
    assert code == 0, err
    row = _file(task).read_text(encoding="utf-8").splitlines()[-1]
    assert "left \\| right next" in row
    assert len(re.split(r"(?<!\\)\|", row)) == 13  # an empty part, the eleven cells, an empty part
    got = _rows(task)[0]
    assert got["quote"] == "left | right next" and got["topic"] == "a b"
    assert got["source"] == "s" and got["status"] == "in force" and got["note"] == ""


def test_quote_file_gives_the_quote_of_the_row(task):
    """E25 (R120): `ledger add --quote-file <path>` takes the quote from the file, as written: a pipe and a line break
    follow the same cell rule as `--quote`; the file is not deleted; `--quote` and `--quote-file` together, a missing
    file and an empty file are usage errors (exit 2) that write nothing. Catches: a quote typed again by hand, a
    command that removes the file, or a row written from a bad file."""
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
    for extra in (("--quote", "q", "--quote-file", str(quote)), ("--quote-file", str(quote.with_name("none.txt"))),
                  ("--quote-file", str(empty))):
        code, _out, _err = cli(task, "ledger", "add", "--card", "C", "--topic", "t", "--source", "s", *extra,
                               session=True)
        assert code == 2, extra
    assert _file(task).read_text(encoding="utf-8") == before


def test_quote_file_loses_one_trailing_newline_only(task):
    """E26 (R120): the quote is the file content with one trailing line break stripped (`\n` or `\r\n`); a second
    line break and the white space around the text stay in the content (the row cell then trims them as for
    `--quote`). Catches: a quote that keeps the editor's final newline, or one that is trimmed beyond it."""
    quote = _file(task).parent / "quote.txt"
    quote.parent.mkdir(parents=True, exist_ok=True)
    for content, want in ((b"use the short form\n", "use the short form"),
                          (b"use the short form\r\n", "use the short form"),
                          (b"use the short form\n\n", "use the short form\n"),
                          (b"  use the short form  ", "  use the short form  ")):
        quote.write_bytes(content)
        assert _ledger().quote_from_file(str(quote)) == want, content
    quote.write_bytes(b"use the short form\n")
    code, _out, err = cli(task, "ledger", "add", "--card", "C", "--topic", "t", "--quote-file", str(quote),
                          "--source", "s", session=True)
    assert code == 0, err
    assert _rows(task)[0]["quote"] == "use the short form"
