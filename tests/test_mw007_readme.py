"""The README section «Questions to the owner» (card MW-007, part 5)."""
import json
import re

import pytest

from _engine import REPO

README = REPO / "README.md"
HEADING = "## Questions to the owner"


def _text():
    return README.read_text(encoding="utf-8")


def _section():
    text = _text()
    start = text.index(HEADING + "\n")
    rest = text[start + len(HEADING):]
    nxt = re.search(r"^## ", rest, re.M)
    return rest[:nxt.start()] if nxt else rest


def _flat(text):
    return " ".join(text.split())


@pytest.mark.engine_repo  # the README is not in an engine copy: `mkway check` leaves these out (as test_register does)
def test_the_readme_has_one_section_questions_to_the_owner():
    """E20 (part 5): one heading `## Questions to the owner`, with a body, and no other heading about asks.
    Catches: a second section, or a heading with no text."""
    text = _text()
    assert text.count("\n" + HEADING + "\n") == 1
    assert len(_flat(_section())) > 400
    assert len([h for h in re.findall(r"^## .*$", text, re.M) if "owner" in h.lower() and "question" in h.lower()]) == 1


@pytest.mark.engine_repo
def test_the_section_states_the_gates_the_keys_and_their_defaults():
    """E21 (part 5): the section names the edit gate (the sources file, the three kinds and their lines), the stop
    gate (the marker, `stop_hook_active`, the transcript it reads), every reason id of the two manifest entries, the
    three profile keys with their defaults, the subtask gate's `paths.exempt` and the start block's `gates off`.
    Reason ids and keys are read from the manifest and the schema, so the text cannot drift from them. Catches: a
    section that describes a gate the engine does not have, or leaves out a refusal a session will meet."""
    flat = _flat(_section())
    manifest = json.loads((REPO / "engine" / "manifest.json").read_text(encoding="utf-8"))["entries"]
    # changed by MW-014 (E17): the reasons and keys MW-014 adds are checked in test_mw014_readme.py, in their own section
    reasons = {r for e in manifest if e["gate"] == "owner_ask" for r in e["reason_ids"]
               if r in ("ask-sources-missing", "ask-sources-kind", "ask-sources-lines", "ask-not-written")}
    assert len(reasons) == 4
    for reason in reasons:
        assert f"`{reason}`" in flat, reason
    schema = json.loads((REPO / "engine" / "profile.schema.json").read_text(encoding="utf-8"))
    for key in schema["properties"]["owner_ask"]["properties"]:
        if key not in ("max_open", "tool_allowed"):
            assert f"`owner_ask.{key}`" in flat, key
    for needed in ("`<asks dir>/<name>_ask.md`", "`<name>_sources.md`", "`kind: substance`", "`kind: session`",
                   "`kind: lock`", "`review: N contradictions`", "`> review: <verbatim>`", "`checked: ListAgents`",
                   "`checked: <lock state>`", "`Request:`", "`stop_hook_active`", "`transcript_path`",
                   "`<bundle.root>/asks`", "`gates.owner_ask`", "`paths.exempt`", "`gates off:`"):
        assert needed in flat, needed


@pytest.mark.engine_repo
def test_the_section_adds_the_two_method_sentences():
    """E22 (part 5): the section carries the two method sentences of the order: a fresh reader checks an ask before
    it goes; C-24 = the owner closes the commit lock while the owner questions a flaw. Catches: a section that
    describes the gates but drops the method."""
    flat = _flat(_section())
    assert "Method: a fresh reader checks an ask before it goes." in flat
    assert "C-24 = the owner closes the commit lock while the owner questions a flaw." in flat
