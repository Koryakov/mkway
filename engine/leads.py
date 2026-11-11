"""The lead role (card MW-017): who is a lead, the hand-off of a card between leads, the notices a lead receives.

A lead is a session that orders work and does not do it. It is known by its session id, which only the hook input
carries (the one-use permit of the lock gate, as for `ledger add`): never by a name in a text. `<state>/leads.json`
is `{"leads": [{"session_id", "role": "lead", "since"}], "handoffs": [{"card", "from", "to", "ts"}]}`. A lead's `give`
of a card it ordered is a hand-off that takes effect only when the new lead runs `lead accept`; the owner's `give`
needs no accept.

A notice is one row `{id, from, to, kind: notice, ts, ack_ts, body}` appended to `<state>/inbox/<lead id>.jsonl`. The
file and the fields are what the messaging card extends, so they stay exactly as they are. The engine writes a notice
when a card is past its Appetite, when a form gate trips, when a default is taken on an ask, and when a builder moves a
card to `waiting`. `ack` sets `ack_ts` of one row. A notice unacked for `leads.escalate_hours` is shown to the owner.

No gate and no command here reads a message: a lead's words are never the owner's consent.
"""
from __future__ import annotations

import datetime
import json
import math
import os
import re
import secrets
from pathlib import Path
from typing import Optional

import cardtool
import helpers
import logs
import profiles
import records
import register

LEADS = "leads.json"
INBOX = "inbox"
ROLE = "lead"
ENGINE = "engine"  # the `from` of a notice the engine writes
NOTICE = "notice"
ORDER_FILE = "ORDER.md"
CARD_FILE = "CARD.md"
ACTIVE = ("open", "waiting", "waiting-owner")  # a card that is being worked: its Appetite runs
_SAFE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


class LeadError(Exception):
    """A refusal of a lead command: a reason id and the text the session reads, which names the way out."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason
        self.message = message


# --- the registry ------------------------------------------------------------------------------------------------

def path(state) -> Path:
    return Path(state) / LEADS


def read(state) -> dict:
    """`{"leads": [...], "handoffs": [...]}`; a missing or unreadable file, or an item without its fields, reads as
    empty: a gate never fails on it."""
    try:
        data = json.loads(path(state).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    data = data if isinstance(data, dict) else {}
    lead_rows = [r for r in data.get("leads") or [] if isinstance(r, dict)
                 and isinstance(r.get("session_id"), str) and r["session_id"]] if isinstance(
        data.get("leads"), list) else []
    hands = [h for h in data.get("handoffs") or [] if isinstance(h, dict)
             and all(isinstance(h.get(k), str) and h[k] for k in ("card", "from", "to"))] if isinstance(
        data.get("handoffs"), list) else []
    return {"leads": lead_rows, "handoffs": hands}


def _write(state, data: dict) -> None:
    target = path(state)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, target)


def lead_ids(state) -> list:
    return [r["session_id"] for r in read(state)["leads"]]


def is_lead(state, session) -> bool:
    return isinstance(session, str) and bool(session.strip()) and session in lead_ids(state)


def register_lead(state, session: str) -> bool:
    """Record the session as a lead; True when it was not one."""
    data = read(state)
    if session in [r["session_id"] for r in data["leads"]]:
        return False
    data["leads"].append({"session_id": session, "role": ROLE, "since": logs.now().isoformat(timespec="milliseconds")})
    _write(state, data)
    return True


def remove_lead(state, session: str) -> bool:
    """Take the session out of the leads, with the hand-offs that name it; True when it was a lead."""
    data = read(state)
    kept = [r for r in data["leads"] if r["session_id"] != session]
    if len(kept) == len(data["leads"]):
        return False
    data["leads"] = kept
    data["handoffs"] = [h for h in data["handoffs"] if session not in (h["from"], h["to"])]
    _write(state, data)
    return True


def resolve_seen(state, who: str, shared=None) -> str:
    """The session id seen in the state records (and the shared sessions file) that `who` names (the owner's
    `lead add`)."""
    if not who or who == register.OWNER:
        raise LeadError("lead-unknown", f"{who!r} names no session; `mkway sessions` lists the ids seen")
    try:
        return cardtool.resolve_session(state, who, shared)
    except cardtool.CardError as exc:
        raise LeadError("lead-ambiguous" if exc.reason == "give-ambiguous" else "lead-unknown", str(exc))


def resolve_lead(state, who: str, *, unknown: str = "lead-unknown", hint: str = "`mkway leads` lists them") -> str:
    """The one registered lead that `who` names (the whole id, else a prefix that matches exactly one)."""
    ids = lead_ids(state)
    if who and who in ids:
        return who
    found = [i for i in ids if who and i.startswith(who)]
    if len(found) == 1:
        return found[0]
    if not found:
        raise LeadError(unknown, f"no registered lead starts with {who!r}; {hint}")
    raise LeadError("lead-ambiguous", f"{who!r} starts {len(found)} leads: {', '.join(found)}; give more of the id")


def not_registered() -> LeadError:
    return LeadError("lead-not-registered", "this session is no registered lead: it runs `mkway lead register` in its "
                                            "own session, or the owner runs `mkway lead add <id-prefix>`")


# --- the hand-off of a card (a lead's give, then the new lead's accept) -----------------------------------------------

def give(root, profile, state, session: str, card: str, who: str) -> tuple:
    """A lead's `give <card> <id-prefix>`: only a card this session ordered, only to another registered lead. The
    register is not changed; the hand-off waits for `lead accept`. Returns (card id, the lead it is offered to)."""
    if not is_lead(state, session):
        raise not_registered()
    card_id = cardtool.card_ref(profile, card)
    row = register.find(register.read(root, profile), card_id)
    if row is None:
        raise cardtool.CardError(f"{card_id} is not in the register", reason="card-unknown")
    ordered = row.get(register.ORDERED) or register.OWNER
    if ordered != session:
        raise LeadError("lead-give-not-yours", f"{card_id} was ordered by {ordered}, not by this session: a lead gives "
                                               f"only the cards it ordered. The owner's `mkway give {card_id} "
                                               f"<id-prefix>` moves any card")
    target = resolve_lead(state, who, unknown="lead-give-not-lead",
                          hint="the owner adds one with `mkway lead add <id-prefix>`, or that session runs "
                               "`mkway lead register`")
    if target == session:
        raise LeadError("lead-give-self", f"{card_id} is already yours; give it to another lead with `mkway give "
                                          f"{card_id} <id-prefix>`")
    if register.file_has_orderer(root, profile) is not True:
        raise cardtool.CardError(f"the register has no `{register.orderer_column(profile)}` column; the owner adds it "
                                 f"with `mkway card resync --add-ordered-by` in their own terminal",
                                 reason="give-no-column")
    data = read(state)
    data["handoffs"] = [h for h in data["handoffs"] if h["card"] != card_id]
    data["handoffs"].append({"card": card_id, "from": session, "to": target,
                             "ts": logs.now().isoformat(timespec="milliseconds")})
    _write(state, data)
    return card_id, target


def accept(root, profile, state, session: str, card: str) -> tuple:
    """`lead accept <card>` by the new lead: the card's orderer becomes this session. Refused when no hand-off to this
    session waits (`lead-accept-none`) or the card has another orderer than the one who offered it
    (`lead-accept-stale`; the hand-off is dropped). Returns (card id, the previous orderer)."""
    if not is_lead(state, session):
        raise not_registered()
    card_id = cardtool.card_ref(profile, card)
    data = read(state)
    mine = [h for h in data["handoffs"] if h["card"] == card_id and h["to"] == session]
    if not mine:
        raise LeadError("lead-accept-none", f"no hand-off of {card_id} to this session is waiting; the lead that "
                                            f"ordered it runs `mkway give {card_id} <your id prefix>` first (the "
                                            f"owner's `mkway give` needs no accept)")
    offered_by = mine[-1]["from"]
    row = register.find(register.read(root, profile), card_id)
    if row is None:
        raise cardtool.CardError(f"{card_id} is not in the register", reason="card-unknown")
    ordered = row.get(register.ORDERED) or register.OWNER
    data["handoffs"] = [h for h in data["handoffs"] if h["card"] != card_id]
    _write(state, data)
    if ordered != offered_by:
        raise LeadError("lead-accept-stale", f"{card_id} is now ordered by {ordered}, not by {offered_by}, so the "
                                             f"hand-off is dropped; the orderer runs `mkway give {card_id} <your id "
                                             f"prefix>` again")
    register.set_ordered(root, profile, card_id, session)
    return card_id, offered_by


# --- the notices -----------------------------------------------------------------------------------------------------

def inbox_path(state, lead: str) -> Path:
    if not isinstance(lead, str) or not _SAFE.fullmatch(lead) or ".." in lead:
        raise LeadError("lead-bad-id", f"{lead!r} is not a plain session id, so it has no inbox; `mkway leads` lists "
                                       f"the registered leads")
    return Path(state) / INBOX / f"{lead}.jsonl"


def _when(text) -> Optional[datetime.datetime]:
    try:
        when = datetime.datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None
    return when if when.tzinfo else when.replace(tzinfo=datetime.timezone.utc)


def append_notice(state, lead: str, body: str, *, sender: str = ENGINE, now=None) -> dict:
    """Append one notice row to the lead's inbox; the row is returned."""
    target = inbox_path(state, lead)
    moment = now or logs.now()
    moment = moment if moment.tzinfo else moment.replace(tzinfo=datetime.timezone.utc)
    row = {"id": f"n-{moment.strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(3)}", "from": sender, "to": lead,
           "kind": NOTICE, "reply_to": None, "ts": moment.isoformat(timespec="milliseconds"), "ack_ts": None,
           "body": body}  # MW-018: `reply_to` joins the row, so a message and a notice have one shape
    logs.append_jsonl(target, row)
    return row


def _read_rows(file: Path) -> list:
    try:
        lines = file.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def inbox_rows(state, lead: str) -> list:
    try:
        return _read_rows(inbox_path(state, lead))
    except LeadError:
        return []


def all_rows(state) -> list:
    folder = Path(state) / INBOX
    try:
        files = sorted(p for p in folder.iterdir() if p.is_file() and p.name.endswith(".jsonl"))
    except OSError:
        return []
    return [r for f in files for r in _read_rows(f)]


def unacked(state, lead: str) -> list:
    return [r for r in inbox_rows(state, lead) if r.get("ack_ts") is None]


def ack(state, lead, notice_id: str) -> dict:
    """Set `ack_ts` of the one unacked notice `notice_id` in the lead's inbox (`lead` None: the owner, any inbox).
    `ack-unknown` when there is none."""
    if lead is None:
        folder = Path(state) / INBOX
        try:
            files = sorted(p for p in folder.iterdir() if p.is_file() and p.name.endswith(".jsonl"))
        except OSError:
            files = []
    else:
        files = [inbox_path(state, lead)]
    for file in files:
        rows = _read_rows(file)
        for row in rows:
            if row.get("id") == notice_id and row.get("ack_ts") is None:
                row["ack_ts"] = logs.now().isoformat(timespec="milliseconds")
                tmp = file.with_name(file.name + ".tmp")
                tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
                os.replace(tmp, file)
                return row
    if lead is not None and any(r.get("id") == notice_id and r.get("ack_ts") is None for r in all_rows(state)):
        raise LeadError("ack-not-yours", f"{notice_id!r} is a row of another session's inbox: only its recipient acks "
                                         f"it. `mkway board` lists your own unacked rows, and `mkway inbox <id>` reads "
                                         f"one")
    where = "any inbox" if lead is None else "your inbox"
    raise LeadError("ack-unknown", f"no unacked row {notice_id!r} in {where}; `mkway board` lists the unacked rows "
                                   f"with their ids (a lead: `mkway leads`)")


def escalated(state, hours, now=None) -> list:
    """The notices, in every inbox, that stayed unacked for `hours` or more."""
    limit = (now or logs.now()) - datetime.timedelta(hours=hours)
    out = []
    for row in all_rows(state):
        when = _when(row.get("ts"))
        if row.get("ack_ts") is None and when is not None and when <= limit:
            out.append(row)
    return out


def notify_all(state, body: str) -> list:
    """A notice to every registered lead (a gate that tripped)."""
    return [append_notice(state, lead, body) for lead in lead_ids(state)]


def notify_orderer(root, profile, card_id: str, body: str) -> list:
    """A notice to the card's orderer, when that is a registered lead; nothing otherwise."""
    state = profiles.shared_state_dir(root, profile)
    row = register.find(register.read(root, profile), card_id)
    ordered = (row.get(register.ORDERED) or register.OWNER) if row else None
    return [append_notice(state, ordered, body)] if ordered and ordered in lead_ids(state) else []


# --- the Appetite of a card ------------------------------------------------------------------------------------------

_AMOUNT = re.compile(r"(\d+(?:\.\d+)?)\s*(minutes?|mins?|hours?|hrs?|h|days?|d|weeks?|w)\b", re.I)
_FROM = re.compile(r"\bfrom\s+(\d{4})-(\d{2})-(\d{2})\b", re.I)
_HOURS = {"m": 1 / 60, "h": 1, "d": 24, "w": 168}


def appetite_due(text) -> Optional[datetime.datetime]:
    """The moment a card's Appetite cell runs out, as a naive local time: the start date plus the whole days the amount
    takes (at least one), at 00:00. The cell says only a date, so a day is the finest step. None when the cell has no
    amount or no start date."""
    amount, start = _AMOUNT.search(text or ""), _FROM.search(text or "")
    if not amount or not start:
        return None
    try:
        begin = datetime.datetime(int(start.group(1)), int(start.group(2)), int(start.group(3)))
    except ValueError:
        return None
    hours = float(amount.group(1)) * _HOURS[amount.group(2)[0].lower()]
    return begin + datetime.timedelta(days=max(1, math.ceil(hours / 24 - 1e-9)))


def overdue(root, profile, lead=None, now=None) -> list:
    """(card id, orderer, Appetite cell) of each card past its Appetite that is open or waiting and ordered by a
    registered lead (by `lead` alone when given)."""
    state = profiles.shared_state_dir(root, profile)
    ids = set(lead_ids(state))
    now = now or datetime.datetime.now()
    out = []
    try:
        rows = register.read(root, profile)
    except (OSError, register.RegisterError):
        return []
    for row in rows:
        ordered = row.get(register.ORDERED) or register.OWNER
        if ordered not in ids or (lead is not None and ordered != lead) or row.get("status") not in ACTIVE:
            continue
        try:
            cell = cardtool.header(cardtool.card_file(root, profile, row["id"]).read_text(encoding="utf-8"),
                                   "Appetite")
        except (OSError, cardtool.CardError):
            continue
        due = appetite_due(cell)
        if due is not None and now >= due:
            out.append((row["id"], ordered, cell))
    return out


def sweep(root, profile, now=None) -> list:
    """Write the notice of each card past its Appetite that has none yet (one per card and text, acked or not).
    Returns the rows written."""
    state = profiles.shared_state_dir(root, profile)
    written = []
    for card_id, lead, cell in overdue(root, profile, now=now):
        body = (f"{card_id} is past its Appetite ({cell}): close it with `mkway card close {card_id}` once its tests "
                f"pass, or cut the work down; the order is yours")
        if any(r.get("body") == body for r in inbox_rows(state, lead)):
            continue
        written.append(append_notice(state, lead, body))
    return written


# --- what a session and the owner read ---------------------------------------------------------------------------------

SHOWN = 5
NE = cardtool.NE


def _notice_line(row: dict) -> str:
    return f"{row.get('id')} {str(row.get('ts'))[:16]} {row.get('body')}"


def start_lines(root, profile, session, now=None) -> list:
    """The start block's lines: a lead sees its own unacked notices; any other session sees the notices that stayed
    unacked past `leads.escalate_hours`, which is how they reach the owner. Never raises."""
    state = profiles.shared_state_dir(root, profile)
    try:
        sweep(root, profile)
    except Exception:
        pass
    lines = []
    if is_lead(state, session):
        rows = unacked(state, session)
        lines.append(f"lead: unacked notices: {len(rows)}" + ("; acknowledge each with `mkway ack <id>`" if rows else ""))
        lines += [f"  notice {_notice_line(r)}" for r in rows[:SHOWN]]
        if len(rows) > SHOWN:
            lines.append(f"  and {len(rows) - SHOWN} more: `mkway leads`")
        return lines
    hours = profiles.leads_settings(profile)["escalate_hours"]
    rows = escalated(state, hours, now=now)
    if rows:
        per: dict = {}
        for r in rows:
            per[r.get("to")] = per.get(r.get("to"), 0) + 1
        lines.append(f"lead notices unacked over {hours:g} h: {len(rows)} ("
                     + ", ".join(f"{lead}: {n}" for lead, n in sorted(per.items())) + "); `mkway leads` lists them")
        lines += [f"  {r.get('to')} {_notice_line(r)}" for r in rows[:SHOWN]]
    return lines


def view_lines(root, profile, now=None) -> list:
    """`mkway leads`: one line for each registered lead (id, cards ordered and not closed, overdue, last activity,
    unacked and escalated notices), the unacked notices under it, and a warning line for a lead above
    `leads.max_cards` (a warning, never a refusal)."""
    state = profiles.shared_state_dir(root, profile)
    ids = sorted(lead_ids(state))
    if not ids:
        return ["no registered lead; a lead runs `mkway lead register` in its own session, or the owner runs "
                "`mkway lead add <id-prefix>`"]
    settings = profiles.leads_settings(profile)
    try:
        rows = register.read(root, profile)
    except (OSError, register.RegisterError):
        rows = []
    seen, _missing = cardtool.seen_sessions(profiles.state_dir(root, profile), state)
    late = overdue(root, profile, now=now)
    stale = {r.get("id") for r in escalated(state, settings["escalate_hours"])}
    out, warnings = [], []
    for sid in ids:
        ordered = [r["id"] for r in rows if (r.get(register.ORDERED) or register.OWNER) == sid
                   and r.get("status") != "closed"]
        mine_late = [c for c, lead, _cell in late if lead == sid]
        open_notices = unacked(state, sid)
        out.append(f"{sid}  ordered {len(ordered)} ({', '.join(ordered) or 'none'})  overdue {len(mine_late)} "
                   f"({', '.join(mine_late) or 'none'})  last activity {seen.get(sid) or NE}  unacked "
                   f"{len(open_notices)} (escalated {sum(1 for r in open_notices if r.get('id') in stale)})")
        out += [f"  unacked {_notice_line(r)}" for r in open_notices[:SHOWN * 2]]
        if len(ordered) > settings["max_cards"]:
            warnings.append(f"warning: {sid} has {len(ordered)} cards ordered and not closed, above leads.max_cards "
                            f"{settings['max_cards']}; hand some on with `mkway give <card> <id-prefix>`; nothing is "
                            f"refused")
    return out + warnings


# --- the order file ---------------------------------------------------------------------------------------------------

def order_template() -> Path:
    return cardtool.ENGINE_COPY / "cards" / "_TEMPLATE" / ORDER_FILE


def write_order(folder, card_id: str) -> Optional[Path]:
    """The card folder's `ORDER.md` from the engine's template, headed with the card id; an existing file is kept.
    None when the engine copy has no template."""
    target = Path(folder) / ORDER_FILE
    try:
        lines = order_template().read_text(encoding="utf-8").splitlines(keepends=True)
    except OSError:
        return None
    if target.exists() or not lines:
        return None
    lines[0] = f"# {card_id}: order\n"
    with open(target, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("".join(lines))
    return target


# --- what a lead may write -----------------------------------------------------------------------------------------------

def writable(root, profile, session, rel) -> bool:
    """True when `rel` (a repo path) is one a registered lead may write: `<card folder>/ORDER.md` of a card it
    ordered, `<card folder>/CARD.md` of a card it ordered while the card is `proposed` (MW-028: the lead authors its
    own card before the owner opens it; the sealed register's status decides), or inside the asks folder. Whether the
    session is a lead is the caller's check."""
    if not isinstance(rel, str):
        return False
    if helpers.matches(rel, profiles.owner_ask(profile)["dir"]):
        return True
    try:
        rows = register.read(root, profile)
    except (OSError, register.RegisterError):
        return False
    for row in rows:
        if (row.get(register.ORDERED) or register.OWNER) != session:
            continue
        folder = cardtool.norm_entry(row.get("folder", ""))
        if not folder:
            continue
        if helpers.matches(rel, f"{folder}/{ORDER_FILE}"):
            return True
        if row.get("status") == "proposed" and helpers.matches(rel, f"{folder}/{CARD_FILE}") \
                and not register.seal_problem(root, profile):
            return True
    return False
