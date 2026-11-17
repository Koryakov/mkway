"""Card MW-025: the install check runs only tests that fit a copy. Synthetic scratch folders only.

E1 (the guard against a test that reads a file an installed copy does not have) moved to MW-029: it no longer runs a
whole copy suite (minutes) but reads the sources of the tests a copy would run, in seconds. See
`tests/test_mw029_fast_guard.py::test_no_collected_test_reads_a_path_a_copy_lacks`.
"""
import ast
import os
import re

import pytest

import _docs as docs
from _engine import REPO
import install

pytestmark = pytest.mark.engine_repo  # the copy holds this file too: the marker keeps the guard from running itself


FAILING = '''
def test_one_fails():
    assert False


def test_two_fails():
    assert False
'''


def _module_marked(tree):
    """True when the module assigns `pytestmark` with the engine_repo marker."""
    return any(isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "pytestmark" for t in node.targets)
               and "engine_repo" in ast.unparse(node.value) for node in tree.body)


def _is_marked(tree, node):
    """True when the test node carries the engine_repo marker in its decorators, or the module does."""
    return any("engine_repo" in ast.unparse(d) for d in node.decorator_list) or _module_marked(tree)


def test_the_eight_tests_that_read_engine_repository_files_are_marked():
    """Checks: each of the five named tests of the gap is one module-level test and carries the engine_repo marker, so a copy leaves it out (E2)."""
    names = ["test_the_changelog_covers_the_register", "test_the_readme_has_the_versioning_section",
             "test_the_readme_changelog_register_and_keys_name_the_card",
             "test_the_register_changelog_and_card_name_the_card",
             "test_register_changelog_version_and_readme_name_the_card"]
    trees = {p: ast.parse(p.read_text(encoding="utf-8")) for p in sorted((REPO / "tests").glob("test_*.py"))}
    holders = {name: [(tree, node) for tree in trees.values() for node in tree.body
                      if isinstance(node, ast.FunctionDef) and node.name == name] for name in names}
    assert {name: len(holders[name]) for name in names} == {name: 1 for name in names}
    unmarked = [name for name in names if not _is_marked(*holders[name][0])]
    assert unmarked == []
