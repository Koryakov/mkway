"""Card MW-014, part 5: the README section «Asks that do not stop the work». The reasons and keys are read from the
manifest and the schema, so the text cannot drift from them."""
import json
import re

import pytest

from _engine import REPO

README = REPO / "README.md"
HEADING = "## Asks that do not stop the work"
COMMAND_REASONS = ("ask-not-reversible", "ask-deadline-not-passed", "ask-not-open", "ask-unknown", "ask-no-default")

pytestmark = pytest.mark.engine_repo  # the README is not in an engine copy: `mkway check` leaves these out


def _section():
    text = README.read_text(encoding="utf-8")
    start = text.index(HEADING + "\n")
    rest = text[start + len(HEADING):]
    nxt = re.search(r"^## ", rest, re.M)
    return " ".join((rest[:nxt.start()] if nxt else rest).split())


def test_one_section_with_a_body():
    """Checks: one heading `## Asks that do not stop the work`, with a body (E17)."""
    # Catches: a missing or doubled section
    assert README.read_text(encoding="utf-8").count("\n" + HEADING + "\n") == 1
    assert len(_section()) > 800


def test_the_section_names_every_reason_key_and_command():
    """Checks: every reason, key, command, file line and placeholder of the section is in its text (E17)."""
    # every reason id the manifest declares for the new steps and every reason of the two commands, the three profile
    # keys, the five field lines, the four statuses, the three commands and the two placeholders are in the text;
    # Catches: a refusal a session will meet that the README does not explain
    flat = _section()
    manifest = json.loads((REPO / "engine" / "manifest.json").read_text(encoding="utf-8"))["entries"]
    reasons = {r for e in manifest if e["gate"] == "owner_ask" for r in e["reason_ids"]
               if r.startswith(("ask-fields", "ask-already", "ask-tool", "ask-past", "ask-record", "notify-"))}
    assert len(reasons) == 7
    missing_reasons = [r for r in sorted(reasons) + list(COMMAND_REASONS) if f"`{r}`" not in flat]
    assert not missing_reasons, missing_reasons
    missing_keys = [k for k in ("owner_ask.max_open", "owner_ask.tool_allowed", "notify.command") if f"`{k}`" not in flat]
    assert not missing_keys, missing_keys
    missing_lines = [line for line in (
        "`default: <text or none>`", "`deadline: <ISO local time or none>`", "`blocked: <what waits, or none>`",
        "`reversible: yes|no`", "`status: open`", "`answered`", "`default-taken`", "`withdrawn`",
        "`mkway asks`", "`mkway ask default <id>`", "`mkway ask answered <id>`", "`--quote-file`",
        "`{file}`", "`{line}`", "`AskUserQuestion`", "`open asks: N (oldest <age>)", "`ask-default`")
        if line not in flat]
    assert not missing_lines, missing_lines


def test_the_section_states_the_never_default_list_and_marks_the_example():
    """Checks: the method rule lists what is never taken by default, and the notify command is marked as an example (E17)."""
    # the list leaves out no case: irreversible, leaves the task, deletes, locks and windows, the owner's own words;
    # the example reads as an example with no channel shipped, and is the one generic HTTP push with a placeholder;
    # Catches: a list that leaves out a case, or an example that reads as the engine's own channel
    flat = _section().lower()
    missing_items = [item for item in ("irreversible", "leaves the task", "deletes", "locks and windows",
                                       "the owner's own words") if item not in flat]
    assert not missing_items, missing_items
    assert "never" in flat
    assert "default" in flat
    assert "example" in flat
    assert "ships no channel" in flat
    assert "curl" in flat
