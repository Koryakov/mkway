# MW-020: Deliverables: built from tested code, compared with a named base

| | |
|---|---|
| **Appetite** | 2 hours — from 2026-11-11 |
| **Status** | proposed |
| **Created / updated** | 2026-11-11 / 2026-11-11 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | none new: the order of 2026-11-11 (card D) carries the design; each reading of it is a Log line |
| **Canon** | none for deliverables: the engine has no ledger; the basis is the order of 2026-11-11 and the check file of MW-019 |
| **Paths** | `engine/deliverables.py`, `engine/outbox.py`, `engine/cardtool.py`, `engine/startline.py`, `engine/mkway.py`, `engine/gate_lock.py`, `engine/defaults.json`, `engine/profile.schema.json`, `engine/profiles.py`, `engine/KEYS.md`, `README.md`, `CHANGELOG.md`, `tests/`, `cards/REGISTER.md`, `cards/MW-020-deliverables/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository. The release is `0.2.0` in the CHANGELOG; `VERSION` is not changed here. Parts: 1 keys; 2 `mkway built`;
3 `card close`; 4 `mkway delivered` and the `base:` line; 5 `mkway deliverables` and the start line; 6 README.

## 1. Goal

A result file is ready only when it exists at a named path, with its sha256, built on the final HEAD from code whose
tests passed; and a number that says «changed» or «now» names its base, a file that was delivered, never an internal
run. The engine makes both mechanical: `mkway built` records where a file came from and refuses a dirty or an untested
tree; `card close` refuses a deliverable that was not built from the current hash; the owner's `mkway delivered` keeps
the base; the check file of MW-019 names it in a `base:` line — order of 2026-11-11, card D.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | profile keys | no `deliverables` group | `deliverables.paths` and `deliverables.require_base` are in the schema (non-empty lists of non-empty strings); a bad value or an unknown key is refused; `profiles.deliverable_settings` gives two lists, empty for a missing or unusable value | tests/test_mw020_keys.py::test_the_schema_takes_the_two_deliverables_keys; tests/test_mw020_keys.py::test_the_accessor_defaults_to_none_and_tolerates_a_bad_value |
| E2 | KEYS lines | none | both keys are «in schema now» lines of the Added keys table with the default none and the card | tests/test_mw020_keys.py::test_keys_md_has_a_line_for_each_key_with_its_default |
| E3 | built, dirty | none | an uncommitted change in a tracked file (modified or staged) refuses `built-dirty`, names the file and the commit; an untracked file does not count; nothing is recorded | tests/test_mw020_built.py::test_built_is_refused_while_a_tracked_file_has_uncommitted_changes |
| E4 | built, untested | none | no green row of `commit_tests.jsonl` for HEAD's tree (none, red, another tree, an older tree) refuses `built-untested` and names the way | tests/test_mw020_built.py::test_built_is_refused_without_a_green_row_for_the_tree_of_head |
| E5 | built, provenance | none | a clean, green HEAD gives a row {path, sha256, head, tree, time, session} in `deliverables.jsonl` (session from the lock gate's permit, `owner` from the owner's terminal), the ledger row `built <path> <sha8> at <head8>`; a missing file is `built-no-file`; the lock gate lets a session run it and leaves the permit | tests/test_mw020_built.py::test_built_records_the_provenance_and_a_ledger_row; tests/test_mw020_built.py::test_a_file_that_is_not_there_is_refused_and_no_permit_is_left; tests/test_mw020_built.py::test_a_session_may_run_it_and_the_gate_issues_the_permit |
| E6 | card close | closes with no look at deliverables | an Acceptance row that names a path of `deliverables.paths` refuses `close-deliverable-unbuilt` unless a provenance row holds the file's current sha256 and its head is HEAD or an ancestor of HEAD; the text names `mkway built <path>`; rows that name no deliverable are not judged | tests/test_mw020_close.py::test_a_close_is_refused_while_a_named_deliverable_is_not_built; tests/test_mw020_close.py::test_a_close_goes_through_with_a_provenance_of_the_current_hash; tests/test_mw020_close.py::test_a_head_that_is_not_an_ancestor_of_head_is_refused; tests/test_mw020_close.py::test_rows_that_name_no_deliverable_are_not_judged |
| E7 | close, base | none | a named path of `deliverables.require_base` refuses `base-unknown` while its check file has no `base: <sha8>` line or names a sha8 no delivered row holds; the text names `mkway delivered` and the line | tests/test_mw020_close.py::test_a_path_that_requires_a_base_is_refused_until_a_delivered_base_is_named |
| E8 | delivered | none | the owner's `mkway delivered <path>` appends {path, sha256, time} to `delivered.jsonl` and keeps a copy at `<state>/delivered/<name>.<sha8>`, never overwriting an older copy; a session is refused `owner-only-command` by the command and by the lock gate; a missing file is `delivered-no-file` | tests/test_mw020_delivered.py::test_delivered_records_the_hash_and_keeps_a_copy; tests/test_mw020_delivered.py::test_a_session_never_delivers |
| E9 | `base:` line | none | the parser of MW-019 reads an optional line `base: <sha8>`; it must be the prefix of a delivered row, else the check is `unproven` and the problem names `base-unknown`; a wrong form is named | tests/test_mw020_delivered.py::test_the_optional_base_line_is_read_by_the_outbox_parser |
| E10 | base required | none | a file of `deliverables.require_base` under the outbox is `unproven` without a `base:` line and valid with a delivered one | tests/test_mw020_delivered.py::test_a_path_that_requires_a_base_is_unproven_without_one |
| E11 | board, start line | none | `mkway deliverables` lists path, sha8, state (built, changed, unbuilt) and delivered sha8; the start block says `deliverables: N built, M changed since built, K delivered` when the key is set | tests/test_mw020_board.py::test_the_deliverables_command_prints_a_row_per_file; tests/test_mw020_board.py::test_the_deliverables_command_without_keys_or_files; tests/test_mw020_board.py::test_the_start_block_counts_built_changed_and_delivered |
| E12 | README | no section | one section «Deliverables» with the keys, commands, files, reason ids, the rules and the bypass cases | tests/test_mw020_readme.py::test_one_section_with_a_body; tests/test_mw020_readme.py::test_the_section_names_every_reason_key_command_and_file; tests/test_mw020_readme.py::test_the_section_names_the_rules_behind_the_gates |

## 8. Log

One line per step. No re-run of a check or an agent round without a new input named in the Log row.

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-11 | W0: start checks each alone: `pwd` = the worktree, `git log --oneline -1` = 32850bb, `git status --short` empty. Card, register row and changelog row written by hand | the commit that carries this row | readings of the order, each decided without waiting: (a) all refusals are command checks (`mkway built`, `card close`), strict like MW-011 and MW-019: no new hook entry, so the manifest is unchanged; (b) the «tree hash» of a `commit_tests.jsonl` row is, as the commit gate writes it, the sha256 of `git ls-files -s -z`; MW-021's test rows use the git tree id; `built` accepts either form for HEAD; (c) the session of a provenance row is the lock gate's one-use permit (as MW-015), `owner` from the owner's terminal; (d) a `base:` line present on any check must name a delivered row (`base-unknown`), required for `deliverables.require_base` paths |
| 2026-11-11 | red: rows E1 to E12, `tests/_mw020.py` and six `tests/test_mw020_*.py` files | e22a7a1 | 22 tests red for the right reasons (no `deliverables` group, no `built`, `delivered` or `deliverables` command, no README section); 1 guard green before the code and kept green: `test_rows_that_name_no_deliverable_are_not_judged` |
| 2026-11-11 | green: `engine/deliverables.py`, the `base` line in `engine/defaults.json` read by `outbox.py` (`optional`, `base_values`, base problems in `inspect`), `profiles.deliverable_settings`, schema group `deliverables`, `mkway built`, `delivered`, `deliverables`, the owner-only `delivered` in `mkway.py` and `gate_lock.py`, the permit for `built`, `cardtool.unbuilt_deliverables` in both closes, the start line, KEYS.md rows, README section | the commit that carries this row | the 20 card tests and the README, schema, keys, manifest, start block, outbox and owner-only tests green (targeted run). Tests changed by this card, expectation only: `tests/test_keys.py` and `tests/test_schema.py` (the new key and group names). Readings: (e) a row of `commit_tests.jsonl` names its tree as the sha256 of the staged listing (`ls-files -s -z`, the commit gate), while MW-021's `last_green_tree` and tests read it as a git tree id; `built` accepts both, and MW-021's lookup finds no tree on rows the real gate writes (not changed here, found while reading); (f) a commit of tests alone writes no row, so `built-untested` names a commit that carries a change outside the test roots as the way to get one; (g) the deliverable files are found by a walk of the working tree like `rules.cards`, check files (`.check.md`) are never deliverables; (h) a `base:` line on any check must name a delivered row, required for `deliverables.require_base` paths |
| 2026-11-11 | whole suite on the green commit 4695207, `python -m pytest`, term scan included, run once at the end as ordered (this worktree has no commit-check record, so the commit itself ran no suite) | the commit that carries this row | 781 passed in 298 s (master 32850bb: 758, plus the 23 card tests); no term-scan exception added; `VERSION` not changed |
| 2026-11-11 | ported onto master efdf04c (which carries MW-018) by re-applying the card's changes by hand; no test changed beyond the two key and group lists, where master's entries are kept | the commit that carries this row | `python -m pytest`, term scan included: 819 passed in 296 s (master 796, plus the 23 card tests); no term-scan exception added |
