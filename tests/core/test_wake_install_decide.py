"""Card MW-078, rows I1 to I8: how the pure install core (`engine/core_install.py`) treats the inbox waiter entry of the
manifest: its own Stop handler with `asyncRewake` and a timeout of the deadline plus 60, owned by the install marker,
switched by `wake.mode`. No disk, no process. Written after the green commit to cover the changed lines (the card Log
names the coverage report as their red proof)."""
import json

import pytest

import _engine  # noqa: F401  (puts the engine on sys.path)
from _engine import make_profile
import core_install as core

COMMAND = 'python -I -X utf8 "${CLAUDE_PROJECT_DIR}/mkway/engine/mkway.py" hook-wait'
WAITER = {"name": "inbox_waiter", "gate": "wake", "group": "wake", "function": None, "reason_ids": [], "event": "Stop",
          "matcher": None, "timeout": 14460, "default_on": True, "waiter": True}
TABLE = {"start": {}, "stop": {}, "wake": {}}


def _stop(profile, **kw):
    """The Stop entries generated for the waiter entry alone."""
    return [e for e in core.generate_entries(profile, [WAITER], TABLE, **kw) if e["event"] == "Stop"]


def _stop_handlers(text):
    data = json.loads(text)
    return [h for group in data["hooks"]["Stop"] for h in group["hooks"]]


def test_the_waiter_entry_is_one_stop_entry_with_async_rewake_and_the_default_timeout():
    """Checks: I1, one Stop entry: the engine's `hook-wait`, no matcher, `async_rewake` true, timeout 14400 plus 60."""
    assert _stop(make_profile()) == [{"event": "Stop", "group": "wake", "matcher": None, "command": COMMAND,
                                      "timeout": 14460, "on_failure": None, "async_rewake": True}]


def test_a_profile_deadline_sets_the_timeout_to_the_deadline_plus_60():
    """Checks: I2, `wake.deadline_seconds` 100 gives a timeout of 160."""
    (entry,) = _stop(make_profile(wake={"deadline_seconds": 100}))
    assert entry["timeout"] == 160


def test_wake_mode_off_leaves_the_waiter_out():
    """Catches: I3, a waiter handler installed although `wake.mode` is off."""
    assert _stop(make_profile(wake={"mode": "off"})) == []


def test_a_named_profile_is_passed_on_to_the_waiter_command():
    """Checks: I4, a profile outside the default place is named in the command, as for the other entries."""
    (entry,) = _stop(make_profile(), profile_rel="mkway/other.json")
    assert entry["command"] == COMMAND + ' --profile "${CLAUDE_PROJECT_DIR}/mkway/other.json"'


def test_the_settings_file_gets_the_waiter_handler_with_the_async_rewake_field():
    """Checks: I5, the handler has type, command, timeout and `asyncRewake` true, and nothing else."""
    entries = core.generate_entries(make_profile(), [WAITER], TABLE)
    verdict = core.settings_text(None, entries, "mkway")
    assert _stop_handlers(verdict.out) == [{"type": "command", "command": COMMAND, "timeout": 14460,
                                            "asyncRewake": True}]


def test_an_ordinary_entry_gets_no_async_rewake_field():
    """Checks: I6, the nearest allow of I5: a handler of a gate carries no `asyncRewake`."""
    entry = {"event": "Stop", "group": "stop", "matcher": None, "command": "python x hook Stop --group stop",
             "timeout": 25, "on_failure": None}
    verdict = core.settings_text(None, [entry], "mkway")
    assert _stop_handlers(verdict.out) == [{"type": "command", "command": "python x hook Stop --group stop",
                                            "timeout": 25}]


@pytest.mark.parametrize("field, expected", [({"asyncRewake": True}, True), ({"asyncRewake": False}, False),
                                             ({}, "absent")])
def test_the_owned_entries_carry_the_async_rewake_field_only_when_the_handler_has_it(field, expected):
    """Checks: I7, an owned handler's `asyncRewake` is read as written (true, false) and left out when missing."""
    handler = {"type": "command", "command": COMMAND, "timeout": 14460, **field}
    text = json.dumps({"hooks": {"Stop": [{"hooks": [handler]}]}})
    (entry,) = core.owned_entries(text, "mkway")
    assert entry.get("async_rewake", "absent") == expected


@pytest.mark.parametrize("event, expected", [("Stop", True), ("Nonsense", False)])
def test_a_waiter_entry_loads_only_on_a_known_event(event, expected):
    """Checks: I8, the waiter entry is loadable on Stop with mode on, and not on an event the install does not know."""
    assert core.loadable_on(make_profile(), dict(WAITER, event=event)) is expected
