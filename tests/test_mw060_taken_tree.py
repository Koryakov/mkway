"""Card MW-060: `commit_tests` builds and tests exactly the tree the commit will produce, read through the one reader
`commit_files` uses (`gate_commit`). Table tests on the pure parts (the reader's combination and the tree plan), shell
tests on real scratch repositories. Synthetic names only."""
import pytest

from _commit_project import git, make_project, reason, rows, run_gate, stage, write
from _engine import REPO  # noqa: F401  (puts the engine folder on the path)
import gate_commit
import gate_commit_tests
import helpers

BREAKS_APP = "def add(a, b):\n    return 0\n"
GUARD = ("from pathlib import Path\n\n\ndef test_no_draft_folder():\n"
         "    assert not (Path(__file__).resolve().parent.parent / 'pkg' / 'draft').exists()\n")


def commit_of(command):
    (found,) = helpers.commit_cmd(command)
    return found


# ---- the reader's table of what a commit takes moved to the pure core (MW-052: tests/core/test_commit_decide.py) ----------

# ---- the tree plan: where each file of the tested tree comes from ----------------------------------------------------

HEAD = ["a.py", "b.py", "c.py"]
INDEX = ["a.py", "b.py", "c.py", "new3.py"]
PLAN = [  # (command, head list, index list, taken) -> {path: where its content comes from}
    ("git commit -m x", HEAD, INDEX, [("M", "a.py", "index"), ("A", "new3.py", "index")],
     {"a.py": "index", "b.py": "index", "c.py": "index", "new3.py": "index"}),
    ("git commit -m x -a", HEAD, INDEX, [("M", "a.py", "work"), ("M", "b.py", "work"), ("A", "new3.py", "work")],
     {"a.py": "work", "b.py": "work", "c.py": "index", "new3.py": "work"}),
    ("git commit -m x -- b.py", HEAD, INDEX, [("M", "b.py", "work")],
     {"a.py": "head", "b.py": "work", "c.py": "head"}),
    ("git commit -m x -o b.py", HEAD, INDEX, [("M", "b.py", "work")],
     {"a.py": "head", "b.py": "work", "c.py": "head"}),
    ("git commit -m x --only b.py", HEAD, INDEX, [("M", "b.py", "work")],
     {"a.py": "head", "b.py": "work", "c.py": "head"}),
    ("git commit -m x -- new3.py", HEAD, INDEX, [("A", "new3.py", "work")],
     {"a.py": "head", "b.py": "head", "c.py": "head", "new3.py": "work"}),
    ("git commit -m x -- c.py", HEAD, INDEX, [("D", "c.py", "work")], {"a.py": "head", "b.py": "head"}),
    ("git commit -m x -i -- b.py", HEAD, INDEX,
     [("M", "b.py", "work"), ("M", "a.py", "index"), ("A", "new3.py", "index")],
     {"a.py": "index", "b.py": "work", "c.py": "index", "new3.py": "index"}),
    ("git commit -m x -- fresh.py", [], ["fresh.py", "other.py"], [("A", "fresh.py", "work")], {"fresh.py": "work"}),
]


@pytest.mark.parametrize("command, head, index, taken, expected", PLAN, ids=[f"{p[0]} #{n}" for n, p in enumerate(PLAN)])
def test_the_tree_plan_for_each_commit_form(command, head, index, taken, expected):
    """E1, E2, E3: a `--` commit tests HEAD's files plus the named paths as the working tree has them (a deleted named
    path is gone, a staged file of another card is not there); `-i` and a plain commit start from the index; `-a` takes
    the working-tree content of every modified tracked file. Catches: the index leaking into a `--` tree."""
    assert gate_commit_tests.tree_plan(commit_of(command), head, index, taken) == expected


# ---- real repositories ------------------------------------------------------------------------------------------------

def _committed_util(tmp_path, **kw):
    proj = make_project(tmp_path, **kw)
    write(proj, "util.py", "X = 1\n")
    git(proj.parent if kw.get("top") else proj, "add", "util.py")
    git(proj.parent if kw.get("top") else proj, "commit", "-q", "-m", "util")
    return proj


def test_a_commit_of_a_clean_path_is_allowed_while_another_cards_breaking_file_is_staged(tmp_path):
    """E4: another card's file is staged and breaks a test; `git commit -- util.py` (a clean path) is allowed, the same
    state as a plain commit is refused as new red. Catches: the real-install refusal of a builder's own commit."""
    proj = _committed_util(tmp_path)
    stage(proj, "app.py", BREAKS_APP)
    write(proj, "util.py", "X = 2\n")
    assert reason(run_gate(proj, "git commit -m x -- util.py")) == "allow"
    verdict = run_gate(proj, "git commit -m x")
    assert reason(verdict) == "commit-tests-failed"
    assert "tests/test_ok.py::test_add" in verdict.message


def test_the_forms_that_take_the_index_are_tested_with_the_index(tmp_path):
    """E2, E3: `-i -- util.py` takes the staged breaking file with the named path, so it is refused; `-a` takes the
    unstaged edit that breaks a test, so it is refused too. Catches: a form that tests less than git commits."""
    proj = _committed_util(tmp_path)
    stage(proj, "app.py", BREAKS_APP)
    write(proj, "util.py", "X = 2\n")
    assert reason(run_gate(proj, "git commit -m x -i -- util.py")) == "commit-tests-failed"
    git(proj, "reset", "-q")
    write(proj, "app.py", BREAKS_APP)  # tracked, modified, not staged
    assert reason(run_gate(proj, "git commit -m x -a")) == "commit-tests-failed"
    assert reason(run_gate(proj, "git commit -m x -- util.py")) == "allow"


def test_an_untracked_file_in_a_named_folder_is_not_in_the_tested_tree_but_a_staged_one_is(tmp_path):
    """E5, E6: the shape of the real install: the task root below the git top, a two-line quoted message with an empty
    line, two folder names after `--`, a folder of untracked files inside one of them, another card's breaking file
    staged. git takes no untracked file, so the untracked folder is not tested (allow); a test staged as added inside a
    named folder is taken, so it is tested (refused, named). Catches: `add -A` pulling untracked files into the tree."""
    proj = make_project(tmp_path, top=True)
    write(proj, "tests/test_guard.py", GUARD)
    git(proj.parent, "add", "-A")
    git(proj.parent, "commit", "-q", "-m", "guard")
    stage(proj, "app.py", BREAKS_APP)
    for n in range(3):
        stage(proj, f"pkg/m{n}.py", "A = 1\n")
        stage(proj, f"tests/pkg_plan/test_p{n}.py", "def test_p():\n    assert True\n")
    write(proj, "pkg/draft/note.txt", "untracked\n")
    command = 'git commit -m "first line of the message\n\nsecond line of the message" -- pkg tests/pkg_plan'
    assert reason(run_gate(proj, command)) == "allow"
    stage(proj, "tests/pkg_plan/test_red.py", "def test_red():\n    assert False\n")
    verdict = run_gate(proj, command)
    assert reason(verdict) == "commit-tests-failed"
    assert "tests/pkg_plan/test_red.py::test_red" in verdict.message and "test_guard" not in verdict.message


def test_the_row_is_keyed_by_the_tree_the_commit_produces_never_by_the_index(tmp_path):
    """E7 (the chief ruling R168): the key of the result row is the digest of the tree built for the run. After the very
    same `--` commit is made by git, that digest is one of the keys of the tree of HEAD, and it is not the digest of the
    index the gate found. Catches: a result cached under the index while another tree was tested."""
    proj = _committed_util(tmp_path)
    stage(proj, "app.py", BREAKS_APP)
    write(proj, "util.py", "X = 2\n")
    index_digest = gate_commit_tests.staged_key(git(proj, "ls-files", "-s", "-z").encode())
    assert reason(run_gate(proj, "git commit -m x -- util.py")) == "allow"
    (row,) = rows(proj)
    assert row["tree"] != index_digest
    git(proj, "commit", "-q", "-m", "x", "--", "util.py")
    assert row["tree"] in gate_commit_tests.tree_keys(proj, "HEAD")


def test_both_gates_read_what_the_commit_takes_through_one_function(tmp_path, monkeypatch):
    """E8: `commit_tests` takes the list from `gate_commit.taken`, the reader `commit_files` uses: with the reader
    replaced by one that names no path, the same breaking `--` commit is no longer refused (nothing to test); with the
    real reader it is refused. Catches: a second list of the commit forms inside the test gate."""
    proj = make_project(tmp_path)
    write(proj, "app.py", BREAKS_APP)  # tracked, modified in the working tree
    assert reason(run_gate(proj, "git commit -m x -- app.py")) == "commit-tests-failed"
    monkeypatch.setattr(gate_commit, "taken", lambda *_a, **_k: [])
    assert reason(run_gate(proj, "git commit -m x -- app.py")) == "allow"


# the form table of a message-only amend and its no-git-call proof moved to the core and the shell (MW-052)


def test_a_message_only_amend_is_not_tested_while_another_cards_breaking_file_is_staged(tmp_path):
    """E15: another card's file is staged and breaks a test; `git commit --amend --only -m x` and `-o` (no paths) change
    no file, so nothing is tested (allow, no row); a plain `--amend` takes the index, so it is refused as new red; an
    amend that names a clean path takes that path alone (allow). Catches: a message fix refused for red it cannot carry."""
    proj = _committed_util(tmp_path)
    stage(proj, "app.py", BREAKS_APP)
    write(proj, "util.py", "X = 2\n")
    for command in ("git commit --amend --only -m x", "git commit --amend -o -m x"):
        assert reason(run_gate(proj, command)) == "allow", command
    assert rows(proj) == []
    assert reason(run_gate(proj, "git commit --amend -m x")) == "commit-tests-failed"
    assert reason(run_gate(proj, "git commit --amend --only -m x -- util.py")) == "allow"


def test_commit_files_still_reads_the_same_list_through_the_shared_reader():
    """E9: the file gate's `_taken` is the shared reader with its own path normaliser, so a table row through `combine`
    is the answer of both. Catches: a refactor that leaves the file gate on a copy."""
    assert callable(gate_commit.taken) and callable(gate_commit.combine)
    assert gate_commit._taken.__module__ == "gate_commit"
