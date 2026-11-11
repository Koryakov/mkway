"""Card MW-017, part 5, rows E19 to E21: the README section «The lead role», the two keys, the version. The reasons
and keys are read from the manifest and the schema, so the text cannot drift from them."""
import json
import re

import pytest

from _engine import REPO, make_profile
from _keys_md import section_rows, unquote
import profiles

README = REPO / "README.md"
HEADING = "## The lead role"
COMMAND_REASONS = ("lead-no-session", "lead-session-only", "lead-unknown", "lead-ambiguous", "lead-give-not-yours",
                   "lead-give-not-lead", "lead-give-self", "lead-accept-none", "lead-accept-stale",
                   "lead-not-registered", "lead-bad-id", "ack-unknown")


def _section():
    text = README.read_text(encoding="utf-8")
    start = text.index(HEADING + "\n")
    rest = text[start + len(HEADING):]
    nxt = re.search(r"^## ", rest, re.M)
    return " ".join((rest[:nxt.start()] if nxt else rest).split())


@pytest.mark.engine_repo
def test_the_readme_has_one_section_the_lead_role():
    """E19: one heading `## The lead role` with a body."""
    assert README.read_text(encoding="utf-8").count("\n" + HEADING + "\n") == 1
    assert len(_section()) > 1200


@pytest.mark.engine_repo
def test_the_section_names_every_command_reason_key_and_file():
    """E19: every command, every reason id the lead gate declares and every reason of the commands, the two keys, the
    state files, the four order headings, the four notice kinds and the rule that a lead's message is no consent are in
    the text. Catches: a refusal or command a session will meet that the README does not explain."""
    flat = _section()
    manifest = json.loads((REPO / "engine" / "manifest.json").read_text(encoding="utf-8"))["entries"]
    declared = {r for e in manifest if e["gate"] == "lead" for r in e["reason_ids"]}
    assert declared == {"lead-no-edit", "lead-no-take", "lead-notices-unacked"}
    for reason in sorted(declared) + list(COMMAND_REASONS):
        assert f"`{reason}`" in flat, reason
    for needed in ("`mkway lead register`", "`mkway lead add <id-prefix>`", "`mkway lead remove <id-prefix>`",
                   "`mkway lead accept <card>`", "`mkway give <card> <id-prefix>`", "`mkway ack <id>`",
                   "`mkway leads`", "`leads.escalate_hours`", "`leads.max_cards`", "`leads.json`",
                   "`inbox/<lead id>.jsonl`", "`ORDER.md`", "`Objective`", "`Output form`", "`Time-box`",
                   "`Boundary`", "`mkway gate on lead`",
                   "`id`, `from`, `to`, `kind`, `reply_to`, `ts`, `ack_ts`, `body`",  # changed by MW-018: `reply_to`
                   "past its Appetite", "a gate tripped", "a default was taken", "a builder finished",
                   "never the owner's consent"):
        assert needed in flat, needed


def test_the_schema_and_the_accessor_for_the_two_keys():
    """E20: `leads.escalate_hours` (a number above 0, default 4) and `leads.max_cards` (a whole number from 1, default
    5) are in the schema; an unusable value reads as the default, as every engine key does."""
    schema = json.loads((REPO / "engine" / "profile.schema.json").read_text(encoding="utf-8"))
    props = schema["properties"]["leads"]["properties"]
    assert set(props) == {"escalate_hours", "max_cards"} and props["max_cards"]["type"] == "integer"
    assert profiles.validate(make_profile(leads={"escalate_hours": 1.5, "max_cards": 3})) == []
    assert profiles.validate(make_profile(leads={"max_cards": 0})) != []
    assert profiles.leads_settings(make_profile()) == {"escalate_hours": 4, "max_cards": 5}
    assert profiles.leads_settings(None) == {"escalate_hours": 4, "max_cards": 5}
    assert profiles.leads_settings(make_profile(leads={"escalate_hours": 0.5, "max_cards": 9})) == {
        "escalate_hours": 0.5, "max_cards": 9}
    for bad in ({"escalate_hours": 0, "max_cards": 0}, {"escalate_hours": "x", "max_cards": 2.5},
                {"escalate_hours": True, "max_cards": True}, "text", []):
        assert profiles.leads_settings(make_profile(leads=bad)) == {"escalate_hours": 4, "max_cards": 5}, bad


def test_keys_md_has_a_line_for_each_lead_key():
    """E20: both keys are «in schema now» rows of the added keys, with their schema path and the default."""
    rows = {unquote(r[0]): r for r in section_rows("Added keys")}
    for key, default in (("leads.escalate_hours", "4"), ("leads.max_cards", "5")):
        assert key in rows, key
        assert rows[key][1] == "in schema now" and unquote(rows[key][2]) == key
        assert f"default `{default}`" in rows[key][3] and "MW-017" in rows[key][4], key


@pytest.mark.engine_repo  # MW-025: the changelog is not in an installed copy
def test_the_version_is_0_2_0_and_the_changelog_names_the_card():
    """E21: the lead role adds commands and gates, so by the README's rule the minor number moves: `VERSION` reads
    `0.2.0` and the changelog has a `## 0.2.0` section with the line of this card, above `## 0.1.0`."""
    assert (REPO / "VERSION").read_text(encoding="utf-8").strip() == "0.2.7"  # changed by MW-027: 0.2.7
    text = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    assert text.index("\n## 0.2.0\n") < text.index("\n## 0.1.0\n")
    section = text.split("\n## 0.2.0\n", 1)[1].split("\n## ", 1)[0]
    assert "- MW-017: Lead role" in [x for x in section.splitlines() if x.startswith("- ")]
