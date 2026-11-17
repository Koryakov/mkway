"""Card MW-083 (decisions: R199, R200), rows E14 to E19: the real repository under a parallel run. These tests read the
real files and start a child pytest in the repository, so the module is marked `engine_repo` (a task's copy leaves it
out). MW-085 R213: the group of the shared real state, `shared_real`, is by `real_shared_state` alone. Every child run names its own `--basetemp` below tmp_path:
the fixed `.pytest_tmp` of `pytest.ini` is cleared blindly by a run, and the outer run's folders lie in it.

Time: E15 and E17 run the 1700 small tests of `tests/core` in a child (about 20 s serial), E18 and E19 collect the whole
suite once (module fixture); each of these gets a timeout of 300 s, as the row says why it is above 20 s."""
import configparser
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.engine_repo

REPO = Path(__file__).resolve().parents[1]
REQUIREMENTS = [
    "pytest-xdist==3.8.0 --hash=sha256:202ca578cfeb7370784a8c33d6d05bc6e13b4f25b5053c30a152269fd10f0b88",
    "execnet==2.1.2 --hash=sha256:67fba928dd5a544b783f6056f449e5e3931a5c378b128bc18501f7ea79e296ec",
]

# A plugin written into tmp_path: after collection it dumps, per test, the markers that name shared real state and the
# arguments of its `xdist_group` marks, to the file named by `MARKS_OUT`.
MARKS_PLUGIN = '''import json
import os


def pytest_collection_finish(session):
    rows = []
    for item in session.items:
        shared = bool(item.get_closest_marker("real_shared_state"))  # MW-085 R213: `engine_repo` alone is not shared state
        groups = [list(mark.args) for mark in item.iter_markers("xdist_group")]
        rows.append({"id": item.nodeid, "shared": shared, "groups": groups})
    with open(os.environ["MARKS_OUT"], "w", encoding="utf-8") as out:
        json.dump(rows, out)
'''


def _run(tmp_path, *args):
    """The exit code and output of `python -m pytest <args> --basetemp=<tmp_path>/bt` in the real repository."""
    env = {k: v for k, v in os.environ.items()
           if k not in ("CLAUDECODE", "PYTHONPATH", "MKWAY_TEST_WORKERS") and not k.startswith("PYTEST_XDIST")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    done = subprocess.run([sys.executable, "-m", "pytest", *args, f"--basetemp={tmp_path / 'bt'}"], cwd=REPO, env=env,
                          capture_output=True, text=True, timeout=300)
    return done.returncode, done.stdout + done.stderr


@pytest.fixture(scope="module")
def collected(tmp_path_factory):
    """The rows the plugin dumped for the whole real suite, collected once for this module."""
    work = tmp_path_factory.mktemp("marks")
    (work / "marksdump.py").write_text(MARKS_PLUGIN, encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "PYTHONPATH")}
    env.update({"PYTHONPATH": str(work), "MARKS_OUT": str(work / "rows.json"), "PYTHONDONTWRITEBYTECODE": "1"})
    subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "marksdump",
                    f"--basetemp={work / 'bt'}"], cwd=REPO, env=env, capture_output=True, text=True, timeout=300)
    return json.loads((work / "rows.json").read_text(encoding="utf-8"))


def _shared_without_the_group(rows):
    return [r["id"] for r in rows if r["shared"] and r["groups"] != [["shared_real"]]]


def _shared_count(rows):
    return len([r for r in rows if r["shared"]])


def _others_in_the_group(rows):
    """The tests with no `real_shared_state` that sit in the group `shared_real` (a group of their own, as the six
    end-to-end files keep, is not it: MW-085 R213)."""
    return [r["id"] for r in rows if not r["shared"] and ["shared_real"] in r["groups"]]


def _addopts_with_a_worker_option():
    ini = configparser.ConfigParser()
    ini.read(REPO / "pytest.ini", encoding="utf-8")
    tokens = shlex.split(ini["pytest"]["addopts"])
    return [t for t in tokens if t.startswith(("-n", "--dist", "--numprocesses"))]


def test_the_requirements_file_pins_the_two_packages():
    """Checks: the test requirements file pins exactly pytest-xdist and its execnet."""
    # Catches: a file that is missing, unpinned, or pins another package
    text = (REPO / "tools" / "requirements-test.txt").read_text(encoding="utf-8")
    assert text.splitlines() == REQUIREMENTS


@pytest.mark.real_shared_state  # starts a child pytest in the real repository (cwd=REPO), so it runs in the shared lane (R213a)
def test_the_core_tests_run_without_xdist(tmp_path):
    """Checks: the core tests run serially with xdist disabled, so a missing package does not stop pytest."""
    # Catches: a conftest hook for xdist that stops pytest when the package is absent
    code, _out = _run(tmp_path, "-q", "-p", "no:xdist", "tests/core")
    assert code == 0


def test_the_default_options_hold_no_worker_option():
    """Checks: the default options hold no worker option, so a plain run works where xdist is absent."""
    # Catches: -n or --dist in the default options
    assert _addopts_with_a_worker_option() == []


@pytest.mark.real_shared_state  # starts a child pytest in the real repository (cwd=REPO), so it runs in the shared lane (R213a)
def test_the_core_tests_run_in_parallel_with_the_guard_on(tmp_path):
    """Checks: the core tests run in parallel with the hermetic guard on, and pass."""
    # a fixed seed keeps the run from depending on the clock; Catches: workers that break the hermetic guard of tests/core
    code, _out = _run(tmp_path, "-q", "-n", "2", "--seed", "3", "tests/core")
    assert code == 0


@pytest.mark.real_shared_state  # uses the collected fixture, which starts a child collection in the real repository (R213a)
def test_every_engine_repo_and_shared_state_test_is_in_the_shared_group(collected):
    """Checks: every test of real shared state holds exactly the one group shared_real (MW-085 R213)."""
    # the group is by real_shared_state alone; Catches: a test of real shared state that parallel workers could run beside another
    assert (_shared_without_the_group(collected), _shared_count(collected) > 0) == ([], True)


@pytest.mark.real_shared_state  # uses the collected fixture, which starts a child collection in the real repository (R213a)
def test_no_other_test_is_in_the_shared_group(collected):
    """Checks: only the tests of real shared state are in the group shared_real (MW-085 R213)."""
    # every other test is spread over the workers or holds a group of its own
    assert _others_in_the_group(collected) == []
