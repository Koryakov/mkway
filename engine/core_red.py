"""The decision of the red proof (card MW-072, ruling R177 gaps 1 and 2, ruling R183): a pure core. No input, no output, no
git, no clock, no process. `decide(facts)` reads one `Facts` record the shell (`engine/gate_commit_tests.py`) built and
gives a `Verdict`: the refusals (at most one per test, file or reason), the ids to record as red, as pins, as `Checks:`
guards, and the file -> module of each red-by-missing file.

Two kinds of commit (`Facts.code` says which): a tests-only commit (no code file), a commit with code.
- tests-only: every new test id (defined by a changed test file in the committed tree, not in HEAD's) must be red. A failing test is red. A
  test file that fails at collection with an ImportError, ModuleNotFoundError or AttributeError whose missing module lies
  in the card's own Paths is red by missing that module; any other collection error, a setup error, and a file with no
  new test are `red-not-proven`. A new id that passes is allowed only through `_passing_new_id` (the one place the rule
  of a passing new test lives): a declared pin (card kind refactor or migration, a `Pins:` docstring, an Acceptance row
  that names it as pinning) or a `Checks:` guard beside at least one red id of the same commit (ruling R183).
- with code: a new id is allowed only when the red record holds it or it is a declared pin (`test-without-red-proof`); the
  card needs a record in this root (`red-not-recorded`); every recorded red id must now pass, a deleted, renamed, skipped
  or failing one is `red-ids-still-red`.
A session that holds no card is not judged (no record can be keyed).

`parse_case_map(text)` (card MW-089) is the one reader of a card's `case_map.md`: it gives one `CaseMapLine` per line.

The case_map rules (card MW-090, rulings R219 to R225, refusals only): when a commit stages the card's `case_map.md`
(`Facts.case_map` is its committed text), the lines new against HEAD's are judged, in a tests-only and in a code commit.
A new mapping or dropped line needs a counting decision (`case-map-no-decision`); under one, its left side must be a test of
its file at HEAD, gone from the committed tree and in no other card's red record (`case-map-unknown-left`), its right side a
test of its file in the committed tree (`case-map-unknown-right`); one right side appears in at most one mapping line and
never names a test that exists at HEAD (`case-map-merge`); a line the parser calls malformed, a side with a `[case]` suffix
and a left side that is not in exactly one kind of line are `case-map-malformed`. These refusals come first in the verdict,
so the reason id of the commit is a case_map one when the case_map is bad. A valid line changes nothing yet.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Mapping, NamedTuple, Optional, Tuple

import helpers

NOT_PROVEN = "red-not-proven"
STILL_RED = "red-ids-still-red"
NOT_RECORDED = "red-not-recorded"
WITHOUT_PROOF = "test-without-red-proof"
REASON_IDS = (NOT_PROVEN, STILL_RED, NOT_RECORDED, WITHOUT_PROOF)
# card MW-131 (R322): the id of the allow line that names the legacy rows the search limit left out; a `warn`, never a refusal
PARTIAL = "red-record-partial"
# card MW-131 (R314 7): why the card has no red record, the cause the shell passes in `Facts.record_cause`; one text each
CAUSE_NO_ROW = "no-row"  # the card has no row that holds a red id, a pin or a missing file
CAUSE_NOT_IN_HISTORY = "not-in-history"  # rows exist, but none names a commit of HEAD
CAUSE_OUT_OF_TIME = "out-of-time"  # the search limit ran out and no row was found
CAUSE_UNREADABLE = "unreadable"  # the git history of HEAD could not be read
CM_NO_DECISION = "case-map-no-decision"
CM_UNKNOWN_LEFT = "case-map-unknown-left"
CM_UNKNOWN_RIGHT = "case-map-unknown-right"
CM_MERGE = "case-map-merge"
CM_MALFORMED = "case-map-malformed"
CASE_MAP_REASONS = (CM_NO_DECISION, CM_UNKNOWN_LEFT, CM_UNKNOWN_RIGHT, CM_MERGE, CM_MALFORMED)  # the order the refusals are listed in
CASE_MAP_CAP = 10  # lines named per reason; the rest are counted (R220)
_COUNTED = ("mapping", "dropped")
PIN_KINDS = ("refactor", "migration")
PASSED, FAILED, SKIPPED, GONE = "passed", "failed", "skipped", "gone"

_NO_MODULE = re.compile(r"^(?:ModuleNotFoundError|ImportError): No module named '?([\w.]+)'?")
_NO_NAME = re.compile(r"^ImportError: cannot import name '[^']+' from '([\w.]+)'")
_NO_ATTRIBUTE = re.compile(r"^AttributeError: module '([\w.]+)' has no attribute")
_MAP_LINE = re.compile(r"^(\S+\.py::\S+) -> (?:(\S+\.py::\S+)|dropped: (\S.*))$")
_KEPT_DASH = re.compile(r"^# kept: (tests/\S+\.py::\w+) - (\S.*)$")
_KEPT_PAREN = re.compile(r"^# kept: (tests/\S+\.py::\w+) \((.+)\)$")


class CaseMapLine(NamedTuple):
    """One line of a case_map.md: its 1-based number, its raw text (unstripped), its kind (`blank`, `comment`, `mapping`,
    `dropped`, `malformed`) and the fields of that kind; a field that does not belong to the kind is None."""
    number: int
    raw: str
    kind: str
    old: Optional[str] = None  # mapping, dropped: the left side as written
    new: Optional[str] = None  # mapping: the right side as written
    why: Optional[str] = None  # dropped: the text after `dropped: `
    kept_id: Optional[str] = None  # comment `# kept: <id> - <why>` or `# kept: <id> (<why>)`
    kept_why: Optional[str] = None


def parse_case_map(text: str) -> List[CaseMapLine]:
    """Every line of `text` as one `CaseMapLine`, in order; the kind is decided on the stripped line. A split is several
    lines with the same left side, each its own entry. The grammar is the widest one in use; narrower rules belong to the
    readers."""
    out = []
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            out.append(CaseMapLine(number, raw, "blank"))
        elif line.startswith(("#", ">")):
            kept = _KEPT_DASH.match(line) or _KEPT_PAREN.match(line)
            out.append(CaseMapLine(number, raw, "comment", kept_id=kept and kept.group(1), kept_why=kept and kept.group(2)))
        else:
            m = _MAP_LINE.match(line)
            if m is None:
                out.append(CaseMapLine(number, raw, "malformed"))
            elif m.group(3) is None:
                out.append(CaseMapLine(number, raw, "mapping", m.group(1), m.group(2)))
            else:
                out.append(CaseMapLine(number, raw, "dropped", m.group(1), why=m.group(3)))
    return out


class Decision(NamedTuple):
    """One decision the commit message names (a match of `tests.red_proof.decision_pattern`) and what the shell found in the
    root's ledger: with no ledger file the defaults stand (a row, not closed, not by this session)."""
    ident: str
    in_ledger: bool = True  # False: the root has a ledger and it holds no row with this id
    closed: str = ""  # the row's status when the ledger's own closed statuses hold it (withdrawn, superseded)
    by_self: bool = False  # the row's by is the committing session


def _why_not(d: Decision) -> str:
    """Why `d` does not count as the decision of a line; empty when it counts."""
    if not d.in_ledger:
        return f"{d.ident}: it is not a row of the ledger"
    if d.closed:
        return f"{d.ident}: its status is {d.closed}"
    if d.by_self:
        return f"{d.ident}: it is by this session"
    return ""


@dataclass(frozen=True)
class Record:
    """What the root's red record holds for the card: the red ids, the declared pins, the red-by-missing files."""
    red: frozenset = frozenset()
    pins: frozenset = frozenset()
    files: frozenset = frozenset()


@dataclass(frozen=True)
class Facts:
    card: str  # the card the session holds; empty: not judged
    kind: str = ""  # the card's declared kind: `refactor`, `migration` or empty
    paths: Tuple[str, ...] = ()  # the card's Paths, repo-relative
    code: bool = False  # the commit stages a file that is neither a test nor a document
    new_ids: Tuple[str, ...] = ()  # test ids (base ids, no `[case]`) a changed test file defines and HEAD's does not
    failed: frozenset = frozenset()  # ids that fail in the committed tree
    errored: Mapping[str, str] = field(default_factory=dict)  # id -> message: errors at setup
    file_errors: Mapping[str, str] = field(default_factory=dict)  # changed test file -> first error line at collection
    file_new: Mapping[str, Tuple[str, ...]] = field(default_factory=dict)  # file -> its test ids new in the commit
    pin_docstring: frozenset = frozenset()  # new ids whose docstring starts `Pins:`
    pin_rows: frozenset = frozenset()  # new ids an Acceptance row names as pinning
    checks_docstring: frozenset = frozenset()  # new ids whose docstring starts `Checks:`
    record: Optional[Record] = None  # None: no record of the card in this root
    record_cause: str = ""  # card MW-131: why `record` is None, one of the CAUSE_* constants; empty reads as CAUSE_NO_ROW
    record_checked: int = 0  # card MW-131: the git trees the search digested (text of CAUSE_OUT_OF_TIME)
    record_limit: float = 0  # card MW-131: the search limit in seconds (text of CAUSE_OUT_OF_TIME)
    outcomes: Mapping[str, str] = field(default_factory=dict)  # recorded red id -> passed, failed, skipped, gone
    # card MW-090: the card's case_map.md. None: the commit does not stage it, no case_map rule runs
    case_map: Optional[str] = None  # its text in the committed tree
    case_map_head: str = ""  # its text at HEAD ("" when HEAD has none)
    decisions: Tuple[Decision, ...] = ()  # the decisions the commit message names; none: no match, or no usable pattern
    test_roots: Tuple[str, ...] = ()  # the profile's test roots
    head_ids: frozenset = frozenset()  # static test ids at HEAD of the files the new lines' sides name
    tree_ids: frozenset = frozenset()  # the same in the committed tree
    other_red: Mapping[str, str] = field(default_factory=dict)  # id -> card of the red records of the other cards


@dataclass(frozen=True)
class Refusal:
    reason: str
    text: str


@dataclass(frozen=True)
class Verdict:
    refusals: Tuple[Refusal, ...] = ()
    red: Tuple[str, ...] = ()
    pins: Tuple[str, ...] = ()
    checks: Tuple[str, ...] = ()
    missing: Mapping[str, str] = field(default_factory=dict)

    @property
    def allowed(self) -> bool:
        return not self.refusals


def _lies_in(module: str, paths) -> bool:
    """The file of `module` (`a.b` is `a/b.py` or `a/b/__init__.py`) lies in the card's Paths: a file entry that ends with
    that path (a module on the import path by its bare name), any entry `helpers.matches` takes for the path, or an entry
    that starts with the module's folder (`src` for `src/feature.py`: R217a, a new package in a folder that does not exist
    yet is the normal case, and Python then says `No module named 'src'`, the package, not the file)."""
    rel = module.replace(".", "/")
    for candidate in (f"{rel}.py", f"{rel}/__init__.py"):
        for entry in paths:
            e = entry.replace("\\", "/").strip().rstrip("/")
            if helpers.matches(candidate, entry) or (e.endswith(".py") and (e == candidate or e.endswith("/" + candidate))):
                return True
            if e.startswith(rel + "/"):
                return True
    return False


def missing_module(line: str, paths) -> Optional[str]:
    """The module an error line says is missing (ModuleNotFoundError, ImportError, AttributeError of a module) when its
    file lies in `paths`; None for any other error and for a module outside the Paths."""
    for pattern in (_NO_MODULE, _NO_NAME, _NO_ATTRIBUTE):
        found = pattern.match((line or "").strip())
        if found:
            return found.group(1) if _lies_in(found.group(1), paths) else None
    return None


def in_record(ident: str, ids) -> bool:
    """`ident` is one of `ids`, or a parametrized case of one (`id[case]`)."""
    return any(ident == r or ident.startswith(r + "[") for r in ids)


def _is_pin(ident: str, f: Facts) -> bool:
    return f.kind in PIN_KINDS and ident in f.pin_docstring and ident in f.pin_rows


def _passing_new_id(ident: str, f: Facts, has_red: bool):
    """The one rule of a new test that passes in a tests-only commit: ('pin' | 'checks', '') when it is allowed, else
    (None, the reason it is not). Ruling R183: a `Checks:` guard beside a red id; pinning for refactor and migration."""
    if _is_pin(ident, f):
        return "pin", ""
    if ident in f.checks_docstring and has_red:
        return "checks", ""
    why = "it passes before any code change, so it has not been seen to fail"
    if f.kind in PIN_KINDS:
        if ident not in f.pin_docstring:
            why += f"; a pin of a {f.kind} card needs the docstring `Pins:`"
        if ident not in f.pin_rows:
            why += "; a pin needs an Acceptance row that names it as pinning"
    elif ident in f.checks_docstring:
        why += "; a `Checks:` test is allowed only beside a red id of the same commit"
    return None, why


def _tests_only(f: Facts, refusals: list):
    red, pins, checks, missing = [], [], [], {}
    for file, line in f.file_errors.items():
        module = missing_module(line, f.paths)
        news = f.file_new.get(file, ())
        if module is None:
            refusals.append(Refusal(NOT_PROVEN, f"{file}: {NOT_PROVEN}: the file fails to collect ({line}); that is red only "
                                                f"for a missing module or name that lies in the card's Paths"))
        elif not news:
            refusals.append(Refusal(NOT_PROVEN, f"{file}: {NOT_PROVEN}: the file fails to collect ({line}) and holds no new "
                                                f"test, so it breaks tests that were green and proves nothing new"))
        else:
            red.extend(news)
            missing[file] = module
    greens = []
    for ident in f.new_ids:
        if ident in f.failed:
            red.append(ident)
        elif ident in f.errored:
            module = missing_module(f.errored[ident], f.paths)
            if module is None:
                refusals.append(Refusal(NOT_PROVEN, f"{ident}: {NOT_PROVEN}: it errors at setup ({f.errored[ident]}), "
                                                    f"which is a broken test, not a red one"))
            else:
                red.append(ident)
                missing[ident.split("::", 1)[0]] = module
        else:
            greens.append(ident)
    for ident in greens:
        kind, why = _passing_new_id(ident, f, bool(red))
        if kind == "pin":
            pins.append(ident)
        elif kind == "checks":
            checks.append(ident)
        else:
            refusals.append(Refusal(NOT_PROVEN, f"{ident}: {NOT_PROVEN}: {why}"))
    return tuple(red), tuple(pins), tuple(checks), missing


def not_recorded_text(f: Facts) -> str:
    """The text of `red-not-recorded` after its id, one true text per cause (card MW-131, R314 7; the wording of R324). The ways
    out need no owner: (i) no row: commit the failing tests first, alone, then the code (or the code in the checkout where they
    were committed); (ii) rows no commit of HEAD has: the code where the red tests were committed, or a failing test of the card
    first; (iii) the search limit ran out: a further tests-only red commit renews the record; (iv) the history could not be
    read: repeat the call."""
    if f.record_cause == CAUSE_NOT_IN_HISTORY:
        return (f"{f.card} has red record rows, but none of them belongs to a commit in the history of HEAD: the red commit "
                f"was not made, or it sits on a branch that is not merged here; commit the code where the red tests were "
                f"committed, or, if they were never committed, commit a failing test of the card first, alone (the gate runs "
                f"it and records the red), then commit the code")
    if f.record_cause == CAUSE_OUT_OF_TIME:
        return (f"the search for the older red record rows of {f.card} (written with no git tree) ran out of time "
                f"(limit {f.record_limit:g} s) after {f.record_checked} git trees checked, and no row was found; commit a "
                f"failing test of the card, alone (the gate runs it and records the red; a further tests-only red commit "
                f"renews the record), then commit the code")
    if f.record_cause == CAUSE_UNREADABLE:
        return f"the git history of HEAD could not be read, so the red record of {f.card} could not be checked; repeat the call"
    return (f"{f.card} has no red record: no tests-only commit of the card was recorded as red; commit the failing tests "
            f"first, alone (the gate runs them and records the red), then commit the code; if they were committed in another "
            f"checkout, commit the code there")


def partial_text(card: str, times, limit) -> str:
    """The line of the warn `red-record-partial` (card MW-131, R322; the wording of R324): the count and the times of the legacy
    rows (written with no git tree) that the search limit left out while at least one row was found. It names no way out: the
    check goes on with the rows found, and the line needs no action (the commit may still be refused for another reason)."""
    shown = ", ".join(times[:5]) + (f", and {len(times) - 5} more" if len(times) > 5 else "")
    return (f"{PARTIAL}: the red record of {card} was read without {len(times)} older row(s) written with no git tree "
            f"(times {shown}) because the search for them ran out of time (limit {limit:g} s); the check goes on with the "
            f"rows that were found; this line needs no action")


def _with_code(f: Facts, refusals: list) -> None:
    held = f.record.red if f.record else frozenset()
    unrecorded = [i for i in f.new_ids if not in_record(i, held) and not _is_pin(i, f)]
    if unrecorded:
        refusals.append(Refusal(WITHOUT_PROOF, f"{WITHOUT_PROOF}: new test(s) committed with code and not in the red record "
                                               f"of {f.card}: {'; '.join(unrecorded)}; commit the test first, alone, and "
                                               f"see it fail, then commit the code"))
    elif f.record is None and not f.new_ids:
        refusals.append(Refusal(NOT_RECORDED, f"{NOT_RECORDED}: {not_recorded_text(f)}"))
    if f.record is None:
        return
    what = {FAILED: "it still fails", GONE: "it was deleted or renamed (it is no longer collected)",
            SKIPPED: "it is skipped"}
    for ident in sorted(f.record.red):
        outcome = f.outcomes.get(ident, GONE)
        if outcome != PASSED:
            refusals.append(Refusal(STILL_RED, f"{ident}: {STILL_RED}: a recorded red test must now pass, and {what.get(outcome, 'it did not pass')}"))


def case_map_new(text: str, head: str) -> List[CaseMapLine]:
    """The lines of `text` that are new against `head`, judged by the case_map rules (R223 2): the mapping, dropped and
    malformed lines whose stripped text is no line of `head`'s, each text once, in order. Blank and comment lines are never
    judged, and a line removed against HEAD is not in `text` at all."""
    seen = {line.strip() for line in head.splitlines()}
    out = []
    for line in parse_case_map(text):
        key = line.raw.strip()
        if line.kind != "blank" and line.kind != "comment" and key not in seen:
            seen.add(key)
            out.append(line)
    return out


def _file_of(side: str) -> str:
    return side.split("::", 1)[0]


def _under(side: str, roots) -> bool:
    """The file of a side lies under a test root."""
    return any(helpers.matches(_file_of(side), root) for root in roots)


def case_map_files(text: str, head: str, roots) -> List[str]:
    """The files the shell must read to judge `text`: the file of each side of each new line, when it lies under a test
    root; sorted. A side outside the test roots is unknown whatever its file holds, so it is not read."""
    files = set()
    for line in case_map_new(text, head):
        for side in (line.old, line.new):
            if side and _under(side, roots):
                files.add(_file_of(side))
    return sorted(files)


def _left_fact(f: Facts, left: str) -> str:
    """The first fact that makes the left side of a mapping or dropped line unknown (R223 4, R225 6); empty when it holds."""
    if not _under(left, f.test_roots) or left not in f.head_ids:
        return f"{left} is not a test id of its file at HEAD under a test root"
    if left in f.tree_ids:
        return f"{left} still exists in the committed tree, so the line copies the test and is no rename or drop"
    if left in f.other_red:
        return f"{left} is in the red record of {f.other_red[left]}, which belongs to that card"
    return ""


def _merge_fact(f: Facts, line: CaseMapLine, lefts) -> str:
    """The merge a new mapping line makes (R225 2, R225a), empty when it makes none: several lefts for its right side, or a
    right side that exists at HEAD."""
    form = f"-> dropped: merged into {line.new}, <why>"
    if len(lefts) > 1:
        return (f"{line.new} is the right side of {len(lefts)} mapping lines ({', '.join(lefts)}): one right side appears in "
                f"at most one mapping line; write `{lefts[0]} -> {line.new}` and, for each other left, `<left> {form}`")
    if line.new in f.head_ids:
        return (f"{line.new} already exists at HEAD, so the line merges into an existing test: write "
                f"`{line.old} {form}`")
    return ""


def _kinds_fact(left: str, group) -> str:
    """One left side appears in exactly one kind of line: all mappings (a split), or one dropped line (R225a)."""
    dropped = sum(1 for line in group if line.kind == "dropped")
    if dropped and dropped < len(group):
        return (f"{left} has a mapping line and a dropped line: one left side appears in exactly one kind of line, all "
                f"mappings (a split) or one dropped line")
    return f"{left} has {dropped} dropped lines: it has exactly one" if dropped > 1 else ""


def _case_map(f: Facts) -> list:
    """The refusals of the case_map rules, in the order of `CASE_MAP_REASONS`, at most `CASE_MAP_CAP` lines per reason."""
    if f.case_map is None:
        return []
    fresh = case_map_new(f.case_map, f.case_map_head)
    found = {reason: [] for reason in CASE_MAP_REASONS}

    def refuse(reason: str, line: CaseMapLine, fact: str) -> None:
        found[reason].append(f"case_map.md line {line.number} `{line.raw.strip()}`: {reason}: {fact}")

    whole = {}  # distinct stripped texts of the whole committed map (old and new lines): a new line may clash with an old one
    for line in parse_case_map(f.case_map):
        if line.kind in _COUNTED and "[" not in line.old + (line.new or ""):
            whole.setdefault(line.raw.strip(), line)
    by_right, by_left = {}, {}
    for line in whole.values():
        by_left.setdefault(line.old, []).append(line)
        if line.kind == "mapping":
            by_right.setdefault(line.new, []).append(line)
    asked = [line for line in fresh if line.kind in _COUNTED]
    plain = [line for line in asked if line.raw.strip() in whole]  # a side with a `[case]` suffix is not in `whole`
    counting = [d for d in f.decisions if not _why_not(d)]
    if asked and not counting:
        why = "; ".join(_why_not(d) for d in f.decisions) or (
            "the commit message holds no match of tests.red_proof.decision_pattern (an empty or unusable pattern is no decision)")
        found[CM_NO_DECISION].append(f"{CM_NO_DECISION}: {len(asked)} new mapping or dropped line(s) in case_map.md and no "
                                     f"decision counts ({why}); a line is honoured only in a commit whose message names a "
                                     f"decision that counts")
    merges, clashes = {}, {}
    for line in plain:
        if counting:
            fact = _left_fact(f, line.old)
            if fact:
                refuse(CM_UNKNOWN_LEFT, line, fact)
            if line.kind == "mapping" and (not _under(line.new, f.test_roots) or line.new not in f.tree_ids):
                refuse(CM_UNKNOWN_RIGHT, line, f"{line.new} is not a test id of its file in the committed tree under a test root")
            merge = _merge_fact(f, line, sorted({m.old for m in by_right.get(line.new, ())})) if line.kind == "mapping" else ""
            if merge:
                merges.setdefault(line.new, (line, merge))
        clash = _kinds_fact(line.old, by_left[line.old])
        if clash:
            clashes.setdefault(line.old, (line, clash))
    for line, fact in merges.values():
        refuse(CM_MERGE, line, fact)
    for line in fresh:
        if line.kind == "malformed":
            refuse(CM_MALFORMED, line, "the line is neither `<old> -> <new>` nor `<old> -> dropped: <why>`")
        elif line.raw.strip() not in whole:
            refuse(CM_MALFORMED, line, "a side has a [case] suffix: a side is a function-level base id")
    for line, fact in clashes.values():
        refuse(CM_MALFORMED, line, fact)
    out = []
    for reason, texts in found.items():
        out += [Refusal(reason, text) for text in texts[:CASE_MAP_CAP]]
        if len(texts) > CASE_MAP_CAP:
            out.append(Refusal(reason, f"{reason}: {len(texts) - CASE_MAP_CAP} more refused line(s) of the same reason, "
                                       f"see the card's case_map.md"))
    return out


def decide(f: Facts) -> Verdict:
    """The verdict of one commit; see the module text."""
    if not f.card:
        return Verdict()
    refusals: list = _case_map(f)
    if f.code:
        _with_code(f, refusals)
        return Verdict(tuple(refusals), pins=tuple(i for i in f.new_ids if _is_pin(i, f)))
    red, pins, checks, missing = _tests_only(f, refusals)
    return Verdict(tuple(refusals), red, pins, checks, missing)
