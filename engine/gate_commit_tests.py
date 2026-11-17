"""The commit gate (card MW-005): tests before a commit, red test first, no red commit.

A `git commit` of a session (PreToolUse, Bash and PowerShell, shell group, after the lock gate) runs the project's tests
first, and the tests run on the STAGED tree, never on the working tree (an untracked conftest must not make a commit
pass). The index is exported with `git checkout-index -a -f --prefix=<folder>/` into a folder under the state
dir, the suite runs there, and the folder is removed. The rules:
- the tree tested is the tree git will commit (card MW-060), read through `gate_commit.taken`, the one reader the file
  gate uses: a plain commit is the index, `-a` the index plus every modified tracked file, `-i -- <paths>` the index
  plus the named paths, `-- <paths>` (`--only`, `-o`) HEAD plus the named paths as the working tree has them and
  nothing else of the index; an untracked file is never in it. Built in a temporary index file (`tree_plan` says what
  it must hold, and a difference refuses); the real index is never changed, and the key of a result row is the digest
  of the tree built, never of the real index; a message-only amend (`--amend` with `--only` or `-o`, no paths) changes
  no file: nothing to test;
- every staged file under `test_roots`: the red-first commit. A session that holds a card, with a pytest command, is
  judged by the red proof (card MW-072, `core_red.decide`): the suite runs on the committed tree, each new test id must
  be red (red by missing a module of the card's Paths counts), the red ids go to `<state.dir>/red_proof.jsonl` by card; a
  code commit needs that record and every recorded id passing; a new id committed with code needs the record. The
  refusals are `red-not-proven`, `red-ids-still-red`, `red-not-recorded`, `test-without-red-proof`; `tests.red_proof.mode`
  `watch` writes the record and a warning and allows. Any other session or command: no run, tests alone may be red;
  card MW-090: a commit that stages the card's `case_map.md` (a documents-only commit too, with no suite run) has its new
  lines judged under a decision the commit message names (`tests.red_proof.decision_pattern`, and the ledger when the root
  has one): `case-map-no-decision`, `case-map-unknown-left`, `case-map-unknown-right`, `case-map-merge`,
  `case-map-malformed`; they stand before the red proof's reasons and follow `tests.red_proof.mode` too;
- every staged file matches `paths.docs`: no run;
- otherwise the command (`tests.command`, default `python -m pytest -q` over the `test_roots`) runs with the
  environment names of `test_env`, `ENGINE_TERMS_FILE` and the system essentials (SESSION_ENV: the folders Python and
  Windows need to find installed packages included, MW-057) only; a red run refuses `commit-tests-failed` and names the
  first 10 failing test ids, for a file that failed at collection or import its first error line, the untracked
  files of the working tree when such a failure exists (MW-057), and the way out; a run over `gates.commit_tests.budget_seconds` is stopped and refused
  `commit-tests-over-budget`; a command that cannot start, or any git read that fails, refuses `commit-tests-not-run`
  (fail closed);
- one run per staged tree and command: a row of `<state.dir>/commit_tests.jsonl` holds the tree hash, the result and
  the duration; the same index is not run twice. A budget raised above the one an `over-budget` row ran under runs
  again;
- card MW-056, a commit is refused only for new red: a red staged tree is compared with the tree of HEAD (run once, kept
  in `<state.dir>/commit_tests_head.jsonl` by the tree of HEAD, ignored when `tests.command` or the profile changes).
  A test red now and not red at HEAD, a red test inside the committing card's Paths, and a test red at HEAD and now
  that no open card's Paths holds, refuse `commit-tests-failed`; a test red at HEAD and now inside another open card's
  Paths does not, and the allow line (a warn, `commit-tests-still-red`) says `<test id> still red, owned by <card id>`
  (`judge` decides);
- card MW-062, a test absent at HEAD (a red case HEAD's tree never collected, for example a parametrised case over
  files another card creates) is judged by its owner, the open card whose Paths hold the test FILE: another open card
  does not block and the allow line counts the cases per owner (`40 cases absent at HEAD, owned by <card id>`), the
  committing card refuses, no open card refuses as new red. A test collected at HEAD, green there, and red now stays
  new red. The ids HEAD collects are listed once per tree of HEAD (`commit_tests_collect.jsonl`), and only when a new
  red case lies in an open card's file. A pytest command also runs with `--continue-on-collection-errors` (the row keeps
  the command as the profile states it), so one file that fails at collection at HEAD does not stop the run and hide
  the red tests of other files;
- card MW-069, a test whose FILE failed at collection at HEAD (one bare file id among HEAD's failures) is red at HEAD
  for every id in it, never new red and never absent: owned by another open card it does not block and is listed;
  with a closed owner or none it blocks, and the refusal says the file was already red at HEAD and names the closed card;
- card MW-108, only the new red of THIS commit refuses (concept lines 2 and 5): a test red at HEAD and still red inside no
  open card's Paths (an orphan) never blocks, and one inside the committing card's Paths blocks only when its `card take`
  did not record it red (`inherited_red.jsonl`, `cardtool.Inherited`: the card's inherited red, which its close needs
  green). A card whose take record is not established, or whose take recorded the test green or holds no record of it,
  keeps the refusal, as new red, with the text that names the way out (R283). Old reds are allowed with the line
  `old red: <id>, owner <card>` (`owner none` for an orphan) and listed in the key `old_red` of the run's row of
  `commit_tests.jsonl`, `[{test, card}]`. The refusal of a new red also gives the plain form of the red-first commit.
  `head_red` is the one function that reads the red at HEAD for a take, from the kept rows (never a suite run);
- a staging command in the same shell command as the commit (`git add ... && git commit`) is refused
  `commit-tests-chained`: the index is read before the command runs, so it would be the wrong tree.
The program the engine runs is git or the profile's Python only (`runner`). No task name is in this file.
"""
from __future__ import annotations

import ast
import datetime
import hashlib
import json
import os
import re
import shlex
import shutil
import stat
import time
from pathlib import Path
from typing import NamedTuple

import cardtool
import core_red
import core_verdicts
import gate
import gate_commit
import helpers
import ledger
import logs
import profiles
import register
import runner
import shared_records

STATE_FILE = "commit_tests.jsonl"
HEAD_FILE = "commit_tests_head.jsonl"  # MW-056: the results of HEAD's tree, one row per run, by the tree of HEAD
COLLECT_FILE = "commit_tests_collect.jsonl"  # MW-062: the test ids HEAD's tree collects, one row per listing
# MW-114: the version of the reader of test ids that wrote a kept row. 1 = before MW-114 (an id cut at its first space), 2 = ids
# read whole. A kept listing or a kept failing run of another version is not reused: its ids would not match the whole ones.
READER = 2
RED_FILE = "red_proof.jsonl"  # MW-072: the red record, one row per allowed tests-only commit, by card
TREE_LIMIT = 60  # commits of HEAD searched for the tree of a red record row (MW-130: `verdict add` no longer uses it; MW-131: nor does the card's own record, `_record_of`; `_others_red` through `_record_rows`, and `_head_red`, do)
FOLDER ="commit_tests"  # `<state.dir>/commit_tests/`: the exports and temporary index files of a run
MAX_IDS = 10
HOOK_LIMIT = 840  # seconds: the manifest's hook timeout (900) less a margin for the exports and the log
GIT_SECONDS = 30
# MW-131 (R317 3, R323): the wall time the gate gives, in ONE call, to the digest search for the legacy rows of the card's own
# red record (ten digests at the slowest measured, 0.228 s, rounded up). The limit of `verdict add` is its own constant (60 s).
# Named limit: on a repository where one digest takes longer than this a legacy row cannot be found; legacy rows exist only in
# tasks installed before MW-130, and the one such task was measured.
OWN_RECORD_SEARCH_SECONDS = 3
_clock = time.perf_counter  # the clock of that limit (a test replaces it)
INDEX_CHANGERS = {"add", "rm", "mv", "restore", "reset", "checkout", "switch", "apply", "stash", "merge", "rebase",
                  "cherry-pick", "revert", "am", "pull", "update-index", "read-tree"}
SESSION_ENV = ("PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP", "TMPDIR", "HOME", "USERPROFILE",
               "LANG", "LC_ALL",
               # MW-057: what Python and Windows need to find the packages a person installed for their own user
               # (`pip install --user` lives under APPDATA), the program folders and the user's identity; no secret
               "APPDATA", "LOCALAPPDATA", "PROGRAMDATA", "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMW6432",
               "COMMONPROGRAMFILES", "SYSTEMDRIVE", "HOMEDRIVE", "HOMEPATH", "USERNAME", "USERDOMAIN",
               "PROCESSOR_ARCHITECTURE", "NUMBER_OF_PROCESSORS", "OS", "PYTHONUSERBASE", "PYTHONHOME")
ALWAYS_ENV = ("ENGINE_TERMS_FILE",)
SUMMARY_LINE = re.compile(r"^(FAILED|ERROR) (?=\S)(.*?)[ \t\r]*$", re.M)  # MW-114: a short-summary line, id and message not yet split
DASH = " - "  # between the id and the message of a short-summary line
COLLECT_HEAD = re.compile(r"^_+ ERROR collecting (.+?) _+[ \t]*$", re.M)  # a file that failed at collection or import
ERROR_LINE = re.compile(r"^E[ \t]+(\S.*?)[ \t]*$", re.M)  # a line of a pytest traceback that starts with `E`
EXCEPTION = re.compile(r"^[A-Za-z_][\w.]*(?:Error|Exception|Exit|Warning)\b")
MAX_LINE = 200  # characters of one shown error line
MAX_UNTRACKED = 5
OUT = "A refused commit changes nothing: the index and the working tree stay as they are."


class NotRun(Exception):
    """The tests could not be started or the staged tree could not be read: the commit is refused."""


class RecordBusy(NotRun):
    """MW-129 (R310 1 a): another writer holds the append lock of the red proof file beyond the bounded wait; the record was
    not written, so the commit is refused `shared-record-busy` (never a silent drop)."""


def _git(folder, *args, env=None, text=True):
    proc = runner.run(runner.GIT + ["-C", str(folder), *args], capture_output=True, text=text,
                      timeout=GIT_SECONDS, env=env)
    return proc


def _read(folder, *args, env=None, text=True):
    proc = _git(folder, *args, env=env, text=text)
    if proc.returncode != 0:
        raise NotRun(f"git {args[0]} failed (exit {proc.returncode}), so the staged tree could not be read")
    return proc.stdout


def staged_key(listing: bytes) -> str:
    """The `tree` key of a row: the sha256 of `git ls-files -s -z` as the gate reads the staged index (card MW-023)."""
    return hashlib.sha256(listing).hexdigest()


_digest_left = None  # MW-131: the time left of the running search for the `ls-tree` of one digest; None outside a search


def _listing(root, rev):
    """The bytes `git ls-files -s -z` prints for the index that equals commit `rev` (taken from `ls-tree -r -z`, which
    holds the same entries in the same order), or None when git cannot tell."""
    timeout = GIT_SECONDS if _digest_left is None else min(GIT_SECONDS, _digest_left)  # MW-131: never past the search limit
    try:
        proc = runner.git(root, "ls-tree", "-r", "-z", rev, text=False, timeout=timeout)
    except (OSError, runner.TimeoutExpired, ValueError, runner.Refused):
        return None
    if proc.returncode != 0:
        return None
    out = []
    for entry in proc.stdout.split(b"\0"):
        if not entry:
            continue
        head, _tab, path = entry.partition(b"\t")
        parts = head.split(b" ")
        if len(parts) != 3:
            return None
        out.append(parts[0] + b" " + parts[2] + b" 0\t" + path + b"\0")
    return b"".join(out)


def tree_keys(root, rev="HEAD") -> list:
    """The keys a row of `commit_tests.jsonl` may use for the tree of commit `rev`: its git tree id, then the digest
    the gate writes (`staged_key`). The one definition every reader uses (card MW-023); `[]` when git cannot tell."""
    try:
        proc = runner.git(root, "rev-parse", f"{rev}^{{tree}}", timeout=GIT_SECONDS)
    except (OSError, runner.TimeoutExpired, ValueError, runner.Refused):
        return []
    tree = proc.stdout.strip()
    if proc.returncode != 0 or not tree:
        return []
    listing = _listing(root, rev)
    return [tree] if listing is None else [tree, staged_key(listing)]


def trees_of_keys(root, keys, limit=100) -> dict:
    """{key: git tree id} for the keys that name a recent commit of HEAD (`limit` commits, newest first) in either form;
    a key no commit names is left out. Stops once every key is found."""
    wanted = {k for k in keys if isinstance(k, str) and k}
    found = {}
    try:
        proc = runner.git(root, "rev-list", f"--max-count={limit}", "HEAD", timeout=GIT_SECONDS)
    except (OSError, runner.TimeoutExpired, ValueError, runner.Refused):
        return found
    for commit in proc.stdout.split() if proc.returncode == 0 else []:
        have = tree_keys(root, commit)
        for key in have:
            if key in wanted:
                found.setdefault(key, have[0])
        if wanted <= set(found):
            break
    return found


# ---- card MW-130 (R313, R317, R320): the search for a card's red-proof row in the WHOLE history of HEAD ------------------
FOUND, NOT_IN_HISTORY, OUT_OF_TIME, UNREADABLE = "found", "not-in-history", "out-of-time", "unreadable"


class Search(NamedTuple):
    """The answer of `find_red_rows`: `case` is one of FOUND, NOT_IN_HISTORY, OUT_OF_TIME, UNREADABLE; `checked` the number of
    git trees whose digest the legacy search computed. MW-131: `rows` the rows found (every row when `every_row`, else the first
    find); `lost` the legacy rows not found when the limit ran out AFTER at least one row was found (FOUND with a partial find)."""
    case: str
    checked: int = 0
    rows: tuple = ()
    lost: tuple = ()


def commit_history(root):
    """[(commit, git tree id, committer time)] of the WHOLE history of HEAD, all parents, from ONE `git log` call through
    `runner.git` (card MW-130, R313 1); None when git cannot answer (a non-zero exit, a timeout, a failure to start)."""
    try:
        proc = runner.git(root, "log", "--format=%H %T %ct", "HEAD", timeout=GIT_SECONDS)
    except (OSError, runner.TimeoutExpired, ValueError, runner.Refused):
        return None
    if proc.returncode != 0:
        return None
    out = []
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[2].isdigit():
            out.append((parts[0], parts[1], int(parts[2])))
    return out


def digest_of_tree(root, tree: str):
    """The digest the gate writes for a staged tree (`staged_key` of the `ls-tree` listing) of the git tree id `tree`; None
    when git cannot tell. The one function that computes a digest from a tree id for the search below."""
    listing = _listing(root, tree)
    return None if listing is None else staged_key(listing)


def _epoch(value):
    """A row time (ISO, UTC unless it names an offset) as epoch seconds; None when it cannot be read."""
    try:
        found = datetime.datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return int((found if found.tzinfo else found.replace(tzinfo=datetime.timezone.utc)).timestamp())


def _queue(history: list, rows: list) -> list:
    """The commits of the one listing in the order the legacy search digests them (MW-131, DESIGN 3): ONE queue for all the rows
    still to find, ordered by the distance between the committer time of the commit and the time of the NEAREST of those rows;
    a distance tie: the newer commit first. A row with no readable time ranks after every timed row: when none has one, the
    newest commit comes first."""
    timed = [t for t in (_epoch(r.get("time")) for r in rows) if t is not None]
    if not timed:
        return sorted(history, key=lambda h: -h[2])
    return sorted(history, key=lambda h: (min(abs(h[2] - t) for t in timed), -h[2]))


def _digest_within(root, tree: str, left):
    """The digest of `tree`, its `ls-tree` allowed `left` seconds at most (and never more than GIT_SECONDS)."""
    global _digest_left
    _digest_left = left
    try:
        return digest_of_tree(root, tree)
    finally:
        _digest_left = None


def _legacy_search(root, rows: list, history: list, limit_seconds, clock, every_row: bool = False) -> tuple:
    """The reader-side search for rows that carry a digest only: (case, git trees digested, rows found, rows not found). One
    queue of commits for all the rows together (`_queue`), re-ranked without a row once it is found; each DISTINCT tree is
    digested once and compared with the digests of ALL the rows still to find. It ends at the first find when not `every_row`;
    otherwise when every row is found (case FOUND) or no commit is left. Stopped by `limit_seconds` of `clock()` time, ONE
    total per call, read before each digest: OUT_OF_TIME, never «not found»; each `ls-tree` gets the time left. A tree whose
    listing git cannot give does not match and the search goes on; a search that ends with rows not found after such a tree is
    UNREADABLE, never NOT_IN_HISTORY."""
    pending = {}
    for r in rows:
        if len(r["tree"]) == 64 and all(c in "0123456789abcdef" for c in r["tree"]):
            pending.setdefault(r["tree"], []).append(r)
    if not pending or not history:
        return NOT_IN_HISTORY, 0, (), tuple(rows)
    started, seen, checked, unreadable, found = clock(), set(), 0, False, []
    while pending:
        again = False
        for _commit, tree, _ct in _queue(history, [r for same in pending.values() for r in same]):
            if tree in seen:
                continue
            now = clock()
            if now - started >= limit_seconds:
                return OUT_OF_TIME, checked, tuple(found), tuple(r for same in pending.values() for r in same)
            digest = _digest_within(root, tree, limit_seconds - (now - started))
            checked += 1
            seen.add(tree)
            if digest is None:
                unreadable = True
                continue
            if digest in pending:
                found.extend(pending.pop(digest))
                if not every_row:
                    return FOUND, checked, tuple(found), ()
                again = True  # the queue is ranked again without the rows found
                break
        if not again:
            break
    lost = tuple(r for same in pending.values() for r in same)
    if not lost:
        return FOUND, checked, tuple(found), ()
    return (UNREADABLE if unreadable else NOT_IN_HISTORY), checked, tuple(found), lost


def find_red_rows(root, rows: list, limit_seconds, clock, every_row: bool = False) -> Search:
    """Whether a red-proof row of `rows` (dicts with a str `tree`, at least one) names a commit of the WHOLE history of HEAD,
    however many commits followed it (card MW-130, R313; the one search, R317 4, R320; `verdict add` and, since card MW-131, the
    commit gate call it). A row with a `git_tree` is found only when that id is among the tree ids of the one listing, and no
    digest work is done for it (R316 7); so is a row whose `tree` is itself a git tree id. A row with no `git_tree` (a legacy
    row) is found by its digest, `_legacy_search`, within `limit_seconds` of `clock()`, never longer. A git error is UNREADABLE,
    never FOUND. By default the search ends at the first row found (`verdict add`); with `every_row` (the gate) the answer holds
    EVERY row found, and a legacy row left out by the limit is named in `lost` when at least one row was found."""
    history = commit_history(root)
    if history is None:
        return Search(UNREADABLE)
    trees = {t for _c, t, _ct in history}
    listed = [r for r in rows if r.get("git_tree") in trees or r["tree"] in trees]
    if listed and not every_row:
        return Search(FOUND, 0, tuple(listed))
    legacy = [r for r in rows if not r.get("git_tree") and not any(r is f for f in listed)]
    case, checked, found, lost = _legacy_search(root, legacy, history, limit_seconds, clock, every_row) if legacy \
        else (NOT_IN_HISTORY, 0, (), ())
    got = tuple(listed) + found
    if got:
        return Search(FOUND, checked, got, lost if case == OUT_OF_TIME else ())
    return Search(case, checked)


class Judgement(NamedTuple):
    """The failing tests of a staged tree, sorted by what they mean for the commit (card MW-056). `new`: not red at
    HEAD (rule a). `own`: blocks, inside the committing card's Paths: a case absent at HEAD, or (card MW-108) a test red
    at HEAD and now that the card did not inherit at its take (rule b, `own_why` says why). `orphan`: red at HEAD and
    now, inside no open card's Paths (rule c, no owner); since card MW-108 it does not block. `owned`: {test id: card id}
    red at HEAD and now, inside another open card's Paths, or released to that card (rule c, does not block). Every list
    keeps the order of the staged run. `absent` (card MW-062): {test id: card id} red now and not collected at HEAD at
    all, inside another open card's Paths: judged by that card, does not block. `old_own` (card MW-108): red at HEAD and
    now, inside the committing card's Paths, and recorded red at its take (its inherited red): does not block."""
    new: list
    own: list
    orphan: list
    owned: dict
    absent: dict = {}
    file_red: dict = {}  # card MW-069: {test id: closed owner card id or None} of an `orphan` whose FILE failed at collection at HEAD
    old_own: list = []
    own_why: dict = {}  # card MW-108: {test id: not-established | green | none} of an old red in `own`: why it counts as new
    card_id: str = ""  # card MW-108: the committing card, the owner named in the line of an `old_own` test

    @property
    def blocked(self) -> bool:
        return bool(self.new or self.own)


def norm_id(ident: str) -> str:
    """A test id with `/` in its file part: pytest prints `tests\\x.py::t` on Windows and `tests/x.py::t` elsewhere."""
    file, sep, rest = ident.partition("::")
    return file.replace("\\", "/") + sep + rest


def _owns(paths, ident: str) -> bool:
    """The file of a test id (the part before `::`; a collection error names the file alone) lies in `paths`."""
    file = norm_id(ident).split("::", 1)[0]
    return any(helpers.matches(file, entry) for entry in paths)


def _other_owner(card, open_cards, ident: str):
    """The first open card (register order) other than the committing one whose Paths hold the file of `ident`."""
    return next((cid for cid, paths in open_cards if (card is None or cid != card[0]) and _owns(paths, ident)), None)


def _closed_owner(closed_cards, ident: str):
    """The first closed card (register order) whose Paths hold the file of `ident`, or None."""
    return next((cid for cid, paths in closed_cards if _owns(paths, ident)), None)


def judge(staged, head, card, open_cards, head_seen=None, closed_cards=(), inherited=None) -> Judgement:
    """Which red tests of the staged tree block the commit. `staged` and `head`: the failing test ids of the staged
    tree and of HEAD's tree. `card`: (id, Paths) of the committing card, or None. `open_cards`: [(id, Paths)] of every
    open card, in register order. `head_seen` (card MW-062): every test id HEAD's tree collects, red or green, or None
    when that is not known. A test that was collected at HEAD and was not red there is new red (a) whoever owns it. A
    test ABSENT at HEAD (a case of an id with `::` that HEAD never collected, for example a parametrised case over files
    another card creates) is judged by the open card whose Paths hold its FILE, never per id: the committing card
    refuses (b), another open card does not block and is named, no open card refuses as new red (c). Of the tests red at
    HEAD and now, one in the committing card's Paths blocks (b); one in another open card's Paths is that card's and
    does not block, one in no open card's Paths has no owner and blocks (c). A test that is green in the staged tree
    never appears. Card MW-069: a test id whose FILE failed at collection at HEAD (HEAD's failures hold the bare file,
    no `::`) is red at HEAD, a file-level failure is a failure: never new red and never absent, it takes the red-at-HEAD
    branches. One that no open card owns is named in `file_red` with the first of `closed_cards` ([(id, Paths)]) whose
    Paths hold its file, or None. Card MW-108 (`inherited`, the committing card's `cardtool.Inherited`, None for none):
    a test red at HEAD and now inside the committing card's Paths does not block when its take recorded it red (`old_own`)
    and is another card's when it was released to that card (`owned`); any other such test is new red and blocks (`own`,
    `own_why`: not-established when the take record could not be established, green when the take recorded it green,
    none when the take record holds no record of it; a card with no take record at all, one taken before the record
    existed, keeps the old refusal with no `own_why`). A test red at HEAD and now in no open card's Paths no longer blocks."""
    old = {norm_id(t) for t in head}
    broken = {i for i in old if "::" not in i}  # files that failed at collection or import at HEAD
    seen = None if head_seen is None else {norm_id(t) for t in head_seen}
    new, own, orphan, owned, absent, file_red = [], [], [], {}, {}, {}
    old_own, own_why = [], {}
    for raw in staged:
        ident = norm_id(raw)
        by_file = "::" in ident and ident.split("::", 1)[0] in broken
        if ident not in old and not by_file:
            if seen is None or "::" not in ident or ident in seen:
                new.append(ident)  # it existed at HEAD and was not red there, or HEAD's cases are not known
            elif card is not None and _owns(card[1], ident):
                own.append(ident)  # absent at HEAD, the committing card's file
            else:
                owner = _other_owner(card, open_cards, ident)
                if owner is None:
                    new.append(ident)  # absent at HEAD and no open card owns the file
                else:
                    absent[ident] = owner
        elif card is not None and _owns(card[1], ident):
            if inherited is not None and ident in inherited.released:
                owned[ident] = inherited.released[ident]  # the orderer released it to another named card
            elif inherited is not None and ident in inherited.red:
                old_own.append(ident)  # recorded red at the take of this card: its inherited red
            else:
                own.append(ident)
                if inherited is not None and inherited.taken:
                    own_why[ident] = ("not-established" if not inherited.established
                                      else "green" if ident in inherited.green else "none")
        else:
            owner = _other_owner(card, open_cards, ident)
            if owner is None:
                orphan.append(ident)
                if by_file:
                    file_red[ident] = _closed_owner(closed_cards, ident)
            else:
                owned[ident] = owner
    return Judgement(new, own, orphan, owned, absent, file_red, old_own, own_why, card[0] if card else "")


CONTINUE = "--continue-on-collection-errors"
RUN_MODE = "run-continues-past-collection-errors"  # in the key of a result: a result of the older mode is stale (MW-062)


def _continuing(argv) -> list:
    """The command a run executes (card MW-062): a pytest command also given `--continue-on-collection-errors`. pytest
    stops a whole run at the first file that fails at collection and runs no test, so a HEAD with one such file would
    record none of its other red tests, and the staged tree, which collects, would show them as new. The row keeps the
    command as the profile states it."""
    return list(argv) + [CONTINUE] if "pytest" in argv and CONTINUE not in argv else list(argv)


def profile_key(profile) -> str:
    """The digest of the profile a result was made under: a changed profile makes a kept result stale (MW-056 e); so does
    a change of the way the run is made (MW-062)."""
    text = json.dumps(profile, sort_keys=True, default=str) + "|" + RUN_MODE
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _chained(command: str, shell: str):
    """The name of an index-changing git command that comes before the commit in the same shell command, or None."""
    try:
        simples = helpers.parse(command, shell)
    except helpers.ParseError:
        return None
    for s in simples:
        argv = helpers._argv(s.words)
        if helpers._prog(argv) != "git":
            continue
        sub = helpers._git_sub(argv)[0]
        if sub == "commit":
            return None
        if sub in INDEX_CHANGERS:
            return sub
    return None


def check(event, ctx):
    profile = ctx.profile if isinstance(ctx.profile, dict) else {}
    tool_input = ctx.tool_input if isinstance(ctx.tool_input, dict) else {}
    command = tool_input.get("command")
    if profiles.vcs(profile) != "git" or not isinstance(command, str) or "commit" not in command.lower():
        return gate.allow()
    commits = ctx.commit_cmd(command)
    if not commits:
        return gate.allow()
    shell = "powershell" if ctx.tool_name == "PowerShell" else "bash"
    sub = _chained(command, shell)
    if sub or len(commits) > 1:
        what = f"`git {sub}`" if sub else "another commit"
        return gate.refuse("commit-tests-chained",
                           f"{what} and the commit are one shell command: the tests run on the index as it is before "
                           f"the command starts, which is not the tree this commit would take. Run {what} alone "
                           f"first, then the commit alone")
    try:
        return _gate(ctx, profile, commits[0])
    except RecordBusy as exc:
        return gate.refuse("shared-record-busy", str(exc))
    except NotRun as exc:
        return gate.refuse("commit-tests-not-run", f"the tests were not run, so the commit is refused: {exc}")
    except runner.TimeoutExpired as exc:
        return gate.refuse("commit-tests-not-run", f"a git read did not answer within {exc.timeout:g} s, so the "
                                                   f"staged tree could not be tested; run the commit again")
    except runner.Refused as exc:
        return gate.refuse("commit-tests-not-run", f"the tests were not run, so the commit is refused: {exc}")


def _gate(ctx, profile, commit):
    if commit.folder_unreadable:
        raise NotRun("the commit runs in a folder the gate cannot read; `cd` to a literal folder")
    if gate_commit.message_only_amend(commit):
        return gate.allow()  # MW-060: the tree does not change, nothing to test
    folder = Path(ctx.root)
    if commit.cwd:
        rel = ctx.norm(commit.cwd)
        if rel is None:
            return gate.allow()  # a commit in another project is not this project's
        folder = folder if rel == "." else folder / rel
    top = Path(_read(folder, "rev-parse", "--show-toplevel").strip())
    prefix = helpers.top_prefix(ctx.root)
    state = profiles.state_dir(ctx.root, profile)
    work = state / FOLDER / f"run-{os.getpid()}-{int(time.time() * 1000)}"
    started = time.perf_counter()
    budget = profiles.commit_tests_budget(profile)
    limit = min(budget, HOOK_LIMIT)
    try:
        env = None
        index = None
        if commit.paths or commit.all:
            index = work / "index"
            work.mkdir(parents=True, exist_ok=True)
            env = _temp_index(folder, top, index, commit)
        rels = _staged(folder, top, prefix, env, commit)
        if not rels:
            return gate.allow()
        roots = profiles.test_roots(profile)
        if profiles.docs_only(profile, rels):
            return _docs_commit(ctx, profile, folder, top, prefix, state, work, started, limit, budget, rels, roots, env,
                                commit.message)
        in_roots = [any(helpers.matches(r, root) for root in roots) for r in rels]
        code = any(not t and not profiles.docs_only(profile, [r]) for r, t in zip(rels, in_roots))
        tests_only = not code and any(in_roots)
        card, _open = _cards(ctx, profile)
        try:
            argv = _argv(profile, roots)
        except NotRun:
            if tests_only:
                return gate.allow()  # the command cannot be read: as before, tests alone may be red
            raise
        judged = card is not None and "pytest" in argv  # MW-072: the red proof needs a held card and a pytest command
        if tests_only and not judged:
            return gate.allow()  # the red-first commit of a session the proof cannot judge: tests alone may be red
        tree = staged_key(_read(folder, "ls-files", "-s", "-z", env=env, text=False))
        run = _Run(ctx, profile, folder, top, prefix, state, work, argv, started, limit, budget, profile_key(profile))
        row = _cached(state, tree, run.command, limit, run.pkey, (STATE_FILE,))
        fresh = row is None
        if fresh:
            row = run.execute(tree, run.tree_cwd(env))
        try:
            return _judged(run, row, tree, card, rels, roots, code, env, commit.message, judged, limit, commit)
        finally:
            # the row of a fresh run is written once, after the judgement, so it can hold `old_red` (MW-108); a kept row
            # that the judgement now annotates differently (a card was taken in between) is written again with the key
            if fresh:
                logs.append_jsonl(state / STATE_FILE, {**row, "old_red": run.old_red} if run.old_red else row)
            elif run.old_red and row.get("old_red") != run.old_red:
                logs.append_jsonl(state / STATE_FILE, {**row, "old_red": run.old_red})
    finally:
        _remove(work, state)


def _judged(run: "_Run", row: dict, tree: str, card, rels, roots, code: bool, env, message, judged: bool, limit,
            commit=None):
    """The verdict of a staged run: the red proof, then the new red (cards MW-056, MW-072, MW-108). `commit` (card MW-130)
    is the parsed commit command, for the git tree id of the row the red proof writes."""
    excused, proof = set(), None
    if judged:
        excused, proof = _red_proof(run, row, tree, card, rels, roots, code, env, message, commit)
    if row["result"] != "fail" or not row.get("failed_ids"):
        result = _verdict(row, roots, limit, _untracked(run.top, run.prefix, row))  # green, over budget, or red with no test named: as before
    else:
        rest = [i for i in row["failed_ids"] if i not in excused]
        result = _new_red(run, {**row, "failed_ids": rest}, roots) if rest else gate.allow()
    if result.kind == gate.REFUSE or proof is None:
        return result  # a red suite is refused as before; the red proof speaks when the suite itself is fine
    return proof if proof.kind == gate.REFUSE or result.kind == gate.ALLOW else result


def tree_id(ctx, commit):
    """MW-068 (R173 item 1): the git tree id of the tree this commit produces, built the way MW-060 builds the tree to test
    (a temporary index for `-- <paths>` and `-a`, the real index for a plain commit), so it is the tree git then commits.
    None when it cannot be told (a message-only amend, a folder the gate cannot read, a git read that fails): a commit
    with no tree has no record, and the record never blocks a commit. The real index is not changed."""
    if commit.folder_unreadable or gate_commit.message_only_amend(commit):
        return None
    folder = Path(ctx.root)
    if commit.cwd:
        rel = ctx.norm(commit.cwd)
        if rel is None:
            return None
        folder = folder if rel == "." else folder / rel
    state = profiles.state_dir(ctx.root, ctx.profile if isinstance(ctx.profile, dict) else {})
    work = state / FOLDER / f"tree-{os.getpid()}-{int(time.time() * 1000)}"
    try:
        top = Path(_read(folder, "rev-parse", "--show-toplevel").strip())
        env = None
        if commit.paths or commit.all:
            work.mkdir(parents=True, exist_ok=True)
            env = _temp_index(folder, top, work / "index", commit)
        return _read(folder, "write-tree", env=env).strip() or None
    except (NotRun, runner.TimeoutExpired, runner.Refused, OSError, ValueError):
        return None
    finally:
        _remove(work, state)


def _untracked(top, prefix, row) -> list:
    """The files of the working tree that git does not track and does not ignore, relative to the task root, for a
    red run with a file-level failure (card MW-057: a test that needs one fails in the export, and the refusal says
    so). A hint only: any failure to read them is an empty list, never a refusal."""
    if row.get("result") != "fail" or not row.get("file_errors"):
        return []
    try:
        proc = runner.git(top, "ls-files", "--others", "--exclude-standard", "-z", text=False, timeout=GIT_SECONDS)
    except (OSError, runner.TimeoutExpired, ValueError, runner.Refused):
        return []
    if proc.returncode != 0:
        return []
    out = []
    for name in (n.decode("utf-8", "replace") for n in proc.stdout.split(b"\0") if n):
        if not prefix:
            out.append(name)
        elif name.startswith(prefix + "/"):
            out.append(name[len(prefix) + 1:])
        else:
            out.append("../" + name)
    return out


class _Run:
    """What one gate call needs to run the suite on a tree: the folders, the command, the clock and the budget."""

    def __init__(self, ctx, profile, folder, top, prefix, state, work, argv, started, limit, budget, pkey):
        self.ctx, self.profile, self.folder, self.top, self.prefix = ctx, profile, folder, top, prefix
        self.state, self.work, self.argv, self.started = state, work, argv, started
        self.limit, self.budget, self.pkey = limit, budget, pkey
        self.command = " ".join(argv)
        self.old_red = []  # card MW-108: the old reds of this commit, `old_red_list`, set by `_new_red` when it allows

    def tree_cwd(self, env) -> Path:
        """The folder of the task root inside the export of the staged tree, made once per gate call."""
        cwd = self.work / "tree" / self.prefix if self.prefix else self.work / "tree"
        if not cwd.is_dir():
            self.work.mkdir(parents=True, exist_ok=True)
            _read(self.top, "checkout-index", "-a", "-f", f"--prefix={(self.work / 'tree').as_posix()}/", env=env)
        if not cwd.is_dir():
            raise NotRun(f"the staged tree has no folder {self.prefix or '.'}, so there is nothing to run in")
        return cwd

    def execute(self, tree, cwd) -> dict:
        """Run the command in `cwd` (an exported tree) within what is left of the time limit; the row of that run."""
        remaining = self.limit - (time.perf_counter() - self.started)
        code, out, err = (None, b"", b"")
        if remaining > 0:
            code, out, err = runner.run_tree(_continuing(self.argv), timeout=remaining, python=_python(self.profile),
                                             cwd=str(cwd), env=_environment(self.ctx, self.profile))
        return _row(self.ctx, tree, self.argv, code, out, err, time.perf_counter() - self.started, self.budget,
                    self.pkey)


def _head_folder(run: "_Run") -> Path:
    """The folder of the task root inside an export of HEAD's tree, made once per gate call (the HEAD run and the listing
    of HEAD's cases both use it)."""
    top = run.work / "head"
    if not top.is_dir():
        run.work.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ)
        env["GIT_INDEX_FILE"] = str(run.work / "head-index")
        _read(run.folder, "read-tree", "HEAD", env=env)
        _read(run.top, "checkout-index", "-a", "-f", f"--prefix={top.as_posix()}/", env=env)
    return top / run.prefix if run.prefix else top


def _head_ids(run: "_Run"):
    """Every test id HEAD's tree collects, red or green (card MW-062), as a set; None when it cannot be told (a command
    that is not pytest, a listing that did not finish or names no run), and then nothing is taken as absent. One listing
    per tree of HEAD, command and profile, kept in `commit_tests_collect.jsonl`."""
    argv = collect_argv(run.argv)
    keys = tree_keys(run.folder, "HEAD")
    if argv is None or not keys:
        return None
    tree = keys[-1]
    path = Path(run.state) / COLLECT_FILE
    if path.is_file():
        for line in reversed(path.read_text(encoding="utf-8").splitlines()):
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict) and row.get("tree") == tree and row.get("command") == run.command \
                    and row.get("profile") == run.pkey and row.get("reader") == READER \
                    and isinstance(row.get("collected"), list):
                return set(row["collected"])
    cwd = _head_folder(run)
    remaining = run.limit - (time.perf_counter() - run.started)
    if remaining <= 0 or not cwd.is_dir():
        return None
    # pytest prints a failing id relative to the folder it started in, and a listed id relative to its rootdir; those
    # differ when a config file above the task root moves the rootdir up, so the listing pins the rootdir to the folder
    code, out, err = runner.run_tree(argv + [f"--rootdir={cwd}"], timeout=remaining, python=_python(run.profile),
                                     cwd=str(cwd), env=_environment(run.ctx, run.profile))
    if code not in (0, 1, 2, 5):  # listed, collection errors reported (1 or 2), nothing collected: else no listing
        return None
    ids = collected_ids((out or b"").decode("utf-8", "replace") + "\n" + (err or b"").decode("utf-8", "replace"))
    if ids is None:
        return None
    logs.append_jsonl(path, {"time": logs.now().isoformat(timespec="milliseconds"), "tree": tree,
                             "command": run.command, "profile": run.pkey, "reader": READER, "collected": sorted(ids)})
    return ids


def _head_row(run: "_Run"):
    """The result of the suite on the tree of HEAD (MW-056 e): a kept row of the same tree, command and profile (the
    HEAD file, or a staged run of that very tree), else one run on an export of HEAD, kept in `commit_tests_head.jsonl`.
    None when the repository has no HEAD (nothing is red there); a result of the same shape as the staged row."""
    if _git(run.folder, "rev-parse", "--verify", "-q", "HEAD").returncode != 0:
        return None
    keys = tree_keys(run.folder, "HEAD")
    if not keys:
        raise NotRun("the tree of HEAD could not be read, so new red cannot be told from old")
    tree = keys[-1]  # the digest the gate writes for a staged tree: the same value names the same tree
    found = _cached(run.state, tree, run.command, run.limit, run.pkey, (HEAD_FILE, STATE_FILE))
    if found is not None:
        return found
    cwd = _head_folder(run)
    if cwd.is_dir():
        row = run.execute(tree, cwd)
    else:  # HEAD has no task folder yet: no test of it is red
        row = _row(run.ctx, tree, run.argv, 0, b"", b"", 0.0, run.budget, run.pkey)
    logs.append_jsonl(Path(run.state) / HEAD_FILE, row)
    return row


def _new_red(run: "_Run", row: dict, roots):
    """The staged tree is red and names its failing tests: refuse what is new or has no owner or belongs to the
    committing card, allow (with the allow line) what other open cards still own (MW-056)."""
    head = _head_row(run)
    if head is not None and head["result"] == "over-budget":
        return gate.refuse("commit-tests-over-budget",
                           f"the tests of the tree of HEAD (run once to tell new red from old red) did not finish "
                           f"within the budget of {head.get('limit_seconds', run.limit):g} s "
                           f"(gates.commit_tests.budget_seconds), so the commit is refused. Either the owner raises "
                           f"the budget in the profile, in their own terminal (a session cannot), or you fix the red "
                           f"of the staged tree. {OUT}")
    if head is not None and head["result"] == "fail" and not head.get("failed_ids"):
        return _verdict(row, roots, run.limit, _untracked(run.top, run.prefix, row))  # HEAD is red and names no test: old and new cannot be told apart
    head_ids = head.get("failed_ids", []) if head is not None and head["result"] == "fail" else []
    card, open_cards = _cards(run.ctx, run.profile)
    closed_cards = _closed_cards(run.ctx, run.profile)
    inherited = cardtool.inherited_of(run.state, card[0]) if card else None  # MW-108: what the take of the card recorded
    judgement = judge(row["failed_ids"], head_ids, card, open_cards, closed_cards=closed_cards, inherited=inherited)
    if head is not None and any("::" in i and any(_owns(paths, i) for _cid, paths in open_cards)
                                for i in judgement.new):
        # MW-062: a red case an open card holds the file of may not exist at HEAD at all; ask HEAD's tree which cases it has
        seen = _head_ids(run)
        if seen is not None:
            judgement = judge(row["failed_ids"], head_ids, card, open_cards, head_seen=seen,
                              closed_cards=closed_cards, inherited=inherited)
    if judgement.blocked:
        at_head = ()
        if judgement.new:  # MW-135: a red test that HEAD collects was green there (it is not in HEAD's red), a red proof does not excuse it
            seen = _head_ids(run)
            if seen is not None:
                collected = {norm_id(t) for t in seen}
                at_head = tuple(i for i in judgement.new if norm_id(i) in collected)
        return gate.refuse("commit-tests-failed", _refusal(judgement, card[0] if card else None, roots,
                                                           row.get("file_errors") or {},
                                                           _untracked(run.top, run.prefix, row), at_head))
    run.old_red = old_red_list(judgement, card[0] if card else None, row["failed_ids"])
    return gate.warn("commit-tests-still-red", _allow_line(judgement))


def static_ids(text: str, file: str) -> dict:
    """{test id: docstring} of the tests a Python source defines (card MW-072): `file::name` for a module function that
    starts with `test`, `file::Class::name` for such a method of a class that starts with `Test`. A source that does not
    parse has none. Parametrized cases are not expanded (the id is the base id)."""
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return {}
    out = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
            out[f"{file}::{node.name}"] = (ast.get_docstring(node) or "").strip()
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) and sub.name.startswith("test"):
                    out[f"{file}::{node.name}::{sub.name}"] = (ast.get_docstring(sub) or "").strip()
    return out


PIN_NODE = re.compile(r"[\w./-]+\.py::[\w:\[\]-]+")


def pin_rows(card_text: str) -> set:
    """The test nodes the Acceptance rows of a card name as pinning (card MW-072): a table row whose first cell is an
    example id (`E1`) and whose text holds the word `pinning`, the nodes it names, `/` in the file part."""
    out = set()
    for line in card_text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.startswith("|") else []
        if cells and re.fullmatch(r"[A-Z]\d+", cells[0]) and "pinning" in line.lower():
            out |= {norm_id(n) for n in PIN_NODE.findall(line)}
    return out


def _blob(run: "_Run", env, spec_rel: str, rev: str):
    """The text of a file as the staged index (`rev` is empty) or a commit holds it, None when it is not there."""
    path = f"{run.prefix}/{spec_rel}" if run.prefix else spec_rel
    proc = _git(run.top, "show", f"{rev}:{path}", env=env if not rev else None, text=False)
    return proc.stdout.decode("utf-8", "replace") if proc.returncode == 0 else None


def _kept_red_rows(run: "_Run", keep) -> list:
    """The rows of `red_proof.jsonl` (the shared folder only, MW-129) that `keep(row)` takes, whatever their tree. Watch rows are
    rows too. A line that is not JSON is skipped."""
    return [row for row in shared_records.read_rows(run.ctx.root, run.profile, RED_FILE)
            if isinstance(row.get("tree"), str) and keep(row)]


def _record_rows(run: "_Run", keep) -> list:
    """The rows of `red_proof.jsonl` that `keep(row)` takes and whose tree is a commit of HEAD, within the last TREE_LIMIT
    commits (a row of a commit that was never made is no record). Watch rows are rows too. A line that is not JSON is skipped.
    Since card MW-131 only `_others_red` reads this; the card's own record is `_record_of`."""
    rows = _kept_red_rows(run, keep)
    if not rows:
        return []
    found = trees_of_keys(run.folder, {r["tree"] for r in rows}, limit=TREE_LIMIT)
    return [r for r in rows if r["tree"] in found]


class OwnRecord(NamedTuple):
    """The answer of `_record_of` (card MW-131): the `record` (None when no row was found), the `cause` of a None record (one of
    core_red.CAUSE_*, empty with a record), `checked` the git trees digested, `lost` the legacy rows the search limit left out
    after at least one row was found."""
    record: object
    cause: str = ""
    checked: int = 0
    lost: tuple = ()


def _record_of(run: "_Run", card_id: str) -> OwnRecord:
    """The red record of a card in this root (card MW-072; card MW-131): the UNION of the rows of `red_proof.jsonl` for the card
    that the one search `find_red_rows` finds in the WHOLE history of HEAD, however many commits followed them (a row of a
    commit that was never made is no record). No record when no such row holds a red id, a pin or a red-by-missing file; the
    cause says why: no row, rows no commit has, the search limit ran out, the history could not be read. No listing is read
    when the card has no row."""
    rows = _kept_red_rows(run, lambda row: row.get("card") == card_id
                          and (row.get("red") or row.get("pins") or row.get("missing")))
    if not rows:
        return OwnRecord(None, core_red.CAUSE_NO_ROW)
    found = find_red_rows(run.folder, rows, OWN_RECORD_SEARCH_SECONDS, _clock, every_row=True)
    if found.case != FOUND:
        causes = {NOT_IN_HISTORY: core_red.CAUSE_NOT_IN_HISTORY, OUT_OF_TIME: core_red.CAUSE_OUT_OF_TIME,
                  UNREADABLE: core_red.CAUSE_UNREADABLE}  # causes of a missing record, not reason ids
        return OwnRecord(None, causes[found.case], found.checked)
    record = core_red.Record(red=frozenset(i for r in found.rows for i in r.get("red", [])),
                             pins=frozenset(i for r in found.rows for i in r.get("pins", [])),
                             files=frozenset(f for r in found.rows for f in (r.get("missing") or {})))
    return OwnRecord(record, "", found.checked, found.lost)


# MW-114: a `-v` line is read from the right: it starts with `<path>::`, the id is everything up to the LAST status word
# that is followed by the end of the line or by a progress mark such as `[ 50%]`; trailing spaces and CR are not the id's.
# pytest prints the reason of a skip or an xfail in brackets after its word (`SKIPPED (reason)`): it may stand between.
STATUS = re.compile(r"^(\S+::(?:.*\S)?)[ \t]+(PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS)"
                    r"(?:[ \t]+\(.*?\))?(?:[ \t]+\[[ \t]*\d+%\])?[ \t\r]*$", re.M)


def printed_ids(text: str) -> list:
    """The ids a run printed whole, longest first: the `-v` status lines and the `--collect-only -q` lines (MW-114)."""
    return sorted({i for i, _ in STATUS.findall(text)} | set(ID_LINE.findall(text)), key=len, reverse=True)


def _split_summary(rest: str, printed) -> tuple:
    """(id, message) of the text after `FAILED ` or `ERROR ` on a short-summary line (MW-114). Rule 1: the longest printed
    id that the text starts with, followed by the end of the line or ` - `. Rule 2, when no printed id fits: with a bracket
    part (a `[` before the first ` - `) the id ends at the first ` - ` that follows a `]`; otherwise at the first ` - `;
    no such ` - ` means the whole text is the id."""
    for ident in printed:
        if rest == ident or rest.startswith(ident + DASH):
            return ident, rest[len(ident) + len(DASH):]
    first, bracket = rest.find(DASH), rest.find("[")
    if first != -1 and bracket != -1 and bracket < first:
        end = first
        while end != -1 and "]" not in rest[:end]:
            end = rest.find(DASH, end + 1)
        first = end
    if first == -1:
        return rest, ""
    return rest[:first], rest[first + len(DASH):]


def summary_entries(text: str, printed=None) -> list:
    """[(word, id, message)] for every `FAILED` and `ERROR` line of the short summary, the id whole (MW-114)."""
    printed = printed_ids(text) if printed is None else printed
    return [(word, *_split_summary(rest, printed)) for word, rest in SUMMARY_LINE.findall(text)]


def failed_ids(text: str) -> list:
    """The ids of every `FAILED` and `ERROR` line, in order, each read whole (MW-114)."""
    return [ident for _, ident, _ in summary_entries(text)]


def _outcomes(run: "_Run", cwd: Path, ids, roots) -> dict:
    """{recorded id: passed | failed | skipped | gone} in the staged tree (card MW-072): the files of the ids run once
    with `-v`; a recorded id passes when it, or every case of it, passed. Fail closed: a run that does not finish refuses."""
    files = sorted({i.split("::", 1)[0] for i in ids})
    present = [f for f in files if (cwd / f).is_file()]
    seen = {}
    if present:
        words = [w for w in run.argv if w not in QUIET_FLAGS and w.replace("\\", "/").strip("/") not in roots]
        remaining = run.limit - (time.perf_counter() - run.started)
        code, out, err = (None, b"", b"")
        if remaining > 0:
            code, out, err = runner.run_tree(words + ["-v", CONTINUE, f"--rootdir={cwd}", *present], timeout=remaining,
                                             python=_python(run.profile), cwd=str(cwd),
                                             env=_environment(run.ctx, run.profile))
        if code is None:
            raise NotRun("the recorded red tests did not finish within the time left, so they could not be checked")
        text = (out or b"").decode("utf-8", "replace") + "\n" + (err or b"").decode("utf-8", "replace")
        seen = {norm_id(i): s for i, s in STATUS.findall(text.replace("\r\n", "\n"))}
    result = {}
    for ident in ids:
        states = [s for i, s in seen.items() if i == ident or i.startswith(ident + "[")]
        if not states:
            result[ident] = core_red.GONE
        elif any(s in ("FAILED", "ERROR") for s in states):
            result[ident] = core_red.FAILED
        elif any(s in ("SKIPPED", "XFAIL") for s in states):
            result[ident] = core_red.SKIPPED
        else:
            result[ident] = core_red.PASSED
    return result


def _write_record(run: "_Run", card_id: str, tree: str, verdict, would: list, mode: str, commit=None) -> None:
    if not (verdict.red or verdict.pins or verdict.checks or verdict.missing or would):
        return
    row = {"time": logs.now().isoformat(timespec="milliseconds"), "session": run.ctx.session_id, "card": card_id,
           "tree": tree, "red": list(verdict.red), "pins": list(verdict.pins), "checks": list(verdict.checks),
           "missing": dict(verdict.missing), "would_refuse": would, "mode": mode}
    git_tree = tree_id(run.ctx, commit) if commit is not None else None  # card MW-130: the tree git will commit, as the reader finds it
    if git_tree:
        row["git_tree"] = git_tree  # a row with no git_tree is a legacy row (the digest above stays)
    try:
        # MW-129: into the shared folder, under the append lock; the same tree judged before (a repeated call) is not
        # written again: one row per tree and card, checked inside the lock with the append (P1)
        shared_records.append_row(run.ctx.root, run.profile, RED_FILE, row, key=("tree", "card"))
    except logs.AppendBusy:
        raise RecordBusy(f"another writer holds the append lock of {shared_records.shared_path(run.ctx.root, run.profile, RED_FILE)}"
                         f", so the red record of {card_id} was not written and the commit is refused: repeat the call")


def _others_red(run: "_Run", card_id: str) -> dict:
    """{red id: card} of the red records of every card but `card_id` in this root (card MW-090, R225 6): all cards' rows,
    the window and the watch rows of `_record_of`."""
    rows = _record_rows(run, lambda row: row.get("card") != card_id and row.get("red"))
    return {i: str(r.get("card")) for r in rows for i in r["red"]}


def _decisions(run: "_Run", message) -> tuple:
    """The decisions the commit message names (card MW-090, R222 1): the non-empty matches of `tests.red_proof.decision_pattern`,
    each once; none when the pattern is empty or does not compile. In a root whose ledger file exists a match is a row of it
    or not, with its closed status (the ledger's own closed statuses) and whether its `by` is this session (case, spaces and
    the `session:` prefix ignored, as `core_verdicts.who` does); with no ledger file the pattern alone decides."""
    try:
        pattern = re.compile(profiles.red_proof_decision_pattern(run.profile))
    except re.error:
        return ()
    ids = list(dict.fromkeys(m.group(0) for m in pattern.finditer(message or "") if m.group(0)))
    if not ledger.path(run.ctx.root, run.profile).is_file():
        return tuple(core_red.Decision(i) for i in ids)
    rows = {r["id"]: r for r in ledger.read(run.ctx.root, run.profile)}
    me = core_verdicts.who(run.ctx.session_id)
    return tuple(core_red.Decision(i, in_ledger=False) if i not in rows else core_red.Decision(
        i, closed=rows[i]["status"] if ledger.is_closed(rows[i]["status"]) else "",
        by_self=bool(me) and core_verdicts.who(rows[i]["by"]) == me) for i in ids)


def _case_map_facts(run: "_Run", card_id: str, rels, roots, env, message) -> dict:
    """The case_map part of the facts (card MW-090), or {} when the commit does not stage the card's `case_map.md` (or deletes
    it): its text in the committed tree and at HEAD, the decisions, the test roots, the static test ids at HEAD and in the
    committed tree of the files the new lines' sides name (a left file is read by its own path at HEAD, it may be
    unstaged), and the red ids of the other cards."""
    rel = cardtool.card_file(Path(run.ctx.root), run.profile, card_id).with_name("case_map.md") \
        .relative_to(Path(run.ctx.root)).as_posix()
    text = _blob(run, env, rel, "") if rel in rels else None
    if text is None:
        return {}
    head = _blob(run, None, rel, "HEAD") or ""
    files = core_red.case_map_files(text, head, roots)
    ids = lambda rev, e: frozenset(i for f in files for i in static_ids(_blob(run, e, f, rev) or "", f))  # noqa: E731
    return {"case_map": text, "case_map_head": head, "decisions": _decisions(run, message), "test_roots": tuple(roots),
            "head_ids": ids("HEAD", None), "tree_ids": ids("", env), "other_red": _others_red(run, card_id)}


def _answer(verdict, mode: str):
    """The gate answer for a verdict that refuses: a refusal, or in `watch` mode a warning with the same reason and text;
    None when the verdict allows. The first refusal's reason id is the reason id of the commit."""
    if not verdict.refusals:
        return None
    said = " | ".join(r.text for r in verdict.refusals)
    if mode == "watch":
        return gate.warn(verdict.refusals[0].reason, f"watch mode, the commit is allowed: {said}")
    return gate.refuse(verdict.refusals[0].reason, f"{said}. {OUT}")


def _docs_commit(ctx, profile, folder, top, prefix, state, work, started, limit, budget, rels, roots, env, message):
    """A commit of documents alone (card MW-090, R225 4): no suite run, as before, except that a commit that stages the
    card's `case_map.md` has its lines judged. A session with no card, or a command that is not pytest, is not judged."""
    card, _open = _cards(ctx, profile)
    try:
        argv = _argv(profile, roots)
    except NotRun:
        return gate.allow()
    if card is None or "pytest" not in argv:
        return gate.allow()
    run = _Run(ctx, profile, folder, top, prefix, state, work, argv, started, limit, budget, profile_key(profile))
    extra = _case_map_facts(run, card[0], rels, roots, env, message)
    if not extra:
        return gate.allow()
    verdict = core_red.decide(core_red.Facts(card=card[0], paths=tuple(sorted(card[1])), **extra))
    answer = _answer(verdict, profiles.red_proof_mode(profile))
    return gate.allow() if answer is None else answer


def _red_proof(run: "_Run", row: dict, tree: str, card, rels, roots, code: bool, env, message=None, commit=None):
    """The red proof of a commit (card MW-072): (the failing ids it excuses, its refusal, its watch warning, or None).
    Reads the facts (the new test ids by `ast`: the tests the changed test files define in the committed tree and not in
    HEAD's, with no collection run; the card; the red record; the recorded ids' outcomes; card MW-090: the case_map lines
    and the decisions of the commit `message`, None for no message) and lets `core_red.decide` decide. A run that is over
    budget or names no failing test is left to the old judgement."""
    if row["result"] == "over-budget" or (row["result"] == "fail" and not row.get("failed_ids")):
        return set(), None
    card_id, card_paths = card
    try:
        text = cardtool.card_file(Path(run.ctx.root), run.profile, card_id).read_text(encoding="utf-8")
    except (OSError, cardtool.CardError, register.RegisterError):
        text = ""
    own = _record_of(run, card_id)
    record = own.record
    tests = {r for r in rels if r.endswith(".py") and any(helpers.matches(r, root) for root in roots)}
    setup = row.get("setup_errors") or {}
    file_errs = {} if code else {f: m for f, m in (row.get("file_errors") or {}).items() if "::" not in f and f in tests}
    sources, fresh = {}, {}
    for file in sorted(tests):
        sources[file] = static_ids(_blob(run, env, file, "") or "", file)
        before = static_ids(_blob(run, None, file, "HEAD") or "", file)
        fresh[file] = tuple(sorted(set(sources[file]) - set(before)))
    file_new = {f: fresh[f] for f in file_errs}
    new_ids = tuple(i for f in sorted(tests) if f not in file_errs for i in fresh[f])  # a file that fails to collect: file_new
    base = lambda i: i.split("[", 1)[0]  # noqa: E731
    cases = lambda b: [i for i in row.get("failed_ids", []) if i == b or i.startswith(b + "[")]  # noqa: E731
    failing = {b: cases(b) for b in new_ids if cases(b)}  # new test -> its failing cases (a parametrized test has many)
    doc = lambda i: sources.get(i.split("::", 1)[0], {}).get(base(i), "")  # noqa: E731
    pinned = pin_rows(text)
    kind = cardtool.header(text, "Kind").strip().strip("`").lower()
    outcomes = {}
    if code and record and record.red:
        outcomes = _outcomes(run, run.tree_cwd(env), sorted(record.red), roots)
    facts = core_red.Facts(
        card=card_id, kind=kind, paths=tuple(sorted(card_paths)), code=code, new_ids=new_ids,
        failed=frozenset(b for b, ids in failing.items() if any(i not in setup for i in ids)),
        errored={b: setup[ids[0]] for b, ids in failing.items() if all(i in setup for i in ids)},
        file_errors=file_errs, file_new=file_new,
        pin_docstring=frozenset(i for i in new_ids if doc(i).startswith("Pins:")),
        pin_rows=frozenset(i for i in new_ids if norm_id(base(i)) in pinned),
        checks_docstring=frozenset(i for i in new_ids if doc(i).startswith("Checks:")),
        record=record, record_cause=own.cause, record_checked=own.checked, record_limit=OWN_RECORD_SEARCH_SECONDS,
        outcomes=outcomes, **_case_map_facts(run, card_id, rels, roots, env, message))
    verdict = core_red.decide(facts)
    mode = profiles.red_proof_mode(run.profile)
    would = list(dict.fromkeys(r.reason for r in verdict.refusals))
    if not code and (mode == "watch" or not would):
        _write_record(run, card_id, tree, verdict, would, mode, commit)
    excused = set() if code else {i for ids in failing.values() for i in ids} | set(file_errs)  # red the commit must show
    answer = _answer(verdict, mode)  # the case_map refusals stand first in the verdict: they name the reason id
    if answer is None and own.lost:
        # MW-131 (R322): the limit ran out after a row was found: the commit goes on with the found rows and one warn line names
        # what was left out; an allow line with its own id, never a refusal
        times = [str(r.get("time") or "not established") for r in own.lost]
        answer = gate.warn(core_red.PARTIAL, core_red.partial_text(card_id, times, OWN_RECORD_SEARCH_SECONDS))
    return excused, answer


def _cards(ctx, profile):
    """(the committing card as (id, Paths) or None, [(id, Paths)] of every open card in register order). The card is
    the one this session holds, when it is open; a register that cannot be read leaves no card and no owner."""
    try:
        rows = register.read(ctx.root, profile)
        held = ctx.records.card()
    except (OSError, ValueError, register.RegisterError):
        return None, []
    open_cards = [(r["id"], cardtool.paths_set(r.get("paths", ""))) for r in rows if r.get("status") == "open"]
    return next(((cid, paths) for cid, paths in open_cards if cid == held), None), open_cards


def _closed_cards(ctx, profile) -> list:
    """[(id, Paths)] of every closed card in register order (MW-069: names the closed owner of a red the file of which
    failed at collection at HEAD); a register that cannot be read gives none."""
    try:
        rows = register.read(ctx.root, profile)
    except (OSError, ValueError, register.RegisterError):
        return []
    return [(r["id"], cardtool.paths_set(r.get("paths", ""))) for r in rows if r.get("status") == "closed"]


class HeadRed(NamedTuple):
    """What the rows kept in the state folder say about the red at HEAD inside some Paths (card MW-108, R283 2).
    `established`: a usable row was found in HEAD's history. `red`: the ids the nearest row lists as failing, inside the
    Paths, in the order of its run. `green`: ids inside the Paths that an older row listed as failing and the nearest row
    does not (recorded green). `record`: the commit whose row was the nearest, `behind`: how many commits before HEAD."""
    established: bool
    red: list
    green: list
    record: str = ""
    behind: int = 0


NOT_KNOWN = HeadRed(False, [], [])


def head_red(root, profile, paths) -> HeadRed:
    """The one source of the list of red tests at HEAD that `card take` records (card MW-108). It never runs the suite and
    never refuses: it reads the rows the commit gate kept (`commit_tests_head.jsonl` and `commit_tests.jsonl`, keyed by
    tree) for the commits of HEAD's history, newest first, within TREE_LIMIT commits, rows of the same command, profile
    and reader only. The nearest row of the history decides; an id that an older row listed and the nearest does not is
    recorded green. Not established (`NOT_KNOWN`) when the profile has no git, the command cannot be read, git cannot be
    read or no row of HEAD's history is usable."""
    try:
        return _head_red(Path(root), profile, paths)
    except (NotRun, OSError, ValueError, runner.Refused, runner.TimeoutExpired):
        return NOT_KNOWN


def _usable(row, command, pkey) -> bool:
    """A kept row that tells which tests failed: the same command and profile, a pass, or a fail that names its tests and was
    read by the current reader."""
    if not (isinstance(row, dict) and isinstance(row.get("tree"), str) and row.get("command") == command
            and row.get("profile") == pkey):
        return False
    return row.get("result") == "pass" or (row.get("result") == "fail" and row.get("reader") == READER
                                           and bool(row.get("failed_ids")))


def _kept_rows(state, command, pkey) -> dict:
    """{tree key: the last usable row} of the two row files of the state folder; a line that is not JSON is skipped."""
    kept = {}
    for name in (HEAD_FILE, STATE_FILE):
        path = Path(state) / name
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if _usable(row, command, pkey):
                kept[row["tree"]] = row
    return kept


def _head_red(root: Path, profile, paths) -> HeadRed:
    if profiles.vcs(profile) != "git":
        return NOT_KNOWN
    command, pkey = " ".join(_argv(profile, profiles.test_roots(profile))), profile_key(profile)
    kept = _kept_rows(profiles.state_dir(root, profile), command, pkey)
    if not kept:
        return NOT_KNOWN
    proc = runner.git(root, "rev-list", f"--max-count={TREE_LIMIT}", "HEAD", timeout=GIT_SECONDS)
    commits = proc.stdout.split() if proc.returncode == 0 else []
    found = []  # (commit, steps behind HEAD, row) of the commits of HEAD's history that have a row, nearest first
    for steps, commit in enumerate(commits):
        row = next((kept[k] for k in tree_keys(root, commit) if k in kept), None)
        if row is not None:
            found.append((commit, steps, row))
        if len(found) == len(kept):
            break
    if not found:
        return NOT_KNOWN
    failing = lambda row: [norm_id(i) for i in row.get("failed_ids", [])] if row["result"] == "fail" else []  # noqa: E731
    near = failing(found[0][2])
    older = {i for _c, _s, row in found[1:] for i in failing(row)}
    return HeadRed(True, [i for i in near if _owns(paths, i)],
                   sorted(i for i in older if i not in near and _owns(paths, i)), found[0][0], found[0][1])


def _ids(ids, quota: int):
    """(`a; b; c`, ids used) with at most `quota` ids shown."""
    shown = ids[:max(quota, 0)]
    return "; ".join(shown), len(shown)


def _refusal(judgement: Judgement, card_id, roots, errors=None, untracked=(), at_head=()) -> str:
    errors = errors or {}
    quota, parts = MAX_IDS, []
    own = [i for i in judgement.own if i not in judgement.own_why]
    existing = [i for i in judgement.new if i in at_head]  # MW-135: collected at HEAD and green there
    kinds = [([i for i in judgement.new if i not in at_head], "new red, not red at HEAD"),
             (existing, "new red (not red at HEAD: the test exists at HEAD and was green there, so a red-first commit "
                        "does not excuse it)"),
             (own, f"red in the Paths of {card_id}, the card of this commit")]
    # MW-108 (R283): an old red in the card's own Paths counts as new unless its take recorded it red; say which case it is
    for why, text in OWN_WHY.items():
        kinds.append(([i for i in judgement.own if judgement.own_why.get(i) == why], text.format(card=card_id)))
    for ids, what in kinds:
        if not ids:
            continue
        text, used = _ids([f"{i} ({errors[i]})" if i in errors else i for i in ids], quota)
        quota -= used
        count = f"{len(ids)}" if used == len(ids) else f"{len(ids)}, first {used} shown"
        parts.append(f"{what} ({count}): {text}" if used else f"{what} ({len(ids)}): not listed here")
    only_existing = bool(existing) and len(existing) == sum(len(ids) for ids, _what in kinds if ids)
    if only_existing:  # MW-135: the red-first commit is the very thing that was refused, so it is not offered for this test
        ways = (f"{_untracked_note(untracked, errors)}Two ways out: put the changed existing test in the same commit as "
                f"the code change, where the run is green; or write the new expectation as a new test name in the "
                f"red-first commit, and change or remove the old test in the green commit.")
        note = (f"; still red and owned by another open card, not blocking: {len(judgement.owned)}"
                if judgement.owned else "")
        if judgement.absent:
            note += f"; absent at HEAD and owned by another open card, not blocking: {len(judgement.absent)}"
        return f"the tests of the staged tree are red: {'; '.join(parts)}{note}. {ways} {OUT}"
    ways = (f"{_untracked_note(untracked, errors)}Fix them and stage the fix, or commit the tests alone as the "
            f"red-first commit (every staged file under {', '.join(roots)}; that commit may be red).")
    if any(w in ("not-established", "none") for w in judgement.own_why.values()):
        ways += " " + NOT_ESTABLISHED_WAY.format(card=card_id or "<card id>")
    if existing:
        ways += (" For a test that exists at HEAD and was green there: put the changed test in the same commit as the "
                 "code change, where the run is green, or write the new expectation as a new test name in the red-first "
                 "commit and change or remove the old test in the green commit.")
    ways += (f" Plain form of the red-first commit, run alone: `git commit -m \"{card_id or '<card id>'} tests only: "
             f"<what>\" -- <test files>`. Only a new red blocks: an old red does not block a commit.")
    note = (f"; still red and owned by another open card, not blocking: {len(judgement.owned)}"
            if judgement.owned else "")
    if judgement.absent:
        note += f"; absent at HEAD and owned by another open card, not blocking: {len(judgement.absent)}"
    return f"the tests of the staged tree are red: {'; '.join(parts)}{note}. {ways} {OUT}"


def _absent_text(absent: dict) -> str:
    """`40 cases absent at HEAD, owned by CARD-002`: one phrase per owner, in the order the owners first appear."""
    counts = {}
    for owner in absent.values():
        counts[owner] = counts.get(owner, 0) + 1
    return "; ".join(f"{n} {'case' if n == 1 else 'cases'} absent at HEAD, owned by {owner}"
                     for owner, n in counts.items())


OWN_WHY = {  # MW-108, R283: the old reds in the Paths of the committing card that its take record does not excuse
    "not-established": "red at HEAD and still red in the Paths of {card}, but the take record of {card} is not "
                       "established (no test record of HEAD's history was found when the card was taken), so it counts "
                       "as new red",
    "green": "red at HEAD and still red in the Paths of {card}, but recorded green when {card} was taken, so it counts "
             "as new red",
    "none": "red at HEAD and still red in the Paths of {card}, but the take record of {card} holds no record of it, so "
            "it counts as new red",
}
NOT_ESTABLISHED_WAY = ("A red the take record does not hold: release the card and take it again (`mkway card release "
                       "{card}` then `mkway card take {card}`); this refusal just kept a test row of HEAD, the new take "
                       "reads it and records those reds as the old red of the card.")


def old_red_list(judgement: Judgement, card_id, order) -> list:
    """The `old_red` field of the commit row (card MW-108): one `{test, card}` per old red of the commit, in the order of
    the staged run `order`; `card` is the committing card for its inherited red, the other open card that owns the file
    (or that the id was released to), None for a red no open card owns."""
    owner = {**{i: card_id for i in judgement.old_own}, **judgement.owned, **{i: None for i in judgement.orphan}}
    rank = {norm_id(i): n for n, i in reversed(list(enumerate(order)))}
    return [{"test": i, "card": owner[i]} for i in sorted(owner, key=lambda i: rank.get(i, len(rank)))]


def _allow_line(judgement: Judgement) -> str:
    line = "the commit is allowed: no new red"
    shown = [f"old red: {i}, owner {judgement.card_id}" for i in judgement.old_own]
    for i in judgement.orphan:
        if i in judgement.file_red:
            closed = judgement.file_red[i]
            where = f" (its file failed at collection at HEAD{f', closed card {closed}' if closed else ''})"
        else:
            where = ""
        shown.append(f"old red: {i}, owner none{where}")
    if shown:
        line += ". Not blocking, " + "; ".join(shown[:MAX_IDS]) + (f"; and {len(shown) - MAX_IDS} more"
                                                                    if len(shown) > MAX_IDS else "")
    if judgement.owned:
        items = [f"{ident} still red, owned by {owner}" for ident, owner in judgement.owned.items()]
        shown = "; ".join(items[:MAX_IDS]) + (f"; and {len(items) - MAX_IDS} more" if len(items) > MAX_IDS else "")
        line += f". Not blocking, red at HEAD and still red: {shown}"
    if judgement.absent:
        line += f". Not blocking, red now and judged by the card that owns the file: {_absent_text(judgement.absent)}"
    return line


QUIET_FLAGS = ("-q", "-qq", "-qqq", "--quiet", "-v", "-vv", "-vvv", "--verbose")
ID_LINE = re.compile(r"^(\S+?\.py::(?:.*\S)?)[ \t\r]*$", re.M)  # a line of `--collect-only -q` that names a test: the id whole (MW-114)
LISTED = re.compile(r"\b(?:collected|deselected)\b")


def collect_argv(argv):
    """The command that lists the test ids of a tree (card MW-062): the tests command with its quiet and verbose flags
    removed, then `--collect-only -q` (one id per line) and `--continue-on-collection-errors`; None when the command is
    not pytest, so HEAD's ids cannot be listed and nothing is taken as absent."""
    if "pytest" not in argv:
        return None
    return [w for w in argv if w not in QUIET_FLAGS] + ["--collect-only", "-q", "--continue-on-collection-errors"]


def collected_ids(text: str):
    """The set of test ids a `--collect-only -q` run printed, read as the failing ids are (`/` in the file part, the
    whole line without its trailing spaces: an id may hold a space); an empty set for a run that collected nothing; None when the text shows no collection run."""
    text = text.replace("\r\n", "\n")
    ids = {norm_id(i) for i in ID_LINE.findall(text)}
    if ids:
        return ids
    return set() if LISTED.search(text) else None


def _only(commit) -> bool:
    """`-- <paths>`, `--only`, `-o`: git commits HEAD plus the named paths, nothing else of the index."""
    return bool(commit.paths) and not commit.all and not commit.include


def tree_plan(commit, head, index, taken) -> dict:
    """{path: where its content comes from} for the tree this commit produces (card MW-060): `head` the paths of HEAD's
    tree, `index` the paths of the real index, `taken` the reader's list (`gate_commit.taken`). A `--` commit starts
    from HEAD, every other form from the index; every `work` entry of the list then takes the working-tree content (a
    deleted one is gone). Sources: `head`, `index`, `work`. Pure: no git call."""
    base, paths = ("head", head) if _only(commit) else ("index", index)
    plan = {path: base for path in paths}
    for status, rel, source in taken:
        if source != "work":
            continue
        if status == "D":
            plan.pop(rel, None)
        else:
            plan[rel] = "work"
    return plan


def _paths(top, *args, env=None) -> set:
    """The paths a `git ls-tree -r` or `git ls-files` read prints, `-z`."""
    return {n for n in _read(top, args[0], "-z", *args[1:], env=env).split("\0") if n}


def _temp_index(folder, top, index: Path, commit):
    """The environment of a temporary index that holds exactly the tree this commit produces (card MW-060), built from
    the list `gate_commit.taken` gives, the one the file gate reads: HEAD for a `--` commit, the real index for the other
    forms, then the working-tree content of every `work` path. Untracked files are never added (git commits none). The
    built index is compared with `tree_plan`, and any difference refuses (fail closed). The real index is not changed."""
    env = dict(os.environ)
    env["GIT_INDEX_FILE"] = str(index)
    has_head = _git(folder, "rev-parse", "--verify", "-q", "HEAD").returncode == 0
    listing = gate_commit.taken(lambda path: path, folder, commit)
    if listing is None:
        raise NotRun("the files this commit takes could not be read from git, so the tree to test could not be built")
    if _only(commit):  # HEAD plus the working-tree content of the named paths
        _read(folder, "read-tree", *(["HEAD"] if has_head else ["--empty"]), env=env)
    else:
        real = Path(_real_index(folder))
        if real.is_file():
            shutil.copyfile(real, index)
    work = [rel for _status, rel, source in listing if source == "work"]
    if work:
        proc = runner.run(runner.GIT + ["-C", str(top), "update-index", "--add", "--remove", "-z", "--stdin"],
                          input="\0".join(work) + "\0", capture_output=True, text=True, timeout=GIT_SECONDS, env=env)
        if proc.returncode != 0:
            raise NotRun(f"git update-index failed (exit {proc.returncode}), so the tree to test could not be built")
    head = _paths(top, "ls-tree", "-r", "--name-only", "HEAD") if has_head and _only(commit) else set()
    real_index = set() if _only(commit) else _paths(top, "ls-files")  # the real index: no GIT_INDEX_FILE
    if _paths(top, "ls-files", env=env) != set(tree_plan(commit, head, real_index, listing)):
        raise NotRun("the tree built for the tests differs from the tree this commit takes, so it is not tested")
    return env


def _real_index(folder) -> str:
    """The path of the real index file (a worktree's own one included)."""
    real = Path(_read(folder, "rev-parse", "--git-path", "index").strip())
    return str(real if real.is_absolute() else Path(folder) / real)


def _staged(folder, top, prefix, env, commit) -> list:
    """The paths this commit changes, relative to the task root; a path outside the root is kept as `../<path>`."""
    has_head = _git(folder, "rev-parse", "--verify", "-q", "HEAD").returncode == 0
    base = None
    if has_head:
        base = "HEAD"
        if commit.amend:
            base = "HEAD^" if _git(folder, "rev-parse", "--verify", "-q", "HEAD^").returncode == 0 else None
    if base:
        raw = _read(top, "diff-index", "--cached", "--name-only", "--no-renames", "-z", base, env=env)
    else:
        raw = _read(top, "ls-files", "-z", env=env)
    out = []
    for name in (n for n in raw.split("\0") if n):
        if not prefix:
            out.append(name)
        elif name.startswith(prefix + "/"):
            out.append(name[len(prefix) + 1:])
        else:
            out.append("../" + name)
    return out


def _python(profile):
    value = (profile.get("python") or {}).get("command") if isinstance(profile.get("python"), dict) else None
    return value if isinstance(value, str) and value else "python"


def _argv(profile, roots) -> list:
    py = _python(profile)
    command = profiles.tests_command(profile)
    if command is None:
        return [py, "-m", "pytest", "-q", *roots]
    try:
        words = shlex.split(command, posix=False)
    except ValueError as exc:
        raise NotRun(f"tests.command cannot be read ({exc})")
    words = [w[1:-1] if len(w) >= 2 and w[0] == w[-1] and w[0] in "\"'" else w for w in words]
    if not words:
        raise NotRun("tests.command is empty")
    if words[0].lower() in ("python", "python3"):
        words[0] = py
    if not runner.allowed(words[0], py):
        raise NotRun(f"tests.command starts with {words[0]!r}, which is neither the profile's Python nor git; the "
                     f"engine runs no other program, so the command cannot run")
    return words


def _environment(ctx, profile) -> dict:
    """Only the names the run needs: the system essentials, `ENGINE_TERMS_FILE` and the profile's `test_env`."""
    source = {k.upper(): (k, v) for k, v in {**os.environ, **dict(ctx.env or {})}.items()}
    wanted = [*SESSION_ENV, *ALWAYS_ENV, *profiles.test_env(profile)]
    env = {}
    for name in wanted:
        if name.upper() in source:
            key, value = source[name.upper()]
            env[key] = value
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _cached(state, tree, command, limit, pkey, names=(STATE_FILE,)):
    """The last row of this tree, command and profile in the named state files that still stands, or None. A row made
    under another profile (MW-056 e) or a red row that does not list its failing tests is no answer."""
    found = None
    for name in names:
        path = Path(state) / name
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict) and row.get("tree") == tree and row.get("command") == command \
                    and row.get("profile") == pkey:
                found = row
    if found is None:
        return None
    if found.get("result") == "over-budget" and limit > float(found.get("limit_seconds") or 0):
        return None  # a raised budget runs again
    if found.get("result") == "fail" and "failed_ids" not in found:
        return None  # a row of an older engine: it cannot tell old red from new
    if found.get("result") == "fail" and found.get("reader") != READER:
        return None  # MW-114: its failed ids were read by an older reader (cut at a space): run again
    return found if found.get("result") in ("pass", "fail", "over-budget") else None


def file_errors(text: str) -> dict:
    """{file: its first error line} for the files that failed at collection or import (card MW-057): the last
    exception line of the file's traceback in the errors section (a module or file not found, a syntax error), else
    the text after `ERROR <file> - ` in the short summary. A test-level failure has no entry."""
    found = {}
    text = text.replace("\r\n", "\n")  # pytest output on Windows ends its lines with CRLF
    entries = summary_entries(text)
    summary = [norm_id(i) for w, i, _ in entries if w == "ERROR" and "::" not in i]  # the ids the failure count uses
    heads = list(COLLECT_HEAD.finditer(text))
    for n, head in enumerate(heads):
        stop = heads[n + 1].start() if n + 1 < len(heads) else len(text)
        body = text[head.end():stop]
        cut = re.search(r"^=", body, re.M)  # the next banner (short summary, totals) ends the section
        body = body[:cut.start()] if cut else body
        lines = ERROR_LINE.findall(body)
        pick = next((ln for ln in reversed(lines) if EXCEPTION.match(ln)), lines[-1] if lines else None)
        if pick:
            # the header names the file relative to pytest's rootdir, the summary id relative to where it started:
            # they are the same file when one path ends with the other
            path = norm_id(head.group(1).strip())
            ident = next((i for i in summary if path == i or path.endswith("/" + i) or i.endswith("/" + path)), path)
            found.setdefault(ident, pick[:MAX_LINE])
    for word, ident, message in entries:
        if word == "ERROR" and message and "::" not in ident:
            found.setdefault(norm_id(ident), message[:MAX_LINE])
    return found


def _untracked_note(untracked, errors) -> str:
    """The clause that says the working tree holds files the staged tree does not carry, for a file-level failure
    only; the files that the error lines name come first; at most MAX_UNTRACKED are shown."""
    names = [n for n in untracked or [] if isinstance(n, str) and n]
    if not names or not errors:
        return ""
    said = " ".join(errors.values()).lower()

    def named(name):
        stem = name.rsplit("/", 1)[-1].rsplit(".", 1)[0].lower()
        return not ((len(stem) >= 3 and stem in said) or name.lower() in said)

    names.sort(key=named)  # stable: the ones an error line names first, the rest in the order given
    shown = ", ".join(names[:MAX_UNTRACKED]) + (f" and {len(names) - MAX_UNTRACKED} more"
                                                if len(names) > MAX_UNTRACKED else "")
    return (f"The working tree has untracked files that the staged tree does not carry ({shown}); a test that needs "
            f"one fails here, so stage it. ")


def _row(ctx, tree, argv, code, out, err, duration, budget, pkey) -> dict:
    text = (out or b"").decode("utf-8", "replace") + "\n" + (err or b"").decode("utf-8", "replace")
    entries = summary_entries(text)
    ids = [norm_id(i) for _, i, _ in entries]
    every = list(dict.fromkeys(ids))  # MW-056: all of them, once each, `/` in the file part
    tail = [ln.strip() for ln in text.splitlines() if ln.strip()][-4:]
    result = "over-budget" if code is None else ("pass" if code == 0 else "fail")
    errors = file_errors(text)
    messages = {norm_id(i): m for w, i, m in entries if w == "ERROR" and m and "::" in i}  # MW-072: errors at setup, by test id
    setup = {i: messages.get(i, "error at setup") for i in dict.fromkeys(norm_id(i) for w, i, _ in entries if w == "ERROR")
             if "::" in i}
    return {"time": logs.now().isoformat(timespec="milliseconds"), "session": ctx.session_id, "tree": tree,
            "command": " ".join(argv), "profile": pkey, "reader": READER, "result": result,
            "duration_seconds": round(duration, 3),
            "budget_seconds": budget, "limit_seconds": min(budget, HOOK_LIMIT), "exit_code": code,
            "failed_count": len(ids), "failing": ids[:MAX_IDS], "failed_ids": every,
            "file_errors": {i: errors[i] for i in every if i in errors}, "setup_errors": setup,
            "tail": " | ".join(tail)[:600]}


def _verdict(row, roots, limit, untracked=()):
    if row["result"] == "pass":
        return gate.allow()
    if row["result"] == "over-budget":
        return gate.refuse("commit-tests-over-budget",
                           f"the tests of the staged tree did not finish within the budget of "
                           f"{row.get('limit_seconds', limit):g} s (gates.commit_tests.budget_seconds), so the commit "
                           f"is refused. Either the owner raises the budget in the profile, in their own terminal "
                           f"(a session cannot), or you shrink the commit and split it. {OUT}")
    ways = (f"Fix them and stage the fix, or commit the tests alone as the red-first commit (every staged file under "
            f"{', '.join(roots)}; that commit may be red). {OUT}")
    if row["failing"]:
        count = row["failed_count"]
        shown = f"first {len(row['failing'])} of {count}" if count > len(row["failing"]) else f"all {count}"
        errors = row.get("file_errors") or {}
        items = [f"{i} ({errors[i]})" if i in errors else i for i in row["failing"]]
        return gate.refuse("commit-tests-failed",
                           f"the tests of the staged tree are red: {count} failing ({shown}): "
                           f"{'; '.join(items)}. {_untracked_note(untracked, errors)}{ways}")
    return gate.refuse("commit-tests-failed", f"the tests of the staged tree did not pass: the run exited "
                                              f"{row['exit_code']} and named no failing test ({row['tail']}). {ways}")


def _remove(work: Path, state: Path) -> None:
    """Remove this run's folder, only when it is inside `<state.dir>/commit_tests/`."""
    try:
        if work.exists() and Path(work).resolve().parent == (Path(state) / FOLDER).resolve():
            def writable(func, path, _info):
                os.chmod(path, stat.S_IWRITE)
                func(path)
            try:
                shutil.rmtree(work, onexc=writable)  # Python 3.12 and later
            except TypeError:
                shutil.rmtree(work, onerror=writable)
    except OSError:
        pass
