# MW-089: One reader for case_map.md: a pure parser in core_red that every case_map test uses

| | |
|---|---|
| **Appetite** | 1 day — the most this work is worth, from the creation date |
| **Status** | proposed |
| **Created / updated** | 2026-11-13 / 2026-11-13 |
| **Waiting for** | nothing |
| **Form** | card |
| **Decisions** | R222, R223, R224 — ids only, no text copied from the ledger; a commit that changes a test names one |
| **Canon** | `none for case_map parser, after a ledger search by retro-oper10` |
| **Paths** | `engine/core_red.py`, `tests/core/test_case_map_parse.py`, `tests/test_meta_cards.py`, `tests/test_mw052_case_map.py`, `cards/MW-089-case-map-parser/CARD.md`, `cards/REGISTER.md`, `CHANGELOG.md` |

## 1. Goal

«MW-089a = one pure parser in core_red plus test_meta_cards and the three test files moved onto it (R223 is the T7 decision for touching those committed tests); the parser classifies every line (mapping, dropped, comment, blank, malformed) with line number and raw text, so the two «# kept:» readers read comment lines through it and no second regex survives» — retro-chief10, ruling R223, 2026-11-13.

## Acceptance examples

Each row becomes a test; `card close` needs every row to name one.

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | a mapping line | four readers, four regexes | kind mapping with old and new | tests/core/test_case_map_parse.py::test_a_line_is_classified_with_its_fields[mapping] |
| E2 | a dropped line | the same | kind dropped with old and why | tests/core/test_case_map_parse.py::test_a_line_is_classified_with_its_fields[dropped] |
| E3 | a split: two lines, one left side | a dict keeps the last | two entries | tests/core/test_case_map_parse.py::test_a_split_is_one_entry_per_line_with_the_same_left_side |
| E4 | a # comment | skipped by each reader | kind comment | tests/core/test_case_map_parse.py::test_a_line_is_classified_with_its_fields[hash_comment] |
| E5 | a > comment | skipped by each reader | kind comment | tests/core/test_case_map_parse.py::test_a_line_is_classified_with_its_fields[gt_comment] |
| E6 | a blank line | skipped by each reader | kind blank | tests/core/test_case_map_parse.py::test_a_line_is_classified_with_its_fields[blank] |
| E7 | a malformed line such as a -> b | each reader decides alone | kind malformed | tests/core/test_case_map_parse.py::test_a_line_is_classified_with_its_fields[malformed] |
| E8 | a kept comment, dash form | a regex in one test file | kept id and why | tests/core/test_case_map_parse.py::test_a_kept_comment_carries_its_id_and_why_in_either_form[dash_form] |
| E9 | a kept comment, parenthesis form | a regex in another test file | kept id and why | tests/core/test_case_map_parse.py::test_a_kept_comment_carries_its_id_and_why_in_either_form[paren_form] |
| E10 | a kept comment in neither form | not read | kept fields None | tests/core/test_case_map_parse.py::test_a_kept_comment_carries_its_id_and_why_in_either_form[neither_form] |
| E11 | a side without tests/ | stripped or refused by reader | kept as written | tests/core/test_case_map_parse.py::test_a_line_is_classified_with_its_fields[sides_as_written] |
| E12 | a CRLF line | handled by splitlines in each reader | raw text kept, kind from the stripped text | tests/core/test_case_map_parse.py::test_a_line_is_classified_with_its_fields[crlf_raw_kept] |
| E13 | line numbers | none | 1-based over every line kind | tests/core/test_case_map_parse.py::test_line_numbers_count_from_one_over_every_line_kind |
| E14 | test_meta_cards, ids of card rows exist | own regex | same result through the parser | tests/test_meta_cards.py::test_every_test_id_a_card_row_names_exists_or_has_a_case_map_line |
| E15 | test_meta_cards, map lines well formed | own regex | same result through the parser | tests/test_meta_cards.py::test_every_case_map_line_is_well_formed_and_its_right_side_exists |
| E16 | test_meta_cards, the checker can fail | own regex | same result through the parser | tests/test_meta_cards.py::test_the_checker_catches_a_missing_id_and_accepts_a_mapped_one |
| E17 | test_mw052, every old case mapped, dropped or kept | own regexes | same result through the parser | tests/test_mw052_case_map.py::test_every_old_case_has_a_new_home_or_is_dropped_or_kept_and_nothing_is_unmapped |
| E18 | no case_map line regex left in the two moved files | one in each | none | checked by reading: tests/test_meta_cards.py; checked by reading: tests/test_mw052_case_map.py |

## 8. Log

One line per step. No re-run of a check or an agent round without a new input named in the Log row.

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-13 | baseline: the four case_map readers before any change | bd75117 | 11 passed in 4.14s (test_meta_cards, test_mw052, test_mw064, test_mw065) |
| 2026-11-13 | red run of tests/core/test_case_map_parse.py | fe932ab | ImportError: cannot import name parse_case_map from core_red; 1 error in 0.34s; red by missing core_red, a module in the card Paths |
| 2026-11-13 | the parser type | ea3842a | NamedTuple CaseMapLine in engine/core_red.py: number, raw, kind, old, new, why, kept_id, kept_why; parse_case_map returns a list of them |
| 2026-11-13 | green run: test_case_map_parse.py with tests/core/test_red_is_pure.py | ea3842a | 14 passed in 0.23s |
| 2026-11-13 | acceptance E1 | ea3842a | tests/core/test_case_map_parse.py::test_a_line_is_classified_with_its_fields[mapping]: red seen yes, green yes |
| 2026-11-13 | acceptance E2 | ea3842a | tests/core/test_case_map_parse.py::test_a_line_is_classified_with_its_fields[dropped]: red seen yes, green yes |
| 2026-11-13 | acceptance E3 | ea3842a | tests/core/test_case_map_parse.py::test_a_split_is_one_entry_per_line_with_the_same_left_side: red seen yes, green yes |
| 2026-11-13 | acceptance E4 | ea3842a | tests/core/test_case_map_parse.py::test_a_line_is_classified_with_its_fields[hash_comment]: red seen yes, green yes |
| 2026-11-13 | acceptance E5 | ea3842a | tests/core/test_case_map_parse.py::test_a_line_is_classified_with_its_fields[gt_comment]: red seen yes, green yes |
| 2026-11-13 | acceptance E6 | ea3842a | tests/core/test_case_map_parse.py::test_a_line_is_classified_with_its_fields[blank]: red seen yes, green yes |
| 2026-11-13 | acceptance E7 | ea3842a | tests/core/test_case_map_parse.py::test_a_line_is_classified_with_its_fields[malformed]: red seen yes, green yes |
| 2026-11-13 | acceptance E8 | ea3842a | tests/core/test_case_map_parse.py::test_a_kept_comment_carries_its_id_and_why_in_either_form[dash_form]: red seen yes, green yes |
| 2026-11-13 | acceptance E9 | ea3842a | tests/core/test_case_map_parse.py::test_a_kept_comment_carries_its_id_and_why_in_either_form[paren_form]: red seen yes, green yes |
| 2026-11-13 | acceptance E10 | ea3842a | tests/core/test_case_map_parse.py::test_a_kept_comment_carries_its_id_and_why_in_either_form[neither_form]: red seen yes, green yes |
| 2026-11-13 | acceptance E11 | ea3842a | tests/core/test_case_map_parse.py::test_a_line_is_classified_with_its_fields[sides_as_written]: red seen yes, green yes |
| 2026-11-13 | acceptance E12 | ea3842a | tests/core/test_case_map_parse.py::test_a_line_is_classified_with_its_fields[crlf_raw_kept]: red seen yes, green yes |
| 2026-11-13 | acceptance E13 | ea3842a | tests/core/test_case_map_parse.py::test_line_numbers_count_from_one_over_every_line_kind: red seen yes, green yes |
| 2026-11-13 | acceptance E14 | e862293 | tests/test_meta_cards.py::test_every_test_id_a_card_row_names_exists_or_has_a_case_map_line: red seen no: existing tests moved onto the parser, same results, T7 decision R223; green yes |
| 2026-11-13 | acceptance E15 | e862293 | tests/test_meta_cards.py::test_every_case_map_line_is_well_formed_and_its_right_side_exists: red seen no: existing tests moved onto the parser, same results, T7 decision R223; green yes |
| 2026-11-13 | acceptance E16 | e862293 | tests/test_meta_cards.py::test_the_checker_catches_a_missing_id_and_accepts_a_mapped_one: red seen no: existing tests moved onto the parser, same results, T7 decision R223; green yes |
| 2026-11-13 | acceptance E17 | e862293 | tests/test_mw052_case_map.py::test_every_old_case_has_a_new_home_or_is_dropped_or_kept_and_nothing_is_unmapped: red seen no: existing tests moved onto the parser, same results, T7 decision R223; green yes |
| 2026-11-13 | acceptance E18 | e862293 | checked by reading: tests/test_meta_cards.py; checked by reading: tests/test_mw052_case_map.py: no case_map line regex is left in either file |
| 2026-11-13 | move run: the four readers after the move, git diff showed no hunk inside a test function including decorator lines | e862293 | 11 passed in 3.39s, same count as the baseline |
| 2026-11-13 | R224: not moved here, inline parsing in the test body: tests/test_mw064_case_map.py::test_every_old_case_has_a_new_home_or_a_dropped_reason_or_stays_and_nothing_is_unmapped and tests/test_mw064_case_map.py::test_a_module_whose_every_case_moved_is_one_docstring_line, tests/test_mw065_case_map.py::test_every_old_case_is_mapped_and_gone_or_is_a_wiring_case_that_stays; they move onto the parser in the wave C card whose partition holds them (the common wave C order carries that line; the card ids are set at wave C start) | e862293 | recorded; the three files are unchanged by this card |
| 2026-11-13 | R224: transitional loss, test_meta_cards parse_map keeps last-wins on a split, closed by wave C rewrite of test_meta_cards, covered meanwhile for new maps by MW-090 every-line check; MW-052 splits stay fully checked by test_mw052 | e862293 | recorded |
| 2026-11-13 | no refusal added: the common rules gate items do not apply | the commit that carries this line | recorded |
| 2026-11-13 | docs tests that read REGISTER.md or CHANGELOG.md check only their own card line; an appended line cannot change them | the commit that carries this line | recorded |
| 2026-11-13 | run 5a: tests/core, test_red_facts, the four readers, test_register, test_repo_scan, test_mw016_version, test_mw082_duplicates, test_mw082_attributes under MKWAY_TEST_WORKERS=2 | e862293 | 2083 passed in 44.09s; G8 warnings 1 (tests/test_mw082_attributes.py::test_git_reads_union_for_both_files, not a file of this card) |
| 2026-11-13 | run 5b: coverage of engine/core_red.py with test_case_map_parse, test_red_decide, test_red_facts | e862293 | 81 passed in 47.51s; engine/core_red.py 165 stmts, 0 missed, 68 branches, 0 partial, 100%; no missed lines |
