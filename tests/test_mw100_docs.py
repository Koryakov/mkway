"""Card MW-100: the register, the changelog, the module docstrings and the README name what the card changes. Documents are
read here only (a doc-consistency check); no behaviour is judged from them."""
import re

import pytest

import _docs as docs
from _engine import REPO

pytestmark = pytest.mark.engine_repo

TITLE = "A weak or wrong verdict is answered by a re-cut, never by an acceptance"
NEW_IDS = ("verdict-recut-nothing", "verdict-recut-no-change", "verdict-recut-stale", "verdict-recut-exceeded",
           "verdict-recut-not-lead", "verdict-recut-pending", "verdict-run-before-recut")
REUSED_IDS = ("verdict-by-holder", "verdict-by-committer", "verdict-by-owner", "verdict-no-caller", "verdict-card-state",
              "verdict-node-unknown", "verdict-not-enforced")
README = REPO / "README.md"


def test_register_changelog_and_card_name_the_card():
    """Checks: the card has its register row, its changelog line last in the top section, its card folder, and VERSION is set."""
    register = (REPO / "cards" / "REGISTER.md").read_text(encoding="utf-8")
    row = re.search(r"^\| MW-100 \| (.+?) \| proposed \| `cards/MW-100-[a-z0-9-]+` \|$", register, re.M)
    assert row is not None, "no register row of MW-100"
    assert row.group(1) == TITLE
    top = (REPO / "CHANGELOG.md").read_text(encoding="utf-8").split("\n## ")[1].rstrip().splitlines()
    assert f"- MW-100: {TITLE}" in top  # MW-101 (R253) adds its line after this one
    docs.assert_version_file()
    assert list((REPO / "cards").glob("MW-100-*/CARD.md"))


def test_the_module_docstrings_name_every_reason_id():
    """Checks: the modules documenting the recut name the command and every reason id; the add module names the new add refusal."""
    import core_verdict_add
    import core_verdict_recut
    import verdict_add
    import verdict_recut
    text = (core_verdict_recut.__doc__ or "") + (verdict_recut.__doc__ or "")
    missing = [i for i in (*NEW_IDS[:6], *REUSED_IDS) if i not in text]
    assert (missing, "mkway verdict recut" in text, "verdict-run-before-recut" in (verdict_add.__doc__ or ""),
            "verdict-run-before-recut" in core_verdict_add.REASONS) == ([], True, True, True)


def test_the_readme_paragraph_names_the_command_and_every_id():
    """Checks: the last paragraph of the section that holds the verdict command paragraph names the command, every id, the key and both modes."""
    text = README.read_text(encoding="utf-8")
    start = text.index("## Outbox check: a text leaves only after a fresh reader")
    section = text[start:].split("\n## ")[0]
    paragraphs = [" ".join(p.split()) for p in section.rstrip().split("\n\n")]
    last = next(p for p in paragraphs if p.startswith("**The verdict recut (MW-100).**"))  # MW-101 (R253) adds one after it
    assert last.startswith("**The verdict recut (MW-100).**")
    assert [w for w in ("`mkway verdict recut`", "`tests.verdict_add.mode`", "`trip`", "`watch`", "in both modes",
                        *(f"`{i}`" for i in (*NEW_IDS, *REUSED_IDS))) if w not in last] == []
