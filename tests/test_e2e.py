"""End to end on a synthetic task under the pytest temp folder (card MW-002, rows E39-E44), with vcs git and vcs
none, at one bundle depth (`mkway`). The engine source is built from this repository (marker `engine_repo`)."""
import json
import re
import shlex
import subprocess
import sys
import time

import pytest

from _engine import REPO, jsonl
from test_install import clean_env, make_source, make_task, mkway

pytestmark = pytest.mark.engine_repo

MACHINE = re.compile(r"[A-Za-z]:[\\/]|\\Users\\|/Users/|/home/")


def _install(tmp_path, vcs, engine_gates=True):
    src = make_source(tmp_path, vcs=vcs, fixture_gate=True, tag="v0.2.0" if vcs == "git" else None,
                      engine_gates=engine_gates)
    task = make_task(tmp_path, vcs=vcs)
    env = clean_env(tmp_path)
    args = ["install", "--from", str(src)] + (["--ref", "v0.2.0"] if vcs == "git" else ["--vcs", "none"])
    proc = mkway(task, env, *args)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return task, env


def _entries(task):
    data = json.loads((task / ".claude" / "settings.json").read_text(encoding="utf-8"))
    for event, groups in data["hooks"].items():
        for group in groups:
            for h in group["hooks"]:
                yield event, group.get("matcher"), h


def _run_command(task, env, command, payload, timeout):
    """Run a generated command as Claude Code would: ${CLAUDE_PROJECT_DIR} from the env, JSON on stdin, and the
    `CLAUDECODE` a session's hooks carry (close-fix 1: the suite no longer inherits it from the chat it runs in)."""
    expanded = command.replace("${CLAUDE_PROJECT_DIR}", task.as_posix())
    argv = shlex.split(expanded)
    assert argv[0] == "python"
    argv[0] = sys.executable
    run_env = dict(env, CLAUDE_PROJECT_DIR=str(task), CLAUDECODE="1")
    started = time.monotonic()
    proc = subprocess.run(argv, input=json.dumps(payload), capture_output=True, text=True, env=run_env,
                          timeout=timeout)
    return proc, time.monotonic() - started


START = {"session_id": "e2e", "hook_event_name": "SessionStart", "source": "startup"}
EDIT = {"session_id": "e2e", "hook_event_name": "PreToolUse", "tool_name": "Edit",
        "tool_input": {"file_path": "src/a.py"}}
READ = {"session_id": "e2e", "hook_event_name": "PreToolUse", "tool_name": "Read",
        "tool_input": {"file_path": "src/a.py"}}


@pytest.mark.parametrize("vcs", ["git", "none"])
def test_end_to_end(tmp_path, vcs):
    """E39: install; a SessionStart prints the start line; a PreToolUse with the always-refuse fixture gate is
    blocked and writes one refusal row; one changed byte in the copy gives a drift warning.
    Changed by MW-003: the source leaves out the engine's own `on` gates (they have their own end-to-end test,
    test_e2e_gates.py), so this stays the core's test with the fixture gate alone."""
    task, env = _install(tmp_path, vcs, engine_gates=False)
    commands = {(event, h["command"].split(" --group ")[1]): h for event, _m, h in _entries(task)}
    assert set(commands) == {("SessionStart", "start"), ("PreToolUse", "edit")}
    proc, _ = _run_command(task, env, commands[("SessionStart", "start")]["command"], START, 60)
    assert proc.returncode == 0, proc.stderr
    context = json.loads(proc.stdout)["hookSpecificOutput"]["additionalContext"]
    version = (REPO / "VERSION").read_text(encoding="utf-8").strip()  # MW-016: the copy's VERSION, then the ref
    assert (f"mkway v{version} (" if vcs == "git" else f"mkway v{version} (unversioned)") in context
    assert "drift: none" in context and "gates on: fixture_refuse" in context
    assert ("vcs: git" if vcs == "git" else "vcs: none, every git step is off") in context
    proc, _ = _run_command(task, env, commands[("PreToolUse", "edit")]["command"], EDIT, 60)
    out = json.loads(proc.stdout)["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny"
    rows = jsonl(task / "mkway" / "state" / "refusals.jsonl")
    assert [(r["gate"], r["reason_id"]) for r in rows] == [("fixture_refuse", "fixture-refuse")]
    tool = task / "mkway" / "engine" / "tools" / "term_scan.json"
    tool.write_bytes(tool.read_bytes() + b" ")  # one added byte
    proc, _ = _run_command(task, env, commands[("SessionStart", "start")]["command"], START, 60)
    context = json.loads(proc.stdout)["hookSpecificOutput"]["additionalContext"]
    (line,) = [x for x in context.splitlines() if x.startswith("drift:")]
    assert "copy" in line and "mkway install" in line


@pytest.mark.parametrize("vcs", ["git", "none"])
def test_generated_commands_cannot_break_a_session(tmp_path, vcs):
    """E40: each generated command, run in a subprocess on a sample SessionStart and a sample PreToolUse input
    (a tool the fixture gate does not match), exits 0, allows, and stays within its timeout."""
    task, env = _install(tmp_path, vcs)
    entries = list(_entries(task))
    assert entries
    for event, _matcher, h in entries:
        for payload in (START, READ):
            proc, took = _run_command(task, env, h["command"], payload, h["timeout"])
            assert proc.returncode == 0, (h["command"], proc.stderr)
            assert took < h["timeout"]
            assert "deny" not in proc.stdout and '"block"' not in proc.stdout, proc.stdout


@pytest.mark.parametrize("vcs", ["git", "none"])
def test_generated_files_hold_no_machine_path(tmp_path, vcs):
    """E41: the lock, the starter profile and the generated entries hold no drive letter, no \\Users\\ and no
    absolute path."""
    task, _env = _install(tmp_path, vcs)
    texts = [(task / "mkway" / "mkway.lock").read_text(encoding="utf-8"),
             (task / "mkway" / "profile.json").read_text(encoding="utf-8"),
             json.dumps([h for _e, _m, h in _entries(task)])]
    for text in texts:
        assert not MACHINE.search(text), text
        assert str(tmp_path) not in text and tmp_path.as_posix() not in text
    for _e, _m, h in _entries(task):
        path = next(w for w in shlex.split(h["command"]) if "CLAUDE_PROJECT_DIR" in w)  # after `-I -X utf8` (R111 a)
        assert path.startswith("${CLAUDE_PROJECT_DIR}/"), path
    for value in json.loads(texts[1]).values():
        for v in (value.values() if isinstance(value, dict) else [value]):
            assert not (isinstance(v, str) and v.startswith(("/", "\\"))), v


def test_settings_local_is_git_ignored(tmp_path):
    """E42 (changed by MW-027): with vcs git, install writes no `.claude/settings.local.json` (the owner's own
    per-machine file); the hook entries are in `.claude/settings.json`, which git does not ignore."""
    task, _env = _install(tmp_path, "git")
    assert not (task / ".claude" / "settings.local.json").exists()
    assert (task / ".claude" / "settings.json").is_file()
    proc = subprocess.run(["git", "check-ignore", "-q", ".claude/settings.json"], cwd=str(task))
    assert proc.returncode == 1


def test_root_suite_does_not_collect_mkway(tmp_path):
    """E43: the engine's pytest config (`testpaths = tests`) does not collect tests under `mkway/` (a later
    self-install puts a copy there)."""
    root = tmp_path / "selfroot"
    (root / "tests").mkdir(parents=True)
    (root / "mkway" / "engine" / "tests").mkdir(parents=True)
    (root / "pytest.ini").write_bytes((REPO / "pytest.ini").read_bytes())
    (root / "tests" / "test_ok.py").write_text("def test_ok():\n    pass\n", encoding="utf-8")
    (root / "mkway" / "engine" / "tests" / "test_copy.py").write_text("def test_copy():\n    pass\n",
                                                                     encoding="utf-8")
    proc = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "--basetemp", str(tmp_path / "bt")],
                          cwd=str(root), capture_output=True, text=True, timeout=120)
    assert "tests/test_ok.py::test_ok" in proc.stdout
    assert "test_copy" not in proc.stdout


def test_engine_repo_marker_selects_the_repository_only_tests(tmp_path):
    """E44: the marker `engine_repo` is declared and carried by the register, repository-scan, install and
    end-to-end tests, so `-m "not engine_repo"` (what `mkway check` runs in a copy) leaves them out."""
    assert "engine_repo:" in (REPO / "pytest.ini").read_text(encoding="utf-8")
    # the engine repository's own run never filters the marked tests out (blind check F3)
    assert "-m" not in (REPO / "pytest.ini").read_text(encoding="utf-8").split("addopts", 1)[1].splitlines()[0]
    proc = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-m", "not engine_repo",
                           "-p", "no:cacheprovider", "--basetemp", str(tmp_path / "bt")], cwd=str(REPO),
                          capture_output=True, text=True, timeout=120)
    collected = proc.stdout
    for module in ("test_register.py", "test_repo_scan.py", "test_install.py", "test_e2e.py",
                   "test_term_scan.py::test_scan_covers_tracked_files_only"):
        assert module not in collected, module
    assert "test_dispatch.py" in collected and "test_cards.py" in collected
