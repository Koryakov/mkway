"""Agent records, part 3 (card MW-004): install writes the hook entries of `SubagentStart` and `SubagentStop`,
through the root launcher, like the other entries (`python -I -X utf8 "${CLAUDE_PROJECT_DIR}/<bundle>/engine/mkway.py"
hook <event> --group post`). Synthetic task roots under the pytest temp folder only."""
import json

import pytest

from _engine import ENGINE, jsonl, make_profile
import install

LAUNCHER = 'python -I -X utf8 "${CLAUDE_PROJECT_DIR}/mkway/engine/mkway.py" hook '


def _manifest():
    return json.loads((ENGINE / "manifest.json").read_text(encoding="utf-8"))["entries"]


def test_generate_entries_has_both_agent_events():
    """E17: with the engine's own manifest and a default profile, the entries are one per event and group, the two
    agent events after PostToolUse and before any later event; each is a whole entry through the root launcher with
    no matcher (every agent), no onFailure (the `post` group's), timeout 10 + 15 s. Catches: an event missing from
    the install's event order (no entry), a matcher that limits the record to one agent type, a `block`."""
    entries = install.generate_entries(make_profile(), _manifest())
    assert [(e["event"], e["group"]) for e in entries] == [
        ("SessionStart", "start"), ("UserPromptSubmit", "prompt"), ("PreToolUse", "edit"), ("PreToolUse", "shell"),
        ("PreToolUse", "message"),  # changed by MW-018 (E12): the SendMessage gate
        ("PostToolUse", "post"), ("SubagentStart", "post"), ("SubagentStop", "post"),
        ("Stop", "stop")]  # the owner-ask stop gate of MW-007 comes after the agent events
    by_event = {e["event"]: e for e in entries}
    for event in ("SubagentStart", "SubagentStop"):
        assert by_event[event] == {"event": event, "group": "post", "matcher": None,
                                   "command": LAUNCHER + f"{event} --group post", "timeout": 25, "on_failure": None}


def test_the_gate_switch_drops_both_entries():
    """E18: `gates.agents.on: false` leaves out both agent entries and no other. Catches: a switch that does one
    event only, or one that drops the whole `post` group."""
    on = install.generate_entries(make_profile(), _manifest())
    assert {"SubagentStart", "SubagentStop"} <= {e["event"] for e in on}  # on by default, so the switch has an effect
    entries = install.generate_entries(make_profile(gates={"agents": {"on": False}}), _manifest())
    assert [e["event"] for e in entries] == ["SessionStart", "UserPromptSubmit", "PreToolUse", "PreToolUse",
                                             "PreToolUse", "PostToolUse", "Stop"]  # `Stop`: the owner-ask gate of MW-007;
    # the third `PreToolUse` is the SendMessage gate of MW-018


def test_settings_hold_the_agent_entries_once(tmp_path):
    """E19: `write_settings` puts a group with no matcher under each event; a second write changes nothing (no
    duplicate), and a hook it does not own under the same event is kept. Catches: an entry with a `matcher` key, a
    duplicate after a re-install, a foreign hook removed."""
    profile = make_profile()
    entries = install.generate_entries(profile, _manifest())
    settings = tmp_path / ".claude" / "settings.local.json"
    settings.parent.mkdir()
    foreign = {"hooks": [{"type": "command", "command": "python other_hook.py", "timeout": 5}]}
    settings.write_text(json.dumps({"hooks": {"SubagentStop": [foreign]}}), encoding="utf-8")
    install.write_settings(settings, entries, "mkway")
    first = settings.read_text(encoding="utf-8")
    install.write_settings(settings, entries, "mkway")
    assert settings.read_text(encoding="utf-8") == first
    hooks = json.loads(first)["hooks"]
    assert hooks["SubagentStart"] == [{"hooks": [{"type": "command", "command": LAUNCHER + "SubagentStart --group post",
                                                  "timeout": 25}]}]
    assert hooks["SubagentStop"] == [foreign, {"hooks": [{"type": "command",
                                                          "command": LAUNCHER + "SubagentStop --group post",
                                                          "timeout": 25}]}]


@pytest.mark.engine_repo  # the engine repository is the install source
def test_a_real_install_records_an_agent(tmp_path):
    """E20: a real `mkway install` writes both entries; the generated commands, run as Claude Code runs them
    (the project dir from the env, the hook JSON on stdin), exit 0 with nothing on stdout and append the start and
    the end row; the start block of the same session still says `drift: none`. Catches: an entry that install
    writes but the launcher cannot run (a module that cannot be imported under `-I`), or drift on the new entries."""
    from test_e2e import START, _entries, _run_command
    from test_install import clean_env, make_source, make_task, mkway
    src = make_source(tmp_path, vcs="none")
    task = make_task(tmp_path, vcs="none")
    env = clean_env(tmp_path)
    proc = mkway(task, env, "install", "--from", str(src), "--vcs", "none")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    commands = {event: h["command"] for event, _m, h in _entries(task) if event.startswith("Subagent")}
    assert set(commands) == {"SubagentStart", "SubagentStop"}
    base = {"session_id": "e2e", "agent_id": "a1", "agent_type": "worker"}
    for event, extra in (("SubagentStart", {}), ("SubagentStop", {"last_assistant_message": "the report"})):
        run, _ = _run_command(task, env, commands[event], dict(base, hook_event_name=event, **extra), 60)
        assert (run.returncode, run.stdout) == (0, ""), run.stderr
    start, end = jsonl(task / "mkway" / "state" / "agents.jsonl")
    assert (start["kind"], end["kind"], end["result"], end["result_source"]) == ("start", "end", "the report",
                                                                                 "payload")
    assert end["started"] == start["started"] and isinstance(end["elapsed_seconds"], float)
    run, _ = _run_command(task, env, 'python -I -X utf8 "${CLAUDE_PROJECT_DIR}/mkway/engine/mkway.py" hook '
                                     "SessionStart --group start", START, 60)
    context = json.loads(run.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "drift: none" in context
    assert "gates on: " in context and "agent_start" in context and "agent_stop" in context

