# MW-103: A registered lead's write outside the repository is lead-no-edit, except a narrow default list of the harness's own state folders

| | |
|---|---|
| **Appetite** | 1.5 hours — from 2026-11-14 |
| **Status** | proposed |
| **Created / updated** | 2026-11-14 / 2026-11-14 |
| **Waiting for** | nothing |
| **Form** | card |
| **Decisions** | R255, R255b — ids only, no text copied from the ledger; a commit that changes a test names one |
| **Canon** | none for a lead's write outside the repository: the basis is a real install where a lead holding no card wrote four note files outside the task repository and the gate let them pass, and rulings R255 and R255b |
| **Paths** | `engine/core_session.py`, `engine/gate_lead.py`, `engine/profiles.py`, `engine/profile.schema.json`, `engine/defaults.json`, `engine/KEYS.md`, `tests/`, `README.md`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-103-lead-outside/CARD.md` |

How to use: see `cards/_TEMPLATE/CARD.md`.

## 1. Goal

«for a registered lead, an edit-tool path or a shell write outside the repository is `lead-no-edit` too ... except the harness's own state folders, a narrow default list a profile may extend; the settings files and the hooks folders match nothing» — rulings R255 and R255b, 2026-11-14.

## Acceptance examples

Each row becomes a test; `card close` needs every row to name one. E1 to E7: the pure core; E8 to E22: the shell expansion and match; E23 and E24: the shell redirect; E25 to E27: the real hook; E28: the replay; E29 to E31: the documents; E32: the profile accessor.

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | a lead's edit record outside the repository, not matched | not judged, allowed | refused `lead-no-edit` naming the raw path | tests/core/test_mw103_outside_core.py::test_a_lead_edit_outside_the_repository_that_matches_nothing_is_refused |
| E2 | the same record, matched (nearest allow of E1) | allowed | allowed | tests/core/test_mw103_outside_core.py::test_a_lead_edit_outside_the_repository_that_matches_the_list_is_allowed |
| E3 | two outside edit records, one matched and one not | allowed | refused naming the unmatched one | tests/core/test_mw103_outside_core.py::test_two_outside_edit_records_one_unmatched_is_refused_naming_it |
| E4 | a lead's ORDER.md of its own card (nearest allow) | allowed | allowed | tests/core/test_mw103_outside_core.py::test_a_lead_own_order_file_is_still_allowed |
| E5 | a session that is no lead writes outside | allowed | allowed, not judged | tests/core/test_mw103_outside_core.py::test_a_session_that_is_no_lead_is_not_judged_outside |
| E6 | a lead's shell write outside, not matched, then matched, then one of each | allowed | refused naming the raw path; allowed; refused naming the unmatched one | tests/core/test_mw103_outside_core.py::test_a_lead_shell_write_outside_is_judged_by_its_record |
| E7 | the refusal text of an outside path | n/a | names the path, prints the passed list, hands the work to a builder; a variable path is still refused first | tests/core/test_mw103_outside_core.py::test_the_outside_refusal_names_the_path_and_the_passed_list |
| E8 | a lead's Write to `<home>/.claude/projects/p/memory/m.md` | allowed | allowed | tests/shell/test_mw103_outside_facts.py::test_a_lead_write_to_its_memory_folder_is_allowed |
| E9 | a lead's Write to `<home>/.claude/settings.json` | allowed | refused `lead-no-edit` | tests/shell/test_mw103_outside_facts.py::test_a_lead_write_to_the_settings_file_is_refused |
| E10 | a lead's Write to `<home>/.claude/settings.local.json` | allowed | refused `lead-no-edit` | tests/shell/test_mw103_outside_facts.py::test_a_lead_write_to_the_local_settings_file_is_refused |
| E11 | a lead's Write to `<home>/.claude/hooks/x.py` | allowed | refused `lead-no-edit` | tests/shell/test_mw103_outside_facts.py::test_a_lead_write_to_the_home_hooks_folder_is_refused |
| E12 | a lead's Write to `<temp>/claude/x/.claude/hooks/h.py` (the deny beats the list) | allowed | refused `lead-no-edit` | tests/shell/test_mw103_outside_facts.py::test_the_hooks_deny_beats_the_temp_pattern |
| E13 | a lead's Write to `<home>/.claude/plans/a.md` | allowed | allowed | tests/shell/test_mw103_outside_facts.py::test_a_lead_write_to_the_plans_folder_is_allowed |
| E14 | a lead's Write to `<temp>/claude/s/x.txt` | allowed | allowed | tests/shell/test_mw103_outside_facts.py::test_a_lead_write_to_the_harness_temp_folder_is_allowed |
| E15 | a lead's Write to `<temp>/other/x.txt` | allowed | refused `lead-no-edit` | tests/shell/test_mw103_outside_facts.py::test_a_lead_write_to_another_temp_folder_is_refused |
| E16 | a lead's Write to `<home>/.claude/projects/p/memory/../../../settings.json` | allowed | refused `lead-no-edit` | tests/shell/test_mw103_outside_facts.py::test_a_path_that_climbs_out_of_memory_to_the_settings_file_is_refused |
| E17 | a relative path `../notes/a.md` from a cwd inside the repository | allowed | refused, joined to the cwd | tests/shell/test_mw103_outside_facts.py::test_a_relative_path_is_joined_to_the_cwd_and_refused |
| E18 | a lead's Write to `~/.claude/plans/a.md` | allowed | allowed | tests/shell/test_mw103_outside_facts.py::test_a_tilde_path_is_read_from_the_home_and_allowed |
| E19 | (Windows) mixed case and backslashes in a memory path | allowed | matched as the same path, allowed | tests/shell/test_mw103_outside_facts.py::test_windows_mixed_case_and_backslashes_match_the_same_path |
| E20 | (Windows) the 8.3 short name and the long name of the fake temp folder | allowed | both matched, allowed | tests/shell/test_mw103_outside_facts.py::test_windows_short_and_long_temp_names_both_match |
| E21 | a profile adds an absolute folder | the folder refused | the folder allowed, the defaults still allowed; a profile pattern that re-allows the settings files is still refused | tests/shell/test_mw103_outside_facts.py::test_a_profile_adds_a_folder_and_cannot_reopen_the_settings_files |
| E22 | a profile list with a relative pattern, an empty string or a non-list | accepted as unknown key | `profile-invalid` | tests/shell/test_mw103_outside_facts.py::test_a_bad_outside_writable_list_is_profile_invalid |
| E23 | a lead's `echo x > <temp>/claude/s/x.txt` | allowed | allowed | tests/shell/test_mw103_outside_facts.py::test_a_lead_redirect_to_the_harness_temp_folder_is_allowed |
| E24 | a lead's `echo x > <notes folder>/a.md` | allowed | refused `lead-no-edit` | tests/shell/test_mw103_outside_facts.py::test_a_lead_redirect_to_the_notes_folder_is_refused |
| E25 | the real hook: a lead's Write to the notes folder | allowed | deny `lead-no-edit` | tests/test_mw103_outside_e2e.py::test_the_real_hook_refuses_a_lead_write_to_the_notes_folder |
| E26 | the real hook: a lead's Write to its memory folder (nearest allow of E25) | allowed | allow | tests/test_mw103_outside_e2e.py::test_the_real_hook_allows_a_lead_write_to_its_memory_folder |
| E27 | the real hook: a non-lead's Write outside | allowed | allow, not judged | tests/test_mw103_outside_e2e.py::test_the_real_hook_allows_a_non_lead_write_outside |
| E28 | replay of the four note files: a registered lead holding no card writes `<fake>/project_x/analysis/notes/<name>.md` | allowed at 5419bf8 | deny `lead-no-edit` | tests/test_mw103_outside_e2e.py::test_replay_a_lead_with_no_card_writing_note_files_outside_is_refused[note_one]; tests/test_mw103_outside_e2e.py::test_replay_a_lead_with_no_card_writing_note_files_outside_is_refused[note_two]; tests/test_mw103_outside_e2e.py::test_replay_a_lead_with_no_card_writing_note_files_outside_is_refused[note_three]; tests/test_mw103_outside_e2e.py::test_replay_a_lead_with_no_card_writing_note_files_outside_is_refused[note_four] |
| E29 | `leads.outside_writable` in `defaults.json` and the schema | absent | the three patterns, an array of strings in the schema | tests/test_mw103_outside_docs.py::test_defaults_and_schema_hold_the_three_patterns |
| E30 | KEYS.md rows and counts | no row | a row in the added keys, a row in the engine defaults, the counts 30 in `defaults.json` | tests/test_mw103_outside_docs.py::test_keys_md_has_the_rows_and_the_counts |
| E31 | README paragraph, register row, changelog line | none | one paragraph, one row, one line, each at the end | tests/test_mw103_outside_docs.py::test_readme_register_and_changelog_name_the_card |
| E32 | a profile's unusable items and a repeat of a default | n/a | skipped; a usable item follows the three defaults | tests/shell/test_mw103_outside_facts.py::test_the_accessor_skips_unusable_items_and_repeats_no_default |

## 8. Log

One line per step. No re-run of a check or an agent round without a new input named in the Log row.

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-14 | card written, Acceptance table first | 12fa0c0 | E1 to E31 named; engine base 5419bf8 |
| 2026-11-14 | existing checks changed before the code, R255: three core rows and one shell test expected an outside write to be not judged, the key checks count the new key | 41364c7 | tests-only commit; red at the base for the changed expectations |
| 2026-11-14 | red commit, tests only | 7739f87 | core file not collectable, red by missing core_session.OutsideRecord; shell 22 of 22 failed; e2e 5 of 7 failed; docs 3 of 3 failed; E26 and E27 pass at the base by design: today everything outside is allowed, so the nearest allows hold; the red commit message says 4 of 6 for the e2e, the run shows 5 of 7 |
| 2026-11-14 | existing check changed, R255b: the MW-017 schema check pinned the leads group to two keys | 0fc424c | tests-only commit, found by the first green run, red at the base of the code |
| 2026-11-14 | one new row E32 and its test, found by the coverage run of the new branches | d0891f6 | tests-only commit, red by missing profiles.outside_writable at that commit (HEAD held 0 uses of the name) |
| 2026-11-14 | green commit | 681533c | every red id passes; the engine files and documents only, no test edited |
| 2026-11-14 | run, order set with -n 4 (tests/core, my four files, test_session_facts, test_meta_cards, test_register, test_repo_scan, test_install, test_keys, test_defaults, test_mw078_keys, test_mw017_shared, test_mw017_docs, test_mw028_lead_authors, test_manifest, test_helpers, test_profile, test_e2e_gates; the whole suite is void here, owner 13.11) | 681533c | 2707 passed in 72.41 s, the NDA scan files included |
| 2026-11-14 | coverage with branches of my engine lines, my files plus tests/core/test_session_decide.py, test_session_facts.py, test_helpers.py, test_profile.py | 681533c | core_session.py 100 percent, 0 missed; gate_lead.py missed 161-162 only (the existing prompt-sweep handler, not a line of this card); profiles.py and helpers.py: no missed line or branch among the lines this card adds |
| 2026-11-14 | decision of mine, not in the order: a path outside the repository with no record in the facts is refused, so a shell that forgets the record never opens the gate | 681533c | core test test_an_outside_path_with_no_record_is_refused |
| 2026-11-14 | note: shell redirects to the null sinks (/dev/null, NUL) never reach the gate, the reader drops them | 681533c | tests/shell/test_session_facts.py::the-reader row a-redirect-into-dev-null-allows stays green |
| 2026-11-14 | acceptance E1 | 681533c | tests/core/test_mw103_outside_core.py::test_a_lead_edit_outside_the_repository_that_matches_nothing_is_refused: red by missing core_session.OutsideRecord (collection error), green yes |
| 2026-11-14 | acceptance E2 | 681533c | tests/core/test_mw103_outside_core.py::test_a_lead_edit_outside_the_repository_that_matches_the_list_is_allowed: red by missing core_session.OutsideRecord, green yes |
| 2026-11-14 | acceptance E3 | 681533c | tests/core/test_mw103_outside_core.py::test_two_outside_edit_records_one_unmatched_is_refused_naming_it: red by missing core_session.OutsideRecord, green yes |
| 2026-11-14 | acceptance E4 | 681533c | tests/core/test_mw103_outside_core.py::test_a_lead_own_order_file_is_still_allowed: red by missing core_session.OutsideRecord, green yes |
| 2026-11-14 | acceptance E5 | 681533c | tests/core/test_mw103_outside_core.py::test_a_session_that_is_no_lead_is_not_judged_outside: red by missing core_session.OutsideRecord, green yes |
| 2026-11-14 | acceptance E6 | 681533c | tests/core/test_mw103_outside_core.py::test_a_lead_shell_write_outside_is_judged_by_its_record: red by missing core_session.OutsideRecord, five ids, green yes |
| 2026-11-14 | acceptance E7 | 681533c | tests/core/test_mw103_outside_core.py::test_the_outside_refusal_names_the_path_and_the_passed_list: red by missing core_session.OutsideRecord, three ids, green yes |
| 2026-11-14 | acceptance E8 | 681533c | tests/shell/test_mw103_outside_facts.py::test_a_lead_write_to_its_memory_folder_is_allowed: red by missing gate_lead.outside_allowed, green yes |
| 2026-11-14 | acceptance E9 | 681533c | tests/shell/test_mw103_outside_facts.py::test_a_lead_write_to_the_settings_file_is_refused: red: allowed at the base, green yes |
| 2026-11-14 | acceptance E10 | 681533c | tests/shell/test_mw103_outside_facts.py::test_a_lead_write_to_the_local_settings_file_is_refused: red: allowed at the base, green yes |
| 2026-11-14 | acceptance E11 | 681533c | tests/shell/test_mw103_outside_facts.py::test_a_lead_write_to_the_home_hooks_folder_is_refused: red: allowed at the base, green yes |
| 2026-11-14 | acceptance E12 | 681533c | tests/shell/test_mw103_outside_facts.py::test_the_hooks_deny_beats_the_temp_pattern: red: allowed at the base, green yes |
| 2026-11-14 | acceptance E13 | 681533c | tests/shell/test_mw103_outside_facts.py::test_a_lead_write_to_the_plans_folder_is_allowed: red by missing gate_lead.outside_allowed, green yes |
| 2026-11-14 | acceptance E14 | 681533c | tests/shell/test_mw103_outside_facts.py::test_a_lead_write_to_the_harness_temp_folder_is_allowed: red by missing gate_lead.outside_allowed, green yes |
| 2026-11-14 | acceptance E15 | 681533c | tests/shell/test_mw103_outside_facts.py::test_a_lead_write_to_another_temp_folder_is_refused: red: allowed at the base, green yes |
| 2026-11-14 | acceptance E16 | 681533c | tests/shell/test_mw103_outside_facts.py::test_a_path_that_climbs_out_of_memory_to_the_settings_file_is_refused: red: allowed at the base, green yes |
| 2026-11-14 | acceptance E17 | 681533c | tests/shell/test_mw103_outside_facts.py::test_a_relative_path_is_joined_to_the_cwd_and_refused: red: allowed at the base, green yes |
| 2026-11-14 | acceptance E18 | 681533c | tests/shell/test_mw103_outside_facts.py::test_a_tilde_path_is_read_from_the_home_and_allowed: red by missing gate_lead.outside_allowed, green yes |
| 2026-11-14 | acceptance E19 | 681533c | tests/shell/test_mw103_outside_facts.py::test_windows_mixed_case_and_backslashes_match_the_same_path: red by missing gate_lead.outside_allowed, ran on Windows, green yes |
| 2026-11-14 | acceptance E20 | 681533c | tests/shell/test_mw103_outside_facts.py::test_windows_short_and_long_temp_names_both_match: red by missing gate_lead.outside_allowed, ran on Windows with a real short name, green yes |
| 2026-11-14 | acceptance E21 | 681533c | tests/shell/test_mw103_outside_facts.py::test_a_profile_adds_a_folder_and_cannot_reopen_the_settings_files: red by missing gate_lead.outside_allowed, green yes |
| 2026-11-14 | acceptance E22 | 681533c | tests/shell/test_mw103_outside_facts.py::test_a_bad_outside_writable_list_is_profile_invalid: red: six ids, the bad lists failed on the unknown-key error text, the good list failed as not allowed here, green yes |
| 2026-11-14 | acceptance E23 | 681533c | tests/shell/test_mw103_outside_facts.py::test_a_lead_redirect_to_the_harness_temp_folder_is_allowed: red by missing gate_lead.outside_allowed, green yes |
| 2026-11-14 | acceptance E24 | 681533c | tests/shell/test_mw103_outside_facts.py::test_a_lead_redirect_to_the_notes_folder_is_refused: red: allowed at the base, green yes |
| 2026-11-14 | acceptance E25 | 681533c | tests/test_mw103_outside_e2e.py::test_the_real_hook_refuses_a_lead_write_to_the_notes_folder: red: allow at the base, green yes |
| 2026-11-14 | acceptance E26 | 681533c | tests/test_mw103_outside_e2e.py::test_the_real_hook_allows_a_lead_write_to_its_memory_folder: red seen NO: allow at the base by design, a guard against over-refusal, green yes |
| 2026-11-14 | acceptance E27 | 681533c | tests/test_mw103_outside_e2e.py::test_the_real_hook_allows_a_non_lead_write_outside: red seen NO: allow at the base by design, a guard against over-refusal, green yes |
| 2026-11-14 | acceptance E28 | 681533c | tests/test_mw103_outside_e2e.py::test_replay_a_lead_with_no_card_writing_note_files_outside_is_refused, four ids: red: allow at the base for all four note names, green yes |
| 2026-11-14 | acceptance E29 | 681533c | tests/test_mw103_outside_docs.py::test_defaults_and_schema_hold_the_three_patterns: red: key absent, green yes |
| 2026-11-14 | acceptance E30 | 681533c | tests/test_mw103_outside_docs.py::test_keys_md_has_the_rows_and_the_counts: red: rows absent, green yes |
| 2026-11-14 | acceptance E31 | 681533c | tests/test_mw103_outside_docs.py::test_readme_register_and_changelog_name_the_card: red: README paragraph and changelog line absent, green yes |
| 2026-11-14 | acceptance E32 | 681533c | tests/shell/test_mw103_outside_facts.py::test_the_accessor_skips_unusable_items_and_repeats_no_default: red by missing profiles.outside_writable at d0891f6, green yes |
| 2026-11-14 | NDA: the folder name of the real case's task, used as the notes folder in my tests and the E28 row, replaced by a generic name; the earlier commits 12fa0c0 and 7739f87 still hold the word in history, so the merge should squash them or the owner decides | next commit | tests-only commit, then this card; term scan and the 52 tests of the four files, the scan and the meta test pass |
| 2026-11-14 | merge red, 2 failed: the MW-103 docs test read README and was not marked engine_repo, and the MW-102 docs test pinned its changelog line as last; both fixed, no expectation of the engine changed | next commit | MW-102 check loosened in 9766f54, R256; my docs test marked engine_repo and no last-line pin; run with -n 4: 2752 passed in 82.90 s, with test_mw029_fast_guard and every test_mw*_docs |
