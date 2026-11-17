# MW-048: The owner's words can be recorded verbatim

| | |
|---|---|
| **Appetite** | 1 hour — from 2026-11-12 |
| **Status** | proposed |
| **Created / updated** | 2026-11-12 / 2026-11-12 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | none new: the lead's ruling carries it, quoted in the Goal |
| **Canon** | none for quoted arguments: the basis is the refusal `engine-call-not-plain` of a quote with an apostrophe and parentheses |
| **Paths** | `engine/`, `tests/`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-048-quoted-args/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository. `VERSION` is not changed here.

## 1. Goal

A lead's `ledger add --quote "Definitely no. We shouldn't. (10536)."` was refused `engine-call-not-plain`, and the
`--quote-file` route needs a write a lead may not make. The ruling: «the plain-call check judges the command's structure
outside quotes only: the content of a quoted argument is literal, both for bash and PowerShell quoting; `--quote-file`
accepts any path inside the bundle's asks folder as well; the refusal text names the fix: put the quote in a file under
mkway/asks and pass --quote-file.» Inside double quotes `$name`, `$(...)` and a backtick stay refused.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | a quote with an apostrophe, parentheses, `;`, `\|`, `>` inside double quotes (bash, PowerShell) or any text inside single quotes | `engine-call-not-plain` | allowed | tests/test_mw048_quoted_args.py::test_quoted_content_is_literal_and_allowed |
| E2 | a real chain, pipe or redirect outside quotes | refused | still `engine-call-not-plain` | tests/test_mw048_quoted_args.py::test_a_real_chain_outside_quotes_is_refused |
| E3 | `$(...)`, a backtick or `$name` inside double quotes | refused | still refused | tests/test_mw048_quoted_args.py::test_expansion_inside_double_quotes_stays_refused |
| E4 | the refusal text | no fix named | names mkway/asks, `--quote-file`, dollar sign or backtick | tests/test_mw048_quoted_args.py::test_the_refusal_names_the_fix |
| E5 | `--quote-file` under the asks or ledger folder | not limited | allowed | tests/test_mw048_quoted_args.py::test_quote_file_inside_asks_or_ledger_is_accepted |
| E6 | `--quote-file` elsewhere | not limited | refused `quote-file-outside` | tests/test_mw048_quoted_args.py::test_quote_file_outside_asks_and_ledger_is_refused |

## 8. Log

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-12 | red: rows E1 to E6 | 7643843 | 9 failed for the right reason (quoted content refused, no quote-file limit, no fix text); the first commit tries were refused by the session guard's message rule, not a lock |
| 2026-11-12 | e2e budget 90 -> 120 s: one more real-hook row; MW-051 (install hashes while copying) brings the install time down | the commit that carries this line | a time budget, not a behaviour assert; the row for `quote-file-outside` added to `tests/test_e2e_gates.py` (MW-039 reason-id rule) |
| 2026-11-12 | green: quoted words literal, fix text, `quote-file-outside` | the commit that carries this line | rows E1 to E6 green |
