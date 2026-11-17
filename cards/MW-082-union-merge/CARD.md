# MW-082: Append-only files merge without conflicts

| | |
|---|---|
| **Appetite** | 1.5 hours - from 2026-11-12 |
| **Status** | proposed |
| **Created / updated** | 2026-11-12 / 2026-11-12 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | R197 A, R197a |
| **Canon** | none: the basis is ruling R197 A and the git docs on the built-in merge driver `union` |
| **Paths** | `.gitattributes`, `engine/register.py`, `README.md`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-082-union-merge/CARD.md`, `tests/test_mw082_attributes.py`, `tests/test_mw082_duplicates.py`, `tests/core/test_mw082_register_order.py`, `tests/shell/test_mw082_union_merge.py` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository. `VERSION` is not changed. No refusal and no engine gate: the gate items of the common test-gate rules (switch,
reason ids, e2e deny, time per commit) do not apply.

## 1. Goal

«one tiny card on master, merged first, .gitattributes with merge=union for CHANGELOG.md and cards/REGISTER.md» - R197 A, 2026-11-12.
Real case: dry-run merges of the branches of MW-075 and MW-076 into master 8cc1d84 both predicted conflicts in exactly
`CHANGELOG.md` and `cards/REGISTER.md`: every card appends one line at the end of the same section.
Guards (R197 A): 1 duplicates fail a meta test; 2 the register reader does not depend on row order; 3 the Log names the rule below.

## Acceptance examples

Each row becomes a test; `card close` needs every row to name one. Guards 1 and 2 check reading, not new engine rules.

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | `.gitattributes` | none | exactly the two lines `CHANGELOG.md merge=union` and `cards/REGISTER.md merge=union` | tests/test_mw082_attributes.py::test_the_attributes_file_holds_the_two_union_lines |
| E2 | git's reading of the attribute | unspecified for both files | `union` for both | tests/test_mw082_attributes.py::test_git_reads_union_for_both_files |
| E3 | merge of two appended changelog lines | conflict | exit 0 | tests/shell/test_mw082_union_merge.py::test_changelog_merge_exits_zero |
| E4 | the merged changelog | markers | each new line once, next heading intact | tests/shell/test_mw082_union_merge.py::test_changelog_merge_keeps_each_line_once_and_the_heading |
| E5 | merge of two appended register rows, base row without final newline | conflict | exit 0 | tests/shell/test_mw082_union_merge.py::test_register_merge_exits_zero |
| E6 | the merged register | markers | base row once, each new row once, one row per line | tests/shell/test_mw082_union_merge.py::test_register_merge_keeps_each_row_once_on_its_own_line |
| E7 | control: the real attributes file is in the repository under another name, so not applied | conflict | exit not 0 | tests/shell/test_mw082_union_merge.py::test_register_merge_without_the_attributes_conflicts |
| E8 | guard 1: the real changelog | no check | no card line twice in a release section | tests/test_mw082_duplicates.py::test_the_real_changelog_has_no_card_line_twice_in_a_section |
| E9 | guard 1: a synthetic changelog with a line twice | not found | the card id is named | tests/test_mw082_duplicates.py::test_a_card_line_twice_in_one_section_is_found |
| E10 | guard 1: the real register | no check | no card id twice | tests/test_mw082_duplicates.py::test_the_real_register_has_no_card_id_twice |
| E11 | guard 1: a synthetic register with an id twice | not found | the card id is named | tests/test_mw082_duplicates.py::test_a_register_card_id_twice_is_found |
| E12 | guard 2: the same rows in two orders | order read | the same rows by id | tests/core/test_mw082_register_order.py::test_parse_gives_the_same_rows_in_either_order |
| E13 | guard 2: `find` in two orders | order read | the same row | tests/core/test_mw082_register_order.py::test_find_gives_the_same_row_in_either_order |
| E14 | guard 2: `closed_ids` in two orders | order read | the same set | tests/core/test_mw082_register_order.py::test_closed_ids_are_the_same_in_either_order |
| E15 | guard 2: a stray line between rows | rows after it lost | no row lost | tests/core/test_mw082_register_order.py::test_a_stray_line_between_rows_loses_no_row |
| E16 | both real files | register without final newline | both end with a newline | tests/test_mw082_attributes.py::test_both_union_files_end_with_a_newline |

## 8. Log

One line per step. No re-run of a check or an agent round without a new input named in the Log row.

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-12 | start checks, each alone: `pwd` = the worktree, HEAD 8cc1d84, status = clean | 8cc1d84 | base of the card |
| 2026-11-12 | no refusal and no engine gate: the gate items of the common rules (switch, reason ids, e2e deny, time per commit) do not apply | | the card adds an attributes file, tests and a reader fix only |
| 2026-11-12 | R183 note: guard 1 (E8 to E11) and the order checks of guard 2 (E12 to E14) are green on base by design: guard 1 has no engine code (the test is the guard); E8 and E10 read the real files, E9 and E11 prove the check on a synthetic duplicate; E12 to E14 check that the reader already ignores order | | 10 green ids, 11 red ids |
| 2026-11-12 | guard 3 (R197 A): an existing register row is edited only on master by the orderer (MW-053); branches only add rows, so the same-line case stays rare. The commit rule itself is `ORDERER_RULE` in `engine/core.py` | | the same sentence is one README line at the end of «Moving cards» |
| 2026-11-12 | red commit: tests, card, register row and changelog line only | f0c9493 | 11 red ids, as in «Red run» below |
| 2026-11-12 | green commit (the commit holding this row, after f0c9493): `.gitattributes` with the two lines, a final newline on `cards/REGISTER.md`, `engine/register.py` `parse` skips a line that is not a row instead of stopping (the only engine change), one README line | | the card's 21 ids pass; with `tests/core`, `tests/test_meta_cards.py` and `tests/test_register.py`: 1774 passed in 31.69 s |
| 2026-11-12 | coverage, `python -m coverage run --branch -m pytest` on the four test files, report for `engine/register.py` | | the changed line of `parse` is not among the missed lines (missed: 50-52, 60, 64, 68, 72, 81, 99-101, 106-110, 116-120, 124, 153, 158-169, 178, 186-192, 198-206, 215-240, 247-254, 259-261, 266-269, 273-292, 296-299, 303-307, 312-334, 343-350, 355-362, 369-370, 377, 381-392, 398-405, 412-430: code this card did not change) |
| 2026-11-12 | whole suite once, `python -m pytest -q`, term scan included, on the tree with the green change: 3 failed, 3434 passed, 4 deselected in 1529.83 s. Two failures were mine (the shell test file held an address-shaped literal, term scan group B, and lacked the `engine_repo` marker though it reads `.gitattributes`): fixed by a separate tests-only commit before the green commit (the wrong test, not the code); the three affected tests and the shell file then pass, 8 passed. The third, `tests/test_repo_scan.py::test_repository_has_no_term_hits` at `cards/MW-077-perf-rest/CARD.md:42` group B #11, is in a file this card does not touch and was there at base 8cc1d84 (not fixed here: another card's file; reported to the orderer) | | no new failure from this card; the suite was not repeated whole |
| 2026-11-12 | the union driver leaves ours first, then theirs: E4 and E6 pin that order; the docs say the order of added lines is not promised, so a git release that changes it fails those two ids, and the fix is the literal, not the driver | | verified on the installed git |
| 2026-11-12 | table: acceptance row -> test node -> red seen -> green. E1 -> test_the_attributes_file_holds_the_two_union_lines -> yes -> yes; E2 -> test_git_reads_union_for_both_files -> yes -> yes; E3 -> test_changelog_merge_exits_zero -> yes -> yes; E4 -> test_changelog_merge_keeps_each_line_once_and_the_heading -> yes -> yes; E5 -> test_register_merge_exits_zero -> yes -> yes; E6 -> test_register_merge_keeps_each_row_once_on_its_own_line -> yes -> yes; E7 -> test_register_merge_without_the_attributes_conflicts -> yes -> yes; E8 -> test_the_real_changelog_has_no_card_line_twice_in_a_section -> no, green on base by design -> yes; E9 -> test_a_card_line_twice_in_one_section_is_found -> no, same -> yes; E10 -> test_the_real_register_has_no_card_id_twice -> no, same -> yes; E11 -> test_a_register_card_id_twice_is_found -> no, same -> yes; E12 -> test_parse_gives_the_same_rows_in_either_order -> no, reader already order-free -> yes; E13 -> test_find_gives_the_same_row_in_either_order -> no, same -> yes; E14 -> test_closed_ids_are_the_same_in_either_order -> no, same -> yes; E15 -> test_a_stray_line_between_rows_loses_no_row -> yes -> yes; E16 -> test_both_union_files_end_with_a_newline -> yes -> yes | | all 16 rows green |
| 2026-11-13 | port onto 128e8d8 of f0c9493 1e76f3a 8497849, same test ids, R204: master moved (MW-084) and the append-only files conflicted; the whole suite runs in the merge gate (R204) | this commit | own files and tests/core pass |

### Red run

Command: `python -m pytest -q tests/test_mw082_attributes.py tests/test_mw082_duplicates.py tests/core/test_mw082_register_order.py tests/shell/test_mw082_union_merge.py`. Every new id that must fail, fails:

- tests/test_mw082_attributes.py: `test_the_attributes_file_holds_the_two_union_lines`, `test_git_reads_union_for_both_files` (no `.gitattributes`), `test_both_union_files_end_with_a_newline` (the register has no final newline)
- tests/core/test_mw082_register_order.py: `test_a_stray_line_between_rows_loses_no_row[blank]`, `[text]`, `[marker]` (`parse` stops at the first line that is not a row)
- tests/shell/test_mw082_union_merge.py: all five (red by missing `.gitattributes` at the repository root)
- result: 11 failed, 10 passed in 5.64 s; the 10 passed are the green-by-design ids named above
