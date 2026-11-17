# MW-086: A docs test checks that its changelog line is present, not that it is last

| | |
|---|---|
| **Appetite** | 1 day |
| **Status** | proposed |
| **Created / updated** | 2026-11-13 / 2026-11-13 |
| **Waiting for** | nothing |
| **Form** | card |
| **Decisions** | R210 |
| **Canon** | none for changelog position, after a ledger search |
| **Paths** | `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-086-docs-presence`, `tests/test_mw080_docs.py` |

How to use: `mkway card new <title>` writes this file and the register row; the register's status is the one the
gates read. Paths: the files and folders the card may edit, in backticks, comma-separated; the owner's `card open`
records them. The header rows and the headings `1. Goal`, `Acceptance examples`, `8. Log` are read by the gates — keep them. A card that needs a new
decision stops and shows the owner example rows to choose from. More than 3 hours → split first. At most one page
before the log. Tests first: first Log row — red tests committed alone (the card's `tests/` folder only), the commit
id and the red run's output in its message; later row — the code commit, naming that commit id and the green run.
When two requirements contradict: `card set <id> waiting`, a Log line that names both, then the ask.
Test quality: Acceptance rows: one per rule clause of a computed value. The Test cell is a `; ` list of full node ids
(`tests/test_x.py::test_y`), or `checked by reading: <path>` naming the file read; nothing else.
A test is evidence only when T1 one row, one node; T2 one id, one case; T3 deny plus nearest allow per refusal reason; T4 independent expectation, «Catches: ...» on a failure test; T5 changed lines run; T6 blind verdict; T7 a committed test changes only with a decision; T8 shape: no test imports a test, synthetic data, the real hook for a refusal (criteria: the owner's test criteria, T1-T8).
Close notes: before `card close`, every test node a row names has a verdict row (true / weak / wrong, reason, by) from a reader who did not write the test in `tests/verdicts/<ID>.md`.

## 1. Goal

I NEED TO FIX TESTS FIRST!! ALL BAD THINGS like reading real repo, real installation etc etc - you must carefully check tests! — owner, 2026-11-13.

## Acceptance examples

Each row becomes a test; `card close` needs every row to name one.

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | changelog check of MW-080 | the MW-080 line must be the last line of the top section | the MW-080 line is in the top section | tests/test_mw080_docs.py::test_register_changelog_and_card_name_the_card |

## 8. Log

One line per step. No re-run of a check or an agent round without a new input named in the Log row.

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-13 | red: MW-086's changelog line made MW-080's line not last; the old position check failed | this commit | 1 failed, 5 passed in 0.74s |
| 2026-11-13 | green: tests-only change of a committed test, T7 decision R210 (position check broke whenever a later card appended a changelog line; mkcl gate of t97, 13.11) | this commit | the 4 test files test_mw080_docs, test_register, test_meta_cards, test_mw082_attributes plus tests/core and the term scan pass |
