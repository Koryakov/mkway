# MW-087: The no-disk guard of the core tests lets the coverage tracer's own file calls through

| | |
|---|---|
| **Appetite** | 1 day — the most this work is worth, from the creation date |
| **Status** | proposed |
| **Created / updated** | 2026-11-13 / 2026-11-13 |
| **Waiting for** | nothing |
| **Form** | card |
| **Decisions** | R215 |
| **Canon** | `none for no-disk guard, coverage tracer, test helper`, after a ledger search by retro-oper10 |
| **Paths** | `tests/_no_io.py`, `tests/core/test_commit_decide.py`, `tests/core/test_session_decide.py`, `tests/core/test_lock_decide.py`, `cards/MW-087-no-io-coverage/CARD.md`, `cards/REGISTER.md`, `CHANGELOG.md` |

## 1. Goal

«I NEED TO FIX TESTS FIRST!! ALL BAD THINGS like reading real repo, real installation etc etc - you must carefully check tests!» — owner, 2026-11-13.

## Acceptance examples

Each row becomes a test; `card close` needs every row to name one.

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | the guard ids under --cov | fail | pass | tests/core/test_commit_decide.py::test_the_guard_fails_on_disk_access[open]; tests/core/test_commit_decide.py::test_the_guard_fails_on_disk_access[read_text]; tests/core/test_commit_decide.py::test_the_guard_fails_on_disk_access[clock] |
| E2 | the same ids without --cov | pass | pass | tests/core/test_commit_decide.py::test_the_guard_fails_on_disk_access[open]; tests/core/test_commit_decide.py::test_the_guard_fails_on_disk_access[read_text]; tests/core/test_commit_decide.py::test_the_guard_fails_on_disk_access[clock] |
| E3 | the guard still fires for a call from the test | pass | pass | tests/core/test_commit_decide.py::test_the_guard_fails_on_disk_access[open]; tests/core/test_commit_decide.py::test_the_guard_fails_on_disk_access[read_text]; tests/core/test_commit_decide.py::test_the_guard_fails_on_disk_access[clock]; tests/core/test_session_decide.py::test_the_guard_fails_on_disk_and_clock_access[open]; tests/core/test_session_decide.py::test_the_guard_fails_on_disk_and_clock_access[clock]; tests/core/test_session_decide.py::test_the_guard_fails_on_disk_and_clock_access[stat]; tests/core/test_lock_decide.py::test_the_guard_of_this_file_fails_on_disk_access |
| E4 | one helper serves all three files | three copies | one | checked by reading: tests/_no_io.py |
| E5 | a call with a coverage frame BELOW the test is still refused | (no test) | refused | tests/core/test_commit_decide.py::test_a_coverage_frame_below_the_test_does_not_pass_a_call_through |

## 8. Log

One line per step. No re-run of a check or an agent round without a new input named in the Log row.

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-13 | red run under --cov, commit guard ids | 76a7c8f | tests/core/test_commit_decide.py::test_the_guard_fails_on_disk_access: 3 failed in 3.65s, FAILED [open], [read_text], [clock]: the tracer's path lookup hit the patched os call |
| 2026-11-13 | red run under --cov, session and lock guard tests | 76a7c8f | session test_the_guard_fails_on_disk_and_clock_access: 3 passed in 0.44s; lock test_the_guard_of_this_file_fails_on_disk_access: 1 failed in 0.72s |
| 2026-11-13 | acceptance E1 | c19c66a | the three commit guard ids under --cov: red seen yes, green yes |
| 2026-11-13 | acceptance E2 | c19c66a | the same ids without --cov: red seen no: passes at the start sha by design, green yes |
| 2026-11-13 | acceptance E3 | c19c66a | commit, session and lock guard ids: red seen no: passes at the start sha by design, green yes |
| 2026-11-13 | acceptance E4 | c19c66a | checked by reading: tests/_no_io.py |
| 2026-11-13 | acceptance E5 | c19c66a | tests/core/test_commit_decide.py::test_a_coverage_frame_below_the_test_does_not_pass_a_call_through: new id, green yes; it would also pass on the old copies, it guards the new pass-through |
| 2026-11-13 | decision R215 and waiver | c19c66a | T7 decision R215 covers the edit of the three committed guards; items b and f of the common rules are waived for this card by the order owner: no tests-only red commit, the helper and the three edits land in one commit |
| 2026-11-13 | green 4a under --cov | c19c66a | commit guard ids 3 passed in 0.49s; session guard ids 3 passed in 0.43s; lock guard test 1 passed in 0.56s; E5 test 1 passed in 0.41s |
| 2026-11-13 | green 4b three core files without --cov | c19c66a | 732 passed in 4.17s |
| 2026-11-13 | green 4c parallel under --cov, tests/core and the meta tests | c19c66a | 1878 passed in 18.97s with MKWAY_TEST_WORKERS=2 |
