# MW-080: A verdict row is written only by the engine command

| | |
|---|---|
| **Appetite** | 2.5 hours — from 2026-11-12 |
| **Status** | proposed |
| **Created / updated** | 2026-11-12 / 2026-11-12 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | R194, R196, R196a |
| **Canon** | none: the basis is a real first close under R181 that no session could finish, and rulings R194, R196, R196a |
| **Paths** | `engine/mkway.py`, `engine/core_verdict_add.py`, `engine/verdict_add.py`, `engine/core_lock.py`, `engine/verdicts.py`, `engine/gate_outbox.py`, `engine/proof.py`, `engine/profiles.py`, `engine/manifest.json`, `engine/profile.schema.json`, `engine/KEYS.md`, `tests/`, `README.md`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-068-test-verdicts/case_map.md`, `cards/MW-080-verdict-add/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository. `VERSION` is not changed here. The decision is a pure core (`engine/core_verdict_add.py`: `Facts`, `Verdict`,
`decide`, no input or output); the shell (`engine/verdict_add.py`) reads the facts (register, records, git, `agents.jsonl`,
the proof file, the commit records) and writes the table rows and the record. The command ids are documented in the module
docstring and the README like the close ids; only `verdict-file-by-command` is a manifest reason (entry `outbox_check.pre`).
Not edited here: `engine/dispatch.py`, `engine/gate_message.py`, `engine/leads.py`, `engine/messages.py`,
`engine/core_install.py`, `engine/startline.py`, `engine/gate_commit_tests.py`, `engine/core_shape.py`,
`engine/gate_test_shape.py` (other cards own them).

## 1. Goal

«The only writer is `mkway verdict add <card> <node> <true|weak|wrong> <reason>`: by = the caller (MW-049), the proof link =
the reader run recorded by MW-071, refused inside the command when the caller is the card's holder or a committer of the
test file (R173), allowed only while the card is waiting or released. Several nodes per call are fine (repeat the node
argument); no Write-tool path exists for tests/verdicts at all, and the subtask and lead.edit gates stay as they are.» —
ruling R194, 2026-11-12.

Addition, ruling R196: the proof is read from git, never from the file's mtime: the checker run must start after the last
commit that touched the test file, and the file must equal HEAD at the time of the call, else `verdict-stale` names the two
shas. Independence rests on the data shape (only the command writes proof rows), never on a gate mode. Addition, ruling
R196a: a profile with no `tests.verdict_add.mode` behaves as `trip`.

## Acceptance examples

Each row becomes a test; `card close` needs every row to name one. E1 to E38 are the pure core table, E39 to E41 are the
purity of the core and the lock gate's head, E42 to E50 read real git and real files, E51 to E65 write the table and the
record on real files, E66 to E76 run the command in process, E77 to E88 run the real command and the real hooks, E89 to
E94 are the documents, E95 to E99 are the profile and card facts the shell reads (added with the tests, see the Log), E100
to E104 are the branches the coverage run found untested (added after the code, see the Log).

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | a waiting card, one fresh reader run, a caller who never took the card | no command | allowed | tests/core/test_verdict_add_decide.py::test_a_waiting_card_with_one_fresh_run_is_allowed |
| E2 | the same run a second call (nearest allow of E4) | no command | allowed | tests/core/test_verdict_add_decide.py::test_the_same_run_a_second_time_is_allowed |
| E3 | a second distinct run (nearest allow of E4) | no command | allowed | tests/core/test_verdict_add_decide.py::test_a_second_distinct_run_is_allowed |
| E4 | a third distinct run | allowed | refused `verdict-runs-exceeded` | tests/core/test_verdict_add_decide.py::test_a_third_distinct_run_is_refused_as_runs_exceeded |
| E5 | the refusal text of E4 | none | names the two earlier runs | tests/core/test_verdict_add_decide.py::test_the_runs_exceeded_text_names_the_two_earlier_runs |
| E6 | two runs used, one of them fresh again, one new fresh run | n/a | the used run is chosen: allowed | tests/core/test_verdict_add_decide.py::test_a_run_already_used_is_chosen_before_a_new_one |
| E7 | an open card with no holder (a released card) | no command | allowed | tests/core/test_verdict_add_decide.py::test_an_open_card_with_no_holder_is_allowed |
| E8 | an open card with a holder | allowed | refused `verdict-card-state` | tests/core/test_verdict_add_decide.py::test_an_open_card_with_a_holder_is_refused_as_card_state |
| E9 | a `waiting-owner` card | allowed | refused `verdict-card-state` | tests/core/test_verdict_add_decide.py::test_a_waiting_owner_card_is_refused_as_card_state |
| E10 | a closed card | allowed | refused `verdict-card-state` | tests/core/test_verdict_add_decide.py::test_a_closed_card_is_refused_as_card_state |
| E11 | a proposed card | allowed | refused `verdict-card-state` | tests/core/test_verdict_add_decide.py::test_a_proposed_card_is_refused_as_card_state |
| E12 | the refusal text of E8 | none | names the status | tests/core/test_verdict_add_decide.py::test_the_card_state_text_names_the_status |
| E13 | a caller that held the card once and released it | allowed | refused `verdict-by-holder` | tests/core/test_verdict_add_decide.py::test_a_former_holder_after_release_is_refused_as_by_holder |
| E14 | the caller is the holder now | allowed | refused `verdict-by-holder` | tests/core/test_verdict_add_decide.py::test_the_current_holder_is_refused_as_by_holder |
| E15 | the caller committed the test file | allowed | refused `verdict-by-committer` | tests/core/test_verdict_add_decide.py::test_a_committer_of_the_test_file_is_refused_as_by_committer |
| E16 | the caller committed another file only (nearest allow of E15) | n/a | allowed | tests/core/test_verdict_add_decide.py::test_a_committer_of_another_file_is_allowed |
| E17 | the owner's terminal | allowed | refused `verdict-by-owner` | tests/core/test_verdict_add_decide.py::test_the_owners_terminal_is_refused_as_by_owner |
| E18 | a session with no permit (no caller) | allowed | refused `verdict-no-caller` | tests/core/test_verdict_add_decide.py::test_a_call_with_no_caller_is_refused_as_no_caller |
| E19 | a node the card's Acceptance rows do not name | allowed | refused `verdict-node-unknown` | tests/core/test_verdict_add_decide.py::test_a_node_the_card_does_not_name_is_refused_as_node_unknown |
| E20 | the test file differs from HEAD | allowed | refused `verdict-stale` | tests/core/test_verdict_add_decide.py::test_a_test_file_that_differs_from_head_is_refused_as_stale |
| E21 | the refusal text of E20 | none | names both shas | tests/core/test_verdict_add_decide.py::test_the_stale_text_names_both_blob_shas |
| E22 | a test file with no commit | allowed | refused `verdict-stale` | tests/core/test_verdict_add_decide.py::test_an_uncommitted_test_file_is_refused_as_stale |
| E23 | the reader run began before the last commit of the test file | allowed | refused `verdict-stale` | tests/core/test_verdict_add_decide.py::test_a_run_that_started_before_the_last_commit_is_refused_as_stale |
| E24 | the refusal text of E23 | none | names the last commit | tests/core/test_verdict_add_decide.py::test_the_stale_run_text_names_the_last_commit |
| E25 | no checker run in the caller's session | allowed | refused `verdict-no-reader-run` | tests/core/test_verdict_add_decide.py::test_a_session_with_no_checker_run_is_refused_as_no_reader_run |
| E26 | two nodes, each with a fresh run, no run fresh for both | allowed | refused `verdict-stale` | tests/core/test_verdict_add_decide.py::test_two_nodes_with_no_common_fresh_run_are_refused_as_stale |
| E27 | two nodes with one common fresh run (nearest allow of E26) | n/a | allowed | tests/core/test_verdict_add_decide.py::test_two_nodes_with_one_common_fresh_run_are_allowed |
| E28 | a profile with no `outbox.checkers` | allowed | refused `verdict-not-enforced` naming `outbox.checkers` | tests/core/test_verdict_add_decide.py::test_a_profile_with_no_checkers_is_refused_as_not_enforced_naming_the_key |
| E29 | a profile with `cards.verdicts` off | allowed | refused `verdict-not-enforced` naming `cards.verdicts` | tests/core/test_verdict_add_decide.py::test_a_profile_with_verdicts_off_is_refused_as_not_enforced_naming_the_key |
| E30 | watch mode, no reader run | refused | allowed, the reason listed as watched | tests/core/test_verdict_add_decide.py::test_in_watch_mode_a_missing_reader_run_is_allowed_and_listed |
| E31 | trip mode, the same fact as E30 (nearest deny of E30) | n/a | refused `verdict-no-reader-run` | tests/core/test_verdict_add_decide.py::test_in_trip_mode_the_same_missing_reader_run_is_refused |
| E32 | no mode in the profile, the same fact (ruling R196a) | n/a | refused as in trip | tests/core/test_verdict_add_decide.py::test_with_no_mode_in_the_profile_the_command_behaves_as_trip |
| E33 | watch mode, a card state refusal | refused | allowed, listed | tests/core/test_verdict_add_decide.py::test_in_watch_mode_a_card_state_refusal_is_allowed_and_listed |
| E34 | watch mode, `verdict-by-holder` | refused | still refused | tests/core/test_verdict_add_decide.py::test_in_watch_mode_by_holder_is_still_refused |
| E35 | watch mode, `verdict-by-committer` | refused | still refused | tests/core/test_verdict_add_decide.py::test_in_watch_mode_by_committer_is_still_refused |
| E36 | watch mode, `verdict-by-owner` | refused | still refused | tests/core/test_verdict_add_decide.py::test_in_watch_mode_by_owner_is_still_refused |
| E37 | watch mode, `verdict-stale` | refused | still refused | tests/core/test_verdict_add_decide.py::test_in_watch_mode_stale_is_still_refused |
| E38 | watch mode, `verdict-no-caller` (no `by` can be written) | refused | still refused | tests/core/test_verdict_add_decide.py::test_in_watch_mode_no_caller_is_still_refused |
| E39 | the core's imports | n/a | only pure modules | tests/core/test_verdict_add_is_pure.py::test_the_verdict_add_core_imports_only_pure_modules |
| E40 | the core's calls | n/a | no input, output or clock | tests/core/test_verdict_add_is_pure.py::test_the_verdict_add_core_calls_no_io_function |
| E41 | the lock gate on `verdict add` | no permit | leaves the by-permit that names the caller | tests/core/test_verdict_add_lock_head.py::test_the_lock_gate_leaves_a_by_permit_for_verdict_add |
| E42 | a committed test file, real git | none | last commit sha, equal blobs | tests/shell/test_verdict_add_facts.py::test_the_last_commit_of_the_test_file_and_its_blobs_are_read_from_git |
| E43 | the file edited after the commit | none | the file blob differs from HEAD's | tests/shell/test_verdict_add_facts.py::test_an_edited_test_file_reads_a_file_blob_that_differs_from_head |
| E44 | an untracked test file | none | no commit | tests/shell/test_verdict_add_facts.py::test_an_untracked_test_file_reads_no_commit |
| E45 | a checker end row that started after the last commit | none | fresh | tests/shell/test_verdict_add_facts.py::test_a_checker_run_that_started_after_the_last_commit_is_fresh |
| E46 | a checker end row that started before it | none | read, not fresh | tests/shell/test_verdict_add_facts.py::test_a_checker_run_that_started_before_the_last_commit_is_not_fresh |
| E47 | end rows of another session or another agent type | none | no reader | tests/shell/test_verdict_add_facts.py::test_a_run_of_another_session_or_another_agent_type_is_no_reader |
| E48 | commit records of the test file | none | the sessions, matched by tree sha | tests/shell/test_verdict_add_facts.py::test_the_committers_come_from_the_commit_records_by_tree |
| E49 | a take and a release of the card | none | the session is a holder ever | tests/shell/test_verdict_add_facts.py::test_every_session_that_ever_took_the_card_is_a_holder_ever |
| E50 | a proof record naming an agent run | none | the run is used for the card | tests/shell/test_verdict_add_facts.py::test_a_run_recorded_for_the_card_is_a_used_run |
| E51 | an allowed call | no row | the row in the table, a record with the row key | tests/shell/test_verdict_add_write.py::test_an_allowed_call_writes_the_row_and_the_record |
| E52 | the record | none | agent, run number, test file blob | tests/shell/test_verdict_add_write.py::test_the_record_holds_the_agent_run_number_and_the_test_blob |
| E53 | a second call with the same run | none | run 1 again, the first row kept | tests/shell/test_verdict_add_write.py::test_a_second_call_with_the_same_run_keeps_run_one |
| E54 | a refused call | none | nothing written | tests/shell/test_verdict_add_write.py::test_a_refused_call_writes_nothing |
| E55 | the same node again | one row | the row replaced | tests/shell/test_verdict_add_write.py::test_the_row_of_the_same_node_is_replaced |
| E56 | another node | one row | both rows | tests/shell/test_verdict_add_write.py::test_a_row_of_another_node_is_kept_and_a_new_node_is_appended |
| E57 | a new file | none | the header the reader skips | tests/shell/test_verdict_add_write.py::test_a_new_verdict_file_gets_the_header_the_reader_skips |
| E58 | a reason with a pipe character and a newline | none | a slash and a space | tests/shell/test_verdict_add_write.py::test_a_pipe_and_a_newline_in_a_reason_are_replaced |
| E59 | the run number | none | in the record, never in the table | tests/shell/test_verdict_add_write.py::test_the_run_number_is_in_the_record_and_never_in_the_table |
| E60 | a row the command wrote, close check | n/a | proven | tests/shell/test_verdict_add_write.py::test_a_row_written_by_the_command_is_proven_at_close |
| E61 | a row changed by hand after the command wrote it (nearest deny of E60) | n/a | `verdict-unproven` | tests/shell/test_verdict_add_write.py::test_a_typed_row_reads_verdict_unproven_at_close |
| E62 | node A recorded, node B typed | n/a | B unproven, A proven | tests/shell/test_verdict_add_write.py::test_node_a_recorded_and_node_b_typed_leaves_b_unproven |
| E63 | the post step of a Write of a verdict file | a proof row | no proof row | tests/shell/test_verdict_add_write.py::test_a_post_step_write_of_a_verdict_file_leaves_no_proof_row |
| E64 | a row typed with the Write tool, close check | proven | `verdict-unproven` | tests/shell/test_verdict_add_write.py::test_a_row_typed_with_the_write_tool_reads_verdict_unproven_at_close |
| E65 | the pre step on a Write of a verdict file, and on another test file (nearest allow) | allowed | refused `verdict-file-by-command`; the other allowed | tests/shell/test_verdict_add_write.py::test_the_pre_step_refuses_a_write_of_a_verdict_file; tests/shell/test_verdict_add_write.py::test_the_pre_step_allows_a_write_of_another_test_file |
| E66 | the owner's terminal, in process | no command | exit 1, `verdict-by-owner` | tests/shell/test_verdict_add_cli.py::test_the_owners_terminal_is_refused_as_by_owner |
| E67 | a session with no permit | no command | exit 1, `verdict-no-caller` | tests/shell/test_verdict_add_cli.py::test_a_session_with_no_permit_is_refused_as_no_caller |
| E68 | a card not in the register | no command | exit 1, `card-unknown` | tests/shell/test_verdict_add_cli.py::test_an_unknown_card_is_refused |
| E69 | a call with no reason | no command | usage error | tests/shell/test_verdict_add_cli.py::test_a_call_with_no_reason_is_a_usage_error |
| E70 | a word that is none of true, weak, wrong | no command | usage error | tests/shell/test_verdict_add_cli.py::test_a_word_that_is_none_of_true_weak_wrong_is_a_usage_error |
| E71 | an allowed call | no command | exit 0, the rows and the run printed | tests/shell/test_verdict_add_cli.py::test_an_allowed_call_prints_the_rows_and_exits_zero |
| E72 | the node argument repeated | no command | one row per node | tests/shell/test_verdict_add_cli.py::test_several_nodes_in_one_call_write_one_row_each |
| E73 | watch mode, a watched refusal | refused | row written, would-refuse row in the refusal log | tests/shell/test_verdict_add_cli.py::test_in_watch_mode_a_watched_refusal_is_logged_and_the_row_is_written |
| E74 | no mode in the profile (ruling R196a), the same call | n/a | refused as in trip | tests/shell/test_verdict_add_cli.py::test_a_profile_with_no_mode_refuses_the_same_call |
| E75 | a bare card number | no command | takes the profile's card prefix | tests/shell/test_verdict_add_cli.py::test_a_bare_card_number_takes_the_card_prefix |
| E76 | a refusal | none | a refusal row with the reason id in the refusal log | tests/shell/test_verdict_add_cli.py::test_a_refusal_leaves_a_row_in_the_refusal_log |
| E77 | the real command, a former holder | no command | non-zero exit, `verdict-by-holder` | tests/test_mw080_command_e2e.py::test_the_real_command_refuses_a_former_holder |
| E78 | the real command, no reader run | no command | non-zero exit, `verdict-no-reader-run` | tests/test_mw080_command_e2e.py::test_the_real_command_refuses_a_session_with_no_reader_run |
| E79 | the real command, a run that began before the last commit | no command | non-zero exit, `verdict-stale` | tests/test_mw080_command_e2e.py::test_the_real_command_refuses_a_reader_run_that_began_before_the_last_commit |
| E80 | the real command, a fresh run (nearest allow of E77 to E79) | no command | exit 0, the row written | tests/test_mw080_command_e2e.py::test_the_real_command_allows_a_fresh_reader_run_and_writes_the_row |
| E81 | the real command in the owner's terminal | no command | non-zero exit, `verdict-by-owner` | tests/test_mw080_command_e2e.py::test_the_real_command_refuses_the_owners_terminal |
| E82 | the real PreToolUse hook, Write of a verdict file | allowed | deny `verdict-file-by-command` | tests/test_mw080_command_e2e.py::test_the_real_hook_refuses_a_write_of_a_verdict_file |
| E83 | the real PreToolUse hook, Edit | allowed | deny `verdict-file-by-command` | tests/test_mw080_command_e2e.py::test_the_real_hook_refuses_an_edit_of_a_verdict_file |
| E84 | the real PreToolUse hook, MultiEdit | allowed | deny `verdict-file-by-command` | tests/test_mw080_command_e2e.py::test_the_real_hook_refuses_a_multiedit_of_a_verdict_file |
| E85 | the real PreToolUse hook, Write of another test file (nearest allow) | n/a | allowed | tests/test_mw080_command_e2e.py::test_the_real_hook_allows_a_write_of_another_test_file |
| E86 | a row typed through the real Write and post hooks, then the real close | proven | refused `verdict-unproven` | tests/test_mw080_command_e2e.py::test_a_row_typed_through_the_real_write_hooks_is_unproven_at_the_close |
| E87 | replay: a session that is neither holder nor committer, one fresh reader run, two calls (two nodes true, one weak) | no session could write | both calls allowed; the real close reports the weak node | tests/test_mw080_command_e2e.py::test_the_first_real_close_shape_two_calls_then_the_close_reports_the_weak_node |
| E88 | the gate list: every declared PreToolUse reason has a real-hook row | no row for `verdict-file-by-command` | a row in the real-hook table | tests/test_e2e_gates.py::test_every_declared_reason_has_a_row_or_a_stated_exemption |
| E89 | register row, changelog line, card | none | present, the changelog line last in `## 0.2.7` | tests/test_mw080_docs.py::test_register_changelog_and_card_name_the_card |
| E90 | the schema and KEYS.md | no key | `tests.verdict_add.mode` is `trip` or `watch`, last in `tests`, a KEYS row | tests/test_mw080_docs.py::test_the_schema_and_keys_name_the_verdict_add_mode |
| E91 | the defaults | n/a | the key is not in `defaults.json` | tests/test_mw080_docs.py::test_the_defaults_do_not_hold_the_key |
| E92 | the manifest | one reason id | `outbox_check.pre` declares `verdict-file-by-command` too | tests/test_mw080_docs.py::test_the_manifest_declares_the_verdict_file_refusal |
| E93 | the module docstring | none | names every command reason id | tests/test_mw080_docs.py::test_the_module_docstring_names_every_reason_id |
| E94 | the README paragraph | none | after the blind verdict paragraph, names the command, every reason id, both modes and the refusals that hold in both | tests/test_mw080_docs.py::test_the_readme_paragraph_names_the_command_the_reasons_and_the_modes |
| E95 | a profile with no `outbox.checkers` | none | the facts say checkers missing | tests/shell/test_verdict_add_facts.py::test_a_profile_with_no_checkers_reads_checkers_missing |
| E96 | a profile with `cards.verdicts` off | none | the facts say verdicts off | tests/shell/test_verdict_add_facts.py::test_a_profile_with_verdicts_off_reads_verdicts_off |
| E97 | `tests.verdict_add.mode` watch, and no key | none | `watch`, and empty | tests/shell/test_verdict_add_facts.py::test_the_mode_of_the_profile_is_read_and_a_missing_key_reads_empty |
| E98 | the register status and the card's Acceptance nodes | none | the status, and per node whether the card names it | tests/shell/test_verdict_add_facts.py::test_the_card_status_and_the_nodes_the_card_names_are_read |
| E99 | the owner flag and an empty caller | none | as the command passes them | tests/shell/test_verdict_add_facts.py::test_the_facts_hold_the_caller_and_the_owner_flag_as_given |
| E100 | a checker end row with no readable start time | none | left out of the node's readers | tests/shell/test_verdict_add_facts.py::test_an_end_row_with_no_readable_time_is_left_out |
| E101 | a git that cannot run | none | no commit and no blobs are read | tests/shell/test_verdict_add_facts.py::test_a_git_that_cannot_run_reads_no_commit_and_no_blobs |
| E102 | a card whose register folder holds no card file | none | `card-unknown` | tests/shell/test_verdict_add_facts.py::test_a_card_whose_card_file_is_missing_is_unknown |
| E103 | a verdict file that is not UTF-8 text | none | exit 1 `not written`, the file unchanged | tests/shell/test_verdict_add_cli.py::test_a_verdict_file_that_is_not_utf8_is_refused_and_left_alone |
| E104 | the pre step when the path cannot be read (nearest deny: E65) | none | allowed | tests/shell/test_verdict_add_write.py::test_a_pre_step_that_cannot_read_the_path_allows_the_write |

## 8. Log

One line per step. No re-run of a check or an agent round without a new input named in the Log row.

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-12 | start checks, each alone: `pwd` = the worktree, HEAD 8cc1d84, `git status --short` = clean | 8cc1d84 | base of the card |
| 2026-11-12 | red: the card with rows E1 to E99, the tests (core table, purity, lock head, facts on real git, table and record writes, in-process command, real command and real hooks, documents), the new refusal row in the real-hook table, the changed expectations of three older tests (key list, outbox pre reason ids, outbox README reason set), decision: R196. The register row and the changelog line ship with the green commit, so row E89 is red now. Rows E95 to E99 were added while writing the tests (they read the profile and the card into the facts); E61 reads a row changed by hand after the command wrote it | e027ce6 | `python -m pytest` on the new files and the changed ones: 64 failed, 4 passed (the 4 are older tests of the same three files), 1 collection error (tests/core/test_verdict_add_decide.py: no module core_verdict_add, so its 38 ids are red by missing module); tests/test_e2e_gates.py: 2 failed (the new row and the meta test). Every one of the 99 new ids fails: 38 by missing module core_verdict_add, 61 for the right reason (no module verdict_add, no command, no mode key, no manifest id, the post step still records a verdict write). No new id passed; a nearest-allow row is a pair that also needs the new refusal |
| 2026-11-12 | migration, tests only (decision R196 item 5): the Write path no longer records a verdict write, so the shared proof helper `tests/_mw068.py` and the records e2e write the command's record directly, and the test of the old post step record is dropped (named in `cards/MW-068-test-verdicts/case_map.md`) | fec4afc | the 56 tests that use the helper pass before and after |
| 2026-11-13 | the engine code was written and the branch coverage run (`python -m coverage run --branch --source=engine`) listed branches of the new code with no test; rows E100 to E104 and their five tests are added in a tests-only commit before the green commit. They are not red by a missing module (the code already exists in the work tree): each was shown to fail with its branch broken (the start-time check of `proof.reader_ends`, the `except` of `verdict_add._git`, of the card file read and of the non-UTF-8 verdict file, and of `gate_outbox._pre`): 5 failed, 0 passed; unbroken: 46 passed in the three files. The term scan flagged an address-like author in the new test helper (`tests/_mw080.py` lines 37 and 38, group B #11); the author is now `mkway-test` as in the other helpers | the commit that carries this line | 5 new ids, red by mutation, green on the code |
| 2026-11-13 | green for E1 to E104, decisions R194, R196, R196a, red commit e027ce6, migration fec4afc, extra tests 97d0987: `engine/core_verdict_add.py` (pure: `Facts`, `Verdict`, `decide`), `engine/verdict_add.py` (the shell: facts from the register, records, git, `agents.jsonl`, the proof file; the table rows and the record), `verdict add` in `engine/mkway.py`, the `verdict` head of the by-permit in `engine/core_lock.py`, the refusal `verdict-file-by-command` in the pre step of `engine/gate_outbox.py` (the post step records no verdict write; `verdicts.record_write` is removed), `proof.reader_ends` (the one read of the checker runs), `profiles.verdict_add_mode`, the manifest id, the schema key `tests.verdict_add.mode` last in `tests`, the KEYS row, the README paragraphs (after the blind verdict paragraph, and one line in «Tests before a commit», which the older test E20 of MW-005 requires for every `tests` key), the register row and the changelog line (last in `## 0.2.7`). Two points beyond the rulings: `verdict-no-caller` (no by-permit, so no `by` can be written) is refused in both modes like the other independence refusals; the record also holds `tests` (the blob of each test file) and `agent` and `run`. No allow marker (`term-scan: allow`) is used by this card | the commit that carries this line | whole suite once: 3517 passed, 3 failed, 4 deselected in 1071.66 s (0:17:51). The 3 failures: `tests/test_install.py::test_fixed_set_is_nda_clean` and `tests/test_repo_scan.py` (two hits in `tests/_mw080.py`, fixed in 97d0987) and `tests/test_mw005_readme.py::test_the_section_states_the_rules_the_keys_and_every_reason` (no `tests.verdict_add` in its section, fixed in the README); re-run alone after the fix, the 6 files (install, mw005 readme, repo scan, mw080 docs, mw019 readme, facts) give 31 passed and 1 failed: `tests/test_repo_scan.py` still reports one hit, `cards/MW-077-perf-rest/CARD.md:42 group B #11`, a tracked file this card does not touch, so it is not caused here and is left for its own card; no second whole-suite run (order of the owner) |
| 2026-11-13 | coverage, `python -m coverage run --branch --source=engine -m pytest` on the new core, shell and records tests (103 passed), `coverage report -m` | the commit that carries this line | `core_verdict_add.py` 100 percent (28 branches), `verdict_add.py` 100 percent (20 branches), missed lines in code changed by this card: none (the handler `_verdict` in `mkway.py`, the lock head, the pre step, `reader_ends`, `verdict_add_mode` are all hit); the other missed lines of the touched files belong to other cards and other test files. Time added per commit: the new pre check on a call that is not a write is 0.27 microseconds (200000 calls timed); a Write or Edit adds one path normalisation and one name test; the lock gate adds one string comparison; no git call and no file read is added to a commit or to any hook other than `mkway verdict add` itself |
| 2026-11-13 | table, Acceptance row -> test node -> red seen -> green: E1 to E38 `tests/core/test_verdict_add_decide.py` 38 ids yes yes; E39, E40 `tests/core/test_verdict_add_is_pure.py` 2 ids yes yes; E41 `tests/core/test_verdict_add_lock_head.py` 1 id yes yes; E42 to E50, E95 to E99 and E100 to E102 `tests/shell/test_verdict_add_facts.py` (14 ids red by e027ce6, E100 to E102 red by mutation) yes yes; E51 to E65 `tests/shell/test_verdict_add_write.py` 16 ids yes yes, E104 same file red by mutation yes yes; E66 to E76 `tests/shell/test_verdict_add_cli.py` 11 ids yes yes, E103 same file red by mutation yes yes; E77 to E87 `tests/test_mw080_command_e2e.py` 11 ids yes yes; E88 `tests/test_e2e_gates.py::test_every_declared_reason_has_a_row_or_a_stated_exemption` yes yes; E89 to E94 `tests/test_mw080_docs.py` 6 ids yes yes | the commit that carries this line | every row names its test node in the Acceptance table above; every id was red before its code (E100 to E104 by mutation) and is green now |
