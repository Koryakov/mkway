"""`mkway install` and `mkway check` (card MW-002, rows E29-E33, E45). Synthetic task roots and engine sources
under the pytest temp folder only; install and check never run on another folder.

These tests build their engine source from this engine repository's working tree, so they run only in the
engine repository (marker `engine_repo`), never in a task's copy.
"""
import json
import os
import re
import subprocess
import sys

import pytest

from _engine import FIXTURES, REPO, fake_program, make_profile, write_profile
import install

sys.path.insert(0, str(REPO / "tools"))
import term_scan  # noqa: E402

pytestmark = pytest.mark.engine_repo

CYRILLIC = re.compile("[" + chr(0x0400) + "-" + chr(0x04FF) + "]")
GIT_ID = ["-c", "user.name=mkway-test", "-c", "user.email=mkway-test"]
FIXTURE_ENTRY = {"name": "fixture_refuse", "gate": "fixture_refuse", "group": "edit",
                 "function": "fixture_gates:always_refuse", "reason_ids": ["fixture-refuse"], "event": "PreToolUse",
                 "matcher": "Edit|Write", "timeout": 10, "onFailure": "block", "mode": None, "status": "planned",
                 "default_on": True}


def git(cwd, *args):
    return subprocess.run(["git", *GIT_ID, *args], cwd=str(cwd), capture_output=True, text=True, check=True).stdout


def make_light_source(tmp_path):
    """MW-013: an engine source whose `tests/` is the one fixture test, so `mkway check` proves it runs the copy's
    tests and the term scan without running this repository's whole suite inside a test. The scan reads the
    fixture's text file, which stays in the copy under `fixtures/synthetic/`."""
    src = make_source(tmp_path, vcs="none", fresh=True)  # MW-037: it deletes files, so it keeps a private copy
    for path in (src / "tests").rglob("test_*.py"):  # the helpers stay: the allow list pins a row of `_engine.py`
        path.unlink()
    (src / "tests" / "test_fixture_pass.py").write_bytes((FIXTURES / "check_set_pass.py").read_bytes())
    return src


_SHARED_SOURCES = {}  # MW-037: one built source per kind for the whole run; a test that only installs from it reads it
SHARED_ROOT = None  # set by the session fixture in conftest.py (a folder inside the pytest temp folder)


def make_source(tmp_path, *, vcs, fixture_gate=False, tag=None, engine_gates=True, fresh=False):
    """An engine source: the fixed file set of this repository's working tree, optionally with the always-refuse
    fixture gate in its manifest, optionally a git repository with one commit (and a tag). `engine_gates=False`
    (card MW-003) drops the engine's own `on` entries, so a test of the generation mechanics sees the fixture gate
    alone. MW-037: the same kind is built once and shared, as tests only read it; `fresh=True` builds a private one
    in `tmp_path` for a test that changes its source."""
    tmp_path.mkdir(parents=True, exist_ok=True)  # the build always made the caller's folder; callers rely on it
    if fresh or SHARED_ROOT is None:
        return _build_source(tmp_path, vcs=vcs, fixture_gate=fixture_gate, tag=tag, engine_gates=engine_gates)
    key = (vcs, fixture_gate, tag, engine_gates)
    if key not in _SHARED_SOURCES:
        _SHARED_SOURCES[key] = _build_source(SHARED_ROOT / f"kind{len(_SHARED_SOURCES)}", vcs=vcs,
                                             fixture_gate=fixture_gate, tag=tag, engine_gates=engine_gates)
    return _SHARED_SOURCES[key]


def _build_source(tmp_path, *, vcs, fixture_gate, tag, engine_gates):
    src = tmp_path / f"src-{vcs}"
    for rel, data in install.folder_files(REPO).items():
        path = src / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    if fixture_gate or not engine_gates:
        manifest = json.loads((src / "engine" / "manifest.json").read_text(encoding="utf-8"))
        if not engine_gates:
            manifest["entries"] = [e for e in manifest["entries"] if e.get("status") != "on"]
        if fixture_gate:
            manifest["entries"].append(FIXTURE_ENTRY)
        (src / "engine" / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
        (src / "engine" / "fixture_gates.py").write_bytes((FIXTURES / "fixture_gates.py").read_bytes())
    if vcs == "git":
        git(src, "init", "-q")
        git(src, "add", "-A")
        git(src, "commit", "-q", "-m", "synthetic engine source")
        if tag:
            git(src, "tag", tag)
    return src


def make_task(tmp_path, *, vcs, name="task"):
    root = tmp_path / name
    root.mkdir()
    if vcs == "git":
        git(root, "init", "-q")
    return root


def clean_env(tmp_path, **extra):
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_PROJECT_DIR", "ENGINE_TERMS_FILE")}
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    env.update(HOME=str(home), USERPROFILE=str(home))
    env.update(extra)
    return env


def mkway(root, env, *args):
    return subprocess.run([sys.executable, str(REPO / "mkway.py"), *args, "--root", str(root)],
                          capture_output=True, text=True, env=env, timeout=300)


def test_check_lists_and_pins_the_term_scan_exceptions(tmp_path, monkeypatch):
    """E70 (fix check 3 M3; changed by fix check 4 F3, F7 and blind round 5): `mkway check` prints each term-scan
    exception of the copy, and fails on an exception the copy's allow list (`tools/term_scan_allow.txt`) does not
    name and on a list row with no marker. Synthetic term file: one pattern that hits the copy's one recorded
    exception line. It runs `check` in process with the nested pytest stubbed (F7), and re-pins the lock after each
    planted change, so the copy hash matches and only the scan can fail the check (F3).
    Catches: a check that prints the allow-list problems but leaves them out of its result
    (`ok = ok and not result.hits`); a check that looks at one direction of the mismatch only; a check that does not
    print the exceptions."""
    src = make_source(tmp_path, vcs="none")
    task = make_task(tmp_path, vcs="none")
    env = clean_env(tmp_path)
    assert mkway(task, env, "install", "--from", str(src), "--vcs", "none").returncode == 0
    terms = tmp_path / "terms.txt"
    terms.write_text("re:%2 %3 " + "%4\n", encoding="utf-8")  # built in two parts: this line must not hit
    real_run = subprocess.run

    def stub(argv, *args, **kwargs):  # the copy's own suite is E33's job; here only the scan part runs
        if "pytest" in argv:
            return subprocess.CompletedProcess(argv, 0, "1 passed\n", "")
        return real_run(argv, *args, **kwargs)

    monkeypatch.setattr(install.subprocess, "run", stub)
    copy = task / "mkway" / "engine"
    lock_path = task / "mkway" / "mkway.lock"

    def repin():
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        lock["hash"] = install.copy_hash(copy)
        lock_path.write_text(json.dumps(lock), encoding="utf-8")

    check_env = dict(env, ENGINE_TERMS_FILE=str(terms))
    code, lines = install.check(task, env=check_env)
    assert code == 0, lines
    assert [x for x in lines if re.fullmatch(
        r"term scan exception: tests/_engine\.py:\d+ \(cmd no-echo marker, not an NDA term\)", x)], lines
    planted = copy / "tests" / "planted.md"
    planted.write_text("x %2 %3 " + "%4 y  # term-scan: allow planted\n", encoding="utf-8")
    repin()
    code, lines = install.check(task, env=check_env)
    assert "copy hash: matches the lock" in lines and code == 1, lines
    assert "term scan: tests/planted.md:1 exception not in the allow list" in lines
    planted.write_text("x\n", encoding="utf-8")  # the planted marker is gone; the file stays
    allow = copy / "tools" / "term_scan_allow.txt"
    allow.write_text(allow.read_text(encoding="utf-8").rstrip("\r\n") + "\ntests/none.md\tB\tx\n", encoding="utf-8")
    repin()
    code, lines = install.check(task, env=check_env)
    assert "copy hash: matches the lock" in lines and code == 1, lines
    assert "term scan: tests/none.md: allow-list row has no marker with its reason" in lines


def test_fixed_set_is_nda_clean():
    """E45: every file of the fixed set holds no term hit and no Cyrillic letter, so the set stays clean as it
    grows (`fixtures/synthetic/` joined it, decision C21)."""
    try:
        entries = term_scan.resolve_entries(env=os.environ, config_path=REPO / "tools" / "term_scan.json")
    except term_scan.TermListMissing:
        pytest.fail(term_scan.MISSING_MESSAGE)
    files = [REPO / rel for rel in install.folder_files(REPO)]
    assert any(f.name == "fixture_gates.py" for f in files)
    result = term_scan.scan_files(files, entries, base=REPO)
    assert not result.hits, "\n".join(f"{h.path}:{h.line} group {h.group} #{h.index}" for h in result.hits)
    bad = [f"{p.relative_to(REPO).as_posix()}:{n}" for p in files
           for n, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1)
           if CYRILLIC.search(line)]
    assert not bad, bad


START_INPUT = json.dumps({"session_id": "s1", "hook_event_name": "SessionStart", "source": "startup"})


def _start_context(task, env, *extra):
    proc = subprocess.run([sys.executable, str(task / "mkway" / "engine" / "mkway.py"), "hook", "SessionStart",
                           "--group", "start", *extra], input=START_INPUT, capture_output=True, text=True,
                          env=dict(env, CLAUDE_PROJECT_DIR=str(task)), timeout=60)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)["hookSpecificOutput"]["additionalContext"]


def test_install_writes_the_machine_interpreter(tmp_path):
    """E47 (content check F1): install writes the interpreter it used into the untracked <state.dir>/machine.json;
    with `--python` the entries carry it and the start line still says `drift: none`."""
    src = make_source(tmp_path, vcs="none")
    task = make_task(tmp_path, vcs="none")
    # changed by fix check 2 L4: a fake `py` launcher first on PATH, so the test needs no real `py`
    fake = fake_program(tmp_path / "launcher", "py", forward_after_first=True)
    env = clean_env(tmp_path, PATH=str(fake.parent) + os.pathsep + os.environ.get("PATH", ""))
    proc = mkway(task, env, "install", "--from", str(src), "--vcs", "none", "--python", "py -3")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    machine = json.loads((task / "mkway" / "state" / "machine.json").read_text(encoding="utf-8"))
    assert machine == {"python": "py -3"}
    settings = json.loads((task / ".claude" / "settings.json").read_text(encoding="utf-8"))
    # MW-027: the committed entries carry the profile's `python.command`; the machine's own stays in machine.json, and
    # the start line says so as drift-machine
    assert settings["hooks"]["SessionStart"][0]["hooks"][0]["command"].startswith('python -I -X utf8 "${CLAUDE_PROJECT_DIR}/')
    context = _start_context(task, env)
    assert "drift: none" not in context and "drift-machine" in context


def test_profile_arg_install_has_no_false_drift(tmp_path):
    """E48 (content check F2): after `install --profile conf/p.json`, a SessionStart with the same `--profile`
    reports `drift: none`: the fresh generation carries the same `--profile` part."""
    src = make_source(tmp_path, vcs="none")
    task = make_task(tmp_path, vcs="none")
    env = clean_env(tmp_path)
    proc = mkway(task, env, "install", "--from", str(src), "--vcs", "none", "--profile", "conf/p.json")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    settings = json.loads((task / ".claude" / "settings.json").read_text(encoding="utf-8"))
    command = settings["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    assert command.endswith('--profile "${CLAUDE_PROJECT_DIR}/conf/p.json"')
    assert "drift: none" in _start_context(task, env, "--profile", str(task / "conf" / "p.json"))


