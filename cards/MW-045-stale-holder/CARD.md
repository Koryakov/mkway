# MW-045: A crashed card holder never blocks the root

| | |
|---|---|
| **Appetite** | 1 hour — from 2026-11-12 |
| **Status** | proposed |
| **Created / updated** | 2026-11-12 / 2026-11-12 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | none new: the lead's ruling on stale holders carries it, quoted in the Goal |
| **Canon** | none for stale holders: the basis is the gap `take-root-busy` (MW-034) leaves when a holder crashes |
| **Paths** | `engine/`, `tests/`, `README.md`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-045-stale-holder/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository. `VERSION` is not changed here.

## 1. Goal

MW-034's `take-root-busy` refuses a take while another session holds an open card in the root. A holder that crashed
never releases, so the root stays busy for good. The ruling: «both ways, logged: `card release <id>` by the owner or by
the card's orderer (the lead, as every orderer move), and an automatic release at take time when the holder's last_seen
is older than `cards.stale_hours` (default 4, the same figure as leads.escalate_hours), with a row «stale holder <id>
released» in the card Log.» A holder with no row in `sessions.jsonl` counts as stale only when its hold is older than
the same hours. The refusal text of `take-root-busy` names both ways out.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | the owner's terminal `card release <id>` of a card a session holds | refused `card-not-yours`, only `--force` freed it | frees it: no holder, an owner `release` record, a Log row naming the owner; `--force` still frees it | tests/test_mw045_stale_holder.py::test_the_owners_terminal_release_frees_a_held_card |
| E2 | a session that ordered the card runs `card release <id>` | `card-not-yours` | the gate leaves a permit, the CLI frees the card: no holder, a `release` record by `orderer` naming that session, a Log row naming the orderer | tests/test_mw045_stale_holder.py::test_the_orderer_session_releases_the_card_another_session_holds |
| E3 | a third session (not the holder, not the orderer) runs `card release <id>` | `card-not-yours` | still `card-not-yours`, the message names the orderer and the owner's way; the holder stays | tests/test_mw045_stale_holder.py::test_a_third_session_cannot_release_the_card |
| E4 | a take while the holder's last seen is older than `cards.stale_hours` | `take-root-busy` for good | the gate allows; the CLI releases the holder first (record by `stale`), writes the Log row `stale holder <8 characters> released`, then the take goes on | tests/test_mw045_stale_holder.py::test_a_stale_holder_is_released_at_take_with_a_log_row |
| E5 | a take while the holder is fresh | `take-root-busy` | still `take-root-busy`; the text names `card release <card>` by the owner or the orderer and the automatic release after `cards.stale_hours`; nothing is released | tests/test_mw045_stale_holder.py::test_a_fresh_holder_still_refuses_and_the_text_names_both_ways_out |
| E6 | `cards.stale_hours` | no key | the key sets the hours: a holder last seen 2 h ago is fresh at the default 4 and stale at 1 | tests/test_mw045_stale_holder.py::test_the_key_changes_the_hours |
| E7 | a holder with no `sessions.jsonl` row | not read | stale only when its take record is older than the hours; a recent take is fresh | tests/test_mw045_stale_holder.py::test_a_holder_with_no_sessions_row_is_stale_only_by_its_hold_time |
| E8 | schema, accessor, KEYS.md | none | `cards.stale_hours` (a number above 0, default 4; an unusable value reads as 4) in the schema, `profiles.cards_stale_hours` and a KEYS.md row | tests/test_mw045_stale_holder.py::test_the_key_is_in_the_schema_the_accessor_and_keys_md |
| E9 | README, register, changelog | the busy-root text named no automatic way out | README names `card release` by the owner or the orderer and the stale release; register row; a line under the release that names the card; VERSION: see VERSION | tests/test_mw045_stale_holder.py::test_readme_register_changelog_and_card_name_the_card |

## 8. Log

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-12 | red: rows E1 to E9 | 0c88fb5 | 10 failed for the right reason (a plain owner release refused, the orderer refused, no stale release, no key, no docs); the older test L1 of MW-003 (the owner's plain release needs `--force`) changed to the new rule, `--force` still tested |
| 2026-11-12 | green: `cards.stale_hours`, orderer release by permit, stale release at take, refusal text, README, register, changelog | the commit that carries this line | rows E1 to E9 green; whole suite, `python -m pytest`, term scan included, no exception added: 931 passed in 601 s. The ledger row of a release is its record row (`by` `owner`, `orderer` or `stale`), as every card move; the Log row names the 8-character id |
| 2026-11-12 | MW-040: row E9 named a release number or an old VERSION | the commit that carries this line | the row says «see VERSION» and «the release that names the card»; its test reads the VERSION file and finds the card's changelog line (`tests/_docs.py`), no release number is pinned |
