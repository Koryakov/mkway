"""Card MW-110 (concept line 3): every refusal of the send tool names a way out, and one test per reason proves the way out
works: the refused call is made, then the step the refusal names, and the second call goes through. Synthetic sessions and
roots only (the helpers of the messaging tests); each test has its own task root."""
import datetime
import json

import pytest

from _engine import cli, gate_call, jsonl, write_profile
from _mw018 import id_of, register_lead, rows_of, seen, send, session_run, state, world
from _mw110 import denied, hook_shell
import dispatch
import gate_message
import gate_ping

NAME = "MKWAY_SESSION_ID"


def _reason(err):
    import re
    found = re.search(r"mkway: ([a-z-]+):", err)
    return found.group(1) if found else None


def _sent(root, sender, to, kind="order", text="build the thing"):
    code, out, err = send(root, sender, to, kind, text)
    assert code == 0, err
    return id_of(out)


def _body(root, text="a note"):
    (root / "body.txt").write_text(text, encoding="utf-8")


def test_way_out_inbox_not_yours(tmp_path):
    """Checks: `inbox-not-yours` names `mkway board`, which lists the session's own rows; the recipient reads the row."""
    root = world(tmp_path)
    row = _sent(root, "lead-a", "build-a1")
    code, _out, err = session_run(root, "build-a2", "inbox", row)
    board_code, board, _berr = session_run(root, "build-a1", "board")
    read_code, shown, read_err = session_run(root, "build-a1", "inbox", row)
    assert (code, _reason(err)) == (1, "inbox-not-yours")
    assert (board_code, row in board, read_code, "build the thing" in shown) == (0, True, 0, True), read_err


def test_way_out_inbox_unknown(tmp_path):
    """Checks: `inbox-unknown` names `mkway board`, which lists the unacked rows with their ids; the listed id is read."""
    root = world(tmp_path)
    row = _sent(root, "lead-a", "build-a1")
    code, _out, err = session_run(root, "build-a1", "inbox", "m-nothing")
    _board_code, board, _berr = session_run(root, "build-a1", "board")
    read_code, shown, read_err = session_run(root, "build-a1", "inbox", row)
    assert (code, _reason(err)) == (1, "inbox-unknown")
    assert (row in board, read_code, "build the thing" in shown) == (True, 0, True), read_err


def test_way_out_message_ambiguous(tmp_path):
    """Checks: `message-ambiguous` asks for more of the id; the whole id is delivered."""
    root = world(tmp_path)
    code, _out, err = send(root, "lead-a", "build-a", "order", "which one?")
    again, _out2, err2 = send(root, "lead-a", "build-a1", "order", "which one?")
    assert (code, _reason(err)) == (1, "message-ambiguous")
    assert (again, len(rows_of(root, "build-a1"))) == (0, 1), err2


def test_way_out_message_dead_letter(tmp_path):
    """Checks: `message-dead-letter` says to send again to a session that is alive; once it is seen again the send goes."""
    root = world(tmp_path)
    register_lead(root, "lead-c")
    seen(root, "lead-c", when=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=13))
    code, _out, err = send(root, "lead-a", "lead-c", "notice", "are you there?")
    seen(root, "lead-c")
    again, _out2, err2 = send(root, "lead-a", "lead-c", "notice", "are you there?")
    assert (code, _reason(err)) == (1, "message-dead-letter")
    assert (again, len(rows_of(root, "lead-c"))) == (0, 1), err2


def test_way_out_message_duplicate(tmp_path):
    """Checks: `message-duplicate` asks for a body written for this recipient; a different body is delivered."""
    root = world(tmp_path)
    _sent(root, "lead-a", "build-a1", text="build the thing")
    code, _out, err = send(root, "lead-a", "build-a2", "order", "build the thing")
    again, _out2, err2 = send(root, "lead-a", "build-a2", "order", "build the other thing")
    assert (code, _reason(err)) == (1, "message-duplicate")
    assert (again, len(rows_of(root, "build-a2"))) == (0, 1), err2


def test_way_out_message_duplicate_second_ping(tmp_path):
    """Checks: the ping side of `message-duplicate` (a fix of the pre-merge readers): the first ping of a row is allowed, the
    second is refused with the text that says to write another row; the new row's first ping is allowed."""
    root = world(tmp_path)
    first = _sent(root, "lead-a", "build-a1", text="build the thing")

    def ping(row_id):
        return gate_call(gate_message.check, root, tool="SendMessage", session="lead-a",
                         tool_input={"to": "x", "message": f"mkway inbox {row_id}"})
    allowed, refused = ping(first), ping(first)
    second = _sent(root, "lead-a", "build-a1", text="and one more thing")
    again = ping(second)
    assert (allowed.kind, refused.kind, refused.reason_id, again.kind) == ("allow", "refuse", "message-duplicate", "allow")
    assert "mkway send" in refused.message


def test_way_out_message_empty(tmp_path):
    """Checks: `message-empty` asks for text in the body file; a file with text is delivered."""
    root = world(tmp_path)
    code, _out, err = send(root, "lead-a", "lead-b", "notice", "  \n")
    again, _out2, err2 = send(root, "lead-a", "lead-b", "notice", "now with words")
    assert (code, _reason(err)) == (1, "message-empty")
    assert (again, len(rows_of(root, "lead-b"))) == (0, 1), err2


def test_way_out_message_no_file(tmp_path):
    """Checks: `message-no-file` says to write the message into a file and name it with `--file`; the written file is sent."""
    root = world(tmp_path)
    args = ("send", "--to", "lead-b", "--kind", "notice", "--file", "later.txt")
    code, _out, err = session_run(root, "lead-a", *args)
    (root / "later.txt").write_text("written now", encoding="utf-8")
    again, _out2, err2 = session_run(root, "lead-a", *args)
    assert (code, _reason(err)) == (1, "message-no-file")
    assert (again, rows_of(root, "lead-b")[0]["body"]) == (0, "written now"), err2


def test_way_out_message_no_session(tmp_path):
    """Checks: `message-no-session` names the launcher line; a session whose launcher set the variable sends."""
    root = world(tmp_path)
    _body(root)
    args = ("send", "--to", "lead-a", "--kind", "notice", "--file", "body.txt")
    code, _out, err = cli(root, *args, session=True)
    again, _out2, err2 = cli(root, *args, session=True, env={NAME: "build-a1"})
    assert (code, _reason(err)) == (1, "message-no-session")
    assert (again, rows_of(root, "lead-a")[-1]["from"]) == (0, "build-a1"), err2


def test_way_out_message_reply_unknown(tmp_path):
    """Checks: `message-reply-unknown` says `--reply-to` names a row addressed to the sender; the real row id is accepted."""
    root = world(tmp_path)
    asked = _sent(root, "lead-a", "build-a1", kind="question", text="which file?")
    code, _out, err = send(root, "build-a1", "lead-a", "answer", "this one", "--reply-to", "m-nothing")
    again, _out2, err2 = send(root, "build-a1", "lead-a", "answer", "this one", "--reply-to", asked)
    assert (code, _reason(err)) == (1, "message-reply-unknown")
    assert (again, rows_of(root, "lead-a")[-1]["reply_to"]) == (0, asked), err2


def test_way_out_message_text_unsafe(tmp_path):
    """Checks: `message-text-unsafe` says to put the message in a file and pass `--file`; the file form is delivered."""
    root = world(tmp_path)
    code, _out, err = cli(root, "send", "--to", "lead-b", "--kind", "notice", "--text", "a $(b) c", session=True,
                          env={NAME: "lead-a"})  # the lock gate stops this shape first; the engine's own refusal is shown here
    again, _out2, err2 = send(root, "lead-a", "lead-b", "notice", "a $(b) c")
    assert (code, _reason(err)) == (1, "message-text-unsafe")
    assert (again, rows_of(root, "lead-b")[-1]["body"]) == (0, "a $(b) c"), err2


def test_way_out_message_text_unsafe_real_path(tmp_path):
    """Checks: what a session really gets (a fix of the pre-merge readers). A double-quoted text with `$(` is stopped by the
    lock gate first, as `engine-call-not-plain`, whose text says to run the call alone in its plain form. The same text in
    single quotes is literal for the shell, so the hook lets it through and the engine's own refusal is what the session
    reads: `message-text-unsafe`, which says to put the message in a file and pass `--file`; the file form is delivered."""
    root = world(tmp_path)
    head = "python mkway/engine/mkway.py send --to lead-b --kind notice --text "
    double = hook_shell(root, head + '"a $(b) c"', "lead-a", {NAME: "lead-a"})
    single = hook_shell(root, head + "'a $(b) c'", "lead-a", {NAME: "lead-a"})
    code, _out, err = cli(root, "send", "--to", "lead-b", "--kind", "notice", "--text", "a $(b) c", session=True,
                          env={NAME: "lead-a"})
    again, _out2, err2 = send(root, "lead-a", "lead-b", "notice", "a $(b) c")
    assert denied(double).startswith("[mkway lock.shell engine-call-not-plain] ")
    assert denied(single) is None
    assert (code, _reason(err)) == (1, "message-text-unsafe")
    assert "--file" in err
    assert (again, rows_of(root, "lead-b")[-1]["body"]) == (0, "a $(b) c"), err2


def test_way_out_message_topology(tmp_path):
    """Checks: `message-topology` names the lead of the builder's card; the send to that lead is delivered."""
    root = world(tmp_path)
    code, _out, err = send(root, "build-a1", "build-a2", "question", "may I?")
    again, _out2, err2 = send(root, "build-a1", "lead-a", "question", "may I?")
    assert (code, _reason(err)) == (1, "message-topology")
    assert "lead-a" in err
    assert (again, len(rows_of(root, "lead-a"))) == (0, 1), err2


def test_way_out_send_session_only(tmp_path):
    """Checks: `send-session-only` says the owner tells a lead through a session; the session's send is delivered."""
    root = world(tmp_path)
    _body(root)
    code, _out, err = cli(root, "send", "--to", "lead-a", "--kind", "notice", "--file", "body.txt")
    again, _out2, err2 = send(root, "build-a1", "lead-a", "notice", "the owner asks for the status")
    assert (code, _reason(err)) == (1, "send-session-only")
    assert (again, len(rows_of(root, "lead-a"))) == (0, 1), err2


def _stop(root, written, ping, name):
    """The Stop of `build-a1` with a transcript of the turn: the send, then a SendMessage with the text `ping` (None: none)."""
    return gate_call(gate_ping.stop, root, tool=None, session="build-a1", event="Stop", gate="ping.stop",
                     hook_input={"transcript_path": _transcript(root, written["ts"], ping, name), "stop_hook_active": False})


def _written(tmp_path):
    root = world(tmp_path)
    _sent(root, "build-a1", "lead-a", kind="result", text="the card is finished")
    return root, jsonl(state(root) / "inbox-writes.jsonl")[-1]


def test_way_out_ping_not_sent(tmp_path):
    """Checks: `ping-not-sent` names the ping line to send with SendMessage; with exactly that line, the id of the written
    row, in the transcript the Stop passes."""
    root, written = _written(tmp_path)
    refused = _stop(root, written, None, "none")
    passed = _stop(root, written, f"mkway inbox {written['id']}", "exact")
    assert (refused.kind, refused.reason_id) == ("refuse", "ping-not-sent")
    assert f"mkway inbox {written['id']}" in refused.message
    assert passed.kind == "allow"


@pytest.mark.parametrize("ping", [
    pytest.param("mkway inbox m-20200101000000-aaaaaa", id="a-ping-for-another-id"),
    pytest.param("the report is in your inbox, please read it", id="free-text-only"),
    pytest.param("mkway inbox WRITTEN and please read it", id="the-ping-line-with-more-words"),
    pytest.param("mkway inbox WRITTENx", id="the-id-with-more-characters"),
    pytest.param("mkway inbox", id="the-line-with-no-id"),
    pytest.param(" mkway inbox WRITTEN", id="a-leading-space"),
    pytest.param("mkway inbox WRITTEN ", id="a-trailing-space"),
])
def test_a_message_that_is_not_the_exact_ping_line_of_the_write_does_not_let_the_stop_pass(tmp_path, ping):
    """Catches: R279a: a SendMessage taken as the ping of a write whatever it says (a ping for another row, free text, the
    line with words around it): the Stop is refused again and names the written row's own ping line."""
    root, written = _written(tmp_path)
    got = _stop(root, written, ping.replace("WRITTEN", written["id"]), "other")
    assert (got.kind, got.reason_id) == ("refuse", "ping-not-sent")
    assert f"mkway inbox {written['id']}" in got.message


def test_the_exact_ping_line_with_a_final_line_break_lets_the_stop_pass(tmp_path):
    """Checks: the nearest allow of the refusals above: the exact line of the write's id, a final line break allowed, as the
    send gate reads it."""
    root, written = _written(tmp_path)
    assert _stop(root, written, f"mkway inbox {written['id']}\n", "break").kind == "allow"


def test_free_text_after_an_inbox_write_then_the_stop_is_refused_and_the_ping_after_it_passes(tmp_path):
    """Catches: R279a: a builder that writes to the inbox, says something in free text and stops (the text is allowed by the
    send gate since MW-110) is let go; the ping line sent after the free text is what lets the Stop pass."""
    root, written = _written(tmp_path)
    free = _stop(root, written, "I have finished, see the inbox", "free")
    line = _stop(root, written, f"mkway inbox {written['id']}", "line")
    assert (free.kind, free.reason_id) == ("refuse", "ping-not-sent")
    assert line.kind == "allow"


def _stamp(text, seconds):
    when = datetime.datetime.fromisoformat(text) + datetime.timedelta(seconds=seconds)
    return when.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _transcript(root, written_at, ping, name):
    def use(cid, tool, ts, **inp):
        return {"type": "assistant", "timestamp": ts,
                "message": {"content": [{"type": "tool_use", "id": cid, "name": tool, "input": inp}]}}
    rows = [{"type": "user", "timestamp": _stamp(written_at, -5), "message": {"content": "finish the card"}},
            use("t1", "Bash", _stamp(written_at, -1), command="python mkway/engine/mkway.py send --to x --kind result"),
            {"type": "user", "timestamp": _stamp(written_at, 1),
             "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": "sent"}]}}]
    if ping is not None:
        rows.append(use("p1", "SendMessage", _stamp(written_at, 3), to="lead", message=ping))
    path = root.parent / f"turn-{name}.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return str(path)


def _gate(root, session, command, env):
    ctx = dispatch.make_context(profile=json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8")),
                                root=root, session_id=session, event="PreToolUse", gate="message.session",
                                tool_name="Bash", tool_input={"command": command}, budget_seconds=None,
                                once=lambda targets: True, env=env)
    return gate_message.session("PreToolUse", ctx)


def test_way_out_session_id_mismatch(tmp_path):
    """Checks: `session-id-mismatch` names the launcher line, which sets the variable to the session's own id; with the
    variable equal to the hook's id the same call passes."""
    root = world(tmp_path)
    command = "python mkway/engine/mkway.py send --to lead-a --kind notice --file body.txt"
    refused = _gate(root, "build-a1", command, {NAME: "lead-b"})
    passed = _gate(root, "build-a1", command, {NAME: "build-a1"})
    assert (refused.kind, refused.reason_id) == ("refuse", "session-id-mismatch")
    assert "--session-id" in refused.message
    assert passed.kind == "allow"


def test_way_out_session_id_unverified(tmp_path):
    """Checks: `session-id-unverified` (R279) says the variable alone proves nothing after the end date and names a session
    with the hooks and the launcher line; the same send in a session with the hooks (the lock gate's permit under the
    session's own id) and the launcher's variable goes (R279c: with no variable the end date refuses too)."""
    root = world(tmp_path)
    _body(root)
    profile = json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))
    profile["messaging"] = {"session_id_watch_until": "2020-01-01"}
    write_profile(root, profile)
    code, _out, err = cli(root, "send", "--to", "lead-a", "--kind", "notice", "--file", "body.txt", session=True,
                          env={NAME: "build-a1"})
    from _engine import gate_call
    import gate_lock
    plain = "python mkway/engine/mkway.py send --to lead-a --kind notice --file body.txt"
    gate_call(gate_lock.check, root, tool="Bash", tool_input={"command": plain}, session="build-a1")
    again, _out2, err2 = cli(root, "send", "--to", "lead-a", "--kind", "notice", "--file", "body.txt", session=True,
                             env={NAME: "build-a1"})
    assert (code, _reason(err)) == (1, "session-id-unverified")
    assert "hooks" in err
    assert "--session-id" in err
    assert (again, rows_of(root, "lead-a")[-1]["from"]) == (0, "build-a1"), err2


def test_way_out_send_record_failed(tmp_path):
    """Checks: `send-record-failed` (R279c Q3) names the record file and says the way out is the state folder; once the folder
    can be written the same send is recorded first and delivered."""
    root = world(tmp_path)
    blocked = state(root) / "message-record.jsonl"
    blocked.mkdir()  # a folder where the file belongs: appending to it fails
    code, _out, err = send(root, "lead-a", "build-a1", "order", "build the thing")
    refused_rows = rows_of(root, "build-a1")
    blocked.rmdir()  # the way out: the state folder can be written again
    again, _out2, err2 = send(root, "lead-a", "build-a1", "order", "build the thing")
    assert (code, _reason(err)) == (1, "send-record-failed")
    assert "message-record.jsonl" in err
    assert "state folder" in err
    assert refused_rows == []
    assert (again, len(rows_of(root, "build-a1"))) == (0, 1), err2
    assert [r["event"] for r in jsonl(state(root) / "message-record.jsonl")] == ["send"]


def test_way_out_session_id_unset(tmp_path):
    """Checks: the `session-id-unset` warn names the launcher line; once the variable is set the warn is gone."""
    root = world(tmp_path)
    command = "git status"
    warned = _gate(root, "build-a1", command, {})
    set_now = _gate(root, "build-a1", command, {NAME: "build-a1"})
    assert (warned.kind, warned.reason_id) == ("warn", "session-id-unset")
    assert "--session-id" in warned.message
    assert set_now.kind == "allow"
