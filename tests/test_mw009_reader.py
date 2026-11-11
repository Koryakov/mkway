"""Deletes (card MW-009), part P2: the delete gate's reader and its refusals: every delete form in every position, a
target that is not a literal path inside the root that exists, a wildcard, a target outside the root, destructive SQL,
the owner-only trash commands, the false blocks of the owner's guard and the manifest entry. Synthetic task roots
only. Part P3 adds the backup and the record; P4 the git forms."""
import json

from _engine import gate_call, task_root

LIST_FIX = "mkway delete --list <file>"
TERMINAL = "your own terminal"


def _gate():
    import importlib
    return importlib.import_module("gate_delete")


def _root(tmp_path, **over):
    root = task_root(tmp_path, **over)
    (root / "d").mkdir()
    for rel in ("a.txt", "b.txt", "d/b.txt", "d/c.txt"):
        (root / rel).write_text("x\n", encoding="utf-8")
    (tmp_path / "elsewhere.txt").write_text("x\n", encoding="utf-8")
    return root


def _check(root, command, tool="Bash", session="s1", **payload):
    return gate_call(_gate().check, root, tool=tool, tool_input={"command": command}, session=session, **payload)


def _reason(verdict):
    return verdict.reason_id if verdict.kind == "refuse" else "allow"


def test_literal_existing_targets_inside_the_root_pass(tmp_path):
    """E4 (part 2): a delete whose every target is a literal path inside the root that exists is allowed, in the
    spellings a session writes: options, `--`, quotes, an absolute path inside the root, a path after a literal `cd`,
    a variable assigned a literal in the same command, a PowerShell parameter or alias, the cmd options `/s /q`.
    Catches: a gate that refuses every delete, or one that cannot read a plain spelling."""
    root = _root(tmp_path)
    here = root.as_posix()
    for cmd in ("rm a.txt", "rm -f a.txt b.txt", "rm -rf d", "rm -r -f -- d", "rm --recursive --force d",
                'rm "a.txt"', f"rm {here}/a.txt", "rm ./a.txt", "rmdir d", "unlink a.txt", "cd d && rm b.txt",
                "cd d; rm ./c.txt", "X=a.txt; rm $X", "del a.txt", "erase a.txt", "cmd /c del /q /f a.txt",
                "cmd /c rd /s /q d", "rd d", "RM a.txt", "env FOO=1 rm a.txt", "timeout 5 rm a.txt",
                "rm a.txt 2>/dev/null"):
        assert _reason(_check(root, cmd)) == "allow", cmd
    for cmd in ("Remove-Item a.txt", "Remove-Item -Path a.txt -Force", "Remove-Item -LiteralPath d -Recurse",
                "ri -Recurse -Force d", "Remove-Item -Path ./d/b.txt", "rm a.txt", "del a.txt", "rd d"):
        assert _reason(_check(root, cmd, tool="PowerShell")) == "allow", cmd


FORMS = ("rm {t}", "rmdir {t}", "unlink {t}", "del {t}", "erase {t}", "rd {t}", "find {t} -delete",
         "find . -name {t} -exec rm {{}} \\;", "python -c \"import os; os.remove('{t}')\"",
         "python3 -c \"import os; os.unlink('{t}')\"", "python -c \"import shutil; shutil.rmtree('{t}')\"",
         "python -c \"import os; os.rmdir('{t}')\"",
         "python -c \"from pathlib import Path; Path('{t}').unlink()\"",
         "python -c \"import os; os.remove(input())\"", "python -c \"import os; os.remove(os.environ['X'])\"")
PS_FORMS = ("Remove-Item {t}", "ri {t}", "rm {t}", "del {t}", "erase {t}", "rd {t}", "rmdir {t}")


def test_every_delete_form_is_read(tmp_path):
    """E5 (part 2): each delete form the order names is a delete: `rm`, `rmdir`, `unlink`, `del`, `erase`, `rd`,
    `find -delete`, `find -exec rm`, the Python calls `os.remove`, `os.unlink`, `os.rmdir`, `shutil.rmtree` and
    `Path.unlink`, and in PowerShell `Remove-Item` and its aliases. A target that does not exist is refused
    `delete-target-unknown`, and the message names the path. A Python call with a computed path is unknown too.
    Catches: a form the reader does not know, which would let a delete through."""
    root = _root(tmp_path)
    for form in FORMS:
        v = _check(root, form.format(t="nothere.txt"))
        assert v.kind == "refuse" and v.reason_id == "delete-target-unknown", form
        assert LIST_FIX in v.message, form
    for form in PS_FORMS:
        v = _check(root, form.format(t="nothere.txt"), tool="PowerShell")
        assert v.kind == "refuse" and v.reason_id == "delete-target-unknown", form
    v = _check(root, "rm a.txt nothere.txt")
    assert v.reason_id == "delete-target-unknown" and "nothere.txt" in v.message and "does not exist" in v.message


POSITIONS = ("{}", "true && {}", "false || {}", "true; {}", "echo x | {}", "echo y\n{}", "({})", "echo $({})",
             "echo `{}`", "bash -c '{}'", "sh -c \"{}\"", "cmd /c {}", "pwsh -c \"{}\"", "powershell -Command \"{}\"",
             "git commit -m x && {}", "git commit -m \"$({})\"", "nice {}", "xargs -0 {}", "echo a | xargs {}")


def test_a_delete_is_refused_in_every_position(tmp_path):
    """E6 (part 2): the same delete, `rm nothere.txt`, is refused alone, after `&&`, `||`, `;`, `|`, a newline, in
    parentheses, in `$( )` and backticks, behind `bash -c`, `cmd /c`, `pwsh -c`, `xargs`, after a `git commit` chain
    and inside a commit message substitution; in any letter case; `xargs rm` takes its targets from stdin, so it is
    unknown. Catches: a position the reader does not enter."""
    root = _root(tmp_path)
    for pos in POSITIONS:
        cmd = pos.format("rm nothere.txt")
        assert _reason(_check(root, cmd)) == "delete-target-unknown", cmd
    for cmd in ("RM nothere.txt", "Rm -rf nothere", "/bin/rm nothere.txt", "xargs rm", "ls | xargs rm -f",
                "echo a | xargs -I{} rm {}"):
        assert _reason(_check(root, cmd)) == "delete-target-unknown", cmd


def test_computed_and_broad_targets_are_unknown(tmp_path):
    """E7 (part 2): a variable, a substitution, an unknown PowerShell parameter or a splat is
    `delete-target-unknown` with the way out; a variable assigned a literal in the same command is read; the state
    folder, the folder that holds it and the root itself are too broad (unknown). Check order per target: variable,
    outside, wildcard, missing. Catches: a computed target that runs, or a delete of the state folder."""
    root = _root(tmp_path)
    for cmd in ("rm $X", "rm ${X}", "rm \"$(cat list)\"", "rm `ls`", "rm $HOME/x", "for f in a.txt; do rm $f; done",
                "rm -rf mkway", "rm -rf mkway/state", "rm -rf .", "rm -rf ./", "rm -rf d/..", "rm"):
        v = _check(root, cmd)
        assert v.kind == "refuse" and v.reason_id == "delete-target-unknown", cmd
        assert LIST_FIX in v.message, cmd
    for cmd in ("Remove-Item @args", "Remove-Item a.txt -Bogus", "Remove-Item $env:TEMP\\x", "Remove-Item (Get-Item a.txt)"):
        assert _reason(_check(root, cmd, tool="PowerShell")) == "delete-target-unknown", cmd
    assert _reason(_check(root, "rm ../*.txt")) == "delete-outside-root"  # outside is judged before the wildcard
    assert _reason(_check(root, "rm ../nothere.txt")) == "delete-outside-root"  # and before missing


def test_a_target_outside_the_root_is_always_refused(tmp_path):
    """E8 (part 2): a literal target outside the root is `delete-outside-root` whether it exists or not: `..`, an
    absolute path, the home folder, another drive; the message names the path and the owner's own terminal, never
    the list command, because the list command refuses it too. Catches: a gate that lets a session delete beside
    its task."""
    root = _root(tmp_path)
    outside = (tmp_path / "elsewhere.txt").as_posix()
    for cmd in ("rm ../elsewhere.txt", f"rm {outside}", f"rm -rf {tmp_path.as_posix()}", "rm /nothere/x",
                "rm ~/x.txt", "cd .. && rm elsewhere.txt", "rm a.txt ../elsewhere.txt", "rm -rf ../task2",
                "del C:/Windows/x.txt", "cmd /c del /q ../elsewhere.txt"):
        v = _check(root, cmd)
        assert v.kind == "refuse" and v.reason_id == "delete-outside-root", cmd
        assert TERMINAL in v.message and LIST_FIX not in v.message, cmd
    v = _check(root, "Remove-Item ../elsewhere.txt", tool="PowerShell")
    assert v.reason_id == "delete-outside-root"


def test_a_wildcard_is_refused(tmp_path):
    """E9 (part 2): a `*`, `?` or `[..]` in a delete target is `delete-wildcard`, naming the list command as the
    way out; a PowerShell `-Include`, `-Exclude` or `-Filter` is a wildcard too. Catches: `rm dir/*.txt`, the
    owner's first example, running."""
    root = _root(tmp_path)
    for cmd in ("rm *.txt", "rm d/*", "rm a?.txt", "rm [ab].txt", "rm -r d/**", "rm -rf d/*.txt", "del *.txt",
                "cmd /c del /q d\\*.txt", "rm d/c.*"):
        v = _check(root, cmd)
        assert v.kind == "refuse" and v.reason_id == "delete-wildcard", cmd
        assert LIST_FIX in v.message, cmd
    for cmd in ("Remove-Item *.txt", "Remove-Item d -Include *.txt", "Remove-Item d -Exclude a.txt",
                "Remove-Item d -Filter *.tmp", "ri d\\*"):
        assert _reason(_check(root, cmd, tool="PowerShell")) == "delete-wildcard", cmd


SQL = ("psql -c \"DROP TABLE t\"", "psql -c \"delete from t where id = 1\"", "sqlite3 x.db \"DELETE FROM t\"",
       "duckdb f.db \"drop table t\"", "mysql -e \"TRUNCATE t\"", "sqlcmd -Q \"truncate table t\"",
       "sqlite3 x.db <<'EOF'\nDROP TABLE t;\nEOF",
       "python -c \"import sqlite3; c = sqlite3.connect('x'); c.execute('DROP TABLE t')\"",
       "python -c \"import duckdb; duckdb.sql('delete from t')\"",
       "python -c \"import pandas as pd; pd.read_sql('truncate table t', c)\"",
       "echo y | psql -c \"drop database d\"")
SQL_SAFE = ("psql -c \"select 1\"", "sqlite3 x.db \"select * from t\"", "grep -n \"drop table|delete from\" f.py",
            "echo \"drop table t\"", "rg -n \"delete from\" src", "git log --grep \"delete from x\"",
            "cat f.sql", "head -5 f.sql", "git commit -m \"rm the old rows; del x; delete from cache; drop table t; "
            "truncate it\"", "python -c \"print('drop table t')\"",
            "python -c \"import sqlite3; c = sqlite3.connect('x'); c.execute('select 1')\"")


def test_destructive_sql_is_refused_unless_the_profile_allows_it(tmp_path):
    """E10 (part 2): `DROP`, `DELETE FROM` and `TRUNCATE` in the arguments or the heredoc of a SQL client, or in a
    Python string passed to `execute`, `executemany`, `executescript`, `sql` or `read_sql`, are `delete-sql`; the same
    words in a quoted echo, a read-only program's pattern or a commit message are not. `delete.sql_allowed: true`
    turns the family off. Catches: the words read as text anywhere, or SQL through a client that runs."""
    root = _root(tmp_path)
    for cmd in SQL:
        v = _check(root, cmd)
        assert v.kind == "refuse" and v.reason_id == "delete-sql", cmd
        assert "delete.sql_allowed" in v.message, cmd
    for cmd in SQL_SAFE:
        assert _reason(_check(root, cmd)) == "allow", cmd
    open_root = _root(tmp_path / "open", delete={"sql_allowed": True})
    for cmd in SQL:
        assert _reason(_check(open_root, cmd)) == "allow", cmd
    assert _reason(_check(open_root, "rm nothere.txt")) == "delete-target-unknown"  # only SQL is switched off


FALSE_BLOCKS = ("ls --format=rm", "echo confirm", "rmdir_helper", "./rmdir_helper a.txt", "rm_old a.txt",
                "cat del.txt", "ls x.rm", "echo \"rm\"", "echo rm -rf x", "a=rm", "echo $rm", "echo \"rm -rf *\"",
                "git status", "ls", "git log -- a.rm", "ls -la d", "grep -rn rm src", "cat a.txt | head",
                "pytest tests/test_del.py", "python -m pytest tests/test_rm.py -q", "python script.py d/b.txt",
                "python tools/clean.py --rm old", "git commit -m \"rm the old rows\"",
                "git commit -F - <<'EOF'\nrm the old rows; del x; truncate it\nEOF",
                "python - <<'EOF'\nx = [1, 2]\ndel x\nprint('rm')\nEOF",
                "python -c \"x = [1]; x.remove(1); del x\"", "python -c \"d = {}; d.pop('a', None)\"",
                "python mkway/engine/mkway.py delete --list /outside/the/root/list.txt",
                "python mkway/engine/mkway.py delete --list list.txt", "py -3 mkway/engine/mkway.py delete --list l.txt",
                "echo a.txt > list.txt && python mkway/engine/mkway.py delete --list list.txt")


def test_the_false_blocks_of_the_owners_guard_pass(tmp_path):
    """E11 (part 2): a remove word inside a longer word or a file name, as a quoted echo, an assignment, in a commit
    message, in the pattern of a read-only program, a pytest or python run that only names a path, a `del`
    statement in a Python heredoc, `list.remove` and `dict.pop`, and the list command with its list file inside or
    outside the root are all allowed. Catches: the guard's false blocks, which made the owner stop using it."""
    root = _root(tmp_path)
    for cmd in FALSE_BLOCKS:
        assert _reason(_check(root, cmd)) == "allow", cmd
    for cmd in ("Write-Output 'rm -rf x'", "Get-ChildItem d", "git status",
                "python mkway/engine/mkway.py delete --list ..\\list.txt"):
        assert _reason(_check(root, cmd, tool="PowerShell")) == "allow", cmd


def test_trash_commands_are_the_owners(tmp_path):
    """E12 (part 2): `mkway trash list` and `mkway trash empty ...` are refused `owner-only-command` for a session, in
    any spelling of the call, the refusal naming the owner's terminal; the list command is not owner-only. Catches:
    a session that empties its own trash, which would make the backup worthless."""
    root = _root(tmp_path)
    for cmd in ("python mkway/engine/mkway.py trash list", "python mkway/engine/mkway.py trash empty --older-than 30",
                "python mkway/engine/mkway.py trash empty --older-than 0", "py -3 mkway/engine/mkway.py trash list",
                "cd d && python ../mkway/engine/mkway.py trash list", "echo x && python mkway/engine/mkway.py trash empty",
                "bash -c 'python mkway/engine/mkway.py trash empty --older-than 1'"):
        v = _check(root, cmd)
        assert v.kind == "refuse" and v.reason_id == "owner-only-command", cmd
        assert "trash" in v.message and "terminal" in v.message, cmd
    assert _reason(_check(root, "python mkway/engine/mkway.py delete --list l.txt")) == "allow"
    assert _reason(_check(root, "python mkway/engine/mkway.py card list")) == "allow"


def test_a_non_shell_tool_and_odd_input_are_allowed(tmp_path):
    """E13 (part 2): the gate reads shell tools only; an Edit call, a missing or non-text command and an empty command
    are allowed (never a crash). Catches: a gate that raises on a payload it does not own."""
    root = _root(tmp_path)
    gate = _gate()
    assert gate_call(gate.check, root, tool="Edit", tool_input={"file_path": "a.txt"}).kind == "allow"
    assert gate_call(gate.check, root, tool="Bash", tool_input={}).kind == "allow"
    assert gate_call(gate.check, root, tool="Bash", tool_input={"command": 5}).kind == "allow"
    assert gate_call(gate.check, root, tool="Bash", tool_input=None).kind == "allow"
    assert _reason(_check(root, "")) == "allow"


REASONS = {"delete-target-unknown", "delete-too-large", "delete-backup-failed", "delete-wildcard",
           "delete-outside-root", "delete-sql", "delete-uncommitted", "owner-only-command"}


def test_the_manifest_has_the_delete_gate_after_the_commit_gate():
    """E14 (part 2): one manifest entry `delete` (gate `delete`, group `shell`, PreToolUse, matcher `Bash|PowerShell`,
    function `gate_delete:check`, `onFailure: block` with its reason, status on, default on) that lists the eight
    reason ids, placed after `commit_files`; the function exists. Catches: a gate that is written but not wired, or
    one that fails open."""
    from _engine import REPO
    entries = json.loads((REPO / "engine" / "manifest.json").read_text(encoding="utf-8"))["entries"]
    names = [e["name"] for e in entries]
    entry = entries[names.index("delete")]
    assert (entry["gate"], entry["group"], entry["event"], entry["matcher"], entry["function"]) == (
        "delete", "shell", "PreToolUse", "Bash|PowerShell", "gate_delete:check")
    assert entry["onFailure"] == "block" and entry["status"] == "on" and entry["default_on"] is True
    assert entry["on_failure_reason"] and set(entry["reason_ids"]) == REASONS
    assert names.index("delete") > names.index("commit_files")
    assert callable(getattr(_gate(), "check"))
