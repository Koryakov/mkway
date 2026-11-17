"""Card MW-114: the readers of pytest node ids take the whole id, also when its parameter part holds a space. Pure text in,
ids out: no disk, no git, no process. Every id below holds a space (an id with none was read right before the card, so a test
of it would not be red). The expected values are literals or parametrize values, never computed by the code under test.
Synthetic strings only."""
import pytest

import _engine  # noqa: F401  (puts the engine folder on the import path)
import cardtool
import gate_commit_tests as gct

FILE = "tests/test_q.py::test_q"
CASES = {
    "space": f"{FILE}[select a from b where c = 1]",
    "semicolon": f"{FILE}[drop x; select 1]",
    "brackets": f"{FILE}[a[0] b[1]]",
    "quotes": f"{FILE}[it's a \"b\"]",
    "unicode": f"{FILE}[é ü]",
    "escaped-newline": FILE + "[a\\nb c]",
    "status-word": f"{FILE}[a PASSED b]",
    "status-word-last": f"{FILE}[x FAILED]",
}
IDENTS = list(CASES.values())
NAMES = list(CASES)
WORDS = ["PASSED", "FAILED", "ERROR", "SKIPPED", "XFAIL", "XPASS"]
MARKS = ["[ 50%]", "[100%]", "[  7%]"]

# summary ids: a space, " - " inside the brackets, "]" inside the parameter
SUMMARY = {"space": f"{FILE}[a b]", "dash-in-id": f"{FILE}[a - b]", "bracket-in-id": f"{FILE}[a]b c]"}
MESSAGES = {"plain": "assert 1 == 2", "dash": "x - y - z", "bracket-dash": "[a] - b"}


class Ctx:
    session_id = "s1"
    env = {}


def row_of(text):
    """The record row of a run that printed `text` (pure: no disk)."""
    return gct._row(Ctx, "tree", ["python", "-m", "pytest"], 1, text.encode("utf-8"), b"", 1.0, 600, "p")


@pytest.mark.parametrize("word", WORDS)
@pytest.mark.parametrize("ident", IDENTS, ids=NAMES)
def test_a_verbose_line_gives_the_whole_id_and_its_status(ident, word):
    """Catches: a `-v` line whose id holds a space, read as no test, so a recorded red id counts as gone (DD-013)."""
    assert gct.STATUS.findall(f"{ident} {word}\n") == [(ident, word)]


@pytest.mark.parametrize("mark", MARKS)
@pytest.mark.parametrize("ident", IDENTS, ids=NAMES)
def test_a_verbose_line_with_a_progress_mark_gives_the_whole_id(ident, mark):
    """Catches: a progress mark read as part of the id, or a line with a mark not read at all."""
    assert gct.STATUS.findall(f"{ident} PASSED   {mark}\n") == [(ident, "PASSED")]


@pytest.mark.parametrize("word", ["SKIPPED", "XFAIL"])
@pytest.mark.parametrize("ident", IDENTS, ids=NAMES)
def test_a_verbose_line_with_a_reason_after_the_status_gives_the_whole_id(ident, word):
    """Catches: a skipped or xfail line, which pytest prints with its reason in brackets, not read, so a skip looks deleted."""
    assert gct.STATUS.findall(f"{ident} {word} (not today, see x)   [ 50%]\n") == [(ident, word)]


@pytest.mark.parametrize("ident", IDENTS, ids=NAMES)
def test_a_verbose_line_with_trailing_spaces_and_a_carriage_return_gives_the_whole_id(ident):
    """Catches: trailing spaces or a carriage return kept in the id, so it never matches the recorded one."""
    assert gct.STATUS.findall(f"{ident} FAILED  \r\n") == [(ident, "FAILED")]


def test_a_status_word_inside_an_id_does_not_end_it():
    """Catches: the id cut at a status word that is part of the parameter, not the last one of the line."""
    assert gct.STATUS.findall(f"{FILE}[a PASSED b] FAILED [ 50%]\n") == [(f"{FILE}[a PASSED b]", "FAILED")]


def test_a_line_whose_status_word_is_not_last_names_no_test():
    """Checks: a line with a status word in the middle and none at its end is no status line, so no id is invented."""
    assert gct.STATUS.findall(f"{FILE}[a PASSED b]\n") == []


@pytest.mark.parametrize("ident", IDENTS, ids=NAMES)
def test_a_collect_line_gives_the_whole_id(ident):
    """Catches: a `--collect-only -q` line cut at its first space, so the id of a parametrized case is a prefix."""
    assert gct.collected_ids(f"{ident}\n\n1 test collected in 0.01s\n") == {ident}


@pytest.mark.parametrize("ident", IDENTS, ids=NAMES)
def test_a_collect_line_with_trailing_spaces_and_a_carriage_return_gives_the_whole_id(ident):
    """Catches: trailing spaces or a carriage return kept in a collected id."""
    assert gct.collected_ids(f"{ident}  \r\n\r\n1 test collected in 0.01s\r\n") == {ident}


@pytest.mark.parametrize("ident", list(SUMMARY.values()), ids=list(SUMMARY))
def test_a_failed_summary_line_gives_the_whole_id(ident):
    """Catches: a `FAILED <id> - <message>` line cut at the first space, so failed_ids holds a prefix of the id."""
    text = f"short test summary info\nFAILED {ident} - assert 1 == 2\n1 failed in 0.1s\n"
    assert row_of(text)["failed_ids"] == [ident]


@pytest.mark.parametrize("ident", list(SUMMARY.values()), ids=list(SUMMARY))
def test_an_error_summary_line_gives_the_whole_id_and_its_message(ident):
    """Catches: an `ERROR <id> - <message>` line cut at the first space, so the setup error has a prefix for its id."""
    row = row_of(f"short test summary info\nERROR {ident} - fixture x not found\n1 error in 0.1s\n")
    assert row["failed_ids"] == [ident]
    assert row["setup_errors"] == {ident: "fixture x not found"}


@pytest.mark.parametrize("word", ["FAILED", "ERROR"])
@pytest.mark.parametrize("message", list(MESSAGES.values()), ids=list(MESSAGES))
def test_a_message_holding_a_dash_does_not_cut_the_id(message, word):
    """Catches: an id ended at a « - » that belongs to the message, or a message that swallows the id's end."""
    ident = f"{FILE}[a b]"
    assert row_of(f"{word} {ident} - {message}\n")["failed_ids"] == [ident]


def test_a_printed_id_decides_where_a_summary_id_ends():
    """Catches: a summary id read by a guess when the run printed the id whole on a `-v` line (rule 1)."""
    ident = f"{FILE}[a] - b]"
    text = f"{ident} FAILED   [100%]\nFAILED {ident} - assert 0\n"
    assert row_of(text)["failed_ids"] == [ident]


def test_the_longest_printed_id_is_taken():
    """Catches: a summary id that stops at a shorter printed id that is only the start of it."""
    short, long_ = f"{FILE}[a]", f"{FILE}[a] - b]"
    text = f"{short} PASSED [ 50%]\n{long_} FAILED [100%]\nFAILED {short} - e\nFAILED {long_} - e\n"
    assert row_of(text)["failed_ids"] == [short, long_]


def test_a_new_run_row_carries_the_reader_version():
    """Catches: a kept row with no reader version, which a later engine cannot tell from a row of the older reader."""
    assert row_of(f"FAILED {FILE}[a b] - e\n")["reader"] == 2


def test_the_close_refusal_lists_a_failing_id_with_a_space_whole(tmp_path, monkeypatch):
    """Catches: the close refusal listing a failing id cut at its first space, so the card cannot name the case."""
    out = b"FAILED tests/test_q.py::test_q[a b] - assert 0\n1 failed in 0.1s\n"
    monkeypatch.setattr(cardtool.runner, "run_tree", lambda *args, **kw: (1, out, b""))
    assert cardtool._nodes_problem(tmp_path, {}, ["tests/test_q.py"], "") == "1 failing: tests/test_q.py::test_q[a b]"
