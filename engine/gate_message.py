"""The message gate (card MW-018): what a session may send with SendMessage, and what it is reminded of.

Three entries on this gate, all form class (MW-012: watch mode on a first install, `mkway gate on message` blocks):
- `message.send` (PreToolUse, matcher SendMessage, group `message`): the sender's side only. The body is exactly one ping
  line `mkway inbox <id>` and nothing else; row `<id>` exists in the shared inbox and its `from` is the hook's session id
  (`message-not-in-inbox`); no ping for `<id>` was recorded yet (`message-duplicate`), and then it is. The `to` field is
  never read: the ref of ListAgents is not the session id (card CHECK.md (b)), and who the row is for is what
  `mkway send` decided. A pure idle subscription (`notify_when_idle` with an empty message) carries no text and passes.
- `message.remind` (prompt): a session that is no lead is reminded of its unacked inbox items (`inbox-unacked`); a lead
  has its own reminder (MW-017).
- `message.stop` (Stop): an unacked order older than `messaging.ack_reminder_minutes` is a reminder line
  (`orders-unacked`), never a block.

The gate reads tool names, ids and hashes of rows, never a word of a message for its meaning.
"""
from __future__ import annotations

import gate
import leads
import messages
import profiles

SHOWN = 5
SEND_TOOL = "SendMessage"


def _not_in_inbox(why: str):
    return gate.refuse("message-not-in-inbox", f"SendMessage carries only the ping line of a message you wrote ({why}): "
                                               f"write the message with `mkway send --to <id-prefix> --kind <kind> "
                                               f"--file <body>`, then send exactly the line it prints, "
                                               f"`mkway inbox <id>`, and nothing else")


def check(event, ctx):
    if ctx.tool_name != SEND_TOOL:
        return gate.allow()
    tool_input = ctx.tool_input if isinstance(ctx.tool_input, dict) else {}
    message = tool_input.get("message")
    if tool_input.get("notify_when_idle") is True and (message is None or message == ""):
        return gate.allow()  # a pure subscription: no text is transmitted
    if not isinstance(message, str):
        return _not_in_inbox("the body is not text")
    found = messages.PING_LINE.fullmatch(message.strip())
    if not found:
        return _not_in_inbox("the body is not exactly one line `mkway inbox <id>`")
    row_id = found.group(1)
    session = ctx.session_id
    if not isinstance(session, str) or not session.strip():
        return _not_in_inbox("the hook input names no session id, so the sender cannot be established")
    profile = ctx.profile if isinstance(ctx.profile, dict) else {}
    shared = profiles.shared_state_dir(ctx.root, profile)
    if messages.row_from(shared, row_id, session) is None:
        return _not_in_inbox(f"no row {row_id} of yours is in the inbox")
    if messages.pinged(shared, row_id):
        return gate.refuse("message-duplicate", f"the ping for {row_id} was already sent: the recipient has it "
                                                f"(`mkway inbox {row_id}`). To say more, write another row with "
                                                f"`mkway send --to <id-prefix> --kind <kind> --file <body> --reply-to "
                                                f"<id>` and send its ping line")
    messages.record_ping(shared, row_id, session)
    return gate.allow()


def remind(event, ctx):
    """The prompt step: the unacked inbox items of a session that is no lead (a warn, never a block)."""
    profile = ctx.profile if isinstance(ctx.profile, dict) else {}
    shared = profiles.shared_state_dir(ctx.root, profile)
    if not isinstance(ctx.session_id, str) or not ctx.session_id or leads.is_lead(shared, ctx.session_id):
        return gate.allow()
    rows = leads.unacked(shared, ctx.session_id)
    if not rows:
        return gate.allow()
    text = " | ".join(messages.item_line(r) for r in rows[:SHOWN])
    more = f" | and {len(rows) - SHOWN} more: `mkway board`" if len(rows) > SHOWN else ""
    return gate.warn("inbox-unacked", f"you have {len(rows)} unacked inbox item{'s' if len(rows) != 1 else ''}: "
                                      f"{text}{more}")


def stop(event, ctx):
    """The Stop step: an unacked order older than `messaging.ack_reminder_minutes` is a reminder, never a block."""
    profile = ctx.profile if isinstance(ctx.profile, dict) else {}
    shared = profiles.shared_state_dir(ctx.root, profile)
    if not isinstance(ctx.session_id, str) or not ctx.session_id:
        return gate.allow()
    minutes = profiles.messaging_settings(profile)["ack_reminder_minutes"]
    rows = messages.old_orders(shared, ctx.session_id, minutes)
    if not rows:
        return gate.allow()
    text = " | ".join(f"{r.get('id')} from {r.get('from')}: {messages.first_line(r.get('body'))} "
                      f"(`mkway inbox {r.get('id')}`, then `mkway ack {r.get('id')}`)" for r in rows[:SHOWN])
    return gate.warn("orders-unacked", f"{len(rows)} order{'s' if len(rows) != 1 else ''} unacked for more than "
                                       f"{minutes:g} minutes: {text}")
