"""Card MW-128 (rulings R301, R301a): the shell of the refusal delivery reads its facts from the engine's own records (the calls
log `gate_calls.jsonl`, the timing rows, the register, the message record) and writes what the decision says. The decision is
proven by `tests/core/test_mw128_refusal_core.py`; here one test id proves one fact is read right or one wire is connected, on a
synthetic task root. Every test runs under 20 s. Synthetic roots and session ids only."""
import datetime
import json

import pytest

from _engine import jsonl
from _mw012 import calls as gate_rows, form_entry, make_root, run as run_gate, write_marker
from _mw017 import profile_of
from _mw018 import send, seen, state, world
import dispatch
import gatemode
import messages
import profiles
import register

BUILDER, LEAD, OTHER = "build-a1", "lead-a", "build-a2"
REFUSED_COMMAND = "python mkway/engine/mkway.py card take CARD-002"
ALLOWED_COMMAND = "ls"
ENV_KEYS = {"CLAUDECODE": "1"}


def _fire(root, event, group, session, tool=None, tool_input=None, **extra):
    payload = {"session_id": session, "hook_event_name": event, "cwd": str(root), **extra}
    if tool is not None:
        payload.update(tool_name=tool, tool_input=tool_input)
    return dispatch.run(event, group, json.dumps(payload), env={"CLAUDE_PROJECT_DIR": str(root), **ENV_KEYS})


def _call(root, session, command):
    return _fire(root, "PreToolUse", "shell", session, "Bash", {"command": command})


def _stop(root, session, active=False):
    return _fire(root, "Stop", "stop", session, stop_hook_active=active)


def _out(result):
    return json.loads(result.stdout) if result.stdout else {}


def _refused(root, session=BUILDER):
    """A session's `card take` of a card another session holds: the lock gate refuses it."""
    command = REFUSED_COMMAND if session == BUILDER else REFUSED_COMMAND.replace("CARD-002", "CARD-001")
    result = _call(root, session, command)
    assert _out(result)["hookSpecificOutput"]["permissionDecision"] == "deny"


def _ordered_by(root, who):
    profile = profile_of(root)
    register.set_ordered(root, profile, "CARD-001", who)


def _shared(root):
    return profiles.shared_state_dir(root, profile_of(root))


def _ago(seconds):
    return datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=seconds)


def _text(when):
    return when.isoformat(timespec="milliseconds")


def _call_row(root, session, call_id, when, verdict="allow", event="PreToolUse", **extra):
    row = {"time": _text(when), "gate": "lock.shell", "verdict": verdict, "session": session, "event": event,
           "tool": "Bash", "call": call_id, **extra}
    path = state(root) / "gate_calls.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def _equal_time_rows(root, send_first):
    """A refuse row and a send record of the same session with the SAME time, written in either order."""
    when = _ago(30)
    refusal = dict(verdict="refuse", id="gc-1", target=REFUSED_COMMAND, message="[mkway lock.shell card-not-yours] held")
    record = {"event": "send", "id": "m-x", "session": BUILDER, "to": LEAD, "ts": _text(when)}
    steps = [lambda: _call_row(root, BUILDER, "c1", when, **refusal),
             lambda: (state(root) / "message-record.jsonl").open("a", encoding="utf-8").write(json.dumps(record) + "\n")]
    for step in (steps[::-1] if send_first else steps):
        step()


def _timing_row(root, session, when, event="Stop", group="stop"):
    row = {"time": _text(when), "session": session, "event": event, "group": group, "gates_ms": {}, "total_ms": 1.0}
    path = state(root) / f"timing-{when.strftime('%Y-%m-%d')}.jsonl"
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def test_a_refused_call_leaves_a_gate_refusal_row_with_its_session_call_command_and_text(tmp_path):
    """Catches: a refusal row in the calls log that names no session, no call, no command and no refusal line, so no fact reader can deliver it."""
    root = world(tmp_path)
    _refused(root)
    row = [r for r in jsonl(state(root) / "gate_calls.jsonl") if r.get("verdict") == "refuse"][-1]
    assert (row["session"], row["event"], row["tool"], row["target"]) == (BUILDER, "PreToolUse", "Bash", REFUSED_COMMAND)
    assert row["message"].startswith("[mkway lock.shell ")
    assert row["id"].startswith("gc-")


def test_every_row_of_one_hook_call_shares_one_call_id_and_only_a_refusal_has_a_row_id(tmp_path):
    """Checks: the rows of one dispatcher run carry one call id, and a row id exists only on the refuse row."""
    root = world(tmp_path)
    _call(root, BUILDER, ALLOWED_COMMAND)
    rows = [r for r in jsonl(state(root) / "gate_calls.jsonl") if r.get("session") == BUILDER and r.get("tool") == "Bash"]
    assert len({r["call"] for r in rows}) == 1
    assert [r for r in rows if "id" in r] == []


def test_the_turn_holds_the_calls_of_this_session_after_its_previous_stop(tmp_path):
    """Checks: the calls read for the turn are those of this session at or after its previous Stop timing row, oldest first."""
    root = world(tmp_path)
    _call_row(root, BUILDER, "c0", _ago(60))
    _timing_row(root, BUILDER, _ago(50))
    _call_row(root, BUILDER, "c1", _ago(40))
    _call_row(root, BUILDER, "c2", _ago(30), verdict="refuse", id="gc-2")
    calls = gatemode.turn_calls(state(root), BUILDER)
    assert [(c["call"], c["refused"], c["id"]) for c in calls] == [("c1", False, None), ("c2", True, "gc-2")]


def test_a_refusal_before_the_previous_stop_belongs_to_the_previous_turn(tmp_path):
    """Catches: a refusal of an earlier turn delivered at a later stop, because the turn boundary was not read."""
    root = world(tmp_path)
    _call_row(root, BUILDER, "c1", _ago(40), verdict="refuse", id="gc-1")
    _timing_row(root, BUILDER, _ago(30))
    assert gatemode.turn_calls(state(root), BUILDER) == []


def test_a_prompt_row_of_this_session_is_a_turn_boundary_too(tmp_path):
    """Checks: the UserPromptSubmit timing row starts a turn, as the previous Stop row does."""
    root = world(tmp_path)
    _call_row(root, BUILDER, "c1", _ago(40), verdict="refuse", id="gc-1")
    _timing_row(root, BUILDER, _ago(30), event="UserPromptSubmit", group="prompt")
    assert gatemode.turn_calls(state(root), BUILDER) == []


@pytest.mark.parametrize("other", [
    pytest.param(dict(session=OTHER, event="Stop", group="stop"), id="a-stop-of-another-session"),
    pytest.param(dict(session=BUILDER, event="Stop", group="wake"), id="a-stop-of-the-wake-group"),
    pytest.param(dict(session=BUILDER, event="PreToolUse", group="shell"), id="a-tool-run-is-no-boundary"),
])
def test_a_timing_row_that_is_no_boundary_of_this_session_cuts_nothing(tmp_path, other):
    """Catches: a boundary taken from another session's row, from the wake group's Stop run or from a tool run."""
    root = world(tmp_path)
    _call_row(root, BUILDER, "c1", _ago(40), verdict="refuse", id="gc-1")
    _timing_row(root, other["session"], _ago(30), event=other["event"], group=other["group"])
    assert [c["call"] for c in gatemode.turn_calls(state(root), BUILDER)] == ["c1"]


def test_the_calls_of_another_session_and_the_rows_of_non_tool_events_are_not_engine_calls_of_this_one(tmp_path):
    """Checks: only this session's PreToolUse and PostToolUse rows are its engine calls."""
    root = world(tmp_path)
    _call_row(root, OTHER, "c1", _ago(40), verdict="refuse", id="gc-1")
    _call_row(root, BUILDER, "c2", _ago(30), event="Stop")
    assert gatemode.turn_calls(state(root), BUILDER) == []


def test_a_refusal_in_watch_mode_is_no_gate_refusal_row(tmp_path):
    """Catches: a would-refuse row of a gate in watch mode read as a refusal, when the call went ahead."""
    root = world(tmp_path)
    _call_row(root, BUILDER, "c1", _ago(30), verdict="refuse", id="gc-1", watching=True)
    assert [(c["call"], c["refused"]) for c in gatemode.turn_calls(state(root), BUILDER)] == [("c1", False)]


def test_a_gate_error_row_is_no_gate_refusal_row(tmp_path):
    """Checks: only the verdict refuse is a gate refusal row; an error row of a call is not."""
    root = world(tmp_path)
    _call_row(root, BUILDER, "c1", _ago(30), verdict="error")
    assert [(c["call"], c["refused"]) for c in gatemode.turn_calls(state(root), BUILDER)] == [("c1", False)]


def test_a_missing_calls_log_is_an_empty_turn(tmp_path):
    """Checks: a root with no calls log has no engine call in the turn (no error, no row)."""
    root = world(tmp_path)
    assert gatemode.turn_calls(state(root) / "nowhere", BUILDER) == []


@pytest.mark.parametrize("session, expected", [
    pytest.param(BUILDER, "lead-a", id="the-card-holder-has-the-orderer-of-its-card"),
    pytest.param("free-1", None, id="a-session-with-no-card-has-none"),
])
def test_the_orderer_is_the_orderer_column_of_the_card_the_session_holds(tmp_path, session, expected):
    """Catches: an orderer read from anywhere but the register's orderer column of the card this session holds."""
    root = world(tmp_path)
    assert messages.orderer_of(root, profile_of(root), session) == expected


@pytest.mark.parametrize("who", ["owner", ""])
def test_a_card_ordered_by_the_owner_has_no_orderer(tmp_path, who):
    """Catches: the owner (or an empty cell) taken as a session to write an inbox row to."""
    root = world(tmp_path)
    _ordered_by(root, who)
    assert messages.orderer_of(root, profile_of(root), BUILDER) is None


def test_a_send_of_this_session_is_found_and_the_hooks_own_record_is_not_a_send(tmp_path):
    """Catches: the hook's own inbox write counted as a send, so a refusal it delivered would count as sent by the session."""
    root = world(tmp_path)
    code, _out_text, err = send(root, BUILDER, LEAD, "question", "a real question")
    assert code == 0, err
    sent_id = jsonl(state(root) / "inbox" / f"{LEAD}.jsonl")[-1]["id"]
    hook = messages.send_refusal(root, profile_of(root), _shared(root), BUILDER, LEAD, REFUSED_COMMAND, "[mkway g r] t", "gc-9")
    records = jsonl(state(root) / "message-record.jsonl")
    real = [r["ts"] for r in records if r["event"] == "send" and r["id"] == sent_id]
    assert len(real) == 1
    assert messages.sends_by(_shared(root), BUILDER) == real
    assert [r["event"] for r in records if r["id"] == hook.row["id"]] == ["refusal-delivery"]


def test_the_hooks_inbox_record_reaches_the_orderers_inbox_as_a_notice_from_the_session(tmp_path):
    """Checks: the inbox refusal record is one `notice` row from this session to its orderer, in the orderer's normal inbox."""
    root = world(tmp_path)
    sent = messages.send_refusal(root, profile_of(root), _shared(root), BUILDER, LEAD, REFUSED_COMMAND,
                                 "[mkway lock.shell take-root-busy] held", "gc-9")
    rows = jsonl(state(root) / "inbox" / f"{LEAD}.jsonl")
    assert [(r["id"], r["from"], r["to"], r["kind"]) for r in rows] == [(sent.row["id"], BUILDER, LEAD, "notice")]
    assert "command: " + REFUSED_COMMAND in rows[0]["body"]


def test_the_delivered_ids_are_kept_in_the_state_folder_and_read_back(tmp_path):
    """Checks: a delivered gate refusal row id, and a no-orderer one, are read back from the state folder."""
    root = world(tmp_path)
    gatemode.mark_delivered(state(root), "gc-1", BUILDER, "delivered", "m-1")
    gatemode.mark_delivered(state(root), "gc-2", BUILDER, "no-orderer")
    assert gatemode.delivered_ids(state(root)) == {"gc-1", "gc-2"}


def test_a_stop_with_a_turn_ending_refusal_writes_the_record_and_blocks_with_the_binding_text(tmp_path):
    """Catches: a Stop that lets a turn-ending refusal pass in silence, or blocks with another text than the ruled one."""
    root = world(tmp_path)
    _refused(root)
    out = _out(_stop(root, BUILDER))
    row_id = jsonl(state(root) / "inbox" / f"{LEAD}.jsonl")[-1]["id"]
    assert out == {"decision": "block", "reason": f"your refusal was sent to your orderer as inbox row {row_id}; "
                                                  f"tell your orderer: mkway inbox {row_id}"}


def test_the_way_out_of_refusal_delivered_is_the_ping_line_the_block_names(tmp_path):
    """Checks: the delivered record is in the orderer's inbox, shown by `mkway inbox <id>` with the command and the refusal line."""
    root = world(tmp_path)
    _refused(root)
    _stop(root, BUILDER)
    row_id = jsonl(state(root) / "inbox" / f"{LEAD}.jsonl")[-1]["id"]
    shown = messages.show(_shared(root), LEAD, row_id)
    assert (REFUSED_COMMAND in shown["body"], "[mkway lock.shell " in shown["body"]) == (True, True)


def test_a_second_stop_on_the_same_refusal_blocks_not_and_writes_no_second_record(tmp_path):
    """Catches: a second record or a second block for one gate refusal row id (R301a: once per refusal record id)."""
    root = world(tmp_path)
    _refused(root)
    _stop(root, BUILDER)
    second = _out(_stop(root, BUILDER))
    assert (second.get("decision"), len(jsonl(state(root) / "inbox" / f"{LEAD}.jsonl"))) == (None, 1)


def test_a_stop_that_continues_after_a_hook_writes_the_record_but_does_not_block(tmp_path):
    """Catches: a block when stop_hook_active is true; the record is still written and its id recorded."""
    root = world(tmp_path)
    _refused(root)
    out = _out(_stop(root, BUILDER, active=True))
    assert (out.get("decision"), len(jsonl(state(root) / "inbox" / f"{LEAD}.jsonl")),
            len(gatemode.delivered_ids(state(root)))) == (None, 1, 1)


def test_an_engine_call_after_the_refusal_means_no_delivery(tmp_path):
    """Checks: a session that went on with an allowed engine call after the refusal is allowed to stop, nothing written."""
    root = world(tmp_path)
    _refused(root)
    _call(root, BUILDER, ALLOWED_COMMAND)
    out = _out(_stop(root, BUILDER))
    assert (out.get("decision"), jsonl(state(root) / "inbox" / f"{LEAD}.jsonl")) == (None, [])


def test_a_stop_with_no_refusal_in_the_turn_writes_nothing(tmp_path):
    """Checks: a stop of a session whose turn had no refused engine call is silent (no record, no block)."""
    root = world(tmp_path)
    _call(root, BUILDER, ALLOWED_COMMAND)
    out = _out(_stop(root, BUILDER))
    assert (out.get("decision"), jsonl(state(root) / "inbox" / f"{LEAD}.jsonl")) == (None, [])


def test_the_refusal_of_another_session_is_not_delivered_at_this_sessions_stop(tmp_path):
    """Catches: a Stop that delivers the refusal of another session, read from rows that carry no session."""
    root = world(tmp_path)
    _refused(root, OTHER)
    out = _out(_stop(root, BUILDER))
    assert (out.get("decision"), jsonl(state(root) / "inbox" / f"{LEAD}.jsonl")) == (None, [])


def test_the_way_out_of_refusal_no_orderer_is_one_record_row_and_no_block(tmp_path):
    """Catches: a block, or a missing record row, when the card of the session is ordered by the owner (R301a 3)."""
    root = world(tmp_path)
    _ordered_by(root, "owner")
    _refused(root)
    out = _out(_stop(root, BUILDER))
    rows = [r for r in jsonl(state(root) / "refusals.jsonl") if r.get("reason_id") == "refusal-no-orderer"]
    assert (out.get("decision"), [(r["kind"], r["session"]) for r in rows]) == (None, [("log", BUILDER)])


def test_the_no_orderer_row_is_written_once_per_gate_refusal_row_id(tmp_path):
    """Catches: one no-orderer row for every Stop of the same stopped session."""
    root = world(tmp_path)
    _ordered_by(root, "owner")
    _refused(root)
    _stop(root, BUILDER)
    _stop(root, BUILDER)
    assert len([r for r in jsonl(state(root) / "refusals.jsonl") if r.get("reason_id") == "refusal-no-orderer"]) == 1


def test_the_way_out_of_refusal_delivery_failed_is_the_error_row_that_names_the_refusal(tmp_path):
    """Catches: a failed inbox write that blocks, loops, or leaves no calls-log error row (R301a 2)."""
    root = world(tmp_path)
    _ordered_by(root, "ghost-lead")
    _refused(root)
    out = _out(_stop(root, BUILDER))
    errors = [r for r in jsonl(state(root) / "gate_calls.jsonl") if r.get("reason_id") == "refusal-delivery-failed"]
    assert (out.get("decision"), [(r["verdict"], r["session"]) for r in errors]) == (None, [("error", BUILDER)])


def test_a_failed_inbox_write_is_not_recorded_as_delivered_so_the_next_stop_retries(tmp_path):
    """Catches: an id marked delivered after a failed write, so the orderer never hears of the refusal."""
    root = world(tmp_path)
    _ordered_by(root, "ghost-lead")
    _refused(root)
    _stop(root, BUILDER)
    assert gatemode.delivered_ids(state(root)) == set()


def test_a_failed_inbox_write_tells_the_user_on_the_screen_line_of_the_stop(tmp_path):
    """Checks: the failed write is shown with the Stop's systemMessage, not only logged."""
    root = world(tmp_path)
    _ordered_by(root, "ghost-lead")
    _refused(root)
    out = _out(_stop(root, BUILDER))
    assert "refusal-delivery-failed" in out["systemMessage"]


def test_a_failed_inbox_write_is_a_notice_on_the_start_line_of_this_session_only(tmp_path):
    """Catches: no start-line notice after a failed write, or a notice shown to another session (R301a 2)."""
    root = world(tmp_path)
    _ordered_by(root, "ghost-lead")
    _refused(root)
    _stop(root, BUILDER)
    mine = _out(_fire(root, "SessionStart", "start", BUILDER))["hookSpecificOutput"]["additionalContext"]
    other = _out(_fire(root, "SessionStart", "start", OTHER))["hookSpecificOutput"]["additionalContext"]
    assert ("refusal-delivery-failed" in mine, "refusal-delivery-failed" in other) == (True, False)


def test_the_start_line_notice_ends_once_the_refusal_is_delivered(tmp_path):
    """Checks: after a later stop delivers the refusal, the start line no longer carries the failure notice."""
    root = world(tmp_path)
    _ordered_by(root, "ghost-lead")
    _refused(root)
    _stop(root, BUILDER)
    gatemode.mark_delivered(state(root), next(r["id"] for r in jsonl(state(root) / "gate_calls.jsonl")
                                              if r.get("verdict") == "refuse"), BUILDER, "delivered", "m-1")
    mine = _out(_fire(root, "SessionStart", "start", BUILDER))["hookSpecificOutput"]["additionalContext"]
    assert "refusal-delivery-failed" not in mine


def test_the_target_of_a_refusal_row_is_the_command_head_cut_to_200_characters_with_newlines_as_backslash_n(tmp_path):
    """Catches: a refusal row that keeps the whole command or a raw newline, against the refusal log's rule (MW-061, MW128-D1)."""
    root = world(tmp_path)
    _call(root, BUILDER, REFUSED_COMMAND + "\n# " + "y" * 300)
    row = [r for r in jsonl(state(root) / "gate_calls.jsonl") if r.get("verdict") == "refuse"][-1]
    assert row["target"] == (REFUSED_COMMAND + "\\n# " + "y" * 300)[:200]


def test_the_watching_key_is_on_the_refuse_row_of_a_gate_in_watch_mode_and_nowhere_else(tmp_path):
    """Catches: a refuse row of a gate in watch mode that cannot be told from an enforced refusal (MW128-D1, rule c)."""
    root = make_root(tmp_path)
    write_marker(root, "f1")
    run_gate(root, [form_entry("f1")], "src/bad.py")
    (row,) = gate_rows(root)
    assert set(row) == {"time", "gate", "verdict", "duration_ms", "session", "event", "tool", "call", "id", "target",
                        "message", "reason_id", "watching"}


def test_a_real_send_after_the_refusal_means_no_record_and_no_block(tmp_path):
    """Catches: a session that sent its refusal on itself with `mkway send` told again by the hook, or blocked."""
    root = world(tmp_path)
    _refused(root)
    code, _out_text, err = send(root, BUILDER, LEAD, "question", "my own report of the refusal")
    assert code == 0, err
    out = _out(_stop(root, BUILDER))
    assert (out.get("decision"), [r["body"] for r in jsonl(state(root) / "inbox" / f"{LEAD}.jsonl")]) == (
        None, ["my own report of the refusal"])


@pytest.mark.parametrize("send_first", [True, False])
def test_a_send_with_the_same_time_as_the_refusal_is_not_after_it_in_either_log_order(tmp_path, send_first):
    """Catches: a send of the same millisecond as the refusal, written before or after its row, hiding the refusal."""
    root = world(tmp_path)
    _equal_time_rows(root, send_first)
    out = _out(_stop(root, BUILDER))
    assert (out.get("decision"), len(jsonl(state(root) / "inbox" / f"{LEAD}.jsonl"))) == ("block", 1)


def test_the_next_stop_retries_a_failed_write_once_and_a_third_stop_writes_nothing(tmp_path):
    """Catches: a failed inbox write that is never retried, or retried at every stop (the next stop retries once, never a loop)."""
    root = world(tmp_path)
    _ordered_by(root, "ghost-lead")
    _refused(root)
    first = _out(_stop(root, BUILDER))
    _ordered_by(root, LEAD)
    second = _out(_stop(root, BUILDER))
    third = _out(_stop(root, BUILDER))
    assert (first.get("decision"), second.get("decision"), third.get("decision"),
            len(jsonl(state(root) / "inbox" / f"{LEAD}.jsonl"))) == (None, "block", None, 1)


def test_a_write_that_failed_twice_is_not_retried_a_third_time(tmp_path):
    """Catches: a loop of retries: after one retry that also failed, a later working write still writes nothing."""
    root = world(tmp_path)
    _ordered_by(root, "ghost-lead")
    _refused(root)
    _stop(root, BUILDER)
    _stop(root, BUILDER)
    _ordered_by(root, LEAD)
    out = _out(_stop(root, BUILDER))
    assert (out.get("decision"), jsonl(state(root) / "inbox" / f"{LEAD}.jsonl")) == (None, [])


def test_the_refusal_line_and_the_command_in_the_record_equal_the_gate_refusal_row(tmp_path):
    """Catches: a record whose refusal line or command differs from the row of the calls log in even one character."""
    root = world(tmp_path)
    _refused(root)
    _stop(root, BUILDER)
    row = [r for r in jsonl(state(root) / "gate_calls.jsonl") if r.get("verdict") == "refuse"][-1]
    body = jsonl(state(root) / "inbox" / f"{LEAD}.jsonl")[-1]["body"]
    line = body.split("\nrefusal: ", 1)[1].rsplit("\ngate refusal row: ", 1)[0]
    command = body.split("\ncommand: ", 1)[1].split("\nrefusal: ", 1)[0]
    assert (line, command, body.endswith("gate refusal row: " + row["id"])) == (row["message"], row["target"], True)
