"""The refusal log and the timing log (card MW-002, deliverable 4; R11 point 2, defect 34).

`<state.dir>/refusals.jsonl`: one JSON line per refuse, warn, gate error, over-budget run, undeclared reason and
dispatcher error. Fields: time, session, event, tool, gate, reason_id, target (a path, or the command head cut to
200 characters, every newline of the command written as `\n`: MW-061), kind, and `verdict: null` (filled later by an
audit: right or wrong). Error rows add `exception`
(and `applied` for a gate error); an undeclared reason adds `gate_reason`; an over-budget row adds `elapsed_ms`
and `budget_seconds`.

`<state.dir>/timing-YYYY-MM-DD.jsonl` (UTC date): one row per dispatcher run with the milliseconds of each gate.
Never one row per gate per call.
"""
from __future__ import annotations

import datetime
import json
import os
import secrets
import time
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


# ---- the append lock (card MW-129, R310 1) ---------------------------------------------------------------------------------
# A copy of the register's lock (register.py `_acquire`, `_holds`, `_release`, which stay untouched) with the register's
# numbers (register.py:43-44): a marker file BESIDE the file written, never a lock marker of the owners (`<shared>/locks`).
APPEND_WAIT_SECONDS = 5
APPEND_STALE_SECONDS = 30
APPEND_ATTEMPTS = 3  # builds under the lock before the writer gives up: a takeover in the middle sends it round again


class AppendBusy(Exception):
    """Another writer holds the append lock of a file beyond the bounded wait: the writer wrote nothing (repeat the call)."""


def append_lock_path(path) -> Path:
    path = Path(path)
    return path.with_name(path.name + ".lock")


def _replace_marker(target: Path, data: bytes) -> None:
    tmp = target.with_name(target.name + f".{secrets.token_hex(4)}.tmp")
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, target)


def _acquire(lock: Path) -> str:
    token = secrets.token_hex(16)
    lock.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + APPEND_WAIT_SECONDS
    while True:
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(token)
            return token
        except FileExistsError:
            try:
                stale = time.time() - lock.stat().st_mtime > APPEND_STALE_SECONDS
            except OSError:
                stale = False
            if stale:
                _replace_marker(lock, token.encode("utf-8"))
                return token
            if time.monotonic() > deadline:
                raise AppendBusy(str(lock))
            time.sleep(0.05)


def _holds(lock: Path, token: str) -> bool:
    try:
        return lock.read_text(encoding="utf-8") == token
    except OSError:
        return False


def _release(lock: Path, token: str) -> None:
    if _holds(lock, token):
        try:
            os.remove(lock)
        except OSError:
            pass


def append_jsonl_locked(path, build):
    """Append one complete JSON line under the append lock of `path`. `build(text)` gets the file's text under the lock and
    returns the row to write, or None to write nothing (the check of a key and the append are one step). Returns the row
    written, or None. A file that does not end with a newline gets one first (R310 1 h). The lock is released in `finally`
    (b); after a takeover of a stale marker the writer checks that it still holds the lock just before the append, else it
    acquires again and builds again (c). Raises `AppendBusy` when the lock stays busy beyond the wait."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = append_lock_path(path)
    token = _acquire(lock)
    try:
        for _ in range(APPEND_ATTEMPTS):
            raw = path.read_bytes() if path.is_file() else b""
            row = build(raw.decode("utf-8", "replace"))
            if row is None:
                return None
            if not _holds(lock, token):
                token = _acquire(lock)
                continue
            line = (json.dumps(row, ensure_ascii=False) + "\n").encode("utf-8")
            with open(path, "ab") as fh:
                fh.write((b"\n" if raw and not raw.endswith(b"\n") else b"") + line)
            return row
        raise AppendBusy(str(lock))
    finally:
        _release(lock, token)


def target_of(tool_input):
    if not isinstance(tool_input, dict):
        return None
    for key in _PATH_KEYS:
        if isinstance(tool_input.get(key), str) and tool_input[key]:
            return tool_input[key][:TARGET_MAX]
    command = tool_input.get("command")
    if isinstance(command, str) and command.strip():
        whole = command.strip().replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\n")  # MW-061: not the first line only
        return whole[:TARGET_MAX]
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
