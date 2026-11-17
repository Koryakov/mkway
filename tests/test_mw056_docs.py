"""Card MW-056: the manifest, the README and the register state the rule «a commit is refused only for new red».
Synthetic text only."""
import json

import pytest

from _engine import REPO

pytestmark = pytest.mark.engine_repo

TITLE = "A commit is refused only for new red"


def test_the_manifest_declares_the_warn_reason_of_the_allow_line():
    """E15: the entry `commit_tests` declares `commit-tests-still-red` beside its four older reason ids; the dispatcher
    writes a warn row only for a declared id. Catches: an allow line that the log records as `undeclared-reason`."""
    manifest = json.loads((REPO / "engine" / "manifest.json").read_text(encoding="utf-8"))["entries"]
    (entry,) = [e for e in manifest if e["name"] == "commit_tests"]
    # changed by MW-072 (E54): the entry also declares the four red proof ids; the five older ids stay
    # changed by MW-090 (T7 decision: R225): the entry also declares the five case_map ids; the nine older ids stay
    assert set(entry["reason_ids"]) == {"commit-tests-failed", "commit-tests-over-budget", "commit-tests-not-run",
                                        "commit-tests-chained", "commit-tests-still-red", "red-not-proven",
                                        "red-ids-still-red", "red-not-recorded", "test-without-red-proof",
                                        "case-map-no-decision", "case-map-unknown-left", "case-map-unknown-right",
                                        "case-map-merge", "case-map-malformed", "shared-record-busy",
                                        "red-record-partial",
                                        # changed by MW-134 (R347, R348): the gate also returns the seven retire ids
                                        "retire-no-decision", "retire-decision-not-in-ledger", "retire-decision-closed",
                                        "retire-decision-by-self", "retire-no-ledger", "retire-right-not-red",
                                        "retire-left-failing"}


def test_the_readme_states_the_new_rule():
    """E16: the README section on tests before a commit states the rule: new red refuses, the committing card's own red
    refuses, an old red of another open card does not (with the allow line and its reason id), an old red nobody owns
    refuses, only an open card owns a red, and where HEAD's results are kept and when they are ignored.
    Catches: a gate whose rule lives only in code."""
    text = (REPO / "README.md").read_text(encoding="utf-8")
    body = text.split("## Tests before a commit", 1)[1].split("\n## ", 1)[0]
    for needed in ("new red", "not red at HEAD", "still red, owned by", "`commit-tests-still-red`", "no owner",
                   "a card must take it", "open card", "`commit_tests_head.jsonl`", "tree of HEAD",
                   "`tests.command`", "profile"):
        assert needed in body, needed


def test_register_changelog_and_card_name_the_card():
    """E17: a register row, a CHANGELOG line under the top section, the card folder; VERSION is not changed here."""
    register = (REPO / "cards" / "REGISTER.md").read_text(encoding="utf-8")
    assert f"| MW-056 | {TITLE} |" in register
    assert (REPO / "cards" / "MW-056-new-red-only" / "CARD.md").is_file()
    changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    holding = [sec.splitlines() for sec in changelog.split("\n## ")[1:] if f"MW-056: {TITLE}" in sec]  # MW144-D2
    assert len(holding) == 1 and holding[0][0].strip().count(".") == 2 and holding[0][0].strip().replace(".", "").isdigit()
