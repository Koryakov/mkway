"""The `post` group's agent records (card MW-004, part 1).

`SubagentStart` appends a start row, `SubagentStop` an end row with the result in full, to `<state.dir>/agents.jsonl`
(see `agents.py`). Neither gate ever refuses: a block on `SubagentStop` would keep a finished agent going. When a row
cannot be written the gate warns `agent-record-failed`; the dispatcher logs it and renders no context for these events.
"""
from __future__ import annotations

import agents
import gate
import profiles


def _run(ctx, write):
    try:
        write(profiles.state_dir(ctx.root, ctx.profile), ctx.payload)
    except Exception as exc:
        return gate.warn("agent-record-failed", f"the agent record could not be written ({exc.__class__.__name__}); "
                                                "the agent's result may not be saved")
    return gate.allow()


def start(event, ctx):
    return _run(ctx, agents.record_start)


def stop(event, ctx):
    return _run(ctx, agents.record_end)
