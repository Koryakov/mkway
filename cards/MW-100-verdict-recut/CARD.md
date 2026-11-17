# MW-100: A weak or wrong verdict is answered by a re-cut, never by an acceptance

| | |
|---|---|
| **Appetite** | 2.5 hours — from 2026-11-13 |
| **Status** | proposed |
| **Created / updated** | 2026-11-13 / 2026-11-13 |
| **Waiting for** | nothing |
| **Form** | card |
| **Decisions** | R251, R251a, R251b — ids only, no text copied from the ledger; a commit that changes a test names one |
| **Canon** | none for verdict recut: the basis is a real close that no session could finish after a weak verdict, and rulings R251, R251a, R251b |
| **Paths** | `engine/mkway.py`, `engine/core_verdict_recut.py`, `engine/verdict_recut.py`, `engine/core_verdict_add.py`, `engine/verdict_add.py`, `engine/core_verdicts.py`, `engine/verdicts.py`, `engine/core_lock.py`, `tests/`, `README.md`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-100-verdict-recut/CARD.md` |

## 1. Goal

«there is no acceptance of a verdict, weak or wrong. A weak means the row and the test say different things, and a waiver keeps them different for every later reader. The route for both weak and wrong is the re-cut: the lead changes the row's words or the test, and a fresh blind verdict is run on the new cut.» — R251, 2026-11-13. The command is `mkway verdict recut <card> <node> <reason>`, lead only; R251a points 1 to 8 and R251b A to H settle the rest. The recut ids follow `verdict add`, use the existing `tests.verdict_add.mode` (no new key) and are not manifest entries.

## Acceptance examples

Each row becomes a test; `card close` needs every row to name one. E1 to E43: the pure recut core, its purity and the lock gate; E44 to E55: the budget of `verdict add` per node per cut; E56 to E64: the close check; E65 to E77: the shell facts on real git and real files; E78 to E92: the writes; E93 and E94: replays of the real case; E95 to E102: the real command and hooks; E103 to E105: the documents; E106 to E115: the branches the coverage run found untested (added after the code, see the Log).

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | a lead, a weak last row with its recorded run, the cut changed | no command | allowed, the answered run named | tests/core/test_mw100_recut_decide.py::test_a_lead_with_a_weak_row_and_a_changed_cut_is_allowed |
| E2 | the same with a wrong last row (nearest allow of E3 to E6) | no command | allowed | tests/core/test_mw100_recut_decide.py::test_a_wrong_row_is_allowed_as_well |
| E3 | a node with no row | no command | refused `verdict-recut-nothing` | tests/core/test_mw100_recut_decide.py::test_a_node_with_no_row_is_refused_as_nothing |
| E4 | a node whose last row is true | no command | refused `verdict-recut-nothing` | tests/core/test_mw100_recut_decide.py::test_a_node_whose_last_row_is_true_is_refused_as_nothing |
| E5 | a node whose last row is a recut | no command | refused `verdict-recut-nothing` | tests/core/test_mw100_recut_decide.py::test_a_node_whose_last_row_is_a_recut_is_refused_as_nothing |
| E6 | a weak row with no recorded reader run | no command | refused `verdict-recut-nothing` | tests/core/test_mw100_recut_decide.py::test_a_weak_row_with_no_recorded_run_is_refused_as_nothing |
| E7 | no commit touched the test file or the card since the answered run ended | no command | refused `verdict-recut-no-change` | tests/core/test_mw100_recut_decide.py::test_a_cut_that_did_not_change_is_refused_as_no_change |
| E8 | the refusal text of E7 | none | names the answered run | tests/core/test_mw100_recut_decide.py::test_the_no_change_text_names_the_answered_run |
| E9 | the test file differs from HEAD | no command | refused `verdict-recut-stale` | tests/core/test_mw100_recut_decide.py::test_a_test_file_that_differs_from_head_is_refused_as_recut_stale |
| E10 | the refusal text of E9 | none | names the file and both shas | tests/core/test_mw100_recut_decide.py::test_the_recut_stale_text_names_the_file_and_both_shas |
| E11 | the card file differs from HEAD | no command | refused `verdict-recut-stale` | tests/core/test_mw100_recut_decide.py::test_a_card_file_that_differs_from_head_is_refused_as_recut_stale |
| E12 | a node already recut once | no command | refused `verdict-recut-exceeded` | tests/core/test_mw100_recut_decide.py::test_a_second_recut_of_a_node_is_refused_as_exceeded |
| E13 | the refusal text of E12 | none | says split or withdraw the card | tests/core/test_mw100_recut_decide.py::test_the_exceeded_text_says_split_or_withdraw_the_card |
| E14 | a session that is not the card's orderer | no command | refused `verdict-recut-not-lead` | tests/core/test_mw100_recut_decide.py::test_a_session_that_is_not_the_orderer_is_refused_as_not_lead |
| E15 | a card the owner ordered | no command | refused `verdict-recut-not-lead`, the text names `mkway give` | tests/core/test_mw100_recut_decide.py::test_an_owner_ordered_card_is_refused_as_not_lead_with_the_give_text |
| E16 | the holder now | no command | refused `verdict-by-holder` | tests/core/test_mw100_recut_decide.py::test_the_current_holder_is_refused_as_by_holder |
| E17 | a session that took the card once and released it | no command | refused `verdict-by-holder` | tests/core/test_mw100_recut_decide.py::test_a_former_holder_is_refused_as_by_holder |
| E18 | the caller committed the test file | no command | refused `verdict-by-committer` | tests/core/test_mw100_recut_decide.py::test_a_committer_of_the_test_file_is_refused_as_by_committer |
| E19 | another session committed the test file (nearest allow of E18) | no command | allowed | tests/core/test_mw100_recut_decide.py::test_another_session_that_committed_is_allowed |
| E20 | the owner's terminal | no command | refused `verdict-by-owner` | tests/core/test_mw100_recut_decide.py::test_the_owners_terminal_is_refused_as_by_owner |
| E21 | a call with no caller | no command | refused `verdict-no-caller` | tests/core/test_mw100_recut_decide.py::test_a_call_with_no_caller_is_refused_as_no_caller |
| E22 | an open card with a holder | no command | refused `verdict-card-state` | tests/core/test_mw100_recut_decide.py::test_an_open_card_with_a_holder_is_refused_as_card_state |
| E23 | an open card with no holder (nearest allow of E22) | no command | allowed | tests/core/test_mw100_recut_decide.py::test_an_open_card_with_no_holder_is_allowed |
| E24 | a node the card does not name | no command | refused `verdict-node-unknown` | tests/core/test_mw100_recut_decide.py::test_a_node_the_card_does_not_name_is_refused_as_node_unknown |
| E25 | a profile with no `outbox.checkers` | no command | refused `verdict-not-enforced` | tests/core/test_mw100_recut_decide.py::test_a_profile_with_no_checkers_is_refused_as_not_enforced |
| E26 | a profile with `cards.verdicts` off | no command | refused `verdict-not-enforced` | tests/core/test_mw100_recut_decide.py::test_a_profile_with_verdicts_off_is_refused_as_not_enforced |
| E27 | watch mode, `verdict-by-holder` | refused | still refused | tests/core/test_mw100_recut_decide.py::test_in_watch_mode_by_holder_is_still_refused |
| E28 | watch mode, `verdict-by-committer` | refused | still refused | tests/core/test_mw100_recut_decide.py::test_in_watch_mode_by_committer_is_still_refused |
| E29 | watch mode, `verdict-by-owner` | refused | still refused | tests/core/test_mw100_recut_decide.py::test_in_watch_mode_by_owner_is_still_refused |
| E30 | watch mode, `verdict-no-caller` | refused | still refused | tests/core/test_mw100_recut_decide.py::test_in_watch_mode_no_caller_is_still_refused |
| E31 | watch mode, `verdict-recut-no-change` | refused | still refused | tests/core/test_mw100_recut_decide.py::test_in_watch_mode_no_change_is_still_refused |
| E32 | watch mode, `verdict-recut-stale` | refused | still refused | tests/core/test_mw100_recut_decide.py::test_in_watch_mode_recut_stale_is_still_refused |
| E33 | watch mode, `verdict-recut-not-lead` | refused | allowed, listed as watched | tests/core/test_mw100_recut_decide.py::test_in_watch_mode_not_lead_is_allowed_and_listed |
| E34 | watch mode, `verdict-recut-nothing` | refused | allowed, listed | tests/core/test_mw100_recut_decide.py::test_in_watch_mode_nothing_is_allowed_and_listed |
| E35 | watch mode, `verdict-recut-exceeded` | refused | allowed, listed | tests/core/test_mw100_recut_decide.py::test_in_watch_mode_exceeded_is_allowed_and_listed |
| E36 | watch mode, `verdict-card-state` | refused | allowed, listed | tests/core/test_mw100_recut_decide.py::test_in_watch_mode_card_state_is_allowed_and_listed |
| E37 | watch mode, `verdict-node-unknown` | refused | allowed, listed | tests/core/test_mw100_recut_decide.py::test_in_watch_mode_node_unknown_is_allowed_and_listed |
| E38 | watch mode, `verdict-not-enforced` | refused | allowed, listed | tests/core/test_mw100_recut_decide.py::test_in_watch_mode_not_enforced_is_allowed_and_listed |
| E39 | no mode in the profile, a non-lead caller | n/a | refused as in trip | tests/core/test_mw100_recut_decide.py::test_with_no_mode_the_recut_behaves_as_trip |
| E40 | trip mode, the same fact as E33 (nearest deny of E33) | n/a | refused `verdict-recut-not-lead` | tests/core/test_mw100_recut_decide.py::test_in_trip_mode_the_same_non_lead_is_refused |
| E41 | the recut core's imports | n/a | only pure modules | tests/core/test_mw100_recut_pure.py::test_the_recut_core_imports_only_pure_modules |
| E42 | the recut core's calls | n/a | no input, output or clock | tests/core/test_mw100_recut_pure.py::test_the_recut_core_calls_no_io_function |
| E43 | the lock gate on `verdict recut` | no permit | leaves the by-permit that names the caller | tests/core/test_mw100_recut_pure.py::test_the_lock_gate_leaves_a_by_permit_for_verdict_recut |
| E44 | a node with one earlier run, a new distinct run (nearest allow of E45) | n/a | allowed | tests/core/test_mw100_add_budget.py::test_a_node_with_one_run_takes_a_second_distinct_run |
| E45 | a node with two earlier runs, a third distinct run, at `verdict add` | allowed per card | refused `verdict-runs-exceeded` | tests/core/test_mw100_add_budget.py::test_a_node_with_two_runs_refuses_a_third_as_runs_exceeded |
| E46 | the refusal text of E45 | promised the lead's word and a ledger row | names the node, the runs and `mkway verdict recut` | tests/core/test_mw100_add_budget.py::test_the_runs_exceeded_text_names_the_node_the_runs_and_the_recut_command |
| E47 | case D1: runs on N1, N2, N1 | refused (3 runs per card) | allowed (N1 has 1, N2 has 1) | tests/core/test_mw100_add_budget.py::test_d1_a_run_on_the_first_node_after_a_run_on_the_second_is_allowed |
| E48 | a recut node, no run since the recut, a new run started after it | n/a | allowed: the budget starts again | tests/core/test_mw100_add_budget.py::test_a_node_that_was_recut_starts_with_an_empty_budget |
| E49 | a run already used for the node, at the limit | n/a | allowed, the used run is chosen | tests/core/test_mw100_add_budget.py::test_a_run_used_for_the_node_is_chosen_again_at_the_limit |
| E50 | a recut node, a fresh run that started before the recut | allowed | refused `verdict-run-before-recut` | tests/core/test_mw100_add_budget.py::test_a_fresh_run_that_started_before_the_recut_is_refused_as_run_before_recut |
| E51 | a recut node, a run that started after the recut (nearest allow of E50) | n/a | allowed | tests/core/test_mw100_add_budget.py::test_a_run_that_started_after_the_recut_is_allowed |
| E52 | the refusal text of E50 | none | names the node | tests/core/test_mw100_add_budget.py::test_the_run_before_recut_text_names_the_node |
| E53 | watch mode, `verdict-run-before-recut` | refused | allowed, listed | tests/core/test_mw100_add_budget.py::test_in_watch_mode_run_before_recut_is_allowed_and_listed |
| E54 | trip mode, the same fact as E53 | n/a | refused | tests/core/test_mw100_add_budget.py::test_in_trip_mode_the_same_run_before_recut_is_refused |
| E55 | two nodes, one of them recut, one run common to both started before the recut | allowed | refused `verdict-run-before-recut` | tests/core/test_mw100_add_budget.py::test_a_call_with_two_nodes_needs_a_run_after_the_recut_of_the_recut_node |
| E56 | a node with three reader runs, at `card close` | refused per card | refused `verdict-runs-exceeded` | tests/core/test_mw100_close_decide.py::test_a_third_reader_run_of_a_node_is_refused_as_runs_exceeded_at_close |
| E57 | three nodes with two reader runs each (nearest allow of E56, at the limit) | refused per card | allowed | tests/core/test_mw100_close_decide.py::test_two_reader_runs_of_a_node_are_allowed_at_close |
| E58 | case D1 at close: N1 two runs, N2 and N3 one run each | refused (4 runs per card) | allowed | tests/core/test_mw100_close_decide.py::test_d1_two_nodes_with_two_and_one_run_are_allowed_at_close |
| E59 | the refusal text of E56 | promised the lead's word and a ledger row | names `mkway verdict recut` | tests/core/test_mw100_close_decide.py::test_the_close_runs_exceeded_text_names_the_recut_command |
| E60 | a node whose last row is a recut | no such row | refused `verdict-recut-pending` | tests/core/test_mw100_close_decide.py::test_a_last_row_recut_is_refused_as_recut_pending |
| E61 | a true row dated after the last recut (nearest allow of E60 and E62) | n/a | allowed | tests/core/test_mw100_close_decide.py::test_a_true_row_after_the_recut_is_allowed |
| E62 | a true row older than the node's last recut record | allowed | refused `verdict-recut-pending` | tests/core/test_mw100_close_decide.py::test_a_true_row_older_than_the_recut_is_refused_as_recut_pending |
| E63 | a recut row with no recut record | n/a | refused `verdict-unproven` | tests/core/test_mw100_close_decide.py::test_a_recut_row_with_no_record_is_refused_as_unproven |
| E64 | the refusal text of E60 | none | names the fresh verdict to run | tests/core/test_mw100_close_decide.py::test_the_pending_text_names_the_fresh_verdict_to_run |
| E65 | an old add record with `tests` and no `nodes` | n/a | counts for the nodes of its files only | tests/shell/test_mw100_recut_facts.py::test_an_old_record_with_tests_and_no_nodes_counts_for_the_nodes_of_its_files |
| E66 | an old add record with neither `nodes` nor `tests` | n/a | counts for every node of the card | tests/shell/test_mw100_recut_facts.py::test_an_old_record_with_neither_nodes_nor_tests_counts_for_every_node |
| E67 | an add record with `nodes` | n/a | counts for those nodes only | tests/shell/test_mw100_recut_facts.py::test_a_record_with_nodes_counts_for_those_nodes_only |
| E68 | an add record with no `agent` | n/a | never a run | tests/shell/test_mw100_recut_facts.py::test_a_record_with_no_agent_is_never_a_run |
| E69 | case D2: two reader agents of one session on one node | one run (sessions) | two runs | tests/shell/test_mw100_recut_facts.py::test_d2_two_reader_agents_of_one_session_are_two_runs |
| E70 | runs before and after a recut record | counted together | only the later ones count | tests/shell/test_mw100_recut_facts.py::test_a_recut_record_ends_the_count_of_its_node |
| E71 | a recut record | n/a | never a run | tests/shell/test_mw100_recut_facts.py::test_a_recut_record_is_never_a_run |
| E72 | a commit between the start and the end of the answered run | n/a | not a change | tests/shell/test_mw100_recut_facts.py::test_a_commit_between_the_start_and_the_end_of_the_run_is_not_a_change |
| E73 | a commit after the end of the answered run (nearest allow of E72) | n/a | a change | tests/shell/test_mw100_recut_facts.py::test_a_commit_after_the_end_of_the_run_is_a_change |
| E74 | the answered run's end, read in the session of its add record | n/a | found though the lead's session differs | tests/shell/test_mw100_recut_facts.py::test_the_end_of_the_run_is_read_in_the_session_of_its_add_record |
| E75 | an uncommitted test file | n/a | read as a stale file with both shas | tests/shell/test_mw100_recut_facts.py::test_an_uncommitted_test_file_reads_as_a_stale_file |
| E76 | a commit of the card file alone | n/a | a change | tests/shell/test_mw100_recut_facts.py::test_a_card_file_commit_alone_is_a_change |
| E77 | a reader that started before the recut record, one after it | n/a | only the later one is a run since the recut | tests/shell/test_mw100_recut_facts.py::test_the_readers_that_started_after_the_recut_are_the_only_ones_since_the_recut |
| E78 | an allowed recut | no row | the row, the record and one ledger row | tests/shell/test_mw100_recut_write.py::test_an_allowed_recut_writes_the_row_the_record_and_the_ledger_row |
| E79 | the reason cell | none | `answers <agent id>: <reason>`, no run number | tests/shell/test_mw100_recut_write.py::test_the_row_reason_names_the_answered_agent_and_no_run_number |
| E80 | the record | none | kind `verdict-recut` with node, agent, reason, session, time | tests/shell/test_mw100_recut_write.py::test_the_recut_record_has_kind_verdict_recut_and_its_fields |
| E81 | a refused recut | none | nothing written | tests/shell/test_mw100_recut_write.py::test_a_refused_recut_writes_nothing |
| E82 | a recut with no commit since the run ended, real git | none | refused `verdict-recut-no-change` | tests/shell/test_mw100_recut_write.py::test_a_recut_with_no_change_is_refused_in_process |
| E83 | a commit of the card file only (nearest allow of E82) | none | allowed | tests/shell/test_mw100_recut_write.py::test_a_card_file_commit_alone_allows_the_recut |
| E84 | an uncommitted test file | none | refused `verdict-recut-stale` | tests/shell/test_mw100_recut_write.py::test_an_uncommitted_test_file_is_refused_as_recut_stale |
| E85 | the recut row at close | n/a | proved by its record | tests/shell/test_mw100_recut_write.py::test_the_recut_row_is_proved_at_close_by_its_record |
| E86 | a typed recut row with no record | n/a | `verdict-unproven` | tests/shell/test_mw100_recut_write.py::test_a_typed_recut_row_reads_verdict_unproven_at_close |
| E87 | after a recut, three new runs | n/a | two allowed, the third refused | tests/shell/test_mw100_recut_write.py::test_after_a_recut_two_new_runs_are_allowed_and_a_third_is_refused |
| E88 | a second recut of the node | n/a | refused `verdict-recut-exceeded` | tests/shell/test_mw100_recut_write.py::test_a_second_recut_is_refused_as_exceeded_in_process |
| E89 | the ledger row | none | topic `verdict recut`, by the lead, the quote holds card, node, answered run and reason | tests/shell/test_mw100_recut_write.py::test_the_ledger_row_holds_the_card_the_node_the_run_and_the_reason |
| E90 | the owner's terminal, in process | none | exit 1 `verdict-by-owner` | tests/shell/test_mw100_recut_write.py::test_the_owners_terminal_is_refused_as_by_owner_in_process |
| E91 | a call with no reason | none | usage error | tests/shell/test_mw100_recut_write.py::test_a_call_with_no_reason_is_a_usage_error |
| E92 | watch mode, a last row recut, `card close` | n/a | still refused `verdict-recut-pending` | tests/shell/test_mw100_recut_write.py::test_in_watch_mode_the_recut_pending_close_still_refuses |
| E93 | replay 1: run 1 true, run 2 weak (old records, no `nodes`), no recut | no way out | close says `verdict-weak`, a third run is refused, both texts name `verdict recut` | tests/shell/test_mw100_replay.py::test_replay_one_old_records_count_and_both_refusals_name_the_recut |
| E94 | replay 2: a tests-only commit, the recut, an old run refused, a fresh run `true`, the close | the card never closes | the verdict check passes | tests/shell/test_mw100_replay.py::test_replay_two_the_recut_route_lets_the_verdict_check_pass |
| E95 | the real command, a node with no weak or wrong row | none | non-zero exit, `verdict-recut-nothing` | tests/test_mw100_recut_e2e.py::test_the_real_command_refuses_a_recut_with_nothing_to_answer |
| E96 | the real command, no commit since the run | none | non-zero exit, `verdict-recut-no-change` | tests/test_mw100_recut_e2e.py::test_the_real_command_refuses_a_recut_with_no_change |
| E97 | the real command, an edited and uncommitted test file | none | non-zero exit, `verdict-recut-stale` | tests/test_mw100_recut_e2e.py::test_the_real_command_refuses_a_recut_on_a_stale_file |
| E98 | the real command, a second recut | none | non-zero exit, `verdict-recut-exceeded` | tests/test_mw100_recut_e2e.py::test_the_real_command_refuses_a_second_recut |
| E99 | the real command, a session that did not order the card | none | non-zero exit, `verdict-recut-not-lead` | tests/test_mw100_recut_e2e.py::test_the_real_command_refuses_a_session_that_did_not_order_the_card |
| E100 | the real `card close`, a last row recut | none | non-zero exit, `verdict-recut-pending` | tests/test_mw100_recut_e2e.py::test_the_real_close_refuses_a_last_row_recut |
| E101 | the real `verdict add`, a reader that started before the recut | none | non-zero exit, `verdict-run-before-recut` | tests/test_mw100_recut_e2e.py::test_the_real_command_refuses_a_run_that_started_before_the_recut |
| E102 | the real command, the orderer, a weak row, a changed cut (nearest allow of E95 to E99) | none | exit 0, the row written | tests/test_mw100_recut_e2e.py::test_the_real_command_allows_the_orderers_recut |
| E103 | register row, changelog line, card | none | present, the changelog line last in the top section | tests/test_mw100_docs.py::test_register_changelog_and_card_name_the_card |
| E104 | the module docstrings | none | name every new reason id and the command | tests/test_mw100_docs.py::test_the_module_docstrings_name_every_reason_id |
| E105 | the README paragraph | none | last paragraph of the section of the verdict command paragraph; names the command and every id | tests/test_mw100_docs.py::test_the_readme_paragraph_names_the_command_and_every_id |
| E106 | the command in process, an allowed recut | no command | exit 0, the node and the answered agent printed | tests/shell/test_mw100_recut_branches.py::test_the_command_in_process_prints_the_recut_and_exits_zero |
| E107 | a failed write of the verdict file | none | exit 1, `not written` | tests/shell/test_mw100_recut_branches.py::test_a_write_error_is_reported_as_not_written |
| E108 | a typed weak row that no add record holds | none | no answered run | tests/shell/test_mw100_recut_branches.py::test_a_typed_weak_row_has_no_answered_run |
| E109 | an answered run with no end row in `agents.jsonl` | none | no end, so no change | tests/shell/test_mw100_recut_branches.py::test_an_answered_run_with_no_end_row_reads_no_end_and_no_change |
| E110 | a card that is not in the register | none | `card-unknown` | tests/shell/test_mw100_recut_branches.py::test_a_card_not_in_the_register_is_card_unknown |
| E111 | a registered card with no card file | none | `card-unknown` | tests/shell/test_mw100_recut_branches.py::test_a_card_with_no_card_file_is_card_unknown |
| E112 | watch mode lets a non-lead through | none | the record lists the watched refusal | tests/shell/test_mw100_recut_branches.py::test_a_refusal_watch_mode_let_through_is_named_in_the_record |
| E113 | an older true row restored by hand, `card close` | allowed by date | refused `verdict-recut-pending` | tests/shell/test_mw100_recut_branches.py::test_an_older_true_row_restored_by_hand_is_recut_pending_at_close |
| E114 | a recut record of another node | n/a | the count of this node is unchanged | tests/shell/test_mw100_recut_branches.py::test_a_recut_of_another_node_does_not_touch_the_count |
| E115 | a proof line that is not JSON | n/a | skipped, the records after it count | tests/shell/test_mw100_recut_branches.py::test_a_proof_line_that_is_not_json_is_skipped |

## 8. Log

One line per step. No re-run of a check or an agent round without a new input named in the Log row.

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-13 | start checks, each alone: `pwd` = the worktree, HEAD 4eb074b, `git status --short` = clean | 4eb074b | base of the card |
| 2026-11-13 | acceptance table first, then the tests: E1 to E105 (decision R251b); owner of this run, 13.11: only my own files plus tests/core, tests/test_meta_cards.py and tests/test_register.py, no whole suite (void of the common rule); the recut ids use the existing `tests.verdict_add.mode`, so no new key and no manifest id | none | card written before any test |
| 2026-11-13 | red proof, `python -m pytest -n 4 --dist loadgroup` on the nine new files: 32 failed, 3 passed, 4 collection errors, 180.75 s. The 3 passed were allow rows E57, E58, E61 (they pass on the old code): changed so they fail before the code (E57 and E58 use three nodes, which the per-card count refused; E61 passes the new fact `before_recut`), the card rows E57 and E58 reworded, and the file re-run alone: 9 failed in 0.32 s. The 4 collection errors are red by missing module: `core_verdict_recut` (E1 to E40, 40 ids), and `verdict_recut` through the helper `tests/_mw100.py` (E65 to E77 facts 13 ids, E78 to E92 write 15 ids, E93 and E94 replay 2 ids). The other 35 ids failed for the right reason: E41 and E42 no module, E43 no permit for `recut`, E44 to E55 no `used` and no `since_recut` field, E56 to E64 no per-node `runs` or `before_recut`, E95 to E102 `invalid choice: 'recut'` from the real command, E103 to E105 no row, no docstring, no paragraph. Every one of the 105 new ids fails | the red commit | 105 of 105 red |
| 2026-11-13 | tests-only commits before the green one, decision R251b: 3b1e503 changes the old tests whose expected shape moves with the per-node budget (used runs onto the node, close counts runs per node, the helper record carries `agent`, the add reason set gains `verdict-run-before-recut`); 341c5c9 corrects two of my own tests (the helper gave the card no orderer; replay 2 put the changing commit before the answered run ended); no assertion was weakened | 3b1e503, 341c5c9 | the two replays pass after the fix |
| 2026-11-13 | coverage found ten branches of the new code with no test (`python -m coverage run --branch -m pytest -p no:xdist` on the card tests and the older add and close tests, 270 passed; missed: `verdict_recut.py` lines 65, 75, 99, 103-104, 123, 144, `verdicts.py` the recut-date branch, the recut record of another node and a damaged proof line, `mkway.py` the success print and the write-error return); rows E106 to E115 and their ten tests are added in a tests-only commit before the green commit. They are not red by a missing module (the code exists): each was shown to fail with its branch broken by a throwaway edit (all ten at once, then undone exactly): 10 failed; unbroken: 10 passed in 9.53 s | the commit that carries this line | 10 new ids, red by mutation |
| 2026-11-13 | green for E1 to E115, decision R251b, red commit f48638e, tests-only commits 3b1e503, 341c5c9, ca0d82c: `engine/core_verdict_recut.py` (pure: `Facts`, `Node`, `Verdict`, `decide`), `engine/verdict_recut.py` (the shell: the row, the `verdict-recut` record, the ledger row), the `recut` parser and handler in `engine/mkway.py` (the refusal and watch reporting is shared with `verdict add`), the permit line of `engine/core_lock.py` extended to `recut`, `engine/core_verdict_add.py` and `engine/verdict_add.py` (per node per cut budget, `verdict-run-before-recut`, the record gains `nodes`), `engine/core_verdicts.py` and `engine/verdicts.py` (per node runs from `verdicts.cuts`, `verdict-recut-pending`, the recut row proved by its record, the older true row), both old refusal texts now name `mkway verdict recut`, the README paragraph at the end of the section of the verdict command paragraph and one sentence of that paragraph (the run limit is per node, names `verdict-run-before-recut`), the register row and the changelog line last in the top section. No new key, no manifest id, no allow marker | the commit that carries this line | ordered set (tests/core, test_meta_cards, test_register, this card's files, the older verdict and README tests I touched), `-n 4`: 2291 passed, 1 failed in 198.27 s; the one failure was `tests/test_mw080_docs.py::test_the_readme_paragraph_names_the_command_the_reasons_and_the_modes` (the MW-080 paragraph did not name `verdict-run-before-recut`, which the changed reason set of the tests-only commit 3b1e503 requires); cause removed by editing that README sentence, re-run of the five document tests (test_mw080_docs, test_mw100_docs, test_mw005_readme, test_meta_cards, test_register): 19 passed in 2.66 s |
| 2026-11-13 | coverage, `python -m coverage run --branch -m pytest -p no:xdist` on this card's core and shell tests and the older add and close tests (280 passed in 69.32 s), `coverage report -m` | the commit that carries this line | missed lines in code changed by this card: none. `core_verdict_add.py`, `core_verdict_recut.py`, `verdict_add.py`, `verdict_recut.py` 100 percent with branches; `mkway.py` and `core_lock.py` none missed in the changed hunks. Other missed lines of the touched files are old code of other cards (`core_verdicts.py` 155, 158, 162, 173; `verdicts.py` outside the new functions); the one changed `if` of `verdicts.proof_problems` (line 309) has its false arm covered only by older tests that were not in this run |
| 2026-11-13 | table, Acceptance row -> test node -> red seen -> green: E1 to E40 `tests/core/test_mw100_recut_decide.py` 40 ids yes yes; E41 to E43 `tests/core/test_mw100_recut_pure.py` 3 ids yes yes; E44 to E55 `tests/core/test_mw100_add_budget.py` 12 ids yes yes; E56 to E64 `tests/core/test_mw100_close_decide.py` 9 ids yes yes; E65 to E77 `tests/shell/test_mw100_recut_facts.py` 13 ids yes yes; E78 to E92 `tests/shell/test_mw100_recut_write.py` 15 ids yes yes; E93, E94 `tests/shell/test_mw100_replay.py` 2 ids yes yes; E95 to E102 `tests/test_mw100_recut_e2e.py` 8 ids yes yes; E103 to E105 `tests/test_mw100_docs.py` 3 ids yes yes; E106 to E115 `tests/shell/test_mw100_recut_branches.py` 10 ids red by mutation, green yes | the commit that carries this line | every row names its test node; every id was red before its code (E106 to E115 by mutation) and is green now. Time added per commit: none (no commit gate or hook was changed; the lock gate adds one list comparison on a `verdict` call) |
