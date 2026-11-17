# MW-090: The red proof judges the card's case_map lines under a named decision

| | |
|---|---|
| **Appetite** | 1 day — the most this work is worth, from the creation date |
| **Status** | proposed |
| **Created / updated** | 2026-11-13 / 2026-11-13 |
| **Waiting for** | nothing |
| **Form** | card |
| **Decisions** | R219, R220, R222, R223, R224, R225 — ids only, no text copied from the ledger; a commit that changes a test names one |
| **Canon** | `none for case_map, rename, decision pattern, after a ledger search by retro-oper10` |
| **Paths** | `engine/core_red.py`, `engine/gate_commit_tests.py`, `engine/profiles.py`, `engine/profile.schema.json`, `engine/KEYS.md`, `engine/manifest.json`, `README.md`, `tests/core/test_red_decide.py`, `tests/shell/test_red_facts.py`, `tests/shell/test_red_profile.py`, `tests/test_e2e_gates.py`, `tests/test_keys.py`, `tests/test_mw005_gate.py`, `tests/test_mw005_readme.py`, `tests/test_mw056_docs.py`, `cards/MW-090-case-map-gate/CARD.md`, `cards/REGISTER.md`, `CHANGELOG.md` |

## 1. Goal

«G2 reads the committing card's case_map.md with four conditions, each a table row» — retro-chief10, ruling R219, 2026-11-13.

This card: refusals only (R225 1). After it a well-formed case_map line under a counting decision changes nothing yet; a bad line, or a new line with no counting decision, is refused.

## Acceptance examples

Each row becomes a test; `card close` needs every row to name one.

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | a new mapping or dropped line, no decision names a counting row | not judged | refused `case-map-no-decision`, text says no decision matched | tests/core/test_red_decide.py::test_a_new_mapping_or_dropped_line_with_no_decision_is_refused_as_case_map_no_decision |
| E2 | a named decision that does not count (closed status, by this session, not a ledger row) | not judged | refused `case-map-no-decision`, text names the status, the session or the missing row | tests/core/test_red_decide.py::test_a_named_decision_that_does_not_count_is_refused_with_its_why |
| E3 | a valid mapping under a counting decision | not judged | allowed | tests/core/test_red_decide.py::test_a_valid_mapping_under_a_counting_decision_is_allowed |
| E4 | several named decisions, one counts | not judged | allowed | tests/core/test_red_decide.py::test_one_counting_decision_among_several_named_is_enough |
| E5 | a line already at HEAD (any order), a removed line, comment and blank lines | not judged | not judged | tests/core/test_red_decide.py::test_only_new_mapping_and_dropped_lines_are_judged |
| E6 | a commit that does not stage the case_map | judged as today | judged as today | tests/core/test_red_decide.py::test_a_commit_that_does_not_stage_the_case_map_is_judged_as_before |
| E7 | a left that is no static id of its file at HEAD (also a dropped line's left, a path form, a file outside the test roots) | not judged | refused `case-map-unknown-left`, the text names the fact | tests/core/test_red_decide.py::test_a_left_that_is_not_a_test_id_at_head_is_refused_as_unknown_left |
| E8 | a left that still exists in the committed tree | not judged | refused `case-map-unknown-left`, the text says it is a copy | tests/core/test_red_decide.py::test_a_left_that_still_exists_in_the_committed_tree_is_refused_as_unknown_left |
| E9 | a left in another card's red record | not judged | refused `case-map-unknown-left`, the text names that card | tests/core/test_red_decide.py::test_a_left_in_another_cards_red_record_is_refused_as_unknown_left |
| E10 | a dropped line whose left was at HEAD and is gone | not judged | allowed | tests/core/test_red_decide.py::test_a_dropped_line_whose_left_is_gone_from_the_tree_is_allowed |
| E11 | a right that is no static id in the committed tree, or outside the test roots | not judged | refused `case-map-unknown-right` | tests/core/test_red_decide.py::test_a_right_that_is_not_a_test_id_in_the_committed_tree_is_refused_as_unknown_right |
| E12 | two lefts with one right | not judged | refused `case-map-merge`, the text gives `A -> N` and `B -> dropped: merged into N, <why>` | tests/core/test_red_decide.py::test_two_lefts_with_one_right_are_refused_as_a_merge_with_the_dropped_form |
| E13 | a right that already exists at HEAD | not judged | refused `case-map-merge`, the text says merge into an existing test and gives the form | tests/core/test_red_decide.py::test_a_right_that_already_exists_at_head_is_refused_as_a_merge_into_an_existing_test |
| E14 | a new line whose right is the right of an old line | not judged | refused `case-map-merge` | tests/core/test_red_decide.py::test_a_new_line_that_shares_its_right_with_an_old_line_is_refused_as_a_merge |
| E15 | the merge in the dropped form | not judged | allowed | tests/core/test_red_decide.py::test_the_merge_written_with_the_dropped_form_is_allowed |
| E16 | the same line twice | not judged | counts as one, allowed | tests/core/test_red_decide.py::test_the_same_line_twice_counts_as_one_and_is_not_a_duplicate_right_side |
| E17 | a new line the parser calls malformed | not judged | refused `case-map-malformed` | tests/core/test_red_decide.py::test_a_new_line_the_parser_calls_malformed_is_refused_as_case_map_malformed |
| E18 | a side with a `[case]` suffix | not judged | refused `case-map-malformed` | tests/core/test_red_decide.py::test_a_side_with_a_case_suffix_is_refused_as_case_map_malformed |
| E19 | one left with a mapping and a dropped line | not judged | refused `case-map-malformed` | tests/core/test_red_decide.py::test_a_left_with_a_mapping_and_a_dropped_line_is_refused_as_malformed |
| E20 | one left with two dropped lines | not judged | refused `case-map-malformed` | tests/core/test_red_decide.py::test_a_left_with_two_dropped_lines_is_refused_as_malformed |
| E21 | a new line whose left has a line of the other kind at HEAD | not judged | refused `case-map-malformed` | tests/core/test_red_decide.py::test_a_new_line_whose_left_clashes_with_an_old_line_is_refused_as_malformed |
| E22 | a split of one left into several rights | not judged | allowed | tests/core/test_red_decide.py::test_a_split_of_one_left_into_several_rights_is_allowed |
| E23 | a malformed line, no decision counts | not judged | refused `case-map-malformed` and `case-map-no-decision` is not the only reason | tests/core/test_red_decide.py::test_a_malformed_line_is_refused_even_when_no_decision_counts |
| E24 | a bad case_map and a passing new test | not judged | the first reason is the case_map one, `red-not-proven` follows | tests/core/test_red_decide.py::test_the_case_map_refusal_comes_before_red_not_proven |
| E25 | a code commit with a bad case_map line | not judged | refused with the case_map reason | tests/core/test_red_decide.py::test_a_code_commit_is_judged_by_the_case_map_rules_too |
| E26 | more than ten refused lines of one reason | not capped | ten named, then a count of the rest | tests/core/test_red_decide.py::test_more_than_ten_refusals_of_one_reason_are_capped_with_a_count |
| E27 | the files the shell must read | none | the files of the sides of the new lines under a test root, sorted | tests/core/test_red_decide.py::test_the_files_to_read_are_the_sides_files_of_the_new_lines_under_a_test_root |
| E28 | a new line, the message names no decision, real repository | allowed | refused `case-map-no-decision` | tests/shell/test_red_facts.py::test_a_new_case_map_line_with_no_decision_in_the_message_is_refused |
| E29 | a valid rename, the message matches the pattern, no ledger | allowed | allowed, the pattern alone decides | tests/shell/test_red_facts.py::test_a_decision_in_the_message_counts_by_the_pattern_alone_when_the_root_has_no_ledger |
| E30 | a case_map staged bad and fixed in the working copy | not judged | the staged text is judged, refused | tests/shell/test_red_facts.py::test_the_committed_case_map_is_judged_and_not_the_working_copy |
| E31 | a left file that is not staged | not judged | read at HEAD, its id still exists in the tree, refused `case-map-unknown-left` | tests/shell/test_red_facts.py::test_an_unstaged_left_file_is_read_at_head_and_its_id_still_exists_in_the_tree |
| E32 | a left in another card's row of the red record | not judged | refused `case-map-unknown-left` naming that card | tests/shell/test_red_facts.py::test_a_left_in_the_red_record_of_another_card_is_refused |
| E33 | a left in the same card's row, or in a row of a commit never made | not judged | not another card's record, allowed | tests/shell/test_red_facts.py::test_a_red_record_of_the_same_card_or_of_a_commit_never_made_is_not_another_cards |
| E34 | a decision that is a ledger row in force, by another session | not judged | counts, allowed | tests/shell/test_red_facts.py::test_a_ledger_decision_that_is_in_force_and_not_by_the_session_counts |
| E35 | a ledger decision closed, by this session, or no row | not judged | refused `case-map-no-decision` with its why | tests/shell/test_red_facts.py::test_a_ledger_decision_that_does_not_count_is_refused_with_its_why |
| E36 | a docs-only commit that stages a bad case_map line | allowed | refused | tests/shell/test_red_facts.py::test_a_docs_only_commit_that_stages_a_bad_case_map_line_is_refused |
| E37 | a docs-only commit that stages comment lines only | allowed | allowed, no suite run | tests/shell/test_red_facts.py::test_a_docs_only_commit_of_comment_lines_is_allowed_and_runs_no_suite |
| E38 | a bad case_map that the commit does not stage | not judged | not judged | tests/shell/test_red_facts.py::test_a_case_map_that_is_not_staged_is_not_judged |
| E39 | watch mode | not judged | a warning with the same reason id and text | tests/shell/test_red_facts.py::test_in_watch_mode_a_case_map_refusal_is_a_warning_with_the_same_reason |
| E40 | a decision pattern that does not compile | no key | no decision, refused `case-map-no-decision` | tests/shell/test_red_facts.py::test_a_decision_pattern_that_does_not_compile_is_no_decision |
| E41 | the real hook, no decision | allowed | deny `case-map-no-decision` | tests/test_e2e_gates.py::test_refusal_through_the_real_hook[case_map_no_decision] |
| E42 | the real hook, unknown left | allowed | deny `case-map-unknown-left` | tests/test_e2e_gates.py::test_refusal_through_the_real_hook[case_map_unknown_left] |
| E43 | the real hook, unknown right | allowed | deny `case-map-unknown-right` | tests/test_e2e_gates.py::test_refusal_through_the_real_hook[case_map_unknown_right] |
| E44 | the real hook, merge | allowed | deny `case-map-merge` | tests/test_e2e_gates.py::test_refusal_through_the_real_hook[case_map_merge] |
| E45 | the real hook, malformed | allowed | deny `case-map-malformed` | tests/test_e2e_gates.py::test_refusal_through_the_real_hook[case_map_malformed] |
| E46 | the key `tests.red_proof.decision_pattern`, a string or empty | not in the schema | accepted | tests/shell/test_red_profile.py::test_the_decision_pattern_key_accepts_a_string |
| E47 | the same key with a value that is not a string | not in the schema | rejected, the error says string | tests/shell/test_red_profile.py::test_the_decision_pattern_key_rejects_a_value_that_is_not_a_string |
| E48 | the profile read of the key | none | empty when missing or unusable, else the string | tests/shell/test_red_profile.py::test_the_decision_pattern_defaults_to_empty_and_an_unusable_value_is_empty |
| E49 | KEYS.md and the schema leaves | no row | one Added-keys row, leaves equal | tests/test_keys.py::test_keys_md_has_one_line_per_draft_key |
| E50 | the README on the key | says one setting | names the key, no longer says one setting | tests/shell/test_red_profile.py::test_the_readme_names_the_decision_pattern_key_and_not_one_setting |
| E51 | the manifest entry of the gate | 9 reason ids | 14 reason ids | tests/test_mw005_gate.py::test_the_gate_is_in_the_shell_group_after_the_lock_gate_and_has_a_switch |
| E52 | the README section names every reason id | 9 | 14 | tests/test_mw005_readme.py::test_the_section_states_the_rules_the_keys_and_every_reason |
| E53 | the docs test of the manifest ids | 9 | 14 | tests/test_mw056_docs.py::test_the_manifest_declares_the_warn_reason_of_the_allow_line |
| E54 | the five new ids are declared | not declared | declared | tests/shell/test_red_profile.py::test_the_manifest_declares_the_five_case_map_reason_ids |
| E55 | every declared reason has a real-hook row | rows match the manifest | rows and manifest match with the five new ids | tests/test_e2e_gates.py::test_every_declared_reason_has_a_row_or_a_stated_exemption |

## 8. Log

One line per step. No re-run of a check or an agent round without a new input named in the Log row.

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-13 | red run of the 8 changed test files, python -m pytest -q -p no:xdist --continue-on-collection-errors -rA | 973d99f | 80 failed, 193 passed in 201.10s; failing by file: tests/core/test_red_decide.py 47 cases (TypeError: Facts has no field case_map, no decision or case_map_files yet), tests/shell/test_red_facts.py 11, tests/shell/test_red_profile.py 12, tests/test_e2e_gates.py 6 (the five new rows and the meta test), tests/test_keys.py 1, tests/test_mw005_gate.py 1, tests/test_mw005_readme.py 1, tests/test_mw056_docs.py 1 |
| 2026-11-13 | new ids that pass at red: six, each a Checks guard of unchanged behaviour (an allow row, the nearest allow of a red deny row), so not a defect: test_a_decision_in_the_message_counts_by_the_pattern_alone_when_the_root_has_no_ledger; test_a_red_record_of_the_same_card_or_of_a_commit_never_made_is_not_another_cards both cases; test_a_ledger_decision_that_is_in_force_and_not_by_the_session_counts; test_a_docs_only_commit_of_comment_lines_is_allowed_and_runs_no_suite; test_a_case_map_that_is_not_staged_is_not_judged | 973d99f | PASSED in the red run, green yes; the one-line report to the orderer said seven, the count is six |
| 2026-11-13 | the full list of new ids with their result is the acceptance rows E1 to E55 below: 50 rows red seen yes, 5 rows (E29, E33, E34, E37, E38) hold the 6 Checks guards that pass at red; the fixture and the committed tests changed under T7 decision R225: tests/test_e2e_gates.py (CARD_PATHS gets tests/test_m.py, the proj fixture commits tests/test_m.py with two tests, the second test at HEAD the merge row needs), tests/test_keys.py, tests/test_mw005_gate.py, tests/test_mw005_readme.py, tests/test_mw056_docs.py (exact sets), tests/shell/test_red_facts.py (the import of write), tests/shell/test_red_profile.py | 973d99f | every other row that reads tests/test_a.py still passes: tests/test_a.py is untouched, the rows that write it write a file, not read the HEAD test list |
| 2026-11-13 | acceptance E1 | 9190fd0 | tests/core/test_red_decide.py::test_a_new_mapping_or_dropped_line_with_no_decision_is_refused_as_case_map_no_decision: red seen yes, green yes |
| 2026-11-13 | acceptance E2 | 9190fd0 | tests/core/test_red_decide.py::test_a_named_decision_that_does_not_count_is_refused_with_its_why: red seen yes, green yes |
| 2026-11-13 | acceptance E3 | 9190fd0 | tests/core/test_red_decide.py::test_a_valid_mapping_under_a_counting_decision_is_allowed: red seen yes (TypeError), green yes |
| 2026-11-13 | acceptance E4 | 9190fd0 | tests/core/test_red_decide.py::test_one_counting_decision_among_several_named_is_enough: red seen yes, green yes |
| 2026-11-13 | acceptance E5 | 9190fd0 | tests/core/test_red_decide.py::test_only_new_mapping_and_dropped_lines_are_judged: red seen yes, all five cases, green yes |
| 2026-11-13 | acceptance E6 | 9190fd0 | tests/core/test_red_decide.py::test_a_commit_that_does_not_stage_the_case_map_is_judged_as_before: red seen yes, green yes |
| 2026-11-13 | acceptance E7 | 9190fd0 | tests/core/test_red_decide.py::test_a_left_that_is_not_a_test_id_at_head_is_refused_as_unknown_left: red seen yes, all four cases, green yes |
| 2026-11-13 | acceptance E8 | 9190fd0 | tests/core/test_red_decide.py::test_a_left_that_still_exists_in_the_committed_tree_is_refused_as_unknown_left: red seen yes, green yes |
| 2026-11-13 | acceptance E9 | 9190fd0 | tests/core/test_red_decide.py::test_a_left_in_another_cards_red_record_is_refused_as_unknown_left: red seen yes, green yes |
| 2026-11-13 | acceptance E10 | 9190fd0 | tests/core/test_red_decide.py::test_a_dropped_line_whose_left_is_gone_from_the_tree_is_allowed: red seen yes, green yes |
| 2026-11-13 | acceptance E11 | 9190fd0 | tests/core/test_red_decide.py::test_a_right_that_is_not_a_test_id_in_the_committed_tree_is_refused_as_unknown_right: red seen yes, green yes |
| 2026-11-13 | acceptance E12 | 9190fd0 | tests/core/test_red_decide.py::test_two_lefts_with_one_right_are_refused_as_a_merge_with_the_dropped_form: red seen yes, green yes |
| 2026-11-13 | acceptance E13 | 9190fd0 | tests/core/test_red_decide.py::test_a_right_that_already_exists_at_head_is_refused_as_a_merge_into_an_existing_test: red seen yes, green yes |
| 2026-11-13 | acceptance E14 | 9190fd0 | tests/core/test_red_decide.py::test_a_new_line_that_shares_its_right_with_an_old_line_is_refused_as_a_merge: red seen yes, green yes |
| 2026-11-13 | acceptance E15 | 9190fd0 | tests/core/test_red_decide.py::test_the_merge_written_with_the_dropped_form_is_allowed: red seen yes, green yes |
| 2026-11-13 | acceptance E16 | 9190fd0 | tests/core/test_red_decide.py::test_the_same_line_twice_counts_as_one_and_is_not_a_duplicate_right_side: red seen yes, green yes |
| 2026-11-13 | acceptance E17 | 9190fd0 | tests/core/test_red_decide.py::test_a_new_line_the_parser_calls_malformed_is_refused_as_case_map_malformed: red seen yes, green yes |
| 2026-11-13 | acceptance E18 | 9190fd0 | tests/core/test_red_decide.py::test_a_side_with_a_case_suffix_is_refused_as_case_map_malformed: red seen yes, green yes |
| 2026-11-13 | acceptance E19 | 9190fd0 | tests/core/test_red_decide.py::test_a_left_with_a_mapping_and_a_dropped_line_is_refused_as_malformed: red seen yes, green yes |
| 2026-11-13 | acceptance E20 | 9190fd0 | tests/core/test_red_decide.py::test_a_left_with_two_dropped_lines_is_refused_as_malformed: red seen yes, green yes |
| 2026-11-13 | acceptance E21 | 9190fd0 | tests/core/test_red_decide.py::test_a_new_line_whose_left_clashes_with_an_old_line_is_refused_as_malformed: red seen yes, green yes |
| 2026-11-13 | acceptance E22 | 9190fd0 | tests/core/test_red_decide.py::test_a_split_of_one_left_into_several_rights_is_allowed: red seen yes, green yes |
| 2026-11-13 | acceptance E23 | 9190fd0 | tests/core/test_red_decide.py::test_a_malformed_line_is_refused_even_when_no_decision_counts: red seen yes, green yes |
| 2026-11-13 | acceptance E24 | 9190fd0 | tests/core/test_red_decide.py::test_the_case_map_refusal_comes_before_red_not_proven: red seen yes, green yes |
| 2026-11-13 | acceptance E25 | 9190fd0 | tests/core/test_red_decide.py::test_a_code_commit_is_judged_by_the_case_map_rules_too: red seen yes, green yes |
| 2026-11-13 | acceptance E26 | 9190fd0 | tests/core/test_red_decide.py::test_more_than_ten_refusals_of_one_reason_are_capped_with_a_count: red seen yes, green yes |
| 2026-11-13 | acceptance E27 | 9190fd0 | tests/core/test_red_decide.py::test_the_files_to_read_are_the_sides_files_of_the_new_lines_under_a_test_root: red seen yes, green yes |
| 2026-11-13 | acceptance E28 | 9190fd0 | tests/shell/test_red_facts.py::test_a_new_case_map_line_with_no_decision_in_the_message_is_refused: red seen yes, green yes |
| 2026-11-13 | acceptance E29 | 9190fd0 | tests/shell/test_red_facts.py::test_a_decision_in_the_message_counts_by_the_pattern_alone_when_the_root_has_no_ledger: red seen n/a, Checks guard of unchanged behaviour, passes at red; green yes |
| 2026-11-13 | acceptance E30 | 9190fd0 | tests/shell/test_red_facts.py::test_the_committed_case_map_is_judged_and_not_the_working_copy: red seen yes, green yes |
| 2026-11-13 | acceptance E31 | 9190fd0 | tests/shell/test_red_facts.py::test_an_unstaged_left_file_is_read_at_head_and_its_id_still_exists_in_the_tree: red seen yes, green yes |
| 2026-11-13 | acceptance E32 | 9190fd0 | tests/shell/test_red_facts.py::test_a_left_in_the_red_record_of_another_card_is_refused: red seen yes, green yes |
| 2026-11-13 | acceptance E33 | 9190fd0 | tests/shell/test_red_facts.py::test_a_red_record_of_the_same_card_or_of_a_commit_never_made_is_not_another_cards: red seen n/a, Checks guard of unchanged behaviour, both cases pass at red; green yes |
| 2026-11-13 | acceptance E34 | 9190fd0 | tests/shell/test_red_facts.py::test_a_ledger_decision_that_is_in_force_and_not_by_the_session_counts: red seen n/a, Checks guard of unchanged behaviour, passes at red; green yes |
| 2026-11-13 | acceptance E35 | 9190fd0 | tests/shell/test_red_facts.py::test_a_ledger_decision_that_does_not_count_is_refused_with_its_why: red seen yes, four cases, green yes |
| 2026-11-13 | acceptance E36 | 9190fd0 | tests/shell/test_red_facts.py::test_a_docs_only_commit_that_stages_a_bad_case_map_line_is_refused: red seen yes, green yes |
| 2026-11-13 | acceptance E37 | 9190fd0 | tests/shell/test_red_facts.py::test_a_docs_only_commit_of_comment_lines_is_allowed_and_runs_no_suite: red seen n/a, Checks guard of unchanged behaviour, passes at red; green yes |
| 2026-11-13 | acceptance E38 | 9190fd0 | tests/shell/test_red_facts.py::test_a_case_map_that_is_not_staged_is_not_judged: red seen n/a, Checks guard of unchanged behaviour, passes at red; green yes |
| 2026-11-13 | acceptance E39 | 9190fd0 | tests/shell/test_red_facts.py::test_in_watch_mode_a_case_map_refusal_is_a_warning_with_the_same_reason: red seen yes, green yes |
| 2026-11-13 | acceptance E40 | 9190fd0 | tests/shell/test_red_facts.py::test_a_decision_pattern_that_does_not_compile_is_no_decision: red seen yes, green yes |
| 2026-11-13 | acceptance E41 | 9190fd0 | tests/test_e2e_gates.py::test_refusal_through_the_real_hook[case_map_no_decision]: red seen yes (allow, a docs-only commit was not judged), green yes |
| 2026-11-13 | acceptance E42 | 9190fd0 | tests/test_e2e_gates.py::test_refusal_through_the_real_hook[case_map_unknown_left]: red seen yes (profile-invalid, the key was not in the schema), green yes |
| 2026-11-13 | acceptance E43 | 9190fd0 | tests/test_e2e_gates.py::test_refusal_through_the_real_hook[case_map_unknown_right]: red seen yes (profile-invalid), green yes |
| 2026-11-13 | acceptance E44 | 9190fd0 | tests/test_e2e_gates.py::test_refusal_through_the_real_hook[case_map_merge]: red seen yes (profile-invalid), green yes |
| 2026-11-13 | acceptance E45 | 9190fd0 | tests/test_e2e_gates.py::test_refusal_through_the_real_hook[case_map_malformed]: red seen yes (profile-invalid), green yes |
| 2026-11-13 | acceptance E46 | 9190fd0 | tests/shell/test_red_profile.py::test_the_decision_pattern_key_accepts_a_string: red seen yes, green yes |
| 2026-11-13 | acceptance E47 | 9190fd0 | tests/shell/test_red_profile.py::test_the_decision_pattern_key_rejects_a_value_that_is_not_a_string: red seen yes, green yes |
| 2026-11-13 | acceptance E48 | 9190fd0 | tests/shell/test_red_profile.py::test_the_decision_pattern_defaults_to_empty_and_an_unusable_value_is_empty: red seen yes, green yes |
| 2026-11-13 | acceptance E49 | 9190fd0 | tests/test_keys.py::test_keys_md_has_one_line_per_draft_key: red seen yes (existing test, set changed under R225), green yes |
| 2026-11-13 | acceptance E50 | 9190fd0 | tests/shell/test_red_profile.py::test_the_readme_names_the_decision_pattern_key_and_not_one_setting: red seen yes, green yes |
| 2026-11-13 | acceptance E51 | 9190fd0 | tests/test_mw005_gate.py::test_the_gate_is_in_the_shell_group_after_the_lock_gate_and_has_a_switch: red seen yes (existing test, set changed under R225), green yes |
| 2026-11-13 | acceptance E52 | 9190fd0 | tests/test_mw005_readme.py::test_the_section_states_the_rules_the_keys_and_every_reason: red seen yes (existing test, count changed under R225), green yes |
| 2026-11-13 | acceptance E53 | 9190fd0 | tests/test_mw056_docs.py::test_the_manifest_declares_the_warn_reason_of_the_allow_line: red seen yes (existing test, set changed under R225), green yes |
| 2026-11-13 | acceptance E54 | 9190fd0 | tests/shell/test_red_profile.py::test_the_manifest_declares_the_five_case_map_reason_ids: red seen yes, green yes |
| 2026-11-13 | acceptance E55 | 9190fd0 | tests/test_e2e_gates.py::test_every_declared_reason_has_a_row_or_a_stated_exemption: red seen yes (five rows for ids the manifest did not declare yet), green yes |
| 2026-11-13 | green run of the 8 changed test files before the green commit | 9190fd0 | 273 passed in 202.52s, the 80 red ids and the 193 others |
| 2026-11-13 | how the message reaches _red_proof: _gate hands commit.message (None when the command carries none) to _red_proof as a new last argument and to _docs_commit; _decisions matches tests.red_proof.decision_pattern in it, and a root whose ledger file exists gets a flag per matched id (row, closed status, by this session) | 9190fd0 | proved by E28, E29, E34, E35 on real git repositories |
| 2026-11-13 | how the reason order puts the case_map refusals first: core_red.decide builds its refusals list from _case_map before _with_code or _tests_only, and the gate takes the reason id from the first refusal, which is what would[0] was | 9190fd0 | proved by E24 and E25; inside the case_map the order is no-decision, unknown-left, unknown-right, merge, malformed |
| 2026-11-13 | how a docs-only commit staging the case_map is judged: _gate calls _docs_commit for a commit of documents alone; with a held card, a pytest command and the card's case_map.md among the staged files it builds the facts without a suite run and lets core_red.decide judge, in watch mode a warning, else a refusal; any other docs-only commit is allowed as before | 9190fd0 | proved by E36, E37 and the e2e rows E41 and E45, which are docs-only commits |
| 2026-11-13 | design choices where the order is silent: D6 to D8 are not judged while no decision counts (the refusal is case-map-no-decision), D9 always is; a whole-map violation (merge, left in two kinds) is refused only when one of its lines is new against HEAD; R220's cap applies: ten lines named per reason, then N more, see the card's case_map.md; a decision that is no ledger row in a root with a ledger counts as not counting and the text says so; the empty pattern and a pattern that does not compile are no decision | 9190fd0 | recorded; E1 E2 E23 E26 E14 E21 E40 |
| 2026-11-13 | no ledger in the e2e baseline: the pattern alone decides there; the ledger level is proven by shell rows E34 and E35 | 9190fd0 | recorded |
| 2026-11-13 | known gap, R223 5b: a session can write a ledger row with another session's by; the later self-set facts card closes it | 9190fd0 | recorded |
| 2026-11-13 | MW-091 adds the status relaxation and the printing of dropped lines, MW-092 the record resolution; a valid line under a decision changes nothing in this card | 9190fd0 | recorded |
| 2026-11-13 | run 4a, first time: MKWAY_TEST_WORKERS=2 python -m pytest -q -n auto --dist loadgroup over the 41 files of the order | 9190fd0 | 1 failed, 3326 passed in 523.60s: tests/test_repo_scan.py::test_repository_has_no_term_hits, tests/shell/test_red_facts.py:311 group B, an id-like literal in a comment of this card's own test |
| 2026-11-13 | cause removed: the comment text of tests/shell/test_red_facts.py line 311 changed, comment only, no code; tests-only commit, T7 decision R225 | 779c414 | tests/test_repo_scan.py alone: 2 passed |
| 2026-11-13 | run 4a, second time, after the cause was removed (R216) | 779c414 | 3327 passed in 512.53s, no failed and no error |
| 2026-11-13 | run 4b: python -m coverage run --branch -m pytest -q -p no:xdist tests/core/test_red_decide.py tests/core/test_case_map_parse.py tests/shell/test_red_facts.py tests/shell/test_red_profile.py, then coverage report -m for engine/core_red.py, engine/gate_commit_tests.py, engine/profiles.py | 779c414 | 166 passed in 79.39s; engine/core_red.py 284 statements, 0 missed, 134 branches, 0 partial, 100 percent; engine/profiles.py: no missed line among the changed lines 325-331; engine/gate_commit_tests.py: missed lines among the changed ones 770-771 and 773 (_docs_commit: a docs-only commit with an unreadable tests command, with no card or with a command that is not pytest returns allow, no shell test of the changed function reaches them); the other missed lines of the file are not this card's |
| 2026-11-13 | run 4c: gate time, python -m pytest -q -p no:xdist --durations=0 on the shell node that commits with a case_map and on test_a_tests_only_commit_of_a_failing_new_test_runs_the_suite_and_records_the_id | 779c414 | call 2.24s for test_a_decision_in_the_message_counts_by_the_pattern_alone_when_the_root_has_no_ledger (stages three files, one run, one red record) against 1.71s for the other node: 0.53s more, the reads of the case_map and of the side files |
