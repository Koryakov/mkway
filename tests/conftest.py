"""One fixture for every test (MW-003 close-fix item 1): the suite may run inside a Claude chat, whose shell carries
`CLAUDECODE`; the CLI refuses the owner's commands there. A test that needs a session's shell passes the variable
itself (`_engine.cli(..., session=True)` or an explicit env).

MW-017 (addition 1), kept by MW-026: `profiles.shared_state_dir` may name a folder outside the task root only when a
profile sets `state.shared_dir`. A test that sets it must name a folder inside this repository (the pytest temp folder
lies there), or the guard fails the test: a write outside the repository."""
import os
import re
import time
from pathlib import Path

import pytest

import _hermetic
import _template

REPO = Path(__file__).resolve().parents[1]

# MW-085 (decisions: R207, R209): what an act outside the temp folder of a test gets outside `tests/core`: "warn" (a row in
# `g8_warnings.jsonl`) while the tests are rewritten, then "raise". R209's later one-line card changes this constant; a write
# into a template folder raises in every mode, and `tests/core` raises through its own conftest.
OUTSIDE_CORE_MODE = "warn"
WARN_DIR_ENV = "MKWAY_G8_WARN_DIR"
WARN_FILE = "g8_warnings.jsonl"
WARN_PROPERTY = "g8_warning"
WARN_SHOWN = 200


def pytest_addoption(parser):
    """MW-074 (decision: R177): `--seed N` repeats the shuffled order of the hermetic folders (tests/core); with none the
    seed is the clock's whole seconds. Registered here because an option must exist before a folder's conftest loads."""
    parser.addoption("--seed", type=int, default=None, help="seed of the shuffled order of the hermetic test folders")


def pytest_report_header(config):
    return f"hermetic seed: {_hermetic.run_seed(config)} (repeat the order with --seed N)"


def pytest_terminal_summary(terminalreporter, config):
    """The header is hidden by -q, the usual run of the gates; the summary always names the seed."""
    terminalreporter.write_line(f"hermetic seed: {_hermetic.run_seed(config)}")


def pytest_configure(config):
    """MW-083: `xdist_group` is registered here too, so a run without xdist (`-p no:xdist`) takes the mark without a warning.
    MW-085: the mark `g8_off` (the runtime guard does not judge the test: only a test whose subject is the guard itself, and
    it says why in its docstring), and the collector of the warning rows, in the controller only."""
    config.addinivalue_line("markers", "xdist_group(name): tests of one group run on one worker (pytest-xdist, `--dist loadgroup`)")
    config.addinivalue_line("markers", "g8_off: the runtime guard (G8) does not judge this test; its subject is the guard itself (MW-085)")
    if not hasattr(config, "workerinput"):
        config.pluginmanager.register(G8Rows(config), "mkway-g8-rows")


class G8Rows:
    """MW-085 (R209): the warning rows of a run. A worker leaves each row in the user properties of its test's report; only
    this object, in the controller (never in a worker), and only from the report of the teardown, writes them, once for each
    (id, act, path), as one JSON object per line: `{"id", "act", "path"}`, all text. The file is `g8_warnings_<start>.jsonl`
    in the folder named by `MKWAY_G8_WARN_DIR` when that is set (made if missing), else `g8_warnings.jsonl` in the controller's
    base temp folder (junk, cleared at the next run). It is emptied at the session start."""

    def __init__(self, config):
        """The variable is taken out of the environment here, before xdist starts its workers: a child run (the inner
        `mkway check` of an install test, a pytester run) must not inherit the folder and write a rows file of its own there,
        or, with a relative folder, into the tree it checks."""
        self.config, self.rows, self.seen, self.path = config, [], set(), None
        self.given = os.environ.pop(WARN_DIR_ENV, None)

    def pytest_sessionstart(self, session):
        import json
        self._json = json
        given = self.given
        if given:
            folder = Path(given)
            name = f"g8_warnings_{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
        else:
            factory = getattr(self.config, "_tmp_path_factory", None)
            folder = factory.getbasetemp() if factory is not None else Path(self.config.rootpath) / ".pytest_tmp"
            name = WARN_FILE
        folder.mkdir(parents=True, exist_ok=True)
        self.path = folder / name
        self.path.write_text("", encoding="utf-8")

    def pytest_runtest_logreport(self, report):
        if report.when != "teardown":
            return
        for key, row in report.user_properties:
            if key != WARN_PROPERTY:
                continue
            identity = (row["id"], row["act"], row["path"])
            if identity in self.seen:
                continue
            self.seen.add(identity)
            self.rows.append(row)
            with open(self.path, "a", encoding="utf-8") as handle:
                handle.write(self._json.dumps(row) + "\n")

    def pytest_terminal_summary(self, terminalreporter):
        write = terminalreporter.write_line
        write(f"G8 warnings: {len(self.rows)}")
        write(f"G8 rows file: {self.path}")
        for row in self.rows[:WARN_SHOWN]:
            write(f"G8 {row['act']} {row['id']} {row['path']}")
        if self.rows:
            write("G8 warn rows are fixed by the test-rewrite cards; the switch to raise needs a run with 0 rows")


@pytest.hookimpl(optionalhook=True)
def pytest_xdist_auto_num_workers(config):
    """MW-083 (decisions: R199, R200): `-n auto` starts half the logical cores, or `MKWAY_TEST_WORKERS` workers. This hook
    wins over xdist's own `PYTEST_XDIST_AUTO_NUM_WORKERS`, which is therefore ignored. Optional: a run without xdist
    knows no such hook."""
    import os
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import _xdist_cfg
    return _xdist_cfg.worker_count(os.cpu_count(), os.environ.get(_xdist_cfg.ENV_NAME))


@pytest.hookimpl(optionalhook=True)
def pytest_configure_node(node):
    """MW-083 (S10): the controller hands its seed to every worker it starts, so all workers shuffle `tests/core` in one
    order. Optional: a run without xdist knows no such hook."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import _xdist_cfg
    _xdist_cfg.put_seed(node.workerinput, _hermetic.run_seed(node.config))


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items):
    """MW-052: the layer markers `e2e` and `shell` go on each test by the place of its file (`_markers.marks_for`); the
    default run excludes nothing. MW-083 (S7), MW-085 (R213): every test marked `real_shared_state` goes in the xdist
    group `shared_real`, so `--dist loadgroup` runs them on one worker (they touch the same real files); a test marked
    `engine_repo` alone only reads the working tree and is spread over the workers (it may not write it: the guard refuses);
    the group is chosen by marker, never by a list of files. First in order, so xdist reads the group when it names the tests."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from _markers import marks_for
    for item in items:
        for name in marks_for(str(item.path)):
            item.add_marker(getattr(pytest.mark, name))
        if item.get_closest_marker("real_shared_state"):  # MW-085 R213: `engine_repo` alone (a read) is not shared state
            item.add_marker(pytest.mark.xdist_group("shared_real"))


@pytest.fixture(autouse=True)
def _no_session_variable(monkeypatch):
    monkeypatch.delenv("CLAUDECODE", raising=False)
    monkeypatch.delenv("MKWAY_SESSION_ID", raising=False)  # MW-110: the launcher's variable; a test that needs it sets it itself


@pytest.fixture(autouse=True)
def user_home(tmp_path, monkeypatch):
    """MW-071 (decision: R180): the close check reads a checker's agent definition from the task's `.claude/agents`, then
    from the user's folder named by the environment. No test reads the real one: HOME and USERPROFILE name an empty scratch
    folder, and a test that needs a definition there writes it (the fixture returns the folder)."""
    home = tmp_path / "userhome"
    home.mkdir(exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    return home


@pytest.fixture(autouse=True)
def _git_discovery_stops_at_the_temp_folder(request, monkeypatch):
    """MW-028: `install.detect_vcs` answers git for any folder inside a git work tree, and the temp folder of the suite
    lies inside this repository. Git stops looking for a repository at the temp folder, so a scratch folder with no
    `git init` of its own is in no work tree, as a task folder on a plain disk is."""
    base = request.config.option.basetemp
    if base is not None:
        from pathlib import Path
        monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(Path(base).resolve()))


@pytest.fixture(scope="session")
def shared_templates(tmp_path_factory):
    """MW-085 (R207 Q3): the read-only templates of this worker. A session fixture runs once per worker, so a template is
    built once per worker (no lock between workers, no new package)."""
    return _template.Templates(tmp_path_factory.mktemp("templates"), tmp_path_factory.getbasetemp())


@pytest.fixture
def template_copy(shared_templates, tmp_path):
    """MW-085: `template_copy(name, build)` builds the template `name` once per worker (`build(folder)` fills an empty
    folder) and returns a writable copy of it inside this test's own `tmp_path`. A template whose files name its own folder
    cannot be copied: it raises `TemplateHoldsItsPath`, and the test keeps building in its own `tmp_path`."""
    made = []

    def make(name, build):
        template = shared_templates.get(name, build)
        if shared_templates.holding(name):
            raise _template.TemplateHoldsItsPath(f"{name}: {shared_templates.holding(name)[:5]} name the template folder")
        made.append(name)
        return _template.copy_template(template, tmp_path / f"{name}-copy{len(made)}")
    return make


def _in_core(path):
    """True when `path` lies in a folder `tests/core` (the hermetic folder, guarded by its own conftest)."""
    parts = Path(path).parts
    return any(first == "tests" and second == "core" for first, second in zip(parts, parts[1:]))


@pytest.fixture(autouse=True)
def _g8_guard(request, tmp_path, tmp_path_factory, monkeypatch, shared_templates):
    """MW-085 (R207 Q3, R209): the runtime guard of every test outside `tests/core` (that folder raises through its own
    conftest). A write, a process and a socket outside the test's own `tmp_path` get `OUTSIDE_CORE_MODE`; a write into a
    template folder raises. The mark `g8_off` takes a test out of the guard."""
    node = request.node
    if node.get_closest_marker("g8_off") or _in_core(node.path):
        return

    plain_id = re.sub(r"@[^\[\]]*$", "", node.nodeid)  # `--dist loadgroup` puts `@<group>` on a worker's test id

    def record(act, path):
        node.user_properties.append((WARN_PROPERTY, {"id": plain_id, "act": act, "path": path}))

    label = Path(os.path.relpath(node.path.parent, request.config.rootpath)).as_posix()
    # R213c: an `engine_repo` test that does not carry `real_shared_state` may not write the engine repository outside the
    # base temp folder (which lies inside it); a `real_shared_state` test gets `scratch_root=None` and the verdict of the mode
    scratch = None if node.get_closest_marker("real_shared_state") else tmp_path_factory.getbasetemp()
    guard = _hermetic.Guard(tmp_path, shared_templates.protected, REPO, node.get_closest_marker("engine_repo") is not None,
                            OUTSIDE_CORE_MODE, record, label, scratch)
    _hermetic.install_guard(monkeypatch, guard)


@pytest.fixture(scope="session", autouse=True)
def _shared_engine_sources(tmp_path_factory, shared_templates):
    """MW-037: `test_install.make_source` builds each kind of engine source once, in this folder, and hands the same
    folder to every test that only installs from it. MW-085: the folder is protected like a template (a test never writes
    to it), and its build is a guard exit."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        import test_install
    except ImportError:  # a task's copy has no install tests (its check runs one fixture test)
        yield
        return
    real_build = test_install._build_source

    def build_outside_the_guard(*args, **kwargs):
        with _hermetic.guard_exit():
            return real_build(*args, **kwargs)

    test_install._build_source = build_outside_the_guard
    test_install.SHARED_ROOT = tmp_path_factory.mktemp("shared-sources")
    shared_templates.protect(test_install.SHARED_ROOT)
    yield
    test_install.SHARED_ROOT = None
    test_install._build_source = real_build


@pytest.fixture(autouse=True)
def _shared_state_stays_inside_the_repository(monkeypatch):
    try:
        import profiles  # a test that never imports the engine (the check's fixture test) has nothing to guard
    except ImportError:
        return
    real = profiles.shared_state_dir

    def guarded(root, profile):
        answer = real(root, profile)
        resolved = Path(answer).resolve()
        if REPO not in resolved.parents and resolved != REPO:
            raise AssertionError(f"MW-017 guard: shared state dir {resolved} is outside the repository {REPO}")
        return answer

    monkeypatch.setattr(profiles, "shared_state_dir", guarded)
