# MW-109: fail-closed wiring and the start line

| | |
|---|---|
| **Appetite** | 2 hours — from 2026-11-16 |
| **Status** | proposed |
| **Created / updated** | 2026-11-16 / 2026-11-16 |
| **Waiting for** | nothing |
| **Form** | card |
| **Decisions** | R270, R270a, R270d, R271c, R271c-D1, R268, R216 — ids only, no text copied from the ledger; a commit that changes a test names one |
| **Canon** | none for the fail-closed wiring: the basis is rulings R268 to R271c and the order of the card |
| **Paths** | `engine/core_session.py`, `engine/gate_records.py`, `engine/gate_agents.py`, `engine/gate_outbox.py`, `engine/gate_owner_ask.py`, `engine/dispatch.py`, `engine/manifest.json`, `engine/concept.py`, `tests/test_hooks_fail_closed.py`, `tests/test_concept.py`, `tests/core/test_session_decide.py`, `tests/shell/test_outbox_facts.py`, `tests/shell/test_session_facts.py`, `tests/test_mw004_agents.py`, `README.md`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-109-fail-closed/CARD.md` |

How to use: the form of `cards/_TEMPLATE/CARD.md`. The Acceptance table comes first.

## 1. Goal

«we should have straight, simple as its possible mkway process - it should help work on tasks - not be as evil dog - it should be strong helper!» — owner, 2026-11-16. A hook that fails must not let a call through unseen, and a refusal must name its way out: the failed hook names itself, the error and the repair; a record the engine cannot write refuses with its path; every K1 and K8 refusal this card touches has a test that shows the call passing after the way out.

## Acceptance examples

Each row becomes a test; `card close` needs every row to name one.

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | edit and shell hook entries | onFailure block pinned by no test | each carries onFailure block | tests/test_hooks_fail_closed.py::test_the_entry_of_a_blocking_group_carries_on_failure_block |
| E2 | hook timeouts | no test | timeout of an entry covers its gates, and the shell entry the 780 s budget plus a margin | tests/test_hooks_fail_closed.py::test_the_timeout_of_a_blocking_entry_covers_every_gate_it_runs; tests/test_hooks_fail_closed.py::test_the_shell_entry_leaves_the_commit_tests_budget_and_a_margin |
| E3 | registration and matchers | no test | every gate the manifest turns on has its hook entry; every matcher is a tool name | tests/test_hooks_fail_closed.py::test_every_hook_the_manifest_turns_on_is_registered_in_the_settings_file; tests/test_hooks_fail_closed.py::test_every_matcher_is_a_tool_name_and_no_hook_keys_on_a_word |
| E4 | failed hook refusal | says only that the gate failed | names the hook, the error line and the repair (mkway check, the operator, the owner) | tests/test_hooks_fail_closed.py::test_a_failed_hook_refusal_names_the_hook_the_error_line_and_the_repair; tests/test_hooks_fail_closed.py::test_a_dispatcher_failure_line_names_the_error_and_the_repair |
| E5 | post-record-failed | warn | refuses and names the path; the D1 edit of the pinned tests | tests/core/test_session_decide.py::test_a_record_that_cannot_be_written_is_a_warn_line_and_never_a_refusal; tests/shell/test_session_facts.py::test_a_record_that_cannot_be_written_allows_with_a_warn_row |
| E6 | check-record-failed | warn | refuses and names the path | tests/shell/test_outbox_facts.py::test_a_failed_record_is_a_warn_that_says_the_check_will_read_unproven |
| E7 | agent-record-failed | warn on both events | start refuses, stop is a visible message naming the path | tests/test_mw004_agents.py::test_a_failed_record_never_blocks_and_adds_no_context; tests/shell/test_session_facts.py::test_a_failed_agent_record_is_a_warn_row_and_never_a_block |
| W1 | gate-error way out | no way-out test | the refusal, then the call passes after the way out (`concept.py` row set) | tests/test_hooks_fail_closed.py::test_a_gate_error_way_out |
| W2 | dispatcher-error way out | no way-out test | the refusal, then the call passes after the way out (`concept.py` row set) | tests/test_hooks_fail_closed.py::test_a_dispatcher_error_way_out |
| W3 | profile-invalid way out | no way-out test | the refusal, then the call passes after the way out (`concept.py` row set) | tests/test_hooks_fail_closed.py::test_a_profile_invalid_way_out |
| W4 | post-record-failed way out | no way-out test | the refusal, then the call passes after the way out (`concept.py` row set) | tests/test_hooks_fail_closed.py::test_a_post_record_failed_way_out |
| W5 | agent-record-failed way out | no way-out test | the refusal, then the call passes after the way out (`concept.py` row set) | tests/test_hooks_fail_closed.py::test_an_agent_record_failed_way_out |
| W6 | check-record-failed way out | no way-out test | the refusal, then the call passes after the way out (`concept.py` row set) | tests/test_hooks_fail_closed.py::test_a_check_record_failed_way_out |
| W7 | ask-record-failed way out | no way-out test | the refusal, then the call passes after the way out (`concept.py` row set) | tests/test_hooks_fail_closed.py::test_an_ask_record_failed_way_out |
| W8 | delete-target-unknown way out | no way-out test | the refusal, then the call passes after the way out (`concept.py` row set) | tests/test_hooks_fail_closed.py::test_a_delete_way_out[delete-target-unknown] |
| W9 | delete-wildcard way out | no way-out test | the refusal, then the call passes after the way out (`concept.py` row set) | tests/test_hooks_fail_closed.py::test_a_delete_way_out[delete-wildcard] |
| W10 | delete-sql way out | no way-out test | the refusal, then the call passes after the way out (`concept.py` row set) | tests/test_hooks_fail_closed.py::test_a_delete_way_out[delete-sql] |
| W11 | delete-uncommitted way out | no way-out test | the refusal, then the call passes after the way out (`concept.py` row set) | tests/test_hooks_fail_closed.py::test_a_delete_way_out[delete-uncommitted] |
| W12 | delete-outside-root way out | no way-out test | the refusal, then the call passes after the way out (`concept.py` row set) | tests/test_hooks_fail_closed.py::test_a_delete_way_out[delete-outside-root] |
| W13 | delete-too-large way out | no way-out test | the refusal, then the call passes after the way out (`concept.py` row set) | tests/test_hooks_fail_closed.py::test_a_delete_too_large_way_out |
| W14 | delete-backup-failed way out | no way-out test | the refusal, then the call passes after the way out (`concept.py` row set) | tests/test_hooks_fail_closed.py::test_a_delete_backup_failed_way_out |
| W15 | lock-closed-edit way out | no way-out test | the refusal, then the call passes after the way out (`concept.py` row set) | tests/test_hooks_fail_closed.py::test_a_closed_lock_way_out[lock-closed-edit] |
| W16 | lock-closed-shell way out | no way-out test | the refusal, then the call passes after the way out (`concept.py` row set) | tests/test_hooks_fail_closed.py::test_a_closed_lock_way_out[lock-closed-shell] |
| W17 | lock-closed-commit way out | no way-out test | the refusal, then the call passes after the way out (`concept.py` row set) | tests/test_hooks_fail_closed.py::test_a_closed_lock_way_out[lock-closed-commit] |
| W18 | lock-file-by-session way out | no way-out test | the refusal, then the call passes after the way out (`concept.py` row set) | tests/test_hooks_fail_closed.py::test_a_lock_file_by_session_way_out |
| W19 | built-dirty way out | no way-out test | the refusal, then the call passes after the way out (`concept.py` row set) | tests/test_hooks_fail_closed.py::test_a_built_dirty_way_out |
| W20 | built-untested way out | no way-out test | the refusal, then the call passes after the way out (`concept.py` row set) | tests/test_hooks_fail_closed.py::test_a_built_untested_way_out |
| W21 | profile-outside-root way out | no way-out test | the refusal, then the call passes after the way out (`concept.py` row set) | tests/test_hooks_fail_closed.py::test_an_install_input_way_out[profile-outside-root] |
| W22 | bundle-outside-root way out | no way-out test | the refusal, then the call passes after the way out (`concept.py` row set) | tests/test_hooks_fail_closed.py::test_an_install_input_way_out[bundle-outside-root] |
| W23 | copy-without-lock way out | no way-out test | the refusal, then the call passes after the way out (`concept.py` row set) | tests/test_hooks_fail_closed.py::test_an_install_input_way_out[copy-without-lock] |
| W24 | heredoc anchors | no way-out test | the refusal, then the call passes after the way out (`concept.py` row set) | tests/test_hooks_fail_closed.py::test_the_delete_anchors_are_command_names_only |

## 8. Log

One line per step. No re-run of a check or an agent round without a new input named in the Log row.

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-16 | hooks docs quoted before writing (code.claude.com hooks page, read by an agent) | none | verbatim: «`onFailure` ... Whether the action that triggered the hook goes ahead when the hook fails: `"continue"` or `"block"`», needs Claude Code 2.1.295 or later; «Seconds before canceling.» timeout, default 600 for a command hook. NOT verbatim, a page summary only, because the section «Block the action when a hook fails» was not readable as text: a timed-out or crashing command hook does not block the call unless its entry carries onFailure block, exit 2 blocks. No difference from the requirements |
| 2026-11-16 | decision row R271c-D1 quoted | none | «Card MW-109 may change these HEAD tests in one tests-only commit that cites R271c-D1 in its message, and in no other way»: test_session_decide.py 544-548, test_outbox_facts.py 173-182, test_session_facts.py 553-586, test_mw004_agents.py 161, and the manifest on_failure_reason texts; warn becomes refuse, never weaker |
| 2026-11-16 | red tests, the D1 edits and tests/test_hooks_fail_closed.py | 46d11a6 | 17 ids red and the collection error of test_session_decide.py: 7 failed-hook text ids, 4 record-failed way-out rows, delete-outside-root, and the 5 edited D1 tests; 33 new ids pass at once by design: they pin what is built (onFailure block, timeouts, matchers, registration, the K1 and K8 way-outs, the heredoc anchors) |
| 2026-11-16 | tests-only fix of my own row: the way out of post-record-failed repeats the command, the nonce of the failed call is used | 1becdd2 | the row asserted the old call again after the repair and failed; now a new `card new` is run, then the row passes |
| 2026-11-16 | tests-only fix of my D1 edit: the four edited tests keep their original function names | ad6493e | the case maps of the cards MW-004, MW-065 and MW-066 name them (test_meta_cards red on 2 ids); D1 changes bodies, not names, and those cards are not mine; the names now read «warn» while the bodies assert the refusal |
| 2026-11-16 | heredoc rows of R270d: the engine already allows the word delete and rm in a heredoc body and a quoted string, and judges rm as a command | none | 4 pin rows green at once, no change in engine/core_delete.py; the refusal of the live session (DD-013) comes from the owner's user-level hook, not from this repository (confirmed by retro-oper10) |
| 2026-11-16 | green: record-failed refusals with the path, failed-hook text with the repair, visible SubagentStop message, manifest texts, 23 rows of concept.py, README, CHANGELOG, REGISTER | the commit of this row | the 4 record-failed ids refuse (agent-record-failed on SubagentStart only), gate-error and dispatcher-error name the hook, the error line and `mkway check`; GAPS_ALLOWED 179 to 156, literal ceiling 156; gaps by card 2: 30, 3: 17, 4: 7, 5: 14, 6: 11, 7: 40, 8: 37; way-out rows added 23 (7 delete, 3 lock, lock-file-by-session, 4 record, profile-invalid, 2 built, 3 install, gate-error, dispatcher-error); delete-outside-root is red until card 2 merges (it asserts card 2's text, R270c) and then goes green after the rebase |
