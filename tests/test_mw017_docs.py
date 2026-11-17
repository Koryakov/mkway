"""Card MW-017, part 5, rows E19 to E21: the README section «The lead role», the two keys, the version. The reasons
and keys are read from the manifest and the schema, so the text cannot drift from them."""
import json
import re

import pytest

import _docs as docs
from _engine import REPO, make_profile
from _keys_md import section_rows, unquote
import profiles

HEADING = "## The lead role"
COMMAND_REASONS = ("lead-no-session", "lead-session-only", "lead-unknown", "lead-ambiguous", "lead-give-not-yours",
                   "lead-give-not-lead", "lead-give-self", "lead-accept-none", "lead-accept-stale",
                   "lead-not-registered", "lead-bad-id", "ack-unknown")
BAD_LEADS = (
    pytest.param({"escalate_hours": 0, "max_cards": 0}, id="zero-hours-and-zero-cards"),
    pytest.param({"escalate_hours": "x", "max_cards": 2.5}, id="text-hours-and-fraction-cards"),
    pytest.param({"escalate_hours": True, "max_cards": True}, id="booleans"),
    pytest.param("text", id="text"),
    pytest.param([], id="list"),
)


@pytest.mark.parametrize("bad", BAD_LEADS)
def test_the_schema_and_the_accessor_for_the_two_keys(bad):
    """Checks: `leads.escalate_hours` (a number above 0, default 4) and `leads.max_cards` (a whole number from 1, default 5) are in the schema; an unusable value reads as the default (E20)."""
    schema = json.loads((REPO / "engine" / "profile.schema.json").read_text(encoding="utf-8"))
    props = schema["properties"]["leads"]["properties"]
    assert set(props) == {"escalate_hours", "max_cards"}  # R274-D1: the third key of MW-103 (R255b) moved to `paths.outside_writable`
    assert props["max_cards"]["type"] == "integer"
    assert profiles.validate(make_profile(leads={"escalate_hours": 1.5, "max_cards": 3})) == []
    assert profiles.validate(make_profile(leads={"max_cards": 0})) != []
    assert profiles.leads_settings(make_profile()) == {"escalate_hours": 4, "max_cards": 5}
    assert profiles.leads_settings(None) == {"escalate_hours": 4, "max_cards": 5}
    assert profiles.leads_settings(make_profile(leads={"escalate_hours": 0.5, "max_cards": 9})) == {
        "escalate_hours": 0.5, "max_cards": 9}
    assert profiles.leads_settings(make_profile(leads=bad)) == {"escalate_hours": 4, "max_cards": 5}, bad
