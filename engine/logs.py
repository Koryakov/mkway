"""The refusal log and the timing log (card MW-002, deliverable 4; R11 point 2, defect 34).

`<state.dir>/refusals.jsonl`: one JSON line per refuse, warn, gate error, over-budget run, undeclared reason and
dispatcher error. Fields: time, session, event, tool, gate, reason_id, target (a path, or the command head cut to
200 characters), kind, and `verdict: null` (filled later by an audit: right or wrong). Error rows add `exception`
(and `applied` for a gate error); an undeclared reason adds `gate_reason`; an over-budget row adds `elapsed_ms`
and `budget_seconds`.

`<state.dir>/timing-YYYY-MM-DD.jsonl` (UTC date): one row per dispatcher run with the milliseconds of each gate.
Never one row per gate per call.
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path

REFUSALS = "refusals.jsonl"
TARGET_MAX = 200
_PATH_KEYS = ("file_path", "notebook_path", "path")


def now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def target_of(tool_input):
    if not isinstance(tool_input, dict):
        return None
    for key in _PATH_KEYS:
        if isinstance(tool_input.get(key), str) and tool_input[key]:
            return tool_input[key][:TARGET_MAX]
    command = tool_input.get("command")
    if isinstance(command, str) and command.strip():
        return command.strip().splitlines()[0][:TARGET_MAX]
    return None


def row(*, session, event, tool, gate, reason_id, target, kind, **extra) -> dict:
    out = {"time": now().isoformat(timespec="milliseconds"), "session": session, "event": event, "tool": tool,
           "gate": gate, "reason_id": reason_id, "target": target, "kind": kind, "verdict": None}
    out.update(extra)
    return out


def write_refusal(state_dir: Path, data: dict) -> None:
    append_jsonl(Path(state_dir) / REFUSALS, data)


def write_timing(state_dir: Path, data: dict) -> None:
    append_jsonl(Path(state_dir) / f"timing-{now().strftime('%Y-%m-%d')}.jsonl", data)
