"""Card MW-080 (decision: R194), layer core: the lock gate's decision for the command `verdict add`. The command names the
caller from the one-use by-permit the gate leaves (the hook input is the only source of a session id); this reads the gate's
pure decision only. No disk, no git, no clock."""
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


def verdict(*args):
    facts = core.Facts(tool_name="Bash", command="", targets=(), session_id="s1", vcs_git=False,
                       register_rel="mkway/cards/REGISTER.md", owner_terminal="OWNER-TERMINAL", owner_fix="OWNER-FIX",
                       stale_hours=2, reads=Reads({**QUIET, ("calls",): (args,)}))
    return core.decide(facts)


def test_the_lock_gate_leaves_a_by_permit_for_verdict_add():
    """Catches: a `verdict add` call that leaves no by-permit, so the command cannot name its caller and refuses every session."""
    found = verdict("verdict", "add", "CARD-001", "tests/test_a.py::test_one", "true", "one clause one case")
    assert [(p.kind, p.card) for p in found.permits] == [("by", None)]
