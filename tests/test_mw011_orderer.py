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
    """E1 (rule 1): with `cards.approver: orderer` a new register has the sixth column `Ordered by`; a card made in the
    owner's terminal reads `owner`; the column is inside the seal, so a hand edit of a cell is `register-tampered`.
    Catches: a column outside the seal that a session edits to name itself the orderer."""
    root = _task(tmp_path)
    assert cli(root, "card", "new", "First")[0] == 0
    assert HEADER6 in _text(root)
    assert _row(root, "CARD-001")["ordered"] == "owner"
    _reg(root).write_bytes(_text(root).replace("| owner |", "| s9 |").encode("utf-8"))
    with pytest.raises(register.RegisterError) as caught:
        register.check(root, _profile(root))
    assert caught.value.reason == "register-tampered"
    code, _out, err = cli(root, "card", "new", "Second")
    assert code != 0 and _reason(err) == "register-tampered"


def test_the_sixth_column_name_comes_from_the_profile(tmp_path):
    """E2 (rule 1): `register.columns` may hold a sixth name (the default is `Ordered by`), and a register written for
    a profile that names six columns has all six. Catches: a literal column name in the engine."""
    root = task_root(tmp_path, register={"columns": ["Key", "Name", "State", "Scope", "Where", "Sent by"]})
    assert cli(root, "card", "new", "First")[0] == 0
    assert "| Key | Name | State | Scope | Where | Sent by |" in _text(root)
    assert _row(root, "CARD-001")["ordered"] == "owner"
    assert register.find(register.read(root, _profile(root)), "CARD-001")["status"] == "proposed"


def test_a_register_without_the_column_reads_owner_and_resync_adds_it(tmp_path):
    """E3 (rule 1): an existing register without the column reads every card as `owner` and is not migrated by a
    write; only the owner's `card resync --add-ordered-by` adds the column (then every row says `owner`) and reseals.
    Catches: a silent migration, a session that adds the column, or a seal left behind."""
    root = _task(tmp_path)
    _reg(root).write_bytes(OLD_REGISTER.encode("utf-8"))
    register.reseal(root, _profile(root))
    assert _row(root, "CARD-001")["ordered"] == "owner"
    _session_new(root, "Second", "s-one")
    assert "Ordered by" not in _text(root) and _row(root, "CARD-002")["ordered"] == "owner"
    assert cli(root, "card", "resync")[0] == 0
    assert "Ordered by" not in _text(root)
    code, _out, err = cli(root, "card", "resync", "--add-ordered-by", session=True)
    assert code != 0 and _reason(err) == "owner-only-command"
    code, out, err = cli(root, "card", "resync", "--add-ordered-by")
    assert code == 0, err
    assert HEADER6 in _text(root)
    assert [r["ordered"] for r in register.read(root, _profile(root))] == ["owner", "owner"]
    assert register.seal_problem(root, _profile(root)) is None
    assert cli(root, "card", "new", "Third")[0] == 0 and _row(root, "CARD-003")["ordered"] == "owner"


def test_card_new_writes_the_session_id_or_owner(tmp_path):
    """E4 (rule 1): `card new` run in a session writes the session id the hook input gives, through the `post` group
    (the nonce proves the command ran); run in the owner's terminal it writes `owner`; a session's `card new` the
    `post` group never saw stays `owner`. Catches: an id the session names itself, or a cell left empty."""
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
    """E5 (rule 6): a sub-agent's `card new` carries the hook input's `session_id` beside its `agent_id`: that session
    id is the one written, the agent id is not; a payload with no `session_id` writes no id, the card reads `owner`.
    Catches: an agent id taken for a session, or an id guessed where the payload does not say."""
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
    """E6 (rule 2): `mkway give <card id or bare number> <prefix or owner>` sets `Ordered by` to the one id seen in the
    state records that the prefix names; the bare number uses the profile's card prefix; `owner` takes the card back;
    each give is the owner's record. Catches: a give that stores the prefix, or a bare number read as another card."""
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
    """E7 (rule 2): a prefix must match exactly one id seen in the state records; an ambiguous one is `give-ambiguous`
    and names every candidate, an unknown one `give-unknown`; an id the payload did not state («not established») is
    never a candidate; the register is unchanged. Catches: a give to the first match."""
    root = _task(tmp_path)
    assert cli(root, "card", "new", "First")[0] == 0
    _seen(root, "s-aaa1", "s-aaa2", "s-bbb2")
    agents.record_start(_state(root), {"agent_id": "a9"})  # no session id in the payload: «not established»
    before = _text(root)
    code, _out, err = cli(root, "give", "CARD-001", "s-aaa")
    assert code != 0 and _reason(err) == "give-ambiguous" and "s-aaa1" in err and "s-aaa2" in err
    assert "s-bbb2" not in err
    for who in ("s-zzz", "not"):
        code, _out, err = cli(root, "give", "CARD-001", who)
        assert code != 0 and _reason(err) == "give-unknown", who
    assert cli(root, "give", "CARD-001", "s-aaa1")[0] == 0  # the whole id is one match
    code, _out, err = cli(root, "give", "CARD-404", "s-bbb")
    assert code != 0 and _reason(err) == "card-unknown"
    assert _text(root) != before and _row(root, "CARD-001")["ordered"] == "s-aaa1"


def test_give_is_the_owners_command(tmp_path):
    """E8 (rule 2): a session's `give` is refused by the lock gate (`owner-only-command`) and by the CLI itself when
    `CLAUDECODE` is set (the tripwire), in any spelling; the register is unchanged. Catches: a session that gives
    itself a card."""
    root = _task(tmp_path)
    assert cli(root, "card", "new", "First")[0] == 0
    _seen(root, "s-aaa1")
    before = _text(root)
    code, _out, err = cli(root, "give", "CARD-001", "s-aaa1", session=True)
    assert code != 0 and _reason(err) == "owner-only-command"
    for command in ("python mkway/engine/mkway.py give CARD-001 s-aaa1", "python mkway/engine/mkway.py give 1 s-aaa1",
                    "py -3 mkway/engine/mkway.py give CARD-001 s-aaa1",
                    "cd mkway/engine && python mkway.py give CARD-001 s-aaa1"):
        v = gate_call(gate_lock.check, root, tool="Bash", tool_input={"command": command}, session="s-aaa1")
        assert v.kind == "refuse" and v.reason_id == "owner-only-command", command
    assert _text(root) == before


def test_give_needs_the_column(tmp_path):
    """E9 (rule 1, rule 2): in a register with no `Ordered by` column a give is refused `give-no-column` and names the
    owner's way out (`card resync --add-ordered-by`); nothing is written. Catches: a give that migrates silently."""
    root = _task(tmp_path)
    _reg(root).write_bytes(OLD_REGISTER.encode("utf-8"))
    register.reseal(root, _profile(root))
    _seen(root, "s-aaa1")
    before = _text(root)
    code, _out, err = cli(root, "give", "CARD-001", "s-aaa1")
    assert code != 0 and _reason(err) == "give-no-column" and "--add-ordered-by" in err
    assert _text(root) == before


def test_sessions_lists_ids_with_cards_held_and_ordered(tmp_path):
    """E10 (rule 3): `mkway sessions` prints, for every session id seen in the state records (shell records, agents,
    searches): the last-seen time, the card it holds and the cards it ordered; it writes nothing and runs in a session
    too; rows with no session id are counted as «not established», never listed as a session. Catches: a view that
    guesses chat names, or one that writes."""
    root = _task(tmp_path)
    for title in ("First", "Second"):
        assert cli(root, "card", "new", title)[0] == 0
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
    for line in lines.values():
        assert re.search(r"last seen \d{4}-\d{2}-\d{2}T", line), line
    assert "holds CARD-001" in lines["s-aaa1"] and "ordered none" in lines["s-aaa1"]
    assert "holds none" in lines["s-bbb2"] and "ordered CARD-002" in lines["s-bbb2"]
    assert "holds none" in lines["s-ccc3"]
    assert NE in out and "1 row" in out
    assert _text(root) == before and records.rows(state) == rows_before
    assert jsonl(state / "agents.jsonl")[-1]["session_id"] == NE
