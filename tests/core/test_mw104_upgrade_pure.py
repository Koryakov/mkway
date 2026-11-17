"""Card MW-104: `engine/core_upgrade.py` is pure by construction. A test fails if it imports a module `core_install.py` does
not import, or calls `open`, `print` or `input`, or reads the clock, the disk or the environment. Runtime proof is the guard
of the core tests, which call it with no process, no file and no clock."""
import ast
from pathlib import Path

import _engine  # noqa: F401

ENGINE = Path(__file__).resolve().parents[2] / "engine"
BANNED_CALLS = {"open", "print", "input", "exec", "eval", "__import__", "compile"}
BANNED_ATTRS = {"now", "today", "utcnow", "read_text", "write_text", "read_bytes", "write_bytes", "is_file", "is_dir",
                "exists", "stat", "resolve", "getenv", "environ", "perf_counter", "monotonic", "system", "popen"}


def _scan(source):
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


def test_core_upgrade_imports_only_what_core_install_imports():
    """Catches: an import in engine/core_upgrade.py of a module that core_install.py does not import (a disk, process or clock module)."""
    allowed, _c, _a = _scan((ENGINE / "core_install.py").read_text(encoding="utf-8"))
    modules, _calls, _attrs = _scan((ENGINE / "core_upgrade.py").read_text(encoding="utf-8"))
    assert modules <= allowed | {"__future__"}, sorted(modules - allowed)


def test_core_upgrade_calls_no_io_function():
    """Catches: a call in engine/core_upgrade.py of open, print or input, or a read of the clock, the disk or the environment."""
    _modules, calls, attrs = _scan((ENGINE / "core_upgrade.py").read_text(encoding="utf-8"))
    assert not calls & BANNED_CALLS, sorted(calls & BANNED_CALLS)
    assert not attrs & BANNED_ATTRS, sorted(attrs & BANNED_ATTRS)
