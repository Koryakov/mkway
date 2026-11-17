"""Card MW-116: the commands `mkway reader start <card>` and `mkway reader end`, through the real lock gate (a plain engine
call leaves the session's one-use permit) and through the command line in a session's shell
(the launcher's variable plus the permit, as `mkway send` does). Synthetic task root, sessions and card."""
import datetime
import json

import pytest

import _engine  # noqa: F401  (puts the engine folder on the import path)
from _engine import cli
from _mw110 import denied, hook_shell
from _mw116 import CARD, SESSION, allow_doc, make_world, runs_rows, state_of

NAME = "MKWAY_SESSION_ID"
PLAIN = f"python mkway/engine/mkway.py reader start {CARD}"


@pytest.fixture
def world(tmp_path):
    return make_world(tmp_path)


def _permit(root, session=SESSION):
    """The lock gate's one-use messaging permit of `session` (as the gate writes it)."""
    stamp = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds")
    target = state_of(root) / "permits" / f"{session}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"session_id": session, "scope": "messaging", "time": stamp}), encoding="utf-8")


def _as_session(root, *args, session=SESSION):
    _permit(root, session)
    return cli(root, *args, session=True, env={NAME: session})


def test_the_plain_start_command_passes_the_lock_gate_and_leaves_the_permit(world):
    """Catches: the start command refused as an unknown state-changing engine call, or passing with no permit: the session
    id of the allow file is proved by the permit the gate leaves."""
    out = hook_shell(world, PLAIN, SESSION, env={NAME: SESSION})
    assert denied(out) is None
    assert (state_of(world) / "permits" / f"{SESSION}.json").is_file()


def test_the_start_command_writes_the_allow_file_of_the_session(world):
    """Catches: the command writing the file under another id than the session's own (the launcher's variable, proved by the
    permit): sessions never share a file."""
    code, out, err = _as_session(world, "reader", "start", CARD)
    assert code == 0, err
    assert allow_doc(world)["session_id"] == SESSION
    assert "reader-read-refused" not in out and "allow file" in out


def test_a_second_start_prints_reader_busy_and_its_way_out(world):
    """Catches: a second run in the same session replacing the first; the refusal is exit 1 and names the way out."""
    assert _as_session(world, "reader", "start", CARD)[0] == 0
    code, _out, err = _as_session(world, "reader", "start", CARD)
    assert code == 1
    assert "reader-busy" in err and "wait for your own run or the orderer's release" in err


def test_the_end_command_empties_the_list_of_the_session(world):
    """Checks: the way out of reader-busy: `reader end` empties the session's own list and a new start passes."""
    assert _as_session(world, "reader", "start", CARD)[0] == 0
    assert _as_session(world, "reader", "end")[0] == 0
    assert allow_doc(world)["files"] == []
    assert _as_session(world, "reader", "start", CARD)[0] == 0


def test_the_owner_ends_the_run_of_a_named_session(world):
    """Checks: the orderer's release from the owner's terminal: `reader end --session <id>` empties that session's list."""
    assert _as_session(world, "reader", "start", CARD)[0] == 0
    code, _out, err = cli(world, "reader", "end", "--session", SESSION)
    assert code == 0, err
    assert allow_doc(world)["files"] == []


def test_the_owners_terminal_cannot_start_a_run(world):
    """Catches: a start with no session: the allow file is keyed by the spawning session, so the terminal has none."""
    code, _out, err = cli(world, "reader", "start", CARD)
    assert code != 0 and "`mkway reader start` is a session's command" in err
    assert runs_rows(world) == []


def test_a_card_the_register_does_not_know_is_refused(world):
    """Catches: an allow file for a card that does not exist."""
    code, _out, err = _as_session(world, "reader", "start", "CARD-099")
    assert code != 0 and "card-unknown" in err
    assert allow_doc(world) is None
