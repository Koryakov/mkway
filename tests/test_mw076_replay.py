"""Card MW-076 (decisions: R185 to R188): the replays of the real cases, through the dispatcher and the real manifest.
DD-008 (a builder ran `mkway send` and stopped with no SendMessage; the report sat in the inbox, the lead stayed idle) and
U06 (`mkway card set <card> waiting` wrote a notice to the lead and no ping followed). Synthetic roots, session ids and
transcripts only."""
import datetime
import json
import re

from _engine import cli, jsonl
from _mw017 import session_run
from _mw018 import ping_of, send, state, world
import dispatch

CLAUSE = "if SendMessage is not loaded, load it first with ToolSearch query select:SendMessage"
ENV_OF = lambda root: {"CLAUDE_PROJECT_DIR": str(root), "CLAUDECODE": "1"}  # noqa: E731


def _name_the_lead(root, lead, name):
    path = state(root) / "leads.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for row in data["leads"]:
        if row["session_id"] == lead:
            row["name"] = name
    path.write_text(json.dumps(data), encoding="utf-8")


def _stamp(text, seconds):
    when = datetime.datetime.fromisoformat(text) + datetime.timedelta(seconds=seconds)
    return when.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _transcript(root, written_at, command, pinged=False, row_id=None):  # changed by MW-110 (decision MW110-D3): the ping names the written row
    def use(cid, tool, ts, **inp):
        return {"type": "assistant", "timestamp": ts,
                "message": {"content": [{"type": "tool_use", "id": cid, "name": tool, "input": inp}]}}
    rows = [{"type": "user", "timestamp": _stamp(written_at, -5), "message": {"content": "finish the card"}},
            use("t1", "Bash", _stamp(written_at, -1), command=command),
            {"type": "user", "timestamp": _stamp(written_at, 1),
             "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": "done"}]}}]
    if pinged:
        rows.append(use("p1", "SendMessage", _stamp(written_at, 3), to="lead-a", message=f"mkway inbox {row_id}"))
    path = root.parent / "turn.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return str(path)


def _stop(root, session, transcript, active=False):
    payload = {"session_id": session, "hook_event_name": "Stop", "stop_hook_active": active,
               "transcript_path": transcript, "last_assistant_message": "done"}
    return dispatch.run("Stop", "stop", json.dumps(payload), env=ENV_OF(root))


def test_dd008_a_builder_that_sent_and_stopped_is_blocked_with_the_ping_and_the_lead_is_told_later(tmp_path):
    """Catches: the real DD-008 case: a builder that sent and stopped with no ping is blocked with the ping line."""
    root = world(tmp_path)
    _name_the_lead(root, "lead-a", "dd-lead")
    _code, out, _err = send(root, "build-a1", "lead-a", "result", "the card is finished")
    written = jsonl(state(root) / "inbox-writes.jsonl")[-1]
    transcript = _transcript(root, written["ts"], "python mkway/engine/mkway.py send --to lead-a --kind result")
    # the real DD-008 case: the builder's report sat in the inbox and the lead stayed idle. The first Stop is a block
    # (top-level decision: block) whose reason is the ping line with the lead's name and the fixed clause; the second Stop
    # of the turn passes and writes the row; the lead's next Stop shows it once.
    first = json.loads(_stop(root, "build-a1", transcript).stdout)
    assert first["decision"] == "block"
    assert "[mkway ping.stop ping-not-sent]" in first["reason"]
    assert f"ping your lead: {CLAUSE}; then SendMessage to dd-lead: {ping_of(out)}" in first["reason"]
    assert _stop(root, "build-a1", transcript, active=True).stdout == ""
    line = f"builder build-a1 wrote to the inbox and did not ping: read mkway inbox {written['id']}"
    assert line in _stop(root, "lead-a", transcript).stdout
    assert line not in _stop(root, "lead-a", transcript).stdout


def test_u06_a_builder_that_set_its_card_to_waiting_and_stopped_is_blocked_with_the_notice_ping(tmp_path):
    """Catches: the real U06 case, a card set to waiting wrote a notice to the lead and nothing pinged it."""
    root = world(tmp_path)
    _name_the_lead(root, "lead-a", "dd-lead")
    card = re.search(r"CARD-\d{3}", sorted(p.name for p in (root / "mkway" / "cards").iterdir())[0]).group(0)
    assert cli(root, "card", "open", card)[0] == 0
    # the real U06 case: card set waiting wrote a notice to the lead inside the Bash call and nothing pinged it; the trigger
    # is the engine's own record of that write, not the word send.
    code, _out, err = session_run(root, "build-a1", "card", "set", card, "waiting")
    assert code == 0, err
    written = jsonl(state(root) / "inbox-writes.jsonl")[-1]
    transcript = _transcript(root, written["ts"], f"python mkway/engine/mkway.py card set {card} waiting")
    got = json.loads(_stop(root, "build-a1", transcript).stdout)
    assert got["decision"] == "block"
    assert f"SendMessage to dd-lead: mkway inbox {written['id']}" in got["reason"]
    assert written["from"] == "engine"
    assert written["kind"] == "notice"


def test_a_builder_that_sent_and_then_pinged_is_not_blocked(tmp_path):
    """Checks: the nearest allow of the replays: the same send with a SendMessage call after it leaves the Stop alone."""
    root = world(tmp_path)
    send(root, "build-a1", "lead-a", "result", "the card is finished")
    written = jsonl(state(root) / "inbox-writes.jsonl")[-1]
    transcript = _transcript(root, written["ts"], "python mkway/engine/mkway.py send --to lead-a", pinged=True,
                             row_id=written["id"])
    assert _stop(root, "build-a1", transcript).stdout == ""
