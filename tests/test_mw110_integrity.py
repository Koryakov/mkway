"""Card MW-110 (fix of the pre-merge readers, ruling R279): the identity a gate relies on is wiring, and an identity that
cannot be verified fails closed. The entry `message.session` is of the integrity class: it never watches, it is its own
gate (so the form gate `message` keeps its watch mode on a first install), and a watch marker never turns its refusal
into a would-refuse row. Synthetic roots only."""
import json

import pytest

import _engine  # noqa: F401  (puts the engine folder on the import path)
from _engine import cli
from _mw018 import state, world
from _mw110 import NAME, denied, hook_shell
import dispatch
import gatemode

pytestmark = pytest.mark.engine_repo


def _entry():
    raw = json.loads((dispatch.ENGINE_DIR / "manifest.json").read_text(encoding="utf-8"))["entries"]
    return {e["name"]: e for e in raw}["message.session"]


def test_the_session_id_entry_is_of_the_integrity_class():
    """Catches: an identity check that watches on a first install and lets every session pass as another until the owner
    switches it on: the raw manifest names the class `integrity`."""
    assert _entry()["class"] == "integrity"


def test_the_session_id_check_is_its_own_gate_and_the_message_gate_stays_a_form_gate():
    """Catches: the integrity entry sharing the gate name `message`, which would make the whole message gate an integrity
    gate (no watch mode, no first-install watch list): the class of a gate is the class of all its entries."""
    manifest = dispatch.load_manifest(dispatch.ENGINE_DIR)
    gate = _entry()["gate"]
    assert gate != "message"
    assert gatemode.gate_class(manifest, gate) == gatemode.INTEGRITY
    assert gatemode.gate_class(manifest, "message") == gatemode.FORM


def test_watching_the_session_id_gate_is_refused_and_the_message_gate_still_watches(tmp_path):
    """Catches: `mkway gate watch` accepted for the identity check; the form gate `message` is still accepted."""
    root = world(tmp_path)
    code, _out, err = cli(root, "gate", "watch", _entry()["gate"])
    assert code != 0
    assert "gate-watch-integrity" in err
    assert cli(root, "gate", "watch", "message")[0] == 0


def test_a_watch_marker_never_turns_the_session_id_refusal_into_a_would_refuse_row(tmp_path):
    """Catches: a marker for the gate that lets a session pass as another: through the real hook a mismatch is a deny with
    the entry's tag, whatever markers exist."""
    root = world(tmp_path)
    gatemode.write_marker(state(root), _entry()["gate"], "installed")
    gatemode.write_marker(state(root), "message", "installed")
    reason = denied(hook_shell(root, "python mkway/engine/mkway.py board", "build-a1", {NAME: "lead-b"}))
    assert reason is not None
    assert reason.startswith("[mkway message.session session-id-mismatch] ")
