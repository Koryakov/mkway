"""Deletes (card MW-009), part P4: loss of uncommitted work counts as a delete: `git clean -f`, `git reset --hard`,
`git restore` and `git checkout --` on a path with changes, `git rm` of a changed file; `git rm` of a clean tracked
file is allowed with a record row and no copy. Synthetic task roots, real throwaway git repositories."""
import os

from _commit_fixture import git, make_task, save, stage, work
from _engine import gate_call, jsonl, task_root


def _gate():
    import importlib
    return importlib.import_module("gate_delete")


def _check(root, command, tool="Bash", session="s1"):
    return gate_call(_gate().check, root, tool=tool, tool_input={"command": command}, session=session)


def _reason(verdict):
    return verdict.reason_id if verdict.kind == "refuse" else "allow"


def _task(tmp_path, **over):
    """A git task root with two committed files, `src/a.py` and `src/clean.py`; the tree is clean."""
    root = make_task(tmp_path, card_paths="", **over)
    save(root, "src/a.py", "v1\n")
    save(root, "src/clean.py", "c1\n")
    return root


def subprocess_result(code):
    import subprocess
    return subprocess.CompletedProcess(["git"], code, stdout="", stderr="fatal: not a git repository")


def _rows(root):
    path = root / "mkway" / "state" / "deletes.jsonl"
    return jsonl(path) if path.is_file() else []


def _folders(root):
    trash = root / "mkway" / "state" / "trash"
    return sorted(os.listdir(trash)) if trash.is_dir() else []


def test_git_clean_with_force_is_refused(tmp_path):
    """E21 (part 4): `git clean` with `-f` or `--force` (alone or in a cluster, any position, with `-C`) is
    `delete-uncommitted` even on a clean tree, because untracked files are in no commit; a dry run (`-n`,
    `--dry-run`) and a `git clean` without force pass; the profile `vcs: none` does not switch it off. Catches: the
    quiet loss of every untracked file of the task."""
    root = _task(tmp_path)
    for cmd in ("git clean -f", "git clean -fd", "git clean -fdx", "git clean -f -d", "git clean --force",
                "git clean -d -f -x", "git -C . clean -fd", "echo x && git clean -fdx", "bash -c 'git clean -f'",
                "git clean -ffd", "git clean -f -- src", "cd src && git clean -f"):
        v = _check(root, cmd)
        assert v.kind == "refuse" and v.reason_id == "delete-uncommitted", cmd
        assert "git clean" in v.message and "mkway delete --list <file>" in v.message, cmd
    for cmd in ("git clean -n", "git clean -nd", "git clean --dry-run", "git clean -d", "git clean", "git status"):
        assert _reason(_check(root, cmd)) == "allow", cmd
    plain = task_root(tmp_path / "plain", vcs="none")
    assert _reason(_check(plain, "git clean -fd")) == "delete-uncommitted"
    assert _rows(root) == []


def test_git_reset_hard_is_refused_only_when_the_tree_has_changes(tmp_path):
    """E22 (part 4): `git reset --hard` is `delete-uncommitted` when a tracked file has a staged or an unstaged change,
    and passes on a clean tree and when only untracked files exist; `--soft`, `--mixed` and a plain reset never lose
    work; with `vcs: none` git is not read. Catches: a hard reset that throws away work, and a gate that blocks
    every reset."""
    root = _task(tmp_path)
    assert _reason(_check(root, "git reset --hard")) == "allow"
    assert _reason(_check(root, "git reset --hard HEAD~1")) == "allow"
    work(root, "new.txt", "untracked\n")
    assert _reason(_check(root, "git reset --hard")) == "allow"
    work(root, "src/a.py", "v2\n")
    for cmd in ("git reset --hard", "git reset --hard HEAD", "git reset -q --hard origin/x", "git -C . reset --hard",
                "true && git reset --hard"):
        v = _check(root, cmd)
        assert v.kind == "refuse" and v.reason_id == "delete-uncommitted", cmd
        assert "src/a.py" in v.message, cmd
    for cmd in ("git reset --soft HEAD~1", "git reset --mixed", "git reset", "git reset HEAD src/a.py"):
        assert _reason(_check(root, cmd)) == "allow", cmd
    stage(root, "src/a.py")  # now a staged change only
    assert _reason(_check(root, "git reset --hard")) == "delete-uncommitted"
    plain = task_root(tmp_path / "plain", vcs="none")
    assert _reason(_check(plain, "git reset --hard")) == "allow"


def test_restore_and_checkout_of_a_changed_path_are_refused(tmp_path):
    """E23 (part 4): `git restore <path>` and `git checkout -- <path>` (also `git checkout <tree> -- <path>`,
    `restore --source=<tree>`, `restore .`, `checkout .`) are `delete-uncommitted` when the path has a change, and pass
    for a clean path, for a path deleted from the working tree (nothing to lose), for `restore --staged` (the index
    only) and for a branch switch; `restore --staged --worktree` is a worktree restore. Catches: a revert that throws
    away work, and false blocks of a harmless restore."""
    root = _task(tmp_path)
    work(root, "src/a.py", "v2\n")
    for cmd in ("git restore src/a.py", "git restore -- src/a.py", "git checkout -- src/a.py",
                "git checkout HEAD -- src/a.py", "git restore --source=HEAD src/a.py", "git restore .",
                "git checkout -- .", "git checkout .", "git restore src", "git restore --staged --worktree src/a.py",
                "git restore -W src/a.py", "git restore src/clean.py src/a.py", "cd src && git restore a.py"):
        v = _check(root, cmd)
        assert v.kind == "refuse" and v.reason_id == "delete-uncommitted", cmd
        assert "src/a.py" in v.message, cmd
    for cmd in ("git restore src/clean.py", "git checkout -- src/clean.py", "git checkout HEAD -- src/clean.py",
                "git restore --staged src/a.py", "git restore -S src/a.py", "git checkout main", "git checkout -b topic",
                "git checkout", "git restore --help"):
        assert _reason(_check(root, cmd)) == "allow", cmd
    git(root, "checkout", "--", "src/a.py")
    os.remove(root / "src" / "clean.py")  # the test's own step: a path deleted from the working tree
    assert _reason(_check(root, "git restore src/clean.py")) == "allow"
    assert _reason(_check(root, "git checkout -- src/clean.py")) == "allow"
    for cmd, reason in (("git restore ../x", "delete-outside-root"), ("git restore 'src/*.py'", "delete-wildcard"),
                        ("git restore $F", "delete-target-unknown")):
        assert _reason(_check(root, cmd)) == reason, cmd


def test_git_rm_of_a_changed_file_is_refused_and_a_clean_one_is_recorded(tmp_path):
    """E24 (part 4): `git rm` of a path with a staged or unstaged change (also with `-f`, and a folder holding one) is
    `delete-uncommitted`; of a clean tracked path (file or folder) it is allowed with one record row and no copy, git
    keeps the file; `--cached` and `-n` are not deletes, an untracked path leaves no row; a wildcard, a path outside
    the root and a computed one keep their own reasons; one row covers a command that also deletes files. Catches: a
    `git rm` that loses a change, or one that is backed up needlessly."""
    root = _task(tmp_path)
    save(root, "lib/x.py", "x1\n")
    work(root, "src/a.py", "v2\n")
    for cmd in ("git rm src/a.py", "git rm -f src/a.py", "git rm -rf src", "git rm -r src", "git rm --force src/a.py",
                "git rm src/clean.py src/a.py", "git rm -- src/a.py"):
        v = _check(root, cmd)
        assert v.kind == "refuse" and v.reason_id == "delete-uncommitted", cmd
        assert "src/a.py" in v.message, cmd
    stage(root, "src/a.py")
    assert _reason(_check(root, "git rm src/a.py")) == "delete-uncommitted"  # a staged change is a change too
    assert _rows(root) == [] and _folders(root) == []
    for cmd, reason in (("git rm 'lib/*.py'", "delete-wildcard"), ("git rm ../x.py", "delete-outside-root"),
                        ("git rm $F", "delete-target-unknown"), ("git rm -rf mkway/state", "delete-target-unknown")):
        assert _reason(_check(root, cmd)) == reason, cmd
    for cmd in ("git rm --cached src/a.py", "git rm -n lib/x.py", "git rm --dry-run lib/x.py", "git rm new.txt"):
        work(root, "new.txt", "u\n")
        assert _reason(_check(root, cmd)) == "allow", cmd
    assert _rows(root) == []  # none of those is a delete
    assert _reason(_check(root, "git rm lib/x.py")) == "allow"
    assert _reason(_check(root, "git rm -r lib")) == "allow"
    rows = _rows(root)
    assert [r["targets"] for r in rows] == [["lib/x.py"], ["lib"]]
    assert all(r["backup"] is None and r["via"] == "gate" and r["session"] == "s1" for r in rows)
    assert _folders(root) == [] and (root / "lib" / "x.py").is_file()
    work(root, "tmp.txt", "t\n")
    assert _reason(_check(root, "rm tmp.txt && git rm lib/x.py")) == "allow"
    last = _rows(root)[-1]
    assert last["targets"] == ["tmp.txt", "lib/x.py"] and last["backup"]
    (name,) = _folders(root)
    assert (root / "mkway" / "state" / "trash" / name / "tmp.txt").is_file()
    assert not (root / "mkway" / "state" / "trash" / name / "lib").exists()


def test_a_git_read_that_fails_refuses_the_delete(tmp_path, monkeypatch):
    """E25 (part 4): a git read that does not answer (a timeout, a non-zero exit) is `delete-uncommitted` with the
    reason in the text, never an allow. Catches: a gate that lets a hard reset through because git was slow."""
    import runner
    root = _task(tmp_path)
    work(root, "src/a.py", "v2\n")

    def slow(*_a, **_k):
        raise runner.TimeoutExpired(["git"], 10)
    monkeypatch.setattr(_gate().runner, "git", slow)
    for cmd in ("git reset --hard", "git restore src/a.py", "git rm src/clean.py"):
        v = _check(root, cmd)
        assert v.kind == "refuse" and v.reason_id == "delete-uncommitted", cmd
        assert "could not be read" in v.message, cmd
    monkeypatch.undo()
    fail = subprocess_result(128)  # a git that exits with an error
    monkeypatch.setattr(_gate().runner, "git", lambda *_a, **_k: fail)
    v = _check(root, "git reset --hard")
    assert v.kind == "refuse" and v.reason_id == "delete-uncommitted" and "could not be read" in v.message
