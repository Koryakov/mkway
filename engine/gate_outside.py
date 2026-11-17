"""The outside gate (card MW-107; rulings R274, R274a 8.1, 8.2, 8.6 and R274e): a write outside the session's root, for every
session, by an edit tool or by the shell. The decision is the pure `core_session.decide_write_outside` (one reason
`write-outside-root` and one text for every session); this shell reads the facts the way the lead gates do (their `place` and
`outside_records` helpers are used, nothing is copied).

Two entries, both class integrity: a protected target is a hard kind (K1), so the check is hard from install, on purpose, with
no watch date (R274a 8.6; the old home of the shell side, the form gate `lead`, started in watch mode on a first install). A
gate's class is the class of all its entries (R279b), so the check is a gate of its own:
- `outside.edit` (edit tools): each path the tool names, read from the cwd of the call when it is relative (R274e 11);
- `outside.shell` (shell): the write targets the reader can place; each other simple command of a compound is judged, and only
  the target of a delete program is left to the delete gate (R274e 3). A target the reader cannot place passes for a session
  that is no lead, with the calls-log row `write-target-unread` (R274a 8.2, R274e 4: a program that may write anywhere gets the
  row too); a registered lead's unreadable write is refused by the lead gate.

Order (R274e): the entries stand after the lock check of their group, so the lock answers first at a lock target; when it
allows (the path is no target), this check runs. A registered lead is answered by its own gate first, as it always was.
"""
from __future__ import annotations

import core_session
import gate
import gate_lead
import gate_lock
import helpers
import leads
import logs
import profiles
import session_shell

PATH_KEYS = core_session.PATH_KEYS


def _note_unread(event, ctx, profile, tool_input) -> None:
    """MW-107 (R274a 8.2): a write target the reader could not read passed for a session that is no lead. One row of the calls
    log (`write-target-unread`, kind log, verdict allow) so the scorecard counts the passes as well as the refusals."""
    try:
        logs.write_refusal(profiles.state_dir(ctx.root, profile), logs.row(
            session=ctx.session_id, event=event, tool=ctx.tool_name, gate=ctx.gate, reason_id="write-target-unread",
            target=logs.target_of(tool_input), kind="log", verdict="allow"))
    except OSError:
        pass  # a row that cannot be written never fails the call


def _refusal(ctx, profile, items, cwd=None):
    """The outside refusal for these placed paths, or None when none lies outside or every outside one is on the list."""
    if all(item.rel is not None for item in items):
        return None
    return core_session.decide_write_outside(
        tuple(item.rel for item in items), gate_lead.outside_records(ctx, profile, items, cwd),
        gate_lead.outside_patterns(profile), helpers.real_root(ctx.root))


def edit(event, ctx):
    profile = ctx.profile if isinstance(ctx.profile, dict) else {}
    tool_input = ctx.tool_input if isinstance(ctx.tool_input, dict) else {}
    raws = tuple(v for key in PATH_KEYS if isinstance(v := tool_input.get(key), str) and v)
    cwd = gate_lead._cwd(ctx)
    refusal = _refusal(ctx, profile, gate_lead.place(event, ctx, profile, tool_input, raws, cwd), cwd)
    return session_shell.verdict(refusal) if refusal is not None else gate.allow()


def _writes(ctx, command):
    """What the command may write, each target read from the folder it runs in; the target of a delete program is left out."""
    env = ctx.env if isinstance(ctx.env, dict) else {}
    home = env.get("USERPROFILE") or env.get("HOME") or None
    shell = "powershell" if ctx.tool_name == "PowerShell" else "bash"
    return helpers.shell_writes(command, shell, cwd=gate_lock._start(ctx), root=ctx.root, home=home, skip_deletes=True)


def shell(event, ctx):
    profile = ctx.profile if isinstance(ctx.profile, dict) else {}
    tool_input = ctx.tool_input if isinstance(ctx.tool_input, dict) else {}
    command = tool_input.get("command")
    command = command if isinstance(command, str) else ""
    writes = _writes(ctx, command)
    paths = list(writes.paths)
    readable = [path for path in paths if core_session.readable_path(path)]
    refusal = _refusal(ctx, profile, gate_lead.place(event, ctx, profile, tool_input, readable))
    if refusal is not None:
        return session_shell.verdict(refusal)
    unread = len(readable) != len(paths) or bool(writes.reason)
    if unread and not leads.is_lead(profiles.shared_state_dir(ctx.root, profile), ctx.session_id):
        _note_unread(event, ctx, profile, tool_input)
    return gate.allow()
