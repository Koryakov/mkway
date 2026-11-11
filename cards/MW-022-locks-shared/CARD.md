# MW-022: Locks reach every worktree

| | |
|---|---|
| **Appetite** | 1 hour — from 2026-11-11 |
| **Status** | proposed |
| **Created / updated** | 2026-11-11 / 2026-11-11 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | none new: the order of 2026-11-11 and the owner's word «fix it» carry the design |
| **Canon** | none for lock markers: the basis is the order of 2026-11-11 |
| **Paths** | `engine/locks.py`, `engine/mkway.py`, `engine/install.py`, `engine/KEYS.md`, `CHANGELOG.md`, `README.md`, `tests/`, `cards/REGISTER.md`, `cards/MW-022-locks-shared/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository.

## 1. Goal

A hold or a lock typed in one work tree of a repository must stop or open every session of that repository, not only
the sessions of that work tree. The markers move to the shared state folder that MW-017 added (`profiles.shared_state_dir`);
the gates read them there — order of 2026-11-11.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | `mkway hold`, `mkway go`, `lock close\|open <name>` | the marker is `<bundle>/locks/<name>.json` of the work tree where it was typed | the marker is `<shared state dir>/locks/<name>.json`; typed in any work tree it reaches the others; owner-only as before | tests/test_mw022_locks_shared.py::test_a_hold_set_in_the_main_folder_stops_a_write_in_a_linked_work_tree; tests/test_mw022_locks_shared.py::test_a_hold_set_in_a_linked_work_tree_stops_the_main_folder |
| E2 | edit gate and shell gate | read the work tree's own marker | read the shared marker: a hold set in the main folder stops a write in a linked work tree and the other way round | tests/test_mw022_locks_shared.py::test_a_hold_set_in_the_main_folder_stops_a_write_in_a_linked_work_tree; tests/test_mw022_locks_shared.py::test_a_hold_set_in_a_linked_work_tree_stops_the_main_folder |
| E3 | every `locks.targets` entry, open or closed | per work tree | in the shared folder too: `lock open docs` in one work tree opens it in the other, `lock close` shuts it | tests/test_mw022_locks_shared.py::test_a_lock_target_opened_in_one_work_tree_is_open_in_the_other |
| E4 | a repository with no linked work tree, or no git | marker in `<bundle>/locks` | the shared folder is the state folder: `<state>/locks/<name>.json`; the gates read it | tests/test_mw022_locks_shared.py::test_a_repository_with_no_linked_work_tree_behaves_as_before |
| E5 | a work tree whose profile has no target of that name | — | ignores the marker | tests/test_mw022_locks_shared.py::test_a_work_tree_whose_profile_has_no_target_of_that_name_ignores_the_marker |
| E6 | an older per-work-tree marker | the only marker | still read for one version, closed wins between it and the shared marker; `lock open` and `go` remove it | tests/test_mw022_locks_shared.py::test_a_stale_local_marker_still_closes_and_is_reported; tests/test_mw022_locks_shared.py::test_closed_wins_between_the_local_and_the_shared_marker; tests/test_mw022_locks_shared.py::test_the_owner_open_and_go_also_clear_a_stale_local_marker |
| E7 | `mkway lock list`, `mkway check` | the work tree's own locks | `lock list` prints the shared state and the folder it reads from; `lock list` and `check` warn `lock-marker-local` for an older marker | tests/test_mw022_locks_shared.py::test_lock_list_shows_the_shared_state_and_its_folder; tests/test_mw022_locks_shared.py::test_a_stale_local_marker_still_closes_and_is_reported |
| E8 | gate calls, touched, once, trash, commit tests | per work tree | stay per work tree: a hold writes only `locks/` into the shared folder | tests/test_mw022_locks_shared.py::test_everything_else_stays_in_the_work_trees_own_state_folder |
| E9 | README, changelog, register | no word on it | README hold section: «a hold reaches every worktree of the repository»; `## 0.2.0` lists the card; the register has the row; `VERSION` stays `0.2.0` | tests/test_mw022_locks_shared.py::test_the_readme_changelog_register_and_keys_name_the_card |
| E10 | KEYS.md | no line | a «no key» line for the lock marker folder, naming this card | tests/test_mw022_locks_shared.py::test_the_readme_changelog_register_and_keys_name_the_card |

## 8. Log

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-11 | red: rows E1 to E10 | 072c07d | 9 tests red, 2 pass before the code (a marker absent everywhere ignores nothing; `go` already removed the local file) |
| 2026-11-11 | design settled by the order: markers in `<shared state dir>/locks/`; the helper is MW-017's `profiles.shared_state_dir`, no second one; the gates read the shared and the older local marker, closed wins; a hold marker exists in either place = closed; for a lock with an end time, any marker that is not open and unexpired closes | — | reading, to confirm |
| 2026-11-11 | `lock open`, `go` and `lock close` also remove the older local marker of that name, so the owner's word is not overruled by a file nobody writes any more | — | reading, to confirm |
| 2026-11-11 | expectations changed by the rule, as the marker path moves (E1), the README hold section gains one line (E9), and the 0.2.0 list gains this card (E9): `test_mw010_hold.py`, `test_lock.py`, `test_mw003_closefix.py` (marker under `mkway/state/locks`), `test_mw010_readme.py` (3 to 5 lines), `test_mw017_docs.py` (the list holds the MW-017 line, as the order of the peer session gave it); the start line counts the files of both marker folders | the commit that carries this line | expectation only, no check removed |
| 2026-11-11 | whole suite, `python -m pytest`, term scan included | the commit that carries this line | first run 686 passed, 2 failed (two old expectations, fixed as above); second run 688 passed in 266 s (was 677 on the base, 11 new) | no term-scan exception added |
| 2026-11-11 | limit, not settled by the order: in a linked work tree the shared folder lies outside that work tree's root, so the edit gate does not judge a session's direct write to it (the main work tree's own `state` target does); as for `leads.json` of MW-017 | — | to confirm |
