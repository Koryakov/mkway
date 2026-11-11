# <ID>: <title in plain words>

| | |
|---|---|
| **Appetite** | N days — the most this work is worth, from the creation date |
| **Status** | proposed |
| **Created / updated** | YYYY-MM-DD / YYYY-MM-DD |
| **Waiting for** | owner / us / nothing |
| **Form** | card |
| **Decisions** | <decision ids> — ids only, no text copied from the ledger; a commit that changes a test names one |
| **Canon** | `<ledger ids> — settles / does not settle: <at most 10 words>` or `none for <terms>`, after a ledger search |
| **Paths** | |

How to use: `mkway card new <title>` writes this file and the register row; the register's status is the one the
gates read. Paths: the files and folders the card may edit, in backticks, comma-separated; the owner's `card open`
records them. The header rows and the headings `1. Goal`, `Acceptance examples`, `8. Log` are read by the gates — keep them. A card that needs a new
decision stops and shows the owner example rows to choose from. More than 3 hours → split first. At most one page
before the log. Tests first: first Log row — red tests committed alone (the card's `tests/` folder only), the commit
id and the red run's output in its message; later row — the code commit, naming that commit id and the green run.
When two requirements contradict: `card set <id> waiting`, a Log line that names both, then the ask.
Test quality: Acceptance rows: one per rule clause of a computed value. The Test cell is a `; ` list of full node ids
(`tests/test_x.py::test_y`), or `checked by reading: <path>` naming the file read; nothing else.
C1 rows name real tests; C2 clause tested per row; C3 changed lines run; C4 independent expectation; C5 can fail.

## 1. Goal

«the owner's words, quoted» — owner, YYYY-MM-DD.

## Acceptance examples

Each row becomes a test; `card close` needs every row to name one.

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | item id | value today | value after the change | tests/test_x.py::test_y |

## 8. Log

One line per step. No re-run of a check or an agent round without a new input named in the Log row.

| Date | Step | Commit | Result |
|---|---|---|---|
