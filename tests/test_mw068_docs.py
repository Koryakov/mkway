"""Card MW-068: the register, the changelog, the schema, KEYS.md and the template name what the card changes.
Documents are read here only (a doc-consistency check); no behaviour is judged from them."""
import json
import re


import pytest

import _docs as docs
from _engine import ENGINE, REPO

pytestmark = pytest.mark.engine_repo

TITLE = "A test node named by a card has a blind verdict before close"


def test_register_changelog_and_card_name_the_card():
    """Checks: a register row, one changelog line under the top section, and the card folder name the card (E16)."""
    # VERSION is not changed here; Catches: a card added with no register row or no changelog line
    register = (REPO / "cards" / "REGISTER.md").read_text(encoding="utf-8")
    row = re.search(r"^\| MW-068 \| (.+?) \| proposed \| `cards/MW-068-[a-z0-9-]+` \|\r?$", register, re.M)
    assert row
    assert row.group(1) == TITLE, "no register row of MW-068 with the title of the card"
    changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    holding = [sec.splitlines() for sec in changelog.split("\n## ")[1:] if f"- MW-068: {TITLE}" in sec.splitlines()]  # MW144-D2
    assert len(holding) == 1 and holding[0][0].strip().count(".") == 2 and holding[0][0].strip().replace(".", "").isdigit()
    assert f"- MW-068: {TITLE}" in docs.changelog_section(changelog, "MW-068").splitlines()
    docs.assert_version_file()
    assert list((REPO / "cards").glob("MW-068-*/CARD.md"))


def test_the_schema_and_keys_name_cards_verdicts():
    """Checks: the profile key is in the schema as required or off, and has a line in KEYS.md (E14)."""
    # Catches: a key the code reads that the schema refuses (every profile that sets it invalid) or that no document explains
    schema = json.loads((ENGINE / "profile.schema.json").read_text(encoding="utf-8"))
    key = schema["properties"]["cards"]["properties"]["verdicts"]
    assert key["enum"] == ["required", "off"]
    assert "| `cards.verdicts` |" in (ENGINE / "KEYS.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("vcs", ["none", "git"])
def test_a_fresh_install_has_the_verdict_check_on(vcs):
    """Checks: the starter profile of a fresh install and the default keep the verdict check on, never switched off."""
    # Catches: a profile a fresh install writes (or a default) that switches the check off, so a task never has it
    import install
    import cardtool
    profile = install.starter_profile(vcs)
    assert (profile.get("cards") or {}).get("verdicts") != "off"
    assert cardtool.verdicts_required(profile)
    assert cardtool.verdicts_required({})
    assert not cardtool.verdicts_required({"cards": {"verdicts": "off"}})


@pytest.mark.parametrize("vcs", ["none", "git"])
def test_a_fresh_install_writes_the_default_checker(vcs):
    """Checks: a starter profile names the fresh-reader checker, so a new root is not in the unenforced state (R179 cond. 2)."""
    # Catches: a starter profile with no outbox.checkers, so the default-on rule (R173 item 3) holds on paper only
    import install
    assert install.starter_profile(vcs)["outbox"]["checkers"] == ["fresh-reader"]  # decision: R180


def test_the_shared_task_root_does_not_switch_the_check_off(tmp_path):
    """Checks: the shared task root fixture keeps the verdict check on, with no blanket off (E14)."""
    # Catches: a blanket off in the shared fixture, which hides the check from every older close test; a fixture that
    # needs it off says so itself
    from _engine import task_root
    profile = json.loads((task_root(tmp_path).joinpath("mkway", "profile.json")).read_text(encoding="utf-8"))
    assert (profile.get("cards") or {}).get("verdicts") != "off"


def test_the_template_names_t1_to_t8_and_the_verdict_file():
    """Checks: the card form names T1 to T8 and the criteria and the verdict file, and not the old C1 to C5 (E15)."""
    # Catches: a card form that still teaches the old five criteria, or never mentions the verdict file
    text = (REPO / "cards" / "_TEMPLATE" / "CARD.md").read_text(encoding="utf-8")
    assert "C1 rows" not in text
    assert "C5 can fail" not in text
    assert any("T1" in line and "T8" in line for line in text.splitlines())
    assert "tests/verdicts/<ID>.md" in text
