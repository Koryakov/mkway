"""Card MW-107: the register, the changelog and the README name what the card changes. Documents are read here only (a
doc-consistency check); a test checks that its line or row is present, never that it is the last one (R256); no behaviour is
judged from them."""
import re

import pytest

import _docs as docs
from _engine import REPO

pytestmark = pytest.mark.engine_repo

TITLE = "one owner per file kind: the owner table, a write outside the root refused for every session"
LINE = ("- MW-107: " + TITLE + "; the profile key `leads.outside_writable` is now `paths.outside_writable`, `mkway upgrade` renames it, "
        "and the old key is an alias kept until the next major; removed with it")  # R274b, R274-D2 (5): the one line, in full
MARK = "The owner table (MW-107)"
WORDS = ["`engine/owners.py`", "`owner_of`", "orderer", "holder", "reader", "engine", "owner", "`write-outside-root`",
         "`paths.outside_writable`", "`paths.exempt`", "`ORDER_fix1.md`", "one source", "a card whose Paths hold it",
         "`delete-outside-root`", "hard from install", "on purpose", "no watch date", "R274a 8.5", "R274a 8.6",
         "`outside.edit`", "`outside.shell`"]  # R274a 8.6: the gate is hard from install; 8.5: the upgrade step checks the list first; R274e: its own gate


def test_the_readme_changelog_and_register_carry_the_card():
    """Checks: the register row, one changelog line in one release section, the card folder, and one README paragraph that names the table, the roles, the refusal id, the lists and the way outs."""
    register = (REPO / "cards" / "REGISTER.md").read_text(encoding="utf-8")
    row = re.search(r"^\| MW-107 \| (.+?) \| proposed \| `cards/MW-107-[a-z0-9-]+` \|$", register, re.M)
    assert row is not None, "no register row of MW-107"
    section = docs.changelog_section((REPO / "CHANGELOG.md").read_text(encoding="utf-8"), "MW-107")
    paragraphs = [" ".join(part.split()) for part in re.split(r"\n\s*\n", (REPO / "README.md").read_text(encoding="utf-8"))]
    found = [p for p in paragraphs if MARK in p]
    assert len(found) == 1, "the README must hold the paragraph of the owner table once"
    mine = [x for x in section.splitlines() if x.startswith("- MW-107:")]  # R274e (14): exactly one line, equal to the sentence
    assert (row.group(1), mine, bool(list((REPO / "cards").glob("MW-107-*/CARD.md"))),
            [w for w in WORDS if w not in found[0]]) == (TITLE, [LINE], True, [])


def test_the_changelog_says_how_long_the_old_key_is_kept():
    """Checks: R274b 1, a changelog line names the alias of `leads.outside_writable` and says it is kept until the next major and removed with it."""
    section = docs.changelog_section((REPO / "CHANGELOG.md").read_text(encoding="utf-8"), "MW-107")
    lines = [x for x in section.splitlines() if x.startswith("- MW-107:") and "alias kept until the next major; removed with it" in x]
    assert len(lines) == 1 and "`leads.outside_writable`" in lines[0]


def test_the_concept_page_k1_line_names_writes_outside_the_task_next_to_the_deletes():
    """Checks: R274c (2), the K1 line of the concept page names writes outside the task next to the deletes outside the task."""
    text = " ".join((REPO / "engine" / "CONCEPT.md").read_text(encoding="utf-8").split())
    assert "deletes outside the task, writes outside the task and the owner's lever are closed" in text
