"""Card MW-110: the six replay shapes through the REAL hook dispatch (the whole shell group, the lock gate first of the
gates that stop a call, the session-id gate among them), before the CLI. The shapes are synthetic: a session sending,
reading or acking its own inbox, in the plain and in the chained command form (a fix of the pre-merge readers: the chained
shape was only handed to the session-id gate, never to the lock gate or a shell). One test id is one case."""
import pytest

import _engine  # noqa: F401  (puts the engine folder on the import path)
from _engine import cli
from _mw018 import id_of, rows_of, send, world
from _mw110 import NAME, context_of, denied, hook_shell

PLAIN = "python mkway/engine/mkway.py {args}"
CHAINED = "cd mkway && python engine/mkway.py {args} && echo done"
ARGS = {"send": "send --to lead-a --kind notice --file body.txt", "inbox": "inbox {row}", "ack": "ack {row}"}


def case(id_, *values):
    return pytest.param(*values, id=id_)


KINDS = ("send", "inbox", "ack")


def _world_with_row(tmp_path):
    root = world(tmp_path)
    _code, out, _err = send(root, "lead-a", "build-a1", "order", "build the thing")  # the helper writes body.txt too
    (root / "body.txt").write_text("a plain notice", encoding="utf-8")
    return root, id_of(out)


@pytest.mark.parametrize("env", [case("variable-set", {NAME: "build-a1"}), case("variable-unset", {})])
@pytest.mark.parametrize("kind", KINDS)
def test_a_chained_engine_call_is_stopped_by_the_lock_gate_before_it_reaches_a_shell(tmp_path, kind, env):
    """Catches: a chained replay shape taken as delivered because only the session-id gate was asked: the real hook refuses
    the chain itself (`engine-call-not-plain`, the reach rule), with the variable set or not, and its text names the way
    out: the command alone, in its plain form."""
    root, row = _world_with_row(tmp_path)
    reason = denied(hook_shell(root, CHAINED.format(args=ARGS[kind].format(row=row)), "build-a1", env))
    assert reason is not None
    assert reason.startswith("[mkway lock.shell engine-call-not-plain] ")
    assert "alone, in its plain form" in reason


@pytest.mark.parametrize("kind", KINDS)
def test_the_plain_form_is_the_way_out_of_the_chained_one_and_the_cli_delivers(tmp_path, kind):
    """Checks: the nearest allow of the refusal above: the same call in its plain form passes the whole shell group in
    silence (the variable equals the hook's id) and the engine does what it says, from that id, with no permit of its own."""
    root, row = _world_with_row(tmp_path)
    args = ARGS[kind].format(row=row)
    out = hook_shell(root, PLAIN.format(args=args), "build-a1", {NAME: "build-a1"})
    code, shown, err = cli(root, *args.split(), session=True, env={NAME: "build-a1"})
    assert (denied(out), context_of(out), code) == (None, "", 0), err
    done = {"send": lambda: rows_of(root, "lead-a")[-1]["body"] == "a plain notice",
            "inbox": lambda: "build the thing" in shown, "ack": lambda: bool(rows_of(root, "build-a1")[0]["ack_ts"])}
    assert done[kind]()


@pytest.mark.parametrize("kind", KINDS)
def test_with_the_variable_unset_the_plain_form_passes_the_whole_shell_group_with_one_warn(tmp_path, kind):
    """Checks: the transition: with no variable the plain shape is not refused by any gate of the group; the session reads
    one warn `session-id-unset` that names the launcher line."""
    root, row = _world_with_row(tmp_path)
    out = hook_shell(root, PLAIN.format(args=ARGS[kind].format(row=row)), "build-a1", {})
    said = context_of(out)
    assert denied(out) is None
    assert "[mkway message.session session-id-unset]" in said
    assert "--session-id" in said
