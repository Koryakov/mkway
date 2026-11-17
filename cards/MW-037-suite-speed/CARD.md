# MW-037: The whole suite runs well under the merge limit

| | |
|---|---|
| **Appetite** | 1 day — the most this work is worth, from the creation date |
| **Status** | proposed |
| **Created / updated** | 2026-11-12 / 2026-11-12 |
| **Waiting for** | owner |
| **Form** | card |
| **Decisions** | none |
| **Canon** | `none for suite speed` |
| **Paths** | `tests/conftest.py`, `tests/test_install.py`, `tests/test_mw016_version.py`, `cards/MW-037-suite-speed/` |

## 1. Goal

«the whole suite runs well under the merge limit» — the merge tool runs `python -m pytest` with a 600 s limit; the suite
took 523 s at 540d116 and grows with each card. Target: under 300 s, count stays 919, no assert weakened.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | whole suite time | 506 s | under 300 s | checked by reading: cards/MW-037-suite-speed/durations_after.txt |
| E2 | tests passing | 919 | 919 or more | checked by reading: cards/MW-037-suite-speed/durations_after.txt |

## 8. Log

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-12 | Measured at 540d116: `durations_before.txt` | none | 919 passed in 506.58 s. Install tests dominate; each rebuilt its engine source, and files written fresh are slow to read first time on this machine |
| 2026-11-12 | `make_source` returns one session-shared source per kind (read only); `fresh=True` for tests that change their source: `test_install.py::test_install_copies_the_fixed_set_and_writes_the_lock` (edits and builds two sources), `test_mw016_version.py` git source (commits into it), and `make_light_source` (deletes files). No test deleted, skipped or loosened | see git log | First after-run: 918 passed, 444 s; one failure: a test relied on the build creating its folder, so `make_source` creates it again. Final result: 919 passed in 466.68 s (run noise is about 20 s). Row E1 (under 300 s) is NOT met: the sharing saves 40 to 60 s only, because each install still reads its own fresh copy and every new file costs about 4 ms on this machine. Next lever: fewer installs per test, or the scan cost of fresh files |
