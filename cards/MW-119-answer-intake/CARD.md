# MW-119: ask answered runs only in the lead, and its record is the lead's

| | |
|---|---|
| **Appetite** | 3 hours — from 2026-11-16 |
| **Status** | proposed |
| **Created / updated** | 2026-11-16 / 2026-11-16 |
| **Waiting for** | us |
| **Form** | card |
| **Decisions** | R272, R287, R243, R263, MW119-D1 — ids only, no text copied from the ledger; a commit that changes a test names one |
| **Canon** | none for the ask answer: the basis is rulings R272 G5 and R287 and the order of the operator |
| **Paths** | `engine/asks.py`, `engine/core_ask.py`, `engine/mkway.py`, `engine/concept.py`, `tests/_mw119.py`, `tests/test_mw119_answer_intake.py`, `tests/test_mw014_commands.py`, `tests/test_mw015_ledger_by.py`, `README.md`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-119-answer-intake/CARD.md` |

## 1. Goal

«we should have straight, simple as its possible mkway process - it should help work on tasks - not be as evil dog - it should be strong helper!» — owner, 2026-11-16 (R263). Ruling R272 G5: `mkway ask answered` writes the owner's words, so it runs only in the intake role, the lead, and any other session is refused with the way out (the lead records it). Help it gives the task: the owner's word in the ledger is the lead's typed record, visible and attributable, never a worker's own claim that frees its own ask. Named limit (R287): the lead types the quote and the engine does not compare it with the owner's message (no transcript checks, R243). The board line is not in this card: it comes after card MW-112 merges.

## Acceptance examples

Each row becomes a test; `card close` needs every row to name one.

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | `ask answered` by a session that is not a lead | recorded, ask freed | refused `ask-answered-not-lead`, the text names the lead; ask open, no ledger row, no record | tests/test_mw119_answer_intake.py::test_a_session_that_is_not_the_lead_is_refused_with_the_way_out |
| E2 | `ask answered` with no session id (no permit) | recorded | refused `ask-answered-not-lead` | tests/test_mw119_answer_intake.py::test_a_session_with_no_permit_is_refused |
| E3 | the lead's call | row by owner | row `by` is `session:<lead id>`, source starts with `owner`, the verbatim quote, never `by` owner | tests/test_mw119_answer_intake.py::test_the_lead_records_session_and_never_the_owner |
| E4 | the ask is freed | by any session | only by the lead's record (a refused call leaves it open) | tests/test_mw119_answer_intake.py::test_the_ask_is_freed_only_by_the_leads_record |
| E5 | the record the board lists | none | one `ask-answered` row: ask, session, `source` owner, quote, time | tests/test_mw119_answer_intake.py::test_the_record_row_has_session_source_quote_and_time |
| E6 | the pure decision | none | refuse for a non-lead with the way out, allow for the lead | tests/test_mw119_answer_intake.py::test_the_decision_names_the_way_out_for_a_non_lead |
| E7 | way out of the new refusal | none | the lead runs the same command and it is allowed | tests/test_mw119_answer_intake.py::test_the_way_out_of_ask_answered_not_lead_is_the_lead_who_records_it |
| E10 | the owner's terminal (R287b) | by owner | still allowed, `by` owner | tests/test_mw119_answer_intake.py::test_the_owner_terminal_may_answer_with_by_owner |
| E8 | the old commands test, session parts (MW119-D1) | any session | the registered lead; a non-lead refused | tests/test_mw014_commands.py::test_the_ask_commands_are_not_owner_only |
| E9 | the old ledger-by test (MW119-D1) | by owner | `session:<id>` | tests/test_mw015_ledger_by.py::test_ask_answered_writes_owner |

## 8. Log

One line per step. No re-run of a check or an agent round without a new input named in the Log row.

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-16 | start: step 0 (folder mkway-t138, branch t138, base 6c3b48b, clean); order and common parts read | 6c3b48b | chief ruling R287b: the owner terminal tests (tests/test_mw014_commands.py:133, tests/test_mw113_way_out_ask.py:46 and :71) stay unchanged. Named limit: until the date in the profile key messaging.session_id_watch_until a session without the variable could write by: owner; while it is empty, the limit has no end date; the session-id gate closes it with no new code, and tests/core/test_mw110_session_env_core.py:38, case unset-after-window-refuses, covers it |
| 2026-11-16 | red commit, E1 to E9 and the way-out row | 406827f | new file red; the HEAD tests changed only under MW119-D1, session parts only |
| 2026-11-16 | engine: `core_ask.answer_decision`, `asks.answer`, `mkway.py` caller from the permit; concept.py row `ask-answered-not-lead` with its way-out test, a second row `ask-answered` (kind of the proof record, way-out test = the E5 node); GAPS_ALLOWED unchanged (99); manifest.json unchanged: reason ids are read from the source, no manifest row exists for ask ids; README and CHANGELOG | green commit | run set with -n 2: 3130 passed, 1 xfailed, 107 s, term scan included in test_repo_scan |
