"""Card MW-104: the register, the changelog, the README, KEYS.md, release.json and the usage text name what the card
changes. Documents are read here only (a doc-consistency check); a test checks that its line or row is present, never that it
is the last one (R256); no behaviour is judged from them."""
import json
import re

import pytest

import _docs as docs
from _engine import REPO

pytestmark = pytest.mark.engine_repo

TITLE = ("`mkway upgrade`: the owner's command installs a proven-green engine release into a granted task root, with one "
         "ledger row and one commit (a Python rewrite of mkup 1.0.0)")


RELEASE_VALUES = {"branch": "master",
                  "full_command": ["python", "-m", "pytest", "-n", "auto", "--dist", "loadgroup", "--cov=engine",
                                   "--cov-branch", "--cov-report=term"],
                  "narrow_paths": [["cards/**", "cards/REGISTER.md", "CHANGELOG.md"]],
                  "narrow_command": ["python", "-m", "pytest", "tests/test_meta_cards.py", "tests/test_register.py"]}


def _flat(text):
    return " ".join(text.split())


def _section(text, heading):
    start = text.index(heading)
    return text[start:].split("\n## ")[0]


def test_register_changelog_and_card_name_the_card():
    """Checks: the card has its register row, its changelog line in one release section, its card folder."""
    register = (REPO / "cards" / "REGISTER.md").read_text(encoding="utf-8")
    row = re.search(r"^\| MW-104 \| (.+?) \| proposed \| `cards/MW-104-[a-z0-9-]+` \|$", register, re.M)
    assert row is not None, "no register row of MW-104"
    assert row.group(1) == TITLE
    section = docs.changelog_section((REPO / "CHANGELOG.md").read_text(encoding="utf-8"), "MW-104")
    assert f"- MW-104: {TITLE}" in section.splitlines()
    docs.assert_version_file()
    assert list((REPO / "cards").glob("MW-104-*/CARD.md"))


def test_the_readme_section_names_the_command_and_the_gap():
    """Checks: the README section of the upgrade command names both modes, the release.json keys, the green record, the owner-only rule and the named gap H7."""
    section = _flat(_section((REPO / "README.md").read_text(encoding="utf-8"), "## Upgrade: "))
    wanted = ["`mkway upgrade`", "`--from-head`", "internal", "`release.json`", "`branch`", "`full_command`", "`narrow_paths`",
              "`narrow_command`", "`mkway green record`", "`green.jsonl`", "`policy.json`", "`updates.jsonl`",
              "`MKWAY_UPGRADE_DIR`", "owner-only", "first-parent", "the lock gate cannot yet hold", "outside the repository",
              "travelling", "R257"]
    assert [w for w in wanted if w not in section] == []


def test_keys_md_documents_release_json():
    """Checks: KEYS.md has a release.json table with the four keys, and says `full_command` is distinct from the profile key `tests.command`."""
    section = _flat(_section((REPO / "engine" / "KEYS.md").read_text(encoding="utf-8"), "## release.json keys"))
    wanted = ["`branch`", "`full_command`", "`narrow_paths`", "`narrow_command`", "`tests.command`", "distinct",
              "never installed", "HEAD"]
    assert [w for w in wanted if w not in section] == []


def test_release_json_holds_the_four_values():
    """Checks: release.json at the top holds exactly the four keys with the values of the order, and the repository does not ignore it (it is tracked)."""
    data = json.loads((REPO / "release.json").read_text(encoding="utf-8"))
    assert data == RELEASE_VALUES
    assert "release.json" not in (REPO / ".gitignore").read_text(encoding="utf-8")


def test_the_usage_text_names_green_record():
    """Checks: the usage text of mkway.py names `green record` in its owner-only list, next to install and upgrade."""
    text = _flat((REPO / "engine" / "mkway.py").read_text(encoding="utf-8"))
    assert "(lock, gate, install, upgrade, green record, give," in text
    assert "mkway.py upgrade --target <repo>" in text
    assert "mkway.py green record --repo <path>" in text
