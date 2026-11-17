"""Card MW-085 (decisions: R204, R207, R209): the shared test templates and the runtime guard (G8) outside `tests/core`.

A costly real install is built ONCE per worker as a read-only template; each test that needs one gets a writable copy in its
own `tmp_path`. The guard decides every write, process and socket of a test (`_hermetic.decide`): in `tests/core` it raises,
elsewhere it warns (one row per test id, act and path in `g8_warnings.jsonl`), and a write into a template folder raises
everywhere. Decisions are tested on `decide` with literal values; the live wiring runs a real pytest inside a pytester folder
(the folder holds copies of the support files and writes only to targets inside itself). Synthetic values only.

The live tests carry the mark `g8_off`: their subject is the guard, and they start real child runs whose working folder is the
pytester folder; the guard of the outer run would warn on its own subject (the Log of the card says so).
"""
import json
import os
import shutil
import stat
from pathlib import Path

import pytest

import _hermetic
import _template  # absent until the green commit: every id of this file is red by a missing module

pytest_plugins = ["pytester"]

HERE = Path(__file__).resolve().parent
TMP, TPL, ENGINE, ELSE = "/w/tmp/t1", "/w/tpl/demo", "/w/engine", "/w/else"
SCRATCH = "/w/engine/.pytest_tmp"  # the base temp folder lies INSIDE the engine root (pytest.ini), hence `scratch_root`


def build_demo(folder):
    """A template with one text file that tells the build count by existing."""
    (folder / "data.txt").write_text("template\n", encoding="utf-8")


def build_read_only(folder):
    """A template whose only file carries the read-only flag (what git does to its object files)."""
    build_demo(folder)
    os.chmod(folder / "data.txt", stat.S_IREAD)


def build_with_own_path(folder):
    """A template that writes its own folder into a file: a copy of it would point back at the template."""
    (folder / "where.txt").write_text(f"built in {folder}\n", encoding="utf-8")


@pytest.fixture
def first_view(shared_templates):
    return shared_templates.get("demo-once", build_demo)


@pytest.fixture
def second_view(shared_templates):
    return shared_templates.get("demo-once", build_demo)


def test_a_template_is_built_once_and_two_fixtures_see_the_same_folder(first_view, second_view, shared_templates):
    """Checks: two fixtures that ask for the one template get the same folder and the build ran once (R207 Q3)."""
    assert first_view == second_view
    assert shared_templates.build_count("demo-once") == 1


def test_a_copy_is_its_own_and_writable(shared_templates, template_copy):
    """Checks: a copy of a template is its own and writable, with no shared files and no read-only flag kept from the template's file."""
    # a copy that shares the template's files, or keeps the read-only flag, makes a write into the copy fail or reach the template
    template = shared_templates.get("demo-copy", build_read_only)
    copy = template_copy("demo-copy", build_read_only)
    (copy / "data.txt").write_text("changed\n", encoding="utf-8")
    (copy / "new.txt").write_text("new\n", encoding="utf-8")
    assert (copy / "data.txt").read_text(encoding="utf-8") == "changed\n"
    assert (template / "data.txt").read_text(encoding="utf-8") == "template\n"
    assert not (template / "new.txt").exists()


def test_decide_refuses_a_write_into_a_template_folder_in_warn_mode():
    """Catches: a template write that only warns (R209: the one exception to warn; the template must stay intact)."""
    got = _hermetic.decide("write", f"{TPL}/data.txt", None, None, TMP, [TPL], ENGINE, False, "warn", scratch_root=SCRATCH)
    assert got == "refuse"


INNER_TEMPLATE_OVERWRITE = '''
def build(folder):
    (folder / "a.txt").write_text("a", encoding="utf-8")


def test_overwrite_a_template_file(shared_templates):
    template = shared_templates.get("inner", build)
    (template / "a.txt").write_text("b", encoding="utf-8")
'''

INNER_WRITE_TWICE_OUTSIDE = '''
import os


def test_writes_outside_its_tmp_path():
    target = os.path.join(os.path.dirname(__file__), "outside.txt")
    for _ in range(2):
        with open(target, "w", encoding="utf-8") as handle:
            handle.write("x")
'''


INNER_GROUPED_WRITE = '''
import os

import pytest

pytestmark = pytest.mark.xdist_group("grp")


def test_writes_outside_its_tmp_path():
    with open(os.path.join(os.path.dirname(__file__), "outside.txt"), "w", encoding="utf-8") as handle:
        handle.write("x")
'''

INNER_ENV_NOT_INHERITED = '''
import os


def test_the_rows_folder_is_not_in_the_environment():
    assert os.environ.get("MKWAY_G8_WARN_DIR") is None
'''


def lay_out(pytester, monkeypatch, *, core_conftest=False):
    """The inner project: copies of the support files in `tests/` (a task keeps its own copies), nothing else."""
    monkeypatch.delenv("MKWAY_G8_WARN_DIR", raising=False)
    tests = pytester.path / "tests"
    tests.mkdir()
    for name in ("conftest.py", "_hermetic.py", "_markers.py", "_xdist_cfg.py"):
        shutil.copyfile(HERE / name, tests / name)
    for path in HERE.glob("_template*.py"):
        shutil.copyfile(path, tests / path.name)
    if core_conftest:
        (tests / "core").mkdir()
        shutil.copyfile(HERE / "core" / "conftest.py", tests / "core" / "conftest.py")
    return tests


def rows_of(pytester):
    """The rows the inner controller wrote (its basetemp holds the file); an empty list when there is none."""
    found = list(pytester.path.glob("runpytest-*/g8_warnings.jsonl"))
    if not found:
        return []
    return [json.loads(line) for line in found[0].read_text(encoding="utf-8").splitlines() if line.strip()]


def row_summary(pytester):
    """[(act, test file name)] of the rows, in the order written."""
    return [(r["act"], r["id"].split("::")[0].rsplit("/", 1)[-1]) for r in rows_of(pytester)]


def row_ids(pytester):
    """The test ids of the rows, in the order written, from the folder `tests/suite/` on (the inner run may take the rootdir
    of the outer repository, which puts a path in front)."""
    return [r["id"].rsplit("tests/suite/", 1)[-1] for r in rows_of(pytester)]


def within(base, text):
    """True when the folder named by `text` is `base` or lies below it."""
    found = Path(text).resolve()
    return found == base or base in found.parents


@pytest.mark.g8_off
@pytest.mark.engine_repo  # copies the real support files (tests/_template*.py, conftest) read-only into the pytester folder: the guard is the subject
def test_live_a_template_file_overwritten_outside_core_raises(pytester, monkeypatch):
    """Catches: a guard that only warns on a template write outside tests/core, where the mode is warn."""
    tests = lay_out(pytester, monkeypatch)
    (tests / "suite").mkdir()
    (tests / "suite" / "test_overwrite.py").write_text(INNER_TEMPLATE_OVERWRITE, encoding="utf-8")
    result = pytester.runpytest_subprocess()
    result.assert_outcomes(failed=1)
    assert result.parseoutcomes()["failed"] == 1
    result.stdout.fnmatch_lines(["*HermeticError*template*"])


def test_the_build_saw_a_tmp_home(shared_templates, tmp_path_factory, monkeypatch):
    """Checks: a template is built with a tmp HOME, a tmp git ceiling and without the session variable of Claude Code."""
    # a template built with the real HOME, the real git ceiling or the session variable of Claude Code fails here
    monkeypatch.setenv("CLAUDECODE", "1")
    shared_templates.get("demo-env", build_demo)
    seen = shared_templates.env_at_build("demo-env")
    base = tmp_path_factory.getbasetemp().resolve()
    assert within(base, seen["HOME"])
    assert within(base, seen["USERPROFILE"])
    assert within(base, seen["GIT_CEILING_DIRECTORIES"])
    assert seen["CLAUDECODE"] is None


def test_a_copy_holds_no_template_path(shared_templates, template_copy):
    """Checks: no text file of a copy of a clean template names the template folder's absolute path."""
    # such a path dies with the template, as a git worktree's gitdir file does
    template = shared_templates.get("demo-clean", build_demo)
    copy = template_copy("demo-clean", build_demo)
    assert _template.files_holding(copy, template) == []


def test_a_template_that_holds_its_own_path_is_refused_for_copies(template_copy):
    """Catches: a copy of a template whose files point back at the template folder; the test must keep building (R207 Q2)."""
    with pytest.raises(_template.TemplateHoldsItsPath):
        template_copy("demo-dirty", build_with_own_path)


# Each case: operation, target, cwd, argv, is an engine_repo test, the verdict of mode "warn", the verdict of mode "raise".
DECIDE_CASES = [
    pytest.param("write", f"{ELSE}/x.txt", None, None, False, "warn", "refuse", id="write-outside-the-test-tmp"),
    pytest.param("write", f"{TMP}/x.txt", None, None, False, "allow", "allow", id="write-inside-the-test-tmp"),
    pytest.param("write", f"{TMP}/sub/deep/x.txt", None, None, False, "allow", "allow", id="write-nested-in-the-test-tmp"),
    pytest.param("write", "/w/tmp/t2/x.txt", None, None, False, "warn", "refuse", id="write-in-a-sibling-tmp-of-the-basetemp"),
    pytest.param("process", None, None, ["python", "-c", "pass"], False, "warn", "refuse", id="process-with-no-cwd"),
    pytest.param("process", None, TMP, ["python", "-c", "pass"], False, "allow", "allow", id="process-cwd-in-the-test-tmp"),
    pytest.param("process", None, f"{TMP}/repo", ["python", "-c", "pass"], False, "allow", "allow", id="process-cwd-below-the-test-tmp"),
    pytest.param("process", None, ELSE, ["python", "-c", "pass"], False, "warn", "refuse", id="process-cwd-elsewhere"),
    pytest.param("socket", None, None, None, False, "warn", "refuse", id="socket"),
    pytest.param("read", f"{ENGINE}/README.md", None, None, True, "allow", "allow", id="engine-repo-test-reads-the-engine-repo"),
    pytest.param("write", f"{ENGINE}/x.txt", None, None, False, "warn", "refuse", id="other-test-writes-the-engine-repo"),
    pytest.param("process", None, None, ["git", "-C", ENGINE, "log", "-1"], True, "allow", "allow", id="engine-repo-test-git-C-log"),
    pytest.param("process", None, None, ["git", "-C", ENGINE, "commit", "-m", "x"], True, "warn", "refuse", id="engine-repo-test-git-C-commit"),
    pytest.param("process", None, None, ["git", "-C", ENGINE, "log", "-1"], False, "warn", "refuse", id="other-test-git-C-log-in-the-engine-repo"),
    pytest.param("process", None, ENGINE, ["git", "--no-optional-locks", "show", "HEAD"], True, "allow", "allow", id="engine-repo-test-git-option-then-show"),
    pytest.param("process", None, ENGINE, ["git", "-c", "user.name=x", "diff"], True, "allow", "allow", id="engine-repo-test-git-c-value-then-diff"),
    pytest.param("process", None, ENGINE, ["git", "push"], True, "warn", "refuse", id="engine-repo-test-git-push"),
    pytest.param("process", None, ENGINE, ["python", "-c", "pass"], True, "warn", "refuse", id="engine-repo-test-runs-python-in-the-engine-repo"),
    pytest.param("write", f"{TPL}/data.txt", None, None, False, "refuse", "refuse", id="write-into-a-template"),
    pytest.param("process", None, f"{TPL}/sub", ["python", "-c", "pass"], False, "refuse", "refuse", id="process-cwd-in-a-template"),
    pytest.param("process", None, None, ["git", "-C", f"{TPL}/sub", "rev-parse", "--show-toplevel"], False, "allow", "allow", id="git-C-rev-parse-in-a-template"),
]


@pytest.mark.parametrize("op, target, cwd, argv, engine_repo_test, warn_says, raise_says", DECIDE_CASES)
def test_decide_table(op, target, cwd, argv, engine_repo_test, warn_says, raise_says):
    """Catches: a verdict of `decide` that differs from the ruling (R209 D2, R207 Q2) in mode warn or in mode raise."""
    in_warn = _hermetic.decide(op, target, cwd, argv, TMP, [TPL], ENGINE, engine_repo_test, "warn", scratch_root=SCRATCH)
    in_raise = _hermetic.decide(op, target, cwd, argv, TMP, [TPL], ENGINE, engine_repo_test, "raise", scratch_root=SCRATCH)
    assert (in_warn, in_raise) == (warn_says, raise_says)


# R213c: a write into the engine repository by an `engine_repo` test that does not carry `real_shared_state` is a real act,
# refused in every mode (the same class as a template write). `scratch_root` is the base temp folder: it lies inside the
# engine root (pytest.ini), so without it the guard could not tell a scratch file from an engine file. A test with
# `real_shared_state` passes `scratch_root=None`: it may touch the shared state and gets the verdict of the mode.
# Each case: target, is an engine_repo test, scratch_root, the verdict of mode "warn", the verdict of mode "raise".
ENGINE_WRITE_CASES = [
    pytest.param(f"{ENGINE}/engine/x.py", True, SCRATCH, "refuse", "refuse", id="engine-repo-test-writes-an-engine-file"),
    pytest.param(f"{ENGINE}/x.txt", True, SCRATCH, "refuse", "refuse", id="engine-repo-test-writes-the-engine-root"),
    pytest.param(f"{ENGINE}/.pytest_tmpx/x.txt", True, SCRATCH, "refuse", "refuse", id="engine-repo-test-writes-a-folder-named-like-the-scratch"),
    pytest.param(f"{SCRATCH}/popen-gw0/gates0/x.txt", True, SCRATCH, "warn", "refuse", id="engine-repo-test-writes-the-base-temp-folder"),
    pytest.param(f"{ENGINE}/engine/x.py", True, None, "warn", "refuse", id="real-shared-state-test-writes-an-engine-file"),
    pytest.param(f"{ENGINE}/engine/x.py", False, SCRATCH, "warn", "refuse", id="other-test-writes-an-engine-file"),
]


@pytest.mark.parametrize("target, engine_repo_test, scratch_root, warn_says, raise_says", ENGINE_WRITE_CASES)
def test_decide_table_for_a_write_into_the_engine_repository(target, engine_repo_test, scratch_root, warn_says, raise_says):
    """Catches: an engine_repo test that writes an engine file and is only warned, a refusal that also hits the base temp folder, or a real shared state test refused (R213 A2, R213c)."""
    # the base temp folder lies inside the engine root and the nine files write there; a test of real shared state follows the mode
    in_warn = _hermetic.decide("write", target, None, None, TMP, [TPL], ENGINE, engine_repo_test, "warn", scratch_root=scratch_root)
    in_raise = _hermetic.decide("write", target, None, None, TMP, [TPL], ENGINE, engine_repo_test, "raise", scratch_root=scratch_root)
    assert (in_warn, in_raise) == (warn_says, raise_says)


@pytest.mark.g8_off
@pytest.mark.engine_repo  # copies the real support files (tests/_template*.py, conftest) read-only into the pytester folder: the guard is the subject
def test_outside_core_a_write_outside_the_tmp_path_passes_and_leaves_one_row(pytester, monkeypatch):
    """Checks: a write outside the tmp path from a test outside tests/core passes in mode warn and leaves exactly one row for the act."""
    # a guard that fails the test, or writes a row twice for one act, or none, fails here
    tests = lay_out(pytester, monkeypatch)
    (tests / "suite").mkdir()
    (tests / "suite" / "test_outside.py").write_text(INNER_WRITE_TWICE_OUTSIDE, encoding="utf-8")
    result = pytester.runpytest_subprocess()
    result.assert_outcomes(passed=1)
    result.stdout.fnmatch_lines(["G8 warnings: 1"])
    assert row_summary(pytester) == [("write", "test_outside.py")]


@pytest.mark.g8_off
@pytest.mark.engine_repo  # copies the real support files (tests/_template*.py, conftest) read-only into the pytester folder: the guard is the subject
def test_in_core_the_same_write_fails(pytester, monkeypatch):
    """Catches: a guard that only warns inside tests/core, where every such act must fail the test."""
    tests = lay_out(pytester, monkeypatch, core_conftest=True)
    (tests / "core" / "test_outside.py").write_text(INNER_WRITE_TWICE_OUTSIDE, encoding="utf-8")
    result = pytester.runpytest_subprocess()
    result.assert_outcomes(failed=1)
    assert result.parseoutcomes()["failed"] == 1
    result.stdout.fnmatch_lines(["*hermetic test: file write outside tmp_path*"])


@pytest.mark.g8_off
@pytest.mark.engine_repo  # copies the real support files (tests/_template*.py, conftest) read-only into the pytester folder: the guard is the subject
def test_two_workers_write_two_rows_and_no_duplicate(pytester, monkeypatch):
    """Checks: two workers write two rows for two tests, with no duplicate and none lost between a worker and the controller (xdist, -n 2)."""
    tests = lay_out(pytester, monkeypatch)
    (tests / "suite").mkdir()
    (tests / "suite" / "test_one.py").write_text(INNER_WRITE_TWICE_OUTSIDE, encoding="utf-8")
    (tests / "suite" / "test_two.py").write_text(INNER_WRITE_TWICE_OUTSIDE, encoding="utf-8")
    result = pytester.runpytest_subprocess("-p", "xdist", "-n", "2")
    result.assert_outcomes(passed=2)
    result.stdout.fnmatch_lines(["G8 warnings: 2"])
    assert sorted(row_summary(pytester)) == [("write", "test_one.py"), ("write", "test_two.py")]


@pytest.mark.g8_off
@pytest.mark.engine_repo  # copies the real support files (tests/_template*.py, conftest) read-only into the pytester folder: the guard is the subject
def test_a_child_of_the_run_does_not_inherit_the_rows_folder(pytester, monkeypatch):
    """Checks: a child of the run does not inherit the rows folder, so it writes no rows file there."""
    # a rows folder that stays in the environment makes a child run (the inner mkway check of an install test) write its own rows file there, or, with a relative folder, into the tree the test checks
    tests = lay_out(pytester, monkeypatch)
    (tests / "suite").mkdir()
    (tests / "suite" / "test_env.py").write_text(INNER_ENV_NOT_INHERITED, encoding="utf-8")
    monkeypatch.setenv("MKWAY_G8_WARN_DIR", str(pytester.path / "rows"))
    result = pytester.runpytest_subprocess("-p", "xdist", "-n", "2")
    result.assert_outcomes(passed=1)
    assert len(list((pytester.path / "rows").glob("g8_warnings_*.jsonl"))) == 1


@pytest.mark.g8_off
@pytest.mark.engine_repo  # copies the real support files (tests/_template*.py, conftest) read-only into the pytester folder: the guard is the subject
def test_a_row_id_has_no_xdist_group_suffix(pytester, monkeypatch):
    """Checks: a row id carries no group suffix that the loadgroup distribution puts on a worker's test id."""
    # the id the rewrite cards and the register of test ids use has no @group suffix
    tests = lay_out(pytester, monkeypatch)
    (tests / "suite").mkdir()
    (tests / "suite" / "test_grouped.py").write_text(INNER_GROUPED_WRITE, encoding="utf-8")
    result = pytester.runpytest_subprocess("-p", "xdist", "-n", "2", "--dist", "loadgroup")
    result.assert_outcomes(passed=1)
    assert row_ids(pytester) == ["test_grouped.py::test_writes_outside_its_tmp_path"]


INNER_GROUPING = '''
import pytest


@pytest.mark.engine_repo
def test_engine_repo_alone_is_not_in_the_shared_lane(request):
    assert request.node.get_closest_marker("xdist_group") is None


@pytest.mark.real_shared_state
def test_real_shared_state_is_in_the_shared_lane(request):
    assert request.node.get_closest_marker("xdist_group").args == ("shared_real",)

'''


@pytest.mark.g8_off
@pytest.mark.engine_repo  # copies the real support files (tests/_template*.py, conftest) read-only into the pytester folder: the guard is the subject
def test_only_real_shared_state_goes_in_the_shared_lane(pytester, monkeypatch):
    """Checks: engine_repo alone is not in the group shared_real and a real_shared_state test is (R213 A1)."""
    # engine_repo alone is a test that only reads the working tree and would be kept on one worker; an engine_repo test that writes carries real_shared_state too
    tests = lay_out(pytester, monkeypatch)
    (tests / "suite").mkdir()
    (tests / "suite" / "test_lane.py").write_text(INNER_GROUPING, encoding="utf-8")
    result = pytester.runpytest_subprocess()
    result.assert_outcomes(passed=2)
    assert result.parseoutcomes()["passed"] == 2


INNER_ENGINE_WRITE = '''
from pathlib import Path

import pytest


@pytest.mark.engine_repo
def test_an_engine_repo_test_writes_next_to_its_tests():
    (Path(__file__).parent / "planted.txt").write_text("x", encoding="utf-8")


@pytest.mark.engine_repo
@pytest.mark.real_shared_state
def test_a_real_shared_state_test_writes_next_to_its_tests():
    (Path(__file__).parent / "planted_shared.txt").write_text("x", encoding="utf-8")


@pytest.mark.engine_repo
def test_an_engine_repo_test_writes_into_its_tmp_path(tmp_path):
    (tmp_path / "scratch.txt").write_text("x", encoding="utf-8")
'''


@pytest.mark.g8_off
@pytest.mark.engine_repo  # copies the real support files (tests/_template*.py, conftest) read-only into the pytester folder: the guard is the subject
def test_an_engine_repo_test_that_writes_the_engine_repo_fails(pytester, monkeypatch):
    """Catches: an engine_repo test without real_shared_state that writes into the engine repository and is only warned, in mode warn outside tests/core (R213 A2, R213c)."""
    # the engine repository here is the folder of the inner project; the nearest allows are in the same file: a test that also carries real_shared_state (a row, no failure) and a write into its own tmp_path
    tests = lay_out(pytester, monkeypatch)
    (tests / "suite").mkdir()
    (tests / "suite" / "test_engine_write.py").write_text(INNER_ENGINE_WRITE, encoding="utf-8")
    result = pytester.runpytest_subprocess()
    result.assert_outcomes(failed=1, passed=2)
    result.stdout.fnmatch_lines(["*HermeticError*into the engine repository*planted.txt*"])
    assert row_summary(pytester) == [("write", "test_engine_write.py")]
