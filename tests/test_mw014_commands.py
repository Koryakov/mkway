"""Card MW-014, part 4: `mkway ask default <id>` and `mkway ask answered <id>`. Synthetic task roots only; no task data."""
import json

import pytest

import _mw014
from _engine import cli, jsonl, task_root
from _mw014 import FAR, PAST, write_ask
import ledger
import records


@pytest.fixture
def task(tmp_path):
    return task_root(tmp_path)


def _status(root, name="t"):
    text = (root / "mkway" / "asks" / f"{name}_ask.md").read_text(encoding="utf-8")
    return [l for l in text.splitlines() if l.startswith("status:")]


def _ledger(root):
    return ledger.read(root, json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8")))


def _reasons(root):
    return [(r["reason_id"], r["kind"]) for r in jsonl(root / "mkway" / "state" / "refusals.jsonl")]


def test_the_default_is_refused_before_the_deadline_and_with_no_deadline(task):
    """E13: `ask default` is refused `ask-deadline-not-passed` while the deadline is ahead, and when the ask has no
    deadline; the file keeps `status: open` and the ledger gets no row. Catches: a session that takes the default
    the minute after it asked."""
    for deadline in (FAR, "none"):
        write_ask(task, "t", deadline=deadline)
        code, out, err = cli(task, "ask", "default", "t", session=True)
        assert code == 1 and "ask-deadline-not-passed" in err, deadline
        assert _status(task) == ["status: open"] and _ledger(task) == []


def test_the_default_of_an_irreversible_ask_stays_waiting(task):
    """E14: for `reversible: no` the command is refused `ask-not-reversible` with the text «stays waiting; the owner
    decides», even past the deadline; nothing changes. Catches: a default taken for a delete, a lock, a window or the
    owner's own words."""
    write_ask(task, "t", deadline=PAST, reversible="no")
    code, out, err = cli(task, "ask", "default", "t", session=True)
    assert code == 1 and "ask-not-reversible" in err and "stays waiting; the owner decides" in err
    assert _status(task) == ["status: open"] and _ledger(task) == []
    assert ("ask-not-reversible", "refuse") in _reasons(task)


def test_other_refusals_name_their_reason(task):
    """E15: an unknown id (also a path, not a name) is `ask-unknown`; an ask that is not open is `ask-not-open`; an ask
    whose default is `none` is `ask-no-default`. Catches: a command that guesses a file, or takes «none» as a default."""
    for bad in ("nope", "../t", "sub/t"):
        code, _out, err = cli(task, "ask", "default", bad, session=True)
        assert code == 1 and "ask-unknown" in err, bad
    write_ask(task, "t", deadline=PAST, status="answered")
    assert "ask-not-open" in cli(task, "ask", "default", "t", session=True)[2]
    write_ask(task, "t", deadline=PAST, default="none")
    assert "ask-no-default" in cli(task, "ask", "default", "t", session=True)[2]
    assert _ledger(task) == []


@pytest.mark.parametrize("session", [True, False])
def test_the_default_is_taken_when_reversible_and_past_the_deadline(task, session):
    """E15: past the deadline, `reversible: yes`: the command writes the ledger row «default taken: <default text>, ask
    <id>», sets `status: default-taken` (the other lines stay), logs `ask-default-taken`, and leaves the record
    `ask-default` that the start line counts (a session's through the `post` group: it prints `mkway-ok`, the owner's
    terminal appends its own). A second call is `ask-not-open`. Catches: a default that leaves no trace, or is taken
    twice."""
    write_ask(task, "t", deadline=PAST, default="keep option A", blocked="the report part")
    code, out, err = cli(task, "ask", "default", "t", session=session)
    assert code == 0, err
    (row,) = _ledger(task)
    assert row["quote"] == "default taken: keep option A, ask t" and row["status"] == "in force"
    assert _status(task) == ["status: default-taken"]
    text = (task / "mkway" / "asks" / "t_ask.md").read_text(encoding="utf-8")
    assert "default: keep option A" in text and "blocked: the report part" in text and text.startswith("Which option?")
    assert ("ask-default-taken", "log") in _reasons(task)
    if session:
        assert "mkway-ok ask-default t " in out
    else:
        assert [r["value"] for r in records.rows(task / "mkway" / "state") if r["kind"] == "ask-default"] == ["t"]
    assert "ask-not-open" in cli(task, "ask", "default", "t", session=session)[2]
    assert len(_ledger(task)) == 1


def test_the_status_line_keeps_the_file_otherwise(task):
    """E15: only the first `status:` line changes; a CRLF file stays CRLF. Catches: a rewrite that touches the owner's
    text."""
    path = write_ask(task, "t", deadline=PAST)
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    assert cli(task, "ask", "default", "t", session=True)[0] == 0
    data = path.read_bytes()
    assert b"status: default-taken\r\n" in data and data.count(b"\r\n") == data.count(b"\n")


def test_answered_writes_the_owners_words_from_the_quote_file(task, tmp_path):
    """E16: `ask answered <id> --quote-file <path>` sets `status: answered` and writes the ledger row with the file's
    text (one trailing line break stripped) as the quote; it needs no deadline and works for `reversible: no`;
    `--quote` is the plain form; an unreadable or empty quote is a usage error that changes nothing; an ask that is not
    open is `ask-not-open`. Catches: an answer recorded without the owner's words, or a file left half changed."""
    quote = tmp_path / "quote.txt"
    quote.write_text("Take B, but not before Friday.\n", encoding="utf-8")
    write_ask(task, "t", deadline=FAR, reversible="no")
    code, out, err = cli(task, "ask", "answered", "t", "--quote-file", str(quote), session=True)
    assert code == 0, err
    (row,) = _ledger(task)
    assert row["quote"] == "Take B, but not before Friday." and _status(task) == ["status: answered"]
    assert row["topic"] == "ask t answered" and "mkway/asks/t_ask.md" in row["source"]
    assert ("ask-answered", "log") in _reasons(task)
    assert "ask-not-open" in cli(task, "ask", "answered", "t", "--quote", "x", session=True)[2]
    write_ask(task, "u")
    assert cli(task, "ask", "answered", "u", "--quote-file", str(tmp_path / "missing.txt"), session=True)[0] == 2
    assert cli(task, "ask", "answered", "u", "--quote", "  ", session=True)[0] == 2
    assert cli(task, "ask", "answered", "u", session=True)[0] == 2
    assert _status(task, "u") == ["status: open"] and len(_ledger(task)) == 1
    assert cli(task, "ask", "answered", "u", "--quote", "plain words", session=False)[0] == 0
    assert _ledger(task)[-1]["quote"] == "plain words" and _status(task, "u") == ["status: answered"]


def test_the_ask_commands_are_not_owner_only(task, tmp_path):
    """E15 E16: both commands are a session's commands (the card says so): a session's run is not refused as
    owner-only, and a session's `ask answered` card is the one the writing session holds. Catches: a command the session
    cannot run, so it can never free its own ask."""
    records.append(task / "mkway" / "state", "s1", "take", "CARD-001")
    write_ask(task, "t", session="s1")
    code, _out, err = cli(task, "ask", "answered", "t", "--quote", "ok", session=True)
    assert code == 0 and "owner-only" not in err
    assert _ledger(task)[0]["card"] == "CARD-001"
