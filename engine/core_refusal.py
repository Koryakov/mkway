"""The pure decision of the refusal delivery (card MW-128; rulings R301 and R301a): a session whose turn ends on a refused
engine call and that sent nothing on has its refusal delivered to its orderer by the Stop hook itself, no model in the loop.

Terms (the order's words): an «engine call» is a tool call the gates judged, as the calls log records it; a «gate refusal row» is
the calls-log row with the verdict refuse and its own id (R301a's «refusal record id»); the «turn» is the calls of the session
since its previous Stop or UserPromptSubmit row; the «orderer» is the value of the register's orderer column for the card the
session holds; a «send» is a `mkway send` call of the session after the refusal row (the hook's own inbox write is not one).

`decide(facts)` reads one `Facts` record the shell (`engine/dispatch.py`, with the readers of `gatemode` and `messages`) built.
It delivers when (a) the last engine call of the turn has a gate refusal row and no engine call follows it, (b) no send followed
the refusal, (e) its row id is not yet delivered, and (c) an orderer is known; with no orderer it asks for one record row and no
block. It blocks only when `stop_hook_active` is false. `finish(decision, written)` turns the shell's write result into what is
recorded and whether to block: a write that failed allows the stop (a Stop hook cannot fail closed) and records nothing.

This module reads no disk, no process, no environment and no clock, and imports no I/O module; a test fails if it does.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Optional

ALLOW, DELIVER, NO_ORDERER = "allow", "deliver", "no-orderer"
DELIVERED = "refusal-delivered"  # the record row of a delivered refusal
NO_ORDERER_ID = "refusal-no-orderer"  # the one record row when no orderer is known
FAILED = "refusal-delivery-failed"  # the calls-log error row of a failed inbox write
PING_PREFIX = "mkway inbox "  # the exact ping line of the block is this prefix and the inbox row id


@dataclass(frozen=True)
class Call:
    """One engine call of the turn: `call` its id, `time` its last row's time, `refused` true when a gate refusal row is in it,
    `id` that row's id (None when the call was not refused)."""
    call: str
    time: str
    refused: bool = False
    id: Optional[str] = None


@dataclass(frozen=True)
class Facts:
    """`calls`: the engine calls of this session in the turn, oldest first; `sends`: the times of this session's `mkway send`
    records; `orderer`: the register's orderer for the card this session holds (None when none); `delivered`: the gate refusal
    row ids already delivered; `hook_active`: the hook input's `stop_hook_active`."""
    calls: tuple = ()
    sends: tuple = ()
    orderer: Optional[str] = None
    delivered: frozenset = frozenset()
    hook_active: bool = False


@dataclass(frozen=True)
class Decision:
    action: str = ALLOW  # allow | deliver | no-orderer
    refusal_id: Optional[str] = None
    orderer: Optional[str] = None
    block: bool = False


@dataclass(frozen=True)
class Outcome:
    block: bool  # the Stop is blocked (once)
    delivered: bool  # the gate refusal row id is recorded as delivered
    error: bool  # the write failed: an error row and a start-line notice


def _when(text) -> Optional[datetime.datetime]:
    """An ISO time as the engine writes it (`...+00:00`) or a transcript does (`...Z`); a time with no zone is UTC."""
    if not isinstance(text, str) or not text.strip():
        return None
    try:
        when = datetime.datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=datetime.timezone.utc)


def _sent_after(sends, refused_at) -> bool:
    """True when a send of the session is strictly later than the refusal (a send of the same millisecond is not after it, so
    it never hides a refusal); a send whose time cannot be read counts as late."""
    moment = _when(refused_at)
    for text in sends:
        when = _when(text)
        if when is None or moment is None or when > moment:
            return True
    return False


def decide(facts: Facts) -> Decision:
    """The order's condition list (a), (b), (e), then (c) and (d); anything else allows the stop silently."""
    last = facts.calls[-1] if facts.calls else None
    if last is None or not last.refused or not last.id:  # (a)
        return Decision()
    if _sent_after(facts.sends, last.time):  # (b)
        return Decision()
    if last.id in facts.delivered:  # (e)
        return Decision()
    if not facts.orderer:  # (c): one record row, never a block
        return Decision(NO_ORDERER, last.id, None, False)
    return Decision(DELIVER, last.id, facts.orderer, not facts.hook_active)  # (d)


def finish(decision: Decision, written: bool) -> Outcome:
    """What the shell does after it tried to write: the block (only a delivered record blocks, and only when `decide` said so),
    the delivered mark, and the error. The no-orderer decision writes a log row, which is its record."""
    if decision.action == ALLOW:
        return Outcome(False, False, False)
    if not written:
        return Outcome(False, False, True)
    return Outcome(decision.block, True, False)


def block_reason(inbox_id: str) -> str:
    """The binding reason text of the one block (R301a: it carries the exact ping line `mkway inbox <id>`)."""
    return f"your refusal was sent to your orderer as inbox row {inbox_id}; tell your orderer: {PING_PREFIX}{inbox_id}"


def inbox_body(session: str, command: str, line: str, refusal_id: str) -> str:
    """The body of the inbox refusal record: the session, the exact command, the exact refusal line, the gate refusal row id."""
    return ("refusal delivered by the engine: the session stopped after this refusal and sent nothing\n"
            f"session: {session}\n"
            f"command: {command}\n"
            f"refusal: {line}\n"
            f"gate refusal row: {refusal_id}")
