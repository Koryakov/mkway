"""Session records (card MW-003, deliverable 2).

`<state.dir>/records.jsonl`: one appended JSON line per recorded command, `{session_id, kind, value, time, by}`.
A session's command is recorded by the `post` group (PostToolUse), which carries the session id: the command
prints `mkway-ok <kind> <value> <nonce>` on success and writes the nonce under `<state.dir>/nonces/`; the `post`
group matches the line and the nonce, then writes the row (`by: session`). The docs give PostToolUse no exit status,
so the nonce is the proof the command ran and succeeded (ruled 09.11). The owner's terminal runs no hook:
there the command appends its own row (`by: owner`, no session id). Records are append-only.

Recorded kinds: new, take, release, open, close, set, search. The card moves are kept for MW-008 and statistics;
the v1 gates read `take`, `release` and `search` (R19a).
"""
from __future__ import annotations

import json
import os
import re
import secrets
from pathlib import Path
from typing import Optional

import logs

RECORDS = "records.jsonl"
NONCES = "nonces"
OK_LINE = re.compile(r"^mkway-ok (\S+) (.+) ([0-9a-f]{32})\s*$", re.M)
SESSION_ENV = "CLAUDECODE"  # set by Claude Code in a session's shell; the owner's own terminal has none (C44)


def append(state_dir, session_id, kind: str, value: str, by: str = "session") -> dict:
    row = {"session_id": session_id, "kind": kind, "value": value,
           "time": logs.now().isoformat(timespec="milliseconds"), "by": by}
    logs.append_jsonl(Path(state_dir) / RECORDS, row)
    return row


def rows(state_dir) -> list:
    path = Path(state_dir) / RECORDS
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


def holders(state_dir, closed=None) -> dict:
    """card id -> the session holding it: its latest accepted `take`, not followed by a `release` of that card by
    that session or by the owner (MW-003). A `take` is ignored when another session holds the card, or when the
    taking session holds a card that is not in `closed` (one card per session; the close check's H3). `closed` is
    the set of closed card ids from the register; None is read as no card closed (the strict reading)."""
    closed = set(closed or ())
    held: dict = {}
    for row in rows(state_dir):
        kind, value, who = row.get("kind"), row.get("value"), row.get("session_id")
        if kind == "take" and who:
            if value in held:
                continue  # a holder is never overridden, not even by itself
            if any(h == who and card not in closed for card, h in held.items()):
                continue
            held[value] = who
        elif kind == "release" and value in held and (row.get("by") == "owner" or who == held[value]):
            held.pop(value, None)  # only the holder or the owner's terminal frees a card
    return held


def session_card(state_dir, session, closed=None) -> Optional[str]:
    """The card this session holds by its latest accepted `take`, or None."""
    if not session:
        return None
    held = holders(state_dir, closed)
    latest = None
    for row in rows(state_dir):
        if row.get("kind") == "take" and row.get("session_id") == session and held.get(row.get("value")) == session:
            latest = row.get("value")
    return latest


def has(state_dir, session, kind: str) -> bool:
    return bool(session) and any(r.get("kind") == kind and r.get("session_id") == session for r in rows(state_dir))


def issue(state_dir, kind: str, value: str) -> str:
    """A fresh nonce for one successful command; its file holds `<kind> <value>`."""
    nonce = secrets.token_hex(16)
    folder = Path(state_dir) / NONCES
    folder.mkdir(parents=True, exist_ok=True)
    with open(folder / nonce, "x", encoding="utf-8", newline="\n") as fh:
        fh.write(f"{kind} {value}")
    return nonce


def consume(state_dir, nonce: str, kind: str, value: str) -> bool:
    """True once for a nonce issued for exactly this kind and value; the nonce is then used up."""
    if not re.fullmatch(r"[0-9a-f]{32}", nonce or ""):
        return False
    path = Path(state_dir) / NONCES / nonce
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    if text != f"{kind} {value}":
        return False
    try:
        os.remove(path)
    except OSError:
        return False
    return True


class View:
    """What a gate reads of the records: bound to the state folder, the calling session and a reader of the closed
    card ids (the register's; MW-003 H3)."""

    def __init__(self, state_dir, session, closed=None):
        self.state_dir = Path(state_dir)
        self.session = session
        self._closed = closed or (lambda: set())

    def holders(self) -> dict:
        return holders(self.state_dir, self._closed())

    def card(self) -> Optional[str]:
        return session_card(self.state_dir, self.session, self._closed())

    def has(self, kind: str) -> bool:
        return has(self.state_dir, self.session, kind)
