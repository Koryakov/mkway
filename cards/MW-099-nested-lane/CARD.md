# MW-099: Tests that start a nested pytest run in their own xdist group

| | |
|---|---|
| **Appetite** | 1 day — the most this work is worth, from the creation date |
| **Status** | closed |
| **Created / updated** | 2026-11-13 / 2026-11-13 |
| **Waiting for** | nothing |
| **Form** | card |
| **Decisions** | R239, R241, R241a — ids only, no text copied from the ledger; a commit that changes a test names one |
| **Canon** | not established |
| **Paths** | `cards/MW-099-nested-lane/CARD.md`, `cards/REGISTER.md`, `CHANGELOG.md` |

## 1. Goal

Find out whether the four nested-pytest tests in the shared xdist lane explain the longer merge gate; the card ends with the measurement, no code (R241a).

## Acceptance examples

Each row becomes a test; `card close` needs every row to name one.

| # | Item | Was | Must be | Test |
|---|---|---|---|---|

## 8. Log

One line per step. No re-run of a check or an agent round without a new input named in the Log row.

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-13 | STEP 1 (a): the shared lane alone, `-m "real_shared_state and not perf" -p no:xdist`, base 24d366d | none (no file change) | 34 passed, 4179 deselected, wall 80.88 s; sum of setup+call+teardown 71.45 s |
| 2026-11-13 | STEP 1 (a): the 15 slowest tests of the lane | none | 21.67 s and 11.64 s the two child-run tests of the nested module; 6.66, 5.21, 4.62, 4.58, 3.65, 2.63 s state-in-root tests; 4.09 s the module fixture `collected` charged to E18; rest at or under 1.05 s |
| 2026-11-13 | STEP 1 (b): `tests/test_mw083_real_repo.py` alone, `-p no:xdist` | none | 6 passed, wall 37.51 s; per test 22.60, 11.08, 3.61 and about 0.00 s for the four with real_shared_state, 0.07 and 0.00 s for the other two |
| 2026-11-13 | STEP 1 (b): sum over the four tests with real_shared_state | none | about 37.3 s |
| 2026-11-13 | Conclusion (R241a) | none | measured and disproved: the lane is 80.9 s alone, the four nested tests 37.3 s, against +311 s; R239's suspicion withdrawn (R241a) |
| 2026-11-13 | Card, register row and changelog line written; run of tests/test_meta_cards.py and tests/test_register.py only, as ordered by R241a | this commit | 7 passed in 2.46 s |
