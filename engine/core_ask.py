"""The pure decisions of the ask family (card MW-065): the owner-ask edit gate and stop gate (MW-007, MW-008, MW-014),
the search gate (MW-008) and the outbox check write gate (MW-019).

Each decision is a function of a Facts record the gate's shell built: the event's tool name and tool input, the path as
the engine reads it, the text of the files the decision needs, the profile's settings, the transcript as parsed entries,
the records as rows. It returns a `Decision` (allow, refuse, warn or log with a reason id and a text); the shell turns it
into a gate verdict and writes any record. This module reads no disk, no process, no environment and no clock, and
imports no I/O module of the engine; a test fails if it does (`tests/core/test_ask_core_is_pure.py`).

No task name and no natural-language word is in this file: the line shapes (`kind:`, `checked:`, `>`, `sha256:`) are the
file format; the texts are those the gates always gave.
"""
from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, field
from typing import Optional

import helpers

WRITE_TOOLS = ("Write", "Edit", "MultiEdit")
QUESTION_TOOL = "AskUserQuestion"


# ---- the decision ---------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Decision:
    kind: str  # allow | refuse | warn | log
    reason: Optional[str] = None
    text: str = ""


def allow() -> Decision:
    return Decision("allow")


def refuse(reason: str, text: str) -> Decision:
    return Decision("refuse", reason, text)


def warn(reason: str, text: str) -> Decision:
    return Decision("warn", reason, text)


def log(reason: str, text: str) -> Decision:
    return Decision("log", reason, text)


# ---- the ask file: its five lines (moved here from `asks.py`, which re-exports them) -------------------------------

ASK_SUFFIX = "_ask.md"
OPEN = "open"
STATUSES = (OPEN, "answered", "default-taken", "withdrawn")
SHAPES = {  # field -> the line shape a refusal names
    "default": "default: <text or none>",
    "deadline": "deadline: <ISO local time or none>",
    "blocked": "blocked: <what waits, or none>",
    "reversible": "reversible: yes|no",
    "status": "status: open",
}
_FIELD = re.compile(r"^(default|deadline|blocked|reversible|status):[ \t]*(.*?)[ \t\r]*$", re.M | re.I)
NONE = "none"


def parse_deadline(value: str) -> Optional[datetime.datetime]:
    """None for `none`; the time for an ISO time (naive = local, a zone is kept); ValueError for anything else."""
    text = (value or "").strip()
    if text.lower() == NONE:
        return None
    if not text:
        raise ValueError("empty")
    return datetime.datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)


def fields(text: str) -> dict:
    """The first line of each field of `text`, as written (value stripped); a field with no line is not a key."""
    found: dict = {}
    for match in _FIELD.finditer(text or ""):
        found.setdefault(match.group(1).lower(), match.group(2))
    return found


def field_problems(text: str, *, need_open: bool = True) -> list:
    """The field names whose line is missing or has no usable value, in the order of `SHAPES`. With `need_open` the
    status must be `open` (what a session may write); else any of the four statuses."""
    found = fields(text)
    bad = []
    for name in SHAPES:
        value = found.get(name)
        if value is None or not value.strip():
            bad.append(name)
        elif name == "deadline":
            try:
                parse_deadline(value)
            except ValueError:
                bad.append(name)
        elif name == "reversible" and value.strip().lower() not in ("yes", "no"):
            bad.append(name)
        elif name == "status":
            allowed = (OPEN,) if need_open else STATUSES
            if value.strip().lower() not in allowed:
                bad.append(name)
    return bad


# ---- the turn of a transcript ---------------------------------------------------------------------------------------

def turn_split(entries):
    """(entries after the last real user message, that user message or None). A real user message is a `user` entry
    whose content is a string or has a text block; a tool result is not one."""
    start = -1
    for i, entry in enumerate(entries):
        message = entry.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if entry.get("type") == "user" and (isinstance(content, str) or (isinstance(content, list) and any(
                isinstance(b, dict) and b.get("type") == "text" for b in content))):
            start = i
    return list(entries[start + 1:]), (entries[start] if start >= 0 else None)


def blocks(entries, kind):
    for entry in entries:
        message = entry.get("message") if entry.get("type") == "assistant" else None
        content = message.get("content") if isinstance(message, dict) else None
        for block in content if isinstance(content, list) else []:
            if isinstance(block, dict) and block.get("type") == kind:
                yield block


# ---- the owner-ask edit gate ----------------------------------------------------------------------------------------

ASK_FILE = re.compile(r"^(?P<name>.+)_ask\.md$", re.I)
SOURCES_SUFFIX = "_sources.md"
KINDS = "substance|session|lock"
KIND_LINE = re.compile(r"^kind:[ \t]*(substance|session|lock)[ \t\r]*$", re.M | re.I)
SESSION_LINE = re.compile(r"^checked:[ \t]*ListAgents\b", re.M | re.I)
LOCK_LINE = re.compile(r"^checked:[ \t]*\S", re.M | re.I)
HOW = ("Before an ask to the owner, write down what was checked: a sources file beside the ask, with the lines of "
       "its kind (README, «Questions to the owner»)")
LEDGER_SOURCE = "ledger"  # MW-008: the source of the past decisions has its own lines, not the contradictions form
LEDGER_COUNT = re.compile(r"^ledger:[ \t]*(\d+)[ \t]+hits?\b", re.M | re.I)
LEDGER_QUOTE = re.compile(r"^>[ \t]*ledger:[ \t]*\S", re.M | re.I)
SEARCH_LINE = re.compile(r"^search:[ \t]*\S", re.M | re.I)
FIELDS_HOW = ("An ask carries five field lines, and the session goes on with the work that does not wait for the "
              "answer (README, «Asks that do not stop the work»)")


@dataclass(frozen=True)
class EditFacts:
    """What the owner-ask edit gate decides on. `rel` is the repo-relative form of the call's `file_path` (None when
    there is no path, or it is outside the root). The four file facts are read by the shell only for an ask path."""
    tool_name: Optional[str]
    tool_input: object
    rel: Optional[str]
    dir: str  # `owner_ask.dir`
    sources: tuple  # `owner_ask.sources`
    max_open: int  # `owner_ask.max_open`
    tool_allowed: bool  # `owner_ask.tool_allowed`
    session_id: Optional[str] = None
    sources_text: Optional[str] = None  # the sources file beside the ask; None when it cannot be read
    ask_text: str = ""  # the ask file on disk now, "" when it cannot be read
    ask_exists: bool = False
    open_ids: tuple = ()  # the asks of this session with `status: open`
    open_error: Optional[str] = None  # the class name of the failure that kept the shell from reading `open_ids`


def ask_target(rel, folder_setting: str):
    """(repo-relative path, name) when `rel` is `<asks dir>/<name>_ask.md`, else None."""
    if not isinstance(rel, str) or not rel or rel == ".":
        return None
    folder, _, base = rel.rpartition("/")
    wanted = "" if folder_setting == "." else folder_setting
    match = ASK_FILE.match(base)
    if match is None or helpers._fold(folder) != helpers._fold(wanted):
        return None
    return rel, match.group("name")


def _lines(text: str, source: str):
    """(count line found, quote line found) for one source name."""
    name = re.escape(source)
    count = re.search(rf"^{name}:[ \t]*\d+[ \t]+contradictions?\b", text, re.M | re.I)
    quote = re.search(rf"^>[ \t]*{name}:[ \t]*\S", text, re.M | re.I)
    return count is not None, quote is not None


def _ledger_missing(text: str) -> list:
    """The lines a `ledger` source still needs: `ledger: N hits`; with N above 0 a `> ledger: <verbatim>` line; with N
    0 a line `search: <record id>` (the record of the `mkway search` that found nothing)."""
    count = LEDGER_COUNT.search(text)
    if count is None:
        return ["ledger: N hits"]
    if int(count.group(1)) > 0:
        return [] if LEDGER_QUOTE.search(text) else ["> ledger: <verbatim quote>"]
    return [] if SEARCH_LINE.search(text) else ["search: <record id>"]


def sources_problem(text: Optional[str], name: str, sources):
    """None when the sources file beside the ask holds what its kind needs, else (reason id, message). `text` is None
    when the file cannot be read."""
    shown = f"{name}{SOURCES_SUFFIX}"
    if text is None:
        return "ask-sources-missing", f"{shown} does not exist beside the ask (or cannot be read). {HOW}"
    found = KIND_LINE.search(text)
    if not found:
        return "ask-sources-kind", f"{shown} has no line `kind: {KINDS}`. {HOW}"
    kind = found.group(1).lower()
    missing = []
    if kind == "substance":
        if LEDGER_SOURCE in sources:
            missing += _ledger_missing(text)
        pairs = [(s, *_lines(text, s)) for s in sources if s != LEDGER_SOURCE]
        missing += [f"{s}: N contradictions" for s, count, _quote in pairs if not count]
        missing += [f"> {s}: <verbatim quote>" for s, _count, quote in pairs if not quote]
    elif kind == "session":
        missing += [] if SESSION_LINE.search(text) else ["checked: ListAgents"]
    elif not LOCK_LINE.search(text):
        missing.append("checked: <lock state>")
    if missing:
        return "ask-sources-lines", f"{shown} (kind {kind}) lacks " + ", ".join(f"`{m}`" for m in missing) + f". {HOW}"
    return None


def resulting_text(tool_name, tool_input, disk_text: str) -> str:
    """The text of the file after this write: a Write's content; for an Edit or a MultiEdit the file on disk
    (`disk_text`) with its edits applied in order (an edit whose text is not found changes nothing, as the tool would
    refuse it)."""
    if tool_name == "Write":
        content = tool_input.get("content")
        return content if isinstance(content, str) else ""
    text = disk_text
    edits = tool_input.get("edits") if tool_name == "MultiEdit" else [tool_input]
    for edit in edits if isinstance(edits, list) else []:
        old, new = (edit.get("old_string"), edit.get("new_string")) if isinstance(edit, dict) else (None, None)
        if not isinstance(old, str) or not isinstance(new, str):
            continue
        if old == "":
            text = new if text == "" else text
        elif old in text:
            text = text.replace(old, new) if edit.get("replace_all") else text.replace(old, new, 1)
    return text


def fields_problem(text: str, rel: str):
    """None when the ask file this write leaves holds its five lines, else (`ask-fields-missing`, text naming each)."""
    missing = field_problems(text)
    if not missing:
        return None
    shown = ", ".join(f"`{SHAPES[m]}`" for m in missing)
    return "ask-fields-missing", f"{rel.rpartition('/')[2]} lacks {shown}. {FIELDS_HOW}"


def open_problem(f: EditFacts):
    """None unless this write starts a NEW ask file while the session already has `max_open` asks with `status: open`:
    then (`ask-already-open`, text: add to the open ask, or wait). A write to an ask that is already on disk is an
    addition to it. A call with no session id is never refused here."""
    if not f.session_id or f.ask_exists:
        return None
    if f.open_error is not None:
        failed = failed_check(f.open_error)
        return failed.reason, failed.text
    mine = f.open_ids
    if len(mine) < f.max_open:
        return None
    return "ask-already-open", (f"this session already has {len(mine)} open ask(s): {', '.join(mine)} "
                                f"(owner_ask.max_open {f.max_open}): add to the open ask, or wait for its "
                                f"answer; do not write a second ask. {FIELDS_HOW}")


def failed_check(error_name: str) -> Decision:
    """The refusal when the shell could not read what the check needs: an ask path fails closed."""
    return refuse("ask-sources-missing", f"the sources check failed ({error_name}). {HOW}")


def _question(f: EditFacts) -> Decision:
    """`AskUserQuestion`: refused `ask-tool-off` unless `owner_ask.tool_allowed`; the text names the file route."""
    if f.tool_allowed:
        return allow()
    return refuse("ask-tool-off", (
        f"the pop-up question tool is off: it stops the work until the owner answers. Ask by writing "
        f"{f.dir}/<name>_ask.md with its sources file, with the lines `default: <text or none>`, "
        f"`deadline: <ISO local time or none>`, `blocked: <what waits, or none>`, `reversible: yes|no` and "
        f"`status: open`, then go on with the work that does not depend on the answer (README, «Asks that do not stop "
        f"the work»)"))


def decide_edit(f: EditFacts) -> Decision:
    """The owner-ask edit gate (PreToolUse)."""
    if f.tool_name == QUESTION_TOOL:
        return _question(f)
    if f.tool_name not in WRITE_TOOLS or not isinstance(f.tool_input, dict):
        return allow()
    target = ask_target(f.rel, f.dir)
    if target is None:
        return allow()
    rel, name = target
    try:
        problem = (sources_problem(f.sources_text, name, f.sources)
                   or fields_problem(resulting_text(f.tool_name, f.tool_input, f.ask_text), rel) or open_problem(f))
    except Exception as exc:  # fail closed, for an ask path only
        return failed_check(exc.__class__.__name__)
    return refuse(*problem) if problem else allow()


# ---- the owner-ask stop gate ----------------------------------------------------------------------------------------

@dataclass(frozen=True)
class StopFacts:
    """What the owner-ask stop gate decides on. `entries` are the transcript's entries as parsed (None when the
    transcript cannot be read). `rels` maps the `file_path` of each write in the transcript to its repo-relative form
    (None when outside the root); `on_disk` is the set of repo-relative paths that are files now."""
    hook_active: bool
    last_message: object
    entries: Optional[tuple]
    markers: tuple
    dir: str
    rels: dict = field(default_factory=dict)
    on_disk: frozenset = frozenset()


def _wrote_ask(f: StopFacts, turn) -> bool:
    for block in blocks(turn, "tool_use"):
        if block.get("name") not in WRITE_TOOLS or not isinstance(block.get("input"), dict):
            continue
        path = block["input"].get("file_path")
        target = ask_target(f.rels.get(path) if isinstance(path, str) else None, f.dir)
        if target is not None and target[0] in f.on_disk:
            return True
    return False


def decide_stop(f: StopFacts) -> Decision:
    """A final reply with a marker line must have written an ask file since the last real user message. With
    `stop_hook_active` it never blocks, so one block cannot trap a session."""
    if f.hook_active:
        return allow()
    readable = f.entries is not None
    turn = turn_split(f.entries)[0] if readable else []
    final = f.last_message
    if not isinstance(final, str):
        texts = [b["text"] for b in blocks(turn, "text") if isinstance(b.get("text"), str)]
        final = texts[-1] if texts else ""
    markers = "|".join(re.escape(m) for m in f.markers)
    found = re.search(rf"^[ \t]*(?:\*\*)?({markers})", final, re.M)
    if found is None or _wrote_ask(f, turn):
        return allow()
    unread = "" if readable else " (the transcript could not be read, so no write could be seen)"
    return refuse("ask-not-written", (
        f"the reply has a line that starts with `{found.group(1)}`, but this turn wrote no "
        f"{f.dir}/<name>_ask.md{unread}. An ask goes to the owner only after it is written to that file "
        f"with its sources file. {HOW}. If what was checked already decides it, do not ask: act, and report it "
        f"without the marker"))


# ---- the search gate ------------------------------------------------------------------------------------------------

SEARCH_HOW = "run `mkway search <words>` first, then ask"


@dataclass(frozen=True)
class SearchFacts:
    """What the search gate decides on. `patterns` is `questions.files` of the profile (None when it is not a list);
    `rel` the repo-relative form of the call's `file_path`; `entries` the transcript as parsed (None when it cannot be
    read); `rows` the engine's records (`rows_error` the class name of the failure that kept the shell from reading
    them)."""
    tool_name: Optional[str]
    tool_input: object
    patterns: object
    rel: Optional[str]
    session_id: Optional[str]
    entries: Optional[tuple] = None
    rows: tuple = ()
    rows_error: Optional[str] = None


def _time(value) -> Optional[datetime.datetime]:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=datetime.timezone.utc)


def search_gated(f: SearchFacts) -> bool:
    if f.tool_name == QUESTION_TOOL:
        return True
    if f.tool_name not in WRITE_TOOLS or not isinstance(f.tool_input, dict):
        return False
    path = f.tool_input.get("file_path")
    if not isinstance(f.patterns, list) or not isinstance(path, str) or not path:
        return False
    if f.rel is None:
        return False
    fold = helpers._fold
    for pattern in f.patterns:
        if isinstance(pattern, str) and pattern.strip():
            text = pattern.strip().replace("\\", "/")
            text = text[2:] if text.startswith("./") else text
            if helpers.glob_re(fold(text)).fullmatch(fold(f.rel)):
                return True
    return False


def unverified(why: str) -> Decision:
    return log("search-unverified", f"the turn boundary could not be established ({why}), so the search check was "
                                    f"skipped; the question is allowed")


def _search_verdict(f: SearchFacts) -> Decision:
    if not f.session_id:
        return unverified("the hook input has no session id")
    if f.entries is None:
        return unverified("the transcript cannot be read")
    _after, user = turn_split(f.entries)
    floor = None
    if user is not None:
        floor = _time(user.get("timestamp"))
        if floor is None:
            return unverified("the last user message has no time")
    if f.rows_error is not None:
        return unverified(f.rows_error)
    for row in f.rows:
        if row.get("kind") != "search" or row.get("session_id") != f.session_id:
            continue
        when = _time(row.get("time"))
        if when is not None and (floor is None or when > floor):
            return allow()
    return refuse("search-missing", f"this session has no search record after the last user message. {SEARCH_HOW}. A "
                                    f"question to the owner goes out only after a search of the past decisions "
                                    f"(README, «Decisions: search before asking»)")


def decide_search(f: SearchFacts) -> Decision:
    """A question to the owner needs a search record of this session newer than the last real user message. It fails
    OPEN: when the turn boundary cannot be established the call is allowed and the verdict is a log row."""
    try:
        if not search_gated(f):
            return allow()
    except Exception:  # not provably a gated call: not this gate's call
        return allow()
    try:
        return _search_verdict(f)
    except Exception as exc:  # fail open, with a row
        return unverified(exc.__class__.__name__)


# ---- the outbox check write gate ------------------------------------------------------------------------------------

MISMATCH = "check-sha-mismatch"
OUTBOX_HOW = "README, «Outbox check: a text leaves only after a fresh reader»"
_SHA_VALUE = re.compile(r"sha256:[ \t]*([0-9A-Za-z]*)", re.I)


def sha_values(text: str) -> list:
    """The digest after every `sha256:` in a check's text, lower case (empty for a form with no digest)."""
    return [m.group(1).lower() for m in _SHA_VALUE.finditer(text or "")]


def under_dir(folder, rel) -> bool:
    return bool(folder) and isinstance(rel, str) and helpers._fold(rel).startswith(helpers._fold(folder) + "/")


def doc_of(folder, end: str, rel) -> Optional[str]:
    """The document a check file belongs to: `rel` without the suffix `end`, when `rel` is `<outbox.dir>/.../<name><end>`;
    else None."""
    if not under_dir(folder, rel) or not helpers._fold(rel).endswith(helpers._fold(end)):
        return None
    doc = rel[:-len(end)]
    return doc if doc.rstrip("/") != folder and not doc.endswith("/") else None


@dataclass(frozen=True)
class OutboxFacts:
    """What the outbox write gate decides on. `rel` is the repo-relative form of the call's `file_path` (None when
    there is none); `suffix` the check suffix; `doc_sha` the sha256 of the document now (None when it does not exist or
    cannot be read); `check_text` the check file on disk now, "" when it cannot be read (an Edit is applied to it);
    `error` the class name of a failure that kept the shell from reading the two."""
    tool_name: Optional[str]
    tool_input: object
    rel: Optional[str]
    dir: Optional[str]
    suffix: str
    doc_sha: Optional[str] = None
    check_text: str = ""
    error: Optional[str] = None


def outbox_target(f: OutboxFacts):
    """(check path, document path) when this call writes a check file under `outbox.dir`, else None."""
    if f.tool_name not in WRITE_TOOLS or not isinstance(f.tool_input, dict) or not f.dir or not isinstance(f.rel, str):
        return None
    document = doc_of(f.dir, f.suffix, f.rel) if f.rel else None
    return (f.rel, document) if document else None


def decide_check_write(f: OutboxFacts) -> Decision:
    """A write that leaves a check file whose `sha256:` line is missing, or is not the sha256 of the document now, is
    refused `check-sha-mismatch`; every other path, tool and profile passes."""
    target = outbox_target(f)
    if target is None:
        return allow()
    rel, document = target
    how = f"`mkway outbox` lists every file with its check state ({OUTBOX_HOW})"
    if f.error is not None:  # fail closed, for a check path only
        return refuse(MISMATCH, f"the sha256 of {document} could not be compared ({f.error}). {how}")
    want = f.doc_sha
    if want is None:
        return refuse(MISMATCH, f"{rel} is a check for {document}, which does not exist (or cannot be read): a "
                                f"check belongs to the text a fresh reader read. {how}")
    values = sha_values(resulting_text(f.tool_name, f.tool_input, f.check_text))
    if values and all(v == want for v in values):
        return allow()
    if not values:
        return refuse(MISMATCH, f"{rel} has no `sha256:` line. A check names the sha256 of the exact text the fresh "
                                f"reader read: write the line `sha256: {want}` (the sha256 of {document} now). {how}")
    shown = next(v for v in values if v != want)
    return refuse(MISMATCH, f"{rel} holds `sha256: {shown or '(no digest)'}`, but the sha256 of {document} now is "
                            f"{want}: write the line `sha256: {want}`. If the document changed after the fresh "
                            f"reader ran, run the reader again on the file as it is now before the check is "
                            f"written. {how}")


def decide_stale_reminder(stale: tuple, first: bool) -> Decision:
    """At Stop: a warn that names each file (repo-relative paths in `stale`) whose check is stale, once per session and
    set of files (`first`). It never blocks."""
    if not stale or not first:
        return allow()
    return warn("outbox-changed-after-check", (
        f"outbox: {', '.join(stale)} changed after its check. A text leaves only after a fresh reader has "
        f"read it as it is now: run the checker again and write the new check; `mkway outbox` shows the state of every "
        f"file ({OUTBOX_HOW})"))


# ---- `mkway ask answered`: the intake role only (card MW-119) -------------------------------------------------------

ANSWER_NOT_LEAD = "ask-answered-not-lead"


def answer_decision(caller: str, lead: bool) -> Decision:
    """`ask answered` writes the owner's words, so it runs only in the intake role, the lead (MW-119; R272 G5). `caller` is
    the session id the lock gate's one-use permit names, empty when none was found; `lead` says it is a registered lead."""
    if not (caller or "").strip():
        return refuse(ANSWER_NOT_LEAD, f"{ANSWER_NOT_LEAD}: the session id of this call is not established, so the owner's "
                                       f"answer is not recorded; the lead records it with `mkway ask answered <id>`, run "
                                       f"alone in its plain form")
    if not lead:
        return refuse(ANSWER_NOT_LEAD, f"{ANSWER_NOT_LEAD}: only the lead records the owner's answer; this session is not a "
                                       f"lead; give the owner's words to the lead, who runs `mkway ask answered <id>`")
    return allow()
