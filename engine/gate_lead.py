"""The lead gate (card MW-017): what a registered lead may not do, and what it is told. The decisions are the pure
`core_session.decide_lead_edit`, `decide_lead_shell` and `decide_lead_remind` (card MW-066); this shell reads the facts.

Three entries on this gate, all form class (MW-012: watch mode on a first install, `mkway gate on lead` blocks):
- `lead.edit` (edit tools) and `lead.shell` (shell): a registered lead writes only `<card folder>/ORDER.md` of a card it
  ordered, `<card folder>/CARD.md` of a card it ordered while that card is `proposed` (MW-028; open seals it), and the
  asks folder; any other write is `lead-no-edit`. In the shell, `card take` is `lead-no-take`. A path outside the
  root is `write-outside-root`, the one reason and text of every session (MW-103; MW-107, R274), except the folders of
  `paths.outside_writable` (the engine's list in `defaults.json` plus the profile's additions, and the old key
  `leads.outside_writable` as an alias): this shell expands `<home>` and `<temp>`, compares real paths, applies the deny (a
  `.claude` folder followed by `hooks`, and `<home>/.claude/settings*.json`, never match) and hands the core one
  `OutsideRecord` for each such path; the core reads no folder. `place` also reads another checkout of the same repository
  below the root as outside, and joins a relative edit path to the cwd (as the shell reader does for a shell path). A session
  that is no lead is judged by the gate `outside` (`gate_outside`, class integrity, R274e), which uses the helpers of this
  module; a lead's unreadable write stays refused here, and the lead gates pass the owner table's notes to the core.
- `lead.remind` (prompt): the overdue cards of every lead are noticed at any session's next prompt; a lead is reminded
  of its unacked notices (`lead-notices-unacked`).

The gate knows a lead by the session id of the hook input and the registry `<state>/leads.json`; it reads tool names,
paths and ids, never a message: a lead's words are never the owner's consent. A session that is no lead is not judged by this gate; its write outside its root is the gate `outside`'s.
"""
from __future__ import annotations

import os
import re
import tempfile
from collections import namedtuple

import core_session
import gate
import gate_lock
import helpers
import leads
import logs
import owners
import profiles
import session_shell

PATH_KEYS = core_session.PATH_KEYS
SHELL_TOOLS = gate_lock.SHELL_TOOLS
SHOWN = core_session.SHOWN


# ---- a path outside the repository (MW-103, R255b) ---------------------------------------------------------------------

def _fold(text: str) -> str:
    return text.casefold() if os.name == "nt" else text


def _home() -> str:
    return os.path.expanduser("~")


def _temp() -> str:
    return os.environ.get("TEMP") or os.environ.get("TMP") or tempfile.gettempdir()


def _expand(pattern: str) -> str:
    """One pattern with `<home>` and `<temp>` replaced and slashes for backslashes; read at each call, never cached."""
    for mark, base in (("<home>/", _home), ("<temp>/", _temp)):
        if pattern.startswith(mark):
            return base().replace("\\", "/").rstrip("/") + "/" + pattern[len(mark):]
    return pattern.replace("\\", "/")


def outside_patterns(profile) -> tuple:
    """The expanded list a lead may write outside the repository: the engine's own list, then the profile's additions."""
    return tuple(_expand(p) for p in profiles.outside_writable(profile))


def _regex(expanded: str) -> str:
    """The pattern as a regex over a canonical path: the folders before the first wildcard are made real the same way a
    path is, `*` is one folder name, `**` any depth below."""
    parts = expanded.split("/")
    first = next((i for i, part in enumerate(parts) if "*" in part), len(parts))
    out = [re.escape(helpers._canon("/".join(parts[:first]) or "/").rstrip("/"))]
    for part in parts[first:]:
        if part == "**":
            out.append(".+")
        elif part == "*":
            out.append("[^/]+")
        else:
            out.append(re.escape(_fold(part)).replace(r"\*", "[^/]*"))
    return "/".join(out)


def _denied(canon: str) -> bool:
    """A `.claude` folder followed by `hooks` anywhere, or `<home>/.claude/settings*.json`: matched by no pattern."""
    parts = canon.split("/")
    if any(a == ".claude" and b == "hooks" for a, b in zip(parts, parts[1:])):
        return True
    return re.fullmatch(re.escape(helpers._canon(_home())) + r"/\.claude/settings[^/]*\.json", canon) is not None


def outside_allowed(path: str, profile=None) -> bool:
    """True when the absolute `path` is in the list of folders a lead may write outside the repository and the deny does
    not catch it."""
    canon = helpers._canon(path)
    if _denied(canon):
        return False
    return any(re.fullmatch(_regex(pattern), canon) for pattern in outside_patterns(profile))


def _note_problem(event, ctx, profile, tool_input, problem: str) -> None:
    """MW-107 (R274 design note): the linked checkouts could not be read. The write is still judged by the root rule; one row
    of the calls log (the `write-target-unresolved` log row, with a `note`, the guard's own row) names the failure. A failed
    write never fails the call."""
    try:
        logs.write_refusal(profiles.state_dir(ctx.root, profile), logs.row(
            session=ctx.session_id, event=event, tool=ctx.tool_name, gate=ctx.gate, reason_id="write-target-unresolved",
            target=logs.target_of(tool_input), kind="log", note=problem))
    except OSError:
        pass


Placed = namedtuple("Placed", "raw rel checkout")  # a raw path, its repository form (None outside the root), in another checkout


def _cwd(ctx):
    """MW-107 (R274e 11): the folder a relative edit path is joined to, the hook input's cwd (None when it names none). The shell
    reader already joins a shell path to its own cwd, so a shell path is placed with no cwd here: one base for both tools."""
    return gate_lock.edit_cwd(ctx)  # one base for every gate of the edit group (round-2 reader item 1)


def place(event, ctx, profile, tool_input, raws, cwd=None) -> list:
    """MW-107 (R274 5.2, R274a 8.4): each raw path with its repository form, None outside the root, and whether it lies in another
    checkout of the same repository. Another checkout is outside whatever the folder nesting, so a path inside the root that lies
    in a linked checkout below it is None too (and the refusal says how a brief travels). A list of checkouts that cannot be
    read leaves the root rule alone and is logged."""
    rels = tuple(ctx.norm(v, cwd=cwd) for v in raws)
    if all(rel is None for rel in rels):
        return [Placed(raw, rel, False) for raw, rel in zip(raws, rels)]
    nested, problem = helpers.checkouts_below(ctx.root)
    if problem:
        _note_problem(event, ctx, profile, tool_input, problem)
    if not nested:
        return [Placed(raw, rel, False) for raw, rel in zip(raws, rels)]
    env = ctx.env if isinstance(ctx.env, dict) else {}
    home = env.get("USERPROFILE") or env.get("HOME") or None
    prefix = helpers.top_prefix(ctx.root)
    found = []
    for raw, rel in zip(raws, rels):
        full = helpers.absolute(raw, ctx.root, top_prefix=prefix, home=home, cwd=cwd) if rel is not None else None
        canon = helpers._canon(full) if full else ""
        inside = any(canon == place or canon.startswith(place + "/") for place in nested)
        found.append(Placed(raw, None, True) if inside else Placed(raw, rel, False))
    return found


def placed(event, ctx, profile, tool_input, raws, cwd=None) -> tuple:
    """The repository form of each raw path (`place` without the checkout flag), for the gates that only need to know what is outside."""
    return tuple(p.rel for p in place(event, ctx, profile, tool_input, raws, cwd))


def _outside_record(ctx, profile, placed_path: Placed, cwd=None) -> core_session.OutsideRecord:
    env = ctx.env if isinstance(ctx.env, dict) else {}
    home = env.get("USERPROFILE") or env.get("HOME") or None
    absolute = helpers.absolute(placed_path.raw, ctx.root, top_prefix=helpers.top_prefix(ctx.root), home=home, cwd=cwd) or ""
    return core_session.OutsideRecord(raw=placed_path.raw, abs=absolute, matched=bool(absolute) and outside_allowed(absolute, profile),
                                      checkout=placed_path.checkout)


def outside_records(ctx, profile, items, cwd=None) -> tuple:
    """One record for each placed path whose repository form is None, in order (the outside gate and the lead gates call it)."""
    return tuple(_outside_record(ctx, profile, item, cwd) for item in items if item.rel is None)


def _writable(ctx, profile, rels) -> frozenset:
    """The paths of `rels` (repository forms) this lead may write: the one place the register and the card status are read."""
    return frozenset(r for r in rels if r not in (None, ".") and leads.writable(ctx.root, profile, ctx.session_id, r))


def _notes(profile, rels, root="") -> dict:
    """MW-107 (R274e 5): the owner table's sentence for each repository path, so a lead's refusal says who owns the file."""
    return {rel: owners.describe(rel, profile, root=root) for rel in rels if rel not in (None, ".")}


def _facts(ctx, profile, **given) -> core_session.LeadFacts:
    state = profiles.shared_state_dir(ctx.root, profile)
    return core_session.LeadFacts(is_lead=leads.is_lead(state, ctx.session_id), root=helpers.real_root(ctx.root),
                                  ask_dir=profiles.owner_ask(profile)["dir"], **given)


def edit(event, ctx):
    profile = ctx.profile if isinstance(ctx.profile, dict) else {}
    if not leads.is_lead(profiles.shared_state_dir(ctx.root, profile), ctx.session_id):
        return gate.allow()
    tool_input = ctx.tool_input if isinstance(ctx.tool_input, dict) else {}
    raws = tuple(v for key in PATH_KEYS if isinstance(v := tool_input.get(key), str) and v)
    cwd = _cwd(ctx)
    items = place(event, ctx, profile, tool_input, raws, cwd)
    rels = tuple(item.rel for item in items)
    return session_shell.verdict(core_session.decide_lead_edit(
        _facts(ctx, profile, paths=rels, writable=_writable(ctx, profile, rels), notes=_notes(profile, rels, str(ctx.root)),
               outside=outside_records(ctx, profile, items, cwd), outside_list=outside_patterns(profile))))


def shell(event, ctx):
    """The lead's shell step. A session that is no lead is judged only by the outside gate (R274e): it passes here."""
    profile = ctx.profile if isinstance(ctx.profile, dict) else {}
    tool_input = ctx.tool_input if isinstance(ctx.tool_input, dict) else {}
    command = tool_input.get("command")
    command = command if isinstance(command, str) else ""
    if not leads.is_lead(profiles.shared_state_dir(ctx.root, profile), ctx.session_id):
        return gate.allow()
    takes = any(gate_lock._positional(args)[:2] == ["card", "take"] for args in ctx.mkway_calls(command))
    writes = ctx.shell_writes(command)
    items = place(event, ctx, profile, tool_input, tuple(writes.paths))
    pairs = tuple((item.raw, item.rel) for item in items)
    return session_shell.verdict(core_session.decide_lead_shell(
        _facts(ctx, profile, takes_card=takes, writes=pairs, writes_anywhere=bool(writes.reason),
               writable=_writable(ctx, profile, [rel for _path, rel in pairs]), notes=_notes(profile, [rel for _path, rel in pairs], str(ctx.root)),
               outside=outside_records(ctx, profile, items), outside_list=outside_patterns(profile))))


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
    rows = tuple({"id": r.get("id"), "body": r.get("body")} for r in leads.unacked(state, ctx.session_id))
    if rows and not ctx.once([str(r["id"]) for r in rows]):  # MW-112 (MW112-D1): the same set of notices is said once per session
        return gate.allow()
    return session_shell.verdict(core_session.decide_lead_remind(_facts(ctx, profile, unacked=rows)))
