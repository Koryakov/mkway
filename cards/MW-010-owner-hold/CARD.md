# MW-010: Owner hold

| | |
|---|---|
| **Appetite** | 1 hour — from 2026-11-10 |
| **Status** | proposed |
| **Created / updated** | 2026-11-10 / 2026-11-10 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | none new: the order of 2026-11-10 fixes the rules; each reading is a Log line |
| **Canon** | none for the hold: the engine has no ledger; the basis is the order of 2026-11-10 |
| **Paths** | `engine/`, `tests/`, `README.md`, `cards/REGISTER.md`, `cards/MW-010-owner-hold/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; `card new` could not run here (the engine repository has no
profile of its own), so the card and its register row are written by hand in the form `card new` writes: the
register row is `proposed`, and the owner's terminal opens and closes it.

## 1. Goal

«let the owner stop every session write and commit at once from his own terminal, and resume» — owner, 2026-11-10.
A profile lock target may declare `open_by_default: true`: it is open until the owner's `mkway lock close <name>`
writes a marker, and open again after `mkway lock open <name>` removes it. Both lock gates read the marker.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | flag in the schema | the key is invalid | `open_by_default` (boolean) is valid on a profile lock target; another type is invalid | tests/test_mw010_hold.py::test_schema_accepts_open_by_default_on_a_profile_target |
| E2 | flag on a built-in name | none | the schema check refuses it with a text naming the target, the flag and «built-in», for every built-in name | tests/test_mw010_hold.py::test_schema_refuses_open_by_default_on_a_built_in_name |
| E3 | no marker | every target closed until opened | the target is open: one edit and one commit pass | tests/test_mw010_hold.py::test_no_marker_lets_one_edit_and_one_commit_pass |
| E4 | marker | none | `lock close` writes it, `--minutes` ignored; edit and commit are refused with the lock text plus «hold by the owner; wait for the owner's word»; `lock open` removes it; a session cannot run either | tests/test_mw010_hold.py::test_a_marker_refuses_the_edit_and_the_commit_until_the_owner_opens |
| E5 | list and start block | none | `lock list` shows `hold: open (default)` or `hold: closed by the owner`; the start block's locks line counts the marker | tests/test_mw010_hold.py::test_lock_list_and_the_start_line_show_both_states |
| E6 | README recipe | none | section `## Owner hold`, 3-4 lines: the profile line, the two commands, what it stops and what it does not | tests/test_mw010_readme.py::test_the_readme_has_the_owner_hold_recipe |
| E7 | short forms | none | `mkway hold` = `lock close hold`, `mkway go` = `lock open hold`; a profile with no `hold` target gets a refusal naming «no hold target» and the profile line | tests/test_mw010_hold.py::test_hold_and_go_do_what_lock_close_and_open_do |
| E8 | short forms in a session | none | both are owner-only: the CLI refuses with `owner-only-command`, the lock gate refuses the shell call | tests/test_mw010_hold.py::test_hold_and_go_are_refused_inside_a_session |

## 8. Log

One line per step. No re-run of a check or an agent round without a new input named in the Log row.

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-10 | W0 | 7392d3c | card and register row written by hand (`proposed`). Start checks, each alone: `pwd` = <worktree>, HEAD 549cce1, status clean. Baseline 396 passed |
| 2026-11-10 | P1 | 7392d3c | red part 1 (E1-E5): five tests in `tests/test_mw010_hold.py`, all failing for the right reason (flag not in the schema, no marker logic) |
| 2026-11-10 | P1 | 2c61db2 | green part 1 (E1-E5): schema key `open_by_default` plus a built-in-name check in `schema_check` (`BUILT_IN_TARGETS`); `locks.py` marker logic (`lock close` writes it, `lock open` removes it); `lock close` takes `--minutes` and ignores it; refusal text «hold by the owner; wait for the owner's word»; `lock list` lines; start block locks line names a closed hold. Full suite: 401 passed. Readings: the marker is `locks/<name>.json` with state closed, no expiry; `BUILT_IN_TARGETS` is a literal list in `schema_check` (stdlib only), and E2 reads the names from `locks.built_in`, so a drift fails the test |
| 2026-11-10 | P2 | 9c4e16d | red part 2 (E6): `tests/test_mw010_readme.py` fails, no such section |
| 2026-11-10 | P2 | (this commit) | green part 2 (E6): README section «Owner hold» before «Known limits», 4 lines. Full suite with the term scan: 402 passed |
| 2026-11-10 | P3 | f3a66b2 | red part 3 (E7, E8), owner ruling R123: the two short-form tests fail, the commands do not exist. Row E6 not changed yet |
| 2026-11-10 | P3 | 50bc9c3 | red row E6 strengthened (no weakening): the recipe must name `mkway hold` and `mkway go` before the long forms; fails, README has only the long forms |
| 2026-11-10 | P3 | (this commit) | green part 3 (E6-E8): `hold` and `go` parsers in `engine/mkway.py` rewrite to `lock close hold` and `lock open hold` after the profile load; a profile with no open-by-default `hold` target is refused with «no hold target» and the profile line; both owner-only in the CLI (`_owner_only`) and in the lock gate (`_call`); README recipe shows the short forms first, still 4 lines. Full suite with the term scan: 404 passed. Reading: the missing-target refusal is folded into E7 (R123 asked for two tests) |
| 2026-11-10 | PORT | (this commit) | port of t8 onto master e02aa7e (MW-005 and MW-008 already in): source commits 549cce1..b5922e6 (7392d3c, 2c61db2, 9c4e16d, 5518ea7, f3a66b2, 50bc9c3, b5922e6) re-applied by editing; README, register, schema, mkway.py and startline.py carry both sides; the card and the two test files are as in t8, no test weakened. Targeted files 26 passed; full suite with the term scan: 460 passed |
