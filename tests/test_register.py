"""The engine's own card register (card MW-001, row E10)."""
import re

import pytest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
REGISTER = REPO / "cards" / "REGISTER.md"
HEADER = ["Id", "Title", "Status", "Folder"]
CARD_ID = re.compile(r"^MW-\d{3}$")


def _rows(text):
    rows = []
    for line in text.splitlines():
        if line.startswith("|") and not set(line) <= set("|-: "):
            rows.append([c.strip() for c in line.strip().strip("|").split("|")])
    return rows


def _row_problems(card_id, title, status, folder):
    """The failed conditions of one register row, each named with its card id; an empty list when the row is sound."""
    folder = folder.strip("`")
    problems = []
    if not CARD_ID.match(card_id):
        problems.append(f"{card_id}: id not in the MW form")
    if not title:
        problems.append(f"{card_id}: no title")
    if not status:
        problems.append(f"{card_id}: no status")
    if not (REPO / folder / "CARD.md").is_file():
        problems.append(f"{card_id}: no CARD.md in {folder}")
    if not Path(folder).name.startswith(card_id + "-"):
        problems.append(f"{card_id}: folder {folder} is not named by the id")
    return problems


@pytest.mark.engine_repo  # MW-002 (C14): needs the engine repository itself
def test_register_row_points_to_card_folder():
    """Checks: the register is an Id/Title/Status/Folder table and each row's folder holds its CARD.md (E10)."""
    rows = _rows(REGISTER.read_text(encoding="utf-8"))
    assert rows[0] == HEADER
    body = rows[1:]
    assert body, "the register has no card"
    bad = [problem for card_id, title, status, folder in body
           for problem in _row_problems(card_id, title, status, folder)]
    assert not bad, bad


TEMPLATE = REPO / "cards" / "_TEMPLATE" / "CARD.md"
# R12 (2026-11-09): the engine ships one card form, the one-page form of the source (Goal, Acceptance examples, Log).
SECTIONS = ["1. Goal", "Acceptance examples", "8. Log"]
STATUS_LABELS = ["**Appetite**", "**Status**", "**Created / updated**", "**Waiting for**", "**Form**",
                 "**Decisions**", "**Canon**", "**Paths**"]
COLUMNS = {"Acceptance examples": [["#", "Item", "Was", "Must be", "Test"]],
           "8. Log": [["Date", "Step", "Commit", "Result"]]}
MAX_LINES_BEFORE_LOG = 40  # one page, as in the source form
# Cards written before R12 keep the form they were written in (decision C8); they are history, not checked here.
HISTORY_CARDS = {("MW-001", "cards/MW-001-engine-skeleton")}


def _cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _shape(text):
    """(labels of the status table before the first section, [(section, [table header rows])]).
    Tables under a ### subheading are extra and not part of the shape."""
    labels, sections, current, sub, prev = [], [], None, False, False
    for line in text.splitlines():
        if line.startswith("## "):
            current = (line[3:].strip(), [])
            sections.append(current)
            sub = prev = False
            continue
        if line.startswith("### "):
            sub = True
            continue
        is_row = line.startswith("|")
        if current is None and is_row and line.lstrip("| ").startswith("**"):
            labels.append(_cells(line)[0])
        elif is_row and not prev and current is not None and not sub:
            current[1].append(_cells(line))
        prev = is_row
    return labels, sections


@pytest.mark.engine_repo  # MW-002 (C14): needs the engine repository itself
def test_card_has_template_sections():
    """Checks: the cleaned template is the one-page form, and every card after R12 has the same shape (E11)."""
    # its header labels, its three sections in order, their table columns, at most one page before the log
    text = TEMPLATE.read_text(encoding="utf-8")
    labels, sections = _shape(text)
    assert labels == STATUS_LABELS
    assert [s for s, _ in sections] == SECTIONS
    assert {s: t for s, t in sections if t} == COLUMNS
    headings = [l for l in text.splitlines() if l.startswith("#")]
    assert headings[1:] == ["## " + s for s in SECTIONS], headings
    assert not any(col in text for col in ("Store write", "Owner yes"))
    before_log = text.split("## 8. Log")[0]
    assert len(before_log.splitlines()) <= MAX_LINES_BEFORE_LOG
    rows = _rows(REGISTER.read_text(encoding="utf-8"))[1:]
    checked = [(card_id, folder.strip("`")) for card_id, _title, _status, folder in rows
               if (card_id, folder.strip("`")) not in HISTORY_CARDS]
    mismatch = [card_id for card_id, folder in checked
                if _shape((REPO / folder / "CARD.md").read_text(encoding="utf-8")) != (labels, sections)]
    assert not mismatch, mismatch
