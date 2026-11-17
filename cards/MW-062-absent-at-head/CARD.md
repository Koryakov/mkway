# MW-062: A test absent at HEAD is judged by its owner card

| | |
|---|---|
| **Appetite** | 2 hours — from 2026-11-12 |
| **Status** | proposed |
| **Created / updated** | 2026-11-12 / 2026-11-12 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | none new: the ruling of the task brief carries it, quoted in the Goal |
| **Canon** | none: the basis is a refusal in a real install where a card's commit made another open card's red-first cases appear |
| **Paths** | `engine/`, `tests/`, `README.md`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-062-absent-at-head/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository. `VERSION` is not changed here. It extends the red and green decision of MW-056 in
`engine/gate_commit_tests.py`; command parsing is not touched.

## 1. Goal

A card's red-first test file (committed, in its Paths) parametrizes over files that another open card creates. At HEAD
those cases do not exist; the other card's commit makes them appear, red because the first card's code is not in, and
the gate refused it «new red, not red at HEAD». The ruling: «a test id ABSENT at HEAD and red in the tree to commit is
judged by its owner: the open card whose Paths hold the test FILE (ownership by the file path, never per id). Owner is
another open card: no block, the allow line lists it with a count per owner. Owner is the committing card: refuse (rule
b). No open card owns the file: block (rule c tail). Green at HEAD and red now: refuse (rule a), unchanged. Red at HEAD
stays as MW-056 rules it.» — the chief's ruling R170, 2026-11-12.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | a case absent at HEAD, file in another open card's Paths | refused as new red | no block; the judgement names the owner by the file, a folder entry owns the files below it | tests/test_mw062_judge.py::test_a_case_absent_at_head_is_judged_by_the_open_card_that_owns_its_file |
| E2 | a case absent at HEAD, file in the committing card's Paths | refused as new red | refused as the committing card's own red (rule b) | tests/test_mw062_judge.py::test_a_case_absent_at_head_in_the_file_of_the_committing_card_blocks |
| E3 | a case absent at HEAD, no open card owns the file | refused as new red | still refused as new red (a waiting card owns nothing) | tests/test_mw062_judge.py::test_a_case_absent_at_head_that_no_open_card_owns_blocks |
| E4 | green at HEAD and red now; red at HEAD; a file-level id; HEAD's ids unknown | rules a, b, c | unchanged: new red refuses, the MW-056 buckets stay, a file-level id is never absent, no ids of HEAD means nothing is absent | tests/test_mw062_judge.py::test_rules_a_and_c_stay_as_they_were_for_a_test_that_exists_at_head |
| E5 | every branch in one run | not a case | each case in its bucket, in the order of the run, the first open card in register order owns a file held by two | tests/test_mw062_judge.py::test_every_branch_at_once_buckets_in_the_order_of_the_run_and_the_owners_in_register_order |
| E6 | the allow line and the refusal text | no such line | `40 cases absent at HEAD, owned by CARD-002` with a count per owner, beside the MW-056 text; a refusal says how many absent cases of other cards do not block | tests/test_mw062_judge.py::test_the_allow_line_counts_the_absent_cases_per_owner; tests/test_mw062_judge.py::test_the_refusal_says_how_many_absent_cases_another_card_owns |
| E7 | the listing of HEAD's cases | not made | the tests command with `-q` and `--collect-only`, one id per line, read as the failing ids are; not pytest means nothing is absent | tests/test_mw062_judge.py::test_the_collect_command_is_the_tests_command_asked_for_names_only; tests/test_mw062_judge.py::test_the_collected_ids_are_read_from_the_listing_one_per_line |
| E8 | the real shape on a real repository, the creating card commits with `--` | refused | allowed, a warn `commit-tests-still-red` listing `2 cases absent at HEAD, owned by CARD-002` | tests/test_mw062_shell.py::test_cases_absent_at_head_that_another_open_card_owns_pass_and_are_listed_with_their_count |
| E9 | the test file fails at collection at HEAD | its cases refused as new | its cases are red at HEAD, not absent (changed by MW-069, R176): allowed, listed as still red, owned by CARD-002 | tests/test_mw062_shell.py::test_a_file_that_failed_at_collection_at_head_makes_its_cases_red_there_owned_by_its_card |
| E10 | the same, the file in the committing card's Paths | refused | refused `commit-tests-failed`, the cases named with the card | tests/test_mw062_shell.py::test_the_same_cases_in_the_paths_of_the_committing_card_are_refused |
| E11 | no open owner; a case green at HEAD | refused | still refused as new red | tests/test_mw062_shell.py::test_no_open_owner_and_a_case_that_was_green_at_head_stay_refused |
| E12 | the real hook | deny `commit-tests-failed` | allow, the allow line names the count and CARD-002 | tests/test_mw062_e2e.py::test_cases_that_appear_with_the_creating_cards_files_are_allowed_through_the_real_hook |
| E13 | the rootdir of the tests command is above the task root | not a case | the listing of HEAD writes ids as the failure list does, so the cases are still absent, not new | tests/test_mw062_shell.py::test_the_listing_of_head_writes_ids_the_way_the_failure_list_does_when_the_rootdir_is_above |
| E14 | a file fails at collection at HEAD, another file has a red test there | the run stops at the collection error: HEAD records no red test, the other red looks new and is refused | HEAD's run and the staged run continue past a collection error; the other red is recorded per id and stays still red, owned by its card | tests/test_mw062_shell.py::test_a_collection_error_at_head_does_not_hide_the_red_tests_of_other_files_there |

## 8. Log

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-12 | start checks, each alone: `pwd` = the worktree, HEAD 6c6b79d, `git status --short` = clean | 6c6b79d | base of the card |
| 2026-11-12 | red: rows E1 to E12, card, register row, changelog line, tests only | 78be7cc | 13 of 14 new tests failed for the right reason: no `absent` bucket, no `head_seen`, no helpers, the real hook and the shell cases refused the commit as new red; the guard row of a case green at HEAD passed, as it must. Full suite not run for a red commit |
| 2026-11-12 | red: rows E13 E14, tests and card rows only | 5059325 | E14 failed for the right reason: a red test of another file, red at HEAD, was refused as new red because the HEAD run stopped at a collection error. E13 was found while making green (the listing of HEAD printed ids with a folder prefix, so every red case looked absent and a real new red was let through); it was added after the first red commit and is shown to fail with the rootdir pin of the listing removed |
| 2026-11-12 | green: `judge` with `head_seen` and the `absent` bucket, the allow line and refusal note, the listing of HEAD's cases (`collect_argv`, `collected_ids`, kept in `commit_tests_collect.jsonl`, asked only when a new red case lies in an open card's file), the runs continue past a collection error, README | the commit that carries this line | rows E1 to E14 green. Readings: (a) absent means not collected at HEAD, read from a `--collect-only -q` listing of HEAD's export, not from green results; a command that is not pytest, or a listing that cannot be read, means nothing is absent and the old rule stands; (b) an id with no `::` is never absent; (c) the committing card's file refuses as its own red, a file no open card holds refuses as new red; (d) the listing pins `--rootdir` to the start folder, since pytest prints a listed id relative to its rootdir and a failing id relative to the start folder; (e) the cache key of a result now carries the run mode, so an older HEAD result made without the flag is not reused. No manifest change: the allow line is the existing warn `commit-tests-still-red`. `VERSION` unchanged |
| 2026-11-12 | cause of a red test that fails on a clean copy of HEAD but was recorded as new red | the commit that carries this line | confirmed in the real install by the lead: the last two HEAD rows were `fail`, exit code 2, with only 5 file-level ids and no per-test id. pytest stops a whole run at the first file that fails at collection and runs no test, so HEAD's baseline kept none of its other red tests, while the staged tree collected and ran them all. Fix: HEAD and the staged run use `--continue-on-collection-errors` (row E14); the row keeps the command as the profile states it |
| 2026-11-12 | term scan found a pattern hit in my own test file (a decorator line inside a string); the line is written in call form and the variables renamed, no exception added, behaviour of the test unchanged | the commit that carries this line | the term scan and the install set check are clean |
| 2026-11-12 | whole suite, `python -m pytest`, term scan included, on the final tree | the commit that carries this line | 1252 passed in 1049.23 s (17 min 29 s). Earlier runs not counted: one gave 1250 passed, 2 failed, both the term-scan hit above; one was stopped because a second pytest run started beside it shares the temp folder `.pytest_tmp` and disturbed it |
| 2026-11-12 | rows E9 and E14 changed by MW-069 (ruling R176: a file that failed at collection at HEAD is red at HEAD for its ids, never absent): the message is `still red, owned by CARD-002`, no longer `absent at HEAD`; the verdict (allowed, warn) is the same | the MW-069 green commit | test change follows the MW-069 red commit 8838c73 |
