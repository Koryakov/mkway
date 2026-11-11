"""The `post` group's record step (card MW-003, deliverable 2).

PostToolUse on Bash and PowerShell. For each `mkway-ok <kind> <value> <nonce>` line in the tool's stdout whose
nonce was issued for that kind and value, it appends `{session_id, kind, value, time, by: session}` to the records.
It never refuses: the tool already ran, and a block after it undoes nothing (decision 5). When the record cannot be
written it warns `post-record-failed`; the next gate's refusal is the signal.
"""
from __future__ import annotations

import gate
import profiles
import records
import register


def _stdout(response) -> str:
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        for key in ("stdout", "output"):
            if isinstance(response.get(key), str):
                return response[key]
    return ""


def _ordered_by(ctx, card_id: str) -> None:
    """Card MW-011: a session's `card new` proved itself with its nonce, and only the hook input knows the session id,
    so the register's `Ordered by` cell of that card is written here, through the sealed writer. No id in the payload,
    or no such column: the card keeps reading `owner`."""
    session = ctx.session_id
    if isinstance(session, str) and session.strip() and register.file_has_orderer(ctx.root, ctx.profile) is True:
        register.set_ordered(ctx.root, ctx.profile, card_id, session, only_owner=True)


def record(event, ctx):
    try:
        state = profiles.state_dir(ctx.root, ctx.profile)
        for kind, value, nonce in records.OK_LINE.findall(_stdout(ctx.tool_response)):
            if records.consume(state, nonce, kind, value):
                records.append(state, ctx.session_id, kind, value, by="session")
                if kind == "new":
                    try:
                        _ordered_by(ctx, value)
                    except Exception as exc:  # the record stands; the card reads `owner`, the safe side
                        return gate.warn("post-record-failed", f"the card's Ordered by cell could not be written "
                                                               f"({exc.__class__.__name__}); {value} reads owner")
    except Exception as exc:  # decision 5: allow, with a warn row
        return gate.warn("post-record-failed", f"the session record could not be written ({exc.__class__.__name__});"
                                               " a gate that needs it will refuse next")
    return gate.allow()
