"""Card MW-106: the concept base. `engine/concept.py` is the table of every refusal reason, `engine/CONCEPT.md` is the
one page every session reads; four tests fail when the engine drifts from them. Hermetic: files are parsed with ast and
read as text, nothing is imported from another test module, run, or collected. Synthetic text only."""
import ast
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
ENGINE = REPO / "engine"
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

# every way the engine emits a reason id: a refusal, a warn, a log row, an allow line, a tagged text, a log row base
REFUSE_CALLS = {"refuse", "Refused", "warn", "log", "allow_with_line", "refusal"}  # and every call of a *Error class
SECOND_ARGUMENT_CALLS = {"Refusal", "Verdict", "_tag", "base_row"}
REASON_KEYWORDS = {"reason", "reason_id"}
EXITS = {"tool", "instruction", "remove", "record"}
KIND_IDS = ["K1", "K2", "K3", "K4", "K5", "K6", "K7", "K8"]
RECORD_IDS = ["R1", "R2", "R3", "R4"]
HEADINGS = ["## a. The yardstick", "## b. The eight lines", "## c. The eight hard-gate kinds", "## d. The four records",
            "## e. The content principles", "## f. The next cards"]
YARDSTICK = "The process is straight and as simple as possible"


def _module_strings(tree):
    """The module-level `NAME = "text"` constants of a parsed module, tuple unpacking included."""
    out = {}
    for node in tree.body:
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1):
            continue
        target, value = node.targets[0], node.value
        pairs = []
        if isinstance(target, ast.Name):
            pairs = [(target, value)]
        elif isinstance(target, ast.Tuple) and isinstance(value, ast.Tuple) and len(target.elts) == len(value.elts):
            pairs = list(zip(target.elts, value.elts))
        out.update({t.id: v.value for t, v in pairs
                    if isinstance(t, ast.Name) and isinstance(v, ast.Constant) and isinstance(v.value, str)})
    return out


def _global_constants(trees):
    """The module-level string constants of all engine files by name; a name that two files give different values is
    left out, so an attribute such as `add.NODE_UNKNOWN` resolves only when its name is unambiguous."""
    seen, clashing = {}, set()
    for tree in trees:
        for name, value in _module_strings(tree).items():
            if seen.get(name, value) != value:
                clashing.add(name)
            seen[name] = value
    return {name: value for name, value in seen.items() if name not in clashing}


def _text_of(node, constants):
    """The string a call argument stands for: a literal, a constant of the same file or (by name, also as an attribute
    of another module) of any engine file; else None. `constants` is the file's own map over the global one."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return constants.get(node.id)
    if isinstance(node, ast.Attribute):
        return constants.get(node.attr)
    return None


def _call_name(call):
    func = call.func
    return func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None


def _reason_arguments(call):
    """The argument of a call that holds a reason id: the first of the calls in REFUSE_CALLS, the second of the calls
    in SECOND_ARGUMENT_CALLS, such as `Refusal(node, reason, ...)`, `Verdict(kind, reason, ...)` and `_tag(gate, reason, ...)`."""
    name, args = _call_name(call), call.args
    first_argument = name in REFUSE_CALLS or (name or "").endswith("Error")  # AskError, LeadError, CardError, ...
    chosen = args[:1] if first_argument else args[1:2] if name in SECOND_ARGUMENT_CALLS else []
    # `gate.log("a" if done else "b", ...)` holds two ids
    return [part for arg in chosen for part in ([arg.body, arg.orelse] if isinstance(arg, ast.IfExp) else [arg])]


def _is_reason_tuple(node):
    """A module-level assignment of a tuple or list to REASONS, REASON_IDS or a name ending with _REASONS."""
    if not (isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, (ast.Tuple, ast.List))):
        return False
    name = node.targets[0].id
    return name in {"REASONS", "REASON_IDS"} or name.endswith("_REASONS")


def _emitted_constants(node):
    """The row kinds of the watch mode: the module constants WOULD_REFUSE and ON_ROW, and the values of TRANSITIONS."""
    if not (isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)):
        return []
    name, value = node.targets[0].id, node.value
    if name in {"WOULD_REFUSE", "ON_ROW"} and isinstance(value, ast.Constant) and isinstance(value.value, str):
        return [value.value]
    if name == "TRANSITIONS" and isinstance(value, ast.Dict):
        return [v.value for v in value.values if isinstance(v, ast.Constant) and isinstance(v.value, str)]
    return []


def source_reason_ids():
    """The reason ids the engine source uses, found with ast over engine/*.py: the reason argument of a refusing call
    (see `_reason_arguments`), a `reason="..."` or `reason_id="..."` keyword, the first element of a returned
    `(id, text)` tuple, the values of a dict literal that is subscripted, the kind of a row dict, and the strings or
    constants of a module-level reason tuple. A constant is read in its own file, else by name from any engine file.
    The id shape is lower-case words joined by hyphens; the engine has no one-word reason id (the one-word strings
    it passes the same way are row kinds and node verdict words, not reasons)."""
    shape = re.compile(r"[a-z][a-z0-9]*(-[a-z0-9]+)+")
    found = set()
    trees = {path: ast.parse(path.read_text(encoding="utf-8")) for path in sorted(ENGINE.glob("*.py"))}
    everywhere = _global_constants(trees.values())
    for tree in trees.values():
        constants = {**everywhere, **_module_strings(tree)}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                texts = [_text_of(a, constants) for a in _reason_arguments(node)]
                texts += [_text_of(k.value, constants) for k in node.keywords if k.arg in REASON_KEYWORDS]
                found.update(t for t in texts if t and shape.fullmatch(t))
            elif isinstance(node, ast.Return) and isinstance(node.value, ast.Tuple) and len(node.value.elts) == 2:
                texts = [_text_of(node.value.elts[0], constants)]  # the checks return (reason id, text)
                found.update(t for t in texts if t and shape.fullmatch(t))
            elif isinstance(node, ast.Subscript) and isinstance(node.value, ast.Dict):
                texts = [_text_of(v, constants) for v in node.value.values]  # {"edit": "id-a", "shell": "id-b"}[how]
                found.update(t for t in texts if t and shape.fullmatch(t))
            elif isinstance(node, ast.Dict):  # a row written as {"kind": "<id>"}
                texts = [_text_of(v, constants) for k, v in zip(node.keys, node.values)
                         if isinstance(k, ast.Constant) and k.value == "kind"]
                found.update(t for t in texts if t and shape.fullmatch(t))
        for node in tree.body:
            if _is_reason_tuple(node):
                found.update(t for t in (_text_of(e, constants) for e in node.value.elts) if t and shape.fullmatch(t))
            found.update(t for t in _emitted_constants(node) if shape.fullmatch(t))
    return found


def collected_test_ids():
    """The node ids of every test under tests/, read statically: module functions and methods of Test classes whose
    names start with `test`, as `tests/<path>::name` or `tests/<path>::Class::name`; no pytest collection."""
    ids = set()
    for path in sorted((REPO / "tests").rglob("test_*.py")):
        rel = path.relative_to(REPO).as_posix()
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
                ids.add(f"{rel}::{node.name}")
            elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
                ids.update(f"{rel}::{node.name}::{m.name}" for m in node.body
                           if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and m.name.startswith("test"))
    return ids


def _base(node_id):
    """A node id without its parametrised suffix."""
    return node_id.split("[", 1)[0]


def _section(text, heading):
    """The text of one `## ` section of CONCEPT.md, from its heading to the next heading."""
    start = text.index(heading)
    nxt = text.find("\n## ", start + 1)
    return text[start:] if nxt == -1 else text[start:nxt]


def test_every_reason_in_the_source_has_a_row_and_every_row_a_reason():
    """Catches: a refusal reason the engine uses that the table never placed, or a row for a reason that is gone."""
    import concept
    source = source_reason_ids()
    rows = set(concept.REASONS)
    assert sorted(source - rows) == [], f"reason ids with no row in REASONS: {sorted(source - rows)}"
    assert sorted(rows - source) == [], f"rows whose reason id is not in the source: {sorted(rows - source)}"


@pytest.mark.parametrize("reason", ["gate-error", "commit-tests-still-red", "ask-past-deadline",
                                    "ping-skipped", "undeclared-reason", "would-refuse", "gate-watch", "gate-watch-installed",
                                    "gate-on",
                                    "ask-not-open",  # AskError(...)
                                    "lead-unknown",  # LeadError(...)
                                    "ledger-by-owner",  # run.refusal(...)
                                    "close-deliverable-unbuilt", "base-unknown",  # a returned (id, text) tuple
                                    "verdict-written",  # the kind of a record row
                                    "agent-record-failed",  # raised only by allow_with_line
                                    "notify-sent", "notify-failed",  # both branches of a conditional
                                    "ping-skipped-listed",
                                    "lock-closed-commit",  # a value of a dict that is subscripted
                                    "verdict-node-unknown"])  # a constant of another file, read as an attribute
def test_the_finder_sees_every_way_the_engine_emits_a_reason(reason):
    """Catches: a finder that sees only refusals, so a reason raised through a helper, a warn or a log row has no row."""
    assert reason in source_reason_ids()


def test_there_are_eight_kinds_and_four_exits_and_every_row_uses_them():
    """Catches: a ninth kind, a row of an unknown kind or exit, an exit row with no card 2 to 8, a kind row with a card."""
    import concept
    assert list(concept.KINDS) == KIND_IDS
    assert list(concept.RECORDS) == RECORD_IDS
    bad_place = sorted(r for r, row in concept.REASONS.items() if row.kind_or_exit not in set(KIND_IDS) | EXITS)
    assert bad_place == [], f"rows of a kind or exit that does not exist: {bad_place}"
    bad_exit = sorted(r for r, row in concept.REASONS.items()
                      if row.kind_or_exit in EXITS and row.card not in range(2, 9))
    assert bad_exit == [], f"exit rows without a card number 2 to 8: {bad_exit}"
    bad_kind = sorted(r for r, row in concept.REASONS.items() if row.kind_or_exit in KIND_IDS and row.card is not None)
    assert bad_kind == [], f"kind rows that carry a card number: {bad_kind}"


def test_every_row_has_a_way_out_test_or_a_gap_and_the_gaps_only_shrink():
    """Catches: a way-out test that does not exist, a row with neither a test nor a gap card, a count of gaps above the
    number written in concept.py."""
    import concept
    ids = {_base(i) for i in collected_test_ids()}
    missing = sorted(r for r, row in concept.REASONS.items() if row.way_out is not None and _base(row.way_out) not in ids)
    assert missing == [], f"way-out tests that are not in tests/: {missing}"
    neither = sorted(r for r, row in concept.REASONS.items()
                     if not ((row.way_out is not None and row.gap is None)
                             or (row.way_out is None and row.gap in range(2, 9))))
    assert neither == [], f"rows with no way-out test and no gap card, or with both: {neither}"
    gaps = [r for r, row in concept.REASONS.items() if row.way_out is None]
    assert len(gaps) == concept.GAPS_ALLOWED, f"{len(gaps)} gap rows, GAPS_ALLOWED is {concept.GAPS_ALLOWED}"
    # a literal ceiling: each later card lowers this number in the same commit as GAPS_ALLOWED, so a new gap with a
    # raised constant cannot pass
    assert concept.GAPS_ALLOWED <= 55, f"GAPS_ALLOWED {concept.GAPS_ALLOWED} is above the ceiling of the test"  # MW-115: one less (gate-watch-integrity has a way-out test); MW-112: 96 (MW-108) less the 40 gap rows of block 7 = 56; MW-110: 113 less the 14 rows of block 5


def test_the_concept_page_holds_its_parts_in_order():
    """Catches: a concept page that lost the yardstick, a numbered line, a kind, a record or a card, or reordered them."""
    text = (ENGINE / "CONCEPT.md").read_text(encoding="utf-8")
    places = [text.index(h) for h in HEADINGS]
    assert places == sorted(places), "the six sections are not in the order a to f"
    assert YARDSTICK in _section(text, HEADINGS[0])
    numbered = re.findall(r"^(\d)\. ", _section(text, HEADINGS[1]), re.M)
    assert numbered == ["1", "2", "3", "4", "5", "6", "7", "8"]
    assert re.findall(r"^- \*\*(K\d)\b", _section(text, HEADINGS[2]), re.M) == KIND_IDS
    assert re.findall(r"^- \*\*(R\d)\b", _section(text, HEADINGS[3]), re.M) == RECORD_IDS
    assert "the task-content concept, later" in _section(text, HEADINGS[4])
    assert re.findall(r"^(\d)\. ", _section(text, HEADINGS[5]), re.M) == ["2", "3", "4", "5", "6", "7", "8"]
