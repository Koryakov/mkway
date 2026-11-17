"""Card MW-072: `engine/core_red.py` is pure by construction: it imports only the standard modules that touch no disk,
process, clock or environment, and the engine's `helpers` (the reader's pure functions on text)."""
import ast
from pathlib import Path

CORE = Path(__file__).resolve().parents[2] / "engine" / "core_red.py"
ALLOWED = {"__future__", "re", "dataclasses", "typing", "helpers"}


def _imported_modules(source):
    tree = ast.parse(source)
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            modules.add((node.module or "").split(".")[0])
    return modules


def test_core_red_imports_only_the_pure_modules():
    """Catches: an I/O import (os, subprocess, runner, git) that would let the decision read the world itself."""
    modules = _imported_modules(CORE.read_text(encoding="utf-8"))
    assert modules <= ALLOWED, sorted(modules - ALLOWED)
