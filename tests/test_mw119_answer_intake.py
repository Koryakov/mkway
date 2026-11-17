"""Card MW-119 (fix item 5): `mkway ask answered` runs only in the intake role, the lead. A non-lead session is refused
with the way out; the lead's record is session:<id> + source owner + the verbatim quote, never by owner, with its time;
the ask is freed only by that record. Synthetic task roots only; no task data."""
import json

import pytest

from _engine import jsonl, task_root
from _mw014 import write_ask
from _mw119 import as_session, make_lead
import core_ask
import ledger
import proof

LEAD, OTHER = "s-lead", "s-other"
QUOTE = "Take B, but not before Friday."


@pytest.fixture
def task(tmp_path):
    root = task_root(tmp_path)
    make_lead(root, LEAD)
    write_ask(root, "t")
    return root


def _rows(root):
    return ledger.read(root, json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8")))


def _status(root):
    text = (root / "mkway" / "asks" / "t_ask.md").read_text(encoding="utf-8")
    return [x for x in text.splitlines() if x.startswith("status:")]


def _answers(root):
    return [r for r in jsonl(root / "mkway" / "state" / proof.FILE) if r.get("kind") == "ask-answered"]


def test_a_session_that_is_not_the_lead_is_refused_with_the_way_out(task):
    """Catches: any session writing the owner's words and freeing its own ask (E1)."""
    code, _out, err = as_session(task, OTHER, "ask", "answered", "t", "--quote", QUOTE)
    assert code == 1
    assert "ask-answered-not-lead" in err
    assert "lead" in err and "mkway ask answered" in err  # the way out: the lead records it
    assert (_status(task), _rows(task), _answers(task)) == (["status: open"], [], [])


def test_a_session_with_no_permit_is_refused(task):
    """Catches: an unknown caller treated as the lead (E1)."""
    from _engine import cli
    code, _out, err = cli(task, "ask", "answered", "t", "--quote", QUOTE, session=True)
    assert (code, "ask-answered-not-lead" in err, _status(task)) == (1, True, ["status: open"])


def test_the_lead_records_session_and_never_the_owner(task):
    """Catches: the owner's label on a row a session wrote (E2)."""
    code, _out, err = as_session(task, LEAD, "ask", "answered", "t", "--quote", QUOTE)
    assert code == 0, err
    (row,) = _rows(task)
    assert (row["by"], row["quote"]) == (f"session:{LEAD}", QUOTE)
    assert row["by"] != "owner" and row["source"].startswith("owner")


def test_the_ask_is_freed_only_by_the_leads_record(task):
    """Catches: an ask freed by a refused call (E3)."""
    assert as_session(task, OTHER, "ask", "answered", "t", "--quote", QUOTE)[0] == 1
    assert _status(task) == ["status: open"]
    assert as_session(task, LEAD, "ask", "answered", "t", "--quote", QUOTE)[0] == 0
    assert _status(task) == ["status: answered"]


def test_the_record_row_has_session_source_quote_and_time(task):
    """Catches: a record the board cannot list since the last start (E4)."""
    assert as_session(task, LEAD, "ask", "answered", "t", "--quote", QUOTE)[0] == 0
    (rec,) = _answers(task)
    assert (rec["ask"], rec["session"], rec["source"], rec["quote"]) == ("t", LEAD, "owner", QUOTE)
    assert rec["time"] and "by" not in rec


def test_the_decision_names_the_way_out_for_a_non_lead():
    """Catches: a refusal with no way out (E1)."""
    d = core_ask.answer_decision(OTHER, False)
    assert (d.kind, d.reason) == ("refuse", "ask-answered-not-lead")
    assert "lead" in d.text
    assert core_ask.answer_decision(LEAD, True).kind == "allow"


def test_the_way_out_of_ask_answered_not_lead_is_the_lead_who_records_it(task):
    """Checks: a non-lead session's answer is refused ask-answered-not-lead and the text names the lead; the lead runs
    the same command with the same words and the ask is answered."""
    code, _out, err = as_session(task, OTHER, "ask", "answered", "t", "--quote", QUOTE)
    assert (code, "ask-answered-not-lead" in err, _status(task)) == (1, True, ["status: open"])
    code, _out, err = as_session(task, LEAD, "ask", "answered", "t", "--quote", QUOTE)
    assert code == 0, err
    assert _status(task) == ["status: answered"]


def test_the_owner_terminal_may_answer_with_by_owner(task):
    """Catches: the owner's own terminal refused, or its row labelled as a session (R287b)."""
    from _engine import cli
    code, _out, err = cli(task, "ask", "answered", "t", "--quote", QUOTE, session=False)
    assert code == 0, err
    (row,) = _rows(task)
    assert (row["by"], row["quote"], _status(task)) == ("owner", QUOTE, ["status: answered"])
