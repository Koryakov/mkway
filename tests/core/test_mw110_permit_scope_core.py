"""Card MW-110 (ruling R279c Q1), layer core: the lock gate leaves the one-use permit of a messaging command (`send`, `inbox`,
`ack`) with the scope `messaging`, which the shell writes under the session's own id; every other command that names the
session keeps the shared by-permit with no scope, so their behaviour is not changed. The kind stays `by`. This reads the
gate's pure decision only: no disk, no git, no clock."""
import pytest

import _engine  # noqa: F401  (puts the engine folder on the import path)
import core_lock as core

QUIET = {("engine_call",): None, ("calls",): (), ("parse_ok",): True, ("names_commit",): False, ("carrier",): None,
         ("form",): None, ("env",): None, ("cdpath",): False, ("writes",): core.WriteFacts(), ("expanded_text",): "",
         ("commits",): (), ("unknown_shape",): "", ("holders",): {}, ("mine",): None, ("stale",): {}, ("lead",): False,
         ("register",): core.RegisterFacts()}


class Reads(dict):
    """The facts of the case; a disk fact is "no file"."""

    def __contains__(self, key):
        return key[0] == "disk" or dict.__contains__(self, key)

    def __getitem__(self, key):
        return None if key[0] == "disk" else dict.__getitem__(self, key)


def verdict(*args, lead=False):
    facts = core.Facts(tool_name="Bash", command="", targets=(), session_id="s1", vcs_git=False,
                       register_rel="mkway/cards/REGISTER.md", owner_terminal="OWNER-TERMINAL", owner_fix="OWNER-FIX",
                       stale_hours=2, reads=Reads({**QUIET, ("calls",): (args,), ("lead",): lead}))
    return core.decide(facts)


def permits(found):
    return [(p.kind, p.card, p.scope) for p in found.permits]


@pytest.mark.parametrize("args", [
    pytest.param(("send", "--to", "x", "--kind", "notice", "--file", "b.txt"), id="send"),
    pytest.param(("inbox", "m-1"), id="inbox"),
    pytest.param(("ack", "m-1"), id="ack"),
])
def test_a_messaging_command_leaves_a_permit_with_the_messaging_scope(args):
    """Catches: a messaging command whose permit goes into the shared by-permit, where another session's command can take
    it: the kind is `by` and the scope is `messaging`."""
    assert permits(verdict(*args)) == [("by", None, "messaging")]


@pytest.mark.parametrize("args, lead", [
    pytest.param(("verdict", "add", "CARD-001", "tests/test_a.py::test_one", "true", "one clause one case"), False,
                 id="verdict-add"),
    pytest.param(("built", "CARD-001"), False, id="built"),
    pytest.param(("lead", "register"), False, id="lead-register"),
    pytest.param(("give", "CARD-001", "s9"), True, id="a-lead-gives-a-card"),
])
def test_every_other_command_keeps_the_shared_by_permit_with_no_scope(args, lead):
    """Catches: R279c scope: the change leaking into other commands: their permit has no scope, so it is written to the
    shared by-permit as before."""
    assert permits(verdict(*args, lead=lead)) == [("by", None, "")]
