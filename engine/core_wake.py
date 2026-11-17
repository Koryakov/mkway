"""The pure core of the inbox waiter (card MW-078): what the waiter does at each look is decided here, from facts the
waiter process read; this module reads nothing: no file, no process, no environment, no clock.

A session that stops is idle until something wakes it. The waiter is a Stop handler (`asyncRewake`) that watches one
session's inbox and wakes the session when a new row is addressed to it. `decide` answers one look: `wake(row id)`,
`heartbeat` (the deadline is reached with nothing new), `wait` (look again after a poll) or `quiet-exit` (this session
is none of the sessions that wait: the owner's tab, a `-p` run, a chief). No task name and no natural-language word is
in this file.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

WAKE, HEARTBEAT, WAIT, QUIET = "wake", "heartbeat", "wait", "quiet-exit"
KINDS = (WAKE, HEARTBEAT, WAIT, QUIET)
HEARTBEAT_LINE = "no new rows, end the turn"  # ruling R191: the session wakes, does nothing and stops; the Stop re-arms
MODE_ON = "on"


@dataclass(frozen=True)
class Row:
    """One inbox row as the waiter reads it: its id, who wrote it, whom it is addressed to and whether it is acked."""
    id: str
    writer: Optional[str]
    to: Optional[str]
    acked: bool


@dataclass(frozen=True)
class Facts:
    """What one look reads. `rows` are in file order, the oldest first; `woken` are the row ids that already woke this
    session; `now` and `deadline` are on one clock."""
    session: str = ""
    mode: str = MODE_ON
    safe_id: bool = True
    is_lead: bool = False
    holds_card: bool = False
    last_holder_unclosed: bool = False
    rows: tuple = ()
    woken: tuple = ()
    now: float = 0.0
    deadline: float = 0.0


@dataclass(frozen=True)
class Verdict:
    kind: str
    row_id: Optional[str] = None

    def __post_init__(self):
        if self.kind not in KINDS:
            raise ValueError(f"unknown verdict kind: {self.kind!r}")


def armed(f: Facts) -> bool:
    """A waiter arms only when the mode is on and the id is a plain id, for a lead, the holder of a card, or the last
    holder of a card that is released and not yet closed (that session waits for the lead's close or fix message)."""
    return f.mode == MODE_ON and f.safe_id and (f.is_lead or f.holds_card or f.last_holder_unclosed)


def decide(f: Facts) -> Verdict:
    """One look: a session that does not arm quits quietly; else the oldest unacked row addressed to this session, written
    by another session and not yet woken for, wakes it; else the deadline gives the heartbeat; else wait."""
    if not armed(f):
        return Verdict(QUIET)
    for row in f.rows:
        if row.acked or row.writer == f.session or row.to != f.session:
            continue
        if isinstance(row.id, str) and row.id and row.id not in f.woken:
            return Verdict(WAKE, row.id)
    if f.now >= f.deadline:
        return Verdict(HEARTBEAT)
    return Verdict(WAIT)


def last_holder(rows, card: str, closed: bool) -> Optional[str]:
    """The session that held `card` last, when the card is released and not closed; else None. `rows` are the session
    records (`kind`, `value`, `session_id`, `by`) in order; only the rows of this card count. A take of a held card is
    ignored; a release frees the card only from the holder, or from the owner, the orderer or the engine itself
    (`by` is one of `owner`, `orderer`, `stale`)."""
    if closed:
        return None
    holder, last = None, None
    for row in rows:
        if row.get("value") != card:
            continue
        kind, who = row.get("kind"), row.get("session_id")
        if kind == "take" and who and holder is None:
            holder = who
        elif kind == "release" and holder is not None and (row.get("by") in ("owner", "orderer", "stale")
                                                           or who == holder):
            last, holder = holder, None
    return last if holder is None else None
