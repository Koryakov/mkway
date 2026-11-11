"""Card MW-015: a session never writes the owner's words in the ledger (`by` of `ledger add` and `ask default`).
Synthetic task roots only; no task data."""
import json

import pytest

from _engine import cli, gate_call, task_root
from _mw014 import PAST, write_ask
import cardtool
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
    """E1: a session's `ledger add` with no `--by` writes by=`session:<session id>`, the id read from the one-use permit
    the lock gate left; the permit is used once. Catches: a session row labelled as the owner."""
    cardtool.issue_by_permit(task / "mkway" / "state", "s-abc")
    code, _out, err = _add(task)
    assert code == 0, err
    assert [r["by"] for r in _rows(task)] == ["session:s-abc"]
    assert _add(task)[0] == 0 and _rows(task)[1]["by"] == "session:unknown"


def test_without_a_permit_the_by_is_session_unknown(task):
    """E2: a session's `ledger add` with no permit writes by=`session:unknown`. Catches: a guessed id, or the owner's
    label as the fallback."""
    assert _add(task)[0] == 0
    assert [r["by"] for r in _rows(task)] == ["session:unknown"]


def test_the_owners_terminal_writes_owner(task):
    """E3: with no `CLAUDECODE` (the owner's terminal) the by is `owner`; `--by <text>` there is taken as typed.
    Catches: the owner's rows losing their label."""
    assert _add(task, session=False)[0] == 0
    assert _add(task, "--by", "other words", session=False)[0] == 0
    assert [r["by"] for r in _rows(task)] == ["owner", "other words"]


def test_a_session_passing_by_owner_is_refused(task):
    """E4: a session's `--by owner` is refused `ledger-by-owner` («only the owner's terminal writes by=owner»), in any
    letter case; no row is written. Catches: a session that signs the owner's name."""
    for word in ("owner", "Owner"):
        code, _out, err = _add(task, "--by", word)
        assert code == 1 and "ledger-by-owner" in err and "only the owner's terminal writes by=owner" in err
    assert _rows(task) == []


def test_ask_answered_writes_owner(task, tmp_path):
    """E5: `ask answered` records the owner's answer from the quote file with by=`owner`, also run by a session.
    Catches: the owner's answer labelled as a session's."""
    quote = tmp_path / "quote.txt"
    quote.write_text("Take B.\n", encoding="utf-8")
    write_ask(task, "t")
    cardtool.issue_by_permit(task / "mkway" / "state", "s-abc")
    assert cli(task, "ask", "answered", "t", "--quote-file", str(quote), session=True)[0] == 0
    assert [(r["by"], r["quote"]) for r in _rows(task)] == [("owner", "Take B.")]


def test_ask_default_writes_the_session_and_default_taken(task):
    """E6: `ask default` writes by=`session:<session id>` and sets `status: default-taken`; with no permit
    `session:unknown`. Catches: a default taken by a session that reads as the owner's word."""
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
    """E1 E6: the lock gate, on a session's plain `ledger add` or `ask default` call, leaves the one-use permit that
    names the session id of the hook input. Catches: a CLI that can never learn the session id."""
    state = task / "mkway" / "state"
    for command in ("python mkway/engine/mkway.py ledger add --card C --topic t --quote q --source s",
                    "python mkway/engine/mkway.py ask default t"):
        gate_call(gate_lock.check, task, tool="Bash", tool_input={"command": command}, session="s-hook")
        assert cardtool.take_by_permit(state) == "s-hook", command
        assert cardtool.take_by_permit(state) is None
