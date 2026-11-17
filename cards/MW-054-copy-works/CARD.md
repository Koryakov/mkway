# MW-054: A builder in a git worktree copy can take and work its card

| | |
|---|---|
| **Appetite** | 2 hours — from 2026-11-12 |
| **Status** | proposed |
| **Created / updated** | 2026-11-12 / 2026-11-12 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | none new: two rulings of the chief session of 2026-11-12 (git is the authority for a MISSING seal; a copy seals from its own branch HEAD) and its test-layer ruling |
| **Canon** | none for copy, seal, root |
| **Paths** | `engine/register.py`, `engine/paths.py`, `engine/mkway.py`, `tests/`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-054-copy-works/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository. `VERSION` is not changed here.

## 1. Goal

A git worktree copy of a task folder is a working root for a builder with no step by the owner: its start line is clean,
its `card take` is seen by every gate of that copy, a Write in the card's Paths is allowed, and the main root and the
other copies are not touched (holders stay per root). Two faults stopped it in the real install: the seal file is not in
git, so a new copy never has it; and the CLI of a session trusted `CLAUDE_PROJECT_DIR` inherited from the session that
launched it, so its take went to another root than the hooks read.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | the seal verdict (table) | a missing seal was always `register.sha is missing` | missing seal and register equal to its HEAD version, line ends aside (a checkout may convert them; the file's own bytes are sealed): adopt; missing seal and register differs from HEAD or is not committed: missing; a seal that exists and differs: differs, whatever HEAD holds | tests/test_mw054_decisions.py::test_the_seal_verdict_table |
| E2 | the CLI's root (table) | the variable always won | the variable holds when the folder is inside it or in no other mkway root; a folder inside ANOTHER mkway root decides for the CLI; the hook keeps the variable; `--root` wins | tests/test_mw054_decisions.py::test_the_cli_root_choice_table; tests/test_mw054_decisions.py::test_find_root_trusts_the_variable_for_the_hook_and_asks_the_folder_for_the_cli |
| E3 | a fresh copy on real git | start line and gates: `register-tampered` | the seal and the copy of the register are made from the committed bytes, one Log row, nothing written in the main root, a second look adds nothing | tests/test_mw054_copy_seal.py::test_a_fresh_copy_seals_from_its_committed_register |
| E4 | the refusals that stay | — | a seal that exists and differs stays refused and is not overwritten; a register edited after the commit, or never committed, with no seal stays refused and no seal is made | tests/test_mw054_copy_seal.py::test_a_seal_that_differs_and_a_register_that_differs_from_head_stay_refused |
| E5 | a copy of a branch whose register differs from master's | — | the copy seals from its own HEAD, not from master's; a copy of master beside it keeps master's | tests/test_mw054_copy_seal.py::test_a_copy_of_a_branch_with_its_own_register_seals_from_that_branch |
| E6 | the builder in a fresh copy, real hooks | start line `register-tampered`; Write refused | clean start line; take recorded in the copy; Write in the Paths allowed, outside them `file-not-in-card`; the main root untouched; a second copy independent | tests/test_mw054_copy_e2e.py::test_a_builder_in_a_fresh_copy_takes_its_card_and_writes_in_its_paths |
| E7 | a session whose shell names another root | the take went to that root; Write refused `no-open-card` | the take lands in the copy, the Write in the Paths is allowed, the other root gets no nonce and no record | tests/test_mw054_copy_e2e.py::test_a_session_started_from_another_root_still_takes_in_its_own_copy |
| E8 | register, changelog | no row | a register row, a line under the top changelog section, VERSION unchanged | tests/test_mw054_decisions.py::test_register_changelog_and_card_name_the_card |

## 8. Log

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-12 | root cause, two faults. (1) the seal: `register.sha` lives in the untracked state folder, so a new copy never has it, and every reader of the seal (start line, subtask gate, commit gate, the register's writers) answers `register-tampered (register.sha is missing)`; reproduced before any fix by the E6 scenario (start line `register-tampered`, Write refused `register-tampered`). (2) the reported `no-open-card`: the take never reached the copy. The real copy's state holds no `records.jsonl` and no `nonces` folder, and its post step ran after every Bash call in under 1 ms, so it found no nonce to record. A session's shell carries `CLAUDE_PROJECT_DIR` inherited from the session that launched it (observed in a session started that way: the variable names the launcher's project, not the working folder; Claude Code sets the right value only for the hooks), and `paths.find_root` trusts the variable first, so the CLI issued its nonce and its take in the launcher's root while the hook read the copy's. Row E7 reproduces the symptom (take prints its ok line, the copy holds no record). The take and the write gate read the same state folder per root, and the session id is the same in both: neither is a cause. Not established: which root the real builder's variable named (no nonce was found under the main root or the shared folder). The repro opens the card as the owner; the `Ordered by` cell plays no part in the seal or the take | — | recorded only |
| 2026-11-12 | red: rows E1 to E8 | the commit that carries this line | 21 failed, 1 passed in 17 s (E1 is one test per table row, 14 rows): E1 to E3, E5 to E8 fail for the right reason (no `seal_verdict`, no `cli_root`, copy answers `register-tampered`, take not recorded, no register row); E4 passes, it guards the refusals that stay. Committed red as e2e129c |
| 2026-11-12 | green: `register.seal_verdict` and `_adopt` (a missing seal is made by the first reader from the HEAD version, the file's own bytes sealed, one `log` row `register-seal-adopted`; `write` passes `_locked` so it does not wait on its own lock), `paths.cli_root` and `find_root(env_needs_cwd)` for the command line only (the hook keeps trusting the variable), register row, changelog line. Two corrections of my own red tests, no weakening: row E6 compared the main root's whole `records.jsonl` with empty, but it holds the owner's `new` and `open` rows, so it now asserts that no row with a session id is there; the register test of E8 got the `engine_repo` marker the copy guard (MW-029) demands | the commit that carries this line | rows E1 to E8 green. Whole suite, `python -m pytest`, term scan included, no exception added: 1103 passed and 1 failed in 708 s (the failure was the copy guard on the unmarked E8 test, the count includes one untracked scratch test not committed); after the marker the guard test and every MW-054 file, with the register and card tests, ran again: 36 passed in 59 s. The seal is made from git only for a MISSING seal; a session that deletes `register.sha` after committing an edited register is not stopped by this card (decided limit of the ruling: git is the authority) |
