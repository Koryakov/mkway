"""Card MW-130 (decision R316 7), layer shell, on real git repositories and the real commit gate: one test per commit form that
`gate_commit_tests._gate` parses (`core.CommitFacts`: a plain commit, `-a`, `-- <paths>`, `-i -- <paths>`, `--amend`, and the
message-only amend that takes nothing). For each form the gate is run once (`run_gate` with the command), the commit is then
made with the same form, and the `git_tree` of the red-proof row is compared with `git rev-parse HEAD^{tree}` of the commit
just made. Synthetic files only."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/: the shared helpers and `_engine`
from _commit_project import OK_TEST, git, reason, run_gate, stage, write  # noqa: E402
from _engine import gate_call  # noqa: E402
import gate_commit_tests as gct  # noqa: E402
from _red_project import RED_MUL, record_rows, red_project  # noqa: E402

NEW_FILE = "tests/test_new.py"
OK_FILE = "tests/test_ok.py"


EDITED = OK_TEST + "\n\ndef test_new():\n    assert False\n"  # a tracked test file with one new failing test
MESSAGE = "CARD-001 red"


def _tree(root) -> str:
    return git(root, "rev-parse", "HEAD^{tree}").strip()


def _red_commit(root):
    """The card's red commit through the gate and a plain commit: the commit an amend then changes."""
    stage(root, NEW_FILE, RED_MUL)
    assert reason(run_gate(root)) == "allow"
    git(root, "commit", "-q", "-m", MESSAGE)


def test_an_all_commit_row_git_tree_is_the_tree_of_the_commit_just_made(tmp_path):
    """Checks: form `-a` (the unstaged edit of a tracked test file, taken from the working tree through a temporary index):
    the row's git_tree equals the tree of the commit made."""
    root = red_project(tmp_path)
    write(root, OK_FILE, EDITED)
    assert reason(run_gate(root, "git commit -a -m x")) == "allow"
    git(root, "commit", "-q", "-a", "-m", MESSAGE)
    assert record_rows(root)[-1]["git_tree"] == _tree(root)


def test_a_commit_with_paths_row_git_tree_is_the_tree_of_the_commit_just_made(tmp_path):
    """Checks: form `-- <paths>` (HEAD plus the working-tree content of the named path): the row's git_tree equals the tree
    of the commit made."""
    root = red_project(tmp_path)
    write(root, OK_FILE, EDITED)
    stage(root, "README.md", "# fixture project, edited\n")  # staged, and no part of a `--` commit: HEAD plus the path is not the index plus the path
    assert reason(run_gate(root, f"git commit -m x -- {OK_FILE}")) == "allow"
    git(root, "commit", "-q", "-m", MESSAGE, "--", OK_FILE)
    assert record_rows(root)[-1]["git_tree"] == _tree(root)
    assert "README.md" not in git(root, "show", "--name-only", "--format=", "HEAD").split()


def test_a_commit_include_row_git_tree_is_the_tree_of_the_commit_just_made(tmp_path):
    """Checks: form `-i -- <paths>` (the index plus the named path): the row's git_tree equals the tree of the commit made."""
    root = red_project(tmp_path)
    write(root, OK_FILE, EDITED)
    stage(root, "README.md", "# fixture project, edited\n")  # staged, and part of a `-i` commit: the index plus the path
    assert reason(run_gate(root, f"git commit -i -m x -- {OK_FILE}")) == "allow"
    git(root, "commit", "-q", "-i", "-m", MESSAGE, "--", OK_FILE)
    assert record_rows(root)[-1]["git_tree"] == _tree(root)
    assert "README.md" in git(root, "show", "--name-only", "--format=", "HEAD").split()


def test_an_amend_row_git_tree_is_the_tree_of_the_amended_commit(tmp_path):
    """Checks: form `--amend` that takes a new staged test file: the row's git_tree equals the tree of the amended commit,
    not the tree of the commit it replaced."""
    root = red_project(tmp_path)
    stage(root, "README.md", "# fixture project, edited\n")
    git(root, "commit", "-q", "-m", "docs only")  # the commit the amend replaces
    before = _tree(root)
    stage(root, NEW_FILE, RED_MUL)
    assert reason(run_gate(root, "git commit --amend -m x")) == "allow"
    git(root, "commit", "-q", "--amend", "-m", MESSAGE)
    assert (record_rows(root)[-1]["git_tree"], before != _tree(root)) == (_tree(root), True)


def test_a_message_only_amend_judges_nothing_and_writes_no_row(tmp_path):
    """GUARD (green today): the form that takes no file is allowed before any judgement, so it writes no red-proof row, with
    or without a git_tree: the number of rows is the same before and after."""
    root = red_project(tmp_path)
    _red_commit(root)
    rows = len(record_rows(root))
    assert reason(run_gate(root, "git commit --amend -o -m y")) == "allow"
    assert len(record_rows(root)) == rows


def test_a_commit_made_from_another_folder_row_git_tree_is_the_tree_of_the_commit_just_made(tmp_path):
    """Checks: the form `cd <folder> && git commit` where the folder is a LINKED WORKTREE below the root (`ctx.norm(commit.cwd)`:
    the gate reads the folder the command names): its HEAD and index differ from the root's, and the row's git_tree equals the
    tree of the commit made in the worktree, not the root's tree."""
    root = red_project(tmp_path)
    stage(root, "README.md", "# fixture project, edited\n")
    git(root, "commit", "-q", "-m", "docs only")  # the root's HEAD moves on; the worktree starts from the commit before
    linked = root / "wt"
    git(root, "worktree", "add", "-q", "-b", "linked", str(linked), "HEAD~1")
    stage(linked, NEW_FILE, RED_MUL)
    verdict = gate_call(gct.check, root, tool="Bash", tool_input={"command": "cd wt && git commit -m x"}, session="s1",
                        gate="commit_tests", cwd=str(root))
    assert reason(verdict) == "allow"
    git(linked, "commit", "-q", "-m", MESSAGE)
    made = git(linked, "rev-parse", "HEAD^{tree}").strip()
    assert (record_rows(root)[-1]["git_tree"], made != _tree(root)) == (made, True)
