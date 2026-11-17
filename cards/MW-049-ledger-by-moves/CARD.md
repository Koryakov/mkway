# MW-049: Every ledger row names who really made the move

| | |
|---|---|
| **Appetite** | 1 hour — from 2026-11-12 |
| **Status** | proposed |
| **Created / updated** | 2026-11-12 / 2026-11-12 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | none new: the lead's ruling carries it, quoted in the Goal |
| **Canon** | none for ledger by: the basis is MW-015, which fixed `ledger add` and `ask default` only |
| **Paths** | `engine/`, `tests/`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-049-ledger-by-moves/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository. `VERSION` is not changed here.

## 1. Goal

The ledger rows that `card open` and `card close` write carried by=`owner` even when a session ran the move. The
ruling: «every row the engine writes on a card move carries by=`session:<id>` when the hook environment shows a
session, and by=`owner` only from the owner's terminal. Check every engine-written row (open, close, give, release,
built, delivered) for the same fault; test each with both callers.» Checked: only `card open` and `card close` had the
fault; `built` already names the session; `give`, `release` and `delivered` write no ledger row.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | a lead's `card open` of its own card; the owner's open | the row had by=`owner` | by=`session:<id>`; the owner's terminal writes no session label | tests/test_mw049_ledger_by_moves.py::test_open_by_a_lead_writes_the_session_and_the_owner_writes_none |
| E2 | the orderer's `card close`; the owner's close | the row had by=`owner` | by=`session:<id>`; the owner's terminal writes no session label | tests/test_mw049_ledger_by_moves.py::test_close_by_the_orderer_writes_the_session_and_the_owner_writes_none |
| E3 | `built` by a session and by the owner | already right | by=`session:<id>` and `owner` | tests/test_mw049_ledger_by_moves.py::test_built_by_a_session_and_by_the_owner |
| E4 | `delivered` (and `give`, `release`) | write no ledger row | still none; any row is `owner` | tests/test_mw049_ledger_by_moves.py::test_delivered_give_and_release_write_no_session_labelled_owner_row |
| E5 | any engine call of `ledger.add` | `by` could be left to the default | every call names `by` | tests/test_mw049_ledger_by_moves.py::test_every_engine_ledger_write_names_its_by |

## 8. Log

One line per step. No re-run of a check or an agent round without a new input named in the Log row.

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-12 | red tests | 9e97bf3 | E1, E2, E5 red; E3, E4 already green (built names the session; delivered, give, release write no row) |
| 2026-11-12 | code, green | the commit that follows 9e97bf3 | `cardtool.move` names by=`session:<id>` on open and close; whole suite incl. term scan: 1053 passed in 683 s |
