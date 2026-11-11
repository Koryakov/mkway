"""Card MW-018, parts 7 to 9, rows E16 to E18: the three keys, the README section «Messaging order», the register row, the
changelog line. The reasons and keys are read from the manifest and the schema, so the text cannot drift from them."""
import json
import re

import pytest

from _engine import REPO, make_profile
from _keys_md import section_rows, unquote
import profiles

README = REPO / "README.md"
HEADING = "## Messaging order"
COMMAND_REASONS = ("message-no-session", "send-session-only", "message-no-file", "message-topology", "message-duplicate",
                   "message-dead-letter", "message-ambiguous", "message-reply-unknown", "message-empty",
                   "inbox-not-yours", "inbox-unknown", "ack-not-yours")
KEYS = (("messaging.duplicate_window_hours", "1"), ("messaging.dead_hours", "12"),
        ("messaging.ack_reminder_minutes", "30"))


def _section():
    text = README.read_text(encoding="utf-8")
    start = text.index(HEADING + "\n")
    rest = text[start + len(HEADING):]
    nxt = re.search(r"^## ", rest, re.M)
    return " ".join((rest[:nxt.start()] if nxt else rest).split())


# --- E14: keys ---------------------------------------------------------------------------------------------------

def test_the_schema_and_the_accessor_for_the_three_keys():
    """E16: `messaging.duplicate_window_hours` (default 1), `messaging.dead_hours` (default 12) and
    `messaging.ack_reminder_minutes` (default 30) are numbers above 0 in the schema; an unusable value reads as the
    default, as every engine key does."""
    schema = json.loads((REPO / "engine" / "profile.schema.json").read_text(encoding="utf-8"))
    props = schema["properties"]["messaging"]["properties"]
    assert set(props) == {"duplicate_window_hours", "dead_hours", "ack_reminder_minutes"}
    assert all(p["type"] == "number" and p["exclusiveMinimum"] == 0 for p in props.values())
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
    for bad in ({"duplicate_window_hours": 0, "dead_hours": -1, "ack_reminder_minutes": "x"},
                {"duplicate_window_hours": True, "dead_hours": None, "ack_reminder_minutes": []}, "text", []):
        assert profiles.messaging_settings(make_profile(messaging=bad)) == default, bad


def test_keys_md_has_a_line_for_each_messaging_key_and_the_default_lock_target():
    """E16: the three keys are «in schema now» rows of the added keys, with their schema path and default; the engine
    default `locks.targets` is a row of the engine defaults, «in defaults.json»."""
    rows = {unquote(r[0]): r for r in section_rows("Added keys")}
    for key, default in KEYS:
        assert key in rows, key
        assert rows[key][1] == "in schema now" and unquote(rows[key][2]) == key
        assert f"default `{default}`" in rows[key][3] and "MW-018" in rows[key][4], key
    marks = {(unquote(r[0]), unquote(r[1])): r[2] for r in section_rows("Engine defaults")}
    assert marks[("locks", "targets")] == "in defaults.json"


# --- E15: README -------------------------------------------------------------------------------------------------

@pytest.mark.engine_repo
def test_the_readme_has_one_section_messaging_order():
    """E17: one heading `## Messaging order` with a body."""
    assert README.read_text(encoding="utf-8").count("\n" + HEADING + "\n") == 1
    assert len(_section()) > 1500


@pytest.mark.engine_repo
def test_the_section_names_every_command_reason_key_file_and_rule():
    """E17: every command with its flags, every reason id the message gate declares and every reason of the commands,
    the three keys, the state files, the row fields, the five kinds, the star per card, the ping line sent with
    SendMessage by name found in ListAgents, the absence of a socket poster, the watch mode and the two method rules are
    in the text. Catches: a refusal or a command a session will meet that the README does not explain."""
    flat = _section()
    manifest = json.loads((REPO / "engine" / "manifest.json").read_text(encoding="utf-8"))["entries"]
    declared = {r for e in manifest if e["gate"] == "message" for r in e["reason_ids"]}
    assert declared == {"message-not-in-inbox", "message-duplicate", "inbox-unacked", "orders-unacked"}
    for reason in sorted(declared) + list(COMMAND_REASONS):
        assert f"`{reason}`" in flat, reason
    for needed in ("`mkway send --to <id-prefix> --kind <kind> --file <body> [--reply-to <id>]`", "`mkway inbox <id>`",
                   "`mkway ack <id>`", "`mkway board`", "`mkway gate on message`", "`messaging.duplicate_window_hours`",
                   "`messaging.dead_hours`", "`messaging.ack_reminder_minutes`", "`inbox/<session id>.jsonl`",
                   "`dead-letter.jsonl`", "`pings.jsonl`", "`sessions.jsonl`",
                   "`id`, `from`, `to`, `kind`, `reply_to`, `ts`, `ack_ts`, `body`", "`order`", "`question`",
                   "`answer`", "`notice`", "`result`", "a star per card", "`ListAgents`", "`SendMessage`",
                   "no socket", "`locks.targets`", "`inbox`", "watch mode",
                   "a lead forwards the original id and rewrites nothing", "a body quoting the owner is not an order"):
        assert needed in flat, needed


# --- E16: register, changelog, version ---------------------------------------------------------------------------

@pytest.mark.engine_repo  # MW-025: the register and the changelog are not in an installed copy
def test_the_register_row_the_changelog_line_and_the_card_folder():
    """E18: the register has the row MW-018 «Messaging order» with its folder; the changelog lists it under
    `## 0.2.0` after MW-017; `VERSION` stays `0.2.0` (MW-017 sets it for this release); the card folder holds the card
    and the open check."""
    register = (REPO / "cards" / "REGISTER.md").read_text(encoding="utf-8")
    assert "| MW-018 | Messaging order | proposed | `cards/MW-018-messaging-order` |" in register
    text = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    section = text.split("\n## 0.2.0\n", 1)[1].split("\n## ", 1)[0]
    # changed by the port onto master: other cards (MW-019, MW-021, MW-022) share the release, so the lines are members
    items = [x for x in section.splitlines() if x.startswith("- ")]
    assert "- MW-017: Lead role" in items and "- MW-018: Messaging order" in items
    assert items.index("- MW-017: Lead role") < items.index("- MW-018: Messaging order")
    assert (REPO / "VERSION").read_text(encoding="utf-8").strip() == "0.2.7"  # changed by MW-027: 0.2.7
    folder = REPO / "cards" / "MW-018-messaging-order"
    assert (folder / "CARD.md").is_file() and (folder / "CHECK.md").is_file()
    assert not (folder / "probe").exists()
