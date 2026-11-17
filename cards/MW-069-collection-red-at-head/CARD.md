# MW-069: A test file that fails collection at HEAD is red at HEAD for its ids

| | |
|---|---|
| **Appetite** | 2 hours — from 2026-11-12 |
| **Status** | proposed |
| **Created / updated** | 2026-11-12 / 2026-11-12 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | R176 |
| **Canon** | none: the basis is a refusal in a real install, ruled R176 |
| **Paths** | `engine/gate_commit_tests.py`, `tests/`, `README.md`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-069-collection-red-at-head/CARD.md`, `cards/MW-062-absent-at-head/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository. `VERSION` is not changed here. It extends the red and green decision of MW-056 and MW-062 in
`engine/gate_commit_tests.py` only; `engine/helpers.py`, `engine/core.py` and `engine/gate_commit.py` are not touched.

## 1. Goal

A committing card adds a module that a committed test file of another card imports. At HEAD that file fails at
collection, so the gate refused the commit «new red, not red at HEAD» for the file's tests. The ruling: «a test file
that fails collection at HEAD is red at HEAD for every id in it (a file-level failure is a failure; DD-001 did not newly
break them), so the message «new red» is wrong and the classifier gets a small fix card (collection failure at HEAD = red
at HEAD for the file's ids). The branch that then applies is still the rule c tail: owned by a closed card = no open
owner = block. The engine is right to block: a closed card left red tests.» — the chief's ruling R176, 2026-11-12.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | a case of a file that failed at collection at HEAD, held by another open card | refused as new red (or listed as absent) | no block; red at HEAD, owned by that card | tests/test_mw069_judge.py::test_a_case_of_a_file_that_failed_at_collection_at_head_and_is_held_by_another_open_card_does_not_block |
| E2 | the same, only a closed card holds the file | refused as new red | blocked as red at HEAD, the closed owner named | tests/test_mw069_judge.py::test_a_case_of_a_file_that_failed_at_collection_at_head_with_only_a_closed_owner_blocks_naming_it |
| E3 | the same, no card holds the file | refused as new red | blocked as red at HEAD, no owner named | tests/test_mw069_judge.py::test_a_case_of_a_file_that_failed_at_collection_at_head_with_no_owner_at_all_blocks_without_a_card |
| E4 | the same, the committing card holds the file | refused as new red | blocked as the committing card's own red (rule b) | tests/test_mw069_judge.py::test_a_case_of_a_file_that_failed_at_collection_at_head_in_the_committing_cards_paths_blocks_as_its_own |
| E5 | a red case whose file did not fail at collection at HEAD | new red | still new red (rule a) | tests/test_mw069_judge.py::test_a_case_of_a_file_that_did_not_fail_at_collection_at_head_stays_new_red |
| E6 | a case red at HEAD by its own id | MW-056 buckets | unchanged, not marked as a collection failure | tests/test_mw069_judge.py::test_a_red_at_head_with_its_own_id_is_not_listed_as_a_collection_failure |
| E7 | the refusal text | «new red, not red at HEAD» | says the file was already red at HEAD and names the closed owner, or that it has no owner; never «new red» | tests/test_mw069_judge.py::test_the_refusal_says_the_file_was_already_red_at_head_and_names_the_closed_owner |
| E8 | the real shape on a real repository, the owner closed | refused as new red | refused `commit-tests-failed`, «already red at HEAD», the closed owner named | tests/test_mw069_shell.py::test_a_file_that_failed_at_collection_at_head_with_a_closed_owner_is_refused_as_red_at_head |
| E9 | the same, the owner open | allowed, listed as absent | allowed, listed `still red, owned by CARD-002` | tests/test_mw069_shell.py::test_a_file_that_failed_at_collection_at_head_with_an_open_owner_is_allowed_and_listed |

## 8. Log

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-12 | start checks, each alone: `pwd` = the worktree, HEAD d1b4d69, `git status --short` = clean | d1b4d69 | base of the card |
| 2026-11-12 | red: rows E1 to E9, tests, card, register row, changelog line | 8838c73 | all 10 new test nodes failed: the core table on the missing `closed_cards` and `file_red`, the shell tests on the real refusal «new red» (closed owner) and the allow line «1 case absent at HEAD» (open owner). Full suite not run for a red commit |
| 2026-11-12 | green: `judge` reads a bare file id among HEAD's failures as red at HEAD for every id of that file (`file_red`, `closed_cards`), the refusal names the closed owner, `_closed_cards`; only `engine/gate_commit_tests.py` changed. MW-062 rows E9 and E14 messages follow (see its Log), verdicts unchanged | the commit that carries this line | `tests/test_mw069*.py`, `test_mw056*.py`, `test_mw060*.py`, `test_mw062*.py`, `test_meta_cards.py`: 87 passed in 134.58 s. Whole suite not run here by the task's order. `VERSION` unchanged |
