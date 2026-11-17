# MW-136: a true way out in the refusal text of card-paths-changed

| | |
|---|---|
| **Appetite** | 1 hour - from 2026-11-17 |
| **Status** | proposed |
| **Created / updated** | 2026-11-17 / 2026-11-17 |
| **Waiting for** | us |
| **Form** | card |
| **Decisions** | none new: the basis is the order of 2026-11-17 |
| **Canon** | none for the refusal text: the basis is the order of 2026-11-17 |
| **Paths** | `engine/core_session.py`, `tests/test_mw136_paths_wayout.py`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-136-paths-wayout-text/CARD.md` |

## 1. Goal

The refusal `card-paths-changed` told the owner to run `card open <id>` again, but a re-open of an open card records no Paths (rule H1), so the step did nothing. The text now names the routes that work today: restore the card's Paths to the recorded set, or put the extra files under a new card that the lead orders and opens. Only the text changes; what is allowed or refused does not.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | the owner's re-open in the text | the text says to ask the owner to run `card open <id>` again | the text names no re-open of the card as a way out | tests/test_mw136_paths_wayout.py::test_the_refusal_no_longer_names_the_owners_reopen |
| E2 | the routes in the text | none that works | the text names the restore and the new card opened by its orderer | tests/test_mw136_paths_wayout.py::test_the_refusal_names_the_restore_and_the_new_card_routes |
| E3 | the restore route | not run | after the restore, the same edit passes | tests/test_mw136_paths_wayout.py::test_restoring_the_recorded_paths_makes_the_same_edit_pass |
| E4 | the new-card route | not run | a new card with the extra Paths, opened by its orderer, lets the edit of the extra file pass | tests/test_mw136_paths_wayout.py::test_a_new_card_opened_by_its_orderer_lets_an_extra_file_pass |

## 8. Log

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-17 | red tests | 79d9ecd | tests/test_mw136_paths_wayout.py alone: E1 and E2 fail on the old text, E3 and E4 pass (the routes already work; the test runs them) |
| 2026-11-17 | text | this commit | engine/core_session.py: the `card-paths-changed` text; own test file, test_meta_cards, test_register, tests/core and tests/test_e2e_gates: 3190 passed; the whole suite is not run here, the batch merge runs it once |
