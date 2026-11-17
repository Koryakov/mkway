"""The lock gate's decisions as one pure function of facts (card MW-063).

`decide(facts) -> Verdict` reads only the `Facts` record the shell (`gate_lock.py`) built: the tool, the closed or open
state of every lock target, the caller's session id, the profile's switches, and `reads`, the facts the shell reads on
request. A fact that is not in `reads` yet is asked for: `decide` returns a `NEED` verdict whose `need` is the key
(`("register",)`, `("expanded", 0)`, ...); the shell reads that one fact, adds it to `reads` and decides again. The
decision is the same whichever way the facts arrive, and a decision that does not reach a fact never asks for it.

No `os`, `pathlib`, `subprocess`, `time` or `datetime` here, no engine I/O module, no environment: the shell reads the
disk, git and the clock; this module names refusals. The one engine module it imports is `helpers`, for the pure path
matching on text. Refusals and records are data; the shell writes them (the one-use permits are `Permit` rows).

The rules are those of `gate_lock.py` before this card (card MW-003, deliverable 3; spec section 1, L1-L8; MW-045):
an edit-tool write in a closed target, a shell command whose writes reach one, a commit that takes one, a session's
call of an owner-only command, and the rules of taking and releasing a card.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Mapping, Optional

import helpers

ALLOW, REFUSE, LOG, NEED = "allow", "refuse", "log", "need"
SHELL_TOOLS = ("Bash", "PowerShell")
PATH_KEYS = ("file_path", "notebook_path", "path")
NEVER_OPEN = ("locks", "register", "state", "upgrade")  # `upgrade`: MW-105 (R260 a), a folder outside the repository
UPGRADE, UNC = "upgrade", "unc"  # the classes of a path outside the repository, read by the shell (MW-105)
VARIABLE = re.compile(r"[$`%(){}]")
WHY = {"unparsed": "the shell text or a Python body does not parse",
       "capable": "a computed path, a variable, or a program that can write anywhere"}
CLI = "python mkway/engine/mkway.py"
TERMINAL = "the owner runs it in their own terminal, where no hook runs"
REASONS = ("lock-closed-edit", "lock-closed-shell", "lock-closed-commit", "lock-file-by-session", "owner-only-command",
           "session-has-card", "card-not-yours", "take-root-busy", "engine-call-not-plain", "command-unparsed",
           "commit-folder-unreadable", "pathspec-unparsed", "gate-git-timeout", "quote-file-outside",
           "close-not-orderer", "close-by-holder", "register-tampered")  # refusals; the one log row is below
LOG_REASON = "write-target-unresolved"


@dataclass(frozen=True)
class Verdict:
    """allow, refuse or log (blocks nothing), each with the one-use permits to leave; or NEED (a fact to read)."""
    kind: str
    reason: Optional[str] = None
    text: str = ""
    permits: tuple = ()
    need: Optional[tuple] = None

    def __post_init__(self):
        if self.kind not in (ALLOW, REFUSE, LOG, NEED):
            raise ValueError(f"unknown verdict kind: {self.kind!r}")
        if self.kind in (REFUSE, LOG) and not (self.reason and self.text):
            raise ValueError("a refuse or a log needs a reason and a text")
        if self.kind == NEED and not self.need:
            raise ValueError("a need names the fact it asks for")


@dataclass(frozen=True)
class Permit:
    """A one-use permit the shell leaves: kind `by` (names the session), `close`, `open` or `release` (name a card).
    `on_fail` is the verdict when the permit cannot be written. `scope` (MW-110, R279c): `messaging` for the by-permit of
    `send`, `inbox` and `ack`, which the shell writes under the session's own id; empty for every other permit."""
    kind: str
    card: Optional[str] = None
    on_fail: Optional[Verdict] = None
    scope: str = ""


def allow() -> Verdict:
    return Verdict(ALLOW)


def refuse(reason: str, text: str) -> Verdict:
    return Verdict(REFUSE, reason, text)


def log(reason: str, text: str) -> Verdict:
    return Verdict(LOG, reason, text)


@dataclass(frozen=True)
class Target:
    """A lock target: the name, the repo paths or globs, and whether its lock is closed now (the shell reads the
    markers and the clock). `open_by_default` is the owner hold (MW-010)."""
    name: str
    entries: tuple
    built_in: bool
    open_by_default: bool = False
    closed: bool = True


@dataclass(frozen=True)
class Row:
    """One register row as the gate needs it. `orderer_problem` and `open_problem` are the card tool's answers for
    this session (None when it may close, or open, the card as its orderer)."""
    status: Optional[str]
    ordered_by: str = "owner"
    orderer_problem: Optional[tuple] = None
    open_problem: Optional[tuple] = None


@dataclass(frozen=True)
class RegisterFacts:
    """The sealed register: `problem` is (reason, message) when the seal fails, else `rows` by card id."""
    problem: Optional[tuple] = None
    rows: Mapping = field(default_factory=dict)


@dataclass(frozen=True)
class WriteFacts:
    """What the reader says a shell command writes: a reason when it cannot read it all, and (text, repo path) of each
    path it names (the repo path is None outside the root). MW-105: an entry has a third item, the class `upgrade` or
    `unc` the shell read for a path outside the repository; a two-item entry has no class."""
    reason: Optional[str] = None
    paths: tuple = ()


@dataclass(frozen=True)
class CommitFacts:
    """One `git commit` the reader found: its flags, its pathspecs as written and their repo paths."""
    folder_unreadable: bool = False
    paths: tuple = ()
    include: bool = False
    amend: bool = False
    all: bool = False
    rels: tuple = ()


@dataclass(frozen=True)
class Names:
    """File names git reported (repo paths; None outside the root), or `problem`, for example `git exit 128`."""
    paths: tuple = ()
    problem: Optional[str] = None


@dataclass(frozen=True)
class Timeout:
    """A git read did not answer in time."""
    seconds: float


@dataclass(frozen=True)
class Seal:
    """The register's seal: the seal file's name and text, and the sha256 of the working-tree register (None: no file)."""
    name: str
    present: bool
    seal: str = ""
    work: Optional[str] = None


@dataclass(frozen=True)
class Blob:
    """The sha256 of a staged blob, or the git exit code that failed."""
    sha: Optional[str] = None
    exit_code: int = 0


@dataclass(frozen=True)
class Facts:
    tool_name: Optional[str]
    command: str = ""
    targets: tuple = ()
    session_id: Optional[str] = None
    edit_rels: tuple = ()
    edit_classes: tuple = ()  # MW-105: (raw path, class) for each path key of an edit tool, in the order of `edit_rels`
    vcs_git: bool = False
    owner_moves: tuple = ("open", "closed")
    orderer: bool = False
    stale_hours: float = 0.0
    register_rel: Optional[str] = None
    owner_terminal: str = ""
    owner_fix: str = ""
    owner_name: str = "owner"
    reads: Mapping = field(default_factory=dict)

    def with_read(self, key: tuple, value) -> "Facts":
        return replace(self, reads={**self.reads, key: value})


class _Need(Exception):
    def __init__(self, key: tuple):
        super().__init__(key)
        self.key = key


class _Stop(Exception):
    def __init__(self, verdict: Verdict):
        super().__init__(verdict.reason)
        self.verdict = verdict


def _read(f: Facts, *key):
    if key in f.reads:
        return f.reads[key]
    raise _Need(key)


def _git(value):
    """A git read's answer; a read that did not answer in time refuses `gate-git-timeout` (list item 11, R44 row 4)."""
    if isinstance(value, Timeout):
        raise _Stop(refuse("gate-git-timeout", f"a git read did not answer within {value.seconds:g} s, so the commit "
                                               f"could not be checked; run it again"))
    return value


def decide(f: Facts) -> Verdict:
    permits: list = []
    try:
        v = _shell(f, permits) if f.tool_name in SHELL_TOOLS else _edit(f)
    except _Need as need:
        return Verdict(NEED, need=need.key)
    except _Stop as stop:
        v = stop.verdict
    return replace(v, permits=tuple(permits)) if permits else v


# ---- targets -----------------------------------------------------------------------------------------------------------

_ABSOLUTE_ENTRY = re.compile(r"^(?:/|[A-Za-z]:/)")


def is_absolute_entry(entry: str) -> bool:
    """True for a target entry that is an absolute folder outside the repository (`upgrade`, MW-105). The repo matchers
    below skip it: a repo glob such as `up*` would match its parts (`helpers.matches`), and only `named_target` and the
    shell's class check read it."""
    return bool(_ABSOLUTE_ENTRY.match(entry.strip().replace("\\", "/")))


def closed_target(targets, rel: Optional[str]) -> Optional[Target]:
    """The closed target that holds the repo path, or None."""
    if rel is None:
        return None
    for t in targets:
        if t.closed and any(helpers.matches(rel, e) for e in t.entries if not is_absolute_entry(e)):
            return t
    return None


def _glob_folder(entry: str) -> Optional[str]:
    """The literal folder in front of a glob entry's first wildcard (`docs` for `docs/**/*.md`), "" for a glob at the
    root, None for a slash-free glob (it matches in any folder)."""
    if "/" not in entry.rstrip("/"):
        return None
    head = entry[:min(i for i, ch in enumerate(entry) if ch in "*?[")]
    return head.rsplit("/", 1)[0] if "/" in head else ""


def held_target(targets, rel: Optional[str], file_in):
    """(closed target, what shows it) when the path `rel` holds a closed target: the root holds every target; a folder
    holds a literal entry below it, a glob whose literal folder is below it or is it, or a file on disk that a glob
    entry matches (`file_in(rel, entry)`: the first such file, or None). None otherwise (list item 2, R37 (a) H2)."""
    if rel is None:
        return None
    fold = helpers._fold
    for t in targets:
        if not t.closed:
            continue
        for raw in t.entries:
            if is_absolute_entry(raw):  # MW-105: the root holds no folder outside the repository
                continue
            e = raw.strip().replace("\\", "/")
            e = e[2:] if e.startswith("./") else e
            if rel == ".":
                return t, e.rstrip("/")
            if not any(ch in e for ch in "*?["):
                if fold(e.rstrip("/")).startswith(fold(rel) + "/"):
                    return t, e.rstrip("/")
                continue
            folder = _glob_folder(e)
            if folder is not None and (fold(folder) == fold(rel) or fold(folder).startswith(fold(rel) + "/")):
                return t, e
            hit = file_in(rel, e)
            if hit:
                return t, hit
    return None


def _literal_of(entry: str) -> Optional[str]:
    """The literal repo path an entry names: the entry itself, or a glob's literal folder; None for a slash-free
    glob or a glob at the root."""
    e = entry.strip().replace("\\", "/")
    e = e[2:] if e.startswith("./") else e
    if any(ch in e for ch in "*?["):
        return _glob_folder(e) or None
    return e.rstrip("/") or None


def _reaches(glob_parts: list, parts: list) -> bool:
    """True when a glob path's leading segments match a literal path's segments one by one (`mkway/engin?/x`
    reaches `mkway/engine`); a `**` segment reaches anything below where it stands (remainder item 4, H14)."""
    fold = helpers._fold
    for k, seg in enumerate(parts):
        if k >= len(glob_parts):
            return False
        if glob_parts[k] == "**":
            return True
        if not helpers.glob_re(fold(glob_parts[k])).fullmatch(fold(seg)):
            return False
    return True


def glob_target(targets, rel: Optional[str]):
    """(closed target, the path) when the glob path `rel` matches a closed target's literal path or one of its parent
    folders (`mkway/*` matches `mkway/engine`; list item 5), or its leading segments match the target's segments one
    by one, so it writes inside it (`mkway/engin?/gate_lock.py`; remainder item 4, R95 (4a)); None otherwise."""
    if rel is None:
        return None
    for t in targets:
        if not t.closed:
            continue
        for entry in t.entries:
            if is_absolute_entry(entry):  # MW-105: `up*` and `C*` must not match the parts of an absolute folder
                continue
            lit = _literal_of(entry)
            parts = lit.split("/") if lit else []
            for k in range(len(parts), 0, -1):
                candidate = "/".join(parts[:k])
                if helpers.matches(candidate, rel):
                    return t, candidate
            if parts and _reaches(rel.split("/"), parts):
                return t, lit
    return None


_BEFORE = r"(?:^|(?<=[\s'\"/=:;,(\[{|&<>`]))"
_AFTER = r"(?=$|[\s'\"/;,)\]}|&<>`*?\[])"  # a glob character is a boundary too (remainder item 4, M1)


def named_target(targets, text: str):
    """(closed target, the literal) when the command text names a closed target literally (list item 5, R43 (b);
    R81, R81a; close-fix 5, R84): its repo path of two or more segments with a path boundary on both sides; or its
    base name in a path position. A folder target's base name (`state`, `locks`, `engine`), a leading-dot file's
    (`.gitignore`), an undotted file's (`run`) and a one-segment literal (`docs`) count only right after `/` or
    `\\`, so a plain word never names a target; a dotted file's base name (`mkway.lock`) also counts after the start,
    a quote or a space. The base name ends before a quote, a space, a separator (folders only) or the end. None
    otherwise."""
    flat = (text or "").replace("\\", "/")
    flags = re.IGNORECASE if helpers.CASE_FOLD else 0
    for t in targets:
        if not t.closed:
            continue
        for entry in t.entries:
            lit = _literal_of(entry)
            if not lit:
                continue
            if "/" in lit and re.search(_BEFORE + re.escape(lit) + _AFTER, flat, flags):  # close-fix 5: boundaries
                return t, lit
            base = lit.rsplit("/", 1)[-1]
            folder = entry.rstrip().endswith("/") or any(ch in entry for ch in "*?[")
            dotted = "." in base and not base.startswith(".")
            if folder or not dotted or "/" not in lit:  # R81, R84: right after a separator only
                pattern = r"/" + re.escape(base) + (r"(?=$|['\"\s/])" if folder else r"(?=$|['\"\s])")
            else:
                pattern = r"(?:^|[/'\"\s])" + re.escape(base) + r"(?=$|['\"\s])"
            if re.search(pattern, flat, flags):
                return t, lit
    return None


def _fix(target: Target) -> str:
    """The way out named in a refusal for the closed target."""
    if target.open_by_default:  # the owner hold (MW-010)
        return (f"hold by the owner; wait for the owner's word (the owner lifts it with `{CLI} lock open "
                f"{target.name}`, {TERMINAL})")
    if target.name in NEVER_OPEN:
        return "only the engine's own commands write it"
    if target.built_in:
        return f"the owner may open it with `{CLI} lock open {target.name}` ({TERMINAL})"
    return f"ask the owner to open it: `{CLI} lock open {target.name}` ({TERMINAL})"


def _refuse_target(target: Target, rel: str, how: str, holds=None) -> Verdict:
    if target.name == "locks" and holds is None:
        return refuse("lock-file-by-session", f"{rel} is a lock file: lock files are written only by the owner's "
                                              f"`mkway lock open|close` ({TERMINAL})")
    reason = {"edit": "lock-closed-edit", "shell": "lock-closed-shell", "commit": "lock-closed-commit"}[how]
    fix = _fix(target)
    if holds is not None:
        return refuse(reason, f"{rel} holds {holds}, which is inside the closed lock {target.name!r}; {fix}")
    return refuse(reason, f"{rel} is inside the closed lock {target.name!r}; {fix}")


def _closed(f: Facts, rel, how: str) -> Optional[Verdict]:
    """The refusal for a path inside a closed target, or one that holds a closed target (list item 2), or None."""
    target = closed_target(f.targets, rel)
    if target:
        return _refuse_target(target, rel, how)
    held = held_target(f.targets, rel, lambda r, e: _read(f, "disk", r, e))
    if held:
        return _refuse_target(held[0], rel, how, holds=held[1])
    return None


def _glob_inside(f: Facts, rel) -> Optional[Verdict]:
    """`lock-closed-shell` when the glob path `rel`'s literal folder (before its first wildcard) lies inside a closed
    target (close-fix 2, B-H1: `mkway/engine/*`); None otherwise."""
    if rel is None:
        return None
    head = rel[:min(i for i, ch in enumerate(rel) if ch in "*?[")]
    folder = head.rsplit("/", 1)[0] if "/" in head else ""
    target = closed_target(f.targets, folder) if folder else None
    if target is None:
        return None
    return refuse("lock-closed-shell", f"{rel} is a glob inside {folder}, which is inside the closed lock "
                                       f"{target.name!r}; {_fix(target)}")


UPGRADE_TARGET = Target(UPGRADE, (), True)  # the name and the way out of a refusal; the folder is the shell's to compare


def _outside(raw: str, cls: Optional[str], how: str) -> Optional[Verdict]:
    """MW-105: the refusal for a path the shell classed `upgrade` (it is, equals, or holds the guarded upgrade folder: the
    same ids and text as a repo target, R260a 2) or `unc` (a network path is not read, so it is refused with a text that
    names no target, R260a); None for no class. Decided before the variable and glob branches (R260b 3)."""
    reason = {"edit": "lock-closed-edit", "shell": "lock-closed-shell"}[how]
    if cls == UNC:
        return refuse(reason, f"{raw} is a network path and cannot be checked; write to a local path")
    if cls == UPGRADE:
        return _refuse_target(UPGRADE_TARGET, raw, how)
    return None


# ---- the edit tool -----------------------------------------------------------------------------------------------------

def _edit(f: Facts) -> Verdict:
    for i, rel in enumerate(f.edit_rels):
        raw, cls = f.edit_classes[i] if i < len(f.edit_classes) else (rel, None)
        verdict = _outside(raw, cls, "edit") or _closed(f, rel, "edit")
        if verdict:
            return verdict
    return allow()


# ---- the engine's own commands -----------------------------------------------------------------------------------------

def positional(args) -> list:
    out, i = [], 0
    while i < len(args):
        a = args[i]
        if a in ("--root", "--profile", "--minutes", "--text", "--source", "--from", "--ref", "--vcs", "--python"):
            i += 2
            continue
        if not a.startswith("-"):
            out.append(a)
        i += 1
    return out


def quote_file_value(args) -> Optional[str]:
    """The path a `--quote-file` option names (the last one), or None."""
    value = None
    for i, a in enumerate(args):
        if a == "--quote-file" and i + 1 < len(args):
            value = args[i + 1]
        elif a.startswith("--quote-file="):
            value = a.split("=", 1)[1]
    return value


def _owner_only(what: str) -> Verdict:
    return refuse("owner-only-command", f"`mkway {what}` is the owner's command: {TERMINAL}. A session never grants "
                                        "itself a card or a lock and never declares itself done")


def _register(f: Facts) -> RegisterFacts:
    reg = _read(f, "register")
    if reg.problem:
        raise _Stop(refuse(*reg.problem))
    return reg


def _status(f: Facts, card_id) -> Optional[str]:
    """The sealed register's status of a card (None: no such row); a failed seal stops with its refusal."""
    row = _register(f).rows.get(card_id)
    return row.status if row else None


def _quote_file_problem(f: Facts, args) -> Optional[Verdict]:
    """MW-048: a `--quote-file` names a file inside the bundle's asks folder (or the ledger folder); any other path is
    refused `quote-file-outside`, as the engine would read any file of the machine otherwise."""
    value = quote_file_value(args)
    if value is None:
        return None
    rel = _read(f, "quote_rel", value)
    folders = _read(f, "quote_folders")
    if rel is not None and ".." not in rel.split("/") and any(rel.startswith(x.strip("/") + "/") for x in folders):
        return None
    return refuse("quote-file-outside", f"`--quote-file {value}` is outside the quote folders; put the quote in a "
                                        f"file under {folders[0]} (or {folders[1]}) and pass --quote-file")


def _close_by_orderer(f: Facts, card_id, permits: list) -> Optional[Verdict]:
    """MW-011, `cards.approver: orderer`: a session's `card close`. The orderer must be this session and not the
    card's holder; the gate then leaves the one-use permit the CLI reads."""
    if not card_id:
        return None  # the CLI refuses a close with no card id
    row = _register(f).rows.get(card_id)
    if row is None:
        return None  # the CLI says `card-unknown`
    if row.orderer_problem:
        return refuse(*row.orderer_problem)
    permits.append(Permit("close", card_id, refuse("close-not-orderer", f"{card_id}: the permit of this close could "
                                                                        f"not be written; {f.owner_terminal}")))
    return None


def _open_by_lead(f: Facts, card_id, permits: list) -> Optional[Verdict]:
    """MW-028, `cards.approver: orderer`: a registered lead's `card open` of a proposed card it ordered leaves the
    one-use permit the CLI reads; any other card stays the owner's to open."""
    if not card_id:
        return None
    row = _register(f).rows.get(card_id)
    if row is None:
        return None
    if row.open_problem:
        return refuse("owner-only-command", row.open_problem[1])
    permits.append(Permit("open", card_id, _owner_only("card open")))
    return None


def _release_by_orderer(f: Facts, card_id, permits: list) -> Verdict:
    """MW-045: a session's `card release` of a card another session holds passes only for the session that ordered
    the card; the gate leaves the one-use permit the CLI reads. Anyone else is `card-not-yours`."""
    row = _register(f).rows.get(card_id)
    ordered = row.ordered_by if row else None
    fail = refuse("card-not-yours", f"{card_id} is held by another session; a session releases only its own card, and "
                                    f"the card's orderer may free it with `{CLI} card release {card_id}`. The owner "
                                    f"frees it with `{CLI} card release {card_id} --force` ({TERMINAL})")
    if ordered and ordered != f.owner_name and ordered == f.session_id:
        permits.append(Permit("release", card_id, fail))
        return None
    return fail


def _call(f: Facts, args, permits: list) -> Optional[Verdict]:
    pos = positional(args)
    if not pos:
        return None
    head = pos[0]
    if head == "lock" and pos[1:2] and pos[1] in ("open", "close"):
        return _owner_only(" ".join(pos[:2]))
    if head == "gate" and pos[1:2] and pos[1] in ("off", "on", "watch"):  # `watch`: MW-012
        return _owner_only(" ".join(pos[:2]))
    if head in ("install", "upgrade", "hold", "go", "delivered"):  # `hold` and `go`: the short forms of the lock close
        return _owner_only(head)                                   # and open; `delivered` (MW-020): the owner's base
    if head == "green" and pos[1:2] == ["record"]:  # MW-104 (R257f): the green record is the owner's to write
        return _owner_only("green record")
    if head == "built":  # MW-020: the provenance row names the session; the CLI reads it from this one-use permit
        permits.append(Permit("by"))
        return None
    if head == "verdict" and pos[1:2] in (["add"], ["recut"]):  # MW-080 (R194), MW-100 (R251a point 8): `by` is the caller
        permits.append(Permit("by"))
        return None
    if head == "give":  # MW-011: the owner says who ordered a card; MW-017: a registered lead's give is a hand-off
        if not _read(f, "lead"):
            return _owner_only(head)
        permits.append(Permit("by"))
        return None
    if head == "lead" and pos[1:2]:  # MW-017: `lead add|remove` are the owner's; register and accept name the session
        if pos[1] in ("add", "remove"):
            return _owner_only(f"lead {pos[1]}")
        if pos[1] in ("register", "accept"):
            permits.append(Permit("by"))
        return None
    if (head == "ledger" and pos[1:2] == ["add"]) or (head == "ask" and pos[1:2] == ["answered"]):
        problem = _quote_file_problem(f, args)  # MW-048
        if problem:
            return problem
    if head in ("ack", "send", "inbox", "reader"):  # MW-116: `reader start|end` takes its session id the way `send` does
        permits.append(Permit("by", scope="messaging"))  # MW-017 `ack`, MW-018 `send`, `inbox`; MW-110 R279c: its own file
        return None
    if (head == "ledger" and pos[1:2] == ["add"]) or (head == "ask" and pos[1:2] == ["default"]):
        permits.append(Permit("by"))  # MW-015: names the session
        return None
    if head != "card" or len(pos) < 2:
        return None
    sub, card_id = pos[1], (pos[2] if len(pos) > 2 else None)
    if sub == "new":  # MW-017: a lead's new card gets its order file; the CLI reads who ran it from the permit
        if _read(f, "lead"):
            permits.append(Permit("by"))
        return None
    moves = f.owner_moves
    if sub == "resync":
        return _owner_only("card resync")
    if sub == "release-red":  # MW-108 (R283 4): the orderer's; the CLI reads the caller from this by-permit and decides
        permits.append(Permit("by"))
        return None
    held = _read(f, "holders")
    if sub == "release":
        if any(a == "--force" or a.startswith("--force=") for a in args):
            return _owner_only("card release --force")
        holder = held.get(card_id)
        if holder and holder != f.session_id:
            return _release_by_orderer(f, card_id, permits)  # MW-045
        if holder:
            permits.append(Permit("by"))  # MW-076 (R189): the holder's own release tells the orderer; the notice names it
        return None
    if sub == "close" and f.orderer:
        return _close_by_orderer(f, card_id, permits)
    if sub == "open" and f.orderer and "open" in moves and _read(f, "lead"):
        return _open_by_lead(f, card_id, permits)  # MW-028
    if sub in ("open", "close"):
        status = "open" if sub == "open" else "closed"
        return _owner_only(f"card {sub}") if status in moves else None
    if sub == "set":
        status = pos[3] if len(pos) > 3 else None
        if status == "closed" and f.orderer:  # MW-011: `closed` by a session goes through `card close` only
            return _owner_only("card set closed")
        if status == "waiting" and (not card_id or held.get(card_id) != f.session_id):
            return refuse("card-not-yours", f"{card_id} is not the card this session holds; a session pauses only its "
                                            f"own card (`{CLI} card take <id>` first)")
        if status == "waiting":
            permits.append(Permit("by"))  # MW-076 (R189): the notice to the orderer names the session that caused it
        if status not in moves:
            return None
        if status == "open" and card_id and held.get(card_id) == f.session_id:
            if _status(f, card_id) == "waiting":
                return None  # R19c: the holder reopens its own pause
        return _owner_only(f"card set {status}")
    if sub == "take":
        holder = held.get(card_id)
        stale = _read(f, "stale")  # MW-045: the CLI releases these before the take
        if holder and holder != f.session_id and card_id not in stale:
            return refuse("card-not-yours", f"{card_id} is held by another session. The owner or the card's "
                                            f"orderer frees it with `{CLI} card release {card_id}`; a holder "
                                            f"unseen for over {f.stale_hours:g} h "
                                            f"(`cards.stale_hours`) is released at a take")
        mine = _read(f, "mine")
        if mine and mine != card_id and _status(f, mine) != "closed":
            return refuse("session-has-card", f"this session holds {mine}, which is not closed: one card per "
                                              f"session. Free it with `{CLI} card release {mine}` first")
        for other_card, other in held.items():  # MW-034: one builder per task root, so one worktree and one index
            if other != f.session_id and other_card not in stale and _status(f, other_card) == "open":
                return refuse("take-root-busy", f"session {other[:8]} already holds {other_card} in this task "
                                                f"root: one builder per worktree and index. Wait until that "
                                                f"session closes or hands off {other_card}, or work in your "
                                                f"own worktree. Two ways out if it is gone: the owner or the "
                                                f"card's orderer frees it with `{CLI} card release "
                                                f"{other_card}`, or it is released at your take once its "
                                                f"holder was last seen over "
                                                f"{f.stale_hours:g} h ago "
                                                f"(`cards.stale_hours`)")
        if any(who != f.session_id for who in stale.values()):
            permits.append(Permit("by"))  # the CLI reads who takes from it, to free the others only
    return None


# ---- the shell tool ----------------------------------------------------------------------------------------------------

def _shell(f: Facts, permits: list) -> Verdict:
    # H4 (R54): the exact form first, then the call's own rules; false blocks (E98): a variable assigned a literal in
    # the same command is read, so `python $D/tool.py` is no disguised engine script
    problem = _read(f, "engine_call")
    if problem:
        return refuse("engine-call-not-plain", f"the engine call is refused: {problem}. Run the mkway command alone, "
                                               f"in its plain form: `{CLI} <command> <args>`")
    for args in _read(f, "calls"):
        verdict = _call(f, args, permits)
        if verdict is not None:
            return verdict
    if f.vcs_git and not _read(f, "parse_ok") and _read(f, "names_commit"):  # list item 7 (R43 point 2)
        return refuse("command-unparsed", "this command cannot be parsed and holds a `git ... commit`, so its commit "
                                          "cannot be checked; run the commit alone, in a plain form: `git commit -m "
                                          "\"<message>\" -- <paths>`")
    carrier = _read(f, "carrier") if f.vcs_git else None
    if carrier:  # close-fix 3 (B-H5, R83), remainder item 1 (R95 (2a)): an unread commit fails closed
        return refuse("command-unparsed", f"this command may run a `git ... commit` the gate cannot read (through "
                                          f"{carrier}), so its commit cannot be checked; run the commit alone, in a "
                                          "plain form: `git commit -m \"<message>\" -- <paths>`")
    form = _read(f, "form") if f.vcs_git else None
    if form:  # close-fix 8 (A-M2, R83): a git form the reader cannot check is refused outright
        return refuse(form[0], f"{form[1]}, so its effect cannot be checked; run the plain form: `git commit -m "
                               f"\"<message>\" -- <paths>` with exact option names")
    env = _read(f, "env")
    if env:  # close-fix 7 (B-H4), remainder item 8 (H7): an `env` the gate cannot read
        return refuse("command-unparsed", f"{env}; run the command directly, without that `env` option")
    if _read(f, "cdpath"):  # remainder item 10 (H5b): `cd` under `CDPATH` lands where it is not named
        return refuse("command-unparsed", "this command holds `CDPATH` and a `cd`, so the folder it runs in cannot be "
                                          "read; run the `cd` without `CDPATH`, to a literal folder")
    writes = _read(f, "writes")
    why = writes.reason
    for entry in writes.paths:
        text, rel = entry[0], entry[1]
        verdict = _outside(text, entry[2] if len(entry) > 2 else None, "shell")  # MW-105: before the variable and glob checks
        if verdict:
            return verdict
        if VARIABLE.search(text):  # a variable or substitution path is `capable` (R43)
            why = why or helpers.CAPABLE
            continue
        if any(ch in text for ch in "*?["):  # a glob: refused when it matches a closed target or its folder
            hit = glob_target(f.targets, rel)
            if hit:
                return _refuse_target(hit[0], rel, "shell", holds=hit[1])
            inside = _glob_inside(f, rel)
            if inside:
                return inside
            continue
        verdict = _closed(f, rel, "shell")  # (a)
        if verdict:
            return verdict
    pending = None
    if why:
        hit = named_target(f.targets, f.command) or named_target(f.targets, _read(f, "expanded_text"))  # item 12
        if hit:  # (b) literal reach
            return refuse("lock-closed-shell", f"this command's write targets cannot all be read ({why}: {WHY[why]}), "
                                               f"and it names {hit[1]}, which is inside the closed lock "
                                               f"{hit[0].name!r}; split it into plain commands that write literal "
                                               f"paths")
        pending = log(LOG_REASON, f"write targets not read ({why}: {WHY[why]})")  # (c)
    if f.vcs_git:
        for i, commit in enumerate(_read(f, "commits")):
            verdict = _commit(f, i, commit)
            if verdict is not None:
                return verdict
        shape = _read(f, "unknown_shape")
        if shape and _read(f, "names_commit"):  # remainder item 10 (R95 (1b)): a commit the shape hides
            return refuse("command-unparsed", f"this command holds a shape the gate does not follow ({shape}) and "
                                              f"names a `git ... commit`, so its commit cannot be checked; run the "
                                              f"commit alone, in a plain form: `git commit -m \"<message>\" -- "
                                              f"<paths>`")
    return pending or allow()


def _commit(f: Facts, i: int, c: CommitFacts) -> Optional[Verdict]:
    if c.folder_unreadable:  # list item 9 (R44 row 2)
        return refuse("commit-folder-unreadable", "this commit runs in a folder the gate cannot read (a `cd` or `-C` "
                                                  "to a variable or an unreadable target), so its paths cannot be "
                                                  "checked; `cd` to a literal folder, or commit from the root with "
                                                  "repo paths")
    unresolved = [p for p in c.paths if "$" in p or "`" in p]  # `:(glob)` pathspec magic is not one
    if unresolved:  # list item 12 (R44 row 5): only a path still unresolved after the same-command expansion
        return refuse("pathspec-unparsed", f"the commit path {unresolved[0]} holds a variable or a substitution that "
                                           f"is not a literal assigned earlier in this command, so it cannot be "
                                           f"checked; name the path literally")
    rels = list(c.rels)
    if c.paths:  # list item 2: a pathspec is the changed tracked files it matches, each checked
        expanded = _git(_read(f, "expanded", i))
        if expanded.problem:
            return refuse("lock-closed-commit", f"the commit pathspec could not be expanded ({expanded.problem}), so "
                                                f"its files could not be checked; name plain paths")
        rels += [r for r in expanded.paths if r not in rels]
    staged: list = []
    if c.include:
        names = _git(_read(f, "staged", i))
        if names.problem:  # list item 3: a failed read refuses, never an empty list
            return refuse("lock-closed-commit", f"the staged names could not be read ({names.problem}), so the "
                                                f"commit could not be checked")
        staged = list(names.paths)
    elif c.amend or not c.paths:  # list item 16 (R68): the commit takes the index, or with -a the changes
        every = c.all and not c.paths
        names = _git(_read(f, "index", i, every))
        if names.problem:
            return refuse("lock-closed-commit", f"the files this commit takes could not be read ({names.problem}), "
                                                f"so it could not be checked; name your paths after `--`")
        for rel in names.paths:
            verdict = _index_commit(f, rel, every)
            if verdict is not None:
                return verdict
    for rel in rels + staged:
        if rel is None:
            continue
        if rel == f.register_rel:
            verdict = _register_commit(f, rel, rel in staged or c.include)
            if verdict is not None:
                return verdict
            continue
        target = closed_target(f.targets, rel)
        if target:
            return _refuse_target(target, rel, "commit")
    return None


def _index_commit(f: Facts, rel, every: bool) -> Optional[Verdict]:
    """The refusal for one file a commit with no pathspec takes, naming the session's own step; or None."""
    if rel is None:
        return None
    if rel == f.register_rel:
        return _register_commit(f, rel, not every)
    target = closed_target(f.targets, rel)
    if not target:
        return None
    if every:
        return refuse("lock-closed-commit", f"{rel} has a change inside the closed lock {target.name!r} and `-a` "
                                            f"would commit it; commit without -a and name your own paths after `--`")
    return refuse("lock-closed-commit", f"{rel} is staged and inside the closed lock {target.name!r}; unstage it "
                                        f"with `git restore --staged {rel}` and commit without it")


def _register_commit(f: Facts, rel: str, include_index: bool) -> Optional[Verdict]:
    """The register passes only when its sha256 (the working tree's bytes, and with `-i` the staged blob too) equals
    the seal (R19a)."""
    seal = _read(f, "seal")
    if not seal.present:
        return refuse("lock-closed-commit", f"{rel}: {seal.name} is missing, so the register cannot be checked; "
                                            f"{f.owner_fix}")
    if seal.work != seal.seal:
        return refuse("lock-closed-commit", f"{rel} differs from its seal; only the engine's own commands write it. "
                                            f"{f.owner_fix}")
    if include_index:
        blob = _git(_read(f, "blob", rel))
        if blob.exit_code != 0:
            return refuse("lock-closed-commit", f"the staged {rel} could not be read (git exit {blob.exit_code}), so "
                                                f"it could not be checked against its seal; stage it with `git add "
                                                f"{rel}` or leave it out")
        if blob.sha != seal.seal:
            return refuse("lock-closed-commit", f"the staged {rel} differs from its seal; only the engine's own "
                                                f"commands write it. {f.owner_fix}")
    return None
