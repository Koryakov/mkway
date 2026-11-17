"""The search gate (card MW-008): search the past decisions before asking.

PreToolUse, edit group. It gates `AskUserQuestion`, and a Write, Edit or MultiEdit of a path that matches a glob of
`questions.files`. The call is refused `search-missing` unless this session has a `search` record (written by the
`post` group after `mkway search`) newer than the last real user message of the transcript the hook input names. The
turn boundary is read by the Stop gate's reader (`gate_owner_ask.read_entries`).

It fails OPEN: when the turn boundary cannot be established (no session id, no readable transcript, a user message with
no time) the call is allowed and the verdict is a `log` row, `search-unverified`. A gate that blocked every question on
a reading failure of its own would be worse than a missed search. No task word is in this file.

The decision is `engine/core_ask.py` (card MW-065); this module is the shell: it reads the call's path, the transcript
and the records, calls `core_ask.decide_search`, and turns the decision into a verdict.
"""
from __future__ import annotations

import dataclasses

import core_ask as core
import gate
import gate_owner_ask
import profiles
import records

WRITE_TOOLS = core.WRITE_TOOLS
QUESTION_TOOL = core.QUESTION_TOOL
HOW = core.SEARCH_HOW


def _call_facts(ctx) -> core.SearchFacts:
    """The facts of the call itself: the tool, the profile's `questions.files`, the path as the engine reads it."""
    tool_input = ctx.tool_input
    section = ctx.profile.get("questions") if isinstance(ctx.profile, dict) else None
    patterns = section.get("files") if isinstance(section, dict) else None
    path = tool_input.get("file_path") if isinstance(tool_input, dict) else None
    rel = ctx.norm(path) if (ctx.tool_name in WRITE_TOOLS and isinstance(patterns, list) and isinstance(path, str)
                             and path) else None
    return core.SearchFacts(tool_name=ctx.tool_name, tool_input=tool_input, patterns=patterns, rel=rel,
                            session_id=ctx.session_id)


def _turn_facts(ctx) -> dict:
    """The transcript as parsed (None when it cannot be read) and the records of the state folder (a failure to read
    them is named, not raised)."""
    hook_input = ctx.hook_input if isinstance(ctx.hook_input, dict) else {}
    entries = gate_owner_ask.read_entries(hook_input.get("transcript_path"))
    found = {"entries": None if entries is None else tuple(entries)}
    if ctx.session_id and entries is not None:
        try:
            found["rows"] = tuple(records.rows(profiles.state_dir(ctx.root, ctx.profile)))
        except Exception as exc:
            found["rows_error"] = exc.__class__.__name__
    return found


def check(event, ctx):
    if event != "PreToolUse":
        return gate.allow()
    try:
        facts = _call_facts(ctx)
        gated = core.search_gated(facts)
    except Exception:  # not provably a gated call: not this gate's call
        return gate.allow()
    if not gated:
        return gate.allow()
    try:
        facts = dataclasses.replace(facts, **_turn_facts(ctx))
    except Exception as exc:  # fail open, with a row
        return gate_owner_ask.as_verdict(core.unverified(exc.__class__.__name__))
    return gate_owner_ask.as_verdict(core.decide_search(facts))
