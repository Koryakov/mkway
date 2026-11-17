"""Card MW-112 part (v) (ruling R284), layer core: the role files the engine ships (`engine/roles/lead.md`, `builder.md`,
`operator.md`). Read as text; nothing is imported from a test module. Synthetic checks over the shipped files."""
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
ROLES = REPO / "engine" / "roles"
BUDGET = {"lead": 40, "builder": 30, "operator": 30}  # the engine's constants, the same numbers as startline.ROLE_BUDGET
TAG = re.compile(r"^- \[([a-z0-9-]+)\] ", re.M)
if str(REPO / "engine") not in sys.path:
    sys.path.insert(0, str(REPO / "engine"))


def _lines(name):
    return [x for x in (ROLES / f"{name}.md").read_text(encoding="utf-8").splitlines() if x.strip()]


@pytest.mark.parametrize("name", ["lead", "builder", "operator"])
def test_a_shipped_role_file_is_inside_its_line_budget(name):
    """Catches: a role file that grows past its budget, so the always-on text grows without a limit (F26, H13)."""
    assert len(_lines(name)) <= BUDGET[name]


def test_the_engine_budget_constants_are_the_ruled_numbers():
    """Catches: a budget that moved from 40, 30 and 30 without a ruling."""
    import startline
    assert dict(startline.ROLE_BUDGET) == BUDGET


@pytest.mark.parametrize("name", ["lead", "builder", "operator"])
def test_every_line_of_a_role_file_is_one_tagged_rule(name):
    """Catches: a role line with no id tag, so the table can not point at it; the title line is the only other line."""
    body = _lines(name)[1:]
    assert all(TAG.match(x) for x in body)


@pytest.mark.parametrize("name", ["lead", "builder", "operator"])
def test_a_role_file_names_no_task_number_path_or_person(name):
    """Catches: a task trace in a shipped file: a card id, a decision id, a drive path or a ruling number."""
    text = (ROLES / f"{name}.md").read_text(encoding="utf-8")
    assert not re.search(r"\b[A-Z]{1,4}-?\d{2,}\b|[A-Za-z]:[\\/]|\\|\bR\d{2,}", text)


def test_every_instruction_row_has_a_line_in_the_role_file_its_comment_names():
    """Catches: R269c: an instruction row whose role-file line does not exist, so nothing replaces the hook for it."""
    import concept
    source = (REPO / "engine" / "concept.py").read_text(encoding="utf-8").splitlines()
    for reason, row in concept.REASONS.items():
        if row.kind_or_exit != "instruction":
            continue
        (line,) = [x for x in source if x.lstrip().startswith(f'"{reason}": Row(')]
        named = re.search(r"engine/roles/(lead|builder|operator)\.md", line)
        assert named, f"{reason}: the comment names no role file"
        assert f"[{reason}]" in (ROLES / f"{named.group(1)}.md").read_text(encoding="utf-8"), reason


def test_the_part_two_lines_exist_once_each_where_the_mapping_puts_them():
    """Catches: one of the generic lines the 7824 mapping gives to the role texts missing from the file that should carry it."""
    want = {"lead": ["route-once", "agent-brief", "pre-run-check", "triage", "minimal-model"],
            "builder": ["do-step-zero", "agent-brief"], "operator": ["route-once", "minimal-model", "practice-rules"]}
    for name, tags in want.items():
        assert [t for t in tags if t not in TAG.findall((ROLES / f"{name}.md").read_text(encoding="utf-8"))] == [], name
