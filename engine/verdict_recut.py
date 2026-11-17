"""The shell of `mkway verdict recut <card> <node> <reason>` (card MW-100; rulings R251, R251a, R251b): a weak or wrong verdict
is answered by a re-cut, never by an acceptance. The card's orderer (the lead) changes the row's words (`CARD.md`) or the test,
commits it, and runs this command; a fresh blind verdict is then run on the new cut (`mkway verdict add`).

The command writes three things, and only when the pure `core_verdict_recut.decide` allows:
  - a typed row `recut` for the node in `tests/verdicts/<card>.md`, its reason cell `answers <agent id>: <reason>` (the agent id
    of the reader run the last row answers, never a run number: R251b A);
  - a record of kind `verdict-recut` in the proof file (`proof.FILE`): `doc`, `node`, `agent` (the answered agent id), `reason`,
    `session` (the lead), `row` (the row key, so a row changed by hand is no longer proved) and `time`. Run counters read only
    the kind `verdict-written`, so a recut is never a run and the lead is never a reader (R251b B);
  - one ledger row, topic `verdict recut`, by the lead's session, whose quote holds the card, the node, the answered run and the
    reason (an engine-written row, like `card open`: its quote is the command's data, not the owner's words).
The recut resets the node's run budget (`verdicts.cuts`: runs count since the node's last recut) and `verdict add` then needs a
reader run that started after the recut record (`verdict-run-before-recut`).

The facts (`read_facts`): the register's status, holder and orderer of the card; every session that ever took the card; the
card's Acceptance nodes; the profile's `outbox.checkers`, `cards.verdicts` and `tests.verdict_add.mode`; per node the committers of
its test file, its last verdict row, the add record that wrote it (its agent and its session), the END of that answered run
(`proof.reader_ends` in the session of that add record, not the lead's: R251b H), whether a commit touched the test file or the
card file after that end (git, committer time), and the two files against HEAD (blob at HEAD and now). The caller is the lock gate's
one-use by-permit (`verdict` is a by-permit head; the permit covers `add` and `recut`); the owner's terminal has none.

Refusal ids of the command (documented here and in the README; none is a manifest reason):
  verdict-not-enforced   no `outbox.checkers`, or `cards.verdicts` off: names the key
  verdict-by-owner       the owner's terminal (refused in both modes)
  verdict-no-caller      no by-permit: the session id is not established (refused in both modes)
  verdict-by-holder      the caller ever took the card (refused in both modes)
  verdict-card-state     the card is not waiting, nor open with no holder
  verdict-recut-not-lead the caller did not order the card (a card the owner ordered: the owner gives it to a lead with
                         `mkway give`; that lead runs the recut)
  verdict-node-unknown   the card's Acceptance rows do not name the node
  verdict-by-committer   the caller committed the node's test file (refused in both modes)
  verdict-recut-nothing  the node's last row is not weak or wrong, or no recorded reader run answers it
  verdict-recut-exceeded the node was re-cut once already: split or withdraw the card
  verdict-recut-stale    the test file or the card file is not HEAD's text (refused in both modes)
  verdict-recut-no-change no commit touched the test file or the card file since the answered run ended (refused in both modes)
`verdict-recut-pending` is a close refusal (`core_verdicts`): the card's last row for a node is a recut, or a true row is older
than the node's last recut record. `tests.verdict_add.mode` is `trip` or `watch` as for `verdict add` (a missing key is trip).
"""
from __future__ import annotations

from pathlib import Path

import cardtool
import core_verdict_recut as core
import ledger
import logs
import profiles
import proof
import records
import register
import verdict_add
import verdicts
from core_verdicts import Row

KIND = verdicts.RECUT_KIND
TOPIC = "verdict recut"


def _answer(state, card_id: str, node: str, checkers, last):
    """(agent id, the end of that run as a time text) of the reader run the node's last row answers; empty strings when no
    add record of the engine holds that row, or when the run's end row cannot be found (the session is the add record's)."""
    mine = verdicts._mine(last, verdicts._proof_rows(state, card_id)) if last is not None else []
    if not mine or not isinstance(mine[-1].get("agent"), str) or not mine[-1]["agent"]:
        return "", ""
    agent, session = mine[-1]["agent"], str(mine[-1].get("session") or "")
    ends = [ended for found, _began, ended in proof.reader_ends(state, session, tuple(checkers)) if found == agent]
    return agent, (ends[-1].isoformat(timespec="milliseconds") if ends else "")


def _changed(root, rels, ended: str) -> bool:
    """True when a commit touched one of the files `rels` after `ended` (committer time; the end is the bound, R251b H)."""
    bound = proof.moment(ended) if ended else None
    if bound is None:
        return False
    for rel in rels:
        for line in verdict_add._git(root, "log", "--format=%cI", "--", rel).splitlines():
            when = proof.moment(line.strip())
            if when is not None and when > bound:
                return True
    return False


def _stale(root, rels) -> tuple:
    """(file, blob at HEAD, blob now) of each file in `rels` that is not HEAD's text; no blob reads as empty."""
    out = []
    for rel in rels:
        head = verdict_add._git(root, "rev-parse", "--verify", "-q", f"HEAD:./{rel}")
        now = verdict_add._git(root, "hash-object", "--", rel) if (Path(root) / rel).is_file() else ""
        if head != now:
            out.append((rel, head, now))
    return tuple(out)


def read_facts(root, profile, state, card_id: str, node: str, caller: str, owner: bool = False) -> core.Facts:
    """The facts of one call (see the module docstring); `card-unknown` when the register or the card file lacks the card."""
    row = register.find(register.read(root, profile), card_id)
    if row is None:
        raise cardtool.CardError(f"{card_id} is not in the register", reason="card-unknown")
    card_path = cardtool.card_file(root, profile, card_id)
    try:
        named = set(cardtool.test_nodes(card_path.read_text(encoding="utf-8")))
    except OSError:
        raise cardtool.CardError(f"{card_id} has no card file", reason="card-unknown")
    checkers = profiles.outbox_settings(profile)["checkers"]
    rels = (node.partition("::")[0], card_path.relative_to(Path(root)).as_posix())
    last = next((r for r in reversed(verdicts.rows_of(root, card_id)) if r.node == node), None)
    agent, ended = _answer(state, card_id, node, checkers, last)
    found = core.Node(node, node in named, verdicts.committers_of(root, state, rels[0]), last.verdict if last else "", agent,
                      ended, _stale(root, rels), _changed(root, rels, ended), verdicts.cuts(state, card_id, [node])[node].recuts)
    return core.Facts(caller=caller or "", owner=owner, status=row.get("status", ""),
                      holder=records.holders(state, register.closed_ids(root, profile)).get(card_id, ""),
                      orderer=row.get(register.ORDERED) or register.OWNER, ever_held=verdict_add.took_by(state, card_id),
                      node=found, checkers_missing=not checkers, verdicts_off=not cardtool.verdicts_required(profile),
                      mode=profiles.verdict_add_mode(profile))


def record(state, card_id: str, node: str, caller: str, reason: str, row: Row, verdict: core.Verdict) -> dict:
    """Append the recut record to the proof file (kind `verdict-recut`), with the refusals watch mode let through."""
    entry = {"kind": KIND, "doc": verdicts.verdict_file(card_id), "node": node, "agent": verdict.answered, "reason": reason,
             "session": caller, "row": verdicts.row_key(row), "time": logs.now().isoformat(timespec="milliseconds")}
    if verdict.watched:
        entry["watched"] = [r.reason for r in verdict.watched]
    logs.append_jsonl(Path(state) / proof.FILE, entry)
    return entry


def apply(root, profile, state, card_id: str, node: str, reason: str, caller: str, owner: bool = False) -> core.Verdict:
    """One whole call: read the facts, decide, and when allowed write the row, the record and the ledger row."""
    facts = read_facts(root, profile, state, card_id, node, caller, owner)
    verdict = core.decide(facts)
    if verdict.allowed:
        said = verdict_add.clean(reason)
        row = Row(node, "recut", f"answers {verdict.answered or 'no run'}: {said}", f"session:{caller}")
        verdict_add.put_rows(root, card_id, [row])
        record(state, card_id, node, caller, said, row, verdict)
        ledger.add(root, profile, card=card_id, topic=TOPIC, by=f"session:{caller}", source=f"card {card_id} verdict recut",
                   quote=f"card {card_id}, node {node}, answered run {verdict.answered or 'none'}: {said}")
    return verdict


def report(card_id: str, node: str, verdict: core.Verdict) -> list:
    """The lines a successful call prints."""
    return [f"{card_id} {node} recut", f"answers {verdict.answered or 'no run'}: a fresh blind reader runs `mkway verdict add` "
            f"on the new cut", f"row written to {verdicts.verdict_file(card_id)}"]
