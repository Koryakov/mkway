# MW-056: A commit is refused only for new red

| | |
|---|---|
| **Appetite** | 2 hours — from 2026-11-12 |
| **Status** | proposed |
| **Created / updated** | 2026-11-12 / 2026-11-12 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | none new: the rule a to e of the task brief of 2026-11-12 carries it, it was approved there |
| **Canon** | none for the commit gate: the basis is a refusal in a real install, where a card's code commit was stopped by five red tests of two other open cards |
| **Paths** | `engine/`, `tests/`, `README.md`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-056-new-red-only/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository. `VERSION` is not changed here.

## 1. Goal

«a commit is refused only for new red» — task brief, 2026-11-12.
The gate `commit_tests` refused every commit while any test of the staged tree was red, so one card that was mid-way
(its red-first tests committed, its code not) stopped every other card. The rule now: (a) a test red in the staged tree
and not red at HEAD is new breakage and refuses, whoever owns it; (b) a red test inside the committing card's Paths
refuses; (c) a test red at HEAD and still red does not refuse when it lies in another open card's Paths (the allow line
says `<test id> still red, owned by <card id>`), and refuses when it lies in no open card's Paths (it has no owner; a
card must take it); (d) the red-first commit of tests alone stays allowed as MW-005 allows it; (e) HEAD's results are
kept by the tree of HEAD in the root state, so a repeat costs one run, and are ignored when `tests.command` or the
profile changes. Running only the card's own tests is rejected: it would miss the breakage of others.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | rule a, a test red now and not red at HEAD | any red refused | blocks whoever owns the file: no owner, another open card, the committing card; an old red beside it does not hide it | tests/test_mw056_judge.py::test_a_new_red_blocks_whoever_owns_it |
| E2 | rule b, a red test of the committing card | refused as any red | blocks even when it was already red at HEAD; the committing card's Paths win over another card's; no card taken owns nothing | tests/test_mw056_judge.py::test_a_red_test_of_the_committing_card_blocks |
| E3 | rule c, an old red of another open card | refused | does not block; the judgement names the owning card | tests/test_mw056_judge.py::test_an_old_red_of_an_open_card_does_not_block_and_names_its_owner |
| E4 | rule c, an old red in no open card's Paths | refused | blocks as an orphan (no owner) | tests/test_mw056_judge.py::test_an_old_red_that_no_open_card_owns_blocks |
| E5 | staged tree green, or a red of HEAD fixed | not a case | never blocks, whatever HEAD was | tests/test_mw056_judge.py::test_green_tests_and_fixed_tests_never_block |
| E6 | the owner of an id | not a case | read from the file of the id (collection error, parametrised id, backslashes) and a folder entry owns the files below it, not a sibling folder | tests/test_mw056_judge.py::test_the_owner_is_read_from_the_file_of_the_id_and_a_folder_entry_counts |
| E7 | order and stability | not a case | two open cards own a file: the first in register order is named; buckets keep the run's order and repeat exactly | tests/test_mw056_judge.py::test_the_first_open_card_in_register_order_is_named_when_two_own_a_file; tests/test_mw056_judge.py::test_the_buckets_keep_the_order_of_the_staged_run_and_repeat_exactly |
| E8 | the allow line | no such line | a warn `commit-tests-still-red`: `<test id> still red, owned by <card id>`; the commit passes | tests/test_mw056_head.py::test_an_old_red_of_another_open_card_passes_and_the_allow_line_names_the_owner |
| E9 | the refusal text | one list of the first 10 red ids | names each kind: new (not red at HEAD), the committing card's own, no owner with «a card must take it»; the way out of MW-005 stays | tests/test_mw056_head.py::test_the_refusal_names_each_kind_of_red_and_the_way_out |
| E10 | only an open card owns a red | not a case | a `waiting` card owns nothing (its red blocks as no owner); opened again it owns it | tests/test_mw056_head.py::test_only_an_open_card_owns_a_red_test |
| E11 | rule d, the red-first commit | allowed, no run | still allowed with no staged run and no HEAD run, HEAD red and a new red test | tests/test_mw056_head.py::test_a_red_first_commit_runs_nothing_even_at_head; tests/test_mw005_gate.py::test_red_first_a_commit_of_tests_alone_may_be_red_anything_else_may_not |
| E12 | rule e, HEAD's result kept | not run | the first red attempt runs the staged tree and HEAD's tree and keeps HEAD's row (`commit_tests_head.jsonl`) under HEAD's tree; a second attempt on the same HEAD runs the staged tree only | tests/test_mw056_head.py::test_head_results_are_cached_by_the_tree_of_head |
| E13 | rule e, stale cache | not a case | a changed `tests.command` or a changed profile runs HEAD again | tests/test_mw056_head.py::test_the_head_cache_is_ignored_when_the_tests_command_or_the_profile_changes |
| E14 | no HEAD | not a case | every red is new, no HEAD run | tests/test_mw056_head.py::test_a_repository_with_no_head_treats_every_red_as_new |
| E15 | the real hook, a new red | not shown | the installed hook denies `commit-tests-failed`, the test named as new | tests/test_mw056_e2e.py::test_a_new_red_is_denied_through_the_real_hook |
| E16 | the real hook, another card's old red | the commit was refused | the installed hook allows and the allow line names `CARD-002` | tests/test_mw056_e2e.py::test_another_cards_old_red_is_allowed_through_the_real_hook |
| E17 | manifest | four reason ids | `commit-tests-still-red` is declared beside the four older ids | tests/test_mw056_docs.py::test_the_manifest_declares_the_warn_reason_of_the_allow_line |
| E18 | README | the section states the old rule | the section states the new rule, the allow line, the HEAD cache and when it is ignored | tests/test_mw056_docs.py::test_the_readme_states_the_new_rule |
| E19 | register, changelog | no row | a register row, a line under the top changelog section, VERSION unchanged | tests/test_mw056_docs.py::test_register_changelog_and_card_name_the_card |

## 8. Log

One line per step. No re-run of a check or an agent round without a new input named in the Log row.

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-12 | start checks, each alone: `pwd` = the worktree, HEAD ab155d0, `git status --short` = clean | ab155d0 | base of the card |
| 2026-11-12 | red: rows E1 to E19, card, register row, changelog line, tests only | d4d43bd | every new test failed for the right reason: no `judge`, no `HEAD_FILE`, the manifest lacked the fifth reason id, the gate refused the other card's old red, and the real hook named the id with a backslash. Test changes by MW-056, nothing weakened: `tests/test_mw005_gate.py` expects five reason ids instead of four, and `tests/test_e2e_gates.py` states an exemption for the warn id. Full suite not run for a red commit |
| 2026-11-12 | green: `judge`, ids kept with `/`, HEAD run and its cache (`commit_tests_head.jsonl`, keyed by the tree of HEAD, command and profile), the warn `commit-tests-still-red`, manifest, README | the commit that carries this line | rows E1 to E19 green. Readings: (a) only an `open` card owns a red test, as the brief says, so a `waiting` card owns nothing; (b) HEAD results go in their own file so the existing one-row-per-run assertions of MW-005 stay as they are; a staged row of the same tree also answers for HEAD; (c) a red run that names no failing test, or a HEAD that is red and names none, is refused as before; (d) HEAD over budget is refused `commit-tests-over-budget`. Test changes by MW-056, nothing weakened: row E6 of `tests/test_mw056_judge.py` compares the owner key with `/` (my row was wrong, found at green); `tests/test_mw005_readme.py` expects five reason ids; the docs tests carry the `engine_repo` mark (the first whole-suite run failed on the copy guard for that, 1 failed, 1100 passed in 590 s). Whole suite, `python -m pytest`, term scan included, no exception added: 1101 passed in 566 s (9 min 26 s) |
