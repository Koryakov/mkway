# MW-141: a test's row ages are measured when the test runs, not when its module is imported

| | |
|---|---|
| **Appetite** | 1 hour - from 2026-11-17 |
| **Status** | proposed |
| **Created / updated** | 2026-11-17 / 2026-11-17 |
| **Waiting for** | us |
| **Form** | card |
| **Decisions** | MW141-D1 |
| **Canon** | none for test clocks: the basis is the order of 2026-11-17 |
| **Paths** | `tests/shell/test_session_facts.py`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-141-fixture-clock/CARD.md` |

## 1. Goal

The merge run of 2026-11-17 (1878 s) failed on one test: a «45-minute-old» order was over 60 minutes old because the test file took its clock once at import. The ages of the rows in tests/shell/test_session_facts.py are now measured from the moment the fixture runs (`now()` inside `build_inboxes`, and at the notice row). No assert changes and no case is removed (decision row MW141-D1). A guard test proves it.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | the 60-minute limit lets a 45-minute-old unacked order pass | warns when the test runs over 15 minutes after import | allows whenever the test runs | tests/shell/test_session_facts.py::test_the_stop_reminder_reads_the_age_of_unacked_orders_against_the_profiles_minutes |
| E2 | rows built 20 minutes after the module was imported | a 45-minute order is 65 minutes old and warns under a 60-minute limit | the same order still passes | tests/shell/test_session_facts.py::test_the_ages_of_the_rows_do_not_depend_on_how_long_ago_the_module_was_imported |

## 8. Log

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-17 | change | this commit | MW141-D1: module-level `NOW` removed; `now()` read inside `build_inboxes` and at the notice row; the guard test added (run with the old import-time clock put back it fails, with the fix it passes); tests/shell/test_session_facts.py: 126 passed. One tests-only commit as the order says, so the red guard is shown by that run, not by a separate earlier commit |
| 2026-11-17 | candidates | - | other test files with a module-level real-clock `now()` compared with the real clock: none found (a search of tests/ for module-level clock assignments and helpers; the T0 of tests/_mw019.py is a fixed date, and the two e2e files that subtract it take the real clock inside the test). Not covered: module-scoped fixtures that read the clock indirectly through a helper |
