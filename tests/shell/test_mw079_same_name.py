"""MW-079: the replay of the real clash (card MW-073): one test file name in tests/core and in tests/shell."""
import subprocess
import sys

import pytest

TEST_FILE = "def test_one():\n    assert 1 + 1 == 2\n"


# the without_init case names the clash; the with_init case is the nearest allow: both collected, 2 passed
@pytest.mark.parametrize(
    "extra_file, exit_code, output_has",
    [
        pytest.param("notes.txt", 2, "import file mismatch", id="without_init"),
        pytest.param("__init__.py", 0, "2 passed", id="with_init"),
    ],
)
def test_same_named_files_clash_without_a_package_and_collect_with_one(tmp_path, extra_file, exit_code, output_has):
    """Catches: a same-named test file in tests/shell and tests/core that pytest cannot collect together; with_init is the nearest allow."""
    (tmp_path / "tests" / "core").mkdir(parents=True)
    (tmp_path / "tests" / "shell").mkdir()
    (tmp_path / "tests" / "core" / "test_x.py").write_text(TEST_FILE, encoding="utf-8")
    (tmp_path / "tests" / "shell" / "test_x.py").write_text(TEST_FILE, encoding="utf-8")
    (tmp_path / "tests" / "shell" / extra_file).write_text("", encoding="utf-8")
    run = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        cwd=tmp_path, capture_output=True, text=True, timeout=15,
    )
    assert run.returncode == exit_code, run.stdout + run.stderr
    assert output_has in run.stdout + run.stderr
