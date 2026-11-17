"""The decision of the close-time verdict check (card MW-068): a pure core. No input, no output, no git, no clock.

`decide(facts)` reads one `Facts` record the shell (`engine/verdicts.py`) built: the test nodes an Acceptance row names,
the rows of the card's verdict file, and the authors of each test file. For each named node it gives at most one
refusal, in this order: `verdict-missing` (no row, or a row whose verdict is none of true, weak, wrong),
`verdict-by-author` (the row's `by` is an author of the node's test file), `verdict-by-holder` (the row's `by` is the
session that holds the card), `verdict-by-committer` (the row's `by` is a session in the commit records of the node's
test file; a file with no record has no committer, so the holder check alone judges it: ruling R173 item 1),
`verdict-unproven` (the row has no proof of the reader: the shell says why, node by node, in `unproven`; ruling R173
item 2; a why that begins `verdict-stale:` is the id `verdict-stale`: the Acceptance rows of the node changed after the
verdict, MW-117, R287 Q4), `verdict-recut-pending` (card MW-100, R251: the last row is a `recut`, or a true row is older than the node's last
recut record, `before_recut`: the new cut waits for a fresh blind verdict), `verdict-weak`, `verdict-wrong`. A `recut` row is
proved by its own record, not by a reader run (`unproven` says so when it has none). The last row of a node is its verdict.
A card that names no node is allowed.

Before the rows, `verdict-runs-exceeded` (card MW-071, R181; per node per cut since card MW-100, R251b D): a node with more
than two reader runs since its last recut (`Facts.runs`, {node: the agent runs}).

Before the nodes (card MW-071, ruling R180) each configured checker is judged on its agent definition (`Facts.checkers`):
`checker-not-found` (no definition), `checker-not-read-only` (no tools line, or any tool beyond Read and Grep).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional, Tuple

TRUE, WEAK, WRONG = "true", "weak", "wrong"
WORDS = (TRUE, WEAK, WRONG)
MISSING, BY_AUTHOR, WEAK_ROW, WRONG_ROW = "verdict-missing", "verdict-by-author", "verdict-weak", "verdict-wrong"
BY_HOLDER = "verdict-by-holder"
BY_COMMITTER = "verdict-by-committer"
UNPROVEN = "verdict-unproven"
STALE = "verdict-stale"  # MW-117, R287 Q4: the shell's why starts with this id when the Acceptance rows of the node changed
RUNS_EXCEEDED = "verdict-runs-exceeded"  # card MW-071, ruling R181
RECUT, RECUT_PENDING = "recut", "verdict-recut-pending"  # card MW-100, rulings R251, R251b
MAX_RUNS = 2
NOT_READ_ONLY = "checker-not-read-only"  # card MW-071, ruling R180
NOT_FOUND = "checker-not-found"
READ_ONLY_TOOLS = ("Read", "Grep")
SESSION = "session:"


@dataclass(frozen=True)
class Row:
    node: str
    verdict: str
    reason: str
    by: str


@dataclass(frozen=True)
class Checker:
    """One configured checker (card MW-071): its name, the tools its agent definition lists (None: no tools line, so all
    tools), whether a definition was found, and where the shell looked (shown when it was not found)."""
    name: str
    tools: Optional[Tuple[str, ...]]
    found: bool
    searched: str = ""


@dataclass(frozen=True)
class Facts:
    nodes: Tuple[str, ...]
    rows: Tuple[Row, ...]
    authors: Mapping[str, frozenset]  # test file (as in the node id) -> the names that committed it
    holder: str = ""  # the session that holds the card now; empty when nobody does
    committers: Mapping[str, frozenset] = field(default_factory=dict)  # test file -> the sessions of its commit records
    unproven: Mapping[str, str] = field(default_factory=dict)  # node -> why its row has no proof of the reader
    checkers_missing: bool = False  # the profile names no `outbox.checkers`: no reader can be proved (ruling R179)
    checkers: Tuple[Checker, ...] = ()  # the configured checkers' definitions; each must be read-only (ruling R180)
    runs: Mapping[str, Tuple[str, ...]] = field(default_factory=dict)  # node -> its reader agent runs since its last recut: at most two (R181, R251b D)
    before_recut: frozenset = frozenset()  # the nodes whose true row is older than the node's last recut record (R251b E)
    changed: Optional[frozenset] = None  # the nodes new or changed in the card's commits; None: not known, all need rows


@dataclass(frozen=True)
class Refusal:
    node: str
    reason: str
    text: str


@dataclass(frozen=True)
class Verdict:
    refusals: Tuple[Refusal, ...]
    warnings: Tuple[str, ...] = ()

    @property
    def allowed(self) -> bool:
        return not self.refusals


def _name(text: str) -> str:
    """A reader or an author for comparing: spaces off, lower case, the `session:` form of an id without its prefix."""
    value = (text or "").strip().casefold()
    return value[len(SESSION):].strip() if value.startswith(SESSION) else value


who = _name  # the shell compares sessions the same way: case, spaces and the `session:` prefix ignored


def _pending(node: str, why: str):
    return Refusal(node, RECUT_PENDING, f"{node}: {RECUT_PENDING}: {why}; a fresh blind reader (one that started after the recut, "
                                        f"and did not build or commit the test) runs `mkway verdict add <card> <node> "
                                        f"<true|weak|wrong> <reason>` on the new cut")


def _unproven_refusal(node: str, why: str):
    """`verdict-stale` when the shell's why begins with that id (the Acceptance rows of the node changed after the verdict, MW-117),
    else `verdict-unproven`."""
    if why.startswith(f"{STALE}:"):
        return Refusal(node, STALE, f"{node}: {why}")
    return Refusal(node, UNPROVEN, f"{node}: {UNPROVEN}: {why}")


def _refusal(node: str, row, authors: frozenset, holder: str = "", committers: frozenset = frozenset(),
             unproven: str = "", before_recut: bool = False):
    if row is None or row.verdict.strip().casefold() not in WORDS + (RECUT,):
        shown = f"a row says {row.verdict!r}, which is none of true, weak, wrong" if row else "it has no row"
        return Refusal(node, MISSING, f"{node}: {MISSING}: {shown}; the verdict file needs one row "
                                      f"`node | true, weak or wrong | reason | by` from a reader who did not write the test")
    if row.verdict.strip().casefold() == RECUT:  # the lead's row: proved by its recut record, never by a reader run
        if unproven:
            return _unproven_refusal(node, unproven)
        return _pending(node, "the last row is a recut and no verdict followed it")
    if _name(row.by) in {_name(a) for a in authors}:
        return Refusal(node, BY_AUTHOR, f"{node}: {BY_AUTHOR}: the row's by `{row.by}` is an author of the test file; "
                                        f"a caller who did not write the test gives the verdict")
    if _name(holder) and _name(row.by) == _name(holder):
        return Refusal(node, BY_HOLDER, f"{node}: {BY_HOLDER}: the row's by `{row.by}` is the session that holds the card "
                                        f"({holder}); a caller who did not build the card gives the verdict")
    if _name(row.by) and _name(row.by) in {_name(s) for s in committers}:
        return Refusal(node, BY_COMMITTER, f"{node}: {BY_COMMITTER}: the row's by `{row.by}` is a session that committed "
                                           f"the test file (the commit gate's record); a caller who did not commit the "
                                           f"test gives the verdict")
    if unproven:
        return _unproven_refusal(node, unproven)
    word = row.verdict.strip().casefold()
    if word == TRUE and before_recut:
        return _pending(node, "the true row is older than the node's last recut record, so it judged the old cut")
    if word == WEAK:
        return Refusal(node, WEAK_ROW, f"{node}: {WEAK_ROW}: {row.reason}")
    if word == WRONG:
        return Refusal(node, WRONG_ROW, f"{node}: {WRONG_ROW}: {row.reason}")
    return None


NOT_ENFORCED = "blind verdict not enforced: outbox.checkers missing in profile"  # ruling R179 condition 1


def not_enforced(nodes, checkers_missing: bool):
    """The warning when the card names a test node and the profile names no checker, else None. Pure."""
    return NOT_ENFORCED if nodes and checkers_missing else None


def stop_warning(is_lead: bool, required: bool, checkers_missing: bool):
    """The warning a lead's Stop repeats while the check is on and the key is missing, else None (it trips when the key is
    set, the check is off, or the session is no lead). Pure."""
    return NOT_ENFORCED if is_lead and required and checkers_missing else None


def checker_refusal(checker: Checker):
    """The refusal for one configured checker, or None when its definition lists only Read and/or Grep (ruling R180)."""
    if not checker.found:
        return Refusal("", NOT_FOUND, f"{NOT_FOUND}: no agent definition of the checker `{checker.name}`; searched "
                                      f"{checker.searched}")
    if not checker.tools:
        return Refusal("", NOT_READ_ONLY, f"{NOT_READ_ONLY}: the checker `{checker.name}` has no tools line in its agent "
                                          f"definition, so it has every tool; the blind checker lists Read and Grep only")
    extra = [t for t in checker.tools if t not in READ_ONLY_TOOLS]
    if extra:
        return Refusal("", NOT_READ_ONLY, f"{NOT_READ_ONLY}: the checker `{checker.name}` lists {', '.join(extra)} beyond "
                                          f"Read and Grep; the blind checker is a reader that lists Read and Grep only")
    return None


def decide(facts: Facts) -> Verdict:
    warning = not_enforced(facts.nodes, facts.checkers_missing)
    if warning:  # ruling R179: with no checker nothing can prove a blind reader; the close passes and says so
        return Verdict((), (warning,))
    bad = [r for r in (checker_refusal(c) for c in facts.checkers) if r is not None] if facts.nodes else []
    if bad:  # ruling R180: a checker that is not a read-only reader cannot back a verdict
        return Verdict(tuple(bad))
    over = [n for n in dict.fromkeys(facts.nodes) if len(facts.runs.get(n, ())) > MAX_RUNS]
    if over:  # ruling R181, R251b D: one cut allows two reader runs per node; the way on is a recut of that node
        spent = "; ".join(f"{n}: {', '.join(facts.runs[n])}" for n in over)
        return Verdict((Refusal("", RUNS_EXCEEDED, f"{RUNS_EXCEEDED}: a node has had more than {MAX_RUNS} reader runs since "
                                                   f"its cut, at most {MAX_RUNS} are allowed ({spent}); the lead changes the "
                                                   f"row's words or the test, commits, and runs `mkway verdict recut <card> "
                                                   f"<node> <reason>`, then a fresh reader judges the new cut"),))
    last = {}
    for row in facts.rows:
        last[row.node] = row
    found = []
    for node in dict.fromkeys(facts.nodes):
        if facts.changed is not None and node not in facts.changed:  # ruling R181: an older, unchanged test needs no row
            continue
        file = node.partition("::")[0]
        refusal = _refusal(node, last.get(node), facts.authors.get(file, frozenset()), facts.holder,
                           facts.committers.get(file, frozenset()), facts.unproven.get(node, ""),
                           node in facts.before_recut)
        if refusal is not None:
            found.append(refusal)
    return Verdict(tuple(found))
