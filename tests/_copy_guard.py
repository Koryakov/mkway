"""Card MW-029: a static guard for the tests an installed copy runs. Not a test module.

`mkway check` in a copy runs `-m "not engine_repo"`. A test that reads a file the copy lacks (the README, the
changelog, the register) fails there. The guard collects the tests such a copy would run, reads their source and names
every one that reads a path install does not copy. `install.in_set` is the one list of copied files (MW-025).
"""
import ast
import functools
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from _engine import REPO
import install

ROOT_NAME = "REPO"  # the repository root, by the name every test file gives it
FILE_PLACE = ("tests", "<file>")  # a test file lives in tests/: `Path(__file__).resolve().parents[1]` is the root
STAR = "*"  # a part the source does not fix (a variable)
PATH_WRAPS = ("resolve", "absolute", "expanduser")


def _clean_env():
    return {k: v for k, v in os.environ.items() if k not in ("CLAUDE_PROJECT_DIR", "ENGINE_TERMS_FILE")}


def _text_parts(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [p for p in node.value.replace("\\", "/").split("/") if p and p != "."]
    return None


def _resolve(node, aliases):
    """The path an expression names, as a list of parts below the repository root (a STAR part ends the fixed
    part), or None when it is not a path built from the root."""
    if isinstance(node, ast.Name):
        if node.id == "__file__":
            return list(FILE_PLACE)
        if node.id in aliases:
            return list(aliases[node.id])
        return [] if node.id == ROOT_NAME else None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        left = _resolve(node.left, aliases)
        return None if left is None else _extend(left, [node.right])
    if isinstance(node, ast.Attribute) and node.attr == "parent":
        base = _resolve(node.value, aliases)
        return None if base is None else base[:-1]
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Attribute) and node.value.attr == "parents":
        base = _resolve(node.value.value, aliases)
        index = node.slice
        if base is None or not (isinstance(index, ast.Constant) and isinstance(index.value, int)):
            return None
        return base[:len(base) - index.value - 1] if index.value + 1 <= len(base) else []
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in PATH_WRAPS and not node.args:
            return _resolve(func.value, aliases)
        if isinstance(func, ast.Name) and func.id in ("Path", "str") and len(node.args) == 1:
            return _resolve(node.args[0], aliases)
        if isinstance(func, ast.Attribute) and func.attr == "joinpath":
            base = _resolve(func.value, aliases)
            return None if base is None else _extend(base, node.args)
        if isinstance(func, ast.Attribute) and func.attr == "join" and isinstance(func.value, ast.Attribute) \
                and func.value.attr == "path" and node.args:
            base = _resolve(node.args[0], aliases)
            return None if base is None else _extend(base, node.args[1:])
    return None


def _extend(base, operands):
    parts = list(base)
    for operand in operands:
        if parts and parts[-1] == STAR:
            break
        fixed = _text_parts(operand)
        parts.extend(fixed if fixed is not None else [STAR])
    return parts


def _is_path_expr(node):
    return (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)) or (
        isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ("joinpath", "join"))


@functools.lru_cache(maxsize=None)
def _files(root):
    return frozenset(rel for rel, _p in install._walk(Path(root)))


def _copied(root, parts):
    """True when the fixed part of the path is a file install copies, or a folder of which install copies every file.
    A path that does not exist in the repository is not a read of an engine-only file: left alone."""
    fixed = [p for p in parts if p != STAR]
    rel = "/".join(fixed)
    if any(p in install.SKIP_PARTS for p in fixed):
        return True  # a generated folder (temp, caches): not an engine file
    if not rel:
        return True  # the root itself: a walk over it finds the copy's own files
    if not (Path(root) / rel).exists():
        return True
    if (Path(root) / rel).is_file():
        return install.in_set(rel)
    if install.in_set(rel + "/"):
        return True
    below = [f for f in _files(str(root)) if f.startswith(rel + "/")]
    return bool(below) and all(install.in_set(f) for f in below)


def _refs(node, aliases, out):
    """Collect (line, parts) for each path expression rooted at the repository: the outermost chain only."""
    if _is_path_expr(node):
        parts = _resolve(node, aliases)
        if parts is not None:
            out.append((node.lineno, parts))
            for child in ast.iter_child_nodes(node):
                if _resolve(child, aliases) is None:
                    _refs(child, aliases, out)
            return
    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in aliases and aliases[node.id]:
        out.append((node.lineno, aliases[node.id]))
        return
    for child in ast.iter_child_nodes(node):
        _refs(child, aliases, out)


def _module_aliases(tree):
    """Module-level `NAME = <path from the root>`: NAME stands for that path in the file."""
    aliases = {}
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
            parts = _resolve(stmt.value, aliases)
            name = stmt.targets[0].id
            if parts is not None:
                aliases[name] = parts
            elif name in aliases:
                del aliases[name]
    return aliases


def _names_used(node):
    used = {n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        used |= {a.arg for a in node.args.args + node.args.kwonlyargs}  # a fixture is named by the argument
    return used


def reads_outside_copy(source, names=None, root=REPO):
    """[(function name, path)] for the functions of `source` that read a path install does not copy, directly or
    through a module constant or a function of the same file; `names` limits the answer (None: every function).
    Module-level reads (outside an alias line) are reported under the name `<module>`."""
    tree = ast.parse(source)
    aliases = _module_aliases(tree)
    defs = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defs.setdefault(node.name, []).append(node)
    own = {}
    for name, nodes in defs.items():
        found = []
        for fn in nodes:
            refs = []
            for stmt in fn.body:
                _refs(stmt, aliases, refs)
            found += [(line, parts) for line, parts in refs if not _copied(root, parts)]
        own[name] = found
    module_refs = []
    for stmt in tree.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name) \
                and stmt.targets[0].id in aliases:
            continue
        _refs(stmt, aliases, module_refs)
    module_bad = [(line, parts) for line, parts in module_refs if not _copied(root, parts)]
    uses = {name: set().union(*(_names_used(fn) for fn in nodes)) & set(defs) - {name}
            for name, nodes in defs.items()}
    bad = {name: list(found) for name, found in own.items()}
    changed = True
    while changed:  # a function that uses a bad function of the same file is bad too
        changed = False
        for name, used in uses.items():
            if not bad[name]:
                for other in used:
                    if bad.get(other):
                        bad[name] = list(bad[other])
                        changed = True
                        break
    result = []
    for name, found in bad.items():
        if found and (names is None or name in names):
            result.append((name, "/".join(p for p in found[0][1] if p != STAR)))
    if module_bad:
        result.append(("<module>", "/".join(p for p in module_bad[0][1] if p != STAR)))
        if names is not None:
            result += [(n, "/".join(p for p in module_bad[0][1] if p != STAR)) for n in names if n in defs]
    return result


def _short(nodeid):
    path, _sep, rest = nodeid.partition("::")
    return path, rest.split("::")[-1].split("[")[0]


def collect(root, targets=None):
    """The node ids pytest would run in a copy: `--collect-only -m "not engine_repo"` over the tests folder or the
    given files. A scratch file outside tests/ finds the helpers through PYTHONPATH."""
    root = Path(root)
    env = _clean_env()
    env["PYTHONPATH"] = str(root / "tests")
    args = [str(t) for t in targets] if targets else [str(root / "tests")]
    proc = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-m", "not engine_repo",
                           "-p", "no:cacheprovider", "-o", "addopts=", "--rootdir", str(root), *args],
                          cwd=str(root), capture_output=True, text=True, env=env, timeout=180)
    nodes = [x for x in proc.stdout.splitlines() if re.match(r"^\S+\.py::", x)]
    if proc.returncode not in (0, 5):
        raise RuntimeError("collection failed:\n" + proc.stdout[-2000:] + proc.stderr[-1000:])
    return nodes


def guard(root, nodes):
    """One line per collected test, and per helper file, that reads a path install does not copy."""
    root = Path(root)
    lines, by_file = [], {}
    for node in nodes:
        path, name = _short(node)
        by_file.setdefault(path, set()).add(name)
    for path, names in sorted(by_file.items()):
        file = Path(path) if Path(path).is_absolute() else root / path
        for name, read in sorted(reads_outside_copy(file.read_text(encoding="utf-8"), names, root)):
            lines.append(f"{path}::{name} reads {read}")
    helpers = sorted((root / "tests").glob("_*.py")) + sorted((root / "tests").glob("conftest.py"))
    for file in helpers:
        for name, read in reads_outside_copy(file.read_text(encoding="utf-8"), None, root):
            lines.append(f"tests/{file.name}::{name} reads {read}")
    return lines


@functools.lru_cache(maxsize=None)
def check_repo(root):
    """(guard lines for the repository's own tests, seconds it took)."""
    start = time.perf_counter()
    lines = guard(root, collect(root))
    return lines, time.perf_counter() - start
