# MW-024: Commands find the task root below the git top

| | |
|---|---|
| **Appetite** | 40 minutes — from 2026-11-11 |
| **Status** | proposed |
| **Created / updated** | 2026-11-11 / 2026-11-11 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | none new: the standing rule «a gap found in real work gets its own fix card at once» carries it |
| **Canon** | none for the root lookup: the basis is the gap found in the owner's first real install |
| **Paths** | `engine/paths.py`, `engine/install.py`, `engine/mkway.py`, `README.md`, `CHANGELOG.md`, `VERSION`, `tests/`, `cards/REGISTER.md`, `cards/MW-024-task-root-below-top/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository.

## 1. Goal

A task folder that sits below the top of a git work tree (installed with `--root <worktree>/task/<Task>`) is found by
the commands run from it: without `--root` and without `$CLAUDE_PROJECT_DIR` the root is the nearest folder, from the
current folder up to the git top, that holds `mkway/profile.json`; without one the git top stays the answer. At a root
with no install, `check` and every command that needs the profile print one line naming the root and the fix and exit
1, never a traceback (the gap crashed with NotADirectoryError, WinError 267).

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | root two levels below the top, run from the root | the git top | that root | tests/test_mw024_task_root.py::test_find_root_takes_the_nearest_folder_with_a_profile_below_the_git_top |
| E2 | run from a subfolder of the root | the git top | the nearest folder up with `mkway/profile.json` | tests/test_mw024_task_root.py::test_find_root_walks_up_from_a_subfolder_of_the_task_root |
| E3 | no profile anywhere | the git top | the git top (unchanged) | tests/test_mw024_task_root.py::test_find_root_keeps_the_git_top_when_no_profile_exists |
| E4 | `--root`, `$CLAUDE_PROJECT_DIR` | win | still win | tests/test_mw024_task_root.py::test_root_arg_and_project_dir_still_win |
| E5 | `check` / `board` at a root with no install | traceback | one line with the root and `--root <task folder>`, exit 1 | tests/test_mw024_task_root.py::test_commands_at_a_root_without_an_install_say_so_in_one_line |
| E6 | register, changelog, version, README | no word | register row, a line under the release that names the card, VERSION: see VERSION, README line | tests/test_mw024_task_root.py::test_register_changelog_version_and_readme_name_the_card |

## 8. Log

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-11 | red: rows E1 to E6 | e9bacfc | 4 tests red, 2 pass before the code (E3, E4 guard today's answers) |
| 2026-11-11 | rows E1 to E6 changed the `VERSION` pin `0.2.0` to `0.2.1` in the tests of MW-016, MW-017, MW-018, MW-022, MW-023 (a patch release, README rule); no other change to them | the commit that carries this line | reading, to confirm |
| 2026-11-11 | whole suite, `python -m pytest`, term scan included | the commit that carries this line | 831 passed in 370 s (825 on the base, 6 new); no term-scan exception added |
| 2026-11-12 | MW-040: row E6 named a release number or an old VERSION | the commit that carries this line | the row says «see VERSION» and «the release that names the card»; its test reads the VERSION file and finds the card's changelog line (`tests/_docs.py`), no release number is pinned |
