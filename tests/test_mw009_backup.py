"""Deletes (card MW-009), part P3: the backup before a delete runs and its record row: the copy into the trash folder,
the size limit, a failed copy or record, no trash for a refused command, and the fail-closed crash. Synthetic task roots
only; the files live in the pytest temp folder."""
import json
import os
import re

import pytest

from _engine import ENGINE, gate_call, jsonl, task_root

STAMP = re.compile(r"^\d{8}T\d{6}-\d{6}(-\d+)?$")


def _gate():
    import importlib
    return importlib.import_module("gate_delete")


def _root(tmp_path, **over):
    root = task_root(tmp_path, **over)
    (root / "d").mkdir()
    for rel, text in (("a.txt", "alpha\n"), ("b.txt", "beta\n"), ("d/b.txt", "inner b\n"), ("d/c.txt", "inner c\n")):
        (root / rel).write_text(text, encoding="utf-8")
    (tmp_path / "elsewhere.txt").write_text("x\n", encoding="utf-8")
    return root


def _check(root, command, tool="Bash", session="s1"):
    return gate_call(_gate().check, root, tool=tool, tool_input={"command": command}, session=session)


def _state(root):
    return root / "mkway" / "state"


def _folders(root):
    trash = _state(root) / "trash"
    return sorted(os.listdir(trash)) if trash.is_dir() else []


def _rows(root):
    return jsonl(_state(root) / "deletes.jsonl") if (_state(root) / "deletes.jsonl").is_file() else []


def test_a_delete_is_copied_into_the_trash_and_recorded(tmp_path):
    """E15 (part 3): before a delete may run, every target is copied into `<state.dir>/trash/<timestamp>/<repo path>`
    (a folder with its content, a file at its path) and one row is appended to `<state.dir>/deletes.jsonl` with the
    session, the time, the targets in command order and the backup folder; the gate itself deletes nothing; two
    deletes make two folders and two rows, even within one second; a PowerShell delete is backed up the same way.
    Catches: a delete that cannot be undone, or one with no trace of who made it."""
    root = _root(tmp_path)
    assert _check(root, "rm -rf d a.txt").kind == "allow"
    (name,) = _folders(root)
    assert STAMP.match(name), name
    folder = _state(root) / "trash" / name
    assert (folder / "a.txt").read_text(encoding="utf-8") == "alpha\n"
    assert (folder / "d" / "b.txt").read_text(encoding="utf-8") == "inner b\n"
    assert (folder / "d" / "c.txt").read_text(encoding="utf-8") == "inner c\n"
    assert (root / "a.txt").is_file() and (root / "d" / "c.txt").is_file()  # the tool deletes, not the gate
    (row,) = _rows(root)
    assert row["session"] == "s1" and row["targets"] == ["d", "a.txt"] and row["via"] == "gate"
    assert row["backup"] == f"mkway/state/trash/{name}" and isinstance(row["time"], str) and row["time"]
    assert _check(root, "cd d && rm b.txt", session="s2").kind == "allow"
    assert _check(root, "rm b.txt", session="s2").kind == "allow"
    assert len(_folders(root)) == 3 and len(set(_folders(root))) == 3
    rows = _rows(root)
    assert [r["targets"] for r in rows] == [["d", "a.txt"], ["d/b.txt"], ["b.txt"]]
    assert [r["session"] for r in rows] == ["s1", "s2", "s2"]
    assert (_state(root) / "trash" / rows[1]["backup"].rsplit("/", 1)[1] / "d" / "b.txt").is_file()
    assert _check(root, "Remove-Item -Recurse -Force d", tool="PowerShell").kind == "allow"
    last = _state(root) / "trash" / _rows(root)[-1]["backup"].rsplit("/", 1)[1]
    assert (last / "d" / "c.txt").read_text(encoding="utf-8") == "inner c\n"


def test_an_empty_folder_and_a_nested_file_keep_their_path(tmp_path):
    """E16 (part 3): an empty folder is backed up as a folder, a file in a nested folder at its full repo path, and a
    target named twice in one command once. Catches: a copy that flattens paths or loses an empty folder."""
    root = _root(tmp_path)
    (root / "empty" / "deeper").mkdir(parents=True)
    (root / "d" / "sub").mkdir()
    (root / "d" / "sub" / "x.txt").write_text("deep\n", encoding="utf-8")
    assert _check(root, "rmdir empty/deeper; rm d/sub/x.txt d/sub/x.txt").kind == "allow"
    (name,) = _folders(root)
    folder = _state(root) / "trash" / name
    assert (folder / "empty" / "deeper").is_dir()
    assert (folder / "d" / "sub" / "x.txt").read_text(encoding="utf-8") == "deep\n"
    assert _rows(root)[0]["targets"] == ["empty/deeper", "d/sub/x.txt"]


def test_a_backup_above_the_limit_is_refused(tmp_path):
    """E17 (part 3): the total size of the targets above `delete.max_backup_mb` is `delete-too-large`, «needs the
    owner's terminal»: nothing is copied and no row is written; a size exactly at the limit passes; a folder counts by
    its content. Catches: a delete of a big tree that fills the disk, or a limit that is read as a count of files."""
    root = _root(tmp_path, delete={"max_backup_mb": 1})
    mib = 1024 * 1024
    (root / "edge.bin").write_bytes(b"x" * mib)
    (root / "big.bin").write_bytes(b"x" * (mib + 1))
    (root / "d" / "half1.bin").write_bytes(b"x" * (mib // 2))
    (root / "d" / "half2.bin").write_bytes(b"x" * (mib // 2 + 10))
    for cmd in ("rm big.bin", "rm -rf d", "rm a.txt big.bin"):
        v = _check(root, cmd)
        assert v.kind == "refuse" and v.reason_id == "delete-too-large", cmd
        assert "needs the owner's terminal" in v.message and "delete.max_backup_mb" in v.message, cmd
    assert _folders(root) == [] and _rows(root) == []
    assert _check(root, "rm edge.bin").kind == "allow"
    assert len(_folders(root)) == 1 and len(_rows(root)) == 1


def test_a_failed_copy_or_record_refuses_the_delete(tmp_path, monkeypatch):
    """E18 (part 3): a copy that fails, a trash folder that cannot be made and a record row that cannot be written are
    each `delete-backup-failed`, naming what failed; the delete is refused, never allowed without its backup. Catches:
    a delete that runs although its backup or its record is missing."""
    import trash
    root = _root(tmp_path)

    def boom(*_a, **_k):
        raise OSError("disk full")
    monkeypatch.setattr(trash.shutil, "copy2", boom)
    v = _check(root, "rm a.txt")
    assert v.kind == "refuse" and v.reason_id == "delete-backup-failed" and "disk full" in v.message
    monkeypatch.undo()
    assert _rows(root) == []
    blocked = _root(tmp_path / "blocked")
    (_state(blocked)).mkdir(parents=True, exist_ok=True)
    (_state(blocked) / "trash").write_text("a file where the trash folder must be\n", encoding="utf-8")
    v = _check(blocked, "rm a.txt")
    assert v.kind == "refuse" and v.reason_id == "delete-backup-failed"
    unrecorded = _root(tmp_path / "unrecorded")
    monkeypatch.setattr(trash.logs, "append_jsonl", boom)
    v = _check(unrecorded, "rm a.txt")
    assert v.kind == "refuse" and v.reason_id == "delete-backup-failed" and "record" in v.message
    monkeypatch.undo()


def test_a_refused_or_plain_command_leaves_no_trash(tmp_path):
    """E19 (part 3): a command that is refused for any reason, and a command that deletes nothing, copy nothing and write
    no row. Catches: a trash folder that fills with copies of deletes that never ran."""
    root = _root(tmp_path)
    for cmd in ("ls", "echo rm a.txt", "rm a.txt nothere.txt", "rm a.txt ../elsewhere.txt", "rm *.txt", "rm $X",
                "psql -c \"drop table t\"", "python mkway/engine/mkway.py trash list", "git status"):
        _check(root, cmd)
    assert _folders(root) == [] and _rows(root) == []
    assert not (_state(root) / "trash").exists() and not (_state(root) / "deletes.jsonl").exists()


def test_a_crash_in_the_gate_blocks_the_delete(tmp_path, monkeypatch):
    """E20 (part 3): through the dispatcher with the engine's own manifest, a crash in the delete gate (here: the backup
    raises) is `gate-error` and blocks the shell call: the entry's `onFailure: block`. Catches: a crash that lets a
    delete through unbacked."""
    import dispatch
    import trash
    root = _root(tmp_path)

    def crash(*_a, **_k):
        raise RuntimeError("planted")
    monkeypatch.setattr(trash, "backup", crash)
    payload = {"session_id": "s1", "hook_event_name": "PreToolUse", "cwd": str(root), "tool_name": "Bash",
               "tool_input": {"command": "rm a.txt"}}
    res = dispatch.run("PreToolUse", "shell", json.dumps(payload),
                       env={"CLAUDE_PROJECT_DIR": str(root), "CLAUDECODE": "1"}, engine_dir=ENGINE)
    out = json.loads(res.stdout)["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny" and "gate-error" in out["permissionDecisionReason"]
    assert "delete" in out["permissionDecisionReason"] and "RuntimeError" in out["permissionDecisionReason"]
    assert (root / "a.txt").is_file() and _rows(root) == []
