# MW-128: a refusal that ends a turn is delivered to the orderer by the Stop hook itself: an inbox record and one block, no model in the loop

| | |
|---|---|
| **Appetite** | 1 day — from 2026-11-16 |
| **Status** | proposed |
| **Created / updated** | 2026-11-16 / 2026-11-16 |
| **Waiting for** | us |
| **Form** | card |
| **Decisions** | R301, R301a, MW128-D1 (amended) — ids only, no text copied from the ledger; a commit that changes a test names one |
| **Canon** | none for the refusal delivery: the basis is rulings R301 and R301a and the order of 2026-11-16 |
| **Paths** | `engine/dispatch.py`, `engine/messages.py`, `engine/gatemode.py`, `engine/concept.py`, `engine/owners.py`, `engine/startline.py`, `engine/core_refusal.py`, `tests/core/test_mw128_refusal_core.py`, `tests/shell/test_mw128_refusal_shell.py`, `tests/test_mw128_refusal_e2e.py`, `tests/test_mw012_class.py`, `cards/MW-128-refusal-delivery/CARD.md`, `cards/REGISTER.md`, `CHANGELOG.md` |

## 1. Goal

«The Stop hook, when the session's last engine call in the turn was refused and no send followed, WRITES the refusal into the orderer's inbox as a record itself (no model in the loop) and blocks ONCE with the exact ping line «mkway inbox <id>», never twice (stop_hook_active)» — chief, R301 (a'), 2026-11-16. A builder that stops after a refusal and never runs `mkway send` leaves its orderer with an idle session and no word; the engine now reports it.

## Acceptance examples

Each row becomes a test; `card close` needs every row to name one.

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | last engine call of the turn refused, no call or send after it, orderer known, id not delivered, not continued | the stop passes in silence | deliver: one inbox record, then one block | tests/core/test_mw128_refusal_core.py::test_a_turn_ending_refusal_with_an_orderer_is_delivered_and_blocks_once |
| E2 | the same facts with stop_hook_active true | not decided | the record is written and recorded, no block | tests/core/test_mw128_refusal_core.py::test_a_continued_stop_delivers_but_never_blocks |
| E3 | condition (a): no call, a last call allowed, a call after the refusal, a refused call with no row id | not decided | allow silently | tests/core/test_mw128_refusal_core.py::test_condition_a_fails_so_the_stop_is_allowed_silently |
| E4 | condition (b): a send of the session at or after the refusal | not decided | allow silently | tests/core/test_mw128_refusal_core.py::test_condition_b_fails_when_a_send_followed_the_refusal |
| E5 | a send before the refusal | not decided | does not hide the refusal: deliver | tests/core/test_mw128_refusal_core.py::test_a_send_before_the_refusal_does_not_count_as_the_send_of_it |
| E6 | condition (e): the gate refusal row id is already delivered | not decided | allow silently, with or without stop_hook_active | tests/core/test_mw128_refusal_core.py::test_condition_e_fails_for_an_id_that_is_already_delivered |
| E7 | no orderer (no card, or an empty column) with (a), (b), (e) true | not decided | one record row, no block | tests/core/test_mw128_refusal_core.py::test_condition_c_fails_with_no_orderer_so_one_record_row_and_no_block |
| E8 | the inbox write fails | not decided | the stop is allowed, the id is not recorded as delivered, an error is raised for the shell | tests/core/test_mw128_refusal_core.py::test_a_failed_inbox_write_allows_the_stop_and_is_not_recorded_as_delivered |
| E9 | the reason text of the one block | none | the binding text with the exact ping line `mkway inbox <id>` | tests/core/test_mw128_refusal_core.py::test_the_block_reason_is_the_binding_text_with_the_exact_ping_line |
| E10 | the owner table | no row for the delivered-refusal record | one engine row, `inbox-refusal` | tests/core/test_mw128_refusal_core.py::test_the_owner_table_has_an_engine_row_for_the_refusal_delivery_record |
| E11 | the turn of a session | not recorded | the calls of this session at or after its previous Stop or UserPromptSubmit timing row | tests/shell/test_mw128_refusal_shell.py::test_the_turn_holds_the_calls_of_this_session_after_its_previous_stop |
| E12 | the orderer | not read | the register's orderer column of the card this session holds; the owner or an empty cell is none | tests/shell/test_mw128_refusal_shell.py::test_the_orderer_is_the_orderer_column_of_the_card_the_session_holds |
| E13 | a refused call in the calls log | time, gate, verdict, duration | also session, event, tool, call, and on a refuse row id, target (the refusal log's cut, 200 characters), refusal line, reason id | tests/shell/test_mw128_refusal_shell.py::test_a_refused_call_leaves_a_gate_refusal_row_with_its_session_call_command_and_text |
| E14 | the hook's own inbox write | would count as a send | a record of event `refusal-delivery`, no send | tests/shell/test_mw128_refusal_shell.py::test_a_send_of_this_session_is_found_and_the_hooks_own_record_is_not_a_send |
| E15 | a failed inbox write | silent | a calls-log error row, a screen line, a start-line notice of this session only | tests/shell/test_mw128_refusal_shell.py::test_a_failed_inbox_write_is_a_notice_on_the_start_line_of_this_session_only |
| E16 | no orderer, several stops | not decided | one record row per gate refusal row id | tests/shell/test_mw128_refusal_shell.py::test_the_no_orderer_row_is_written_once_per_gate_refusal_row_id |
| E17 | a refused call, then a stop, through the real hooks | the orderer's inbox stays empty | the inbox holds the record; the hook prints exactly the block JSON with the binding reason | tests/test_mw128_refusal_e2e.py::test_a_turn_ending_refusal_is_delivered_to_the_orderer_and_the_stop_blocks_once_with_the_binding_text |
| E18 | a second stop with stop_hook_active true | not decided | allows, no second record | tests/test_mw128_refusal_e2e.py::test_a_second_stop_on_the_same_refusal_with_stop_hook_active_true_allows_and_writes_nothing |
| E19 | the target of a refuse row | not written | the command head cut to 200 characters, newlines written as backslash n (MW-061) | tests/shell/test_mw128_refusal_shell.py::test_the_target_of_a_refusal_row_is_the_command_head_cut_to_200_characters_with_newlines_as_backslash_n |
| E20 | a refuse row of a gate in watch mode | not told from an enforced refusal | carries `watching`: true, only then; its key set is the refuse set plus `watching` | tests/shell/test_mw128_refusal_shell.py::test_the_watching_key_is_on_the_refuse_row_of_a_gate_in_watch_mode_and_nowhere_else |
| E21 | the key sets of the calls-log rows (decision MW128-D1) | four keys on every row | exact sets per verdict: a plain row has eight keys, a refuse row twelve; a row stays under 200 characters | tests/test_mw012_class.py::test_the_calls_log_gets_one_row_per_gate_per_call |
| E22 | a send at the same time as the refusal | counted as after it | not after: only a strictly later send counts | tests/core/test_mw128_refusal_core.py::test_a_send_at_the_same_time_as_the_refusal_is_not_after_it |
| E23 | the same-time send, rows written in either order | not tested | the refusal is delivered in both orders | tests/shell/test_mw128_refusal_shell.py::test_a_send_with_the_same_time_as_the_refusal_is_not_after_it_in_either_log_order |
| E24 | a real `mkway send` after the refusal | not wired | no record, no block | tests/shell/test_mw128_refusal_shell.py::test_a_real_send_after_the_refusal_means_no_record_and_no_block |
| E25 | the same, through the real hooks | not wired | no record, no block | tests/test_mw128_refusal_e2e.py::test_a_real_send_after_the_refusal_means_no_record_and_no_block |
| E26 | a failed write, then two more stops | no retry | the next stop retries once and blocks once; a third stop writes nothing | tests/shell/test_mw128_refusal_shell.py::test_the_next_stop_retries_a_failed_write_once_and_a_third_stop_writes_nothing |
| E27 | a write that failed twice | not decided | not tried a third time (never a loop) | tests/shell/test_mw128_refusal_shell.py::test_a_write_that_failed_twice_is_not_retried_a_third_time |
| E28 | the refusal line and command in the record | checked by prefix | equal to the gate refusal row's message and target | tests/shell/test_mw128_refusal_shell.py::test_the_refusal_line_and_the_command_in_the_record_equal_the_gate_refusal_row |
| E29 | the same, through the real hooks | checked by substring | equal to the gate refusal row's message and target | tests/test_mw128_refusal_e2e.py::test_the_orderers_inbox_record_holds_the_refusal_line_of_the_gate_refusal_row_exactly |
| E30 | which send the hook reads | only a count | the id and time of the real send; the hook's own record is event refusal-delivery | tests/shell/test_mw128_refusal_shell.py::test_a_send_of_this_session_is_found_and_the_hooks_own_record_is_not_a_send |
| E31 | the owner row of the orderer's inbox file | names `mkway send` only | names the Stop hook too | tests/core/test_mw128_refusal_core.py::test_the_orderers_inbox_file_is_owned_by_the_engine_and_names_the_stop_hook_as_a_writer |

## 8. Log

One line per step. No re-run of a check or an agent round without a new input named in the Log row.

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-16 | start: step 0 (folder mkway-t140, branch t140, base 441f2d3, clean) | 441f2d3 | order read: task order, common order, v2.1 common part, R301, R301a, the research file |
| 2026-11-16 | tests-only commit, red: core, shell and e2e files; run -n 2 of the three files | c0d6750 | 33 failed, 5 passed (the nearest-allow rows), 1 error (core_refusal missing) |
| 2026-11-16 | the run found two HEAD pins in tests/test_mw012_class.py (line 48 the key set, line 53 the row size); asked, decision row MW128-D1 amended: exact key sets per verdict, size under 200, target on the refusal log's rule, watching only on a refuse row of a gate whose watch marker was present | c0d6750 | stop and ask, answered |
| 2026-11-16 | tests-only commit under MW128-D1: lines 48 and 53 changed, lines 47 and 49 to 52 byte-for-byte; two new shell rows (target cut, watching) | 3c864f0 | red at the base engine for line 48, the target row and the watching row |
| 2026-11-16 | implementation choices (the order's list): the session holds a card = `records.session_card` read through `messages._held_in`, orderer = the register cell (`register.ORDERED`), the owner or an empty cell = no orderer; the hook's own inbox write is a message-record row of event `refusal-delivery`, a `send` is event `send`; delivered ids in `<state>/refusal-delivered.jsonl` (`gatemode.mark_delivered`); the error row is written by `gatemode.append_call` with verdict error and reason `refusal-delivery-failed`; the inbox record is a `notice` through `messages.send_refusal`; new core module `engine/core_refusal.py` | 3c864f0 | no new file outside the Files list except the core module the order allows |
| 2026-11-16 | boundary row of the «turn»: the engine's timing log `timing-YYYY-MM-DD.jsonl` (one row per dispatcher run): the latest row of this session with event UserPromptSubmit, or event Stop of group stop; no row = the whole log tail. Reason ids: refusal-delivered, refusal-no-orderer, refusal-delivery-failed (record rows 7 in concept.py, way-out tests named there); GAPS_ALLOWED unchanged at 55. Not covered: an `error` row with applied refuse (gate-error) is no gate refusal row, so it is not delivered | 3c864f0 | noted for the readers |
| 2026-11-16 | code commit: core_refusal, dispatch Stop step, gatemode readers and writer, messages send_refusal and readers, owner row, concept rows, start-line notice, card, register, changelog; run -n 2 of tests/core, test_meta_cards, test_register, test_repo_scan, test_concept, my three files and every test file that imports dispatch, messages, gatemode, concept, owners, startline, with MKWAY_SESSION_ID unset | 4956946 | 4226 passed, 1 xfailed (old), 0 failed, 296 s; term scan inside test_repo_scan passed; GAPS_ALLOWED stays 55, the ceiling line of test_concept untouched |
| 2026-11-16 | blind reader 2 round: tests-only commit in my own new files, no HEAD test, no decision row; red: 5 failed (same-time send in core and shell, retry once, inbox owner row text); the real-send, exact-line and which-send rows passed already | c831a15 | red |
| 2026-11-16 | rows changed with a reason: the core row `a-send-at-the-refusal-time` (it allowed) is replaced by `a-send-one-millisecond-after-the-refusal` plus the row E22, because «after» is strictly later: the two logs are separate files, so there is no log order across them and a send of the same millisecond must never hide a refusal; the code compared with >=, now > | c831a15 | row E22, E23 |
| 2026-11-16 | found while writing the retry row: after a failed write the next Stop opens a later turn, so the refusal is outside the turn and the id could never be retried. Fix: `gatemode.retry_candidate` finds the refusal again from the error row (reason refusal-delivery-failed) when the turn offers none; once only (a refusal with two failed writes is not tried again); the facts then go through the same decide | 6d1640f | E26, E27 |
| 2026-11-16 | IMPLEMENTATION CHOICES, added: an orderer cell that names the owner counts as no orderer, as an empty cell does (the order says: no card, or the column empty): an owner-ordered card has no session inbox to write to, a write would only fail as a dead letter; test tests/shell/test_mw128_refusal_shell.py::test_a_card_ordered_by_the_owner_has_no_orderer, with the no-orderer row test_the_way_out_of_refusal_no_orderer_is_one_record_row_and_no_block | c0d6750 | owner = none |
| 2026-11-16 | item 7, which owner row covers the orderer's inbox file: the row `inbox` (role engine, pattern `<state>/inbox`) already owns `inbox/<session>.jsonl`, the file the record is written into; its command text named `mkway send` only and now names the Stop hook's refusal record too (test E31). The row `inbox-refusal` owns the delivered-id file `refusal-delivered.jsonl`, a different file | 6d1640f | E31 |
| 2026-11-16 | code commit of the reader round and its run: -n 2, no coverage, MKWAY_SESSION_ID unset (env -u): tests/core, the three card files, test_meta_cards, test_register, test_concept, test_mw107_owner_meta, test_mw107_owner_shell, test_repo_scan | 6d1640f | 3153 passed, 0 failed, 56 s; the 78 tests of the three card files all pass |
