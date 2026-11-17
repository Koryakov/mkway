"""The pure core of the close-time freshness of a verdict row (card MW-101; decisions R196, R253). No I/O: `decide` gets the
old text of a test file (the blob the add record names), the new text (HEAD's) and the node id, and returns a `Verdict`.

A row stays fresh while its node's meaning is unchanged: the node's own source (the function, its decorators and its
docstring) is equal in both texts, and so is the non-test code of the file. A test function is a function whose name starts
with `test` and that carries no fixture decorator (`pytest.fixture` or `fixture`, called or not), at top level or as a method
of a top-level class. Non-test code is the source text, decorators included, of every other top-level statement and of every
other member of a top-level class, in order, with the head of each class (its decorators, name and bases). Fixtures (also one
named `test_*`), helpers, imports, module constants and class bodies stay in. The compare is of text: a comment or a blank
line inside a kept statement is a change; between two statements it is none.

The node is found by its full path: `file::test_x` is the top-level function, `file::Class::test_x` the method `test_x` of
the top-level class `Class`; `[params]` is dropped; a deeper path is not found. When a name is defined twice the last one
wins, as it does when pytest imports the file.

Kinds of a stale verdict: `unreadable` (a text does not parse), `missing` (the node is not in a text), `node` (its own source
changed), `code` (the non-test code changed). Never guessed as unchanged.

Named gap (R253): cross-file helpers (`tests/_*.py` kits, `conftest.py`) are not read; a change there leaves a row fresh.
"""
from __future__ import annotations

import ast
from typing import NamedTuple, Optional

FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)


class Verdict(NamedTuple):
    """`fresh`; else the `kind` of the staleness and its `text` (names what changed)."""
    fresh: bool
    kind: str
    text: str


def _lines(text: str) -> list:
    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n")


def _first(item) -> int:
    """The first line of a statement, its decorators included."""
    return min([item.lineno] + [d.lineno for d in getattr(item, "decorator_list", [])])


def _source(lines: list, item) -> str:
    return "\n".join(lines[_first(item) - 1:item.end_lineno])


def _is_fixture(item) -> bool:
    for decorator in item.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if (isinstance(target, ast.Name) and target.id == "fixture") or (
                isinstance(target, ast.Attribute) and target.attr == "fixture"):
            return True
    return False


def _is_test(item) -> bool:
    return isinstance(item, FUNCTIONS) and item.name.startswith("test") and not _is_fixture(item)


def _head(lines: list, cls) -> str:
    """The head of a class: its decorators, its line and what lies between it and its first member."""
    start = _first(cls)
    end = _first(cls.body[0]) - 1
    return "\n".join(lines[start - 1:max(end, start)]).rstrip()


def _code(body: list, lines: list, owner: str = "") -> list:
    """The non-test code of a body, in order, as `(owner class, source text)` pairs."""
    found = []
    for item in body:
        if _is_test(item):
            continue
        if isinstance(item, ast.ClassDef) and not owner:
            found.append((item.name, _head(lines, item)))
            found.extend(_code(item.body, lines, item.name))
        else:
            found.append((owner, _source(lines, item)))
    return found


def _find(tree, node: str) -> Optional[ast.AST]:
    """The function the node id names (the last definition of the name); None when it is not found."""
    parts = node.partition("::")[2].split("::")
    parts[-1] = parts[-1].partition("[")[0]
    scope = tree.body
    if len(parts) == 2:
        classes = [i for i in scope if isinstance(i, ast.ClassDef) and i.name == parts[0]]
        scope = classes[-1].body if classes else []
    elif len(parts) != 1:
        scope = []
    found = [i for i in scope if isinstance(i, FUNCTIONS) and i.name == parts[-1]]
    return found[-1] if found else None


def decide(old: str, new: str, node: str) -> Verdict:
    """Fresh when the texts are equal, or when the node's own source and the file's non-test code are equal in both."""
    if old == new:
        return Verdict(True, "", "")
    trees = []
    for which, text in (("old", old), ("new", new)):
        try:
            trees.append(ast.parse(text))
        except (SyntaxError, ValueError, RecursionError):
            return Verdict(False, "unreadable", f"the {which} text of the test file cannot be parsed")
    texts = (_lines(old), _lines(new))
    items = [_find(tree, node) for tree in trees]
    for which, item in zip(("old", "new"), items):
        if item is None:
            return Verdict(False, "missing", f"{node} is not found in the {which} text of the test file")
    if _source(texts[0], items[0]) != _source(texts[1], items[1]):
        return Verdict(False, "node", f"the own source of {node} (the function, its decorators and its docstring) changed")
    if _code(trees[0].body, texts[0]) != _code(trees[1].body, texts[1]):
        return Verdict(False, "code", "the non-test code of its file (module level, fixtures, helpers, imports) changed")
    return Verdict(True, "", "")
