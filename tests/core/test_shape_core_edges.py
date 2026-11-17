"""Card MW-073 (decision: R177), layer core: the edges of the shape rules the first table does not reach (aliased imports,
a dynamic import of a test module, containers on the left of `==`). Synthetic sources only."""
import pytest

import _engine  # noqa: F401
from core_shape import Facts, Source, decide

PATH = "tests/test_x.py"
CORE_PATH = "tests/core/test_x.py"
DOC = '    """Checks: one thing."""\n'


def _test(body, *, args=""):
    return f"def test_a({args}):\n{DOC}{body}"


def _breaks(source, path=PATH):
    verdict = decide(Facts((Source(path, source),)))
    return [(b.function, b.rule) for b in verdict.breaches]


@pytest.mark.parametrize("head, body", [
    ("from time import sleep\n\n\n", "    sleep(1)\n    assert 1 == 1\n"),
    ("from socket import create_connection\n\n\n", "    create_connection(1)\n    assert 1 == 1\n"),
    ("import socket as net\n\n\n", "    net.socket()\n    assert 1 == 1\n"),
    ("", "    import socket\n    assert socket\n"),
], ids=["from-time", "from-socket", "alias", "import-in-body"])
def test_an_aliased_or_imported_network_or_sleep_name_is_refused_as_s6(head, body):
    """Catches: a sleep or a network call hidden behind an import alias."""
    assert _breaks(head + _test(body)) == [("test_a", "S6")]


def test_a_dynamic_import_of_a_test_module_is_refused_as_s5():
    """Catches: a test that reaches another test module through import_module instead of an import line."""
    assert _breaks(_test("    mod = import_module('test_other')\n    assert mod\n")) == [("test_a", "S5")]


@pytest.mark.parametrize("body", [
    "    assert decide(1) == ','.join(['a'])\n",
    "    assert (1, 2) == decide(1)\n",
    "    assert {'a': 1} == decide(1)\n",
    "    assert -1 == decide(1)\n",
], ids=["join-of-a-constant", "tuple-left", "dict-left", "negative-left"])
def test_a_core_test_whose_expected_side_is_a_pure_literal_or_a_constant_join_is_allowed(body):
    """Checks: an expected value written out as a literal, on either side, is independent of the code."""
    assert _breaks(_test(body), CORE_PATH) == []


@pytest.mark.parametrize("body", [
    "    assert (x, 1) == decide(1)\n",
    "    assert decide(1) == {'a': decide(2)}\n",
], ids=["tuple-with-a-name", "dict-with-a-call"])
def test_a_core_test_whose_expected_side_holds_a_name_or_a_call_is_refused_as_s7(body):
    """Catches: an expected container that is only partly literal, so part of it is the code's own answer."""
    assert _breaks(_test(body, args="x"), CORE_PATH) == [("test_a", "S7")]
