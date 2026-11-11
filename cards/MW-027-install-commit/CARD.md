# MW-027: Install: one step to a committed fence

| | |
|---|---|
| **Appetite** | 120 minutes — from 2026-11-11 |
| **Status** | proposed |
| **Created / updated** | 2026-11-11 / 2026-11-11 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | the ruling of the chief session and the owner's answer «we will commit when you fix»: mkway is committed into the task's repository; the hook entries are committed in `.claude/settings.json`; a per-machine interpreter stays in `state/machine.json`, nothing of mkway goes to `settings.local.json` (the operator approved this default) |
| **Canon** | none: the basis is the gap found in the owner's first real install (the standing rule «a gap found in real work gets its own fix card at once») |
| **Paths** | `engine/install.py`, `engine/mkway.py`, `engine/locks.py`, `engine/startline.py`, `README.md`, `CHANGELOG.md`, `VERSION`, `tests/`, `cards/REGISTER.md`, `cards/MW-027-install-commit/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository.

## 1. Goal

One `mkway install` leaves a task folder that the owner commits as it is, and every worktree of that commit has working
hooks with no install. Install writes the bundle `.gitignore` (state, locks, bytecode and check temp folders) whatever
the profile's vcs, and the engine copy is tracked, so the first `git add` takes no run-time file and a fresh worktree has
the copy. The hook entries go into the committed `.claude/settings.json` (merged, never overwritten; a reinstall
replaces only mkway's own entries and strips them from an old `settings.local.json`). `.claude/settings.json` is a
protected path of the commit check. Install ends by printing `git add <paths>` and `git commit -m "mkway <version>:
install"`, or runs them with `--commit` in the owner's terminal. The README «Use in a task» is five lines.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | install, session start, a refusal, `git add -A` | state, bytecode, check temp offered for commit | no run-time file staged; the bundle `.gitignore` is written with vcs none too and does not ignore `engine/` | tests/test_mw027_install_commit.py::test_install_writes_the_bundle_gitignore_so_the_first_add_is_clean |
| E1 | the same with vcs none | no `.gitignore` | the lines are there | tests/test_mw027_install_commit.py::test_install_writes_the_bundle_gitignore_with_vcs_none_too |
| E2 | hook entries | `settings.local.json` | `settings.json`, merged, once each, a reinstall changes nothing | tests/test_mw027_install_commit.py::test_hook_entries_go_into_the_committed_settings_json |
| E3 | an old-style install, then a reinstall | entries in the local file | each hook once, the owner's own entries and keys of the local file kept | tests/test_mw027_install_commit.py::test_a_reinstall_strips_mkways_entries_from_settings_local_json |
| E4 | a session edits or commits `.claude/settings.json` | allowed | refused `lock-closed-edit`, `lock-closed-commit` | tests/test_mw027_install_commit.py::test_the_settings_files_are_protected_paths |
| E5 | the end of install | nothing | the two commit lines, with vcs git only | tests/test_mw027_install_commit.py::test_install_prints_the_two_commit_lines |
| E6 | `install --commit` | no flag | commits in the owner's terminal, refused in a chat and with vcs none | tests/test_mw027_install_commit.py::test_install_commit_runs_the_two_lines_in_the_owners_terminal_only |
| E7 | a worktree of the commit | needs its own install | the start hook works, no drift | tests/test_mw027_install_commit.py::test_a_fresh_worktree_has_working_hooks_with_no_install |
| E8 | the copy under autocrlf | converted | `engine/** -text` | tests/test_mw027_install_commit.py::test_the_engine_copy_is_never_converted_by_git |
| E9 | an earlier `.gitignore` with `engine/` | silent | one report line, nothing removed | tests/test_mw027_install_commit.py::test_an_older_ignore_line_for_the_engine_copy_is_reported |
| E10 | README «Use in a task» | settings.local.json called git-ignored | five lines, no such claim | tests/test_mw027_install_commit.py::test_readme_use_in_a_task_has_five_lines_and_no_ignored_settings_claim |
| E11 | register, changelog, version | no word | register row, `## 0.2.7` on top, `VERSION` 0.2.7 | tests/test_mw027_install_commit.py::test_register_changelog_and_version_name_the_card |

## 8. Log

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-11 | the operator's question and answer: the entries in `settings.local.json` would run beside those in `settings.json` (Claude Code runs both), so the per-machine interpreter is not put there; the committed entries use the profile's `python.command`, `--python` is recorded in `state/machine.json` only, and the start line then reports `drift-machine` | — | approved by the operator: «build your default» |
| 2026-11-11 | red: rows E1 to E11 | 9e8e78f | 12 tests red, 1 passes before the code (the local file stays a protected path) |
| 2026-11-11 | the engine copy is tracked now (R18 amended): a fresh worktree of the commit has the hooks' target, so `engine/` leaves the bundle `.gitignore`; bytecode and check temp folders, written when the copy runs, join it; `engine/** -text` keeps the copy's hash under autocrlf; an older `.gitignore` that still names `engine/` gets one report line | the commit that carries this line | reading, to confirm |
| 2026-11-11 | in a worktree no install ran in, `state/machine.json` is missing: the start line then takes the profile's `python.command` as the machine interpreter, so a fresh worktree shows no `drift-machine` | the commit that carries this line | reading, to confirm |
| 2026-11-11 | older tests changed, node names kept because MW-002 rows cite them: `test_install_creates_folders_starter_profile_and_ignore_lines` (E30: `engine/` no longer ignored, the bundle `.gitignore` also with vcs none), `test_hook_entries_generated_and_other_keys_kept` (E31), `test_cards_and_ledger_are_tracked` (E67: the ignore lines), `test_install_names_old_ignore_lines_for_cards_and_ledger` (E72: filters the R18 line, `engine/` has its own), `test_install_refuses_a_python_that_is_not_an_interpreter` (E59), `test_install_writes_the_machine_interpreter` (E47: `drift-machine` is the answer for a differing `--python`), `test_profile_arg_install_has_no_false_drift` (E48), `test_install_says_when_git_cannot_check_the_ignore` (E52: install no longer asks git about `settings.local.json`, so the row's subject is gone; the test now proves install still succeeds outside a work tree), `test_settings_local_is_git_ignored` (E42: install writes no `settings.local.json`, `settings.json` is not ignored); the settings path in the start-line, agent-install and message-gate tests; one row for `.claude/settings.json` in the lock test; the version pin `0.2.6` read `0.2.7` in the tests of MW-016, MW-017, MW-018, MW-022, MW-023, MW-024, MW-025, MW-026, MW-028 | the commit that carries this line | reading, to confirm |
| 2026-11-11 | whole suite, `python -m pytest`, term scan included | the commit that carries this line | 875 passed in 436 s; no term-scan exception added |
| 2026-11-11 | ported onto master 4fd59c6 (MW-030 and MW-031 merged): t27's lines applied to the files master also changed (register, changelog, `engine/install.py`), the rest copied; the live install test of MW-030 reads the hooks from `.claude/settings.json` and gains E9 and E10 (status offers no run-time file; a second worktree of the committed install starts with no install); MW-030 row E8 and MW-031 row E7 changed with a Log line each (a newer release is on top, VERSION 0.2.7) | the commit that carries this line | whole suite, `python -m pytest`, term scan included: 893 passed in 467 s; no term-scan exception added |
| 2026-11-11 | ported again onto master f77c7da (MW-032 merged): t27b's lines applied to `engine/install.py` keeping MW-032's swap by rename and its read-only-aware remover, to the register, the changelog (`## 0.2.7` on top, MW-032's line kept under `## 0.2.6`) and the live test (MW-032's reinstall step kept, E9 and E10 added); MW-032 row E8 changed with a Log line (VERSION 0.2.7) | the commit that carries this line | whole suite, `python -m pytest`, term scan included: 901 passed in 509 s; no term-scan exception added |
