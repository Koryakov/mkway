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
import board
import cardtool
import core_ping
import core_session
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
RECORD = "message-record.jsonl"  # record R1: one row per delivered send and per ack (ruling R279)
REFUSAL_EVENT = "refusal-delivery"  # MW-128: the record row of the inbox write the Stop hook makes; it is no `send`
SCOPE = "messaging"  # the scope of the one-use permit of a messaging command (ruling R279c Q1)
_SESSION_FILE = re.compile(r"[A-Za-z0-9._-]+")
PING_PREFIX = core_session.PING_PREFIX  # one definition, in the pure core (card MW-066)
ID_PATTERN = core_session.ID_PATTERN
PING_LINE = core_session.PING_LINE
SHOWN = 5
NE = "not established"
_EXPANDS = re.compile(r"\$(?=\S)|`")  # `$(`, `$name`, `${`, `$1`, a backtick; a `$` before a space or at the end is a dollar


def text_problem(text: str) -> Optional[str]:
    """MW-055: None when `text` is taken as the literal body of `send --text`; else what is wrong. The content of a quoted
    argument is literal (MW-048) except `$(...)`, a backtick, `$name`, `${name}` and `$digit`, which a shell expands."""
    if _EXPANDS.search(text or ""):
        return ("the text holds `$(...)`, a backtick or `$name`, which a shell expands before the engine sees it; put "
                "the message in a file under mkway/asks and pass `--file <path>`")
    return None


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
    leads.write_row(shared, row)


def body_hash(text) -> str:
    """The hash of a body with its line ends and the white space around it ignored: the same words are the same body."""
    flat = str(text if text is not None else "").replace("\r\n", "\n").strip()
    return hashlib.sha256(flat.encode("utf-8")).hexdigest()


def first_line(text, limit: int = 80) -> str:
    line = str(text or "").strip().splitlines()[0] if str(text or "").strip() else ""
    return line if len(line) <= limit else line[:limit - 1] + "…"


# --- the permit of a messaging command (ruling R279c Q1) ------------------------------------------------------------
# The lock gate leaves the permit of `send`, `inbox` and `ack` under the session's own id, `permits/<session id>.json`, so
# two sessions never overwrite or take each other's. The CLI opens only the file its variable names; with no variable,
# before the end date, it takes the single most recent one. The shared `by.json` of the other commands is not touched.

def _permit_file(state, session) -> Optional[Path]:
    if not isinstance(session, str) or session in (".", "..") or not _SESSION_FILE.fullmatch(session):
        return None
    return Path(state) / cardtool.PERMITS / f"{session}.json"


def issue_message_permit(state, session) -> bool:
    """Leave the one-use permit of a messaging command under the session's own id: `{session_id, scope, time}`. False when
    the id is empty or cannot be a file name."""
    target = _permit_file(state, session)
    if target is None:
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(json.dumps({"session_id": session, "scope": SCOPE,
                               "time": logs.now().isoformat(timespec="milliseconds")}), encoding="utf-8")
    os.replace(tmp, target)
    return True


def _read_permit(file: Path):
    """(session id, age in seconds) of a messaging-scope permit file; None when it cannot be read or is no such permit."""
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
        moment = datetime.datetime.fromisoformat(data["time"])
        moment = moment if moment.tzinfo else moment.replace(tzinfo=datetime.timezone.utc)
        session = data.get("session_id")
        if data.get("scope") == SCOPE and isinstance(session, str) and session:
            return session, (logs.now() - moment).total_seconds()
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        pass
    return None


def _fresh(age: float) -> bool:
    return -5 <= age <= cardtool.PERMIT_SECONDS


def _consume(file: Path) -> None:
    """A permit is used once: the file is taken away whatever it held."""
    try:
        os.remove(file)
    except OSError:
        pass


def take_message_permit(state, session) -> Optional[str]:
    """The session id inside `permits/<session>.json`, once: the file is consumed whatever it holds. None when there is none,
    it is no messaging permit, it is older than `cardtool.PERMIT_SECONDS`, or it cannot be read. Only this one file is opened."""
    target = _permit_file(state, session)
    if target is None:
        return None
    found = _read_permit(target)
    _consume(target)
    return found[0] if found and _fresh(found[1]) else None


def take_latest_message_permit(state) -> Optional[str]:
    """The session id of the most recent fresh messaging permit of any session, once (that file is consumed); the expired
    messaging permits are consumed too. None when there is none. The caller asks only when the variable is unset and the end
    date has not passed: this is the transition's accepted limit, two sessions at once can take each other's permit."""
    folder = Path(state) / cardtool.PERMITS
    try:
        files = [f for f in folder.iterdir() if f.is_file() and f.name.endswith(".json")]
    except OSError:
        return None
    best = None
    for file in files:
        found = _read_permit(file)
        if found is None:
            continue
        if not _fresh(found[1]):
            _consume(file)
        elif best is None or found[1] < best[1]:
            best = (found[0], found[1], file)
    if best is None:
        return None
    _consume(best[2])
    return best[0]


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
            leads.append_notice(shared, lead, text, now=now, by=sender)
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
            if kind == ORDER and target_role.kind == "none" and not target_role.card:
                refuse(f"order refused: {target} holds no card. Start a new builder session with the order as its "
                       f"first prompt (mkcl), one card = one session.")
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


def send(root, profile, shared, sender, to, kind, body, reply_to=None, now=None, record=None) -> Sent:
    """Deliver one message: the row goes to the recipient's inbox; the caller prints the ping. Raises MessageError with
    the reason id (`message-empty`, `message-reply-unknown`, `message-ambiguous`, `message-dead-letter` after the dead
    letter is written, `message-topology`, `message-duplicate`). `record` (R279c Q3): a function of the row, called BEFORE
    the row is delivered; a record that cannot be written raises `send-record-failed` and nothing is delivered."""
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
    if record is not None:
        _written_first(lambda: record(row), "send", shared)
    append_row(shared, row)
    return Sent(row, target, target_root)


def _written_first(write, what: str, shared) -> None:
    """R279c Q3: the record is written before the action; an OSError is `send-record-failed` (the id of a send and of an
    ack), and the text names the file, the state folder and the way out."""
    try:
        write()
    except OSError as exc:
        done = "nothing is delivered" if what == "send" else "the row stays unacked"
        raise MessageError("send-record-failed", f"the record of this {what} could not be written to "
                                                 f"{Path(shared) / RECORD} ({exc.__class__.__name__}), and the record is "
                                                 f"written first, so {done}. Make the state folder {shared} writable (free "
                                                 f"space, rights, no folder in place of the file), then run the command "
                                                 f"again")


def ack(shared, session: Optional[str], row_id: str) -> dict:
    """Acknowledge one row (`session` None: the owner, any inbox), record first (R279c Q3): when the row exists and is
    unacked in the scope, its record row is written, and only then is the row acked; a record that cannot be written is
    `send-record-failed` and the row stays unacked. A row that cannot be acked for its own cause (`ack-unknown`,
    `ack-not-yours`) keeps that reason and writes no record."""
    rows = leads.all_rows(shared) if session is None else leads.inbox_rows(shared, session)
    if any(r.get("id") == row_id and r.get("ack_ts") is None for r in rows):
        _written_first(lambda: record_ack(shared, row_id, session), "ack", shared)
    return leads.ack(shared, session, row_id)


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


def record_send(shared, row: dict, session: str, file, now=None) -> None:
    """Record R1 (ruling R279 Q1): one engine-written row for each delivered send, in `<shared>/message-record.jsonl`: the
    sender's session id, the recipient, the file as named (`--text` for the text form), the sha256 of the body and a time.
    The inbox file alone is not the record: a session can rewrite its own copy of a row."""
    logs.append_jsonl(Path(shared) / RECORD, {
        "event": "send", "id": row["id"], "session": session, "to": row["to"], "file": file,
        "sha256": hashlib.sha256(str(row["body"]).encode("utf-8")).hexdigest(),
        "ts": _now(now).isoformat(timespec="milliseconds")})


def record_ack(shared, row_id: str, session: Optional[str], now=None) -> None:
    """Record R1: one engine-written row for each acknowledgement: the acking session (`owner` for the owner's terminal)
    and the row id."""
    logs.append_jsonl(Path(shared) / RECORD, {"event": "ack", "id": row_id, "session": session or "owner",
                                              "ts": _now(now).isoformat(timespec="milliseconds")})


def sends_by(shared, session: str) -> list:
    """MW-128: the times of the `mkway send` calls of this session, from the message record (event `send`). The inbox write the
    Stop hook makes itself is a row of event `refusal-delivery` and is no send."""
    try:
        lines = (Path(shared) / RECORD).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            row = json.loads(line)
        except (ValueError, AttributeError):
            continue
        if isinstance(row, dict) and row.get("event") == "send" and row.get("session") == session:
            out.append(row.get("ts"))
    return out


def orderer_of(root, profile, session) -> Optional[str]:
    """MW-128: the value of the register's orderer column for the card this session holds; None when the session holds no card,
    or the cell is empty or names the owner (the owner is no session an inbox row can go to)."""
    found = _held_in(root, profile, session)
    if not found or not found[1] or found[1] == register.OWNER:
        return None
    return found[1]


def sends_to(shared, session: str) -> list:
    """MW-132 (R1-6): this session's `mkway send` records as (time, recipient), oldest first, from the message record (event
    `send`). `sends_by` stays as MW-128 reads it. The engine's own inbox writes (events `refusal-delivery`, `handoff-notice`) are
    no send."""
    try:
        lines = (Path(shared) / RECORD).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            row = json.loads(line)
        except (ValueError, AttributeError):
            continue
        if isinstance(row, dict) and row.get("event") == "send" and row.get("session") == session:
            out.append((row.get("ts"), row.get("to")))
    return out


def held_card(root, profile, session):
    """MW-132 (R1-7, R2-22): (card id, orderer) of the card the session holds in `root`; None when it holds none. The orderer is the
    register's orderer cell, the owner when the cell is empty. Unlike `_held_in` this raises when the records or the register cannot
    be read, so the caller can tell a failed read from «no card» and from «no orderer»."""
    state = profiles.state_dir(root, profile)
    card = records.session_card(state, session, register.closed_ids(root, profile))
    if not card:
        return None
    row = register.find(register.read(root, profile), card)
    return card, ((row.get(register.ORDERED) or register.OWNER) if row else register.OWNER)


HANDOFF_EVENT = "handoff-notice"  # MW-132 (R1-3): the record row of the inbox write the Stop hook makes for a silent turn end


def record_handoff(shared, row: dict, session: str, card: str, now=None) -> None:
    """MW-132 (R1-3): the message record of the handoff notice: event `handoff-notice`, so it is told apart from a `send` of the
    session (`sends_by` and `sends_to` never count it) and from a `refusal-delivery`."""
    logs.append_jsonl(Path(shared) / RECORD, {
        "event": HANDOFF_EVENT, "id": row["id"], "session": session, "to": row["to"], "card": card,
        "ts": _now(now).isoformat(timespec="milliseconds")})


def send_handoff(root, profile, shared, session, to, body, card, now=None) -> Sent:
    """MW-132 (R338, R338a): the one handoff notice, a `notice` row from this session to its orderer. It is the engine's own write,
    so the star topology of `send` is not asked: an orderer that is a seen session but no registered lead still gets it (only the
    block is dropped for such a role). Raises `MessageError` when the orderer is not a live session; the record is written first."""
    moment = _now(now)
    settings = profiles.messaging_settings(profile)
    target, why, target_root = resolve(shared, to, settings["dead_hours"], moment)
    if why is not None:
        raise MessageError("message-dead-letter", f"{to!r} is not a live session ({why}); the handoff notice was not written")
    row = make_row(session, target, NOTICE, body, None, moment)
    _written_first(lambda: record_handoff(shared, row, session, card, now), "send", shared)
    append_row(shared, row)
    return Sent(row, target, target_root)


PATHS_EVENT = "paths-notice"  # MW-137: the record row of the inbox notice a re-record of a card's Paths writes to its holder


def record_paths_notice(shared, row: dict, session: str, card: str, now=None) -> None:
    """MW-137: the message record of the paths notice: event `paths-notice`, so `sends_by` and `sends_to` never count it."""
    logs.append_jsonl(Path(shared) / RECORD, {
        "event": PATHS_EVENT, "id": row["id"], "session": session, "to": row["to"], "card": card,
        "ts": _now(now).isoformat(timespec="milliseconds")})


def send_paths_notice(shared, sender, to, body, card, now=None) -> dict:
    """MW-137 (R352 A d): the one `notice` row from the lead (`owner` from the owner's terminal) to the holder of a card whose
    Paths were re-recorded. The engine's own write, as the handoff notice and the refusal record are: the star topology of
    `send` is not asked, and the holder needs no live session in the sessions file. The record is written first; the row is
    returned. Raises `LeadError` for an id that has no inbox and `MessageError` (`send-record-failed`) for a record that cannot
    be written."""
    leads.inbox_path(shared, to)  # an id that has no inbox path is refused before anything is written
    row = make_row(sender, to, NOTICE, body, None, now)
    _written_first(lambda: record_paths_notice(shared, row, sender, card, now), "send", shared)
    append_row(shared, row)
    return row


def record_refusal(shared, row: dict, session: str, refusal_id: str, now=None) -> None:
    """MW-128: the message record of the inbox write the Stop hook makes itself: event `refusal-delivery`, so it is told apart
    from a `send` of the session."""
    logs.append_jsonl(Path(shared) / RECORD, {
        "event": REFUSAL_EVENT, "id": row["id"], "session": session, "to": row["to"], "refusal": refusal_id,
        "ts": _now(now).isoformat(timespec="milliseconds")})


def send_refusal(root, profile, shared, session, to, command, line, refusal_id, now=None) -> Sent:
    """MW-128 (R301, R301a): the one inbox refusal record, a `notice` from this session to its orderer through `send` (so it
    shows in the orderer's normal inbox and `mkway inbox <id>` reads it). Raises what `send` raises when it cannot be written."""
    import core_refusal
    body = core_refusal.inbox_body(session, command, line, refusal_id)
    return send(root, profile, shared, session, to, NOTICE, body, now=now,
                record=lambda row: record_refusal(shared, row, session, refusal_id, now))


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


def engine_row(shared, row_id: str, session: str):
    """MW-076 (R187, R189, R197 B): the row `row_id` when the engine wrote it (a notice) for another session and `session`
    is the one that caused it: the record row names it as `by`. A notice with no `by` is nobody's to ping (see
    `engine_no_by`), and a row caused by another session is None."""
    found = locate(shared, row_id)
    if not found or found[0].get("from") != leads.ENGINE or found[1] == session:
        return None
    record = next((r for r in leads.inbox_writes(shared) if r.get("id") == row_id), {})
    return found[0] if record.get("by") == session else None


def engine_no_by(shared, row_id: str) -> bool:
    """MW-076 (R197 B): True when the row `row_id` is a notice the engine wrote and its record has no `by`."""
    found = locate(shared, row_id)
    if not found or found[0].get("from") != leads.ENGINE:
        return False
    record = next((r for r in leads.inbox_writes(shared) if r.get("id") == row_id), {})
    return not record.get("by")


def sessions_data(root, profile):
    """The parsed mkcl `sessions.json` that the profile key `sessions.file` names (read only); None when there is no key,
    or the file is missing or cannot be read (the caller falls back silently)."""
    named = profiles.sessions_file(profile)
    if not named:
        return None
    path = Path(named)
    path = path if path.is_absolute() else Path(root) / path
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def target_name(root, profile, shared, target, sender=None):
    """The SendMessage name of the session `target` (R185, in this order): the `name` of its row in the lead register,
    else the name in mkcl's sessions file (by its resume id, else the starter of the sender's card); None when unknown."""
    for row in leads.read(shared)["leads"]:
        if row["session_id"] == target and isinstance(row.get("name"), str) and row["name"].strip():
            return row["name"].strip()
    card = role_of(root, profile, shared, sender).card if sender else None
    return core_ping.sessions_name(sessions_data(root, profile), target, card)


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
                f"{first_line(r.get('body'))} (age {board.age_text(r.get('ts'), _now(None))})" for r in rows]  # MW-112 (R270a): every one, with its age
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
    try:  # MW-112 (R3): old red, uncommitted files, a card with no result, a failed agent record, under the cards
        extra = [f"  {line}" for line in board.lines(root, profile)]
    except Exception:
        extra = []
    out += (cards + extra) or ["  no card"]
    out.append("asks:")
    try:
        out += [f"  {line}" for line in asks.board_lines(root, profile)]
    except Exception:
        out.append("  the asks could not be read")
    return out
