"""Card MW-027: install ends in a committed fence. The hook entries go into the committed `.claude/settings.json`, the
bundle `.gitignore` keeps run-time files out of the first `git add`, install prints (or with `--commit` runs) the two
commit lines, and a fresh worktree of that commit has working hooks with no install. Synthetic scratch repositories under
the pytest temp folder only."""
import json
import re
import subprocess

import pytest

import _docs as docs
from _engine import REPO, gate_call
from test_install import clean_env, git, make_source, make_task, mkway
import gate_lock
import install

pytestmark = pytest.mark.engine_repo

OWNED = 'hook'  # every owned command holds this word after the engine path
COMMIT_ENV = {"GIT_AUTHOR_NAME": "mkway-test", "GIT_AUTHOR_EMAIL": "mkway-test", "GIT_COMMITTER_NAME": "mkway-test",
              "GIT_COMMITTER_EMAIL": "mkway-test"}


def _version():
    return (REPO / "VERSION").read_text(encoding="utf-8").strip()


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _owned(path):
    """The owned hook commands of a settings file (those that run the copy's mkway.py)."""
    if not path.is_file():
        return []
    out = []
    for groups in (_read(path).get("hooks") or {}).values():
        for group in groups:
            out += [h["command"] for h in group.get("hooks", []) if "/mkway/engine/mkway.py" in h.get("command", "")]
    return out


def _run_entry(root, event, group, payload):
    """Run the committed hook command of `event`/`group` as Claude Code would, with CLAUDE_PROJECT_DIR set."""
    data = _read(root / ".claude" / "settings.json")
    command = next(h["command"] for g in data["hooks"][event] for h in g["hooks"] if f"--group {group}" in h["command"])
    env = clean_env(root.parent, CLAUDE_PROJECT_DIR=str(root))
    command = command.replace("${CLAUDE_PROJECT_DIR}", str(root))
    return subprocess.run(command, shell=True, input=json.dumps(payload), capture_output=True, text=True, env=env,
                          cwd=str(root), timeout=120)


def _install(tmp_path, *extra, vcs="git", name="task", fixture=False):
    src = make_source(tmp_path, vcs="none")
    task = make_task(tmp_path, vcs=vcs, name=name)
    proc = mkway(task, clean_env(tmp_path, **COMMIT_ENV), "install", "--from", str(src), "--vcs", vcs, *extra)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    return task, src, proc


def test_install_writes_the_bundle_gitignore_so_the_first_add_is_clean(tmp_path):
    """E1: after install, a session start and a refusal, the first `git add -A` of the task folder takes no
    run-time file: no state, locks, bytecode or check temp folder, no settings.local.json."""
    task, _src, _proc = _install(tmp_path)
    start = {"hook_event_name": "SessionStart", "session_id": "s1", "cwd": str(task)}
    assert _run_entry(task, "SessionStart", "start", start).returncode == 0
    edit = {"hook_event_name": "PreToolUse", "session_id": "s1", "cwd": str(task), "tool_name": "Edit",
            "tool_input": {"file_path": str(task / "mkway" / "profile.json"), "old_string": "a", "new_string": "b"}}
    refused = _run_entry(task, "PreToolUse", "edit", edit)
    assert "lock-closed-edit" in refused.stdout + refused.stderr
    git(task, "add", "-A")
    staged = git(task, "diff", "--cached", "--name-only").split()
    assert ".claude/settings.json" in staged and "mkway/.gitignore" in staged and "mkway/engine/mkway.py" in staged
    for bad in ("/state/", "/locks/", "__pycache__", ".pytest_tmp", "settings.local.json", ".pyc"):
        assert not [p for p in staged if bad in p], (bad, staged)
    assert git(task, "status", "--porcelain").count("??") == 0


@pytest.mark.parametrize("rel", [".claude/settings.json", ".claude/settings.local.json"])
def test_the_settings_files_are_protected_paths(tmp_path, rel):
    """E4: a session's edit of `.claude/settings.json` is refused; a commit of a staged change of it is refused
    (`lock-closed-commit`); the owner's commit, run in their terminal, is not a hook call and is not affected."""
    task, _src, _proc = _install(tmp_path)
    edit = gate_call(gate_lock.check, task, tool="Write", tool_input={"file_path": str(task / rel), "content": "{}"},
                     session="s1")
    assert (edit.kind, edit.reason_id) == ("refuse", "lock-closed-edit")
    if rel.endswith("settings.json"):
        git(task, "add", "-A")
        git(task, "commit", "-q", "-m", "base")
        path = task / rel
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        git(task, "add", rel)
        verdict = gate_call(gate_lock.check, task, tool="Bash", tool_input={"command": 'git commit -m "x"'},
                            session="s1")
        assert (verdict.kind, verdict.reason_id) == ("refuse", "lock-closed-commit")


def test_a_fresh_worktree_has_working_hooks_with_no_install(tmp_path):
    """E7: after install and the commit, a worktree added from it runs the start hook from the committed
    `settings.json`: exit 0, the start block, and no drift against the copy or the interpreter."""
    src = make_source(tmp_path, vcs="none")
    task = make_task(tmp_path, vcs="git")
    env = clean_env(tmp_path, **COMMIT_ENV)
    assert mkway(task, env, "install", "--from", str(src), "--commit").returncode == 0
    wt = tmp_path / "wt"
    git(task, "worktree", "add", "-q", str(wt), "-b", "wt")
    assert not (wt / "mkway" / "state").exists()
    start = {"hook_event_name": "SessionStart", "session_id": "s2", "cwd": str(wt)}
    proc = _run_entry(wt, "SessionStart", "start", start)
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, out
    assert "mkway v" in out
    assert "drift-machine" not in out and "hook entries:" not in out and "copy:" not in out.replace("copy: ok", "")


