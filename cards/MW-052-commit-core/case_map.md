# MW-052 case map: old commit_files tests -> new tests

# One line per pair: `old test -> new test`, or `old test -> dropped: doc` (the line grammar of MW-040, read by
# tests/test_meta_cards.py). A test with several new homes has one line per home. A line `# kept: <old test> - <why>`
# marks a test that stays where it is (it is not a commit_files decision, or it proves what real git does); the
# comment line above a group says which old case it was. New homes: tests/core/test_commit_decide.py (table tests on
# Facts -> Verdict, no disk, no git; the rows carry the old case id in their pytest id), tests/shell/test_commit_facts.py
# (the fact reader on prepared plain, linked and sparse repositories and on a real register),
# tests/shell/test_commit_wiring.py (manifest and dispatcher). dropped: doc = a README, CHANGELOG, register or VERSION
# substring test (the ruling: documents are not evidence). tests/test_mw052_case_map.py proves that a mapped test is
# gone from its old module, that a kept test is still there, and that no test of an old module is unmapped.

# E7: files named, count of the rest, Paths and way out in the text
tests/test_mw006_commit_files.py::test_a_staged_file_outside_the_card_paths_is_refused -> tests/core/test_commit_decide.py::test_outside_files
tests/test_mw006_commit_files.py::test_a_staged_file_outside_the_card_paths_is_refused -> tests/core/test_commit_decide.py::test_outside_files_lists_only_the_outside_ones
# E8: decision in the core, the card, status and exempt entries read by the shell
tests/test_mw006_commit_files.py::test_always_allowed_files_and_empty_paths_pass -> tests/core/test_commit_decide.py::test_always_allowed_files_pass_whatever_the_paths_say
tests/test_mw006_commit_files.py::test_always_allowed_files_and_empty_paths_pass -> tests/core/test_commit_decide.py::test_a_session_with_no_card_commits_only_the_always_allowed_files
tests/test_mw006_commit_files.py::test_always_allowed_files_and_empty_paths_pass -> tests/core/test_commit_decide.py::test_a_card_that_is_not_open_holds_no_commit
tests/test_mw006_commit_files.py::test_always_allowed_files_and_empty_paths_pass -> tests/core/test_commit_decide.py::test_an_empty_paths_is_no_file_rule
tests/test_mw006_commit_files.py::test_always_allowed_files_and_empty_paths_pass -> tests/shell/test_commit_facts.py::test_the_card_the_session_holds_and_the_files_no_rule_applies_to
tests/test_mw006_commit_files.py::test_always_allowed_files_and_empty_paths_pass -> tests/shell/test_commit_facts.py::test_the_files_no_card_rule_applies_to_are_facts
tests/test_mw006_commit_files.py::test_always_allowed_files_and_empty_paths_pass -> tests/shell/test_commit_facts.py::test_a_card_that_is_not_open_is_a_fact
tests/test_mw006_commit_files.py::test_always_allowed_files_and_empty_paths_pass -> tests/shell/test_commit_facts.py::test_a_tampered_register_is_a_fact_with_the_owners_way_out
# E9: judgment in the core, the list of each form in the shell
tests/test_mw006_commit_files.py::test_every_commit_form_reads_the_files_it_would_stage -> tests/core/test_commit_decide.py::test_each_commit_form_is_judged_by_what_it_takes
tests/test_mw006_commit_files.py::test_every_commit_form_reads_the_files_it_would_stage -> tests/shell/test_commit_facts.py::test_the_taken_list_of_each_form_on_each_kind_of_repository
# E10: rows `mw006_e10_...`
tests/test_mw006_commit_files.py::test_a_staged_file_outside_the_paths_is_a_ride_in_whoever_wrote_it -> tests/core/test_commit_decide.py::test_each_commit_form_is_judged_by_what_it_takes
tests/test_mw006_commit_files.py::test_a_staged_file_outside_the_paths_is_a_ride_in_whoever_wrote_it -> tests/core/test_commit_decide.py::test_no_session_record_decides_a_commit
# E11
tests/test_mw006_commit_files.py::test_no_session_record_decides_a_commit -> tests/core/test_commit_decide.py::test_no_session_record_decides_a_commit
# E12: eight chained forms, PowerShell, three read-only forms
tests/test_mw006_commit_files.py::test_staging_in_the_same_command_is_refused -> tests/core/test_commit_decide.py::test_staging_in_the_same_command_is_refused
tests/test_mw006_commit_files.py::test_staging_in_the_same_command_is_refused -> tests/core/test_commit_decide.py::test_staging_in_the_same_powershell_command_is_refused
tests/test_mw006_commit_files.py::test_staging_in_the_same_command_is_refused -> tests/core/test_commit_decide.py::test_a_read_only_git_call_beside_the_commit_is_fine
# E13
tests/test_mw006_commit_files.py::test_unreadable_commits_fail_closed_and_other_commands_pass -> tests/core/test_commit_decide.py::test_a_commit_the_reader_cannot_read_fails_closed
tests/test_mw006_commit_files.py::test_unreadable_commits_fail_closed_and_other_commands_pass -> tests/core/test_commit_decide.py::test_a_command_that_is_no_commit_passes
tests/test_mw006_commit_files.py::test_unreadable_commits_fail_closed_and_other_commands_pass -> tests/core/test_commit_decide.py::test_a_tool_that_is_no_shell_and_a_project_with_no_git_pass
tests/test_mw006_commit_files.py::test_unreadable_commits_fail_closed_and_other_commands_pass -> tests/core/test_commit_decide.py::test_a_git_read_that_failed_refuses_with_its_text_or_the_default
tests/test_mw006_commit_files.py::test_unreadable_commits_fail_closed_and_other_commands_pass -> tests/core/test_commit_decide.py::test_a_tampered_register_refuses_and_names_the_owners_way_out
tests/test_mw006_commit_files.py::test_unreadable_commits_fail_closed_and_other_commands_pass -> tests/shell/test_commit_facts.py::test_a_git_read_that_times_out_is_an_unread_fact_with_the_way_out
tests/test_mw006_commit_files.py::test_unreadable_commits_fail_closed_and_other_commands_pass -> tests/shell/test_commit_facts.py::test_a_git_read_that_answers_non_zero_is_an_empty_unread
tests/test_mw006_commit_files.py::test_unreadable_commits_fail_closed_and_other_commands_pass -> tests/shell/test_commit_facts.py::test_a_command_with_no_commit_and_a_non_shell_tool_read_no_git
# E14
tests/test_mw006_commit_content.py::test_junk_files_are_refused_at_any_depth -> tests/core/test_commit_decide.py::test_junk_files_are_refused_at_any_depth
tests/test_mw006_commit_content.py::test_junk_files_are_refused_at_any_depth -> tests/core/test_commit_decide.py::test_names_that_only_look_like_junk_pass
tests/test_mw006_commit_content.py::test_junk_files_are_refused_at_any_depth -> tests/core/test_commit_decide.py::test_two_junk_files_are_named_together
# E15: git's ignore answer is a fact
tests/test_mw006_commit_content.py::test_a_force_added_ignored_file_is_refused -> tests/core/test_commit_decide.py::test_a_force_added_ignored_file_is_refused
tests/test_mw006_commit_content.py::test_a_force_added_ignored_file_is_refused -> tests/core/test_commit_decide.py::test_an_ignored_file_already_in_the_repository_stays_editable
tests/test_mw006_commit_content.py::test_a_force_added_ignored_file_is_refused -> tests/core/test_commit_decide.py::test_ignore_rules_that_could_not_be_read_fail_closed
tests/test_mw006_commit_content.py::test_a_force_added_ignored_file_is_refused -> tests/shell/test_commit_facts.py::test_the_ignore_answer_covers_the_added_paths_only
# E16
tests/test_mw006_commit_content.py::test_data_files_are_refused_by_extension -> tests/core/test_commit_decide.py::test_data_files_are_refused_by_extension
tests/test_mw006_commit_content.py::test_data_files_are_refused_by_extension -> tests/core/test_commit_decide.py::test_names_that_only_contain_a_data_extension_pass
# E17: which copy is measured is the shell's fact
tests/test_mw006_commit_content.py::test_a_file_over_the_size_limit_is_refused -> tests/core/test_commit_decide.py::test_a_file_over_the_size_limit_is_refused_and_one_under_passes
tests/test_mw006_commit_content.py::test_a_file_over_the_size_limit_is_refused -> tests/core/test_commit_decide.py::test_sizes_that_could_not_be_read_fail_closed
tests/test_mw006_commit_content.py::test_a_file_over_the_size_limit_is_refused -> tests/shell/test_commit_facts.py::test_the_size_is_that_of_the_staged_blob_or_of_the_working_file
# E18
tests/test_mw006_commit_content.py::test_the_profile_overrides_junk_data_and_size -> tests/core/test_commit_decide.py::test_the_profile_overrides_replace_the_defaults_each_alone
tests/test_mw006_commit_content.py::test_the_profile_overrides_junk_data_and_size -> tests/shell/test_commit_facts.py::test_the_profile_settings_default_and_override_each_alone
tests/test_mw006_commit_content.py::test_the_profile_overrides_junk_data_and_size -> tests/shell/test_commit_facts.py::test_the_facts_carry_the_profile_values
# E19
tests/test_mw006_commit_content.py::test_deleting_a_junk_or_data_file_is_allowed -> tests/core/test_commit_decide.py::test_deleting_a_junk_data_or_big_file_is_allowed_and_changing_one_is_not
tests/test_mw006_commit_content.py::test_deleting_a_junk_or_data_file_is_allowed -> tests/shell/test_commit_facts.py::test_a_deleted_file_has_no_size
# E20: the message file and here-document are read by the shell
tests/test_mw006_commit_message.py::test_the_message_must_name_the_open_card -> tests/core/test_commit_decide.py::test_a_message_that_names_the_open_card_passes
tests/test_mw006_commit_message.py::test_the_message_must_name_the_open_card -> tests/core/test_commit_decide.py::test_a_message_that_does_not_name_the_open_card_is_refused
tests/test_mw006_commit_message.py::test_the_message_must_name_the_open_card -> tests/core/test_commit_decide.py::test_a_session_with_no_open_card_has_none_to_name
tests/test_mw006_commit_message.py::test_the_message_must_name_the_open_card -> tests/shell/test_commit_facts.py::test_the_message_is_read_as_text_or_as_none
# E21
tests/test_mw006_commit_message.py::test_the_switch_turns_the_message_rule_off -> tests/core/test_commit_decide.py::test_the_switch_turns_the_message_rule_off_and_nothing_else
tests/test_mw006_commit_message.py::test_the_switch_turns_the_message_rule_off -> tests/shell/test_commit_facts.py::test_the_facts_carry_the_profile_values
# E22
tests/test_mw006_commit_message.py::test_an_unreadable_message_refuses -> tests/core/test_commit_decide.py::test_an_unreadable_message_refuses_while_the_rule_is_on
tests/test_mw006_commit_message.py::test_an_unreadable_message_refuses -> tests/shell/test_commit_facts.py::test_the_message_is_read_as_text_or_as_none
# E23
tests/test_mw006_commit_message.py::test_the_gate_runs_in_the_shell_group_with_its_tag_and_a_switch -> tests/shell/test_commit_wiring.py::test_the_manifest_declares_exactly_the_reasons_the_core_can_return
tests/test_mw006_commit_message.py::test_the_gate_runs_in_the_shell_group_with_its_tag_and_a_switch -> tests/shell/test_commit_wiring.py::test_the_gate_refuses_through_the_dispatcher_with_its_tag_and_a_switch
# E24: README substring test
tests/test_mw006_readme.py::test_the_readme_has_one_section_commit_checks -> dropped: doc
# E25: README substring test; the reason ids against the manifest are proven by the wiring test
tests/test_mw006_readme.py::test_the_section_states_the_rules_reasons_keys_and_ways_out -> dropped: doc
# MW-033 E1
tests/test_mw033_commit_gate.py::test_the_id_may_stand_anywhere_in_the_subject -> tests/core/test_commit_decide.py::test_a_message_that_names_the_open_card_passes
tests/test_mw033_commit_gate.py::test_the_id_may_stand_anywhere_in_the_subject -> tests/core/test_commit_decide.py::test_a_message_that_does_not_name_the_open_card_is_refused
# MW-033 E2
tests/test_mw033_commit_gate.py::test_the_open_card_id_passes_whatever_the_prefix_is_now -> tests/core/test_commit_decide.py::test_the_open_card_id_passes_whatever_the_prefix_is_now
tests/test_mw033_commit_gate.py::test_the_open_card_id_passes_whatever_the_prefix_is_now -> tests/core/test_commit_decide.py::test_with_no_prefix_set_only_the_open_cards_own_id_counts
tests/test_mw033_commit_gate.py::test_the_open_card_id_passes_whatever_the_prefix_is_now -> tests/shell/test_commit_facts.py::test_the_facts_carry_the_profile_values
# MW-033 E3
tests/test_mw033_commit_gate.py::test_the_refusal_says_the_id_may_stand_anywhere_in_the_first_line -> tests/core/test_commit_decide.py::test_the_refusal_names_the_card_that_was_named_and_the_way_out
# MW-033 E4
tests/test_mw033_commit_gate.py::test_a_chained_add_and_commit_says_to_use_two_calls -> tests/core/test_commit_decide.py::test_a_chained_add_and_commit_says_to_use_two_calls
# MW-033 E5
tests/test_mw033_commit_gate.py::test_readme_register_changelog_and_card_name_the_card -> dropped: doc
# MW-034 E1
tests/test_mw034_staged_paths.py::test_a_staged_file_outside_the_paths_is_refused -> tests/core/test_commit_decide.py::test_a_staged_file_outside_the_paths_is_refused_and_one_inside_passes
# MW-034 E2
tests/test_mw034_staged_paths.py::test_files_a_script_wrote_inside_the_paths_are_allowed -> tests/core/test_commit_decide.py::test_files_a_script_wrote_inside_the_paths_are_allowed
# MW-034 E3
tests/test_mw034_staged_paths.py::test_a_file_staged_earlier_outside_the_paths_is_judged_by_what_git_takes -> tests/core/test_commit_decide.py::test_a_file_staged_earlier_outside_the_paths_is_refused_in_the_forms_that_take_the_staged_list
tests/test_mw034_staged_paths.py::test_a_file_staged_earlier_outside_the_paths_is_judged_by_what_git_takes -> tests/shell/test_commit_facts.py::test_the_taken_list_of_each_form_on_each_kind_of_repository
# MW-034 E4
# kept: tests/test_mw034_staged_paths.py::test_a_second_session_cannot_take_a_card_in_a_busy_root - `take-root-busy` is the lock gate (next card of the migration)
# MW-034 E5
# kept: tests/test_mw034_staged_paths.py::test_the_same_session_may_take_its_own_card_again - lock gate
# MW-034 E6
# kept: tests/test_mw034_staged_paths.py::test_a_take_after_the_holders_card_closed_is_allowed - lock gate
# MW-034 E7
tests/test_mw034_staged_paths.py::test_readme_register_changelog_and_card_name_the_card -> dropped: doc
# MW-043 E1: the `-o` and `--only` spellings are the same form as `--` for the reader
tests/test_mw043_commit_takes.py::test_a_foreign_staged_file_does_not_stop_a_commit_that_names_its_own_paths -> tests/shell/test_commit_facts.py::test_the_taken_list_of_each_form_on_each_kind_of_repository
tests/test_mw043_commit_takes.py::test_a_foreign_staged_file_does_not_stop_a_commit_that_names_its_own_paths -> tests/shell/test_commit_facts.py::test_the_paths_form_agrees_with_what_real_git_commits
# MW-043 E2
tests/test_mw043_commit_takes.py::test_a_plain_commit_takes_the_staged_list_and_is_refused_for_a_foreign_file -> tests/core/test_commit_decide.py::test_a_plain_commit_takes_the_staged_list_and_names_the_way_out
tests/test_mw043_commit_takes.py::test_a_plain_commit_takes_the_staged_list_and_is_refused_for_a_foreign_file -> tests/shell/test_commit_facts.py::test_the_taken_list_of_each_form_on_each_kind_of_repository
# MW-043 E3
tests/test_mw043_commit_takes.py::test_an_include_commit_takes_the_staged_list_plus_the_named_paths -> tests/core/test_commit_decide.py::test_an_include_commit_takes_the_staged_list_plus_the_named_paths
tests/test_mw043_commit_takes.py::test_an_include_commit_takes_the_staged_list_plus_the_named_paths -> tests/shell/test_commit_facts.py::test_the_taken_list_of_each_form_on_each_kind_of_repository
# MW-043 E4
tests/test_mw043_commit_takes.py::test_an_all_commit_takes_the_staged_list_plus_every_modified_tracked_file -> tests/core/test_commit_decide.py::test_an_all_commit_takes_the_staged_list_plus_every_modified_tracked_file
tests/test_mw043_commit_takes.py::test_an_all_commit_takes_the_staged_list_plus_every_modified_tracked_file -> tests/shell/test_commit_facts.py::test_the_all_form_agrees_with_what_real_git_commits
# MW-043 E5
tests/test_mw043_commit_takes.py::test_an_amend_follows_the_same_rule_and_judges_nothing_else -> tests/core/test_commit_decide.py::test_an_amend_follows_the_form_it_is_given_and_judges_nothing_else
tests/test_mw043_commit_takes.py::test_an_amend_follows_the_same_rule_and_judges_nothing_else -> tests/shell/test_commit_facts.py::test_the_taken_list_of_each_form_on_each_kind_of_repository
# MW-043 E6
tests/test_mw043_commit_takes.py::test_a_named_path_outside_the_card_is_still_refused -> tests/core/test_commit_decide.py::test_a_named_path_outside_the_card_is_refused_with_the_way_out_for_a_named_path
# MW-043 E7
# kept: tests/test_mw043_commit_takes.py::test_the_start_block_counts_the_files_staged_outside_the_card - the start block line is not a commit_files decision
# MW-043 E8
# kept: tests/test_mw043_commit_takes.py::test_staged_outside_counts_against_one_card_or_every_open_card - `staged_outside` serves the start block and `mkway check`
# MW-043 E9
# kept: tests/test_mw043_commit_takes.py::test_check_prints_the_staged_files_outside_every_open_card - `mkway check` line
# MW-043 E10
tests/test_mw043_commit_takes.py::test_readme_register_changelog_and_card_name_the_card -> dropped: doc
# MW-021 E4
tests/test_mw021_commit.py::test_a_new_rule_card_with_no_test_file_is_refused -> tests/core/test_commit_decide.py::test_a_new_rule_card_with_no_test_file_is_refused_and_with_its_test_allowed
# MW-021 E5
tests/test_mw021_commit.py::test_a_changed_card_needs_its_test_staged_too -> tests/core/test_commit_decide.py::test_a_changed_card_needs_its_test_staged_too
# MW-021 E5
tests/test_mw021_commit.py::test_the_named_paths_form_is_read_too -> tests/core/test_commit_decide.py::test_the_named_paths_form_is_read_too
# MW-021 E6
tests/test_mw021_commit.py::test_what_is_allowed -> tests/core/test_commit_decide.py::test_what_a_rule_card_check_allows
# MW-021 E6
tests/test_mw021_commit.py::test_the_check_is_off_without_both_keys_and_without_the_id_form -> tests/core/test_commit_decide.py::test_a_rule_card_check_that_is_off_refuses_nothing
tests/test_mw021_commit.py::test_the_check_is_off_without_both_keys_and_without_the_id_form -> tests/shell/test_commit_facts.py::test_rule_cards_and_their_tests_are_read_from_the_profile
tests/test_mw021_commit.py::test_the_check_is_off_without_both_keys_and_without_the_id_form -> tests/shell/test_commit_facts.py::test_the_rule_card_check_is_off_without_both_keys_and_the_id_form
# MW-021 E6
tests/test_mw021_commit.py::test_the_manifest_declares_the_reason_in_the_integrity_commit_gate -> tests/shell/test_commit_wiring.py::test_the_manifest_declares_exactly_the_reasons_the_core_can_return
# MW-053 E1: decision in the core, the ordered rows and holders read by the shell, one run through the real register
tests/test_mw053_orderer_commit.py::test_orderer_commits_card_md_and_register_without_holding_the_card -> tests/core/test_commit_decide.py::test_the_orderer_commits_card_md_order_md_and_the_register_without_holding_the_card
tests/test_mw053_orderer_commit.py::test_orderer_commits_card_md_and_register_without_holding_the_card -> tests/shell/test_commit_facts.py::test_the_orderer_facts_are_the_cards_the_session_ordered_and_who_holds_them
tests/test_mw053_orderer_commit.py::test_orderer_commits_card_md_and_register_without_holding_the_card -> tests/shell/test_commit_facts.py::test_the_gate_lets_the_orderer_commit_its_card_folder_and_refuses_the_stranger
# MW-053 E2
tests/test_mw053_orderer_commit.py::test_the_plain_form_of_the_orderer_takes_the_staged_list -> tests/core/test_commit_decide.py::test_the_plain_form_of_the_orderer_takes_the_staged_list
# MW-053 E3
tests/test_mw053_orderer_commit.py::test_the_include_form_of_the_orderer_takes_the_staged_list_plus_the_named -> tests/core/test_commit_decide.py::test_the_include_form_of_the_orderer_takes_the_staged_list_plus_the_named
# MW-053 E4
tests/test_mw053_orderer_commit.py::test_two_ordered_cards_in_one_commit_are_allowed -> tests/core/test_commit_decide.py::test_two_ordered_cards_in_one_commit_are_allowed
# MW-053 E5
tests/test_mw053_orderer_commit.py::test_the_register_alone_is_allowed_for_the_orderer -> tests/core/test_commit_decide.py::test_the_register_alone_is_allowed_for_the_orderer
# MW-053 E6
tests/test_mw053_orderer_commit.py::test_a_session_that_did_not_order_the_card_is_refused_as_today -> tests/core/test_commit_decide.py::test_a_session_that_did_not_order_the_card_is_refused_as_today
tests/test_mw053_orderer_commit.py::test_a_session_that_did_not_order_the_card_is_refused_as_today -> tests/shell/test_commit_facts.py::test_a_session_that_orders_nothing_has_no_ordered_cards
tests/test_mw053_orderer_commit.py::test_a_session_that_did_not_order_the_card_is_refused_as_today -> tests/shell/test_commit_facts.py::test_a_session_has_only_the_cards_it_ordered
# MW-053 E7: the owner's and the empty session id are left out of `ordered` by the shell
tests/test_mw053_orderer_commit.py::test_a_card_ordered_by_the_owner_or_a_session_without_an_id_is_refused -> tests/core/test_commit_decide.py::test_a_card_ordered_by_the_owner_is_no_ordered_card_of_a_session
tests/test_mw053_orderer_commit.py::test_a_card_ordered_by_the_owner_or_a_session_without_an_id_is_refused -> tests/shell/test_commit_facts.py::test_a_session_that_orders_nothing_has_no_ordered_cards
tests/test_mw053_orderer_commit.py::test_a_card_ordered_by_the_owner_or_a_session_without_an_id_is_refused -> tests/shell/test_commit_facts.py::test_a_card_the_owner_ordered_is_not_in_a_sessions_facts
# MW-053 E8
tests/test_mw053_orderer_commit.py::test_a_mixed_commit_is_refused_naming_the_files_that_do_not_belong -> tests/core/test_commit_decide.py::test_a_mixed_commit_is_refused_naming_the_files_that_do_not_belong
# MW-053 E9
tests/test_mw053_orderer_commit.py::test_a_holder_keeps_its_rules -> tests/core/test_commit_decide.py::test_a_holder_keeps_its_rules
# MW-053 E10: the holders are a fact, unread fails closed
tests/test_mw053_orderer_commit.py::test_a_file_under_the_holders_paths_is_the_holders_and_names_the_holder -> tests/core/test_commit_decide.py::test_a_file_under_the_holders_paths_is_the_holders_and_names_the_holder
tests/test_mw053_orderer_commit.py::test_a_file_under_the_holders_paths_is_the_holders_and_names_the_holder -> tests/core/test_commit_decide.py::test_holders_that_could_not_be_read_fail_closed_only_when_they_are_needed
tests/test_mw053_orderer_commit.py::test_a_file_under_the_holders_paths_is_the_holders_and_names_the_holder -> tests/shell/test_commit_facts.py::test_holders_that_cannot_be_read_are_an_unread_fact
tests/test_mw053_orderer_commit.py::test_a_file_under_the_holders_paths_is_the_holders_and_names_the_holder -> tests/shell/test_commit_facts.py::test_a_register_that_cannot_be_read_gives_no_ordered_cards
# MW-053 E11
tests/test_mw053_orderer_commit.py::test_the_other_checks_still_run_on_the_orderer_files -> tests/core/test_commit_decide.py::test_the_other_checks_still_run_on_the_orderer_files
# MW-053 E12: register and CHANGELOG substring test
tests/test_mw053_orderer_commit.py::test_register_changelog_and_card_name_the_card -> dropped: doc
# MW-058 E1: the form is the core's, the list of each form is the shell's
tests/test_mw058_amend_only.py::test_the_files_an_amend_takes_follow_its_form -> tests/core/test_commit_decide.py::test_a_message_only_amend_takes_no_files
tests/test_mw058_amend_only.py::test_the_files_an_amend_takes_follow_its_form -> tests/core/test_commit_decide.py::test_the_files_the_shell_read_for_a_message_only_amend_are_not_judged
tests/test_mw058_amend_only.py::test_the_files_an_amend_takes_follow_its_form -> tests/core/test_commit_decide.py::test_the_forms_that_take_files_are_judged_by_them
tests/test_mw058_amend_only.py::test_the_files_an_amend_takes_follow_its_form -> tests/shell/test_commit_facts.py::test_the_files_an_amend_takes_follow_its_form
# MW-058 E2
# kept: tests/test_mw058_amend_only.py::test_real_git_takes_nothing_for_a_message_only_amend - a proof of what real git does, no engine code is called; it moves with the shell layer's own card
# MW-058 E3
tests/test_mw058_amend_only.py::test_the_message_checks_still_run_on_a_message_only_amend -> tests/core/test_commit_decide.py::test_the_message_checks_still_run_on_a_message_only_amend
tests/test_mw058_amend_only.py::test_the_message_checks_still_run_on_a_message_only_amend -> tests/shell/test_commit_facts.py::test_the_message_checks_still_run_on_a_message_only_amend_through_the_gate
# MW-058 E5: register and CHANGELOG substring test
tests/test_mw058_amend_only.py::test_register_changelog_and_card_name_the_card -> dropped: doc
# MW-060 E1..E3: `combine` is pure and lives in the core; `gate_commit.combine` is the same function
tests/test_mw060_taken_tree.py::test_the_reader_combines_the_lists_as_git_takes_them -> tests/core/test_commit_decide.py::test_the_reader_combines_the_lists_as_git_takes_them
# MW-060 E14: `message_only_amend` is the core's, the no-git-call part is the shell's
tests/test_mw060_taken_tree.py::test_a_message_only_amend_takes_no_files -> tests/core/test_commit_decide.py::test_a_message_only_amend_takes_no_files
tests/test_mw060_taken_tree.py::test_a_message_only_amend_takes_no_files -> tests/shell/test_commit_facts.py::test_a_message_only_amend_reads_no_git_and_takes_no_files
# MW-060 E8
# kept: tests/test_mw060_taken_tree.py::test_both_gates_read_what_the_commit_takes_through_one_function - `commit_tests` calls `gate_commit.taken`, the one reader; its own gate's card
# MW-060 E9
# kept: tests/test_mw060_taken_tree.py::test_commit_files_still_reads_the_same_list_through_the_shared_reader - the file gate's `_taken` is the shared reader; the proof that there is one
