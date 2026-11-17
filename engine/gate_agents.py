"""The `post` group's agent records (card MW-004, part 1).

`SubagentStart` appends a start row, `SubagentStop` an end row with the result in full, to `<state.dir>/agents.jsonl`
(see `agents.py`). When a row cannot be written (R271c): `SubagentStart` refuses `agent-record-failed`, naming the path;
`SubagentStop` never refuses (a block there would keep a finished agent going): it warns, and the dispatcher shows the
line (the text is `core_session.agent_record_failed`).
"""
from __future__ import annotations

from pathlib import Path

import agents
import core_session
import gate
import profiles
import session_shell


def _run(event, ctx, write):
    path = "the state folder's " + agents.AGENTS
    try:
        state = profiles.state_dir(ctx.root, ctx.profile)
        path = str(Path(state) / agents.AGENTS)
        write(state, ctx.payload)
    except Exception as exc:
        return session_shell.verdict(core_session.agent_record_failed(exc.__class__.__name__, path, event))
    return gate.allow()


def start(event, ctx):
    return _run(event, ctx, agents.record_start)


def stop(event, ctx):
    return _run(event, ctx, agents.record_end)
