"""Card MW-064: `engine/core_delete.py` is pure by construction. A test fails if it imports `os`, `pathlib`, `subprocess`,
`time`, `datetime`, any other standard-library module that reaches the disk, a process, the environment or the clock, or
one of the engine's I/O modules; and if it calls `open`, `print`, `input` or reads the clock. The one engine module it
may import is `helpers` (the reader's pure functions on text). The run-time proof is the guard of
`test_delete_decide.py`."""
import ast
from pathlib import Path

import pytest

import _engine  # noqa: F401

CORE = Path(__file__).resolve().parents[2] / "engine" / "core_delete.py"
ALLOWED = {"__future__", "re", "ast", "calendar", "dataclasses", "typing", "helpers"}
BANNED_NAMES = {"os", "pathlib", "subprocess", "time", "datetime", "shutil", "sys", "json", "io", "tempfile", "glob",
                "socket", "logging", "runner", "register", "records", "cardtool", "profiles", "logs", "gate",
                "gate_delete", "trash", "locks", "ledger", "leads", "outbox", "sessions", "rules"}
BANNED_CALLS = {"open", "print", "input", "exec", "eval", "__import__", "compile"}
BANNED_ATTRS = {"now", "today", "utcnow", "read_text", "write_text", "read_bytes", "write_bytes", "is_file", "is_dir",
                "exists", "lexists", "stat", "lstat", "resolve", "getenv", "environ", "perf_counter", "monotonic",
                "listdir", "mkdir", "copytree", "copy2", "rmtree", "remove", "unlink"}


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
    """Checks: the core imports no disk, process, clock or engine I/O module, only the allowed pure ones."""
    # Catches: a core that imports os, pathlib, subprocess, time, datetime, shutil or an I/O module, so a decision could
    # read the disk, run git or read the clock
    modules, _calls, _attrs = _scan(CORE.read_text(encoding="utf-8"))
    assert (sorted(modules - ALLOWED), sorted(modules & BANNED_NAMES)) == ([], [])


def test_the_scan_read_the_real_core_module():
    """Checks: the scan reads the real core module, which imports helpers and dataclasses."""
    modules, _calls, _attrs = _scan(CORE.read_text(encoding="utf-8"))
    assert {"helpers", "dataclasses"} <= modules


def test_core_calls_no_io_function():
    """Checks: the core calls no open, print, input, exec or eval."""
    _modules, calls, _attrs = _scan(CORE.read_text(encoding="utf-8"))
    assert sorted(calls & BANNED_CALLS) == []


def test_core_reads_no_clock_and_no_file_attribute():
    """Checks: the core reads no clock, environment or file through a method (now, read_text, exists, stat, environ)."""
    _modules, _calls, attrs = _scan(CORE.read_text(encoding="utf-8"))
    assert sorted(attrs & BANNED_ATTRS) == []


@pytest.mark.parametrize("source, what", [
    ("import os\n", "os"), ("from pathlib import Path\n", "pathlib"), ("import subprocess\n", "subprocess"),
    ("import time\n", "time"), ("import datetime\n", "datetime"), ("import runner\n", "runner"),
    ("from trash import backup\n", "trash"), ("def f():\n    import os\n", "os")])
def test_the_scan_catches_each_banned_import(source, what):
    """Catches: a scan that lets a banned import through (the scan itself can fail)."""
    modules, _calls, _attrs = _scan(source)
    assert what in modules
    assert not modules <= ALLOWED


@pytest.mark.parametrize("source, kind, name", [
    ("x = open('f')\n", "call", "open"), ("y = datetime.now()\n", "attr", "now"),
    ("z = p.read_text()\n", "attr", "read_text"), ("q = os.path.lexists(p)\n", "attr", "lexists")])
def test_the_scan_catches_a_file_read_and_a_clock_read(source, kind, name):
    """Catches: a scan that lets a file read or a clock read through (the scan itself can fail)."""
    _modules, calls, attrs = _scan(source)
    assert name in (calls if kind == "call" else attrs)
