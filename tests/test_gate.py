"""The gate interface (card MW-002, row E3)."""
import dataclasses
from pathlib import Path

import pytest

import _engine  # noqa: F401  (puts engine/ and the synthetic fixtures on the path)
import fixture_gates
import gate


def _ctx(**over):
    values = dict(profile={}, root=Path("."), session_id="s1", event="PreToolUse", gate="g", tool_name="Edit",
                  tool_input={}, budget_seconds=None, once=lambda targets: True)
    values.update(over)
    return gate.Context(**values)


def test_fixture_gates_prove_the_interface():
    """Catches: a gate is (event, ctx) -> Verdict; the two fixture gates always refuse or always warn with a reason id and a message. E3"""
    ctx = _ctx()
    v = fixture_gates.always_refuse("PreToolUse", ctx)
    assert isinstance(v, gate.Verdict)
    assert (v.kind, v.reason_id) == (gate.REFUSE, "fixture-refuse")
    assert v.message
    v = fixture_gates.always_warn("PreToolUse", ctx)
    assert (v.kind, v.reason_id) == (gate.WARN, "fixture-warn")
    assert v.message
    assert gate.allow().kind == gate.ALLOW
    # ctx carries the profile, root, session id, tool name and input, the once-store and the budget.
    assert {f.name for f in dataclasses.fields(gate.Context)} == {
        "profile", "root", "session_id", "event", "gate", "tool_name", "tool_input", "budget_seconds", "once",
        # changed by MW-003 (deliverables 1 and 2): the shared helpers, the records and the PostToolUse response
        "tool_response", "profile_file", "norm", "commit_cmd", "shell_writes", "mkway_calls", "records", "env",
        "cwd",  # changed by MW-003 batch 3 (item 15): the hook input's cwd
        "hook_input",  # changed by MW-007 (E15): the whole hook input, for the stop gate
        "payload"}  # changed by MW-004 (part 1): the whole hook input, for the SubagentStart/Stop fields
    assert set(gate.KINDS) == {"allow", "refuse", "warn", "log"}  # changed by MW-003 list item 5 (R43): `log`


def test_verdict_rejects_bad_values():
    """Catches: an unknown kind, or a refuse or warn without a reason id or a message, is accepted as a Verdict. E3"""
    with pytest.raises(ValueError):
        gate.Verdict("block", "r", "m")
    with pytest.raises(ValueError):
        gate.refuse("", "message")
    with pytest.raises(ValueError):
        gate.warn("reason", "")
