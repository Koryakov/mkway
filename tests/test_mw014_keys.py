"""Card MW-014: the profile keys, the schema, the KEYS lines and the manifest entries of the asks that do not stop the
work. Synthetic profiles only."""
import json
from pathlib import Path

import pytest

from _engine import make_profile
from _keys_md import section_rows, unquote
import dispatch
import profiles

ENGINE = Path(__file__).resolve().parents[1] / "engine"


def _entries():
    return {e["name"]: e for e in json.loads((ENGINE / "manifest.json").read_text(encoding="utf-8"))["entries"]}


@pytest.mark.parametrize("value, ok", [
    ({"max_open": 1}, True), ({"max_open": 3}, True), ({"max_open": 0}, False), ({"max_open": -1}, False),
    ({"max_open": "1"}, False), ({"max_open": 1.5}, False), ({"max_open": True}, False),
    ({"tool_allowed": True}, True), ({"tool_allowed": False}, True), ({"tool_allowed": "yes"}, False),
    ({"tool_allowed": 1}, False),
])
def test_the_schema_takes_max_open_and_tool_allowed(value, ok):
    """Catches: a limit of 0 that blocks every ask, or a text switch. E19: owner_ask.max_open is a whole number from 1; owner_ask.tool_allowed is true or false; any other value is a profile error that names the key."""
    errors = profiles.validate(make_profile(owner_ask=value))
    assert (errors == []) is ok, errors
    assert ok or any(f"owner_ask.{next(iter(value))}" in e for e in errors), errors


def test_the_accessor_defaults_and_tolerates_a_bad_value():
    """Catches: a gate that fails on a bad key instead of taking the default. E19: profiles.owner_ask gives max_open 1 and tool_allowed False when the keys are missing or unusable, and the value when it is usable."""
    assert profiles.owner_ask({})["max_open"] == 1
    assert profiles.owner_ask({})["tool_allowed"] is False
    got = profiles.owner_ask({"owner_ask": {"max_open": 3, "tool_allowed": True}})
    assert (got["max_open"], got["tool_allowed"]) == (3, True)
    got = profiles.owner_ask({"owner_ask": {"max_open": 0, "tool_allowed": "x"}})
    assert (got["max_open"], got["tool_allowed"]) == (1, False)


@pytest.mark.parametrize("key", ["owner_ask.max_open", "owner_ask.tool_allowed"])
def test_keys_md_has_a_line_for_each_new_ask_key(key):
    """Checks: a key in the schema that the keys list does not know. E19: KEYS.md has an in-schema-now line for each new ask key, with the schema path, the values and the reason."""
    rows = {unquote(r[0]): r for r in section_rows("Added keys")}
    assert key in rows, key
    assert rows[key][1] == "in schema now", key
    assert rows[key][2] == f"`{key}`", key
    assert rows[key][3], key
    assert rows[key][4], key
    assert "MW-014" in rows[key][4], key


def test_the_edit_entry_also_matches_the_question_tool_and_declares_the_new_reasons():
    """Catches: a reason the gate returns that the manifest does not declare, logged as undeclared-reason. E6: the manifest entry owner_ask.edit matches AskUserQuestion besides the three write tools, and declares ask-fields-missing, ask-already-open and ask-tool-off."""
    entry = _entries()["owner_ask.edit"]
    assert entry["matcher"] == "Edit|Write|MultiEdit|AskUserQuestion"
    missing = [r for r in ("ask-sources-missing", "ask-sources-kind", "ask-sources-lines", "ask-fields-missing",
                           "ask-already-open", "ask-tool-off") if r not in entry["reason_ids"]]
    assert missing == [], missing
    names = list(_entries())
    assert names.index("owner_ask.edit") < names.index("search")  # the tool is refused before it is searched for
    assert dispatch.matcher_matches(entry["matcher"], "AskUserQuestion")
