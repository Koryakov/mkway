"""Card MW-057: the commit test run sees what the working tree sees, and says why it failed.

Shell tests on a real small repository (the repository is one folder above the task root, the shape of the real
install): a test that finds its root through git or through a `.git` folder, a test that imports a sibling folder whose
scripts are staged and not committed, a test that reads a data file by an absolute path outside the repository. The
same tests pass in the working tree; the gate must pass them in the exported staged tree. Synthetic values only."""
import subprocess
import sys

import pytest

import _commit_project as cp

APP_CHANGED = "def add(a, b):\n    return a + b\n\n\nNOTE = 1\n"

GIT_ROOT = (
    "import pathlib\n"
    "import subprocess\n\n\n"
    "def test_root_from_git():\n"
    "    here = pathlib.Path(__file__).resolve().parent\n"
    "    out = subprocess.run(['git', 'rev-parse', '--show-toplevel'], cwd=str(here), capture_output=True, text=True)\n"
    "    assert out.returncode == 0, out.stderr\n"
    "    top = pathlib.Path(out.stdout.strip())\n"
    "    assert (top / 'analysis' / 'helper.py').is_file()\n"
)
DOT_GIT = (
    "import pathlib\n\n\n"
    "def test_root_from_a_dot_git_folder():\n"
    "    here = pathlib.Path(__file__).resolve()\n"
    "    tops = [p for p in here.parents if (p / '.git').exists()]\n"
    "    assert tops, 'no .git folder above ' + str(here)\n"
    "    assert (tops[0] / 'analysis' / 'helper.py').is_file()\n"
)
SIBLING = (
    "import pathlib\n"
    "import sys\n\n"
    "sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'analysis'))\n"
    "import helper\n\n\n"
    "def test_sibling_import():\n"
    "    assert helper.X == 1\n"
)


def data_test(path):
    return ("import pathlib\n\n\n"
            "def test_absolute_data_file():\n"
            f"    assert pathlib.Path({str(path)!r}).read_text(encoding='utf-8').strip() == 'data'\n")


def shape(tmp_path, body):
    """A repository whose task root is `<top>/task`; the sibling folder `analysis/` and the test are STAGED, not
    committed (as in the real install); `app.py` has a staged change, so the commit is a code commit."""
    root = cp.make_project(tmp_path, top=True)
    top = root.parent
    cp.stage(top, "analysis/helper.py", "X = 1\n")
    cp.stage(root, "tests/test_shape.py", body)
    cp.stage(root, "app.py", APP_CHANGED)
    return root


def working_tree_passes(root):
    proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/test_shape.py"],
                          cwd=str(root), capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr


@pytest.mark.parametrize("body", [GIT_ROOT, DOT_GIT, SIBLING], ids=["git-rev-parse", "dot-git-above", "sibling-import"])
def test_the_export_collects_what_the_working_tree_collects(tmp_path, body):
    """Checks: a test that finds its root through git, through a `.git` folder or through a sibling import is collected in the exported staged tree as it is in the working tree."""
    root = shape(tmp_path, body)
    working_tree_passes(root)
    verdict = cp.run_gate(root)
    assert cp.reason(verdict) == "allow", verdict.message if verdict.kind == "refuse" else ""


def test_a_data_file_by_an_absolute_path_outside_the_repo_is_read(tmp_path):
    """Checks: a data file read by an absolute path outside the repository is read in the exported staged tree."""
    outside = tmp_path / "outside" / "in.txt"
    outside.parent.mkdir()
    outside.write_text("data\n", encoding="utf-8")
    root = shape(tmp_path, data_test(outside))
    working_tree_passes(root)
    verdict = cp.run_gate(root)
    assert cp.reason(verdict) == "allow", verdict.message if verdict.kind == "refuse" else ""


USER_PKG = (
    "import userpkg\n\n\n"
    "def test_user_site_import():\n"
    "    assert userpkg.X == 1\n"
)


def user_site(tmp_path, monkeypatch):
    """A per-user package folder reached through APPDATA, the way Python on Windows finds the packages a person
    installed with `pip install --user`; the package `userpkg` lives only there."""
    appdata = tmp_path / "appdata"
    appdata.mkdir()
    monkeypatch.setenv("APPDATA", str(appdata))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    proc = subprocess.run([sys.executable, "-c", "import site;print(int(site.ENABLE_USER_SITE));"
                           "print(site.getusersitepackages())"], capture_output=True, text=True,
                          cwd=str(tmp_path), env=dict(__import__("os").environ))
    enabled, folder = proc.stdout.split("\n")[:2]
    if enabled != "1":
        pytest.skip("this Python has no user site")
    path = __import__("pathlib").Path(folder)
    path.mkdir(parents=True)
    (path / "userpkg.py").write_text("X = 1\n", encoding="utf-8")
    return path


def test_a_package_of_the_user_site_is_found_in_the_export(tmp_path, monkeypatch):
    """Checks: a package of the user site, found through APPDATA, is found by the export gate as it is by the working tree."""
    user_site(tmp_path, monkeypatch)
    root = shape(tmp_path, USER_PKG)
    working_tree_passes(root)
    verdict = cp.run_gate(root)
    assert cp.reason(verdict) == "allow", verdict.message


def test_a_test_that_needs_an_untracked_file_is_refused_and_the_refusal_says_so(tmp_path):
    """Catches: a test that needs an untracked file passing the commit gate, or a refusal that does not name the untracked file and the missing module."""
    root = cp.make_project(tmp_path, top=True)
    cp.stage(root, "tests/test_shape.py", SIBLING)
    cp.write(root.parent, "analysis/helper.py", "X = 1\n")  # in the working tree, not in the index
    cp.stage(root, "app.py", APP_CHANGED)
    working_tree_passes(root)
    verdict = cp.run_gate(root)
    assert cp.reason(verdict) == "commit-tests-failed"
    text = verdict.message
    assert "untracked" in text, text
    assert "analysis/helper.py" in text, text
    assert "ModuleNotFoundError" in text, text
    assert "helper" in text, text


# ---- the refusal text: table tests on the text building (no git, no pytest run) ---------------------------------------

COLLECT_ERRORS = """\
==================================== ERRORS ====================================
_____________ ERROR collecting tests/analysis_plan/test_plan.py ______________
ImportError while importing test module '/w/tests/analysis_plan/test_plan.py'.
Traceback:
tests/analysis_plan/test_plan.py:3: in <module>
    import heavylib
E   ModuleNotFoundError: No module named 'heavylib'
_____________ ERROR collecting tests/register/test_register.py ______________
/w/tests/register/test_register.py:5: in <module>
    DATA = open(r"C:\\data\\in.csv").read()
E   FileNotFoundError: [Errno 2] No such file or directory: 'C:\\\\data\\\\in.csv'
_____________ ERROR collecting tests/test_split.py ______________
E     File "/w/tests/test_split.py", line 1
E       def (
E           ^
E   SyntaxError: invalid syntax
=========================== short test summary info ============================
ERROR tests/analysis_plan/test_plan.py
ERROR tests/register/test_register.py
ERROR tests/test_split.py
!!!!!!!!!!!!!!!!!!! Interrupted: 3 errors during collection !!!!!!!!!!!!!!!!!!!!
"""
TEST_LEVEL = """\
=================================== FAILURES ===================================
____________________________ test_x ____________________________
E   assert 1 == 2
=========================== short test summary info ============================
FAILED tests/test_a.py::test_x - assert 1 == 2
1 failed, 3 passed in 0.1s
"""
SHORT_ONLY = """\
=========================== short test summary info ============================
ERROR tests/test_c.py - ModuleNotFoundError: No module named 'tablelib'
"""


class Ctx:
    session_id = "s1"
    env = {}


def refusal_text(output, code=1, untracked=()):
    import gate_commit_tests as g
    row = g._row(Ctx, "tree", ["python", "-m", "pytest"], code, output.encode("utf-8"), b"", 1.0, 600, "p")
    verdict = g._verdict(row, ["tests"], 600, untracked=list(untracked))
    return row, verdict.message


def test_a_file_level_failure_shows_its_first_error_line_per_file():
    """Catches: a file-level failure whose first error line is not shown per file in the refusal text."""
    row, text = refusal_text(COLLECT_ERRORS)
    assert row["failed_count"] == 3
    assert "tests/analysis_plan/test_plan.py (ModuleNotFoundError: No module named 'heavylib')" in text, text
    assert "tests/register/test_register.py (FileNotFoundError: [Errno 2] No such file or directory" in text, text
    assert "tests/test_split.py (SyntaxError: invalid syntax)" in text, text


def test_the_error_line_is_read_from_the_short_summary_when_there_is_no_section():
    """Catches: an error line not read from the short summary when the output has no section."""
    _row, text = refusal_text(SHORT_ONLY)
    assert "tests/test_c.py (ModuleNotFoundError: No module named 'tablelib')" in text, text


def test_the_error_line_is_read_from_output_with_windows_line_ends():
    """Catches: an error line lost when the output has Windows line ends."""
    _row, text = refusal_text(COLLECT_ERRORS.replace("\n", "\r\n"))
    assert "tests/analysis_plan/test_plan.py (ModuleNotFoundError: No module named 'heavylib')" in text, text
    assert "tests/test_split.py (SyntaxError: invalid syntax)" in text, text


def test_a_section_header_relative_to_the_rootdir_joins_the_summary_id_by_its_path_end():
    """Catches: a section header relative to the rootdir not joined to its summary id by the path end."""
    output =("=== ERRORS ===\r\n_ ERROR collecting .t/run-1/tree/task/src/test_gone.py _\r\nTraceback:\r\n"
              "E   ModuleNotFoundError: No module named 'gonelib'\r\n=== short test summary info ===\r\n"
              "ERROR src\\test_gone.py\r\n")
    row, text = refusal_text(output)
    assert row["failing"] == ["src/test_gone.py"]
    assert "src/test_gone.py (ModuleNotFoundError: No module named 'gonelib')" in text, text


def test_a_backslash_path_is_shown_with_slashes():
    """Catches: a backslash path shown in the refusal text instead of with slashes."""
    _row, text = refusal_text(COLLECT_ERRORS.replace("tests/test_split.py", "tests\\test_split.py"))
    assert "tests/test_split.py (SyntaxError: invalid syntax)" in text, text


def test_a_test_level_failure_keeps_its_text_unchanged():
    """Catches: a test-level failure text changed from its ruled wording."""
    _row, text = refusal_text(TEST_LEVEL)
    assert text.startswith("the tests of the staged tree are red: 1 failing (all 1): tests/test_a.py::test_x. "), text


def test_untracked_files_are_named_only_for_a_file_level_failure():
    """Catches: untracked files named for a test-level failure, or left out of a file-level one."""
    _row, with_errors = refusal_text(COLLECT_ERRORS, untracked=["analysis/helper.py", "data/x.csv"])
    assert "untracked" in with_errors, with_errors
    assert "analysis/helper.py" in with_errors, with_errors
    assert "data/x.csv" in with_errors, with_errors
    _row, without = refusal_text(TEST_LEVEL, untracked=["analysis/helper.py"])
    assert "untracked" not in without, without
    _row, none = refusal_text(COLLECT_ERRORS, untracked=[])
    assert "untracked" not in none, none


def test_the_untracked_list_is_capped_and_says_how_many_more():
    """Catches: an untracked list that is not capped at five names, or that does not say how many more it leaves out."""
    names =[f"d/f{n}.py" for n in range(12)]
    _row, text = refusal_text(COLLECT_ERRORS, untracked=names)
    assert "d/f0.py" in text, text
    assert "d/f11.py" not in text, text
    assert "7 more" in text, text


def test_the_environment_of_the_run_carries_what_python_needs_to_find_its_packages(monkeypatch):
    """Catches: a run environment that drops a variable Python needs to find its packages, or passes a secret token through."""
    import gate_commit_tests as g
    names = ("APPDATA", "LOCALAPPDATA", "PROGRAMDATA", "SYSTEMDRIVE", "USERNAME", "PYTHONUSERBASE")
    monkeypatch.setenv("APPDATA", "x")
    monkeypatch.setenv("LOCALAPPDATA", "x")
    monkeypatch.setenv("PROGRAMDATA", "x")
    monkeypatch.setenv("SYSTEMDRIVE", "x")
    monkeypatch.setenv("USERNAME", "x")
    monkeypatch.setenv("PYTHONUSERBASE", "x")
    monkeypatch.setenv("SECRET_TOKEN", "do-not-pass")
    got = {k.upper() for k in g._environment(Ctx, {})}
    assert set(names) <= got, sorted(set(names) - got)
    assert "SECRET_TOKEN" not in got
