"""Asks that do not stop the work (card MW-014): the ask file's fields, its status, who wrote it.

An ask file is `<asks dir>/<name>_ask.md` (the folder is `owner_ask.dir`; the id of the ask is `<name>`). Beside its
free text it holds five lines: `default: <text or none>`, `deadline: <ISO local time or none>`, `blocked: <what waits,
or none>`, `reversible: yes|no`, `status: open`. The later statuses are `answered`, `default-taken` and `withdrawn`;
the owner sets them in an editor, or the session's commands do (`mkway ask default`, `mkway ask answered`).

Who wrote an ask is a record `ask <name>` of that session (`<state.dir>/records.jsonl`), written by the post step after
the write; the first record of a name is its owner. The age of an ask is the age of its file.

This module reads and writes ask files and holds the text of the board, the start line and the reminder; the gate
(`gate_owner_ask`) and the commands (`mkway asks`, `mkway ask ...`) call it. No task name and no natural-language word
is in this file: the line shapes are the file format.
"""
from __future__ import annotations

import datetime
import os
import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import profiles
import records
# The ask file's five lines are read by the pure core (card MW-065); they are re-exported here for the callers.
from core_ask import (ASK_SUFFIX, NONE, OPEN, SHAPES, STATUSES, _FIELD, field_problems, fields,  # noqa: F401
                      parse_deadline)

RECORD_KIND = "ask"


def folder(root, profile) -> Path:
    return Path(root) / profiles.owner_ask(profile)["dir"]


def _now(like: Optional[datetime.datetime] = None) -> datetime.datetime:
    return datetime.datetime.now(like.tzinfo) if like is not None and like.tzinfo else datetime.datetime.now()


@dataclass
class Ask:
    id: str
    path: Path
    text: str
    status: str
    default: str
    blocked: str
    reversible: str
    deadline: Optional[datetime.datetime]
    mtime: float
    deadline_raw: str = NONE

    @property
    def is_open(self) -> bool:
        return self.status == OPEN

    def age_seconds(self) -> float:
        return max(0.0, datetime.datetime.now().timestamp() - self.mtime)

    def past_deadline(self) -> bool:
        return self.deadline is not None and _now(self.deadline) >= self.deadline


def read(path) -> Ask:
    """One ask file. A field that is missing or unusable reads as `not established`; a deadline that cannot be read is
    none (the board never fails on a hand-edited file)."""
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    found = fields(text)
    try:
        deadline = parse_deadline(found.get("deadline", NONE))
    except ValueError:
        deadline = None
    unknown = "not established"
    return Ask(id=path.name[:-len(ASK_SUFFIX)], path=path, text=text,
               status=(found.get("status") or unknown).strip().lower(), default=found.get("default") or unknown,
               blocked=found.get("blocked") or unknown, reversible=(found.get("reversible") or unknown).lower(),
               deadline=deadline, mtime=path.stat().st_mtime, deadline_raw=found.get("deadline") or NONE)


def all_asks(root, profile) -> list:
    """Every `<name>_ask.md` of the asks folder (not its subfolders), oldest first, a file that cannot be read left out."""
    base = folder(root, profile)
    out = []
    try:
        names = sorted(p for p in base.iterdir() if p.is_file() and p.name.lower().endswith(ASK_SUFFIX))
    except OSError:
        return []
    for path in names:
        try:
            out.append(read(path))
        except OSError:
            continue
    return sorted(out, key=lambda a: (a.mtime, a.id))


def find(root, profile, ask_id: str) -> Optional[Ask]:
    for ask in all_asks(root, profile):
        if ask.id == ask_id:
            return ask
    return None


def owners(state) -> dict:
    """ask id -> the session that wrote it first (its first `ask` record with a session id)."""
    found: dict = {}
    for row in records.rows(state):
        if row.get("kind") == RECORD_KIND and row.get("session_id") and isinstance(row.get("value"), str):
            found.setdefault(row["value"], row["session_id"])
    return found


def open_of_session(root, profile, session) -> list:
    """The ids of the asks of `session` that still have `status: open` (a record whose file is gone counts for nothing)."""
    if not session:
        return []
    mine = {ask_id for ask_id, who in owners(profiles.state_dir(root, profile)).items() if who == session}
    return [a.id for a in all_asks(root, profile) if a.id in mine and a.is_open]


def record_owner(root, profile, session, ask_id: str) -> bool:
    """Write the `ask` record of this session for this ask, when the ask has no owner yet. True when a row was written."""
    state = profiles.state_dir(root, profile)
    if not session or ask_id in owners(state):
        return False
    records.append(state, session, RECORD_KIND, ask_id, by="session")
    return True


# --- the notification (rule 4) -----------------------------------------------------------------------------------

NOTIFY_SECONDS = 10  # the command's limit; it never holds the session longer
_PLACEHOLDER = re.compile(r"\{(file|line)\}")
LINE_MAX = 200


def question_line(ask: Ask) -> str:
    """The first line of the ask that is not a field line, without leading `#` and spaces; the id when there is none."""
    for raw in ask.text.splitlines():
        text = raw.strip().lstrip("#").strip()
        if text and not _FIELD.match(text):
            return text[:LINE_MAX]
    return ask.id


def notify_line(ask: Ask) -> str:
    deadline = ask.deadline.isoformat(timespec="minutes") if ask.deadline else NONE
    raw = fields(ask.text).get("deadline")
    return f"{question_line(ask)} | default: {ask.default} | deadline: {raw.strip() if raw else deadline}"


def split_command(text: str) -> list:
    """The words of a command line, read here and never by a shell: the placeholders are filled after the split, so a
    question text is one argument and runs nothing. On Windows a backslash is a path character, so quotes are removed."""
    if os.name == "nt":
        words = shlex.split(text, posix=False)
        return [w[1:-1] if len(w) >= 2 and w[0] == w[-1] and w[0] in "\"'" else w for w in words]
    return shlex.split(text)


def notify(root, profile, ask: Ask):
    """Run `notify.command` for this ask: (True, text) when it ran and exited 0, else (False, why). It never raises."""
    command = profiles.notify_command(profile)
    if command is None:
        return None
    values = {"file": str(ask.path), "line": notify_line(ask)}
    try:
        argv = [_PLACEHOLDER.sub(lambda m: values[m.group(1)], word) for word in split_command(command)]
        if not argv:
            return False, "notify.command has no program"
        done = subprocess.run(argv, cwd=str(root), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, timeout=NOTIFY_SECONDS)
    except subprocess.TimeoutExpired:
        return False, f"the notify command ran over {NOTIFY_SECONDS} s and was stopped"
    except (OSError, ValueError) as exc:
        return False, f"the notify command could not run ({exc.__class__.__name__})"
    if done.returncode != 0:
        return False, f"the notify command exited with {done.returncode}"
    return True, f"notify command run for ask {ask.id}"


# --- the board, the start line, the reminder (rule 5) ------------------------------------------------------------

DEFAULT_RECORD = "ask-default"  # the record of a default taken (`mkway ask default`), counted on the start line
UNKNOWN = "not established"


def age_text(seconds: float) -> str:
    """`<n>m` under an hour, `<n>h` under two days, else `<n>d` (whole units, rounded down)."""
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    return f"{hours}h" if hours < 48 else f"{hours // 24}d"


def card_of(root, profile, ask_id: str) -> str:
    """The card the session that wrote the ask holds, `not established` when no session wrote it or it holds none."""
    import register
    state = profiles.state_dir(root, profile)
    session = owners(state).get(ask_id)
    try:
        closed = register.closed_ids(root, profile)
    except Exception:
        closed = None
    return records.session_card(state, session, closed) or UNKNOWN


def board_lines(root, profile) -> list:
    """One row per ask file, oldest first: id, card, age, deadline, default, status, blocked part."""
    return [f"{a.id} | card {card_of(root, profile, a.id)} | age {age_text(a.age_seconds())} | "
            f"deadline {a.deadline_raw} | default {a.default} | status {a.status} | blocked {a.blocked}"
            for a in all_asks(root, profile)] or ["no ask files"]


def defaults_taken(root, profile) -> int:
    """The `ask-default` records at or after the baseline of the owner's last re-seal; all of them with no baseline."""
    import register
    since = ""
    try:
        base = register.read_baseline(root, profile)
        since = base["time"] if base else ""
    except Exception:
        since = ""
    return sum(1 for r in records.rows(profiles.state_dir(root, profile))
               if r.get("kind") == DEFAULT_RECORD and str(r.get("time", "")) >= since)


def start_line(root, profile) -> str:
    opened = [a for a in all_asks(root, profile) if a.is_open]
    oldest = age_text(max(a.age_seconds() for a in opened)) if opened else "none"
    late = sum(1 for a in opened if a.past_deadline())
    return (f"open asks: {len(opened)} (oldest {oldest}); past deadline: {late}; defaults taken since the owner's "
            f"last re-seal: {defaults_taken(root, profile)}")


def reminders(root, profile, session) -> list:
    """One line for each open ask of this session that is past its deadline."""
    if not session:
        return []
    mine = set(open_of_session(root, profile, session))
    return [f"ask {a.id} is past its deadline: take the default with `mkway ask default {a.id}` if reversible, else "
            f"keep waiting" for a in all_asks(root, profile) if a.id in mine and a.past_deadline()]


# --- the session's commands (rule 6) -----------------------------------------------------------------------------

_STATUS_LINE = re.compile(r"^(status:[ \t]*)(.*?)([ \t\r]*)$", re.M | re.I)


ANSWER_KIND = "ask-answered"  # MW-119: the proof-file record of an answer recorded in the owner's name


class AskError(Exception):
    """A refusal of `ask default` or `ask answered`: a reason id and the text the session reads."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason
        self.message = message


def set_status(path, status: str) -> None:
    """Replace the value of the first `status:` line, the rest of the file byte for byte (line breaks included)."""
    with open(path, "r", encoding="utf-8", newline="") as fh:
        text = fh.read()
    changed, count = _STATUS_LINE.subn(lambda m: m.group(1) + status + m.group(3), text, count=1)
    if count != 1:
        raise AskError("ask-not-open", f"{Path(path).name} has no status line")
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(changed)


def _open_ask(root, profile, ask_id: str) -> Ask:
    """The open ask named `ask_id` (a name of the asks folder, never a path), else the refusal."""
    ask = find(root, profile, ask_id) if ask_id and not re.search(r"[\\/]", ask_id) else None
    if ask is None:
        raise AskError("ask-unknown", f"no ask named {ask_id!r} in the asks folder (`mkway asks` lists them)")
    if not ask.is_open:
        raise AskError("ask-not-open", f"ask {ask.id} has status {ask.status}, not open; nothing changed")
    return ask


def _rel(root, ask: Ask) -> str:
    try:
        return ask.path.resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return ask.path.as_posix()


def take_default(root, profile, ask_id: str, by: Optional[str] = None):
    """`mkway ask default <id>` (MW-014, rule 6): only for `reversible: yes` once the deadline has passed. It writes the
    ledger row «default taken: <default text>, ask <id>» with `by` (MW-015: the session, never the owner's label), then
    sets `status: default-taken`. Returns (ask, ledger row). Raises AskError."""
    import ledger
    ask = _open_ask(root, profile, ask_id)
    if ask.reversible != "yes":
        raise AskError("ask-not-reversible", f"ask {ask.id} is not reversible: it stays waiting; the owner decides")
    if ask.deadline is None:
        raise AskError("ask-deadline-not-passed", f"ask {ask.id} has no deadline, so its default is never taken; keep "
                                                  f"waiting")
    if not ask.past_deadline():
        raise AskError("ask-deadline-not-passed", f"the deadline of ask {ask.id} ({ask.deadline_raw}) has not passed; "
                                                  f"keep working on the rest and wait")
    if ask.default.strip().lower() in (NONE, UNKNOWN):
        raise AskError("ask-no-default", f"ask {ask.id} has no default to take; keep waiting")
    row = ledger.add(root, profile, card=card_of(root, profile, ask.id), topic=f"ask {ask.id} default taken",
                     quote=f"default taken: {ask.default}, ask {ask.id}", source=f"ask file {_rel(root, ask)}",
                     by=by)
    set_status(ask.path, "default-taken")
    return ask, row


def answer(root, profile, ask_id: str, quote: str, caller: Optional[str] = None, lead: bool = False, state=None):
    """`mkway ask answered <id>` (MW-014, rule 6; MW-119): sets `status: answered` and writes the ledger row with the owner's
    words. It runs only in the lead: `caller` is the session id of the one-use permit and `lead` says it is a registered
    lead, else `ask-answered-not-lead` (R272 G5). The row is `session:<id>`, its source starts with `owner`, never `by: owner`;
    one record of kind `ask-answered` (ask, session, source, quote, time) goes to the proof file in `state` for the board.
    `caller=None` is the owner's terminal, held as before until the chief rules (MW119-D1). Returns (ask, ledger row)."""
    import core_ask
    import ledger
    ask = _open_ask(root, profile, ask_id)
    if caller is None:
        row = ledger.add(root, profile, card=card_of(root, profile, ask.id), topic=f"ask {ask.id} answered", quote=quote,
                         source=f"ask file {_rel(root, ask)}", by=ledger.formats()["owner_who"])  # the owner's terminal
        set_status(ask.path, "answered")
        return ask, row
    verdict = core_ask.answer_decision(caller, lead)
    if verdict.kind != "allow":
        raise AskError(verdict.reason, verdict.text.split(": ", 1)[1])
    row = ledger.add(root, profile, card=card_of(root, profile, ask.id), topic=f"ask {ask.id} answered", quote=quote,
                     source=f"owner, ask file {_rel(root, ask)}", by=f"session:{caller}")
    set_status(ask.path, "answered")
    if state is not None:
        import logs
        import proof
        logs.append_jsonl(Path(state) / proof.FILE, {"kind": ANSWER_KIND, "ask": ask.id, "session": caller, "source": "owner",
                                                    "quote": quote, "time": logs.now().isoformat(timespec="milliseconds")})
    return ask, row
