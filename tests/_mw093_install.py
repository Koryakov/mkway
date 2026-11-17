"""Helpers of the install test of card MW-004 (copied for MW-093, rule S5: a test does not import another test module).

Copied from tests/test_e2e.py (`_entries`, `_run_command`, `START`) and from tests/test_install.py (`make_source` for
vcs none with the engine's own gates, `make_task`, `clean_env`, `mkway`). The copies build their source fresh in the
test's own folder: the shared source cache of tests/test_install.py needs its session fixture, which this module does
not use. Synthetic task roots only."""
import json
import os
import shlex
import subprocess
import sys
import time

import install
from _engine import REPO

START = {"session_id": "e2e", "hook_event_name": "SessionStart", "source": "startup"}


def _entries(task):
    data = json.loads((task / ".claude" / "settings.json").read_text(encoding="utf-8"))
    for event, groups in data["hooks"].items():
        for group in groups:
            for h in group["hooks"]:
                yield event, group.get("matcher"), h


def _run_command(task, env, command, payload, timeout):
    """Run a generated command as Claude Code would: ${CLAUDE_PROJECT_DIR} from the env, JSON on stdin, and the
    `CLAUDECODE` a session's hooks carry (close-fix 1: the suite no longer inherits it from the chat it runs in)."""
    expanded = command.replace("${CLAUDE_PROJECT_DIR}", task.as_posix())
    argv = shlex.split(expanded)
    assert argv[0] == "python"
    argv[0] = sys.executable
    run_env = dict(env, CLAUDE_PROJECT_DIR=str(task), CLAUDECODE="1")
    started = time.monotonic()
    proc = subprocess.run(argv, input=json.dumps(payload), capture_output=True, text=True, env=run_env,
                          timeout=timeout)
    return proc, time.monotonic() - started


def make_source(tmp_path, *, vcs):
    """An engine source of this repository's working tree with the engine's own gates, built in tmp_path (vcs none)."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    src = tmp_path / f"src-{vcs}"
    for rel, data in install.folder_files(REPO).items():
        path = src / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return src


def make_task(tmp_path, *, vcs, name="task"):
    root = tmp_path / name
    root.mkdir()
    return root


def clean_env(tmp_path, **extra):
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_PROJECT_DIR", "ENGINE_TERMS_FILE")}
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    env.update(HOME=str(home), USERPROFILE=str(home))
    env.update(extra)
    return env


def mkway(root, env, *args):
    return subprocess.run([sys.executable, str(REPO / "mkway.py"), *args, "--root", str(root)],
                          capture_output=True, text=True, env=env, timeout=300)
