# MW-137: the lead that ordered an open card re-records its Paths

| | |
|---|---|
| **Appetite** | 1 day - from 2026-11-17 |
| **Status** | proposed |
| **Created / updated** | 2026-11-17 / 2026-11-17 |
| **Waiting for** | us |
| **Form** | card |
| **Decisions** | R352 A and R353: the order of 2026-11-17 |
| **Canon** | none for the re-record: the basis is the order of 2026-11-17 |
| **Paths** | `engine/cardtool.py`, `engine/leads.py`, `engine/messages.py`, `engine/core_lock.py`, `engine/gate_lock.py`, `engine/mkway.py`, `engine/core_session.py`, `engine/gate_subtask.py`, `engine/board.py`, `engine/scorecard.py`, `engine/concept.py`, `tests/test_mw137_lead_paths.py`, `tests/core/test_mw137_lock_core.py`, `README.md`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-137-lead-paths/CARD.md` |

## 1. Goal

«It should work automatically. Without me» and «I want that you fix All of them» — owner, 2026-11-17.

Paths are recorded once, at the first open from `proposed`. When a decision legitimately widens a card's work, nobody but the owner's register edit and `card resync` could change them. The lead role that ordered an open card now re-records them with `mkway card paths <id> --add <entry> ... --remove <entry> ...`, with the same checks as the first open, and never the card's holder. The lead's intent is in the call: the engine records only when the card file's Paths equal the recorded set plus and minus the named entries.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | widen | only the owner's register edit changes the Paths | the lead's `--add` records the set, and the later edit of the new file passes | tests/test_mw137_lead_paths.py::test_a_lead_widens_the_paths_and_the_later_edit_of_the_new_file_passes |
| E2 | narrow | the same | `--remove` is the same move; the dropped file is refused | tests/test_mw137_lead_paths.py::test_a_lead_narrows_the_paths_with_the_same_command |
| E3 | the holder | not applicable | a holder, also when it is a lead, is refused `paths-by-holder` | tests/test_mw137_lead_paths.py::test_the_holder_cannot_change_the_paths_of_its_own_card_also_when_it_is_a_lead |
| E4 | a session that is no lead | not applicable | refused `paths-not-lead`, nothing recorded | tests/test_mw137_lead_paths.py::test_a_session_that_is_no_lead_is_refused |
| E5 | a card the owner ordered | not applicable | refused `paths-not-orderer`; the Paths stay the owner's | tests/test_mw137_lead_paths.py::test_a_card_ordered_by_the_owner_stays_the_owners |
| E6 | a card an earlier lead session ordered | not applicable | refused `paths-not-orderer` for the current lead (R356: the card's `Ordered by` is the caller's own session); the owner's `give` is the way out and is run | tests/test_mw137_lead_paths.py::test_a_card_ordered_by_an_earlier_lead_session_is_refused_for_the_current_lead |
| E7 | a too-wide entry | not applicable | refused `card-paths-too-wide` by the check of the first open | tests/test_mw137_lead_paths.py::test_a_too_wide_entry_is_refused_by_the_shared_check |
| E8 | the record row | none | one row: card, old set, new set, who, time | tests/test_mw137_lead_paths.py::test_the_record_row_names_card_old_set_new_set_who_and_time |
| E9 | the holder's notice | none | one `notice` to the holder; nobody else is written to | tests/test_mw137_lead_paths.py::test_the_holder_gets_one_notice_and_nobody_else_is_pinged |
| E10 | no holder | not applicable | the row is written, no notice | tests/test_mw137_lead_paths.py::test_with_no_holder_the_row_is_written_and_no_notice_is_sent |
| E11 | the owner's view | none | `mkway board` shows a line for the re-recorded card | tests/test_mw137_lead_paths.py::test_the_owner_view_shows_a_line_for_a_re_recorded_card |
| E12 | the scorecard | none | a count of re-records per card | tests/test_mw137_lead_paths.py::test_the_scorecard_counts_the_re_records_of_each_card |
| E13 | the holder wrote the file too | not applicable | the file holds an entry the call does not name: refused `paths-file-differs`, difference printed, nothing recorded | tests/test_mw137_lead_paths.py::test_the_holder_adds_an_entry_to_the_file_and_the_lead_names_another_refused_with_the_difference |
| E14 | the call before the file edit | not applicable | refused `paths-file-differs`, naming the missing entry | tests/test_mw137_lead_paths.py::test_the_call_before_the_holder_edited_the_file_is_refused_naming_the_missing_entry |
| E15 | the holder's own `waiting` | not applicable | allowed | tests/test_mw137_lead_paths.py::test_the_holders_own_waiting_is_allowed |
| E16 | the owner's pause | not applicable | refused `paths-card-state` | tests/test_mw137_lead_paths.py::test_the_pause_the_owner_set_is_refused |
| E17 | `cards.approver: owner-only` | not applicable | a lead is refused `owner-only-command`; the owner's terminal runs it | tests/test_mw137_lead_paths.py::test_under_the_owner_only_approver_a_lead_is_refused_and_the_owner_runs_it |
| E18 | a session id with no permit | not applicable | refused `paths-no-permit`; the plain call through the hook passes | tests/test_mw137_lead_paths.py::test_the_way_out_of_paths_no_permit_is_the_plain_call_through_the_hook |
| E19 | way out of `paths-not-lead` | not applicable | the owner's terminal passes | tests/test_mw137_lead_paths.py::test_the_way_out_of_paths_not_lead_is_the_owner_terminal |
| E20 | way out of `paths-not-orderer` | not applicable | the register edit and `card resync` change the Paths (run) | tests/test_mw137_lead_paths.py::test_the_way_out_of_paths_not_orderer_is_the_register_edit_and_card_resync |
| E21 | way out of `paths-by-holder` | not applicable | the orderer's call passes | tests/test_mw137_lead_paths.py::test_the_way_out_of_paths_by_holder_is_the_orderer_call |
| E22 | way out of `paths-card-state` | not applicable | `card open` (the lead for a proposed card, the owner for a closed card or the owner's pause), then the call passes | tests/test_mw137_lead_paths.py::test_the_way_out_of_paths_card_state |
| E23 | way out of `paths-file-differs` | not applicable | the file made to match, then the same call passes | tests/test_mw137_lead_paths.py::test_the_way_out_of_paths_file_differs_is_the_file_made_to_match |
| E24 | `paths-record-failed` | not applicable | a row that cannot be written stops the re-record; a writable state folder and a repeat pass | tests/test_mw137_lead_paths.py::test_the_way_out_of_paths_record_failed_is_a_writable_state_folder |
| E25 | the `card-paths-changed` text | names the restore and the new card (MW-136) | also names `card paths <id> --add <entry>`, and that command runs | tests/test_mw137_lead_paths.py::test_the_way_out_of_card_paths_changed_names_the_lead_re_record_and_it_runs |
| E26 | the lock gate, no problem | not applicable | `card paths` leaves the one-use permit of kind `paths` for the card | tests/core/test_mw137_lock_core.py::test_a_card_paths_call_the_card_tool_accepts_leaves_the_card_bound_permit |
| E27 | the lock gate, a problem | not applicable | refused with the card tool's reason and text, no permit | tests/core/test_mw137_lock_core.py::test_a_card_paths_call_the_card_tool_refuses_is_refused_with_its_reason_and_text |
| E28 | the permit that cannot be written | not applicable | refused `paths-no-permit` with its way | tests/core/test_mw137_lock_core.py::test_the_permit_that_cannot_be_written_refuses_with_a_way_that_names_the_plain_call_and_the_owner |
| E29 | an approver that is not the orderer | not applicable | the owner's command | tests/core/test_mw137_lock_core.py::test_under_an_approver_that_is_not_the_orderer_card_paths_is_the_owners_command |
| E30 | a card not in the register | not applicable | left to the command (`card-unknown`) | tests/core/test_mw137_lock_core.py::test_a_card_that_is_not_in_the_register_is_left_to_the_command_to_name |
| E31 | a card ordered by a session that never was a lead | not applicable | refused `paths-not-orderer` | tests/test_mw137_lead_paths.py::test_a_card_ordered_by_a_session_that_never_was_a_lead_is_refused |
| E32 | the Paths check | not applicable | the command calls `cardtool.recorded_paths`, not a copy | tests/test_mw137_lead_paths.py::test_the_command_judges_the_paths_with_cardtool_recorded_paths_not_a_copy |
| E33 | every entry removed | not applicable | refused `card-paths-too-wide`: an empty Paths is no file rule | tests/test_mw137_lead_paths.py::test_removing_every_entry_is_refused_because_an_empty_set_is_no_file_rule |
| E34 | the card tool judges again | not applicable | a permit left for a session that is no lead is refused `paths-not-lead` | tests/test_mw137_lead_paths.py::test_the_card_tool_judges_again_with_the_session_the_permit_names |
| E35 | a call that names no entry | not applicable | changes nothing | tests/test_mw137_lead_paths.py::test_a_call_that_names_no_entry_changes_nothing |
| E36 | the planned change of lead | not applicable | before the hand-off another lead is refused `paths-not-orderer` naming `give` and `lead accept`; after `give` and `lead accept` the new lead re-records (the way out is run) | tests/test_mw137_lead_paths.py::test_the_way_out_of_paths_not_orderer_for_another_leads_card_is_the_hand_off |
| E37 | the commit gate's `file-not-in-card` text | says to ask the owner to `card open <id>` again, which records no Paths | the sentence is gone; the text names the lead's `card paths` | tests/test_mw137_commit_way_out.py::test_the_commit_refusal_no_longer_sends_the_owner_to_a_reopen |
| E38 | the way out of that refusal | a re-open that changes nothing | the lead that ordered the card runs the named `card paths <id> --add <entry>`, then the same commit passes (real hook) | tests/test_mw137_commit_way_out.py::test_the_way_out_of_the_commit_refusal_is_the_leads_card_paths_and_the_same_commit_passes |
| E39 | the edit gate's `file-not-in-card` text | says to ask the owner to `card open <id>` again (pinned by two HEAD tests, changed under MW137-D1) | names the lead's `card paths <id> --add <entry>`; the lead adds the entry, then the same edit passes | tests/test_mw137_lead_paths.py::test_the_way_out_of_file_not_in_card_of_the_edit_gate_is_the_leads_card_paths_and_the_same_edit_passes |

## 8. Log

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-17 | red tests | c1d40b5 | the two test files alone: 37 red, 1 green (E30, an allow that holds today) |
| 2026-11-17 | test labels | ac2254e | tests/test_mw137_lead_paths.py: docstring labels E5b, E7b, E7c, E18b renamed E31 to E34 and E1, E2, E35 added so the rows match one to one; no assertion changed |
| 2026-11-17 | code | ac2254e | engine/cardtool.py (`card paths`, `paths_problem`, `rerecord_paths`, the shared wide-entry check), engine/leads.py (the lead registry is unchanged; `was_lead` was added and then removed by R356), engine/messages.py (the paths notice), engine/core_lock.py and engine/gate_lock.py (the permit), engine/mkway.py, engine/core_session.py (text), engine/board.py, engine/scorecard.py, engine/concept.py, README.md; own files, tests/core and the card tests: see the commit message |
| 2026-11-17 | R356 red tests | 6027434 | the term a of the order changed (the card's `Ordered by` is the caller's own session; no reading of the role): E6 rewritten (refused, the owner's give is the way out) and E36 added (the hand-off); 2 red, 32 green |
| 2026-11-17 | R356 code | this commit | `was_lead` removed; `cardtool.paths_problem` checks lead, holder, then `Ordered by` equals the caller, then the state; the refusal texts name the hand-off (`give`, `lead accept`) or the owner's give; own file, test_mw137_lock_core and tests/core: see the commit message |
| 2026-11-17 | R358 3 red tests | 2500834 | tests/test_mw137_commit_way_out.py alone, through the real hook: E37 and E38 fail on the old text of the commit gate |
| 2026-11-17 | R358 3 code | this commit | engine/core.py: the `file-not-in-card` text of the commit gate names `card paths <id> --add <entry>` instead of the re-open; the rest of the text is kept; the same sentence in engine/core_session.py (the edit gate, line 205) is not in this order and is unchanged; own files and tests/core: see the commit message |
| 2026-11-17 | MW137-D1 tests | 939b345 | tests only, under decision row MW137-D1: tests/core/test_mw107_ways_out_core.py and tests/core/test_session_decide.py change only the lines that pin the edit gate's `file-not-in-card` sentence; E39 added; 3 red on the old text |
| 2026-11-17 | MW137-D1 code | this commit | engine/core_session.py: the edit gate's `file-not-in-card` text names `card paths <id> --add <entry>` instead of the re-open; own files and tests/core: see the commit message |
