# MW-104: `mkway upgrade`: the owner's command installs a proven-green engine release into a granted task root, with one ledger row and one commit (a Python rewrite of mkup 1.0.0)

| | |
|---|---|
| **Appetite** | 3 hours — from 2026-11-14 |
| **Status** | proposed |
| **Created / updated** | 2026-11-14 / 2026-11-14 |
| **Waiting for** | nothing |
| **Form** | card |
| **Decisions** | R257, R257b, R257c, R257e, R257f, R257g, R257h, R256, R216 — ids only, no text copied from the ledger; a commit that changes a test names one |
| **Canon** | none for an engine command that installs a release into a task root: the basis is the mkup 1.0.0 behaviour and its spec, and rulings R257 to R257h |
| **Paths** | `engine/core_upgrade.py`, `engine/upgrade.py`, `engine/mkway.py`, `engine/core_lock.py`, `engine/KEYS.md`, `release.json`, `tests/`, `README.md`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-104-upgrade/CARD.md` |

## 1. Goal

«Python rewrite, one runtime; the 111 cases as parametrized tables over literals (S7); tagged release the public default, from-HEAD mode an internal flag; the engine reads nothing from mkcl's files (test command and merge-green record get engine-owned homes, paths as config values)» — ruling R257, 2026-11-14.

## Acceptance examples

Each row becomes a test; `card close` needs every row to name one. E1 to E2: purity of the new core; E3 to E42: the pure core; E43 to E74: the update, the green source and the narrow route on a real git repository with a stub engine; E75 to E82: the engine homes H0 to H3; E83 to E96: release mode and the downgrade guard; E97 to E100: the green record; E101 to E104: owner-only and the real engine end to end; E105 to E116: hermetic, the installed set, the documents and the batch branch list; E117 to E130: refusals the case table does not reach (found by the coverage of the two new modules). Gap H7 (R257h): the lock gate cannot hold a path outside the repository; the owner-only refusal covers the command line until a follow-up card adds absolute-path lock targets.

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | the new core module imports | n/a | only what core_install imports | tests/core/test_mw104_upgrade_pure.py::test_core_upgrade_imports_only_what_core_install_imports |
| E2 | the new core module calls | n/a | no file, process, print or clock function | tests/core/test_mw104_upgrade_pure.py::test_core_upgrade_calls_no_io_function |
| E3 | H1 pure choice: override set; override empty; Windows APPDATA; XDG; home | n/a | the folder and whether the override was used | tests/core/test_mw104_upgrade_core.py::test_the_upgrade_folder_is_chosen_from_env_platform_and_home |
| E4 | grant: two roots, one root, BOM, sibling roots, trailing separator | n/a | accepted | tests/core/test_mw104_upgrade_core.py::test_a_grant_is_accepted |
| E5 | grant: both root forms, none, empty, wildcard, absolute, climbing, target itself, duplicates, inside another, bad JSON, unknown key, bad target and shared | n/a | refused with the literal text | tests/core/test_mw104_upgrade_core.py::test_a_grant_is_refused |
| E6 | H2 grant holding engine, branch, python, mkcl-log or test-command | n/a | refused with T1 and the new home | tests/core/test_mw104_upgrade_core.py::test_a_grant_holding_a_moved_key_is_refused_with_its_new_home |
| E7 | the same grant without that key (nearest allow of E6) | n/a | accepted | tests/core/test_mw104_upgrade_core.py::test_the_same_grant_without_the_moved_key_is_accepted |
| E8 | no grant file | n/a | `There is no grant: <file> does not exist. Only the owner writes that file.` | tests/core/test_mw104_upgrade_core.py::test_the_missing_grant_text_names_the_file |
| E9 | root pick: one root needs no name, several need one, the full path of a listed root, blank | n/a | the grant's own spelling | tests/core/test_mw104_upgrade_core.py::test_a_root_is_picked |
| E10 | root pick: several roots no name, not listed, climbing, same prefix, other with one root | n/a | refused with the literal text | tests/core/test_mw104_upgrade_core.py::test_a_root_is_refused_by_the_pick |
| E11 | target: same folder, trailing separator, other capitals on Windows | n/a | accepted | tests/core/test_mw104_upgrade_core.py::test_the_target_is_accepted |
| E12 | target: empty, relative, not the grant's | n/a | refused with the literal text | tests/core/test_mw104_upgrade_core.py::test_the_target_is_refused |
| E13 | H3 release.json valid: text or list commands, slash branch | n/a | accepted, display form returned | tests/core/test_mw104_upgrade_core.py::test_release_config_is_accepted |
| E14 | H3 release.json: bad JSON, not an object, missing key, unknown key, bad branch `a..b`, bad full_command, bad narrow_paths | n/a | refused `release.json is invalid: <why>` | tests/core/test_mw104_upgrade_core.py::test_release_config_is_refused |
| E15 | H3 narrow_command missing, a number, an empty list, an empty text | n/a | refused `release.json is invalid: <why>` | tests/core/test_mw104_upgrade_core.py::test_narrow_command_is_refused_when_missing_or_wrong |
| E16 | H3 narrow_command as text or list (nearest allow of E15) | n/a | accepted | tests/core/test_mw104_upgrade_core.py::test_narrow_command_is_accepted_as_text_or_list |
| E17 | display form of a command (text trimmed, list joined, items with space or quote wrapped) | n/a | the literal form | tests/core/test_mw104_upgrade_core.py::test_the_display_form_of_a_command |
| E18 | pattern check: empty, backslash, absolute, inner wildcard, dot parts, valid | n/a | none or the reason | tests/core/test_mw104_upgrade_core.py::test_a_path_pattern_is_checked |
| E19 | matcher: every depth, exact only, sibling prefix, case, empty, dots and backslash, first rule wins | n/a | the rule index or none | tests/core/test_mw104_upgrade_core.py::test_the_narrow_matcher_picks_the_rule |
| E20 | the first path no rule covers | n/a | named, or none | tests/core/test_mw104_upgrade_core.py::test_the_first_uncovered_path_is_named |
| E21 | green record read: unparsable lines, blank lines, a list, a text | n/a | skipped | tests/core/test_mw104_upgrade_core.py::test_green_rows_skip_unparsable_lines |
| E22 | H4 the exact row proves a sha | n/a | the row | tests/core/test_mw104_upgrade_core.py::test_the_exact_green_row_proves_a_sha |
| E23 | H4 a row differing only in sha, repo, into, command or kind (nearest deny of E22) | n/a | proves nothing | tests/core/test_mw104_upgrade_core.py::test_a_green_row_differing_in_one_field_does_not_prove |
| E24 | green record with a bad sha, kind, missing field, bad branch, bad rule | n/a | refused naming the field | tests/core/test_mw104_upgrade_core.py::test_a_green_record_with_a_bad_field_is_refused |
| E25 | green record with every field good (nearest allow of E24) | n/a | accepted, the row | tests/core/test_mw104_upgrade_core.py::test_a_good_green_record_is_accepted |
| E26 | narrow walk: one, two, a batch | n/a | the full-green head and the count | tests/core/test_mw104_upgrade_core.py::test_the_narrow_walk_reaches_the_full_green_head |
| E27 | narrow walk: no result, no narrow claim, other command, no usable from, more than 200 | n/a | refused with the literal reason | tests/core/test_mw104_upgrade_core.py::test_the_narrow_walk_is_refused |
| E28 | narrow cover: covered, uncovered path, rename both sides, case, none changed, off the chain, unlisted | n/a | accepted or the literal reason | tests/core/test_mw104_upgrade_core.py::test_the_narrow_cover_accepts_or_refuses |
| E29 | tag refs text | n/a | tag and commit pairs, annotated and plain | tests/core/test_mw104_upgrade_core.py::test_tag_refs_are_parsed |
| E30 | tags: newest proven over newer unproven; version order over date; off the chain skipped; narrow row proves none | n/a | the tag and the skipped | tests/core/test_mw104_upgrade_core.py::test_the_newest_proven_tag_is_chosen |
| E31 | tags: none proven | n/a | `no release tag is proven green; nothing was changed` | tests/core/test_mw104_upgrade_core.py::test_no_proven_tag_is_refused |
| E32 | guard 7a to 8a: no source commit, not in repository, older (release and head), diverged, lower version, new major, unparsable version | n/a | refused with the literal text | tests/core/test_mw104_upgrade_core.py::test_the_downgrade_guard_refuses |
| E33 | guard: a newer release of the same major (nearest allow of E32) | n/a | allowed | tests/core/test_mw104_upgrade_core.py::test_the_guard_allows_a_newer_release |
| E34 | guard: chosen sha equals the lock source | n/a | up to date | tests/core/test_mw104_upgrade_core.py::test_an_equal_sha_is_up_to_date |
| E35 | install line with and without prefix, several paths | n/a | paths and prefix read | tests/core/test_mw104_upgrade_core.py::test_the_install_line_is_read |
| E36 | install line: missing, unsafe path, unknown message | n/a | refused with the literal text | tests/core/test_mw104_upgrade_core.py::test_the_install_line_is_refused |
| E37 | commit message form | n/a | `[prefix ]mkway install <sha8>` | tests/core/test_mw104_upgrade_core.py::test_the_commit_message_form |
| E38 | ledger quote: plain, narrow, release, override | n/a | the literal quote | tests/core/test_mw104_upgrade_core.py::test_the_ledger_quote_forms |
| E39 | final refusal texts | n/a | the literals of the table below | tests/core/test_mw104_upgrade_core.py::test_the_refusal_texts_are_the_literals |
| E40 | a command has no pieces left when every text is blank | n/a | refused | tests/core/test_mw104_upgrade_core.py::test_a_command_of_blank_texts_is_refused |
| E41 | versions: compared as numbers, not as text | n/a | 0.10.0 above 0.9.0 | tests/core/test_mw104_upgrade_core.py::test_versions_are_compared_as_numbers |
| E42 | release.json is not in the installed set | n/a | not in the set | tests/core/test_mw104_upgrade_core.py::test_release_json_is_not_in_the_installed_set |
| E43 | normal update: full row, tracked ledger, another file staged | n/a | one commit with only the printed paths and the ledger; the other file stays staged; lock source = new; ledger row by tool:mkway-upgrade; engine saw no CLAUDECODE; install args end `--shared` | tests/shell/test_mw104_upgrade_shell.py::test_a_proven_release_updates_with_one_commit |
| E44 | no commit prefix in the profile | n/a | message `mkway install <sha8>` | tests/shell/test_mw104_upgrade_shell.py::test_no_commit_prefix_gives_a_plain_message |
| E45 | no grant, unparsable grant, unknown key | n/a | refused and logged | tests/shell/test_mw104_upgrade_shell.py::test_a_missing_or_bad_grant_is_refused_and_logged |
| E46 | target not the grant's, empty, relative | n/a | refused, nothing changed | tests/shell/test_mw104_upgrade_shell.py::test_a_target_that_is_not_the_grants_is_refused |
| E47 | target with a trailing separator (nearest allow of E46) | n/a | accepted | tests/shell/test_mw104_upgrade_shell.py::test_a_target_with_a_trailing_separator_is_accepted |
| E48 | lock missing, root folder missing | n/a | refused naming mkway.lock | tests/shell/test_mw104_upgrade_shell.py::test_a_missing_lock_or_root_is_refused |
| E49 | the chosen head has no proving row: no file, other command, other repo, other branch, narrow kind alone | n/a | refused | tests/shell/test_mw104_upgrade_shell.py::test_a_head_without_a_proving_green_row_is_refused |
| E50 | engine dirty, engine on another branch | n/a | refused | tests/shell/test_mw104_upgrade_shell.py::test_a_dirty_engine_or_another_branch_is_refused |
| E51 | lock source equals the chosen sha | n/a | up to date, log has update and update-result | tests/shell/test_mw104_upgrade_shell.py::test_a_lock_at_the_chosen_sha_is_up_to_date |
| E52 | engine major differs from the lock | n/a | refused `A new major is the owner's hand` | tests/shell/test_mw104_upgrade_shell.py::test_a_new_major_is_refused |
| E53 | an install path modified or untracked | n/a | refused before a write, lists the lines | tests/shell/test_mw104_upgrade_shell.py::test_changes_in_an_install_path_are_refused_before_a_write |
| E54 | dry run | n/a | checks and exact commands, nothing changed | tests/shell/test_mw104_upgrade_shell.py::test_a_dry_run_changes_nothing_and_lists_checks_and_commands |
| E55 | the release's ledger command has no --by | n/a | refused before install: `has no --by option` | tests/shell/test_mw104_upgrade_shell.py::test_a_ledger_command_without_by_is_refused |
| E56 | install fails, unsafe path, no commit line, unknown message, ledger fails, commit fails | n/a | nothing committed, the answer says what was written | tests/shell/test_mw104_upgrade_shell.py::test_a_failing_install_commits_nothing |
| E57 | the log cannot be written | n/a | refused before install: `Cannot write the log` | tests/shell/test_mw104_upgrade_shell.py::test_a_log_that_cannot_be_written_is_refused |
| E58 | the grant lists two roots and the call names the second | n/a | only that root updated, one commit | tests/shell/test_mw104_upgrade_shell.py::test_the_call_names_the_second_root |
| E59 | the grant and the green record, every route | n/a | bytes before = bytes after | tests/shell/test_mw104_upgrade_shell.py::test_the_grant_and_the_green_record_are_never_written |
| E60 | the checks name the command that was checked | n/a | the detail holds the command | tests/shell/test_mw104_upgrade_shell.py::test_the_checks_name_the_command_that_was_checked |
| E61 | a green row of another command | n/a | refused naming both commands and `No green record` | tests/shell/test_mw104_upgrade_shell.py::test_a_row_of_another_command_names_both_commands |
| E62 | a head no merge ended at | n/a | the plain reason with no `ran "` text | tests/shell/test_mw104_upgrade_shell.py::test_a_head_no_merge_ended_at_has_the_plain_reason |
| E63 | from-head: one narrow row on top of the full-green head | n/a | installed, lock = that commit | tests/shell/test_mw104_upgrade_shell.py::test_one_narrow_merge_installs_from_head |
| E64 | the answer, the ledger row and the log on the narrow route | n/a | name the full-green head and the rule | tests/shell/test_mw104_upgrade_shell.py::test_the_narrow_route_is_named_in_answer_ledger_and_log |
| E65 | dry run on the narrow route | n/a | check names `narrow test runs only` and `rule 0`; nothing changed | tests/shell/test_mw104_upgrade_shell.py::test_a_narrow_dry_run_names_the_rule_and_changes_nothing |
| E66 | two narrow merges in a row | n/a | installed, `mergeResults` 2 | tests/shell/test_mw104_upgrade_shell.py::test_two_narrow_merges_install |
| E67 | a batch: one row whose from is the old head, two commits | n/a | installed | tests/shell/test_mw104_upgrade_shell.py::test_a_batch_of_two_commits_in_one_row_installs |
| E68 | a path outside the patterns | n/a | refused naming the path | tests/shell/test_mw104_upgrade_shell.py::test_a_path_outside_the_patterns_is_refused |
| E69 | a rename out of a card path | n/a | refused naming the destination | tests/shell/test_mw104_upgrade_shell.py::test_a_rename_out_of_a_covered_path_is_refused |
| E70 | a commit with no row, a row that is not narrow | n/a | refused `not produced by a mkcl merge` | tests/shell/test_mw104_upgrade_shell.py::test_a_broken_narrow_chain_is_refused |
| E71 | `Cards/a.md` against `cards/**` | n/a | refused naming `Cards/a.md` | tests/shell/test_mw104_upgrade_shell.py::test_the_narrow_match_is_case_sensitive |
| E72 | the full-green head is a run of another command | n/a | refused `full, passing test run` | tests/shell/test_mw104_upgrade_shell.py::test_a_full_green_head_of_another_command_is_refused |
| E73 | the full-green head is not on the first-parent chain | n/a | refused `first-parent` | tests/shell/test_mw104_upgrade_shell.py::test_a_full_green_head_off_the_first_parent_chain_is_refused |
| E74 | the head is itself full-green | n/a | installed, `narrow` absent | tests/shell/test_mw104_upgrade_shell.py::test_a_full_green_head_installs_with_no_narrow_rule |
| E75 | H0 run from an installed copy (a mkway.lock beside the engine folder) | n/a | refused `run mkway upgrade from the engine repository, not from an installed copy; nothing was changed` | tests/shell/test_mw104_upgrade_dirs.py::test_a_run_from_an_installed_copy_is_refused |
| E76 | H0 run from the engine repository (nearest allow of E75) | n/a | the engine repository is found | tests/shell/test_mw104_upgrade_dirs.py::test_a_run_from_the_engine_repository_finds_it |
| E77 | H1 shell: the folder inside a tree and not ignored | n/a | refused | tests/shell/test_mw104_upgrade_dirs.py::test_an_upgrade_folder_inside_a_tree_and_not_ignored_is_refused |
| E78 | H1 shell: the same folder ignored; a folder outside every tree (nearest allow of E77) | n/a | allowed | tests/shell/test_mw104_upgrade_dirs.py::test_an_upgrade_folder_ignored_or_outside_every_tree_is_allowed |
| E79 | H1/H6 override set | n/a | the path in the output and in the ledger quote | tests/shell/test_mw104_upgrade_dirs.py::test_the_override_is_printed_and_in_the_ledger_quote |
| E80 | H3 release.json missing at HEAD, invalid at HEAD | n/a | refused with the literal text | tests/shell/test_mw104_upgrade_dirs.py::test_a_missing_or_invalid_release_json_at_head_is_refused |
| E81 | H3 a dirty working release.json | n/a | refused as an unclean checkout, never read | tests/shell/test_mw104_upgrade_dirs.py::test_a_dirty_working_release_json_is_refused_unread |
| E82 | H3 a valid committed release.json (nearest allow of E80 and E81) | n/a | read from HEAD, accepted | tests/shell/test_mw104_upgrade_dirs.py::test_a_valid_committed_release_json_is_read_from_head |
| E83 | M1 newest proven tag over a newer unproven one | n/a | the proven tag installs, the other is named in the checks | tests/shell/test_mw104_upgrade_shell.py::test_the_newest_proven_tag_installs_over_a_newer_unproven_one |
| E84 | M1 version order beats tag date | n/a | the higher version | tests/shell/test_mw104_upgrade_shell.py::test_version_order_beats_tag_date |
| E85 | M1 a tag off the first-parent chain | n/a | skipped | tests/shell/test_mw104_upgrade_shell.py::test_a_tag_off_the_first_parent_chain_is_skipped |
| E86 | M1 no proven tag | n/a | refused `no release tag is proven green; nothing was changed` | tests/shell/test_mw104_upgrade_shell.py::test_no_proven_tag_is_refused |
| E87 | M1 a narrow chain on a tag | n/a | proves nothing, refused | tests/shell/test_mw104_upgrade_shell.py::test_a_narrow_chain_does_not_prove_a_tag |
| E88 | M1 the release's own install code | n/a | a release tree whose install writes a marker the HEAD code does not: the marker is written | tests/shell/test_mw104_upgrade_shell.py::test_release_mode_runs_the_releases_own_install_code |
| E89 | M2 from-head installs the HEAD commit | n/a | the answer has no `release`, the lock source is HEAD | tests/shell/test_mw104_upgrade_shell.py::test_from_head_installs_the_head_commit |
| E90 | guard 7a: lock source null | n/a | refused, nothing changed | tests/shell/test_mw104_upgrade_shell.py::test_a_lock_with_no_source_commit_is_refused |
| E91 | guard 7b: lock source not in the repository | n/a | refused, nothing changed | tests/shell/test_mw104_upgrade_shell.py::test_a_lock_source_not_in_the_engine_repository_is_refused |
| E92 | guard 7c: release older than the install | n/a | refused, nothing changed | tests/shell/test_mw104_upgrade_shell.py::test_a_release_older_than_the_install_is_refused |
| E93 | guard 7c: diverged | n/a | refused, nothing changed | tests/shell/test_mw104_upgrade_shell.py::test_a_diverged_install_is_refused |
| E94 | guard 8a: lower version | n/a | refused, nothing changed | tests/shell/test_mw104_upgrade_shell.py::test_a_lower_version_is_refused |
| E95 | guard: a newer release (nearest allow of E90 to E94) | n/a | installs | tests/shell/test_mw104_upgrade_shell.py::test_a_newer_release_installs_over_an_older_install |
| E96 | the real shape: newest tag v0.2.1, install at a 0.2.7 head | n/a | refused, never a downgrade | tests/shell/test_mw104_upgrade_shell.py::test_replay_the_newest_tag_older_than_the_install_never_downgrades |
| E97 | green record: bad sha, bad kind, missing field | n/a | refused, the file bytes unchanged | tests/shell/test_mw104_green_shell.py::test_a_bad_green_record_is_refused_and_writes_nothing |
| E98 | green record: good (nearest allow of E97) | n/a | one line appended, earlier bytes unchanged | tests/shell/test_mw104_green_shell.py::test_a_good_green_record_appends_one_line |
| E99 | green record written without a final line break in the file | n/a | the new row starts a new line | tests/shell/test_mw104_green_shell.py::test_a_record_after_a_file_without_a_line_break_starts_a_new_line |
| E100 | an unreadable green record | n/a | the upgrade refuses | tests/shell/test_mw104_green_shell.py::test_an_unreadable_green_record_refuses_the_upgrade |
| E101 | core lock decision: a session's `green record` | n/a | refused `owner-only-command` | tests/core/test_mw104_lock_green.py::test_a_session_green_record_is_owner_only |
| E102 | core lock decision: another command (nearest allow of E101) | n/a | allowed | tests/core/test_mw104_lock_green.py::test_a_session_command_that_is_not_green_record_passes |
| E103 | CLI: `upgrade` and `green record` with CLAUDECODE | n/a | refused `owner-only-command` | tests/test_mw104_upgrade_e2e.py::test_upgrade_and_green_record_are_refused_in_a_session |
| E104 | CLI: the same without CLAUDECODE (nearest allow of E103) | n/a | not the owner-only refusal | tests/test_mw104_upgrade_e2e.py::test_upgrade_and_green_record_pass_the_owner_check_without_the_marker |
| E105 | e2e run 1: a dry run from the real engine copy | n/a | checks listed; task repo and grant bytes unchanged | tests/test_mw104_upgrade_e2e.py::test_e2e_a_dry_run_lists_checks_and_changes_nothing |
| E106 | e2e run 2: the real upgrade, v0.0.2 picked | n/a | one commit with only the printed paths plus the ledger; a pre-staged file stays out; ledger row by tool:mkway-upgrade with `, release v0.0.2` | tests/test_mw104_upgrade_e2e.py::test_e2e_the_real_upgrade_picks_the_proven_release |
| E107 | hermetic: the autouse fixture of the card's modules | n/a | upgrade folder, APPDATA, XDG and home under tmp_path | tests/shell/test_mw104_upgrade_dirs.py::test_the_hermetic_fixture_is_active |
| E108 | register row, changelog line, card | none | present | tests/test_mw104_docs.py::test_register_changelog_and_card_name_the_card |
| E109 | README section | none | names the command, both modes, release.json keys, the green record, the gap H7 | tests/test_mw104_docs.py::test_the_readme_section_names_the_command_and_the_gap |
| E110 | KEYS.md | none | a release.json table with the four keys, `full_command` distinct from `tests.command` | tests/test_mw104_docs.py::test_keys_md_documents_release_json |
| E111 | `release.json` values | none | the four values of the order, tracked by git | tests/test_mw104_docs.py::test_release_json_holds_the_four_values |
| E112 | mkway.py usage text | `install, upgrade` | names `green record` | tests/test_mw104_docs.py::test_the_usage_text_names_green_record |
| E113 | green record `--branch` of a batch merge: names joined by `, `, each by the branch rule | n/a | accepted, the text kept | tests/core/test_mw104_upgrade_core.py::test_a_batch_branch_list_is_accepted |
| E114 | green record `--branch` with a bad name inside the list (nearest deny of E113) | n/a | refused `branch must be a branch name` | tests/core/test_mw104_upgrade_core.py::test_a_bad_name_inside_a_branch_list_is_refused |
| E115 | green record of a batch branch list, through the shell | n/a | one line, the branch text as given | tests/shell/test_mw104_green_shell.py::test_a_batch_branch_list_is_stored_as_given |
| E116 | the session marker with the empty value | n/a | refused `owner-only-command` | tests/test_mw104_upgrade_e2e.py::test_the_marker_is_refused_with_any_value |
| E117 | narrow route: every changed path has a rule, but no one rule has them all (nearest deny of E28) | n/a | refused `no single narrow_paths rule covers every path` | tests/core/test_mw104_upgrade_core.py::test_the_narrow_cover_accepts_or_refuses |
| E118 | the texts of an unreadable task root and an unreadable lock | n/a | the literals | tests/core/test_mw104_upgrade_core.py::test_the_refusal_texts_are_the_literals |
| E119 | the grant lists two roots: none named, or one that is not listed | n/a | refused with the T5 texts, nothing changed | tests/shell/test_mw104_upgrade_edges.py::test_a_root_that_is_not_named_or_not_listed_is_refused |
| E120 | the lock is not JSON, or JSON that is not an object | n/a | refused `The lock <file> cannot be read` | tests/shell/test_mw104_upgrade_edges.py::test_a_lock_that_is_not_a_json_object_is_refused |
| E121 | the granted target is a subfolder of a repository | n/a | refused `is not the top folder of a git working tree` | tests/shell/test_mw104_upgrade_edges.py::test_a_target_that_is_not_the_top_of_a_work_tree_is_refused |
| E122 | the engine repository has a damaged index | n/a | refused `The engine repository <path> cannot be read` | tests/shell/test_mw104_upgrade_edges.py::test_an_engine_repository_that_git_cannot_read_is_refused |
| E123 | the task repository has a damaged index | n/a | refused `The task root <path> cannot be read` | tests/shell/test_mw104_upgrade_edges.py::test_a_task_root_that_git_cannot_read_is_refused |
| E124 | the release cannot be exported by git archive | n/a | refused before a write, the lock unchanged | tests/shell/test_mw104_upgrade_edges.py::test_a_failing_archive_is_refused_before_a_write |
| E125 | the interpreter cannot start the ledger command | n/a | refused `could not run the engine's ledger command` | tests/shell/test_mw104_upgrade_edges.py::test_an_interpreter_that_cannot_start_is_refused |
| E126 | the process helper given a program that does not exist | n/a | no exit code, the reason | tests/shell/test_mw104_upgrade_edges.py::test_a_program_that_cannot_start_has_no_exit_code |
| E127 | `git add` fails after the install (index lock held) | n/a | nothing committed, the answer says files may be written | tests/shell/test_mw104_upgrade_edges.py::test_a_git_add_that_fails_commits_nothing |
| E128 | the ledger is not tracked by git | n/a | the row is written, the ledger is not in the commit | tests/shell/test_mw104_upgrade_edges.py::test_a_ledger_that_is_not_tracked_is_not_committed |
| E129 | an up-to-date run whose log cannot be written | n/a | refused `Cannot write the log (` | tests/shell/test_mw104_upgrade_edges.py::test_a_log_that_cannot_be_written_on_an_up_to_date_run_is_reported |
| E130 | a green record whose file cannot be written | n/a | refused `green record refused: cannot write` | tests/shell/test_mw104_upgrade_edges.py::test_a_green_record_that_cannot_be_written_is_refused |

### Final texts

Every refusal ends «Nothing was changed.» where the spec says so; `<x>` is a value.

| Id | Literal text |
|---|---|
| T1 | `policy.json is invalid: <key> is not a grant key: remove it from the upgrade grant (<path>); <new home>`, the new home being `release.json (branch)`, `release.json (full_command)`, `the engine repository mkway upgrade runs from`, `the running interpreter` or `the green record` |
| T2 | `There is no grant: <file> does not exist. Only the owner writes that file.` |
| T3 | `target is required (the one folder the policy names).` and `target must be a full path.` |
| T4 | `<target> is not the target the policy names (<grant target>). Only that folder is updated; other copies get the engine through git.` |
| T5 | `root is required: the policy lists <N> roots (<list>); name the one to update.` and `root <asked> is not in the policy's list (<list>). Only listed roots are updated.` |
| T6 | `release.json is missing at HEAD. Nothing was changed.` and `release.json is invalid: <why>. Nothing was changed.` |
| T7 | `No green record in <green file> shows a full, passing test run (<command>) for the engine HEAD <sha8> on <branch>, and the narrow-test route does not apply: <reason> Merge it with mkcl-merge first. Nothing was changed.` |
| T8 | `the mkcl merge that ended at <sha8> ran "<other>", but full_command in release.json is "<command>". mkcl's command changed after that merge: merge again with mkcl-merge so the run uses the current command (only the owner edits that file; mkway upgrade never changes it).` |
| T9 | `no release tag is proven green; nothing was changed` |
| T10 | `the installed engine has no source commit (installed from a plain folder); reinstall from the engine repository. Nothing was changed.` |
| T11 | `the installed engine <sha8> is not in the engine repository. Nothing was changed.` |
| T12 | `the release <tag> (<sha8>) is older than the installed engine <sha8>. Nothing was changed.`; from head: `the engine HEAD <sha8> is older than the installed engine <sha8>. Nothing was changed.`; `the engine <sha8> and the installed engine <sha8> have diverged. Nothing was changed.` |
| T13 | `version <a> is lower than the installed <b>. Nothing was changed.` |
| T14 | `run mkway upgrade from the engine repository, not from an installed copy; nothing was changed` |
| T15 | `the upgrade folder <path> is inside a git working tree (<top>) and is not ignored by it; put it outside every repository or ignore it; nothing was changed` |
| T16 | `The engine's ledger command has no --by option, so it cannot record a row by=tool:mkway-upgrade. A mkway card has to add that first; nothing was changed.` |

## 8. Log

One line per step. No re-run of a check or an agent round without a new input named in the Log row.

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-14 | acceptance table written before any test | - | E1 to E116 and the final texts T1 to T16 above; the order amendment R257g (2) adds the key narrow_command (rows E15, E16); ruling R257h: gap H7 named, no lock-gate rows; the batch branch list of mkcl 0.6.0 adds rows E113 to E115 |
| 2026-11-14 | run set override | - | the whole-suite run required before every commit by the project rules is overridden for this card by the owner, 13.11: the merge runs the whole suite once; the builder runs its own files, tests/core, test_meta_cards, test_register, test_repo_scan, test_install, test_mw029_fast_guard, every test_mw*_docs and the existing test files it touches, with MKWAY_TEST_WORKERS=4 |
| 2026-11-14 | gap H7 | - | the lock gate cannot yet hold the upgrade folder's green.jsonl and policy.json, which lie outside the repository; the owner-only CLAUDECODE refusal covers the command line until a follow-up card adds absolute-path lock targets; a process outside Claude Code can still write green.jsonl (R257b, R257f), closed only by the later travelling-proof card |
| 2026-11-14 | test row corrected: E42 | - | the case `engine/release.json` is removed from the parameters of the test: everything under engine/ is in the install set by the rule itself, so the case asserted what core_install denies; the row's claim, the top-level release.json is not installed, is unchanged and still tested by `release.json` and `release.json.bak` |
| 2026-11-14 | test row corrected: E24 | - | the case `capital-hex` built its value with `A.upper()` where A is all digits, so it tested a valid sha; it now uses forty capital A |
| 2026-11-14 | test setups corrected: E43, E106, E59, E85 and the helper | - | E43 and E106 listed files that install rewrites with identical content, which no commit holds; E43 now lists the four changed files, E106 requires the lock and the ledger and allows the three unchanged ones; E59 narrow case: the commit also changed the stub engine file, a path no rule covers, so it now keeps the same stub; E85: the side commit changed VERSION and the stub like the main line, a merge conflict, so it keeps the base version and stub; helper: the real engine copy writes byte code beside its modules when the e2e runs it, so the copy gets a .gitignore for it as the real repository has; the synthetic git identity is now `mkway-test` because the term scan flagged the address-shaped value (group B, two lines of the helper, no term printed) |
| 2026-11-14 | test of an older card changed: MW-102 docs (R256, R257) | - | its check that the changelog line is the LAST line of the top section is now a presence check, as R256 requires of a docs test; this card adds its own line at the end of the same section |
| 2026-11-14 | rows E117 to E130 added | - | the coverage of the two new modules (branch coverage, the run set) showed 3 lines of the pure core and 27 lines of the shell that no row reached; dead branches were removed from the code (a drive-root special case in the folder key, an unreachable empty-body check, a duplicate-root guard, an unreadable-grant text folded into «no grant», a second `_Done` handler, a tarfile fallback written as a plain extraction); the reachable refusals got these rows |
| 2026-11-14 | red proof | 5653b0a | tests only, rows E1 to E116: 103 failed, the core file red by the missing module core_upgrade, the shell and e2e rows red by the missing module upgrade; 13 `Checks:` guards pass beside them (the hermetic fixture, 9 cases, and the lock gate allow cases, 4); core_shape.decide over the 118 test functions: 0 breaches |
| 2026-11-14 | red commits | 5653b0a, 4f926f3, 00ca6dd | 5653b0a: rows E1 to E116; 4f926f3: rows E117 to E130 and the corrected rows, still red by the missing modules; 00ca6dd: the MW-102 docs test changed to a presence check (R256, R257), a passing test changed in its own commit |
| 2026-11-14 | green commit | 2e76555 | core_upgrade, upgrade, mkway.py, core_lock, KEYS.md, release.json, README, register row, changelog line; no test edited in it |
| 2026-11-14 | run | 2e76555 | the run set of the override above, `MKWAY_TEST_WORKERS=4 python -m pytest -n auto --dist loadgroup --cov=engine --cov-branch`: 2664 passed in 115 seconds, test_repo_scan and test_install included |
| 2026-11-14 | coverage | 2e76555 | core_upgrade.py 453 statements, 0 missed, 234 branches, 0 partial; upgrade.py 384 statements, 0 missed, 98 branches, 0 partial; missed lines: none |
| 2026-11-14 | term scan | 2e76555 | test_repo_scan and test_install pass; no line carries `term-scan: allow`; one early hit (group B, two lines of the test helper) was an address-shaped synthetic git identity, replaced, see the row «test setups corrected» |
| 2026-11-14 | notes | 2e76555 | CRLF warnings on add are harmless (the checkout converts line ends); the coverage run left an untracked `.coverage` file in the worktree, not committed; the commit messages carry no attribution trailer because the rules forbid angle brackets in a message |
| 2026-11-14 | E1 | 2e76555 | green: test_core_upgrade_imports_only_what_core_install_imports |
| 2026-11-14 | E2 | 2e76555 | green: test_core_upgrade_calls_no_io_function |
| 2026-11-14 | E3 | 2e76555 | green: test_the_upgrade_folder_is_chosen_from_env_platform_and_home |
| 2026-11-14 | E4 | 2e76555 | green: test_a_grant_is_accepted |
| 2026-11-14 | E5 | 2e76555 | green: test_a_grant_is_refused |
| 2026-11-14 | E6 | 2e76555 | green: test_a_grant_holding_a_moved_key_is_refused_with_its_new_home |
| 2026-11-14 | E7 | 2e76555 | green: test_the_same_grant_without_the_moved_key_is_accepted |
| 2026-11-14 | E8 | 2e76555 | green: test_the_missing_grant_text_names_the_file |
| 2026-11-14 | E9 | 2e76555 | green: test_a_root_is_picked |
| 2026-11-14 | E10 | 2e76555 | green: test_a_root_is_refused_by_the_pick |
| 2026-11-14 | E11 | 2e76555 | green: test_the_target_is_accepted |
| 2026-11-14 | E12 | 2e76555 | green: test_the_target_is_refused |
| 2026-11-14 | E13 | 2e76555 | green: test_release_config_is_accepted |
| 2026-11-14 | E14 | 2e76555 | green: test_release_config_is_refused |
| 2026-11-14 | E15 | 2e76555 | green: test_narrow_command_is_refused_when_missing_or_wrong |
| 2026-11-14 | E16 | 2e76555 | green: test_narrow_command_is_accepted_as_text_or_list |
| 2026-11-14 | E17 | 2e76555 | green: test_the_display_form_of_a_command |
| 2026-11-14 | E18 | 2e76555 | green: test_a_path_pattern_is_checked |
| 2026-11-14 | E19 | 2e76555 | green: test_the_narrow_matcher_picks_the_rule |
| 2026-11-14 | E20 | 2e76555 | green: test_the_first_uncovered_path_is_named |
| 2026-11-14 | E21 | 2e76555 | green: test_green_rows_skip_unparsable_lines |
| 2026-11-14 | E22 | 2e76555 | green: test_the_exact_green_row_proves_a_sha |
| 2026-11-14 | E23 | 2e76555 | green: test_a_green_row_differing_in_one_field_does_not_prove |
| 2026-11-14 | E24 | 2e76555 | green: test_a_green_record_with_a_bad_field_is_refused, the capital-hex case corrected in 4f926f3 |
| 2026-11-14 | E25 | 2e76555 | green: test_a_good_green_record_is_accepted |
| 2026-11-14 | E26 | 2e76555 | green: test_the_narrow_walk_reaches_the_full_green_head |
| 2026-11-14 | E27 | 2e76555 | green: test_the_narrow_walk_is_refused |
| 2026-11-14 | E28 | 2e76555 | green: test_the_narrow_cover_accepts_or_refuses |
| 2026-11-14 | E29 | 2e76555 | green: test_tag_refs_are_parsed |
| 2026-11-14 | E30 | 2e76555 | green: test_the_newest_proven_tag_is_chosen |
| 2026-11-14 | E31 | 2e76555 | green: test_no_proven_tag_is_refused |
| 2026-11-14 | E32 | 2e76555 | green: test_the_downgrade_guard_refuses |
| 2026-11-14 | E33 | 2e76555 | green: test_the_guard_allows_a_newer_release |
| 2026-11-14 | E34 | 2e76555 | green: test_an_equal_sha_is_up_to_date |
| 2026-11-14 | E35 | 2e76555 | green: test_the_install_line_is_read |
| 2026-11-14 | E36 | 2e76555 | green: test_the_install_line_is_refused |
| 2026-11-14 | E37 | 2e76555 | green: test_the_commit_message_form |
| 2026-11-14 | E38 | 2e76555 | green: test_the_ledger_quote_forms |
| 2026-11-14 | E39 | 2e76555 | green: test_the_refusal_texts_are_the_literals |
| 2026-11-14 | E40 | 2e76555 | green: test_a_command_of_blank_texts_is_refused |
| 2026-11-14 | E41 | 2e76555 | green: test_versions_are_compared_as_numbers |
| 2026-11-14 | E42 | 2e76555 | green: test_release_json_is_not_in_the_installed_set, the row corrected in 4f926f3 |
| 2026-11-14 | E43 | 2e76555 | green: test_a_proven_release_updates_with_one_commit, the expected files corrected in 4f926f3 |
| 2026-11-14 | E44 | 2e76555 | green: test_no_commit_prefix_gives_a_plain_message |
| 2026-11-14 | E45 | 2e76555 | green: test_a_missing_or_bad_grant_is_refused_and_logged |
| 2026-11-14 | E46 | 2e76555 | green: test_a_target_that_is_not_the_grants_is_refused |
| 2026-11-14 | E47 | 2e76555 | green: test_a_target_with_a_trailing_separator_is_accepted |
| 2026-11-14 | E48 | 2e76555 | green: test_a_missing_lock_or_root_is_refused |
| 2026-11-14 | E49 | 2e76555 | green: test_a_head_without_a_proving_green_row_is_refused |
| 2026-11-14 | E50 | 2e76555 | green: test_a_dirty_engine_or_another_branch_is_refused |
| 2026-11-14 | E51 | 2e76555 | green: test_a_lock_at_the_chosen_sha_is_up_to_date |
| 2026-11-14 | E52 | 2e76555 | green: test_a_new_major_is_refused |
| 2026-11-14 | E53 | 2e76555 | green: test_changes_in_an_install_path_are_refused_before_a_write |
| 2026-11-14 | E54 | 2e76555 | green: test_a_dry_run_changes_nothing_and_lists_checks_and_commands |
| 2026-11-14 | E55 | 2e76555 | green: test_a_ledger_command_without_by_is_refused |
| 2026-11-14 | E56 | 2e76555 | green: test_a_failing_install_commits_nothing |
| 2026-11-14 | E57 | 2e76555 | green: test_a_log_that_cannot_be_written_is_refused |
| 2026-11-14 | E58 | 2e76555 | green: test_the_call_names_the_second_root |
| 2026-11-14 | E59 | 2e76555 | green: test_the_grant_and_the_green_record_are_never_written, the narrow case corrected in 4f926f3 |
| 2026-11-14 | E60 | 2e76555 | green: test_the_checks_name_the_command_that_was_checked |
| 2026-11-14 | E61 | 2e76555 | green: test_a_row_of_another_command_names_both_commands |
| 2026-11-14 | E62 | 2e76555 | green: test_a_head_no_merge_ended_at_has_the_plain_reason |
| 2026-11-14 | E63 | 2e76555 | green: test_one_narrow_merge_installs_from_head |
| 2026-11-14 | E64 | 2e76555 | green: test_the_narrow_route_is_named_in_answer_ledger_and_log |
| 2026-11-14 | E65 | 2e76555 | green: test_a_narrow_dry_run_names_the_rule_and_changes_nothing |
| 2026-11-14 | E66 | 2e76555 | green: test_two_narrow_merges_install |
| 2026-11-14 | E67 | 2e76555 | green: test_a_batch_of_two_commits_in_one_row_installs |
| 2026-11-14 | E68 | 2e76555 | green: test_a_path_outside_the_patterns_is_refused |
| 2026-11-14 | E69 | 2e76555 | green: test_a_rename_out_of_a_covered_path_is_refused |
| 2026-11-14 | E70 | 2e76555 | green: test_a_broken_narrow_chain_is_refused |
| 2026-11-14 | E71 | 2e76555 | green: test_the_narrow_match_is_case_sensitive |
| 2026-11-14 | E72 | 2e76555 | green: test_a_full_green_head_of_another_command_is_refused |
| 2026-11-14 | E73 | 2e76555 | green: test_a_full_green_head_off_the_first_parent_chain_is_refused |
| 2026-11-14 | E74 | 2e76555 | green: test_a_full_green_head_installs_with_no_narrow_rule |
| 2026-11-14 | E75 | 2e76555 | green: test_a_run_from_an_installed_copy_is_refused |
| 2026-11-14 | E76 | 2e76555 | green: test_a_run_from_the_engine_repository_finds_it |
| 2026-11-14 | E77 | 2e76555 | green: test_an_upgrade_folder_inside_a_tree_and_not_ignored_is_refused |
| 2026-11-14 | E78 | 2e76555 | green: test_an_upgrade_folder_ignored_or_outside_every_tree_is_allowed |
| 2026-11-14 | E79 | 2e76555 | green: test_the_override_is_printed_and_in_the_ledger_quote |
| 2026-11-14 | E80 | 2e76555 | green: test_a_missing_or_invalid_release_json_at_head_is_refused |
| 2026-11-14 | E81 | 2e76555 | green: test_a_dirty_working_release_json_is_refused_unread |
| 2026-11-14 | E82 | 2e76555 | green: test_a_valid_committed_release_json_is_read_from_head |
| 2026-11-14 | E83 | 2e76555 | green: test_the_newest_proven_tag_installs_over_a_newer_unproven_one |
| 2026-11-14 | E84 | 2e76555 | green: test_version_order_beats_tag_date |
| 2026-11-14 | E85 | 2e76555 | green: test_a_tag_off_the_first_parent_chain_is_skipped, the side commit corrected in 4f926f3 |
| 2026-11-14 | E86 | 2e76555 | green: test_no_proven_tag_is_refused |
| 2026-11-14 | E87 | 2e76555 | green: test_a_narrow_chain_does_not_prove_a_tag |
| 2026-11-14 | E88 | 2e76555 | green: test_release_mode_runs_the_releases_own_install_code |
| 2026-11-14 | E89 | 2e76555 | green: test_from_head_installs_the_head_commit |
| 2026-11-14 | E90 | 2e76555 | green: test_a_lock_with_no_source_commit_is_refused |
| 2026-11-14 | E91 | 2e76555 | green: test_a_lock_source_not_in_the_engine_repository_is_refused |
| 2026-11-14 | E92 | 2e76555 | green: test_a_release_older_than_the_install_is_refused |
| 2026-11-14 | E93 | 2e76555 | green: test_a_diverged_install_is_refused |
| 2026-11-14 | E94 | 2e76555 | green: test_a_lower_version_is_refused |
| 2026-11-14 | E95 | 2e76555 | green: test_a_newer_release_installs_over_an_older_install |
| 2026-11-14 | E96 | 2e76555 | green: test_replay_the_newest_tag_older_than_the_install_never_downgrades |
| 2026-11-14 | E97 | 2e76555 | green: test_a_bad_green_record_is_refused_and_writes_nothing |
| 2026-11-14 | E98 | 2e76555 | green: test_a_good_green_record_appends_one_line |
| 2026-11-14 | E99 | 2e76555 | green: test_a_record_after_a_file_without_a_line_break_starts_a_new_line |
| 2026-11-14 | E100 | 2e76555 | green: test_an_unreadable_green_record_refuses_the_upgrade |
| 2026-11-14 | E101 | 2e76555 | green: test_a_session_green_record_is_owner_only |
| 2026-11-14 | E102 | 2e76555 | green: test_a_session_command_that_is_not_green_record_passes |
| 2026-11-14 | E103 | 2e76555 | green: test_upgrade_and_green_record_are_refused_in_a_session |
| 2026-11-14 | E104 | 2e76555 | green: test_upgrade_and_green_record_pass_the_owner_check_without_the_marker |
| 2026-11-14 | E105 | 2e76555 | green: test_e2e_a_dry_run_lists_checks_and_changes_nothing, the engine copy given a byte-code ignore file in 4f926f3 |
| 2026-11-14 | E106 | 2e76555 | green: test_e2e_the_real_upgrade_picks_the_proven_release, the expected files corrected in 4f926f3 |
| 2026-11-14 | E107 | 2e76555 | green: test_the_hermetic_fixture_is_active |
| 2026-11-14 | E108 | 2e76555 | green: test_register_changelog_and_card_name_the_card |
| 2026-11-14 | E109 | 2e76555 | green: test_the_readme_section_names_the_command_and_the_gap |
| 2026-11-14 | E110 | 2e76555 | green: test_keys_md_documents_release_json |
| 2026-11-14 | E111 | 2e76555 | green: test_release_json_holds_the_four_values |
| 2026-11-14 | E112 | 2e76555 | green: test_the_usage_text_names_green_record |
| 2026-11-14 | E113 | 2e76555 | green: test_a_batch_branch_list_is_accepted |
| 2026-11-14 | E114 | 2e76555 | green: test_a_bad_name_inside_a_branch_list_is_refused |
| 2026-11-14 | E115 | 2e76555 | green: test_a_batch_branch_list_is_stored_as_given |
| 2026-11-14 | E116 | 2e76555 | green: test_the_marker_is_refused_with_any_value |
| 2026-11-14 | E117 | 2e76555 | green: test_the_narrow_cover_accepts_or_refuses, the split-across-rules case |
| 2026-11-14 | E118 | 2e76555 | green: test_the_refusal_texts_are_the_literals, the two unreadable texts |
| 2026-11-14 | E119 | 2e76555 | green: test_a_root_that_is_not_named_or_not_listed_is_refused |
| 2026-11-14 | E120 | 2e76555 | green: test_a_lock_that_is_not_a_json_object_is_refused |
| 2026-11-14 | E121 | 2e76555 | green: test_a_target_that_is_not_the_top_of_a_work_tree_is_refused |
| 2026-11-14 | E122 | 2e76555 | green: test_an_engine_repository_that_git_cannot_read_is_refused |
| 2026-11-14 | E123 | 2e76555 | green: test_a_task_root_that_git_cannot_read_is_refused |
| 2026-11-14 | E124 | 2e76555 | green: test_a_failing_archive_is_refused_before_a_write |
| 2026-11-14 | E125 | 2e76555 | green: test_an_interpreter_that_cannot_start_is_refused |
| 2026-11-14 | E126 | 2e76555 | green: test_a_program_that_cannot_start_has_no_exit_code |
| 2026-11-14 | E127 | 2e76555 | green: test_a_git_add_that_fails_commits_nothing |
| 2026-11-14 | E128 | 2e76555 | green: test_a_ledger_that_is_not_tracked_is_not_committed |
| 2026-11-14 | E129 | 2e76555 | green: test_a_log_that_cannot_be_written_on_an_up_to_date_run_is_reported |
| 2026-11-14 | E130 | 2e76555 | green: test_a_green_record_that_cannot_be_written_is_refused |
