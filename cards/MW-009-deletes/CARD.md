# MW-009: deletes: explicit, backed up, logged

| | |
|---|---|
| **Appetite** | 2.5 hours — from 2026-11-10 |
| **Status** | proposed |
| **Created / updated** | 2026-11-10 / 2026-11-10 |
| **Waiting for** | nothing |
| **Form** | card |
| **Decisions** | none new: the rules are the owner's order of 2026-11-10; each reading of the order is a Log line |
| **Canon** | none for the delete gate: the engine has no ledger; the basis is the order of 2026-11-10 |
| **Paths** | `engine/`, `tests/`, `README.md`, `cards/REGISTER.md`, `cards/MW-009-deletes/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; `card new` cannot run here (the engine repository has no
profile of its own), so the card and its register row are written by hand; the register row is `proposed`, and the
owner's terminal opens and closes it.

## 1. Goal

«deletes: explicit, backed up, logged» — owner's order, 2026-11-10.
Basis, figures of a source task: 336 deletes in 42,322 tool calls; 223 blocked and 124 backed up since 23.10. The
engine gets a delete gate (shell group, `onFailure: block`): a delete runs only when every target is a literal path
inside the root that exists; it is backed up first into `<state.dir>/trash/<timestamp>/` and one record row is
written; a wildcard, a target outside the root, SQL and loss of uncommitted work are refused with their own reason;
`mkway delete --list <file>` is the way out for many files; the trash is emptied only by the owner.

## Acceptance examples

Rows are added with the red tests of each part.

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | `delete` keys in the schema | no such key: the profile is invalid | `max_backup_mb` (a number above 0), `sql_allowed` (a boolean); an unknown key is invalid | tests/test_mw009_keys.py::test_delete_keys_are_in_the_schema |
| E2 | defaults and overrides | none | no `delete`: 5120 MB and SQL not allowed; a profile value replaces it; an unusable value falls back | tests/test_mw009_keys.py::test_delete_defaults_and_overrides |
| E3 | KEYS.md lines | none | two «in schema now» lines in «Added keys», each with its default | tests/test_mw009_keys.py::test_delete_keys_are_lines_of_keys_md_with_their_defaults; tests/test_keys.py::test_keys_md_has_one_line_per_draft_key |
| E4 | literal existing targets | none | a delete of literal paths inside the root that exist is allowed in every plain spelling | tests/test_mw009_reader.py::test_literal_existing_targets_inside_the_root_pass |
| E5 | every delete form | none | rm, rmdir, unlink, del, erase, rd, find -delete, find -exec rm, Python removal calls, Remove-Item and aliases are read; a missing target is `delete-target-unknown` | tests/test_mw009_reader.py::test_every_delete_form_is_read |
| E6 | every position | none | the same delete is refused alone, in chains, substitutions, behind shells, cmd, pwsh and xargs | tests/test_mw009_reader.py::test_a_delete_is_refused_in_every_position |
| E7 | computed and broad targets | none | variable, substitution, unknown parameter, splat, state folder and root are `delete-target-unknown` with the list command named | tests/test_mw009_reader.py::test_computed_and_broad_targets_are_unknown |
| E8 | outside the root | none | `delete-outside-root`, the owner's own terminal named | tests/test_mw009_reader.py::test_a_target_outside_the_root_is_always_refused |
| E9 | wildcard | none | `delete-wildcard`, the list command named; `-Include`, `-Exclude`, `-Filter` count | tests/test_mw009_reader.py::test_a_wildcard_is_refused |
| E10 | SQL | none | `delete-sql` unless `delete.sql_allowed`; the words in text are not SQL | tests/test_mw009_reader.py::test_destructive_sql_is_refused_unless_the_profile_allows_it |
| E11 | false blocks | the owner's guard blocks them | the cases of the owner's guard log pass, the list command included | tests/test_mw009_reader.py::test_the_false_blocks_of_the_owners_guard_pass |
| E12 | trash commands | none | `mkway trash list` and `empty` are `owner-only-command` for a session | tests/test_mw009_reader.py::test_trash_commands_are_the_owners |
| E13 | odd input | none | a non-shell tool or a non-text command is allowed, never a crash | tests/test_mw009_reader.py::test_a_non_shell_tool_and_odd_input_are_allowed |
| E14 | manifest entry | none | entry `delete`, shell group, `onFailure: block`, eight reason ids, after `commit_files` | tests/test_mw009_reader.py::test_the_manifest_has_the_delete_gate_after_the_commit_gate; tests/test_manifest.py |
| E15 | backup and record | a delete leaves no copy and no trace | every target is copied into `<state.dir>/trash/<timestamp>/<repo path>` before the tool runs; one row in `<state.dir>/deletes.jsonl` (session, time, targets, backup folder) | tests/test_mw009_backup.py::test_a_delete_is_copied_into_the_trash_and_recorded |
| E16 | paths kept | none | an empty folder and a nested file keep their repo path; a target named twice is copied once | tests/test_mw009_backup.py::test_an_empty_folder_and_a_nested_file_keep_their_path |
| E17 | size limit | none | above `delete.max_backup_mb` = `delete-too-large`, «needs the owner's terminal», no copy, no row; exactly at the limit passes | tests/test_mw009_backup.py::test_a_backup_above_the_limit_is_refused |
| E18 | backup failure | none | a failed copy, trash folder or record row = `delete-backup-failed`, the delete is refused | tests/test_mw009_backup.py::test_a_failed_copy_or_record_refuses_the_delete |
| E19 | no trash for a refusal | none | a refused or non-delete command copies nothing and writes no row | tests/test_mw009_backup.py::test_a_refused_or_plain_command_leaves_no_trash |
| E20 | fail closed | none | a crash in the gate is `gate-error` and blocks the call | tests/test_mw009_backup.py::test_a_crash_in_the_gate_blocks_the_delete |
| E21 | git clean | none | `git clean` with force is `delete-uncommitted` on any tree and with `vcs: none`; a dry run and a clean without force pass | tests/test_mw009_git.py::test_git_clean_with_force_is_refused |
| E22 | git reset --hard | none | refused when a tracked file has a staged or unstaged change, allowed on a clean tree and with only untracked files | tests/test_mw009_git.py::test_git_reset_hard_is_refused_only_when_the_tree_has_changes |
| E23 | git restore and checkout | none | `delete-uncommitted` for a path with a change; a clean path, a path deleted from the tree, `--staged` and a branch switch pass | tests/test_mw009_git.py::test_restore_and_checkout_of_a_changed_path_are_refused |
| E24 | git rm | none | a changed file is `delete-uncommitted`; a clean tracked file is allowed with one record row and no copy; `--cached` and `-n` are no deletes | tests/test_mw009_git.py::test_git_rm_of_a_changed_file_is_refused_and_a_clean_one_is_recorded |
| E25 | git read fails | none | a timeout or a git error is `delete-uncommitted`, never an allow | tests/test_mw009_git.py::test_a_git_read_that_fails_refuses_the_delete |
| E26 | list command | wildcards and big deletes have no way out | `mkway delete --list <file>` (a session's command, the list file anywhere) backs up, deletes and writes one row, `via: list` | tests/test_mw009_commands.py::test_the_list_command_backs_up_deletes_and_records |
| E27 | bad lines | none | any bad line (missing, outside, wildcard, closed lock, state folder, root, empty list) deletes nothing and is named by number | tests/test_mw009_commands.py::test_one_bad_line_deletes_nothing |
| E28 | list size limit | none | above `delete.max_backup_mb` nothing is deleted, «needs the owner's terminal» | tests/test_mw009_commands.py::test_the_list_command_respects_the_size_limit |
| E29 | gate and commands | the owner's guard blocks its own list script | the gate passes the list command and refuses `trash list` and `trash empty` | tests/test_mw009_commands.py::test_the_gate_lets_the_list_command_through_and_stops_the_trash_commands |
| E30 | trash commands | none | `trash list` and `trash empty --older-than <days>` are owner-only; the engine never empties the trash itself | tests/test_mw009_commands.py::test_the_trash_commands_are_the_owners |
| E31 | README section | no section on deletes | one section `## Deletes` with a body | tests/test_mw009_readme.py::test_the_readme_has_one_section_deletes |
| E32 | the section's content | none | every reason id, both keys with defaults, the folders and files, the commands, the tripwire and the limits are named; ids and keys are read from the manifest and the schema | tests/test_mw009_readme.py::test_the_section_states_the_rules_reasons_keys_commands_and_limits |
| E33 | start line | none | the gate is on `gates on:`; with `gates.delete.on: false` it is on `gates off:` | tests/test_mw009_readme.py::test_the_start_line_names_the_delete_gate_on_and_off |

## 8. Log

One line per step. No re-run of a check or an agent round without a new input named in the Log row.

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-10 | W0 | (this commit) | card and register row written by hand. Start checks, each alone: `pwd` = the worktree root, HEAD 549cce1, `git status --short` empty. Baseline full suite at 549cce1: 396 passed (550 s) |
| 2026-11-10 | P1 keys | red ea2f859, green (this commit) | rows E1 E2 E3: schema group `delete`, `profiles.delete_settings`, two KEYS lines. Targeted files green (15 passed); full suite is run once at the end |
| 2026-11-10 | P2 reader | red 1cbfcd7, green (this commit) | rows E4 to E14: `engine/gate_delete.py`, manifest entry `delete`. Readings taken: `find -delete` and `xargs rm` are `delete-target-unknown`; a PowerShell encoded command is not entered (known limit: an opaque text); a missing literal target, the state folder, the root and any folder that holds or lies in the state folder are `delete-target-unknown`; `cmd /c` text is read with `/s /q`-style options; a PowerShell `-Include`, `-Exclude`, `-Filter` is a wildcard; SQL is read in a SQL client's arguments, heredoc and piped text and in Python strings passed to `execute`, `executemany`, `executescript`, `sql`, `read_sql`; SQL read from a file or stdin is a known limit; backtick substitutions are read outside single quotes. Targeted files green: 124 passed (install and dispatch tests included, 399 s) |
| 2026-11-10 | P3 backup | red a4aab23, green (this commit) | rows E15 to E20: `engine/trash.py`, the gate calls it after a clean read. Readings taken: the folder name is `<UTC date>T<time>-<microseconds>`, a clash adds `-2`; the limit is on the total bytes of all targets and a size equal to the limit passes; a target inside another target is copied once; the record row has `via` (`gate` here, `list` for the list command) and `backup` as a repo path; a partial copy of a failed backup stays in the trash (the engine never deletes there). The state folder needs no skip in the copy: a target that holds it is refused by P2. Targeted files green (reader and backup tests, 17 passed) |
| 2026-11-10 | P4 uncommitted work | red 86e92b9, green (this commit) | rows E21 to E25: the git forms in `engine/gate_delete.py`, the record-only path in `engine/trash.py`. Readings taken: `git clean` with force is refused on any tree and with `vcs: none` (untracked files are in no commit), a dry run passes; the other git forms are read only with `vcs: git`; a change that is only a deletion (` D`, `D `) is no work to lose; a staged change counts as a change for `restore`, `checkout --` and `rm`; `git checkout` reads paths only after `--` or a lone `.`; `git restore --staged` and `git rm --cached` are not deletes; a wildcard, outside or computed path in a git form keeps its own reason; an untracked path of `git rm` leaves no row; `git checkout -f`, `git switch --discard-changes` and `git stash` are not read (known limit for the README). A git read that fails or times out is `delete-uncommitted`. Targeted files green (reader, backup and git tests, 22 passed) |
| 2026-11-10 | P5 commands | red 77e0a06, green (this commit) | rows E26 to E30: `mkway delete --list <file>`, `mkway trash list`, `mkway trash empty --older-than <days>` in `engine/mkway.py`, the logic in `engine/trash.py`. Readings taken: the CLI knows no session id, so a list-command row has `session: null` and `by: session` or `owner` (the session id stays «not established» for commands); the list file is read as UTF-8 with or without a BOM and may lie anywhere; a list line is an exact path (a `*`, `?` or `[` is a bad line, a `$` is a literal); relative lines are read from the root; the list command is limited by `delete.max_backup_mb` and copies a git-tracked clean file too; a trash folder is aged by the stamp in its name and a folder with no stamp is never touched; `--older-than 0` empties everything; each empty writes one row `via: trash-empty`. Row E29 was already green at the red commit, because P2 had made the gate pass the list command and refuse `trash`; it stays as the pipeline test. Targeted files green (27 passed; cli, lock, card and e2e tests 61 passed) |
| 2026-11-10 | P6 text | red bf19a1d, green (this commit) | rows E31 to E33: README section «Deletes» (reason ids and keys checked against the manifest and the schema), the KEYS lines of P1. Row E33 (the start line names the gate on and off) was already green at the red commit, because the start line follows the manifest entry; it stays as the test of `gates.delete.on: false`. Known limits written in the README: SQL from a file or stdin, an encoded command, `git checkout -f`, `git switch --discard-changes`, `git stash`, a script file's own removal calls. Targeted files green (README, term scan and repo scan tests, 21 passed) |
| 2026-11-10 | END | (this commit) | full suite `python -m pytest` at f9b8b61: 429 passed in 542 s (396 baseline + 33 new tests); every row E1 to E33 has its test node; the term scan is part of the suite. Parts: P1 ea2f859 / 875d16e, P2 1cbfcd7 / d975d3d, P3 a4aab23 / 9dd7ee6, P4 86e92b9 / 7149a9f, P5 77e0a06 / 535d6fc, P6 bf19a1d / f9b8b61. Not done here: the card status stays `proposed` (the owner's terminal opens and closes it); `delete.generated_state` stays «later» |
| 2026-11-10 | PORT | source 549cce1..693b0b1, port (this commit) | port of t7 onto master a98a20b, by editing files: the shared files keep master's content (MW-005, MW-008, MW-010) and gain the MW-009 content; the manifest entry `delete` sits after `commit_files` and before `commit_tests`; no test weakened; one extension: the exact shell-group list in `tests/test_mw005_gate.py` now names `delete`. Full suite `python -m pytest` before the commit: 493 passed in 675 s, the term scan included |

### Resume

State when the first session was stopped (owner: lower effort). Nothing but this card is committed yet; no code and
no test of MW-009 exists. Rules below are the order, rule numbers 1 to 10.

**Parts planned** (red commit with tests and the card rows, then green commit with code and the Log rows; commit
messages without parentheses and naming the rows; a red commit is not run through the full suite, a green one is;
the full suite takes about 9 minutes, run it once per green commit at most):
1. P1 keys: schema group `delete` with `max_backup_mb` (number above 0, default 5120) and `sql_allowed` (boolean,
   default false); `profiles.delete_settings(profile)` with constants beside `owner_ask` (a bad value takes the
   default); two «in schema now» lines in KEYS.md «Added keys»; extend `tests/test_schema.py` (set of groups) and
   `tests/test_keys.py` (set of added keys) as MW-007 did (extension only). `delete.generated_state` stays «later».
2. P2 reader and refusals (rules 1, 3, 5, 6, 8): `engine/gate_delete.py`, function `check`, manifest entry
   `delete` (gate `delete`, group `shell`, event PreToolUse, matcher `Bash|PowerShell`, `onFailure: block`, an
   `on_failure_reason`, placed after `commit_files`; extend `ON` in `tests/test_manifest.py`). Reasons:
   `delete-target-unknown`, `delete-too-large`, `delete-backup-failed`, `delete-wildcard`, `delete-outside-root`,
   `delete-sql`, `delete-uncommitted`, `owner-only-command` (for `mkway trash ...`, refused in the gate itself so
   `gate_lock.py` is not touched).
3. P3 backup and record (rule 2): `engine/trash.py`: copy every target into `<state>/trash/<timestamp>/<repo
   path>`, size check against `delete.max_backup_mb`, one row in `<state>/deletes.jsonl` (session, time, targets,
   backup folder), copy or record failure = `delete-backup-failed`. The copy must skip the state folder (it sits
   inside the root).
4. P4 uncommitted work (rule 7): `git clean -f`, `git reset --hard`, `git restore` and `git checkout --` on a path
   with changes, `git rm` of a changed file = `delete-uncommitted`; `git rm` of a clean tracked file = allowed with a
   record row and no copy (git keeps it). Read the changes with `runner.git` (`status --porcelain -- <path>`).
5. P5 commands (rules 4, 9): `mkway delete --list <file>` (session command, the gate never refuses it) and
   `mkway trash list`, `mkway trash empty --older-than <days>` (owner-only: `_owner_only` in `engine/mkway.py`, the
   CLAUDECODE tripwire, as for `lock`).
6. P6 text (rule 10): README section «Deletes» (README tests use the `engine_repo` marker; read reason ids from the
   manifest as `tests/test_mw007_readme.py` does), KEYS lines, `gates on` and `gates off` of the start line name the
   gate (it follows from the manifest entry; test it, including `gates.delete.on: false`). Then the END row: full
   suite, every row covered, HEAD.
Report to the retro session one line per part, and at the end HEAD and the suite count.

**Done:** W0 (this commit), baseline 396 passed. **In progress:** P1, next step: write
`tests/test_mw009_keys.py` (schema, defaults and overrides, KEYS lines), add rows E1 to E3 to the Acceptance table,
commit red.

**How the engine is wired (read, so a new session need not re-read it):** a gate is `check(event, ctx)` returning
`gate.allow()`, `gate.refuse(reason_id, text)` or `gate.warn`; tests call it with `_engine.gate_call(function,
root, tool="Bash", tool_input={"command": ...})` on `_engine.task_root(tmp_path, vcs="git")`, and git fixtures are in
`tests/_commit_fixture.py` (`make_task`, `work`, `save`). The shell reader is `engine/helpers.py`: `parse(cmd,
shell)` gives `Simple` objects (`words`, `redirects`, `heredocs`, `subs`), `expand_vars` and `folder_track` give the
folder each command runs in, `_argv` and `_prog` strip wrappers (`env`, `timeout`, `nice`), `norm(path, root, ...)`
gives a repo path or None outside the root (`ctx.norm`), `python_code_writes` shows how a Python body is read with
`ast`, `_ps_param` and `_PS_SWITCHES` normalise PowerShell parameters. `locks.closed_target(root, profile, rel,
profile_file)` is the closed-lock test. State folder is `profiles.state_dir`; it is ignored by git and is a lock
target that is never open, so a session's own `rm` inside it is already refused by the lock gate. Log rows go
through `logs.append_jsonl`. The dispatcher runs gates in manifest order; the lock gate refuses `mkway` owner-only
commands only for the commands it knows.

**Reading decisions taken (write each as a Log line when the part lands):** `find -delete`, `-exec` and `xargs rm`
are `delete-target-unknown` (the target set is computed); a literal target that does not exist is
`delete-target-unknown` with the text saying so; a target that is or holds the state folder is refused with
`delete-target-unknown` (too broad); check order per target: variable or substitution (unknown), outside the root,
wildcard, missing; `git clean -f` is always `delete-uncommitted`, `git reset --hard` only when the tree has changes,
`git restore` and `git checkout --` only for a path with changes, `git restore --staged` and `git rm --cached` are
not deletes; a PowerShell `-Include`, `-Exclude` or `-Filter` is a wildcard; an unknown PowerShell parameter or a
splat is unknown; `del`, `erase` and `rd` take `/s /q /f /a /p` style options; SQL is read only in the arguments and
heredoc of a SQL client (`psql`, `sqlite3`, `duckdb`, `mysql`, `sqlcmd` and similar) and in Python string constants
passed to `execute`, `executemany`, `executescript`, `sql`, `read_sql`; SQL read from a file or stdin is a known
limit for the README. Do not write the source task's number or any other task id, name or path in any tracked file.

**From the owner's guard (read only, cases to test):** it refuses, and so must this gate, `rm` / `rmdir` / `unlink`
/ `del` / `erase` / `rd` / `ri` / `Remove-Item` / `git rm` / `git clean` in every position: alone, after `&&`, `||`,
`;`, `|`, a newline, in parentheses, in `$( )` and backticks, behind `bash -c`, `cmd /c`, `pwsh -c`, `xargs`, in any
letter case, and after a `git commit ... &&` chain or inside `git commit -m "$(rm -rf x)"`; `find ... -delete` in
all those positions; `python -c "import os; os.remove(...)"`; SQL through `psql -c`, `duckdb file "drop table t"`;
a glob path (`rm dir/*.txt`). **False blocks to test as allowed:** a remove word as part of a longer word or file
name (`rmdir_helper`, `rm_old`, `del.txt`, `x.rm`, `echo confirm`, `ls --format=rm`), as a quoted echo text
(`echo "rm"`), as an assignment (`a=rm`, `$rm`), in a commit message (`git commit -m "rm the old rows; del x;
delete from cache; drop table t; truncate it"`, also by `-F -` heredoc and a PowerShell here-string), in the quoted
pattern of a read-only program (`grep -n "drop table|delete from" f.py`, `rg`, `git log --grep`, `cat`, `head`),
`git status`, `ls`, `git log -- a.rm`; a `pytest` or `python script.py` run that only names a path; a `del` inside
a Python heredoc (a statement, not a call); and the list command, also when its list file is outside the root:
`python mkway/engine/mkway.py delete --list <file>` must pass (the owner's guard falsely blocked its own list script,
the list file lying in the scratchpad).
