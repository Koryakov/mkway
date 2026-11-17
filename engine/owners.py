"""The owner table (card MW-107, concept line 1, kind K6): one owner per file kind. Data plus one function, `owner_of`.

Every file kind the engine knows has exactly one row: a name, the one role that writes and commits it, the command that
writes it (or what the owner does), and the patterns of its place, built from the profile. The roles are `owner` (the
person, in their own terminal), `orderer` (the lead that ordered a card), `holder` (the session that holds the card),
`reader` (the blind reader or checker), `engine` (the engine's own commands and hooks); `any` is the role of a row every
session may write (the profile's `paths.exempt`, the outside-writable folders).

Three call sites read this one table, so no gate keeps a list of its own: the subtask gate (`gate_subtask`: the card
files a session may always write, the exempt paths, the lead's set), the lead gate (`leads.writable`: what a registered lead
may write) and the commit-files scope (`gate_commit`: what the orderer may commit). A path no row matches has no owner:
the gate refuses it, and the text names the way out (a card whose Paths hold it, or the profile names the kind). A target
outside the session's root has an owner only when the shell matched it against the outside-writable list (role `any`).

This module reads nothing: no file, no process, no environment, no clock. It is called by the shells; the pure cores
(`core`, `core_session`) take its answers as facts and import nothing but `helpers`. No task name is in this file.
"""
from __future__ import annotations

from typing import NamedTuple, Optional

import helpers
import profiles

OWNER, ORDERER, HOLDER, READER, ENGINE = "owner", "orderer", "holder", "reader", "engine"
ANY = "any"
ROLES = (OWNER, ORDERER, HOLDER, READER, ENGINE)
VERDICT_DIR = "tests/verdicts"  # the same folder as `verdicts.VERDICT_DIR`
WAY_OUT_NO_ROW = "a card whose Paths hold it, or the profile names the kind (`paths.exempt`)"
WAY_OUT_OUTSIDE = ("write the file inside {root}; a file the task needs elsewhere is a folder the owner adds to "
                   "paths.outside_writable")  # R274 5.3; `{root}` is the root, or "your root" when the caller has none
OWNER_NOTE = "Owner table:"


class Kind(NamedTuple):
    """One row. `edit`: a session may write the kind with an edit tool or the shell (False: only the command writes it)."""
    name: str
    role: str
    command: str
    patterns: tuple
    edit: bool = True


OUTSIDE_ROW = Kind("outside-writable", ANY, "the harness's own folders and the folders of `paths.outside_writable`", ())

# the profile keys that name a folder or a pattern of files, and the kind that owns what they name; the keys that name
# one and are no write target, with the reason (the meta test reads both against the schema)
PROFILE_KEYS = {
    "bundle.root": "card-file", "owner_ask.dir": "asks", "outbox.dir": "outbox", "outbox.id_patterns_file": "task-input",
    "paths.exempt": "exempt", "test_roots": "work-files", "knowledge.files": "work-files", "questions.files": "work-files",
    "deliverables.paths": "work-files", "deliverables.require_base": "work-files", "rules.cards": "work-files",
    "rules.test_for": "work-files", "tests.hermetic_dirs": "work-files", "sessions.file": "task-input",
    "locks.targets": "locked", "state.dir": "state",
}
NOT_TARGETS = {
    "state.shared_dir": "outside the repository: the outside rule judges it, and only the engine writes there",
    "paths.docs": "a list of commits that run no tests: it names no owner",
    "paths.outside_writable": "the outside rule's own list: its rows are `any`",
    "commit.junk": "files nobody commits (K4)",
    "commit.data_patterns": "files nobody commits (K4)",
    "messaging.session_id_watch_until": "an end date `YYYY-MM-DD`, no path: it names no place (MW-110)",
}


def _section(profile, name) -> dict:
    value = profile.get(name) if isinstance(profile, dict) else None
    return value if isinstance(value, dict) else {}


def _strings(value) -> list:
    return [v.replace("\\", "/") for v in value if isinstance(v, str) and v] if isinstance(value, list) else []


def _state(profile) -> str:
    value = _section(profile, "state").get("dir")
    return value.replace("\\", "/").strip("/") if profiles._valid_relative(value) else profiles.DEFAULT_STATE_DIR


def _lock_paths(profile) -> list:
    targets = _section(profile, "locks").get("targets")
    found = []
    for target in targets if isinstance(targets, list) else []:
        found += [p for p in _strings(target.get("paths")) if "<" not in p] if isinstance(target, dict) else []
    return found


def table(profile) -> tuple:
    """The rows for this profile, most specific first: the first row whose pattern matches a path owns it. The profile's own
    `exempt` row is last: a broad exempt pattern never hides a kind the engine knows."""
    bundle, state = profiles.bundle_root(profile), _state(profile)
    asks = profiles.owner_ask(profile)["dir"]
    outbox = profiles.outbox_settings(profile)
    rules, deliver = _section(profile, "rules"), profiles.deliverable_settings(profile)
    test_for = rules.get("test_for")
    work = [*profiles.test_roots(profile), *_strings(_section(profile, "knowledge").get("files")),
            *_strings(_section(profile, "questions").get("files")), *deliver["paths"], *deliver["require_base"],
            *_strings(rules.get("cards")), *([test_for.replace("{id}", "*")] if isinstance(test_for, str) else []),
            *_strings(_section(profile, "tests").get("hermetic_dirs"))]
    task_input = [p for p in (outbox["patterns_file"], _section(profile, "sessions").get("file")) if isinstance(p, str) and p]
    rows = [
        Kind("verdict-file", ORDERER, "a reader writes the rows with `mkway verdict add`, the orderer commits the file",
             (f"{VERDICT_DIR}/*.md",), edit=False),
        Kind("asks", ORDERER, "the orderer writes the ask file and its sources file, and the quote files `mkway ledger add "
                              "--quote-file <file>` reads", (asks,)),
        Kind("order-file", ORDERER, "the orderer writes it after `mkway card new <title>` made the card; the fix-round "
                                    "files `ORDER_<name>.md` are the same kind", (f"{bundle}/cards/*/ORDER*.md",)),
        Kind("card-file", ORDERER, "written with `mkway card new <title>` by the orderer while the card is proposed; after "
                                   "`mkway card open` the card commands or the owner change it", (f"{bundle}/cards/*/CARD.md",)),
        Kind("register", ENGINE, "written by the card commands `mkway card new|take|open|set|close`",
             (f"{bundle}/cards/REGISTER.md",), edit=False),
        Kind("ledger", ENGINE, "`mkway ledger add` appends the rows", (f"{bundle}/ledger/ledger.md",), edit=False),
        Kind("quote-file", ORDERER, "the orderer writes it, `mkway ledger add --quote-file <file>` reads it",
             (f"{bundle}/ledger",)),
        Kind("inbox", ENGINE, "written by `mkway send` and by the Stop hook's refusal record (MW-128) and handoff notice (MW-132), read with "
                              "`mkway inbox <id>`",
             (f"{state}/inbox", f"{state}/pings.jsonl", f"{state}/dead-letter.jsonl"), edit=False),
        Kind("inbox-refusal", ENGINE, "written by the Stop hook when a session stops after a refused engine call and sent "
                                      "nothing: the delivered-refusal record; the orderer reads the inbox row with "
                                      "`mkway inbox <id>` (MW-128)", (f"{state}/refusal-delivered.jsonl",), edit=False),
        Kind("state", ENGINE, "written by the engine's own commands and hooks", (state,), edit=False),
        Kind("outbox-check", READER, "the checker agent writes the check file of a text",
             (f"{outbox['dir']}/**/*.check.md",) if outbox["dir"] else ()),
        Kind("outbox", HOLDER, "the holder writes the text; it leaves only with a check file",
             (outbox["dir"],) if outbox["dir"] else ()),
        Kind("install", OWNER, "the owner installs it: `mkway install` or `mkway upgrade` in their own terminal",
             (f"{bundle}/engine", f"{bundle}/profile.json", f"{bundle}/locks", ".claude"), edit=False),
        Kind("task-input", OWNER, "the owner supplies it", tuple(task_input), edit=False),
        Kind("locked", OWNER, "closed by the lock gate: the owner opens it with `mkway lock open <name>`",
             tuple(_lock_paths(profile)), edit=False),
        Kind("work-files", HOLDER, "the holder writes it inside its card's Paths", tuple(work)),
        Kind("exempt", ANY, "the profile's `paths.exempt` names it: any session may write it",
             tuple(_strings(_section(profile, "paths").get("exempt")))),
    ]
    return tuple(rows)


def patterns_of(name: str, profile) -> tuple:
    """The patterns of the row `name` for this profile (the gates read their lists here: the card files a session may
    always write, the exempt paths, the folders a commit takes freely)."""
    return next((row.patterns for row in table(profile) if row.name == name), ())


def _under(folder, text) -> bool:
    folder = helpers._fold(folder.replace("\\", "/").rstrip("/"))
    return bool(folder) and (text == folder or text.startswith(folder + "/"))


def _below_root(profile, root) -> str:
    """The shared folder (`state.shared_dir`) as a path below `root`, when it is a PROPER subfolder of the root; "" when it is
    unset, is the root itself, is a parent of it, or lies elsewhere (R316 6: the outside case is the branch of `kind_of` for
    a path of None)."""
    shared = _section(profile, "state").get("shared_dir")
    if not (isinstance(shared, str) and shared and root):
        return ""
    folder = helpers._fold(shared.replace("\\", "/").rstrip("/"))
    top = helpers._fold(str(root).replace("\\", "/").rstrip("/"))
    return folder[len(top) + 1:] if top and folder.startswith(top + "/") else ""


def kind_of(path, profile, outside=None, root=None) -> Optional[Kind]:
    """The row that owns `path`, or None. `path` is a repository path (posix, relative to the task root); None stands for a
    target outside the root, judged by `outside` (the shell's record: `.abs` its absolute form, `.matched` true when the
    shell matched it against the outside-writable list). `.` (the root itself) has no owner."""
    if path is None:
        shared = _section(profile, "state").get("shared_dir")
        absolute = getattr(outside, "abs", "") or ""
        if isinstance(shared, str) and shared and absolute and _under(shared, helpers._fold(absolute.replace("\\", "/"))):
            return next(k for k in table(profile) if k.name == "state")
        return OUTSIDE_ROW if getattr(outside, "matched", False) else None
    if not isinstance(path, str) or path == ".":
        return None
    if _under(_below_root(profile, root), helpers._fold(path)):  # MW-129, R316 6: every path under the shared folder is `state`
        return next(k for k in table(profile) if k.name == "state")
    for row in table(profile):
        if any(helpers.matches(path, pattern) for pattern in row.patterns):
            return row
    return None


def owner_of(path, profile, outside=None, root=None) -> Optional[str]:
    """The one role that owns `path` (see `kind_of`), or None when no row matches: such a path is refused unless a card's
    Paths hold it."""
    row = kind_of(path, profile, outside, root)
    return row.role if row else None


def _who(row: Kind) -> str:
    return "open to every session" if row.role == ANY else f"the {row.role}'s"


def describe(path, profile, outside=None, root="") -> str:
    """One sentence for a refusal: who owns the path and which command writes it, or that it has no owner row and the way
    out. For a target outside the root (`path` None) the way out is the outside rule's, naming `root` when given."""
    row = kind_of(path, profile, outside, root or None)
    if path is None:
        raw = getattr(outside, "raw", "") or "a path outside the root"
        if row is None:
            return f"{raw} is outside your root and has no owner row: {WAY_OUT_OUTSIDE.format(root=root or 'your root')}"
        return f"{raw} is {_who(row)} ({row.name}): {row.command}"
    if row is None:
        return f"`{path}` has no owner row: {WAY_OUT_NO_ROW}"
    return f"`{path}` is {_who(row)} ({row.name}): {row.command}"
