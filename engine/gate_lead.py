"""The lead gate (card MW-017): what a registered lead may not do, and what it is told.

Three entries on this gate, all form class (MW-012: watch mode on a first install, `mkway gate on lead` blocks):
- `lead.edit` (edit tools) and `lead.shell` (shell): a registered lead writes only `<card folder>/ORDER.md` of a card it
  ordered, `<card folder>/CARD.md` of a card it ordered while that card is `proposed` (MW-028; open seals it), and the
  asks folder; any other write is `lead-no-edit`. In the shell, `card take` is `lead-no-take`.
- `lead.remind` (prompt): the overdue cards of every lead are noticed at any session's next prompt; a lead is reminded
  of its unacked notices (`lead-notices-unacked`).

The gate knows a lead by the session id of the hook input and the registry `<state>/leads.json`; it reads tool names,
paths and ids, never a message: a lead's words are never the owner's consent. A session that is no lead is not judged.
"""
from __future__ import annotations

import re

import gate
import gate_lock
import leads
import profiles

PATH_KEYS = ("file_path", "notebook_path", "path")
SHELL_TOOLS = gate_lock.SHELL_TOOLS
_VARIABLE = re.compile(r"[$`%(){}]")
_GLOB = re.compile(r"[*?\[]")
SHOWN = 5


def _allowed(profile) -> str:
    return (f"`<card folder>/ORDER.md` of a card it ordered, `<card folder>/CARD.md` of a card it ordered while the "
            f"card is proposed (after `mkway card open` the card commands or the owner change it), and the asks "
            f"folder `{profiles.owner_ask(profile)['dir']}`")


def _no_edit(profile, what: str):
    return gate.refuse("lead-no-edit", f"{what}: a lead orders work and does not do it; it writes only {_allowed(profile)}. "
                                       f"Write the order there and hand the work to a builder (`mkway card new "
                                       f"<title>`), or the owner ends the lead role with `mkway lead remove "
                                       f"<id-prefix>` in their own terminal")


def edit(event, ctx):
    profile = ctx.profile if isinstance(ctx.profile, dict) else {}
    state = profiles.shared_state_dir(ctx.root, profile)
    if not leads.is_lead(state, ctx.session_id):
        return gate.allow()
    tool_input = ctx.tool_input if isinstance(ctx.tool_input, dict) else {}
    for key in PATH_KEYS:
        value = tool_input.get(key)
        if not (isinstance(value, str) and value):
            continue
        rel = ctx.norm(value)
        if rel is None:  # outside the repository: not this gate's, as for the subtask gate
            continue
        if rel == "." or not leads.writable(ctx.root, profile, ctx.session_id, rel):
            return _no_edit(profile, rel)
    return gate.allow()


def shell(event, ctx):
    profile = ctx.profile if isinstance(ctx.profile, dict) else {}
    state = profiles.shared_state_dir(ctx.root, profile)
    if not leads.is_lead(state, ctx.session_id):
        return gate.allow()
    tool_input = ctx.tool_input if isinstance(ctx.tool_input, dict) else {}
    command = tool_input.get("command")
    command = command if isinstance(command, str) else ""
    for args in ctx.mkway_calls(command):
        pos = gate_lock._positional(args)
        if pos[:2] == ["card", "take"]:
            return gate.refuse("lead-no-take", f"a lead orders work and holds no card: `mkway card take` is the "
                                               f"builder's command. Hand the work to a builder session (write its "
                                               f"order, then `mkway card new <title>`), or the owner ends the lead role "
                                               f"with `mkway lead remove <id-prefix>` in their own terminal")
    writes = ctx.shell_writes(command)
    for path in writes.paths:
        if _VARIABLE.search(path) or _GLOB.search(path):
            return _no_edit(profile, f"{path} (a path the gate cannot read)")
        rel = ctx.norm(path)
        if rel is None:
            continue
        if rel == "." or not leads.writable(ctx.root, profile, ctx.session_id, rel):
            return _no_edit(profile, rel)
    if writes.reason:
        return _no_edit(profile, "this command may write anywhere (a computed path, a variable, or a program that can "
                                 "write anywhere)")
    return gate.allow()


def remind(event, ctx):
    """The prompt step. Every session's next prompt finds the cards past their Appetite (a notice to the lead that
    ordered each); a registered lead is reminded of its unacked notices."""
    profile = ctx.profile if isinstance(ctx.profile, dict) else {}
    state = profiles.shared_state_dir(ctx.root, profile)
    try:
        leads.sweep(ctx.root, profile)
    except Exception:
        pass  # a notice that cannot be written never blocks a prompt
    if not leads.is_lead(state, ctx.session_id):
        return gate.allow()
    rows = leads.unacked(state, ctx.session_id)
    if not rows:
        return gate.allow()
    text = " | ".join(f"{r.get('id')}: {r.get('body')} (`mkway ack {r.get('id')}`)" for r in rows[:SHOWN])
    more = f" | and {len(rows) - SHOWN} more: `mkway leads`" if len(rows) > SHOWN else ""
    return gate.warn("lead-notices-unacked", f"you have {len(rows)} unacked notice{'s' if len(rows) != 1 else ''}: "
                                             f"{text}{more}")
