"""Card MW-061: the register and the changelog name the card. Synthetic text only."""
import re

import pytest

import _docs as docs
from _engine import REPO

pytestmark = pytest.mark.engine_repo

TITLE = "A command with a newline inside quotes is read whole"


def test_register_changelog_and_card_name_the_card():
    """Checks: a register row, one changelog line under the top section and the card folder of MW-061 name the card; VERSION stays one semver line (E9)."""
    register = (REPO / "cards" / "REGISTER.md").read_text(encoding="utf-8")
    row = re.search(r"^\| MW-061 \| (.+?) \| proposed \| `cards/MW-061-[a-z0-9-]+` \|\r?$", register, re.M)
    assert row, "no register row of MW-061 with the title of the card"
    assert row.group(1) == TITLE, "no register row of MW-061 with the title of the card"
    changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    top = changelog.split("\n## ")[1]
    assert f"- MW-061: {TITLE}" in top.splitlines(), "no changelog line of MW-061 under the top section"
    assert f"- MW-061: {TITLE}" in docs.changelog_section(changelog, "MW-061").splitlines()
    docs.assert_version_file()
    assert list((REPO / "cards").glob("MW-061-*/CARD.md"))
