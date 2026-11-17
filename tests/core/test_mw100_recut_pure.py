"""Card MW-100 (decision: R251a point 8), layer core: `engine/core_verdict_recut.py` is pure by construction, and the lock
gate leaves the by-permit for `verdict recut` as it does for `verdict add`. A test fails if the core imports a module that
reaches the disk, a process, the environment or the clock (its own sibling cores are allowed), or calls `open`, `print`,
`input` or reads the clock. The scan reads the source with `ast`. No disk, no git, no clock."""
import ast
from pathlib import Path

import _engine  # noqa: F401  (puts the engine folder on the import path)
import core_lock as core

CORE = Path(__file__).resolve().parents[2] / "engine" / "core_verdict_recut.py"
ALLOWED = {"__future__", "re", "dataclasses", "typing", "core_verdict_add"}
BANNED_CALLS = {"open", "print", "input", "exec", "eval", "__import__", "compile"}
BANNED_ATTRS = {"now", "today", "utcnow", "read_text", "write_text", "read_bytes", "write_bytes", "is_file", "is_dir",
                "exists", "stat", "resolve", "getenv", "environ", "perf_counter", "monotonic"}
QUIET = {("engine_call",): None, ("calls",): (), ("parse_ok",): True, ("names_commit",): False, ("carrier",): None,
         ("form",): None, ("env",): None, ("cdpath",): False, ("writes",): core.WriteFacts(), ("expanded_text",): "",
         ("commits",): (), ("unknown_shape",): "", ("holders",): {}, ("mine",): None, ("stale",): {}, ("lead",): False,
         ("register",): core.RegisterFacts()}


class Reads(dict):
    """The facts of the case; a disk fact is "no file"."""

    def __contains__(self, key):
        return key[0] == "disk" or dict.__contains__(self, key)

    def __getitem__(self, key):
        return None if key[0] == "disk" else dict.__getitem__(self, key)


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


def verdict(*args):
    facts = core.Facts(tool_name="Bash", command="", targets=(), session_id="s1", vcs_git=False,
                       register_rel="mkway/cards/REGISTER.md", owner_terminal="OWNER-TERMINAL", owner_fix="OWNER-FIX",
                       stale_hours=2, reads=Reads({**QUIET, ("calls",): (args,)}))
    return core.decide(facts)


def test_the_recut_core_imports_only_pure_modules():
    """Catches: an I/O module (os, pathlib, subprocess, time, datetime, an engine reader) imported into the decision."""
    modules, _calls, _attrs = scan(CORE.read_text(encoding="utf-8"))
    assert modules - ALLOWED == set()


def test_the_recut_core_calls_no_io_function():
    """Catches: the decision reading a file, printing, or asking the clock."""
    _modules, calls, attrs = scan(CORE.read_text(encoding="utf-8"))
    assert (calls & BANNED_CALLS) | (attrs & BANNED_ATTRS) == set()


def test_the_lock_gate_leaves_a_by_permit_for_verdict_recut():
    """Catches: a `verdict recut` call that leaves no by-permit, so every recut is refused as verdict-no-caller."""
    found = verdict("verdict", "recut", "CARD-001", "tests/test_a.py::test_one", "the row said byte for byte")
    assert [(p.kind, p.card) for p in found.permits] == [("by", None)]
