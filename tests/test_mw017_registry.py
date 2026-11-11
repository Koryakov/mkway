"""Card MW-017, part 1, rows E1 to E4: who is a lead (`<state>/leads.json`), the owner's `lead add|remove`, a lead's
`give` that waits for `lead accept`. Identity is always the hook's session id (the one-use permit of the lock gate).
Synthetic roots and session ids only."""
import json

import pytest

from _engine import cli, gate_call, task_root
from _mw017 import (inbox, lead_root, leads_data, leads_file, new_card, profile_of, reason_of, register_lead,
                    row_of, session_run, state)
import gate_lock
import records


def test_register_writes_the_session_id_role_and_since(tmp_path):
    """E1: `mkway lead register` in a session writes `{session_id, role: lead, since}` to `<state>/leads.json`; the id
    is the hook's, and a second run changes nothing. Catches: a lead written under a name, or twice."""
    root = lead_root(tmp_path)
    code, out, err = session_run(root, "lead-a", "lead", "register")
    assert code == 0, err
    (row,) = leads_data(root)["leads"]
    assert set(row) == {"session_id", "role", "since"}
    assert row["session_id"] == "lead-a" and row["role"] == "lead" and row["since"]
    assert session_run(root, "lead-a", "lead", "register")[0] == 0
    assert len(leads_data(root)["leads"]) == 1
    assert any(r.get("kind") == "lead" and r.get("session_id") == "lead-a" for r in records.rows(state(root)))


def test_register_needs_a_session_and_the_hook_check(tmp_path):
    """E1: with no hook check (no permit naming the session) the CLI refuses `lead-no-session` and writes nothing; the
    owner's terminal is refused `lead-session-only`; both texts name the command that fixes it."""
    root = lead_root(tmp_path)
    code, _out, err = cli(root, "lead", "register", session=True)
    assert code != 0 and reason_of(err) == "lead-no-session" and "mkway lead add" in err
    code, _out, err = cli(root, "lead", "register")
    assert code != 0 and reason_of(err) == "lead-session-only" and "mkway lead add" in err
    assert not leads_file(root).exists()


def test_the_owner_adds_and_removes_a_lead_by_prefix(tmp_path):
    """E2: the owner's `lead add <id-prefix>` names a session id seen in the state records and writes it as a lead;
    `lead remove <id-prefix>` names a registered lead. An unknown or ambiguous prefix is `lead-unknown` or
    `lead-ambiguous`, each text naming the command that lists the ids."""
    root = lead_root(tmp_path)
    for sid in ("abcd-1111", "abcd-2222", "wxyz-3333"):
        records.append(state(root), sid, "take", "CARD-001")
    code, _out, err = cli(root, "lead", "add", "abcd")
    assert code != 0 and reason_of(err) == "lead-ambiguous" and "abcd-1111" in err and "abcd-2222" in err
    code, _out, err = cli(root, "lead", "add", "nope")
    assert code != 0 and reason_of(err) == "lead-unknown" and "mkway sessions" in err
    assert cli(root, "lead", "add", "wxyz")[0] == 0
    assert [r["session_id"] for r in leads_data(root)["leads"]] == ["wxyz-3333"]
    code, _out, err = cli(root, "lead", "remove", "abcd")
    assert code != 0 and reason_of(err) == "lead-unknown" and "mkway leads" in err
    assert cli(root, "lead", "remove", "wxyz-3")[0] == 0
    assert leads_data(root)["leads"] == []


def test_add_and_remove_are_owner_only(tmp_path):
    """E2: a session's `lead add` and `lead remove` are refused by the CLI and by the lock gate (`owner-only-command`);
    `lead register` is not an owner command. Catches: a lead that makes itself or another session a lead."""
    root = lead_root(tmp_path)
    records.append(state(root), "s-9", "take", "CARD-001")
    for sub in ("add", "remove"):
        code, _out, err = cli(root, "lead", sub, "s-9", session=True)
        assert code != 0 and reason_of(err) == "owner-only-command", sub
        verdict = gate_call(gate_lock.check, root, tool="Bash", session="lead-a",
                            tool_input={"command": f"python mkway/engine/mkway.py lead {sub} s-9"})
        assert verdict.kind == "refuse" and verdict.reason_id == "owner-only-command", sub
    assert not leads_file(root).exists()
    ok = gate_call(gate_lock.check, root, tool="Bash", session="lead-a",
                   tool_input={"command": "python mkway/engine/mkway.py lead register"})
    assert ok.kind == "allow"


def test_a_lead_gives_a_card_it_ordered_and_it_waits_for_the_accept(tmp_path):
    """E3 and E4: a lead's `give <card> <id-prefix>` of a card it ordered, to another registered lead, changes nothing
    in the register; `lead accept <card>` by the new lead makes it the orderer and clears the hand-off. Catches: a card
    that changes hands without the new lead's word."""
    root = lead_root(tmp_path)
    register_lead(root, "lead-a")
    register_lead(root, "lead-b")
    card = new_card(root, "lead-a")
    assert row_of(root, card)["ordered"] == "lead-a"
    code, out, err = session_run(root, "lead-a", "give", card, "lead-b")
    assert code == 0, err
    assert row_of(root, card)["ordered"] == "lead-a"
    (hand,) = leads_data(root)["handoffs"]
    assert (hand["card"], hand["from"], hand["to"]) == (card, "lead-a", "lead-b") and hand["ts"]
    code, out, err = session_run(root, "lead-b", "lead", "accept", card)
    assert code == 0, err
    assert row_of(root, card)["ordered"] == "lead-b" and leads_data(root)["handoffs"] == []


def test_a_lead_give_refusals_name_the_fix(tmp_path):
    """E3: a session that is no lead is refused `owner-only-command` by the gate; a lead's give of a card it did not
    order is `lead-give-not-yours` (the text names the owner's `mkway give`); to a session that is no lead
    `lead-give-not-lead` (names `mkway lead add`); to itself `lead-give-self`; of an unknown card `card-unknown`."""
    root = lead_root(tmp_path)
    register_lead(root, "lead-a")
    register_lead(root, "lead-b")
    mine = new_card(root, "lead-a")
    other = new_card(root, "builder-1", "Other")
    code, _out, err = session_run(root, "builder-1", "give", mine, "lead-b")
    assert code is None and err.startswith("owner-only-command:")
    code, _out, err = session_run(root, "lead-a", "give", other, "lead-b")
    assert code != 0 and reason_of(err) == "lead-give-not-yours" and f"mkway give {other}" in err
    records.append(state(root), "builder-1", "take", other)
    code, _out, err = session_run(root, "lead-a", "give", mine, "builder-1")
    assert code != 0 and reason_of(err) == "lead-give-not-lead" and "mkway lead add" in err
    code, _out, err = session_run(root, "lead-a", "give", mine, "lead-a")
    assert code != 0 and reason_of(err) == "lead-give-self"
    code, _out, err = session_run(root, "lead-a", "give", "CARD-099", "lead-b")
    assert code != 0 and reason_of(err) == "card-unknown"
    assert leads_data(root).get("handoffs", []) == []


def test_the_accept_refusals_name_the_fix(tmp_path):
    """E4: `lead accept` with no hand-off to this session is `lead-accept-none` (names `mkway give <card>`); a
    hand-off whose orderer changed since is `lead-accept-stale` and is dropped; a session that is no lead is
    `lead-not-registered` (names `mkway lead register`)."""
    root = lead_root(tmp_path)
    for lead in ("lead-a", "lead-b", "lead-c"):
        register_lead(root, lead)
    card = new_card(root, "lead-a")
    code, _out, err = session_run(root, "lead-b", "lead", "accept", card)
    assert code != 0 and reason_of(err) == "lead-accept-none" and f"mkway give {card}" in err
    assert session_run(root, "lead-a", "give", card, "lead-b")[0] == 0
    code, _out, err = session_run(root, "lead-c", "lead", "accept", card)
    assert code != 0 and reason_of(err) == "lead-accept-none"
    records.append(state(root), "lead-c", "take", "CARD-050")  # the owner's give below names an id seen in the records
    assert cli(root, "give", card, "lead-c")[0] == 0  # the owner's give needs no accept
    code, _out, err = session_run(root, "lead-b", "lead", "accept", card)
    assert code != 0 and reason_of(err) == "lead-accept-stale"
    assert row_of(root, card)["ordered"] == "lead-c" and leads_data(root)["handoffs"] == []
    code, _out, err = session_run(root, "builder-2", "lead", "accept", card)
    assert code != 0 and reason_of(err) == "lead-not-registered" and "mkway lead register" in err


def test_the_owners_give_is_unchanged(tmp_path):
    """E3: the owner's terminal `give` still sets the orderer at once and a session that is no lead is still refused
    by the CLI itself (a tripwire, as before)."""
    root = lead_root(tmp_path)
    card = new_card(root, "builder-1")
    records.append(state(root), "lead-z", "take", "CARD-077")
    assert cli(root, "give", card, "lead-z")[0] == 0
    assert row_of(root, card)["ordered"] == "lead-z"
    code, _out, err = cli(root, "give", card, "owner", session=True)
    assert code != 0 and reason_of(err) in ("owner-only-command", "lead-no-session", "lead-not-registered")
    assert row_of(root, card)["ordered"] == "lead-z"
    assert inbox(root, "lead-z") == []
