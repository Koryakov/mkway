"""Card MW-110: the session-id check through the REAL hook command. One engine install (module fixture, a scratch git
repository) runs the shell hook entries the way Claude Code does: the generated command line, through the shell, a real
hook payload on stdin, and an environment that carries the launcher's variable or not. The verdict is read from the hook's
JSON, never only from the exit code. Synthetic sessions only."""
import json
import re
import subprocess

import pytest

from _hook_driver import Fired, HookRun, decision, install_project

pytestmark = pytest.mark.engine_repo

NAME = "MKWAY_SESSION_ID"
SESSION = "s-e2e-1"
COMMAND = "python mkway/engine/mkway.py board"


@pytest.fixture(scope="module")
def proj(tmp_path_factory):
    return install_project(tmp_path_factory.mktemp("mw110"))


def shell_hooks(p, session, command, env_extra):
    """Every PreToolUse hook entry of the shell group for a Bash call, as one real process each, with `env_extra` added to
    the hook's environment."""
    data = p.payload("PreToolUse", session, "Bash", {"command": command})
    env = {**p.env(session=True), **env_extra}
    fired = Fired("PreToolUse")
    for event, matcher, line, timeout in p.entries:
        if event == "PreToolUse" and "--group shell" in line and re.fullmatch(matcher or ".*", "Bash"):
            proc = subprocess.run([p.bash, "-c", line], input=json.dumps(data), capture_output=True, text=True,
                                  encoding="utf-8", cwd=str(p.root), env=env, timeout=timeout)
            fired.runs.append(HookRun("shell", line, proc.returncode, proc.stdout, proc.stderr, 0.0))
    return fired


@pytest.mark.parametrize("env_extra, command", [
    pytest.param({NAME: "another-session"}, COMMAND, id="mismatch"),
    pytest.param({NAME: SESSION}, f"{NAME}=another-session {COMMAND}", id="inline"),
])
def test_the_real_hook_denies_a_mismatch_and_an_inline_assignment(proj, env_extra, command):
    """Catches: a shell call whose environment id is another session's, or that assigns the variable inline, passing the
    real hook; the verdict is a deny `session-id-mismatch` from the entry `message.session`."""
    got = decision(shell_hooks(proj, SESSION, command, env_extra))
    assert (got.kind, got.reason_id, got.gate) == ("deny", "session-id-mismatch", "message.session")


def test_the_real_hook_allows_an_equal_id_with_no_warn(proj):
    """Checks: the nearest allow: the environment id is the hook's own id, the call passes and nothing is said."""
    fired = shell_hooks(proj, SESSION, COMMAND, {NAME: SESSION})
    assert decision(fired).kind == "allow"
    assert [r.stdout for r in fired.runs if "session-id" in r.stdout] == []


def test_the_real_hook_warns_for_an_unset_variable_and_allows(proj):
    """Checks: the transition: no variable in the hook's environment is an allow with one warn line `session-id-unset`
    that names the launcher line."""
    fired = shell_hooks(proj, "s-e2e-unset", COMMAND, {})
    assert decision(fired).kind == "allow"
    said = [r.stdout for r in fired.runs if "session-id-unset" in r.stdout]
    assert len(said) == 1
    assert "--session-id" in said[0]
