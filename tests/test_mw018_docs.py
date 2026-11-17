"""Card MW-018, parts 7 to 9, rows E16 to E18: the three keys, the README section «Messaging order», the register row, the
changelog line. The reasons and keys are read from the manifest and the schema, so the text cannot drift from them."""
import json

import pytest

import _docs as docs
from _engine import REPO, make_profile
from _keys_md import section_rows, unquote
import profiles

COMMAND_REASONS = ("message-no-session", "send-session-only", "message-no-file", "message-topology", "message-duplicate",
                   "message-dead-letter", "message-ambiguous", "message-reply-unknown", "message-empty",
                   "inbox-not-yours", "inbox-unknown", "ack-not-yours")
KEYS = (("messaging.duplicate_window_hours", "1"), ("messaging.dead_hours", "12"),
        ("messaging.ack_reminder_minutes", "30"))


# --- E14: keys ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("bad", [
    pytest.param({"duplicate_window_hours": 0, "dead_hours": -1, "ack_reminder_minutes": "x"}, id="zero-negative-text"),
    pytest.param({"duplicate_window_hours": True, "dead_hours": None, "ack_reminder_minutes": []}, id="bool-none-list"),
    pytest.param("text", id="text"),
    pytest.param([], id="empty-list"),
])
def test_the_schema_and_the_accessor_for_the_three_keys(bad):
    """Catches: a messaging key that is not a number above 0 in the schema, or an unusable value that does not read as the default. E16"""
    # E16: duplicate_window_hours default 1, dead_hours default 12, ack_reminder_minutes default 30; an unusable value
    # reads as the default, as every engine key does.
    schema = json.loads((REPO / "engine" / "profile.schema.json").read_text(encoding="utf-8"))
    props = schema["properties"]["messaging"]["properties"]
    # changed by MW-110 (decision MW110-D1): the key `session_id_watch_until` (a text date) joins the three numeric keys
    assert set(props) == {"duplicate_window_hours", "dead_hours", "ack_reminder_minutes", "session_id_watch_until"}
    assert all(p["type"] == "number" and p["exclusiveMinimum"] == 0 for k, p in props.items()
               if k != "session_id_watch_until")
    assert profiles.validate(make_profile(messaging={"duplicate_window_hours": 0.5, "dead_hours": 24,
                                                     "ack_reminder_minutes": 10})) == []
    assert profiles.validate(make_profile(messaging={"dead_hours": 0})) != []
    assert profiles.validate(make_profile(messaging={"other": 1})) != []
    default = {"duplicate_window_hours": 1, "dead_hours": 12, "ack_reminder_minutes": 30}
    assert profiles.messaging_settings(make_profile()) == default
    assert profiles.messaging_settings(None) == default
    assert profiles.messaging_settings(make_profile(messaging={"duplicate_window_hours": 0.5, "dead_hours": 24,
                                                               "ack_reminder_minutes": 10})) == {
        "duplicate_window_hours": 0.5, "dead_hours": 24, "ack_reminder_minutes": 10}
    assert profiles.messaging_settings(make_profile(messaging=bad)) == default, bad


# --- E16: register, changelog, version ---------------------------------------------------------------------------
