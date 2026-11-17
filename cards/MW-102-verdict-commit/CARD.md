# MW-102: The orderer commits the verdict file of a card it ordered, under the close's row proof

| | |
|---|---|
| **Appetite** | 1.5 hours — from 2026-11-13 |
| **Status** | proposed |
| **Created / updated** | 2026-11-13 / 2026-11-13 |
| **Waiting for** | nothing |
| **Form** | card |
| **Decisions** | R254, R194, R196, R225 — ids only, no text copied from the ledger; a commit that changes a test names one |
| **Canon** | none for the commit of a verdict file: the basis is a real install where a closed card's verdict file waited uncommitted because no session could commit it, and ruling R254 |
| **Paths** | `engine/core.py`, `engine/gate_commit.py`, `engine/verdicts.py`, `engine/manifest.json`, `tests/`, `README.md`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-102-verdict-commit/CARD.md` |

## 1. Goal

«the orderer's commit scope includes tests/verdicts/<card>.md for every card it ordered; the holder stays refused for that path; a commit that stages it runs the same row proof as close» — ruling R254, 2026-11-13.

## Acceptance examples

Each row becomes a test; `card close` needs every row to name one. E1 to E11: the pure core; E12 to E21: the shell on a real git repo; E22 and E23: the replay of the real case; E24 to E26: the real hook; E27 to E29: the documents; E30: the nearest allow of E3 and E4.

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | the orderer stages the verdict file of a card it ordered | refused `file-not-in-card` | allowed | tests/core/test_mw102_verdict_commit_core.py::test_the_orderer_commits_the_verdict_file_of_a_card_it_ordered |
| E2 | the orderer stages the verdict file of a card it did not order (nearest deny of E1) | refused `file-not-in-card` | refused `file-not-in-card`, the text names the orderer of that card | tests/core/test_mw102_verdict_commit_core.py::test_the_orderer_is_refused_the_verdict_file_of_a_card_it_did_not_order |
| E3 | the holder stages its own card's verdict file, its Paths cover it | allowed by the Paths | refused `file-not-in-card`, «the holder never commits its own card's verdict file» | tests/core/test_mw102_verdict_commit_core.py::test_the_holder_never_commits_its_own_cards_verdict_file |
| E4 | a holder whose Paths cover another card's verdict file stages it | allowed by the Paths | refused `file-not-in-card` | tests/core/test_mw102_verdict_commit_core.py::test_a_holder_whose_paths_cover_another_cards_verdict_file_is_refused |
| E5 | the orderer stages its verdict file and CARD.md | refused | allowed | tests/core/test_mw102_verdict_commit_core.py::test_the_orderer_commits_the_verdict_file_with_card_md |
| E6 | the proof facts say a row is unproven | n/a | refused `verdict-unproven`, the text names the node and the proof text | tests/core/test_mw102_verdict_commit_core.py::test_an_unproven_row_is_refused_naming_the_node |
| E7 | the proof facts say every row is proved (nearest allow of E6) | n/a | allowed | tests/core/test_mw102_verdict_commit_core.py::test_rows_that_are_all_proved_are_allowed |
| E8 | the message of the verdict commit names no card id | n/a | refused `commit-message-card` | tests/core/test_mw102_verdict_commit_core.py::test_a_message_that_names_no_card_of_the_verdict_commit_is_refused |
| E9 | the message names the card (nearest allow of E8) | n/a | allowed | tests/core/test_mw102_verdict_commit_core.py::test_a_message_that_names_the_card_of_the_verdict_commit_is_allowed |
| E10 | an orderer that also holds the card stages its verdict file | n/a | refused `file-not-in-card`, the holder text | tests/core/test_mw102_verdict_commit_core.py::test_an_orderer_that_also_holds_the_card_is_refused_its_verdict_file |
| E11 | the orderer sentence of a refusal | names folders and REGISTER.md | also names the verdict file of each card it ordered | tests/core/test_mw102_verdict_commit_core.py::test_the_orderer_sentence_names_the_verdict_file |
| E12 | an edited row staged, the working copy clean (the same as the index), committed from the index | n/a | refused `verdict-unproven`, judged by the staged rows | tests/shell/test_mw102_verdict_commit_facts.py::test_an_edited_row_staged_with_a_clean_working_copy_is_unproven |
| E13 | a clean row staged, the working copy edited, committed from the index (nearest allow of E12) | n/a | allowed | tests/shell/test_mw102_verdict_commit_facts.py::test_a_clean_row_staged_with_an_edited_working_copy_is_allowed |
| E14 | the `-- <paths>` form with an edited working file | n/a | refused `verdict-unproven`, judged by the working file | tests/shell/test_mw102_verdict_commit_facts.py::test_the_paths_form_judges_the_working_file |
| E15 | the `-- <paths>` form with a row the command wrote (nearest allow of E14) | n/a | allowed | tests/shell/test_mw102_verdict_commit_facts.py::test_the_paths_form_with_a_row_written_by_the_command_is_allowed |
| E16 | a typed row with no record | n/a | refused `verdict-unproven` | tests/shell/test_mw102_verdict_commit_facts.py::test_a_typed_row_with_no_record_is_unproven |
| E17 | rows written through the real `verdict add` | n/a | allowed | tests/shell/test_mw102_verdict_commit_facts.py::test_rows_written_by_verdict_add_are_allowed |
| E18 | a typed row of a node no Acceptance row names | n/a | not judged, allowed | tests/shell/test_mw102_verdict_commit_facts.py::test_a_row_for_a_node_no_acceptance_row_names_is_not_judged |
| E19 | a profile with no `outbox.checkers`, a typed row | n/a | the proof is skipped, allowed | tests/shell/test_mw102_verdict_commit_facts.py::test_with_no_checkers_the_proof_is_skipped |
| E20 | `cards.verdicts: off`, a typed row | n/a | the proof is skipped, allowed | tests/shell/test_mw102_verdict_commit_facts.py::test_with_cards_verdicts_off_the_proof_is_skipped |
| E21 | git cannot show the staged blob | n/a | refused `commit-unreadable`, never allowed | tests/shell/test_mw102_verdict_commit_facts.py::test_a_staged_blob_git_cannot_show_refuses_unreadable |
| E22 | replay of the real case: an orderer holding no card, a closed card it ordered, a verdict file whose rows have records | refused `file-not-in-card`, «this session holds no open card (no card is taken)» | allowed | tests/shell/test_mw102_replay.py::test_replay_the_orderer_of_a_closed_card_commits_its_verdict_file |
| E23 | the same file staged by a session that ordered no card (nearest deny of E22) | refused `file-not-in-card`, «this session holds no open card» | refused `file-not-in-card`, the text names the orderer of the card | tests/shell/test_mw102_replay.py::test_replay_a_session_that_ordered_no_card_is_refused_the_file |
| E24 | through the real hook: the holder commits its own card's verdict file | n/a | deny `file-not-in-card` | tests/test_mw102_e2e.py::test_the_holder_commits_its_own_verdict_file_and_the_real_hook_denies |
| E25 | through the real hook: the orderer commits a typed row | n/a | deny `verdict-unproven` | tests/test_mw102_e2e.py::test_the_orderer_commits_a_typed_row_and_the_real_hook_denies |
| E26 | through the real hook: the orderer commits rows the command wrote (nearest allow) | n/a | allow | tests/test_mw102_e2e.py::test_the_orderer_commits_rows_written_by_verdict_add_and_the_real_hook_allows |
| E27 | register row, changelog line, card | none | present, the changelog line last in the top section | tests/test_mw102_docs.py::test_register_changelog_and_card_name_the_card |
| E28 | the README paragraph | none | last paragraph of the section of the verdict command paragraph; names the sequence verdict add, commit, close, status commit | tests/test_mw102_docs.py::test_the_readme_paragraph_names_the_sequence |
| E29 | the reason id `verdict-unproven` | not a reason of `commit_files` | in the core's REASONS and in the manifest entry `commit_files` | tests/test_mw102_docs.py::test_the_reason_is_declared_in_the_core_and_the_manifest |
| E30 | the holder stages a plain test file inside its Paths (nearest allow of E3 and E4) | n/a | allowed | tests/core/test_mw102_verdict_commit_core.py::test_the_holder_commits_a_plain_test_file_inside_its_paths |

## 8. Log

One line per step. No re-run of a check or an agent round without a new input named in the Log row.

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-13 | Red proof: the 30 new ids, run before any engine code (core and e2e together, then shell, replay and docs) | 95eca0e | core 12 failed with `Facts` and `Ordered` lacking the new fields, e2e 3 failed, shell facts 10, replay 2 and docs 3 failed: 30 of 30 new ids red, none passed. The first run of the core file was red by a collection `TypeError` and the e2e fixture failed on a Paths entry `tests/` that `card open` refuses as too wide; both fixed in the red commit by building the `Ordered` rows in functions and giving CARD-002 the Paths `tests/verdicts/`. The commit message says 31 ids: the right count is 30 |
| 2026-11-13 | Tests-only commit: two existing checks change before the code (R254): the MW-101 changelog line no longer has to be last, and the real-hook coverage list exempts `verdict-unproven` with a pointer to the MW-102 real-hook test | 129ad57 | no test weakened; the message also says the README paragraph check was relaxed, it was not, see commit a52e49b |
| 2026-11-13 | Tests-only commit: two defects of my own tests found when the code ran: E30 staged a file outside the holder Paths, and the typed-row helper wrote into a folder that did not exist (E16, E19, E20, E21 failed on the folder, not on the gate); expectations unchanged | dea2cd7 | the five ids then passed; cause removed and the run repeated: 24 passed |
| 2026-11-13 | Tests-only commit: two more existing checks change (R254): the MW-101 README paragraph check finds its paragraph anywhere in the section, and the commit_files manifest check lists ten reason ids; the ORDERER_RULE sentence keeps its old text as a prefix, so no existing expected text changed | a52e49b | the wiring check and the MW-101 document check were red on the green code until this commit |
| 2026-11-13 | Green: the engine change, README paragraph at the end of the MW-080 section, register row, changelog line, manifest reason | 0ae2df9 | all 30 ids green; no test edited in this commit |
| 2026-11-13 | Coverage of my engine lines: `python -m coverage run --branch -m pytest` of my core, shell and replay tests, report of `engine/core.py`, `engine/gate_commit.py`, `engine/verdicts.py` | 0ae2df9 | missed changed lines: none of mine; the diff also lists core.py:381 (the old `return verdict` after the rule-without-test check) and verdicts.py:68 (the old `return []` of `rows_of`), which are not new code; no partial branch on a new line |
| 2026-11-13 | Run: own tests, tests/core, tests/test_meta_cards.py, tests/test_register.py, tests/test_repo_scan.py, tests/test_install.py and the commit-gate, verdict and document tests the change touches, `-n 4` (whole suite not run, owner 13.11) | 0ae2df9 | 2385 passed in 37 s, the NDA scan files included |
| 2026-11-13 | acceptance E1 | 95eca0e / 0ae2df9 | tests/core/test_mw102_verdict_commit_core.py::test_the_orderer_commits_the_verdict_file_of_a_card_it_ordered: red seen yes, green yes |
| 2026-11-13 | acceptance E2 | 95eca0e / 0ae2df9 | tests/core/test_mw102_verdict_commit_core.py::test_the_orderer_is_refused_the_verdict_file_of_a_card_it_did_not_order: red seen yes, green yes |
| 2026-11-13 | acceptance E3 | 95eca0e / 0ae2df9 | tests/core/test_mw102_verdict_commit_core.py::test_the_holder_never_commits_its_own_cards_verdict_file: red seen yes, green yes |
| 2026-11-13 | acceptance E4 | 95eca0e / 0ae2df9 | tests/core/test_mw102_verdict_commit_core.py::test_a_holder_whose_paths_cover_another_cards_verdict_file_is_refused: red seen yes, green yes |
| 2026-11-13 | acceptance E5 | 95eca0e / 0ae2df9 | tests/core/test_mw102_verdict_commit_core.py::test_the_orderer_commits_the_verdict_file_with_card_md: red seen yes, green yes |
| 2026-11-13 | acceptance E6 | 95eca0e / 0ae2df9 | tests/core/test_mw102_verdict_commit_core.py::test_an_unproven_row_is_refused_naming_the_node: red seen yes, green yes |
| 2026-11-13 | acceptance E7 | 95eca0e / 0ae2df9 | tests/core/test_mw102_verdict_commit_core.py::test_rows_that_are_all_proved_are_allowed: red seen yes, green yes |
| 2026-11-13 | acceptance E8 | 95eca0e / 0ae2df9 | tests/core/test_mw102_verdict_commit_core.py::test_a_message_that_names_no_card_of_the_verdict_commit_is_refused: red seen yes, green yes |
| 2026-11-13 | acceptance E9 | 95eca0e / 0ae2df9 | tests/core/test_mw102_verdict_commit_core.py::test_a_message_that_names_the_card_of_the_verdict_commit_is_allowed: red seen yes, green yes |
| 2026-11-13 | acceptance E10 | 95eca0e / 0ae2df9 | tests/core/test_mw102_verdict_commit_core.py::test_an_orderer_that_also_holds_the_card_is_refused_its_verdict_file: red seen yes, green yes |
| 2026-11-13 | acceptance E11 | 95eca0e / 0ae2df9 | tests/core/test_mw102_verdict_commit_core.py::test_the_orderer_sentence_names_the_verdict_file: red seen yes, green yes |
| 2026-11-13 | acceptance E12 | 95eca0e / 0ae2df9 | tests/shell/test_mw102_verdict_commit_facts.py::test_an_edited_row_staged_with_a_clean_working_copy_is_unproven: red seen yes, green yes |
| 2026-11-13 | acceptance E13 | 95eca0e / 0ae2df9 | tests/shell/test_mw102_verdict_commit_facts.py::test_a_clean_row_staged_with_an_edited_working_copy_is_allowed: red seen yes, green yes |
| 2026-11-13 | acceptance E14 | 95eca0e / 0ae2df9 | tests/shell/test_mw102_verdict_commit_facts.py::test_the_paths_form_judges_the_working_file: red seen yes, green yes |
| 2026-11-13 | acceptance E15 | 95eca0e / 0ae2df9 | tests/shell/test_mw102_verdict_commit_facts.py::test_the_paths_form_with_a_row_written_by_the_command_is_allowed: red seen yes, green yes |
| 2026-11-13 | acceptance E16 | 95eca0e / 0ae2df9 | tests/shell/test_mw102_verdict_commit_facts.py::test_a_typed_row_with_no_record_is_unproven: red seen yes, green yes |
| 2026-11-13 | acceptance E17 | 95eca0e / 0ae2df9 | tests/shell/test_mw102_verdict_commit_facts.py::test_rows_written_by_verdict_add_are_allowed: red seen yes, green yes |
| 2026-11-13 | acceptance E18 | 95eca0e / 0ae2df9 | tests/shell/test_mw102_verdict_commit_facts.py::test_a_row_for_a_node_no_acceptance_row_names_is_not_judged: red seen yes, green yes |
| 2026-11-13 | acceptance E19 | 95eca0e / 0ae2df9 | tests/shell/test_mw102_verdict_commit_facts.py::test_with_no_checkers_the_proof_is_skipped: red seen yes, green yes |
| 2026-11-13 | acceptance E20 | 95eca0e / 0ae2df9 | tests/shell/test_mw102_verdict_commit_facts.py::test_with_cards_verdicts_off_the_proof_is_skipped: red seen yes, green yes |
| 2026-11-13 | acceptance E21 | 95eca0e / 0ae2df9 | tests/shell/test_mw102_verdict_commit_facts.py::test_a_staged_blob_git_cannot_show_refuses_unreadable: red seen yes, green yes |
| 2026-11-13 | acceptance E22 | 95eca0e / 0ae2df9 | tests/shell/test_mw102_replay.py::test_replay_the_orderer_of_a_closed_card_commits_its_verdict_file: red seen yes, green yes |
| 2026-11-13 | acceptance E23 | 95eca0e / 0ae2df9 | tests/shell/test_mw102_replay.py::test_replay_a_session_that_ordered_no_card_is_refused_the_file: red seen yes, green yes |
| 2026-11-13 | acceptance E24 | 95eca0e / 0ae2df9 | tests/test_mw102_e2e.py::test_the_holder_commits_its_own_verdict_file_and_the_real_hook_denies: red seen yes, green yes |
| 2026-11-13 | acceptance E25 | 95eca0e / 0ae2df9 | tests/test_mw102_e2e.py::test_the_orderer_commits_a_typed_row_and_the_real_hook_denies: red seen yes, green yes |
| 2026-11-13 | acceptance E26 | 95eca0e / 0ae2df9 | tests/test_mw102_e2e.py::test_the_orderer_commits_rows_written_by_verdict_add_and_the_real_hook_allows: red seen yes, green yes |
| 2026-11-13 | acceptance E27 | 95eca0e / 0ae2df9 | tests/test_mw102_docs.py::test_register_changelog_and_card_name_the_card: red seen yes, green yes |
| 2026-11-13 | acceptance E28 | 95eca0e / 0ae2df9 | tests/test_mw102_docs.py::test_the_readme_paragraph_names_the_sequence: red seen yes, green yes |
| 2026-11-13 | acceptance E29 | 95eca0e / 0ae2df9 | tests/test_mw102_docs.py::test_the_reason_is_declared_in_the_core_and_the_manifest: red seen yes, green yes |
| 2026-11-13 | acceptance E30 | 95eca0e / 0ae2df9 | tests/core/test_mw102_verdict_commit_core.py::test_the_holder_commits_a_plain_test_file_inside_its_paths: red seen yes, green yes |
