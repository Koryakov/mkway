"""Card MW-073 (decision: R177), layer shell: the commands and the repository shapes the gate leaves alone or reads from
another folder, and the failure that must never block (a git read that fails). Synthetic files only; paths in constants."""
import pytest

import _engine  # noqa: F401
from _commit_project import make_project, stage
from _engine import gate_call
import gate_test_shape

NEW_FILE = "tests/test_new.py"
BAD = 'def test_new():\n    """Checks: one thing."""\n    for x in (1,):\n        assert x\n'
NOT_A_COMMIT = "echo commit"
TWO_COMMITS = "git commit -m a; git commit -m b"
IN_ROOT = "cd . && git commit -m x"
IN_TESTS = "cd tests && git commit -m x"
BOGUS_TREE = "0" * 40


def _check(root, command, **over):
    return gate_call(gate_test_shape.check, root, tool="Bash", tool_input={"command": command}, gate="tests.shape",
                     **over)


def test_a_project_with_no_git_is_not_judged(tmp_path):
    """Checks: a profile whose vcs is not git has no commit to judge."""
    root = make_project(tmp_path, vcs="none")
    assert _check(root, "git commit -m x").kind == "allow"


@pytest.mark.parametrize("command", [NOT_A_COMMIT, TWO_COMMITS], ids=["no-commit", "two-commits"])
def test_a_command_with_no_commit_or_with_two_is_not_judged(tmp_path, command):
    """Checks: only one plain commit is judged; a chained pair is the test gate's refusal."""
    root = make_project(tmp_path)
    stage(root, NEW_FILE, BAD)
    assert _check(root, command).kind == "allow"


@pytest.mark.parametrize("command", [IN_ROOT, IN_TESTS], ids=["root", "subfolder"])
def test_a_commit_is_judged_in_the_folder_it_names(tmp_path, command):
    """Checks: a `cd` to the root or below it is judged as the commit of this project."""
    root = make_project(tmp_path)
    stage(root, NEW_FILE, BAD)
    assert _check(root, command, cwd=str(root)).kind == "refuse"


def test_a_commit_in_a_folder_outside_the_root_is_another_projects_and_not_judged(tmp_path):
    """Checks: a `cd` to a folder above the root names another project's commit."""
    root = make_project(tmp_path)
    stage(root, NEW_FILE, BAD)
    assert _check(root, f"cd {tmp_path.as_posix()} && git commit -m x", cwd=str(root)).kind == "allow"


def test_a_git_read_that_fails_never_blocks_the_commit(tmp_path, monkeypatch):
    """Catches: a failing git read that refuses a commit the gate could not judge, when the commit gates own that case."""
    root = make_project(tmp_path)
    stage(root, NEW_FILE, BAD)
    monkeypatch.setattr(gate_test_shape.gate_commit_tests, "tree_id", lambda ctx, commit: BOGUS_TREE)
    assert _check(root, "git commit -m x").kind == "allow"


def test_a_task_below_the_git_top_is_judged_by_its_own_paths(tmp_path):
    """Catches: a task folder inside a bigger repository whose test paths are read from the repository top."""
    root = make_project(tmp_path, top=True)
    stage(root, NEW_FILE, BAD)
    verdict = _check(root, "git commit -m x")
    assert (verdict.kind, verdict.reason_id) == ("refuse", "test-shape")


def test_a_test_file_outside_the_task_folder_is_not_judged(tmp_path):
    """Checks: a bad test file beside the task folder, in the same repository, is not this task's test."""
    root = make_project(tmp_path, top=True)
    stage(root.parent, NEW_FILE, BAD)
    assert _check(root, "git commit -m x").kind == "allow"
