"""Card MW-104 (R257f): the lock gate refuses a session's `green record` as an owner-only command, in any spelling the other
owner commands are read in. `core_lock.decide(facts)` as a table; no disk, no git, no clock. Synthetic values only.
Gap H7 (R257h): the gate cannot yet hold the upgrade folder's files, which lie outside the repository; this card refuses the
command, not a write to the file."""
import pytest

import _engine  # noqa: F401  (puts the engine folder on the import path)
import core_lock as core

REGISTER = "mkway/cards/REGISTER.md"
BUILT_IN = (core.Target("engine", ("mkway/engine/",), True), core.Target("register", (REGISTER,), True))


class Reads(dict):
    """The facts a case gives; a disk fact is "no file"."""

    def __contains__(self, key):
        return key[0] == "disk" or dict.__contains__(self, key)

    def __getitem__(self, key):
        return None if key[0] == "disk" else dict.__getitem__(self, key)


QUIET = {("engine_call",): None, ("parse_ok",): True, ("names_commit",): False, ("carrier",): None, ("form",): None,
         ("env",): None, ("cdpath",): False, ("writes",): core.WriteFacts(), ("expanded_text",): "", ("commits",): (),
         ("unknown_shape",): ""}


def call(*args):
    reads = {**QUIET, ("calls",): (args,), ("holders",): {}, ("mine",): None, ("stale",): {}, ("lead",): False,
             ("register",): core.RegisterFacts()}
    return core.Facts(tool_name="Bash", command="x", targets=BUILT_IN, vcs_git=False, register_rel=REGISTER,
                      owner_terminal="OWNER-TERMINAL", owner_fix="OWNER-FIX", stale_hours=2, session_id="s1",
                      reads=Reads(reads))


def outcome(f):
    """The reason of a refusal, else the kind."""
    v = core.decide(f)
    return v.reason if v.kind == core.REFUSE else v.kind


@pytest.mark.parametrize("args", [
    pytest.param(("green", "record", "--repo", "x"), id="the-command-with-options"),
    pytest.param(("green", "record"), id="the-bare-command"),
])
def test_a_session_green_record_is_owner_only(args):
    """Catches: a session's `green record` that the lock gate lets through to a CLI the session could strip CLAUDECODE for."""
    assert outcome(call(*args)) == "owner-only-command"


@pytest.mark.parametrize("args", [
    pytest.param(("green",), id="green-alone"),
    pytest.param(("green", "list"), id="green-with-another-word"),
    pytest.param(("search", "words"), id="search"),
    pytest.param(("check",), id="check"),
])
def test_a_session_command_that_is_not_green_record_passes(args):
    """Checks: the nearest allow of the green-record refusal: other commands, `green` alone included, are not owner-only."""
    assert outcome(call(*args)) == "allow"
