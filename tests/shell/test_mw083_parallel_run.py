"""Card MW-083 (decisions: R199, R200), rows E11 to E13, layer shell: a real pytest run with workers on a small synthetic
project. Each project lies in tmp_path with its own `pytest.ini`; the run is a child process of the test with its
`--basetemp` inside tmp_path. A worker reports a value by writing a file under tmp_path (the output of a worker is not
transferred to the controller). Needs pytest-xdist; without it the runs fail, as these rows are about it."""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parents[1]
INI = "[pytest]\ntestpaths = tests\naddopts = -p no:cacheprovider\n"

# The root conftest of the seed project: each worker writes the seed it uses to `<SEED_OUT>/<worker id>.txt`. The second
# worker waits 1.2 s first, so a seed taken from the clock by each worker would differ from the first worker's seed.
SEED_PLUGIN = '''import os
import sys
import time
from pathlib import Path


def pytest_sessionstart(session):
    handed = getattr(session.config, "workerinput", None)
    if handed is None:
        return
    if handed["workerid"] == "gw1":
        time.sleep(1.2)
    sys.path.insert(0, str(Path(__file__).resolve().parent / "tests"))
    import _hermetic
    Path(os.environ["SEED_OUT"], handed["workerid"] + ".txt").write_text(str(_hermetic.run_seed(session.config)))
'''

# The test file of the temp project: each test writes its tmp_path to `<TEMP_OUT>/<test>-<worker id>.txt`.
TEMP_TESTS = '''import os
from pathlib import Path


def _record(tmp_path, name):
    Path(os.environ["TEMP_OUT"], name + "-" + os.environ["PYTEST_XDIST_WORKER"] + ".txt").write_text(str(tmp_path))


def test_a(tmp_path):
    _record(tmp_path, "a")


def test_b(tmp_path):
    _record(tmp_path, "b")
'''


def _seed_project(tmp_path):
    """A project with the real tests/conftest.py, _markers.py, _hermetic.py (and _xdist_cfg.py once it exists), the root
    conftest above and four tiny tests."""
    proj = tmp_path / "proj"
    (proj / "tests").mkdir(parents=True)
    for name in ("conftest.py", "_markers.py", "_hermetic.py", "_template.py", "_xdist_cfg.py"):
        if (TESTS / name).exists():
            shutil.copy(TESTS / name, proj / "tests" / name)
    (proj / "pytest.ini").write_text(INI, encoding="utf-8")
    (proj / "conftest.py").write_text(SEED_PLUGIN, encoding="utf-8")
    body = "".join(f"def test_t{n}():\n    assert {n} == {n}\n" for n in range(1, 5))
    (proj / "tests" / "test_small.py").write_text(body, encoding="utf-8")
    return proj


def _run(proj, out_dir, *args, **extra_env):
    """The exit code and the whole output of `python -m pytest <args>` in `proj`. `SEED_OUT` and `TEMP_OUT` name `out_dir`."""
    out_dir.mkdir(exist_ok=True)
    env = {k: v for k, v in os.environ.items()
           if k not in ("CLAUDECODE", "PYTHONPATH", "MKWAY_TEST_WORKERS") and not k.startswith("PYTEST_XDIST")}
    env.update({"PYTHONDONTWRITEBYTECODE": "1", "SEED_OUT": str(out_dir), "TEMP_OUT": str(out_dir)}, **extra_env)
    done = subprocess.run([sys.executable, "-m", "pytest", *args], cwd=proj, env=env, capture_output=True, text=True,
                          timeout=120)
    return done.returncode, done.stdout + done.stderr


def _files(out_dir):
    """The text of each file in `out_dir`, by file name."""
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(out_dir.glob("*.txt"))}


def _both_workers_with(printed):
    """The files two workers write when both hold the first printed seed (none when nothing was printed)."""
    return {f"gw{n}.txt": seed for seed in printed[:1] for n in (0, 1)}


def test_every_worker_uses_the_seed_the_controller_printed(tmp_path):
    """Catches: workers that each take their own clock seed, so the shuffled order differs between workers and xdist refuses the run."""
    out = tmp_path / "out"
    _code, text = _run(_seed_project(tmp_path), out, "-q", "-n", "2", "-p", "no:cacheprovider",
                       f"--basetemp={tmp_path / 'bt'}")
    printed = re.findall(r"hermetic seed: (\d+)", text)
    assert (_files(out), len(printed)) == (_both_workers_with(printed), 1)


def test_auto_takes_its_count_from_the_variable_only(tmp_path):
    """Catches: `-n auto` that counts workers by `PYTEST_XDIST_AUTO_NUM_WORKERS` or by the cores instead of `MKWAY_TEST_WORKERS`."""
    out = tmp_path / "out"
    _run(_seed_project(tmp_path), out, "-q", "-n", "auto", "--dist", "loadgroup", "-p", "no:cacheprovider",
         f"--basetemp={tmp_path / 'bt'}", MKWAY_TEST_WORKERS="2", PYTEST_XDIST_AUTO_NUM_WORKERS="5")
    assert sorted(_files(out)) == ["gw0.txt", "gw1.txt"]


def _temp_project(tmp_path):
    proj = tmp_path / "tempproj"
    (proj / "tests").mkdir(parents=True)
    (proj / "pytest.ini").write_text(INI, encoding="utf-8")
    (proj / "tests" / "test_where.py").write_text(TEMP_TESTS, encoding="utf-8")
    return proj


def _outside(paths, base):
    """The paths that do not lie below `base`."""
    root = Path(base).resolve()
    return [p for p in paths if root not in Path(p).resolve().parents]


def test_each_worker_has_its_own_temp_folder_under_the_basetemp(tmp_path):
    """Catches: workers that share one temp folder (a fixed `--basetemp` cleared blindly by each) or write outside it."""
    out = tmp_path / "out"
    base = tmp_path / "bt"
    _run(_temp_project(tmp_path), out, "-q", "-n", "2", "--dist", "each", "-p", "no:cacheprovider", f"--basetemp={base}")
    paths = list(_files(out).values())
    assert (len(set(paths)), _outside(paths, base)) == (4, [])
