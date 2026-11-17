"""Card MW-070, the real shape on a real small repository: an Acceptance row names a test that reads a register file.
`card close` runs the named nodes on an export of HEAD's tree, so a file that is only staged, only untracked or only
modified in the working tree is not what the node reads. The fact reader is `cardtool.tests_problem`, the step of the
orderer's close that runs the nodes (a real git repository, a real pytest run, about a second per run). Synthetic names
only."""
import json
import sys

from _commit_project import git, make_project, write
from _engine import task_root
import cardtool

NODE = "tests/test_reg.py::test_the_register_is_done"
READS = ("from pathlib import Path\n\n\ndef test_the_register_is_done():\n"
         "    path = Path(__file__).resolve().parent.parent / 'data' / 'register.txt'\n"
         "    assert path.read_text(encoding='utf-8').strip() == 'done'\n")


def project(tmp_path, *, at_head=None, **over):
    """A repository whose HEAD holds the test above; `at_head` is the text of `data/register.txt` committed with it
    (None: the file is not in HEAD)."""
    root = make_project(tmp_path, **over)
    write(root, "tests/test_reg.py", READS)
    git(root, "add", "--", "tests/test_reg.py")
    if at_head is not None:
        write(root, "data/register.txt", at_head)
        git(root, "add", "--", "data/register.txt")
    git(root, "commit", "-q", "-m", "the test and its register")
    return root


def run_nodes(root):
    profile = json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))
    return cardtool.tests_problem(root, profile, [NODE])


def test_a_register_file_that_is_only_staged_refuses_the_close(tmp_path):
    """E1: the register file is in the index and not in HEAD, so the node does not find it and the close is refused.
    Catches: a close that runs the node on the working tree and passes over a register that another card only staged."""
    root = project(tmp_path)
    write(root, "data/register.txt", "done\n")
    git(root, "add", "--", "data/register.txt")
    assert run_nodes(root) is not None


def test_a_register_file_that_is_only_untracked_refuses_the_close(tmp_path):
    """E2: the register file is neither staged nor tracked, so the node does not find it and the close is refused.
    Catches: a close that lets an untracked file turn a red node green."""
    root = project(tmp_path)
    write(root, "data/register.txt", "done\n")
    assert run_nodes(root) is not None


def test_a_file_modified_but_not_staged_is_read_as_it_is_at_head_and_the_red_stays(tmp_path):
    """E3: HEAD holds `todo`, the working tree `done`, nothing staged: the node reads HEAD's `todo` and the close is
    refused. Catches: a close that reads the working-tree edit of a file HEAD still holds red."""
    root = project(tmp_path, at_head="todo\n")
    write(root, "data/register.txt", "done\n")
    assert run_nodes(root) is not None


def test_a_file_broken_in_the_working_tree_only_does_not_refuse_a_close_that_is_green_at_head(tmp_path):
    """E4: HEAD holds `done`, the working tree `broken`, nothing staged: the node reads HEAD's `done` and the close
    passes (the same tree rule as a commit). Catches: a close that reads the working tree in either direction."""
    root = project(tmp_path, at_head="done\n")
    write(root, "data/register.txt", "broken\n")
    assert run_nodes(root) is None


def test_a_register_file_committed_green_lets_the_close_pass(tmp_path):
    """E5: the nearest allow of E1 and E2: the register file is committed with `done`, and the close passes. Catches:
    a close that refuses a tree that HEAD holds green."""
    root = project(tmp_path, at_head="done\n")
    assert run_nodes(root) is None


def test_the_refusal_names_the_red_node_and_says_it_ran_on_heads_tree(tmp_path):
    """E6: the text of the refusal holds the full id of the red node and says the node ran on HEAD's tree, so the card's
    builder knows to commit the file. Catches: a refusal that names no node or hides which tree was read."""
    root = project(tmp_path)
    write(root, "data/register.txt", "done\n")
    git(root, "add", "--", "data/register.txt")
    text = run_nodes(root)
    assert text is not None and NODE in text and "HEAD's tree" in text


def test_the_export_of_heads_tree_is_removed_after_the_run(tmp_path):
    """E7: after a refused close no folder of the run is left under the state folder. Catches: an export of HEAD that
    stays on disk and is found, stale, by the next run."""
    root = project(tmp_path)
    assert run_nodes(root) is not None
    left = root / "mkway" / "state" / "commit_tests"
    assert not left.exists() or not list(left.iterdir())


def test_a_root_with_no_git_still_runs_the_nodes_where_they_are(tmp_path):
    """E8: with `vcs: none` there is no HEAD, so the node runs on the files as they are and an untracked register file
    is read. Catches: a close that refuses every card of a root that has no git."""
    root = task_root(tmp_path, vcs="none", python={"command": sys.executable})
    write(root, "tests/test_reg.py", READS)
    write(root, "data/register.txt", "done\n")
    assert run_nodes(root) is None


def test_a_repository_with_no_commit_refuses_the_close_saying_there_is_no_head(tmp_path):
    """E9: a git repository with no commit has no tree to export: the close is refused and the text says HEAD has no
    commit. Catches: a close that runs on the working tree because HEAD is missing."""
    root = make_project(tmp_path, commit=False)
    write(root, "tests/test_reg.py", READS)
    write(root, "data/register.txt", "done\n")
    text = run_nodes(root)
    assert text is not None and "HEAD" in text
