"""The ping gate (card MW-076; decisions R185 to R188): a session that caused an inbox write to another session also pings
it with SendMessage; a lead is told of the pings that were skipped. The decisions are the pure `core_ping`; this shell
reads the facts and writes the rows a verdict carries.

One entry, `ping.stop` (Stop, class form; switch `gates.ping.on`; mode `gates.ping.mode`: `trip` refuses, `watch` warns):
- a builder's Stop (any session that is no registered lead): the engine's record of inbox writes
  (`<shared>/inbox-writes.jsonl`, written by `leads.write_row`, the one writer of an inbox row) says which rows this
  session caused this turn; the transcript says whether a SendMessage came after. The first Stop is refused
  `ping-not-sent` with the ping line and the target's name; the Stop of the continuation (`stop_hook_active`, the field
  Claude Code documents) passes with the log verdict `ping-skipped` and a row in `<shared>/ping-skipped.jsonl`.
- a lead's Stop: each skipped ping addressed to it, and each engine notice nobody pinged, is listed once as a warn line
  (`ping-skipped-listed`); `<shared>/ping-seen.jsonl` remembers what it was shown.

The gate reads tool names, ids, times and file rows, never a message for its meaning.
"""
from __future__ import annotations

import json
from pathlib import Path

import core_ping as core
import gate
import gate_owner_ask
import leads
import logs
import messages
import profiles

SKIPPED_FILE = "ping-skipped.jsonl"
SEEN_FILE = "ping-seen.jsonl"


def _rows(path) -> list:
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
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


def _verdict(decided: core.Verdict) -> gate.Verdict:
    if decided.kind == "refuse":
        return gate.refuse(decided.reason, decided.text)
    if decided.kind == "warn":
        return gate.warn(decided.reason, decided.text)
    if decided.kind == "log":
        return gate.log(decided.reason, decided.text)
    return gate.allow()


def _now() -> str:
    return logs.now().isoformat(timespec="milliseconds")


def _builder_name(root, profile, shared, session) -> str:
    """How the lead's line names the builder: the `name` of its live builder row in mkcl's sessions file (by its card),
    else the first eight characters of its session id."""
    card = messages.role_of(root, profile, shared, session).card
    data = messages.sessions_data(root, profile)
    rows = data.get("sessions") if isinstance(data, dict) else None
    for row in rows if isinstance(rows, list) else []:
        if isinstance(row, dict) and card and row.get("kind") == "builder" and row.get("card") == card \
                and row.get("state") != "closed" and isinstance(row.get("name"), str) and row["name"].strip():
            return row["name"].strip()
    return session[:8]


def _candidates(shared, session) -> list:
    """The record rows this session may have caused: it wrote them, or the engine did (the core attributes the latter),
    addressed to another session."""
    return [w for w in leads.inbox_writes(shared)
            if w.get("to") != session and (w.get("from") == session or w.get("from") == leads.ENGINE)]


def _builder_stop(ctx, profile, shared, session):
    candidates = _candidates(shared, session)
    if not candidates:
        return gate.allow()
    hook_input = ctx.hook_input if isinstance(ctx.hook_input, dict) else {}
    after, readable, user = gate_owner_ask.turn_split(hook_input.get("transcript_path"))
    names = {}
    for write in candidates:
        to = write.get("to")
        if to not in names:
            names[to] = messages.target_name(ctx.root, profile, shared, to, session)
    facts = core.PingFacts(
        session_id=session, entries=tuple(after) if readable else None,
        writes=tuple({**w, "name": names.get(w.get("to"))} for w in candidates),
        turn_start=user.get("timestamp") if isinstance(user, dict) else None,
        hook_active=bool(hook_input.get("stop_hook_active")), is_lead=False, mode=profiles.ping_mode(profile))
    decided = core.decide_stop(facts)
    builder = _builder_name(ctx.root, profile, shared, session) if decided.records else None
    known = {r.get("inbox_id") for r in _rows(Path(shared) / SKIPPED_FILE)}
    for _what, row in decided.records:  # the builder's records are `ping-skipped` rows only
        if row["inbox_id"] not in known:
            logs.append_jsonl(Path(shared) / SKIPPED_FILE, {
                "id": f"ps-{row['inbox_id']}", "builder_session": session, "builder": builder, "lead": row["to"],
                "inbox_id": row["inbox_id"], "kind": row["kind"], "name": row["name"], "ts": _now()})
    return _verdict(decided)


def _lead_rows(shared, session) -> tuple:
    """The skipped pings and the unpinged engine notices addressed to this lead, as the core reads them."""
    skipped = [r for r in _rows(Path(shared) / SKIPPED_FILE) if r.get("lead") == session]
    rows = [{"id": r["id"], "builder": r.get("builder"), "inbox_id": r.get("inbox_id"), "origin": "session"}
            for r in skipped if isinstance(r.get("id"), str)]
    listed = {r.get("inbox_id") for r in skipped}
    for write in leads.inbox_writes(shared):
        if write.get("from") == leads.ENGINE and write.get("to") == session and write.get("id") not in listed \
                and not messages.pinged(shared, write.get("id")):
            rows.append({"id": f"en-{write['id']}", "builder": None, "inbox_id": write["id"], "origin": "engine"})
    return tuple(rows)


def _lead_stop(shared, session):
    seen = frozenset(r.get("id") for r in _rows(Path(shared) / SEEN_FILE) if r.get("lead") == session)
    decided = core.decide_lead_stop(core.LeadStopFacts(is_lead=True, rows=_lead_rows(shared, session), seen=seen))
    for _what, row in decided.records:  # the lead's records are `seen` rows only
        for row_id in row["ids"]:
            logs.append_jsonl(Path(shared) / SEEN_FILE, {"id": row_id, "lead": session, "ts": _now()})
    return _verdict(decided)


def stop(event, ctx):
    """The Stop step of the ping gate: a lead's list, or a builder's refusal; a session with no id is not judged."""
    profile = ctx.profile if isinstance(ctx.profile, dict) else {}
    shared = profiles.shared_state_dir(ctx.root, profile)
    session = ctx.session_id
    if not isinstance(session, str) or not session.strip():
        return gate.allow()
    if leads.is_lead(shared, session):
        return _lead_stop(shared, session)
    return _builder_stop(ctx, profile, shared, session)
