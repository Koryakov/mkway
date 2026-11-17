"""The message gate (card MW-018): what a session may send with SendMessage, and what it is reminded of. The decisions
are the pure `core_session.decide_send`, `decide_message_remind` and `decide_message_stop` (card MW-066); this shell
reads the facts and writes the ping row a verdict carries.

Three entries of the gate `message` are form class (MW-012: watch mode on a first install, `mkway gate on message` blocks);
the fourth, `message.session`, is its own gate `session_id` of the integrity class (MW-110, ruling R279: it never watches):
- `message.send` (PreToolUse, matcher SendMessage, group `message`): the sender's side only. Free text passes (MW-110:
  `message-not-in-inbox` is removed). A body that is exactly one ping line `mkway inbox <id>` of a row in the shared inbox
  whose `from` is the hook's session id is the sender's ping: no ping for `<id>` was recorded yet (`message-duplicate`),
  and then it is. The `to` field is never read: the ref of ListAgents is not the session id (card CHECK.md (b)), and who
  the row is for is what `mkway send` decided. A pure idle subscription (`notify_when_idle` with an empty message)
  carries no text and passes.
- `message.session` (PreToolUse, matcher Bash and PowerShell, group `shell`, gate `session_id`, integrity, MW-110): the
  session id of a shell call. `SESSION_ENV` is the engine's contract with the launcher, one module constant. The
  launcher's variable in the hook's environment is the hook's own session id (`session-id-mismatch`); a command that
  assigns the variable is refused the same way; an unset variable is a warn once (`session-id-unset`) until the owner
  sets `messaging.session_id_watch_until` and it has passed.
- `message.remind` (prompt): a session that is no lead is reminded of its unacked inbox items (`inbox-unacked`); a lead
  has its own reminder (MW-017).
- `message.stop` (Stop): an unacked order older than `messaging.ack_reminder_minutes` is a reminder line
  (`orders-unacked`), never a block.

The gate reads tool names, ids and hashes of rows, never a word of a message for its meaning.
"""
from __future__ import annotations

import core_session
import gate
import leads
import logs
import messages
import profiles
import session_shell

SHOWN = core_session.SHOWN
SEND_TOOL = core_session.SEND_TOOL


def _shared(ctx, profile):
    return profiles.shared_state_dir(ctx.root, profile)


def check(event, ctx):
    if ctx.tool_name != SEND_TOOL:
        return gate.allow()
    profile = ctx.profile if isinstance(ctx.profile, dict) else {}
    shared = _shared(ctx, profile)
    session = ctx.session_id
    row_id = core_session.ping_row_id(ctx.tool_input)
    known = row_id is not None and isinstance(session, str) and bool(session.strip())
    facts = core_session.MessageFacts(
        tool_name=ctx.tool_name, tool_input=ctx.tool_input, session_id=session, report_route=gate.REPORT_ROUTE,
        row_is_senders=known and (messages.row_from(shared, row_id, session) is not None
                                  or messages.engine_row(shared, row_id, session) is not None),  # MW-076, R187, R189
        row_no_by=known and messages.engine_no_by(shared, row_id),  # R197 B
        pinged=known and messages.pinged(shared, row_id))
    decided = core_session.decide_send(facts)
    for what, row in decided.records:
        if what == "ping":
            messages.record_ping(shared, row["id"], row["session"])
    return session_shell.verdict(decided)


def session(event, ctx):
    """Entry `message.session` (card MW-110): every shell call is checked against the launcher's variable. The environment
    of the hook process is the launcher's; the decision is the pure `core_session.decide_session_env`. The warn for an
    unset variable is said once per session."""
    profile = ctx.profile if isinstance(ctx.profile, dict) else {}
    tool_input = ctx.tool_input if isinstance(ctx.tool_input, dict) else {}
    command = tool_input.get("command")
    env = ctx.env if ctx.env is not None else {}
    name = core_session.SESSION_ENV
    decided = core_session.decide_session_env(core_session.SessionEnvFacts(
        session_id=ctx.session_id, env_name=name, env_id=env.get(name), command=command if isinstance(command, str) else None,
        day=logs.now().date().isoformat(), watch_until=profiles.session_id_watch_until(profile),
        watch_bad=profiles.session_id_watch_unreadable(profile), launcher=core_session.launcher_line(name)))
    if decided.kind == core_session.ALLOW_LINE and not ctx.once([decided.reason]):
        return gate.allow()
    return session_shell.verdict(decided)


def remind(event, ctx):
    """The prompt step: the unacked inbox items of a session that is no lead (a warn, never a block)."""
    profile = ctx.profile if isinstance(ctx.profile, dict) else {}
    shared = _shared(ctx, profile)
    session = ctx.session_id
    if not isinstance(session, str) or not session or leads.is_lead(shared, session):
        return gate.allow()
    unacked = leads.unacked(shared, session)
    if unacked and not ctx.once([str(r.get("id")) for r in unacked]):  # MW-112 (MW112-D1): one event, one line and one row
        return gate.allow()
    items = tuple(messages.item_line(r) for r in unacked)
    return session_shell.verdict(core_session.decide_message_remind(
        core_session.MessageFacts(session_id=session, unacked=items)))


def stop(event, ctx):
    """The Stop step: an unacked order older than `messaging.ack_reminder_minutes` is a reminder, never a block."""
    profile = ctx.profile if isinstance(ctx.profile, dict) else {}
    shared = _shared(ctx, profile)
    session = ctx.session_id
    if not isinstance(session, str) or not session:
        return gate.allow()
    minutes = profiles.messaging_settings(profile)["ack_reminder_minutes"]
    old = messages.old_orders(shared, session, minutes)
    if old and not ctx.once([str(r.get("id")) for r in old]):  # MW-112 (MW112-D1): never a Stop loop
        return gate.allow()
    orders = tuple({"id": r.get("id"), "from": r.get("from"), "first": messages.first_line(r.get("body"))} for r in old)
    return session_shell.verdict(core_session.decide_message_stop(
        core_session.MessageFacts(session_id=session, minutes=minutes, old_orders=orders)))
