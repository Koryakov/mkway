"""Messages between sessions (card MW-018): one order instead of anarchy.

A star per card. A lead is a registered lead (MW-017). A builder is the holder of a card that a lead ordered, read from
the records and the register of the work tree the session runs in (the shared `sessions.jsonl` names it). Lead to lead,
lead to a builder of a card it ordered, a builder to the lead of its card only, a session with no role to a lead only.
Never builder to builder. `mkway send` enforces it; the hook gate `message` (gate_message.py) judges only the ping.

One append-only inbox per session, `<shared state>/inbox/<session id>.jsonl`, the file MW-017 made for notices. A row
is `{id, from, to, kind, reply_to, ts, ack_ts, body}`; kind is one of `order`, `question`, `answer`, `notice`, `result`.
A session is known by the hook's session id (the lock gate's one-use permit), never by a name in a text. The body lives
in the inbox; the session pinged is told with the native tool by the ping line `mkway inbox <id>` (no socket poster:
card CHECK.md (a)). A send to an unknown or long-unseen session is a row in `<shared state>/dead-letter.jsonl` and a
notice to the sender's lead. Nothing here reads a message for meaning.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import asks
import leads
import logs
import paths
import profiles
import records
import register
import sessions

ORDER, QUESTION, ANSWER, NOTICE, RESULT = "order", "question", "answer", "notice", "result"
KINDS = (ORDER, QUESTION, ANSWER, NOTICE, RESULT)
EVENTS = (NOTICE, RESULT)  # go to a lead and are never relayed on
ROW_FIELDS = ("id", "from", "to", "kind", "reply_to", "ts", "ack_ts", "body")
DEAD = "dead-letter.jsonl"
PINGS = "pings.jsonl"
PING_PREFIX = "mkway inbox "
ID_PATTERN = r"[A-Za-z0-9][A-Za-z0-9._-]*"
PING_LINE = re.compile(re.escape(PING_PREFIX) + "(" + ID_PATTERN + ")")
SHOWN = 5
NE = "not established"


class MessageError(Exception):
    """A refusal of a messaging command: a reason id and the text the session reads, which names the way out."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason
        self.message = message


def ping_line(row_id: str) -> str:
    return f"{PING_PREFIX}{row_id}"


def _now(now=None) -> datetime.datetime:
    moment = now or logs.now()
    return moment if moment.tzinfo else moment.replace(tzinfo=datetime.timezone.utc)


def make_row(sender, to, kind, body, reply_to, now=None) -> dict:
    moment = _now(now)
    return {"id": f"m-{moment.strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(3)}", "from": sender, "to": to, "kind": kind,
            "reply_to": reply_to, "ts": moment.isoformat(timespec="milliseconds"), "ack_ts": None, "body": body}


def append_row(shared, row: dict) -> None:
    logs.append_jsonl(leads.inbox_path(shared, row["to"]), row)


def body_hash(text) -> str:
    """The hash of a body with its line ends and the white space around it ignored: the same words are the same body."""
    flat = str(text if text is not None else "").replace("\r\n", "\n").strip()
    return hashlib.sha256(flat.encode("utf-8")).hexdigest()


def first_line(text, limit: int = 80) -> str:
    line = str(text or "").strip().splitlines()[0] if str(text or "").strip() else ""
    return line if len(line) <= limit else line[:limit - 1] + "…"


# --- who is who ---------------------------------------------------------------------------------------------------

@dataclass
class Role:
    kind: str  # `lead`, `builder` (holds a card a lead ordered) or `none`
    lead: Optional[str] = None  # a builder's lead: the orderer of its card
    card: Optional[str] = None


def _held_in(root, profile, session):
    """(card id, orderer) of the card the session holds in the work tree `root`; None when it holds none or the
    records or the register cannot be read."""
    try:
        state = profiles.state_dir(root, profile)
        card = records.session_card(state, session, register.closed_ids(root, profile))
        if not card:
            return None
        row = register.find(register.read(root, profile), card)
        return card, ((row.get(register.ORDERED) or register.OWNER) if row else register.OWNER)
    except Exception:
        return None


def _same(a, b) -> bool:
    return os.path.normcase(os.path.abspath(str(a))) == os.path.normcase(os.path.abspath(str(b)))


def role_of(root, profile, shared, session) -> Role:
    """A session's role as `root` can read it: a registered lead; the holder of a card a lead ordered, read in `root`
    and in the work tree the shared sessions file names for it; else none."""
    if leads.is_lead(shared, session):
        return Role("lead")
    folders = [(Path(root), profile)]
    known = sessions.latest(shared).get(session)
    if known and known[1] and not _same(known[1], root) and Path(known[1]).is_dir():
        other, errors = profiles.load(paths.profile_path(Path(known[1])))
        if isinstance(other, dict) and not errors:
            folders.append((Path(known[1]), other))
    for where, prof in folders:
        found = _held_in(where, prof, session)
        if found:
            card, ordered = found
            if ordered in leads.lead_ids(shared):
                return Role("builder", ordered, card)
            return Role("none", None, card)
    return Role("none")


# --- the recipient ------------------------------------------------------------------------------------------------

def resolve(shared, prefix: str, hours, now=None):
    """(session id or None, why not, its root text): the session of the shared sessions file that `prefix` names (a whole
    id, else a prefix that starts exactly one). `why` is `unknown` (no such session) or `stale` (last seen more than
    `hours` ago); `message-ambiguous` when the prefix starts several."""
    latest = sessions.latest(shared)
    ids = sorted(latest)
    found = [prefix] if prefix in ids else [i for i in ids if prefix and i.startswith(prefix)]
    if not found:
        return None, "unknown", ""
    if len(found) > 1:
        raise MessageError("message-ambiguous", f"{prefix!r} starts {len(found)} sessions: {', '.join(found)}; give "
                                                f"more of the id (`mkway board` lists them)")
    sid = found[0]
    stamp, root = latest[sid]
    seen = sessions._when(stamp)
    if seen is None or _now(now) - seen > datetime.timedelta(hours=hours):
        return sid, "stale", root
    return sid, None, root


def _dead_letter(root, profile, shared, sender, sender_role, to, kind, body, reply_to, why, now):
    row = make_row(sender, to, kind, body, reply_to, now)
    dead = {k: row[k] for k in ("id", "from", "to", "kind", "reply_to", "ts")}
    dead.update(reason=why, body=body)
    logs.append_jsonl(Path(shared) / DEAD, dead)
    lead = sender if sender_role.kind == "lead" else sender_role.lead
    told = ""
    if lead:
        text = (f"message {dead['id']} to {to!r} was not delivered ({why}: " + (
            "no session of that name or id was ever seen" if why == "unknown" else "that session was last seen too "
            "long ago") + f"); it is in {DEAD}. `mkway board` lists the sessions that are alive")
        try:
            leads.append_notice(shared, lead, text, now=now)
            told = " and your lead was told" if lead != sender else " and a notice is in your inbox"
        except leads.LeadError:
            pass
    raise MessageError("message-dead-letter", f"{to!r} is not a live session ({why}); the message is row {dead['id']} of "
                                              f"{DEAD}{told}. `mkway board` lists the sessions with their ids and "
                                              f"folders; send again to one of them")


# --- the order ----------------------------------------------------------------------------------------------------

def _topology(sender, sender_role: Role, target, target_role: Role, kind: str) -> None:
    def refuse(text):
        raise MessageError("message-topology", text)

    if target == sender:
        refuse("a message to yourself reaches no one; send to the lead of your card (`mkway board` shows it)")
    if kind == ORDER and sender_role.kind != "lead":
        refuse("only a lead orders; a builder sends a `question`, an `answer` or a `result` to the lead of its card, "
               "with `mkway send --to <lead id> --kind <kind> --file <body>`")
    if kind in EVENTS and target_role.kind != "lead":
        refuse(f"a `{kind}` is an event and goes to a lead, never on to a builder; send it to a lead (`mkway leads` "
               f"lists them), or use `--kind order` or `--kind question` for a builder")
    if sender_role.kind == "lead":
        mine = target_role.kind == "builder" and target_role.lead == sender
        if target_role.kind != "lead" and not mine:
            refuse("a lead writes to another lead or to a builder of a card it ordered; `mkway board` shows its "
                   "builders and the leads")
    elif sender_role.kind == "builder":
        if target != sender_role.lead:
            refuse(f"a builder writes to the lead of its card only, which is {sender_role.lead}: "
                   f"`mkway send --to {sender_role.lead} --kind <kind> --file <body>`")
    elif target_role.kind != "lead":
        refuse("a session with no role writes to a lead only; `mkway leads` lists the leads, then "
               "`mkway send --to <lead id> --kind <kind> --file <body>`")


def _duplicate(shared, sender, target, body, hours, now) -> None:
    window = datetime.timedelta(hours=hours)
    digest = body_hash(body)
    for row in leads.all_rows(shared):
        if row.get("from") != sender or row.get("to") == target or body_hash(row.get("body")) != digest:
            continue
        when = leads._when(row.get("ts"))
        if when is not None and now - when < window:
            raise MessageError("message-duplicate", f"the same body went to {row.get('to')} at "
                                                    f"{str(row.get('ts'))[:16]} (row {row.get('id')}): one message has "
                                                    f"one recipient. Write the body for this recipient with "
                                                    f"`mkway send --to <id-prefix> --kind <kind> --file <body>`, or "
                                                    f"wait for the `messaging.duplicate_window_hours` window to pass")


@dataclass
class Sent:
    row: dict
    target: str
    root: str


def send(root, profile, shared, sender, to, kind, body, reply_to=None, now=None) -> Sent:
    """Deliver one message: the row goes to the recipient's inbox; the caller prints the ping. Raises MessageError with
    the reason id (`message-empty`, `message-reply-unknown`, `message-ambiguous`, `message-dead-letter` after the dead
    letter is written, `message-topology`, `message-duplicate`)."""
    moment = _now(now)
    settings = profiles.messaging_settings(profile)
    if kind not in KINDS:
        raise MessageError("message-topology", f"{kind!r} is no kind: one of {', '.join(KINDS)}")
    if not isinstance(body, str) or not body.strip():
        raise MessageError("message-empty", "the body is empty; write the message into the file named by `--file`")
    if reply_to is not None and not any(r.get("id") == reply_to for r in leads.inbox_rows(shared, sender)):
        raise MessageError("message-reply-unknown", f"{reply_to!r} is no row of your inbox; `--reply-to` names a row "
                                                    f"addressed to you (`mkway board` lists them)")
    sender_role = role_of(root, profile, shared, sender)
    target, why, target_root = resolve(shared, to, settings["dead_hours"], moment)
    if why is not None:
        _dead_letter(root, profile, shared, sender, sender_role, to, kind, body, reply_to, why, moment)
    _topology(sender, sender_role, target, role_of(root, profile, shared, target), kind)
    _duplicate(shared, sender, target, body, settings["duplicate_window_hours"], moment)
    row = make_row(sender, target, kind, body, reply_to, moment)
    append_row(shared, row)
    return Sent(row, target, target_root)


# --- reading ------------------------------------------------------------------------------------------------------

def locate(shared, row_id):
    """(row, the session whose inbox holds it) of the first row with this id, or None."""
    folder = Path(shared) / leads.INBOX
    try:
        files = sorted(p for p in folder.iterdir() if p.is_file() and p.name.endswith(".jsonl"))
    except OSError:
        return None
    for file in files:
        for row in leads._read_rows(file):
            if row.get("id") == row_id:
                return row, file.name[:-len(".jsonl")]
    return None


def show(shared, session, row_id: str) -> dict:
    """The row for `mkway inbox <id>`: the session's own (`session` None: the owner, any row)."""
    found = locate(shared, row_id)
    if found is None:
        raise MessageError("inbox-unknown", f"no row {row_id!r} in any inbox; `mkway board` lists the unacked rows with "
                                            f"their ids")
    row, owner = found
    if session is not None and owner != session:
        raise MessageError("inbox-not-yours", f"{row_id!r} is a row of another session's inbox: only its recipient "
                                              f"reads it. `mkway board` lists your own unacked rows")
    return row


def show_lines(row: dict) -> list:
    return [f"id {row.get('id')}", f"kind {row.get('kind')}", f"from {row.get('from')}", f"to {row.get('to')}",
            f"reply_to {row.get('reply_to') or 'none'}", f"ts {row.get('ts')}",
            f"acked {row.get('ack_ts') or 'no'}", "body:", str(row.get("body"))]


def pinged(shared, row_id: str) -> bool:
    try:
        lines = (Path(shared) / PINGS).read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    for line in lines:
        try:
            if json.loads(line).get("id") == row_id:
                return True
        except (ValueError, AttributeError):
            continue
    return False


def record_ping(shared, row_id: str, session: str, now=None) -> None:
    logs.append_jsonl(Path(shared) / PINGS, {"id": row_id, "session": session,
                                             "ts": _now(now).isoformat(timespec="milliseconds")})


def row_from(shared, row_id: str, session: str):
    """The row `row_id` when some inbox holds it and `session` wrote it; else None."""
    found = locate(shared, row_id)
    return found[0] if found and found[0].get("from") == session else None


# --- what a session is told ---------------------------------------------------------------------------------------

def item_line(row: dict) -> str:
    return (f"{row.get('id')} {row.get('kind')} from {row.get('from')}: {first_line(row.get('body'))} "
            f"(`mkway inbox {row.get('id')}`, then `mkway ack {row.get('id')}`)")


def start_lines(shared, session) -> list:
    """The start block's inbox lines for a session that is no lead (a lead's own lines are MW-017's): none when nothing
    is unacked. Never raises."""
    try:
        if leads.is_lead(shared, session):
            return []
        rows = leads.unacked(shared, session) if session else []
    except Exception:
        return []
    if not rows:
        return []
    out = [f"inbox: unacked items: {len(rows)}"]
    out += [f"  {item_line(r)}" for r in rows[:SHOWN]]
    if len(rows) > SHOWN:
        out.append(f"  and {len(rows) - SHOWN} more: `mkway board`")
    return out


def old_orders(shared, session, minutes, now=None) -> list:
    """The unacked orders of the session's inbox older than `minutes`."""
    limit = _now(now) - datetime.timedelta(minutes=minutes)
    out = []
    for row in leads.unacked(shared, session):
        when = leads._when(row.get("ts"))
        if row.get("kind") == ORDER and when is not None and when <= limit:
            out.append(row)
    return out


# --- the board ----------------------------------------------------------------------------------------------------

def _role_text(role: Role) -> str:
    if role.kind == "lead":
        return "lead"
    if role.kind == "builder":
        return f"builder of {role.lead} ({role.card})"
    return "no role" + (f" (holds {role.card}, ordered by the owner)" if role.card else "")


def board_lines(root, profile) -> list:
    """`mkway board`: inboxes (role, folder, unacked, the orders among them, each unacked row), cards (status, who
    ordered, who holds) and asks, in one view. Read-only."""
    shared = profiles.shared_state_dir(root, profile)
    latest = sessions.latest(shared)
    folder = Path(shared) / leads.INBOX
    try:
        with_inbox = [p.name[:-len(".jsonl")] for p in folder.iterdir() if p.name.endswith(".jsonl")]
    except OSError:
        with_inbox = []
    ids = sorted(set(latest) | set(with_inbox) | set(leads.lead_ids(shared)))
    out = ["inboxes:"]
    for sid in ids:
        rows = leads.unacked(shared, sid)
        stamp, where = latest.get(sid, ("", ""))
        out.append(f"  {sid}  {_role_text(role_of(root, profile, shared, sid))}  root {where or NE}  last seen "
                   f"{stamp or NE}  unacked {len(rows)} (orders {sum(1 for r in rows if r.get('kind') == ORDER)})")
        out += [f"    unacked {r.get('id')} {str(r.get('ts'))[:16]} {r.get('kind')} from {r.get('from')}: "
                f"{first_line(r.get('body'))}" for r in rows[:SHOWN * 2]]
    if not ids:
        out.append("  no session seen")
    out.append("cards:")
    cards = []
    try:
        closed = register.closed_ids(root, profile)
        held = records.holders(profiles.state_dir(root, profile), closed)
        for row in register.read(root, profile):
            if row.get("status") != "closed":
                cards.append(f"  {row['id']}  {row.get('status')}  ordered by "
                             f"{row.get(register.ORDERED) or register.OWNER}  held by {held.get(row['id']) or 'none'}")
    except Exception:
        cards = []
    out += cards or ["  no card"]
    out.append("asks:")
    try:
        out += [f"  {line}" for line in asks.board_lines(root, profile)]
    except Exception:
        out.append("  the asks could not be read")
    return out
