"""Card MW-021, row E9: the README section «Rule cards paired with tests». The reason is read from the manifest, so the
text cannot drift from it."""
import json
import re

import pytest

from _engine import REPO

README = REPO / "README.md"
HEADING = "## Rule cards paired with tests"

pytestmark = pytest.mark.engine_repo  # the README is not in an engine copy: `mkway check` leaves these out


def _section():
    text = README.read_text(encoding="utf-8")
    rest = text[text.index(HEADING + "\n") + len(HEADING):]
    nxt = re.search(r"^## ", rest, re.M)
    return " ".join((rest[:nxt.start()] if nxt else rest).split())


def test_one_section_with_a_body():
    """E9: one heading `## Rule cards paired with tests`, with a body. Catches: a missing or doubled section."""
    assert README.read_text(encoding="utf-8").count("\n" + HEADING + "\n") == 1
    assert len(_section()) > 600


def test_the_section_names_the_keys_the_reason_the_command_and_the_start_line():
    """E9: both keys, the `{id}` form, `ids.rule_card`, the reason id from the manifest, the command, the start line,
    the state file of the last green tree and the way out of a refusal. Catches: a refusal a session will meet that the
    README does not explain."""
    flat = _section()
    manifest = json.loads((REPO / "engine" / "manifest.json").read_text(encoding="utf-8"))["entries"]
    reasons = [r for e in manifest if e["name"] == "commit_files" for r in e["reason_ids"] if r.startswith("rule-")]
    assert reasons == ["rule-without-test"]
    for word in ("rules.cards", "rules.test_for", "{id}", "ids.rule_card", "rule-without-test", "mkway rules",
                 "rules: N cards, M without tests", "commit_tests.jsonl", "git add", "commit_files", "integrity"):
        assert word in flat, word
