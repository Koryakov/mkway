"""Agent records, part 2 (card MW-004): the profile key `agents.cap_minutes` and the start-block lines.

The start block shows one line for each agent of THIS session that ran over the cap, or that has a start row with no
end row. Synthetic task roots and synthetic `agents.jsonl` rows only.
"""
import datetime
import json

import pytest

from _engine import make_profile, task_root
import agents
import dispatch
import logs
import profiles

T0 = datetime.datetime(2026, 11, 10, 8, 0, 0, tzinfo=datetime.timezone.utc)
NE = "not established"


def iso(minutes=0):
    return (T0 + datetime.timedelta(minutes=minutes)).isoformat(timespec="milliseconds")


def start_row(agent, at, session="s1", kind="worker"):
    return {"kind": "start", "session_id": session, "agent_id": agent, "agent_type": kind, "started": iso(at)}


def end_row(agent, began, took_minutes, session="s1", kind="worker"):
    return {"kind": "end", "session_id": session, "agent_id": agent, "agent_type": kind, "started": iso(began),
            "ended": iso(began + took_minutes), "elapsed_seconds": took_minutes * 60.0, "result": "r",
            "result_source": "payload"}


def _put(root, rows):
    path = root / "mkway" / "state" / "agents.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def _agent_lines(root, session="s1", now_minutes=600, monkeypatch=None):
    """The `agent ...` lines of the SessionStart block for `session`, with the clock at minute `now_minutes`."""
    monkeypatch.setattr(logs, "now", lambda: T0 + datetime.timedelta(minutes=now_minutes))
    payload = {"session_id": session, "hook_event_name": "SessionStart", "source": "resume"}
    res = dispatch.run("SessionStart", "start", json.dumps(payload), env={"CLAUDE_PROJECT_DIR": str(root)})
    assert res.exit_code == 0
    context = json.loads(res.stdout)["hookSpecificOutput"]["additionalContext"]
    return [line for line in context.splitlines() if line.startswith("agent ")]


@pytest.mark.parametrize("value", [30, 0.5, 90, 1])
def test_schema_takes_a_positive_cap(value):
    """Checks: `agents.cap_minutes` is a number above 0 (E10), so the profile validates."""
    assert profiles.validate(make_profile(agents={"cap_minutes": value})) == []


@pytest.mark.parametrize("value", [0, -5, "30", True, None, [30]])
def test_schema_refuses_an_unusable_cap(value):
    """Catches: a cap of 0 (every agent over it), a cap read as text, a boolean read as 1 (E10: zero, a negative number, a string, a boolean, null and a list are profile errors naming the key)."""
    errors = profiles.validate(make_profile(agents={"cap_minutes": value}))
    assert errors
    assert all(e.startswith("agents.cap_minutes") for e in errors), errors


def test_schema_refuses_another_agents_key():
    """Catches: a misspelt key that is silently ignored (E10: the agents group takes cap_minutes only)."""
    errors = profiles.validate(make_profile(agents={"cap_minute": 30}))
    assert any(e.startswith("agents.cap_minute") for e in errors), errors


def test_cap_default_and_profile_value():
    """Checks: no key, no agents group, or a profile that is not an object gives 30 minutes, and the profile value wins (E11)."""
    assert agents.cap_minutes(make_profile()) == 30
    assert agents.cap_minutes(make_profile(agents={})) == 30
    assert agents.cap_minutes(None) == 30
    assert agents.cap_minutes(make_profile(agents={"cap_minutes": 5})) == 5
    assert agents.cap_minutes(make_profile(agents={"cap_minutes": 0.5})) == 0.5


def test_start_block_lists_an_agent_over_the_cap(tmp_path, monkeypatch):
    """Catches: a `>=` for `>`, another session's agents shown, a line per row instead of per agent (E12: an agent of this session over the cap gets one line with type, id, minutes and cap; at the cap, under it, another session's agent and an end row with no known time get none)."""
    root = task_root(tmp_path)
    _put(root, [
        start_row("over", 0), end_row("over", 0, 31),
        end_row("exact", 0, 30), end_row("under", 0, 29),
        start_row("other", 0, session="s2"), end_row("other", 0, 90, session="s2"),
        dict(end_row("unknown", 0, 0), started=NE, elapsed_seconds=NE),
    ])
    (line,) = _agent_lines(root, monkeypatch=monkeypatch)
    assert line == (f"agent worker over: ran 31.0 min, over the cap of 30 min "
                    f"(started {iso(0)}, ended {iso(31)})")


def test_start_block_lists_an_agent_with_no_end_row(tmp_path, monkeypatch):
    """Catches: an unfinished agent that is not shown, a finished one that is, or a pairing by agent id alone (E13: a start row with no end row after it gets one line whatever the cap; a resumed agent with no second end does)."""
    root = task_root(tmp_path)
    _put(root, [
        start_row("lost", 480),
        start_row("done", 100), end_row("done", 100, 5),
        start_row("again", 200), end_row("again", 200, 5), start_row("again", 300),
        start_row("other", 480, session="s2"),
    ])
    lines = _agent_lines(root, now_minutes=600, monkeypatch=monkeypatch)
    assert lines == [
        f"agent worker lost: started {iso(480)}, no end row (120.0 min so far, cap 30 min)",
        f"agent worker again: started {iso(300)}, no end row (300.0 min so far, cap 30 min)"]


def test_profile_cap_sets_the_limit(tmp_path, monkeypatch):
    """Catches: a cap fixed at 30 in the start block (E12: with agents.cap_minutes 5 a 6-minute agent is listed and a 4-minute one is not, and the line names the profile's cap)."""
    root = task_root(tmp_path, agents={"cap_minutes": 5})
    _put(root, [end_row("six", 0, 6), end_row("four", 0, 4)])
    (line,) = _agent_lines(root, monkeypatch=monkeypatch)
    assert "agent worker six: ran 6.0 min, over the cap of 5 min" in line


def test_start_block_has_no_agent_line_when_there_is_nothing(tmp_path, monkeypatch):
    """Catches: a header or an empty line added to every start block (E14: no agents file, or only rows of finished agents under the cap, gives no line)."""
    root = task_root(tmp_path)
    assert _agent_lines(root, monkeypatch=monkeypatch) == []
    _put(root, [start_row("a", 0), end_row("a", 0, 3)])
    assert _agent_lines(root, monkeypatch=monkeypatch) == []


def test_a_damaged_agents_file_is_skipped_not_fatal(tmp_path, monkeypatch):
    """Catches: a start block that fails on one bad line (E15: a line that is not JSON and a row of the wrong shape are skipped; the start block still shows the other agents)."""
    root = task_root(tmp_path)
    path = root / "mkway" / "state" / "agents.jsonl"
    path.write_text("not json\n" + json.dumps([1, 2]) + "\n" + json.dumps(end_row("over", 0, 45)) + "\n"
                    + json.dumps({"kind": "start", "session_id": "s1"}) + "\n", encoding="utf-8")
    lines = _agent_lines(root, monkeypatch=monkeypatch)
    assert len(lines) == 2
    assert lines[0].startswith("agent worker over: ran 45.0 min")
    assert lines[1] == "agent not established not established: started not established, no end row (cap 30 min)"


def test_keys_md_lists_the_cap():
    """Checks: KEYS.md lists agents.cap_minutes among the added keys, in schema now, with its default 30 (E16)."""
    from _keys_md import section_rows, unquote
    rows = {unquote(r[0]): r for r in section_rows("Added keys")}
    key, verdict, path, values, reason = rows["agents.cap_minutes"]
    assert (verdict, unquote(path)) == ("in schema now", "agents.cap_minutes")
    assert "default 30" in values
    assert reason
