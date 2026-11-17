"""The subtask gate (card MW-003, deliverable 5; spec section 2 and its addendum; replaces reg 9). The decision is the
pure `core_session.decide_subtask` (card MW-066); this shell reads the facts and maps the verdict.

An edit-tool write inside the root passes when, in this order:
- S3/S4: the path is a card file (`<bundle.root>/cards/*/CARD.md`) or matches `paths.exempt`: always allowed, even with no
  taken card, so a session can write its new card before the owner opens it;
- S1: this session holds a card by its latest `take` record (`no-open-card` otherwise);
- R19a: the register's seal holds (`register-tampered` otherwise; the status is read from the sealed register only,
  never from the card file's own Status line);
- S2: the card is `open` in the register (`card-not-open` otherwise, naming the status and the command that moves it);
- v3.1: the card file's `Paths` set equals the set the owner's `card open` recorded in the register (entries
  normalised; order, blanks and spaces ignored), else `card-paths-changed` until the owner opens the card again;
- the path is named by a recorded entry (a file, a folder, or a glob), else `file-not-in-card`. An empty `Paths`
  means no file rule.
A path outside the root (MW-107, R274: the root of the session, and another checkout of the same repository, whatever the folder
nesting) is no business of the card rules: the gate `outside` refuses it `write-outside-root` unless `paths.outside_writable`
names it (R274e), after the lock check and before this gate.
"""
from __future__ import annotations

from dataclasses import replace

import cardtool
import core_session
import gate
import gate_lead
import leads
import owners
import profiles
import register
import session_shell

PATH_KEYS = core_session.PATH_KEYS
CLI = core_session.CLI


def _exempt(profile) -> list:
    """The paths no card rule applies to: the `exempt` row of the owner table (the profile's `paths.exempt`)."""
    return list(owners.patterns_of("exempt", profile))


def _card_facts(ctx, profile) -> dict:
    """The facts only the card rules need: the held card, the register's seal, the card's row and its Paths now. Each
    is read only when the one before it left the rule open, as the gate always did."""
    card_id = ctx.records.card()
    if not card_id:
        return {}
    problem = register.seal_problem(ctx.root, profile)
    found = {"card_id": card_id, "register_problem": problem or None}
    if problem:
        return found
    row = register.find(register.read(ctx.root, profile), card_id)
    found.update(card_found=row is not None, card_status=row.get("status") if row else None)
    if row and row.get("status") == "open":
        found["recorded"] = cardtool.paths_set(row.get("paths", ""))
        try:
            found["now_paths"] = cardtool.paths_set(cardtool.card_paths(ctx.root, profile, card_id))
        except (OSError, cardtool.CardError):
            found["now_paths"] = None
    return found


def check(event, ctx):
    profile = ctx.profile if isinstance(ctx.profile, dict) else {}
    tool_input = ctx.tool_input if isinstance(ctx.tool_input, dict) else {}
    raws = tuple(v for k in PATH_KEYS if isinstance(v := tool_input.get(k), str) and v)
    rels = gate_lead.placed(event, ctx, profile, tool_input, raws, gate_lead._cwd(ctx))  # MW-107: another checkout is outside
    shared = profiles.shared_state_dir(ctx.root, profile)
    lead = leads.is_lead(shared, ctx.session_id)  # MW-017: a lead holds no card; its order file and the asks are its own rule's
    facts = core_session.SubtaskFacts(
        paths=rels, card_files=next(iter(owners.patterns_of("card-file", profile)), ""), exempt=tuple(_exempt(profile)),
        lead_may_write=frozenset(r for r in rels if lead and r not in (None, ".")
                                 and leads.writable(ctx.root, profile, ctx.session_id, r)),
        owner_fix=register.OWNER_FIX, report_route=gate.REPORT_ROUTE, cli=CLI)
    judged = core_session.pending(facts)
    if not judged:
        return gate.allow()
    facts = replace(facts, owner_notes={r: owners.describe(r, profile, root=str(ctx.root)) for r in judged}, **_card_facts(ctx, profile))
    return session_shell.verdict(core_session.decide_subtask(facts))
