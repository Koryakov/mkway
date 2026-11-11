"""Commit checks (card MW-006), part 2: the record of the paths a session wrote, for the rule «own changes only».
Synthetic task roots only; the gate is called with the dispatcher's own context."""
import json

from _engine import gate_call, jsonl, task_root
import dispatch

SHELL = "Bash|PowerShell"
EDITS = "Edit|Write|MultiEdit|NotebookEdit"


def _touch(root, tool, tool_input, session="s1"):
    import gate_commit
    return gate_call(gate_commit.touch, root, tool=tool, tool_input=tool_input, session=session)


def _touched(root, session="s1"):
    import gate_commit
    return gate_commit.touched(root / "mkway" / "state", session)


def test_an_edit_tool_write_is_recorded_for_the_session(tmp_path):
    """E4 (part 2): a Write, Edit, MultiEdit or NotebookEdit path is recorded for the calling session, in the one
    repo-relative form, whatever its spelling; the call is allowed; a path outside the root is not recorded; another
    session's record is separate. Catches: a record that keeps the spelling (so `./src/a.py` and `src/a.py` differ),
    one shared by every session, or a recorder that refuses."""
    root = task_root(tmp_path)
    for tool, key, path in (("Edit", "file_path", "src/a.py"), ("Write", "file_path", "./src/b.py"),
                            ("MultiEdit", "file_path", str(root / "src" / "c.py")),
                            ("Write", "file_path", "src\\d.py"), ("NotebookEdit", "notebook_path", "nb/e.ipynb")):
        assert _touch(root, tool, {key: path}).kind == "allow", path
    assert _touch(root, "Edit", {"file_path": str(tmp_path / "elsewhere.py")}).kind == "allow"
    assert _touch(root, "Edit", {"other": 1}).kind == "allow"
    assert _touch(root, "Edit", {"file_path": "src/z.py"}, session="s2").kind == "allow"
    paths, unresolved = _touched(root)
    assert sorted(paths) == ["nb/e.ipynb", "src/a.py", "src/b.py", "src/c.py", "src/d.py"]
    assert unresolved is False
    assert _touched(root, "s2") == (["src/z.py"], False)
    assert _touched(root, "s3") == ([], False)
    row = jsonl(root / "mkway" / "state" / "touched.jsonl")[0]
    assert row["session_id"] == "s1" and row["path"] == "src/a.py" and row["via"] == "Edit" and row["time"]


def test_readable_shell_writes_are_recorded_and_unreadable_ones_marked(tmp_path):
    """E5 (part 2): the paths `shell_writes` reads from a shell command are recorded (a redirect, a copy target, a
    delete, `tee`, a PowerShell writer); a glob is kept as a glob; a command that writes nothing records nothing; a
    write whose target the gate cannot read (a variable, `eval`) is recorded as unresolved.
    Catches: a shell write that leaves no record, a glob that is expanded or dropped, or an unreadable write that
    is counted as no write."""
    root = task_root(tmp_path)
    cases = [
        ("Bash", "echo hi > src/a.txt", ["src/a.txt"], False),
        ("Bash", "cp src/a.txt out/b.txt", ["out/b.txt"], False),
        ("Bash", "echo hi | tee out/c.txt", ["out/c.txt"], False),
        ("Bash", "rm src/old.py", ["src/old.py"], False),
        ("Bash", "rm src/*.tmp", ["src/*.tmp"], False),
        ("Bash", "mkdir -p out/deep && touch out/deep/f.txt", ["out/deep", "out/deep/f.txt"], False),
        ("PowerShell", "Set-Content -Path src/p.txt -Value hi", ["src/p.txt"], False),
        ("Bash", "ls src && git status && git log --oneline -1", [], False),
        ("Bash", "echo hi > $TARGET", [], True),
        ("Bash", "eval \"$STEP\"", [], True),
        ("Bash", "echo hi > /elsewhere/outside.txt", [], False),
    ]
    for i, (tool, command, want, unresolved) in enumerate(cases):
        session = f"s{i}"
        assert _touch(root, tool, {"command": command}, session=session).kind == "allow", command
        paths, flag = _touched(root, session)
        assert (sorted(paths), flag) == (sorted(want), unresolved), command


def _run(root, group, tool, tool_input, session="s1"):
    payload = {"session_id": session, "hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input,
               "cwd": str(root)}
    event = "PreToolUse"
    return dispatch.run(event, group, json.dumps(payload), env={"CLAUDE_PROJECT_DIR": str(root)})


def test_the_recorders_are_wired_after_the_gates_that_refuse(tmp_path):
    """E6 (part 2): the manifest has `touched.edit` (edit group, after the edit gates) and `touched.shell` (shell
    group, after the lock gate), both on the gate `commit_files`, function `gate_commit:touch`, `onFailure: block`;
    a call another gate refuses records nothing (the write never happens); an allowed call records its path; the
    one switch `gates.commit_files.on: false` turns both off.
    Catches: a recorder that runs before the lock gate (a refused write would count as touched), or a recorder with
    a switch of its own."""
    entries = dispatch.load_manifest(dispatch.ENGINE_DIR)
    names = [e["name"] for e in entries]
    by = {e["name"]: e for e in entries}
    for name, group, matcher in (("touched.edit", "edit", EDITS), ("touched.shell", "shell", SHELL)):
        e = by[name]
        assert (e["gate"], e["group"], e["event"], e["matcher"], e["function"], e["onFailure"], e["status"]) == (
            "commit_files", group, "PreToolUse", matcher, "gate_commit:touch", "block", "on"), name
        assert e["reason_ids"] == ["touch-record-failed"] and e["on_failure_reason"], name
    assert names.index("touched.edit") > max(names.index("subtask"), names.index("owner_ask.edit"),
                                             names.index("lock.edit"))
    assert names.index("touched.shell") > names.index("lock.shell")

    root = task_root(tmp_path, paths={"exempt": ["src/**"]})
    store = root / "mkway" / "state" / "touched.jsonl"
    assert json.loads(_run(root, "edit", "Edit", {"file_path": "mkway/profile.json"}).stdout)[
        "hookSpecificOutput"]["permissionDecision"] == "deny"  # lock gate
    assert json.loads(_run(root, "edit", "Edit", {"file_path": "other/x.py"}).stdout)[
        "hookSpecificOutput"]["permissionDecision"] == "deny"  # subtask gate: no open card
    assert json.loads(_run(root, "shell", "Bash", {"command": "echo x > mkway/profile.json"}).stdout)[
        "hookSpecificOutput"]["permissionDecision"] == "deny"  # lock gate
    assert not store.exists()
    assert _run(root, "edit", "Edit", {"file_path": "src/x.py"}).exit_code == 0
    assert _run(root, "shell", "Bash", {"command": "echo x > src/y.txt"}).exit_code == 0
    assert [(r["path"], r["via"]) for r in jsonl(store)] == [("src/x.py", "Edit"), ("src/y.txt", "Bash")]

    off = task_root(tmp_path, name="off", paths={"exempt": ["src/**"]}, gates={"commit_files": {"on": False}})
    assert _run(off, "edit", "Edit", {"file_path": "src/x.py"}).exit_code == 0
    assert _run(off, "shell", "Bash", {"command": "echo x > src/y.txt"}).exit_code == 0
    assert not (off / "mkway" / "state" / "touched.jsonl").exists()
