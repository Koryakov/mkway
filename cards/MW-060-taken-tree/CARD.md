# MW-060: commit_tests tests the tree git will commit

| | |
|---|---|
| **Appetite** | 2 hours — from 2026-11-12 |
| **Status** | proposed |
| **Created / updated** | 2026-11-12 / 2026-11-12 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | none new: the lead's task carries it, the rule «judge a commit by what git takes» was already ruled (MW-043) |
| **Canon** | none: the basis is a real install where a builder's `--` commit was refused for 40 red tests none of its files could have broken |
| **Paths** | `engine/`, `tests/`, `README.md`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-060-taken-tree/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository. `VERSION` is not changed here. MW-056's red or green decision, MW-057's run environment and refusal text
stay as they are. A message-only amend (`--amend --only` or `-o`, no paths) is MW-058's form for `commit_files`; the lead
moved the test gate's part of it here (the field `Commit.only` and its condition are MW-058's, taken over unchanged).

## 1. Goal

«commit_tests must build and test exactly the tree the commit will produce»: `-- <paths>`, `--only` and `-o` HEAD plus
the named paths as the working tree has them; `-i` the index plus the named paths; a plain commit the index; `-a` the
index plus every modified tracked file; read by the one reader `commit_files` uses, so the two gates never disagree; the
key of a kept test result is the digest of the tree built, never the index; `--amend --only` or `-o` with no paths: the
tree does not change, nothing to test — task and chief ruling R168, 2026-11-12.
The cause found: the gate built the `--` tree with `git add -A -- <paths>`, which also takes the untracked files inside a
named folder; git commits no untracked file, so the gate tested a tree git would not commit (reproduced: a folder of
untracked files inside a named folder turns a test red that the committed tree does not have). Not established: whether
that is the only cause of the 40 refused tests of the real install (the command was reproduced in shape, with a
synthetic guard test, not with that task's tests).

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | `-- paths`, `-o`, `--only` | a second list in the test gate | the tree is HEAD plus the named paths from the working tree; a deleted named path is gone; nothing else of the index | tests/test_mw060_taken_tree.py::test_the_reader_combines_the_lists_as_git_takes_them; tests/test_mw060_taken_tree.py::test_the_tree_plan_for_each_commit_form |
| E2 | `-i -- paths` | index plus paths (by `add -A`) | the index plus the named paths, refused when the staged part is red | tests/test_mw060_taken_tree.py::test_the_forms_that_take_the_index_are_tested_with_the_index |
| E3 | plain commit, `--amend`, `-a` | index; index plus `add -u` | the index; the index plus the working-tree content of every modified tracked file | tests/test_mw060_taken_tree.py::test_the_tree_plan_for_each_commit_form; tests/test_mw060_taken_tree.py::test_the_forms_that_take_the_index_are_tested_with_the_index |
| E4 | another card's breaking file staged, a clean path committed with `--` | allowed (already so for a path alone) | still allowed; the same state as a plain commit is refused as new red | tests/test_mw060_taken_tree.py::test_a_commit_of_a_clean_path_is_allowed_while_another_cards_breaking_file_is_staged |
| E5 | untracked files inside a named folder; task root below the git top; two-line message with an empty line | the untracked files were in the tested tree: refused | not in the tested tree: allowed | tests/test_mw060_taken_tree.py::test_an_untracked_file_in_a_named_folder_is_not_in_the_tested_tree_but_a_staged_one_is |
| E6 | a test staged as added inside a named folder | tested | still tested: git takes it, so a red one is refused and named | tests/test_mw060_taken_tree.py::test_an_untracked_file_in_a_named_folder_is_not_in_the_tested_tree_but_a_staged_one_is |
| E7 | the key of a kept result (R168) | digest of the listing of the temporary index | the digest of the tree built; after git makes the same commit it is a key of HEAD's tree, and it is not the index's digest | tests/test_mw060_taken_tree.py::test_the_row_is_keyed_by_the_tree_the_commit_produces_never_by_the_index |
| E8 | one source of truth | `commit_tests` has its own reading of the forms | `commit_tests` takes the list from `gate_commit.taken`, replacing it changes its answer | tests/test_mw060_taken_tree.py::test_both_gates_read_what_the_commit_takes_through_one_function |
| E9 | `commit_files` | its own `_taken` | `_taken` is the shared reader with its path normaliser; MW-043 rows stay green | tests/test_mw060_taken_tree.py::test_commit_files_still_reads_the_same_list_through_the_shared_reader; tests/test_mw043_commit_takes.py::test_a_foreign_staged_file_does_not_stop_a_commit_that_names_its_own_paths; tests/test_mw043_commit_takes.py::test_an_include_commit_takes_the_staged_list_plus_the_named_paths; tests/test_mw043_commit_takes.py::test_an_all_commit_takes_the_staged_list_plus_every_modified_tracked_file |
| E10 | the real hook, the builder's folder with another card's breaking file staged | denied in the real install | the installed hook allows | tests/test_mw060_e2e.py::test_a_commit_of_the_builders_own_folder_is_allowed_through_the_real_hook |
| E11 | the real hook, the same state as a plain commit | denied | still denied `commit-tests-failed`, the test named as new | tests/test_mw060_e2e.py::test_the_same_state_as_a_plain_commit_is_denied_through_the_real_hook |
| E12 | README | states the index | states the tree each form tests, that untracked files are not in it, the shared reader and the key | tests/test_mw060_docs.py::test_the_readme_states_which_tree_each_commit_form_tests |
| E13 | register, changelog | no row | a register row, a line under the top changelog section, VERSION unchanged | tests/test_mw060_docs.py::test_register_changelog_and_card_name_the_card |
| E14 | `--amend --only` or `-o`, no paths: what the parser and the reader say | `--only` and `-o` not read; the amend read as a plain one | `Commit.only` is set; a message-only amend takes no files; an amend with the index, with a path, with `-a` or `-i` still takes them | tests/test_mw060_taken_tree.py::test_a_message_only_amend_takes_no_files |
| E15 | a message-only amend while another card's breaking file is staged | refused as new red (the index was tested) | allowed with no run and no row; a plain `--amend` is still refused; an amend that names a clean path is allowed | tests/test_mw060_taken_tree.py::test_a_message_only_amend_is_not_tested_while_another_cards_breaking_file_is_staged |

## 8. Log

One line per step. No re-run of a check or an agent round without a new input named in the Log row.

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-12 | start checks, each alone: `pwd` = the worktree, HEAD 2aa0807, `git status --short` = clean | 2aa0807 | base of the card |
| 2026-11-12 | probes before any test, through the real gate: `--` with a path, several paths, a folder, a staged-as-added path, `-o`, `--only`, PowerShell, task root below the git top, `git -C`, a message with `#` — all allowed while another card's breaking file was staged (the stated defect did not reproduce); then the real command shape with an untracked folder inside a named folder reproduced a refusal | not committed | cause: `git add -A -- <paths>` in `_temp_index` takes untracked files, git does not |
| 2026-11-12 | red: rows E1 to E13, card, register row, changelog line, tests only | the red commit | 21 failed and 2 errored for the right reason (no `combine`, `taken`, `tree_plan`; the untracked folder refused; the README lacked the rule). Rows E2, E4, E7 and the plain-commit deny of E11 pass today: they pin behaviour that must stay. One test mistake of mine, fixed before the commit: the e2e card Paths named `tests/`, which `card open` refuses as too wide. Full suite not run for a red commit |
| 2026-11-12 | red: rows E14 and E15, added after the lead's note that the test gate still tested the index for a message-only amend; the tests and the card rows go in this commit alone | the commit that carries this line | 9 failed for the right reason (no `message_only_amend`; a message-only amend refused as new red). Nothing weakened |
| 2026-11-12 | green: `gate_commit.combine`, `taken`, `message_only_amend` (the one reader, `commit_files` through its normaliser), `Commit.only` as MW-058 names it, `tree_plan`, the temporary index built from the reader with `update-index` and compared with the plan (a difference refuses), the README and gate docstring | the commit that carries this line | rows E1 to E15 green. Not done: MW-056's decision, MW-057's environment and refusal text and `VERSION` are untouched; the cache key stays the digest of the built tree's listing (a `tree_keys` key of HEAD after the same commit, proved in E7). The first whole run failed once: the scratch probe file of this card (untracked, task ids in a line) hit the term scan (`tests/test_install.py::test_fixed_set_is_nda_clean`, 1 failed, 1203 passed in 772.05 s); it was emptied, not deleted, and no exception was added. Whole suite, `python -m pytest`, term scan included: 1213 passed in 665.98 s (11 min 6 s) |
