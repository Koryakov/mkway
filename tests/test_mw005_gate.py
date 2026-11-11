"""Tests before a commit (card MW-005, part B): the gate `commit_tests`. Each test builds the tiny synthetic project of
`_commit_project.py` (one test, about a second); the engine's own suite is never run here. No task data."""
import json
import os
import time

import pytest

from _commit_project import (MANY_FAILING, git, make_project, reason, rows, run_gate, set_profile, stage, write)
from _engine import jsonl
import dispatch  # after _engine, which puts the engine folder on the path

GATES_OFF = {"commit_tests": {"on": False}}
# changed by the port onto MW-006: the file gate `commit_files` runs before `commit_tests` and refuses a session with no
# open card first, so the wiring test switches it off to reach the test gate; nothing else of that test is changed
FILES_OFF = {"commit_files": {"on": False}}


@pytest.fixture
def proj(tmp_path):
    return make_project(tmp_path)


def test_only_a_session_commit_of_a_git_project_is_gated(proj):
    """E6 (part B): a command that is not a commit, a commit with nothing staged, and any command in a project with
    `vcs: none` pass with no run (no state row); a commit through PowerShell is gated like one through Bash.
    Catches: a gate that runs the suite on every shell call, or one that skips PowerShell."""
    stage(proj, "notes.txt", "x\n")
    for command in ("git status", "git log -1", "git add notes.txt", "python -c pass"):
        assert reason(run_gate(proj, command)) == "allow", command
    assert rows(proj) == []
    git(proj, "reset", "-q")
    assert reason(run_gate(proj, "git commit -m x --allow-empty")) == "allow"
    assert rows(proj) == []
    stage(proj, "notes.txt", "x\n")
    assert reason(run_gate(proj, "git commit -m x", tool="PowerShell")) == "allow"
    assert [r["result"] for r in rows(proj)] == ["pass"]
    set_profile(proj, vcs="none")
    stage(proj, "more.txt", "y\n")
    assert reason(run_gate(proj, "git commit -m x")) == "allow"
    assert len(rows(proj)) == 1


def test_a_green_staged_tree_passes_and_leaves_one_state_row(proj):
    """E7 (part B): a commit that stages a code file runs the suite on the staged tree; green lets it through and
    writes one row in `<state>/commit_tests.jsonl` with the staged-tree hash, the result and the duration.
    Catches: a run that leaves no record, or a hash that is not one value per staged tree."""
    stage(proj, "app.py", "def add(a, b):\n    return b + a\n")
    assert reason(run_gate(proj)) == "allow"
    (row,) = rows(proj)
    assert row["result"] == "pass"
    assert isinstance(row["tree"], str) and len(row["tree"]) >= 40
    assert isinstance(row["duration_seconds"], (int, float)) and 0 <= row["duration_seconds"] < 60


def test_a_failing_suite_refuses_and_names_the_first_ten_tests_and_the_way_out(proj):
    """E8 (part B): a red suite refuses the commit (`commit-tests-failed`); the text names the first 10 failing test
    ids (12 fail, so the 11th and 12th are left out), the count, and both ways out: fix, or commit the tests alone
    as the red-first commit. The row says `fail`.
    Catches: a refusal with no test id, a list that is not capped, a refusal with no way out."""
    stage(proj, "app.py", "def add(a, b):\n    return a + b + 0\n")
    stage(proj, "tests/test_many.py", MANY_FAILING)
    verdict = run_gate(proj)
    assert reason(verdict) == "commit-tests-failed"
    text = verdict.message
    assert "tests/test_many.py::test_f01" in text and "tests/test_many.py::test_f10" in text
    assert "test_f11" not in text and "test_f12" not in text
    assert "12" in text and "red-first" in text and "fix" in text.lower()
    assert [r["result"] for r in rows(proj)] == ["fail"]


def test_the_tests_run_on_the_staged_tree_never_on_the_working_tree(proj):
    """E9 (part B): the defect that started this gate. A working tree that passes only because of an untracked conftest is refused
    (the staged tree has no such file); a working tree that is broken by an unstaged edit does not refuse a staged
    tree that is green.
    Catches: a run in the working tree, which lets an untracked file make a commit pass."""
    write(proj, "tests/conftest.py", "import pytest\n\nhelper = pytest.fixture(lambda: 1)\n")
    stage(proj, "app.py", "def add(a, b):\n    return a + b + 0\n")
    stage(proj, "tests/test_uses.py", "def test_uses(helper):\n    assert helper == 1\n")
    verdict = run_gate(proj)
    assert reason(verdict) == "commit-tests-failed"
    assert "tests/test_uses.py::test_uses" in verdict.message
    git(proj, "reset", "-q")
    (proj / "tests" / "test_uses.py").unlink()
    (proj / "tests" / "conftest.py").unlink()
    stage(proj, "notes.txt", "x\n")
    write(proj, "app.py", "def add(a, b):\n    return 0\n")  # unstaged edit that breaks the working tree
    assert reason(run_gate(proj)) == "allow"


def test_red_first_a_commit_of_tests_alone_may_be_red_anything_else_may_not(proj):
    """E10 (part B): a commit whose staged files all lie under `test_roots` may be red and runs no suite; the same
    failing test staged with a code file is refused. With `test_roots` set, the folder is the profile's.
    Catches: a red-first commit that is refused, or a mixed commit that slips through as red-first."""
    stage(proj, "tests/test_new.py", "def test_new():\n    assert False\n")
    assert reason(run_gate(proj)) == "allow"
    assert rows(proj) == []
    stage(proj, "app.py", "def add(a, b):\n    return a + b + 0\n")
    assert reason(run_gate(proj)) == "commit-tests-failed"
    git(proj, "reset", "-q")
    set_profile(proj, test_roots=["spec"])
    stage(proj, "spec/test_new.py", "def test_new():\n    assert False\n")
    assert reason(run_gate(proj)) == "allow"
    stage(proj, "tests/test_other.py", "def test_other():\n    assert False\n")
    assert reason(run_gate(proj)) == "commit-tests-failed"


def test_a_docs_only_commit_runs_no_tests(proj):
    """E11 (part B): with a red suite in HEAD, a commit whose staged files all match `paths.docs` (a Markdown file,
    a card file) is allowed with no run; with `paths.docs` set, only its globs count.
    Catches: the unread `paths.docs` key, a docs commit that waits for a suite."""
    stage(proj, "tests/test_bad.py", "def test_bad():\n    assert False\n")
    git(proj, "commit", "-q", "-m", "red head")
    stage(proj, "README.md", "# changed\n")
    stage(proj, "mkway/cards/X-001/CARD.md", "# card\n")
    assert reason(run_gate(proj)) == "allow"
    assert rows(proj) == []
    set_profile(proj, paths={"docs": ["notes/**"]})
    verdict = run_gate(proj)
    assert reason(verdict) == "commit-tests-failed"
    assert "tests/test_bad.py::test_bad" in verdict.message
    git(proj, "reset", "-q")
    stage(proj, "notes/a.txt", "a\n")
    assert reason(run_gate(proj)) == "allow"


def test_a_run_over_the_budget_is_refused_with_the_way_out(proj):
    """E12 (part B): a run that takes longer than `gates.commit_tests.budget_seconds` is stopped and refused
    (`commit-tests-over-budget`, fail closed); the text names the budget, the owner raising it in the profile in their
    terminal, and shrinking the commit. The row says `over-budget`. A raised budget runs again (a second row).
    Catches: an unbounded run, a run over budget that lets the commit through, a refusal with no way out."""
    set_profile(proj, gates={"commit_tests": {"budget_seconds": 1}})
    stage(proj, "app.py", "def add(a, b):\n    return a + b + 0\n")
    stage(proj, "tests/test_slow.py", "import time\n\n\ndef test_slow():\n    time.sleep(30)\n")
    started = time.perf_counter()
    verdict = run_gate(proj)
    assert time.perf_counter() - started < 25
    assert reason(verdict) == "commit-tests-over-budget"
    text = verdict.message.lower()
    assert "1" in verdict.message and "budget" in text and "profile" in text and "terminal" in text
    assert "smaller" in text or "shrink" in text or "split" in text
    assert [r["result"] for r in rows(proj)] == ["over-budget"]
    set_profile(proj, gates={"commit_tests": {"budget_seconds": 2}})
    assert reason(run_gate(proj)) == "commit-tests-over-budget"
    assert [r["result"] for r in rows(proj)] == ["over-budget", "over-budget"]


COUNTING = ("import os\n\n\ndef test_count():\n    with open(os.environ['COUNT_FILE'], 'a') as fh:\n"
            "        fh.write('run LEAK=%s\\n' % os.environ.get('LEAK_ME', 'none'))\n")


def test_one_run_per_staged_tree_and_only_the_named_environment_reaches_it(proj, tmp_path, monkeypatch):
    """E13 (part B): the same index is run once: the second attempt does not run again and gives the same verdict
    (a green and a red one alike); a changed index runs again. The run sees `test_env` names and not the rest of the
    session's environment.
    Catches: a re-run of an unchanged index (the biggest cost), a verdict that changes between attempts, a leak of
    the session's environment into the project's tests."""
    count = tmp_path / "count.txt"
    monkeypatch.setenv("COUNT_FILE", str(count))
    monkeypatch.setenv("LEAK_ME", "1")
    set_profile(proj, test_env=["COUNT_FILE"])
    stage(proj, "app.py", "def add(a, b):\n    return a + b + 0\n")
    stage(proj, "tests/test_count.py", COUNTING)
    assert reason(run_gate(proj)) == "allow"
    assert reason(run_gate(proj)) == "allow"
    assert count.read_text(encoding="utf-8").splitlines() == ["run LEAK=none"]
    assert len(rows(proj)) == 1
    stage(proj, "tests/test_count.py", COUNTING + "\n\ndef test_red():\n    assert False\n")
    first = run_gate(proj)
    second = run_gate(proj)
    assert reason(first) == reason(second) == "commit-tests-failed"
    assert first.message == second.message
    assert len(count.read_text(encoding="utf-8").splitlines()) == 2
    assert [r["result"] for r in rows(proj)] == ["pass", "fail"]
    assert rows(proj)[0]["tree"] != rows(proj)[1]["tree"]


def test_commit_all_and_a_pathspec_are_tested_as_the_commit_will_take_them(proj):
    """E14 (part B): `git commit -a` takes the tracked changes of the working tree and `git commit -- <path>` takes
    that path's working-tree content: each is tested on that tree, not on the index; the real index is not changed
    by the gate. A plain commit is tested on the index.
    Catches: a `-a` commit that is tested without its unstaged change."""
    stage(proj, "notes.txt", "x\n")
    write(proj, "app.py", "def add(a, b):\n    return 0\n")  # tracked, unstaged, breaks the suite
    assert reason(run_gate(proj, "git commit -m x")) == "allow"
    assert reason(run_gate(proj, "git commit -a -m x")) == "commit-tests-failed"
    assert reason(run_gate(proj, "git commit -m x -- app.py")) == "commit-tests-failed"
    assert git(proj, "diff", "--cached", "--name-only").split() == ["notes.txt"]


def test_a_commit_chained_after_a_staging_command_is_refused(proj):
    """E15 (part B): `git add ... && git commit` is refused (`commit-tests-chained`): the index is read before the
    command runs, so the gate would test the wrong tree; the text says to run the staging command alone first. A
    `cd` before the commit does not change the index and passes.
    Catches: a staged-tree gate that is bypassed by staging inside the commit command."""
    stage(proj, "notes.txt", "x\n")
    for command in ("git add -A && git commit -m x", "git add app.py; git commit -m x", "git rm -q app.py && git commit -m x"):
        verdict = run_gate(proj, command)
        assert reason(verdict) == "commit-tests-chained", command
        assert "alone" in verdict.message
    assert rows(proj) == []
    assert reason(run_gate(proj, "cd . && git commit -m x")) == "allow"


def test_a_command_that_cannot_run_the_tests_is_refused(proj):
    """E16 (part B): fail closed: `tests.command` whose program is neither the profile's Python nor git is refused
    (`commit-tests-not-run`, the text names the command); a command that starts with `python` runs with the
    profile's Python and its result counts.
    Catches: a commit that passes because the tests could not start."""
    stage(proj, "notes.txt", "x\n")
    set_profile(proj, tests={"command": "unknown-runner -x tests"})
    verdict = run_gate(proj)
    assert reason(verdict) == "commit-tests-not-run"
    assert "unknown-runner" in verdict.message
    set_profile(proj, tests={"command": "python -m pytest -q tests/test_ok.py"})
    assert reason(run_gate(proj)) == "allow"
    set_profile(proj, tests={"command": "python -m pytest -q tests/test_missing.py"})
    assert reason(run_gate(proj)) == "commit-tests-failed"


def test_the_first_commit_of_a_repository_and_a_root_below_the_top(tmp_path):
    """E17 (part B): a repository with no HEAD is tested on its index (a red one is refused); a task root below the
    top of its repository runs the suite in its own folder of the exported tree.
    Catches: a crash with no HEAD, a run in the wrong folder of the export."""
    first = make_project(tmp_path, name="first", commit=False)
    stage(first, "tests/test_bad.py", "def test_bad():\n    assert False\n")
    assert reason(run_gate(first)) == "commit-tests-failed"
    git(first, "rm", "-q", "--cached", "--", "tests/test_bad.py")
    (first / "tests" / "test_bad.py").unlink()
    assert reason(run_gate(first)) == "allow"
    deep = make_project(tmp_path, name="deep", top=True)
    stage(deep, "notes.txt", "x\n")
    assert reason(run_gate(deep)) == "allow"
    stage(deep, "app.py", "def add(a, b):\n    return 0\n")
    assert reason(run_gate(deep)) == "commit-tests-failed"


def test_the_gate_is_in_the_shell_group_after_the_lock_gate_and_has_a_switch(proj):
    """E18 (part B): the manifest entry `commit_tests` (gate `commit_tests`, group `shell`, PreToolUse on
    Bash|PowerShell, `onFailure: block`, a one-line `on_failure_reason`, the four reason ids) comes after `lock.shell`;
    through the dispatcher a red commit is denied with the tag `[mkway commit_tests commit-tests-failed]` and a log
    row; `gates.commit_tests.on: false` turns the gate off.
    Catches: a gate that is written but not wired, or one that cannot be switched off."""
    manifest = json.loads((dispatch.ENGINE_DIR / "manifest.json").read_text(encoding="utf-8"))["entries"]
    names = [e["name"] for e in manifest if e["group"] == "shell" and e["status"] == "on"]
    # changed by the port onto MW-006: the shell group also holds `touched.shell` and `commit_files`; the cheap file
    # checks of `commit_files` come before the slow test run of `commit_tests`, which still follows `lock.shell`
    # changed by the port onto MW-009: the shell group also holds `delete`, after `commit_files` and before the slow run
    assert names == ["lock.shell", "touched.shell", "commit_files", "delete", "commit_tests"]
    (entry,) = [e for e in manifest if e["name"] == "commit_tests"]
    assert (entry["gate"], entry["event"], entry["matcher"], entry["onFailure"], entry["function"]) == (
        "commit_tests", "PreToolUse", "Bash|PowerShell", "block", "gate_commit_tests:check")
    assert set(entry["reason_ids"]) == {"commit-tests-failed", "commit-tests-over-budget", "commit-tests-not-run",
                                        "commit-tests-chained"}
    assert entry["timeout"] == 900 and entry["on_failure_reason"].strip() and "\n" not in entry["on_failure_reason"]
    stage(proj, "app.py", "def add(a, b):\n    return 0\n")
    set_profile(proj, gates=FILES_OFF)
    payload = {"session_id": "s1", "tool_name": "Bash", "cwd": str(proj),
               "tool_input": {"command": "git commit -m x"}}
    env = {"CLAUDE_PROJECT_DIR": str(proj), "CLAUDECODE": "1"}
    result = dispatch.run("PreToolUse", "shell", json.dumps(payload), env=env)
    out = json.loads(result.stdout)["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny"
    assert "[mkway commit_tests commit-tests-failed]" in out["permissionDecisionReason"]
    assert ("commit_tests", "commit-tests-failed") in [
        (r["gate"], r["reason_id"]) for r in jsonl(proj / "mkway" / "state" / "refusals.jsonl")]
    set_profile(proj, gates={**FILES_OFF, **GATES_OFF})
    assert dispatch.run("PreToolUse", "shell", json.dumps(payload), env=env).stdout == ""
