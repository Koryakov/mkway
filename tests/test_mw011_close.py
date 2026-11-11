"""Card MW-011, part 2: `card close` by the session that ordered the card (`cards.approver: orderer`). Synthetic task
roots and synthetic hook payloads only.

A session's close is decided in two places, because only the hook knows the session id: the lock gate (PreToolUse)
checks the orderer and the holder and leaves a one-use permit that names the session; the CLI reads the permit,
checks everything again with that id, runs the tests the Acceptance rows name, and only then closes.
"""
import datetime
import json
import re

import pytest

from _engine import cli, gate_call, jsonl, task_root
import cardtool
import dispatch
import gate_lock
import gate_records
import logs
import records
import register
import startline

ORD, HOLD, THIRD = "s-ord", "s-hold", "s-third"
OK = "tests/test_ok.py::test_ok"
ALSO = "tests/test_ok.py::test_also_ok"
BAD = "tests/test_bad.py::test_bad"
T0 = datetime.datetime(2026, 11, 10, 8, 0, 0, tzinfo=datetime.timezone.utc)


def _profile(root):
    return json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))


def _state(root):
    return root / "mkway" / "state"


def _row(root, card_id="CARD-001"):
    return register.find(register.read(root, _profile(root)), card_id)


def _card_file(root, card_id="CARD-001"):
    (folder,) = [p for p in (root / "mkway" / "cards").iterdir() if p.name.startswith(card_id + "-")]
    return folder / "CARD.md"


def _log(root, card_id="CARD-001"):
    return _card_file(root, card_id).read_text(encoding="utf-8").split("## 8. Log", 1)[1]


def _reason(err):
    m = re.search(r"mkway: ([a-z-]+):", err)
    return m.group(1) if m else None


def _set_paths(root, card_id, value):
    path = _card_file(root, card_id)
    path.write_text(re.sub(r"^\| \*\*Paths\*\* \|.*\|$", f"| **Paths** | {value} |", path.read_text(encoding="utf-8"),
                           flags=re.M), encoding="utf-8")


def _set_tests(root, card_id, cells):
    path = _card_file(root, card_id)
    text = path.read_text(encoding="utf-8")
    head = "| # | Item | Was | Must be | Test |\n|---|---|---|---|---|\n"
    start = text.index(head) + len(head)
    end = text.index("\n\n", start)
    rows = "".join(f"| E{i} | x | a | b | {c} |\n" for i, c in enumerate(cells, 1))
    path.write_text(text[:start] + rows.rstrip("\n") + text[end:], encoding="utf-8")


def _task(tmp_path, approver="orderer", **over):
    cards = dict(over.pop("cards", {}))
    if approver:
        cards["approver"] = approver
    if cards:
        over["cards"] = cards
    root = task_root(tmp_path, test_roots=["tests"], **over)
    (root / "tests").mkdir()
    (root / "tests" / "test_ok.py").write_text("def test_ok():\n    assert True\n\n\ndef test_also_ok():\n"
                                               "    assert 1 + 1 == 2\n", encoding="utf-8")
    (root / "tests" / "test_bad.py").write_text("def test_bad():\n    assert False\n", encoding="utf-8")
    return root


def _ready(tmp_path, cells=(OK, ALSO), creator=ORD, holder=HOLD, opened=True, approver="orderer", **over):
    """CARD-001 with Acceptance rows `cells`, made by session `creator` (None: the owner's terminal), opened by the
    owner, taken by `holder`, and the owner's baseline set."""
    root = _task(tmp_path, approver, **over)
    if creator:
        code, out, err = cli(root, "card", "new", "Work", session=True)
        assert code == 0, err
        gate_call(gate_records.record, root, tool="Bash", tool_response={"stdout": out}, session=creator,
                  event="PostToolUse")
    else:
        assert cli(root, "card", "new", "Work")[0] == 0
    _set_paths(root, "CARD-001", "`src/a.py`")
    _set_tests(root, "CARD-001", list(cells))
    if opened:
        assert cli(root, "card", "open", "CARD-001")[0] == 0
    if holder:
        records.append(_state(root), holder, "take", "CARD-001")
    assert cli(root, "card", "resync")[0] == 0
    return root


def _close(root, session, card="CARD-001", via="close"):
    """The gate first (the hook), then the CLI as the session's shell runs it, then the `post` group: (where it
    stopped or `ok`, reason id, text)."""
    command = f"python mkway/engine/mkway.py card {via} {card}"
    verdict = gate_call(gate_lock.check, root, tool="Bash", tool_input={"command": command}, session=session)
    if verdict.kind == "refuse":
        return "gate", verdict.reason_id, verdict.message
    code, out, err = cli(root, "card", via, card, session=True)
    if code == 0:
        gate_call(gate_records.record, root, tool="Bash", tool_response={"stdout": out}, session=session,
                  event="PostToolUse")
        return "ok", None, out
    return "cli", _reason(err), err


def test_the_orderer_closes_a_card_it_does_not_hold(tmp_path):
    """E11 (rule 4, rule 5): with `cards.approver: orderer` the session that ordered the card closes it when it is not
    the holder, the card is open and every Acceptance row's test passes now; the status is `closed`, the Log gets one
    row «closed by <session id>; ordered by <value>», the close is a session record, and the start block's card
    changes show it (no new line). Catches: a close that needs the owner, or one that leaves no trace."""
    root = _ready(tmp_path)
    how, reason, text = _close(root, ORD)
    assert (how, reason) == ("ok", None), text
    assert _row(root)["status"] == "closed"
    assert re.search(r"^\| \d{4}-\d{2}-\d{2} \| close \| \S+ \| closed by s-ord; ordered by s-ord \|$", _log(root),
                     re.M)
    last = records.rows(_state(root))[-1]
    assert (last["kind"], last["value"], last["session_id"], last["by"]) == ("close", "CARD-001", ORD, "session")
    _status, changes = startline._changes(root, _profile(root))
    assert ("CARD-001", "open", "closed", "close by session") in changes
    assert register.seal_problem(root, _profile(root)) is None


def test_the_holder_never_closes_its_own_work(tmp_path):
    """E12 (rule 4): the closer is not the holder. The orderer that also holds the card is refused `close-by-holder`;
    the holder that did not order it, and a third session, are refused `close-not-orderer`; each refusal names the
    way out and the card stays open. Catches: a session that approves its own work."""
    root = _ready(tmp_path, holder=ORD)
    how, reason, text = _close(root, ORD)
    assert (how, reason) == ("gate", "close-by-holder")
    assert "give" in text and "terminal" in text
    assert _row(root)["status"] == "open"
    other = _ready(tmp_path / "two")
    for session in (HOLD, THIRD):
        how, reason, text = _close(other, session)
        assert (how, reason) == ("gate", "close-not-orderer"), session
        assert ORD in text and "terminal" in text
    assert _row(other)["status"] == "open" and "closed by" not in _log(other)


def test_a_failing_or_missing_test_refuses_the_close(tmp_path):
    """E13 (rule 4): every Acceptance row's test must pass now: a red test is `close-tests-failing` naming it, a row
    that names no existing test is the same refusal; the card stays open and nothing is logged. A row `checked by
    reading` names a file that exists and runs nothing. Catches: a close over a red or missing test."""
    root = _ready(tmp_path, cells=(OK, BAD))
    how, reason, text = _close(root, ORD)
    assert (how, reason) == ("cli", "close-tests-failing")
    assert BAD in text and OK not in text.replace(BAD, "")
    assert _row(root)["status"] == "open" and "closed by" not in _log(root)
    missing = _ready(tmp_path / "two", cells=(OK, "tests/test_ok.py::test_gone"))
    how, reason, text = _close(missing, ORD)
    assert (how, reason) == ("cli", "close-tests-failing") and "test_gone" in text
    assert _row(missing)["status"] == "open"
    (tmp_path / "three").mkdir()
    reading = _ready(tmp_path / "three", cells=("checked by reading: README.md",))
    (reading / "README.md").write_text("synthetic\n", encoding="utf-8")
    assert _close(reading, ORD)[:2] == ("ok", None)


def test_the_tests_run_when_the_close_runs_not_when_the_card_was_written(tmp_path):
    """E14 (rule 4): the named tests run at the close: the same card is refused while a test is red and closes once
    the test passes. Catches: a result cached from an earlier run."""
    root = _ready(tmp_path, cells=("tests/test_flip.py::test_flip",))
    flip = root / "tests" / "test_flip.py"
    flip.write_text("def test_flip():\n    assert False\n", encoding="utf-8")
    assert _close(root, ORD)[:2] == ("cli", "close-tests-failing")
    flip.write_text("def test_flip():\n    assert True\n", encoding="utf-8")
    assert _close(root, ORD)[:2] == ("ok", None)


def test_an_owner_ordered_card_closes_only_in_the_owners_terminal_until_given(tmp_path):
    """E15 (rule 4): a card whose `Ordered by` is `owner` is refused `close-not-orderer` to every session, the message
    naming the owner's terminal and `give`; the owner's own `card close` passes; after the owner's `give` the
    ordering session closes it. Catches: a session that closes a card nobody gave it."""
    root = _ready(tmp_path, creator=None)
    assert _row(root)["ordered"] == "owner"
    how, reason, text = _close(root, ORD)
    assert (how, reason) == ("gate", "close-not-orderer") and "owner" in text and "give" in text
    records.append(_state(root), ORD, "search", "x")
    assert cli(root, "give", "CARD-001", ORD)[0] == 0
    assert _close(root, ORD)[:2] == ("ok", None)
    assert "closed by s-ord; ordered by s-ord" in _log(root)
    other = _ready(tmp_path / "two", creator=None)
    assert cli(other, "card", "close", "CARD-001")[0] == 0 and _row(other)["status"] == "closed"


def test_only_an_open_or_waiting_card_closes_by_its_orderer(tmp_path):
    """E16 (rule 4): the card is `open` or `waiting`: a `waiting` card closes; a `proposed`, a `waiting-owner` and a
    `closed` card are `card-bad-move`. Catches: a close that skips the chain."""
    waiting = _ready(tmp_path)
    assert cli(waiting, "card", "set", "CARD-001", "waiting", session=True)[0] == 0
    assert _row(waiting)["status"] == "waiting"
    assert _close(waiting, ORD)[:2] == ("ok", None)
    assert _close(waiting, ORD)[:2] == ("cli", "card-bad-move")  # closed already
    proposed = _ready(tmp_path / "two", opened=False)
    assert _close(proposed, ORD)[:2] == ("cli", "card-bad-move") and _row(proposed)["status"] == "proposed"
    paused = _ready(tmp_path / "three")
    assert cli(paused, "card", "set", "CARD-001", "waiting")[0] == 0
    assert _row(paused)["status"] == "waiting-owner"
    assert _close(paused, ORD)[:2] == ("cli", "card-bad-move") and _row(paused)["status"] == "waiting-owner"


def test_the_cli_decides_again_with_the_session_the_permit_names(tmp_path, monkeypatch):
    """E17 (rule 4): the CLI never takes a session's word: with no permit, an expired one, one for another card, or
    one that names a session that is not the orderer or is the holder, a session's `card close` is refused
    (`close-not-orderer`, `close-by-holder`); a permit is used once. Catches: a CLI that closes without the hook's
    check, a replayed permit, or a forged session id."""
    clock = {"at": T0}
    monkeypatch.setattr(logs, "now", lambda: clock["at"])
    root = _ready(tmp_path)
    state = _state(root)

    def attempt():
        code, _out, err = cli(root, "card", "close", "CARD-001", session=True)
        assert code != 0 and _row(root)["status"] == "open"
        return _reason(err)

    assert attempt() == "close-not-orderer"  # no permit at all
    cardtool.issue_close_permit(state, "CARD-002", ORD)
    assert attempt() == "close-not-orderer"  # a permit for another card
    cardtool.issue_close_permit(state, "CARD-001", ORD)
    clock["at"] = T0 + datetime.timedelta(minutes=10)
    assert attempt() == "close-not-orderer"  # expired
    cardtool.issue_close_permit(state, "CARD-001", HOLD)
    assert attempt() == "close-not-orderer"  # a permit that names a session that did not order the card
    cardtool.issue_close_permit(state, "CARD-001", THIRD)
    assert attempt() == "close-not-orderer"
    holds = _ready(tmp_path / "two", holder=ORD)
    cardtool.issue_close_permit(_state(holds), "CARD-001", ORD)
    code, _out, err = cli(holds, "card", "close", "CARD-001", session=True)
    assert code != 0 and _reason(err) == "close-by-holder" and _row(holds)["status"] == "open"
    cardtool.issue_close_permit(state, "CARD-001", ORD)
    code, out, err = cli(root, "card", "close", "CARD-001", session=True)
    assert code == 0, err
    assert cli(root, "card", "close", "CARD-001", session=True)[0] != 0  # the permit was used up


def test_a_session_never_sets_closed_and_the_default_stays_owner_only(tmp_path):
    """E18 (rule 4): `card set <id> closed` stays the owner's even with `orderer`, in light mode too; with the default
    approver `card close` is `owner-only-command` for the orderer as for every session, at the gate and at the CLI,
    and the owner's terminal closes as before. Catches: a second door to `closed`, or a default that changed."""
    root = _ready(tmp_path)
    verdict = gate_call(gate_lock.check, root, tool="Bash", session=ORD,
                        tool_input={"command": "python mkway/engine/mkway.py card set CARD-001 closed"})
    assert verdict.kind == "refuse" and verdict.reason_id == "owner-only-command"
    code, _out, err = cli(root, "card", "set", "CARD-001", "closed", session=True)
    assert code != 0 and _reason(err) == "owner-only-command" and _row(root)["status"] == "open"
    light = _ready(tmp_path / "two", cards={"owner_moves": []})
    verdict = gate_call(gate_lock.check, light, tool="Bash", session=ORD,
                        tool_input={"command": "python mkway/engine/mkway.py card set CARD-001 closed"})
    assert verdict.kind == "refuse" and verdict.reason_id == "owner-only-command"
    code, _out, err = cli(light, "card", "set", "CARD-001", "closed", session=True)
    assert code != 0 and _reason(err) == "owner-only-command"
    assert _close(light, THIRD)[:2] == ("gate", "close-not-orderer")
    default = _ready(tmp_path / "three", approver=None)
    assert _close(default, ORD)[:2] == ("gate", "owner-only-command")
    code, _out, err = cli(default, "card", "close", "CARD-001", session=True)
    assert code != 0 and _reason(err) == "owner-only-command"
    assert cli(default, "card", "close", "CARD-001")[0] == 0 and _row(default)["status"] == "closed"


def test_the_gate_reads_the_session_id_of_the_hook_input(tmp_path):
    """E19 (rule 6): a payload with no `session_id` cannot be the orderer (`close-not-orderer`, «not established»); a
    sub-agent is its `session_id` as the hook input gives it, beside its `agent_id`: the holder's sub-agent is refused,
    the orderer's passes; the refusal row carries the declared reason id. Catches: an agent id taken for a session."""
    root = _ready(tmp_path)
    verdict = gate_call(gate_lock.check, root, tool="Bash", session=None,
                        tool_input={"command": "python mkway/engine/mkway.py card close CARD-001"})
    assert verdict.kind == "refuse" and verdict.reason_id == "close-not-orderer" and "not established" in verdict.message

    def fire(session, **extra):
        payload = {"session_id": session, "hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": str(root),
                   "tool_input": {"command": "python mkway/engine/mkway.py card close CARD-001"}, **extra}
        return dispatch.run("PreToolUse", "shell", json.dumps(payload), env={"CLAUDE_PROJECT_DIR": str(root)})

    denied = fire(HOLD, agent_id="a-1", agent_type="worker")
    assert "close-not-orderer" in denied.stdout and "deny" in denied.stdout
    assert fire(ORD, agent_id="a-1", agent_type="worker").stdout == ""
    assert fire("a-1").stdout != ""  # an agent id is no session id
    reasons = [r["reason_id"] for r in jsonl(_state(root) / "refusals.jsonl") if r.get("kind") == "refuse"]
    assert reasons and set(reasons) == {"close-not-orderer"}


def test_the_new_reasons_are_declared_in_the_manifest():
    """E20 (rule 4): the lock gate's shell entry declares `close-not-orderer` and `close-by-holder`, else the
    dispatcher logs the refusal as undeclared."""
    entries = dispatch.load_manifest(dispatch.ENGINE_DIR)
    (shell,) = [e for e in entries if e["name"] == "lock.shell"]
    assert {"close-not-orderer", "close-by-holder"} <= set(shell["reason_ids"])
