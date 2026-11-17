"""Card MW-073 (decision: R177), layer shell: the shape gate reads the commit's tree and HEAD's from a real small git repository.
Synthetic files only. Paths sit in constants at the top: a test body names no test file."""
import pytest

import _engine  # noqa: F401
from _commit_project import git, make_project, set_profile, stage
from _engine import gate_call, jsonl
import gate_test_shape

NEW_FILE = "tests/test_new.py"
OTHER_FILE = "tests/test_other.py"
OUTSIDE_FILE = "src/test_new.py"
NOTES_FILE = "notes.txt"
GOOD = 'def test_new():\n    """Checks: one thing."""\n    assert 1 + 1 == 2\n'
BAD = 'def test_new():\n    """Checks: one thing."""\n    for x in (1,):\n        assert x\n'
GOOD_OTHER = 'def test_other():\n    """Checks: another thing."""\n    assert 2 + 2 == 4\n'
COMMIT = "git commit -m x"
AMEND = "git commit --amend -m x"
AMEND_MESSAGE = "git commit --amend --only -m x"  # the form that takes no file (gate_commit.message_only_amend)
NAMED = f"git commit -m x -- {NEW_FILE}"
ROW_FILE = ("mkway", "state", "test_shape.jsonl")


def _check(root, command=COMMIT):
    return gate_call(gate_test_shape.check, root, tool="Bash", tool_input={"command": command}, gate="tests.shape")


def _save(root, rel, text):
    """A file staged and committed with git directly (the test's own step, no gate)."""
    stage(root, rel, text)
    git(root, "commit", "-q", "-m", f"add {rel}")


def _stage_all(root, files):
    for rel, text in files.items():
        stage(root, rel, text)


def _rows(root):
    return jsonl(root.joinpath(*ROW_FILE))


def test_a_commit_that_adds_a_bad_test_is_refused_test_shape(tmp_path):
    """Catches: a commit that adds a test with a loop and is let through for want of any shape check on tests-only commits."""
    root = make_project(tmp_path)
    stage(root, NEW_FILE, BAD)
    verdict = _check(root)
    assert (verdict.kind, verdict.reason_id) == ("refuse", "test-shape")
    assert "tests/test_new.py::test_new: S1" in verdict.message


def test_a_commit_that_adds_a_good_test_is_allowed(tmp_path):
    """Checks: the nearest allow of the refusal above, the same file with the loop taken out."""
    root = make_project(tmp_path)
    stage(root, NEW_FILE, GOOD)
    assert _check(root).kind == "allow"


def test_a_commit_that_leaves_an_old_bad_test_as_it_is_is_allowed(tmp_path):
    """Checks: an old bad test is not judged again by a commit that only adds a good test to its file."""
    root = make_project(tmp_path)
    _save(root, NEW_FILE, BAD)
    stage(root, NEW_FILE, BAD + "\n\n" + GOOD_OTHER)
    assert _check(root).kind == "allow"


def test_the_first_commit_with_a_bad_test_is_refused(tmp_path):
    """Catches: a repository with no HEAD whose first commit holds a bad test and is not judged."""
    root = make_project(tmp_path, commit=False)
    stage(root, NEW_FILE, BAD)
    verdict = _check(root)
    assert (verdict.kind, verdict.reason_id) == ("refuse", "test-shape")
    assert "tests/test_new.py::test_new: S1" in verdict.message


def test_a_commit_of_named_paths_that_adds_a_bad_test_is_refused(tmp_path):
    """Catches: a `-- <paths>` commit judged by the index instead of the content it takes."""
    root = make_project(tmp_path)
    stage(root, NEW_FILE, BAD)
    verdict = _check(root, NAMED)
    assert (verdict.kind, verdict.reason_id) == ("refuse", "test-shape")


def test_an_amend_is_judged_against_the_parent_of_head(tmp_path):
    """Catches: an amend that keeps a bad test the amended commit holds, judged against HEAD and so seen as unchanged."""
    root = make_project(tmp_path)
    _save(root, NEW_FILE, BAD)
    stage(root, OTHER_FILE, GOOD_OTHER)
    verdict = _check(root, AMEND)
    assert (verdict.kind, verdict.reason_id) == ("refuse", "test-shape")
    assert "tests/test_new.py::test_new: S1" in verdict.message


@pytest.mark.parametrize("command, files", [(AMEND_MESSAGE, {}), (COMMIT, {NOTES_FILE: "a note\n"})],
                         ids=["message-only-amend", "no-test-file"])
def test_a_message_only_amend_and_a_commit_with_no_test_file_are_allowed(tmp_path, command, files):
    """Checks: a commit that takes no test file has nothing to judge."""
    root = make_project(tmp_path)
    _stage_all(root, files)
    assert _check(root, command).kind == "allow"


def test_a_test_file_outside_the_test_roots_is_not_judged(tmp_path):
    """Checks: a file named like a test that lies outside the profile's test roots is not a test of this project."""
    root = make_project(tmp_path)
    stage(root, OUTSIDE_FILE, BAD)
    assert _check(root).kind == "allow"


def test_the_trip_mode_refuses_and_writes_one_record_row(tmp_path):
    """Catches: a refusal that leaves no row, so nobody can count how often the gate blocks."""
    root = make_project(tmp_path)
    stage(root, NEW_FILE, BAD)
    _check(root)
    rows = _rows(root)
    assert len(rows) == 1
    assert rows[0]["mode"] == "trip"
    assert rows[0]["breaches"] == [{"file": NEW_FILE, "function": "test_new", "rule": "S1"}]


def test_the_watch_mode_allows_with_a_warn_and_writes_the_row(tmp_path):
    """Checks: in watch the gate says the reason and the rule, writes its row, and lets the commit through."""
    root = make_project(tmp_path)
    set_profile(root, tests={"shape": {"mode": "watch"}})
    stage(root, NEW_FILE, BAD)
    verdict = _check(root)
    assert (verdict.kind, verdict.reason_id) == ("warn", "test-shape")
    assert "S1" in verdict.message
    assert "watch" in verdict.message
    assert [r["mode"] for r in _rows(root)] == ["watch"]
