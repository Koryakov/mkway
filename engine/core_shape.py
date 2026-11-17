"""The shape decision of the tests a commit adds or changes (card MW-073, ruling R177): a pure core. No input, no output, no
git, no clock; it only parses the text it is given.

`decide(facts)` reads one `Facts` record the shell (`engine/gate_test_shape.py`) built: for each test file the commit
takes, the text of the file in the committed tree (`new`) and in the base (`old`, None for a new file). A test function
is judged only when it is new or changed (its syntax tree differs from the one of the same name in `old`); an old
function that did not change is never judged again. The rules, one `Breach` per function and rule:
S1 no `for`, `while` or `if` statement in the body; S2 at least one `assert` or `pytest.raises`; S3 no `assert True`,
`assert False`, no `assert a and b`; S4 a one-line docstring that starts `Catches:`, `Checks:` or `Pins:`; S5 no import
of another test module (`test_*`, `tests`, `tests.*`; a helper that starts with `_` is allowed) and no literal that names
another test file; S6 no `time.sleep`, `socket`, `requests`, `urllib`, `http` and no absolute path literal; S7 in a test
under `tests/core` the expected side of `==` is a literal or a parametrize argument, never a call. A new file whose
module level imports a test module breaks S5 on the name `<module>`.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

S1, S2, S3, S4, S5, S6, S7 = "S1", "S2", "S3", "S4", "S5", "S6", "S7"
RULES = (S1, S2, S3, S4, S5, S6, S7)
TEXTS = {
    S1: "a for, while or if in the test body; use pytest.mark.parametrize for cases",
    S2: "no assert and no pytest.raises: the test checks nothing",
    S3: "an assert that is constant (assert True, assert False) or composite (assert a and b)",
    S4: ("no one-line docstring that starts Catches: (failure path), Checks: (allow path) or Pins: (pinned behaviour; "
         "the red proof decides whether a pin is allowed)"),
    S5: "an import of another test module, or a literal that names another test file; a helper starts with _",
    S6: "time.sleep, socket, requests, urllib, http, or an absolute path literal; use tmp_path",
    S7: "in a core test the expected side of == is a call; use a literal or a parametrize argument",
}
MODULE = "<module>"
SHOWN = 10
CORE_FOLDER = "tests/core/"
NETWORK = frozenset({"socket", "requests", "urllib", "http"})
SAFE_CALLS = frozenset({"frozenset", "set", "tuple", "list", "dict", "sorted", "len", "str", "int", "float", "bool",
                        "repr", "Path", "PurePath", "PurePosixPath", "PureWindowsPath"})
TEST_FILE_LITERAL = re.compile(r"[\w./\\-]*test_\w+\.py")
ABSOLUTE = re.compile(r"[A-Za-z]:[\\/]|\\\\|/[\w.~-]+(?:/|$)")


@dataclass(frozen=True)
class Source:
    path: str  # relative to the task root, `/` separators
    new: str  # the file in the committed tree
    old: Optional[str] = None  # the file in the base; None for a file the commit adds


@dataclass(frozen=True)
class Facts:
    sources: Tuple[Source, ...]


@dataclass(frozen=True)
class Breach:
    file: str
    function: str
    rule: str
    text: str


@dataclass(frozen=True)
class Verdict:
    breaches: Tuple[Breach, ...]
    unparsed: Tuple[str, ...] = ()  # files that are not Python: the test run reports them, this decision only lists them
    judged: int = 0  # the test functions that were new or changed

    @property
    def allowed(self) -> bool:
        return not self.breaches


def is_test_file(path: str) -> bool:
    name = path.replace("\\", "/").rsplit("/", 1)[-1]
    return name.startswith("test_") and name.endswith(".py")


def _is_test_module(name: str) -> bool:
    top = name.split(".")[0]
    return top == "tests" or top.startswith("test_")


def _test_functions(tree: ast.Module) -> Dict[str, ast.AST]:
    """{qualified name: node} of the module-level `test_*` functions and the `test_*` methods of `Test*` classes."""
    found = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
            found[node.name] = node
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name.startswith("test_"):
                    found[f"{node.name}.{item.name}"] = item
    return found


def _module_imports(tree: ast.Module) -> List[ast.stmt]:
    return [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]


def _imported_names(node: ast.stmt) -> List[str]:
    if isinstance(node, ast.Import):
        return [a.name for a in node.names]
    return [node.module or ""]


def _aliases(tree: ast.Module) -> Tuple[frozenset, frozenset]:
    """(names that stand for a banned network module, names that stand for `time.sleep`) bound by the module's imports."""
    network, sleeps = set(NETWORK), set()
    for node in _module_imports(tree):
        if isinstance(node, ast.Import):
            network |= {a.asname or a.name.split(".")[0] for a in node.names if a.name.split(".")[0] in NETWORK}
        elif (node.module or "").split(".")[0] in NETWORK:
            network |= {a.asname or a.name for a in node.names}
        elif node.module == "time":
            sleeps |= {a.asname or a.name for a in node.names if a.name == "sleep"}
    return frozenset(network), frozenset(sleeps)


def _body_nodes(func) -> List[ast.AST]:
    return [n for stmt in func.body for n in ast.walk(stmt)]


def _is_raises(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    fn = node.func
    return (isinstance(fn, ast.Attribute) and fn.attr == "raises") or (isinstance(fn, ast.Name) and fn.id == "raises")


def _skipped_constants(func) -> set:
    """The ids of the string constants no literal rule reads: the docstring, the tail parts of an f-string, the right
    operand of an operator (`str(tmp_path) + "/x"`)."""
    skip = set()
    first = func.body[0]
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
        skip.add(id(first.value))
    for node in _body_nodes(func):
        if isinstance(node, ast.JoinedStr):
            skip |= {id(v) for v in node.values[1:]}
        elif isinstance(node, ast.BinOp):
            skip.add(id(node.right))
    return skip


def _strings(func) -> List[str]:
    skip = _skipped_constants(func)
    return [n.value for n in _body_nodes(func)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in skip]


def _s1(func, nodes) -> bool:
    return any(isinstance(n, (ast.For, ast.AsyncFor, ast.While, ast.If)) for n in nodes)


def _s2(func, nodes) -> bool:
    return not any(isinstance(n, ast.Assert) or _is_raises(n) for n in nodes)


def _s3(func, nodes) -> bool:
    for n in nodes:
        if isinstance(n, ast.Assert):
            test = n.test
            if isinstance(test, ast.Constant) and isinstance(test.value, bool):
                return True
            if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.And):
                return True
    return False


def _s4(func, nodes) -> bool:
    doc = ast.get_docstring(func)
    return not (doc and "\n" not in doc and doc.startswith(("Catches:", "Checks:", "Pins:")))


def _s5(func, nodes) -> bool:
    for n in nodes:
        if isinstance(n, (ast.Import, ast.ImportFrom)) and any(_is_test_module(x) for x in _imported_names(n)):
            return True
        if isinstance(n, ast.Call) and isinstance(n.func, (ast.Name, ast.Attribute)):
            name = n.func.id if isinstance(n.func, ast.Name) else n.func.attr
            if name in ("import_module", "__import__") and n.args and isinstance(n.args[0], ast.Constant) \
                    and isinstance(n.args[0].value, str) and _is_test_module(n.args[0].value):
                return True
    return any(TEST_FILE_LITERAL.fullmatch(s) for s in _strings(func))


def _s6(func, nodes, network, sleeps) -> bool:
    for n in nodes:
        if isinstance(n, ast.Name) and (n.id in network or n.id in sleeps):
            return True
        if isinstance(n, ast.Attribute) and n.attr == "sleep" and isinstance(n.value, ast.Name) \
                and n.value.id == "time":
            return True
        if isinstance(n, (ast.Import, ast.ImportFrom)) and any(x.split(".")[0] in NETWORK for x in _imported_names(n)):
            return True
    return any(ABSOLUTE.match(s) for s in _strings(func))


def _is_safe_call(node: ast.Call) -> bool:
    fn = node.func
    if isinstance(fn, ast.Name):
        return fn.id in SAFE_CALLS
    return isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Constant)  # "text".join(...)


def _is_pure_literal(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return all(_is_pure_literal(e) for e in node.elts)
    if isinstance(node, ast.Dict):
        return all(k is not None and _is_pure_literal(k) and _is_pure_literal(v) for k, v in zip(node.keys, node.values))
    if isinstance(node, ast.UnaryOp):
        return _is_pure_literal(node.operand)
    return False


def _computed(node: ast.AST, tainted: set) -> bool:
    """The expression holds a call that is not a literal constructor, or a name set from such a call."""
    for n in ast.walk(node):
        if isinstance(n, ast.Call) and not _is_safe_call(n):
            return True
        if isinstance(n, ast.Name) and n.id in tainted:
            return True
    return False


def _tainted(nodes) -> set:
    names = set()
    for n in nodes:
        if isinstance(n, ast.Assign) and _computed(n.value, set()):
            names |= {t.id for t in n.targets if isinstance(t, ast.Name)}
    return names


def _s7(func, nodes) -> bool:
    tainted = _tainted(nodes)
    for n in nodes:
        if isinstance(n, ast.Assert) and isinstance(n.test, ast.Compare):
            sides = [n.test.left, *n.test.comparators]
            for left, op, right in zip(sides, n.test.ops, sides[1:]):
                if isinstance(op, ast.Eq) and not _is_pure_literal(left) and _computed(right, tainted):
                    return True
    return False


def _breaks(func, path: str, tree: ast.Module) -> List[str]:
    nodes = _body_nodes(func)
    network, sleeps = _aliases(tree)
    found = [S1] if _s1(func, nodes) else []
    found += [S2] if _s2(func, nodes) else []
    found += [S3] if _s3(func, nodes) else []
    found += [S4] if _s4(func, nodes) else []
    found += [S5] if _s5(func, nodes) else []
    found += [S6] if _s6(func, nodes, network, sleeps) else []
    found += [S7] if CORE_FOLDER in path.replace("\\", "/") and _s7(func, nodes) else []
    return found


def _parse(text: Optional[str]) -> Optional[ast.Module]:
    try:
        return None if text is None else ast.parse(text)
    except (SyntaxError, ValueError):
        return None


def _judge(source: Source):
    """(breaches, judged count, parsed) of one file."""
    tree = _parse(source.new)
    if tree is None:
        return [], 0, False
    old = _parse(source.old)
    before = {} if old is None else {k: ast.dump(v) for k, v in _test_functions(old).items()}
    old_imports = set() if old is None else {ast.dump(n) for n in _module_imports(old)}
    out = [Breach(source.path, MODULE, S5, TEXTS[S5]) for n in _module_imports(tree)
           if ast.dump(n) not in old_imports and any(_is_test_module(x) for x in _imported_names(n))][:1]
    judged = 0
    for name, func in _test_functions(tree).items():
        if before.get(name) == ast.dump(func):
            continue
        judged += 1
        out += [Breach(source.path, name, rule, TEXTS[rule]) for rule in _breaks(func, source.path, tree)]
    return out, judged, True


def decide(facts: Facts) -> Verdict:
    breaches, unparsed, judged = [], [], 0
    for source in facts.sources:
        if not is_test_file(source.path):
            continue
        found, count, parsed = _judge(source)
        breaches += found
        judged += count
        unparsed += [] if parsed else [source.path]
    return Verdict(tuple(breaches), tuple(unparsed), judged)


def refusal_text(verdict: Verdict) -> str:
    """The text of a refusal: the count, the first ten breaches as `file::function: rule reason`, the rest counted."""
    shown = [f"{b.file}::{b.function}: {b.rule} {b.text}" for b in verdict.breaches[:SHOWN]]
    more = len(verdict.breaches) - len(shown)
    count = len(verdict.breaches)
    head = f"{count} {'breach' if count == 1 else 'breaches'} of the test shape rules in the tests this commit adds or changes"
    tail = f"; and {more} more" if more > 0 else ""
    return (f"{head}: {'; '.join(shown)}{tail}. Fix the tests and stage the fix; only a function that is new or changed "
            f"in the commit is judged.")
