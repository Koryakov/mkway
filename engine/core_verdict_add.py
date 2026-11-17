"""The decision of `mkway verdict add` (card MW-080; rulings R194, R196, R196a): a pure core. No input, no output, no git, no
clock; the shell (`engine/verdict_add.py`) reads the facts and writes the rows.

`decide(facts)` reads one `Facts` record: the caller (the session the lock gate's by-permit names), whether the owner's
terminal runs it, the card's register status and holder, every session that ever took the card, the profile's switches, and per requested
node a `Node`: whether the card names it, the sessions that committed its test file, the last commit of the file, the blob of
the file at HEAD and now, the checker runs of the caller's session (`readers`) and those of them that started after that
commit (`fresh`), the reader runs already used for the node since its last recut (`used`, card MW-100: the budget is per node
per cut), and for a recut node the readers that started after the recut record (`since_recut`; None: never recut). It gives
a `Verdict`: the refusals that block, the refusals that watch mode let through (`watched`), and the reader run the call uses
(`run`, its `number` for the node).

Refusal ids, in the order they are judged (a refusal text begins with its id):
  verdict-not-enforced   no `outbox.checkers`, or `cards.verdicts` is off: no reader can be proved (names the key)
  verdict-by-owner       the owner's terminal: a verdict is never the owner's (R181)
  verdict-no-caller      a session whose id the gate left no permit for: no `by` can be written
  verdict-by-holder      the caller ever took the card (not only the holder now)
  verdict-card-state     the card is not waiting or open (closed, proposed or waiting for the owner; a builder may hold an open
                         card: ruling R272 G3 supersedes R194, MW-117)
  verdict-no-red-proof   the card has no red-proof row, so its tests were never proved red (MW-117; the way out is the red
                         commit of the card's tests). MW-130: one id, four true texts, by `Facts.red_case`: (i) no row of the
                         card; (ii) rows exist but no commit of HEAD has their tree; (iii) the search for the commit of an
                         older row (no git tree) ran out of time after N commits; (iv) the git history of HEAD could not be
                         read (way out: repeat the call)
  per node:
  verdict-node-unknown   the card's Acceptance rows do not name the node
  verdict-by-committer   the caller is a committer of the node's test file (the commit gate's records, R173)
  verdict-stale          the test file is not HEAD's text (uncommitted change, or no commit: both blob shas named), or no
                         checker run of the caller's session started after the last commit of the file (R196), or no
                         single run is fresh for every node of the call
  verdict-no-reader-run  the caller's session has no run of a configured checker at all
  verdict-runs-exceeded  a third distinct reader run for a node since its last recut (at most two per node per cut; R181,
                         R251b D); the text names `mkway verdict recut`, the lead's way to a new cut
  verdict-run-before-recut  a recut node, and no run common to the call started after the recut record (R251a point 3): a
                         run used or started before a recut can never judge the new cut
  verdict-reader-unguarded  the reader run the call uses has no record row of the allowlist hook, or its allow list was not
                         exactly the card's two inputs (card MW-116, R287c; `Facts.guard`: agent id -> the problem, empty when
                         the run is guarded); the way out is to trust the folder of the agent file, run `mkway reader start`
                         and a fresh reader (refused in both modes)

Mode (`tests.verdict_add.mode`, ruling R196a): `watch` lets a refusal through (it is listed in `Verdict.watched`) except the
ones that decide independence or that make a row impossible: `verdict-by-holder`, `verdict-by-committer`,
`verdict-by-owner`, `verdict-stale`, `verdict-no-caller`. Any other value, and a missing key, is `trip`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping
from typing import Optional, Tuple

TRIP, WATCH = "trip", "watch"
NOT_ENFORCED = "verdict-not-enforced"
BY_OWNER = "verdict-by-owner"
NO_CALLER = "verdict-no-caller"
BY_HOLDER = "verdict-by-holder"
CARD_STATE = "verdict-card-state"
NO_RED_PROOF = "verdict-no-red-proof"
# MW-130: which case of the red proof holds (the shell's `verdict_add.red_proven`); one reason id, four true texts
RED_PROVEN, RED_NO_ROW, RED_NOT_IN_HEAD, RED_OUT_OF_TIME, RED_UNREADABLE = "proven", "i", "ii", "iii", "iv"
RED_WAY_OUT = "commit the card's red tests (the commit gate records the row), then call again"
NODE_UNKNOWN = "verdict-node-unknown"
BY_COMMITTER = "verdict-by-committer"
STALE = "verdict-stale"
NO_READER_RUN = "verdict-no-reader-run"
RUNS_EXCEEDED = "verdict-runs-exceeded"
RUN_BEFORE_RECUT = "verdict-run-before-recut"
UNGUARDED = "verdict-reader-unguarded"  # card MW-116, R287c
REASONS = (NOT_ENFORCED, BY_OWNER, NO_CALLER, BY_HOLDER, CARD_STATE, NO_RED_PROOF, NODE_UNKNOWN, BY_COMMITTER, STALE, NO_READER_RUN,
           RUNS_EXCEEDED, RUN_BEFORE_RECUT)  # UNGUARDED (MW-116) is judged after the run is chosen, see `_judge`; it is not listed
ALWAYS = (BY_HOLDER, BY_COMMITTER, BY_OWNER, STALE, NO_CALLER, UNGUARDED)  # refused in both modes
MAX_RUNS = 2
WAITING, OPEN = "waiting", "open"
SESSION = "session:"
SHORT = 12  # characters of a sha in a text


@dataclass(frozen=True)
class Node:
    name: str
    known: bool = True
    committers: frozenset = frozenset()
    commit: str = ""  # the sha of the last commit that touched the test file; empty: none
    head_blob: str = ""  # the blob of the test file at HEAD; empty: none
    file_blob: str = ""  # the blob of the test file as it is now; empty: none
    readers: Tuple[str, ...] = ()  # agent ids of every checker end row of the caller's session, in order of their end
    fresh: Tuple[str, ...] = ()  # of those, the ones that started after the last commit of the test file
    used: Tuple[str, ...] = ()  # the reader runs used for this node since its last recut, in order (card MW-100)
    since_recut: Optional[Tuple[str, ...]] = None  # None: never recut; else the readers that started after the recut record
    acceptance: str = ""  # the Acceptance extract of this node (MW-117); the core never reads it, the shell hashes it into the record


@dataclass(frozen=True)
class Facts:
    caller: str = ""
    owner: bool = False
    status: str = ""
    holder: str = ""
    ever_held: frozenset = frozenset()
    nodes: Tuple[Node, ...] = ()
    checkers_missing: bool = False
    verdicts_off: bool = False
    mode: str = ""
    red_proven: bool = False  # the card has a red-proof row of a commit of HEAD (MW-117); not proven unless the shell says so
    red_case: str = ""  # MW-130: when not proven, which text: "" or RED_NO_ROW (i), RED_NOT_IN_HEAD (ii), RED_OUT_OF_TIME (iii), RED_UNREADABLE (iv)
    red_checked: int = 0  # (iii): the commits whose tree was digested before the legacy search ran out of time
    red_seconds: float = 0.0  # (iii): the wall-time cap of that search
    guard: Mapping[str, str] = field(default_factory=dict)  # reader run (agent id) -> why it is unguarded; absent or empty: guarded
    guard_sha: Mapping[str, str] = field(default_factory=dict)  # reader run -> the sha256 of the allow file it read under


@dataclass(frozen=True)
class Refusal:
    node: str
    reason: str
    text: str


@dataclass(frozen=True)
class Verdict:
    refusals: Tuple[Refusal, ...] = ()
    watched: Tuple[Refusal, ...] = ()
    run: str = ""
    number: int = 0

    @property
    def allowed(self) -> bool:
        return not self.refusals


def _same(a: str, b: str) -> bool:
    """Two session ids for comparing: spaces off, lower case, a `session:` prefix ignored."""
    def plain(text):
        value = (text or "").strip().casefold()
        return value[len(SESSION):].strip() if value.startswith(SESSION) else value
    return plain(a) != "" and plain(a) == plain(b)


def _short(sha: str) -> str:
    return sha[:SHORT] if sha else "none"


def _node(node: Node, caller: str):
    """The one refusal of a node, or None."""
    if not node.known:
        return Refusal(node.name, NODE_UNKNOWN, f"{node.name}: {NODE_UNKNOWN}: the card's Acceptance rows do not name this "
                                                f"node, so no verdict row is written for it")
    if any(_same(caller, s) for s in node.committers):
        return Refusal(node.name, BY_COMMITTER, f"{node.name}: {BY_COMMITTER}: the caller committed the test file (the "
                                                f"commit gate's record); a session that did not commit the test gives "
                                                f"the verdict")
    if not node.commit or node.head_blob != node.file_blob:
        what = ("the test file has no commit" if not node.commit else
                f"the test file is not HEAD's text: HEAD holds {_short(node.head_blob)}, the file now is "
                f"{_short(node.file_blob)}")
        return Refusal(node.name, STALE, f"{node.name}: {STALE}: {what}; commit the change, run a fresh reader on the "
                                         f"committed text, then call again")
    if not node.readers:
        return Refusal(node.name, NO_READER_RUN, f"{node.name}: {NO_READER_RUN}: this session ran no agent of a "
                                                 f"configured checker type; run a fresh reader on the committed test "
                                                 f"file, then call again")
    if not node.fresh:
        return Refusal(node.name, STALE, f"{node.name}: {STALE}: no checker run of this session started after the last "
                                         f"commit {_short(node.commit)} of the test file, so the reader read an older "
                                         f"text; run a fresh reader, then call again")
    return None


def _run(f: Facts):
    """(the reader run of the call, its number for the node, the refusal when there is none): a run fresh for every node;
    for a recut node, one that started after the recut record; a run already used for the node before a new one; a node whose
    budget (`MAX_RUNS` distinct runs since its last recut) is spent takes no new run."""
    first, *rest = f.nodes
    common = tuple(dict.fromkeys(r for r in first.fresh if all(r in n.fresh for n in rest)))
    if not common:
        return "", 0, Refusal("", STALE, f"{STALE}: no single checker run started after the last commit of every test "
                                         f"file of this call; call once per test file, or run a fresh reader after the "
                                         f"last of those commits")
    cut = [n for n in f.nodes if n.since_recut is not None]
    if cut:
        common = tuple(r for r in common if all(r in n.since_recut for n in cut))
        if not common:
            names = ", ".join(n.name for n in cut)
            return "", 0, Refusal("", RUN_BEFORE_RECUT, f"{RUN_BEFORE_RECUT}: {names} was re-cut after every fresh run of "
                                                       f"this call started; a run used or started before a recut never "
                                                       f"judges the new cut: run a fresh reader that starts after the "
                                                       f"recut, then call again")
    spent = [r for r in common if any(r not in n.used and len(n.used) >= MAX_RUNS for n in f.nodes)]
    open_runs = [r for r in common if r not in spent]
    if not open_runs:
        full = next(n for n in f.nodes if len(n.used) >= MAX_RUNS)
        return "", 0, Refusal("", RUNS_EXCEEDED, f"{RUNS_EXCEEDED}: {full.name} has used {len(full.used)} reader runs since "
                                                 f"its cut ({', '.join(full.used[:MAX_RUNS])}), at most {MAX_RUNS} are "
                                                 f"allowed; the run of this call ({common[-1]}) would be another; the lead "
                                                 f"changes the row's words or the test, commits, and runs `mkway verdict "
                                                 f"recut <card> <node> <reason>`, then a fresh reader judges the new cut")
    used = [r for r in open_runs if any(r in n.used for n in f.nodes)]
    run = (used or open_runs)[-1]
    return run, max((n.used.index(run) if run in n.used else len(n.used)) + 1 for n in f.nodes), None


def _no_red_proof_text(f: Facts) -> str:
    """The one text of `verdict-no-red-proof` that is true for the case the shell found (card MW-130, R313 8, R313a)."""
    head = f"{NO_RED_PROOF}: "
    if f.red_case == RED_NOT_IN_HEAD:
        return (head + f"the card's red-proof rows name trees that no commit of HEAD has, so the red commit was never made "
                       f"on this branch; {RED_WAY_OUT}")
    if f.red_case == RED_OUT_OF_TIME:
        return (head + f"the search for the commit of the card's older red-proof row (no git tree) ran out of time (limit "
                       f"{f.red_seconds:g} s) after {f.red_checked} commits checked; {RED_WAY_OUT}")
    if f.red_case == RED_UNREADABLE:
        return head + "the git history of HEAD could not be read, so the card's red-proof rows could not be checked; repeat the call"
    return head + f"the card has no red-proof row, so its tests were never proved red; {RED_WAY_OUT}"


def _judge(f: Facts):
    """(every refusal in order, the run the call uses or empty)."""
    if f.checkers_missing or f.verdicts_off:
        key = "`outbox.checkers` is missing in the profile, so no reader can be proved" if f.checkers_missing else (
            "`cards.verdicts` is off in the profile, so the close does not read verdicts")
        return [Refusal("", NOT_ENFORCED, f"{NOT_ENFORCED}: {key}; the owner sets that key")], "", 0
    if f.owner:
        return [Refusal("", BY_OWNER, f"{BY_OWNER}: the verdict is never the owner's; a reader session that did not build "
                                      f"or commit the card's tests runs this command")], "", 0
    if not (f.caller or "").strip():
        return [Refusal("", NO_CALLER, f"{NO_CALLER}: no hook check of this call was found (none, used, or too old), so "
                                       f"the session id is not established; run the command alone, in its plain form, "
                                       f"in a session with the engine hooks")], "", 0
    found = []
    if any(_same(f.caller, s) for s in f.ever_held):
        found.append(Refusal("", BY_HOLDER, f"{BY_HOLDER}: the caller took this card once; a session that built the card "
                                            f"never gives a verdict on it, not even after it released the card"))
    if f.status not in (WAITING, OPEN):
        found.append(Refusal("", CARD_STATE, f"{CARD_STATE}: the card is {f.status or 'not established'}; a verdict is "
                                             f"written while the card is waiting or open (a builder may still hold it), "
                                             f"never when it is closed, proposed or waiting for the owner"))
    if not f.red_proven:
        found.append(Refusal("", NO_RED_PROOF, _no_red_proof_text(f)))
    nodes = [_node(n, f.caller) for n in f.nodes]
    found += [r for r in nodes if r is not None]
    if f.nodes and not any(nodes):
        run, number, refusal = _run(f)
        if refusal is None and f.guard.get(run):
            refusal = Refusal("", UNGUARDED, f"{UNGUARDED}: {f.guard[run]}")
        return found + ([refusal] if refusal else []), run, number
    return found, "", 0


def decide(facts: Facts) -> Verdict:
    found, run, number = _judge(facts)
    watch = facts.mode == WATCH
    blocking = tuple(r for r in found if not watch or r.reason in ALWAYS)
    watched = tuple(r for r in found if r not in blocking)
    if blocking:
        return Verdict(blocking, watched)
    return Verdict((), watched, run, number)
