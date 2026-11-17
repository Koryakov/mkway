"""Card MW-072, through the REAL hook command: one engine install per test (a scratch git repository, the task folder below
the git top), one open card held by a session, a real pytest run on the committed tree. The verdict is read from the hook's
JSON (`tests/_hook_driver.py::decision`). Synthetic names only."""
import pytest

from _hook_driver import decision
from _red_project import APP2, APP_MUL, GREEN, RED_MUL, install_red

pytestmark = pytest.mark.engine_repo

NEW_FILE = "tests/test_new.py"  # R217a: a test file name is a module constant, never a literal in a test body (S5)
COMMIT = 'git commit -m "CARD-001 change"'
RED_COMMIT = 'git commit -m "CARD-001 red"'


@pytest.fixture
def proj(tmp_path):
    return install_red(tmp_path)


def record_file(p):
    return p.root / "mkway" / "state" / "red_proof.jsonl"


def fire(p, session, command=COMMIT):
    return decision(p.fire("PreToolUse", session, "Bash", {"command": command}))


def stage(p, rel, text):
    p.write(rel, text)
    p.git("add", "-f", "--", rel)


def red_first(p, session):
    stage(p, NEW_FILE,RED_MUL)
    assert fire(p, session, RED_COMMIT).kind == "allow"
    p.git("commit", "-q", "-m", "CARD-001 red")
    return record_file(p).is_file()


def test_the_real_hook_denies_a_tests_only_commit_of_a_passing_new_test(proj):
    """Catches: a gate that decides in process and lets the real hook pass a tests-only commit of a passing test."""
    p, session = proj
    stage(p, NEW_FILE,GREEN)
    got = fire(p, session)
    assert (got.kind, got.reason_id) == ("deny", "red-not-proven")


def test_the_real_hook_denies_a_commit_that_deletes_the_recorded_test(proj):
    """Catches: a green suite made by deleting the recorded red test, passed by the real hook."""
    p, session = proj
    red_first(p, session)
    p.git("rm", "-q", "--", NEW_FILE)
    stage(p, "app.py", APP_MUL)
    got = fire(p, session)
    assert (got.kind, got.reason_id) == ("deny", "red-ids-still-red")


def test_the_real_hook_denies_a_code_commit_with_no_record(proj):
    """Catches: code committed through the real hook in a root where no red test was ever committed."""
    p, session = proj
    stage(p, "app.py", APP_MUL)
    got = fire(p, session)
    assert (got.kind, got.reason_id) == ("deny", "red-not-recorded")


def test_the_real_hook_denies_a_new_test_committed_with_its_code(proj):
    """Catches: the test-after commit, a green new test with its code, passed by the real hook."""
    p, session = proj
    stage(p, NEW_FILE,GREEN)
    stage(p, "app.py", APP_MUL)
    got = fire(p, session)
    assert (got.kind, got.reason_id) == ("deny", "test-without-red-proof")


def test_the_real_hook_allows_the_red_first_commit(proj):
    """Checks: the red-first commit of a failing new test passes the real hook."""
    p, session = proj
    stage(p, NEW_FILE,RED_MUL)
    assert fire(p, session, RED_COMMIT).kind == "allow"
    assert record_file(p).is_file()


def test_the_real_hook_allows_the_code_commit_after_the_red_commit(proj):
    """Checks: the code that makes the recorded red test pass passes the real hook."""
    p, session = proj
    assert red_first(p, session)
    stage(p, "app.py", APP_MUL)
    assert fire(p, session).kind == "allow"
