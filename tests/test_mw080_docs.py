"""Card MW-080: the register, the changelog, the schema, KEYS.md, the manifest, the module docstring and the README name what
the card changes. Documents are read here only (a doc-consistency check); no behaviour is judged from them."""
import json
import re

import pytest

import _docs as docs
from _engine import ENGINE, REPO

pytestmark = pytest.mark.engine_repo

TITLE = "A verdict row is written only by the engine command"
REASONS = ("verdict-by-holder", "verdict-by-committer", "verdict-by-owner", "verdict-no-caller", "verdict-card-state",
           "verdict-no-reader-run", "verdict-stale", "verdict-runs-exceeded", "verdict-node-unknown",
           "verdict-not-enforced", "verdict-run-before-recut",  # R251b: the recut adds one add refusal
           "verdict-no-red-proof")  # MW-117 (MW117-D1): the red-proof row of the card
README = REPO / "README.md"


def test_register_changelog_and_card_name_the_card():
    """Checks: the card has its register row, its changelog line in the top section, its card folder, and VERSION is set. R210"""
    register = (REPO / "cards" / "REGISTER.md").read_text(encoding="utf-8")
    row = re.search(r"^\| MW-080 \| (.+?) \| proposed \| `cards/MW-080-[a-z0-9-]+` \|$", register, re.M)
    assert row is not None, "no register row of MW-080"
    assert row.group(1) == TITLE
    changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"- MW-080: {TITLE}" in changelog.split("\n## ")[1].splitlines()
    docs.assert_version_file()
    assert list((REPO / "cards").glob("MW-080-*/CARD.md"))


def test_the_schema_and_keys_name_the_verdict_add_mode():
    """Checks: the verdict add mode is in the schema with the values trip and watch, and KEYS.md explains it."""
    schema = json.loads((ENGINE / "profile.schema.json").read_text(encoding="utf-8"))
    tests = schema["properties"]["tests"]["properties"]
    # R210a: the last-position check is void (JSON key order carries no meaning); only the presence of the key is checked.
    assert "verdict_add" in tests
    assert tests["verdict_add"]["properties"]["mode"]["enum"] == ["trip", "watch"]
    assert "| `tests.verdict_add.mode` |" in (ENGINE / "KEYS.md").read_text(encoding="utf-8")


def test_the_defaults_do_not_hold_the_key():
    """Checks: the key is in the schema and not in defaults.json, which tests/test_defaults.py counts. R196a"""
    assert "verdict_add" in (ENGINE / "profile.schema.json").read_text(encoding="utf-8")
    assert "verdict_add" not in (ENGINE / "defaults.json").read_text(encoding="utf-8")


def test_the_manifest_declares_the_verdict_file_refusal():
    """Checks: the manifest entry of the verdict file refusal declares its two reason ids."""
    manifest = json.loads((ENGINE / "manifest.json").read_text(encoding="utf-8"))["entries"]
    (entry,) = [e for e in manifest if e["name"] == "outbox_check.pre"]
    assert entry["reason_ids"] == ["check-sha-mismatch", "verdict-file-by-command"]


def test_the_module_docstring_names_every_reason_id():
    """Checks: the module documenting the command names every reason id, and the core declares the same set."""
    import core_verdict_add
    import verdict_add
    assert set(core_verdict_add.REASONS) == set(REASONS)
    assert [r for r in REASONS if r not in (verdict_add.__doc__ or "")] == []


def test_the_readme_paragraph_names_the_command_the_reasons_and_the_modes():
    """Checks: the README paragraph after the blind verdict one names the command, a reason id, the key, the modes and the refusals in both."""
    text = README.read_text(encoding="utf-8")
    start = text.index("## Outbox check: a text leaves only after a fresh reader")
    paragraphs = [" ".join(p.split()) for p in text[start:].split("\n\n")]
    (at,) = [i for i, p in enumerate(paragraphs) if p.startswith("**The blind verdict at `card close` (MW-068).**")]
    flat = paragraphs[at + 1]
    assert flat.startswith("**The verdict command (MW-080).**")
    assert [w for w in ("`mkway verdict add`", "`tests.verdict_add.mode`", "`trip`", "`watch`", "in both modes",
                        *(f"`{r}`" for r in REASONS), "`verdict-file-by-command`") if w not in flat] == []
