"""Card MW-015: a session never writes the owner's words in the ledger (`by` of `ledger add` and `ask default`).
Synthetic task roots only; no task data."""
import json

import pytest

from _engine import cli, gate_call, task_root
from _mw014 import PAST, write_ask
import cardtool
from _mw119 import as_session, make_lead
import gate_lock
import ledger


@pytest.fixture
def task(tmp_path):
    return task_root(tmp_path)


def _rows(root):
    return ledger.read(root, json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8")))


def _add(root, *extra, session=True):
    return cli(root, "ledger", "add", "--card", "CARD-001", "--topic", "a topic", "--quote", "a quote",
               "--source", "a source", *extra, session=session)


def test_the_default_by_of_a_session_is_its_session_id(task):
    """Catches: a session row labelled as the owner (E1)."""
    cardtool.issue_by_permit(task / "mkway" / "state", "s-abc")
    code, _out, err = _add(task)
    assert code == 0, err
    assert [r["by"] for r in _rows(task)] == ["session:s-abc"]
    assert _add(task)[0] == 0
    assert _rows(task)[1]["by"] == "session:unknown"


def test_without_a_permit_the_by_is_session_unknown(task):
    """Catches: a guessed id, or the owner's label as the fallback (E2)."""
    assert _add(task)[0] == 0
    assert [r["by"] for r in _rows(task)] == ["session:unknown"]


def test_the_owners_terminal_writes_owner(task):
    """Checks: with no `CLAUDECODE` (the owner's terminal) the by is `owner`, and `--by <text>` there is taken as typed (E3)."""
    assert _add(task, session=False)[0] == 0
    assert _add(task, "--by", "other words", session=False)[0] == 0
    assert [r["by"] for r in _rows(task)] == ["owner", "other words"]


@pytest.mark.parametrize("word", [pytest.param("owner", id="lower"), pytest.param("Owner", id="capitalised")])
def test_a_session_passing_by_owner_is_refused(task, word):
    """Catches: a session that signs the owner's name, in any letter case (E4)."""
    code, _out, err = _add(task, "--by", word)
    assert code == 1
    assert "ledger-by-owner" in err
    assert "only the owner's terminal writes by=owner" in err
    assert _rows(task) == []


def test_ask_answered_writes_owner(task, tmp_path):
    """Checks: `ask answered` records the owner's answer from the quote file, by the lead's session, never by owner (E5, MW119-D1)."""
    quote = tmp_path / "quote.txt"
    quote.write_text("Take B.\n", encoding="utf-8")
    write_ask(task, "t")
    make_lead(task, "s-abc")  # MW119-D1: the lead records the answer
    assert as_session(task, "s-abc", "ask", "answered", "t", "--quote-file", str(quote))[0] == 0
    assert [(r["by"], r["quote"]) for r in _rows(task)] == [("session:s-abc", "Take B.")]  # MW119-D1: never by owner


def test_ask_default_writes_the_session_and_default_taken(task):
    """Catches: a default taken by a session that reads as the owner's word (E6)."""
    write_ask(task, "t", deadline=PAST)
    cardtool.issue_by_permit(task / "mkway" / "state", "s-abc")
    assert cli(task, "ask", "default", "t", session=True)[0] == 0
    assert [r["by"] for r in _rows(task)] == ["session:s-abc"]
    text = (task / "mkway" / "asks" / "t_ask.md").read_text(encoding="utf-8")
    assert "status: default-taken" in text
    write_ask(task, "u", deadline=PAST)
    assert cli(task, "ask", "default", "u", session=True)[0] == 0
    assert _rows(task)[-1]["by"] == "session:unknown"


def test_the_lock_gate_leaves_the_permit_for_the_ledger_and_default_commands(task):
    """Checks: the lock gate leaves a permit for each ledger and default command, so the CLI learns the session id (E1 E6)."""
    state = task / "mkway" / "state"
    gate_call(gate_lock.check, task, tool="Bash",
              tool_input={"command": "python mkway/engine/mkway.py ledger add --card C --topic t --quote q --source s"},
              session="s-hook")
    assert cardtool.take_by_permit(state) == "s-hook"
    assert cardtool.take_by_permit(state) is None
    gate_call(gate_lock.check, task, tool="Bash", tool_input={"command": "python mkway/engine/mkway.py ask default t"},
              session="s-hook")
    assert cardtool.take_by_permit(state) == "s-hook"
    assert cardtool.take_by_permit(state) is None
