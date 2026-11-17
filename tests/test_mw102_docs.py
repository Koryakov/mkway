"""Card MW-102: the register, the changelog, the README and the manifest name what the card changes. Documents are read here
only (a doc-consistency check); no behaviour is judged from them."""
import json
import re

import pytest

import _docs as docs
from _engine import REPO

pytestmark = pytest.mark.engine_repo

TITLE = "The orderer commits the verdict file of a card it ordered, under the close's row proof"
README = REPO / "README.md"


def test_register_changelog_and_card_name_the_card():
    """Checks: the card has its register row, its changelog line last in the top section, its card folder."""
    register = (REPO / "cards" / "REGISTER.md").read_text(encoding="utf-8")
    row = re.search(r"^\| MW-102 \| (.+?) \| proposed \| `cards/MW-102-[a-z0-9-]+` \|$", register, re.M)
    assert row is not None, "no register row of MW-102"
    assert row.group(1) == TITLE
    changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    holding = [sec.splitlines() for sec in changelog.split("\n## ")[1:] if f"- MW-102: {TITLE}" in sec.splitlines()]  # MW144-D2
    assert len(holding) == 1 and holding[0][0].strip().count(".") == 2 and holding[0][0].strip().replace(".", "").isdigit()
    # changed by R256: the line is not pinned as the last line of its section
    docs.assert_version_file()
    assert list((REPO / "cards").glob("MW-102-*/CARD.md"))


def test_the_readme_paragraph_names_the_sequence():
    """Checks: the last paragraph of the section that holds the verdict command paragraph names the file, the sequence and the proof."""
    text = README.read_text(encoding="utf-8")
    start = text.index("## Outbox check: a text leaves only after a fresh reader")
    section = text[start:].split("\n## ")[0]
    last = " ".join(section.rstrip().split("\n\n")[-1].split())
    assert last.startswith("**The verdict file commit (MW-102).**")
    assert [w for w in ("`tests/verdicts/<card>.md`", "`verdict add`", "the orderer commits the verdict file", "close",
                        "status commit", "`verdict-unproven`", "the holder", "R254") if w not in last] == []


def test_the_reason_is_declared_in_the_core_and_the_manifest():
    """Checks: `verdict-unproven` is a reason of the core's list and of the manifest entry `commit_files`."""
    import core
    manifest = json.loads((REPO / "engine" / "manifest.json").read_text(encoding="utf-8"))
    entry = next(e for e in manifest["entries"] if e["name"] == "commit_files")
    assert ("verdict-unproven" in core.REASONS, "verdict-unproven" in entry["reason_ids"]) == (True, True)
