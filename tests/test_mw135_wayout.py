"""Card MW-135: the refusal `commit-tests-failed` of a tests-only commit whose only red test exists at HEAD and was green
there. The red proof excuses only a test the commit defines new, so the text must say that and name the two ways out, and
must not send the builder to the «tests only» plain form (a circle). Each test builds the tiny synthetic project of
`_commit_project.py` (a real git repository, a real pytest run) and drives the gate in process. Synthetic names only."""
from _commit_project import git, make_project, rows, run_gate, stage
from test_mw056_head import app, new_card, RED


CHANGED = "from app import add\n\n\ndef test_add():\n    assert add(1, 2) == 4\n"
NEW_NAME = "from app import add\n\n\ndef test_add_four():\n    assert add(1, 2) == 4\n"
APP_PLUS_ONE = "def add(a, b):\n    return a + b + 1\n"
EXISTING = "tests/test_ok.py::test_add"
OLD_TEXT = ("the tests of the staged tree are red: new red, not red at HEAD (1): tests/test_new.py::test_new. "
            "Fix them and stage the fix, or commit the tests alone as the red-first commit (every staged file under "
            "tests; that commit may be red). Plain form of the red-first commit, run alone: `git commit -m \"CARD-001 "
            "tests only: <what>\" -- <test files>`. Only a new red blocks: an old red does not block a commit. "
            "A refused commit changes nothing: the index and the working tree stay as they are.")


def project(tmp_path):
    """CARD-001, held by the session, owns `app.py` and `tests/test_one.py`; `tests/test_ok.py::test_add` is green at HEAD."""
    root = make_project(tmp_path)
    assert new_card(root, "First", "`app.py`, `tests/test_one.py`", take=True) == "CARD-001"
    return root


def test_a_tests_only_commit_of_a_changed_existing_test_says_it_exists_at_head_and_names_two_ways(tmp_path):
    """Catches: the circle of the refusal text: a changed test that exists at HEAD and was green there is sent to the red-first commit, which the builder already made. The text says the test exists at HEAD and was green, names both ways out, and offers no plain «tests only» form."""
    root = project(tmp_path)
    stage(root, "tests/test_ok.py", CHANGED)
    verdict = run_gate(root, 'git commit -m "CARD-001 tests only: x"')
    assert verdict.kind == "refuse" and verdict.reason_id == "commit-tests-failed", (verdict.kind, verdict.message)
    text = verdict.message
    assert EXISTING in text
    assert "exists at HEAD and was green there" in text  # (a)
    assert "red-first commit does not excuse it" in text
    assert "same commit as the code change" in text  # (b) way one
    assert "new test name" in text and "green commit" in text  # (b) way two
    assert "Plain form" not in text and "tests only: <what>" not in text  # (c)
    assert "new red, not red at HEAD" not in text


def test_a_new_red_test_that_is_not_at_head_keeps_the_old_refusal_text_exactly(tmp_path):
    """Checks: no regression: a new red test that HEAD does not have is refused with the text it had before MW-135, word for word."""
    root = project(tmp_path)
    stage(root, "app.py", app(1))
    stage(root, "tests/test_new.py", RED.format(name="new"))
    verdict = run_gate(root)
    assert verdict.kind == "refuse" and verdict.reason_id == "commit-tests-failed", (verdict.kind, verdict.message)
    assert verdict.message == OLD_TEXT


def test_the_two_ways_out_of_the_changed_existing_test_pass_the_gate(tmp_path):
    """Checks: the way out is real. (1) The changed existing test committed with the code change that makes it green passes the gate. (2) The new expectation under a new test name passes as the red-first commit, the old test untouched."""
    root = project(tmp_path)
    stage(root, "tests/test_ok.py", CHANGED)
    stage(root, "app.py", APP_PLUS_ONE)
    verdict = run_gate(root, 'git commit -m "CARD-001 change"')
    assert verdict.kind != "refuse", (verdict.kind, verdict.reason_id, verdict.message)
    git(root, "reset", "-q")
    git(root, "checkout", "--", "tests/test_ok.py", "app.py")
    stage(root, "tests/test_four.py", NEW_NAME)
    verdict = run_gate(root, 'git commit -m "CARD-001 tests only: new name"')
    assert verdict.kind != "refuse", (verdict.kind, verdict.reason_id, verdict.message)
    assert rows(root)
