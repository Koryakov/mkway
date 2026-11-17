"""Card MW-076 (decisions: R185 to R188): the shell of the ping gate reads its facts from real files (the lead register,
mkcl's sessions file, the engine's record of inbox writes, the shared inbox, a transcript) and writes what the verdict
says. The decisions are proven by `tests/core/test_ping_decide.py`; here one test id proves one fact is read right or one
wire is connected, on a synthetic task root. Every test runs under 20 s. Synthetic roots and session ids only."""
import datetime
import json
import re

import pytest

from _engine import gate_call, jsonl
from _mw018 import ping_of, send, session_run, state, world
import gate_message
import gate_ping
import leads
import profiles

CLAUSE = "if SendMessage is not loaded, load it first with ToolSearch query select:SendMessage"


def _shared(root):
    return state(root)


def _profile(root):
    return json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))


def _set_profile(root, **keys):
    profile = _profile(root)
    profile.update(keys)
    (root / "mkway" / "profile.json").write_text(json.dumps(profile), encoding="utf-8")


def _name_the_lead(root, lead, name):
    path = _shared(root) / "leads.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for row in data["leads"]:
        if row["session_id"] == lead:
            row["name"] = name
    path.write_text(json.dumps(data), encoding="utf-8")


def _sessions_file(root, *rows):
    path = root.parent / "mkcl-sessions.json"
    path.write_text(json.dumps({"version": 1, "sessions": list(rows)}), encoding="utf-8")
    _set_profile(root, sessions={"file": str(path)})
    return path


def _damaged_file(root):
    (root.parent / "bad.json").write_text("{not json", encoding="utf-8")
    _set_profile(root, sessions={"file": str(root.parent / "bad.json")})


def _stamp(text, seconds):
    when = datetime.datetime.fromisoformat(text) + datetime.timedelta(seconds=seconds)
    return when.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _transcript(root, written_at, *, pinged=False, name="turn.jsonl", row_id=None):  # changed by MW-110 (decision MW110-D3): the ping names the written row
    """A transcript of one turn: the user message just before the write, a Bash call around it, and, with `pinged`, a
    SendMessage call after it."""
    def use(cid, tool, ts, **inp):
        return {"type": "assistant", "timestamp": ts,
                "message": {"content": [{"type": "tool_use", "id": cid, "name": tool, "input": inp}]}}
    rows = [{"type": "user", "timestamp": _stamp(written_at, -5), "message": {"content": "finish the card"}},
            use("t1", "Bash", _stamp(written_at, -1), command="python mkway/engine/mkway.py send --to x --kind result"),
            {"type": "user", "timestamp": _stamp(written_at, 1),
             "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": "sent"}]}}]
    if pinged:
        rows.append(use("p1", "SendMessage", _stamp(written_at, 3), to="lead", message=f"mkway inbox {row_id}"))
    path = root.parent / name
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return str(path)


def _stop(root, session, transcript, *, active=False):
    return gate_call(gate_ping.stop, root, tool=None, session=session, event="Stop", gate="ping.stop",
                     hook_input={"transcript_path": transcript, "stop_hook_active": active})


def _sent(tmp_path, *, sender="build-a1", to="lead-a"):
    """A world where `sender` has just sent a result to `to`: (root, the record row of that write)."""
    root = world(tmp_path)
    code, out, err = send(root, sender, to, "result", "the card is finished")
    assert code == 0, err
    return root, jsonl(_shared(root) / "inbox-writes.jsonl")[-1]


# ---- the engine's record of inbox writes ---------------------------------------------------------------------------

def test_a_send_writes_one_record_row_with_the_writing_session(tmp_path):
    """Checks: `mkway send` records its inbox write: id, from (the hook's session id), to, kind and a time."""
    root, record = _sent(tmp_path)
    inbox_id = ping_of(send(root, "build-a2", "lead-a", "question", "a question")[1]).split()[-1]
    rows = jsonl(_shared(root) / "inbox-writes.jsonl")
    assert (record["from"], record["to"], record["kind"]) == ("build-a1", "lead-a", "result")
    assert set(record) == {"id", "from", "to", "kind", "ts"}
    assert rows[-1]["id"] == inbox_id


def test_a_dead_letter_notice_is_recorded_as_a_write_of_the_engine(tmp_path):
    """Checks: a notice the engine writes (U05, the dead letter to the sender's lead) is in the record, from `engine`."""
    root = world(tmp_path)
    code, _out, _err = send(root, "build-a1", "nobody-here", "question", "anyone there?")
    rows = jsonl(_shared(root) / "inbox-writes.jsonl")
    assert code != 0
    assert [(r["from"], r["to"], r["kind"]) for r in rows] == [("engine", "lead-a", "notice")]


def test_an_appetite_notice_is_recorded_as_a_write_of_the_engine(tmp_path):
    """Checks: any `append_notice` of the engine (U07 and the others) goes through the one recorded writer."""
    root = world(tmp_path)
    leads.append_notice(_shared(root), "lead-a", "a card is past its Appetite")
    rows = jsonl(_shared(root) / "inbox-writes.jsonl")
    assert [(r["from"], r["to"], r["kind"]) for r in rows] == [("engine", "lead-a", "notice")]


# ---- `mkway send` prints the name (R185, R188) ---------------------------------------------------------------------

def test_send_prints_the_name_from_the_lead_register_and_no_listagents_line(tmp_path):
    """Checks: a name in the lead register row makes the printed line ready to paste: the clause, the name, the ping."""
    root = world(tmp_path)
    _name_the_lead(root, "lead-a", "dd-lead")
    _code, out, _err = send(root, "build-a1", "lead-a", "result", "the card is finished")
    line = ping_of(out)
    assert f"ping: {CLAUSE}; then SendMessage to dd-lead: {line}" in out.splitlines()
    assert "ListAgents" not in out


def test_send_reads_the_name_from_the_sessions_file_by_the_card_of_the_sender(tmp_path):
    """Checks: with no name in the register, the profile's `sessions.file` gives the `starter` of the sender's card."""
    root = world(tmp_path)
    card = re.search(r"CARD-\d{3}", " ".join(p.name for p in (root / "mkway" / "cards").iterdir())).group(0)
    _sessions_file(root, {"name": "b", "starter": "dd-starter", "kind": "builder", "card": card, "state": "alive"})
    _code, out, _err = send(root, "build-a1", "lead-a", "result", "the card is finished")
    assert f"then SendMessage to dd-starter: {ping_of(out)}" in out
    assert "ListAgents" not in out


def test_the_register_name_wins_over_the_sessions_file(tmp_path):
    """Checks: the order of R185: the lead register first, the sessions file second."""
    root = world(tmp_path)
    _name_the_lead(root, "lead-a", "dd-lead")
    _sessions_file(root, {"name": "b", "starter": "other-name", "kind": "builder", "card": "CARD-001", "state": "alive"})
    _code, out, _err = send(root, "build-a1", "lead-a", "result", "the card is finished")
    assert "then SendMessage to dd-lead: " in out
    assert "other-name" not in out


@pytest.mark.parametrize("make", [
    pytest.param(lambda root: _set_profile(root, sessions={"file": str(root.parent / "missing.json")}),
                 id="the-file-is-missing"),
    pytest.param(lambda root: _damaged_file(root), id="the-file-is-damaged"),
    pytest.param(lambda root: None, id="no-key-and-no-name"),
])
def test_an_unknown_name_keeps_the_listagents_line_and_the_clause(tmp_path, make):
    """Checks: a send whose name cannot be read still prints the ListAgents line and the clause, so no send fails or prints no way to the lead (the fall-back is silent)."""
    root = world(tmp_path)
    make(root)
    code, out, _err = send(root, "build-a1", "lead-a", "result", "the card is finished")
    assert code == 0
    assert "ListAgents" in out
    assert CLAUSE in out
    assert ping_of(out).startswith("mkway inbox ")


# ---- the Stop gate -------------------------------------------------------------------------------------------------

def test_a_builder_that_sent_and_did_not_ping_is_blocked_with_the_ping_line(tmp_path):
    """Catches: the DD-008 case on real files: the send is in the record, the transcript has no SendMessage after it."""
    root, record = _sent(tmp_path)
    _name_the_lead(root, "lead-a", "dd-lead")
    got = _stop(root, "build-a1", _transcript(root, record["ts"]))
    assert (got.kind, got.reason_id) == ("refuse", "ping-not-sent")
    assert got.message == f"ping your lead: {CLAUSE}; then SendMessage to dd-lead: mkway inbox {record['id']}"


def test_a_builder_that_pinged_after_the_send_is_allowed(tmp_path):
    """Checks: the nearest allow, the transcript has a SendMessage call after the write."""
    root, record = _sent(tmp_path)
    assert _stop(root, "build-a1", _transcript(root, record["ts"], pinged=True, row_id=record["id"])).kind == "allow"


def test_the_second_stop_logs_ping_skipped_and_writes_the_row_for_the_lead(tmp_path):
    """Checks: stop_hook_active true: the Stop passes with a ping-skipped log verdict and one row that names the lead, builder, inbox row and kind."""
    root, record = _sent(tmp_path)
    got = _stop(root, "build-a1", _transcript(root, record["ts"]), active=True)
    rows = jsonl(_shared(root) / "ping-skipped.jsonl")
    assert (got.kind, got.reason_id) == ("log", "ping-skipped")
    assert [(r["builder_session"], r["lead"], r["inbox_id"], r["kind"]) for r in rows] == [
        ("build-a1", "lead-a", record["id"], "result")]


def test_in_watch_mode_the_gate_warns_and_writes_the_row_but_does_not_block(tmp_path):
    """Checks: `gates.ping.mode: watch` in the profile: a warn with the reason line and the record row; the Stop passes."""
    root, record = _sent(tmp_path)
    _set_profile(root, gates={"ping": {"mode": "watch"}})
    got = _stop(root, "build-a1", _transcript(root, record["ts"]))
    assert (got.kind, got.reason_id) == ("warn", "ping-not-sent")
    assert len(jsonl(_shared(root) / "ping-skipped.jsonl")) == 1


@pytest.mark.parametrize("value", ["loud", 3, None, True])
def test_an_unusable_mode_takes_the_default_trip(value):
    """Checks: a bad `gates.ping.mode` never fails the gate: the default `trip` is read."""
    assert profiles.ping_mode({"gates": {"ping": {"mode": value}}}) == "trip"


def test_the_mode_watch_is_read_from_the_profile():
    """Checks: `watch` is the one other value."""
    assert profiles.ping_mode({"gates": {"ping": {"mode": "watch"}}}) == "watch"


def test_an_unreadable_transcript_is_allowed(tmp_path):
    """Checks: a transcript path that cannot be read is no fact: the Stop passes (fails open)."""
    root, _record = _sent(tmp_path)
    assert _stop(root, "build-a1", str(root.parent / "no-such-transcript.jsonl")).kind == "allow"


def test_a_lead_is_not_judged_for_its_own_send(tmp_path):
    """Checks: a registered lead that sent with no ping is exempt at its own Stop."""
    root, record = _sent(tmp_path, sender="lead-a", to="lead-b")
    assert _stop(root, "lead-a", _transcript(root, record["ts"])).kind == "allow"


# ---- the lead's Stop list (R186 b, R187) ---------------------------------------------------------------------------

def test_the_lead_sees_a_ping_skipped_row_once_at_its_next_stop(tmp_path):
    """Checks: the line of R186 (b) at the lead's Stop, with the builder's name; the same row again is silent."""
    root, record = _sent(tmp_path)
    _stop(root, "build-a1", _transcript(root, record["ts"]), active=True)
    first = _stop(root, "lead-a", str(root.parent / "none.jsonl"))
    second = _stop(root, "lead-a", str(root.parent / "none.jsonl"))
    assert (first.kind, first.reason_id) == ("warn", "ping-skipped-listed")
    assert first.message == f"builder build-a1 wrote to the inbox and did not ping: read mkway inbox {record['id']}"
    assert second.kind == "allow"


def test_another_lead_does_not_see_the_row_of_a_builder_of_lead_a(tmp_path):
    """Checks: the list holds the rows addressed to this lead only."""
    root, record = _sent(tmp_path)
    _stop(root, "build-a1", _transcript(root, record["ts"]), active=True)
    assert _stop(root, "lead-b", str(root.parent / "none.jsonl")).kind == "allow"


def test_an_engine_notice_nobody_pinged_is_listed_once_at_the_leads_stop(tmp_path):
    """Checks: U05: the dead-letter notice has no sending session; the lead's Stop lists it once."""
    root = world(tmp_path)
    send(root, "build-a1", "nobody-here", "question", "anyone there?")
    notice = leads.inbox_rows(_shared(root), "lead-a")[-1]
    first = _stop(root, "lead-a", str(root.parent / "none.jsonl"))
    second = _stop(root, "lead-a", str(root.parent / "none.jsonl"))
    assert first.message == f"the engine wrote a notice that no session pinged: read mkway inbox {notice['id']}"
    assert second.kind == "allow"


# ---- the message gate accepts the ping of an engine notice (R187) -------------------------------------------------

def test_a_session_may_ping_a_notice_the_engine_wrote_for_its_lead(tmp_path):
    """Checks: the message gate accepts the ping of a notice the engine wrote for another session's lead (R187)."""
    # R187 needs the builder to ping the notice the engine wrote in its Bash call; a row from engine addressed to another session
    root = world(tmp_path)
    send(root, "build-a1", "nobody-here", "question", "anyone there?")
    notice = leads.inbox_rows(_shared(root), "lead-a")[-1]
    got = gate_call(gate_message.check, root, tool="SendMessage", session="build-a1",
                    tool_input={"to": "lead-a", "message": f"mkway inbox {notice['id']}"})
    assert got.kind == "allow"


def test_a_ping_line_of_a_row_another_session_wrote_passes_and_is_not_recorded(tmp_path):
    """Catches: MW-110: the ping line of a row another session wrote refused as before, or recorded as that session's ping."""
    root, record = _sent(tmp_path)
    got = gate_call(gate_message.check, root, tool="SendMessage", session="build-a2",
                    tool_input={"to": "lead-a", "message": f"mkway inbox {record['id']}"})
    assert got.kind == "allow"
    assert not (_shared(root) / "pings.jsonl").exists()


# ---- R189: who caused an engine notice (the MW-049 caller), and the release notice -----------------------------------

def _holder_world(tmp_path):
    """The world of the replays: `build-a1` holds CARD-001, which `lead-a` ordered and the owner opened."""
    from _engine import cli
    root = world(tmp_path)
    card = re.search(r"CARD-\d{3}", sorted(p.name for p in (root / "mkway" / "cards").iterdir())[0]).group(0)
    assert cli(root, "card", "open", card)[0] == 0
    return root, card


def test_a_card_set_waiting_notice_carries_the_session_that_caused_it_as_by(tmp_path):
    """Checks: R189 (2): the notice to the orderer names the builder as by, in the inbox row and in the record (MW-049)."""
    # the command and the card id are kept as the fallback; the lock gate's by-permit is the same field
    root, card = _holder_world(tmp_path)
    code, _out, err = session_run(root, "build-a1", "card", "set", card, "waiting")
    record = jsonl(_shared(root) / "inbox-writes.jsonl")[-1]
    row = leads.inbox_rows(_shared(root), "lead-a")[-1]
    assert code == 0, err
    assert (record["from"], record["by"], record["cmd"], record["card"], row["by"]) == (
        "engine", "build-a1", "card set", card, "build-a1")


def test_a_release_by_the_holder_writes_a_notice_to_the_orderer_that_names_the_releaser(tmp_path):
    """Checks: R189 (1): the holder's own `card release` writes a notice to the orderer, with `by` the releaser."""
    root, card = _holder_world(tmp_path)
    code, _out, err = session_run(root, "build-a1", "card", "release", card)
    record = jsonl(_shared(root) / "inbox-writes.jsonl")[-1]
    assert code == 0, err
    assert (record["from"], record["to"], record["by"], record["cmd"], record["card"]) == (
        "engine", "lead-a", "build-a1", "card release", card)


def test_a_dead_letter_notice_carries_the_sender_as_by(tmp_path):
    """Checks: R189 (2): the dead-letter notice to the sender's lead names the sender, who ran the failed send."""
    root = world(tmp_path)
    send(root, "build-a1", "nobody-here", "question", "anyone there?")
    assert jsonl(_shared(root) / "inbox-writes.jsonl")[-1]["by"] == "build-a1"


def test_a_release_with_no_one_holding_the_card_writes_no_notice(tmp_path):
    """Checks: the nearest allow of the release notice: nothing is released, so nothing is written."""
    root, card = _holder_world(tmp_path)
    session_run(root, "build-a1", "card", "release", card)
    before = len(jsonl(_shared(root) / "inbox-writes.jsonl"))
    session_run(root, "build-a1", "card", "release", card)
    assert len(jsonl(_shared(root) / "inbox-writes.jsonl")) == before


def test_the_ping_line_of_an_engine_notice_by_another_session_passes_and_is_not_recorded(tmp_path):
    """Catches: MW-110 (R189 (3) before it): a session other than the `by` of an engine notice that pings it is recorded
    as the pinger; it is no longer refused."""
    root = world(tmp_path)
    send(root, "build-a1", "nobody-here", "question", "anyone there?")
    notice = leads.inbox_rows(_shared(root), "lead-a")[-1]
    got = gate_call(gate_message.check, root, tool="SendMessage", session="build-a2",
                    tool_input={"to": "lead-a", "message": f"mkway inbox {notice['id']}"})
    assert got.kind == "allow"
    assert not (_shared(root) / "pings.jsonl").exists()


# ---- reads and writes at the edges (the rows of the shell that the tests above leave out) -------------------------------

def test_a_stop_with_no_session_id_is_not_judged(tmp_path):
    """Checks: a hook input with no session id names no one, so the gate allows."""
    root, record = _sent(tmp_path)
    assert _stop(root, "", _transcript(root, record["ts"])).kind == "allow"


def test_the_lead_line_names_the_builder_by_its_row_in_the_sessions_file(tmp_path):
    """Checks: the builder's name for the lead's line is the `name` of its live builder row for its card (mkcl's file)."""
    root, record = _sent(tmp_path)
    card = re.search(r"CARD-\d{3}", sorted(p.name for p in (root / "mkway" / "cards").iterdir())[0]).group(0)
    _sessions_file(root, {"name": "dd-008-builder", "starter": "x", "kind": "builder", "card": card, "state": "alive"})
    _stop(root, "build-a1", _transcript(root, record["ts"]), active=True)
    got = _stop(root, "lead-a", str(root.parent / "none.jsonl"))
    assert got.message == f"builder dd-008-builder wrote to the inbox and did not ping: read mkway inbox {record['id']}"


def test_the_same_skipped_ping_is_recorded_once(tmp_path):
    """Checks: two continuation Stops for one write leave one row in `ping-skipped.jsonl`, not two."""
    root, record = _sent(tmp_path)
    _stop(root, "build-a1", _transcript(root, record["ts"]), active=True)
    _stop(root, "build-a1", _transcript(root, record["ts"]), active=True)
    assert len(jsonl(_shared(root) / "ping-skipped.jsonl")) == 1


def test_two_writes_to_the_same_lead_are_both_recorded_with_one_name_lookup(tmp_path):
    """Checks: two sends to one lead in a turn, no ping: both rows are recorded at the continuation Stop."""
    root, record = _sent(tmp_path)
    send(root, "build-a1", "lead-a", "result", "and one more thing")
    _stop(root, "build-a1", _transcript(root, record["ts"]), active=True)
    assert len(jsonl(_shared(root) / "ping-skipped.jsonl")) == 2


def test_damaged_lines_in_the_record_files_are_skipped(tmp_path):
    """Checks: a line that is not JSON, and a JSON line that is not an object, in `ping-skipped.jsonl` are ignored."""
    root, record = _sent(tmp_path)
    (_shared(root) / "ping-skipped.jsonl").write_text("not json\n[1]\n", encoding="utf-8")
    _stop(root, "build-a1", _transcript(root, record["ts"]), active=True)
    assert _stop(root, "lead-a", str(root.parent / "none.jsonl")).reason_id == "ping-skipped-listed"


def test_a_builder_that_wrote_nothing_is_allowed_before_its_transcript_is_read(tmp_path):
    """Checks: no row in the record of inbox writes: the Stop passes at once (the common case costs one file read)."""
    root = world(tmp_path)
    assert _stop(root, "build-a2", str(root.parent / "none.jsonl")).kind == "allow"


def test_a_sessions_file_row_of_another_kind_is_passed_over_when_naming_the_builder(tmp_path):
    """Checks: the name search skips rows that are no live builder row of the card and takes the one that is."""
    root, record = _sent(tmp_path)
    card = re.search(r"CARD-\d{3}", sorted(p.name for p in (root / "mkway" / "cards").iterdir())[0]).group(0)
    _sessions_file(root, {"name": "a-lead", "kind": "lead", "card": None, "state": "alive"},
                   {"name": "dd-b", "starter": "x", "kind": "builder", "card": card, "state": "alive"})
    _stop(root, "build-a1", _transcript(root, record["ts"]), active=True)
    assert jsonl(_shared(root) / "ping-skipped.jsonl")[0]["builder"] == "dd-b"


def test_damaged_lines_in_the_record_of_inbox_writes_are_skipped(tmp_path):
    """Checks: a line that is not JSON, and one that is not an object, before the real rows do not hide them."""
    root = world(tmp_path)
    (_shared(root) / "inbox-writes.jsonl").write_text("not json\n[1]\n", encoding="utf-8")
    code, _out, _err = send(root, "build-a1", "lead-a", "result", "the card is finished")
    record = leads.inbox_writes(_shared(root))
    assert code == 0
    assert [r["from"] for r in record] == ["build-a1"]


def test_a_notice_that_cannot_be_written_never_fails_the_card_move(tmp_path, monkeypatch):
    """Checks: the notice to the orderer is a side effect: when it raises, `card set waiting` still succeeds."""
    root, card = _holder_world(tmp_path)

    def boom(*_args, **_kwargs):
        raise OSError("the inbox is full")
    monkeypatch.setattr(leads, "notify_orderer", boom)
    code, _out, err = session_run(root, "build-a1", "card", "set", card, "waiting")
    assert code == 0, err


# ---- R197 B: an engine notice with no `by` is not pingable ----------------------------------------------------------------

def test_the_ping_line_of_a_notice_with_no_by_passes_and_is_not_recorded(tmp_path):
    """Catches: MW-110 (R197 B before it): the ping line of a notice nobody caused recorded as a ping; no ping is needed
    and none is refused."""
    root = world(tmp_path)
    notice = leads.append_notice(_shared(root), "lead-a", "a card is past its Appetite")
    got = gate_call(gate_message.check, root, tool="SendMessage", session="build-a1",
                    tool_input={"to": "lead-a", "message": f"mkway inbox {notice['id']}"})
    assert got.kind == "allow"
    assert not (_shared(root) / "pings.jsonl").exists()
