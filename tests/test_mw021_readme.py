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
    """Checks: the README has the heading once, and the section under it has a body. E9"""
    assert README.read_text(encoding="utf-8").count("\n" + HEADING + "\n") == 1
    assert len(_section()) > 600


@pytest.mark.parametrize("word", [
    pytest.param("rules.cards", id="rules-cards"),
    pytest.param("rules.test_for", id="rules-test-for"),
    pytest.param("{id}", id="id-form"),
    pytest.param("ids.rule_card", id="ids-rule-card"),
    pytest.param("rule-without-test", id="reason-id"),
    pytest.param("mkway rules", id="command"),
    pytest.param("rules: N cards, M without tests", id="start-line"),
    pytest.param("commit_tests.jsonl", id="state-file"),
    pytest.param("git add", id="way-out-git-add"),
    pytest.param("commit_files", id="commit-files-gate"),
    pytest.param("integrity", id="integrity-class"),
])
def test_the_section_names_the_keys_the_reason_the_command_and_the_start_line(word):
    """Checks: the section names one key, reason, command or start-line word per case, so a refusal a session meets is explained. E9"""
    flat = _section()
    manifest = json.loads((REPO / "engine" / "manifest.json").read_text(encoding="utf-8"))["entries"]
    reasons = [r for e in manifest if e["name"] == "commit_files" for r in e["reason_ids"] if r.startswith("rule-")]
    assert reasons == ["rule-without-test"]
    assert word in flat
