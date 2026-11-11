"""The dispatcher (card MW-002, rows E5-E16, E21, E23). Synthetic task roots under the pytest temp folder only."""
import datetime
import json
import os
import shutil
import subprocess
import sys

import pytest

from _engine import ENGINE, FIXTURES, REPO, entry, jsonl, make_profile, write_profile
import dispatch

NOT_A_BREACH = "not a rule breach"


@pytest.fixture
def task(tmp_path):
    root = tmp_path / "task"
    root.mkdir()
    write_profile(root, make_profile())
    return root


def _payload(event="PreToolUse", tool="Edit", tool_input=None, session="s1"):
    p = {"session_id": session, "hook_event_name": event, "cwd": "."}
    if event in ("PreToolUse", "PostToolUse"):
        p["tool_name"] = tool
        p["tool_input"] = {"file_path": "src/a.py"} if tool_input is None else tool_input
    return p


def run(root, event, group, entries, payload=None, gates=None, stdin=None, engine_dir=ENGINE, manifest="given"):
    if gates is not None:
        write_profile(root, make_profile(gates))
    text = stdin if stdin is not None else json.dumps(payload or _payload(event))
    # changed by MW-003 (R23): a hook runs inside a session, so its env carries the session signal; E30 covers its
    # absence (the start line's `session-signal-missing` warn row)
    return dispatch.run(event, group, text, env={"CLAUDE_PROJECT_DIR": str(root), "CLAUDECODE": "1"},
                        engine_dir=engine_dir,
                        manifest=entries if manifest == "given" else None, gate_paths=[FIXTURES])


def refusals(root):
    return jsonl(root / "mkway" / "state" / "refusals.jsonl")


REFUSE = entry("r1", "fixture_gates:always_refuse")
WARN = entry("w1", "fixture_gates:always_warn", reason_ids=["fixture-warn"])


def test_refuse_blocks_pretooluse_and_ends_the_run(task):
    """E5: a refuse blocks the PreToolUse call with the message (documented deny output, exit 0), writes one row, and
    ends the run: the gate after it does not run."""
    res = run(task, "PreToolUse", "edit", [REFUSE, WARN])
    assert res.exit_code == 0
    out = json.loads(res.stdout)["hookSpecificOutput"]
    assert out["hookEventName"] == "PreToolUse"
    assert out["permissionDecision"] == "deny"
    assert "fixture gate: always refuses" in out["permissionDecisionReason"]
    assert "additionalContext" not in out
    rows = refusals(task)
    assert [(r["gate"], r["reason_id"], r["kind"]) for r in rows] == [("r1", "fixture-refuse", "refuse")]


def test_warn_reaches_context_and_blocks_nothing(task):
    """E6: a warn reaches the model as additionalContext, sets no permission decision, and writes one row."""
    res = run(task, "PreToolUse", "edit", [WARN])
    assert res.exit_code == 0
    out = json.loads(res.stdout)["hookSpecificOutput"]
    assert out["hookEventName"] == "PreToolUse"
    assert "fixture gate: always warns" in out["additionalContext"]
    assert "permissionDecision" not in out
    assert [(r["gate"], r["reason_id"], r["kind"]) for r in refusals(task)] == [("w1", "fixture-warn", "warn")]


def test_gate_off_in_profile_or_unmatched_tool_is_skipped(task):
    """E7: a gate the profile turns off, a gate off by default, and a gate whose own matcher does not match the tool
    name do not run; the same gate runs when its matcher matches."""
    res = run(task, "PreToolUse", "edit", [REFUSE], gates={"r1": {"on": False}})
    assert (res.exit_code, res.stdout) == (0, "")
    off_by_default = entry("r2", "fixture_gates:always_refuse", default_on=False)
    res = run(task, "PreToolUse", "edit", [off_by_default], gates={})
    assert (res.exit_code, res.stdout) == (0, "")
    shell_only = entry("r3", "fixture_gates:always_refuse", matcher="Bash|PowerShell")
    res = run(task, "PreToolUse", "edit", [shell_only])
    assert (res.exit_code, res.stdout) == (0, "")
    assert refusals(task) == []
    res = run(task, "PreToolUse", "edit", [shell_only], payload=_payload(tool="Bash", tool_input={"command": "ls"}))
    assert json.loads(res.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_stop_refuse_blocks_the_stop(task):
    """E8: at Stop a refuse writes the documented block (`decision: block` with the reason)."""
    stop = entry("s1", "fixture_gates:always_refuse", event="Stop", group="stop")
    res = run(task, "Stop", "stop", [stop])
    assert res.exit_code == 0
    out = json.loads(res.stdout)
    assert out["decision"] == "block"
    assert "fixture gate: always refuses" in out["reason"]


def test_gate_error_applies_on_failure(task):
    """E9: a gate that raises: onFailure block -> refuse `gate-error`, the message names the gate and the exception
    class and says it is not a rule breach; any other onFailure -> allow. Both are logged with the exception class.
    (Changed by R13c: a gate module that cannot be imported is a dispatcher failure, E57, no longer a gate error.)"""
    boom = entry("b1", "fixture_gates:raises", on_failure="block")
    res = run(task, "PreToolUse", "edit", [boom])
    reason = json.loads(res.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
    assert "b1" in reason and "RuntimeError" in reason and NOT_A_BREACH in reason
    soft = entry("b2", "fixture_gates:raises", on_failure="none")
    res = run(task, "PreToolUse", "edit", [soft])
    assert (res.exit_code, res.stdout) == (0, "")
    rows = refusals(task)
    assert [(r["gate"], r["reason_id"], r["exception"], r["applied"]) for r in rows] == [
        ("b1", "gate-error", "RuntimeError", "refuse"),
        ("b2", "gate-error", "RuntimeError", "allow"),
    ]
    assert all(r["verdict"] is None for r in rows)


def _one_stderr_line(res):
    lines = [line for line in res.stderr.splitlines() if line.strip()]
    assert len(lines) == 1, res.stderr
    return lines[0]


def _plant_crashes(tmp_path, event, group):
    """Run one dispatcher call per planted crash; return {case: (result, refusal rows of its root)}."""
    refuse = entry("r1", "fixture_gates:always_refuse", event=event, group=group)
    missing = entry("m1", "no_such_module:gate", event=event, group=group, on_failure="none")
    payload = _payload(event, tool="Bash", tool_input={"command": "ls"}) if group == "shell" else _payload(event)
    out = {}
    root = tmp_path / f"{group}-stdin"
    write_profile(root, make_profile())
    out["stdin"] = (run(root, event, group, [refuse], stdin="{not json"), root)
    root = tmp_path / f"{group}-manifest"
    write_profile(root, make_profile())
    bad_engine = tmp_path / f"{group}-bad_engine"
    bad_engine.mkdir()
    (bad_engine / "manifest.json").write_text("{broken", encoding="utf-8")
    out["manifest"] = (run(root, event, group, None, payload=payload, engine_dir=bad_engine, manifest=None), root)
    root = tmp_path / f"{group}-module"
    write_profile(root, make_profile())
    out["module"] = (run(root, event, group, [missing], payload=payload), root)
    root = tmp_path / f"{group}-profile"
    (root / "mkway" / "profile.json").mkdir(parents=True)  # the profile path is a folder: the load raises
    out["profile"] = (run(root, event, group, [refuse], payload=payload), root)
    root = tmp_path / f"{group}-log"
    write_profile(root, make_profile())
    (root / "mkway" / "state").write_text("a file where the state folder should be", encoding="utf-8")
    out["log"] = (run(root, event, group, [refuse], payload=payload), root)
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    root = tmp_path / f"{group}-log-refusals"  # only the refusal row cannot be written
    write_profile(root, make_profile())
    (root / "mkway" / "state" / "refusals.jsonl").mkdir(parents=True)
    out["log-refusals"] = (run(root, event, group, [refuse], payload=payload), root)
    root = tmp_path / f"{group}-log-timing"  # only the timing row cannot be written
    write_profile(root, make_profile())
    (root / "mkway" / "state" / f"timing-{today}.jsonl").mkdir(parents=True)
    out["log-timing"] = (run(root, event, group, [refuse], payload=payload), root)
    root = tmp_path / f"{group}-log-alone"  # log broken, no gate refuses
    write_profile(root, make_profile())
    (root / "mkway" / "state").write_text("a file where the state folder should be", encoding="utf-8")
    out["log-alone"] = (run(root, event, group, [], payload=payload), root)
    warn = entry("w1", "fixture_gates:always_warn", event=event, group=group, reason_ids=["fixture-warn"])
    root = tmp_path / f"{group}-log-warn"  # a warn whose row cannot be written: it must not block (fix check 3)
    write_profile(root, make_profile())
    (root / "mkway" / "state" / "refusals.jsonl").mkdir(parents=True)
    out["log-warn"] = (run(root, event, group, [warn], payload=payload), root)
    root = tmp_path / f"{group}-log-warn-then-refuse"  # the warn row fails first; the later refusal still stands
    write_profile(root, make_profile())
    (root / "mkway" / "state" / "refusals.jsonl").mkdir(parents=True)
    out["log-warn-then-refuse"] = (run(root, event, group, [warn, refuse], payload=payload), root)
    return {case: (res, refusals(root)) for case, (res, root) in out.items()}


CRASH_CLASSES = {"stdin": ("JSONDecodeError",), "manifest": ("JSONDecodeError",),
                 "module": ("ModuleNotFoundError",), "profile": ("IsADirectoryError", "PermissionError")}


NON_BLOCKING = [("SessionStart", "start"), ("UserPromptSubmit", "prompt"), ("PostToolUse", "post"), ("Stop", "stop")]


def _refusal_stands(event, out):
    """The fixture refusal is in the output the event uses for it, in the documented form (fix checks N1, blind)."""
    if event in ("SessionStart", "PreToolUse"):
        hso = out["hookSpecificOutput"]
        if hso.get("hookEventName") != event:
            return False
        if event == "SessionStart":
            return "fixture gate: always refuses" in hso["additionalContext"]
        return (hso.get("permissionDecision") == "deny"
                and "fixture gate: always refuses" in hso.get("permissionDecisionReason", ""))
    return out.get("decision") == "block" and "fixture gate: always refuses" in out["reason"]


def _nothing_blocked(out):
    hso = out.get("hookSpecificOutput", {})
    return "permissionDecision" not in hso and "decision" not in out


def _log_case_holds(event, case, out, rows):
    """A failed log write never blocks and never unblocks (fix checks N1, blind, 3)."""
    if case in ("log-alone", "log-warn"):
        assert _nothing_blocked(out), case
        if case == "log-warn":
            assert "fixture gate: always warns" in out["hookSpecificOutput"]["additionalContext"], case
    else:
        assert _refusal_stands(event, out), case
    if case == "log-timing":  # only the broken row is lost
        assert [r["reason_id"] for r in rows] == ["fixture-refuse"], case


@pytest.mark.parametrize("event,group", NON_BLOCKING)
def test_outer_handler_catches_each_crash(tmp_path, event, group):
    """E10 (changed by R13c: the exit-0 rule now holds in the groups start, post, prompt and stop; E57 covers edit
    and shell. Changed by the fix check: run in all four groups (N7); in the log case the refusal the gate made
    stands (N1)): a crash in the dispatcher itself (bad stdin, a broken manifest, a gate module that cannot be
    imported), in the profile load, or in the log write: exit 0, one stderr line, a `systemMessage`, and a
    `dispatcher-error` row (verdict null, the exception class); when even the row cannot be written, the stderr line
    says so."""
    for case, (res, rows) in _plant_crashes(tmp_path, event, group).items():
        assert res.exit_code == 0, case
        line = _one_stderr_line(res)
        assert "dispatcher-error" in line, case
        out = json.loads(res.stdout)
        assert out.get("systemMessage"), case
        if case.startswith("log"):
            assert "could not be written" in line, case
            _log_case_holds(event, case, out, rows)
            continue
        assert [(r["reason_id"], r["verdict"]) for r in rows] == [("dispatcher-error", None)], case
        assert rows[0]["exception"] in CRASH_CLASSES[case], case


@pytest.mark.parametrize("event,group", [("PreToolUse", "edit"), ("PreToolUse", "shell")])
def test_dispatcher_failure_blocks_in_edit_and_shell(tmp_path, event, group):
    """E57 (R13c point 3): in `edit` and `shell` a failure the dispatcher cannot evaluate past (bad stdin, a broken
    manifest, a gate module that cannot be imported, a profile that cannot be read) exits 2 with `dispatcher-error`
    and its reason on stderr, so the tool call is blocked, and writes the row. A failed log write alone never blocks
    and never unblocks: exit 0, stderr and a `systemMessage`, and the refusal the gate made stands (changed by the
    fix check N1: it asserted the outcome where the deny was dropped)."""
    for case, (res, rows) in _plant_crashes(tmp_path, event, group).items():
        line = _one_stderr_line(res)
        assert "dispatcher-error" in line, case
        if case.startswith("log"):
            assert res.exit_code == 0, case
            out = json.loads(res.stdout)
            assert "could not be written" in line and out.get("systemMessage"), case
            _log_case_holds(event, case, out, rows)
            continue
        assert res.exit_code == 2, case
        assert "blocked" in line and NOT_A_BREACH in line, case
        assert [(r["reason_id"], r["verdict"]) for r in rows] == [("dispatcher-error", None)], case
        assert rows[0]["exception"] in CRASH_CLASSES[case], case


def test_broken_profile_stays_a_warn_in_edit(task):
    """E58 (R13c point 3): a broken profile is not a dispatcher failure: exit 0, no `dispatcher-error`. Changed by
    MW-003 (R37 H1, fail closed): in `edit` it is the `profile-invalid` refusal, never a fallback to defaults."""
    broken = make_profile()
    broken["vcs"] = "svn"
    write_profile(task, broken)
    res = run(task, "PreToolUse", "edit", [REFUSE])
    assert res.exit_code == 0 and "dispatcher-error" not in res.stderr
    out = json.loads(res.stdout)["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny" and "profile-invalid" in out["permissionDecisionReason"]


def test_non_utf8_profile_is_a_warn(task):
    """E60 (fix check N3): a profile holding a byte that is not UTF-8 (an ANSI save) is `profile-invalid`, and the
    message says the file is not UTF-8. Changed by MW-003 (R37 H1): in `edit` it is a refusal (exit 0, deny)."""
    raw = json.dumps(make_profile()).encode("utf-8").replace(b"{", b'{"note": "x\xe9x", ', 1)
    (task / "mkway" / "profile.json").write_bytes(raw)
    res = run(task, "PreToolUse", "edit", [REFUSE])
    assert res.exit_code == 0, res.stderr
    out = json.loads(res.stdout)["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny"
    assert "profile-invalid" in out["permissionDecisionReason"] and "not UTF-8" in out["permissionDecisionReason"]


def test_gate_sys_exit_is_a_gate_error(task):
    """E61 (fix check N5): a gate that calls `sys.exit` is caught: a `gate-error` with the class `SystemExit`, and
    its onFailure applies as for any gate error (E9): block -> refuse in `edit`; otherwise allow. Both logged."""
    hard = entry("x1", "fixture_gates:exits", on_failure="block")
    res = run(task, "PreToolUse", "edit", [hard])
    assert res.exit_code == 0
    reason = json.loads(res.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
    assert "x1" in reason and "SystemExit" in reason and NOT_A_BREACH in reason
    soft = entry("x2", "fixture_gates:exits", event="UserPromptSubmit", group="prompt", on_failure="none")
    res = run(task, "UserPromptSubmit", "prompt", [soft])
    assert (res.exit_code, res.stdout) == (0, "")
    assert [(r["gate"], r["reason_id"], r["exception"], r["applied"]) for r in refusals(task)] == [
        ("x1", "gate-error", "SystemExit", "refuse"),
        ("x2", "gate-error", "SystemExit", "allow"),
    ]


def test_failed_once_write_counts_as_first_time(task):
    """E64 (fix check 2 L1): a once-store write that fails counts as «first time», for a gate's `ctx.once` and for
    the dispatcher's own profile once-store: the refusal (or the warn) stands, and a `systemMessage` says the row is
    missing. Never a gate-error, never a lost refusal. (Changed by fix check 3, blind: only the once folder is
    broken, the logs stay writable; run twice. Changed by blind round 5: control runs with a healthy once folder
    give no `systemMessage`, so the message seen later can only come from the failed once-store write.)
    Catches: a failed once write that returns False (the refusal or the warn is lost); a failed once write turned
    into a gate-error; a failed once write swallowed with no message while a general `systemMessage` is added to
    every refusal or warn (the control runs fail)."""
    state = task / "mkway" / "state"
    healthy = run(task, "PreToolUse", "edit", [entry("o3", "fixture_gates:refuse_once", on_failure="none")])
    assert json.loads(healthy.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "systemMessage" not in json.loads(healthy.stdout)  # control: no message when the once write works
    good = make_profile()
    broken = make_profile()
    broken["vcs"] = "svn"
    write_profile(task, broken)
    # changed by MW-003 (R37 H1): `edit` refuses a broken profile on every call (no once-store); the profile
    # once-store now serves the non-blocking groups' log row, so its failure is checked in `post` below
    healthy = run(task, "PreToolUse", "edit", [REFUSE], payload=_payload(session="s9"))
    assert "profile-invalid" in json.loads(healthy.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
    assert "systemMessage" not in json.loads(healthy.stdout)  # control: no message when nothing failed
    write_profile(task, good)
    shutil.rmtree(state / "once")
    (state / "once").write_text("a file where the once folder should be", encoding="utf-8")
    once = entry("o2", "fixture_gates:refuse_once", on_failure="none")
    for _ in range(2):  # every failed write counts as the first time
        res = run(task, "PreToolUse", "edit", [once])
        assert res.exit_code == 0
        out = json.loads(res.stdout)
        hso = out["hookSpecificOutput"]
        assert hso["hookEventName"] == "PreToolUse" and hso["permissionDecision"] == "deny"
        assert "refuses the first time" in hso["permissionDecisionReason"] and "gate-error" not in res.stderr
        assert out.get("systemMessage")  # only the once write failed, so this message is the once-store's
    write_profile(task, broken)
    res = run(task, "PostToolUse", "post", [REFUSE], payload=_payload("PostToolUse"))
    assert res.exit_code == 0
    out = json.loads(res.stdout)
    assert out.get("systemMessage")  # the profile once-store's write failed: counted as the first time, and said
    assert [r["reason_id"] for r in refusals(task)] == [  # every row still written
        "fixture-refuse", "profile-invalid", "fixture-refuse", "fixture-refuse", "profile-invalid"]


@pytest.mark.parametrize("module", ["fixture_exits_on_import", "fixture_exits_2_on_import"])
@pytest.mark.parametrize("event,group,code", [("PreToolUse", "edit", 2), ("PreToolUse", "shell", 2),
                                              ("SessionStart", "start", 0), ("UserPromptSubmit", "prompt", 0),
                                              ("PostToolUse", "post", 0), ("Stop", "stop", 0)])
def test_gate_module_exit_on_import_follows_the_group_rule(task, event, group, code, module):
    """E65 (fix check 2 L2): a gate module that calls `sys.exit` while it is imported is caught like any module
    that cannot load (R13c): a `dispatcher-error` row with `SystemExit`, one stderr line and a `systemMessage`;
    exit 2 in `edit` and `shell`, exit 0 elsewhere, whatever code the module exits with. Never a silent pass.
    (Changed by fix check 3, blind: all six groups, and a module that exits with code 2.)"""
    bad = entry("e1", f"{module}:gate", event=event, group=group)
    res = run(task, event, group, [bad], payload=_payload(event))
    assert res.exit_code == code
    line = _one_stderr_line(res)
    assert "dispatcher-error" in line and "SystemExit" in line
    assert json.loads(res.stdout).get("systemMessage")
    assert [(r["reason_id"], r["exception"]) for r in refusals(task)] == [("dispatcher-error", "SystemExit")]


def _launcher(folder, body):
    """The root launcher beside a synthetic `engine/mkway.py` that fails at start-up."""
    (folder / "engine").mkdir(parents=True)
    shutil.copy(REPO / "mkway.py", folder / "mkway.py")
    (folder / "engine" / "mkway.py").write_text(body, encoding="utf-8")
    return folder / "mkway.py"


def _hook(launcher, *args):
    return subprocess.run([sys.executable, str(launcher), "hook", *args], input="{}", capture_output=True,
                          text=True, timeout=60)


def test_start_up_failures_follow_the_group_rule(tmp_path):
    """E62 (fix check N6): a failure before the dispatcher runs (an engine module that cannot be imported, a
    non-zero exit, a command line the parser refuses) writes one `mkway dispatcher-error: <class> at start-up`
    stderr line, and exits 2 only in `edit` and `shell`; in every other group, or with no group, it exits 0."""
    broken = _launcher(tmp_path / "import", "raise ImportError('planted start-up failure')\n")
    for group, code in (("edit", 2), ("shell", 2), ("start", 0), ("prompt", 0), ("post", 0), ("stop", 0)):
        res = _hook(broken, "PreToolUse", "--group", group)
        assert res.returncode == code, group
        assert "mkway dispatcher-error: ImportError at start-up" in res.stderr, group
    assert _hook(broken, "PreToolUse", "--group=edit").returncode == 2
    exits = _launcher(tmp_path / "exit", "import sys\nsys.exit(1)\n")
    res = _hook(exits, "Stop", "--group", "stop")
    assert res.returncode == 0 and "mkway dispatcher-error: SystemExit at start-up" in res.stderr
    assert _hook(exits, "PreToolUse", "--group", "shell").returncode == 2
    res = _hook(REPO / "mkway.py", "UserPromptSubmit")  # no --group: the parser refuses the command line
    assert res.returncode == 0 and "mkway dispatcher-error: SystemExit at start-up" in res.stderr


def test_once_store_true_only_first_time(task):
    """E11: ctx.once is true only the first time per session + gate + target set; it is stored under state.dir."""
    once = entry("o1", "fixture_gates:warn_once", reason_ids=["fixture-once"])

    def warned(path, session="s1"):
        res = run(task, "PreToolUse", "edit", [once], payload=_payload(tool_input={"file_path": path}, session=session))
        return res.stdout != ""

    assert warned("a.py") is True
    assert warned("a.py") is False
    assert warned("b.py") is True
    assert warned("a.py", session="s2") is True
    assert any((task / "mkway" / "state" / "once").iterdir())


def test_once_key_is_the_target_set(task):
    """E11: the key holds a hash of the target set: the same targets in another order are the same key; another gate
    is another key."""
    store = dispatch.OnceStore(task / "mkway" / "state", "s1")
    assert store.once("g1", ["x", "y"]) is True
    assert store.once("g1", ["y", "x", "x"]) is False
    assert store.once("g2", ["x", "y"]) is True
    assert dispatch.OnceStore(task / "mkway" / "state", "s9").once("g1", ["x", "y"]) is True


def test_budget_reaches_ctx_and_over_budget_is_logged(task):
    """E12: the dispatcher passes gates.<name>.budget_seconds in ctx; a gate over its budget is logged
    `over-budget`. No budget in the profile -> ctx gets None and nothing is logged."""
    slow = entry("slow", "fixture_gates:slow_warn", reason_ids=["fixture-slow"])
    res = run(task, "PreToolUse", "edit", [slow], gates={"slow": {"on": True, "budget_seconds": 0.01}})
    assert "budget=0.01" in json.loads(res.stdout)["hookSpecificOutput"]["additionalContext"]
    rows = refusals(task)
    assert [r["reason_id"] for r in rows] == ["fixture-slow", "over-budget"]
    assert rows[1]["gate"] == "slow" and rows[1]["elapsed_ms"] > 10
    res = run(task, "PreToolUse", "edit", [slow], gates={})
    assert "budget=None" in json.loads(res.stdout)["hookSpecificOutput"]["additionalContext"]
    assert [r["reason_id"] for r in refusals(task)] == ["fixture-slow", "over-budget", "fixture-slow"]


ROW_FIELDS = {"time", "session", "event", "tool", "gate", "reason_id", "target", "verdict", "kind"}


def test_refusal_row_fields(task):
    """E13: a row holds time, session id, event, tool, gate, reason id, target (a path, or the command head cut to
    200 characters) and `verdict: null`."""
    command = "echo " + "x" * 300
    run(task, "PreToolUse", "edit", [REFUSE], payload=_payload(tool="Bash", tool_input={"command": command}))
    run(task, "PreToolUse", "edit", [WARN], payload=_payload(tool="Write", tool_input={"file_path": "src/b.py"}))
    first, second = refusals(task)
    assert set(first) == ROW_FIELDS and set(second) == ROW_FIELDS
    assert first["target"] == command[:200] and len(first["target"]) == 200
    assert (first["session"], first["event"], first["tool"], first["verdict"]) == ("s1", "PreToolUse", "Bash", None)
    assert second["target"] == "src/b.py" and second["tool"] == "Write"
    datetime.datetime.fromisoformat(first["time"])


def test_gate_without_reason_ids_is_not_loaded(task):
    """E14: a gate whose entry has no reason_ids (missing or empty) is not loaded and is named in the result."""
    no_key = entry("n1", "fixture_gates:always_refuse", reason_ids=None)
    empty = entry("n2", "fixture_gates:always_refuse", reason_ids=[])
    res = run(task, "PreToolUse", "edit", [no_key, empty])
    assert (res.exit_code, res.stdout) == (0, "")
    assert res.not_loaded == ["n1", "n2"]
    assert refusals(task) == []


def test_undeclared_reason_is_logged(task):
    """E15: a Verdict whose reason id is not in the entry's list is logged as `undeclared-reason` (the gate's own id
    kept beside it); the verdict still applies."""
    sneaky = entry("u1", "fixture_gates:undeclared", reason_ids=["fixture-refuse"])
    res = run(task, "PreToolUse", "edit", [sneaky])
    assert json.loads(res.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    (row,) = refusals(task)
    assert (row["reason_id"], row["gate_reason"]) == ("undeclared-reason", "not-declared")


def test_one_timing_row_per_run(task):
    """E16: one timing row per dispatcher run, holding the milliseconds of each gate, in a daily file; never one row
    per gate."""
    w2 = entry("w2", "fixture_gates:always_warn", reason_ids=["fixture-warn"])
    run(task, "PreToolUse", "edit", [WARN, w2])
    run(task, "PreToolUse", "edit", [WARN, w2])
    files = sorted((task / "mkway" / "state").glob("timing-*.jsonl"))
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    assert [f.name for f in files] == [f"timing-{today}.jsonl"]
    rows = jsonl(files[0])
    assert len(rows) == 2
    for row in rows:
        assert set(row["gates_ms"]) == {"w1", "w2"}
        assert all(isinstance(ms, (int, float)) and ms >= 0 for ms in row["gates_ms"].values())
        assert (row["event"], row["group"], row["session"]) == ("PreToolUse", "edit", "s1")


def test_broken_profile_warns_and_blocks_nothing(task):
    """E21: with a broken profile PreToolUse runs no gate and names the broken key under `profile-invalid`. Changed
    by MW-003 (R37 H1, fail closed): the call is refused, not allowed with defaults; the owner fixes the profile in
    their own editor, where no hook runs."""
    broken = make_profile()
    broken["bundle"]["root"] = "../outside"
    write_profile(task, broken)
    res = run(task, "PreToolUse", "edit", [REFUSE])
    assert res.exit_code == 0
    out = json.loads(res.stdout)["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny"
    assert "profile-invalid" in out["permissionDecisionReason"] and "bundle.root" in out["permissionDecisionReason"]
    assert [(r["gate"], r["reason_id"]) for r in refusals(task)] == [("profile", "profile-invalid")]


def test_profile_invalid_warns_once_per_profile_hash(task):
    """E37 (C17 a): the `profile-invalid` row of a non-blocking group uses the once-store: once per session, and
    again only when the profile's content changes; never on every call. Changed by MW-003 (R37 H1): `edit` and
    `shell` refuse every call, so the once rule is checked in `prompt`."""
    broken = make_profile()
    broken["bundle"]["root"] = "../outside"
    write_profile(task, broken)

    def warned(session="s1"):
        before = len(refusals(task))
        res = run(task, "UserPromptSubmit", "prompt", [REFUSE], payload=_payload("UserPromptSubmit", session=session))
        assert res.exit_code == 0
        return len(refusals(task)) > before

    assert [warned(), warned(), warned()] == [True, False, False]
    broken["bundle"]["root"] = "../elsewhere"
    write_profile(task, broken)
    assert [warned(), warned()] == [True, False]
    assert warned(session="s2") is True
    assert [r["reason_id"] for r in refusals(task)] == ["profile-invalid"] * 3


@pytest.mark.parametrize("script", ["mkway.py", "engine/mkway.py"])
def test_cli_and_launcher_run_a_hook(task, script):
    """E23: `mkway.py hook <event> --group <name>` (the root launcher and the engine module) reads the hook JSON from
    stdin, exits 0 and allows when no gate is on; the root comes from CLAUDE_PROJECT_DIR, never from the engine's
    own folder. Changed by MW-003: the engine's gates are on by default now, so the profile turns them off."""
    write_profile(task, make_profile({"lock": {"on": False}, "subtask": {"on": False}, "records": {"on": False}}))
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
    env["CLAUDE_PROJECT_DIR"] = str(task)
    proc = subprocess.run([sys.executable, str(REPO / script), "hook", "PreToolUse", "--group", "edit"],
                          input=json.dumps(_payload()), capture_output=True, text=True, env=env, timeout=60)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == "" and proc.stderr == ""
    assert list((task / "mkway" / "state").glob("timing-*.jsonl"))
    assert not (REPO / "mkway" / "state").exists() and not (ENGINE / "mkway").exists()
