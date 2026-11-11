"""Card MW-017, part 3, rows E9 to E16: the notices a lead receives (`<state>/inbox/<lead id>.jsonl`), `mkway ack`, the
start block and prompt reminder of a lead, and the escalation to the owner. The inbox file and its fields are what
the next card (messaging) extends, so they are pinned exactly. Synthetic roots and session ids only."""
import datetime
import json
import re

import pytest

from _engine import cli, gate_call
from _mw012 import form_entry, make_root, run, seed_calls
from _mw014 import PAST, write_ask
from _mw017 import NOTICE_FIELDS, inbox, lead_root, new_card, profile_of, register_lead, session_run, state
import cardtool
import gate_lead
import leads
import records
import register
import startline

NOW = datetime.datetime(2026, 11, 12, 9, 0)  # a naive local time, as the Appetite dates are read


def _set_status(root, card, status):
    register.write(root, profile_of(root), lambda rows: [dict(r, status=status) if r["id"] == card else r
                                                         for r in rows])


def _set_appetite(root, card, text):
    path = cardtool.card_file(root, profile_of(root), card)
    body = re.sub(r"^\| \*\*Appetite\*\* \|.*\|$", lambda _m: f"| **Appetite** | {text} |",
                  path.read_text(encoding="utf-8"), flags=re.M)
    path.write_text(body, encoding="utf-8", newline="\n")


def _ordered_open_card(root, lead, appetite=None, status="open"):
    card = new_card(root, lead)
    _set_status(root, card, status)
    if appetite:
        _set_appetite(root, card, appetite)
    return card


def test_a_notice_row_has_exactly_the_agreed_fields_and_file(tmp_path):
    """E9: a notice is one row `{id, from, to, kind: notice, reply_to, ts, ack_ts, body}` (MW-018 adds `reply_to`) appended to
    `<state>/inbox/<lead id>.jsonl`; the fields and their order are what the messaging card extends. A lead id that is
    not a plain name writes nothing (`lead-bad-id`). Catches: a renamed field, a row in the wrong file."""
    root = lead_root(tmp_path)
    first = leads.append_notice(state(root), "lead-a", "first body")
    second = leads.append_notice(state(root), "lead-a", "second body")
    assert list(first) == NOTICE_FIELDS
    assert (first["kind"], first["to"], first["from"], first["ack_ts"], first["body"]) == (
        "notice", "lead-a", "engine", None, "first body")
    assert datetime.datetime.fromisoformat(first["ts"]) and first["id"] != second["id"]
    assert inbox(root, "lead-a") == [first, second]
    with pytest.raises(leads.LeadError) as caught:
        leads.append_notice(state(root), "a/b", "x")
    assert caught.value.reason == "lead-bad-id"
    assert sorted(p.name for p in (state(root) / "inbox").iterdir()) == ["lead-a.jsonl"]


def test_the_appetite_cell_gives_a_due_date():
    """E10: `<n> <unit> from <date>` is due on the start date plus the whole days the amount takes, at least one;
    units minute, hour, day and week; a cell that says no amount or no date has no due date."""
    due = leads.appetite_due
    assert due("2 hours — from 2026-11-10") == datetime.datetime(2026, 11, 11)
    assert due("30 minutes — from 2026-11-11") == datetime.datetime(2026, 11, 12)
    assert due("3 days — the most this work is worth, from 2026-11-10") == datetime.datetime(2026, 11, 13)
    assert due("1 week - from 2026-11-01") == datetime.datetime(2026, 11, 8)
    assert due("26 hours from 2026-11-10") == datetime.datetime(2026, 11, 12)
    for none in ("N days — the most this work is worth, from the creation date", "", "soon", "2 hours"):
        assert due(none) is None, none


def test_a_card_past_its_appetite_notifies_the_lead_that_ordered_it_once(tmp_path):
    """E10: a card of a registered lead that is open or waiting and past its Appetite is a notice to that lead, once
    (the same card never again, acked or not); a closed or proposed card, a card still in time, a card the owner
    ordered and a card of a session that is no lead give none. The text names `mkway card close <id>`."""
    root = lead_root(tmp_path)
    register_lead(root, "lead-a")
    late = _ordered_open_card(root, "lead-a", "1 day — from 2026-11-10")
    waiting = _ordered_open_card(root, "lead-a", "1 day — from 2026-11-10", status="waiting")
    in_time = _ordered_open_card(root, "lead-a", "5 days — from 2026-11-10")
    closed = _ordered_open_card(root, "lead-a", "1 day — from 2026-11-10", status="closed")
    proposed = _ordered_open_card(root, "lead-a", "1 day — from 2026-11-10", status="proposed")
    builder = _ordered_open_card(root, "builder-1", "1 day — from 2026-11-10")
    owners = new_card(root, "builder-1")
    cli(root, "give", owners, "owner")
    _set_status(root, owners, "open")
    _set_appetite(root, owners, "1 day — from 2026-11-10")
    rows = leads.sweep(root, profile_of(root), now=NOW)
    bodies = [r["body"] for r in inbox(root, "lead-a")]
    assert len(rows) == 2 and len(bodies) == 2
    assert any(late in b for b in bodies) and any(waiting in b for b in bodies)
    assert all("Appetite" in b and "mkway card close" in b for b in bodies)
    assert not any(x in b for b in bodies for x in (in_time, closed, proposed, builder, owners))
    assert leads.sweep(root, profile_of(root), now=NOW) == []
    leads.ack(state(root), "lead-a", inbox(root, "lead-a")[0]["id"])
    assert leads.sweep(root, profile_of(root), now=NOW) == [] and len(inbox(root, "lead-a")) == 2
    assert inbox(root, "builder-1") == []


def test_the_prompt_gate_sweeps_for_every_session(tmp_path):
    """E10: the prompt-group step finds the overdue cards at any session's next prompt (a builder's, the owner's), not
    only a lead's; with real time, a card due long ago."""
    root = lead_root(tmp_path)
    register_lead(root, "lead-a")
    card = _ordered_open_card(root, "lead-a", "1 day — from 2000-01-01")
    verdict = gate_call(gate_lead.remind, root, session="builder-1", event="UserPromptSubmit")
    assert verdict.kind == "allow"
    assert [card in r["body"] for r in inbox(root, "lead-a")] == [True]


def test_a_tripped_gate_notifies_every_lead(tmp_path):
    """E11: when a form gate trips into watch (MW-012) every registered lead gets a notice that names the gate and the
    owner's `mkway gate on <gate>`; with no lead registered nothing is written and the trip is unchanged."""
    root = make_root(tmp_path)
    seed_calls(root, "f1", allow=13, refuse=6)
    run(root, [form_entry("f1")], "src/bad.py")
    assert not (state(root) / "inbox").exists()
    other = make_root(tmp_path / "two")
    for lead in ("lead-a", "lead-b"):
        leads.register_lead(state(other), lead)
    seed_calls(other, "f1", allow=13, refuse=6)
    run(other, [form_entry("f1")], "src/bad.py")
    for lead in ("lead-a", "lead-b"):
        (row,) = inbox(other, lead)
        assert "f1" in row["body"] and "tripped" in row["body"] and "mkway gate on f1" in row["body"]


def _ask_by(root, name, builder, card=None):
    write_ask(root, name, session=builder, deadline=PAST)
    if card:
        records.append(state(root), builder, "take", card)


def test_a_default_taken_notifies_the_orderer_of_the_ask_card(tmp_path):
    """E12: `mkway ask default` notifies the lead that ordered the card the asking session holds; with the card not
    established every lead is told; a card ordered by the owner tells nobody."""
    root = lead_root(tmp_path)
    register_lead(root, "lead-a")
    register_lead(root, "lead-b")
    card = new_card(root, "lead-a")
    _ask_by(root, "q1", "builder-1", card)
    code, _out, err = session_run(root, "builder-1", "ask", "default", "q1")
    assert code == 0, err
    (row,) = inbox(root, "lead-a")
    assert "ask q1" in row["body"] and "default taken" in row["body"] and inbox(root, "lead-b") == []
    _ask_by(root, "q2", "builder-2")
    assert session_run(root, "builder-2", "ask", "default", "q2")[0] == 0
    assert [len(inbox(root, x)) for x in ("lead-a", "lead-b")] == [2, 1]
    owned = new_card(root, "builder-3")
    cli(root, "give", owned, "owner")
    _ask_by(root, "q3", "builder-3", owned)
    assert session_run(root, "builder-3", "ask", "default", "q3")[0] == 0
    assert [len(inbox(root, x)) for x in ("lead-a", "lead-b")] == [2, 1]


def test_a_builder_that_finishes_notifies_the_orderer(tmp_path):
    """E13: a session's `card set <id> waiting` of the card it holds is a notice to the card's orderer when that is a
    registered lead; the text names `mkway card close <id>`. A card the owner ordered gives none."""
    root = lead_root(tmp_path)
    register_lead(root, "lead-a")
    card = new_card(root, "lead-a")
    _set_status(root, card, "open")
    records.append(state(root), "builder-1", "take", card)
    code, _out, err = session_run(root, "builder-1", "card", "set", card, "waiting")
    assert code == 0, err
    (row,) = inbox(root, "lead-a")
    assert card in row["body"] and f"mkway card close {card}" in row["body"] and "finished" in row["body"]
    owned = new_card(root, "builder-2")
    cli(root, "give", owned, "owner")
    _set_status(root, owned, "open")
    records.append(state(root), "builder-2", "take", owned)
    assert session_run(root, "builder-2", "card", "set", owned, "waiting")[0] == 0
    assert len(inbox(root, "lead-a")) == 1


def test_ack_clears_one_notice_of_the_leads_own_inbox(tmp_path):
    """E14: `mkway ack <id>` sets `ack_ts` of that one notice in the calling lead's inbox and changes nothing else.
    Another lead's notice, an acked one and an unknown id are `ack-unknown` (the text names `mkway leads`); a session
    that is no lead is `lead-not-registered`; the owner's terminal acks any lead's notice."""
    root = lead_root(tmp_path)
    register_lead(root, "lead-a")
    register_lead(root, "lead-b")
    one = leads.append_notice(state(root), "lead-a", "one")
    two = leads.append_notice(state(root), "lead-a", "two")
    theirs = leads.append_notice(state(root), "lead-b", "theirs")
    code, out, err = session_run(root, "lead-a", "ack", one["id"])
    assert code == 0, err
    rows = inbox(root, "lead-a")
    assert datetime.datetime.fromisoformat(rows[0]["ack_ts"]) and rows[1] == two
    assert {k: v for k, v in rows[0].items() if k != "ack_ts"} == {k: v for k, v in one.items() if k != "ack_ts"}
    for bad in (one["id"], "n-nothing"):
        code, _out, err = session_run(root, "lead-a", "ack", bad)
        assert code != 0 and "ack-unknown" in err and "mkway leads" in err, bad
    code, _out, err = session_run(root, "lead-a", "ack", theirs["id"])  # changed by MW-018 (E8): another inbox's row
    assert code != 0 and "ack-not-yours" in err
    code, _out, err = session_run(root, "builder-1", "ack", two["id"])  # changed by MW-018: any session acks its own row
    assert code != 0 and "ack-not-yours" in err and "mkway inbox" in err
    assert cli(root, "ack", theirs["id"])[0] == 0
    assert inbox(root, "lead-b")[0]["ack_ts"]


def test_the_start_block_and_the_prompt_show_a_leads_unacked_notices(tmp_path):
    """E15: the start block of a registered lead has the line `lead: unacked notices: N` and one line for each (id and
    body); the prompt reminder warns `lead-notices-unacked` and names `mkway ack <id>`; an acked notice and a session
    that is no lead see nothing."""
    root = lead_root(tmp_path)
    register_lead(root, "lead-a")
    one = leads.append_notice(state(root), "lead-a", "first matter")
    two = leads.append_notice(state(root), "lead-a", "second matter")
    leads.ack(state(root), "lead-a", two["id"])
    profile = profile_of(root)

    def block(session):
        return startline.render(root, root / "mkway" / "profile.json", profile, [], [], {}, session=session)

    text = block("lead-a")
    assert "lead: unacked notices: 1" in text and one["id"] in text and "first matter" in text
    assert two["id"] not in text
    assert "unacked notices" not in block("builder-1")
    verdict = gate_call(gate_lead.remind, root, session="lead-a", event="UserPromptSubmit")
    assert verdict.kind == "warn" and verdict.reason_id == "lead-notices-unacked"
    assert one["id"] in verdict.message and f"mkway ack {one['id']}" in verdict.message
    leads.ack(state(root), "lead-a", one["id"])
    assert gate_call(gate_lead.remind, root, session="lead-a", event="UserPromptSubmit").kind == "allow"
    assert gate_call(gate_lead.remind, root, session="builder-1", event="UserPromptSubmit").kind == "allow"


def test_notices_unacked_past_the_escalation_time_reach_the_owner(tmp_path):
    """E16: a notice unacked for `leads.escalate_hours` (default 4) is shown in the start block of a session that is no
    lead; before that time, and once acked, it is not; the key changes the time."""
    root = lead_root(tmp_path)
    register_lead(root, "lead-a")
    now = datetime.datetime.now(datetime.timezone.utc)
    old = leads.append_notice(state(root), "lead-a", "old matter", now=now - datetime.timedelta(hours=5))
    leads.append_notice(state(root), "lead-b", "newer matter", now=now - datetime.timedelta(hours=2))
    assert [r["id"] for r in leads.escalated(state(root), 4, now=now)] == [old["id"]]
    assert len(leads.escalated(state(root), 1, now=now)) == 2 and leads.escalated(state(root), 6, now=now) == []
    profile = profile_of(root)

    def block(session, prof=profile):
        return startline.render(root, root / "mkway" / "profile.json", prof, [], [], {}, session=session)

    text = block("owner-session")
    assert "lead notices unacked over 4 h: 1" in text and "lead-a" in text and old["id"] in text
    assert "unacked over" not in block("lead-a")
    assert "unacked over 1 h: 2" in block("owner-session", dict(profile, leads={"escalate_hours": 1}))
    leads.ack(state(root), "lead-a", old["id"])
    assert "unacked over 4 h" not in block("owner-session")
