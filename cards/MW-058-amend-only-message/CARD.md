# MW-058: A message-only amend takes no files

| | |
|---|---|
| **Appetite** | 90 minutes — from 2026-11-12 |
| **Status** | proposed |
| **Created / updated** | 2026-11-12 / 2026-11-12 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | none new: the rule of MW-043 («judge a commit by what git takes») carries it |
| **Canon** | none: the basis is a real install where a message-only amend was refused |
| **Paths** | `engine/`, `tests/`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-058-amend-only-message/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository. `VERSION` is not changed here.

## 1. Goal

A real install: a session holding no card ran `git commit --amend --only -m "<message>"` with 170 other files staged.
Git takes nothing from the index in that form (`--only` with no paths and `--amend` rewrites only the message), yet the
commit gate refused it: «cannot be committed: this session holds no open card». The rule: `--amend` with `--only` or
`-o` and no paths takes no files, so the gate has no files to judge and allows it, whoever runs it; the message checks
still run on the new message. With paths it takes exactly the named paths; `--amend` without `--only` keeps the staged
list rule. `-o` is read in a short group (`-om`, which git accepts). — the architect's task, 2026-11-12.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | the files an amend takes, per form (`--only`, `-o`, `-om`, either order, with and without paths, plain, `-a`, `-i`) | `--only` and `-o` were not read: a message-only amend was judged by the staged list | no paths: none; paths: exactly the named; plain `--amend`: the staged list as before | tests/test_mw058_amend_only.py::test_the_files_an_amend_takes_follow_its_form |
| E2 | what real git does | assumed | tree and index unchanged by a message-only amend; with paths only the named path goes in | tests/test_mw058_amend_only.py::test_real_git_takes_nothing_for_a_message_only_amend |
| E3 | the message checks | not reached | still run on the new message: the card id is required for a card holder, a named outside path is refused | tests/test_mw058_amend_only.py::test_the_message_checks_still_run_on_a_message_only_amend |
| E4 | the real hook command, other files staged, no card | denied `file-not-in-card` | allowed; a plain `--amend` stays denied | tests/test_mw058_e2e.py::test_a_message_only_amend_is_allowed_through_the_real_hook_with_files_staged |
| E5 | register, changelog | none | a register row, one line under the top section, the card folder; VERSION unchanged | tests/test_mw058_amend_only.py::test_register_changelog_and_card_name_the_card |

## 8. Log

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-12 | red: rows E1 to E5 | c90ac46 | 9 of 18 tests fail for the right reason (the message-only forms are judged by the staged list; no register row, no changelog line); the rows for paths, plain amend, `-a`, `-i` and the real git proof pass already and pin what stays |
| 2026-11-12 | green: `Commit.only` read from `--only` and `-o` in a short group; `_taken` returns no files for `--amend` with `--only` and no paths. Two test edits after the red commit, none weakened: the e2e fixture sets a green `tests.command` (the separate `commit_tests` gate denied for lack of a test command, not for files), and the docs row carries the `engine_repo` marker (the copy guard of MW-029 asked for it) | the commit that carries this line | rows E1 to E5 green, 18 tests; whole suite `python -m pytest`: 1194 passed, 1 failed in 741.94 s (the missing marker), then fixed and the new files plus `tests/test_mw029_fast_guard.py` re-run: 26 passed in 56.16 s. Not touched, not established: whether the `commit_tests` gate should also skip a message-only amend |
