"""Agent records (card MW-004). Synthetic task roots and synthetic hook payloads only.

Part 1: the `post` group records `SubagentStart` and `SubagentStop` into `<state>/agents.jsonl`: a start row, and an
end row that carries the start time, the end time, the elapsed seconds and the result text in full. It never blocks.
The payload fields (`session_id`, `agent_id`, `agent_type`, `agent_transcript_path`, `last_assistant_message`) are
the ones Claude Code documents for these events; a time or a result the hook cannot establish is «not established».
"""
import datetime
import json

import pytest

from _engine import jsonl, task_root
import dispatch
import logs

NE = "not established"
T0 = datetime.datetime(2026, 11, 10, 8, 0, 0, tzinfo=datetime.timezone.utc)


@pytest.fixture
def clock(monkeypatch):
    """A settable clock: `logs.now()` returns `clock.at` (UTC)."""
    class Clock:
        at = T0

        def after(self, **delta):
            self.at = T0 + datetime.timedelta(**delta)

    c = Clock()
    monkeypatch.setattr(logs, "now", lambda: c.at)
    return c


def _agents(root):
    return jsonl(root / "mkway" / "state" / "agents.jsonl")


def _fire(root, event, **fields):
    payload = {"session_id": "s1", "hook_event_name": event, "cwd": str(root), "transcript_path": "unused.jsonl"}
    payload.update(fields)
    return dispatch.run(event, "post", json.dumps(payload), env={"CLAUDE_PROJECT_DIR": str(root)})


def _start(root, agent="a1", kind="worker", session="s1"):
    return _fire(root, "SubagentStart", session_id=session, agent_id=agent, agent_type=kind)


def _stop(root, agent="a1", kind="worker", session="s1", **fields):
    return _fire(root, "SubagentStop", session_id=session, agent_id=agent, agent_type=kind, **fields)


def iso(**delta):
    return (T0 + datetime.timedelta(**delta)).isoformat(timespec="milliseconds")


def test_start_row_is_appended(tmp_path, clock):
    """E1: a `SubagentStart` appends one line with the session, the agent id and type and the start time.
    Catches: no gate on the event, a row without the session, or a start time taken at the end."""
    root = task_root(tmp_path)
    clock.after(minutes=3)
    res = _start(root)
    assert res.exit_code == 0 and res.stdout == ""
    assert _agents(root) == [{"kind": "start", "session_id": "s1", "agent_id": "a1", "agent_type": "worker",
                              "started": iso(minutes=3)}]


def test_stop_row_carries_the_result_and_the_times(tmp_path, clock):
    """E2: a `SubagentStop` appends an end row: the start time of that agent's start row, the end time, the elapsed
    seconds between them, and `last_assistant_message` in full (newlines and all), `result_source: payload`.
    Catches: a cut or trimmed result, an elapsed time that is not end minus start, a start time of the stop."""
    root = task_root(tmp_path)
    clock.after(minutes=0)
    _start(root)
    clock.after(minutes=42, seconds=30)
    text = "first line\n\n  indented second line\n" + "x" * 5000
    _stop(root, last_assistant_message=text)
    start, end = _agents(root)
    assert start["kind"] == "start"
    assert end == {"kind": "end", "session_id": "s1", "agent_id": "a1", "agent_type": "worker",
                   "started": iso(), "ended": iso(minutes=42, seconds=30), "elapsed_seconds": 2550.0,
                   "result": text, "result_source": "payload"}


def _transcript(path, records):
    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")


def test_result_comes_from_the_agent_transcript_when_the_payload_has_none(tmp_path, clock):
    """E3: with no `last_assistant_message`, the result is the text of the LAST assistant message of the file
    `agent_transcript_path` names (its text blocks joined, a tool call skipped), `result_source: transcript`.
    Catches: the first assistant message, a tool call's input read as the result, a transcript that is not read."""
    root = task_root(tmp_path)
    log = tmp_path / "agent-a1.jsonl"
    _transcript(log, [
        {"type": "user", "message": {"role": "user", "content": "the brief"}},
        {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "early note"}]}},
        {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "tool_use", "id": "t1", "name": "Read", "input": {"file_path": "x"}}]}},
        {"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": "file body"}]}},
        {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "text", "text": "the report, part one"}, {"type": "text", "text": "part two"}]}},
    ])
    _start(root)
    clock.after(minutes=1)
    _stop(root, agent_transcript_path=str(log))
    end = _agents(root)[-1]
    assert end["result"] == "the report, part one\npart two"
    assert end["result_source"] == "transcript"


def test_no_result_is_not_established(tmp_path, clock):
    """E4: no message in the payload, no transcript path (or a file that is missing): the row is still written with
    the result «not established» and `result_source: none`. Catches: a stop that writes no row when it has no text,
    or an empty string standing for a missing result."""
    root = task_root(tmp_path)
    _start(root, agent="a1")
    _start(root, agent="a2")
    clock.after(minutes=1)
    _stop(root, agent="a1")
    _stop(root, agent="a2", agent_transcript_path=str(tmp_path / "missing.jsonl"))
    ends = [r for r in _agents(root) if r["kind"] == "end"]
    assert [(r["agent_id"], r["result"], r["result_source"]) for r in ends] == [("a1", NE, "none"),
                                                                                  ("a2", NE, "none")]


def test_stop_without_a_start_row_has_no_times(tmp_path, clock):
    """E5: a stop whose start was never recorded (the hook was installed mid-run): `started` and `elapsed_seconds`
    are «not established»; `ended` is the stop time. Catches: a guessed start (the session's first row, the stop
    time) or an elapsed time of zero."""
    root = task_root(tmp_path)
    clock.after(minutes=5)
    _stop(root, last_assistant_message="done")
    (end,) = _agents(root)
    assert (end["started"], end["elapsed_seconds"], end["ended"]) == (NE, NE, iso(minutes=5))
    assert end["result"] == "done"


def test_a_stop_pairs_with_its_own_start(tmp_path, clock):
    """E6: the same agent id in another session, and another agent id in the same session, are not this agent's
    start. The stop of (s1, a1) takes the start row of (s1, a1) only. Catches: a pairing by agent id alone or by
    session alone, or by the last start row."""
    root = task_root(tmp_path)
    _start(root, agent="a1", session="s1")
    clock.after(minutes=10)
    _start(root, agent="a1", session="s2")
    _start(root, agent="a2", session="s1")
    clock.after(minutes=20)
    _stop(root, agent="a1", session="s1", last_assistant_message="r1")
    clock.after(minutes=25)
    _stop(root, agent="a1", session="s2", last_assistant_message="r2")
    ends = {(r["session_id"], r["agent_id"]): r for r in _agents(root) if r["kind"] == "end"}
    assert (ends[("s1", "a1")]["started"], ends[("s1", "a1")]["elapsed_seconds"]) == (iso(), 1200.0)
    assert (ends[("s2", "a1")]["started"], ends[("s2", "a1")]["elapsed_seconds"]) == (iso(minutes=10), 900.0)


def test_a_failed_record_never_blocks_and_adds_no_context(tmp_path, clock):
    """E7: when `agents.jsonl` cannot be written, the run exits 0 with nothing on stdout (an `additionalContext` on
    `SubagentStop` would keep the agent going), and a `warn` row `agent-record-failed` is in the refusal log.
    Catches: a refuse, an exit 2, or a warn rendered as context."""
    root = task_root(tmp_path)
    (root / "mkway" / "state" / "agents.jsonl").mkdir()  # a folder where the file should be: every append fails
    for res in (_start(root), _stop(root, last_assistant_message="r")):
        assert res.exit_code == 0 and res.stdout == "" and res.stderr == ""
    rows = jsonl(root / "mkway" / "state" / "refusals.jsonl")
    assert [(r["reason_id"], r["kind"], r["event"]) for r in rows] == [
        ("agent-record-failed", "warn", "SubagentStart"), ("agent-record-failed", "warn", "SubagentStop")]


def test_a_payload_without_an_agent_id_is_still_recorded(tmp_path, clock):
    """E8: a payload with no `agent_id` and no `agent_type` still gets its row, both «not established». Catches: a
    gate that skips an unreadable payload, so the result is lost."""
    root = task_root(tmp_path)
    _fire(root, "SubagentStop", last_assistant_message="r")
    (end,) = _agents(root)
    assert (end["agent_id"], end["agent_type"], end["result"]) == (NE, NE, "r")


def test_the_dispatcher_records_both_events(tmp_path, clock):
    """E9: through the dispatcher with the engine's own manifest: both events write their rows, exit 0, empty
    stdout; turning the gate off in the profile (`gates.agents.on: false`) writes none. Catches: a gate wired to
    one event only, or a switch that does nothing."""
    root = task_root(tmp_path)
    assert _start(root).exit_code == 0
    clock.after(minutes=2)
    res = _stop(root, last_assistant_message="r")
    assert (res.exit_code, res.stdout) == (0, "")
    assert [r["kind"] for r in _agents(root)] == ["start", "end"]
    off = task_root(tmp_path, name="off", gates={"agents": {"on": False}})
    _start(off)
    _stop(off, last_assistant_message="r")
    assert _agents(off) == []
