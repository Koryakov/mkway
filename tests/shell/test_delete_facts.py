"""Card MW-064: the shell of the delete gate on real files and real git. The shell reads the facts the pure core asks for
(where a path lies, whether it exists, what git reports, how big the targets are), runs the backup and writes the
record rows. One test id is one case (T2). Each test is under 20 s (the cap of MW-047, kept by the test concept of
2026-11-12); the git repository is built once for the module. The decisions themselves are the table tests of
`tests/core/test_delete_decide.py`; the real-hook deny of each reason stays in `tests/test_e2e_gates.py` (MW-039).
Synthetic task roots in the pytest temp folder only; no test file is imported."""
import contextlib
import json
import os
import re
import subprocess
import time

import pytest

from _engine import ENGINE, cli, gate_call, jsonl, task_root
import gate_delete

CAP_SECONDS = 20.0
STAMP = re.compile(r"^\d{8}T\d{6}-\d{6}(-\d+)?$")
LIST_FIX = "mkway delete --list <file>"
MIB = 1024 * 1024
GIT_ID = ["-c", "user.name=mkway-test", "-c", "user.email=mkway-test"]


@pytest.fixture(autouse=True)
def _a_shell_test_takes_under_20_seconds():
    started = time.perf_counter()
    yield
    took = time.perf_counter() - started
    assert took < CAP_SECONDS, f"a shell test must run under {CAP_SECONDS:g} s; this one took {took:.1f} s"


def _check(root, command, tool="Bash", session="s1", **payload):
    return gate_call(gate_delete.check, root, tool=tool, tool_input={"command": command}, session=session, **payload)


def _reason(verdict):
    return verdict.reason_id if verdict.kind == "refuse" else "allow"


def _write(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _task(tmp_path, **over):
    """A task root with `a.txt`, `b.txt`, `d/b.txt`, `d/c.txt`, and `elsewhere.txt` beside the root."""
    root = task_root(tmp_path, **over)
    for rel, text in (("a.txt", "alpha\n"), ("b.txt", "beta\n"), ("d/b.txt", "inner b\n"), ("d/c.txt", "inner c\n")):
        _write(root, rel, text)
    (tmp_path / "elsewhere.txt").write_text("x\n", encoding="utf-8")
    return root


@pytest.fixture
def root(tmp_path):
    return _task(tmp_path)


@pytest.fixture
def small(tmp_path):
    """A task root whose backups may not exceed 1 MiB."""
    return _task(tmp_path, delete={"max_backup_mb": 1})


def _state(root):
    return root / "mkway" / "state"


def _folders(root):
    trash = _state(root) / "trash"
    return sorted(os.listdir(trash)) if trash.is_dir() else []


def _rows(root):
    path = _state(root) / "deletes.jsonl"
    return jsonl(path) if path.is_file() else []


def _backup(root, row):
    return _state(root) / "trash" / row["backup"].rsplit("/", 1)[1]


# ---- the shell's own entry: what it reads and what it leaves alone ---------------------------------------------------------

@pytest.mark.parametrize("tool, tool_input", (
    pytest.param("Edit", {"file_path": "a.txt"}, id="a-tool-that-is-no-shell"),
    pytest.param("Bash", {}, id="no-command"), pytest.param("Bash", {"command": 5}, id="a-command-that-is-no-text"),
    pytest.param("Bash", None, id="no-tool-input"), pytest.param("Bash", {"command": "  "}, id="an-empty-command")))
def test_a_call_the_gate_does_not_own_is_allowed(root, tool, tool_input):
    """The gate reads shell commands only; any other call, a missing, non-text or empty command is allowed, never a
    crash. Catches: a gate that raises on a payload it does not own."""
    assert gate_call(gate_delete.check, root, tool=tool, tool_input=tool_input).kind == "allow"


@pytest.mark.parametrize("command", ("rm ../elsewhere.txt", "cd .. && rm elsewhere.txt"))
def test_a_relative_path_out_of_the_real_root_is_outside(root, command):
    """The shell places a target on the real root: a path that climbs out of it is `delete-outside-root`. Catches: a
    shell that gives the core a wrong place, so a file beside the task is deleted."""
    assert _reason(_check(root, command)) == "delete-outside-root"


def test_an_absolute_path_outside_the_real_root_is_outside(root, tmp_path):
    """Catches: an absolute path to a file beside the task that is read as inside."""
    assert _reason(_check(root, f"rm {(tmp_path / 'elsewhere.txt').as_posix()}")) == "delete-outside-root"


def test_an_absolute_path_inside_the_real_root_is_a_repo_path(root):
    """The nearest allow: the same kind of path inside the root is backed up by its repo path. Catches: an absolute path
    inside the root that is refused or recorded in absolute form."""
    assert _reason(_check(root, f"rm {root.as_posix()}/a.txt")) == "allow"
    assert _rows(root)[-1]["targets"] == ["a.txt"]


def test_a_relative_target_is_read_from_the_hooks_cwd(root):
    """In the folder `d` the file `b.txt` is `d/b.txt`. Catches: a delete backed up from the wrong folder."""
    assert _reason(_check(root, "rm b.txt", cwd=str(root / "d"))) == "allow"
    assert _rows(root)[-1]["targets"] == ["d/b.txt"]


def test_a_relative_target_with_a_cwd_outside_the_root_cannot_be_placed(root, tmp_path):
    """Catches: a relative delete placed in the root although the session stands elsewhere."""
    assert _reason(_check(root, "rm b.txt", cwd=str(tmp_path))) == "delete-target-unknown"


def test_a_cd_into_a_folder_that_exists_places_the_target_in_it(root):
    """The nearest allow of the next test. Catches: a `cd` that is not followed."""
    assert _reason(_check(root, "cd d; rm b.txt")) == "allow"
    assert _rows(root)[-1]["targets"] == ["d/b.txt"]


def test_a_cd_into_a_folder_that_does_not_exist_makes_the_folder_unknown(root):
    """The real shell would fail that `cd` and run the delete from the folder it stood in; the gate refuses and says the
    folder cannot be read. Catches: a backup of `a.txt` for a delete that removes another file."""
    v = _check(root, "cd nothere; rm ../a.txt")
    assert (v.kind, v.reason_id) == ("refuse", "delete-target-unknown") and "cannot be read" in v.message


# ---- git: the facts come from real git ----------------------------------------------------------------------------------------

def _git(root, *args):
    return subprocess.run(["git", *GIT_ID, *args], cwd=str(root), capture_output=True, text=True, check=True).stdout


@pytest.fixture(scope="module")
def repo(tmp_path_factory):
    """One git task root for the module: `src/a.py`, `src/clean.py`, `lib/x.py` committed, the tree clean."""
    root = task_root(tmp_path_factory.mktemp("deletegit"), vcs="git")
    (root / "mkway" / ".gitignore").write_text("engine/\nlocks/\nstate/\n", encoding="utf-8")
    for rel in ("src/a.py", "src/clean.py", "lib/x.py"):
        _write(root, rel, "v1\n")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    return root


@contextlib.contextmanager
def _clean(root):
    yield


@contextlib.contextmanager
def _untracked(root):
    _write(root, "new.txt", "untracked\n")
    try:
        yield
    finally:
        os.remove(root / "new.txt")


@contextlib.contextmanager
def _unstaged(root):
    _write(root, "src/a.py", "v2\n")
    try:
        yield
    finally:
        _git(root, "checkout", "HEAD", "--", "src/a.py")


@contextlib.contextmanager
def _staged(root):
    _write(root, "src/a.py", "v2\n")
    _git(root, "add", "-f", "--", "src/a.py")
    try:
        yield
    finally:
        _git(root, "checkout", "HEAD", "--", "src/a.py")


@contextlib.contextmanager
def _removed(root):
    os.remove(root / "src" / "clean.py")
    try:
        yield
    finally:
        _git(root, "checkout", "HEAD", "--", "src/clean.py")


@pytest.mark.parametrize("state", (pytest.param(_clean, id="clean-tree"), pytest.param(_untracked, id="untracked-only")))
def test_a_hard_reset_passes_when_git_reports_no_tracked_change(repo, state):
    """The nearest allow: a clean tree, and a tree with only an untracked file, which a hard reset does not touch.
    Catches: a gate that blocks every hard reset."""
    with state(repo):
        assert _reason(_check(repo, "git reset --hard")) == "allow"


@pytest.mark.parametrize("state", (pytest.param(_unstaged, id="unstaged"), pytest.param(_staged, id="staged")))
def test_a_hard_reset_is_refused_when_git_reports_a_tracked_change(repo, state):
    """Catches: a shell that gives the core a wrong status line, so a hard reset throws away a staged or an unstaged
    change."""
    with state(repo):
        v = _check(repo, "git reset --hard")
    assert (v.kind, v.reason_id) == ("refuse", "delete-uncommitted") and "src/a.py" in v.message


def test_a_soft_reset_passes_although_git_reports_a_change(repo):
    """Catches: a gate that blocks a reset that loses nothing."""
    with _unstaged(repo):
        assert _reason(_check(repo, "git reset --soft HEAD~1")) == "allow"


def test_a_hard_reset_is_not_read_when_the_profile_has_no_git(tmp_path):
    """With `vcs: none` git is not read, so a hard reset passes. Catches: a gate that reads git without the profile
    asking for it."""
    assert _reason(_check(task_root(tmp_path, vcs="none"), "git reset --hard")) == "allow"


@pytest.mark.parametrize("command", ("git restore src/a.py", "git checkout -- src/a.py", "git restore src",
                                     "git restore ."))
def test_a_restore_of_a_changed_path_or_of_a_folder_holding_it_is_refused(repo, command):
    """Catches: a shell that reads the wrong path from git, so a revert throws away a change."""
    with _unstaged(repo):
        v = _check(repo, command)
    assert (v.kind, v.reason_id) == ("refuse", "delete-uncommitted") and "src/a.py" in v.message


def test_a_restore_of_a_clean_path_passes_although_another_path_has_a_change(repo):
    """The nearest allow. Catches: a restore refused for a change in a path it does not name."""
    with _unstaged(repo):
        assert _reason(_check(repo, "git restore src/clean.py")) == "allow"


@pytest.mark.parametrize("command", ("git restore src/clean.py", "git checkout -- src/clean.py"))
def test_restoring_a_path_deleted_from_the_working_tree_passes(repo, command):
    """A deletion is no work to lose. Catches: a refusal to bring a deleted file back."""
    with _removed(repo):
        assert _reason(_check(repo, command)) == "allow"


@pytest.mark.parametrize("state", (pytest.param(_unstaged, id="unstaged"), pytest.param(_staged, id="staged")))
@pytest.mark.parametrize("command", ("git rm src/a.py", "git rm -f src/a.py", "git rm -r src"))
def test_git_rm_of_a_changed_file_is_refused(repo, command, state):
    """Catches: a `git rm` that loses a staged or an unstaged change, directly or through its folder."""
    with state(repo):
        assert _reason(_check(repo, command)) == "delete-uncommitted"


def test_a_refused_git_rm_leaves_no_row_and_no_trash_folder(repo):
    """Catches: a refusal that still writes a record or a copy."""
    before = (len(_rows(repo)), _folders(repo))
    with _unstaged(repo):
        _check(repo, "git rm src/a.py")
    assert (len(_rows(repo)), _folders(repo)) == before


def test_git_rm_of_a_clean_tracked_file_is_recorded_without_a_copy(repo):
    """Git keeps the file, so there is one row with `backup` none and no trash folder. Catches: a `git rm` that is
    backed up needlessly, or that has no record."""
    rows, folders = len(_rows(repo)), _folders(repo)
    assert _reason(_check(repo, "git rm lib/x.py")) == "allow"
    (row,) = _rows(repo)[rows:]
    assert (row["targets"], row["backup"], row["via"], row["session"]) == (["lib/x.py"], None, "gate", "s1")
    assert _folders(repo) == folders and (repo / "lib" / "x.py").is_file()


def test_git_rm_of_a_clean_tracked_folder_is_recorded_without_a_copy(repo):
    """Catches: a folder of tracked files that is copied or not recorded."""
    rows = len(_rows(repo))
    assert _reason(_check(repo, "git rm -r lib")) == "allow"
    (row,) = _rows(repo)[rows:]
    assert (row["targets"], row["backup"]) == (["lib"], None)


@pytest.mark.parametrize("command", ("git rm --cached src/a.py", "git rm -n lib/x.py", "git rm --dry-run lib/x.py"))
def test_a_git_rm_that_deletes_nothing_leaves_no_row(repo, command):
    """Catches: a record row for a `--cached` or dry-run `git rm`."""
    rows = len(_rows(repo))
    assert _reason(_check(repo, command)) == "allow"
    assert len(_rows(repo)) == rows


def test_git_rm_of_an_untracked_file_leaves_no_row(repo):
    """Git does not keep an untracked file, and `git rm` of it is no delete the gate records. Catches: a row for a path
    git does not know."""
    rows = len(_rows(repo))
    with _untracked(repo):
        assert _reason(_check(repo, "git rm new.txt")) == "allow"
    assert len(_rows(repo)) == rows


def test_one_command_that_deletes_a_file_and_git_rms_a_tracked_one_makes_one_row_and_one_copy(repo):
    """The row lists both targets in command order; only the file is copied. Catches: a row that loses one of the two
    deletes, or a copy of the file git keeps."""
    _write(repo, "tmp.txt", "t\n")
    rows, folders = len(_rows(repo)), _folders(repo)
    try:
        assert _reason(_check(repo, "rm tmp.txt && git rm lib/x.py")) == "allow"
        (row,) = _rows(repo)[rows:]
        (name,) = [n for n in _folders(repo) if n not in folders]
    finally:
        os.remove(repo / "tmp.txt")
    assert row["targets"] == ["tmp.txt", "lib/x.py"]
    assert (_state(repo) / "trash" / name / "tmp.txt").is_file()
    assert not (_state(repo) / "trash" / name / "lib").exists()


def test_a_git_that_cannot_read_the_tree_refuses_the_delete(tmp_path):
    """A profile with `vcs: git` on a folder that is no repository makes git exit non-zero; the hard reset is refused and
    the text says git exited. Catches: a gate that lets a hard reset through because git did not answer."""
    v = _check(task_root(tmp_path, vcs="git"), "git reset --hard")
    assert (v.kind, v.reason_id) == ("refuse", "delete-uncommitted")
    assert "git exited 128" in v.message and "could not be read" in v.message


def test_a_git_that_does_not_answer_is_worded_as_such(tmp_path, monkeypatch):
    """A git that times out (fault injected: a real timeout cannot be made to order) is worded `did not answer
    (TimeoutExpired)`. Catches: the exception type lost from the refusal."""
    import runner
    root = task_root(tmp_path, vcs="git")

    def slow(*_a, **_k):
        raise runner.TimeoutExpired(["git"], 10)
    monkeypatch.setattr(gate_delete.runner, "git", slow)
    v = _check(root, "git reset --hard")
    assert v.reason_id == "delete-uncommitted" and "git did not answer (TimeoutExpired)" in v.message


# ---- the backup and its record ----------------------------------------------------------------------------------------------

def test_a_deleted_file_is_copied_into_the_trash_at_its_repo_path(root):
    """Catches: a delete that cannot be undone. The gate itself deletes nothing: the tool does."""
    assert _check(root, "rm a.txt").kind == "allow"
    (row,) = _rows(root)
    assert (_backup(root, row) / "a.txt").read_text(encoding="utf-8") == "alpha\n"
    assert (root / "a.txt").is_file()


def test_a_deleted_folder_is_copied_with_its_content(root):
    """Catches: a folder delete whose content is lost."""
    assert _check(root, "rm -rf d").kind == "allow"
    (row,) = _rows(root)
    assert (_backup(root, row) / "d" / "b.txt").read_text(encoding="utf-8") == "inner b\n"
    assert (_backup(root, row) / "d" / "c.txt").read_text(encoding="utf-8") == "inner c\n"


def test_the_record_row_holds_session_targets_via_time_and_backup(root):
    """The row has the session, the targets in command order, `via: gate`, the time and the backup folder as a repo path.
    Catches: a delete with no trace of who made it."""
    _check(root, "rm -rf d a.txt")
    (name,) = _folders(root)
    (row,) = _rows(root)
    assert (row["session"], row["targets"], row["via"]) == ("s1", ["d", "a.txt"], "gate")
    assert row["backup"] == f"mkway/state/trash/{name}" and row["time"]


def test_the_trash_folder_is_named_by_a_timestamp(root):
    """Catches: a trash folder the owner's `trash empty` cannot age."""
    _check(root, "rm a.txt")
    (name,) = _folders(root)
    assert STAMP.match(name), name


def test_two_deletes_in_a_row_make_two_folders_and_two_rows(root):
    """Even within one second. Catches: a second delete that overwrites the first backup."""
    _check(root, "rm a.txt", session="s1")
    _check(root, "rm b.txt", session="s2")
    assert len(set(_folders(root))) == 2
    assert [(r["session"], r["targets"]) for r in _rows(root)] == [("s1", ["a.txt"]), ("s2", ["b.txt"])]


def test_a_powershell_delete_is_backed_up_the_same_way(root):
    """Catches: a PowerShell delete that has no backup."""
    assert _check(root, "Remove-Item -Recurse -Force d", tool="PowerShell").kind == "allow"
    (row,) = _rows(root)
    assert (_backup(root, row) / "d" / "c.txt").read_text(encoding="utf-8") == "inner c\n"


def test_a_delete_after_a_cd_is_backed_up_at_its_repo_path(root):
    """Catches: a copy flattened to the folder the command stood in."""
    _check(root, "cd d && rm b.txt")
    (row,) = _rows(root)
    assert (_backup(root, row) / "d" / "b.txt").read_text(encoding="utf-8") == "inner b\n"


def test_an_empty_folder_is_backed_up_as_a_folder(root):
    """Catches: a copy that loses an empty folder."""
    (root / "empty" / "deeper").mkdir(parents=True)
    _check(root, "rmdir empty/deeper")
    (row,) = _rows(root)
    assert (_backup(root, row) / "empty" / "deeper").is_dir()


def test_a_file_in_a_nested_folder_keeps_its_full_repo_path(root):
    """Catches: a copy that flattens paths."""
    _write(root, "d/sub/x.txt", "deep\n")
    _check(root, "rm d/sub/x.txt")
    (row,) = _rows(root)
    assert (_backup(root, row) / "d" / "sub" / "x.txt").read_text(encoding="utf-8") == "deep\n"


def test_a_target_named_twice_is_recorded_once(root):
    """Catches: a row that lists a path twice."""
    _check(root, "rm a.txt a.txt")
    assert _rows(root)[0]["targets"] == ["a.txt"]


def test_a_target_exactly_at_the_size_limit_is_backed_up(small):
    """The nearest allow of `delete-too-large`. Catches: a limit that refuses at the limit."""
    (small / "edge.bin").write_bytes(b"x" * MIB)
    assert _check(small, "rm edge.bin").kind == "allow"
    assert len(_folders(small)) == 1 and len(_rows(small)) == 1


def test_a_target_above_the_size_limit_is_refused_and_nothing_is_written(small):
    """Catches: a delete of a big file that fills the disk, or a refusal that still leaves a copy or a row."""
    (small / "big.bin").write_bytes(b"x" * (MIB + 1))
    v = _check(small, "rm big.bin")
    assert (v.kind, v.reason_id) == ("refuse", "delete-too-large")
    assert (_folders(small), _rows(small)) == ([], [])


def test_a_folder_counts_by_its_content_for_the_size_limit(small):
    """Two files under the limit each, over it together. Catches: a limit read on the folder entry or on a count of
    files."""
    (small / "d" / "half1.bin").write_bytes(b"x" * (MIB // 2))
    (small / "d" / "half2.bin").write_bytes(b"x" * (MIB // 2 + 10))
    assert _reason(_check(small, "rm -rf d")) == "delete-too-large"


def test_the_size_refusal_names_the_owners_terminal_and_the_key(small):
    """Catches: a refusal that leaves the session with no way out."""
    (small / "big.bin").write_bytes(b"x" * (MIB + 1))
    message = _check(small, "rm a.txt big.bin").message
    assert "needs the owner's terminal" in message and "delete.max_backup_mb" in message


def test_a_copy_that_fails_refuses_the_delete(root, monkeypatch):
    """The disk-full copy is injected (a real one cannot be made to order); the delete is refused naming the cause and
    no row is written. Catches: a delete that runs although its backup is missing."""
    import trash

    def boom(*_a, **_k):
        raise OSError("disk full")
    monkeypatch.setattr(trash.shutil, "copy2", boom)
    v = _check(root, "rm a.txt")
    assert (v.kind, v.reason_id) == ("refuse", "delete-backup-failed") and "disk full" in v.message
    assert _rows(root) == []


def test_a_trash_folder_that_cannot_be_made_refuses_the_delete(root):
    """A file stands where the trash folder belongs. Catches: a delete that runs although it has no place for its
    backup."""
    (_state(root) / "trash").write_text("a file where the trash folder must be\n", encoding="utf-8")
    assert _reason(_check(root, "rm a.txt")) == "delete-backup-failed"


def test_a_record_row_that_cannot_be_written_refuses_the_delete(root):
    """A folder stands where the record file belongs. Catches: a delete that runs although nothing records it."""
    (_state(root) / "deletes.jsonl").mkdir()
    v = _check(root, "rm a.txt")
    assert (v.kind, v.reason_id) == ("refuse", "delete-backup-failed") and "record" in v.message


@pytest.mark.parametrize("command", ("ls", "echo rm a.txt", "rm a.txt nothere.txt", "rm a.txt ../elsewhere.txt",
                                     "rm *.txt", "rm $X", "psql -c \"drop table t\"",
                                     "python mkway/engine/mkway.py trash list", "git status"))
def test_a_refused_or_plain_command_leaves_no_trash(root, command):
    """Nothing is copied and no row is written. Catches: a trash folder that fills with copies of deletes that never
    ran."""
    _check(root, command)
    assert not (_state(root) / "trash").exists() and not (_state(root) / "deletes.jsonl").exists()


def test_a_crash_in_the_gate_blocks_the_delete(root, monkeypatch):
    """Through the dispatcher with the engine's own manifest, a crash in the delete gate (here: the backup raises) is
    `gate-error` and blocks the shell call: the entry's `onFailure: block`. Catches: a crash that lets a delete through
    unbacked."""
    import dispatch
    import trash

    def crash(*_a, **_k):
        raise RuntimeError("planted")
    monkeypatch.setattr(trash, "backup", crash)
    payload = {"session_id": "s1", "hook_event_name": "PreToolUse", "cwd": str(root), "tool_name": "Bash",
               "tool_input": {"command": "rm a.txt"}}
    res = dispatch.run("PreToolUse", "shell", json.dumps(payload),
                       env={"CLAUDE_PROJECT_DIR": str(root), "CLAUDECODE": "1"}, engine_dir=ENGINE)
    out = json.loads(res.stdout)["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny" and "gate-error" in out["permissionDecisionReason"]
    assert "delete" in out["permissionDecisionReason"] and "RuntimeError" in out["permissionDecisionReason"]
    assert (root / "a.txt").is_file() and _rows(root) == []


# ---- `mkway delete --list` -------------------------------------------------------------------------------------------------

def _list(tmp_path, text, name="list.txt"):
    path = tmp_path / name  # outside the root: the scratchpad case the owner's guard blocked
    path.write_bytes(text.encode("utf-8"))
    return path


@pytest.fixture
def listed(root, tmp_path):
    """The list command run by a session on a list with CRLF, a blank line, spaces, `./`, an absolute path and a path
    twice: (root, exit code, output, errors)."""
    text = f"a.txt\r\n\r\n  d  \r\nd/b.txt\n./b.txt\n{root.as_posix()}/a.txt\n"
    code, out, err = cli(root, "delete", "--list", str(_list(tmp_path, text)), session=True)
    return root, code, out, err


def test_the_list_command_deletes_the_listed_paths(listed):
    """Catches: the way out of a wildcard that is itself blocked."""
    root, code, _out, err = listed
    assert code == 0, err
    assert [(root / rel).exists() for rel in ("a.txt", "d", "b.txt")] == [False, False, False]


def test_the_list_command_copies_the_paths_into_the_trash_first(listed):
    """Catches: a bulk delete with no backup."""
    root, _code, _out, _err = listed
    (row,) = _rows(root)
    assert (_backup(root, row) / "a.txt").read_text(encoding="utf-8") == "alpha\n"
    assert (_backup(root, row) / "d" / "c.txt").read_text(encoding="utf-8") == "inner c\n"


def test_the_list_command_writes_one_row_that_says_it_was_a_list_by_a_session(listed):
    """The CLI knows no session id, so `session` is null and `by` says who. Catches: a bulk delete with no author."""
    root, _code, _out, _err = listed
    (row,) = _rows(root)
    assert (row["via"], row["targets"], row["session"], row["by"]) == (
        "list", ["a.txt", "d", "d/b.txt", "b.txt"], None, "session")


def test_the_list_command_says_how_many_paths_and_where_the_backup_is(listed):
    """Catches: a command that deletes and says nothing."""
    root, _code, out, _err = listed
    assert "deleted 4" in out and _folders(root)[0] in out


def test_the_list_command_works_in_the_owners_terminal(root, tmp_path):
    """The same command with no `CLAUDECODE`: `by` says the owner. Catches: a list command that only a session can run."""
    code, _out, err = cli(root, "delete", "--list", str(_list(tmp_path, "a.txt\n")))
    assert code == 0, err
    assert not (root / "a.txt").exists() and _rows(root)[0]["by"] == "owner"


@pytest.fixture
def locked(tmp_path):
    """A task root with a closed lock on `frozen/f.txt`."""
    root = _task(tmp_path, locks={"targets": [{"name": "frozen", "paths": ["frozen/f.txt"]}]})
    _write(root, "frozen/f.txt", "f\n")
    return root


@pytest.mark.parametrize("line, why", (
    ("nothere.txt", "does not exist"), ("../elsewhere.txt", "outside"), ("d/*.txt", "wildcard"),
    ("frozen/f.txt", "frozen"), ("frozen", "frozen/f.txt"), ("mkway/state", "state"), (".", "root")))
def test_one_bad_line_deletes_nothing_and_is_named(locked, tmp_path, line, why):
    """With a good line and a bad one nothing is deleted, copied or recorded, and the bad line is named with its number
    and its reason, on the real files and the real locks. Catches: a list that deletes the good half, or one that
    deletes what the gate would refuse."""
    code, _out, err = cli(locked, "delete", "--list", str(_list(tmp_path, f"a.txt\n{line}\n")), session=True)
    assert code == 1 and "line 2" in err and line in err and why in err and "line 1" not in err
    assert (locked / "a.txt").is_file() and _folders(locked) == [] and _rows(locked) == []


def test_an_empty_list_is_an_error(root, tmp_path):
    """Catches: a list command that reports success having done nothing."""
    code, _out, err = cli(root, "delete", "--list", str(_list(tmp_path, "\n  \n")), session=True)
    assert code == 1 and "no path" in err


def test_a_missing_list_file_is_an_error_and_deletes_nothing(root, tmp_path):
    """Catches: a crash, or a delete, on a list file that is not there."""
    code, _out, err = cli(root, "delete", "--list", str(tmp_path / "missing.txt"), session=True)
    assert code == 1 and "list file" in err and (root / "a.txt").is_file()


def test_the_list_command_respects_the_size_limit(small, tmp_path):
    """Above `delete.max_backup_mb` nothing is deleted and the text says it needs the owner's terminal. Catches: a bulk
    delete that fills the disk."""
    (small / "big.bin").write_bytes(b"x" * (MIB + 1))
    code, _out, err = cli(small, "delete", "--list", str(_list(tmp_path, "big.bin\na.txt\n")), session=True)
    assert code == 1 and "needs the owner's terminal" in err
    assert (small / "big.bin").is_file() and (small / "a.txt").is_file() and _rows(small) == []


# ---- `mkway trash list` and `mkway trash empty` --------------------------------------------------------------------------------

OLD = "20200101T000000-000000"


@pytest.fixture
def trashed(root, tmp_path):
    """A task root whose trash holds an old stamped folder, a folder with no stamp, and one fresh backup made by the list
    command: (root, the fresh folder's name)."""
    trash = _state(root) / "trash"
    _write(trash, f"{OLD}/x/f.txt", "old\n")
    (trash / "notes").mkdir()
    assert cli(root, "delete", "--list", str(_list(tmp_path, "a.txt\n")), session=True)[0] == 0
    (fresh,) = [n for n in _folders(root) if n not in (OLD, "notes")]
    return root, fresh


@pytest.mark.parametrize("args", (("trash", "list"), ("trash", "empty", "--older-than", "0")))
def test_a_session_may_not_run_the_trash_commands(trashed, args):
    """The `CLAUDECODE` tripwire refuses them, as it does for `lock`; the old folder stays. Catches: a session that
    destroys its own backups."""
    root, _fresh = trashed
    code, _out, err = cli(root, *args, session=True)
    assert code == 1 and "owner-only-command" in err and (_state(root) / "trash" / OLD).is_dir()


def test_a_later_delete_never_empties_the_trash(trashed):
    """The engine never empties the trash by itself. Catches: a backup removed by the next delete."""
    root, _fresh = trashed
    assert (_state(root) / "trash" / OLD).is_dir()


def test_the_owner_lists_the_folders_with_files_size_and_targets(trashed):
    """Catches: a listing that does not say what each folder holds."""
    root, fresh = trashed
    code, out, err = cli(root, "trash", "list")
    assert code == 0, err
    assert OLD in out and fresh in out and "1 files" in out and "a.txt" in out


def test_the_owner_empties_only_the_folders_older_than_the_days(trashed):
    """By the stamp in the name: the old folder goes, the fresh one and the one with no stamp stay. Catches: a backup
    that is emptied before its time, or a folder of the owner's removed."""
    root, fresh = trashed
    code, out, _err = cli(root, "trash", "empty", "--older-than", "30")
    assert code == 0 and "removed 1" in out
    assert not (_state(root) / "trash" / OLD).exists()
    assert (_state(root) / "trash" / fresh).is_dir() and (_state(root) / "trash" / "notes").is_dir()


def test_older_than_zero_empties_every_stamped_folder_and_leaves_the_rest(trashed):
    """Catches: `--older-than 0` that touches a folder with no stamp."""
    root, _fresh = trashed
    code, out, _err = cli(root, "trash", "empty", "--older-than", "0")
    assert code == 0 and "removed 2" in out and _folders(root) == ["notes"]


def test_each_empty_is_one_record_row_by_the_owner(trashed):
    """Catches: an emptied trash with no trace."""
    root, _fresh = trashed
    cli(root, "trash", "empty", "--older-than", "30")
    (row,) = [r for r in _rows(root) if r["via"] == "trash-empty"]
    assert (row["by"], row["targets"]) == ("owner", [OLD])


@pytest.mark.parametrize("args", ((), ("--older-than", "soon")), ids=("missing-days", "days-that-are-no-number"))
def test_the_days_are_required_and_must_be_a_number(trashed, args):
    """Missing and non-numeric days exit 2 and nothing is removed. Catches: an empty that runs on a missing or absurd
    age."""
    root, _fresh = trashed
    assert cli(root, "trash", "empty", *args)[0] == 2 and (_state(root) / "trash" / OLD).is_dir()


def test_negative_days_are_refused(trashed):
    """Catches: an empty of everything through `--older-than -1`."""
    root, _fresh = trashed
    assert cli(root, "trash", "empty", "--older-than", "-1")[0] != 0 and (_state(root) / "trash" / OLD).is_dir()
