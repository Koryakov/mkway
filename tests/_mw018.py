"""Shared helpers for the MW-018 tests (messaging order). Not a test module. Synthetic roots and session ids only."""
import json
import re

from _mw017 import inbox, lead_root, new_card, profile_of, reason_of, register_lead, session_run, state
import sessions

ROW_FIELDS = ["id", "from", "to", "kind", "reply_to", "ts", "ack_ts", "body"]


def seen(root, *ids, when=None, at=None):
    """Rows of the shared `sessions.jsonl`: the sessions the engine has seen (at `when`, naming the folder `at`)."""
    for sid in ids:
        sessions.append(state(root), sid, at or root, now=when)


def world(tmp_path):
    """Two leads; `build-a1` and `build-a2` hold cards lead-a ordered, `build-b1` one lead-b ordered; `free-1` and
    `free-2` hold nothing. Every session is in the shared sessions file."""
    root = lead_root(tmp_path)
    register_lead(root, "lead-a")
    register_lead(root, "lead-b")
    cards = {"build-a1": new_card(root, "lead-a", "First"), "build-a2": new_card(root, "lead-a", "Second"),
             "build-b1": new_card(root, "lead-b", "Other")}
    for who, card in cards.items():
        code, _out, err = session_run(root, who, "card", "take", card)
        assert code == 0, err
    seen(root, "lead-a", "lead-b", "build-a1", "build-a2", "build-b1", "free-1", "free-2")
    return root


def send(root, sender, to, kind, text, *more, name="body.txt"):
    """A session's `mkway send` as the hooks run it; the body is a file under the root. Returns (code, out, err)."""
    (root / name).write_text(text, encoding="utf-8")
    return session_run(root, sender, "send", "--to", to, "--kind", kind, "--file", name, *more)


def ping_of(out) -> str:
    """The exact ping line a successful send prints: `mkway inbox <id>` alone on its line."""
    found = re.findall(r"^(mkway inbox \S+)$", out, re.M)
    assert len(found) == 1, out
    return found[0]


def id_of(out) -> str:
    return ping_of(out).split()[-1]


def rows_of(root, session):
    return inbox(root, session)


def lines(path):
    if not path.is_file():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


__all__ = ["inbox", "lead_root", "new_card", "profile_of", "reason_of", "register_lead", "session_run", "state",
           "ROW_FIELDS", "seen", "world", "send", "ping_of", "id_of", "rows_of", "lines"]
