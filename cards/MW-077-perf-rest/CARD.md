# MW-077: The remaining wall-clock limits are perf checks

| | |
|---|---|
| **Appetite** | 1 hour - from 2026-11-12 |
| **Status** | proposed |
| **Created / updated** | 2026-11-12 / 2026-11-12 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | R172 |
| **Canon** | none: the basis is the ruling R172, applied before to tests/test_e2e_gates.py only |
| **Paths** | `tests/test_mw038_real_shape.py`, `tests/test_mw030_live_install.py`, `tests/test_mw029_fast_guard.py`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-077-perf-rest/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository. `VERSION` is not changed here. No new behaviour: only which tests a commit or merge run selects.

## 1. Goal

«B (R172): a wall-clock limit is a perf check, not a correctness test, and under T8 it may not depend on machine load; mark it perf, keep it out of commit and merge runs, run it alone before a release tag as a step of R152» - R172, 2026-11-12.
Real case: the merge of t91 into master 5343c1c, 2026-11-12: 1 failed, 3418 passed, 1113.6 s;
`tests/test_mw038_real_shape.py::test_the_scenario_runs_inside_the_time_limit` failed with «68 s (limit 60 s)» while the
machine ran several test suites at once: a limit failed on load, not on a defect.

## Acceptance examples

Each row becomes a test; `card close` needs every row to name one. Each time assert sits alone in its test, so the test
is marked whole and nothing is split.

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | the 60 s scenario limit of MW-038 | runs in every commit and merge run | marked perf: selected by `-m perf`, left out of the default run | tests/test_mw038_real_shape.py::test_the_scenario_runs_inside_the_time_limit |
| E2 | the 90 s live install limit of MW-030 | runs in every commit and merge run | marked perf | tests/test_mw030_live_install.py::test_the_run_stays_inside_the_time_limit |
| E3 | the 10 s copy guard limit of MW-029 | runs in every commit and merge run | marked perf | tests/test_mw029_fast_guard.py::test_the_guard_runs_in_under_ten_seconds |

## 8. Log

One line per step. No re-run of a check or an agent round without a new input named in the Log row.

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-12 | start checks, each alone: `pwd` = the worktree, HEAD 5343c1c, `git status --short` = clean | 5343c1c | base of the card |
| 2026-11-12 | no red step: no new behaviour, only test selection (decision R172); the three tests keep their asserts, each gets the performance marker and one docstring sentence naming R172, as in `tests/test_e2e_gates.py` | | `-m perf` on the three files selects exactly the three ids; the three files pass: 31 passed, 3 deselected |
| 2026-11-12 | sweep of `tests/` (not `tests/core`) for other asserts on elapsed time. Not marked, each with its reason: `tests/test_mw005_gate.py` (`< 25` after a 30 s sleep with a 1 s budget), `tests/test_mw014_notify.py` (`< 15`, sleep 30, limit 1) and `tests/test_startline.py` (two `< 4` checks after a 30 s sleep or an orphan) prove that a timeout really stops a slow child: the assert is the correctness of the stop, the margin is large, and the test also asserts the refusal; `tests/test_e2e.py:100` (`took < timeout` of the hook entry) is the contract of the hook timeout; the shell tests (`CAP_SECONDS` in `tests/shell/conftest.py` and the `*_facts.py` files) are the cap of MW-052, a rule for the suite, not a limit of one flow; `tests/test_mw054_copy_e2e.py` records `seconds_build` and asserts nothing on it | | listed, none changed |
| 2026-11-12 | whole suite once, `python -m pytest -q`, term scan included | | 3416 passed, 4 deselected in 1503.59 s |
