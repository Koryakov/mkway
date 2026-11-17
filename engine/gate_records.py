"""The `post` group's record step (card MW-003, deliverable 2). What a line means is the pure `core_session.ok_lines`,
`granted` and `record_failed` (card MW-066); this shell asks the nonce store, writes the rows and maps the verdict.

PostToolUse on Bash and PowerShell. For each `mkway-ok <kind> <value> <nonce>` line in the tool's stdout whose
nonce was issued for that kind and value, it appends `{session_id, kind, value, time, by: session}` to the records.
A block after the tool undoes nothing, but the session must not go on believing it recorded: when the record cannot be
written the step refuses `post-record-failed`, naming the path (R271c-D1); the next gate's refusal is the second signal.
"""
from __future__ import annotations

from pathlib import Path

import core_session
import gate
import profiles
import records
import register
import session_shell


def _ordered_by(ctx, card_id: str) -> None:
    """Card MW-011: a session's `card new` proved itself with its nonce, and only the hook input knows the session id,
    so the register's `Ordered by` cell of that card is written here, through the sealed writer. No id in the payload,
    or no such column: the card keeps reading `owner`."""
    if register.file_has_orderer(ctx.root, ctx.profile) is True:
        register.set_ordered(ctx.root, ctx.profile, card_id, ctx.session_id, only_owner=True)


def record(event, ctx):
    path = "the state folder's records.jsonl"
    try:
        state = profiles.state_dir(ctx.root, ctx.profile)
        path = str(Path(state) / records.RECORDS)
        for kind, value, nonce in core_session.ok_lines(ctx.tool_response):
            if records.consume(state, nonce, kind, value):
                for what, row in core_session.granted(kind, value, ctx.session_id):
                    if what == "record":
                        records.append(state, ctx.session_id, row["kind"], row["value"], by="session")
                        continue
                    try:
                        _ordered_by(ctx, row["card"])
                    except Exception as exc:  # the record stands; the card reads `owner`, the safe side; the refusal names the register
                        return session_shell.verdict(core_session.ordered_failed(
                            exc.__class__.__name__, row["card"], str(register.path(ctx.root, ctx.profile))))
    except Exception as exc:  # R271c-D1: a refusal that names the path
        return session_shell.verdict(core_session.record_failed(exc.__class__.__name__, path))
    return gate.allow()
