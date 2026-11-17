"""Card MW-082 (decisions: R197 A, R197a), guard 2, rows E12 to E15: the register reader does not depend on row order (a
union merge leaves added rows in any order) and loses no row after a stray line. Synthetic registers; the expected values
are written here."""
import pytest

import _engine
import register

PROFILE = _engine.make_profile()
HEAD = "# Card register\n\n| Id | Title | Status | Paths | Folder |\n|---|---|---|---|---|\n"
ROW_A = "| MW-001 | first | closed | `p` | `cards/MW-001-a` |\n"
ROW_B = "| MW-002 | second | open | `p` | `cards/MW-002-b` |\n"
ROW_C = "| MW-003 | third | closed | `p` | `cards/MW-003-c` |\n"
ORDER_ONE = HEAD + ROW_A + ROW_B + ROW_C
ORDER_TWO = HEAD + ROW_C + ROW_A + ROW_B
STATUS_BY_ID = {"MW-001": "closed", "MW-002": "open", "MW-003": "closed"}


def _status_by_id(rows):
    return {r["id"]: r["status"] for r in rows}


@pytest.mark.parametrize("text", [ORDER_ONE, ORDER_TWO], ids=["order-one", "order-two"])
def test_parse_gives_the_same_rows_in_either_order(text):
    """Checks: the rows read by id are the same whichever order the file lists them."""
    assert _status_by_id(register.parse(text, PROFILE)) == STATUS_BY_ID


@pytest.mark.parametrize("text", [ORDER_ONE, ORDER_TWO], ids=["order-one", "order-two"])
def test_find_gives_the_same_row_in_either_order(text):
    """Checks: `find` answers the row of one id whichever order the file lists the rows."""
    row = register.find(register.parse(text, PROFILE), "MW-002")
    assert (row["title"], row["status"], row["folder"]) == ("second", "open", "`cards/MW-002-b`")


@pytest.mark.parametrize("text", [ORDER_ONE, ORDER_TWO], ids=["order-one", "order-two"])
def test_closed_ids_are_the_same_in_either_order(text, tmp_path):
    """Checks: the closed ids are the same set whichever order the file lists the rows."""
    folder = tmp_path / "mkway" / "cards"
    folder.mkdir(parents=True)
    (folder / "REGISTER.md").write_text(text, encoding="utf-8")
    assert register.closed_ids(tmp_path, PROFILE) == {"MW-001", "MW-003"}


@pytest.mark.parametrize("stray", ["\n", "a stray line\n", "<<<<<<< stray\n"], ids=["blank", "text", "marker"])
def test_a_stray_line_between_rows_loses_no_row(stray):
    """Catches: a reader that stops at the first line that is not a table row and drops the rows after it."""
    rows = register.parse(HEAD + ROW_A + stray + ROW_B + ROW_C, PROFILE)
    assert [r["id"] for r in rows] == ["MW-001", "MW-002", "MW-003"]
