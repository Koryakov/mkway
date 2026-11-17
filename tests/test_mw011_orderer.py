"""Card MW-011, part 1: who ordered a card. The register's `Ordered by` column, `card new` in a session, the owner's
`mkway give` and the owner's view `mkway sessions`. Synthetic task roots and synthetic hook payloads only.

A session never knows its own id: the id comes from the hook input, so the `post` group writes it into the register
cell after a `card new` that proved itself with a nonce. A missing or blank cell reads `owner`.
"""
import json
import re

import pytest

from _engine import cli, gate_call, jsonl, task_root
import agents
import dispatch
import gate_lock
import gate_records
import records
import register

NE = "not established"
HEADER6 = "| Id | Title | Status | Paths | Folder | Ordered by |"
OLD_REGISTER = ("# Card register\n\n| Id | Title | Status | Paths | Folder |\n|---|---|---|---|---|\n"
                "| CARD-001 | Old | open | | `mkway/cards/CARD-001-old` |\n")


def _task(tmp_path, **over):
    return task_root(tmp_path, cards={"approver": "orderer"}, **over)


def _profile(root):
    return json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))


def _state(root):
    return root / "mkway" / "state"


def _reg(root):
    return root / "mkway" / "cards" / "REGISTER.md"


def _text(root):
    return _reg(root).read_bytes().decode("utf-8")


def _row(root, card_id):
    return register.find(register.read(root, _profile(root)), card_id)


def _session_new(root, title, session):
    """A session's `card new` and the `post` group's record step that carries the hook input's session id."""
    code, out, err = cli(root, "card", "new", title, session=True)
    assert code == 0, err
    gate_call(gate_records.record, root, tool="Bash", tool_response={"stdout": out}, session=session,
              event="PostToolUse")
    return out


def _reason(err):
    m = re.search(r"mkway: ([a-z-]+):", err)
    return m.group(1) if m else None


def test_ordered_by_column_is_sealed_and_read(tmp_path):
    """Catches: a column outside the seal that a session edits to name itself the orderer (E1, rule 1)."""
    # with cards.approver orderer a new register has the sixth column Ordered by; a card made in the owner's terminal
    # reads owner; the column is inside the seal, so a hand edit of a cell is register-tampered
    root = _task(tmp_path)
    assert cli(root, "card", "new", "First")[0] == 0
    assert HEADER6 in _text(root)
    assert _row(root, "CARD-001")["ordered"] == "owner"
    _reg(root).write_bytes(_text(root).replace("| owner |", "| s9 |").encode("utf-8"))
    with pytest.raises(register.RegisterError) as caught:
        register.check(root, _profile(root))
    assert caught.value.reason == "register-tampered"
    code, _out, err = cli(root, "card", "new", "Second")
    assert code != 0
    assert _reason(err) == "register-tampered"


def test_the_sixth_column_name_comes_from_the_profile(tmp_path):
    """Checks: register.columns may hold a sixth name, and a register written for it has all six (E2, rule 1)."""
    # the default is Ordered by; Catches: a literal column name in the engine
    root = task_root(tmp_path, register={"columns": ["Key", "Name", "State", "Scope", "Where", "Sent by"]})
    assert cli(root, "card", "new", "First")[0] == 0
    assert "| Key | Name | State | Scope | Where | Sent by |" in _text(root)
    assert _row(root, "CARD-001")["ordered"] == "owner"
    assert register.find(register.read(root, _profile(root)), "CARD-001")["status"] == "proposed"


def test_a_register_without_the_column_reads_owner_and_resync_adds_it(tmp_path):
    """Catches: a silent migration, a session that adds the column, or a seal left behind (E3, rule 1)."""
    # an existing register without the column reads every card as owner and is not migrated by a write; only the
    # owner's card resync --add-ordered-by adds the column (then every row says owner) and reseals
    root = _task(tmp_path)
    _reg(root).write_bytes(OLD_REGISTER.encode("utf-8"))
    register.reseal(root, _profile(root))
    assert _row(root, "CARD-001")["ordered"] == "owner"
    _session_new(root, "Second", "s-one")
    assert "Ordered by" not in _text(root)
    assert _row(root, "CARD-002")["ordered"] == "owner"
    assert cli(root, "card", "resync")[0] == 0
    assert "Ordered by" not in _text(root)
    code, _out, err = cli(root, "card", "resync", "--add-ordered-by", session=True)
    assert code != 0
    assert _reason(err) == "owner-only-command"
    code, out, err = cli(root, "card", "resync", "--add-ordered-by")
    assert code == 0, err
    assert HEADER6 in _text(root)
    assert [r["ordered"] for r in register.read(root, _profile(root))] == ["owner", "owner"]
    assert register.seal_problem(root, _profile(root)) is None
    assert cli(root, "card", "new", "Third")[0] == 0
    assert _row(root, "CARD-003")["ordered"] == "owner"


def test_card_new_writes_the_session_id_or_owner(tmp_path):
    """Checks: card new writes the session id the hook gives, or owner, and a card the post group never saw stays owner (E4, rule 1)."""
    # the nonce proves the command ran; Catches: an id the session names itself, or a cell left empty
    root = _task(tmp_path)
    _session_new(root, "By a session", "s-one")
    assert cli(root, "card", "new", "By the owner")[0] == 0
    code, out, err = cli(root, "card", "new", "Unseen", session=True)
    assert code == 0, err
    assert [r["ordered"] for r in register.read(root, _profile(root))] == ["s-one", "owner", "owner"]
    assert register.seal_problem(root, _profile(root)) is None
    assert "s-one" not in (root / "mkway" / "cards" / "CARD-001-by-a-session" / "CARD.md").read_text(encoding="utf-8")


def _post(root, out, **fields):
    payload = {"session_id": "s-sub", "hook_event_name": "PostToolUse", "tool_name": "Bash", "cwd": str(root),
               "tool_input": {"command": "python mkway/engine/mkway.py card new X"},
               "tool_response": {"stdout": out}}
    payload.update(fields)
    payload = {k: v for k, v in payload.items() if v is not None}
    return dispatch.run("PostToolUse", "post", json.dumps(payload), env={"CLAUDE_PROJECT_DIR": str(root)})


def test_a_sub_agent_is_its_session_id_as_the_hook_input_gives_it(tmp_path):
    """Checks: a sub-agent card new writes the hook's session id, not the agent id, and no session id reads owner (E5, rule 6)."""
    # Catches: an agent id taken for a session, or an id guessed where the payload does not say
    root = _task(tmp_path)
    code, out, err = cli(root, "card", "new", "By an agent", session=True)
    assert code == 0, err
    result = _post(root, out, agent_id="a-17", agent_type="worker")
    assert result.exit_code == 0, result.stderr
    assert _row(root, "CARD-001")["ordered"] == "s-sub"
    code, out, err = cli(root, "card", "new", "No id", session=True)
    assert code == 0, err
    assert _post(root, out, session_id=None, agent_id="a-18").exit_code == 0
    assert _row(root, "CARD-002")["ordered"] == "owner"


def _seen(root, *ids):
    for sid in ids:
        records.append(_state(root), sid, "search", "x")


def test_give_sets_the_cell_by_a_prefix_a_bare_number_or_owner(tmp_path):
    """Checks: give sets Ordered by to the one id a prefix names, a bare number uses the card prefix, owner takes it back (E6, rule 2)."""
    # each give is the owner's record; Catches: a give that stores the prefix, or a bare number read as another card
    root = _task(tmp_path)
    assert cli(root, "card", "new", "First")[0] == 0
    _seen(root, "s-aaa1", "s-bbb2")
    code, out, err = cli(root, "give", "CARD-001", "s-aa")
    assert code == 0, err
    assert _row(root, "CARD-001")["ordered"] == "s-aaa1"
    assert register.seal_problem(root, _profile(root)) is None
    assert cli(root, "give", "1", "owner")[0] == 0
    assert _row(root, "CARD-001")["ordered"] == "owner"
    assert cli(root, "give", "001", "s-bbb2")[0] == 0
    assert _row(root, "CARD-001")["ordered"] == "s-bbb2"
    assert records.rows(_state(root))[-1] == dict(records.rows(_state(root))[-1], kind="give", by="owner")


def test_give_refuses_an_ambiguous_or_unknown_prefix_and_names_the_candidates(tmp_path):
    """Catches: a give to the first match of an ambiguous prefix, or a candidate the payload did not state (E7, rule 2)."""
    # an ambiguous prefix is give-ambiguous and names every candidate, an unknown one give-unknown; an id the payload did
    # not state (not established) is never a candidate; the register is unchanged
    root = _task(tmp_path)
    assert cli(root, "card", "new", "First")[0] == 0
    _seen(root, "s-aaa1", "s-aaa2", "s-bbb2")
    agents.record_start(_state(root), {"agent_id": "a9"})  # no session id in the payload: «not established»
    before = _text(root)
    code, _out, err = cli(root, "give", "CARD-001", "s-aaa")
    assert code != 0
    assert _reason(err) == "give-ambiguous"
    assert "s-aaa1" in err
    assert "s-aaa2" in err
    assert "s-bbb2" not in err
    results = [(who, cli(root, "give", "CARD-001", who)) for who in ("s-zzz", "not")]
    unknown = [who for who, (code, _out, err) in results if code == 0 or _reason(err) != "give-unknown"]
    assert not unknown, unknown
    assert cli(root, "give", "CARD-001", "s-aaa1")[0] == 0  # the whole id is one match
    code, _out, err = cli(root, "give", "CARD-404", "s-bbb")
    assert code != 0
    assert _reason(err) == "card-unknown"
    assert _text(root) != before
    assert _row(root, "CARD-001")["ordered"] == "s-aaa1"


def test_give_is_the_owners_command(tmp_path):
    """Catches: a session that gives itself a card, through the lock gate or the CLI tripwire in any spelling (E8, rule 2)."""
    # the register is unchanged after every refused spelling
    root = _task(tmp_path)
    assert cli(root, "card", "new", "First")[0] == 0
    _seen(root, "s-aaa1")
    before = _text(root)
    code, _out, err = cli(root, "give", "CARD-001", "s-aaa1", session=True)
    assert code != 0
    assert _reason(err) == "owner-only-command"
    commands = ("python mkway/engine/mkway.py give CARD-001 s-aaa1", "python mkway/engine/mkway.py give 1 s-aaa1",
                "py -3 mkway/engine/mkway.py give CARD-001 s-aaa1",
                "cd mkway/engine && python mkway.py give CARD-001 s-aaa1")
    verdicts = [(command, gate_call(gate_lock.check, root, tool="Bash", tool_input={"command": command},
                                    session="s-aaa1")) for command in commands]
    not_refused = [command for command, v in verdicts
                   if v.kind != "refuse" or v.reason_id != "owner-only-command"]
    assert not not_refused, not_refused
    assert _text(root) == before


def test_give_needs_the_column(tmp_path):
    """Catches: a give that migrates silently in a register with no Ordered by column (E9, rule 1 and rule 2)."""
    # the give is refused give-no-column and names the owner's way out, card resync --add-ordered-by; nothing is written
    root = _task(tmp_path)
    _reg(root).write_bytes(OLD_REGISTER.encode("utf-8"))
    register.reseal(root, _profile(root))
    _seen(root, "s-aaa1")
    before = _text(root)
    code, _out, err = cli(root, "give", "CARD-001", "s-aaa1")
    assert code != 0
    assert _reason(err) == "give-no-column"
    assert "--add-ordered-by" in err
    assert _text(root) == before


def test_sessions_lists_ids_with_cards_held_and_ordered(tmp_path):
    """Checks: sessions prints each session id seen in the state records with its card held and ordered, and writes nothing (E10, rule 3)."""
    # rows with no session id are counted as not established, never listed as a session; Catches: a view that guesses
    # chat names, or one that writes
    root = _task(tmp_path)
    codes = [cli(root, "card", "new", title)[0] for title in ("First", "Second")]
    assert codes == [0, 0]
    state = _state(root)
    records.append(state, "s-aaa1", "take", "CARD-001")
    records.append(state, "s-bbb2", "search", "x")
    agents.record_start(state, {"session_id": "s-ccc3", "agent_id": "a1", "agent_type": "worker"})
    agents.record_start(state, {"agent_id": "a2"})
    _seen(root, "s-bbb2")
    assert cli(root, "give", "CARD-002", "s-bbb2")[0] == 0
    before, rows_before = _text(root), records.rows(state)
    code, out, err = cli(root, "sessions", session=True)
    assert code == 0, err
    lines = {ln.split()[0]: ln for ln in out.splitlines() if ln.startswith("s-")}
    assert sorted(lines) == ["s-aaa1", "s-bbb2", "s-ccc3"]
    unstamped = [line for line in lines.values() if not re.search(r"last seen \d{4}-\d{2}-\d{2}T", line)]
    assert not unstamped, unstamped
    assert "holds CARD-001" in lines["s-aaa1"]
    assert "ordered none" in lines["s-aaa1"]
    assert "holds none" in lines["s-bbb2"]
    assert "ordered CARD-002" in lines["s-bbb2"]
    assert "holds none" in lines["s-ccc3"]
    assert NE in out
    assert "1 row" in out
    assert _text(root) == before
    assert records.rows(state) == rows_before
    assert jsonl(state / "agents.jsonl")[-1]["session_id"] == NE
