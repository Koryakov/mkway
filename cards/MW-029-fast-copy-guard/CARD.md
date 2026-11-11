# MW-029: The copy guard is fast

| | |
|---|---|
| **Appetite** | 40 minutes — from 2026-11-11 |
| **Status** | proposed |
| **Created / updated** | 2026-11-11 / 2026-11-11 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | none new: the standing rule «a gap found in real work gets its own fix card at once» carries it |
| **Canon** | none for the copy guard: the basis is the gap found in the merge run (the suite passed the tool's limit) |
| **Paths** | `tests/`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-025-copy-check/CARD.md`, `cards/MW-029-fast-copy-guard/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository. `VERSION` is not changed here: other cards in flight set it.

## 1. Goal

The guard of MW-025 ran the whole suite inside a copy (239 s, plus 24 s to build the copy), so the whole suite passed
the 600 s limit of the merge tool and every merge timed out. The guard now collects the tests a copy would run
(`-m "not engine_repo"`), reads their sources and the helpers', and fails when one reads a path that install does not
copy (the list of copied files is install's own, as in MW-025). It runs in seconds and keeps the protection: all eight
tests of the MW-025 gap are found, and a test whose marker is dropped makes it fail.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | collected tests and helpers that read a path a copy lacks | a whole copy suite run | none found, by reading sources | tests/test_mw029_fast_guard.py::test_no_collected_test_reads_a_path_a_copy_lacks |
| E2 | time of the guard | 263 s | under 10 s | tests/test_mw029_fast_guard.py::test_the_guard_runs_in_under_ten_seconds |
| E3 | one of the eight tests, marker dropped in a scratch copy | not tried | the guard names it | tests/test_mw029_fast_guard.py::test_the_guard_fails_when_a_marker_is_dropped |
| E4 | a join, a joinpath, an os join, a path from the file's place | not read | seen | tests/test_mw029_fast_guard.py::test_a_path_join_a_joinpath_and_an_os_join_are_seen |
| E5 | a module constant and a helper that read | not read | the tests that use them are flagged | tests/test_mw029_fast_guard.py::test_a_module_constant_and_a_helper_carry_the_read_to_the_test |
| E6 | copied paths and scratch paths | not read | not flagged | tests/test_mw029_fast_guard.py::test_copied_paths_and_scratch_paths_are_not_flagged |
| E7 | MW-025's slow test | present | removed; MW-025 row E1 names the guard | tests/test_mw029_fast_guard.py::test_the_whole_suite_in_a_copy_test_is_gone_and_the_row_points_to_the_guard |
| E8 | register, changelog | no word | register row, a line under `## 0.2.6` | tests/test_mw029_fast_guard.py::test_register_changelog_and_card_name_the_card |

## 8. Log

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-11 | red: rows E1 to E8 | 3895750 | the file fails at import: the helper `tests/_copy_guard.py` does not exist |
| 2026-11-11 | green: `tests/_copy_guard.py` (static guard); MW-025's whole-copy test removed, its row E1 now names the guard (the protection is the same, the way is reading, not running); register row, changelog line | the commit that carries this line | rows E1 to E8 green; the static read finds all 8 of MW-025's tests, so no run-based check is kept |
| 2026-11-11 | first whole run: 840 passed, 3 failed: the guard flagged the generated folder `.pytest_tmp` (a scratch path, now left alone), and the scan hit a line of the red test file (the marker-dropping lines of E3 were rewritten without a regex and without the marker text; no scan exception added; the test's checks are unchanged) | the commit that carries this line | the three tests pass again |
| 2026-11-11 | ported onto master with MW-026: the changelog line moved from `## 0.2.2` to `## 0.2.6` (one release for both cards), so row E8 and its test read `## 0.2.6` | the commit that carries this line | reading, to confirm |
| 2026-11-11 | whole suite, `python -m pytest`, term scan included; the guard test E2 measures under 10 s (about 2 s alone) | the commit that carries this line | 843 passed in 417 s (6 min 57 s), well under the 600 s limit (was about 9.5 min); no term-scan exception added |
