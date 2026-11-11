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
    src = make_source(tmp_path, vcs="none")
    for path in (src / "tests").rglob("test_*.py"):  # the helpers stay: the allow list pins a row of `_engine.py`
        path.unlink()
    (src / "tests" / "test_fixture_pass.py").write_bytes((FIXTURES / "check_set_pass.py").read_bytes())
    return src


def make_source(tmp_path, *, vcs, fixture_gate=False, tag=None, engine_gates=True):
    """An engine source: the fixed file set of this repository's working tree, optionally with the always-refuse
    fixture gate in its manifest, optionally a git repository with one commit (and a tag). `engine_gates=False`
    (card MW-003) drops the engine's own `on` entries, so a test of the generation mechanics sees the fixture gate
    alone."""
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


def test_install_copies_the_fixed_set_and_writes_the_lock(tmp_path):
    """E29: with git, the copy is the fixed set tracked at the ref (the tag is the version); without git it is the
    folder's set files (no .git, __pycache__, .pytest_tmp, mkway/). The copy keeps the repository tree under
    <bundle.root>/engine/. The lock holds version, source sha, date and the copy's content hash, and no path."""
    src = make_source(tmp_path, vcs="git", tag="v0.1.0")
    (src / "engine" / "untracked.py").write_text("x = 1\n", encoding="utf-8")  # not tracked: not copied
    task = make_task(tmp_path, vcs="git")
    env = clean_env(tmp_path)
    proc = mkway(task, env, "install", "--from", str(src), "--ref", "v0.1.0")
    assert proc.returncode == 0, proc.stderr + proc.stdout
    copy = task / "mkway" / "engine"
    assert (copy / "mkway.py").is_file() and (copy / "engine" / "mkway.py").is_file()
    assert (copy / "cards" / "_TEMPLATE" / "CARD.md").is_file()
    assert (copy / "fixtures" / "synthetic" / "fixture_gates.py").is_file()
    assert not (copy / "engine" / "untracked.py").exists()
    assert not (copy / "cards" / "REGISTER.md").exists() and not (copy / "pytest.ini").exists()
    tracked = sorted(r for r in git(src, "ls-files").split() if install.in_set(r))
    assert sorted(p.relative_to(copy).as_posix() for p in copy.rglob("*") if p.is_file()) == tracked
    lock = json.loads((task / "mkway" / "mkway.lock").read_text(encoding="utf-8"))
    assert set(lock) == {"version", "semver", "source_sha", "date", "hash"}  # MW-016: `semver` joined the lock
    assert lock["version"] == "v0.1.0"
    assert lock["source_sha"] == git(src, "rev-parse", "HEAD").strip()
    assert lock["hash"] == install.copy_hash(copy)

    plain = make_source(tmp_path, vcs="none")
    (plain / "engine" / "__pycache__").mkdir()
    (plain / "engine" / "__pycache__" / "x.pyc").write_bytes(b"\0")
    (plain / ".pytest_tmp" / "junk").mkdir(parents=True)
    (plain / "mkway" / "engine").mkdir(parents=True)
    (plain / "mkway" / "engine" / "stray.py").write_text("y = 2\n", encoding="utf-8")
    task2 = make_task(tmp_path, vcs="none", name="task2")
    proc = mkway(task2, env, "install", "--from", str(plain), "--vcs", "none")
    assert proc.returncode == 0, proc.stderr + proc.stdout
    copy2 = task2 / "mkway" / "engine"
    files = sorted(p.relative_to(copy2).as_posix() for p in copy2.rglob("*") if p.is_file())
    assert files == sorted(install.folder_files(plain))
    assert not any("__pycache__" in f or f.startswith(("mkway/", ".pytest_tmp/")) for f in files)
    lock2 = json.loads((task2 / "mkway" / "mkway.lock").read_text(encoding="utf-8"))
    assert (lock2["version"], lock2["source_sha"]) == ("unversioned", None)


def test_install_creates_folders_starter_profile_and_ignore_lines(tmp_path):
    """E30: install creates cards/, ledger/, locks/ and state/, writes a starter profile only when none exists
    (card prefix CARD, no path), and with vcs git ignores the copy, locks/ and state/ but not the profile, the
    lock, cards/ or ledger/; with vcs none it writes no ignore line. (Changed by R18: cards/ and ledger/ are
    tracked.)"""
    src = make_source(tmp_path, vcs="none")
    task = make_task(tmp_path, vcs="git")
    env = clean_env(tmp_path)
    assert mkway(task, env, "install", "--from", str(src)).returncode == 0
    bundle = task / "mkway"
    for name in ("cards", "ledger", "locks", "state"):
        assert (bundle / name).is_dir(), name
    assert not (bundle / "cards" / "_TEMPLATE").exists()
    profile = json.loads((bundle / "profile.json").read_text(encoding="utf-8"))
    assert profile["vcs"] == "git" and profile["ids"]["card_prefix"] == "CARD"
    assert (profile["bundle"]["root"], profile["state"]["dir"]) == ("mkway", "mkway/state")
    for rel in ("mkway/engine/mkway.py", "mkway/locks/x", "mkway/state/x"):
        assert subprocess.run(["git", "check-ignore", "-q", rel], cwd=str(task)).returncode == 0, rel
    for rel in ("mkway/profile.json", "mkway/mkway.lock", "mkway/cards/x.md", "mkway/ledger/x"):
        assert subprocess.run(["git", "check-ignore", "-q", rel], cwd=str(task)).returncode == 1, rel
    custom = make_profile(gates={"x": {"on": False}}, vcs="git", ids={"card_prefix": "QQ"})
    write_profile(task, custom)
    assert mkway(task, env, "install", "--from", str(src)).returncode == 0
    assert json.loads((bundle / "profile.json").read_text(encoding="utf-8")) == custom

    task2 = make_task(tmp_path, vcs="none", name="task2")
    assert mkway(task2, env, "install", "--from", str(src), "--vcs", "none").returncode == 0
    assert json.loads((task2 / "mkway" / "profile.json").read_text(encoding="utf-8"))["vcs"] == "none"
    assert not (task2 / "mkway" / ".gitignore").exists() and not (task2 / ".gitignore").exists()


def test_hook_entries_generated_and_other_keys_kept(tmp_path):
    """E31: one entry per event and group with a gate on (and the start entry for the start line); the matcher is
    the union of the group's gate matchers; the command is `python "${CLAUDE_PROJECT_DIR}/<bundle.root>/engine/
    mkway.py" hook <event> --group <name>`; only documented fields; a second install changes nothing; every other
    key of the file is kept byte for byte, and a hook that mkway does not own is kept.
    Changed by R13c: the `edit` and `shell` entries carry `"onFailure": "block"` (the group table), the others
    none; the timeout is the sum over the group's gates of (the profile's budget_seconds, else the manifest
    timeout) + 15 s on every entry, at least 10 s.
    Changed by MW-003: the source leaves out the engine's own `on` gates, so the entries come from the fixture gate
    alone, as before."""
    src = make_source(tmp_path, vcs="none", fixture_gate=True, engine_gates=False)
    task = make_task(tmp_path, vcs="none")
    settings = task / ".claude" / "settings.local.json"
    settings.parent.mkdir()
    foreign = {"matcher": "Bash", "hooks": [{"type": "command", "command": "python other_hook.py", "timeout": 5}]}
    head = '{\n  "env": {"A":   "1"},\n  "permissions": {"allow": ["Read(x)"]},\n'
    settings.write_text(head + '  "hooks": ' + json.dumps({"PreToolUse": [foreign]}) + "\n}\n", encoding="utf-8")
    env = clean_env(tmp_path)
    assert mkway(task, env, "install", "--from", str(src), "--vcs", "none").returncode == 0
    text = settings.read_text(encoding="utf-8")
    assert text.startswith(head)
    data = json.loads(text)
    cmd = 'python -I -X utf8 "${CLAUDE_PROJECT_DIR}/mkway/engine/mkway.py" hook '
    assert data["hooks"]["SessionStart"] == [
        {"hooks": [{"type": "command", "command": cmd + "SessionStart --group start", "timeout": 15}]}]
    assert data["hooks"]["PreToolUse"] == [foreign, {"matcher": "Edit|Write", "hooks": [
        {"type": "command", "command": cmd + "PreToolUse --group edit", "timeout": 25, "onFailure": "block"}]}]
    assert set(data["hooks"]) == {"SessionStart", "PreToolUse"}
    for groups in data["hooks"].values():
        for group in groups:
            assert set(group) <= {"matcher", "hooks"}
            for h in group["hooks"]:
                assert set(h) <= {"type", "command", "timeout", "onFailure"}
    assert mkway(task, env, "install", "--from", str(src), "--vcs", "none").returncode == 0
    assert settings.read_text(encoding="utf-8") == text
    gates = [dict(FIXTURE_ENTRY, name="a", gate="a", matcher="Edit|Write", timeout=10),
             dict(FIXTURE_ENTRY, name="b", gate="b", matcher="Write|MultiEdit", timeout=30),
             dict(FIXTURE_ENTRY, name="c", gate="c", group="shell", matcher="Bash", timeout=60),
             dict(FIXTURE_ENTRY, name="d", gate="d", event="Stop", group="stop", matcher=None, timeout=30)]
    union = {(e["event"], e["group"]): e for e in install.generate_entries(make_profile(), gates)}
    assert (union[("PreToolUse", "edit")]["matcher"], union[("PreToolUse", "edit")]["timeout"]) == (
        "Edit|Write|MultiEdit", 55)
    assert [union[k]["on_failure"] for k in (("SessionStart", "start"), ("PreToolUse", "edit"),
                                             ("PreToolUse", "shell"), ("Stop", "stop"))] == [None, "block", "block",
                                                                                              None]
    budgeted = make_profile({"a": {"on": True, "budget_seconds": 3}})
    (edit,) = [e for e in install.generate_entries(budgeted, gates) if e["group"] == "edit"]
    assert edit["timeout"] == 3 + 30 + 15


def test_cards_and_ledger_are_tracked(tmp_path):
    """E67 (R18, retro-chief10, amends R9): after a fresh install with `vcs: git`, git does not ignore `cards/`,
    `ledger/`, `profile.json`, `mkway.lock` or the bundle `.gitignore`, and ignores `engine/`, `locks/` and
    `state/`. The bundle `.gitignore` names exactly those three folders."""
    src = make_source(tmp_path, vcs="none")
    task = make_task(tmp_path, vcs="git")
    env = clean_env(tmp_path)
    assert mkway(task, env, "install", "--from", str(src)).returncode == 0
    bundle = task / "mkway"
    for name in ("cards", "ledger"):
        (bundle / name / "x.md").write_text("x\n", encoding="utf-8")

    def ignored(rel):
        code = subprocess.run(["git", "check-ignore", "-q", rel], cwd=str(task)).returncode
        assert code in (0, 1), rel
        return code == 0

    for rel in ("mkway/cards/", "mkway/cards/x.md", "mkway/ledger/", "mkway/ledger/x.md", "mkway/profile.json",
                "mkway/mkway.lock", "mkway/.gitignore"):
        assert not ignored(rel), rel
    for rel in ("mkway/engine/", "mkway/engine/mkway.py", "mkway/locks/", "mkway/state/"):
        assert ignored(rel), rel
    lines = [line for line in (bundle / ".gitignore").read_text(encoding="utf-8").splitlines()
             if line and not line.startswith("#")]
    assert lines == ["engine/", "locks/", "state/"]


def test_install_names_old_ignore_lines_for_cards_and_ledger(tmp_path):
    """E72 (fix check 3 L7, C36): when the bundle `.gitignore` still holds the `cards/` or `ledger/` lines of an
    earlier install, install prints one line naming them and the R18 rule. It does not delete them. (Changed by
    blind round 5: every old line is kept; `ledger/` alone is named too.)
    Catches: a check that fires only when `cards/` is present, or only when both are; an install that keeps
    `cards/` but drops `ledger/` or the old comment line."""
    src = make_source(tmp_path, vcs="none")
    task = make_task(tmp_path, vcs="git")
    env = clean_env(tmp_path)
    assert mkway(task, env, "install", "--from", str(src)).returncode == 0
    ignore = task / "mkway" / ".gitignore"
    old = ("# mkway install: the engine copy and the work folders are not tracked; profile.json and mkway.lock are\n"
           "engine/\ncards/\nledger/\nlocks/\nstate/\n")
    ignore.write_text(old, encoding="utf-8")
    proc = mkway(task, env, "install", "--from", str(src))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    (line,) = [x for x in proc.stdout.splitlines() if x.startswith("ignore:")]
    assert "cards/" in line and "ledger/" in line and "R18" in line
    after = ignore.read_text(encoding="utf-8").splitlines()
    assert set(old.splitlines()) <= set(after)  # every old line kept
    ignore.write_text("engine/\nledger/\nlocks/\nstate/\n", encoding="utf-8")
    proc = mkway(task, env, "install", "--from", str(src))
    (line,) = [x for x in proc.stdout.splitlines() if x.startswith("ignore:")]
    assert "ledger/" in line and "cards/" not in line
    fresh = make_task(tmp_path, vcs="git", name="fresh")
    proc = mkway(fresh, env, "install", "--from", str(src))
    assert not [x for x in proc.stdout.splitlines() if x.startswith("ignore:")]


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


def test_timeout_floor_is_10_seconds():
    """E63 (fix check N7): an entry's timeout is never under 10 s: budgets that sum below -5 s (the schema sets no
    minimum) give 10."""
    gates = [dict(FIXTURE_ENTRY, name="a", gate="a", matcher="Edit", timeout=10)]
    low = make_profile({"a": {"on": True, "budget_seconds": -100}})
    (edit,) = [e for e in install.generate_entries(low, gates) if e["group"] == "edit"]
    assert edit["timeout"] == 10


def test_install_refuses_a_python_that_is_not_an_interpreter(tmp_path):
    """E59 (fix check N2): `install --python` accepts only an existing executable (a name found on PATH, or a path,
    quoted when it holds a space), optionally with the launcher's version flag (`-3`, `-3.12`), and no shell
    characters. Anything else is refused with a clean message before any write."""
    src = make_source(tmp_path, vcs="none")
    task = make_task(tmp_path, vcs="none")
    env = clean_env(tmp_path)
    missing = '"' + str(tmp_path / "none" / "python.exe") + '"'
    # fix check 2: the program must run and report Python 3.9 or later (M1); the version flag only after `py` (L3)
    other = '"' + str(fake_program(tmp_path / "bin", "notpython", prints="hello")) + '"'
    old = '"' + str(fake_program(tmp_path / "bin", "oldpython", prints="(3, 8)")) + '"'
    flagged = '"' + sys.executable + '" -3'
    # fix check 3 (blind): `py` takes one version flag and nothing else; the task folder stays empty
    fake = fake_program(tmp_path / "launcher", "py", forward_after_first=True)
    env = clean_env(tmp_path, PATH=str(fake.parent) + os.pathsep + os.environ.get("PATH", ""))
    for value in ("exit 0 || python", "python; echo x", "$(python)", "python -c 1", "no-such-interpreter-x",
                  missing, "true", other, old, flagged, "py -c 1", "py -3 -3", "py -3 -c 1", "py --3"):
        proc = mkway(task, env, "install", "--from", str(src), "--vcs", "none", "--python", value)
        assert proc.returncode == 1, value
        assert proc.stderr.startswith("mkway: --python") and "Traceback" not in proc.stderr, value
        assert list(task.iterdir()) == [], value
    # the (3, 9) boundary, a later version, and `py` with a minor version flag are accepted
    ok39 = '"' + str(fake_program(tmp_path / "bin", "py39", prints="(3, 9)")) + '"'
    ok310 = '"' + str(fake_program(tmp_path / "bin", "py310", prints="(3, 10)")) + '"'
    for n, value in enumerate((ok39, ok310, "py -3.12")):
        fresh = make_task(tmp_path, vcs="none", name=f"ok{n}")
        proc = mkway(fresh, env, "install", "--from", str(src), "--vcs", "none", "--python", value)
        assert proc.returncode == 0, value + proc.stdout + proc.stderr
    quoted = '"' + sys.executable + '"'
    assert mkway(task, env, "install", "--from", str(src), "--vcs", "none", "--python", quoted).returncode == 0
    settings = json.loads((task / ".claude" / "settings.local.json").read_text(encoding="utf-8"))
    assert settings["hooks"]["SessionStart"][0]["hooks"][0]["command"].startswith(
        quoted + ' -I -X utf8 "${CLAUDE_PROJECT_DIR}')


def test_install_never_touches_the_home_folder(tmp_path):
    """E32: install reads and writes nothing under the user's home folder."""
    src = make_source(tmp_path, vcs="none")
    task = make_task(tmp_path, vcs="none")
    env = clean_env(tmp_path)
    home = tmp_path / "home"
    (home / ".claude").mkdir()
    (home / ".claude" / "settings.json").write_text('{"hooks": {}}', encoding="utf-8")
    before = {p: p.stat().st_mtime_ns for p in home.rglob("*")}
    assert mkway(task, env, "install", "--from", str(src), "--vcs", "none").returncode == 0
    assert {p: p.stat().st_mtime_ns for p in home.rglob("*")} == before
    src_text = (REPO / "engine" / "install.py").read_text(encoding="utf-8")
    assert "home()" not in src_text and "USERPROFILE" not in src_text and "expanduser" not in src_text


def test_check_compares_hash_runs_tests_and_skips_scan(tmp_path):
    """E33: `mkway check` compares the copy's hash with the lock, runs the copy's tests without the
    engine-repository-only ones, and without a term file prints «term scan: skipped, no term list set»; one
    changed byte in the copy makes it fail and name the fix."""
    src = make_light_source(tmp_path)
    task = make_task(tmp_path, vcs="none")
    env = clean_env(tmp_path)
    assert mkway(task, env, "install", "--from", str(src), "--vcs", "none").returncode == 0
    proc = mkway(task, env, "check")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "copy hash: matches the lock" in proc.stdout
    assert re.search(r"tests: \d+ passed", proc.stdout) and "failed" not in proc.stdout
    assert "tests: 1 passed" in proc.stdout  # MW-013: check collected exactly the one fixture test
    assert "term scan: skipped, no term list set" in proc.stdout
    keys = task / "mkway" / "engine" / "engine" / "KEYS.md"
    keys.write_bytes(keys.read_bytes() + b" ")
    proc = mkway(task, env, "check")
    assert proc.returncode == 1
    assert "copy hash: differs from the lock" in proc.stdout and "mkway install" in proc.stdout


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
    settings = json.loads((task / ".claude" / "settings.local.json").read_text(encoding="utf-8"))
    assert settings["hooks"]["SessionStart"][0]["hooks"][0]["command"].startswith('py -3 -I -X utf8 "${CLAUDE_PROJECT_DIR}/')
    assert "drift: none" in _start_context(task, env)


def test_profile_arg_install_has_no_false_drift(tmp_path):
    """E48 (content check F2): after `install --profile conf/p.json`, a SessionStart with the same `--profile`
    reports `drift: none`: the fresh generation carries the same `--profile` part."""
    src = make_source(tmp_path, vcs="none")
    task = make_task(tmp_path, vcs="none")
    env = clean_env(tmp_path)
    proc = mkway(task, env, "install", "--from", str(src), "--vcs", "none", "--profile", "conf/p.json")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    settings = json.loads((task / ".claude" / "settings.local.json").read_text(encoding="utf-8"))
    command = settings["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    assert command.endswith('--profile "${CLAUDE_PROJECT_DIR}/conf/p.json"')
    assert "drift: none" in _start_context(task, env, "--profile", str(task / "conf" / "p.json"))


def test_install_refuses_a_profile_outside_the_root(tmp_path):
    """E49 (content check F3): a `--profile` outside the root is refused before any write, with a clean message."""
    src = make_source(tmp_path, vcs="none")
    task = make_task(tmp_path, vcs="none")
    env = clean_env(tmp_path)
    outside = tmp_path / "outside" / "p.json"
    proc = mkway(task, env, "install", "--from", str(src), "--vcs", "none", "--profile", str(outside))
    assert proc.returncode == 1
    assert "outside the root" in proc.stderr and "Traceback" not in proc.stderr
    assert not outside.exists() and not outside.parent.exists()
    assert not (task / "mkway").exists() and not (task / ".claude").exists()


def _link_dir(link, target):
    """A directory symlink, else a Windows junction; skip when neither can be made here."""
    try:
        os.symlink(str(target), str(link), target_is_directory=True)
        return
    except (OSError, NotImplementedError):
        pass
    try:
        import _winapi
        _winapi.CreateJunction(str(target), str(link))
    except (ImportError, AttributeError, OSError):
        pytest.skip("neither a symlink nor a junction can be made here")


def test_install_refuses_links_out_of_the_root(tmp_path):
    """E50 (content check F4): a link or junction at <bundle.root> or at <bundle.root>/engine that leads outside
    the root stops the install before any write and before the re-install delete; nothing outside changes."""
    src = make_source(tmp_path, vcs="none")
    env = clean_env(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    task = make_task(tmp_path, vcs="none")
    _link_dir(task / "mkway", outside)
    proc = mkway(task, env, "install", "--from", str(src), "--vcs", "none")
    assert proc.returncode == 1
    assert "outside the root" in proc.stderr and "Traceback" not in proc.stderr
    assert list(outside.iterdir()) == []

    outside2 = tmp_path / "outside2"
    outside2.mkdir()
    (outside2 / "keep.txt").write_text("keep", encoding="utf-8")
    task2 = make_task(tmp_path, vcs="none", name="task2")
    write_profile(task2, make_profile())
    (task2 / "mkway" / "mkway.lock").write_text("{}", encoding="utf-8")
    _link_dir(task2 / "mkway" / "engine", outside2)
    proc = mkway(task2, env, "install", "--from", str(src), "--vcs", "none")
    assert proc.returncode == 1
    assert "outside the root" in proc.stderr and "Traceback" not in proc.stderr
    assert [p.name for p in outside2.iterdir()] == ["keep.txt"]


def test_check_with_a_missing_term_file_says_so(tmp_path):
    """E51 (content check F6): `check` with ENGINE_TERMS_FILE naming a missing file fails with a clean line, not a
    traceback."""
    src = make_light_source(tmp_path)
    task = make_task(tmp_path, vcs="none")
    env = clean_env(tmp_path)
    assert mkway(task, env, "install", "--from", str(src), "--vcs", "none").returncode == 0
    proc = mkway(task, dict(env, ENGINE_TERMS_FILE=str(tmp_path / "missing.txt")), "check")
    assert proc.returncode == 1
    assert "term scan: term list missing (ENGINE_TERMS_FILE)" in proc.stdout
    assert "tests: 1 passed" in proc.stdout  # MW-013: check collected exactly the one fixture test
    assert "Traceback" not in proc.stderr


def test_install_says_when_git_cannot_check_the_ignore(tmp_path):
    """E52 (content check F7): when the profile says git but git cannot check the ignore (not a git work tree),
    install says so and names the hand fix."""
    src = make_source(tmp_path, vcs="none")
    task = make_task(tmp_path, vcs="none")
    write_profile(task, make_profile(vcs="git"))
    env = clean_env(tmp_path, GIT_CEILING_DIRECTORIES=str(tmp_path))
    proc = mkway(task, env, "install", "--from", str(src))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "ignore: git could not check .claude/settings.local.json" in proc.stdout


def test_check_runs_the_term_scan_when_a_term_file_is_set(tmp_path):
    """E53: with ENGINE_TERMS_FILE set, `check` scans the copy's files and reports the counts (0 hits for a clean
    copy). Found by E51: this path raised before its fix."""
    terms = os.environ.get("ENGINE_TERMS_FILE")
    if not terms:
        pytest.fail(term_scan.MISSING_MESSAGE)
    src = make_light_source(tmp_path)
    task = make_task(tmp_path, vcs="none")
    env = clean_env(tmp_path)
    assert mkway(task, env, "install", "--from", str(src), "--vcs", "none").returncode == 0
    proc = mkway(task, dict(env, ENGINE_TERMS_FILE=terms), "check")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert re.search(r"term scan: \d+ entries, 0 hits, \d+ exceptions", proc.stdout)
    assert "tests: 1 passed" in proc.stdout  # MW-013: check collected exactly the one fixture test
