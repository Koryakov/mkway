# MW-075: A Stop warning never wakes the session again

| | |
|---|---|
| **Appetite** | 1 hour — from 2026-11-12 |
| **Status** | proposed |
| **Created / updated** | 2026-11-12 / 2026-11-12 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | none yet: a defect fix asked by the architect, 2026-11-12 |
| **Canon** | none: the basis is a live defect, a lead re-invoked after every Stop |
| **Paths** | `engine/dispatch.py`, `tests/`, `README.md`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-075-stop-warn-never-wakes/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand. `VERSION` is not changed. No new refusal, so no
`tests.<gate>.mode` switch. The fix is in `engine/dispatch.py` (`render`, and the warn append that reads the once-store).
`SubagentStop` has no gate in the manifest, so it is not handled here.

## 1. Goal

A warning must not cost a turn. Real case (a dedup install, engine 8fc6a2e, 2026-11-12): the lead's Stop gate warned
`[mkway outbox_check.stop verdict-not-enforced] blind verdict not enforced: outbox.checkers missing in profile`; the warn
went out as `additionalContext`, and Claude Code re-invoked the lead after every stop, six empty turns in a row. On Stop a
warn is a `systemMessage` (shown to the user, does not continue); a refuse keeps `decision: block` + `reason`; the same
Stop warn text is shown at most once per session; its record row is still written; every other event is unchanged.

## Acceptance examples

Rows E1 to E3 are the pure render table, E4 to E7 run the real dispatcher and state folder, E8 and E9 run the real hook
command; E10 to E12 are guards of unchanged output and pass before the fix (the task asks for them).

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | Stop, one warn | `additionalContext` (wakes the session) | `{"systemMessage": text}` only | tests/core/test_stop_warn_render.py::test_a_stop_warn_is_a_system_message_and_nothing_else |
| E2 | Stop, two warns | both in `additionalContext` | one `systemMessage`, joined by a newline | tests/core/test_stop_warn_render.py::test_two_stop_warns_are_one_system_message_in_order |
| E3 | Stop, refuse and a warn | block + reason + `additionalContext` | block + reason + `systemMessage`, no `hookSpecificOutput` | tests/core/test_stop_warn_render.py::test_a_stop_refuse_keeps_the_block_and_the_reason_and_shows_the_warn_to_the_user_only |
| E4 | first Stop of a lead, key missing | `additionalContext` | `systemMessage` only, exit 0, no block | tests/shell/test_stop_warn_once.py::test_the_first_stop_warning_is_a_system_message_with_no_context_and_no_block |
| E5 | second Stop, same session, same text | printed again | nothing on stdout | tests/shell/test_stop_warn_once.py::test_the_second_stop_of_the_same_session_prints_nothing |
| E6 | second Stop, same session | a record row | a record row, and nothing printed | tests/shell/test_stop_warn_once.py::test_the_record_row_is_written_at_every_stop_even_when_nothing_is_printed |
| E7 | Stop of another lead session (nearest allow of E5) | warned | warned | tests/shell/test_stop_warn_once.py::test_another_session_is_warned_again |
| E8 | the real hook command, Stop payload, no `outbox.checkers` | `additionalContext` | exit 0, `{"systemMessage": line}`, no context, no decision | tests/test_stop_warn_e2e.py::test_the_real_stop_hook_shows_the_warning_to_the_user_and_does_not_continue |
| E9 | replay: six Stops in a row of the dedup lead | six outputs | one `systemMessage`, five empty | tests/test_stop_warn_e2e.py::test_six_stops_in_a_row_print_the_line_once |
| E10 | PreToolUse warn | `additionalContext` | unchanged | tests/core/test_stop_warn_render.py::test_a_warn_on_another_event_is_still_additional_context[PreToolUse] |
| E11 | PostToolUse warn | `additionalContext` | unchanged | tests/core/test_stop_warn_render.py::test_a_warn_on_another_event_is_still_additional_context[PostToolUse] |
| E12 | Stop with nothing to say (nearest allow of E1) | nothing | nothing | tests/core/test_stop_warn_render.py::test_a_stop_with_no_refuse_and_no_warn_prints_nothing |

## 8. Log

One line per step. No re-run of a check or an agent round without a new input named in the Log row.

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-12 | Hooks doc read (https://code.claude.com/docs/en/hooks.md, Stop and SubagentStop). The fetch gave a model summary, not verbatim text, so these lines are paraphrase-grade and the wording is to be checked against the live page. Stop: «`decision: "block"` prevents Claude from stopping», `reason` «tells Claude why it should continue»; `hookSpecificOutput.additionalContext` on Stop: «The conversation continues so Claude can act on it»; exit 2 on Stop «continues the conversation»; `systemMessage`: «Warning message shown to the user»; `continue: false` stops processing. The page does not say `systemMessage` continues a Stop. | | Continue: `decision: block`, exit 2, `additionalContext`. Show only: `systemMessage`. |
| 2026-11-12 | Red tests, tests only (E1 to E12) | see the red commit | Red run: 9 failed (E1 to E9), 4 passed (E10 to E12 guards, by design). Failing ids: the three `test_a_stop_*` and `test_two_stop_warns_*` in `tests/core/test_stop_warn_render.py`; the four in `tests/shell/test_stop_warn_once.py`; the two in `tests/test_stop_warn_e2e.py`. |
| 2026-11-12 | First full suite after the fix: 3397 passed, 1 failed in 976 s: `tests/test_dispatch.py::test_outer_handler_catches_each_crash[Stop-stop]`, an E10 row of an older card that expected a Stop warn in `additionalContext`. The row was wrong for this card's rule, so its helper now reads a Stop warn from `systemMessage` (the warn text is still asserted). | fb8ba2a | Tests-only commit. Decision id for the changed test: not established, asked of the operator. |
| 2026-11-12 | Green: `engine/dispatch.py` (`render` on Stop; the once-store on a Stop warn, the record row written before it), README paragraph | see the green commit | Related tests (tests/core, test_meta_cards, test_dispatch, the Stop and outbox gate tests, README and manifest tests, the three new files): 1803 passed in 28.8 s. Per the owner's word the whole suite was not re-run after the test fix; the one full run before it shows no other failure. |
| 2026-11-12 | Coverage: `python -m coverage run --branch -m pytest` on the new files and test_dispatch.py, report on `engine/dispatch.py` | | The changed lines (the Stop branch of `render`, the once check) and both arms are not in the missed list; the missed lines are older code. |
| 2026-11-12 | Table «Acceptance row -> test node -> red seen -> green» | | E1 to E9: red seen yes, green yes. E10 to E12 are guards: red seen no (they pass before the fix, by design), green yes. SubagentStop has no gate, so no row. «Until the cause changes»: the once key is the tagged text, so a changed text shows again; no separate row. |
