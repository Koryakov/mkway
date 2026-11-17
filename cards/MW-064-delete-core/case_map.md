# Case map of card MW-064: the delete family

> One line per old test: `old_file::old_test -> new_file::new_test` (the main new home; a `# also:` line names the others),
> or `-> dropped: doc` (a README, KEYS or CHANGELOG text check), or `-> dropped: T<n> <why>` (it fails criterion T1 to T8 of
> the final test criteria of 2026-11-12). A case with no new home stays in its module: `# kept: old (why)`.

## tests/test_mw009_reader.py (E4 to E14 of card MW-009)
tests/test_mw009_reader.py::test_literal_existing_targets_inside_the_root_pass -> tests/core/test_delete_decide.py::test_a_literal_existing_target_inside_the_root_is_allowed_and_listed_for_backup
# also: tests/shell/test_delete_facts.py::test_a_relative_target_is_read_from_the_hooks_cwd; tests/shell/test_delete_facts.py::test_a_cd_into_a_folder_that_exists_places_the_target_in_it; tests/shell/test_delete_facts.py::test_a_cd_into_a_folder_that_does_not_exist_makes_the_folder_unknown
tests/test_mw009_reader.py::test_every_delete_form_is_read -> tests/core/test_delete_decide.py::test_every_bash_delete_form_with_a_missing_target_is_unknown
# also: tests/core/test_delete_decide.py::test_every_powershell_delete_form_with_a_missing_target_is_unknown; tests/core/test_delete_decide.py::test_the_refusal_for_a_missing_target_names_the_path
tests/test_mw009_reader.py::test_a_delete_is_refused_in_every_position -> tests/core/test_delete_decide.py::test_a_delete_is_refused_in_every_position
# also: tests/core/test_delete_decide.py::test_a_delete_in_any_letter_case_or_through_xargs_is_unknown
tests/test_mw009_reader.py::test_computed_and_broad_targets_are_unknown -> tests/core/test_delete_decide.py::test_a_computed_or_broad_target_is_unknown_with_the_way_out
# also: tests/core/test_delete_decide.py::test_an_unreadable_powershell_target_is_unknown; tests/core/test_delete_decide.py::test_the_checks_of_one_target_run_in_the_order_variable_outside_wildcard_missing
tests/test_mw009_reader.py::test_a_target_outside_the_root_is_always_refused -> tests/core/test_delete_decide.py::test_a_target_outside_the_root_is_refused_naming_the_owners_terminal
# also: tests/core/test_delete_decide.py::test_a_powershell_target_outside_the_root_is_refused; tests/shell/test_delete_facts.py::test_a_relative_path_out_of_the_real_root_is_outside; tests/shell/test_delete_facts.py::test_an_absolute_path_outside_the_real_root_is_outside; tests/shell/test_delete_facts.py::test_an_absolute_path_inside_the_real_root_is_a_repo_path
tests/test_mw009_reader.py::test_a_wildcard_is_refused -> tests/core/test_delete_decide.py::test_a_wildcard_target_is_refused_naming_the_list_command
# also: tests/core/test_delete_decide.py::test_a_powershell_pattern_is_a_wildcard
tests/test_mw009_reader.py::test_destructive_sql_is_refused_unless_the_profile_allows_it -> tests/core/test_delete_decide.py::test_destructive_sql_is_refused_naming_the_profile_key
# also: tests/core/test_delete_decide.py::test_destructive_sql_passes_when_the_profile_allows_it; tests/core/test_delete_decide.py::test_the_sql_words_as_text_or_a_read_are_not_sql; tests/core/test_delete_decide.py::test_sql_decision_over_every_combination_of_its_two_facts; tests/core/test_delete_decide.py::test_the_profile_switch_turns_off_only_sql
tests/test_mw009_reader.py::test_the_false_blocks_of_the_owners_guard_pass -> tests/core/test_delete_decide.py::test_a_command_that_only_names_a_remove_word_is_allowed_in_bash
# also: tests/core/test_delete_decide.py::test_a_command_that_only_names_a_remove_word_is_allowed_in_powershell
tests/test_mw009_reader.py::test_trash_commands_are_the_owners -> tests/core/test_delete_decide.py::test_a_session_may_not_run_the_trash_commands
# also: tests/core/test_delete_decide.py::test_the_list_command_and_other_engine_commands_are_not_owner_only
tests/test_mw009_reader.py::test_a_non_shell_tool_and_odd_input_are_allowed -> tests/shell/test_delete_facts.py::test_a_call_the_gate_does_not_own_is_allowed
# kept: tests/test_mw009_reader.py::test_the_manifest_has_the_delete_gate_after_the_commit_gate (a wiring check of the engine's own manifest, not a decision of the gate; the real-hook rows of MW-039 prove each deny)

## tests/test_mw009_git.py (E21 to E25)
tests/test_mw009_git.py::test_git_clean_with_force_is_refused -> tests/core/test_delete_decide.py::test_git_clean_with_force_is_refused_whatever_the_vcs_key
# also: tests/core/test_delete_decide.py::test_a_dry_run_and_a_clean_without_force_pass
tests/test_mw009_git.py::test_git_reset_hard_is_refused_only_when_the_tree_has_changes -> tests/core/test_delete_decide.py::test_a_hard_reset_is_refused_when_a_tracked_file_has_a_change
# also: tests/core/test_delete_decide.py::test_a_soft_or_mixed_reset_never_loses_work; tests/core/test_delete_decide.py::test_a_git_revert_over_every_combination_of_its_three_facts; tests/shell/test_delete_facts.py::test_a_hard_reset_passes_when_git_reports_no_tracked_change; tests/shell/test_delete_facts.py::test_a_hard_reset_is_refused_when_git_reports_a_tracked_change; tests/shell/test_delete_facts.py::test_a_soft_reset_passes_although_git_reports_a_change; tests/shell/test_delete_facts.py::test_a_hard_reset_is_not_read_when_the_profile_has_no_git
tests/test_mw009_git.py::test_restore_and_checkout_of_a_changed_path_are_refused -> tests/core/test_delete_decide.py::test_restore_and_checkout_of_a_changed_path_are_refused
# also: tests/core/test_delete_decide.py::test_restore_and_checkout_of_a_clean_path_pass; tests/core/test_delete_decide.py::test_a_path_deleted_from_the_tree_has_nothing_to_lose; tests/core/test_delete_decide.py::test_a_git_path_keeps_its_own_reason; tests/shell/test_delete_facts.py::test_a_restore_of_a_changed_path_or_of_a_folder_holding_it_is_refused; tests/shell/test_delete_facts.py::test_a_restore_of_a_clean_path_passes_although_another_path_has_a_change; tests/shell/test_delete_facts.py::test_restoring_a_path_deleted_from_the_working_tree_passes
tests/test_mw009_git.py::test_git_rm_of_a_changed_file_is_refused_and_a_clean_one_is_recorded -> tests/core/test_delete_decide.py::test_git_rm_of_a_changed_file_is_refused
# also: tests/core/test_delete_decide.py::test_git_rm_keeps_the_reasons_of_a_bad_path; tests/core/test_delete_decide.py::test_a_git_rm_that_is_no_delete_leaves_no_row; tests/core/test_delete_decide.py::test_git_rm_of_a_clean_tracked_path_is_kept_by_git_and_recorded; tests/core/test_delete_decide.py::test_one_row_covers_a_command_that_also_deletes_files; tests/core/test_delete_decide.py::test_git_rm_over_every_combination_of_its_four_facts; tests/shell/test_delete_facts.py::test_git_rm_of_a_changed_file_is_refused; tests/shell/test_delete_facts.py::test_a_refused_git_rm_leaves_no_row_and_no_trash_folder; tests/shell/test_delete_facts.py::test_git_rm_of_a_clean_tracked_file_is_recorded_without_a_copy; tests/shell/test_delete_facts.py::test_git_rm_of_a_clean_tracked_folder_is_recorded_without_a_copy; tests/shell/test_delete_facts.py::test_a_git_rm_that_deletes_nothing_leaves_no_row; tests/shell/test_delete_facts.py::test_git_rm_of_an_untracked_file_leaves_no_row; tests/shell/test_delete_facts.py::test_one_command_that_deletes_a_file_and_git_rms_a_tracked_one_makes_one_row_and_one_copy
tests/test_mw009_git.py::test_a_git_read_that_fails_refuses_the_delete -> tests/core/test_delete_decide.py::test_a_git_read_that_fails_refuses_the_delete
# also: tests/shell/test_delete_facts.py::test_a_git_that_cannot_read_the_tree_refuses_the_delete; tests/shell/test_delete_facts.py::test_a_git_that_does_not_answer_is_worded_as_such

## tests/test_mw009_backup.py (E15 to E20)
tests/test_mw009_backup.py::test_a_delete_is_copied_into_the_trash_and_recorded -> tests/shell/test_delete_facts.py::test_a_deleted_file_is_copied_into_the_trash_at_its_repo_path
# also: tests/shell/test_delete_facts.py::test_a_deleted_folder_is_copied_with_its_content; tests/shell/test_delete_facts.py::test_the_record_row_holds_session_targets_via_time_and_backup; tests/shell/test_delete_facts.py::test_the_trash_folder_is_named_by_a_timestamp; tests/shell/test_delete_facts.py::test_two_deletes_in_a_row_make_two_folders_and_two_rows; tests/shell/test_delete_facts.py::test_a_powershell_delete_is_backed_up_the_same_way; tests/shell/test_delete_facts.py::test_a_delete_after_a_cd_is_backed_up_at_its_repo_path; tests/core/test_delete_decide.py::test_the_record_row_names_time_session_via_targets_and_backup
tests/test_mw009_backup.py::test_an_empty_folder_and_a_nested_file_keep_their_path -> tests/shell/test_delete_facts.py::test_an_empty_folder_is_backed_up_as_a_folder
# also: tests/shell/test_delete_facts.py::test_a_file_in_a_nested_folder_keeps_its_full_repo_path; tests/shell/test_delete_facts.py::test_a_target_named_twice_is_recorded_once; tests/core/test_delete_decide.py::test_a_target_inside_another_target_is_copied_with_it
tests/test_mw009_backup.py::test_a_backup_above_the_limit_is_refused -> tests/core/test_delete_decide.py::test_a_backup_above_the_limit_is_refused
# also: tests/core/test_delete_decide.py::test_a_backup_up_to_the_limit_passes; tests/core/test_delete_decide.py::test_the_size_refusal_names_the_targets_the_limit_and_the_owners_terminal; tests/shell/test_delete_facts.py::test_a_target_exactly_at_the_size_limit_is_backed_up; tests/shell/test_delete_facts.py::test_a_target_above_the_size_limit_is_refused_and_nothing_is_written; tests/shell/test_delete_facts.py::test_a_folder_counts_by_its_content_for_the_size_limit; tests/shell/test_delete_facts.py::test_the_size_refusal_names_the_owners_terminal_and_the_key
tests/test_mw009_backup.py::test_a_failed_copy_or_record_refuses_the_delete -> tests/shell/test_delete_facts.py::test_a_copy_that_fails_refuses_the_delete
# also: tests/shell/test_delete_facts.py::test_a_trash_folder_that_cannot_be_made_refuses_the_delete; tests/shell/test_delete_facts.py::test_a_record_row_that_cannot_be_written_refuses_the_delete
tests/test_mw009_backup.py::test_a_refused_or_plain_command_leaves_no_trash -> tests/shell/test_delete_facts.py::test_a_refused_or_plain_command_leaves_no_trash
# also: tests/core/test_delete_decide.py::test_a_refused_or_plain_command_needs_no_backup; tests/core/test_delete_decide.py::test_an_allowed_delete_needs_a_backup
tests/test_mw009_backup.py::test_a_crash_in_the_gate_blocks_the_delete -> tests/shell/test_delete_facts.py::test_a_crash_in_the_gate_blocks_the_delete

## tests/test_mw009_commands.py (E26 to E30)
tests/test_mw009_commands.py::test_the_list_command_backs_up_deletes_and_records -> tests/shell/test_delete_facts.py::test_the_list_command_deletes_the_listed_paths
# also: tests/shell/test_delete_facts.py::test_the_list_command_copies_the_paths_into_the_trash_first; tests/shell/test_delete_facts.py::test_the_list_command_writes_one_row_that_says_it_was_a_list_by_a_session; tests/shell/test_delete_facts.py::test_the_list_command_says_how_many_paths_and_where_the_backup_is; tests/shell/test_delete_facts.py::test_the_list_command_works_in_the_owners_terminal; tests/core/test_delete_decide.py::test_a_good_list_gives_the_exact_repo_paths_once; tests/core/test_delete_decide.py::test_the_record_row_of_a_command_names_who_ran_it
tests/test_mw009_commands.py::test_one_bad_line_deletes_nothing -> tests/shell/test_delete_facts.py::test_one_bad_line_deletes_nothing_and_is_named
# also: tests/shell/test_delete_facts.py::test_an_empty_list_is_an_error; tests/shell/test_delete_facts.py::test_a_missing_list_file_is_an_error_and_deletes_nothing; tests/core/test_delete_decide.py::test_a_bad_line_is_a_problem_with_its_number_and_its_reason; tests/core/test_delete_decide.py::test_the_good_lines_stay_listed_beside_a_bad_one; tests/core/test_delete_decide.py::test_an_empty_list_is_a_problem
tests/test_mw009_commands.py::test_the_list_command_respects_the_size_limit -> tests/shell/test_delete_facts.py::test_the_list_command_respects_the_size_limit
tests/test_mw009_commands.py::test_the_gate_lets_the_list_command_through_and_stops_the_trash_commands -> dropped: T8 an in-process dispatcher call, not the real hook command (and a loop over cases, T2); the list command and the trash commands are table rows, and the real-hook deny of owner-only-command is the e2e row of MW-039
tests/test_mw009_commands.py::test_the_trash_commands_are_the_owners -> tests/shell/test_delete_facts.py::test_a_session_may_not_run_the_trash_commands
# also: tests/shell/test_delete_facts.py::test_a_later_delete_never_empties_the_trash; tests/shell/test_delete_facts.py::test_the_owner_lists_the_folders_with_files_size_and_targets; tests/shell/test_delete_facts.py::test_the_owner_empties_only_the_folders_older_than_the_days; tests/shell/test_delete_facts.py::test_older_than_zero_empties_every_stamped_folder_and_leaves_the_rest; tests/shell/test_delete_facts.py::test_each_empty_is_one_record_row_by_the_owner; tests/shell/test_delete_facts.py::test_the_days_are_required_and_must_be_a_number; tests/shell/test_delete_facts.py::test_negative_days_are_refused; tests/core/test_delete_decide.py::test_a_folder_older_than_the_days_by_its_stamp_is_removed; tests/core/test_delete_decide.py::test_a_folder_not_older_than_the_days_stays; tests/core/test_delete_decide.py::test_a_name_that_is_no_stamp_is_never_removed; tests/core/test_delete_decide.py::test_the_folders_to_remove_keep_the_order_given

## tests/test_mw009_keys.py (E1 to E3)
# kept: tests/test_mw009_keys.py::test_delete_keys_are_in_the_schema (the profile schema, not a decision of the delete gate)
# kept: tests/test_mw009_keys.py::test_delete_defaults_and_overrides (the profile defaults, not a decision of the delete gate)
tests/test_mw009_keys.py::test_delete_keys_are_lines_of_keys_md_with_their_defaults -> dropped: doc

## tests/test_mw009_readme.py (E31 to E33)
tests/test_mw009_readme.py::test_the_readme_has_one_section_deletes -> dropped: doc
tests/test_mw009_readme.py::test_the_section_states_the_rules_reasons_keys_commands_and_limits -> dropped: doc
# kept: tests/test_mw009_readme.py::test_the_start_line_names_the_delete_gate_on_and_off (the start block's gate list: a start line case, another session's scope)
