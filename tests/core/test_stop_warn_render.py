"""Card MW-075, layer core: what `render` prints for an event and a verdict, as a table. No disk, no git, no clock. A Stop
warn is shown to the user and never sent to the model (a `additionalContext` on Stop re-invokes the session). Each
expected value is a literal written from the card, never from `render`."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/: `_engine` puts engine/ on the path
import _engine  # noqa: E402,F401
from dispatch import render  # noqa: E402

WARN = "[mkway outbox_check.stop verdict-not-enforced] blind verdict not enforced: outbox.checkers missing in profile"
REFUSE = "[mkway owner_ask.stop ask-not-written] an ask is not written"


def test_a_stop_warn_is_a_system_message_and_nothing_else():
    """Checks: a Stop warn is a system message and nothing else, never additionalContext that wakes the session again."""
    code, out, err = render("Stop", None, [WARN])
    assert (code, out, err) == (0, '{"systemMessage": "[mkway outbox_check.stop verdict-not-enforced] blind verdict not enforced: outbox.checkers missing in profile"}', "")


def test_two_stop_warns_are_one_system_message_in_order():
    """Catches: a second Stop warn dropped or sent to the model."""
    code, out, err = render("Stop", None, ["first warn", "second warn"])
    assert (code, json.loads(out), err) == (0, {"systemMessage": "first warn\nsecond warn"}, "")


def test_a_stop_refuse_keeps_the_block_and_the_reason_and_shows_the_warn_to_the_user_only():
    """Catches: a Stop refuse that loses its block or reason, or that still carries the warn as additionalContext."""
    code, out, err = render("Stop", REFUSE, [WARN])
    assert (code, json.loads(out), err) == (0, {"decision": "block", "reason": REFUSE, "systemMessage": WARN}, "")


@pytest.mark.parametrize("event", ["PreToolUse", "PostToolUse", "UserPromptSubmit"])
def test_a_warn_on_another_event_is_still_additional_context(event):
    """Checks: every other event keeps its output (a guard of the unchanged behaviour; it passes before the fix)."""
    code, out, err = render(event, None, [WARN])
    assert (code, json.loads(out), err) == (
        0, {"hookSpecificOutput": {"hookEventName": event, "additionalContext": WARN}}, "")


def test_a_stop_with_no_refuse_and_no_warn_prints_nothing():
    """Checks: the nearest allow of the Stop warn, nothing to say (a guard; it passes before the fix)."""
    assert render("Stop", None, []) == (0, "", "")
