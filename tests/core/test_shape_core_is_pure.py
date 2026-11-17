"""Card MW-073 (decision: R177): `engine/core_shape.py` is pure. It may import `ast`, `re`, `dataclasses`, `typing`; it opens
no file, prints nothing, reads no clock and runs no process."""
import ast
from pathlib import Path

import _engine  # noqa: F401

CORE = Path(__file__).resolve().parents[2] / "engine" / "core_shape.py"
ALLOWED = {"__future__", "ast", "re", "dataclasses", "typing"}
BANNED_CALLS = {"open", "print", "input", "exec", "eval", "__import__", "compile"}
BANNED_ATTRS = {"now", "today", "read_text", "write_text", "is_file", "exists", "stat", "getenv", "environ", "run",
                "Popen", "system"}


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


def test_the_shape_core_imports_only_the_pure_modules():
    """Catches: an import of a module that reaches the disk, a process, the environment or the clock."""
    modules, _calls, _attrs = _scan(CORE.read_text(encoding="utf-8"))
    assert modules <= ALLOWED, sorted(modules - ALLOWED)


def test_the_shape_core_calls_no_io_function_and_reads_no_clock():
    """Catches: a call of open, print or input, or a read of the clock or the environment, inside the decision."""
    _modules, calls, attrs = _scan(CORE.read_text(encoding="utf-8"))
    assert not calls & BANNED_CALLS, sorted(calls & BANNED_CALLS)
    assert not attrs & BANNED_ATTRS, sorted(attrs & BANNED_ATTRS)
