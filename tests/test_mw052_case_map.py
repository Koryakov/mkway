"""Card MW-052: the case map proves the migration. Every old commit_files test is in `cards/MW-052-commit-core/case_map.md`
(a line `old test -> new test`, `old test -> dropped: doc`, or `# kept: old test - why`); the new tests exist; an old test
that was mapped is gone; a test that stays in an old module is a `kept` line, so nothing is left unmapped. The line
grammar is the one of MW-040 (`tests/test_meta_cards.py` reads the same file). The only meta-test of this card: the
ruling says documents are never evidence of behaviour."""
import ast

import pytest

from _engine import REPO
from core_red import parse_case_map

MAP = REPO / "cards" / "MW-052-commit-core" / "case_map.md"
OLD_MODULES = ("test_mw006_commit_files", "test_mw006_commit_content", "test_mw006_commit_message",
               "test_mw006_readme", "test_mw033_commit_gate", "test_mw034_staged_paths", "test_mw043_commit_takes",
               "test_mw021_commit", "test_mw053_orderer_commit", "test_mw058_amend_only")


def _plain(side):
    """The narrow rule of this card: the side starts `tests/`, names a `.py` file, and the name after `::` is an identifier."""
    file, _, name = side.rpartition("::")
    return side.startswith("tests/") and file.endswith(".py") and name.isidentifier()


def _tests_of(path):
    if not path.is_file():
        return set()
    return {n.name for n in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
            if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")}


def _lines():
    """({old: [new, ...]}, {old: 'doc'} dropped, [kept old], [lines that are no part of the grammar])."""
    mapped, dropped, kept, bad = {}, {}, [], []
    for entry in parse_case_map(MAP.read_text(encoding="utf-8")):
        text = entry.raw.strip()
        if entry.kind == "comment":
            if entry.kept_id is not None:
                kept.append(entry.kept_id)
            elif text.startswith(("# kept:", ">")):
                bad.append(text)
        elif entry.kind == "mapping":
            if _plain(entry.old) and _plain(entry.new):
                mapped.setdefault(entry.old, []).append(entry.new)
            else:
                bad.append(text)
        elif entry.kind == "dropped":
            if _plain(entry.old):
                dropped[entry.old] = entry.why
            else:
                bad.append(text)
        elif entry.kind == "malformed":
            bad.append(text)
    return mapped, dropped, kept, bad


def _kept_but_gone(kept):
    return [f"{old} is marked kept but is gone" for old in kept if old.split("::")[1] not in _tests_of(REPO / old.split("::")[0])]


def _mapped_but_present(olds, kept):
    return [f"{old} is mapped and must be removed" for old in olds
            if old not in kept and old.split("::")[1] in _tests_of(REPO / old.split("::")[0])]


def _new_but_missing(olds, kept, mapped):
    return [f"{new} does not exist" for old in olds if old not in kept for new in mapped.get(old, [])
            if not (REPO / new.split("::")[0]).is_file() or new.split("::")[1] not in _tests_of(REPO / new.split("::")[0])]


def _in_no_line(olds):
    return [f"tests/{module}.py::{name} is in no line of the case map" for module in OLD_MODULES
            for name in sorted(_tests_of(REPO / "tests" / f"{module}.py")) if f"tests/{module}.py::{name}" not in olds]


@pytest.mark.engine_repo  # reads the card of this repository
def test_every_old_case_has_a_new_home_or_is_dropped_or_kept_and_nothing_is_unmapped():
    """Checks: every old commit_files test is a mapped line with its old test gone and its new test present, a dropped line, or a kept line that still exists, so nothing is unmapped (MW-052)."""
    mapped, dropped, kept, bad = _lines()
    assert not bad, bad
    olds = [*mapped, *dropped, *kept]
    assert len(olds) >= 40
    assert len(olds) == len(set(olds)), "an old test is in two groups of the map"
    assert _kept_but_gone(kept) == []  # a kept test must still be in its module
    assert _mapped_but_present(olds, kept) == []  # a mapped or dropped old test must be removed
    assert _new_but_missing(olds, kept, mapped) == []  # the new home must exist
    assert _in_no_line(olds) == []  # nothing is left out of the case map


@pytest.mark.engine_repo
@pytest.mark.parametrize("module", [pytest.param(m, id=m) for m in OLD_MODULES])
def test_the_map_lists_the_old_modules_by_name(module):
    """Checks: the case map names each of the ten old commit_files modules by file name (MW-052)."""
    text = MAP.read_text(encoding="utf-8")
    assert f"tests/{module}.py" in text, module
