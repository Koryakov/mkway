"""Card MW-064: the case map proves the migration of the delete family. Every old test of the six `test_mw009_*` modules
is a line of `cards/MW-064-delete-core/case_map.md` (`old -> new`, or `old -> dropped: doc` / `dropped: T<n> ...`) or a
`# kept: old (why)` line; the new tests exist; a mapped old test is gone; a kept old test is still there, so nothing is
left unmapped. A module whose every case moved holds one docstring line. The meta test `test_meta_cards.py` checks the
line form and the right sides; this one checks the left sides."""
import ast
import re

import pytest

from _engine import REPO

MAP = REPO / "cards" / "MW-064-delete-core" / "case_map.md"
OLD_MODULES = ("test_mw009_reader", "test_mw009_git", "test_mw009_backup", "test_mw009_commands", "test_mw009_keys",
               "test_mw009_readme")
LINE = re.compile(r"^(tests/\S+\.py::\w+) -> (tests/\S+\.py::\w+|dropped: .+)$", re.M)
KEPT = re.compile(r"^# kept: (tests/\S+\.py::\w+) \((.+)\)$", re.M)
REASON = re.compile(r"^dropped: (doc|T[1-8]\b.+)$")
MOVED = '"""Moved by MW-064; see cards/MW-064-delete-core/case_map.md"""'


def _tests_of(path):
    if not path.is_file():
        return set()
    return {n.name for n in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
            if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")}


def _line_problems(lines):
    problems = []
    for old, new in lines:
        path, name = old.split("::")
        if name in _tests_of(REPO / path):
            problems.append(f"{old} is mapped and must be removed from its module")
        if new.startswith("dropped:"):
            if not REASON.match(new):
                problems.append(f"{old}: a dropped case names `doc` or the criterion T1..T8: {new}")
            continue
        new_path, new_name = new.split("::")
        if not (REPO / new_path).is_file():
            problems.append(new)
        elif new_name not in _tests_of(REPO / new_path):
            problems.append(f"{new} does not exist")
    return problems


def _kept_problems(kept):
    problems = []
    for old, why in kept:
        path, name = old.split("::")
        if name not in _tests_of(REPO / path):
            problems.append(f"{old} is marked kept but is gone")
        if not why.strip():
            problems.append(f"{old}: no reason")
    return problems


def _unmapped(mapped):
    return [f"tests/{module}.py::{name} is in no line of the case map"
            for module in OLD_MODULES for name in _tests_of(REPO / "tests" / f"{module}.py")
            if f"tests/{module}.py::{name}" not in mapped]


def _moved_problems(kept_files):
    problems = []
    for module in OLD_MODULES:
        path = REPO / "tests" / f"{module}.py"
        if not path.is_file():
            problems.append(f"{module} must not be deleted")
        elif f"tests/{module}.py" not in kept_files and path.read_text(encoding="utf-8").strip() != MOVED:
            problems.append(module)
    return problems


@pytest.mark.engine_repo  # reads the card of this repository
def test_every_old_case_has_a_new_home_or_a_dropped_reason_or_stays_and_nothing_is_unmapped():
    """Checks: an old case is never lost, mapped twice, or left without a new home, a kept reason or a dropped reason, against the old and new modules."""
    text = MAP.read_text(encoding="utf-8")
    lines, kept = LINE.findall(text), KEPT.findall(text)
    assert len(lines) + len(kept) >= 30
    olds = [old for old, _new in lines] + [old for old, _why in kept]
    assert len(olds) == len(set(olds)), "an old test is mapped twice"
    assert _line_problems(lines) == []
    assert _kept_problems(kept) == []
    assert _unmapped(set(olds)) == []


@pytest.mark.engine_repo
def test_a_module_whose_every_case_moved_is_one_docstring_line():
    """Checks: the task's rule, the module is replaced by `Moved by MW-064; see cards/MW-064-*/case_map.md`, never deleted."""
    text = MAP.read_text(encoding="utf-8")
    kept_files = {old.split("::")[0] for old, _why in KEPT.findall(text)}
    assert _moved_problems(kept_files) == []
