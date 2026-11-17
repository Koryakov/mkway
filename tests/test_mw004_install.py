"""Agent records, part 3 (card MW-004): install writes the hook entries of `SubagentStart` and `SubagentStop`,
through the root launcher, like the other entries (`python -I -X utf8 "${CLAUDE_PROJECT_DIR}/<bundle>/engine/mkway.py"
hook <event> --group post`). Synthetic task roots under the pytest temp folder only."""
import json

import pytest

from _engine import ENGINE, jsonl, make_profile
from _mw093_install import START, _entries, _run_command, clean_env, make_source, make_task, mkway
import install

LAUNCHER = 'python -I -X utf8 "${CLAUDE_PROJECT_DIR}/mkway/engine/mkway.py" hook '


    # the third `PreToolUse` is the SendMessage gate of MW-018


@pytest.mark.engine_repo  # the engine repository is the install source
def test_a_real_install_records_an_agent(tmp_path):
    """Catches: an entry that install writes but the launcher cannot run (a module that cannot be imported under `-I`), or drift on the new entries (E20: a real `mkway install` writes both entries; the generated commands, run as Claude Code runs them, exit 0 with nothing on stdout and append the start and the end row; the start block of the same session still says `drift: none`)."""
    src = make_source(tmp_path, vcs="none")
    task = make_task(tmp_path, vcs="none")
    env = clean_env(tmp_path)
    proc = mkway(task, env, "install", "--from", str(src), "--vcs", "none")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    commands = {event: h["command"] for event, _m, h in _entries(task) if event.startswith("Subagent")}
    assert set(commands) == {"SubagentStart", "SubagentStop"}
    base = {"session_id": "e2e", "agent_id": "a1", "agent_type": "worker"}
    run, _ = _run_command(task, env, commands["SubagentStart"], dict(base, hook_event_name="SubagentStart"), 60)
    assert (run.returncode, run.stdout) == (0, ""), run.stderr
    run, _ = _run_command(task, env, commands["SubagentStop"],
                          dict(base, hook_event_name="SubagentStop", last_assistant_message="the report"), 60)
    assert (run.returncode, run.stdout) == (0, ""), run.stderr
    start, end = jsonl(task / "mkway" / "state" / "agents.jsonl")
    assert (start["kind"], end["kind"], end["result"], end["result_source"]) == ("start", "end", "the report",
                                                                                 "payload")
    assert end["started"] == start["started"]
    assert isinstance(end["elapsed_seconds"], float)
    run, _ = _run_command(task, env, 'python -I -X utf8 "${CLAUDE_PROJECT_DIR}/mkway/engine/mkway.py" hook '
                                     "SessionStart --group start", START, 60)
    context = json.loads(run.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "drift: none" in context
    assert "gates on: " in context
    assert "agent_start" in context
    assert "agent_stop" in context
