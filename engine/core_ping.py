"""The pure decisions of the ping gate (card MW-076; decisions R185 to R188): a session that caused an inbox write to
another session this turn also pings it with SendMessage, and a lead is told of the pings that were skipped.

The trigger is the engine's own record of inbox writes (`<shared>/inbox-writes.jsonl`, one row for every row the engine
puts in an inbox: a `send`, a notice), not a list of commands. A write counts for this session when the row says it was
the writer (`from` is the session) or the engine wrote it (`from` is `engine`) while one of this session's Bash calls
was running (between the call and its result in the transcript). It needs a ping when it is addressed to another session,
was written after the start of the turn, and no SendMessage call of the transcript is as late as the write and says exactly
`mkway inbox <id>` for the write's id (card MW-110, ruling R279a: free text and a ping for another row do not count).

Each decision is a function of a Facts record the shell built and returns a `Verdict` (allow, refuse, warn or log with a
reason id and a text, plus the rows the shell writes). This module reads no disk, no process, no environment and no clock,
and imports no I/O module; a test fails if it does. No task name and no natural-language word list is in this file.
"""
from __future__ import annotations

import datetime
import re
from dataclasses import dataclass
from typing import Any, Optional

SEND_TOOL = "SendMessage"
SHELL_TOOLS = ("Bash", "PowerShell")
ENGINE = "engine"  # the `from` of a row the engine wrote with no sending session
REFUSED, SKIPPED, LISTED = "ping-not-sent", "ping-skipped", "ping-skipped-listed"
TRIP, WATCH = "trip", "watch"
# R188: the fixed clause, from the harness's own deferred-tools notice
CLAUSE = "if SendMessage is not loaded, load it first with ToolSearch query select:SendMessage"
PING_PREFIX = "mkway inbox "


@dataclass(frozen=True)
class Verdict:
    kind: str = "allow"  # allow | refuse | warn | log
    reason: Optional[str] = None
    text: str = ""
    records: tuple = ()  # (what, row dict): `ping-skipped`, `seen`


def _allow() -> Verdict:
    return Verdict()


def send_ping_text(name: str, line: str) -> str:
    """The line `mkway send` prints when the lead's name is known (R185, R188): the clause, then the SendMessage to the
    name with the ping line, which is the whole body of that SendMessage."""
    return f"ping: {CLAUSE}; then SendMessage to {name}: {line}"


# ---- time ------------------------------------------------------------------------------------------------------------

def _when(text) -> Optional[datetime.datetime]:
    """An ISO time as the transcript (`...Z`) and the engine (`...+00:00`) write it; a time with no zone is UTC."""
    if not isinstance(text, str) or not text.strip():
        return None
    try:
        when = datetime.datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=datetime.timezone.utc)


# ---- the transcript ---------------------------------------------------------------------------------------------------

def _blocks(entry, kind):
    message = entry.get("message") if isinstance(entry, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    return [b for b in content if isinstance(b, dict) and b.get("type") == kind] if isinstance(content, list) else []


def _bash_windows(entries) -> list:
    """[(start, end)] of each shell call of the turn: the time of the entry with the tool call and of the entry with its
    result; `end` None when the result is not in the turn. A call with no readable time is left out."""
    starts, ends = {}, {}
    for entry in entries:
        when = _when(entry.get("timestamp"))
        for block in _blocks(entry, "tool_use"):
            if block.get("name") in SHELL_TOOLS and when is not None:
                tool_input = block.get("input")
                command = tool_input.get("command") if isinstance(tool_input, dict) else None
                starts[block.get("id")] = (when, command if isinstance(command, str) else "")
        for block in _blocks(entry, "tool_result"):
            if when is not None:
                ends[block.get("tool_use_id")] = when
    return [(start, ends.get(cid), command) for cid, (start, command) in starts.items()]


def _pings(entries) -> list:
    """(time, text) of each SendMessage call of the turn; a call with no readable time counts as the last moment, a call
    with no text field has the text None."""
    out = []
    for entry in entries:
        for block in (b for b in _blocks(entry, "tool_use") if b.get("name") == SEND_TOOL):
            tool_input = block.get("input")
            text = tool_input.get("message") if isinstance(tool_input, dict) else None
            out.append((_when(entry.get("timestamp")) or datetime.datetime.max.replace(tzinfo=datetime.timezone.utc),
                        text if isinstance(text, str) else None))
    return out


def _is_ping_of(text, write) -> bool:
    """Ruling R279a: a SendMessage is the ping of an inbox write only when its text is exactly `mkway inbox <id>` for that
    write's id, with at most ONE final line break (round two of the readers: no strip, so a leading or trailing space, a
    case change and two final breaks do not count). Free text, a ping for another row and the line with words around it
    are not."""
    row_id = write.get("id")
    if not (isinstance(text, str) and isinstance(row_id, str) and row_id):
        return False
    body = text[:-2] if text.endswith("\r\n") else text[:-1] if text.endswith("\n") else text
    return body == f"{PING_PREFIX}{row_id}"


# ---- the builder's Stop -------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class PingFacts:
    """One Stop. `entries`: the entries of the turn (None: the transcript could not be read); `turn_start`: the time of the
    real user message that began the turn (None: not known); `writes`: the engine's record rows of the inbox writes since
    then, `{id, from, to, kind, ts, name}` (`name`: the SendMessage name of `to`, None when not known); `hook_active`:
    the Stop payload's `stop_hook_active`; `is_lead`: the session is a registered lead; `mode`: `gates.ping.mode`."""
    session_id: Any = None
    entries: Optional[tuple] = None
    writes: tuple = ()
    turn_start: Optional[str] = None
    hook_active: bool = False
    is_lead: bool = False
    mode: str = TRIP


def _names_the_call(command, write) -> bool:
    """The Bash command text holds the card id of the write and every word of its `cmd` (`card set`: both words)."""
    card, cmd = write.get("card"), write.get("cmd")
    return (isinstance(card, str) and bool(card) and isinstance(cmd, str) and bool(cmd.split())
            and card in command and all(word in command for word in cmd.split()))


def caused_by(write, when, session, windows) -> bool:
    """THE attribution rule, in one place (R189). An inbox write is this session's when the row names it as the writer
    (`from`), or the engine wrote it and its `by` names this session (the MW-049 caller mechanism; a `by` of another
    session is never this one's). With no `by`, the fallback needs all three together: a moment inside one of this
    session's Bash calls, the command text of that call, and the card id of the write; never the window alone."""
    if write.get("from") == session:
        return True
    if write.get("from") != ENGINE:
        return False
    if write.get("by"):
        return write["by"] == session
    return any(a <= when and (b is None or when <= b) and _names_the_call(command, write)
               for a, b, command in windows)


def pending_writes(f: PingFacts) -> tuple:
    """The writes of this turn, in time order, that this session caused and no SendMessage followed."""
    start = _when(f.turn_start)
    if start is None or f.entries is None:
        return ()
    windows, pings = _bash_windows(f.entries), _pings(f.entries)
    found = []
    for write in f.writes:
        when = _when(write.get("ts"))
        if when is None or when < start or write.get("to") == f.session_id:
            continue
        if caused_by(write, when, f.session_id, windows) and not any(p >= when and _is_ping_of(text, write)
                                                                       for p, text in pings):
            found.append((when, write))
    return tuple(w for _when_, w in sorted(found, key=lambda pair: pair[0]))


def _item(write) -> str:
    line = f"{PING_PREFIX}{write.get('id')}"
    name = write.get("name")
    if name:
        return f"SendMessage to {name}: {line}"
    return f"in ListAgents find the session that runs in that root folder and send it exactly: {line}"


def refusal_text(pending) -> str:
    """R185, R186, R188: `ping your lead:`, the fixed clause, then each ping to send, the target's name and the exact line."""
    return f"ping your lead: {CLAUSE}; then " + " | ".join(_item(w) for w in pending)


def decide_stop(f: PingFacts) -> Verdict:
    """The builder's own Stop. A session with no id, a lead, and a transcript that cannot be read are not judged. With an
    unanswered write: the first Stop is refused `ping-not-sent` (watch mode: a warn); the Stop of the continuation
    (`stop_hook_active`, the documented field; no counter of our own) passes with the log verdict `ping-skipped`. Each
    unanswered write is a record row `ping-skipped`."""
    if not isinstance(f.session_id, str) or not f.session_id.strip() or f.is_lead or f.entries is None:
        return _allow()
    pending = pending_writes(f)
    if not pending:
        return _allow()
    rows = tuple((SKIPPED, {"kind": w.get("kind"), "inbox_id": w.get("id"), "to": w.get("to"), "name": w.get("name")})
                 for w in pending)
    text = refusal_text(pending)
    if f.hook_active:
        return Verdict("log", SKIPPED, text, rows)
    if f.mode == WATCH:
        return Verdict("warn", REFUSED, text, rows)
    return Verdict("refuse", REFUSED, text)


# ---- the lead's Stop (R186 b, R187) --------------------------------------------------------------------------------------

@dataclass(frozen=True)
class LeadStopFacts:
    """A lead's Stop. `rows`: the skipped pings addressed to this lead, `{id, builder, inbox_id, origin}` (`origin`
    `session` for a ping a session skipped, `engine` for a notice the engine wrote that no session pinged); `seen`: the
    row ids this lead was already shown."""
    is_lead: bool = False
    rows: tuple = ()
    seen: frozenset = frozenset()


def _lead_line(row) -> str:
    if row.get("origin") == ENGINE:
        return f"the engine wrote a notice that no session pinged: read {PING_PREFIX}{row.get('inbox_id')}"
    return f"builder {row.get('builder')} wrote to the inbox and did not ping: read {PING_PREFIX}{row.get('inbox_id')}"


def decide_lead_stop(f: LeadStopFacts) -> Verdict:
    """A registered lead's Stop lists each skipped ping it has not been shown, once: one warn line, and a `seen` record."""
    fresh = [r for r in f.rows if r.get("id") not in f.seen]
    if not f.is_lead or not fresh:
        return _allow()
    return Verdict("warn", LISTED, " | ".join(_lead_line(r) for r in fresh), (("seen", {"ids": [r["id"] for r in fresh]}),))


# ---- the name in mkcl's sessions file (R178a, R185) -----------------------------------------------------------------------

def sessions_name(data, target, card) -> Optional[str]:
    """The SendMessage name of the session `target` from mkcl's `sessions.json` (`{"sessions": [{name, starter, kind, card,
    state, resumeId, ...}]}`; a reader ignores fields it does not know): the name of the live row whose `resumeId` is the
    target, else the `starter` of the live builder row of `card` (the lead that started the sender). None when neither."""
    rows = data.get("sessions") if isinstance(data, dict) else data
    rows = [r for r in rows if isinstance(r, dict) and r.get("state") != "closed"] if isinstance(rows, list) else []
    for row in rows:
        if isinstance(target, str) and target and row.get("resumeId") == target and _text(row.get("name")):
            return row["name"]
    for row in rows:
        if card and row.get("kind") == "builder" and row.get("card") == card and _text(row.get("starter")):
            return row["starter"]
    return None


def _text(value) -> bool:
    return isinstance(value, str) and bool(value.strip())
