"""The pure decision of the handoff notice (card MW-132; rulings R337, R337a, R338, R338a): a builder that holds an open card and
ends a turn with no `mkway send` to its orderer has its last message delivered to the orderer by the Stop hook itself, with one
block that asks only for the ping line. No model in the loop. It widens MW-128's Stop step (`core_refusal`) in its own shape.

Terms (the order's words): the «turn» starts at the session's boundary row (the latest UserPromptSubmit row, or the latest Stop
row that was not a continuation: `gatemode.handoff_turn`); a «handoff» is a `mkway send` by the session to its ORDERER strictly
later than that boundary (form 2 of R338 2: the plain reader of «no write or commit row after the send» is not available, so any
send to the orderer in the turn counts: the card Log names the hole); a send to any other session is not a handoff; «delivered
for this turn» is a mark of this session later than the boundary (the notice, a no-orderer row, a MW-128 record, an error row).

`decide(facts)` reads one `Facts` record the shell (`engine/dispatch.py`, with the readers of `gatemode` and `messages`) built.
It writes the notice when the session holds a card, is no lead, its turn is known, nothing is delivered for it, and no send to
the orderer is in it; with no orderer session (the owner, an empty cell, or the session itself) it asks for one record row and
no block. It blocks only for a `builder` (its orderer a registered lead: the printed ping line works for that role) and only when
`stop_hook_active` is false (R338a: the notice is the core, the block the extra). `finish(decision, written)` turns the shell's
write result into what is recorded: a write that failed allows the stop (a Stop hook cannot fail closed) and records nothing.

This module reads no disk, no process, no environment and no clock, and imports no I/O module; a test fails if it does.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Optional

ALLOW, NOTICE, NO_ORDERER = "allow", "notice", "no-orderer"
NOTICE_ID = "handoff-notice"  # the record row of a written notice
NO_ORDERER_ID = "handoff-no-orderer"  # the one record row when the orderer is no session an inbox row can go to
NO_TURN_START_ID = "handoff-no-turn-start"  # the one record row when the engine saw no turn begin (R340a): nothing is judged
FAILED_ID = "handoff-notice-failed"  # the calls-log error row of a failed write
PING_PREFIX = "mkway inbox "  # the exact ping line of the block is this prefix and the inbox row id
BUILDER, LEAD = "builder", "lead"  # the roles `messages.role_of` names
LAST_MESSAGE_LIMIT = 2000  # the last message is cut to this many characters in the notice body
CUT_MARK = " [cut]"
NE = "not established"


@dataclass(frozen=True)
class Facts:
    """`session`: this session; `card`: the card it holds (None when none); `orderer`: the session that ordered the card (None
    for the owner or an empty cell); `role`: `builder` (its orderer a registered lead), `lead`, or `none`; `turn_start`: the
    boundary row's time (None when the engine records none); `sends`: this session's `mkway send` records as (time, recipient);
    `delivered`: a mark of this turn exists; `hook_active`: the hook input's `stop_hook_active`; `background_tasks`: the count
    of the hook input's background tasks (kept in the record row only, never a reason to let the stop pass)."""
    session: str = ""
    card: Optional[str] = None
    orderer: Optional[str] = None
    role: str = "none"
    turn_start: Optional[str] = None
    sends: tuple = ()
    delivered: bool = False
    hook_active: bool = False
    background_tasks: Optional[int] = None


@dataclass(frozen=True)
class Decision:
    action: str = ALLOW  # allow | notice | no-orderer
    card: Optional[str] = None
    orderer: Optional[str] = None
    block: bool = False


@dataclass(frozen=True)
class Outcome:
    block: bool  # the Stop is blocked (once)
    delivered: bool  # the turn's delivery is recorded
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


def _handed_off(sends, orderer, turn_start) -> bool:
    """True when a send to the orderer is strictly later than the boundary (the same millisecond is the previous turn's). A send
    whose time cannot be read does not count (reader 2: it cannot show it is in this turn, and must not excuse a silent turn end)."""
    boundary = _when(turn_start)
    if boundary is None:
        return False
    for when_text, to in sends:
        when = _when(when_text)
        if to == orderer and when is not None and when > boundary:
            return True
    return False


def decide(facts: Facts) -> Decision:
    """The order's list: who is judged, whether the turn is known, whether it is delivered, who the orderer is, the handoff."""
    if not facts.card or facts.role == LEAD or facts.turn_start is None or facts.delivered:
        return Decision()
    if not facts.orderer or facts.orderer == facts.session:
        return Decision(NO_ORDERER, facts.card, None, False)
    if _handed_off(facts.sends, facts.orderer, facts.turn_start):
        return Decision()
    return Decision(NOTICE, facts.card, facts.orderer, facts.role == BUILDER and not facts.hook_active)


def finish(decision: Decision, written: bool) -> Outcome:
    """What the shell does after it tried to write: the block (only a written notice blocks, and only when `decide` said so), the
    delivered mark, and the error. The no-orderer decision writes a log row, which is its record."""
    if decision.action == ALLOW:
        return Outcome(False, False, False)
    if not written:
        return Outcome(False, False, True)
    return Outcome(decision.block, True, False)


def cut_message(value) -> str:
    """The last message as the notice body carries it: «not established» when it is no string or is blank, else cut to
    `LAST_MESSAGE_LIMIT` characters with the cut marked."""
    if not isinstance(value, str) or not value.strip():
        return NE
    text = value.strip()
    return text if len(text) <= LAST_MESSAGE_LIMIT else text[:LAST_MESSAGE_LIMIT] + CUT_MARK


def notice_body(session: str, card: str, last_message) -> str:
    """The body of the handoff notice: the fixed first words (R337 3(e)), then the last message."""
    return f"{session} ended its turn holding {card} without a message to you\nlast message: {cut_message(last_message)}"


def block_reason(card: str, inbox_id: str) -> str:
    """The binding reason text of the one block (R338 1): it carries the exact ping line `mkway inbox <id>`."""
    return (f"you ended your turn holding {card} without a message to your orderer; your last message was sent to your "
            f"orderer as inbox row {inbox_id}; tell your orderer: {PING_PREFIX}{inbox_id}")
