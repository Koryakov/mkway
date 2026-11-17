# MW-084: A term hit in a closed card's text

| | |
|---|---|
| **Appetite** | 1 hour - from 2026-11-13 |
| **Status** | proposed |
| **Created / updated** | 2026-11-13 / 2026-11-13 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | R201, R203 |
| **Canon** | none: the basis is the ruling R201 |
| **Paths** | `cards/MW-077-perf-rest/CARD.md`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-084-term-line/CARD.md` |

## 1. Goal

The term scan passes on the real repository again: one line of a closed card is reworded, nothing else changes.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | the term scan on the real repo | one hit in a closed card's text | no hit | tests/test_repo_scan.py::test_repository_has_no_term_hits |

## 8. Log

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-13 | red | 8cc1d84 | the scan test fails at cards/MW-077-perf-rest/CARD.md:42 group B #11 |
| 2026-11-13 | fix | this commit | cards/MW-077-perf-rest/CARD.md:42 reworded, reason term scan, R201; the row's meaning is unchanged (R203) |
| 2026-11-13 | gates | - | no new test and no engine code: gate, red-proof and coverage items do not apply |
| 2026-11-13 | whole suite | - | python -m pytest -q: 3416 passed, 4 deselected in 1053 s, no failure |
