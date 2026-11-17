"""Card MW-137: `core_lock.decide(facts)` for the engine command `card paths <id> --add <entry>`, as a table test. No disk, no
git, no clock: the case builds a `Facts` record and reads the verdict, under the guard that fails on any file, process or
clock access. The setup lines are copied from tests/core/test_mw108_lock_core.py (a test module is never imported).
Synthetic values only."""
import pytest

import _engine  # noqa: F401  (puts the engine folder on the import path)
import core_lock as core
from _no_io import no_io

REGISTER = "mkway/cards/REGISTER.md"
QUIET = {("engine_call",): None, ("parse_ok",): True, ("names_commit",): False, ("carrier",): None, ("form",): None,
         ("env",): None, ("cdpath",): False, ("writes",): core.WriteFacts(), ("expanded_text",): "", ("commits",): (),
         ("unknown_shape",): ""}
PROBLEM = ("paths-not-lead", "TEXT OF THE PROBLEM")


class Reads(dict):
    """The facts a case gives. A disk fact not named is "no file" (None)."""

    def __contains__(self, key):
        return key[0] == "disk" or dict.__contains__(self, key)

    def __getitem__(self, key):
        return None if key[0] == "disk" else dict.__getitem__(self, key)


def call(*args, problem=None, orderer=True, rows=None, session="s1"):
    rows = {"CARD-001": core.Row("open")} if rows is None else rows
    reads = {("calls",): (args,), ("holders",): {}, ("mine",): None, ("stale",): {}, ("lead",): True,
             ("register",): core.RegisterFacts(rows=rows), ("paths_problem", "CARD-001"): problem}
    return core.Facts(tool_name="Bash", command="", targets=(), vcs_git=False, register_rel=REGISTER, orderer=orderer,
                      owner_terminal="OWNER-TERMINAL", owner_fix="OWNER-FIX", stale_hours=2, session_id=session,
                      reads=Reads({**QUIET, **reads}))


def run(f):
    with no_io():
        return core.decide(f)


@pytest.fixture(autouse=True, scope="module")
def _warm_imports():
    """The first call imports lazily; that stays out of the guard."""
    core.decide(call("card", "list"))


def test_a_card_paths_call_the_card_tool_accepts_leaves_the_card_bound_permit():
    """Checks: the lock gate allows `card paths <id>` when the card tool has no problem for this session, and leaves the
    one-use permit of kind `paths` for that card, so the command reads the session id from it (E26)."""
    got = run(call("card", "paths", "CARD-001", "--add", "src/b.py"))
    assert got.kind == core.ALLOW
    assert [(p.kind, p.card) for p in got.permits] == [("paths", "CARD-001")]


def test_a_card_paths_call_the_card_tool_refuses_is_refused_with_its_reason_and_text():
    """Catches: a hook that passes a session the card tool already knows may not re-record this card, and leaves it a permit. E27"""
    got = run(call("card", "paths", "CARD-001", "--add", "src/b.py", problem=PROBLEM))
    assert (got.kind, got.reason, got.text, got.permits) == (core.REFUSE, "paths-not-lead", "TEXT OF THE PROBLEM", ())


def test_the_permit_that_cannot_be_written_refuses_with_a_way_that_names_the_plain_call_and_the_owner():
    """Catches: a permit that fails to write and lets the call run with no session id. E28"""
    (permit,) = run(call("card", "paths", "CARD-001", "--add", "src/b.py")).permits
    assert permit.on_fail.kind == core.REFUSE and permit.on_fail.reason == "paths-no-permit"
    assert "plain form" in permit.on_fail.text and "owner" in permit.on_fail.text


def test_under_an_approver_that_is_not_the_orderer_card_paths_is_the_owners_command():
    """Catches: a lead that re-records Paths in a root whose profile gives leads no card authority. E29"""
    got = run(call("card", "paths", "CARD-001", "--add", "src/b.py", orderer=False))
    assert (got.kind, got.reason, got.permits) == (core.REFUSE, "owner-only-command", ())


def test_a_card_that_is_not_in_the_register_is_left_to_the_command_to_name():
    """Catches: a hook that invents a refusal for an unknown card instead of the command's `card-unknown`. E30"""
    got = run(call("card", "paths", "CARD-009", "--add", "src/b.py"))
    assert (got.kind, got.permits) == (core.ALLOW, ())
