"""The search gate (card MW-008): search the past decisions before asking.

PreToolUse, edit group. It gates `AskUserQuestion`, and a Write, Edit or MultiEdit of a path that matches a glob of
`questions.files`. The call is refused `search-missing` unless this session has a `search` record (written by the
`post` group after `mkway search`) newer than the last real user message of the transcript the hook input names. The
turn boundary is read by the Stop gate's reader (`gate_owner_ask.turn_split`).

It fails OPEN: when the turn boundary cannot be established (no session id, no readable transcript, a user message with
no time) the call is allowed and the verdict is a `log` row, `search-unverified`. A gate that blocked every question on
a reading failure of its own would be worse than a missed search. No task word is in this file.
"""
from __future__ import annotations

import datetime
from typing import Optional

import gate
import gate_owner_ask
import helpers
import profiles
import records

WRITE_TOOLS = ("Write", "Edit", "MultiEdit")
QUESTION_TOOL = "AskUserQuestion"
HOW = "run `mkway search <words>` first, then ask"


def _time(value) -> Optional[datetime.datetime]:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=datetime.timezone.utc)


def _gated(ctx) -> bool:
    if ctx.tool_name == QUESTION_TOOL:
        return True
    if ctx.tool_name not in WRITE_TOOLS or not isinstance(ctx.tool_input, dict):
        return False
    section = ctx.profile.get("questions") if isinstance(ctx.profile, dict) else None
    patterns = section.get("files") if isinstance(section, dict) else None
    path = ctx.tool_input.get("file_path")
    if not isinstance(patterns, list) or not isinstance(path, str) or not path:
        return False
    rel = ctx.norm(path)
    if rel is None:
        return False
    fold = helpers._fold
    for pattern in patterns:
        if isinstance(pattern, str) and pattern.strip():
            text = pattern.strip().replace("\\", "/")
            text = text[2:] if text.startswith("./") else text
            if helpers.glob_re(fold(text)).fullmatch(fold(rel)):
                return True
    return False


def _unverified(why: str):
    return gate.log("search-unverified", f"the turn boundary could not be established ({why}), so the search check was "
                                         f"skipped; the question is allowed")


def _decide(ctx):
    if not ctx.session_id:
        return _unverified("the hook input has no session id")
    hook_input = ctx.hook_input if isinstance(ctx.hook_input, dict) else {}
    _after, readable, user = gate_owner_ask.turn_split(hook_input.get("transcript_path"))
    if not readable:
        return _unverified("the transcript cannot be read")
    floor = None
    if user is not None:
        floor = _time(user.get("timestamp"))
        if floor is None:
            return _unverified("the last user message has no time")
    state = profiles.state_dir(ctx.root, ctx.profile)
    for row in records.rows(state):
        if row.get("kind") != "search" or row.get("session_id") != ctx.session_id:
            continue
        when = _time(row.get("time"))
        if when is not None and (floor is None or when > floor):
            return gate.allow()
    return gate.refuse("search-missing", f"this session has no search record after the last user message. {HOW}. A "
                                         f"question to the owner goes out only after a search of the past decisions "
                                         f"(README, «Decisions: search before asking»)")


def check(event, ctx):
    if event != "PreToolUse":
        return gate.allow()
    try:
        if not _gated(ctx):
            return gate.allow()
    except Exception:  # not provably a gated call: not this gate's call
        return gate.allow()
    try:
        return _decide(ctx)
    except Exception as exc:  # fail open, with a row
        return _unverified(exc.__class__.__name__)
