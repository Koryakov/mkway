"""The sessions file (card MW-017, addition 1): `<shared state>/sessions.jsonl`, one appended row `{session_id, root, ts}`.

The SessionStart hook appends a row; the prompt hook appends a fresh one when the session's last row is older than ten
minutes, so the last row of a session is its last-seen time. The file lives in the shared state folder
(`profiles.shared_state_dir`), so a session of any work tree of the repository is listed by `mkway sessions` with the
folder it runs in. Nothing here reads a message.
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Optional

import logs

SESSIONS = "sessions.jsonl"
REFRESH = datetime.timedelta(minutes=10)


def path(shared) -> Path:
    return Path(shared) / SESSIONS


def rows(shared) -> list:
    try:
        lines = path(shared).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and isinstance(row.get("session_id"), str) and row["session_id"]:
            out.append(row)
    return out


def _when(text) -> Optional[datetime.datetime]:
    try:
        when = datetime.datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None
    return when if when.tzinfo else when.replace(tzinfo=datetime.timezone.utc)


def append(shared, session: str, root, now=None) -> dict:
    row = {"session_id": session, "root": str(root), "ts": (now or logs.now()).isoformat(timespec="milliseconds")}
    logs.append_jsonl(path(shared), row)
    return row


def touch(shared, session, root, *, force: bool = False, now=None) -> bool:
    """Append a row for the session: always with `force` (the start), else only when its last row is ten minutes old or
    it has none. True when a row was written. A session with no id is not recorded."""
    if not isinstance(session, str) or not session.strip():
        return False
    now = now or logs.now()
    if not force:
        last = max((w for r in rows(shared) if r["session_id"] == session and (w := _when(r.get("ts")))), default=None)
        if last is not None and now - last < REFRESH:
            return False
    append(shared, session, root, now)
    return True


def latest(shared) -> dict:
    """session id -> (last-seen time text, root text) from the latest row of each session."""
    found: dict = {}
    for row in rows(shared):
        ts = row.get("ts") if isinstance(row.get("ts"), str) else ""
        if row["session_id"] not in found or ts >= found[row["session_id"]][0]:
            found[row["session_id"]] = (ts, row.get("root") if isinstance(row.get("root"), str) else "")
    return found
