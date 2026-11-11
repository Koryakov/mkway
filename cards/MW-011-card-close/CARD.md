# MW-011: Card close by the one who ordered it

| | |
|---|---|
| **Appetite** | 2 hours — from 2026-11-10 |
| **Status** | proposed |
| **Created / updated** | 2026-11-10 / 2026-11-10 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | none new: the order of 2026-11-10 carries every rule; each reading of it is a Log line |
| **Canon** | none for the close rule: the engine has no ledger; the basis is the order of 2026-11-10 |
| **Paths** | `engine/`, `tests/`, `README.md`, `cards/REGISTER.md`, `cards/MW-011-card-close/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; `card new` could not run here (the engine repository has no
profile of its own), so the card and its register row are written by hand in the form `card new` writes. The register
row is `proposed`; the owner's terminal opens and closes it. Parts: 1 the `Ordered by` column, `give`, `sessions`;
2 the close by the orderer; 3 README, KEYS and usage texts; 4 the ledger row (needs `engine/ledger.py`, card MW-008).

## 1. Goal

The owner's rule (paraphrased in English; the engine repository is English only): a session may write to the session
that did the work and agree it itself, because the owner's attention is not enough. So a card is closed by the session
that ordered it, never by the one that holds it. `Ordered by` is a sixth register column (inside the seal); `mkway
give` and `mkway sessions` are the owner's commands; `cards.approver: orderer` lets the orderer's `card close` pass
when it is not the holder, the card is open or waiting, and every Acceptance row's test passes now. Default stays
`owner-only`.

## Acceptance examples

Rows are added with the red tests of each part.

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | column sealed and read | five columns | with `cards.approver: orderer` the register has `Ordered by`; an owner card reads `owner`; a hand edit of a cell is `register-tampered` | tests/test_mw011_orderer.py::test_ordered_by_column_is_sealed_and_read |
| E2 | sixth name from the profile | `register.columns` takes five names | a sixth name replaces the default `Ordered by` | tests/test_mw011_orderer.py::test_the_sixth_column_name_comes_from_the_profile |
| E3 | register without the column | none | reads every card as `owner`, no migration by a write; `card resync --add-ordered-by` (owner only) adds the column and reseals | tests/test_mw011_orderer.py::test_a_register_without_the_column_reads_owner_and_resync_adds_it |
| E4 | `card new` records who | no such cell | a session's `card new` writes the hook input's session id through the `post` group, the owner's terminal writes `owner` | tests/test_mw011_orderer.py::test_card_new_writes_the_session_id_or_owner |
| E5 | sub-agent shape | none | the payload's `session_id` is the one written, never the agent id; no `session_id` writes none | tests/test_mw011_orderer.py::test_a_sub_agent_is_its_session_id_as_the_hook_input_gives_it |
| E6 | `give` | none | sets the cell by a prefix of one seen id, a bare number uses the card prefix, `owner` takes the card back | tests/test_mw011_orderer.py::test_give_sets_the_cell_by_a_prefix_a_bare_number_or_owner |
| E7 | `give` refusals | none | an ambiguous prefix is `give-ambiguous` with the candidates, an unknown one `give-unknown`, «not established» is no candidate | tests/test_mw011_orderer.py::test_give_refuses_an_ambiguous_or_unknown_prefix_and_names_the_candidates |
| E8 | `give` is the owner's | none | a session's `give` is `owner-only-command` at the gate and at the CLI | tests/test_mw011_orderer.py::test_give_is_the_owners_command |
| E9 | `give` needs the column | none | `give-no-column`, naming the owner's way out | tests/test_mw011_orderer.py::test_give_needs_the_column |
| E10 | `sessions` | none | every seen id with last seen, the card held, the cards ordered; read-only; rows with no id counted as «not established» | tests/test_mw011_orderer.py::test_sessions_lists_ids_with_cards_held_and_ordered |
| E11 | close by the orderer | the owner's terminal only | with `cards.approver: orderer` the orderer, not the holder, closes an open card whose tests pass; status `closed`, a Log row «closed by <id>; ordered by <value>», a session record, the start block's card changes show it | tests/test_mw011_close.py::test_the_orderer_closes_a_card_it_does_not_hold |
| E12 | holder and third session | none | the orderer that holds the card: `close-by-holder`; the holder that did not order it, or a third session: `close-not-orderer`; each names the way out | tests/test_mw011_close.py::test_the_holder_never_closes_its_own_work |
| E13 | tests must pass | none | a red or missing test named by an Acceptance row is `close-tests-failing`; `checked by reading` rows run nothing | tests/test_mw011_close.py::test_a_failing_or_missing_test_refuses_the_close |
| E14 | tests run at the close | none | the same card is refused while a test is red and closes once it passes | tests/test_mw011_close.py::test_the_tests_run_when_the_close_runs_not_when_the_card_was_written |
| E15 | owner-ordered card | none | refused to every session until the owner gives it; the owner's terminal still closes it | tests/test_mw011_close.py::test_an_owner_ordered_card_closes_only_in_the_owners_terminal_until_given |
| E16 | status | none | `open` and `waiting` close; `proposed`, `waiting-owner`, `closed` are `card-bad-move` | tests/test_mw011_close.py::test_only_an_open_or_waiting_card_closes_by_its_orderer |
| E17 | the CLI decides again | none | no permit, an expired one, one for another card, one naming a non-orderer or the holder: refused; a permit is used once | tests/test_mw011_close.py::test_the_cli_decides_again_with_the_session_the_permit_names |
| E18 | no second door, default unchanged | `card set <id> closed` owner-only | still owner-only with `orderer`, in light mode too; default approver `owner-only` unchanged | tests/test_mw011_close.py::test_a_session_never_sets_closed_and_the_default_stays_owner_only |
| E19 | session id of the hook input | none | no `session_id` is never the orderer; a sub-agent is its `session_id` beside its `agent_id` | tests/test_mw011_close.py::test_the_gate_reads_the_session_id_of_the_hook_input |
| E20 | reasons declared | none | the lock gate's shell entry declares `close-not-orderer` and `close-by-holder` | tests/test_mw011_close.py::test_the_new_reasons_are_declared_in_the_manifest |
| E21 | README section | none | one section `## Closing cards`, with a body | tests/test_mw011_readme.py::test_the_readme_has_one_section_closing_cards |
| E22 | what the section states | none | who may close, the two owner commands, the sixth column and its resync, the three refusals, the default `owner-only` | tests/test_mw011_readme.py::test_the_section_states_who_may_close_the_commands_and_the_default |
| E23 | KEYS lines | `owner-only` only; five columns | `cards.approver` names both values and the default; `register.columns` names the sixth column | tests/test_mw011_readme.py::test_keys_md_lines_state_the_orderer_and_the_sixth_column |
| E24 | usage texts | no `give`, `sessions` | the module usage and the parser help name them and `--add-ordered-by` | tests/test_mw011_readme.py::test_the_usage_texts_name_the_new_commands |
| E25 | ledger row | no ledger row at a close | a successful close by the orderer also writes one ledger row for the card with the Log row's text; a refused close writes none | tests/test_mw011_ledger.py::test_a_close_by_the_orderer_also_writes_a_ledger_row |

## 8. Log

One line per step. No re-run of a check or an agent round without a new input named in the Log row.

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-10 | W0 | 9384984 | card and register row written by hand. Start checks, each alone: `pwd` = <worktree>, HEAD 81036c5, `git status --short` empty. `engine/ledger.py` is not in the tree (card MW-008 is not on this base): part 4 stops there. Readings of the order, each decided without waiting: (a) the engine's own `cards/REGISTER.md` keeps its four columns, this repository has no profile; (b) the sixth column is written only when the profile names six columns or `cards.approver` is `orderer`, or the register already has it, so every existing test keeps its register shape; (c) a session cannot know its own id, so `card new` writes the cell in the `post` group from the hook input, after the nonce proves the command; a failed or unseen write leaves `owner`, the safe side |
| 2026-11-10 | P1 | 9384984 | red part 1 (E1-E10): `tests/test_mw011_orderer.py`; ten tests fail for the right reason: no sixth column, no `ordered` key, no `give` or `sessions` command. Full suite not run for a red commit |
| 2026-11-10 | P1 | (this commit) | green part 1 (E1-E10): `register.py` (sixth column, `ordered` key read as `owner`, `set_ordered`, `reseal --add-orderer`), `cardtool.py` (`approver`, `seen_sessions`, `resolve_session`, `give`), `mkway.py` (`give`, `sessions`, `card resync --add-ordered-by`, `give` in the tripwire), `gate_lock.py` and `helpers.py` (`give` is owner-only and an engine call), `gate_records.py` (the `post` group writes the cell after a session's `card new`), schema (`approver` takes `orderer`, `register.columns` takes five or six). Test fixes found at green, none weakening: E8 first listed the spellings `mkway give` and `bash -c ...`, which the plain-form rule already refuses as `engine-call-not-plain` before the owner-only rule (my slip); they became `py -3 ...` and `cd ... && python mkway.py give ...`, the spellings the existing owner-only test uses. Targeted (orderer, schema, keys, start keys, card moves, cards, lock, helpers, close-fix 1, install seal, profile): 87 passed. Whole suite: 426 passed, 1 failed (`test_install.py::test_check_runs_the_term_scan_when_a_term_file_is_set`): the installed copy runs the copied tests, and my untracked part 2 red file (10 red tests, written while the run was going) was in the copy; the same ten tests fail on their own. The install test is run again with the green of part 2 |
| 2026-11-10 | P1 | 913009c | the «(this commit)» row above is 913009c |
| 2026-11-10 | P2 | 5f783a3 | red part 2 (E11-E20): `tests/test_mw011_close.py`. Design reading: only the hook knows the session id, so the lock gate checks the orderer and the holder and leaves a one-use permit (`<state.dir>/permits/`, 120 s) naming the session; the CLI reads it, checks again with that id, runs the named tests, closes. `card set <id> closed` stays owner-only. The ten tests fail for the right reason: no permit, no new reasons, the CLI refuses a session's `card close` as owner-only. Full suite not run for a red commit |
| 2026-11-10 | P2 | (this commit) | green part 2 (E11-E20): `cardtool.py` (permit: `issue_close_permit`, `take_close_permit`; `orderer_problem`; `test_nodes`, `tests_problem` run `python -m pytest -q <ids>` in the root, restricted environment, 600 s; `append_log_row`; `move(..., closer, state)`), `gate_lock.py` (`_close_by_orderer`; `card set <id> closed` owner-only under `orderer`), `mkway.py` (the permit path of `_move`, the tripwire), manifest (`close-not-orderer`, `close-by-holder` declared). Readings of the order: (a) the gate checks orderer and holder, the CLI checks everything again with the permit's session id and runs the tests, so a hook timeout never limits a test run; (b) `orderer` also holds in light mode; (c) the orderer's close of a card that nobody holds passes; (d) a node id the run prints with a backslash is shown with `/` (found at green: E13 read the Windows form); (e) the permit is read from the state folder, never from the command line. No test changed. Targeted (eleven files): 169 passed. Whole suite with the term scan: 437 passed |
| 2026-11-10 | P2 | 0f09424 | the «(this commit)» row above is 0f09424 |
| 2026-11-10 | P3 | c868f6b | red part 3 (E21-E24): `tests/test_mw011_readme.py`; four tests fail for the right reason: no README section, KEYS lines without `orderer` and the sixth column, usage text without `give` and `sessions`. Full suite not run for a red commit |
| 2026-11-10 | P3 | 51e8ad8 | green part 3 (E21-E24): README section «Closing cards» before «Method» (and item 3 of «Moving cards» now names `orderer`), the `cards.approver` and `register.columns` lines of KEYS.md (no new key: the schema leaves are unchanged), the usage lines and docstring of `mkway.py`. No test changed. Targeted (nine doc and scan files): 33 passed. Whole suite with the term scan: 441 passed, run once for parts 1 to 3 as ordered (the whole suite also ran at the green of parts 1 and 2: 426 with the one explained failure, then 437) |
| 2026-11-10 | PORT | 6f77b1d | port of t9 onto master 4fa3622: source commits 81036c5..8d515b6 (9384984, 913009c, 5f783a3, 0f09424, c868f6b, 51e8ad8, 8d515b6) re-applied by editing, both sides kept: `gate_lock.py` keeps master's `hold` and `go` beside `give`; `mkway.py`, README, KEYS, schema, manifest and the register keep master's content beside the MW-011 content; the three test files and the card brought as they were. Whole suite with the term scan: 517 passed |
| 2026-11-10 | P4 | 052b2a7 | red row E25: `tests/test_mw011_ledger.py`; fails for the right reason: no ledger row after a close. Full suite not run for a red commit |
| 2026-11-10 | P4 | (green commit, the one that carries this row) | green E25: `cardtool.move` writes one ledger row through `engine/ledger.py` after the Log row, same text «closed by <session id>; ordered by <value>», topic `card close`; a refused close writes none. Reading: the row goes after the Log row, so a failed ledger write is the same `close-log-failed` refusal text path. Targeted (ledger, close, mw008 ledger): 18 passed. Whole suite with the term scan: run once before this commit, result in the commit message |
| 2026-11-10 | P4 | superseded | the next row, written when `engine/ledger.py` was not on the base, is replaced by the two rows above: ledger row: done in the port onto master. `engine/ledger.py` (card MW-008) is not on this base (checked: no `ledger*.py` in the tree), so rule 5's ledger row is not built here, by the order; the Log row «closed by <session id>; ordered by <value>» and the start block's card changes are built and tested (E11) |
