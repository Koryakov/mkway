"""Card MW-082 (decisions: R197 A, R197a), guard 1, rows E8 to E11: the union merge keeps the lines of both branches, so a
card line added twice must fail a test. The register's own test (tests/test_register.py) does not check ids for
duplicates, so both checks are here. The real files are read only; the duplicates are synthetic."""
import re
from collections import Counter
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CARD_LINE = re.compile(r"^- (MW-\d{3}):", re.M)
REGISTER_ROW = re.compile(r"^\| (MW-\d{3}) \|", re.M)


def _twice(ids):
    return sorted(i for i, n in Counter(ids).items() if n > 1)


def changelog_duplicates(text):
    """The card ids that appear on two lines of one release section of the changelog `text`."""
    return sorted({i for section in text.split("\n## ") for i in _twice(CARD_LINE.findall(section))})


def register_duplicates(text):
    """The card ids that head two rows of the register `text`."""
    return _twice(REGISTER_ROW.findall(text))


@pytest.mark.engine_repo
def test_the_real_changelog_has_no_card_line_twice_in_a_section():
    """Checks: the changelog on this branch holds one line per card in each release section."""
    assert changelog_duplicates((REPO / "CHANGELOG.md").read_text(encoding="utf-8")) == []


def test_a_card_line_twice_in_one_section_is_found():
    """Catches: a union merge that leaves the same card line twice in one release section."""
    text = "# Changes\n\n## 0.2.7\n- MW-001: one\n- MW-002: two\n- MW-001: one\n\n## 0.2.6\n- MW-001: old\n"
    assert changelog_duplicates(text) == ["MW-001"]


@pytest.mark.engine_repo
def test_the_real_register_has_no_card_id_twice():
    """Checks: the register on this branch holds one row per card id."""
    assert register_duplicates((REPO / "cards" / "REGISTER.md").read_text(encoding="utf-8")) == []


def test_a_register_card_id_twice_is_found():
    """Catches: a union merge that leaves two register rows for one card id."""
    text = "# Card register\n\n| Id | Title | Status | Folder |\n|---|---|---|---|\n| MW-001 | a | open | `x` |\n" \
           "| MW-002 | b | open | `y` |\n| MW-001 | a | closed | `x` |\n"
    assert register_duplicates(text) == ["MW-001"]
