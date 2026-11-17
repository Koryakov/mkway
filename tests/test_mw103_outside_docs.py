"""Card MW-103 (rulings R255, R255b): the default list `paths.outside_writable` is in defaults.json and the schema, documented
in engine/KEYS.md, and the card is in the README, the register and the changelog, each at the end. Synthetic checks on the
repository's own documents."""
import json
from pathlib import Path

import pytest

from _keys_md import section_rows, unquote

pytestmark = pytest.mark.engine_repo

REPO = Path(__file__).resolve().parents[1]
THREE = ["<home>/.claude/projects/*/memory/**", "<home>/.claude/plans/**", "<temp>/claude/**"]


def test_defaults_and_schema_hold_the_three_patterns():
    """Checks: E29, defaults.json holds exactly the three narrow patterns and the schema declares the key as an array of non-empty strings."""
    defaults = json.loads((REPO / "engine" / "defaults.json").read_text(encoding="utf-8"))
    schema = json.loads((REPO / "engine" / "profile.schema.json").read_text(encoding="utf-8"))
    node = schema["properties"]["paths"]["properties"]["outside_writable"]  # R274-D1: the key moved to `paths`
    assert (defaults["paths"]["outside_writable"], node["type"], node["items"]["type"], node["items"]["minLength"]) == (
        THREE, "array", "string", 1)


def test_keys_md_has_the_rows_and_the_counts():
    """Checks: E30, one row in the added keys, one in the engine defaults, and the counts 30 in defaults.json and 32 in the heading."""
    text = (REPO / "engine" / "KEYS.md").read_text(encoding="utf-8")
    added = {unquote(r[0]): r for r in section_rows("Added keys")}
    marks = {(unquote(r[0]), unquote(r[1])): r[2] for r in section_rows("Engine defaults")}
    split = [x for x in text.splitlines() if x.startswith("Split: ") and "defaults.json" in x][0]
    got = (added["paths.outside_writable"][1], marks[("paths", "outside_writable")], "## Engine defaults (32)" in text,  # R274-D1
           split.startswith("Split: 30 in `defaults.json`, 7 later, 0 not established"))
    assert got == ("in schema now", "in defaults.json", True, True)


def test_readme_register_and_changelog_name_the_card():
    """Checks: E31, a paragraph of the lead section names the key, the register has the MW-103 row and the top changelog section holds its line (R256: none is pinned as the last)."""
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    section = readme.split("## The lead role", 1)[1].split("\n## ", 1)[0].strip()
    paragraphs = section.split("\n\n")
    register = (REPO / "cards" / "REGISTER.md").read_text(encoding="utf-8").splitlines()
    changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    holding = [sec.splitlines() for sec in changelog.split("\n## ")[1:] if any(x.startswith("- MW-103:") for x in sec.splitlines())]  # MW144-D2
    assert len(holding) == 1 and holding[0][0].strip().count(".") == 2 and holding[0][0].strip().replace(".", "").isdigit()
    top = holding[0]
    # R274-D1: the key moved to `paths`
    assert (any("paths.outside_writable" in p for p in paragraphs), any(r.startswith("| MW-103 |") for r in register),
            any(t.startswith("- MW-103:") for t in top)) == (True, True, True)
