"""The start line and the drift check (card MW-002, rows E34-E36, E38). Synthetic task roots only."""
import json
import sys
import time

import pytest

from _engine import FIXTURES, entry, fake_program, make_profile, write_profile
import dispatch
import install
import startline

FIXTURE = entry("fixture_refuse", "fixture_gates:always_refuse", matcher="Edit|Write")
NO_IDS = entry("n1", "fixture_gates:always_refuse", reason_ids=None)
MANIFEST = [FIXTURE, NO_IDS]


@pytest.fixture
def task(tmp_path):
    """A task root laid out as an install leaves it: profile, a small copy, its lock, generated hook entries."""
    root = tmp_path / "task"
    profile = make_profile()
    write_profile(root, profile)
    copy = root / "mkway" / "engine"
    (copy / "engine").mkdir(parents=True)
    (copy / "engine" / "a.py").write_text("A = 1\n", encoding="utf-8")
    (copy / "VERSION").write_text("9.9.9\n", encoding="utf-8")  # MW-016: the start block reads the copy's VERSION
    (root / "mkway" / "mkway.lock").write_text(json.dumps(
        {"version": "v9", "source_sha": None, "date": "2026-11-09", "hash": install.copy_hash(copy)}), encoding="utf-8")
    install.write_settings(root / ".claude" / "settings.local.json", install.generate_entries(profile, MANIFEST),
                           "mkway")
    (root / "mkway" / "locks").mkdir()
    for name in ("one.json", "two.json"):
        (root / "mkway" / "locks" / name).write_text("{}", encoding="utf-8")
    state = root / "mkway" / "state"
    state.mkdir()
    (state / "machine.json").write_text(json.dumps({"python": "python"}), encoding="utf-8")  # as install writes it
    rows =[{"reason_id": "gate-error"}, {"reason_id": "gate-error"}, {"reason_id": "dispatcher-error"},
            {"reason_id": "fixture-refuse"}]
    (state / "refusals.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return root


def _render(root, env=None, profile=None, errors=()):
    profile = profile if profile is not None else json.loads((root / "mkway" / "profile.json").read_text("utf-8"))
    return startline.render(root, root / "mkway" / "profile.json", profile, list(errors), MANIFEST, env or {})


def test_start_line_block(task):
    """E34: one block: the version and the profile path; the gates on and the gates not loaded; the vcs line; the
    drift result; the count of files in locks/; the gate-error and dispatcher-error counts."""
    block = _render(task)
    assert "mkway v9.9.9 (v9)" in block and "profile: mkway/profile.json" in block
    assert "gates on: fixture_refuse" in block
    assert "not loaded: n1 (no reason_ids)" in block
    assert "vcs: none, every git step is off" in block
    assert "drift: none" in block
    assert "locks: 2 files in mkway/locks" in block
    assert "errors logged: gate-error 2, dispatcher-error 1" in block


def _drift_lines(block):
    return [line for line in block.splitlines() if line.startswith("drift:")]


def test_drift_three_comparisons_one_warning(task):
    """E35: the drift check compares (1) the copy's hash with the lock, (2) the live owned entries with a fresh
    generation as whole entries (event, matcher, command, timeout), (3) the profile with the schema. Any
    difference gives one warning line that names the fix, `mkway install`."""
    profile = json.loads((task / "mkway" / "profile.json").read_text("utf-8"))
    assert startline.drift(task, profile, [], MANIFEST) == []
    a = task / "mkway" / "engine" / "engine" / "a.py"
    a.write_bytes(a.read_bytes() + b"#")
    assert [i.split(":")[0] for i in startline.drift(task, profile, [], MANIFEST)] == ["copy"]
    a.write_text("A = 1\n", encoding="utf-8")
    settings = task / ".claude" / "settings.local.json"
    data = json.loads(settings.read_text("utf-8"))
    data["hooks"]["PreToolUse"][0]["hooks"][0]["timeout"] = 99
    settings.write_text(json.dumps(data), encoding="utf-8")
    assert [i.split(":")[0] for i in startline.drift(task, profile, [], MANIFEST)] == ["hook entries"]
    data["hooks"]["PreToolUse"][0]["hooks"][0]["timeout"] = 10
    data["hooks"]["PreToolUse"][0]["matcher"] = "Edit"
    settings.write_text(json.dumps(data), encoding="utf-8")
    assert [i.split(":")[0] for i in startline.drift(task, profile, [], MANIFEST)] == ["hook entries"]
    errors = ["bundle.root: not a relative path inside the repository"]
    items = startline.drift(task, profile, errors, MANIFEST)
    assert [i.split(":")[0] for i in items] == ["hook entries", "profile"]
    lines = _drift_lines(_render(task, errors=errors))
    assert len(lines) == 1 and "mkway install" in lines[0] and "bundle.root" in lines[0]


def test_user_layer_information_only(task, tmp_path):
    """E36: the user layer is listed for information only; a missing or unreadable file is said so, and nothing
    fails."""
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    env = {"HOME": str(home), "USERPROFILE": str(home)}
    assert "user layer: ~/.claude/settings.json missing (information only)" in _render(task, env)
    (home / ".claude" / "settings.json").write_text("{broken", encoding="utf-8")
    assert "user layer: ~/.claude/settings.json unreadable (information only)" in _render(task, env)
    hooks = {"Stop": [{"hooks": [{"type": "command", "command": "a"}, {"type": "command", "command": "b"}]}],
             "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "c"}]}]}
    (home / ".claude" / "settings.json").write_text(json.dumps({"hooks": hooks}), encoding="utf-8")
    assert "user layer: ~/.claude/settings.json, 3 hook commands (information only)" in _render(task, env)
    assert "drift: none" in _render(task, env)


def test_start_line_names_invalid_profile(task):
    """E38 (C17 b): at SessionStart the start line reaches the model as additionalContext and names a broken
    profile's keys (`profile-invalid`), before the first tool call."""
    broken = make_profile()
    broken["bundle"]["root"] = "../outside"
    write_profile(task, broken)
    res = dispatch.run("SessionStart", "start", json.dumps({"session_id": "s1", "hook_event_name": "SessionStart"}),
                       env={"CLAUDE_PROJECT_DIR": str(task)}, manifest=MANIFEST, gate_paths=[FIXTURES])
    assert res.exit_code == 0
    context = json.loads(res.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "profile-invalid" in context and "bundle.root" in context
    assert "mkway" in context.splitlines()[0]


def test_drift_compares_whole_commands(task):
    """E46 (content check F1): drift compares whole commands. An owned entry rewritten as `exit 0 || <command>`
    (the hook never runs) is drift. The per-machine interpreter is read from <state.dir>/machine.json, so an entry
    made with `--python` is no drift once that file says so."""
    profile = json.loads((task / "mkway" / "profile.json").read_text("utf-8"))
    settings = task / ".claude" / "settings.local.json"
    data = json.loads(settings.read_text("utf-8"))
    handler = data["hooks"]["SessionStart"][0]["hooks"][0]
    handler["command"] = "exit 0 || " + handler["command"]
    settings.write_text(json.dumps(data), encoding="utf-8")
    assert startline.drift(task, profile, [], MANIFEST) == [  # M2: the machine check sees it too
        "hook entries: 1 missing or changed, 1 not generated",
        "drift-machine: machine.json and the hook entries name different interpreters"]
    quoted ='"' + sys.executable + '"'  # changed by fix check 2 (L4, M2): a real interpreter, not `py -3`
    install.write_settings(settings, install.generate_entries(profile, MANIFEST, python=quoted), "mkway")
    assert [i.split(":")[0] for i in startline.drift(task, profile, [], MANIFEST)] == ["hook entries",
                                                                                       "drift-machine"]
    (task / "mkway" / "state" / "machine.json").write_text(json.dumps({"python": quoted}), encoding="utf-8")
    assert startline.drift(task, profile, [], MANIFEST) == []


def test_drift_machine_checks_the_interpreter(task, tmp_path):
    """E66 (fix check 2 M2, retro-chief10): at start, <state.dir>/machine.json must name an existing executable that
    reports Python 3.9 or later, and must equal the interpreter inside the owned entries. Any difference is a
    `drift-machine` item, and the drift line names `mkway install`. (Changed by blind rounds 3-4 and 5.)
    Catches: a comparison with the first owned entry only; a reader that catches only `JSONDecodeError` (a folder
    or bytes that are not UTF-8 raise, and the start line is lost); a reader that falls back to the profile on an
    empty, blank or non-text value; a start-time rule looser than install's (the `py` argument forms, a flag after
    a program that is not `py`, a missing path); a version compare that refuses the (3, 9) boundary."""
    profile = json.loads((task / "mkway" / "profile.json").read_text("utf-8"))
    settings = task / ".claude" / "settings.local.json"
    machine = task / "mkway" / "state" / "machine.json"

    def put(value, entries_python):
        machine.write_text(json.dumps({"python": value}), encoding="utf-8")
        install.write_settings(settings, install.generate_entries(profile, MANIFEST, python=entries_python), "mkway")

    def machine_items():
        return [i for i in startline.drift(task, profile, [], MANIFEST) if i.startswith("drift-machine")]

    quoted = '"' + sys.executable + '"'
    put(quoted, quoted)
    assert startline.drift(task, profile, [], MANIFEST) == []
    # fix check 3 (blind): one entry that is not the first differs
    data = json.loads(settings.read_text("utf-8"))
    edit = data["hooks"]["PreToolUse"][0]["hooks"][0]
    edit["command"] = edit["command"].replace(quoted, "python", 1)
    settings.write_text(json.dumps(data), encoding="utf-8")
    assert machine_items(), "one non-first entry differs"
    put(quoted, quoted)
    for bad in ("{broken", "{}", json.dumps({"python": ""}), json.dumps({"python": "   "})):
        machine.write_text(bad, encoding="utf-8")
        assert machine_items(), bad
    missing = '"' + str(tmp_path / "none" / "python.exe") + '"'
    for value in (missing, quoted + " -3"):
        put(value, value)
        assert machine_items(), value
    ok39 = '"' + str(fake_program(tmp_path / "bin", "py39", prints="(3, 9)")) + '"'
    put(ok39, ok39)
    assert not machine_items()
    put("exit 0 || python", "exit 0 || python")  # both files edited the same way
    assert machine_items()
    other = '"' + str(fake_program(tmp_path / "bin", "notpython", prints="hello")) + '"'
    put(other, other)
    assert machine_items()
    old = '"' + str(fake_program(tmp_path / "bin", "oldpython", prints="(3, 8)")) + '"'
    put(old, old)
    assert machine_items()
    put(quoted, "python")  # machine.json and the entries differ
    assert machine_items()
    put(quoted, quoted)
    # blind round 5: unreadable machine.json (not UTF-8, a folder), the `py` argument rule at start, a non-string
    machine.write_bytes(b'{"python": "x\xe9"}')
    assert machine_items(), "not UTF-8"
    machine.unlink()
    machine.mkdir()
    assert machine_items(), "a folder"
    (line,) = _drift_lines(_render(task))
    assert "drift-machine" in line and line.endswith("Fix: mkway install")
    machine.rmdir()
    for value in ("py -c 1", "py -3 -3"):
        put(value, value)
        assert machine_items(), value
    put(quoted, quoted)
    machine.write_text(json.dumps({"python": 5}), encoding="utf-8")
    assert machine_items(), "a value that is not text"
    machine.unlink()
    assert machine_items()
    (line,) = _drift_lines(_render(task))
    assert "drift-machine" in line and line.endswith("Fix: mkway install")


def test_start_probe_runs_last_and_has_its_own_timeout(task, tmp_path, monkeypatch):
    """E71 (fix check 3 L5; changed by fix check 4 F6, F7 and blind round 5): the start line compares machine.json
    with the entries first, so a program named only in machine.json is never run, also when there is no owned entry
    at all; the interpreter check has its own timeout (`MACHINE_CHECK_SECONDS`, 5 s), shorter than the start entry's,
    and on timeout gives a visible `drift-machine: interpreter check timed out` item. The start line is never lost.
    The test sets the timeout to 1 s, so the suite does not wait 5 s twice (F7).
    Catches: a probe that runs before the comparison (the toucher runs); a comparison over an empty entry list that
    lets the probe run (`any([])` is False, F6); a probe that ignores `MACHINE_CHECK_SECONDS` (a hard-coded timeout
    takes longer than the time limit); a probe timeout not shorter than the start entry's; a timeout that gives no
    item or loses the drift line."""
    profile = json.loads((task / "mkway" / "profile.json").read_text("utf-8"))
    settings = task / ".claude" / "settings.local.json"
    machine = task / "mkway" / "state" / "machine.json"
    quoted = '"' + sys.executable + '"'
    ran = tmp_path / "ran.txt"
    toucher = '"' + str(fake_program(tmp_path / "bin", "toucher", touches=ran)) + '"'
    install.write_settings(settings, install.generate_entries(profile, MANIFEST, python=quoted), "mkway")
    machine.write_text(json.dumps({"python": toucher}), encoding="utf-8")
    items = startline.drift(task, profile, [], MANIFEST)
    assert "drift-machine: machine.json and the hook entries name different interpreters" in items
    assert not ran.exists(), "the program named only in machine.json ran"
    install.write_settings(settings, [], "mkway")  # F6: no owned entry at all
    assert install.live_entries(settings, "mkway") == []
    items = startline.drift(task, profile, [], MANIFEST)
    assert "drift-machine: machine.json and the hook entries name different interpreters" in items
    assert not ran.exists(), "with no owned entry the program named only in machine.json ran"
    assert startline.MACHINE_CHECK_SECONDS == 5
    start = [e for e in install.generate_entries(profile, MANIFEST) if e["event"] == "SessionStart"]
    assert startline.MACHINE_CHECK_SECONDS < start[0]["timeout"]
    monkeypatch.setattr(startline, "MACHINE_CHECK_SECONDS", 1)
    sleeper = '"' + str(fake_program(tmp_path / "bin", "sleeper", sleeps=30)) + '"'
    install.write_settings(settings, install.generate_entries(profile, MANIFEST, python=sleeper), "mkway")
    machine.write_text(json.dumps({"python": sleeper}), encoding="utf-8")
    started = time.monotonic()
    items = startline.drift(task, profile, [], MANIFEST)
    assert time.monotonic() - started < 4  # the constant is really used
    assert "drift-machine: interpreter check timed out" in items
    (line,) = _drift_lines(_render(task))
    assert "interpreter check timed out" in line and line.endswith("Fix: mkway install")


def test_probe_stops_an_orphaned_child(tmp_path):
    """E73 (fix check 4 F5): when the interpreter probe times out, every process it started is stopped, a grandchild
    whose parent already exited included, and the stop is quick: the probe's timeout plus a few seconds, so the worst
    case (5 s probe, 4 s kill, 2 s drain) stays under the start entry's 15 s.
    Catches: a stop that reaches only the direct child (`taskkill /T` or `proc.kill()` on a parent that already
    exited leaves the orphan running, and it writes its file); a stop that waits on a pipe the orphan still holds
    (the time limit fails)."""
    survived = tmp_path / "survived.txt"
    script = tmp_path / "orphan.py"
    script.write_text(f"import time\ntime.sleep(3)\nopen({str(survived)!r}, 'w').close()\n", encoding="utf-8")
    spawner = '"' + str(fake_program(tmp_path / "bin", "spawner", spawns=script)) + '"'
    started = time.monotonic()
    assert install.interpreter_problem(spawner, timeout=1) == "timeout"
    assert time.monotonic() - started < 4
    time.sleep(3.5)
    assert not survived.exists(), "the orphaned grandchild survived the probe's stop"


def test_drift_compares_on_failure(task):
    """E56 (R13c point 1): `onFailure` is part of the whole entry: an `edit` entry without its `"onFailure":
    "block"` is drift."""
    profile = json.loads((task / "mkway" / "profile.json").read_text("utf-8"))
    settings = task / ".claude" / "settings.local.json"
    data = json.loads(settings.read_text("utf-8"))
    (edit,) = data["hooks"]["PreToolUse"]
    assert edit["hooks"][0]["onFailure"] == "block"
    del edit["hooks"][0]["onFailure"]
    settings.write_text(json.dumps(data), encoding="utf-8")
    assert startline.drift(task, profile, [], MANIFEST) == ["hook entries: 1 missing or changed, 1 not generated"]
