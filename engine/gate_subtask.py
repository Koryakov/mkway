"""The subtask gate (card MW-003, deliverable 5; spec section 2 and its addendum; replaces reg 9).

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
A path outside the root is not this gate's: it allows it.
"""
from __future__ import annotations

import cardtool
import gate
import helpers
import leads
import profiles
import register

PATH_KEYS = ("file_path", "notebook_path", "path")
CLI = "python mkway/engine/mkway.py"


def _exempt(profile) -> list:
    paths = profile.get("paths") if isinstance(profile, dict) else None
    value = paths.get("exempt") if isinstance(paths, dict) else None
    return [x for x in value if isinstance(x, str) and x] if isinstance(value, list) else []


def check(event, ctx):
    profile = ctx.profile if isinstance(ctx.profile, dict) else {}
    tool_input = ctx.tool_input if isinstance(ctx.tool_input, dict) else {}
    rels = [ctx.norm(v) for k in PATH_KEYS if isinstance(v := tool_input.get(k), str) and v]
    for rel in rels:
        verdict = _one(ctx, profile, rel)
        if verdict.kind == "refuse":
            return verdict
    return gate.allow()


def _one(ctx, profile, rel):
    if rel is None or rel == ".":
        return gate.allow()
    card_files = f"{profiles.bundle_root(profile)}/cards/*/CARD.md"  # card files only (close check L4)
    if helpers.matches(rel, card_files) or any(helpers.matches(rel, e) for e in _exempt(profile)):
        return gate.allow()
    if leads.is_lead(profiles.shared_state_dir(ctx.root, profile), ctx.session_id) and \
            leads.writable(ctx.root, profile, ctx.session_id, rel):
        return gate.allow()  # MW-017: a lead holds no card; its order file and the asks folder are its own rule's
    card_id = ctx.records.card()
    if not card_id:
        return gate.refuse("no-open-card", f"{rel}: this session holds no card. Write one with `{CLI} card new "
                                           f"<title>` and take it with `{CLI} card take <id>`; the owner opens it")
    problem = register.seal_problem(ctx.root, profile)
    if problem:
        return gate.refuse("register-tampered", f"{problem}; nothing is edited until the owner checks it: "
                                                f"{register.OWNER_FIX}")
    row = register.find(register.read(ctx.root, profile), card_id)
    status = row.get("status") if row else "not in the register"
    if status != "open":
        how = (f"the owner's `{CLI} card open {card_id}`" if status != "waiting"
               else f"`{CLI} card set {card_id} open` (or the owner's `card open {card_id}`)")
        return gate.refuse("card-not-open", f"{rel}: {card_id} is {status} in the register; edits need it open: "
                                            f"{how}")
    recorded = cardtool.paths_set(row.get("paths", ""))
    try:
        now = cardtool.paths_set(cardtool.card_paths(ctx.root, profile, card_id))
    except (OSError, cardtool.CardError):
        now = None
    if now != recorded:
        return gate.refuse("card-paths-changed", f"{rel}: the Paths of {card_id} differ from the set the owner's "
                                                 f"`card open` recorded ({'; '.join(sorted(recorded)) or 'none'}); "
                                                 f"restore them, or ask the owner to run `{CLI} card open "
                                                 f"{card_id}` again")
    if recorded and not any(helpers.matches(rel, e) for e in recorded):
        return gate.refuse("file-not-in-card", f"{rel} is not in the Paths of {card_id} "
                                               f"({'; '.join(sorted(recorded))}); add it to the card and ask the "
                                               f"owner to `card open {card_id}` again, or write a new card")
    return gate.allow()
