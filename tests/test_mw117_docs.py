"""Card MW-117: the register, the changelog, the README and the manifest name what the card changes (the window of a verdict, the
new refusal verdict-no-red-proof, the close id verdict-stale for an Acceptance change). Documents are read here only (a
doc-consistency check); no behaviour is judged from them."""
import json
import re

import pytest

from _engine import ENGINE, REPO

pytestmark = pytest.mark.engine_repo

TITLE = "a verdict is allowed any time after the red commit, held or not, until the card closes; a test or an Acceptance row edited after it makes it stale at close"
README = (REPO / "README.md").read_text(encoding="utf-8")


def test_register_changelog_and_card_name_the_card():
    """Checks: the card has its register row, its changelog line in the top section and its card folder."""
    register = (REPO / "cards" / "REGISTER.md").read_text(encoding="utf-8")
    row = re.search(r"^\| MW-117 \| (.+?) \| proposed \| `cards/MW-117-[a-z0-9-]+` \|$", register, re.M)
    assert row is not None and row.group(1) == TITLE
    changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    holding = [sec.splitlines() for sec in changelog.split("\n## ")[1:] if f"- MW-117: {TITLE}" in sec.splitlines()]  # MW144-D2
    assert len(holding) == 1 and holding[0][0].strip().count(".") == 2 and holding[0][0].strip().replace(".", "").isdigit()
    assert list((REPO / "cards").glob("MW-117-*/CARD.md"))


def test_the_readme_states_the_window_and_the_new_refusal():
    """Checks: the verdict-timing sentence names the red commit, no longer says a held card is refused, and names the id."""
    start = README.index("**The verdict command (MW-080).**")
    section = README[start:README.index("\n\n", start)]
    assert "verdict-no-red-proof" in section and "red-proof" in section
    assert "open with no holder" not in section


def test_the_manifest_lists_verdict_stale_for_the_commit_gate():
    """Checks: the commit gate may refuse with verdict-stale (an Acceptance change after the verdict)."""
    manifest = json.loads((ENGINE / "manifest.json").read_text(encoding="utf-8"))
    entry = next(e for e in manifest["gates"] if e["name"] == "commit_files") if "gates" in manifest else next(
        e for e in manifest["entries"] if e["name"] == "commit_files")
    assert "verdict-stale" in entry["reason_ids"]
