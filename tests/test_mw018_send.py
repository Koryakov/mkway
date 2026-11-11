"""Card MW-018, parts 1 to 4, rows E1 to E8: the order of messages between sessions. A star per card enforced in
`mkway send`; one append-only inbox per session; `mkway send`, `mkway inbox`, `mkway ack`; the dead letter and the
duplicate. A session is known by the hook's session id (the lock gate's one-use permit), never by a name in a text.
Synthetic roots and session ids only."""
import datetime

from _engine import cli, task_root
from _mw018 import (ROW_FIELDS, id_of, inbox, lead_root, lines, new_card, ping_of, profile_of, reason_of, register_lead,
                    seen, send, session_run, state, world)
import messages


def _reason(err):
    return reason_of(err)


# --- E1: the topology --------------------------------------------------------------------------------------------

ALLOWED = [("lead-a", "lead-b"), ("lead-b", "lead-a"), ("lead-a", "build-a1"), ("lead-a", "build-a2"),
           ("build-a1", "lead-a"), ("build-a2", "lead-a"), ("build-b1", "lead-b"), ("free-1", "lead-a"),
           ("free-2", "lead-b")]
REFUSED = [("build-a1", "build-a2"), ("build-a1", "lead-b"), ("build-a1", "free-1"), ("build-a1", "build-b1"),
           ("lead-a", "build-b1"), ("lead-a", "free-1"), ("lead-b", "build-a1"), ("free-1", "build-a1"),
           ("free-1", "free-2"), ("lead-a", "lead-a"), ("build-a1", "build-a1")]


def test_a_lead_a_builder_of_its_cards_and_a_session_with_no_role_may_send_to_these(tmp_path):
    """E1: the allowed pairs of the star: lead to lead, lead to a builder of a card it ordered, a builder to the lead of
    its card, a session with no role to a lead. Catches: a topology that is too strict for the star itself."""
    root = world(tmp_path)
    for n, (sender, to) in enumerate(ALLOWED):
        code, out, err = send(root, sender, to, "question", f"is this fine? {n}")
        assert code == 0, (sender, to, err)
        assert rows_to(root, to)[-1]["from"] == sender


def rows_to(root, session):
    return inbox(root, session)


def test_every_other_pair_is_message_topology_and_the_text_names_the_way(tmp_path):
    """E1: builder to builder, a builder to another lead, a lead to a builder of another lead, a lead to a session with
    no role, a session with no role to a builder or to another session with no role, and a send to oneself are refused
    `message-topology`; nothing is written; the text names the allowed recipient and the command that lists them."""
    root = world(tmp_path)
    for n, (sender, to) in enumerate(REFUSED):
        code, out, err = send(root, sender, to, "question", f"may I? {n}")
        assert code != 0 and _reason(err) == "message-topology", (sender, to, err)
    assert not (state(root) / "inbox" / "free-1.jsonl").exists() and rows_to(root, "build-a2") == []
    _code, _out, err = send(root, "build-a1", "build-a2", "question", "to a peer")
    assert "lead-a" in err and "mkway send --to" in err
    _code, _out, err = send(root, "free-1", "free-2", "question", "to a peer")
    assert "mkway leads" in err
    _code, _out, err = send(root, "lead-a", "free-1", "question", "to a stranger")
    assert "mkway board" in err


def test_a_command_is_ordered_by_a_lead_and_an_event_goes_to_a_lead(tmp_path):
    """E2: `order` is a lead's kind (a builder's order is `message-topology`); `notice` and `result` are events and
    go to a lead (a lead's event to a builder is `message-topology`); `question` and `answer` follow the star only."""
    root = world(tmp_path)
    assert send(root, "build-a1", "lead-a", "order", "do this")[0] != 0
    assert _reason(send(root, "build-a1", "lead-a", "order", "do this")[2]) == "message-topology"
    assert _reason(send(root, "lead-a", "build-a1", "result", "done")[2]) == "message-topology"
    assert _reason(send(root, "lead-a", "build-a1", "notice", "fyi")[2]) == "message-topology"
    for sender, to, kind in (("lead-a", "build-a1", "order"), ("lead-a", "lead-b", "notice"),
                             ("build-a1", "lead-a", "result"), ("build-a1", "lead-a", "notice"),
                             ("lead-a", "build-a2", "question"), ("build-a2", "lead-a", "answer")):
        code, _out, err = send(root, sender, to, kind, f"a {kind} from {sender}")
        assert code == 0, (sender, to, kind, err)


def test_a_builder_is_known_by_its_card_in_the_work_tree_it_runs_in(tmp_path):
    """E1: the holder of a card is read from the records and the register of the work tree the session runs in, which
    the shared sessions file names (`root`): a lead in one work tree reaches the builder of its card in another."""
    root = world(tmp_path)
    other = lead_root(tmp_path, name="other")
    card = new_card(other, "lead-a", "Elsewhere")
    assert session_run(other, "build-x1", "card", "take", card)[0] == 0
    seen(root, "build-x1", at=other)
    code, _out, err = send(root, "lead-a", "build-x1", "order", "work there")
    assert code == 0, err
    assert _reason(send(root, "lead-b", "build-x1", "order", "not yours")[2]) == "message-topology"
    code, _out, err = send(root, "build-x1", "lead-a", "question", "which file?")  # its own card is read there too
    assert code == 0, err
    assert _reason(send(root, "build-x1", "lead-b", "question", "or you?")[2]) == "message-topology"


# --- E1, E4: the same body to two recipients ---------------------------------------------------------------------

def test_the_same_body_to_a_second_recipient_is_message_duplicate(tmp_path):
    """E3: the same body (white space around it ignored) to a second recipient within the window is refused
    `message-duplicate`, and the text names the first recipient and the way out; the same body to the same recipient is
    not refused; another body is not. Catches: one order broadcast to two builders."""
    root = world(tmp_path)
    assert send(root, "lead-a", "build-a1", "order", "build the thing")[0] == 0
    code, _out, err = send(root, "lead-a", "build-a2", "order", "build the thing\n")
    assert code != 0 and _reason(err) == "message-duplicate" and "build-a1" in err and "mkway send" in err
    assert rows_to(root, "build-a2") == []
    assert send(root, "lead-a", "build-a1", "order", "build the thing")[0] == 0
    assert send(root, "lead-a", "build-a2", "order", "build another thing")[0] == 0


def test_the_duplicate_window_follows_the_key(tmp_path):
    """E3: the window is `messaging.duplicate_window_hours` (default 1): the same body to a second recipient after
    the window goes through; inside it, it is refused; the key moves the window."""
    root = world(tmp_path)
    profile = profile_of(root)
    t0 = datetime.datetime.now(datetime.timezone.utc)
    shared = state(root)
    messages.send(root, profile, shared, "lead-a", "build-a1", "order", "same text", now=t0)

    def again(prof, minutes):
        return messages.send(root, prof, shared, "lead-a", "build-a2", "order", "same text",
                             now=t0 + datetime.timedelta(minutes=minutes))

    try:
        again(profile, 30)
        raise AssertionError("a duplicate inside the window was delivered")
    except messages.MessageError as exc:
        assert exc.reason == "message-duplicate"
    try:
        again(dict(profile, messaging={"duplicate_window_hours": 3}), 120)
        raise AssertionError("a duplicate inside a 3 hour window was delivered")
    except messages.MessageError as exc:
        assert exc.reason == "message-duplicate"
    assert again(profile, 120).row["to"] == "build-a2"


# --- E2: the inbox row -------------------------------------------------------------------------------------------

def test_a_row_has_exactly_the_agreed_fields_and_lives_in_the_recipients_inbox(tmp_path):
    """E4: one row `{id, from, to, kind, reply_to, ts, ack_ts, body}` is appended to
    `<state>/inbox/<recipient session id>.jsonl`: `from` is the hook's session id, `to` the full id the prefix named,
    `ack_ts` empty, `body` the file's text; two sends are two rows, in order, and nothing else is written."""
    root = world(tmp_path)
    code, out, err = send(root, "lead-b", "build-b", "order", "first order")
    assert code == 0, err
    code, out2, err = send(root, "lead-b", "build-b", "question", "second one")
    assert code == 0, err
    rows = rows_to(root, "build-b1")
    assert len(rows) == 2 and all(list(r) == ROW_FIELDS for r in rows)
    first = rows[0]
    assert (first["from"], first["to"], first["kind"], first["reply_to"], first["ack_ts"], first["body"]) == (
        "lead-b", "build-b1", "order", None, None, "first order")
    assert datetime.datetime.fromisoformat(first["ts"]) and first["id"] == id_of(out) and rows[1]["id"] == id_of(out2)
    assert first["id"] != rows[1]["id"]
    assert sorted(p.name for p in (state(root) / "inbox").iterdir()) == ["build-b1.jsonl"]


def test_a_reply_names_a_row_of_the_senders_own_inbox(tmp_path):
    """E4: `--reply-to <id>` is the correlation id: it must be a row in the sender's own inbox; a row in another
    inbox, or no row, is `message-reply-unknown` and nothing is written."""
    root = world(tmp_path)
    code, out, err = send(root, "lead-a", "build-a1", "question", "which file?")
    assert code == 0, err
    asked = id_of(out)
    code, _out, err = send(root, "build-a1", "lead-a", "answer", "this one", "--reply-to", asked)
    assert code == 0, err
    assert rows_to(root, "lead-a")[-1]["reply_to"] == asked
    for sender, wrong in (("build-a2", asked), ("build-a1", "m-nothing")):
        code, _out, err = send(root, sender, "lead-a", "answer", "so", "--reply-to", wrong)
        assert code != 0 and _reason(err) == "message-reply-unknown", (sender, wrong)
    assert len(rows_to(root, "lead-a")) == 1


def test_an_empty_body_is_refused(tmp_path):
    """E4: an empty or blank body file is `message-empty`; nothing is written."""
    root = world(tmp_path)
    code, _out, err = send(root, "lead-a", "lead-b", "notice", "  \n")
    assert code != 0 and _reason(err) == "message-empty" and rows_to(root, "lead-b") == []


# --- E4: send ----------------------------------------------------------------------------------------------------

def test_send_prints_the_exact_ping_line_and_the_recipients_root(tmp_path):
    """E5: a delivered send prints the ping line `mkway inbox <id>` alone on a line and the recipient's root folder
    (from the shared sessions file), and tells the sender to find the name in ListAgents by that folder and send the
    ping line with SendMessage. No socket is used."""
    root = world(tmp_path)
    code, out, err = send(root, "lead-a", "lead-b", "notice", "hello there")
    assert code == 0, err
    row = rows_to(root, "lead-b")[0]
    assert ping_of(out) == f"mkway inbox {row['id']}"
    assert f"root: {root}" in out and "ListAgents" in out and "SendMessage" in out


def test_an_unknown_recipient_goes_to_the_dead_letter_and_the_senders_lead_is_told(tmp_path):
    """E6: a prefix that names no session of the shared sessions file writes a row to `<state>/dead-letter.jsonl` (id,
    from, to as typed, kind, reply_to, ts, reason, body), no inbox row, and a notice to the sender's lead; the sender
    gets `message-dead-letter` naming `mkway board`."""
    root = world(tmp_path)
    code, _out, err = send(root, "build-a1", "zzz-nobody", "question", "anyone there?")
    assert code != 0 and _reason(err) == "message-dead-letter" and "mkway board" in err
    (dead,) = lines(state(root) / "dead-letter.jsonl")
    assert list(dead) == ["id", "from", "to", "kind", "reply_to", "ts", "reason", "body"]
    assert (dead["from"], dead["to"], dead["kind"], dead["reason"], dead["body"]) == (
        "build-a1", "zzz-nobody", "question", "unknown", "anyone there?")
    notices = rows_to(root, "lead-a")
    assert len(notices) == 1 and notices[0]["kind"] == "notice" and "zzz-nobody" in notices[0]["body"]
    assert dead["id"] in notices[0]["body"]
    assert sorted(p.name for p in (state(root) / "inbox").iterdir()) == ["lead-a.jsonl"]
    code, _out, err = send(root, "free-1", "zzz-nobody", "question", "and me?")  # no lead to tell: the row still stands
    assert code != 0 and len(lines(state(root) / "dead-letter.jsonl")) == 2 and len(rows_to(root, "lead-a")) == 1


def test_a_session_last_seen_too_long_ago_goes_to_the_dead_letter(tmp_path):
    """E6: a session last seen more than `messaging.dead_hours` (default 12) ago is dead; inside the time it is not; the
    key moves the time. A lead that sends to it is told in its own inbox."""
    root = world(tmp_path)
    register_lead(root, "lead-c")
    now = datetime.datetime.now(datetime.timezone.utc)
    seen(root, "lead-c", when=now - datetime.timedelta(hours=13))
    code, _out, err = send(root, "lead-a", "lead-c", "notice", "are you there?")
    assert code != 0 and _reason(err) == "message-dead-letter"
    (dead,) = lines(state(root) / "dead-letter.jsonl")
    assert dead["reason"] == "stale" and dead["to"] == "lead-c" and rows_to(root, "lead-c") == []
    assert rows_to(root, "lead-a")[0]["kind"] == "notice" and "lead-c" in rows_to(root, "lead-a")[0]["body"]
    sent = messages.send(root, dict(profile_of(root), messaging={"dead_hours": 24}), state(root), "lead-a", "lead-c",
                         "notice", "now it is alive")
    assert sent.row["to"] == "lead-c"
    seen(root, "lead-c")
    assert send(root, "lead-a", "lead-c", "notice", "back again")[0] == 0


def test_a_prefix_of_two_sessions_is_message_ambiguous(tmp_path):
    """E6: a prefix that starts two session ids is refused `message-ambiguous` and lists them; nothing is written and
    no dead letter is made; a whole id wins over a longer id that starts with it."""
    root = world(tmp_path)
    code, _out, err = send(root, "lead-a", "build-a", "order", "which one?")
    assert code != 0 and _reason(err) == "message-ambiguous" and "build-a1" in err and "build-a2" in err
    assert not (state(root) / "dead-letter.jsonl").exists() and rows_to(root, "build-a1") == []
    seen(root, "lead-a-long")
    assert send(root, "free-1", "lead-a", "question", "whole id")[0] == 0 and len(rows_to(root, "lead-a")) == 1


def test_send_needs_a_session_with_a_hook_check(tmp_path):
    """E5: the sender is the hook's session id (the lock gate's one-use permit): with no permit `message-no-session`,
    and from the owner's terminal `send-session-only` (the owner reads `mkway board`); each text names the fix and
    nothing is written."""
    root = world(tmp_path)
    (root / "body.txt").write_text("text", encoding="utf-8")
    code, _out, err = cli(root, "send", "--to", "lead-a", "--kind", "notice", "--file", "body.txt", session=True)
    assert code != 0 and _reason(err) == "message-no-session" and "alone" in err
    code, _out, err = cli(root, "send", "--to", "lead-a", "--kind", "notice", "--file", "body.txt")
    assert code != 0 and _reason(err) == "send-session-only" and "mkway board" in err
    assert not (state(root) / "inbox" / "lead-a.jsonl").exists()


# --- E5: inbox ---------------------------------------------------------------------------------------------------

def test_inbox_shows_the_row_to_its_recipient_only(tmp_path):
    """E7: `mkway inbox <id>` prints the row (id, kind, from, reply_to, time, body) to the session it is addressed to
    and changes nothing (`ack_ts` stays empty); another session is `inbox-not-yours`, an unknown id `inbox-unknown`;
    the owner's terminal reads any row."""
    root = world(tmp_path)
    code, out, err = send(root, "lead-a", "build-a1", "order", "build the thing")
    assert code == 0, err
    row_id = id_of(out)
    code, shown, err = session_run(root, "build-a1", "inbox", row_id)
    assert code == 0, err
    for needed in (row_id, "order", "lead-a", "build the thing"):
        assert needed in shown, needed
    assert rows_to(root, "build-a1")[0]["ack_ts"] is None
    code, _out, err = session_run(root, "build-a2", "inbox", row_id)
    assert code != 0 and _reason(err) == "inbox-not-yours" and "mkway board" in err
    code, _out, err = session_run(root, "build-a1", "inbox", "m-nothing")
    assert code != 0 and _reason(err) == "inbox-unknown"
    code, shown, _err = cli(root, "inbox", row_id)
    assert code == 0 and "build the thing" in shown


# --- E3: acknowledgements ----------------------------------------------------------------------------------------

def test_any_session_acks_its_own_row_and_nobody_acks_another_sessions(tmp_path):
    """E8: `mkway ack <id>` sets `ack_ts` of a row in the caller's own inbox, builders and leads alike; a row in another
    inbox is `ack-not-yours`; an acked row or an unknown id is `ack-unknown`; the owner's terminal acks any row."""
    root = world(tmp_path)
    code, out, err = send(root, "lead-a", "build-a1", "order", "build the thing")
    assert code == 0, err
    row_id = id_of(out)
    code, _out, err = session_run(root, "build-a2", "ack", row_id)
    assert code != 0 and _reason(err) == "ack-not-yours" and "mkway inbox" in err
    assert rows_to(root, "build-a1")[0]["ack_ts"] is None
    code, _out, err = session_run(root, "build-a1", "ack", row_id)
    assert code == 0, err
    assert datetime.datetime.fromisoformat(rows_to(root, "build-a1")[0]["ack_ts"])
    for bad in (row_id, "m-nothing"):
        code, _out, err = session_run(root, "build-a1", "ack", bad)
        assert code != 0 and _reason(err) == "ack-unknown", bad
    code, out, err = send(root, "build-a1", "lead-a", "result", "built")
    assert code == 0, err
    assert session_run(root, "lead-a", "ack", id_of(out))[0] == 0
    code, out, err = send(root, "lead-a", "lead-b", "notice", "fyi")
    assert cli(root, "ack", id_of(out))[0] == 0 and rows_to(root, "lead-b")[0]["ack_ts"]


def test_the_row_written_by_the_engine_has_the_same_fields_as_a_message(tmp_path):
    """E4: a notice the engine writes (MW-017) carries `reply_to` too, so every row of an inbox has one shape."""
    root = task_root(tmp_path)
    import leads
    row = leads.append_notice(state(root), "lead-a", "something happened")
    assert list(row) == ROW_FIELDS and row["reply_to"] is None
