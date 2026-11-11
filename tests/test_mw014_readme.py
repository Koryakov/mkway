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
    """E17: one heading `## Asks that do not stop the work`, with a body. Catches: a missing or doubled section."""
    assert README.read_text(encoding="utf-8").count("\n" + HEADING + "\n") == 1
    assert len(_section()) > 800


def test_the_section_names_every_reason_key_and_command():
    """E17: every reason id the manifest declares for the new steps and every reason of the two commands, the three
    profile keys, the five field lines, the four statuses, the three commands and the two placeholders are in the text.
    Catches: a refusal a session will meet that the README does not explain."""
    flat = _section()
    manifest = json.loads((REPO / "engine" / "manifest.json").read_text(encoding="utf-8"))["entries"]
    reasons = {r for e in manifest if e["gate"] == "owner_ask" for r in e["reason_ids"]
               if r.startswith(("ask-fields", "ask-already", "ask-tool", "ask-past", "ask-record", "notify-"))}
    assert len(reasons) == 7
    for reason in sorted(reasons) + list(COMMAND_REASONS):
        assert f"`{reason}`" in flat, reason
    for key in ("owner_ask.max_open", "owner_ask.tool_allowed", "notify.command"):
        assert f"`{key}`" in flat, key
    for line in ("`default: <text or none>`", "`deadline: <ISO local time or none>`", "`blocked: <what waits, or none>`",
                 "`reversible: yes|no`", "`status: open`", "`answered`", "`default-taken`", "`withdrawn`",
                 "`mkway asks`", "`mkway ask default <id>`", "`mkway ask answered <id>`", "`--quote-file`",
                 "`{file}`", "`{line}`", "`AskUserQuestion`", "`open asks: N (oldest <age>)", "`ask-default`"):
        assert line in flat, line


def test_the_section_states_the_never_default_list_and_marks_the_example():
    """E17: the method rule lists what is never taken by default (anything irreversible, anything that leaves the task,
    deletes, locks and windows, the owner's own words), and the notify command shown is marked as an example with no
    channel shipped. Catches: a list that leaves out a case, or an example that reads as the engine's own channel."""
    flat = _section().lower()
    for item in ("irreversible", "leaves the task", "deletes", "locks and windows", "the owner's own words"):
        assert item in flat, item
    assert "never" in flat and "default" in flat
    assert "example" in flat and "ships no channel" in flat
    assert "curl" in flat  # the one generic example: an HTTP push service, with a placeholder address
