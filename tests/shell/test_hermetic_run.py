"""Card MW-074 (decision: R177), rows E16 to E24, layer shell: a real pytest run on a small synthetic project that carries
the real conftest files. Synthetic files only, all inside tmp_path; the run is a child process of this test."""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parents[1]
CALL = "def test_x():\n    subprocess.run([sys.executable, '-c', 'pass'])\n"
NOCALL = "def test_x():\n    assert sys.executable\n"


def _project(tmp_path, core_body, other_body=None):
    """A project with the real tests/conftest.py, _markers.py, _hermetic.py and tests/core/conftest.py, eight tiny tests in
    tests/core/test_order.py, one in tests/core/test_body.py, and optionally tests/other/test_free.py."""
    proj = tmp_path / "proj"
    (proj / "tests" / "core").mkdir(parents=True)
    for name in ("conftest.py", "_markers.py", "_hermetic.py", "_template.py"):
        shutil.copy(TESTS / name, proj / "tests" / name)
    shutil.copy(TESTS / "core" / "conftest.py", proj / "tests" / "core" / "conftest.py")
    (proj / "pytest.ini").write_text("[pytest]\ntestpaths = tests\naddopts = -p no:cacheprovider\n", encoding="utf-8")
    order = "".join(f"def test_t{n}():\n    assert {n} == {n}\n" for n in range(1, 9))
    (proj / "tests" / "core" / "test_order.py").write_text(order, encoding="utf-8")
    (proj / "tests" / "core" / "test_body.py").write_text("import subprocess\nimport sys\n" + core_body, encoding="utf-8")
    if other_body is not None:
        (proj / "tests" / "other").mkdir()
        (proj / "tests" / "other" / "test_free.py").write_text("import subprocess\nimport sys\n" + other_body, encoding="utf-8")
    return proj


def _run(proj, *args):
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "PYTHONPATH")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    done = subprocess.run([sys.executable, "-m", "pytest", *args], cwd=proj, env=env, capture_output=True, text=True,
                          timeout=120)
    return done.returncode, done.stdout + done.stderr


def _order(out):
    return re.findall(r"test_order\.py::(test_t\d)", out)


def test_a_core_test_that_calls_subprocess_fails_with_the_hermetic_text(tmp_path):
    """Catches: a core test that starts a process and still passes (replay of the incident the gate is for)."""
    _code, out = _run(_project(tmp_path, CALL), "-q", "tests/core/test_body.py")
    assert "hermetic test: subprocess.run is not allowed in tests/core" in out


def test_the_same_core_test_without_the_call_passes(tmp_path):
    """Checks: the same test with the call removed passes, so the text above comes from the call alone."""
    code, _out = _run(_project(tmp_path, NOCALL), "-q", "tests/core/test_body.py")
    assert code == 0


def test_a_test_outside_the_hermetic_folder_may_start_a_process(tmp_path):
    """Checks: the guard is scoped to the folder that holds the conftest; a test elsewhere may call subprocess."""
    code, _out = _run(_project(tmp_path, NOCALL, other_body=CALL), "-q")
    assert code == 0


def test_the_same_seed_repeats_the_order_in_a_real_run(tmp_path):
    """Checks: `--seed 7` run twice gives the same order of the eight tests."""
    proj = _project(tmp_path, NOCALL)
    first = _order(_run(proj, "-v", "--seed", "7", "tests/core/test_order.py")[1])
    second = _order(_run(proj, "-v", "--seed", "7", "tests/core/test_order.py")[1])
    assert (len(first), first) == (8, second)


def test_two_seeds_give_two_orders_in_a_real_run(tmp_path):
    """Catches: a real run whose order does not follow the seed."""
    proj = _project(tmp_path, NOCALL)
    assert _order(_run(proj, "-v", "--seed", "7", "tests/core/test_order.py")[1]) != _order(
        _run(proj, "-v", "--seed", "8", "tests/core/test_order.py")[1])


def test_the_header_prints_the_given_seed(tmp_path):
    """Checks: the report header names the seed of the run."""
    _code, out = _run(_project(tmp_path, NOCALL), "--seed", "7", "tests/core/test_order.py")
    assert "hermetic seed: 7" in out.split("collected")[0]


def test_a_quiet_run_still_prints_the_seed(tmp_path):
    """Catches: a quiet run (-q hides the header) that loses the seed, so a failing order cannot be repeated."""
    _code, out = _run(_project(tmp_path, NOCALL), "-q", "--seed", "7", "tests/core/test_order.py")
    assert "hermetic seed: 7" in out


def test_a_run_without_a_seed_prints_the_seed_it_chose(tmp_path):
    """Checks: with no `--seed` the run prints the whole-number seed it took from the clock."""
    _code, out = _run(_project(tmp_path, NOCALL), "-q", "tests/core/test_order.py")
    assert re.search(r"hermetic seed: \d+\b", out)


def test_the_printed_seed_repeats_the_order(tmp_path):
    """Checks: the seed printed by a run with no `--seed`, given back, repeats that run's order."""
    proj = _project(tmp_path, NOCALL)
    out = _run(proj, "-v", "tests/core/test_order.py")[1]
    seed = re.search(r"hermetic seed: (\d+)", out).group(1)
    assert _order(_run(proj, "-v", "--seed", seed, "tests/core/test_order.py")[1]) == _order(out)
