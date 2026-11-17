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


def _owner_only(root, sub):
    """A session's `lead add` or `lead remove` is refused by the CLI and by the lock gate (helper, one subcommand)."""
    code, _out, err = cli(root, "lead", sub, "s-9", session=True)
    assert code != 0
    assert reason_of(err) == "owner-only-command"
    verdict = gate_call(gate_lock.check, root, tool="Bash", session="lead-a",
                        tool_input={"command": f"python mkway/engine/mkway.py lead {sub} s-9"})
    assert verdict.kind == "refuse"
    assert verdict.reason_id == "owner-only-command"


def test_register_writes_the_session_id_role_and_since(tmp_path):
    """Checks: mkway lead register in a session writes session_id, role lead and since to leads.json, the id is the hook's, and a second run changes nothing (E1)."""
    root = lead_root(tmp_path)
    code, out, err = session_run(root, "lead-a", "lead", "register")
    assert code == 0, err
    (row,) = leads_data(root)["leads"]
    assert set(row) == {"session_id", "role", "since"}
    assert row["session_id"] == "lead-a"
    assert row["role"] == "lead"
    assert row["since"]
    assert session_run(root, "lead-a", "lead", "register")[0] == 0
    assert len(leads_data(root)["leads"]) == 1
    assert any(r.get("kind") == "lead" and r.get("session_id") == "lead-a" for r in records.rows(state(root)))


def test_register_needs_a_session_and_the_hook_check(tmp_path):
    """Catches: a lead written with no hook check, or a refusal that does not name the fix (E1: with no hook check the CLI refuses lead-no-session and writes nothing; the owner's terminal is refused lead-session-only; both texts name the command that fixes it)."""
    root = lead_root(tmp_path)
    code, _out, err = cli(root, "lead", "register", session=True)
    assert code != 0
    assert reason_of(err) == "lead-no-session"
    assert "mkway lead add" in err
    code, _out, err = cli(root, "lead", "register")
    assert code != 0
    assert reason_of(err) == "lead-session-only"
    assert "mkway lead add" in err
    assert not leads_file(root).exists()


def test_the_owner_adds_and_removes_a_lead_by_prefix(tmp_path):
    """Catches: an ambiguous or unknown prefix that is taken as a lead, or a refusal with no list command named (E2: the owner's lead add by id prefix names a session id seen in the state records; lead remove names a registered lead; an unknown or ambiguous prefix is lead-unknown or lead-ambiguous, each text naming the command that lists the ids)."""
    root = lead_root(tmp_path)
    records.append(state(root), "abcd-1111", "take", "CARD-001")
    records.append(state(root), "abcd-2222", "take", "CARD-001")
    records.append(state(root), "wxyz-3333", "take", "CARD-001")
    code, _out, err = cli(root, "lead", "add", "abcd")
    assert code != 0
    assert reason_of(err) == "lead-ambiguous"
    assert "abcd-1111" in err
    assert "abcd-2222" in err
    code, _out, err = cli(root, "lead", "add", "nope")
    assert code != 0
    assert reason_of(err) == "lead-unknown"
    assert "mkway sessions" in err
    assert cli(root, "lead", "add", "wxyz")[0] == 0
    assert [r["session_id"] for r in leads_data(root)["leads"]] == ["wxyz-3333"]
    code, _out, err = cli(root, "lead", "remove", "abcd")
    assert code != 0
    assert reason_of(err) == "lead-unknown"
    assert "mkway leads" in err
    assert cli(root, "lead", "remove", "wxyz-3")[0] == 0
    assert leads_data(root)["leads"] == []


def test_add_and_remove_are_owner_only(tmp_path):
    """Catches: a lead that makes itself or another session a lead (E2: a session's lead add and lead remove are refused by the CLI and by the lock gate with owner-only-command; lead register is not an owner command)."""
    root = lead_root(tmp_path)
    records.append(state(root), "s-9", "take", "CARD-001")
    _owner_only(root, "add")
    _owner_only(root, "remove")
    assert not leads_file(root).exists()
    ok = gate_call(gate_lock.check, root, tool="Bash", session="lead-a",
                   tool_input={"command": "python mkway/engine/mkway.py lead register"})
    assert ok.kind == "allow"


def test_a_lead_gives_a_card_it_ordered_and_it_waits_for_the_accept(tmp_path):
    """Checks: a lead's give of a card it ordered, to another registered lead, changes nothing in the register, and lead accept by the new lead makes it the orderer and clears the hand-off (E3 and E4)."""
    root = lead_root(tmp_path)
    register_lead(root, "lead-a")
    register_lead(root, "lead-b")
    card = new_card(root, "lead-a")
    assert row_of(root, card)["ordered"] == "lead-a"
    code, out, err = session_run(root, "lead-a", "give", card, "lead-b")
    assert code == 0, err
    assert row_of(root, card)["ordered"] == "lead-a"
    (hand,) = leads_data(root)["handoffs"]
    assert (hand["card"], hand["from"], hand["to"]) == (card, "lead-a", "lead-b")
    assert hand["ts"]
    code, out, err = session_run(root, "lead-b", "lead", "accept", card)
    assert code == 0, err
    assert row_of(root, card)["ordered"] == "lead-b"
    assert leads_data(root)["handoffs"] == []


def test_a_lead_give_refusals_name_the_fix(tmp_path):
    """Catches: a card that changes hands without the new lead's word, or a refusal that does not name the fix (E3: a session that is no lead is refused owner-only-command by the gate; a give of a card the lead did not order is lead-give-not-yours, naming the owner's mkway give; to a session that is no lead lead-give-not-lead, naming mkway lead add; to itself lead-give-self; of an unknown card card-unknown)."""
    root = lead_root(tmp_path)
    register_lead(root, "lead-a")
    register_lead(root, "lead-b")
    mine = new_card(root, "lead-a")
    other = new_card(root, "builder-1", "Other")
    code, _out, err = session_run(root, "builder-1", "give", mine, "lead-b")
    assert code is None
    assert err.startswith("owner-only-command:")
    code, _out, err = session_run(root, "lead-a", "give", other, "lead-b")
    assert code != 0
    assert reason_of(err) == "lead-give-not-yours"
    assert f"mkway give {other}" in err
    records.append(state(root), "builder-1", "take", other)
    code, _out, err = session_run(root, "lead-a", "give", mine, "builder-1")
    assert code != 0
    assert reason_of(err) == "lead-give-not-lead"
    assert "mkway lead add" in err
    code, _out, err = session_run(root, "lead-a", "give", mine, "lead-a")
    assert code != 0
    assert reason_of(err) == "lead-give-self"
    code, _out, err = session_run(root, "lead-a", "give", "CARD-099", "lead-b")
    assert code != 0
    assert reason_of(err) == "card-unknown"
    assert leads_data(root).get("handoffs", []) == []


def test_the_accept_refusals_name_the_fix(tmp_path):
    """Catches: a hand-off accepted by a session it was not given to, or a refusal that does not name the fix (E4: lead accept with no hand-off to this session is lead-accept-none, naming mkway give; a hand-off whose orderer changed since is lead-accept-stale and is dropped; a session that is no lead is lead-not-registered, naming mkway lead register)."""
    root = lead_root(tmp_path)
    register_lead(root, "lead-a")
    register_lead(root, "lead-b")
    register_lead(root, "lead-c")
    card = new_card(root, "lead-a")
    code, _out, err = session_run(root, "lead-b", "lead", "accept", card)
    assert code != 0
    assert reason_of(err) == "lead-accept-none"
    assert f"mkway give {card}" in err
    assert session_run(root, "lead-a", "give", card, "lead-b")[0] == 0
    code, _out, err = session_run(root, "lead-c", "lead", "accept", card)
    assert code != 0
    assert reason_of(err) == "lead-accept-none"
    records.append(state(root), "lead-c", "take", "CARD-050")  # the owner's give below names an id seen in the records
    assert cli(root, "give", card, "lead-c")[0] == 0  # the owner's give needs no accept
    code, _out, err = session_run(root, "lead-b", "lead", "accept", card)
    assert code != 0
    assert reason_of(err) == "lead-accept-stale"
    assert row_of(root, card)["ordered"] == "lead-c"
    assert leads_data(root)["handoffs"] == []
    code, _out, err = session_run(root, "builder-2", "lead", "accept", card)
    assert code != 0
    assert reason_of(err) == "lead-not-registered"
    assert "mkway lead register" in err


def test_the_owners_give_is_unchanged(tmp_path):
    """Checks: the owner's terminal give still sets the orderer at once (E3), and a session that is no lead is still refused by the CLI itself, a tripwire as before."""
    root = lead_root(tmp_path)
    card = new_card(root, "builder-1")
    records.append(state(root), "lead-z", "take", "CARD-077")
    assert cli(root, "give", card, "lead-z")[0] == 0
    assert row_of(root, card)["ordered"] == "lead-z"
    code, _out, err = cli(root, "give", card, "owner", session=True)
    assert code != 0
    assert reason_of(err) in ("owner-only-command", "lead-no-session", "lead-not-registered")
    assert row_of(root, card)["ordered"] == "lead-z"
    assert inbox(root, "lead-z") == []
