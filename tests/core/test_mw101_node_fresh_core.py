"""Card MW-101 (decisions: R196, R253), layer core: `engine/core_node_fresh.py` decides from two texts of a test file and a node
name whether a verdict row is still fresh: the node's own source and the non-test code of its file (module level, fixtures,
helpers, imports, class members that are no test) must be equal; another test function may differ. No disk, no git. The
texts are synthetic."""
import ast
from pathlib import Path

import _engine  # noqa: F401  (puts the engine folder on the import path)
import core_node_fresh as core

CORE = Path(__file__).resolve().parents[2] / "engine" / "core_node_fresh.py"
FILE = "tests/test_k.py"
BASE = '''\
"""module doc"""
import os

import pytest
from pytest import fixture

LIMIT = 3


def helper():
    return LIMIT


@pytest.fixture
def box():
    return helper()


@pytest.fixture(scope="module")
def test_root():
    return os


@fixture
def test_bare():
    return 1


def test_x(box):
    """doc of x"""
    assert box == 3


@pytest.mark.parametrize("v", ["a", "b"])
def test_p(v):
    assert v


def test_y():
    assert True


async def test_a():
    assert True


class TestK(object):
    attr = 1

    def prep(self):
        return 1

    def test_x(self):
        assert self.prep() == 1

    def test_z(self):
        assert True


class TestM:
    def test_x(self):
        assert True
'''
TOP = f"{FILE}::test_x"
IN_K = f"{FILE}::TestK::test_x"


def swap(text: str, old: str, new: str) -> str:
    """`text` with `old` replaced once by `new`; the case itself fails when `old` is not in the text."""
    assert old in text, old
    return text.replace(old, new, 1)


def judge(new: str, node: str = TOP, old: str = BASE) -> tuple:
    verdict = core.decide(old, new, node)
    return verdict.fresh, verdict.kind


def test_equal_text_is_fresh():
    """Checks: the nearest allow of every stale row below, the same text twice is fresh."""
    assert judge(BASE) == (True, "")


def test_a_sibling_test_function_changed_is_fresh():
    """Checks: R253, a change in another test function of the file does not make the node stale."""
    assert judge(swap(BASE, "def test_y():\n    assert True", "def test_y():\n    assert 1 == 1")) == (True, "")


def test_the_node_body_changed_is_stale():
    """Catches: a node whose own assert was weakened still counted as read."""
    assert judge(swap(BASE, "assert box == 3", "assert box")) == (False, "node")


def test_the_node_decorator_changed_is_stale():
    """Catches: a node that gained a decorator (a skip, a mark) still counted as read."""
    mark = chr(64) + "pytest.mark.skip"
    assert judge(swap(BASE, "def test_x(box):", mark + chr(10) + "def test_x(box):")) == (False, "node")


def test_the_node_docstring_changed_is_stale():
    """Catches: a node whose docstring changed (the reader judged the old words) still counted as read."""
    assert judge(swap(BASE, '"""doc of x"""', '"""doc of x, new"""')) == (False, "node")


def test_an_in_file_fixture_changed_is_stale():
    """Catches: R253, a fixture the node uses changed and the row stayed fresh."""
    assert judge(swap(BASE, "return helper()", "return 5")) == (False, "code")


def test_an_in_file_helper_changed_is_stale():
    """Catches: a helper function of the file changed and the row stayed fresh."""
    assert judge(swap(BASE, "return LIMIT", "return LIMIT + 1")) == (False, "code")


def test_an_import_changed_is_stale():
    """Catches: an import of the file changed and the row stayed fresh."""
    assert judge(swap(BASE, "import os\n", "import os\nimport sys\n")) == (False, "code")


def test_a_module_constant_changed_is_stale():
    """Catches: a module constant changed and the row stayed fresh."""
    assert judge(swap(BASE, "LIMIT = 3", "LIMIT = 4")) == (False, "code")


def test_a_comment_between_statements_is_fresh():
    """Checks: the nearest allow of the stale code rows, a comment between two statements is no statement and changes nothing."""
    assert judge(swap(BASE, "LIMIT = 3\n", "LIMIT = 3\n# the limit\n")) == (True, "")


def test_a_blank_line_between_statements_is_fresh():
    """Checks: the nearest allow of the stale code rows, a blank line between two statements changes nothing."""
    assert judge(swap(BASE, "def helper():", "\n\ndef helper():")) == (True, "")


def test_a_sibling_method_of_the_class_changed_is_fresh():
    """Checks: a test method next to the node's method changed; the node's class members that are tests are not code."""
    assert judge(swap(BASE, "def test_z(self):\n        assert True", "def test_z(self):\n        assert 2"),
                 IN_K) == (True, "")


def test_a_non_test_method_of_the_class_changed_is_stale():
    """Catches: a helper method of the node's class changed and the row stayed fresh."""
    assert judge(swap(BASE, "def prep(self):\n        return 1", "def prep(self):\n        return 2"),
                 IN_K) == (False, "code")


def test_the_same_name_in_another_class_changed_is_fresh():
    """Checks: the node is found by its class; a test_x of another class is only a sibling test."""
    assert judge(swap(BASE, "class TestM:\n    def test_x(self):\n        assert True",
                      "class TestM:\n    def test_x(self):\n        assert 9"), IN_K) == (True, "")


def test_a_fixture_named_test_root_changed_is_stale():
    """Catches: a fixture whose name starts with test, in call form, taken for a test function and its change ignored."""
    assert judge(swap(BASE, "return os", "return None")) == (False, "code")


def test_a_fixture_named_test_bare_changed_is_stale():
    """Catches: a fixture whose name starts with test, with a bare decorator, taken for a test function."""
    assert judge(swap(BASE, "def test_bare():\n    return 1", "def test_bare():\n    return 2")) == (False, "code")


def test_a_comment_inside_a_fixture_is_stale():
    """Catches: strictness lost, a comment inside a kept statement is a change (text compare, as the node's own source)."""
    assert judge(swap(BASE, "def box():\n    return", "def box():\n    # a note\n    return")) == (False, "code")


def test_a_parametrized_node_with_a_sibling_changed_is_fresh():
    """Checks: test_p[a] is judged by test_p, so a change in test_y leaves it fresh."""
    assert judge(swap(BASE, "def test_y():\n    assert True", "def test_y():\n    assert 3"),
                 f"{FILE}::test_p[a]") == (True, "")


def test_a_parametrized_node_with_its_function_changed_is_stale():
    """Catches: the [params] part of the node name hiding the function from the compare."""
    assert judge(swap(BASE, "def test_p(v):\n    assert v", "def test_p(v):\n    assert not v"),
                 f"{FILE}::test_p[a]") == (False, "node")


def test_an_old_text_that_does_not_parse_is_stale():
    """Catches: an old text that cannot be read guessed as unchanged."""
    assert judge(BASE, old="def test_x(:\n") == (False, "unreadable")


def test_a_new_text_that_does_not_parse_is_stale():
    """Catches: a new text that cannot be read guessed as unchanged."""
    assert judge("def test_x(:\n") == (False, "unreadable")


def test_a_node_missing_in_the_new_text_is_stale():
    """Catches: a node that was removed or renamed guessed as unchanged."""
    assert judge(swap(BASE, "def test_x(box):", "def test_w(box):")) == (False, "missing")


def test_a_node_missing_in_the_old_text_is_stale():
    """Catches: a node that is new in the file (no old text of it) guessed as unchanged."""
    assert judge(BASE, old=swap(BASE, "def test_x(box):", "def test_w(box):")) == (False, "missing")


def test_a_top_level_node_is_not_the_method_of_a_class():
    """Checks: file::test_x is the top-level function; the method test_x of TestK changed and the top-level node is fresh."""
    assert judge(swap(BASE, "def test_x(self):\n        assert self.prep() == 1",
                      "def test_x(self):\n        assert self.prep() == 5")) == (True, "")


def test_a_class_header_changed_is_stale():
    """Catches: a changed base class of the node's class (it brings other members) still counted as read."""
    assert judge(swap(BASE, "class TestK(object):", "class TestK(Base):"), IN_K) == (False, "code")


def test_an_async_sibling_changed_is_fresh():
    """Checks: an async test function is a test function too, its change leaves the node fresh."""
    assert judge(swap(BASE, "async def test_a():\n    assert True", "async def test_a():\n    assert 7")) == (True, "")


def test_a_node_nested_deeper_than_one_class_is_stale():
    """Catches: a node path of a nested class, which the rule does not find, guessed as unchanged."""
    assert judge(BASE, f"{FILE}::TestK::Inner::test_x", old=BASE + "# trailing\n") == (False, "missing")


def test_the_core_imports_no_io_module():
    """Checks: the core imports only `ast`, `__future__` and typing; it calls no open or print."""
    tree = ast.parse(CORE.read_text(encoding="utf-8"))
    names = {a.name.partition(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    names |= {n.module.partition(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    calls = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert (names - {"__future__", "ast", "typing"}, calls & {"open", "print", "input", "exec", "eval"}) == (set(), set())
