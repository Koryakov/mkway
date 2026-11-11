"""Agent records (card MW-004).

`<state.dir>/agents.jsonl`: appended JSON lines, two kinds per helper agent.
  start: `{kind, session_id, agent_id, agent_type, started}`, written by the `SubagentStart` hook.
  end:   `{kind, session_id, agent_id, agent_type, started, ended, elapsed_seconds, result, result_source}`, written
         by the `SubagentStop` hook. `started` is the start row of the same session and agent id, when that row is
         the last one for the pair; `result` is the payload's `last_assistant_message` in full, else the last
         assistant message of the file `agent_transcript_path` names (`result_source` payload, transcript, or none).
A value the hook cannot establish is the text «not established»: never a guess. Records are append-only.
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Optional

import logs

AGENTS = "agents.jsonl"
NE = "not established"
DEFAULT_CAP_MINUTES = 30  # `agents.cap_minutes` when the profile does not say (part 2)


def stamp(moment: datetime.datetime) -> str:
    return moment.isoformat(timespec="milliseconds")


def append(state_dir, row: dict) -> dict:
    logs.append_jsonl(Path(state_dir) / AGENTS, row)
    return row


def rows(state_dir) -> list:
    path = Path(state_dir) / AGENTS
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _text(value, default=NE) -> str:
    return value if isinstance(value, str) and value.strip() else default


def identity(payload) -> tuple:
    """(session_id, agent_id, agent_type) of a hook payload; each «not established» when missing."""
    payload = payload if isinstance(payload, dict) else {}
    return (_text(payload.get("session_id")), _text(payload.get("agent_id")), _text(payload.get("agent_type")))


def record_start(state_dir, payload) -> dict:
    session, agent, kind = identity(payload)
    return append(state_dir, {"kind": "start", "session_id": session, "agent_id": agent, "agent_type": kind,
                              "started": stamp(logs.now())})


def _last_row(state_dir, session: str, agent: str) -> Optional[dict]:
    last = None
    for row in rows(state_dir):
        if row.get("session_id") == session and row.get("agent_id") == agent:
            last = row
    return last


def _message_text(record) -> str:
    """The text blocks of one transcript record, joined by a newline; empty for a record that is not an assistant
    message or holds no text (a tool call has none)."""
    if not isinstance(record, dict):
        return ""
    message = record.get("message")
    if not isinstance(message, dict) or (record.get("type") or message.get("role")) != "assistant":
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content if content.strip() else ""
    parts = [b.get("text") for b in content or [] if isinstance(b, dict) and b.get("type") == "text"
             and isinstance(b.get("text"), str) and b["text"].strip()]
    return "\n".join(parts)


def transcript_result(path) -> Optional[str]:
    """The last assistant message with text in a transcript file (one JSON record per line); None when the file
    cannot be read or holds none."""
    if not isinstance(path, str) or not path.strip():
        return None
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, ValueError):
        return None
    found = None
    for line in text.splitlines():
        try:
            record = json.loads(line)
        except ValueError:
            continue
        message = _message_text(record)
        if message:
            found = message
    return found


def result_of(payload) -> tuple:
    """(result text, source): the payload's own message, else the transcript's last assistant message."""
    payload = payload if isinstance(payload, dict) else {}
    message = payload.get("last_assistant_message")
    if isinstance(message, str) and message.strip():
        return message, "payload"
    found = transcript_result(payload.get("agent_transcript_path"))
    if found is not None:
        return found, "transcript"
    return NE, "none"


def _parse(value) -> Optional[datetime.datetime]:
    try:
        moment = datetime.datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=datetime.timezone.utc)


def record_end(state_dir, payload) -> dict:
    session, agent, kind = identity(payload)
    ended = logs.now()
    last = _last_row(state_dir, session, agent)
    began = _parse(last.get("started")) if last and last.get("kind") == "start" else None
    result, source = result_of(payload)
    return append(state_dir, {
        "kind": "end", "session_id": session, "agent_id": agent, "agent_type": kind,
        "started": stamp(began) if began else NE, "ended": stamp(ended),
        "elapsed_seconds": round((ended - began).total_seconds(), 3) if began else NE,
        "result": result, "result_source": source})


# ---- the cap and the start block (part 2) -----------------------------------------------------------------------

def cap_minutes(profile):
    """`agents.cap_minutes` of the profile (a number above 0), else 30. A value the schema refuses is never read:
    the profile is then invalid and no gate runs."""
    group = profile.get("agents") if isinstance(profile, dict) else None
    value = group.get("cap_minutes") if isinstance(group, dict) else None
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
        return value
    return DEFAULT_CAP_MINUTES


def _number(value) -> str:
    return f"{value:g}" if isinstance(value, (int, float)) else str(value)


def report(state_dir, session, cap) -> list:
    """The start-block lines for one session, in file order: each end row longer than `cap` minutes (strictly), and
    each agent whose last row is a start row (no end row). Rows of other sessions, and end rows whose time is not
    established, give no line. A row that cannot be read is skipped."""
    if not isinstance(session, str) or not session:
        return []
    mine = [r for r in rows(state_dir) if r.get("session_id") == session]
    last = {}
    for position, row in enumerate(mine):
        last[row.get("agent_id")] = position
    now = logs.now()
    lines = []
    for position, row in enumerate(mine):
        who = f"agent {_text(row.get('agent_type'))} {_text(row.get('agent_id'))}"
        if row.get("kind") == "end":
            took = row.get("elapsed_seconds")
            if isinstance(took, (int, float)) and not isinstance(took, bool) and took > cap * 60:
                lines.append(f"{who}: ran {took / 60:.1f} min, over the cap of {_number(cap)} min "
                             f"(started {_text(row.get('started'))}, ended {_text(row.get('ended'))})")
        elif row.get("kind") == "start" and last.get(row.get("agent_id")) == position:
            began = _parse(row.get("started"))
            so_far = f"{(now - began).total_seconds() / 60:.1f} min so far, " if began else ""
            lines.append(f"{who}: started {_text(row.get('started'))}, no end row ({so_far}cap {_number(cap)} min)")
    return lines
