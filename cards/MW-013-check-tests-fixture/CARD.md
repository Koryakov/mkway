# MW-013: The check tests run a fixture test set, not the whole suite

| | |
|---|---|
| **Appetite** | 30 minutes — from 2026-11-10 |
| **Status** | proposed |
| **Created / updated** | 2026-11-10 / 2026-11-10 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | none new: the ruling of the orderer of 2026-11-10 carries the change |
| **Canon** | none for the check tests: the engine has no ledger; the basis is the order of 2026-11-10 |
| **Paths** | `tests/test_install.py`, `fixtures/synthetic/`, `cards/REGISTER.md`, `cards/MW-013-check-tests-fixture/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository. No change to `engine/install.py` or to `check`: the test builds its engine source with a fixture `tests/`.

## 1. Goal

The three `mkway check` tests ran the engine's whole suite inside a test: 466 s of a 676 s full run (227 s, 120 s,
119 s). The recursion grows with every card and made merge test runs time out. They must prove that `check` runs the
copy's tests and the term scan, not that the whole suite passes — order of 2026-11-10.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | hash, tests, skipped scan | `check` ran every engine test in the copy | `check` collects exactly the one fixture test: `tests: 1 passed` | tests/test_install.py::test_check_compares_hash_runs_tests_and_skips_scan |
| E2 | missing term file | same | the same line, and `tests: 1 passed` | tests/test_install.py::test_check_with_a_missing_term_file_says_so |
| E3 | term scan with a term file | same | the same counts line, and `tests: 1 passed` | tests/test_install.py::test_check_runs_the_term_scan_when_a_term_file_is_set |

## 8. Log

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-10 | red: one new assertion per test, `tests: 1 passed` | 430ec1c | rows E1 E2 E3 red on the whole-suite copy |
| 2026-11-10 | green: `make_light_source` (fixture `tests/`, helpers kept), `fixtures/synthetic/check_set_pass.py` and `check_set_scan.txt` | 8e9314b | the three tests pass in 9 s together (was 466 s); existing assertions unchanged; no change to install.py |
| 2026-11-10 | whole suite, `python -m pytest`, term scan included | 8e9314b | 518 passed in 234 s (was 676 s on a98a20b); no term-scan exception added |
