"""Card MW-063: `engine/core_lock.py` is pure by construction. A test fails if it imports `os`, `pathlib`, `subprocess`,
`time`, `datetime`, any other standard-library module that reaches the disk, a process, the environment or the clock,
or one of the engine's I/O modules; or if it calls `open`, `print`, `input`, or reads the clock. The one engine module it
may import is `helpers` (the reader's pure functions on text). The scan below reads the source with `ast`."""
import ast
from pathlib import Path

import pytest

import _engine  # noqa: F401

CORE = Path(__file__).resolve().parents[2] / "engine" / "core_lock.py"
ALLOWED = {"__future__", "re", "dataclasses", "typing", "helpers"}
BANNED_CALLS = {"open", "print", "input", "exec", "eval", "__import__", "compile"}
BANNED_ATTRS = {"now", "today", "utcnow", "read_text", "write_text", "read_bytes", "write_bytes", "is_file", "is_dir",
                "exists", "stat", "resolve", "getenv", "environ", "perf_counter", "monotonic"}


def scan(source: str):
    """(imported top-level module names, called names, attribute names) of a module's source."""
    modules, calls, attrs = set(), set(), set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            modules.add((node.module or "").split(".")[0])
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            calls.add(node.func.id)
        elif isinstance(node, ast.Attribute):
            attrs.add(node.attr)
    return modules, calls, attrs


def test_the_core_imports_only_pure_modules():
    """Catches: an I/O module (os, pathlib, subprocess, time, datetime, an engine reader) imported into the decision."""
    modules, _calls, _attrs = scan(CORE.read_text(encoding="utf-8"))
    assert modules - ALLOWED == set()


def test_the_core_calls_no_io_function():
    """Catches: a file open, a print or an eval inside the decision."""
    _modules, calls, _attrs = scan(CORE.read_text(encoding="utf-8"))
    assert calls & BANNED_CALLS == set()


def test_the_core_reads_no_clock_file_or_environment():
    """Catches: a clock, file or environment read hidden behind a method call."""
    _modules, _calls, attrs = scan(CORE.read_text(encoding="utf-8"))
    assert attrs & BANNED_ATTRS == set()


@pytest.mark.parametrize("source", [
    pytest.param("import os\n", id="os"),
    pytest.param("from pathlib import Path\n", id="pathlib"),
    pytest.param("import subprocess\n", id="subprocess"),
    pytest.param("import time\n", id="time"),
    pytest.param("import datetime\n", id="datetime"),
    pytest.param("import runner\n", id="runner"),
    pytest.param("from register import find\n", id="register"),
    pytest.param("def f():\n    import os\n", id="import-inside-a-function"),
])
def test_the_scan_catches_a_banned_import(source):
    """Catches: a scan that cannot fail, so an I/O import would pass the purity check."""
    modules, _calls, _attrs = scan(source)
    assert not modules <= ALLOWED


@pytest.mark.parametrize("source, found", [
    pytest.param("x = open('f')\n", "open", id="file-open"),
    pytest.param("y = datetime.now()\n", "now", id="clock-read"),
    pytest.param("z = p.read_text()\n", "read_text", id="text-read"),
])
def test_the_scan_catches_an_io_call_and_a_clock_read(source, found):
    """Catches: a scan that misses a call or attribute that reaches the disk or the clock."""
    _modules, calls, attrs = scan(source)
    assert found in (calls | attrs)
