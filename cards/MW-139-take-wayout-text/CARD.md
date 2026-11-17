# MW-139: the refusal for a red the take record does not hold names the route that works

| | |
|---|---|
| **Appetite** | 1 hour - from 2026-11-17 |
| **Status** | proposed |
| **Created / updated** | 2026-11-17 / 2026-11-17 |
| **Waiting for** | us |
| **Form** | card |
| **Decisions** | none new: the basis is the order of 2026-11-17 (text only, approved by the orderer) |
| **Canon** | none for the refusal text: the basis is the order of 2026-11-17 |
| **Paths** | `engine/gate_commit_tests.py`, `engine/cardtool.py`, `tests/core/test_mw108_judge_core.py`, `tests/shell/test_mw139_way_out_shell.py`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-139-take-wayout-text/CARD.md` |

## 1. Goal

«I want that you fix All of them» — owner, 2026-11-17. A card taken before any kept test row of HEAD's history exists has a take record without the reds of HEAD, and a red-first commit refuses them with a way out that said "the next merge writes the row", which sends a builder in a task that merges seldom nowhere. The refusal now names the route that works: release the card and take it again, because the refused run itself kept a row of HEAD's tests and the new take reads it. Text only; what is allowed and refused does not change.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | the refusal for the own-red cases «none» and «not-established» | «the next merge writes the row; until then every red counts as new» | names `mkway card release <id>` then `mkway card take <id>` and no longer the next merge | tests/core/test_mw108_judge_core.py::test_a_red_in_the_cards_paths_that_the_take_record_does_not_hold_is_new; tests/core/test_mw108_judge_core.py::test_a_red_in_the_cards_paths_is_new_when_its_take_is_not_established |
| E2 | the route is run | not run by any test | card taken with no kept row, red-first commit refused with the new text, release + take, the same commit allowed with the red as old red held by the card's inherited red | tests/shell/test_mw139_way_out_shell.py::test_the_way_out_of_a_red_the_take_record_does_not_hold_works_release_then_take |
| E3 | the take line of a take that is not established | «…; the next merge writes the row» | names `mkway card release <id>` then `mkway card take <id>` after a refused commit or any run that keeps a test row of HEAD; no «next merge» | tests/shell/test_mw139_way_out_shell.py::test_the_take_line_of_a_take_that_is_not_established_names_the_route_not_the_next_merge |

## 8. Log

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-17 | row change | tests commit | decision-free text row: the constant WAY_OUT in tests/core/test_mw108_judge_core.py named the old sentence; it now names the new route and checks the old one is gone (the two refusal tests E10 and E12 of MW-108 keep their other asserts) |
| 2026-11-17 | test fix | code commit | the route test of E2 first ran the release as a session without the row the post hook writes for it; the test now appends that row, as the other card tests do with `hold`; no assertion weakened |
| 2026-11-17 | route | code commit | the route works: the refused run keeps the HEAD row, release + take records the reds, the same commit is allowed with them as old red |
| 2026-11-17 | green | code commit | targets: tests/core, test_meta_cards, test_register, test_term_scan, tests/shell/test_mw108_*, test_mw139 : 3112 passed; the whole suite was not run by order |
| 2026-11-17 | order change | tests commit | the orderer added the `card take` line (engine/cardtool.py) to this card: row E3; the route test now runs the real post hook (gate_records.record) instead of writing the release row by hand |
| 2026-11-17 | green | code commit | E3 code in engine/cardtool.py after red commit a5c492b; targets as above: 3113 passed |
