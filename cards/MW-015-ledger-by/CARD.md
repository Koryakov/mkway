# MW-015: A session never writes the owner's words in the ledger

| | |
|---|---|
| **Appetite** | 20 minutes — from 2026-11-11 |
| **Status** | proposed |
| **Created / updated** | 2026-11-11 / 2026-11-11 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | none new: ruling R134 carries the design |
| **Canon** | none for the ledger `by` column: the basis is ruling R134 |
| **Paths** | `engine/ledger.py`, `engine/asks.py`, `engine/cardtool.py`, `engine/gate_lock.py`, `engine/mkway.py`, `README.md`, `tests/`, `cards/REGISTER.md`, `cards/MW-015-ledger-by/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository.

## 1. Goal

A default taken by a session (`mkway ask default`) wrote a ledger row labelled by=owner, because `ledger.add` had no `by`
argument. A session never writes the owner's words in the ledger — ruling R134.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | `ledger add` by a session | by=owner | `--by` defaults to `session:<session id>`, the id read from the one-use permit the lock gate leaves; the permit is used once | tests/test_mw015_ledger_by.py::test_the_default_by_of_a_session_is_its_session_id; tests/test_mw015_ledger_by.py::test_the_lock_gate_leaves_the_permit_for_the_ledger_and_default_commands |
| E2 | no permit | by=owner | by=`session:unknown` | tests/test_mw015_ledger_by.py::test_without_a_permit_the_by_is_session_unknown |
| E3 | the owner's terminal (no `CLAUDECODE`) | by=owner | by=`owner`; `--by <text>` taken as typed | tests/test_mw015_ledger_by.py::test_the_owners_terminal_writes_owner |
| E4 | a session passes `--by owner` | allowed | refused `ledger-by-owner`, «only the owner's terminal writes by=owner»; no row | tests/test_mw015_ledger_by.py::test_a_session_passing_by_owner_is_refused |
| E5 | `ask answered` | by=owner | by=`owner` (the owner's answer from the quote file) | tests/test_mw015_ledger_by.py::test_ask_answered_writes_owner |
| E6 | `ask default` | by=owner | by=`session:<session id>` (`session:unknown` with no permit), status default-taken | tests/test_mw015_ledger_by.py::test_ask_default_writes_the_session_and_default_taken |

## 8. Log

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-11 | red: rows E1 to E6 | 2323c49 | 7 tests red |
| 2026-11-11 | green: `--by`, `ledger.add(by=)`, by-permit in `cardtool` and `gate_lock`, `ask default`, README line | the commit that carries this line | targeted tests green |
| 2026-11-11 | `tests/test_mw008_ledger.py::test_ledger_add_appends_a_well_formed_row`: the by cell expected `owner` for a session's add, now `session:unknown` | the commit that carries this line | expectation only, as the rule changes it; no check removed |
| 2026-11-11 | whole suite, `python -m pytest`, term scan included | the commit that carries this line | 623 passed in 219 s (was 616 on the base); no term-scan exception added; the by cell fixed in two places of the one MW-008 test |
| 2026-11-11 | reading: «by=`session:<id>`» of `ask default` read as the session id, as in rule 1; the owner's terminal running `ask default` writes `owner`; the card-close ledger row (MW-011) is unchanged | — | to confirm |
