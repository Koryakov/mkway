"""Card MW-132 (rulings R337, R337a, R338, R338a): the shell of the handoff notice reads its facts from the engine's own records (the
timing rows, the calls log, the message record, the register) and the hook input, and writes what the decision says. The decision is
proven by `tests/core/test_mw132_handoff_core.py`; here one test id proves one fact is read right or one wire is connected, on a
synthetic task root, through the real dispatcher (`dispatch.run`). Every test runs under 20 s. Synthetic roots and session ids only."""
import datetime
import json

import pytest

from _engine import jsonl
from _mw017 import profile_of
from _mw017 import new_card
from _mw018 import send, seen, state, world
import dispatch
import gatemode
import leads
import messages
import profiles
import register
import startline

BUILDER, LEAD, OTHER_LEAD, FREE = "build-a1", "lead-a", "lead-b", "free-1"
CARD = "CARD-001"
ENV_KEYS = {"CLAUDECODE": "1"}
LAST = "Should I change those four nodes, then fix the three query files?"
NOTICE_FIRST_LINE = f"{BUILDER} ended its turn holding {CARD} without a message to you"


def _fire(root, event, group, session, tool=None, tool_input=None, **extra):
    payload = {"session_id": session, "hook_event_name": event, "cwd": str(root), **extra}
    if tool is not None:
        payload.update(tool_name=tool, tool_input=tool_input)
    return dispatch.run(event, group, json.dumps(payload), env={"CLAUDE_PROJECT_DIR": str(root), **ENV_KEYS})


def _prompt(root, session=BUILDER):
    return _fire(root, "UserPromptSubmit", "prompt", session)


def _stop(root, session=BUILDER, active=False, last=LAST, **extra):
    if last is not None:
        extra["last_assistant_message"] = last
    return _fire(root, "Stop", "stop", session, stop_hook_active=active, **extra)


def _out(result):
    return json.loads(result.stdout) if result.stdout else {}


def _inbox(root, who=LEAD):
    return jsonl(state(root) / "inbox" / f"{who}.jsonl")


def _rows(root, reason):
    path = state(root) / "refusals.jsonl"
    return [r for r in jsonl(path) if r.get("reason_id") == reason] if path.is_file() else []


def _errors(root, reason="handoff-notice-failed"):
    path = state(root) / "gate_calls.jsonl"
    return [r for r in jsonl(path) if r.get("reason_id") == reason and r.get("verdict") == "error"] if path.is_file() else []


def _ordered_by(root, who):
    register.set_ordered(root, profile_of(root), CARD, who)


def _shared(root):
    return profiles.shared_state_dir(root, profile_of(root))


def _ago(seconds):
    return datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=seconds)


def _text(when):
    return when.isoformat(timespec="milliseconds")


def _timing_row(root, session, when, event="Stop", group="stop", flag=None):
    row = {"time": _text(when), "session": session, "event": event, "group": group, "gates_ms": {}, "total_ms": 1.0}
    if flag is not None:
        row["stop_hook_active"] = flag
    with open(state(root) / f"timing-{when.strftime('%Y-%m-%d')}.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def _call_row(root, session, call_id, when, verdict="allow", event="PreToolUse", tool="Bash", gate="lock.shell", **extra):
    row = {"time": _text(when), "gate": gate, "verdict": verdict, "session": session, "event": event, "tool": tool,
           "call": call_id, **extra}
    path = state(root) / "gate_calls.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def _send_record(root, session, to, when, event="send"):
    row = {"event": event, "id": "m-x", "session": session, "to": to, "ts": _text(when)}
    with open(state(root) / "message-record.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def _refused(root, session=BUILDER):
    result = _fire(root, "PreToolUse", "shell", session, "Bash", {"command": "python mkway/engine/mkway.py card take CARD-002"})
    assert _out(result)["hookSpecificOutput"]["permissionDecision"] == "deny"


def _block_text(inbox_id):
    return (f"you ended your turn holding {CARD} without a message to your orderer; your last message was sent to your "
            f"orderer as inbox row {inbox_id}; tell your orderer: mkway inbox {inbox_id}")


def _start_line(root, session):
    return _out(_fire(root, "SessionStart", "start", session))["hookSpecificOutput"]["additionalContext"]


# ---- the fact readers --------------------------------------------------------------------------------------------------

def test_the_first_stop_of_a_session_has_its_first_row_as_the_turn_start(tmp_path):
    """Checks: R340a (4): with no earlier Stop row the boundary is the first row of this session, never another session's row."""
    root = world(tmp_path)
    when = _ago(60)
    _timing_row(root, BUILDER, when, event="UserPromptSubmit", group="prompt")
    _timing_row(root, BUILDER, _ago(45), event="UserPromptSubmit", group="prompt")
    _timing_row(root, OTHER_LEAD, _ago(30), event="UserPromptSubmit", group="prompt")
    assert gatemode.handoff_turn(state(root), BUILDER) == _text(when)


def test_a_prompt_row_in_the_middle_of_a_turn_does_not_move_the_boundary(tmp_path):
    """Pins: R340a (1): a peer message that arrives mid-turn writes a prompt row; the boundary stays at the first row, not at that row."""
    root = world(tmp_path)
    when = _ago(60)
    _timing_row(root, BUILDER, when, event="UserPromptSubmit", group="prompt")
    _timing_row(root, BUILDER, _ago(20), event="UserPromptSubmit", group="prompt")
    assert gatemode.handoff_turn(state(root), BUILDER) == _text(when)


def test_a_session_with_no_boundary_row_has_no_turn_start(tmp_path):
    """Checks: R340a: the engine holds no row of this session at all: the reader returns none."""
    root = world(tmp_path)
    assert gatemode.handoff_turn(state(root), BUILDER) is None


def test_a_previous_stop_row_that_ended_a_quiet_turn_is_the_next_turn_start(tmp_path):
    """Checks: a Stop run that wrote no mark ended its turn: its timing row is the boundary of the next turn."""
    root = world(tmp_path)
    when = _ago(30)
    _timing_row(root, BUILDER, _ago(60), event="UserPromptSubmit", group="prompt")
    _timing_row(root, BUILDER, when)
    assert gatemode.handoff_turn(state(root), BUILDER) == _text(when)


def test_a_stop_run_that_wrote_the_notice_is_a_continuation_not_a_boundary(tmp_path):
    """Catches: the turn's own first stop taken as the start of a new turn, so a second stop of it would be judged again (R2-18)."""
    root = world(tmp_path)
    _prompt(root)
    start = gatemode.handoff_turn(state(root), BUILDER)
    _stop(root)
    assert gatemode.handoff_turn(state(root), BUILDER, True) == start


def test_a_continued_stop_after_a_stop_another_gate_refused_keeps_the_boundary(tmp_path):
    """Catches: R2-4: a stop refused by another Stop gate taken as the end of the turn when the next stop continues it."""
    root = world(tmp_path)
    start = _ago(60)
    _timing_row(root, BUILDER, start, event="UserPromptSubmit", group="prompt")
    _call_row(root, BUILDER, "c1", _ago(40), verdict="refuse", event="Stop", tool=None, gate="message", id="gc-1")
    _timing_row(root, BUILDER, _ago(30))
    assert gatemode.handoff_turn(state(root), BUILDER, True) == _text(start)


def test_the_sends_reader_returns_the_time_and_the_recipient_of_each_send_of_this_session(tmp_path):
    """Checks: R1-6: a reader of this session's sends with (time, recipient); the hook's own records are no send."""
    root = world(tmp_path)
    code, _o, err = send(root, BUILDER, LEAD, "question", "a real question")
    assert code == 0, err
    messages.send_handoff(root, profile_of(root), _shared(root), BUILDER, LEAD, "body", CARD)
    found = messages.sends_to(_shared(root), BUILDER)
    assert [to for _ts, to in found] == [LEAD]


def test_the_sends_by_reader_of_the_refusal_delivery_still_returns_times_only(tmp_path):
    """Pins: R1-6: `sends_by` stays unchanged for MW-128: times only."""
    root = world(tmp_path)
    send(root, BUILDER, LEAD, "question", "a real question")
    assert [isinstance(t, str) for t in messages.sends_by(_shared(root), BUILDER)] == [True]


def test_the_held_card_reader_returns_the_card_and_its_orderer(tmp_path):
    """Checks: R1-7: one reader returns (card, orderer) of the card the session holds."""
    root = world(tmp_path)
    assert messages.held_card(root, profile_of(root), BUILDER) == (CARD, LEAD)


def test_the_held_card_reader_returns_none_for_a_session_with_no_card(tmp_path):
    """Checks: R1-7: no card is told apart from no orderer: it returns none."""
    root = world(tmp_path)
    assert messages.held_card(root, profile_of(root), FREE) is None


def test_the_held_card_reader_names_the_owner_when_the_orderer_cell_is_empty(tmp_path):
    """Checks: R1-7: a held card with an empty orderer cell comes back with the owner as its orderer."""
    root = world(tmp_path)
    _ordered_by(root, "")
    assert messages.held_card(root, profile_of(root), BUILDER) == (CARD, "owner")


def test_the_held_card_reader_does_not_swallow_a_failed_register_read(tmp_path, monkeypatch):
    """Catches: R2-22: a register read that fails read as «no card», which would hide the failure behind a quiet stop."""
    root = world(tmp_path)
    monkeypatch.setattr(register, "read", lambda *a, **k: (_ for _ in ()).throw(OSError("register unreadable")))
    with pytest.raises(OSError):
        messages.held_card(root, profile_of(root), BUILDER)


# ---- the first stop ----------------------------------------------------------------------------------------------------

def test_a_first_stop_with_no_handoff_writes_the_notice_with_the_last_message_and_blocks_with_the_exact_text(tmp_path):
    """Catches: a builder that ends a turn with a question in its own chat and no word to its orderer (the live case)."""
    root = world(tmp_path)
    _prompt(root)
    out = _out(_stop(root))
    (row,) = _inbox(root)
    assert (row["from"], row["to"], row["kind"], row["body"]) == (BUILDER, LEAD, "notice", NOTICE_FIRST_LINE + "\nlast message: " + LAST)
    assert out == {"decision": "block", "reason": _block_text(row["id"])}


def test_the_way_out_of_handoff_notice_is_the_ping_line_the_block_names(tmp_path):
    """Checks: the notice is in the orderer's inbox and `mkway inbox <id>` shows it with the last message."""
    root = world(tmp_path)
    _prompt(root)
    _stop(root)
    row_id = _inbox(root)[-1]["id"]
    assert LAST in messages.show(_shared(root), LEAD, row_id)["body"]


def test_the_notice_record_row_names_the_card_the_turn_and_the_block(tmp_path):
    """Pins: R1-3 and R1-12: one record row `handoff-notice`: the session, the card, the inbox row, the turn's boundary time, blocked."""
    root = world(tmp_path)
    _prompt(root)
    start = gatemode.handoff_turn(state(root), BUILDER)
    _stop(root)
    (row,) = _rows(root, "handoff-notice")
    assert (row["session"], row["event"], row["kind"], row["card"], row["to"], row["inbox_id"], row["turn"], row["blocked"]) == (
        BUILDER, "Stop", "log", CARD, LEAD, _inbox(root)[-1]["id"], start, True)


def test_the_notice_leaves_its_own_message_record_that_is_no_send(tmp_path):
    """Catches: R1-3: the engine's notice counted as a send of the session, which would hide the next silent turn end."""
    root = world(tmp_path)
    _prompt(root)
    _stop(root)
    events = [r["event"] for r in jsonl(state(root) / "message-record.jsonl")]
    assert (events, messages.sends_by(_shared(root), BUILDER)) == (["handoff-notice"], [])


def test_the_next_stop_after_the_ping_passes_with_no_new_row(tmp_path):
    """Checks: after the block the session runs the ping and stops again: it passes, and no second notice exists."""
    root = world(tmp_path)
    _prompt(root)
    _stop(root)
    messages.show(_shared(root), LEAD, _inbox(root)[-1]["id"])
    second = _out(_stop(root, active=True))
    assert (second.get("decision"), len(_inbox(root)), len(_rows(root, "handoff-notice"))) == (None, 1, 1)


def test_a_first_stop_with_stop_hook_active_true_writes_the_row_and_does_not_block(tmp_path):
    """Catches: a second block in a row: the first stop the step sees may itself be a continuation (R338 1)."""
    root = world(tmp_path)
    _prompt(root)
    out = _out(_stop(root, active=True))
    assert (out.get("decision"), "continue" in out, len(_inbox(root)), [r["blocked"] for r in _rows(root, "handoff-notice")]) == (
        None, False, 1, [False])


def test_a_second_stop_in_the_same_turn_writes_no_second_row(tmp_path):
    """Catches: a second notice at a later stop of one turn (the later stop continues the first: the flag is true)."""
    root = world(tmp_path)
    _prompt(root)
    _stop(root)
    _stop(root, active=True)
    assert len(_inbox(root)) == 1


def test_two_stops_in_one_turn_both_continued_by_the_hook_leave_one_notice_and_one_record_row(tmp_path):
    """Catches: R2-8: two continued stops of one turn writing two notices."""
    root = world(tmp_path)
    _prompt(root)
    _stop(root, active=True)
    _stop(root, active=True)
    assert (len(_inbox(root)), len(_rows(root, "handoff-notice"))) == (1, 1)


def test_a_new_turn_writes_its_own_notice_and_blocks_again(tmp_path):
    """Checks: R2-3: turn 1 ends with a notice and its continued stop; turn 2 (a new prompt row) stops with the flag false: its own notice and block."""
    root = world(tmp_path)
    _prompt(root)
    _stop(root)
    _stop(root, active=True)
    _prompt(root)
    out = _out(_stop(root))
    assert (out.get("decision"), len(_inbox(root))) == ("block", 2)


def test_a_tool_call_after_the_block_then_a_continued_stop_blocks_not_again(tmp_path):
    """Catches: R2-18: the block repeated after the session went on with a tool call and stopped again, continued by the hook."""
    root = world(tmp_path)
    _prompt(root)
    _stop(root)
    _fire(root, "PreToolUse", "shell", BUILDER, "Bash", {"command": "ls"})
    out = _out(_stop(root, active=True))
    assert (out.get("decision"), len(_inbox(root))) == (None, 1)


def test_a_tool_call_after_the_block_then_a_stop_with_stop_hook_active_false_blocks_not_again(tmp_path):
    """Catches: R2-18 (R342): the flag false at the stop after our block and the ping: a loop of notice, block, ping, stop."""
    root = world(tmp_path)
    _prompt(root)
    _stop(root)
    _fire(root, "PreToolUse", "shell", BUILDER, "Bash", {"command": "ls"})
    out = _out(_stop(root, active=False))
    assert (out.get("decision"), "continue" in out, len(_inbox(root)), len(_rows(root, "handoff-notice"))) == (None, False, 1, 1)


def test_a_blocked_stop_a_tool_call_a_plain_stop_and_then_a_new_turn_is_judged_normally(tmp_path):
    """Checks: R342 (3): the link «the stop before it was blocked by this step» does not swallow a later turn: notice and block once."""
    root = world(tmp_path)
    _prompt(root)
    _stop(root)
    _fire(root, "PreToolUse", "shell", BUILDER, "Bash", {"command": "ls"})
    _stop(root, active=False)
    _prompt(root)
    out = _out(_stop(root))
    assert (out.get("decision"), len(_inbox(root)), len(_rows(root, "handoff-notice"))) == ("block", 2, 2)


def test_a_new_prompt_right_after_a_blocked_stop_is_not_judged_the_named_miss(tmp_path):
    """Pins: R342 (4): a person interrupts the continued turn with a new prompt and that turn ends silently: a miss, never a trap."""
    root = world(tmp_path)
    _prompt(root)
    _stop(root)
    _prompt(root)
    out = _out(_stop(root))
    assert (out.get("decision"), len(_inbox(root))) == (None, 1)


def test_the_turn_reader_takes_a_stop_after_a_stop_blocked_by_this_step_as_its_continuation(tmp_path):
    """Pins: R342 (1): after a stop this step blocked, the boundary of the next stop (flag false) is still the session's first row."""
    root = world(tmp_path)
    _prompt(root)
    start = gatemode.handoff_turn(state(root), BUILDER)
    _stop(root)
    assert gatemode.handoff_turn(state(root), BUILDER, False) == start


def _three_turns(root):
    for _turn in range(3):
        _prompt(root)
        _stop(root)
        _stop(root, active=True)
        _stop(root, active=True)


def test_several_turns_leave_at_most_one_notice_each(tmp_path):
    """Checks: R1-13: three turns, each started by a prompt and stopped three times: three notices, one for each turn."""
    root = world(tmp_path)
    _three_turns(root)
    assert len(_inbox(root)) == 3


# ---- who is judged -----------------------------------------------------------------------------------------------------

def test_a_stop_after_a_real_send_to_the_orderer_writes_nothing(tmp_path):
    """Checks: (h) a session with a handoff pays nothing: no block, no row."""
    root = world(tmp_path)
    _prompt(root)
    code, _o, err = send(root, BUILDER, LEAD, "question", "my own report")
    assert code == 0, err
    out = _out(_stop(root))
    assert (out.get("decision"), "continue" in out, [r["body"] for r in _inbox(root)], _rows(root, "handoff-notice")) == (
        None, False, ["my own report"], [])


def test_a_send_to_another_session_than_the_orderer_still_writes_and_blocks(tmp_path):
    """Catches: R2-1: a send recorded to another session taken as a handoff to the orderer."""
    root = world(tmp_path)
    _prompt(root)
    _send_record(root, BUILDER, OTHER_LEAD, datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=5))
    out = _out(_stop(root))
    assert (out.get("decision"), len(_inbox(root))) == ("block", 1)


def test_a_send_of_the_previous_turn_does_not_count(tmp_path):
    """Catches: R2-2: a send before the turn's prompt row taken as this turn's handoff."""
    root = world(tmp_path)
    send(root, BUILDER, LEAD, "question", "yesterday's report")
    _prompt(root)
    out = _out(_stop(root))
    assert (out.get("decision"), len(_inbox(root))) == ("block", 2)


def test_a_send_at_the_same_millisecond_as_the_boundary_does_not_count(tmp_path):
    """Pins: R2-2: a send record with the boundary row's own time is the previous turn's."""
    root = world(tmp_path)
    _prompt(root)
    _send_record(root, BUILDER, LEAD, datetime.datetime.fromisoformat(gatemode.handoff_turn(state(root), BUILDER)))
    out = _out(_stop(root))
    assert (out.get("decision"), len(_inbox(root))) == ("block", 1)


def test_a_send_early_in_the_turn_followed_by_work_still_counts_and_the_log_names_the_hole(tmp_path):
    """Pins: R338 2: the plain reader of «no engine call after the send» is not reused: any send to the orderer in the turn counts."""
    root = world(tmp_path)
    _prompt(root)
    send(root, BUILDER, LEAD, "question", "early report")
    _fire(root, "PreToolUse", "shell", BUILDER, "Bash", {"command": "ls"})
    out = _out(_stop(root))
    assert (out.get("decision"), len(_inbox(root))) == (None, 1)


def test_a_card_ordered_by_the_owner_gets_one_record_row_and_no_block(tmp_path):
    """Checks: (b): an owner-ordered card has no session inbox: one record row `handoff-no-orderer`, no block, no inbox row."""
    root = world(tmp_path)
    _ordered_by(root, "owner")
    _prompt(root)
    out = _out(_stop(root))
    (row,) = _rows(root, "handoff-no-orderer")
    assert (out.get("decision"), "continue" in out, row["session"], row["card"], row["kind"], _inbox(root)) == (
        None, False, BUILDER, CARD, "log", [])


def test_the_no_orderer_row_is_written_once_per_turn_end(tmp_path):
    """Catches: one no-orderer row for every Stop of one turn."""
    root = world(tmp_path)
    _ordered_by(root, "owner")
    _prompt(root)
    _stop(root)
    _stop(root, active=True)
    assert len(_rows(root, "handoff-no-orderer")) == 1


def test_the_way_out_of_handoff_no_orderer_is_one_record_row_and_no_block(tmp_path):
    """Catches: a block, or a missing record row, when the card has no orderer session (an empty cell)."""
    root = world(tmp_path)
    _ordered_by(root, "")
    _prompt(root)
    out = _out(_stop(root))
    assert (out.get("decision"), len(_rows(root, "handoff-no-orderer"))) == (None, 1)


def test_an_orderer_that_is_this_session_gets_one_record_row_and_never_a_block(tmp_path):
    """Checks: R2-6: a message to yourself is refused by the topology; the stop is allowed with one record row."""
    root = world(tmp_path)
    _ordered_by(root, BUILDER)
    _prompt(root)
    out = _out(_stop(root))
    assert (out.get("decision"), len(_rows(root, "handoff-no-orderer")), _inbox(root, BUILDER)) == (None, 1, [])


def test_a_session_with_no_card_is_never_judged(tmp_path):
    """Checks: (b) a session holding no card: nothing, no row, no block."""
    root = world(tmp_path)
    _prompt(root, FREE)
    out = _out(_stop(root, FREE))
    assert (out.get("decision"), _rows(root, "handoff-notice"), _rows(root, "handoff-no-orderer")) == (None, [], [])


def test_a_registered_lead_holding_a_card_is_never_judged(tmp_path):
    """Checks: (b) and R2-14: the lead's own stop passes: no notice, no row, no block."""
    root = world(tmp_path)
    leads.register_lead(_shared(root), BUILDER)
    _prompt(root)
    out = _out(_stop(root))
    assert (out.get("decision"), _inbox(root), _rows(root, "handoff-notice")) == (None, [], [])


def test_an_orderer_that_is_a_seen_session_but_no_lead_gets_the_notice_and_no_block(tmp_path):
    """Checks: R338a: the printed ping line would not work for that role: the notice is written, only the block is dropped."""
    root = world(tmp_path)
    _ordered_by(root, FREE)
    _prompt(root)
    out = _out(_stop(root))
    assert (out.get("decision"), len(_inbox(root, FREE))) == (None, 1)


def test_a_turn_with_no_boundary_row_is_not_judged(tmp_path):
    """Pins: R340a: the engine holds no row of the session at all: nothing is judged, nothing is written to the orderer."""
    root = world(tmp_path)
    out = _out(_stop(root))
    assert (out.get("decision"), _inbox(root)) == (None, [])


def test_a_subagent_stop_is_never_judged(tmp_path):
    """Checks: R2-10: a SubagentStop event of the builder's session writes no notice and no row."""
    root = world(tmp_path)
    _prompt(root)
    got = _fire(root, "SubagentStop", "post", BUILDER, stop_hook_active=False, last_assistant_message=LAST)
    assert (_out(got).get("decision"), _inbox(root), _rows(root, "handoff-notice")) == (None, [], [])


def test_a_turn_ending_with_background_work_running_is_judged_the_same(tmp_path):
    """Checks: R2-16 and R338 3: background_tasks non-empty in the hook input is no exemption: the notice and the block."""
    root = world(tmp_path)
    _prompt(root)
    out = _out(_stop(root, background_tasks=[{"id": "b1"}, {"id": "b2"}]))
    (row,) = _rows(root, "handoff-notice")
    assert (out.get("decision"), row["background_tasks"]) == ("block", 2)


def test_a_hook_input_with_no_background_tasks_field_keeps_none_in_the_record_row(tmp_path):
    """Checks: the record row keeps the background_tasks count only when the hook input has the field."""
    root = world(tmp_path)
    _prompt(root)
    _stop(root)
    (row,) = _rows(root, "handoff-notice")
    assert row["background_tasks"] is None


@pytest.mark.parametrize("extra", [
    pytest.param({}, id="absent"),
    pytest.param({"last_assistant_message": None}, id="null"),
    pytest.param({"last_assistant_message": 12}, id="not-a-string"),
])
def test_a_hook_input_with_no_usable_last_message_writes_the_notice_with_not_established_and_no_error(tmp_path, extra):
    """Checks: R2-5: the last message absent, null or not a string: the body field says «not established», no error row."""
    root = world(tmp_path)
    _prompt(root)
    _stop(root, last=None, **extra)
    assert (_inbox(root)[-1]["body"], _errors(root)) == (NOTICE_FIRST_LINE + "\nlast message: not established", [])


def test_a_long_last_message_is_cut_in_the_notice_body(tmp_path):
    """Checks: the last message is cut to the named limit (2000 characters) with the cut marked."""
    root = world(tmp_path)
    _prompt(root)
    _stop(root, last="y" * 2500)
    assert _inbox(root)[-1]["body"] == NOTICE_FIRST_LINE + "\nlast message: " + "y" * 2000 + " [cut]"


# ---- MW-128 first ------------------------------------------------------------------------------------------------------

def test_a_refusal_delivered_by_the_refusal_step_is_not_doubled_by_a_handoff_notice(tmp_path):
    """Catches: R2-15: after MW-128 blocked a refusal the next stop (flag true, no send) writing a second notice next to it."""
    root = world(tmp_path)
    _prompt(root)
    _refused(root)
    first = _out(_stop(root))
    second = _out(_stop(root, active=True))
    assert (first["reason"].startswith("your refusal was sent to your orderer"), second.get("decision"), len(_inbox(root)),
            _rows(root, "handoff-notice")) == (True, None, 1, [])


def test_a_refusal_with_no_orderer_is_not_followed_by_a_handoff_record_row(tmp_path):
    """Catches: R2-15: MW-128's no-orderer path followed by a second record row of this card at the next stop."""
    root = world(tmp_path)
    _ordered_by(root, "owner")
    _prompt(root)
    _refused(root)
    _stop(root)
    _stop(root, active=True)
    assert (len(_rows(root, "refusal-no-orderer")), _rows(root, "handoff-no-orderer"), _rows(root, "handoff-notice")) == (1, [], [])


def test_a_refusal_whose_inbox_write_failed_is_not_followed_by_a_handoff_notice(tmp_path):
    """Catches: R1-10: MW-128's failed write (an error row) followed by this step's own notice at the same or the next stop."""
    root = world(tmp_path)
    _ordered_by(root, "ghost-lead")
    _prompt(root)
    _refused(root)
    _stop(root)
    _stop(root, active=True)
    assert (len(_errors(root, "refusal-delivery-failed")), _errors(root), _rows(root, "handoff-notice")) == (2, [], [])


# ---- other Stop gates, the eight-block cap, errors ---------------------------------------------------------------------

def _stop_refused_by_another_gate(root, tmp_path, active=False):
    """A Stop of the builder through the dispatcher with one extra Stop gate that refuses (a gate module written in tmp_path)."""
    gate_dir = tmp_path / "zz_gates"
    gate_dir.mkdir(exist_ok=True)
    (gate_dir / "zz_stop_refuser.py").write_text("import gate\n\n\ndef check(event, ctx):\n"
                                                 "    return gate.refuse('zz-refuse', 'a synthetic refusal of another Stop gate')\n",
                                                 encoding="utf-8")
    entry = {"name": "zz.refuse", "gate": "zz", "class": "integrity", "group": "stop", "function": "zz_stop_refuser:check",
             "reason_ids": ["zz-refuse"], "event": "Stop", "matcher": None, "timeout": 10, "onFailure": "none", "mode": None,
             "status": "on", "default_on": True}
    payload = {"session_id": BUILDER, "hook_event_name": "Stop", "cwd": str(root), "stop_hook_active": active,
               "last_assistant_message": LAST}
    return dispatch.run("Stop", "stop", json.dumps(payload), env={"CLAUDE_PROJECT_DIR": str(root), **ENV_KEYS},
                        manifest=dispatch.load_manifest(dispatch.ENGINE_DIR) + [entry],
                        gate_paths=[dispatch.ENGINE_DIR, gate_dir])


def test_a_stop_refused_by_another_gate_writes_nothing_at_that_stop(tmp_path):
    """Checks: R2-4: stop 1 is refused by another Stop gate: this step is skipped, nothing is written and the gate's block stands."""
    root = world(tmp_path)
    _prompt(root)
    out = _out(_stop_refused_by_another_gate(root, tmp_path))
    assert (out.get("decision"), out.get("reason", "").startswith("[mkway zz.refuse zz-refuse]"), _inbox(root)) == ("block", True, [])


def test_a_stop_refused_by_another_gate_then_a_continued_stop_writes_the_notice_and_never_blocks(tmp_path):
    """Checks: R2-4: stop 1 refused by another Stop gate, run through the dispatcher; stop 2 has the flag true: the notice, no block."""
    root = world(tmp_path)
    _prompt(root)
    _stop_refused_by_another_gate(root, tmp_path)
    out = _out(_stop(root, active=True))
    assert (out.get("decision"), "continue" in out, len(_inbox(root))) == (None, False, 1)


def _seven_refused_stops(root):
    """A turn that began 60 s ago (a prompt row) and in which seven stops were refused by another Stop gate: each leaves its refuse row
    and its Stop timing row, all INSIDE the turn."""
    _timing_row(root, BUILDER, _ago(60), event="UserPromptSubmit", group="prompt")
    for n in range(7):
        _call_row(root, BUILDER, f"s{n}", _ago(50 - 5 * n), verdict="refuse", event="Stop", tool=None, gate="message", id=f"gc-{n}")
        _timing_row(root, BUILDER, _ago(49 - 5 * n), flag=n > 0)


def test_the_notice_is_written_even_when_seven_stops_of_the_turn_were_already_refused(tmp_path):
    """Checks: R2-19 (the eight-block cap): seven refused stops inside the turn, then the eighth: the notice is written before any block."""
    root = world(tmp_path)
    _seven_refused_stops(root)
    out = _out(_stop(root, active=True))
    assert (out.get("decision"), len(_inbox(root))) == (None, 1)


def test_a_turn_ending_with_a_sendmessage_row_in_the_calls_log_is_no_handoff_because_the_row_holds_no_recipient(tmp_path):
    """Pins: R2-9: a SendMessage call, as a calls-log row can hold it (tool name, no recipient), is not a send: the notice and the block fire."""
    root = world(tmp_path)
    _prompt(root)
    _call_row(root, BUILDER, "sm1", datetime.datetime.now(datetime.timezone.utc), tool="SendMessage", gate="zz")
    out = _out(_stop(root))
    assert (out.get("decision"), len(_inbox(root))) == ("block", 1)


def test_an_orderer_that_cannot_receive_allows_the_stop_with_an_error_row_and_no_block_text(tmp_path):
    """Catches: R2-20: a write to an orderer no session of that name was ever seen as: a loop, a block, or no error row."""
    root = world(tmp_path)
    _ordered_by(root, "ghost-lead")
    _prompt(root)
    out = _out(_stop(root))
    assert (out.get("decision"), "continue" in out, [(r["session"], r["verdict"]) for r in _errors(root)],
            _rows(root, "handoff-notice")) == (None, False, [(BUILDER, "error")], [])


def test_the_way_out_of_handoff_notice_failed_is_the_error_row_and_the_screen_line(tmp_path):
    """Checks: R338 6: the failed write is shown on the stop's screen line and names the way out: tell the orderer yourself."""
    root = world(tmp_path)
    _ordered_by(root, "ghost-lead")
    _prompt(root)
    text = _out(_stop(root))["systemMessage"]
    assert ("handoff-notice-failed" in text, "mkway send" in text) == (True, True)


def test_a_failed_write_is_tried_once_per_turn_never_a_loop(tmp_path):
    """Catches: R2-20: the failed write retried at every stop of the turn."""
    root = world(tmp_path)
    _ordered_by(root, "ghost-lead")
    _prompt(root)
    _stop(root)
    _stop(root, active=True)
    assert len(_errors(root)) == 1


def test_a_failed_write_is_tried_again_in_the_next_turn(tmp_path):
    """Checks: once per turn, not once ever: the next turn tries the write again and succeeds when the orderer is back."""
    root = world(tmp_path)
    _ordered_by(root, "ghost-lead")
    _prompt(root)
    _stop(root)
    _ordered_by(root, LEAD)
    _prompt(root)
    out = _out(_stop(root))
    assert (out.get("decision"), len(_inbox(root)), len(_errors(root))) == ("block", 1, 1)


def test_a_failed_write_is_a_notice_on_the_start_line_of_this_session_only(tmp_path):
    """Catches: R338 6: no start-line notice after a failed write, or a notice shown to another session."""
    root = world(tmp_path)
    _ordered_by(root, "ghost-lead")
    _prompt(root)
    _stop(root)
    assert ("handoff-notice-failed" in _start_line(root, BUILDER), "handoff-notice-failed" in _start_line(root, "build-a2")) == (
        True, False)


def test_the_start_line_notice_ends_once_a_later_notice_is_written(tmp_path):
    """Checks: after a later turn's notice is written the start line no longer carries the failure notice."""
    root = world(tmp_path)
    _ordered_by(root, "ghost-lead")
    _prompt(root)
    _stop(root)
    _ordered_by(root, LEAD)
    _prompt(root)
    _stop(root)
    assert "handoff-notice-failed" not in _start_line(root, BUILDER)


def test_a_failed_register_read_is_an_error_row_and_a_start_line_notice_not_no_orderer(tmp_path, monkeypatch):
    """Catches: R2-22: a register read that raises told as «no orderer» (one quiet record row) instead of an error."""
    root = world(tmp_path)
    _prompt(root)
    monkeypatch.setattr(register, "read", lambda *a, **k: (_ for _ in ()).throw(OSError("register unreadable")))
    out = _out(_stop(root))
    assert (out.get("decision"), len(_errors(root)), _rows(root, "handoff-no-orderer")) == (None, 1, [])


def test_a_failed_register_read_leaves_the_start_line_notice(tmp_path, monkeypatch):
    """Checks: R2-22: the start line of the session names the failed notice after a register read failed at its stop."""
    root = world(tmp_path)
    _prompt(root)
    with monkeypatch.context() as patch:
        patch.setattr(register, "read", lambda *a, **k: (_ for _ in ()).throw(OSError("register unreadable")))
        _stop(root)
    assert "handoff-notice-failed" in _start_line(root, BUILDER)


# ---- the card the line, the check and the notice use -------------------------------------------------------------------

def _second_take(root, card):
    with open(state(root) / "records.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"session_id": BUILDER, "kind": "take", "value": card, "time": _text(_ago(1)), "by": "session"}) + "\n")


def test_a_second_take_while_the_first_card_is_open_changes_nothing_the_first_card_and_its_orderer_are_used(tmp_path):
    """Pins: R2-7: a take of a second card by a session whose first card is open is ignored by the records: the line, the check and the notice use the first."""
    root = world(tmp_path)
    _second_take(root, new_card(root, OTHER_LEAD, "Fourth"))
    _prompt(root)
    _stop(root)
    (row,) = _rows(root, "handoff-notice")
    assert (row["card"], row["to"], len(_inbox(root)), _inbox(root, OTHER_LEAD)) == (CARD, LEAD, 1, [])


# ---- the owner table and the concept rows ------------------------------------------------------------------------------

def test_the_four_record_ids_are_in_the_concept_table_as_record_rows_with_a_way_out_test():
    """Checks: R338: each id the card adds is a `record` row of the concept table naming its way-out test."""
    import concept
    ids = ("handoff-notice", "handoff-no-orderer", "handoff-notice-failed", "handoff-no-turn-start")
    assert [(concept.REASONS[i].kind_or_exit, concept.REASONS[i].way_out is not None) for i in ids] == [("record", True)] * 4



# ---- reader 2 of 17.11: the turn rule, the second card, the stale orderer, the exact role line -----------------------------

def test_a_continued_stop_makes_the_previous_stop_row_a_continuation(tmp_path):
    """Pins: the design hole: with stop_hook_active true the previous Stop row was blocked by someone, so it is no boundary."""
    root = world(tmp_path)
    start = _ago(60)
    _timing_row(root, BUILDER, start, event="UserPromptSubmit", group="prompt")
    _timing_row(root, BUILDER, _ago(30))
    assert gatemode.handoff_turn(state(root), BUILDER, True) == _text(start)


def test_a_plain_stop_after_a_quiet_stop_row_starts_a_new_turn(tmp_path):
    """Pins: the design hole: with the flag false and no block mark, the previous Stop row ended its turn: it is the new boundary."""
    root = world(tmp_path)
    stop_row = _ago(30)
    _timing_row(root, BUILDER, _ago(60), event="UserPromptSubmit", group="prompt")
    _timing_row(root, BUILDER, stop_row)
    assert gatemode.handoff_turn(state(root), BUILDER, False) == _text(stop_row)


def _background_turns(root):
    """Turn 1 starts with a prompt; turns 2 and 3 start with NO prompt row (background work or a lead's message): each stops plain, then twice continued."""
    _prompt(root)
    for _turn in range(3):
        _stop(root)
        _stop(root, active=True)
        _stop(root, active=True)


def test_turns_that_start_with_no_prompt_row_are_judged_too_one_notice_each(tmp_path):
    """Catches: the design hole: a turn begun by background work right after a noticed stop found «delivered» and was never judged."""
    root = world(tmp_path)
    _background_turns(root)
    assert len(_inbox(root)) == 3


def test_a_send_to_the_orderer_of_a_second_card_is_no_handoff_for_the_first(tmp_path):
    """Checks: R2-7, the check: the second take is ignored while the first card is open; a send to ITS orderer is a send to another session."""
    root = world(tmp_path)
    _second_take(root, new_card(root, OTHER_LEAD, "Fourth"))
    _prompt(root)
    _send_record(root, BUILDER, OTHER_LEAD, datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=5))
    out = _out(_stop(root))
    assert (out.get("decision"), len(_inbox(root)), _inbox(root, OTHER_LEAD)) == ("block", 1, [])


def test_an_orderer_last_seen_too_long_ago_is_a_dead_letter_and_allows_the_stop_with_an_error_row(tmp_path):
    """Catches: R2-20: a stale orderer (last seen beyond the dead-letter hours): a loop, a block, or no error row."""
    root = world(tmp_path)
    seen(root, "stale-lead", when=_ago(30 * 24 * 3600))
    _ordered_by(root, "stale-lead")
    _prompt(root)
    out = _out(_stop(root))
    assert (out.get("decision"), "continue" in out, len(_errors(root)), _inbox(root, "stale-lead")) == (None, False, 1, [])


def test_the_role_line_is_the_one_line_of_the_order_with_the_tag_the_role_file_needs():
    """Pins: (g): the line is the order's sentence, exactly, after the tag `[end-turn-with-send]` every role-file line needs."""
    from pathlib import Path
    text = (Path(__file__).resolve().parents[2] / "engine" / "roles" / "builder.md").read_text(encoding="utf-8")
    line = ("- [end-turn-with-send] Your reader is your orderer, not a person at the screen: end every turn with `mkway send` to "
            "your orderer (your question, your result, or what you wait for).")
    assert line in text.splitlines()


def test_a_session_with_no_row_at_all_is_not_judged_and_leaves_one_record_row(tmp_path):
    """Checks: R340a: no row of the session at all: nothing is judged, nothing is written to the orderer, one record row says so."""
    root = world(tmp_path)
    out = _out(_stop(root))
    assert (out.get("decision"), "continue" in out, _inbox(root), len(_rows(root, "handoff-no-turn-start"))) == (None, False, [], 1)


def test_the_way_out_of_handoff_no_turn_start_is_one_record_row_and_no_block(tmp_path):
    """Checks: the record row names the session and its card; the stop is allowed and nothing blocks."""
    root = world(tmp_path)
    out = _out(_stop(root))
    (row,) = _rows(root, "handoff-no-turn-start")
    assert (out.get("decision"), row["session"], row["card"], row["kind"], _inbox(root)) == (None, BUILDER, CARD, "log", [])


def _replay_of_the_live_builder(root, with_send):
    """The sequence of the live builder (R340a): a first prompt; a stop that is noticed and answered; a peer wake; a send; a peer
    message that arrives mid-turn (it writes a prompt row too); then the stop of that turn."""
    _prompt(root)
    _stop(root)
    _stop(root, active=True)
    _prompt(root)
    if with_send:
        send(root, BUILDER, LEAD, "question", "my own report")
    _prompt(root)
    return _out(_stop(root))


def test_a_send_before_a_mid_turn_peer_message_still_counts_so_the_stop_writes_no_notice(tmp_path):
    """Catches: R340a (1): the live replay: a peer message mid-turn writes a prompt row and a send before it fell outside the turn (a false notice)."""
    root = world(tmp_path)
    out = _replay_of_the_live_builder(root, True)
    assert (out.get("decision"), len(_inbox(root)), len(_rows(root, "handoff-notice"))) == (None, 2, 1)


def test_the_same_replay_with_no_send_writes_the_notice_and_blocks(tmp_path):
    """Checks: R340a (1): the same sequence with no send is a silent turn end: a second notice and a block."""
    root = world(tmp_path)
    out = _replay_of_the_live_builder(root, False)
    assert (out.get("decision"), len(_inbox(root)), len(_rows(root, "handoff-notice"))) == ("block", 2, 2)


def test_a_stop_our_group_allowed_then_a_continued_stop_keeps_the_boundary_and_no_false_notice(tmp_path):
    """Catches: R340a (2): a handoff, a stop our group allowed, then a stop continued because another hook blocked: no false notice."""
    root = world(tmp_path)
    _prompt(root)
    send(root, BUILDER, LEAD, "question", "my own report")
    _stop(root)
    out = _out(_stop(root, active=True))
    assert (out.get("decision"), [r["body"] for r in _inbox(root)], _rows(root, "handoff-notice")) == (None, ["my own report"], [])


def test_a_session_with_stop_rows_but_no_prompt_row_is_not_judged_and_leaves_a_record_row(tmp_path):
    """Checks: R340a with the MW-128 guard: no prompt row of the session in the records means the engine saw no turn begin: one record row, nothing judged."""
    root = world(tmp_path)
    _timing_row(root, BUILDER, _ago(60))
    _timing_row(root, BUILDER, _ago(30))
    out = _out(_stop(root))
    assert (out.get("decision"), _inbox(root), len(_rows(root, "handoff-no-turn-start"))) == (None, [], 1)


def test_a_session_with_rows_but_no_prompt_row_has_no_turn_start(tmp_path):
    """Pins: the boundary reader returns none when the session holds timing rows but no UserPromptSubmit row among them."""
    root = world(tmp_path)
    _timing_row(root, BUILDER, _ago(60))
    _timing_row(root, BUILDER, _ago(30))
    assert gatemode.handoff_turn(state(root), BUILDER) is None


# ---- reader 3 of 17.11: the gaps of the turn boundary and of the no-turn-start row ---------------------------------------------

def _a_turn_with_a_send_then_a_turn_whose_stop_another_gate_refused(root):
    """Turn 1: a prompt, a send to the orderer, a stop that passes. Turn 2: a prompt, then a Stop run of the `stop` group that
    another gate refused (it leaves its timing row, flag false). The next stop is the hook's continuation of it."""
    _prompt(root)
    send(root, BUILDER, LEAD, "question", "my own report")
    _stop(root)
    _prompt(root)
    _timing_row(root, BUILDER, _ago(0))


def test_a_continued_stop_in_a_later_turn_starts_after_the_stop_before_its_chain_not_at_the_first_row(tmp_path):
    """Catches: reader 3 (8a): a rule «a continued stop starts at the session's first row» counts turn 1's send for turn 2 and misses the silent turn."""
    root = world(tmp_path)
    _a_turn_with_a_send_then_a_turn_whose_stop_another_gate_refused(root)
    out = _out(_stop(root, active=True))
    assert (out.get("decision"), len(_inbox(root)), [r["blocked"] for r in _rows(root, "handoff-notice")]) == (None, 2, [False])


def test_two_flag_less_stop_rows_read_as_false_so_a_continued_stop_starts_after_the_earlier_one(tmp_path):
    """Pins: reader 3 (6): a Stop row written before MW-132 has no flag and reads as false: it ends a turn, it continues nothing."""
    root = world(tmp_path)
    _timing_row(root, BUILDER, _ago(90), event="UserPromptSubmit", group="prompt")
    earlier = _ago(60)
    _timing_row(root, BUILDER, earlier)
    _timing_row(root, BUILDER, _ago(30))
    assert gatemode.handoff_turn(state(root), BUILDER, True) == _text(earlier)


def test_a_plain_stop_after_two_flag_less_stop_rows_starts_at_the_latest_of_them(tmp_path):
    """Pins: reader 3 (6): with the current stop's flag false the boundary is the latest flag-less Stop row."""
    root = world(tmp_path)
    _timing_row(root, BUILDER, _ago(90), event="UserPromptSubmit", group="prompt")
    _timing_row(root, BUILDER, _ago(60))
    latest = _ago(30)
    _timing_row(root, BUILDER, latest)
    assert gatemode.handoff_turn(state(root), BUILDER, False) == _text(latest)


def test_a_session_with_a_prompt_row_writes_no_no_turn_start_row(tmp_path):
    """Checks: reader 3 (7): the record row is for a session the engine saw no turn of; one with a prompt row leaves none."""
    root = world(tmp_path)
    _prompt(root)
    _stop(root)
    assert _rows(root, "handoff-no-turn-start") == []


def test_another_sessions_prompt_row_is_no_turn_start_of_this_session(tmp_path):
    """Catches: reader 3 (7): a prompt row of another session in the same records taken as the start of this session's turn."""
    root = world(tmp_path)
    _timing_row(root, OTHER_LEAD, _ago(60), event="UserPromptSubmit", group="prompt")
    _timing_row(root, BUILDER, _ago(30))
    out = _out(_stop(root))
    assert (out.get("decision"), _inbox(root), len(_rows(root, "handoff-no-turn-start"))) == (None, [], 1)
