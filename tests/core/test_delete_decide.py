"""Card MW-064: the table tests of the delete gate's decisions. No disk, no git, no clock: `_delete_world.judge` reads the
command with the gate's reader and answers the core's questions from a virtual task root. One test id is one case
(criterion T2): every row of a table is its own id. The expected values are written from the rules of card MW-009: the
reason ids, the way out named in the text, the targets in command order. The case map is
`cards/MW-064-delete-core/case_map.md`. A failure-path test names the broken behaviour in its «Catches:» line (T4b)."""
import builtins
import os
import subprocess
import time

import pytest

import _delete_world as world
from _delete_world import LIST_FIX, judge, reason
import core_delete as core

TERMINAL = "your own terminal"
MIB = 1024 * 1024
NOW = 1_794_484_800  # 2026-11-12 12:00:00 UTC, written out: the tests never read the clock
DAY = 86400


# ---- a delete that passes: its targets, in command order --------------------------------------------------------------

ALLOWED = (
    ("Bash", "rm a.txt", ("a.txt",)), ("Bash", "rm -f a.txt b.txt", ("a.txt", "b.txt")),
    ("Bash", "rm -rf d", ("d",)), ("Bash", "rm -r -f -- d", ("d",)), ("Bash", "rm --recursive --force d", ("d",)),
    ("Bash", 'rm "a.txt"', ("a.txt",)), ("Bash", "rm /task/a.txt", ("a.txt",)), ("Bash", "rm ./a.txt", ("a.txt",)),
    ("Bash", "rmdir d", ("d",)), ("Bash", "unlink a.txt", ("a.txt",)), ("Bash", "cd d && rm b.txt", ("d/b.txt",)),
    ("Bash", "cd d; rm ./c.txt", ("d/c.txt",)), ("Bash", "X=a.txt; rm $X", ("a.txt",)),
    ("Bash", "del a.txt", ("a.txt",)), ("Bash", "erase a.txt", ("a.txt",)),
    ("Bash", "cmd /c del /q /f a.txt", ("a.txt",)), ("Bash", "cmd /c rd /s /q d", ("d",)), ("Bash", "rd d", ("d",)),
    ("Bash", "RM a.txt", ("a.txt",)), ("Bash", "env FOO=1 rm a.txt", ("a.txt",)),
    ("Bash", "timeout 5 rm a.txt", ("a.txt",)), ("Bash", "rm a.txt 2>/dev/null", ("a.txt",)),
    ("PowerShell", "Remove-Item a.txt", ("a.txt",)), ("PowerShell", "Remove-Item -Path a.txt -Force", ("a.txt",)),
    ("PowerShell", "Remove-Item -LiteralPath d -Recurse", ("d",)), ("PowerShell", "ri -Recurse -Force d", ("d",)),
    ("PowerShell", "Remove-Item -Path ./d/b.txt", ("d/b.txt",)), ("PowerShell", "rm a.txt", ("a.txt",)),
    ("PowerShell", "del a.txt", ("a.txt",)), ("PowerShell", "rd d", ("d",)),
    ("Bash", "rm -rf d a.txt", ("d", "a.txt")), ("Bash", "rm a.txt a.txt", ("a.txt",)),
    ("Bash", "rmdir d; rm d/b.txt d/b.txt", ("d", "d/b.txt")))


@pytest.mark.parametrize("tool, command, targets", ALLOWED)
def test_a_literal_existing_target_inside_the_root_is_allowed_and_listed_for_backup(tool, command, targets):
    """A delete whose every target is a literal path inside the root that exists is allowed, and the paths to back up
    are its targets in command order, a path named twice once. Catches: a gate that refuses a spelling a session writes
    (quotes, `--`, an absolute path inside the root, a path after `cd`, a variable assigned a literal, the cmd options,
    the PowerShell parameters), or one that backs up the wrong paths."""
    decision = judge(command, tool=tool)
    assert (reason(decision), decision.targets) == ("allow", targets)


# ---- every delete form is read ---------------------------------------------------------------------------------------

FORMS = ("rm {t}", "rmdir {t}", "unlink {t}", "del {t}", "erase {t}", "rd {t}", "find {t} -delete",
         "find . -name {t} -exec rm {{}} \\;", "python -c \"import os; os.remove('{t}')\"",
         "python3 -c \"import os; os.unlink('{t}')\"", "python -c \"import shutil; shutil.rmtree('{t}')\"",
         "python -c \"import os; os.rmdir('{t}')\"",
         "python -c \"from pathlib import Path; Path('{t}').unlink()\"",
         "python -c \"import os; os.remove(input())\"", "python -c \"import os; os.remove(os.environ['X'])\"")
PS_FORMS = ("Remove-Item {t}", "ri {t}", "rm {t}", "del {t}", "erase {t}", "rd {t}", "rmdir {t}")


@pytest.mark.parametrize("form", FORMS)
def test_every_bash_delete_form_with_a_missing_target_is_unknown(form):
    """Each delete form (`rm`, `rmdir`, `unlink`, `del`, `erase`, `rd`, `find -delete`, `find -exec rm`, the Python
    calls `os.remove`, `os.unlink`, `os.rmdir`, `shutil.rmtree`, `Path.unlink`, a computed Python path) is a delete: a
    target that does not exist is `delete-target-unknown`, with the way out. Catches: a form the reader does not know,
    which would let a delete through."""
    decision = judge(form.format(t="nothere.txt"))
    assert reason(decision) == "delete-target-unknown" and LIST_FIX in decision.verdict.message


@pytest.mark.parametrize("form", PS_FORMS)
def test_every_powershell_delete_form_with_a_missing_target_is_unknown(form):
    """`Remove-Item` and its aliases are deletes in PowerShell. Catches: an alias the reader does not know."""
    assert reason(judge(form.format(t="nothere.txt"), tool="PowerShell")) == "delete-target-unknown"


def test_the_refusal_for_a_missing_target_names_the_path():
    """The text names the path that does not exist, beside one that does. Catches: a refusal that does not say which
    target stopped the command."""
    message = judge("rm a.txt nothere.txt").verdict.message
    assert "nothere.txt" in message and "does not exist" in message


# ---- every position ---------------------------------------------------------------------------------------------------

POSITIONS = ("{}", "true && {}", "false || {}", "true; {}", "echo x | {}", "echo y\n{}", "({})", "echo $({})",
             "echo `{}`", "bash -c '{}'", "sh -c \"{}\"", "cmd /c {}", "pwsh -c \"{}\"", "powershell -Command \"{}\"",
             "git commit -m x && {}", "git commit -m \"$({})\"", "nice {}", "xargs -0 {}", "echo a | xargs {}")


@pytest.mark.parametrize("position", POSITIONS)
def test_a_delete_is_refused_in_every_position(position):
    """The same delete, `rm nothere.txt`, is `delete-target-unknown` alone, after `&&`, `||`, `;`, `|`, a newline, in
    parentheses, in `$( )` and backticks, behind `bash -c`, `cmd /c`, `pwsh -c`, `xargs`, after a commit chain and in a
    commit message substitution. Catches: a position the reader does not enter, where a delete would run unseen."""
    assert reason(judge(position.format("rm nothere.txt"))) == "delete-target-unknown"


@pytest.mark.parametrize("command", ("RM nothere.txt", "Rm -rf nothere", "/bin/rm nothere.txt", "xargs rm",
                                     "ls | xargs rm -f", "echo a | xargs -I{} rm {}"))
def test_a_delete_in_any_letter_case_or_through_xargs_is_unknown(command):
    """Any letter case, a program path, and `xargs rm` (its targets come from stdin) are `delete-target-unknown`.
    Catches: a delete hidden by its spelling."""
    assert reason(judge(command)) == "delete-target-unknown"


# ---- computed and broad targets ---------------------------------------------------------------------------------------

COMPUTED = ("rm $X", "rm ${X}", "rm \"$(cat list)\"", "rm `ls`", "rm $HOME/x", "for f in a.txt; do rm $f; done",
            "rm -rf mkway", "rm -rf mkway/state", "rm -rf .", "rm -rf ./", "rm -rf d/..", "rm")


@pytest.mark.parametrize("command", COMPUTED)
def test_a_computed_or_broad_target_is_unknown_with_the_way_out(command):
    """A variable, a substitution, a loop variable, the state folder, the folder that holds it, the root and a delete
    with no target are `delete-target-unknown`, naming the list command. Catches: a computed target that runs, or a
    delete of the state folder."""
    decision = judge(command)
    assert reason(decision) == "delete-target-unknown" and LIST_FIX in decision.verdict.message


@pytest.mark.parametrize("command", ("Remove-Item @args", "Remove-Item a.txt -Bogus", "Remove-Item $env:TEMP\\x",
                                     "Remove-Item (Get-Item a.txt)"))
def test_an_unreadable_powershell_target_is_unknown(command):
    """A splat, an unknown parameter, a variable and a parenthesised expression hide the target. Catches: a PowerShell
    delete whose target the gate cannot read but lets through."""
    assert reason(judge(command, tool="PowerShell")) == "delete-target-unknown"


@pytest.mark.parametrize("target, expected", (
    ("$X", "delete-target-unknown"), ("$X*", "delete-target-unknown"), ("../*.txt", "delete-outside-root"),
    ("../nothere.txt", "delete-outside-root"), ("~/*.txt", "delete-outside-root"), ("*.txt", "delete-wildcard"),
    ("nothere.txt", "delete-target-unknown"), ("a.txt", "allow")))
def test_the_checks_of_one_target_run_in_the_order_variable_outside_wildcard_missing(target, expected):
    """One target that fails several checks gets the first reason of the order: computed, outside the root, wildcard,
    missing. Catches: a refusal that names the wrong reason, so the text sends the session the wrong way out."""
    assert reason(judge(f"rm {target}")) == expected


# ---- outside the root -------------------------------------------------------------------------------------------------

OUTSIDE = ("rm ../elsewhere.txt", "rm /elsewhere/x.txt", "rm -rf /elsewhere", "rm /nothere/x", "rm ~/x.txt",
           "cd .. && rm elsewhere.txt", "rm a.txt ../elsewhere.txt", "rm -rf ../task2", "del C:/Windows/x.txt",
           "cmd /c del /q ../elsewhere.txt")


@pytest.mark.parametrize("command", OUTSIDE)
def test_a_target_outside_the_root_is_refused_naming_the_owners_terminal(command):
    """A literal target outside the root (`..`, an absolute path, the home folder, another drive) is
    `delete-outside-root`, existing or not; the text names the owner's own terminal and never the list command, which
    refuses it too. Catches: a session that deletes beside its task."""
    decision = judge(command)
    assert reason(decision) == "delete-outside-root"
    assert TERMINAL in decision.verdict.message and LIST_FIX not in decision.verdict.message


def test_a_powershell_target_outside_the_root_is_refused():
    """Catches: a PowerShell delete beside the task."""
    assert reason(judge("Remove-Item ../elsewhere.txt", tool="PowerShell")) == "delete-outside-root"


# ---- wildcards --------------------------------------------------------------------------------------------------------

WILDCARD = ("rm *.txt", "rm d/*", "rm a?.txt", "rm [ab].txt", "rm -r d/**", "rm -rf d/*.txt", "del *.txt",
            "cmd /c del /q d\\*.txt", "rm d/c.*")
WILDCARD_PS = ("Remove-Item *.txt", "Remove-Item d -Include *.txt", "Remove-Item d -Exclude a.txt",
               "Remove-Item d -Filter *.tmp", "ri d\\*")


@pytest.mark.parametrize("command", WILDCARD)
def test_a_wildcard_target_is_refused_naming_the_list_command(command):
    """A `*`, `?` or `[..]` in a target is `delete-wildcard`, naming the list command as the way out. Catches:
    `rm dir/*.txt` running."""
    decision = judge(command)
    assert reason(decision) == "delete-wildcard" and LIST_FIX in decision.verdict.message


@pytest.mark.parametrize("command", WILDCARD_PS)
def test_a_powershell_pattern_is_a_wildcard(command):
    """`-Include`, `-Exclude`, `-Filter` and a wildcard path are wildcards in PowerShell. Catches: a PowerShell pattern
    delete running."""
    assert reason(judge(command, tool="PowerShell")) == "delete-wildcard"


# ---- destructive SQL ---------------------------------------------------------------------------------------------------

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


@pytest.mark.parametrize("command", SQL)
def test_destructive_sql_is_refused_naming_the_profile_key(command):
    """`DROP`, `DELETE FROM` and `TRUNCATE` in a SQL client's arguments or heredoc, or in a Python string given to a SQL
    call, are `delete-sql`, and the text names `delete.sql_allowed`. Catches: SQL that runs through a client."""
    decision = judge(command)
    assert reason(decision) == "delete-sql" and "delete.sql_allowed" in decision.verdict.message


@pytest.mark.parametrize("command", SQL)
def test_destructive_sql_passes_when_the_profile_allows_it(command):
    """The nearest allow: the same command with `delete.sql_allowed: true`. Catches: a profile key that is read and
    ignored."""
    assert reason(judge(command, sql_allowed=True)) == "allow"


@pytest.mark.parametrize("command", SQL_SAFE)
def test_the_sql_words_as_text_or_a_read_are_not_sql(command):
    """The same words in a quoted echo, a read-only program's pattern, a commit message or a plain print, and a `select`,
    are allowed. Catches: the words read as text anywhere, which blocked the owner's own work."""
    assert reason(judge(command)) == "allow"


@pytest.mark.parametrize("sql_allowed, command, expected", (
    (False, "psql -c \"drop table t\"", "delete-sql"), (False, "psql -c \"select 1\"", "allow"),
    (True, "psql -c \"drop table t\"", "allow"), (True, "psql -c \"select 1\"", "allow")))
def test_sql_decision_over_every_combination_of_its_two_facts(sql_allowed, command, expected):
    """The two facts of the SQL decision (the profile allows it, the statement is destructive), all four combinations.
    Catches: a combination that decides wrongly."""
    assert reason(judge(command, sql_allowed=sql_allowed)) == expected


def test_the_profile_switch_turns_off_only_sql():
    """With `sql_allowed` a missing target is still unknown. Catches: a switch that opens every refusal."""
    assert reason(judge("rm nothere.txt", sql_allowed=True)) == "delete-target-unknown"


# ---- the false blocks of the owner's guard -------------------------------------------------------------------------------

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
FALSE_BLOCKS_PS = ("Write-Output 'rm -rf x'", "Get-ChildItem d", "git status",
                   "python mkway/engine/mkway.py delete --list ..\\list.txt")


@pytest.mark.parametrize("command", FALSE_BLOCKS)
def test_a_command_that_only_names_a_remove_word_is_allowed_in_bash(command):
    """A remove word inside a longer word or a file name, in a quoted echo, an assignment, a commit message, a read-only
    program's pattern, a pytest run, a `del` statement in a Python heredoc, `list.remove`, `dict.pop`, and the list
    command with its file inside or outside the root: allowed, nothing to back up. Catches: the guard's false blocks,
    which made the owner stop using it."""
    decision = judge(command)
    assert (reason(decision), decision.order) == ("allow", ())


@pytest.mark.parametrize("command", FALSE_BLOCKS_PS)
def test_a_command_that_only_names_a_remove_word_is_allowed_in_powershell(command):
    """The same in PowerShell. Catches: a false block of a PowerShell read."""
    decision = judge(command, tool="PowerShell")
    assert (reason(decision), decision.order) == ("allow", ())


# ---- the trash commands are the owner's -----------------------------------------------------------------------------------

TRASH = ("python mkway/engine/mkway.py trash list", "python mkway/engine/mkway.py trash empty --older-than 30",
         "python mkway/engine/mkway.py trash empty --older-than 0", "py -3 mkway/engine/mkway.py trash list",
         "cd d && python ../mkway/engine/mkway.py trash list", "echo x && python mkway/engine/mkway.py trash empty",
         "bash -c 'python mkway/engine/mkway.py trash empty --older-than 1'")


@pytest.mark.parametrize("command", TRASH)
def test_a_session_may_not_run_the_trash_commands(command):
    """`mkway trash list` and `mkway trash empty ...` are `owner-only-command` in any spelling, the text naming the
    owner's terminal. Catches: a session that empties its own trash, which would make the backup worthless."""
    decision = judge(command)
    assert reason(decision) == "owner-only-command"
    assert "trash" in decision.verdict.message and "terminal" in decision.verdict.message


@pytest.mark.parametrize("command", ("python mkway/engine/mkway.py delete --list l.txt",
                                     "python mkway/engine/mkway.py card list"))
def test_the_list_command_and_other_engine_commands_are_not_owner_only(command):
    """The nearest allow of `owner-only-command`: the list command, a session's way out. Catches: a gate that blocks its
    own way out."""
    assert reason(judge(command)) == "allow"


# ---- the nearest allow of each refusal reason ---------------------------------------------------------------------------

@pytest.mark.parametrize("command, facts", (
    pytest.param("rm /task/a.txt", {}, id="outside-root: the same file by its absolute path inside the root"),
    pytest.param("rm a.txt", {}, id="wildcard: the literal name"),
    pytest.param("rm a.txt", {}, id="target-unknown: a target that exists"),
    pytest.param("git reset --hard", {"vcs_git": True}, id="uncommitted: a hard reset on a clean tree"),
    pytest.param("git clean -n", {"vcs_git": True}, id="uncommitted: a dry run of clean"),
    pytest.param("git restore --staged src/a.py", {"vcs_git": True, "changed": {"src/a.py": " M"}},
                 id="uncommitted: the index only")))
def test_the_smallest_change_that_flips_each_refusal_is_allowed(command, facts):
    """For each refusal reason the nearest command that passes. Catches: a refusal wider than its rule."""
    assert reason(judge(command, **facts)) == "allow"


# ---- a refused or plain command needs no backup -------------------------------------------------------------------------

NO_BACKUP = ("ls", "echo rm a.txt", "rm a.txt nothere.txt", "rm a.txt ../elsewhere.txt", "rm *.txt", "rm $X",
             "psql -c \"drop table t\"", "python mkway/engine/mkway.py trash list", "git status")


@pytest.mark.parametrize("command", NO_BACKUP)
def test_a_refused_or_plain_command_needs_no_backup(command):
    """A command that is refused for any reason, and a command that deletes nothing, leave nothing to copy and no row.
    Catches: a trash folder that fills with copies of deletes that never ran."""
    assert not core.needs_backup(judge(command))


def test_an_allowed_delete_needs_a_backup():
    """The nearest allow: a delete that passes has targets to copy. Catches: a delete that runs with no backup."""
    assert core.needs_backup(judge("rm a.txt"))


# ---- git: loss of uncommitted work is a delete ----------------------------------------------------------------------------

CLEAN_REFUSED = ("git clean -f", "git clean -fd", "git clean -fdx", "git clean -f -d", "git clean --force",
                 "git clean -d -f -x", "git -C . clean -fd", "echo x && git clean -fdx", "bash -c 'git clean -f'",
                 "git clean -ffd", "git clean -f -- src", "cd src && git clean -f")
CLEAN_ALLOWED = ("git clean -n", "git clean -nd", "git clean --dry-run", "git clean -d", "git clean", "git status")


@pytest.mark.parametrize("vcs_git", (True, False), ids=("vcs-git", "vcs-none"))
@pytest.mark.parametrize("command", CLEAN_REFUSED)
def test_git_clean_with_force_is_refused_whatever_the_vcs_key(command, vcs_git):
    """`git clean` with `-f` or `--force` (alone or in a cluster, any position) is `delete-uncommitted` even on a clean
    tree, and `vcs: none` does not switch it off; the text names the way out. Catches: the quiet loss of every
    untracked file of the task."""
    decision = judge(command, vcs_git=vcs_git)
    assert reason(decision) == "delete-uncommitted"
    assert "git clean" in decision.verdict.message and LIST_FIX in decision.verdict.message


@pytest.mark.parametrize("command", CLEAN_ALLOWED)
def test_a_dry_run_and_a_clean_without_force_pass(command):
    """The nearest allow of a forced clean. Catches: a gate that blocks every `git clean`."""
    assert reason(judge(command, vcs_git=True)) == "allow"


RESET_REFUSED = ("git reset --hard", "git reset --hard HEAD", "git reset -q --hard origin/x", "git -C . reset --hard",
                 "true && git reset --hard")
RESET_ALLOWED = ("git reset --soft HEAD~1", "git reset --mixed", "git reset", "git reset HEAD src/a.py")


@pytest.mark.parametrize("code", (" M", "M "), ids=("unstaged", "staged"))
@pytest.mark.parametrize("command", RESET_REFUSED)
def test_a_hard_reset_is_refused_when_a_tracked_file_has_a_change(command, code):
    """`git reset --hard` is `delete-uncommitted` when a tracked file has a staged or an unstaged change; the text names
    the file. Catches: a hard reset that throws away work."""
    decision = judge(command, vcs_git=True, changed={"src/a.py": code})
    assert reason(decision) == "delete-uncommitted" and "src/a.py" in decision.verdict.message


@pytest.mark.parametrize("command", RESET_ALLOWED)
def test_a_soft_or_mixed_reset_never_loses_work(command):
    """`--soft`, `--mixed` and a plain reset pass although a tracked file has a change. Catches: a gate that blocks every
    reset."""
    assert reason(judge(command, vcs_git=True, changed={"src/a.py": " M"})) == "allow"


RESTORE_REFUSED = ("git restore src/a.py", "git restore -- src/a.py", "git checkout -- src/a.py",
                   "git checkout HEAD -- src/a.py", "git restore --source=HEAD src/a.py", "git restore .",
                   "git checkout -- .", "git checkout .", "git restore src", "git restore --staged --worktree src/a.py",
                   "git restore -W src/a.py", "git restore src/clean.py src/a.py", "cd src && git restore a.py")
RESTORE_ALLOWED = ("git restore src/clean.py", "git checkout -- src/clean.py", "git checkout HEAD -- src/clean.py",
                   "git restore --staged src/a.py", "git restore -S src/a.py", "git checkout main",
                   "git checkout -b topic", "git checkout", "git restore --help")


@pytest.mark.parametrize("command", RESTORE_REFUSED)
def test_restore_and_checkout_of_a_changed_path_are_refused(command):
    """`git restore <path>` and `git checkout -- <path>` (also with a tree, `--source`, `.`, a folder, the worktree
    switch) are `delete-uncommitted` when the path has a change; the text names the file. Catches: a revert that throws
    away work."""
    decision = judge(command, vcs_git=True, changed={"src/a.py": " M"})
    assert reason(decision) == "delete-uncommitted" and "src/a.py" in decision.verdict.message


@pytest.mark.parametrize("command", RESTORE_ALLOWED)
def test_restore_and_checkout_of_a_clean_path_pass(command):
    """A clean path, `restore --staged` (the index only) and a branch switch pass. Catches: false blocks of a harmless
    restore."""
    assert reason(judge(command, vcs_git=True, changed={"src/a.py": " M"})) == "allow"


@pytest.mark.parametrize("code", (" D", "D "), ids=("unstaged-deletion", "staged-deletion"))
@pytest.mark.parametrize("command", ("git restore src/clean.py", "git checkout -- src/clean.py"))
def test_a_path_deleted_from_the_tree_has_nothing_to_lose(command, code):
    """A deletion is no work to lose, so restoring the path passes. Catches: a refusal to bring a deleted file back."""
    assert reason(judge(command, vcs_git=True, changed={"src/clean.py": code})) == "allow"


@pytest.mark.parametrize("command, expected", (("git restore ../x", "delete-outside-root"),
                                               ("git restore 'src/*.py'", "delete-wildcard"),
                                               ("git restore $F", "delete-target-unknown")))
def test_a_git_path_keeps_its_own_reason(command, expected):
    """A path outside the root, a wildcard and a computed path keep their own reasons in a git form. Catches: a git form
    that skips the path checks."""
    assert reason(judge(command, vcs_git=True)) == expected


GIT_RM_REFUSED = ("git rm src/a.py", "git rm -f src/a.py", "git rm -rf src", "git rm -r src", "git rm --force src/a.py",
                  "git rm src/clean.py src/a.py", "git rm -- src/a.py")


@pytest.mark.parametrize("code", (" M", "M "), ids=("unstaged", "staged"))
@pytest.mark.parametrize("command", GIT_RM_REFUSED)
def test_git_rm_of_a_changed_file_is_refused(command, code):
    """`git rm` of a path with a staged or an unstaged change (also `-f`, and a folder that holds one) is
    `delete-uncommitted`; the text names the file. Catches: a `git rm` that loses a change."""
    decision = judge(command, vcs_git=True, changed={"src/a.py": code}, tracked={"src/a.py", "src/clean.py"})
    assert reason(decision) == "delete-uncommitted" and "src/a.py" in decision.verdict.message


@pytest.mark.parametrize("command, expected", (("git rm 'lib/*.py'", "delete-wildcard"),
                                               ("git rm ../x.py", "delete-outside-root"),
                                               ("git rm $F", "delete-target-unknown"),
                                               ("git rm -rf mkway/state", "delete-target-unknown")))
def test_git_rm_keeps_the_reasons_of_a_bad_path(command, expected):
    """A wildcard, a path outside the root, a computed one and the state folder keep their own reasons. Catches: a
    `git rm` that deletes the state folder."""
    assert reason(judge(command, vcs_git=True, changed={"src/a.py": " M"})) == expected


@pytest.mark.parametrize("command", ("git rm --cached src/a.py", "git rm -n lib/x.py", "git rm --dry-run lib/x.py",
                                     "git rm new.txt"))
def test_a_git_rm_that_is_no_delete_leaves_no_row(command):
    """`--cached`, a dry run and an untracked path are not deletes git keeps: nothing is recorded. Catches: a record row
    for a command that deleted nothing."""
    decision = judge(command, vcs_git=True, tracked={"lib/x.py"}, changed={"src/a.py": " M"})
    assert (reason(decision), decision.order, decision.kept) == ("allow", (), ())


@pytest.mark.parametrize("command, rel", (("git rm lib/x.py", "lib/x.py"), ("git rm -r lib", "lib")))
def test_git_rm_of_a_clean_tracked_path_is_kept_by_git_and_recorded(command, rel):
    """A clean tracked file or folder is allowed with one row and no copy: it is `kept`, never a target. Catches: a
    `git rm` that is backed up needlessly, or that has no record."""
    decision = judge(command, vcs_git=True, tracked={"lib/x.py"})
    assert (reason(decision), decision.kept, decision.targets, decision.order) == ("allow", (rel,), (), (rel,))


def test_one_row_covers_a_command_that_also_deletes_files():
    """`rm tmp.txt && git rm lib/x.py` copies the file and keeps the tracked one, in command order. Catches: a row that
    loses one of the two deletes."""
    decision = judge("rm tmp.txt && git rm lib/x.py", vcs_git=True, tracked={"lib/x.py"},
                     files=world.FILES | {"tmp.txt"})
    assert (decision.targets, decision.kept, decision.order) == (("tmp.txt",), ("lib/x.py",), ("tmp.txt", "lib/x.py"))


@pytest.mark.parametrize("failure", ("did not answer (TimeoutExpired)", "exited 128"))
@pytest.mark.parametrize("command", ("git reset --hard", "git restore src/a.py", "git rm src/clean.py"))
def test_a_git_read_that_fails_refuses_the_delete(command, failure):
    """A git read that does not answer (a timeout, a non-zero exit) is `delete-uncommitted` with the reason in the text,
    never an allow. Catches: a gate that lets a hard reset through because git was slow."""
    decision = judge(command, vcs_git=True, changed={"src/a.py": " M"}, git_failure=failure)
    assert reason(decision) == "delete-uncommitted"
    assert failure in decision.verdict.message and "could not be read" in decision.verdict.message


# git `rm src/a.py`: four facts (the profile reads git, git answers, the file has a change, git tracks it): all sixteen.
# The rule: no git key reads nothing, so it passes; a git that fails refuses; a change refuses; a clean tracked file is
# kept by git (recorded, not copied); an untracked clean file is no git delete at all.
GIT_RM_TABLE = (
    (False, False, False, False, "allow", ()), (False, False, False, True, "allow", ()),
    (False, False, True, False, "allow", ()), (False, False, True, True, "allow", ()),
    (False, True, False, False, "allow", ()), (False, True, False, True, "allow", ()),
    (False, True, True, False, "allow", ()), (False, True, True, True, "allow", ()),
    (True, True, False, False, "delete-uncommitted", ()), (True, True, False, True, "delete-uncommitted", ()),
    (True, True, True, False, "delete-uncommitted", ()), (True, True, True, True, "delete-uncommitted", ()),
    (True, False, True, False, "delete-uncommitted", ()), (True, False, True, True, "delete-uncommitted", ()),
    (True, False, False, False, "allow", ()), (True, False, False, True, "allow", ("src/a.py",)))


@pytest.mark.parametrize("vcs_git, fails, changed, tracked, expected, kept", GIT_RM_TABLE)
def test_git_rm_over_every_combination_of_its_four_facts(vcs_git, fails, changed, tracked, expected, kept):
    """Columns: the profile reads git, git fails, the file has a change, git tracks the file. Catches: a combination of
    facts that decides against the rule."""
    decision = judge("git rm src/a.py", vcs_git=vcs_git, git_failure="exited 128" if fails else None,
                     changed={"src/a.py": " M"} if changed else {}, tracked={"src/a.py"} if tracked else set())
    assert (reason(decision), decision.kept) == (expected, kept)


# git `restore` and `reset --hard`: three facts (the profile reads git, git fails, the tracked file has a change): all eight.
GIT_RESTORE_TABLE = ((False, False, False, "allow"), (False, False, True, "allow"), (False, True, False, "allow"),
                     (False, True, True, "allow"), (True, True, False, "delete-uncommitted"),
                     (True, True, True, "delete-uncommitted"), (True, False, True, "delete-uncommitted"),
                     (True, False, False, "allow"))


@pytest.mark.parametrize("command", ("git restore src/a.py", "git reset --hard"))
@pytest.mark.parametrize("vcs_git, fails, changed, expected", GIT_RESTORE_TABLE)
def test_a_git_revert_over_every_combination_of_its_three_facts(command, vcs_git, fails, changed, expected):
    """Columns: the profile reads git, git fails, the file has a change. Catches: a combination of facts that decides
    against the rule."""
    decision = judge(command, vcs_git=vcs_git, git_failure="exited 128" if fails else None,
                     changed={"src/a.py": " M"} if changed else {})
    assert reason(decision) == expected


# ---- the size limit -----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("total, max_mb", ((MIB + 1, 1), (MIB // 2 + 1, 0.5), (5120 * MIB + 1, 5120)))
def test_a_backup_above_the_limit_is_refused(total, max_mb):
    """A total above `delete.max_backup_mb` is `delete-too-large`. Catches: a delete of a big tree that fills the
    disk."""
    verdict = core.too_large(total, max_mb, ["big.bin"])
    assert (verdict.kind, verdict.reason) == ("refuse", "delete-too-large")


@pytest.mark.parametrize("total, max_mb", ((MIB, 1), (MIB // 2, 0.5), (0, 1), (5 * MIB, 5120)))
def test_a_backup_up_to_the_limit_passes(total, max_mb):
    """The nearest allow: a size exactly at the limit, or below, passes. Catches: a limit read as a count of files or
    one that refuses at the limit."""
    assert core.too_large(total, max_mb, ["x"]) is None


def test_the_size_refusal_names_the_targets_the_limit_and_the_owners_terminal():
    """Catches: a refusal that does not say which delete is too big or where to go."""
    message = core.too_large(MIB + 1, 1, ["big.bin", "a.txt"]).message
    assert "big.bin, a.txt" in message and "(1)" in message and "delete.max_backup_mb" in message
    assert "needs the owner's terminal" in message


# ---- what is copied and what is recorded ---------------------------------------------------------------------------------

@pytest.mark.parametrize("rels, expected", (
    (["d", "a.txt", "d/b.txt", "d/sub/x.txt", "dd/y.txt"], ["d", "a.txt", "dd/y.txt"]),
    (["d/b.txt", "d"], ["d"]), (["a.txt", "b.txt"], ["a.txt", "b.txt"]), ([], [])))
def test_a_target_inside_another_target_is_copied_with_it(rels, expected):
    """Copying `d` copies `d/b.txt` too, so the inner target is not copied twice; a folder whose name only starts with
    the same letters is not inside it. Catches: a copy that doubles files or skips `dd`."""
    assert core.outermost(rels) == expected


def test_the_record_row_names_time_session_via_targets_and_backup():
    """The row has the time, the session, `via`, the targets in command order and the backup folder, and no `by`.
    Catches: a delete with no trace of who made it."""
    row = core.record_row("2026-11-12T01:02:03.004+00:00", "s1", "gate", ("d", "a.txt"), "mkway/state/trash/x")
    assert row == {"time": "2026-11-12T01:02:03.004+00:00", "session": "s1", "via": "gate", "targets": ["d", "a.txt"],
                   "backup": "mkway/state/trash/x"}


def test_the_record_row_of_a_command_names_who_ran_it():
    """The commands know no session id, so `session` is null and `by` says who. Catches: a list delete with no author."""
    row = core.record_row("t", None, "list", ["a.txt"], None, by="owner")
    assert (row["session"], row["backup"], row["by"], row["via"]) == (None, None, "owner", "list")


# ---- the lines of a list file -----------------------------------------------------------------------------------------------

LOCKS = {"frozen/f.txt": ("frozen", None), "frozen": (None, ("frozen", "frozen/f.txt"))}
LIST_FILES = world.FILES | {"frozen", "frozen/f.txt"}


def _list(text):
    facts = core.Facts(state=world.STATE)
    for _ in range(100):
        try:
            return core.list_problems(text, facts)
        except core.Need as need:
            if need.kind == "lnorm":
                answer = world.norm(need.key)
            elif need.kind == "lexists":
                answer = need.key in LIST_FILES
            elif need.kind == "locks":
                answer = LOCKS.get(need.key, (None, None))
            else:
                raise AssertionError(need.kind)
            facts.answers[(need.kind, need.key)] = answer
    raise AssertionError("the core kept asking")


@pytest.mark.parametrize("text, rels", (
    ("a.txt\r\n", ["a.txt"]), ("  d  \r\n", ["d"]), ("./b.txt\n", ["b.txt"]), ("/task/a.txt\n", ["a.txt"]),
    ("a.txt\na.txt\n", ["a.txt"]), ("a.txt\r\n\r\nd/b.txt\n", ["a.txt", "d/b.txt"])))
def test_a_good_list_gives_the_exact_repo_paths_once(text, rels):
    """CRLF, blank lines, spaces, `./`, an absolute path inside the root and a path twice give the exact repo paths in
    order, each once, and no problem. Catches: a list the command cannot read, or a path deleted twice."""
    assert _list(text) == (rels, [])


@pytest.mark.parametrize("line, problem", (
    ("nothere.txt", "line 1: nothere.txt does not exist"),
    ("../elsewhere.txt", "line 1: ../elsewhere.txt lies outside the root"),
    ("d/*.txt", "line 1: d/*.txt is a wildcard: list exact paths"),
    ("frozen/f.txt", "line 1: frozen/f.txt is inside the closed lock 'frozen'"),
    ("frozen", "line 1: frozen holds frozen/f.txt, which is inside the closed lock 'frozen'"),
    ("mkway/state", "line 1: mkway/state is or holds the engine's state folder"),
    ("mkway", "line 1: mkway is or holds the engine's state folder"),
    (".", "line 1: . is the root itself")))
def test_a_bad_line_is_a_problem_with_its_number_and_its_reason(line, problem):
    """A line that does not exist, lies outside the root, holds a wildcard, lies in or holds a closed lock, is or holds
    the state folder or is the root is a problem naming the line number, the line and the reason. Catches: a list that
    deletes what the gate would refuse."""
    assert _list(line + "\n")[1] == [problem]


def test_the_good_lines_stay_listed_beside_a_bad_one():
    """The line numbers count every line; the good lines are still listed (the command deletes nothing while any problem
    exists). Catches: a problem named with the wrong line number."""
    assert _list("a.txt\nnothere.txt\nb.txt\n") == (["a.txt", "b.txt"], ["line 2: nothere.txt does not exist"])


@pytest.mark.parametrize("text", ("", "\n  \n", "   \r\n"))
def test_an_empty_list_is_a_problem(text):
    """A list with no path is an error, not a no-op. Catches: a list command that reports success having done nothing."""
    assert _list(text) == ([], ["the list holds no path"])


# ---- which trash folders the owner's empty removes ---------------------------------------------------------------------------

def _stamp(seconds_before_now, micro=0):
    """The folder name the engine would have made `seconds_before_now` before NOW (a stamp is UTC)."""
    p = time.gmtime(NOW - seconds_before_now)
    return f"{p.tm_year:04d}{p.tm_mon:02d}{p.tm_mday:02d}T{p.tm_hour:02d}{p.tm_min:02d}{p.tm_sec:02d}-{micro:06d}"


@pytest.mark.parametrize("name, days", (
    ("20200101T000000-000000", 30), (_stamp(30 * DAY + 1), 30), (_stamp(3600), 0), (_stamp(1), 0),
    ("20200101T000000-000000-2", 1)))
def test_a_folder_older_than_the_days_by_its_stamp_is_removed(name, days):
    """A folder is removed when the stamp in its name is strictly older than the days; `--older-than 0` removes all; a
    collision suffix (`-2`) is part of the stamp. Catches: a trash that is never emptied."""
    assert core.stale_folders([name], NOW, days) == [name]


@pytest.mark.parametrize("name, days", ((_stamp(3600), 30), (_stamp(30 * DAY), 30), (_stamp(29 * DAY), 30)))
def test_a_folder_not_older_than_the_days_stays(name, days):
    """The nearest allow: a fresh folder, and one exactly as old as the limit, stay. Catches: a backup emptied before its
    time."""
    assert core.stale_folders([name], NOW, days) == []


@pytest.mark.parametrize("name", ("notes", "2020", "20200101", "20200101T000000", "x20200101T000000-000000", ""))
def test_a_name_that_is_no_stamp_is_never_removed(name):
    """Only the exact stamp form is the engine's own folder. Catches: the owner's own folder in the trash removed."""
    assert core.stale_folders([name], NOW, 0) == []


def test_the_folders_to_remove_keep_the_order_given():
    """Catches: a freed-size report that lists the folders in another order than they were removed."""
    fresh, old = _stamp(3600), "20200101T000000-000000"
    assert core.stale_folders([fresh, "notes", old], NOW, 0) == [fresh, old]


# ---- the guard: the core reads no disk, no git, no clock ---------------------------------------------------------------------

@pytest.mark.parametrize("command, facts, expected", (
    ("rm -rf d a.txt", {}, "allow"),
    ("git reset --hard", {"vcs_git": True, "changed": {"src/a.py": " M"}}, "delete-uncommitted"),
    ("psql -c \"drop table t\"", {}, "delete-sql")))
def test_deciding_touches_no_disk_no_process_and_no_clock(monkeypatch, command, facts, expected):
    """With every disk and process entry point made to fail, a table decision still works (the static proof is
    `test_core_delete_is_pure.py`). Catches: a core that reads the disk or runs git itself."""
    touched = []

    def spy(name):
        def boom(*_a, **_k):
            touched.append(name)
            raise OSError(f"the core touched {name}")
        return boom
    with monkeypatch.context() as patched:  # undone before pytest reads a failure: it needs the disk itself
        for name in ("stat", "lstat", "listdir", "scandir"):
            patched.setattr(os, name, spy(f"os.{name}"))
        patched.setattr(subprocess, "Popen", spy("subprocess.Popen"))
        patched.setattr(builtins, "open", spy("open"))
        result = reason(judge(command, **facts))
    assert (touched, result) == ([], expected)
