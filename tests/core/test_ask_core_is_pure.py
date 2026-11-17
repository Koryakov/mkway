"""Card MW-065: `engine/core_ask.py` is pure by construction. A test fails if it imports `os`, `pathlib`, `subprocess`,
`time`, any other standard-library module that reaches the disk, a process or the environment, or one of the engine's I/O
modules; and if it calls `open`, `print`, `input` or reads the clock. The standard-library `datetime` may be imported to
read a time written in a file (`fromisoformat`), never to read the clock. The one engine module it may import is
`helpers` (the reader's pure functions on text)."""
import ast
from pathlib import Path

import pytest

import _engine  # noqa: F401

CORE = Path(__file__).resolve().parents[2] / "engine" / "core_ask.py"
ALLOWED = {"__future__", "re", "dataclasses", "typing", "datetime", "helpers"}
BANNED_NAMES = {"os", "pathlib", "subprocess", "time", "shutil", "sys", "json", "io", "tempfile", "glob", "socket",
                "logging", "runner", "register", "records", "cardtool", "profiles", "logs", "gate", "asks", "outbox",
                "search", "gate_owner_ask", "gate_search", "gate_outbox", "ledger", "locks", "leads", "sessions",
                "rules", "agents", "deliverables"}
BANNED_CALLS = {"open", "print", "input", "exec", "eval", "__import__", "compile"}
BANNED_ATTRS = {"now", "today", "utcnow", "read_text", "write_text", "read_bytes", "write_bytes", "is_file", "is_dir",
                "exists", "stat", "resolve", "getenv", "environ", "perf_counter", "monotonic", "iterdir", "rglob"}


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


def test_core_ask_imports_only_the_pure_modules():
    """Catches: a core_ask.py import outside the pure list, or a banned module, such as the disk, process or engine I/O modules."""
    modules, _calls, _attrs = _scan(CORE.read_text(encoding="utf-8"))
    assert modules <= ALLOWED, f"core_ask.py imports {sorted(modules - ALLOWED)}"
    assert not modules & BANNED_NAMES


def test_core_ask_calls_no_io_function_and_reads_no_clock():
    """Catches: a call to open, print or input, or a clock or disk attribute, in core_ask.py."""
    _modules, calls, attrs = _scan(CORE.read_text(encoding="utf-8"))
    assert not calls & BANNED_CALLS, sorted(calls & BANNED_CALLS)
    assert not attrs & BANNED_ATTRS, sorted(attrs & BANNED_ATTRS)


@pytest.mark.parametrize("source, what", [
    ("import os\n", "os"), ("from pathlib import Path\n", "pathlib"), ("import subprocess\n", "subprocess"),
    ("import time\n", "time"), ("import asks\n", "asks"), ("from outbox import sha_of\n", "outbox"),
    ("def f():\n    import os\n", "os")])
def test_the_scan_catches_each_banned_import(source, what):
    """Catches: a scan that misses one of these banned imports, whether it is at module level or nested in a function."""
    modules, _calls, _attrs = _scan(source)
    assert what in modules
    assert not modules <= ALLOWED


def test_the_scan_catches_a_file_read_and_a_clock_read():
    """Catches: a scan that misses a file read or a clock read in a source."""
    _m, calls, attrs = _scan("x = open('f')\ny = datetime.now()\nz = p.read_text()\nw = p.exists()\n")
    assert "open" in calls
    assert {"now", "read_text", "exists"} <= attrs
