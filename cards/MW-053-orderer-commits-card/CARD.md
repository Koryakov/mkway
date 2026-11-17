# MW-053: The orderer commits the card folder it ordered

| | |
|---|---|
| **Appetite** | 1 hour — from 2026-11-12 |
| **Status** | proposed |
| **Created / updated** | 2026-11-12 / 2026-11-12 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | none new: the task order and its chief ruling carry it, quoted in the Goal |
| **Canon** | none for the commit gate and the orderer: the basis is MW-034 and MW-043 (what a commit takes) and MW-011 (the orderer) |
| **Paths** | `engine/`, `tests/`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-053-orderer-commits-card/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository. `VERSION` is not changed here.

## 1. Goal

On a real install a lead opened the card it ordered, then ran from the task root `git commit -m "<message>" --
<card folder> <register>` alone. The commit gate refused it, `file-not-in-card`, «this session holds no open card», so a
lead could not commit a card it ordered without the owner. The order: «a session that is the card's orderer (the card
row's Ordered by, as `card open` records it), or the owner, may commit a commit whose every taken file (judged by what
git takes, MW-043) is inside that card's own folder or is the register; it does not need to hold the card; several cards
it ordered in one commit are allowed; anything else in the same commit is refused as today, with the same reason, and
the text says that an orderer may commit only the folders of cards it ordered plus the register; a holder's rules do not
change; the other checks still run». The chief ruling: «inside a card folder, a file that the holder's Paths cover belongs
to the holder; the orderer commits only the card's own files and the register; such a file is refused, naming the
holder». Built: `gate_commit._orderer` and a few lines in `_commit`; the orderer is read from the session id and the
register's `Ordered by` cell, as `card close` reads it. The owner's terminal runs no hook, so the owner needs no rule.
Not established: the asks folder lies outside the card folder, so an ask file is not covered here.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | the orderer commits `CARD.md`, `ORDER.md`, the folder, the register of a card it ordered, holding no card | refused `file-not-in-card` | allowed | tests/test_mw053_orderer_commit.py::test_orderer_commits_card_md_and_register_without_holding_the_card |
| E2 | the plain form, a foreign file staged beside | refused | allowed for its own files; the foreign file refused, named, with the orderer sentence | tests/test_mw053_orderer_commit.py::test_the_plain_form_of_the_orderer_takes_the_staged_list |
| E3 | the `-i` form | refused | the staged list plus the named paths judged the same way | tests/test_mw053_orderer_commit.py::test_the_include_form_of_the_orderer_takes_the_staged_list_plus_the_named |
| E4 | two ordered cards in one commit | refused | allowed | tests/test_mw053_orderer_commit.py::test_two_ordered_cards_in_one_commit_are_allowed |
| E5 | the register alone | allowed | still allowed | tests/test_mw053_orderer_commit.py::test_the_register_alone_is_allowed_for_the_orderer |
| E6 | a session that did not order the card | refused | refused as today, only the files of cards it did not order named | tests/test_mw053_orderer_commit.py::test_a_session_that_did_not_order_the_card_is_refused_as_today |
| E7 | a card the owner ordered; a call with no session id | refused | refused | tests/test_mw053_orderer_commit.py::test_a_card_ordered_by_the_owner_or_a_session_without_an_id_is_refused |
| E8 | a mixed commit: own folder, a file outside the cards folder, another's card folder | refused | refused, the last two named, the orderer sentence in the text | tests/test_mw053_orderer_commit.py::test_a_mixed_commit_is_refused_naming_the_files_that_do_not_belong |
| E9 | the holder of a card | judged by its Paths | judged by its Paths, no orderer sentence | tests/test_mw053_orderer_commit.py::test_a_holder_keeps_its_rules |
| E10 | the orderer commits a file the holder's Paths cover | — | refused, the file and the holder named; `CARD.md`, `ORDER.md` allowed | tests/test_mw053_orderer_commit.py::test_a_file_under_the_holders_paths_is_the_holders_and_names_the_holder |
| E11 | junk, a data file, a message that names no ordered card | — | each refused with its own reason | tests/test_mw053_orderer_commit.py::test_the_other_checks_still_run_on_the_orderer_files |
| E12 | the register row, one changelog line, the card folder, VERSION | absent | present, VERSION unchanged | tests/test_mw053_orderer_commit.py::test_register_changelog_and_card_name_the_card |
| E13 | the real hook command, deny and allow | — | the mixed commit denied, the card-folder commit allowed | tests/test_e2e_gates.py::test_refusal_through_the_real_hook; tests/test_e2e_gates.py::test_allow_through_the_real_hook |
| E14 | the real-shape replay, the exact command shape | — | the lead's commit of the folder and the register passes, a builder's of the same folder is refused | tests/test_mw038_real_shape.py::test_s8_the_lead_commits_the_card_folder_it_ordered |

## 8. Log

One line per step. No re-run of a check or an agent round without a new input named in the Log row.

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-12 | red tests | 4017018 | E1 to E4, E6, E8, E10, E11, E12 red; E5, E7, E9 already green (guards of rules that stay) |
| 2026-11-12 | e2e row and replay step | the commit that follows 4017018 | E13 allow row and E14 red with the new helper switched off, green with it on; the deny row passes either way (a mixed commit is refused today too) |
| 2026-11-12 | code, green | the commit that follows 4017018 | whole suite incl. term scan: 1095 passed, 1 failed in 749 s (the copy guard: E12 lacked the `engine_repo` marker); marker added, guard and the card's test file re-run: 20 passed in 48 s; whole suite not re-run |
