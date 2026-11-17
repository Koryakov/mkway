"""The README section «Questions to the owner» (card MW-007, part 5)."""
import json
import re

import pytest

from _engine import REPO

README = REPO / "README.md"
HEADING = "## Questions to the owner"
OWNER_REASONS = ("ask-sources-missing", "ask-sources-kind", "ask-sources-lines", "ask-not-written")
NEEDLES = ("`ask-sources-missing`", "`ask-sources-kind`", "`ask-sources-lines`", "`ask-not-written`",
           "`owner_ask.dir`", "`owner_ask.markers`", "`owner_ask.sources`",
           "`<asks dir>/<name>_ask.md`", "`<name>_sources.md`", "`kind: substance`", "`kind: session`",
           "`kind: lock`", "`review: N contradictions`", "`> review: <verbatim>`", "`checked: ListAgents`",
           "`checked: <lock state>`", "`Request:`", "`stop_hook_active`", "`transcript_path`",
           "`<bundle.root>/asks`", "`gates.owner_ask`", "`paths.exempt`", "`gates off:`")
OWNER_ASK_KEYS = {"dir", "markers", "sources"}  # the schema's owner_ask keys, without max_open and tool_allowed
OWNER_ASK_REASONS = {"ask-already-open", "ask-fields-missing", "ask-not-written", "ask-past-deadline",
                     "ask-record-failed", "ask-sources-kind", "ask-sources-lines", "ask-sources-missing",
                     "ask-tool-off", "notify-failed", "notify-sent"}


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


def _owner_reasons():
    """The four owner-ask reason ids of the manifest that the section must name, in manifest order."""
    manifest = json.loads((REPO / "engine" / "manifest.json").read_text(encoding="utf-8"))["entries"]
    return [r for e in manifest if e["gate"] == "owner_ask" for r in e["reason_ids"] if r in OWNER_REASONS]


def _needle_id(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


@pytest.mark.engine_repo  # the README is not in an engine copy: `mkway check` leaves these out (as test_register does)
def test_the_readme_has_one_section_questions_to_the_owner():
    """Catches: a second section, or a heading with no text (E20 part 5)."""
    text = _text()
    assert text.count("\n" + HEADING + "\n") == 1
    assert len(_flat(_section())) > 400
    assert len([h for h in re.findall(r"^## .*$", text, re.M) if "owner" in h.lower() and "question" in h.lower()]) == 1


@pytest.mark.engine_repo
@pytest.mark.parametrize("needle", NEEDLES, ids=_needle_id)
def test_the_section_states_the_gates_the_keys_and_their_defaults(needle):
    """Checks: the section describes the gates, their keys and their defaults as the engine has them (E21 part 5)."""
    assert len(_owner_reasons()) == 4
    assert needle in _flat(_section())


@pytest.mark.engine_repo
def test_the_owner_ask_keys_and_reasons_are_the_literal_sets():
    """Checks: the owner_ask keys without max_open and tool_allowed, and every owner_ask reason of the manifest, are the literal sets of this test, so a new key or reason fails until it is named here (E21 part 5)."""
    schema = json.loads((REPO / "engine" / "profile.schema.json").read_text(encoding="utf-8"))
    keys = {k for k in schema["properties"]["owner_ask"]["properties"] if k not in ("max_open", "tool_allowed")}
    manifest = json.loads((REPO / "engine" / "manifest.json").read_text(encoding="utf-8"))["entries"]
    reasons = {r for e in manifest if e["gate"] == "owner_ask" for r in e["reason_ids"]}
    assert keys == OWNER_ASK_KEYS
    assert reasons == OWNER_ASK_REASONS
    assert {f"`owner_ask.{k}`" for k in OWNER_ASK_KEYS} <= set(NEEDLES)


@pytest.mark.engine_repo
def test_the_section_adds_the_two_method_sentences():
    """Checks: the section carries the two method sentences of the order, a fresh reader checking an ask before it goes and C-24 for the commit lock (E22 part 5)."""
    flat = _flat(_section())
    assert "Method: a fresh reader checks an ask before it goes." in flat
    assert "C-24 = the owner closes the commit lock while the owner questions a flaw." in flat
