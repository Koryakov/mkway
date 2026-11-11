"""Card MW-018, parts 5 and 6, rows E12 to E15: the lock target of the inbox and the gate `message` on SendMessage. The
gate judges the sender's side only: the body is exactly one ping line, the row exists and is the sender's, the ping is
the first for that row. It never reads the `to` field. Form gate: watch mode first. Synthetic roots only."""
import json

import pytest

from _engine import cli, gate_call, make_profile, write_profile
from _mw018 import id_of, lines, profile_of, send, state, world
import dispatch
import gate_lock
import gate_message
import gatemode
import install
import leads
import locks


def ping(root, session, text, **extra):
    """The gate's verdict for a SendMessage call by `session` with this body."""
    tool_input = dict({"to": "somebody", "message": text}, **extra)
    return gate_call(gate_message.check, root, tool="SendMessage", tool_input=tool_input, session=session)


def pings(root):
    return lines(state(root) / "pings.jsonl")


@pytest.fixture
def sent(tmp_path):
    """A world in which lead-a has sent an order to build-a1 (row `mine`) and lead-b a question to lead-a (row `theirs`)."""
    root = world(tmp_path)
    code, out, err = send(root, "lead-a", "build-a1", "order", "build the thing")
    assert code == 0, err
    mine = id_of(out)
    code, out, err = send(root, "lead-b", "lead-a", "question", "a question", name="other.txt")
    assert code == 0, err
    return root, mine, id_of(out)


# --- E10: the lock target of the inbox ---------------------------------------------------------------------------

def test_the_engine_default_lock_target_inbox_is_in_defaults_json_and_closed(tmp_path):
    """E12: `defaults.json` holds `locks.targets` with one target `inbox`: `<state.dir>/inbox/**` and
    `<state.dir>/pings.jsonl`, taken at the profile's own state folder; it is closed like every lock; a profile target
    of the same name does not replace it."""
    data = json.loads((dispatch.ENGINE_DIR / "defaults.json").read_text(encoding="utf-8"))
    assert data["locks"]["targets"] == [{"name": "inbox", "paths": ["<state.dir>/inbox/**", "<state.dir>/pings.jsonl"]}]
    root = world(tmp_path)
    profile = profile_of(root)
    (target,) = [t for t in locks.targets(root, profile) if t.name == "inbox"]
    assert target.entries == ["mkway/state/inbox/**", "mkway/state/pings.jsonl"] and not target.built_in
    assert not locks.is_open(root, profile, "inbox")
    moved = dict(profile, state={"dir": "var/st"}, locks={"targets": [{"name": "inbox", "paths": ["elsewhere/**"]}]})
    (target,) = [t for t in locks.targets(root, moved) if t.name == "inbox"]
    assert target.entries == ["var/st/inbox/**", "var/st/pings.jsonl"]


def test_a_hand_written_inbox_row_or_ping_is_refused_by_the_lock(tmp_path):
    """E12: an edit tool or a shell write into `<state>/inbox/` or to `<state>/pings.jsonl` is refused by the lock
    gate (no new gate code); the rows are written only by `mkway send` and `mkway ack`, which are not writes the lock
    gate refuses."""
    root = world(tmp_path)
    for path in ("mkway/state/inbox/build-a1.jsonl", "mkway/state/inbox/new-file.jsonl", "mkway/state/pings.jsonl"):
        verdict = gate_call(gate_lock.check, root, tool="Write", tool_input={"file_path": path, "content": "{}"},
                            session="free-1")
        assert verdict.kind == "refuse" and verdict.reason_id == "lock-closed-edit", path
        for command in (f"echo '{{}}' >> {path}", f"cp row.json {path}"):
            verdict = gate_call(gate_lock.check, root, tool="Bash", tool_input={"command": command}, session="free-1")
            assert verdict.kind == "refuse" and verdict.reason_id == "lock-closed-shell", command
    plain = gate_call(gate_lock.check, root, tool="Bash", session="free-1", tool_input={
        "command": "python mkway/engine/mkway.py send --to lead-a --kind question --file body.txt"})
    assert plain.kind == "allow"


# --- E11: the gate -----------------------------------------------------------------------------------------------

def test_a_ping_line_of_a_row_the_session_wrote_passes_and_is_recorded(sent):
    """E13: the body is exactly `mkway inbox <id>` (a final line break allowed), the row exists in the shared inbox, its
    `from` is the hook's session id: allow, and one row `{id, session, ts}` is appended to `<state>/pings.jsonl`. The
    `to` field is never read: any name, or none, passes."""
    root, mine, theirs = sent
    assert ping(root, "lead-a", f"mkway inbox {mine}\n").kind == "allow"
    (row,) = pings(root)
    assert (row["id"], row["session"]) == (mine, "lead-a") and row["ts"]
    assert gate_call(gate_message.check, root, tool="SendMessage", session="lead-b",
                     tool_input={"message": f"mkway inbox {theirs}"}).kind == "allow"
    assert [r["id"] for r in pings(root)] == [mine, theirs]


def test_a_body_with_any_extra_text_is_message_not_in_inbox(sent):
    """E14: text before or after the ping line, a second line, a code fence, another command, an id that is not
    a plain id, an empty or blank body, and a body that is not text are refused `message-not-in-inbox`; the text names
    `mkway send` and the ping line; nothing is recorded."""
    root, mine, _theirs = sent
    bodies = [f"mkway inbox {mine} please build it", f"Hi!\nmkway inbox {mine}", f"mkway inbox {mine}\nand also this",
              f"`mkway inbox {mine}`", f"run: mkway inbox {mine}", f"mkway  inbox {mine}", f"mkway inbox {mine};ls",
              "mkway inbox", "mkway inbox ../x", "mkway inbox a b", "", "   ", "build the thing", None, 7,
              [f"mkway inbox {mine}"], f"mkway inbox {mine}\r\nmkway inbox {mine}"]
    for body in bodies:
        verdict = ping(root, "lead-a", body)
        assert verdict.kind == "refuse" and verdict.reason_id == "message-not-in-inbox", repr(body)
    assert "mkway send" in verdict.message and "mkway inbox <id>" in verdict.message
    assert pings(root) == []
    missing = gate_call(gate_message.check, root, tool="SendMessage", tool_input={"to": "x"}, session="lead-a")
    assert missing.kind == "refuse" and missing.reason_id == "message-not-in-inbox"
    assert gate_call(gate_message.check, root, tool="SendMessage", tool_input=None, session="lead-a").kind == "refuse"


def test_the_id_of_another_senders_row_or_of_no_row_is_refused(sent):
    """E14: a ping for a row another session wrote (the recipient pinging its own received row, a third session,
    a row the engine wrote), for an id that does not exist, and for a dead-letter id is `message-not-in-inbox`; a session
    the hook gives no id for cannot ping at all."""
    root, mine, theirs = sent
    notice = leads.append_notice(state(root), "lead-a", "a matter the engine wrote")
    for session, row_id in (("build-a1", mine), ("lead-b", mine), ("free-1", mine), ("lead-a", theirs),
                            ("lead-a", "m-20990101000000-ffffff"), ("lead-a", "n-1"), ("lead-a", notice["id"])):
        verdict = ping(root, session, f"mkway inbox {row_id}")
        assert verdict.kind == "refuse" and verdict.reason_id == "message-not-in-inbox", (session, row_id)
    send(root, "build-a1", "zzz-nobody", "question", "anyone?", name="dead.txt")
    (dead,) = lines(state(root) / "dead-letter.jsonl")
    assert ping(root, "build-a1", f"mkway inbox {dead['id']}").reason_id == "message-not-in-inbox"
    for nobody in (None, "", 5):
        verdict = gate_call(gate_message.check, root, tool="SendMessage", session=nobody,
                            tool_input={"message": f"mkway inbox {mine}"})
        assert verdict.kind == "refuse" and verdict.reason_id == "message-not-in-inbox", repr(nobody)
    assert pings(root) == []


def test_a_second_ping_for_the_same_row_is_message_duplicate(sent):
    """E14: the first ping passes, the second for the same id is `message-duplicate` (the text names the way:
    a new `mkway send`), whatever the `to` field says; a ping for another row still passes; the refused ping is not
    recorded."""
    root, mine, theirs = sent
    assert ping(root, "lead-a", f"mkway inbox {mine}").kind == "allow"
    for to in ("somebody", "another name [3fa9c1]"):
        verdict = ping(root, "lead-a", f"mkway inbox {mine}", to=to)
        assert verdict.kind == "refuse" and verdict.reason_id == "message-duplicate" and "mkway send" in verdict.message
    assert [r["id"] for r in pings(root)] == [mine]


def test_a_pure_idle_subscription_carries_no_body_and_passes(sent):
    """E14: `notify_when_idle` with an empty message transmits no text, so it is allowed and records no ping; an empty
    message without that flag is refused; any other tool is not this gate's."""
    root, mine, _theirs = sent
    ok = gate_call(gate_message.check, root, tool="SendMessage", session="lead-a",
                   tool_input={"to": "x", "message": "", "notify_when_idle": True})
    assert ok.kind == "allow" and pings(root) == []
    assert ping(root, "lead-a", "", notify_when_idle=False).kind == "refuse"
    assert ping(root, "lead-a", "hello", notify_when_idle=True).kind == "refuse"
    assert gate_call(gate_message.check, root, tool="Write", session="lead-a",
                     tool_input={"file_path": "a.txt", "content": "hi"}).kind == "allow"


# --- E12: wiring -------------------------------------------------------------------------------------------------

def _entries():
    return [e for e in dispatch.load_manifest(dispatch.ENGINE_DIR) if e.get("gate") == "message"]


def test_the_manifest_wires_the_message_gate_as_a_form_gate(tmp_path):
    """E15: three entries on the gate `message`, class form, on by default: `message.send` (group `message`, PreToolUse,
    matcher SendMessage, the two reasons, fails open), `message.remind` (prompt, `inbox-unacked`) and `message.stop`
    (Stop, `orders-unacked`); the group table has `message` with no onFailure; the hook entries install generates hold
    one for `PreToolUse` / `message` with the matcher SendMessage; the switch `gates.message.on: false` drops all
    three."""
    by = {e["name"]: e for e in _entries()}
    assert set(by) == {"message.send", "message.remind", "message.stop"}
    assert all(e["class"] == "form" and e["default_on"] is True and e["status"] == "on" for e in by.values())
    send_entry = by["message.send"]
    assert (send_entry["function"], send_entry["group"], send_entry["event"], send_entry["matcher"]) == (
        "gate_message:check", "message", "PreToolUse", "SendMessage")
    assert send_entry["reason_ids"] == ["message-not-in-inbox", "message-duplicate"] and send_entry["onFailure"] == "none"
    assert "fails open" in send_entry["on_failure_reason"]
    assert (by["message.remind"]["group"], by["message.remind"]["event"], by["message.remind"]["reason_ids"]) == (
        "prompt", "UserPromptSubmit", ["inbox-unacked"])
    assert (by["message.stop"]["group"], by["message.stop"]["event"], by["message.stop"]["reason_ids"]) == (
        "stop", "Stop", ["orders-unacked"])
    assert all(e["onFailure"] == "none" for e in by.values())
    table = json.loads((dispatch.ENGINE_DIR / "manifest.json").read_text(encoding="utf-8"))["groups"]
    assert table["message"] == {}
    assert gatemode.gate_class(dispatch.load_manifest(dispatch.ENGINE_DIR), "message") == gatemode.FORM
    manifest = dispatch.load_manifest(dispatch.ENGINE_DIR)
    found = [e for e in install.generate_entries(make_profile(), manifest) if e["group"] == "message"]
    assert len(found) == 1 and found[0]["event"] == "PreToolUse" and found[0]["matcher"] == "SendMessage"
    assert found[0]["on_failure"] is None and "hook PreToolUse --group message" in found[0]["command"]
    off = install.generate_entries(make_profile(gates={"message": {"on": False}}), manifest)
    assert not [e for e in off if e["group"] == "message"]


def _run(root, tool_input, session="lead-a", manifest=None):
    payload = {"session_id": session, "hook_event_name": "PreToolUse", "tool_name": "SendMessage",
               "tool_input": tool_input, "cwd": str(root)}
    return dispatch.run("PreToolUse", "message", json.dumps(payload), env={"CLAUDE_PROJECT_DIR": str(root)},
                        manifest=manifest or _entries())


def test_in_watch_mode_the_refusal_is_logged_and_the_call_goes_ahead(sent):
    """E15: through the dispatcher a refusal is a deny; with the watch marker it is a `would-refuse` row with the same
    reason id and the call goes ahead (and no ping is recorded for it); a good ping passes in both modes; the owner's
    `mkway gate on message` ends watch."""
    root, mine, _theirs = sent
    bad = {"to": "x", "message": "just words"}
    denied = _run(root, bad)
    assert json.loads(denied.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "message-not-in-inbox" in denied.stdout
    gatemode.write_marker(state(root), "message", "installed")
    allowed = _run(root, bad)
    assert allowed.exit_code == 0 and not allowed.stdout
    rows = [json.loads(x) for x in (state(root) / "refusals.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["kind"] == "would-refuse" and rows[-1]["reason_id"] == "message-not-in-inbox"
    assert rows[-1]["session"] == "lead-a" and pings(root) == []
    assert not _run(root, {"to": "x", "message": f"mkway inbox {mine}"}).stdout and len(pings(root)) == 1
    assert cli(root, "gate", "on", "message")[0] == 0 and not gatemode.is_watching(state(root), "message")


def test_the_check_warns_when_the_settings_lack_the_sendmessage_entry(tmp_path):
    """E15: `mkway check` prints a `message gate:` line: present when the owned hook entries hold the SendMessage entry,
    a warning (never a failure) naming `mkway install` when they do not."""
    from test_install import clean_env, make_light_source, make_task, mkway
    src = make_light_source(tmp_path)
    task = make_task(tmp_path, vcs="none")
    env = {k: v for k, v in clean_env(tmp_path).items() if k != "CLAUDECODE"}
    assert mkway(task, env, "install", "--from", str(src), "--vcs", "none").returncode == 0
    proc = mkway(task, env, "check")
    assert "message gate: the SendMessage hook entry is present" in proc.stdout, proc.stdout + proc.stderr
    settings = task / ".claude" / "settings.local.json"
    data = json.loads(settings.read_text(encoding="utf-8"))
    data["hooks"]["PreToolUse"] = [g for g in data["hooks"]["PreToolUse"] if g.get("matcher") != "SendMessage"]
    settings.write_text(json.dumps(data), encoding="utf-8")
    proc = mkway(task, env, "check")
    line = [x for x in proc.stdout.splitlines() if x.startswith("message gate:")]
    assert len(line) == 1 and "warning" in line[0] and "SendMessage" in line[0] and "mkway install" in line[0]
    assert proc.returncode == 0, proc.stdout


def test_a_first_install_starts_the_message_gate_in_watch(tmp_path):
    """E15: the install's watch rule (MW-012, rule 5) covers the new gate: the form gates that are on start in watch."""
    manifest = dispatch.load_manifest(dispatch.ENGINE_DIR)
    watched = sorted({e.get("gate", e["name"]) for e in manifest if install._loadable_on(make_profile(), e)
                      and gatemode.gate_class(manifest, e.get("gate", e["name"])) == gatemode.FORM})
    assert "message" in watched
