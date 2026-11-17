"""The hermetic guard and the shuffle of small tests (card MW-074, decision: R177). Not a test module.

`tests/conftest.py` registers `--seed` and prints the seed; `tests/core/conftest.py` (a task keeps its own copy in each
folder of its profile key `tests.hermetic_dirs`) turns the guard on for the tests of its folder and shuffles them.
In-house, standard library only."""
import builtins
import contextlib
import io
import os
import random
import socket
import subprocess
import time
from pathlib import Path

SUBPROCESS_CALLS = ("run", "Popen", "call", "check_call", "check_output")
WRITE_MODE = set("wax+")


class HermeticError(AssertionError):
    """A small test did something that is not hermetic."""


def seed_for(given, now):
    """The seed of a run: the one given by `--seed`, else the whole seconds of the clock `now`."""
    return int(given) if given is not None else int(now)


def run_seed(config):
    """The seed of this pytest run, chosen once and kept on the config: the one the controller handed to this worker
    (card MW-083: every worker of a parallel run shuffles in one order), else from `--seed`, else the clock."""
    if not hasattr(config, "_hermetic_seed"):
        handed = None
        if hasattr(config, "workerinput"):
            import _xdist_cfg  # only a worker needs it: a serial run and an older copy of this folder never import it
            handed = _xdist_cfg.handed_seed(config)
        config._hermetic_seed = handed if handed is not None else seed_for(config.getoption("seed"), time.time())
    return config._hermetic_seed


def shuffle_under(items, directory, seed):
    """The items in a new list: the items whose path lies below `directory` are shuffled among the places they hold; every
    other item keeps its place."""
    inside = [i for i, item in enumerate(items) if directory in item.path.parents]
    moved = [items[i] for i in inside]
    random.Random(seed).shuffle(moved)
    out = list(items)
    for place, item in zip(inside, moved):
        out[place] = item
    return out


def _refuse(call, label):
    raise HermeticError(f"hermetic test: {call} is not allowed in {label}")


def _refuser(call, label):
    def refuse(*args, **kwargs):
        _refuse(call, label)
    return refuse


def install(monkeypatch, allowed_root, label):
    """Make the calls a small test must not make raise `HermeticError`: a process, a socket, a sleep, and a file write
    outside `allowed_root` (the test's own tmp_path). `label` is the folder named in the text."""
    for name in SUBPROCESS_CALLS:
        monkeypatch.setattr(subprocess, name, _refuser(f"subprocess.{name}", label))

    class Blocked(socket.socket):
        def __init__(self, *args, **kwargs):
            _refuse("socket.socket", label)

    monkeypatch.setattr(socket, "socket", Blocked)
    monkeypatch.setattr(time, "sleep", _refuser("time.sleep", label))
    root = Path(allowed_root).resolve()
    real_open = builtins.open

    def guarded_open(file, mode="r", *args, **kwargs):
        if not isinstance(file, int) and WRITE_MODE & set(str(mode)):
            target = Path(os.fspath(file)).resolve()
            if root != target and root not in target.parents:
                _refuse(f"file write outside tmp_path ({target})", label)
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded_open)
    monkeypatch.setattr(io, "open", guarded_open)


# ---- card MW-085 (decisions: R204, R207, R209): the guard outside tests/core, decided by one pure function -----------------

READ_ONLY_GIT = ("log", "show", "ls-files", "rev-parse", "diff", "cat-file")
GIT_OPTIONS_WITH_VALUE = ("-C", "-c")


def _inside(child, root):
    """True when `child` is `root` or lies below it. Text work only: nothing is read from the disk."""
    child, root = Path(child), Path(root)
    return child == root or root in child.parents


def _inside_any(child, roots):
    return any(_inside(child, root) for root in roots)


def git_parts(argv, cwd):
    """(subcommand, working folder) of a command line. For git: the subcommand is the first word after `git` that is not an
    option (the value of `-C` and of `-c` is not a word of its own); each `-C <path>` moves the working folder (a relative
    path lies below the folder before it, and with no folder known the result is None). A line that is not git: (None,
    `cwd`)."""
    if not argv or Path(str(argv[0])).stem.lower() != "git":
        return None, cwd
    where, words, skip = cwd, [str(word) for word in argv[1:]], False
    for index, word in enumerate(words):
        if skip:
            skip = False
        elif word in GIT_OPTIONS_WITH_VALUE:
            skip = True
            if word == "-C" and index + 1 < len(words):
                path = words[index + 1]
                if Path(path).anchor:
                    where = path
                elif where is not None:
                    where = str(Path(where) / path)
        elif not word.startswith("-"):
            return word, where
    return None, where


def decide(op, target, cwd, argv, test_tmp, template_dirs, engine_root, engine_repo_test, mode, scratch_root):
    """The verdict of one act of a test: "allow", "warn" or "refuse" (card MW-085; R207 Q2, R209 D2, R213c).

    `op` is "read", "write" (`target` is the path), "process" (`argv` and `cwd`) or "socket". `mode` is "warn" or "raise":
    what an act that is not allowed gets. A write into a template folder is refused in every mode (the template must stay
    intact). A process that works inside a template (or the shared sources) is allowed in every mode when it is one of the
    read-only git commands (`READ_ONLY_GIT`: a template exists to be read, R214), and refused in every mode otherwise. A process whose working folder lies inside `test_tmp` is allowed;
    no working folder is not. A test marked `engine_repo` (`engine_repo_test`) may run only the read-only git commands in
    the engine repository, and a write of it into the engine root outside `scratch_root` is refused in every mode, like a
    template write (R213c). `scratch_root` is the base temp folder of the run, which lies INSIDE the engine root (the
    `.pytest_tmp` of pytest.ini): without it a scratch file and an engine file cannot be told apart. `None` is for a test
    that carries `real_shared_state`: it may touch the shared state and gets the verdict of the mode. Pure: no disk, no
    process."""
    bad = "warn" if mode == "warn" else "refuse"
    if op == "read":
        return "allow"
    if op == "socket":
        return bad
    if op == "write":
        if _inside_any(target, template_dirs):
            return "refuse"
        if _inside(target, test_tmp):
            return "allow"
        if engine_repo_test and scratch_root is not None and _inside(target, engine_root) and not _inside(target, scratch_root):
            return "refuse"
        return bad
    if op == "process":
        subcommand, where = git_parts(argv.split() if isinstance(argv, str) else argv, cwd)
        if where is None:
            return bad
        if _inside_any(where, template_dirs):
            return "allow" if subcommand in READ_ONLY_GIT else "refuse"
        if _inside(where, test_tmp):
            return "allow"
        if engine_repo_test and _inside(where, engine_root) and subcommand in READ_ONLY_GIT:
            return "allow"
        return bad
    raise ValueError(f"unknown act: {op}")


_SUSPENDED = [0]


@contextlib.contextmanager
def guard_exit():
    """The acts inside the block are not judged: a template build, and the build of a shared source folder (R207 Q3)."""
    _SUSPENDED[0] += 1
    try:
        yield
    finally:
        _SUSPENDED[0] -= 1


def _path_text(value):
    return os.fsdecode(os.fspath(value))


class Guard:
    """The guard of one test outside `tests/core`. `check` judges an act with `decide`: it raises `HermeticError` on
    "refuse" and calls `record(op, path)` on "warn". `template_dirs` is a function, as the folders are known only after the
    test starts."""

    def __init__(self, test_tmp, template_dirs, engine_root, engine_repo_test, mode, record, label, scratch_root=None):
        self.test_tmp, self.engine_root = Path(test_tmp).resolve(), Path(engine_root).resolve()
        self.template_dirs, self.engine_repo_test = template_dirs, engine_repo_test
        self.scratch_root = None if scratch_root is None else Path(scratch_root).resolve()
        self.mode, self.record, self.label = mode, record, label

    def check(self, op, target=None, cwd=None, argv=None):
        if _SUSPENDED[0]:
            return
        target = None if target is None else Path(_path_text(target)).resolve()
        cwd = None if cwd is None else Path(_path_text(cwd)).resolve()
        argv = argv if isinstance(argv, str) or argv is None else [_path_text(word) for word in argv]
        templates = self.template_dirs()
        verdict = decide(op, target, cwd, argv, self.test_tmp, templates, self.engine_root, self.engine_repo_test, self.mode,
                         self.scratch_root)
        if verdict == "refuse":
            into_template = op == "write" and _inside_any(target, templates)
            into_engine = op == "write" and not into_template and self.engine_repo_test and self.scratch_root is not None \
                and _inside(target, self.engine_root) and not _inside(target, self.scratch_root)
            where_to = "into a template folder" if into_template else "into the engine repository" if into_engine else "outside tmp_path"
            what = {"write": f"file write {where_to} ({target})",
                    "process": f"process {argv} with working folder {cwd}"}.get(op, op)
            _refuse(what, self.label)
        if verdict == "warn":
            where = target if op == "write" else cwd
            self.record(op, "" if where is None else where.as_posix())


def install_guard(monkeypatch, guard):
    """Put `guard` on what a test does: a file write (`open` in a write mode, and the `os` calls that create, remove or move a
    file or a folder), a process (`subprocess.Popen`, which `run`, `call` and the `check_*` calls start) and a socket. A sleep
    is not judged outside `tests/core`."""
    real_open = builtins.open

    def guarded_open(file, mode="r", *args, **kwargs):
        if not isinstance(file, int) and WRITE_MODE & set(str(mode)):
            guard.check("write", target=file)
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded_open)
    monkeypatch.setattr(io, "open", guarded_open)

    def judge_one(name):
        real = getattr(os, name)

        def judged(path, *args, **kwargs):
            guard.check("write", target=path)
            return real(path, *args, **kwargs)
        monkeypatch.setattr(os, name, judged)

    def judge_two(name):
        real = getattr(os, name)

        def judged(source, target, *args, **kwargs):
            guard.check("write", target=source)
            guard.check("write", target=target)
            return real(source, target, *args, **kwargs)
        monkeypatch.setattr(os, name, judged)

    for name in ("mkdir", "remove", "unlink", "rmdir"):
        judge_one(name)
    for name in ("rename", "replace"):
        judge_two(name)
    real_popen = subprocess.Popen

    class JudgedPopen(real_popen):
        def __init__(self, args, *rest, **kwargs):
            guard.check("process", cwd=kwargs.get("cwd", rest[8] if len(rest) > 8 else None), argv=args)
            super().__init__(args, *rest, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", JudgedPopen)

    class JudgedSocket(socket.socket):
        def __init__(self, *args, **kwargs):
            guard.check("socket")
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(socket, "socket", JudgedSocket)
