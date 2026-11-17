"""Card MW-080: `engine/core_verdict_add.py` is pure by construction. A test fails if it imports `os`, `pathlib`,
`subprocess`, `time`, `datetime`, any other module that reaches the disk, a process, the environment or the clock, or one of
the engine's I/O modules; or if it calls `open`, `print`, `input` or reads the clock. The scan reads the source with `ast`."""
import ast
from pathlib import Path

import _engine  # noqa: F401

CORE = Path(__file__).resolve().parents[2] / "engine" / "core_verdict_add.py"
ALLOWED = {"__future__", "re", "dataclasses", "typing"}
BANNED_CALLS = {"open", "print", "input", "exec", "eval", "__import__", "compile"}
BANNED_ATTRS = {"now", "today", "utcnow", "read_text", "write_text", "read_bytes", "write_bytes", "is_file", "is_dir",
                "exists", "stat", "resolve", "getenv", "environ", "perf_counter", "monotonic"}


def scan(source: str):
    """(imported top-level module names, called names, attribute names) of a module's source."""
    modules, calls, attrs = set(), set(), set()
    for found in ast.walk(ast.parse(source)):
        if isinstance(found, ast.Import):
            modules |= {alias.name.split(".")[0] for alias in found.names}
        elif isinstance(found, ast.ImportFrom):
            modules.add((found.module or "").split(".")[0])
        elif isinstance(found, ast.Call) and isinstance(found.func, ast.Name):
            calls.add(found.func.id)
        elif isinstance(found, ast.Attribute):
            attrs.add(found.attr)
    return modules, calls, attrs


def test_the_verdict_add_core_imports_only_pure_modules():
    """Catches: an I/O module (os, pathlib, subprocess, time, datetime, an engine reader) imported into the decision."""
    modules, _calls, _attrs = scan(CORE.read_text(encoding="utf-8"))
    assert modules - ALLOWED == set()


def test_the_verdict_add_core_calls_no_io_function():
    """Catches: the decision reading a file, printing, or asking the clock."""
    _modules, calls, attrs = scan(CORE.read_text(encoding="utf-8"))
    assert (calls & BANNED_CALLS) | (attrs & BANNED_ATTRS) == set()
