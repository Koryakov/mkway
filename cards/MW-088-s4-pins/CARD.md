# MW-088: The test shape rule S4 accepts a one-line Pins: docstring

| | |
|---|---|
| **Appetite** | 1 day — the most this work is worth, from the creation date |
| **Status** | proposed |
| **Created / updated** | 2026-11-13 / 2026-11-13 |
| **Waiting for** | nothing |
| **Form** | card |
| **Decisions** | R218, R220 — ids only, no text copied from the ledger; a commit that changes a test names one |
| **Canon** | `none for docstring heads, after a ledger search by retro-oper10` |
| **Paths** | `tests/core/test_shape_decide.py`, `engine/core_shape.py`, `README.md`, `cards/MW-088-s4-pins/CARD.md`, `cards/REGISTER.md`, `CHANGELOG.md` |

## 1. Goal

«two engine rules that disagree is a real gap (R141), and it is tiny: after MW-072 merges and before wave C starts, one card makes S4 accept the three heads «Catches:», «Checks:», «Pins:», one table row red first, 20 minutes; the Log quotes the refusal.» — retro-chief10, R218, 2026-11-13.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | a one-line `Pins:` docstring | refused S4 | allowed | tests/core/test_shape_decide.py::test_a_one_line_pins_docstring_is_allowed |
| E2 | a one-line `Catches:` or `Checks:` docstring | allowed | allowed | tests/core/test_shape_decide.py::test_a_catches_line_and_a_checks_line_are_allowed[catches]; tests/core/test_shape_decide.py::test_a_catches_line_and_a_checks_line_are_allowed[checks] |
| E3 | no docstring, another word, two lines | refused S4 | refused S4 | tests/core/test_shape_decide.py::test_a_test_without_a_one_line_catches_or_checks_docstring_is_refused_as_s4[none]; tests/core/test_shape_decide.py::test_a_test_without_a_one_line_catches_or_checks_docstring_is_refused_as_s4[no-word]; tests/core/test_shape_decide.py::test_a_test_without_a_one_line_catches_or_checks_docstring_is_refused_as_s4[two-lines] |
| E4 | the S4 text names the three heads as facts | two heads | three heads | checked by reading: engine/core_shape.py |
| E5 | README and the module docstring name the three heads | two | three | checked by reading: README.md; checked by reading: engine/core_shape.py |

## 8. Log

One line per step. No re-run of a check or an agent round without a new input named in the Log row.

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-13 | the refusal met in the MW-072 port | b40ef91 | «no one-line docstring that starts Catches: (failure path) or Checks: (allow path)» refused a Pins: docstring that the red-proof gate lets through for a refactor or migration card |
| 2026-11-13 | red run, tests only | ee470e2 | FAILED tests/core/test_shape_decide.py::test_a_one_line_pins_docstring_is_allowed (assert [('test_a', 'S4')] == []), 1 failed |
| 2026-11-13 | acceptance E1 | f728a18 | tests/core/test_shape_decide.py::test_a_one_line_pins_docstring_is_allowed: red seen yes, green yes |
| 2026-11-13 | acceptance E2 | f728a18 | tests/core/test_shape_decide.py::test_a_catches_line_and_a_checks_line_are_allowed[catches] and [checks]: red seen no: existing MW-073 tests, unchanged in this card, green yes |
| 2026-11-13 | acceptance E3 | f728a18 | tests/core/test_shape_decide.py::test_a_test_without_a_one_line_catches_or_checks_docstring_is_refused_as_s4[none], [no-word], [two-lines]: red seen no: existing MW-073 tests, unchanged in this card, green yes |
| 2026-11-13 | acceptance E4 | f728a18 | engine/core_shape.py TEXTS S4 names the three heads: checked by reading |
| 2026-11-13 | acceptance E5 | f728a18 | README.md and the engine/core_shape.py module docstring name the three heads: checked by reading |
| 2026-11-13 | docstring at line 86 left as it is | f728a18 | the docstring of test_a_catches_line_and_a_checks_line_are_allowed («both words of the rule») is not changed in this card |
| 2026-11-13 | run a: shape, register, meta and docs tests, 2 workers | f728a18 | 2190 passed in 71.98s |
| 2026-11-13 | run b: coverage of engine/core_shape.py by test_shape_decide.py and test_shape_core_edges.py | f728a18 | 59 passed; 209 statements, 0 missed, one partial branch 116->111 (an existing line, not changed here), 99 percent |
| 2026-11-13 | known risk, not fixed, R221 | the commit that carries this line | the card Kind comes from the card's own header and nothing guards it, so a card that writes Kind refactor plus a pinning row can pin; a later card fixes Kind at open and refuses card-kind-changed |
