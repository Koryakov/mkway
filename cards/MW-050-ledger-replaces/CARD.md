# MW-050: Ledger add can replace an earlier row

| | |
|---|---|
| **Appetite** | 30 minutes — from 2026-11-12 |
| **Status** | proposed |
| **Created / updated** | 2026-11-12 / 2026-11-12 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | none new: the lead's ruling carries it, quoted in the Goal |
| **Canon** | none for ledger replaces: the basis is MW-008, which made the `replaces` column |
| **Paths** | `engine/`, `tests/`, `README.md`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-050-ledger-replaces/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository. `VERSION` is not changed here.

## 1. Goal

`mkway ledger add` had no way to fill the `replaces` column, so a session wrote the link into topic and source. The
ruling: «add `--replaces <id>`: the id must exist; the replaced row's status becomes `superseded` by a rule that keeps
the ledger append-only; never edit an old row.» The rule: a row that a later row names in `replaces` reads as
superseded; its line is not touched.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | `ledger add --replaces <existing id>` | no such option | new row has replaces=<id>; the old row reads as superseded; earlier lines of the file are byte-identical | tests/test_mw050_ledger_replaces.py::test_replaces_an_existing_id_links_the_row_and_supersedes_the_old_one |
| E2 | `ledger add --replaces <unknown id>` | no such option | refused `ledger-replaces-unknown`; nothing written | tests/test_mw050_ledger_replaces.py::test_replaces_an_unknown_id_is_refused_and_nothing_is_written |

## 8. Log

One line per step. No re-run of a check or an agent round without a new input named in the Log row.

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-12 | red tests | b519a89 | E1, E2 red |
| 2026-11-12 | code, green | the commit that follows b519a89 | `--replaces` in ledger.add and the CLI, README line; whole suite incl. term scan: 1055 passed in 674 s |
