"""Card MW-065: the case map proves the migration of the ask family. Every case of the six old gate modules is either a
line of `cards/MW-065-ask-core/case_map.md` (the old test is gone and its new home exists), or one of the wiring cases
that stay (the one deny and the switch of a gate through the real manifest). Nothing is left unaccounted for. The only
test that reads the card (the ruling: documents are never evidence of behaviour)."""
import ast

import pytest

from _engine import REPO
from core_red import parse_case_map

MAP = REPO / "cards" / "MW-065-ask-core" / "case_map.md"
OLD_MODULES = ("test_mw007_edit_gate", "test_mw007_stop_gate", "test_mw008_gate", "test_mw008_ask", "test_mw014_gate",
               "test_mw019_gate")
STAYS = {
    "tests/test_mw007_edit_gate.py::test_the_edit_gate_runs_in_the_edit_group_and_has_a_switch",
    "tests/test_mw007_stop_gate.py::test_the_stop_gate_runs_in_the_stop_group_and_has_a_switch",
    "tests/test_mw008_gate.py::test_the_search_gate_runs_in_the_edit_group_and_has_a_switch",
    "tests/test_mw014_gate.py::test_the_dispatcher_refuses_the_pop_up_tool_before_the_search_gate",
    "tests/test_mw019_gate.py::test_the_manifest_entries_of_the_outbox_check",
    "tests/test_mw019_gate.py::test_the_dispatcher_refuses_a_stale_check_write",
}


def _tests_of(path):
    if not path.is_file():
        return set()
    return {n.name for n in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
            if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")}


def _rows():
    """The mapping lines of the card's case map, read by core_red's parser (R224): (old side, new side)."""
    return [(e.old, e.new) for e in parse_case_map(MAP.read_text(encoding="utf-8")) if e.kind == "mapping"]


def _mapped_but_present(rows):
    return [f"{old} is mapped and must be removed" for old, _new in rows
            if old.split("::")[1] in _tests_of(REPO / old.split("::")[0])]


def _new_but_missing(rows):
    return [f"{new} does not exist" for _old, new in rows if new.split("::")[1] not in _tests_of(REPO / new.split("::")[0])]


def _stays_but_gone():
    return [f"{old} stays and is gone" for old in sorted(STAYS) if old.split("::")[1] not in _tests_of(REPO / old.split("::")[0])]


def _in_no_line(accounted):
    return [f"tests/{module}.py::{name} is in no line of the case map" for module in OLD_MODULES
            for name in sorted(_tests_of(REPO / "tests" / f"{module}.py")) if f"tests/{module}.py::{name}" not in accounted]


@pytest.mark.engine_repo  # reads the card of this repository
def test_every_old_case_is_mapped_and_gone_or_is_a_wiring_case_that_stays():
    """Checks: every old case of the six gate modules is a mapping line whose old test is gone and new test exists, or one of the wiring cases that stay (MW-065)."""
    rows = _rows()
    assert len(rows) == 44
    olds = [old for old, _new in rows]
    assert len(olds) == len(set(olds)), "an old test is mapped twice"
    assert _mapped_but_present(rows) == []  # a mapped old test must be removed
    assert _new_but_missing(rows) == []  # the new home must exist
    assert _stays_but_gone() == []  # a wiring case that stays must still be there
    assert _in_no_line(set(olds) | STAYS) == []  # nothing is left out of the case map


@pytest.mark.engine_repo
@pytest.mark.parametrize("module", [pytest.param("test_mw008_ask", id="test_mw008_ask")])
def test_a_module_with_no_case_left_holds_one_docstring_line(module):
    """Checks: a module whose every case moved holds one docstring line that names the card and the map."""
    text = (REPO / "tests" / f"{module}.py").read_text(encoding="utf-8")
    assert text.strip() == '"""Moved by MW-065; see cards/MW-065-ask-core/case_map.md"""', module
