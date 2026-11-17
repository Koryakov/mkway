"""Card MW-052: `engine/core.py` is pure by construction. A test fails if it imports `os`, `pathlib`, `subprocess`, `time`,
`datetime`, any other standard-library module that reaches the disk, a process, the environment or the clock, or one of
the engine's I/O modules; and if it calls `open`, `print`, `input` or reads the clock. The one engine module it may
import is `helpers` (the reader's pure functions on text). Runtime proof is the guard of `test_commit_decide.py`."""
import ast
from pathlib import Path

import pytest

import _engine  # noqa: F401
from _markers import marks_for
from _mw098_addopts import drop_allowed_pair

CORE = Path(__file__).resolve().parents[2] / "engine" / "core.py"
ALLOWED = {"__future__", "re", "dataclasses", "typing", "helpers"}
BANNED_NAMES = {"os", "pathlib", "subprocess", "time", "datetime", "shutil", "sys", "json", "io", "tempfile", "glob",
                "socket", "logging", "runner", "register", "records", "cardtool", "profiles", "logs", "gate",
                "gate_commit", "gate_commit_tests", "ledger", "locks", "leads", "outbox", "sessions", "rules"}
BANNED_CALLS = {"open", "print", "input", "exec", "eval", "__import__", "compile"}
BANNED_ATTRS = {"now", "today", "utcnow", "read_text", "write_text", "read_bytes", "write_bytes", "is_file", "is_dir",
                "exists", "stat", "resolve", "getenv", "environ", "perf_counter", "monotonic"}


def _scan(source: str):
    """(imported top-level module names, called names, attribute names) of a module's source."""
    tree = ast.parse(source)
    modules, calls, attrs = set(), set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            modules.add((node.module or "").split(".")[0])
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            calls.add(node.func.id)
        elif isinstance(node, ast.Attribute):
            attrs.add(node.attr)
    return modules, calls, attrs


def test_core_imports_only_the_pure_modules():
    """Catches: an import in engine/core.py of a module that reaches the disk, a process, the environment or the clock."""
    modules, _calls, _attrs = _scan(CORE.read_text(encoding="utf-8"))
    assert modules <= ALLOWED, f"core.py imports {sorted(modules - ALLOWED)}"
    assert not modules & BANNED_NAMES


def test_core_calls_no_io_function_and_reads_no_clock():
    """Catches: a call in engine/core.py of open, print or input, or a read of the clock or the disk."""
    _modules, calls, attrs = _scan(CORE.read_text(encoding="utf-8"))
    assert not calls & BANNED_CALLS, sorted(calls & BANNED_CALLS)
    assert not attrs & BANNED_ATTRS, sorted(attrs & BANNED_ATTRS)


@pytest.mark.parametrize("source, what", [
    ("import os\n", "os"), ("from pathlib import Path\n", "pathlib"), ("import subprocess\n", "subprocess"),
    ("import time\n", "time"), ("import datetime\n", "datetime"), ("import runner\n", "runner"),
    ("from register import find\n", "register"), ("def f():\n    import os\n", "os")])
def test_the_scan_catches_each_banned_import(source, what):
    """Checks: the scan catches each of these banned imports, so it can fail."""
    modules, _calls, _attrs = _scan(source)
    assert what in modules
    assert not modules <= ALLOWED


def test_the_scan_catches_a_file_read_and_a_clock_read():
    """Checks: the scan sees a file read and a clock read in a source."""
    _m, calls, attrs = _scan("x = open('f')\ny = datetime.now()\nz = p.read_text()\n")
    assert "open" in calls
    assert {"now", "read_text"} <= attrs


def test_the_markers_are_registered(pytestconfig):
    """Catches: a marker pytest does not know, which a strict run would reject. The ruling: e2e and shell are registered markers."""
    registered = {line.split(":")[0].strip() for line in pytestconfig.getini("markers")}
    assert {"e2e", "shell"} <= registered


PLACES = [("tests/test_e2e_gates.py", {"e2e"}), ("tests/test_e2e.py", {"e2e"}),
          ("tests/test_mw030_live_install.py", {"e2e"}), ("tests/test_mw038_real_shape.py", {"e2e"}),
          ("tests/test_mw038_guard.py", {"e2e"}), ("tests/shell/test_commit_facts.py", {"shell"}),
          ("tests/core/test_commit_decide.py", set()), ("tests/test_gate.py", set())]
PLACE_IDS = ["e2e_gate_rows", "e2e_plain", "e2e_live_install", "e2e_real_shape", "e2e_real_shape_guard", "shell_layer",
             "core_layer", "an_ordinary_test"]  # ids hold no file name: a marker selection prints them


@pytest.mark.parametrize("path, marks", PLACES, ids=PLACE_IDS)
def test_the_markers_are_assigned_by_the_place_of_the_file(path, marks):
    """Catches: a test of the wrong layer that is run, or left out, with its layer. The ruling: e2e (test_e2e*.py, test_mw030*, test_mw038*) and shell (tests/shell) by place."""
    assert marks_for(path) == marks


def test_the_default_run_excludes_nothing(pytestconfig):
    """Catches: a layer silently left out of the default run. The ruling (decision R175): the default run excludes no layer; addopts allows exactly one marker expression, not perf, or none; any other -m expression fails."""
    tokens = list(pytestconfig.getini("addopts"))
    rest = drop_allowed_pair(tokens)
    assert "-m" not in rest
    assert "not e2e" not in " ".join(tokens)
