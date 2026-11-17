"""The decision of `mkway verdict recut <card> <node> <reason>` (card MW-100; rulings R251, R251a, R251b): a pure core. No
input, no output, no git, no clock; the shell (`engine/verdict_recut.py`) reads the facts and writes the row, the record and
the ledger row.

A weak or wrong verdict is answered by a re-cut, never by an acceptance: the card's orderer (the lead) changes the row's words
(`CARD.md`) or the test, commits it, and runs this command; a fresh blind verdict is then run on the new cut. The recut resets
the node's run budget (`verdict add` counts per node per cut) and needs a true verdict dated after it at `card close`.

`decide(facts)` reads one `Facts` record: the caller (the session the lock gate's by-permit names), whether the owner's terminal
runs it, the card's register status, holder and orderer, every session that ever took the card, the profile's switches, and one
`Node`: whether the card names it, the sessions that committed its test file, the node's last verdict row (`last`) and the
reader run that row answers (`answered`, an agent id, with the time that run `ended`), whether a commit touched the node's test
file or the card file since that run ended (`changed`), the files that differ from HEAD (`stale`: file, HEAD blob, blob now),
and the recuts the node already had. It gives a `Verdict`: the refusals that block, the refusals that watch mode let through
(`watched`), and the agent id the recut answers (`answered`).

Refusal ids, in the order they are judged (a refusal text begins with its id). The ids of `verdict add` are reused:
  verdict-not-enforced   no `outbox.checkers`, or `cards.verdicts` is off: no reader can be proved (names the key)
  verdict-by-owner       the owner's terminal (refused in both modes)
  verdict-no-caller      a session whose id the gate left no permit for (refused in both modes)
  verdict-by-holder      the caller ever took the card (refused in both modes)
  verdict-card-state     the card is not waiting, nor open with no holder
  verdict-recut-not-lead the caller did not order the card; a card the owner ordered says that the owner gives it to a lead
                         with `mkway give`, and that lead runs the recut
  per node:
  verdict-node-unknown   the card's Acceptance rows do not name the node
  verdict-by-committer   the caller committed the node's test file (refused in both modes)
  verdict-recut-nothing  the node's last row is not weak or wrong, or no recorded reader run answers it (no row, true, recut)
  verdict-recut-exceeded one recut per node; a second one says to split or withdraw the card
  verdict-recut-stale    the test file or the card file is not HEAD's text (refused in both modes; names the file and both shas)
  verdict-recut-no-change no commit touched the test file or the card file since the answered run ended (refused in both modes:
                         a recut with no changed cut is a waiver in disguise)

Mode (`tests.verdict_add.mode`, ruling R251a point 7): `watch` lets a refusal through (it is listed in `Verdict.watched`) except
`verdict-by-holder`, `verdict-by-committer`, `verdict-by-owner`, `verdict-no-caller`, `verdict-recut-no-change` and
`verdict-recut-stale`. Any other value, and a missing key, is `trip`. `verdict-recut-pending` is a close refusal
(`core_verdicts`) and has no mode.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import core_verdict_add as add

TRIP, WATCH = add.TRIP, add.WATCH
NOT_LEAD = "verdict-recut-not-lead"
NOTHING = "verdict-recut-nothing"
EXCEEDED = "verdict-recut-exceeded"
STALE = "verdict-recut-stale"
NO_CHANGE = "verdict-recut-no-change"
NEW_REASONS = (NOTHING, NO_CHANGE, STALE, EXCEEDED, NOT_LEAD)
REASONS = (add.NOT_ENFORCED, add.BY_OWNER, add.NO_CALLER, add.BY_HOLDER, add.CARD_STATE, NOT_LEAD, add.NODE_UNKNOWN,
           add.BY_COMMITTER, NOTHING, EXCEEDED, STALE, NO_CHANGE)
ALWAYS = (add.BY_HOLDER, add.BY_COMMITTER, add.BY_OWNER, add.NO_CALLER, NO_CHANGE, STALE)  # refused in both modes
WEAK, WRONG = "weak", "wrong"
OWNER = "owner"
WAITING, OPEN = add.WAITING, add.OPEN
SHORT = add.SHORT
_same = add._same
_short = add._short


@dataclass(frozen=True)
class Node:
    name: str
    known: bool = True
    committers: frozenset = frozenset()
    last: str = ""  # the verdict word of the node's last row: true, weak, wrong or recut; empty: no row
    answered: str = ""  # the agent id of the reader run that row answers; empty: no recorded run
    ended: str = ""  # when that run ended (a time text for the messages); empty: not established
    stale: Tuple[Tuple[str, str, str], ...] = ()  # (file, blob at HEAD, blob now) of each file that is not HEAD's text
    changed: bool = False  # a commit touched the test file or the card file after the answered run ended
    recuts: int = 0  # the recuts the node already had


@dataclass(frozen=True)
class Facts:
    caller: str = ""
    owner: bool = False
    status: str = ""
    holder: str = ""
    orderer: str = ""  # the session that ordered the card; empty or `owner`: the owner did
    ever_held: frozenset = frozenset()
    node: Node = Node("")
    checkers_missing: bool = False
    verdicts_off: bool = False
    mode: str = ""


@dataclass(frozen=True)
class Refusal:
    node: str
    reason: str
    text: str


@dataclass(frozen=True)
class Verdict:
    refusals: Tuple[Refusal, ...] = ()
    watched: Tuple[Refusal, ...] = ()
    answered: str = ""

    @property
    def allowed(self) -> bool:
        return not self.refusals


def _lead(f: Facts):
    """The refusal when the caller is not the card's orderer, else None."""
    orderer = (f.orderer or "").strip()
    if not orderer or orderer.casefold() == OWNER:
        return Refusal("", NOT_LEAD, f"{NOT_LEAD}: the owner ordered this card, and only the card's orderer re-cuts a verdict; "
                                     f"the owner gives the card to a lead with `mkway give`; that lead runs the recut")
    if not _same(f.caller, orderer):
        return Refusal("", NOT_LEAD, f"{NOT_LEAD}: only the card's orderer ({orderer}) re-cuts a verdict; this session did not "
                                     f"order the card")
    return None


def _node(n: Node, caller: str):
    """The one refusal of the node, or None."""
    if not n.known:
        return Refusal(n.name, add.NODE_UNKNOWN, f"{n.name}: {add.NODE_UNKNOWN}: the card's Acceptance rows do not name this "
                                                 f"node, so no recut row is written for it")
    if any(_same(caller, s) for s in n.committers):
        return Refusal(n.name, add.BY_COMMITTER, f"{n.name}: {add.BY_COMMITTER}: the caller committed the test file (the "
                                                 f"commit gate's record); a session that did not commit the test re-cuts it")
    if n.last not in (WEAK, WRONG) or not n.answered:
        what = (f"its last row is {n.last}" if n.last else "it has no row") if n.last not in (WEAK, WRONG) else (
            f"its last row is {n.last}, but no recorded reader run answers it (a typed row)")
        return Refusal(n.name, NOTHING, f"{n.name}: {NOTHING}: {what}; a recut answers a weak or wrong verdict of a reader "
                                        f"run the engine recorded, and nothing else")
    if n.recuts >= 1:
        return Refusal(n.name, EXCEEDED, f"{n.name}: {EXCEEDED}: the node was re-cut once already and a second independent "
                                         f"reader still calls it {n.last}, so the row is ambiguous and a third attempt rarely "
                                         f"fixes that; split or withdraw the card")
    if n.stale:
        file, head, now = n.stale[0]
        return Refusal(n.name, STALE, f"{n.name}: {STALE}: {file} is not HEAD's text: HEAD holds {_short(head)}, the file now "
                                      f"is {_short(now)}; commit the change, then call again (the next reader reads HEAD)")
    if not n.changed:
        when = f"since the answered run {n.answered} ended ({n.ended})" if n.ended else (
            f"since the answered run {n.answered} ended (its end is not established)")
        return Refusal(n.name, NO_CHANGE, f"{n.name}: {NO_CHANGE}: no commit touched the test file or the card file {when}; a "
                                          f"recut without a changed cut is a waiver in disguise: change the row's words or "
                                          f"the test, commit it, then call again")
    return None


def _judge(f: Facts):
    """Every refusal in order."""
    if f.checkers_missing or f.verdicts_off:
        key = "`outbox.checkers` is missing in the profile, so no reader can be proved" if f.checkers_missing else (
            "`cards.verdicts` is off in the profile, so the close does not read verdicts")
        return [Refusal("", add.NOT_ENFORCED, f"{add.NOT_ENFORCED}: {key}; the owner sets that key")]
    if f.owner:
        return [Refusal("", add.BY_OWNER, f"{add.BY_OWNER}: a recut is never the owner's; the card's orderer runs this "
                                          f"command")]
    if not (f.caller or "").strip():
        return [Refusal("", add.NO_CALLER, f"{add.NO_CALLER}: no hook check of this call was found (none, used, or too old), "
                                           f"so the session id is not established; run the command alone, in its plain "
                                           f"form, in a session with the engine hooks")]
    found = []
    if any(_same(f.caller, s) for s in f.ever_held):
        found.append(Refusal("", add.BY_HOLDER, f"{add.BY_HOLDER}: the caller took this card once; a session that built the "
                                                f"card never re-cuts its verdicts, not even after it released the card"))
    if not (f.status == WAITING or (f.status == OPEN and not (f.holder or "").strip())):
        found.append(Refusal("", add.CARD_STATE, f"{add.CARD_STATE}: the card is {f.status or 'not established'}"
                                                 f"{' and held by ' + f.holder if f.holder else ''}; a recut is written "
                                                 f"while the card is waiting, or open with no holder"))
    lead = _lead(f)
    if lead is not None:
        found.append(lead)
    refusal = _node(f.node, f.caller)
    return found + ([refusal] if refusal else [])


def decide(facts: Facts) -> Verdict:
    found = _judge(facts)
    watch = facts.mode == WATCH
    blocking = tuple(r for r in found if not watch or r.reason in ALWAYS)
    watched = tuple(r for r in found if r not in blocking)
    return Verdict(blocking, watched, "") if blocking else Verdict((), watched, facts.node.answered)
