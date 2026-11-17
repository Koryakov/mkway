"""Card MW-078: `engine/core_wake.py` is pure by construction. A test fails if it imports `os`, `pathlib`, `subprocess`,
`time`, `datetime`, `json`, any other standard-library module that reaches the disk, a process, the environment or the
clock, or one of the engine's I/O modules; and if it calls `open`, `print`, `input` or reads the clock. It imports no
engine module at all."""
import ast
from pathlib import Path

import _engine  # noqa: F401

CORE = Path(__file__).resolve().parents[2] / "engine" / "core_wake.py"
ALLOWED = {"__future__", "dataclasses", "typing"}
BANNED_CALLS = {"open", "print", "input", "exec", "eval", "__import__", "compile"}
BANNED_ATTRS = {"datetime.now", "datetime.today", "datetime.utcnow", "date.today", "time.time", "read_text", "write_text", "read_bytes", "write_bytes", "is_file", "is_dir",
                "exists", "stat", "getenv", "environ", "perf_counter", "monotonic", "listdir", "mkdir", "unlink",
                "sleep", "getpid"}


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
            if isinstance(node.value, ast.Name):
                attrs.add(f"{node.value.id}.{node.attr}")  # `datetime.now` is a clock read; `facts.now` is a field
    return modules, calls, attrs


def test_the_wake_core_imports_only_the_pure_modules():
    """Catches: a wake core that imports `os`, `time`, `json` or an engine I/O module."""
    modules, _calls, _attrs = _scan(CORE.read_text(encoding="utf-8"))
    assert sorted(modules - ALLOWED) == []


def test_the_scan_read_the_real_wake_core():
    """Catches: a scan that passes because it read an empty file."""
    modules, _calls, _attrs = _scan(CORE.read_text(encoding="utf-8"))
    assert "dataclasses" in modules


def test_the_wake_core_calls_no_io_function():
    """Catches: a wake core that calls `open`, `print`, `input`, `exec` or `eval`."""
    _modules, calls, _attrs = _scan(CORE.read_text(encoding="utf-8"))
    assert sorted(calls & BANNED_CALLS) == []


def test_the_wake_core_reads_no_clock_and_no_file_attribute():
    """Catches: a wake core that reads the clock, the process id, the environment or a file through a method."""
    _modules, _calls, attrs = _scan(CORE.read_text(encoding="utf-8"))
    assert sorted(attrs & BANNED_ATTRS) == []
