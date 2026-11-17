# MW-066 case map: old session-family tests -> new tests

> One line per old test. New homes: `tests/core/test_session_decide.py` (table tests on Facts -> Verdict, no disk, no git),
> `tests/shell/test_session_facts.py` (facts read from real files, the wiring, the dispatcher). `dropped: doc` is a README,
> keys-file, register, CHANGELOG or VERSION text check (a document is never evidence of behaviour). No case is dropped for
> failing T1-T8: every behaviour an old case proved has a new node. A case not listed here stays where it is, because it is
> not a decision of the session gates: the lock-target and lock-gate cases, the install and `mkway check` cases, the start
> block and the board (startline), the send, ack and inbox commands, the notices and the registry commands, the agent rows
> and the owner-terminal and append-only record cases. A listed test is removed from its old module by this card.

tests/test_subtask.py::test_precedence_and_status_from_the_register -> tests/shell/test_session_facts.py::test_the_subtask_facts_are_read_from_the_register_the_records_and_the_card_file
tests/test_subtask.py::test_exempt_paths_and_card_files -> tests/core/test_session_decide.py::test_the_subtask_verdict
tests/test_subtask.py::test_paths_changed_until_the_owner_opens_again -> tests/shell/test_session_facts.py::test_the_subtask_facts_are_read_from_the_register_the_records_and_the_card_file
tests/test_subtask.py::test_tampered_register_refuses_every_edit -> tests/core/test_session_decide.py::test_the_subtask_verdict
tests/test_mw017_gates.py::test_a_lead_may_edit_the_order_of_its_cards_and_the_asks_folder -> tests/shell/test_session_facts.py::test_what_a_lead_may_write_is_read_from_its_register_rows_and_the_card_status
tests/test_mw017_gates.py::test_a_lead_edit_of_any_other_path_is_lead_no_edit -> tests/core/test_session_decide.py::test_the_lead_edit_verdict
tests/test_mw017_gates.py::test_a_session_that_is_no_lead_is_not_judged -> tests/core/test_session_decide.py::test_the_lead_edit_verdict
tests/test_mw017_gates.py::test_the_subtask_gate_lets_a_lead_write_its_order_file -> tests/shell/test_session_facts.py::test_the_subtask_gate_lets_a_lead_write_what_the_lead_rule_allows
tests/test_mw017_gates.py::test_a_lead_shell_write_is_lead_no_edit -> tests/shell/test_session_facts.py::test_the_shell_reader_hands_the_core_the_writes_of_a_command_and_a_card_take
tests/test_mw017_gates.py::test_a_lead_card_take_is_lead_no_take -> tests/core/test_session_decide.py::test_the_lead_shell_verdict
tests/test_mw017_gates.py::test_the_manifest_wires_the_lead_gate_as_a_form_gate_first_in_its_groups -> tests/shell/test_session_facts.py::test_each_session_form_entry_is_wired_to_its_shell_function_and_event
tests/test_mw017_gates.py::test_in_watch_mode_the_refusal_is_logged_and_the_call_goes_ahead -> tests/shell/test_session_facts.py::test_a_lead_edit_refusal_in_watch_mode_is_a_would_refuse_row_and_the_call_goes_ahead
tests/test_mw017_gates.py::test_a_first_install_starts_the_lead_gate_in_watch -> tests/shell/test_session_facts.py::test_a_first_install_starts_the_gate_in_watch
tests/test_mw018_gate.py::test_a_ping_line_of_a_row_the_session_wrote_passes_and_is_recorded -> tests/shell/test_session_facts.py::test_an_allowed_ping_appends_one_ping_row_with_the_row_id_the_session_and_a_time
tests/test_mw018_gate.py::test_a_body_with_any_extra_text_is_message_not_in_inbox -> tests/core/test_session_decide.py::test_the_send_verdict
tests/test_mw018_gate.py::test_the_id_of_another_senders_row_or_of_no_row_is_refused -> tests/shell/test_session_facts.py::test_the_send_gate_finds_the_row_in_the_shared_inbox_and_whether_it_was_pinged
tests/test_mw018_gate.py::test_a_second_ping_for_the_same_row_is_message_duplicate -> tests/core/test_session_decide.py::test_the_send_verdict
tests/test_mw018_gate.py::test_a_pure_idle_subscription_carries_no_body_and_passes -> tests/core/test_session_decide.py::test_the_send_verdict
tests/test_mw018_gate.py::test_the_manifest_wires_the_message_gate_as_a_form_gate -> tests/shell/test_session_facts.py::test_each_session_form_entry_is_wired_to_its_shell_function_and_event
tests/test_mw018_gate.py::test_in_watch_mode_the_refusal_is_logged_and_the_call_goes_ahead -> tests/shell/test_session_facts.py::test_a_message_refusal_in_watch_mode_is_a_would_refuse_row_and_records_no_ping
tests/test_mw018_gate.py::test_a_first_install_starts_the_message_gate_in_watch -> tests/shell/test_session_facts.py::test_a_first_install_starts_the_gate_in_watch
tests/test_mw018_remind.py::test_the_prompt_reminds_a_session_of_its_unacked_items_and_never_blocks -> tests/shell/test_session_facts.py::test_the_prompt_reminder_reads_the_unacked_rows_of_the_sessions_own_inbox
tests/test_mw018_remind.py::test_a_stop_with_an_old_unacked_order_gets_a_reminder_never_a_block -> tests/shell/test_session_facts.py::test_the_stop_reminder_reads_the_age_of_unacked_orders_against_the_profiles_minutes
tests/test_mw028_lead_authors.py::test_a_lead_writes_card_and_order_of_its_proposed_card -> tests/shell/test_session_facts.py::test_what_a_lead_may_write_is_read_from_its_register_rows_and_the_card_status
tests/test_mw028_lead_authors.py::test_after_open_card_is_sealed_to_the_lead_and_order_stays_its_own -> tests/shell/test_session_facts.py::test_what_a_lead_may_write_is_read_from_its_register_rows_and_the_card_status
tests/test_mw028_lead_authors.py::test_another_leads_proposed_card_stays_refused -> tests/shell/test_session_facts.py::test_the_subtask_gate_lets_a_lead_write_what_the_lead_rule_allows
tests/test_mw028_lead_authors.py::test_a_builder_on_a_proposed_card_is_unchanged -> tests/shell/test_session_facts.py::test_the_subtask_gate_lets_a_lead_write_what_the_lead_rule_allows
tests/test_mw028_lead_authors.py::test_register_changelog_version_and_card_name_the_card -> dropped: doc
tests/test_records.py::test_post_group_records_a_session_command -> tests/shell/test_session_facts.py::test_a_line_whose_nonce_was_issued_is_recorded_with_the_session_and_a_time
tests/test_records.py::test_forged_or_replayed_line_writes_no_record -> tests/shell/test_session_facts.py::test_a_replayed_line_is_recorded_once
tests/test_records.py::test_post_failure_allows_with_a_warn_row -> tests/shell/test_session_facts.py::test_a_record_that_cannot_be_written_allows_with_a_warn_row
tests/test_records.py::test_post_reads_a_powershell_string_response -> tests/shell/test_session_facts.py::test_a_powershell_string_response_is_read_like_a_bash_stdout
tests/test_mw017_docs.py::test_the_readme_has_one_section_the_lead_role -> dropped: doc
tests/test_mw017_docs.py::test_the_section_names_every_command_reason_key_and_file -> dropped: doc
tests/test_mw017_docs.py::test_keys_md_has_a_line_for_each_lead_key -> dropped: doc
tests/test_mw017_docs.py::test_the_version_is_0_2_0_and_the_changelog_names_the_card -> dropped: doc
tests/test_mw018_docs.py::test_keys_md_has_a_line_for_each_messaging_key_and_the_default_lock_target -> dropped: doc
tests/test_mw018_docs.py::test_the_readme_has_one_section_messaging_order -> dropped: doc
tests/test_mw018_docs.py::test_the_section_names_every_command_reason_key_file_and_rule -> dropped: doc
tests/test_mw018_docs.py::test_the_register_row_the_changelog_line_and_the_card_folder -> dropped: doc
tests/test_mw017_shared.py::test_the_readme_and_keys_name_the_shared_files -> dropped: doc
