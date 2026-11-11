# MW-025: The install check runs only tests that fit a copy

| | |
|---|---|
| **Appetite** | 40 minutes — from 2026-11-11 |
| **Status** | proposed |
| **Created / updated** | 2026-11-11 / 2026-11-11 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | none new: the standing rule «a gap found in real work gets its own fix card at once» carries it |
| **Canon** | none for the check's test selection: the basis is the gap found in the owner's first real install |
| **Paths** | `engine/install.py`, `CHANGELOG.md`, `VERSION`, `tests/`, `cards/REGISTER.md`, `cards/MW-025-copy-check/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository.

## 1. Goal

`mkway check` in an installed copy runs only tests that fit a copy. In the owner's first real install it ran 763
tests and 8 failed: each read a file only the engine repository has (the README, the changelog, the register) and
none carried the marker `engine_repo` that the check leaves out. A guard test now builds a copy from install's own
file list, runs the copy's tests as the check does and fails while any of them fails, so a new card cannot repeat the
gap; the eight tests carry the marker; the check line names the failing tests (up to ten), not only the count.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | the tests a copy runs, in a copy built from install's file list | 8 fail | 0 fail | tests/test_mw029_fast_guard.py::test_no_collected_test_reads_a_path_a_copy_lacks |
| E2 | the eight tests of the gap | no marker | marked `engine_repo` | tests/test_mw025_copy_check.py::test_the_eight_tests_that_read_engine_repository_files_are_marked |
| E3 | the tests line of a failing check | the count only | the count and the failing test names | tests/test_mw025_copy_check.py::test_check_names_the_failing_tests_not_only_the_count |
| E4 | twelve failing tests | the count only | ten names and `2 more` | tests/test_mw025_copy_check.py::test_check_names_at_most_ten_failing_tests |
| E5 | register, changelog, version | no word | register row, `## 0.2.2` above `## 0.2.1`, `VERSION` 0.2.2 | tests/test_mw025_copy_check.py::test_register_changelog_version_and_card_name_the_card |

## 8. Log

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-11 | red: rows E1 to E5 | 0ed88e1 | E2, E3, E4, E5 red; E1 (the guard) was not run red on its own: the 8 failures are the gap report's, see the next rows |
| 2026-11-11 | green: `engine_repo` marker on the 8 tests; `failed_names` in `engine/install.py` (check line: up to 10 names, then `and N more`); register row, `## 0.2.2`, `VERSION` 0.2.2 | the commit that carries this line | rows E1 to E5 green; the guard found no test beyond the 8 |
| 2026-11-11 | E1 is slow but required: it runs a whole copy suite, 236 s for the targeted run; it carries `engine_repo` so a copy does not run it again. The whole suite is now about 9.5 min | the commit that carries this line | kept, as the task allows |
| 2026-11-11 | rows E1 to E6 of MW-024 and the version pins of MW-016, MW-017, MW-018, MW-022, MW-023 changed `0.2.1` to `0.2.2` (a patch release, README rule); no other change to them | the commit that carries this line | reading, to confirm |
| 2026-11-11 | the first whole run showed 2 term-scan failures on a line of the red test file (line 104); the line was reworded, no exception added | the commit that carries this line | scan tests green again; the red commit still holds the old line |
| 2026-11-11 | MW-029: row E1's whole-copy test was too slow for the merge tool (the suite passed 600 s); it is removed and row E1 now names the static guard `tests/test_mw029_fast_guard.py::test_no_collected_test_reads_a_path_a_copy_lacks`; the protection is the same | the commit that carries this line | rows E2 to E5 unchanged |
| 2026-11-11 | whole suite, `python -m pytest`, term scan included | the commit that carries this line | first run 834 passed, 2 failed (the scan hit above); after the reword the scan tests and E2 pass; second whole run: 836 passed in 637 s (831 on the base, 5 new); no term-scan exception added |
