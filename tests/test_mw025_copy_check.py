"""Card MW-025: the install check runs only tests that fit a copy. Synthetic scratch folders only.

E1 (the guard against a test that reads a file an installed copy does not have) moved to MW-029: it no longer runs a
whole copy suite (minutes) but reads the sources of the tests a copy would run, in seconds. See
`tests/test_mw029_fast_guard.py::test_no_collected_test_reads_a_path_a_copy_lacks`.
"""
import os
import re

import pytest

from _engine import REPO
import install

pytestmark = pytest.mark.engine_repo  # the copy holds this file too: the marker keeps the guard from running itself


def _clean_env():
    return {k: v for k, v in os.environ.items() if k not in ("CLAUDE_PROJECT_DIR", "ENGINE_TERMS_FILE")}


FAILING = '''
def test_one_fails():
    assert False


def test_two_fails():
    assert False
'''


def _check_with(tmp_path, failing_tests):
    src = tmp_path / "src"
    for rel, data in install.folder_files(REPO).items():
        if rel.startswith("tests/") and rel.rsplit("/", 1)[-1].startswith("test_"):
            continue  # the copy's tests are the fixture's alone
        path = src / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    (src / "tests").mkdir(exist_ok=True)
    for name, body in failing_tests.items():
        (src / "tests" / name).write_text(body, encoding="utf-8")
    task = tmp_path / "task"
    task.mkdir()
    env = _clean_env()
    install.install(task, src, vcs="none")
    return install.check(task, env=env)


def test_check_names_the_failing_tests_not_only_the_count(tmp_path):
    """E3: a failing test in the copy: the tests line names it (`file::test`), next to the count."""
    code, lines = _check_with(tmp_path, {"test_fixture_fail.py": FAILING})
    assert code == 1
    line = next(x for x in lines if x.startswith("tests:"))
    assert "test_fixture_fail.py::test_one_fails" in line and "test_fixture_fail.py::test_two_fails" in line
    assert "2 failed" in line


def test_check_names_at_most_ten_failing_tests(tmp_path):
    """E4: twelve failures: ten names, and the line says how many more."""
    body = "\n".join(f"def test_f{n:02d}():\n    assert False\n" for n in range(12))
    code, lines = _check_with(tmp_path, {"test_fixture_many.py": body})
    line = next(x for x in lines if x.startswith("tests:"))
    assert len(re.findall(r"test_fixture_many\.py::test_f\d\d", line)) == 10
    assert "12 failed" in line and "2 more" in line


def test_the_eight_tests_that_read_engine_repository_files_are_marked():
    """E2: the eight tests of the gap carry the marker `engine_repo`, so `mkway check` in a copy leaves them out."""
    wanted = {
        "tests/test_mw016_version.py": ("test_the_changelog_covers_the_register",
                                        "test_the_readme_has_the_versioning_section"),
        "tests/test_mw017_docs.py": ("test_the_version_is_0_2_0_and_the_changelog_names_the_card",),
        "tests/test_mw017_shared.py": ("test_the_readme_and_keys_name_the_shared_files",),
        "tests/test_mw018_docs.py": ("test_the_register_row_the_changelog_line_and_the_card_folder",),
        "tests/test_mw022_locks_shared.py": ("test_the_readme_changelog_register_and_keys_name_the_card",),
        "tests/test_mw023_green_tree.py": ("test_the_register_changelog_and_card_name_the_card",),
        "tests/test_mw024_task_root.py": ("test_register_changelog_version_and_readme_name_the_card",),
    }
    for rel, names in wanted.items():
        text = (REPO / rel).read_text(encoding="utf-8")
        for name in names:
            rows = text.split(f"def {name}(")[0].rstrip().split("\n")
            marked = "engine_repo" in rows[-1] and rows[-1].lstrip().startswith("@pytest")
            assert marked or "pytestmark = pytest.mark.engine_repo" in text, f"{rel}::{name} is not marked"


def test_register_changelog_version_and_card_name_the_card():
    """E5: the register row, `## 0.2.2` above `## 0.2.1` with the card, VERSION 0.2.2, the card folder."""
    register = (REPO / "cards" / "REGISTER.md").read_text(encoding="utf-8")
    assert re.search(r"^\| MW-025 \|.*`cards/MW-025-[a-z0-9-]+`", register, re.M)
    text = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    assert text.index("\n## 0.2.2\n") < text.index("\n## 0.2.1\n")
    assert "MW-025" in text.split("\n## 0.2.2\n", 1)[1].split("\n## ", 1)[0]
    assert list((REPO / "cards").glob("MW-025-*/CARD.md"))
    assert (REPO / "VERSION").read_text(encoding="utf-8").strip() == "0.2.7"  # changed by MW-027: 0.2.7
