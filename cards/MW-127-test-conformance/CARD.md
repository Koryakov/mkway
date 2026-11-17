# MW-127: the merged tests obey the engine's own test rules, first step: the pinned-sha test runs only in the engine repository

| | |
|---|---|
| **Appetite** | 1 hour for this step — from 2026-11-16 |
| **Status** | proposed |
| **Created / updated** | 2026-11-16 / 2026-11-16 |
| **Waiting for** | nothing |
| **Form** | card |
| **Decisions** | MW127-D1, R292, R292b, R294 — ids only, no text copied from the ledger; a commit that changes a test names one |
| **Canon** | none for the engine-only marker: the basis is rulings R292 and R294 and decision row MW127-D1 (1) |
| **Paths** | `tests/test_mw110_exit_rule.py`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-127-test-conformance/CARD.md` |

## 1. Goal

«I agree with all of three.» — owner, 2026-11-16 (the three audit cards, R294). Scope now: item 1 only. A test that reads a pinned commit of the engine repository must not fail in a task install, where that commit does not exist. Items 2 to 8 of the order are postponed to after the new version.

## Acceptance examples

Each row becomes a test; `card close` needs every row to name one.

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | the MW-110 exit-rule test that runs `git show` on the pinned base commit | no marker: fails in every copy that lacks the commit | carries the marker `engine_repo`, so a task copy (`-m "not engine_repo"`) leaves it out and the engine repository still runs it | tests/test_mw110_exit_rule.py::test_a_removed_refusal_had_an_exit_row_of_this_card |

## 8. Log

One line per step. No re-run of a check or an agent round without a new input named in the Log row.

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-16 | start: step 0 (folder, branch t139, base 6c3b48b, clean); scope per the order's line SCOPE NOW: item 1 only | 6c3b48b | items 2 to 8 postponed; the .gitignore item already done by MW-116 |
| 2026-11-16 | marker mechanism found: `engine_repo` declared at pytest.ini:9, used as a module mark at tests/test_e2e.py:15 and per test at tests/test_meta_cards.py:95 | 6c3b48b | the existing mechanism fits; no new marker |
| 2026-11-16 | why the marker is the right tool: commit 8a0dd4d turned the old skip of this fixture into a failure (a rule that cannot run must not pass in silence), so in a task install, which has no pinned commit, the test fails; a task copy runs `-m "not engine_repo"`, so the marker leaves it out there and the engine repository, where the commit exists, still runs it and still fails when the commit is missing | this commit | the fixture and its assert are unchanged: no assert weakened |
| 2026-11-16 | tests-only commit under MW127-D1 (1): marker engine_repo on test_a_removed_refusal_had_an_exit_row_of_this_card; run -n 2 of test_mw110_exit_rule, tests/core, test_meta_cards, test_register, test_concept, test_repo_scan; with -m "not engine_repo" the file collects 2 of 3 tests, the pinned-sha test deselected | 1eea233 | 2922 passed, 0 failed, 33 s; no engine file changed, no assert changed |
