"""Card MW-108: `core_lock.decide(facts)` for the new engine command `card release-red <id> --to <card>`, as a table test. No
disk, no git, no clock: the case builds a `Facts` record and reads the verdict, under the guard that fails on any file,
process or clock access. The setup lines are copied from tests/core/test_lock_decide.py (a test module is never imported).
Synthetic values only."""
import pytest

import _engine  # noqa: F401  (puts the engine folder on the import path)
import core_lock as core
from _no_io import no_io

REGISTER = "mkway/cards/REGISTER.md"
QUIET = {("engine_call",): None, ("parse_ok",): True, ("names_commit",): False, ("carrier",): None, ("form",): None,
         ("env",): None, ("cdpath",): False, ("writes",): core.WriteFacts(), ("expanded_text",): "", ("commits",): (),
         ("unknown_shape",): ""}


class Reads(dict):
    """The facts a case gives. A disk fact not named is "no file" (None)."""

    def __contains__(self, key):
        return key[0] == "disk" or dict.__contains__(self, key)

    def __getitem__(self, key):
        return None if key[0] == "disk" else dict.__getitem__(self, key)


def call(*args, held=None, lead=False, session="s1"):
    reads = {("calls",): (args,), ("holders",): held or {}, ("mine",): None, ("stale",): {}, ("lead",): lead,
             ("register",): core.RegisterFacts(rows={"CARD-001": core.Row("open")})}
    return core.Facts(tool_name="Bash", command="", targets=(), vcs_git=False, register_rel=REGISTER,
                      owner_terminal="OWNER-TERMINAL", owner_fix="OWNER-FIX", stale_hours=2, session_id=session,
                      reads=Reads({**QUIET, **reads}))


def run(f):
    with no_io():
        return core.decide(f)


@pytest.fixture(autouse=True, scope="module")
def _warm_imports():
    """The first call imports lazily; that stays out of the guard."""
    core.decide(call("card", "list"))


@pytest.mark.parametrize("held", [
    pytest.param({}, id="no session holds a card"),
    pytest.param({"CARD-001": "s2"}, id="another session holds the first card"),
])
def test_a_session_release_red_leaves_the_by_permit(held):
    """Checks: `card release-red` by a session is allowed by the lock gate and leaves the one-use by-permit, so the command
    can tell the orderer from any other session; the card tool decides who may (E13)."""
    got = run(call("card", "release-red", "tests/test_x.py::test_y", "--to", "CARD-002", held=held))
    assert got.kind == core.ALLOW
    assert [(p.kind, p.card) for p in got.permits] == [("by", None)]
