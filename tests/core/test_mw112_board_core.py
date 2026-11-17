"""Card MW-112 part (iii) (record R3), layer core: the pure functions of `engine/board.py` that make the lines `mkway board`
adds. No file, no git, no clock but the one a test gives. Synthetic ids and paths only."""
import datetime
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/: the shared helpers and `_engine`
import _engine  # noqa: F401,E402  (puts engine/ on the path)
import board  # noqa: E402

NOW = datetime.datetime(2031, 5, 6, 12, 0, tzinfo=datetime.timezone.utc)


def _at(**delta):
    return (NOW - datetime.timedelta(**delta)).isoformat(timespec="milliseconds")


def test_old_red_lines_name_each_test_with_its_owner_card():
    """Catches: an old red shown without its owner card, or an orphan (card null) shown as if a card held it."""
    rows = [{"tree": "t1", "old_red": [{"test": "tests/a.py::test_one", "card": "CARD-001"},
                                       {"test": "tests/b.py::test_two", "card": None}]}]
    assert board.old_red_lines(rows) == ["old red: tests/a.py::test_one (owner card CARD-001)",
                                         "old red: tests/b.py::test_two (no open card holds it)"]


def test_old_red_is_read_from_the_last_row_of_the_newest_tree():
    """Catches: an old red of an earlier commit shown after a later commit has none (key absent or empty means none)."""
    rows = [{"tree": "t1", "old_red": [{"test": "tests/a.py::test_one", "card": "CARD-001"}]},
            {"tree": "t2", "old_red": []}]
    assert board.old_red_lines(rows) == []


def test_old_red_takes_the_last_row_of_a_tree_that_was_appended_again():
    """Checks: the nearest allow of the test above: the same tree's later row carries the key and is the one read."""
    rows = [{"tree": "t1"}, {"tree": "t1", "old_red": [{"test": "tests/a.py::test_one", "card": "CARD-001"}]}]
    assert board.old_red_lines(rows) == ["old red: tests/a.py::test_one (owner card CARD-001)"]


@pytest.mark.parametrize("bad", [[{"tree": "t1", "old_red": "tests/a.py::test_one"}], [{"tree": "t1", "old_red": [5, None]}], []])
def test_an_old_red_value_of_the_wrong_shape_adds_no_line(bad):
    """Catches: a board that raises, or invents a line, on a record row it can not read."""
    assert board.old_red_lines(bad) == []


@pytest.mark.parametrize("delta, text", [({"seconds": 20}, "under 1 min"), ({"minutes": 7}, "7 min"),
                                         ({"hours": 2, "minutes": 5}, "2 h 5 min"), ({"days": 3, "hours": 4}, "3 d 4 h")])
def test_the_age_of_an_unacked_item(delta, text):
    """Catches: an age that is not the time since the row was written, in the units a reader scans."""
    assert board.age_text(_at(**delta), NOW) == text


def test_an_age_of_a_row_with_no_time_is_not_established():
    """Catches: an invented age for a row whose time can not be read."""
    assert board.age_text(None, NOW) == "not established"


def test_uncommitted_files_are_shown_with_the_card_holder_and_orderer():
    """Catches: uncommitted files of a card shown with no owner, so nobody knows whom to ask."""
    lines = board.uncommitted_lines({"CARD-001": ["a.py", "b.py"]}, {"CARD-001": "abcdef123456"}, {"CARD-001": "owner"}, set())
    assert lines == ["uncommitted files of CARD-001: 2 (held by abcdef12, ordered by owner): a.py, b.py"]


def test_the_files_of_an_ended_session_are_marked_and_name_the_orderer():
    """Catches: R3: the files of a session that ended not told apart from live work, or shown without the orderer."""
    lines = board.uncommitted_lines({"CARD-001": ["a.py"]}, {"CARD-001": "abcdef123456"}, {"CARD-001": "lead-9"}, {"CARD-001"})
    assert lines == ["files of an ended session: CARD-001: 1 (held by abcdef12, ordered by lead-9): a.py"]


def test_a_card_with_no_uncommitted_file_adds_no_line():
    """Catches: a line for every open card, drowning the files that are really left."""
    assert board.uncommitted_lines({"CARD-001": []}, {"CARD-001": "abcdef123456"}, {}, set()) == []


def test_a_taken_card_with_no_result_from_its_holder_says_no_done_file():
    """Catches: R284 (card 5): a taken card whose builder sent no result is not named on the board."""
    cards = [("CARD-001", "abcdef123456", _at(hours=2))]
    assert board.no_done_lines(cards, []) == ["card CARD-001: no DONE file"]


def test_a_result_row_of_the_holder_after_the_take_is_the_done_file():
    """Checks: the nearest allow of the test above: a result row from the holder written after the take clears the line."""
    cards = [("CARD-001", "abcdef123456", _at(hours=2))]
    rows = [{"from": "abcdef123456", "kind": "result", "ts": _at(hours=1)}]
    assert board.no_done_lines(cards, rows) == []


@pytest.mark.parametrize("row", [{"from": "abcdef123456", "kind": "result", "ts": None},
                                 {"from": "abcdef123456", "kind": "question", "ts": "2031-05-06T11:00:00+00:00"},
                                 {"from": "zzzz", "kind": "result", "ts": "2031-05-06T11:00:00+00:00"},
                                 {"from": "abcdef123456", "kind": "result", "ts": "2031-05-06T09:00:00+00:00"}])
def test_a_row_that_is_not_the_holders_result_after_the_take_does_not_clear_the_line(row):
    """Catches: a question, another session's result, a result from before the take, or one with no time clearing the line."""
    cards = [("CARD-001", "abcdef123456", "2031-05-06T10:00:00+00:00")]
    assert board.no_done_lines(cards, [row]) == ["card CARD-001: no DONE file"]


def test_a_failed_agent_record_stays_on_the_board_until_a_later_agent_row_is_written():
    """Catches: R271c: the failed agent record shown once and lost, or shown after a row was written again."""
    failed = [{"reason_id": "agent-record-failed", "kind": "warn", "time": "2031-05-06T10:00:00.000+00:00",
               "target": None, "message": "m"}]
    assert board.agent_failed_lines(failed, []) == ["agent record failed at 2031-05-06T10:00:00.000+00:00: the agent "
                                                    "result is not saved until an agent row is written again"]
    assert board.agent_failed_lines(failed, [{"kind": "end", "ended": "2031-05-06T10:05:00.000+00:00"}]) == []
    assert board.agent_failed_lines(failed, [{"kind": "end", "ended": "2031-05-06T09:00:00.000+00:00"}]) != []
