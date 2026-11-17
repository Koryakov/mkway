# MW-059: The topology refusal names the new-session route

| | |
|---|---|
| **Appetite** | 1 hour — from 2026-11-12 |
| **Status** | proposed |
| **Created / updated** | 2026-11-12 / 2026-11-12 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | none new: the lead's task carries it, quoted in the Goal |
| **Canon** | none: the basis is a real install where a lead ordered an idle session and the refusal named no way out |
| **Paths** | `engine/`, `tests/`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-059-topology-route/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository. `VERSION` is not changed here. The gate is not touched: no new rule, no new key; only the refusal text.

## 1. Goal

A lead sent an order to an idle session that holds no card; the refusal did not say what to do instead. The ruling:
«the gate stays exactly as it is. Only the refusal text changes when the target holds no card: order refused:
<session> holds no card. Start a new builder session with the order as its first prompt (mkcl), one card = one
session. Keep the existing text for the other refusal cases.» — the lead's task, 2026-11-12.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | the refusal text of an order from a lead to a target that holds no card; other targets and other kinds | the generic text for every case | the new-session text for that case only; the other cases keep the generic text | tests/test_mw059_topology_text.py::test_the_refusal_text_for_a_target_that_holds_no_card |
| E2 | the same order through the real hook | deny with the generic text | deny `message-topology` with the new-session text | tests/test_mw059_topology_text.py::test_an_order_to_an_idle_session_is_denied_with_the_new_route_through_the_real_hook |

## 8. Log

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-12 | red: rows E1 E2 | 6fc2698 | E1 (no-card order case) and E2 fail for the right reason: the generic text is shown |
| 2026-11-12 | green: the new text for an order to a target with no card; other cases keep their text | the commit that carries this line | rows E1 E2 green; red commit 6fc2698; whole suite python -m pytest: 1182 passed in 756.46 s |
