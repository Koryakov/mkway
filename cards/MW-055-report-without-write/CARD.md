# MW-055: A session whose writes are refused can still report

| | |
|---|---|
| **Appetite** | 1 hour 30 minutes — from 2026-11-12 |
| **Status** | proposed |
| **Created / updated** | 2026-11-12 / 2026-11-12 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | none new: the lead's task carries it, quoted in the Goal |
| **Canon** | none: the basis is a real install where a builder whose every Write was refused could not tell its lead |
| **Paths** | `engine/`, `tests/`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-055-report-without-write/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository. `VERSION` is not changed here.

## 1. Goal

A builder whose every Write was refused could not tell its lead: `SendMessage` was refused `message-not-in-inbox`
(it carries only the ping line of a message the session wrote), and `mkway send` needed a body file the builder could not
write. The ruling: «`mkway send <to> --text "<body>"`: the CLI writes the message into the inbox itself, the same record
as a body-file send, and prints the ping line. The text is literal under the quoted-argument rules of MW-048; a body with
`$(...)`, a backtick or `$name` is refused with a pointer to the file route. The message gate accepts that ping line
exactly as for a body-file send; nothing else changes in the gate. The refusal texts of the subtask gate and of
`message-not-in-inbox` name this route in one short clause.»

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | which texts the CLI takes as literal | no `--text` | plain words, apostrophe, parentheses, `;`, `\|`, `>`, a lone `$`: taken; `$(...)`, backtick, `$name`, `${name}`, `$1`: refused | tests/test_mw055_send_text.py::test_the_text_decision_table |
| E2 | `send --text` | no such option | the same inbox row as a body-file send; the ping line is printed alone on a line | tests/test_mw055_send_text.py::test_send_text_writes_the_same_row_as_a_body_file |
| E3 | `send --text` with expansion in it | n/a | refused `message-text-unsafe`, naming `--file`; no row written | tests/test_mw055_send_text.py::test_a_text_with_expansion_is_refused_and_names_the_file_route |
| E4 | `--file` and `--text` | `--file` required | exactly one of them; both or none is a usage error | tests/test_mw055_send_text.py::test_exactly_one_of_file_and_text |
| E5 | refusal texts | the route is not named | the subtask gate (`no-open-card`, `card-not-open`) and `message-not-in-inbox` name `--text` | tests/test_mw055_send_text.py::test_the_refusal_texts_name_the_text_route |
| E6 | the ping line of a `--text` send, through the message gate | n/a | allowed, as for a body-file send | tests/test_mw055_send_text.py::test_the_ping_line_of_a_text_send_passes_the_message_gate |
| E7 | a session with no card, through the real hook: `send --text`, then SendMessage with the ping line | n/a | both allowed | tests/test_e2e_gates.py::test_allow_through_the_real_hook[allow_text_send_then_ping] |

## 8. Log

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-12 | red: rows E1 to E7 | d4aba3b | 14 new rows failed for the right reason (no `text_problem`, no `--text`, no route in the refusal texts) |
| 2026-11-12 | green: `send --text`, `message-text-unsafe`, the route clause in the subtask and message refusals; the e2e row E7 | the commit that carries this line | rows E1 to E7 green; whole suite `python -m pytest`: 1097 passed in 749.71 s |
| 2026-11-12 | the task names `--quote-file` as the pointer; `send` has no such option (it belongs to `ledger`), so the refusal points to `--file`, the body-file route of `send` | the commit that carries this line | a wording choice, no behaviour change |
