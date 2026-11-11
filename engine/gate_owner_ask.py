"""The owner-ask gate (card MW-007): questions to the owner go one way.

A session may ask the owner only after it has written down the sources it checked. The gate has two entries on one
function (manifest `owner_ask.edit` and `owner_ask.stop`, one profile switch `gates.owner_ask`):

- Edit gate (PreToolUse; Write, Edit, MultiEdit): a write to `<asks dir>/<name>_ask.md` needs `<name>_sources.md`
  beside it, with a line `kind: substance|session|lock`:
  - substance: for each source name of the profile, a count line `<source>: N contradictions` and at least one quote
    line `> <source>: <verbatim>`; the source named `ledger` (the default, MW-008) has its own lines: `ledger: N hits`
    and, with N above 0, a `> ledger: <verbatim>` line, or, with N 0, a line `search: <record id>`;
  - session: `checked: ListAgents`;
  - lock: `checked: <lock state>` (any text after the colon).
  Otherwise it refuses, and the text names the missing line. It fails closed for an ask path only: a failure while
  deciding whether the path is an ask path allows the write (a gate that blocked every edit on a bug would be worse).
- Stop gate (Stop): a final reply with a line that starts with one of the profile's markers (after spaces and an
  optional `**`) must have written an ask file since the last real user message of the transcript: a Write, Edit or
  MultiEdit of `<asks dir>/<name>_ask.md` that exists on disk now (a write the edit gate refused leaves no file, so it
  does not count). Otherwise it blocks `ask-not-written`. With `stop_hook_active` it never blocks, so one block
  cannot trap a session. The transcript is the file the hook input names (`transcript_path`); when it cannot be
  read, the gate cannot see a write, so a marker line is still blocked and the text says so.

The asks folder, the marker strings and the source names are profile keys with defaults (`profiles.owner_ask`); no
task name and no natural-language word is in this file. The line shapes (`kind:`, `checked:`, `>`) are the file format.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import asks
import gate
import helpers
import profiles

WRITE_TOOLS = ("Write", "Edit", "MultiEdit")
ASK_FILE = re.compile(r"^(?P<name>.+)_ask\.md$", re.I)
SOURCES_SUFFIX = "_sources.md"
KINDS = "substance|session|lock"
KIND_LINE = re.compile(r"^kind:[ \t]*(substance|session|lock)[ \t\r]*$", re.M | re.I)
SESSION_LINE = re.compile(r"^checked:[ \t]*ListAgents\b", re.M | re.I)
LOCK_LINE = re.compile(r"^checked:[ \t]*\S", re.M | re.I)
HOW = ("Before an ask to the owner, write down what was checked: a sources file beside the ask, with the lines of "
       "its kind (README, «Questions to the owner»)")


def _ask_target(ctx, settings, path):
    """(repo-relative path, name) when `path` is `<asks dir>/<name>_ask.md`, else None."""
    if not isinstance(path, str) or not path:
        return None
    rel = ctx.norm(path)
    if rel is None or rel == ".":
        return None
    folder, _, base = rel.rpartition("/")
    wanted = "" if settings["dir"] == "." else settings["dir"]
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


LEDGER_SOURCE = "ledger"  # MW-008: the source of the past decisions has its own lines, not the contradictions form
LEDGER_COUNT = re.compile(r"^ledger:[ \t]*(\d+)[ \t]+hits?\b", re.M | re.I)
LEDGER_QUOTE = re.compile(r"^>[ \t]*ledger:[ \t]*\S", re.M | re.I)
SEARCH_LINE = re.compile(r"^search:[ \t]*\S", re.M | re.I)


def _ledger_missing(text: str) -> list:
    """The lines a `ledger` source still needs: `ledger: N hits`; with N above 0 a `> ledger: <verbatim>` line; with N
    0 a line `search: <record id>` (the record of the `mkway search` that found nothing)."""
    count = LEDGER_COUNT.search(text)
    if count is None:
        return ["ledger: N hits"]
    if int(count.group(1)) > 0:
        return [] if LEDGER_QUOTE.search(text) else ["> ledger: <verbatim quote>"]
    return [] if SEARCH_LINE.search(text) else ["search: <record id>"]


def sources_problem(root, rel: str, name: str, settings):
    """None when the sources file beside the ask holds what its kind needs, else (reason id, message)."""
    folder = rel.rpartition("/")[0]
    shown = f"{name}{SOURCES_SUFFIX}"
    try:
        text = (Path(root) / folder / shown).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "ask-sources-missing", f"{shown} does not exist beside the ask (or cannot be read). {HOW}"
    found = KIND_LINE.search(text)
    if not found:
        return "ask-sources-kind", f"{shown} has no line `kind: {KINDS}`. {HOW}"
    kind = found.group(1).lower()
    missing = []
    if kind == "substance":
        if LEDGER_SOURCE in settings["sources"]:
            missing += _ledger_missing(text)
        pairs = [(s, *_lines(text, s)) for s in settings["sources"] if s != LEDGER_SOURCE]
        missing += [f"{s}: N contradictions" for s, count, _quote in pairs if not count]
        missing += [f"> {s}: <verbatim quote>" for s, _count, quote in pairs if not quote]
    elif kind == "session":
        missing += [] if SESSION_LINE.search(text) else ["checked: ListAgents"]
    elif not LOCK_LINE.search(text):
        missing.append("checked: <lock state>")
    if missing:
        return "ask-sources-lines", f"{shown} (kind {kind}) lacks " + ", ".join(f"`{m}`" for m in missing) + f". {HOW}"
    return None


QUESTION_TOOL = "AskUserQuestion"
FIELDS_HOW = ("An ask carries five field lines, and the session goes on with the work that does not wait for the "
              "answer (README, «Asks that do not stop the work»)")


def _resulting_text(ctx, rel: str) -> str:
    """The text of the ask file after this write: a Write's content; for an Edit or a MultiEdit the file on disk with
    its edits applied in order (an edit whose text is not found changes nothing, as the tool would refuse it)."""
    tool_input = ctx.tool_input
    if ctx.tool_name == "Write":
        content = tool_input.get("content")
        return content if isinstance(content, str) else ""
    try:
        text = (Path(ctx.root) / rel).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    edits = tool_input.get("edits") if ctx.tool_name == "MultiEdit" else [tool_input]
    for edit in edits if isinstance(edits, list) else []:
        old, new = (edit.get("old_string"), edit.get("new_string")) if isinstance(edit, dict) else (None, None)
        if not isinstance(old, str) or not isinstance(new, str):
            continue
        if old == "":
            text = new if text == "" else text
        elif old in text:
            text = text.replace(old, new) if edit.get("replace_all") else text.replace(old, new, 1)
    return text


def fields_problem(ctx, rel: str):
    """None when the ask file this write leaves holds its five lines, else (`ask-fields-missing`, text naming each)."""
    missing = asks.field_problems(_resulting_text(ctx, rel))
    if not missing:
        return None
    shown = ", ".join(f"`{asks.SHAPES[m]}`" for m in missing)
    return "ask-fields-missing", f"{Path(rel).name} lacks {shown}. {FIELDS_HOW}"


def open_problem(ctx, rel: str, name: str, settings):
    """None unless this write starts a NEW ask file while the session already has `owner_ask.max_open` asks with
    `status: open`: then (`ask-already-open`, text: add to the open ask, or wait). A write to an ask that is already on
    disk is an addition to it. A call with no session id is never refused here."""
    if not ctx.session_id or (Path(ctx.root) / rel).exists():
        return None
    mine = asks.open_of_session(ctx.root, ctx.profile, ctx.session_id)
    if len(mine) < settings["max_open"]:
        return None
    return "ask-already-open", (f"this session already has {len(mine)} open ask(s): {', '.join(mine)} "
                                f"(owner_ask.max_open {settings['max_open']}): add to the open ask, or wait for its "
                                f"answer; do not write a second ask. {FIELDS_HOW}")


def _question(ctx):
    """`AskUserQuestion`: refused `ask-tool-off` unless `owner_ask.tool_allowed`; the text names the file route."""
    settings = profiles.owner_ask(ctx.profile)
    if settings["tool_allowed"]:
        return gate.allow()
    return gate.refuse("ask-tool-off", (
        f"the pop-up question tool is off: it stops the work until the owner answers. Ask by writing "
        f"{settings['dir']}/<name>_ask.md with its sources file, with the lines `default: <text or none>`, "
        f"`deadline: <ISO local time or none>`, `blocked: <what waits, or none>`, `reversible: yes|no` and "
        f"`status: open`, then go on with the work that does not depend on the answer (README, «Asks that do not stop "
        f"the work»)"))


def _edit(ctx):
    if ctx.tool_name == QUESTION_TOOL:
        try:
            return _question(ctx)
        except Exception:  # the settings could not be read: the tool stays as it was (the search gate still judges it)
            return gate.allow()
    if ctx.tool_name not in WRITE_TOOLS or not isinstance(ctx.tool_input, dict):
        return gate.allow()
    try:
        settings = profiles.owner_ask(ctx.profile)
        target = _ask_target(ctx, settings, ctx.tool_input.get("file_path"))
    except Exception:  # not provably an ask path: not this gate's write
        return gate.allow()
    if target is None:
        return gate.allow()
    rel, name = target
    try:
        problem = (sources_problem(ctx.root, rel, name, settings) or fields_problem(ctx, rel)
                   or open_problem(ctx, rel, name, settings))
    except Exception as exc:  # fail closed, for an ask path only
        problem = ("ask-sources-missing", f"the sources check failed ({exc.__class__.__name__}). {HOW}")
    return gate.refuse(*problem) if problem else gate.allow()


def _post(ctx):
    """PostToolUse on a write of an ask file (MW-014): record which session wrote it, when it has no owner yet. It never
    refuses: the write already happened (a failed record is a warn, and the one-open rule then cannot see the ask)."""
    if ctx.tool_name not in WRITE_TOOLS or not isinstance(ctx.tool_input, dict):
        return gate.allow()
    try:
        settings = profiles.owner_ask(ctx.profile)
        target = _ask_target(ctx, settings, ctx.tool_input.get("file_path"))
        if target is None or not (Path(ctx.root) / target[0]).is_file():
            return gate.allow()
        asks.record_owner(ctx.root, ctx.profile, ctx.session_id, target[1])
    except Exception as exc:
        return gate.warn("ask-record-failed", f"the ask's owner record could not be written "
                                              f"({exc.__class__.__name__}); the one-open rule cannot see this ask")
    try:  # the owner's notification: never blocks, always a row
        done = asks.notify(ctx.root, ctx.profile, asks.read(Path(ctx.root) / target[0]))
    except Exception as exc:
        done = (False, f"the notify step failed ({exc.__class__.__name__})")
    if done is None:
        return gate.allow()
    return gate.log("notify-sent" if done[0] else "notify-failed", done[1])


def turn_split(path):
    """(entries after the last real user message, readable, that user message or None). A real user message is a
    `user` entry whose content is a string or has a text block; a tool result is not one. A line that is not JSON is
    skipped. The Stop gate and the search gate (MW-008) both read the turn boundary here."""
    entries = []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if isinstance(entry, dict):
                    entries.append(entry)
    except (OSError, TypeError):
        return [], False, None
    start = -1
    for i, entry in enumerate(entries):
        content = (entry.get("message") or {}).get("content") if isinstance(entry.get("message"), dict) else None
        if entry.get("type") == "user" and (isinstance(content, str) or (isinstance(content, list) and any(
                isinstance(b, dict) and b.get("type") == "text" for b in content))):
            start = i
    return entries[start + 1:], True, (entries[start] if start >= 0 else None)


def _turn(path):
    """(entries after the last real user message, readable)."""
    entries, readable, _user = turn_split(path)
    return entries, readable


def _blocks(entries, kind):
    for entry in entries:
        message = entry.get("message") if entry.get("type") == "assistant" else None
        content = message.get("content") if isinstance(message, dict) else None
        for block in content if isinstance(content, list) else []:
            if isinstance(block, dict) and block.get("type") == kind:
                yield block


def _wrote_ask(ctx, settings, turn) -> bool:
    for block in _blocks(turn, "tool_use"):
        if block.get("name") not in WRITE_TOOLS or not isinstance(block.get("input"), dict):
            continue
        target = _ask_target(ctx, settings, block["input"].get("file_path"))
        if target is not None and (Path(ctx.root) / target[0]).is_file():
            return True
    return False


def _stop(ctx):
    hook_input = ctx.hook_input if isinstance(ctx.hook_input, dict) else {}
    if hook_input.get("stop_hook_active"):
        return gate.allow()
    settings = profiles.owner_ask(ctx.profile)
    turn, readable = _turn(hook_input.get("transcript_path"))
    final = hook_input.get("last_assistant_message")
    if not isinstance(final, str):
        texts = [b["text"] for b in _blocks(turn, "text") if isinstance(b.get("text"), str)]
        final = texts[-1] if texts else ""
    markers = "|".join(re.escape(m) for m in settings["markers"])
    found = re.search(rf"^[ \t]*(?:\*\*)?({markers})", final, re.M)
    if found is None or _wrote_ask(ctx, settings, turn):
        return gate.allow()
    unread = "" if readable else " (the transcript could not be read, so no write could be seen)"
    return gate.refuse("ask-not-written", (
        f"the reply has a line that starts with `{found.group(1)}`, but this turn wrote no "
        f"{settings['dir']}/<name>_ask.md{unread}. An ask goes to the owner only after it is written to that file "
        f"with its sources file. {HOW}. If what was checked already decides it, do not ask: act, and report it "
        f"without the marker"))


def _remind(ctx):
    """UserPromptSubmit (MW-014): a session that owns an open ask past its deadline is told to take the default or keep
    waiting. A reminder only: a failure allows."""
    try:
        lines = asks.reminders(ctx.root, ctx.profile, ctx.session_id)
    except Exception:
        return gate.allow()
    return gate.warn("ask-past-deadline", chr(10).join(lines)) if lines else gate.allow()


def check(event, ctx):
    if event == "PreToolUse":
        return _edit(ctx)
    if event == "Stop":
        return _stop(ctx)
    if event == "PostToolUse":
        return _post(ctx)
    if event == "UserPromptSubmit":
        return _remind(ctx)
    return gate.allow()
