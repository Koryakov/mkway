"""Card MW-027: install ends in a committed fence. The hook entries go into the committed `.claude/settings.json`, the
bundle `.gitignore` keeps run-time files out of the first `git add`, install prints (or with `--commit` runs) the two
commit lines, and a fresh worktree of that commit has working hooks with no install. Synthetic scratch repositories under
the pytest temp folder only."""
import json
import re
import subprocess

import pytest

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


def test_install_writes_the_bundle_gitignore_with_vcs_none_too(tmp_path):
    """E1: the bundle `.gitignore` is written whatever the profile's vcs says, so a git repository that the
    profile calls `none` still offers no run-time file."""
    task, _src, _proc = _install(tmp_path, vcs="none")
    text = (task / "mkway" / ".gitignore").read_text(encoding="utf-8").splitlines()
    for line in ("state/", "locks/", "__pycache__/", ".pytest_tmp/"):
        assert line in text, line
    assert "engine/" not in text  # the engine copy is tracked, so a fresh worktree needs no install


def test_hook_entries_go_into_the_committed_settings_json(tmp_path):
    """E2: the owned entries are in `.claude/settings.json`, once each; an existing file is merged (other keys byte for
    byte, other hooks kept); a reinstall replaces only mkway's own entries; `settings.local.json` is not written."""
    src = make_source(tmp_path, vcs="none")
    task = make_task(tmp_path, vcs="git")
    settings = task / ".claude" / "settings.json"
    settings.parent.mkdir()
    foreign = {"matcher": "Bash", "hooks": [{"type": "command", "command": "python other_hook.py", "timeout": 5}]}
    head = '{\n  "env": {"A":   "1"},\n'
    settings.write_text(head + '  "hooks": ' + json.dumps({"PreToolUse": [foreign]}) + "\n}\n", encoding="utf-8")
    env = clean_env(tmp_path)
    assert mkway(task, env, "install", "--from", str(src)).returncode == 0
    first = settings.read_text(encoding="utf-8")
    assert first.startswith(head)
    data = json.loads(first)
    assert foreign in data["hooks"]["PreToolUse"]
    owned = _owned(settings)
    assert owned and len(owned) == len(set(owned))
    assert not (task / ".claude" / "settings.local.json").exists()
    assert mkway(task, env, "install", "--from", str(src)).returncode == 0
    assert settings.read_text(encoding="utf-8") == first


def test_a_reinstall_strips_mkways_entries_from_settings_local_json(tmp_path):
    """E3: an old-style install put the entries into `settings.local.json`; the reinstall leaves each hook once (in
    `settings.json`) and keeps the owner's own entries and keys of the local file."""
    src = make_source(tmp_path, vcs="none")
    task = make_task(tmp_path, vcs="git")
    env = clean_env(tmp_path)
    assert mkway(task, env, "install", "--from", str(src)).returncode == 0
    entries = _owned(task / ".claude" / "settings.json")
    (task / ".claude" / "settings.json").unlink()
    local = task / ".claude" / "settings.local.json"
    own = {"matcher": "Bash", "hooks": [{"type": "command", "command": "python mine.py", "timeout": 5}]}
    local.write_text(json.dumps({"permissions": {"allow": ["Read(x)"]}, "hooks": {"PreToolUse": [own]}}, indent=2),
                     encoding="utf-8")
    install.write_settings(local, install.generate_entries(_read(task / "mkway" / "profile.json"), json.loads(
        (task / "mkway" / "engine" / "engine" / "manifest.json").read_text(encoding="utf-8"))["entries"]), "mkway")
    assert len(_owned(local)) == len(entries)
    assert mkway(task, env, "install", "--from", str(src)).returncode == 0
    assert _owned(local) == []
    assert sorted(_owned(task / ".claude" / "settings.json")) == sorted(entries)
    data = _read(local)
    assert data["permissions"] == {"allow": ["Read(x)"]} and data["hooks"]["PreToolUse"] == [own]


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


def test_install_prints_the_two_commit_lines(tmp_path):
    """E5 (changed by MW-035): with vcs git, install ends with ONE line, `git add <paths>; git commit -m "mkway
    <version>: install" -- <paths>`; with vcs none it prints neither."""
    _task, _src, proc = _install(tmp_path)
    lines = proc.stdout.strip().splitlines()
    paths = ".claude/settings.json mkway"
    assert lines[-1] == f'git add {paths}; git commit -m "mkway {_version()}: install" -- {paths}'
    _task2, _src2, proc2 = _install(tmp_path, vcs="none", name="task2")
    assert "git add" not in proc2.stdout and "git commit" not in proc2.stdout


def test_install_commit_runs_the_two_lines_in_the_owners_terminal_only(tmp_path):
    """E6: `install --commit` makes the commit with that message and leaves the tree clean; inside a Claude chat
    (CLAUDECODE present) it is refused as an owner-only command and nothing is committed; with vcs none it refuses."""
    src = make_source(tmp_path, vcs="none")
    task = make_task(tmp_path, vcs="git")
    chat = mkway(task, clean_env(tmp_path, CLAUDECODE="1", **COMMIT_ENV), "install", "--from", str(src), "--commit")
    assert chat.returncode != 0 and "owner-only-command" in chat.stderr + chat.stdout
    assert subprocess.run(["git", "rev-parse", "--verify", "-q", "HEAD"], cwd=str(task)).returncode != 0
    done = mkway(task, clean_env(tmp_path, **COMMIT_ENV), "install", "--from", str(src), "--commit")
    assert done.returncode == 0, done.stderr + done.stdout
    assert git(task, "log", "-1", "--format=%s").strip() == f"mkway {_version()}: install"
    assert git(task, "status", "--porcelain").strip() == ""
    plain = make_task(tmp_path, vcs="none", name="plain")
    bad = mkway(plain, clean_env(tmp_path, **COMMIT_ENV), "install", "--from", str(src), "--vcs", "none", "--commit")
    assert bad.returncode != 0 and "--commit needs vcs git" in bad.stderr + bad.stdout


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


def test_the_engine_copy_is_never_converted_by_git(tmp_path):
    """E8: `mkway/.gitattributes` keeps the copy's bytes (`engine/** -text`), so a checkout with autocrlf cannot
    change the copy's hash."""
    task, _src, _proc = _install(tmp_path)
    out = git(task, "check-attr", "text", "mkway/engine/mkway.py")
    assert out.strip().endswith("text: unset")


def test_an_older_ignore_line_for_the_engine_copy_is_reported(tmp_path):
    """E9 (changed by MW-035): a bundle `.gitignore` from an earlier install that still ignores `engine/`: install
    removes that exact line and reports it in one line; the lines that ignore `locks/` and `state/` stay."""
    src = make_source(tmp_path, vcs="none")
    task = make_task(tmp_path, vcs="git")
    (task / "mkway").mkdir()
    (task / "mkway" / ".gitignore").write_text("engine/\nlocks/\nstate/\n", encoding="utf-8")
    proc = mkway(task, clean_env(tmp_path), "install", "--from", str(src))
    assert proc.returncode == 0
    assert "ignore: removed engine/ (from an earlier install)" in proc.stdout.splitlines()
    kept = (task / "mkway" / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "engine/" not in kept and "locks/" in kept and "state/" in kept


def test_readme_use_in_a_task_has_five_lines_and_no_ignored_settings_claim():
    """E10: «Use in a task» opens with five numbered lines (worktree, install, commit, open the lead, done); no README
    line calls `.claude/settings.local.json` git-ignored as the place of the hook entries."""
    text = (REPO / "README.md").read_text(encoding="utf-8")
    section = text.split("\n## Use in a task\n", 1)[1].split("\n## ", 1)[0]
    numbered = [line for line in section.splitlines() if re.match(r"^[1-9]\. ", line)]
    assert len(numbered) == 5, numbered
    for word, line in zip(("worktree", "install", "commit", "lead", "done"), numbered):
        assert word in line.lower(), (word, line)
    flat = " ".join(text.split())
    assert not re.search(r"settings\.local\.json`?,? which are git-ignored", flat)
    assert "hook entries into `.claude/settings.local.json`" not in flat


def test_register_changelog_and_version_name_the_card():
    """E11: the register row, `## 0.2.7` on top of the changelog with the card, VERSION 0.2.7."""
    register = (REPO / "cards" / "REGISTER.md").read_text(encoding="utf-8")
    assert re.search(r"^\| MW-027 \|.*`cards/MW-027-[a-z0-9-]+`", register, re.M)
    text = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    assert text.index("\n## 0.2.7\n") < text.index("\n## 0.2.6\n")
    assert "MW-027" in text.split("\n## 0.2.7\n", 1)[1].split("\n## ", 1)[0]
    assert list((REPO / "cards").glob("MW-027-*/CARD.md"))
    assert _version() == "0.2.7"
