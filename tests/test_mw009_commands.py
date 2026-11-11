"""Deletes (card MW-009), part P5: `mkway delete --list <file>` (a session's command: a list of exact paths is backed up,
deleted and recorded) and `mkway trash list` / `mkway trash empty --older-than <days>` (the owner's). Synthetic task
roots only; every file lives in the pytest temp folder."""
import json
import os

from _engine import ENGINE, cli, jsonl, task_root


def _root(tmp_path, **over):
    root = task_root(tmp_path, **over)
    (root / "d").mkdir()
    for rel, text in (("a.txt", "alpha\n"), ("b.txt", "beta\n"), ("d/b.txt", "inner b\n"), ("d/c.txt", "inner c\n")):
        (root / rel).write_text(text, encoding="utf-8")
    (tmp_path / "elsewhere.txt").write_text("x\n", encoding="utf-8")
    return root


def _list(tmp_path, text, name="list.txt"):
    path = tmp_path / name  # outside the root: the scratchpad case the owner's guard blocked
    path.write_bytes(text.encode("utf-8"))
    return path


def _state(root):
    return root / "mkway" / "state"


def _folders(root):
    trash = _state(root) / "trash"
    return sorted(os.listdir(trash)) if trash.is_dir() else []


def _rows(root):
    path = _state(root) / "deletes.jsonl"
    return jsonl(path) if path.is_file() else []


def test_the_list_command_backs_up_deletes_and_records(tmp_path):
    """E26 (part 5): `mkway delete --list <file>` takes one exact repo path per line (CRLF, blank lines, spaces, `./`,
    an absolute path inside the root, a path twice), copies them into the trash, deletes them and writes one record row
    (`via: list`, the targets, the backup folder; the CLI knows no session id, so `session` is null and `by` says who).
    The list file may lie outside the root. It works in a session and in the owner's terminal. Catches: the way out
    of a wildcard that is itself blocked, or a bulk delete with no backup."""
    root = _root(tmp_path)
    here = root.as_posix()
    lst = _list(tmp_path, f"a.txt\r\n\r\n  d  \r\nd/b.txt\n./b.txt\n{here}/a.txt\n")
    code, out, err = cli(root, "delete", "--list", str(lst), session=True)
    assert code == 0, err
    assert not (root / "a.txt").exists() and not (root / "d").exists() and not (root / "b.txt").exists()
    (name,) = _folders(root)
    folder = _state(root) / "trash" / name
    assert (folder / "a.txt").read_text(encoding="utf-8") == "alpha\n"
    assert (folder / "d" / "c.txt").read_text(encoding="utf-8") == "inner c\n"
    assert (folder / "b.txt").read_text(encoding="utf-8") == "beta\n"
    (row,) = _rows(root)
    assert row["via"] == "list" and row["targets"] == ["a.txt", "d", "d/b.txt", "b.txt"]
    assert row["backup"] == f"mkway/state/trash/{name}" and row["session"] is None and row["by"] == "session"
    assert "deleted 4" in out and name in out
    owner = _root(tmp_path / "owner")
    code, out, err = cli(owner, "delete", "--list", str(_list(tmp_path / "owner", "a.txt\n")))
    assert code == 0, err
    assert not (owner / "a.txt").exists() and _rows(owner)[0]["by"] == "owner"


def test_one_bad_line_deletes_nothing(tmp_path):
    """E27 (part 5): every line must exist, lie inside the root, hold no wildcard and not lie in or hold a closed lock
    target or the state folder; with any bad line nothing is deleted, nothing is copied, no row is written, and each
    bad line is named with its number and its reason; an empty list and a missing file are errors. Catches: a list that
    deletes the good half, or one that deletes what the gate would refuse."""
    root = _root(tmp_path, locks={"targets": [{"name": "frozen", "paths": ["frozen/"]}]})
    (root / "frozen").mkdir()
    (root / "frozen" / "f.txt").write_text("f\n", encoding="utf-8")
    lines = ["a.txt", "nothere.txt", "../elsewhere.txt", "d/*.txt", "frozen/f.txt", "mkway/state", ".", "b.txt"]
    code, out, err = cli(root, "delete", "--list", str(_list(tmp_path, "\n".join(lines) + "\n")), session=True)
    assert code == 1
    for number, text, why in ((2, "nothere.txt", "does not exist"), (3, "../elsewhere.txt", "outside"),
                              (4, "d/*.txt", "wildcard"), (5, "frozen/f.txt", "frozen"),
                              (6, "mkway/state", "state"), (7, ".", "root")):
        assert f"line {number}" in err and text in err and why in err, (number, err)
    assert "line 1" not in err and "line 8" not in err
    assert (root / "a.txt").is_file() and (root / "b.txt").is_file() and (root / "frozen" / "f.txt").is_file()
    assert _folders(root) == [] and _rows(root) == []
    code, out, err = cli(root, "delete", "--list", str(_list(tmp_path, "\n  \n", "empty.txt")), session=True)
    assert code == 1 and "no path" in err
    code, out, err = cli(root, "delete", "--list", str(tmp_path / "missing.txt"), session=True)
    assert code == 1 and "list file" in err
    assert (root / "a.txt").is_file() and _rows(root) == []


def test_the_list_command_respects_the_size_limit(tmp_path):
    """E28 (part 5): the list command's backup is limited by `delete.max_backup_mb` too: above it nothing is deleted
    and the text says it needs the owner's terminal. Catches: a bulk delete that fills the disk."""
    root = _root(tmp_path, delete={"max_backup_mb": 1})
    (root / "big.bin").write_bytes(b"x" * (1024 * 1024 + 1))
    code, out, err = cli(root, "delete", "--list", str(_list(tmp_path, "big.bin\na.txt\n")), session=True)
    assert code == 1 and "needs the owner's terminal" in err
    assert (root / "big.bin").is_file() and (root / "a.txt").is_file() and _rows(root) == []


def test_the_gate_lets_the_list_command_through_and_stops_the_trash_commands(tmp_path):
    """E29 (part 5): through the dispatcher with the engine's own manifest, `python mkway/engine/mkway.py delete --list
    <file>` is not refused (the list file outside the root, as the owner's guard falsely refused it) and `mkway trash
    list` and `mkway trash empty ...` are `owner-only-command`. Catches: a gate that blocks its own way out, or a session
    that reaches the trash."""
    import dispatch
    root = _root(tmp_path)
    lst = _list(tmp_path, "a.txt\n")

    def run(command):
        payload = {"session_id": "s1", "hook_event_name": "PreToolUse", "cwd": str(root), "tool_name": "Bash",
                   "tool_input": {"command": command}}
        return dispatch.run("PreToolUse", "shell", json.dumps(payload),
                            env={"CLAUDE_PROJECT_DIR": str(root), "CLAUDECODE": "1"}, engine_dir=ENGINE)
    res = run(f"python mkway/engine/mkway.py delete --list {lst.as_posix()}")
    assert res.exit_code == 0 and res.stdout == "", res.stdout
    for command in ("python mkway/engine/mkway.py trash list", "python mkway/engine/mkway.py trash empty --older-than 1"):
        out = json.loads(run(command).stdout)["hookSpecificOutput"]
        assert out["permissionDecision"] == "deny" and "owner-only-command" in out["permissionDecisionReason"], command


def test_the_trash_commands_are_the_owners(tmp_path):
    """E30 (part 5): `mkway trash list` and `mkway trash empty --older-than <days>` are refused to a session (the
    CLAUDECODE tripwire, `owner-only-command`, as for `lock`); the owner lists the folders (name, files, size, targets)
    and empties those older than the days by the stamp in the name; `--older-than 0` empties all; a folder with no
    stamp is never touched; the days are required and not negative; each empty is one record row; the engine never
    empties the trash by itself. Catches: a session that destroys its own backups."""
    root = _root(tmp_path)
    trash = _state(root) / "trash"
    old = trash / "20200101T000000-000000"
    (old / "x").mkdir(parents=True)
    (old / "x" / "f.txt").write_text("old\n", encoding="utf-8")
    (trash / "notes").mkdir()
    assert cli(root, "delete", "--list", str(_list(tmp_path, "a.txt\n")), session=True)[0] == 0
    (fresh,) = [n for n in _folders(root) if n[0] == "2" and n != old.name]
    assert old.is_dir()  # a later delete never empties the trash
    for args in (("trash", "list"), ("trash", "empty", "--older-than", "0")):
        code, out, err = cli(root, *args, session=True)
        assert code == 1 and "owner-only-command" in err, args
    assert old.is_dir() and (trash / fresh).is_dir()
    code, out, err = cli(root, "trash", "list")
    assert code == 0, err
    assert old.name in out and fresh in out and "1 files" in out and "a.txt" in out
    code, out, err = cli(root, "trash", "empty", "--older-than", "30")
    assert code == 0 and "removed 1" in out, (out, err)
    assert not old.exists() and (trash / fresh).is_dir() and (trash / "notes").is_dir()
    code, out, err = cli(root, "trash", "empty", "--older-than", "0")
    assert code == 0 and "removed 1" in out
    assert _folders(root) == ["notes"]
    emptied = [r for r in _rows(root) if r["via"] == "trash-empty"]
    assert [r["by"] for r in emptied] == ["owner", "owner"] and emptied[0]["targets"] == [old.name]
    assert cli(root, "trash", "empty")[0] == 2 and cli(root, "trash", "empty", "--older-than", "-1")[0] != 0
    assert cli(root, "trash", "empty", "--older-than", "soon")[0] == 2
