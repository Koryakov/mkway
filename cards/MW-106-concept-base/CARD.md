# MW-106: the concept base: CONCEPT.md, the reason table and its four tests

| | |
|---|---|
| **Appetite** | 2 hours — from 2026-11-16 |
| **Status** | proposed |
| **Created / updated** | 2026-11-16 / 2026-11-16 |
| **Waiting for** | nothing |
| **Form** | card |
| **Decisions** | R262, R264, R264a, R264b, R265, R266, R266a, R216 — ids only, no text copied from the ledger; a commit that changes a test names one |
| **Canon** | none for the concept base: the basis is rulings R262 to R266a and the requirements file of the order |
| **Paths** | `engine/CONCEPT.md`, `engine/concept.py`, `tests/test_concept.py`, `README.md`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-106-concept-base/CARD.md` |

How to use: the form of `cards/_TEMPLATE/CARD.md`. The Acceptance table comes first: one row per test T1 to T4 and one per deliverable D1 to D5.

## 1. Goal

«let's start only first task. When you finish it, you should stop» — owner, 2026-11-16. The concept lives in the engine, not in documents: one short file every session can read, locked like the engine, and four tests that fail when the engine drifts from it. Scope: this card only; no gate behaviour changes, no reason id removed or renamed, no new gate, no new lock target.

## Acceptance examples

Each row becomes a test; `card close` needs every row to name one.

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | T1 reason coverage | no table of reasons | every reason id of the engine source has a row and every row a reason; the id is named in the failure | tests/test_concept.py::test_every_reason_in_the_source_has_a_row_and_every_row_a_reason |
| E2 | T2 eight kinds | no kinds | every row is K1 to K8 or an exit; a ninth kind fails; an exit row has a card 2 to 8; a kind row has none | tests/test_concept.py::test_there_are_eight_kinds_and_four_exits_and_every_row_uses_them |
| E3 | T3 way out | no way-out count | every row has a way-out test that exists or a gap card; the gap count equals GAPS_ALLOWED and only shrinks | tests/test_concept.py::test_every_row_has_a_way_out_test_or_a_gap_and_the_gaps_only_shrink |
| E4 | T4 the page | no concept page | the page holds the yardstick, eight numbered lines, K1 to K8, R1 to R4 and cards 2 to 8, in order | tests/test_concept.py::test_the_concept_page_holds_its_parts_in_order |
| E10 | T1 finder | the finder saw refusals only | the finder also sees an id raised through a helper, a warn, a log row, an allow line, a conditional and the watch mode row kinds, so the table holds every id the engine emits | tests/test_concept.py::test_the_finder_sees_every_way_the_engine_emits_a_reason |
| E5 | D1 `engine/CONCEPT.md` | none | sections a to f, one page, plain English, no people's names, no task numbers | checked by reading: engine/CONCEPT.md |
| E6 | D2 `engine/concept.py` | none | data only: KINDS, RECORDS, EXITS, REASONS, GAPS_ALLOWED, a comment naming the gate file on every row | checked by reading: engine/concept.py |
| E7 | D3 the four tests | none | `tests/test_concept.py`, core, hermetic, no subprocess, red first | checked by reading: tests/test_concept.py |
| E8 | D4 README, CHANGELOG, REGISTER | no concept section, no MW-106 line | section «The concept», one changelog line, one register row | checked by reading: README.md |
| E9 | D5 baseline counts | none | the counts as Log rows: kinds, exits, way-out rows and gaps | checked by reading: the Log rows of 2026-11-16 below |

## 8. Log

One line per step. No re-run of a check or an agent round without a new input named in the Log row.

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-16 | red tests T1 to T4 (E1 to E4), tests only | 92dadd4 | red by missing engine/concept.py and engine/CONCEPT.md: 4 failed in 0.4 s, every new id failing |
| 2026-11-16 | tests-only fix of the reason finder of T1 | 0465848 | the first finder read only refuse calls and reason keywords and found 88 ids; the engine also raises through Verdict REFUSE, Refusal, MessageError, RegisterError, BackupError, reason tuples and the ask tuples; now 136 ids; 4 failed, still red. No existing tests/test_mw*_docs.py holds a reason finder, so none was copied: the finder is new, ast based, in test_concept.py |
| 2026-11-16 | fix round R268, item 3: new finder test E10, red proof | 143bf93 | tests only: 5 new ids red: gate-error, commit-tests-still-red, ask-past-deadline, ping-skipped, undeclared-reason, which the engine emits through helpers, warn and log rows |
| 2026-11-16 | fix round R268, item 4: the finder reads helper, warn, log, conditional forms | 5aebb42 | tests only: 151 ids; the 5 ids pass, T1 red with 15 ids unplaced, gate-error among them |
| 2026-11-16 | fix round R268, item 4: four watch mode ids added to E10, red | fdf3117 | tests only: would-refuse, gate-watch, gate-watch-installed, gate-on red |
| 2026-11-16 | fix round R268, item 4: the finder reads the kind of a row dict and the watch mode row kinds | 9e8b29b | tests only: 156 ids, E10 all green, T1 red with 20 ids unplaced |
| 2026-11-16 | green of the fix round: 156 rows in blocks by card, the principle, items 1 to 8 | ff855c3 | T1 to T4 and E10 green; the 17 instruction rows each name the role file line; classification judgements: the commit form rows command-unparsed, engine-call-not-plain, commit-unreadable, commit-folder-unreadable, pathspec-unparsed are K1 gap 6 and commit-message-card K6 gap 6 by the principle; profile-invalid K8; built-dirty and built-untested K5 with gap card 7; lock-file-by-session K1 gap 4 |
| 2026-11-16 | run set after the fix round, -n auto, same files as before | ff855c3 | 2673 passed, 0 failed, 26.3 s; term scan clean, no hit; section f lines of R269c set, no test or table holds them |
| 2026-11-16 | rows of ruling R270, concept.py only, no test change: ask-record-failed and check-record-failed K8 gap 4 (agent-record-failed and post-record-failed also only warn today: same comment); built-dirty, built-untested, bundle-outside-root, profile-outside-root, copy-without-lock gap 4; commit-tests-still-red record card 3 | the commit of this row | 2673 passed, 0 failed, 28.5 s; kinds K1 20, K2 15, K3 26, K4 3, K5 2, K6 17, K7 6, K8 12; exits tool 15, instruction 19, record 21, remove 0; gaps by card 2: 16, 3: 16, 4: 28, 5: 14, 6: 11, 7: 39, 8: 32; GAPS_ALLOWED 156 |
| 2026-11-16 | reader 2 round: E10 pins one id per emit form, literal ceiling 179 in the E3 test, red proof | d4f0f73 | tests only: 6 ids red: ask-not-open, lead-unknown, ledger-by-owner, close-deliverable-unbuilt, base-unknown, verdict-written; 6 regression pins pass at once by design (the commit message says five: six is right) (agent-record-failed, notify-sent, notify-failed, ping-skipped-listed, lock-closed-commit, verdict-node-unknown: forms the finder already read, pinned so they cannot be lost) |
| 2026-11-16 | reader 2 round: the finder reads every Error class, the refusal method, returned id tuples, subscripted dict values, constants of other files | 4183ce5 | tests only: all E10 ids green, T1 red with 23 ids unplaced; no one-word reason id exists (the one-word strings the same forms pass are row kinds and node verdict words), the id shape is unchanged |
| 2026-11-16 | reader 2 round green: 23 rows by ruling R270b, GAPS_ALLOWED 179 | the commit of this row | 2685 passed, 0 failed, 32.6 s; term scan clean; ids: ask-* five K7 gap 8; lead-* ten, ack-* two, ledger-* two K6 gap 2; close-deliverable-unbuilt K2 gap 3; base-unknown and gate-watch-integrity K8 gap 4; verdict-written record 7 (extra) |
| 2026-11-16 | baseline after reader 2 round: kinds K1 to K8 | none | 179 rows; K1 20, K2 16, K3 26, K4 3, K5 2, K6 31, K7 11, K8 14 (123 rows of a kind) |
| 2026-11-16 | baseline after reader 2 round: exits | none | tool 15, instruction 19, record 22, remove 0; 123 + 15 + 19 + 22 + 0 = 179 |
| 2026-11-16 | baseline after reader 2 round: way-out rows and gaps | none | way-out rows present 0; gaps 179 = GAPS_ALLOWED; gaps by card 2: 30, 3: 17, 4: 30, 5: 14, 6: 11, 7: 40, 8: 37; the baseline rows of 2026-11-16 above this one are stale |
| 2026-11-16 | baseline after R268: kinds K1 to K8 | none | 156 rows; K1 20, K2 15, K3 26, K4 3, K5 2, K6 17, K7 6, K8 10 (99 rows of a kind) |
| 2026-11-16 | baseline after R268: exits | none | tool 15 (card 5: 14, card 6: 1), instruction 19, record 23, remove 0; 99 + 15 + 19 + 23 + 0 = 156 |
| 2026-11-16 | baseline after R268: way-out rows and gaps | none | way-out rows present 0; gaps 156 = GAPS_ALLOWED; gaps by card: 2: 16, 3: 15, 4: 21, 5: 14, 6: 14, 7: 44, 8: 32 |
| 2026-11-16 | green: concept.py, CONCEPT.md, README, CHANGELOG, REGISTER; acceptance E1 to E4 | 4146dcd | the four nodes red seen yes, green yes; E5 to E9 by reading |
| 2026-11-16 | run set with -n auto: tests/core, test_concept, every test_mw docs test, test_keys, test_meta_cards, test_register, test_repo_scan, test_install, test_mw029_fast_guard | 4146dcd | 2664 passed, 0 failed, 25.8 s; the term scan in test_repo_scan and test_install clean, no hit |
| 2026-11-16 | source of CONCEPT.md section b | none | `report/architect/R265_eight_lines_2026-11-16.md`, the eight lines without the answer and basis parts, «you» read as «the owner»; two words reworded because the page holds no task names: the name of the earlier task became «the earlier task» in line 8 and «the current task's work» in line 6 |
| 2026-11-16 | baseline: kinds K1 to K8 | none | 136 rows: K1 11, K2 14, K3 23, K4 2, K5 0, K6 12, K7 4, K8 2 (68 rows of a kind) |
| 2026-11-16 | baseline: exits | none | tool 21 (card 5: 14, card 6: 7), instruction 43 (card 7; 41 of them UNSURE), remove 0, record 4 (card 7); 68 + 21 + 43 + 0 + 4 = 136 |
| 2026-11-16 | baseline: way-out rows and gaps | none | way-out rows present 0, gaps 136, GAPS_ALLOWED 136: no test proves a way out yet, the tested way out is the work of cards 2 to 8 |
