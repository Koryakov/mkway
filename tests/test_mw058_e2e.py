"""Card MW-058, through the REAL hook command: one engine install (module fixture, a scratch git repository, the task
folder below the git top). A session that holds no card runs a message-only amend with other files staged; the verdict is
read from the hook's JSON (`tests/_hook_driver.py::decision`). Synthetic names only."""
import pytest

from _hook_driver import decision, install_project

pytestmark = pytest.mark.engine_repo

NOCARD = "n1"


@pytest.fixture(scope="module")
def proj(tmp_path_factory):
    p = install_project(tmp_path_factory.mktemp("amendonly"))
    p.profile(**{"tests.command": "python green.py"})
    decision(p.fire("SessionStart", NOCARD))
    p.write("green.py", "raise SystemExit(0)\n")
    p.write("src/a.py", "VALUE = 1\n")
    p.git("add", "-f", "--", "src/a.py", "green.py")
    p.git("commit", "-q", "-m", "baseline of the amend rows")
    for n in range(3):
        p.write(f"staged/f{n}.py", f"V = {n}\n")
        p.git("add", "-f", "--", f"staged/f{n}.py")
    return p


def test_a_message_only_amend_is_allowed_through_the_real_hook_with_files_staged(proj):
    """Checks: a message-only amend passes the real hook with files staged, and a plain amend is still refused. E4."""
    command = 'git commit --amend --only -m "mkway install 1"'
    got = decision(proj.fire("PreToolUse", NOCARD, "Bash", {"command": command}))
    assert (got.kind, got.reason_id) == ("allow", None), f"{command}: {got}: {got.text}"
    command = 'git commit --amend -om "mkway install 2"'
    got = decision(proj.fire("PreToolUse", NOCARD, "Bash", {"command": command}))
    assert (got.kind, got.reason_id) == ("allow", None), f"{command}: {got}: {got.text}"
    command = 'git commit --amend -m "mkway install 3"'
    got = decision(proj.fire("PreToolUse", NOCARD, "Bash", {"command": command}))
    assert (got.kind, got.reason_id) == ("deny", "file-not-in-card"), f"{command}: {got}: {got.text}"
