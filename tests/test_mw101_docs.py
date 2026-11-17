"""Card MW-101: the register, the changelog and the README name what the card changes. Documents are read here only (a
doc-consistency check); no behaviour is judged from them."""
import re

import pytest

import _docs as docs
from _engine import REPO

pytestmark = pytest.mark.engine_repo

TITLE = "A verdict stays fresh while its node's meaning is unchanged, read from git"
README = REPO / "README.md"


def test_register_changelog_and_card_name_the_card():
    """Checks: the card has its register row last in the register, its changelog line last in the top section, its card folder."""
    register = (REPO / "cards" / "REGISTER.md").read_text(encoding="utf-8")
    row = re.search(r"^\| MW-101 \| (.+?) \| proposed \| `cards/MW-101-[a-z0-9-]+` \|$", register, re.M)
    assert row is not None, "no register row of MW-101"
    assert row.group(1) == TITLE
    changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    holding = [sec.splitlines() for sec in changelog.split("\n## ")[1:] if f"- MW-101: {TITLE}" in sec.splitlines()]  # MW144-D2
    assert len(holding) == 1 and holding[0][0].strip().count(".") == 2 and holding[0][0].strip().replace(".", "").isdigit()
    # MW-102 (R254) adds its line after this one
    docs.assert_version_file()
    assert list((REPO / "cards").glob("MW-101-*/CARD.md"))


def test_the_readme_paragraph_names_the_rule_and_the_gap():
    """Checks: the paragraph of MW-101 in the section that holds the verdict command paragraph names the rule, git, and the named gap."""
    text = README.read_text(encoding="utf-8")
    start = text.index("## Outbox check: a text leaves only after a fresh reader")
    section = text[start:].split("\n## ")[0]
    paragraphs = [" ".join(part.split()) for part in section.rstrip().split("\n\n")]  # MW-102 (R254) adds its paragraph after this one
    last = next((p for p in paragraphs if p.startswith("**Node freshness at close (MW-101).**")), "")
    assert last != ""
    assert [w for w in ("`verdict-unproven`", "`engine/core_node_fresh.py`", "non-test code", "cross-file helpers",
                        "`conftest.py`", "never the file's mtime", "R253") if w not in last] == []
