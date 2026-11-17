"""Card MW-110: a session is known by the environment variable its launcher sets, checked by every shell hook call against
the hook's own session id; `mkway send`, `inbox` and `ack` read the id from it and need no one-use permit. On a real small
task root (synthetic sessions, files under tmp_path). The twelve replays are synthetic: the shapes (a session sending,
reading or acking its own inbox, refused for a missing or an expired hook permit, in the plain and the chained command
form) come from the guard review classification, never from real command texts."""
import datetime
import hashlib
import json

import pytest

import _engine  # noqa: F401  (puts the engine folder on the import path)
from _engine import cli, jsonl, write_profile
from _mw018 import id_of, rows_of, send, session_run, state, world
import core_session as core
import dispatch
import gate_message

NAME = "MKWAY_SESSION_ID"
LAUNCHER_FRAGMENTS = ("MKWAY_SESSION_ID", "--session-id")
PLAIN = "python mkway/engine/mkway.py {args}"
CHAINED = "cd mkway && python engine/mkway.py {args} && echo done"
ARGS = {"send": "send --to lead-a --kind notice --file body.txt", "inbox": "inbox m-1", "ack": "ack m-1"}


def case(id_, *values):
    return pytest.param(*values, id=id_)


def _profile(root):
    return json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))


def session_gate(root, command, session, env, once=None, profile=None):
    """The message.session gate on one shell call, with the hook's environment `env`."""
    ctx = dispatch.make_context(profile=profile or _profile(root), root=root, session_id=session, event="PreToolUse",
                                gate="message.session", tool_name="Bash", tool_input={"command": command},
                                budget_seconds=None, once=once or (lambda targets: True), env=env)
    return gate_message.session("PreToolUse", ctx)


def leave_permit(root, session, age_seconds, name=None):
    """The lock gate's one-use permit of a messaging command of `session` (R279c: `permits/<session id>.json`),
    `age_seconds` old (3600: expired; the limit is 120); None leaves none. `name`: the file name when it is not the id."""
    if age_seconds is None:
        return
    stamp = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=age_seconds)
    target = state(root) / "permits" / f"{name or session}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"session_id": session, "scope": "messaging",
                                  "time": stamp.isoformat(timespec="milliseconds")}), encoding="utf-8")


def permit_file(root, session):
    return state(root) / "permits" / f"{session}.json"


def as_session(root, session, *args):
    """The CLI in a session's shell whose environment carries the launcher's variable."""
    return cli(root, *args, session=True, env={NAME: session})


PERMITS = [case("missing-plain", None, PLAIN), case("missing-chained", None, CHAINED),
           case("expired-plain", 3600, PLAIN), case("expired-chained", 3600, CHAINED)]


@pytest.mark.parametrize("age, shape", PERMITS)
def test_replay_a_session_with_the_env_id_sends_without_a_permit(tmp_path, age, shape):
    """Checks: the replay of a send refused for a missing or an expired permit: with the id in the environment the hook
    gate allows the call and the engine delivers it, from that id."""
    root = world(tmp_path)
    (root / "body.txt").write_text("a plain notice", encoding="utf-8")
    leave_permit(root, "build-a1", age)
    gate = session_gate(root, shape.format(args=ARGS["send"]), "build-a1", {NAME: "build-a1"})
    code, out, err = as_session(root, "build-a1", "send", "--to", "lead-a", "--kind", "notice", "--file", "body.txt")
    assert (gate.kind, code, rows_of(root, "lead-a")[-1]["from"], rows_of(root, "lead-a")[-1]["body"]) == (
        "allow", 0, "build-a1", "a plain notice"), err


@pytest.mark.parametrize("age, shape", PERMITS)
def test_replay_a_session_with_the_env_id_reads_its_inbox_without_a_permit(tmp_path, age, shape):
    """Checks: the replay of an inbox read refused for a missing or an expired permit: it is shown to its recipient."""
    root = world(tmp_path)
    _code, out, _err = send(root, "lead-a", "build-a1", "order", "build the thing")
    leave_permit(root, "build-a1", age)
    gate = session_gate(root, shape.format(args=f"inbox {id_of(out)}"), "build-a1", {NAME: "build-a1"})
    code, shown, err = as_session(root, "build-a1", "inbox", id_of(out))
    assert (gate.kind, code, "build the thing" in shown) == ("allow", 0, True), err


@pytest.mark.parametrize("age, shape", PERMITS)
def test_replay_a_session_with_the_env_id_acks_without_a_permit(tmp_path, age, shape):
    """Checks: the replay of an ack refused for a missing or an expired permit: the row of its own inbox is acked."""
    root = world(tmp_path)
    _code, out, _err = send(root, "lead-a", "build-a1", "order", "build the thing")
    leave_permit(root, "build-a1", age)
    gate = session_gate(root, shape.format(args=f"ack {id_of(out)}"), "build-a1", {NAME: "build-a1"})
    code, _acked, err = as_session(root, "build-a1", "ack", id_of(out))
    assert (gate.kind, code, bool(rows_of(root, "build-a1")[0]["ack_ts"])) == ("allow", 0, True), err


@pytest.mark.parametrize("command", [case(f"{name}-{shape}", form.format(args=ARGS[name]))
                                      for name in ("send", "inbox", "ack")
                                      for shape, form in (("plain", PLAIN), ("chained", CHAINED))])
def test_replay_with_the_variable_unset_the_hook_warns_and_allows(tmp_path, command):
    """Checks: the same shapes with the launcher variable unset (the transition): the hook gate allows the call and says
    once, as a warn `session-id-unset`, that the launcher line sets the variable."""
    root = world(tmp_path)
    gate = session_gate(root, command, "build-a1", {})
    assert (gate.kind, gate.reason_id) == ("warn", "session-id-unset")


def test_with_the_variable_unset_a_valid_permit_still_names_the_session(tmp_path):
    """Checks: the transition: a session whose launcher does not set the variable still sends through the lock gate's
    one-use permit, as today."""
    root = world(tmp_path)
    code, _out, err = send(root, "build-a1", "lead-a", "question", "which file?")
    assert (code, rows_of(root, "lead-a")[-1]["from"]) == (0, "build-a1"), err


def test_with_no_id_at_all_send_is_refused_and_names_the_launcher_line(tmp_path):
    """Catches: a send with no variable and no permit that names no way out: the refusal names the variable and the
    launcher's `--session-id` line, and nothing is written."""
    root = world(tmp_path)
    (root / "body.txt").write_text("text", encoding="utf-8")
    code, _out, err = cli(root, "send", "--to", "lead-a", "--kind", "notice", "--file", "body.txt", session=True)
    assert code != 0
    assert "message-no-session" in err
    assert [f for f in LAUNCHER_FRAGMENTS if f not in err] == []
    assert rows_of(root, "lead-a") == []


def test_an_env_id_that_differs_from_the_permit_is_session_id_mismatch(tmp_path):
    """Catches: a session that sends under another session's id because its environment says so: the permit file the
    variable names (R279c: the CLI opens only that file) names another session, so the two ids differ and the call is
    refused with nothing written."""
    root = world(tmp_path)
    (root / "body.txt").write_text("text", encoding="utf-8")
    leave_permit(root, "build-a1", 0, name="lead-b")
    code, _out, err = as_session(root, "lead-b", "send", "--to", "lead-a", "--kind", "notice", "--file", "body.txt")
    assert code != 0
    assert "session-id-mismatch" in err
    assert [f for f in LAUNCHER_FRAGMENTS if f not in err] == []
    assert rows_of(root, "lead-a") == []


@pytest.mark.parametrize("env, command, session, kind, reason", [
    case("equal-allows", {NAME: "build-a1"}, PLAIN.format(args=ARGS["send"]), "build-a1", "allow", None),
    case("mismatch-denies", {NAME: "lead-b"}, PLAIN.format(args=ARGS["send"]), "build-a1", "refuse", "session-id-mismatch"),
    case("inline-assignment-denies", {NAME: "build-a1"}, f"{NAME}=lead-b " + PLAIN.format(args=ARGS["send"]), "build-a1",
         "refuse", "session-id-mismatch"),
    case("unset-warns", {}, PLAIN.format(args=ARGS["send"]), "build-a1", "warn", "session-id-unset"),
])
def test_the_session_gate_reads_the_hook_environment(tmp_path, env, command, session, kind, reason):
    """Catches: a shell hook call whose environment id is another session's passing, an inline assignment of the
    variable passing, or an equal id refused; the gate reads the environment the hook process carries."""
    root = world(tmp_path)
    gate = session_gate(root, command, session, env)
    assert (gate.kind, gate.reason_id) == (kind, reason)


def test_the_unset_variable_warns_once_per_session(tmp_path):
    """Catches: the transition warn repeated on every shell call of a session: the first call warns, the second passes."""
    root = world(tmp_path)
    store = dispatch.OnceStore(state(root), "build-a1")
    first = session_gate(root, "git status", "build-a1", {}, once=lambda targets: store.once("message.session", targets))
    second = session_gate(root, "git status", "build-a1", {}, once=lambda targets: store.once("message.session", targets))
    assert (first.kind, second.kind) == ("warn", "allow")


@pytest.mark.parametrize("watch_until, kind, reason", [
    case("no-date-warns-and-allows", "", "warn", "session-id-unset"),
    case("a-past-date-refuses", "2020-01-01", "refuse", "session-id-mismatch"),
    case("a-future-date-warns-and-allows", "2999-01-01", "warn", "session-id-unset"),
    case("an-unreadable-date-counts-as-passed", "next week", "refuse", "session-id-mismatch"),
    case("an-impossible-date-counts-as-passed", "2026-13-45", "refuse", "session-id-mismatch"),
])
def test_the_watch_date_of_the_profile_ends_the_permit_path(tmp_path, watch_until, kind, reason):
    """Catches: the permit path with no end once the owner set `messaging.session_id_watch_until`, or an end that comes
    with no date set: an empty value means no expiry; a past date refuses an unset variable and names the launcher line; a
    value that cannot be read counts as passed (R279c Q2)."""
    root = world(tmp_path)
    profile = _profile(root)
    profile["messaging"] = {"session_id_watch_until": watch_until}
    gate = session_gate(root, "git status", "build-a1", {}, profile=profile)
    assert (gate.kind, gate.reason_id) == (kind, reason)
    assert [f for f in LAUNCHER_FRAGMENTS if f not in gate.message] == []


def test_the_owner_terminal_is_still_send_session_only(tmp_path):
    """Checks: the owner's terminal carries no variable and no hook: `send` stays the session's command."""
    root = world(tmp_path)
    (root / "body.txt").write_text("text", encoding="utf-8")
    code, _out, err = cli(root, "send", "--to", "lead-a", "--kind", "notice", "--file", "body.txt")
    assert code != 0
    assert "send-session-only" in err


def test_a_permit_the_send_did_not_use_is_still_taken(tmp_path):
    """Checks: the one-use permit is consumed at every messaging command, used or not, so an old one cannot name a later
    caller; with the variable set the session's own permit file is read, compared and removed."""
    root = world(tmp_path)
    (root / "body.txt").write_text("text", encoding="utf-8")
    leave_permit(root, "build-a1", 0)
    code, _out, err = as_session(root, "build-a1", "send", "--to", "lead-a", "--kind", "notice", "--file", "body.txt")
    assert (code, permit_file(root, "build-a1").exists()) == (0, False), err


def test_the_hook_leaves_the_permit_of_a_messaging_command_under_the_sessions_own_id(tmp_path):
    """Catches: R279c Q1: a messaging command's permit written into the one shared file, where two sessions overwrite and
    take each other's: the gate writes `permits/<session id>.json` and no shared `by.json`."""
    from _engine import gate_call
    import gate_lock
    root = world(tmp_path)
    for session, args in (("build-a1", "send --to lead-a --kind notice --file body.txt"), ("build-a2", "inbox m-1"),
                          ("lead-b", "ack m-1")):
        verdict = gate_call(gate_lock.check, root, tool="Bash", tool_input={"command": PLAIN.format(args=args)},
                            session=session)
        assert verdict.kind != "refuse", verdict.message
    files = sorted(p.name for p in (state(root) / "permits").glob("*.json"))
    assert files == ["build-a1.json", "build-a2.json", "lead-b.json"]
    assert json.loads(permit_file(root, "build-a2").read_text(encoding="utf-8"))["session_id"] == "build-a2"


def test_a_command_that_is_no_messaging_command_still_leaves_the_shared_by_permit(tmp_path):
    """Catches: R279c scope: the change reaching the other commands that name the session: `lead register` still writes
    the shared `by.json` and no file under the session's id."""
    from _engine import gate_call
    import gate_lock
    root = world(tmp_path)
    verdict = gate_call(gate_lock.check, root, tool="Bash", tool_input={"command": PLAIN.format(args="lead register")},
                        session="build-a1")
    assert verdict.kind != "refuse", verdict.message
    assert ((state(root) / "permits" / "by.json").is_file(), permit_file(root, "build-a1").exists()) == (True, False)


def test_two_sessions_permits_present_each_cli_takes_its_own(tmp_path):
    """Catches: R279c Q1, the race of one shared permit: the permits of two sessions are present at once; the CLI of each
    reads the variable and opens only its own file, so each message is from its own sender and the other permit stays."""
    root = world(tmp_path)
    (root / "body.txt").write_text("text of the first", encoding="utf-8")
    leave_permit(root, "build-a1", 0)
    leave_permit(root, "build-a2", 0)
    first, _o, err1 = as_session(root, "build-a1", *("send", "--to", "lead-a", "--kind", "notice", "--file", "body.txt"))
    assert (first, permit_file(root, "build-a1").exists(), permit_file(root, "build-a2").exists()) == (0, False, True), err1
    (root / "body.txt").write_text("text of the second", encoding="utf-8")
    second, _o2, err2 = as_session(root, "build-a2", *("send", "--to", "lead-a", "--kind", "notice", "--file", "body.txt"))
    assert (second, permit_file(root, "build-a2").exists()) == (0, False), err2
    assert [(r["from"], r["body"]) for r in rows_of(root, "lead-a")] == [("build-a1", "text of the first"),
                                                                        ("build-a2", "text of the second")]
    assert _warn_rows(root) == []


def test_with_no_variable_the_most_recent_permit_is_taken_with_a_warn_that_names_the_limit(tmp_path):
    """Checks: R279c Q1 (the transition, before the end date): a session whose launcher sets no variable takes the single
    most recent permit, once, with one warn row whose note says two sessions at once can take each other's permit."""
    root = world(tmp_path)
    (root / "body.txt").write_text("a plain notice", encoding="utf-8")
    leave_permit(root, "build-a2", 30)
    leave_permit(root, "build-a1", 1)
    code, _out, err = cli(root, *("send", "--to", "lead-a", "--kind", "notice", "--file", "body.txt"), session=True)
    warns = _warn_rows(root)
    assert (code, rows_of(root, "lead-a")[-1]["from"]) == (0, "build-a1"), err
    assert (permit_file(root, "build-a1").exists(), permit_file(root, "build-a2").exists()) == (False, True)
    assert len(warns) == 1
    assert [f for f in ("most recent permit", "two sessions", "messaging.session_id_watch_until") if f not in warns[0]["note"]] == []


# ---- the proof of a sender (ruling R279): the hook's permit, never the variable alone ---------------------------------------

def _with_watch_until(root, value):
    profile = _profile(root)
    profile["messaging"] = {"session_id_watch_until": value}
    write_profile(root, profile)


def _warn_rows(root):
    return [r for r in jsonl(state(root) / "refusals.jsonl") if r.get("reason_id") == "session-id-unset"]


def _send_args():
    return ("send", "--to", "lead-a", "--kind", "notice", "--file", "body.txt")


@pytest.mark.parametrize("watch_until", [case("no-date", ""), case("a-future-date", "2999-01-01")])
def test_with_no_permit_the_variable_counts_before_the_end_date_and_leaves_a_warn_record(tmp_path, watch_until):
    """Checks: R279: no permit and a variable, before `messaging.session_id_watch_until` (or with no date): the send is
    delivered from that id and the engine writes one warn row `session-id-unset` naming the session."""
    root = world(tmp_path)
    (root / "body.txt").write_text("a plain notice", encoding="utf-8")
    _with_watch_until(root, watch_until)
    code, _out, err = as_session(root, "build-a1", *_send_args())
    warns = _warn_rows(root)
    assert (code, rows_of(root, "lead-a")[-1]["from"]) == (0, "build-a1"), err
    assert [(w["session"], w["kind"]) for w in warns] == [("build-a1", "warn")]


@pytest.mark.parametrize("kind", ["send", "inbox", "ack"])
def test_with_no_permit_after_the_end_date_the_variable_is_no_proof(tmp_path, kind):
    """Catches: a session that sets the variable by a script the text check cannot see and sends as another session after
    the transition: no permit and a past date is a refusal `session-id-unverified` whose text names the hooks and the
    launcher line; nothing is written and nothing is acked."""
    root = world(tmp_path)
    (root / "body.txt").write_text("text", encoding="utf-8")
    _code, out, _err = send(root, "lead-a", "build-a1", "order", "build the thing")
    warns_before = _warn_rows(root)  # the setup send ran with no variable and left its own warn
    _with_watch_until(root, "2020-01-01")
    args = {"send": _send_args(), "inbox": ("inbox", id_of(out)), "ack": ("ack", id_of(out))}[kind]
    code, shown, err = as_session(root, "build-a1", *args)
    assert code != 0
    assert "session-id-unverified" in err
    assert [f for f in (*LAUNCHER_FRAGMENTS, "hooks") if f not in err] == []
    assert (rows_of(root, "lead-a"), "build the thing" in shown, rows_of(root, "build-a1")[0]["ack_ts"]) == ([], False, None)
    assert _warn_rows(root) == warns_before


def test_a_sessions_own_permit_is_the_proof_after_the_end_date(tmp_path):
    """Checks: the nearest allow of the refusal above: a session with the hooks (a fresh permit under its own id) and the
    launcher's variable sends after the end date; no warn row is written, the permit proved it."""
    root = world(tmp_path)
    (root / "body.txt").write_text("a plain notice", encoding="utf-8")
    _with_watch_until(root, "2020-01-01")
    leave_permit(root, "build-a1", 0)
    code, _out, err = as_session(root, "build-a1", *_send_args())
    assert (code, rows_of(root, "lead-a")[-1]["from"], _warn_rows(root)) == (0, "build-a1", []), err


def test_with_no_variable_after_the_end_date_even_a_permit_is_not_taken(tmp_path):
    """Catches: R279c Q1: after `watch_until` a session with no variable is `session-id-unverified` even when a permit
    exists (the transition is over), and the permit of another session is left alone; nothing is written."""
    root = world(tmp_path)
    (root / "body.txt").write_text("text", encoding="utf-8")
    _with_watch_until(root, "2020-01-01")
    leave_permit(root, "build-a1", 0)
    code, _out, err = cli(root, *_send_args(), session=True)
    assert code != 0
    assert "session-id-unverified" in err
    assert [f for f in (*LAUNCHER_FRAGMENTS, "hooks", "not set") if f not in err] == []
    assert (rows_of(root, "lead-a"), permit_file(root, "build-a1").exists(), _warn_rows(root)) == ([], True, [])


def test_another_sessions_permit_never_proves_a_variable(tmp_path):
    """Catches: R279c Q1 (the permit of one session read for another): a command whose variable names a session that has no
    permit of its own is not served by the permit of another session, which stays untouched. Before the end date the
    variable alone counts, with the warn row (the accepted limit of the transition); after it, `session-id-unverified`."""
    root = world(tmp_path)
    (root / "body.txt").write_text("text", encoding="utf-8")
    leave_permit(root, "build-a1", 0)
    before, _o, err = as_session(root, "lead-b", *_send_args())
    assert (before, rows_of(root, "lead-a")[-1]["from"], permit_file(root, "build-a1").exists()) == (0, "lead-b", True), err
    assert [(w["session"], w["kind"]) for w in _warn_rows(root)] == [("lead-b", "warn")]
    _with_watch_until(root, "2020-01-01")
    after, _o2, err2 = as_session(root, "lead-b", *_send_args())
    assert after != 0
    assert "session-id-unverified" in err2
    assert (len(rows_of(root, "lead-a")), permit_file(root, "build-a1").exists()) == (1, True)


def test_an_unreadable_watch_date_counts_as_passed_for_the_cli_and_the_text_names_it(tmp_path):
    """Catches: R279c Q2: a `messaging.session_id_watch_until` that cannot be read read as no expiry: with no own permit
    the variable alone is refused `session-id-unverified`, and the text names the value and that it counts as passed."""
    root = world(tmp_path)
    (root / "body.txt").write_text("text", encoding="utf-8")
    _with_watch_until(root, "next week")
    code, _out, err = as_session(root, "build-a1", *_send_args())
    assert code != 0
    assert "session-id-unverified" in err
    assert [f for f in ("next week", "counts as passed", "messaging.session_id_watch_until") if f not in err] == []
    assert rows_of(root, "lead-a") == []


def test_the_hook_text_for_an_unreadable_watch_date_names_the_value(tmp_path):
    """Checks: the hook's refusal for an unset variable with a date that cannot be read says which value and that it counts
    as passed."""
    root = world(tmp_path)
    profile = _profile(root)
    profile["messaging"] = {"session_id_watch_until": "next week"}
    gate = session_gate(root, "git status", "build-a1", {}, profile=profile)
    assert (gate.kind, gate.reason_id) == ("refuse", "session-id-mismatch")
    assert [f for f in ("next week", "counts as passed") if f not in gate.message] == []


# ---- no id at all: inbox and ack as well (a fix of the pre-merge readers) -----------------------------------------------------

@pytest.mark.parametrize("kind", ["inbox", "ack"])
def test_with_no_id_at_all_inbox_and_ack_are_refused_and_name_the_launcher_line(tmp_path, kind):
    """Catches: a read or an ack with no variable and no permit that is answered or that names no way out: refused
    `message-no-session` with the launcher line, nothing shown and nothing acked."""
    root = world(tmp_path)
    _code, out, _err = send(root, "lead-a", "build-a1", "order", "build the thing")
    code, shown, err = cli(root, kind, id_of(out), session=True)
    assert code != 0
    assert "message-no-session" in err
    assert [f for f in LAUNCHER_FRAGMENTS if f not in err] == []
    assert ("build the thing" in shown, rows_of(root, "build-a1")[0]["ack_ts"]) == (False, None)


# ---- the record (R1, ruling R279): one engine-written row per send and per acknowledgement ----------------------------------

def _record(root):
    return jsonl(state(root) / "message-record.jsonl")


def test_a_send_writes_one_record_row_with_the_sender_recipient_file_hash_and_time(tmp_path):
    """Catches: a send that leaves only the inbox file (which the sender could rewrite) as its record: the engine writes one
    row with the sender's session id, the recipient, the file as named, the sha256 of the body and a time."""
    root = world(tmp_path)
    _code, out, err = send(root, "build-a1", "lead-a", "result", "the card is finished")
    (row,) = _record(root)
    assert {k: row[k] for k in ("event", "id", "session", "to", "file", "sha256")} == {
        "event": "send", "id": id_of(out), "session": "build-a1", "to": "lead-a", "file": "body.txt",
        "sha256": hashlib.sha256(b"the card is finished").hexdigest()}, err
    assert datetime.datetime.fromisoformat(row["ts"]).tzinfo is not None


def test_a_text_send_records_the_text_form_in_place_of_a_file(tmp_path):
    """Checks: `send --text` has no file: the record row says so, and its hash is the hash of the text."""
    root = world(tmp_path)
    code, _out, err = as_session(root, "lead-a", "send", "--to", "lead-b", "--kind", "notice", "--text", "plain words")
    (row,) = _record(root)
    assert (code, row["file"], row["session"], row["sha256"]) == (0, "--text", "lead-a",
                                                                  hashlib.sha256(b"plain words").hexdigest()), err


def test_an_ack_writes_one_record_row_with_the_acking_session(tmp_path):
    """Catches: an ack that leaves no record but the changed inbox row: the engine writes one row with the session and the
    row id."""
    root = world(tmp_path)
    _code, out, _err = send(root, "lead-a", "build-a1", "order", "build the thing")
    code, _acked, err = session_run(root, "build-a1", "ack", id_of(out))
    rows = [r for r in _record(root) if r["event"] == "ack"]
    assert (code, [(r["id"], r["session"]) for r in rows]) == (0, [(id_of(out), "build-a1")]), err
    assert datetime.datetime.fromisoformat(rows[0]["ts"]).tzinfo is not None


def test_the_owners_ack_is_recorded_as_the_owner(tmp_path):
    """Checks: the owner's terminal acks any row; the record row names the owner, never a session."""
    root = world(tmp_path)
    _code, out, _err = send(root, "lead-a", "build-a1", "order", "build the thing")
    code, _acked, err = cli(root, "ack", id_of(out))
    assert (code, [(r["id"], r["session"]) for r in _record(root) if r["event"] == "ack"]) == (
        0, [(id_of(out), "owner")]), err


def _block_the_record(root):
    """A folder where the record file should be: appending to it fails, as a state folder that cannot be written would."""
    target = state(root) / "message-record.jsonl"
    if target.is_file():
        target.unlink()
    target.mkdir()
    return target


def test_a_send_whose_record_cannot_be_written_is_refused_and_nothing_is_delivered(tmp_path):
    """Catches: R279c Q3: a send that delivers first and records after (or only warns): the record is written FIRST, and a
    record that cannot be written refuses `send-record-failed`, names the file and the state folder, and delivers nothing,
    no inbox row and no write record."""
    root = world(tmp_path)
    inbox_writes = jsonl(state(root) / "inbox-writes.jsonl")
    _block_the_record(root)
    code, out, err = send(root, "lead-a", "build-a1", "order", "build the thing")
    assert code != 0
    assert "send-record-failed" in err
    assert [f for f in ("message-record.jsonl", "state folder") if f not in err] == []
    assert (rows_of(root, "build-a1"), jsonl(state(root) / "inbox-writes.jsonl"), "mkway inbox" in out) == (
        [], inbox_writes, False)


def test_an_ack_whose_record_cannot_be_written_is_refused_and_the_row_stays_unacked(tmp_path):
    """Catches: R279c Q3 for the ack: the same rule: refused `send-record-failed`, the row is not acked."""
    root = world(tmp_path)
    _code, out, _err = send(root, "lead-a", "build-a1", "order", "build the thing")
    _block_the_record(root)
    code, _acked, err = session_run(root, "build-a1", "ack", id_of(out))
    assert code != 0
    assert "send-record-failed" in err
    assert rows_of(root, "build-a1")[0]["ack_ts"] is None


def test_a_refused_ack_of_an_unknown_row_is_still_the_acks_own_reason_not_a_record_failure(tmp_path):
    """Catches: the record check swallowing the reason of an ack that is refused for its own cause: with the record blocked,
    an ack of a row that does not exist still says `ack-unknown`."""
    root = world(tmp_path)
    _block_the_record(root)
    code, _acked, err = session_run(root, "build-a1", "ack", "m-nothing")
    assert code != 0
    assert "ack-unknown" in err
    assert "send-record-failed" not in err


@pytest.mark.parametrize("text", [case("empty-body", "  \n"), case("topology", "may I?")])
def test_a_refused_send_writes_no_record_row(tmp_path, text):
    """Catches: a record row for a message that was never delivered (an empty body, a builder to a builder)."""
    root = world(tmp_path)
    to = "build-a2" if text == "may I?" else "lead-b"
    code, _out, _err = send(root, "build-a1", to, "question", text)
    assert (code != 0, [r for r in _record(root) if r["event"] == "send"]) == (True, [])


def test_a_refused_ack_writes_no_record_row(tmp_path):
    """Catches: a record row for an ack of a row that is not the session's (`ack-not-yours`)."""
    root = world(tmp_path)
    _code, out, _err = send(root, "lead-a", "build-a1", "order", "build the thing")
    code, _acked, _err = session_run(root, "build-a2", "ack", id_of(out))
    assert (code != 0, [r for r in _record(root) if r["event"] == "ack"]) == (True, [])


def test_send_by_the_session_run_helper_still_delivers_from_the_hook_id(tmp_path):
    """Checks: the existing path of the hooks (gate permit, then the CLI) is unchanged for a session with no variable."""
    root = world(tmp_path)
    (root / "body.txt").write_text("text", encoding="utf-8")
    code, out, err = session_run(root, "free-1", "send", "--to", "lead-a", "--kind", "question", "--file", "body.txt")
    assert code == 0, err
    assert rows_of(root, "lead-a")[-1]["from"] == "free-1"
    assert id_of(out).startswith("m-")
