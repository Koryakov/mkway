# MW-065 case map: old test -> new test

> One line per old case: `old_file::old_test -> new_file::new_test`. An old test that held several cases is split into one
> test id per case; its line names the main new node, the card rows name them all. Nothing is dropped. A case that proves
> the wiring through the real manifest and dispatcher (the deny and the switch of one gate) has no new home and stays in
> its old module; those cases are listed at the end as a comment, and `tests/test_mw065_case_map.py` checks that they are
> still there.

## tests/test_mw007_edit_gate.py (owner-ask edit gate)
tests/test_mw007_edit_gate.py::test_edit_gate_leaves_other_writes_alone -> tests/core/test_ask_decide.py::test_a_write_to_a_path_that_is_not_an_ask_is_allowed
tests/test_mw007_edit_gate.py::test_an_ask_needs_a_sources_file_with_a_kind -> tests/core/test_ask_decide.py::test_an_ask_with_no_sources_file_is_refused_and_names_it
tests/test_mw007_edit_gate.py::test_substance_needs_a_count_line_and_a_quote_line -> tests/core/test_ask_decide.py::test_substance_needs_a_count_line_and_a_quote_line
tests/test_mw007_edit_gate.py::test_a_full_substance_sources_file_lets_the_ask_through -> tests/core/test_ask_decide.py::test_a_full_substance_sources_file_is_allowed
tests/test_mw007_edit_gate.py::test_session_and_lock_kinds_each_need_their_checked_line -> tests/core/test_ask_decide.py::test_a_session_or_lock_file_without_its_checked_line_is_refused
tests/test_mw007_edit_gate.py::test_folder_and_sources_come_from_the_profile -> tests/shell/test_ask_facts.py::test_a_source_the_profile_lists_is_named_when_missing
tests/test_mw007_edit_gate.py::test_an_unreadable_sources_file_refuses_and_never_crashes -> tests/shell/test_ask_facts.py::test_a_folder_in_place_of_the_sources_file_is_refused_missing

## tests/test_mw007_stop_gate.py (owner-ask stop gate)
tests/test_mw007_stop_gate.py::test_a_reply_without_the_marker_is_never_blocked -> tests/core/test_ask_decide.py::test_a_final_reply_that_may_go_to_the_owner_is_allowed
tests/test_mw007_stop_gate.py::test_a_marker_line_needs_an_ask_written_in_this_turn -> tests/core/test_ask_decide.py::test_a_final_reply_with_a_marker_and_no_ask_written_is_blocked
tests/test_mw007_stop_gate.py::test_stop_hook_active_never_blocks -> tests/core/test_ask_decide.py::test_a_final_reply_that_may_go_to_the_owner_is_allowed
tests/test_mw007_stop_gate.py::test_only_a_real_ask_file_counts_as_written -> tests/core/test_ask_decide.py::test_a_final_reply_with_a_marker_and_no_ask_written_is_blocked
tests/test_mw007_stop_gate.py::test_marker_and_folder_come_from_the_profile -> tests/shell/test_ask_facts.py::test_a_marker_the_profile_lists_needs_an_ask_file
tests/test_mw007_stop_gate.py::test_a_missing_or_broken_transcript_does_not_crash_the_gate -> tests/shell/test_ask_facts.py::test_a_transcript_that_is_not_there_blocks_a_marker_and_says_so

## tests/test_mw008_gate.py (search gate)
tests/test_mw008_gate.py::test_a_question_needs_a_search_of_this_turn -> tests/core/test_ask_decide.py::test_a_question_with_no_search_of_this_turn_is_refused
tests/test_mw008_gate.py::test_only_a_record_newer_than_the_last_user_message_counts -> tests/core/test_ask_decide.py::test_a_question_after_a_search_of_this_turn_is_allowed
tests/test_mw008_gate.py::test_a_write_to_a_question_file_is_gated -> tests/core/test_ask_decide.py::test_a_write_to_a_question_file_with_no_search_is_refused
tests/test_mw008_gate.py::test_the_gate_fails_open_with_a_log_row -> tests/shell/test_ask_facts.py::test_a_transcript_that_cannot_be_read_is_a_log_row_never_a_refusal

## tests/test_mw008_ask.py (ledger source of the ask)
tests/test_mw008_ask.py::test_substance_with_hits_needs_the_count_and_a_ledger_quote -> tests/core/test_ask_decide.py::test_substance_with_hits_needs_the_count_and_a_ledger_quote
tests/test_mw008_ask.py::test_zero_hits_need_a_search_record_line -> tests/core/test_ask_decide.py::test_zero_hits_need_a_search_record_line
tests/test_mw008_ask.py::test_a_full_ledger_sources_file_lets_the_ask_through -> tests/core/test_ask_decide.py::test_a_full_ledger_sources_file_is_allowed

## tests/test_mw014_gate.py (ask fields, one open ask, pop-up tool)
tests/test_mw014_gate.py::test_a_missing_field_line_is_refused_and_named -> tests/core/test_ask_decide.py::test_a_missing_field_line_is_refused_and_named
tests/test_mw014_gate.py::test_an_ask_with_no_field_names_all_five -> tests/core/test_ask_decide.py::test_an_ask_with_no_field_names_all_five
tests/test_mw014_gate.py::test_a_field_with_an_unusable_value_counts_as_missing -> tests/core/test_ask_decide.py::test_a_field_with_an_unusable_value_counts_as_missing
tests/test_mw014_gate.py::test_a_complete_ask_is_allowed_by_every_write_tool -> tests/core/test_ask_decide.py::test_a_complete_ask_is_allowed
tests/test_mw014_gate.py::test_an_edit_is_judged_on_the_file_it_leaves -> tests/core/test_ask_decide.py::test_an_edit_that_leaves_the_ask_incomplete_is_refused_and_named
tests/test_mw014_gate.py::test_the_fields_come_after_the_sources_and_leave_other_files_alone -> tests/core/test_ask_decide.py::test_the_sources_check_decides_before_the_fields
tests/test_mw014_gate.py::test_a_second_open_ask_by_the_same_session_is_refused -> tests/core/test_ask_decide.py::test_a_second_open_ask_by_the_same_session_is_refused
tests/test_mw014_gate.py::test_an_ask_that_is_no_longer_open_frees_the_session -> tests/shell/test_ask_facts.py::test_an_ask_that_is_no_longer_open_frees_the_session
tests/test_mw014_gate.py::test_max_open_comes_from_the_profile -> tests/shell/test_ask_facts.py::test_the_profile_refuses_a_third_open_ask
tests/test_mw014_gate.py::test_a_session_without_an_id_and_a_missing_file_do_not_count -> tests/shell/test_ask_facts.py::test_a_record_whose_ask_file_is_gone_counts_for_nothing
tests/test_mw014_gate.py::test_the_post_step_records_who_wrote_an_ask -> tests/shell/test_ask_facts.py::test_the_post_step_records_the_session_that_wrote_an_ask
tests/test_mw014_gate.py::test_the_pop_up_question_tool_is_refused_with_the_file_route -> tests/core/test_ask_decide.py::test_the_pop_up_question_tool_is_refused_with_the_file_route
tests/test_mw014_gate.py::test_the_switch_lets_the_pop_up_question_tool_through -> tests/shell/test_ask_facts.py::test_the_pop_up_question_tool_follows_the_profile

## tests/test_mw019_gate.py (outbox check gate)
tests/test_mw019_gate.py::test_a_check_whose_sha_line_is_not_the_documents_is_refused -> tests/core/test_ask_decide.py::test_a_write_that_leaves_a_check_with_no_right_sha_is_refused
tests/test_mw019_gate.py::test_a_check_with_the_right_sha_is_allowed_by_every_write_tool -> tests/core/test_ask_decide.py::test_a_write_that_leaves_a_check_with_the_right_sha_is_allowed
tests/test_mw019_gate.py::test_an_edit_is_judged_on_the_file_it_leaves -> tests/shell/test_outbox_facts.py::test_an_edit_that_turns_the_sha_wrong_is_refused_although_the_file_on_disk_was_right
tests/test_mw019_gate.py::test_a_check_with_no_sha_line_or_a_second_wrong_one_is_refused -> tests/core/test_ask_decide.py::test_a_write_that_leaves_a_check_with_no_right_sha_is_refused
tests/test_mw019_gate.py::test_a_check_of_a_missing_document_is_refused -> tests/shell/test_outbox_facts.py::test_a_check_of_a_document_that_is_not_on_disk_is_refused_and_names_it
tests/test_mw019_gate.py::test_other_files_and_tools_are_not_this_gates -> tests/core/test_ask_decide.py::test_a_write_that_is_not_a_check_file_is_allowed
tests/test_mw019_gate.py::test_the_post_step_records_the_session_and_the_check_sha -> tests/shell/test_outbox_facts.py::test_the_post_step_records_the_check_and_its_session
tests/test_mw019_gate.py::test_the_post_step_ignores_other_files -> tests/shell/test_outbox_facts.py::test_the_post_step_leaves_no_row_for_a_file_that_is_not_a_written_check
tests/test_mw019_gate.py::test_a_failed_record_is_a_warn_never_a_refusal -> tests/shell/test_outbox_facts.py::test_a_failed_record_is_a_warn_that_says_the_check_will_read_unproven
tests/test_mw019_gate.py::test_the_stop_reminder_names_a_file_changed_after_its_check -> tests/shell/test_outbox_facts.py::test_a_file_changed_after_its_check_gets_a_reminder_that_names_it
tests/test_mw019_gate.py::test_the_stop_reminder_is_silent_and_never_blocks -> tests/shell/test_outbox_facts.py::test_a_valid_file_gives_no_reminder

# Stays (no new home): the wiring cases, each the one deny and the switch of its gate through the real manifest.
# tests/test_mw007_edit_gate.py::test_the_edit_gate_runs_in_the_edit_group_and_has_a_switch
# tests/test_mw007_stop_gate.py::test_the_stop_gate_runs_in_the_stop_group_and_has_a_switch
# tests/test_mw008_gate.py::test_the_search_gate_runs_in_the_edit_group_and_has_a_switch
# tests/test_mw014_gate.py::test_the_dispatcher_refuses_the_pop_up_tool_before_the_search_gate
# tests/test_mw019_gate.py::test_the_manifest_entries_of_the_outbox_check
# tests/test_mw019_gate.py::test_the_dispatcher_refuses_a_stale_check_write
