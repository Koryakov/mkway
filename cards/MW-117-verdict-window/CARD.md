# MW-117: a verdict is allowed any time after the red commit, held or not, until the card closes; a test or an Acceptance row edited after it makes it stale at close

| | |
|---|---|
| **Appetite** | 3 hours — from 2026-11-16 |
| **Status** | proposed |
| **Created / updated** | 2026-11-16 / 2026-11-16 |
| **Waiting for** | nothing |
| **Form** | card |
| **Decisions** | R272, R287, R263, MW117-D1, MW117-D2 — ids only, no text copied from the ledger; a commit that changes a test names one |
| **Canon** | none for the verdict window: the basis is rulings R272 G3 and R287 Q4 and the order of the operator |
| **Paths** | `engine/core_verdict_add.py`, `engine/verdict_add.py`, `engine/verdicts.py`, `engine/core_verdicts.py`, `engine/core.py`, `engine/cardtool.py`, `engine/gate_commit.py`, `engine/manifest.json`, `engine/concept.py`, `README.md`, `CHANGELOG.md`, `tests/core/test_mw117_verdict_window_core.py`, `tests/shell/test_mw117_verdict_window_shell.py`, `tests/test_mw117_docs.py`, `tests/core/test_verdict_add_decide.py`, `tests/test_mw113_command_e2e.py`, `tests/_mw080.py`, `tests/test_concept.py`, `cards/REGISTER.md`, `cards/MW-117-verdict-window/CARD.md` |

## 1. Goal

«we should have straight, simple as its possible mkway process - it should help work on tasks - not be as evil dog - it should be strong helper!» — owner, 2026-11-16 (R263). Order of the operator: ruling R272 G3 supersedes R194. Help it gives the task: a reader may judge the tests as soon as the red commit is made, while the builder still works the card, so the verdict is not the last thing waited for. Safety: the verdict stays bound to the test file (per node, from git, R253) and to the Acceptance rows of its node (sha256 of the engine-written extract, R287 Q4); an edit of either after the verdict makes it stale at close.

Never weaker: `verdict-card-state` keeps refusing a closed, a proposed and a waiting-owner card; it stops refusing only an open card that a builder holds (R272 G3 supersedes R194). `verdict-by-holder`, `verdict-by-committer`, `verdict-by-owner` stay. The red-proof row check is new, with its own id `verdict-no-red-proof`, way out: commit the red tests.

## Acceptance examples

Each row becomes a test; `card close` needs every row to name one. E22 is a pin: it passed before the code (the binding of MW-101, `verdicts._meaning_problem`).

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | an open card a builder holds, red-proof row present | `verdict-card-state`: no verdict while a builder holds the card | a reader that never held the card gives the verdict | tests/core/test_mw117_verdict_window_core.py::test_an_open_card_held_by_a_builder_with_a_red_proof_row_is_allowed |
| E2 | a waiting card, red-proof row present (nearest allow) | allowed | allowed | tests/core/test_mw117_verdict_window_core.py::test_a_waiting_card_with_a_red_proof_row_is_allowed |
| E3 | an open card with no red-proof row | allowed when released | refused `verdict-no-red-proof` | tests/core/test_mw117_verdict_window_core.py::test_an_open_card_with_no_red_proof_row_is_refused_no_red_proof |
| E4 | a waiting card with no red-proof row | allowed | refused `verdict-no-red-proof` | tests/core/test_mw117_verdict_window_core.py::test_a_waiting_card_with_no_red_proof_row_is_refused_no_red_proof |
| E5 | the text of `verdict-no-red-proof` | none | begins with the id and names the red commit of the card's tests as the way out | tests/core/test_mw117_verdict_window_core.py::test_the_no_red_proof_text_names_its_way_out |
| E6 | a closed card with a red-proof row (never weaker) | refused `verdict-card-state` | refused `verdict-card-state` | tests/core/test_mw117_verdict_window_core.py::test_a_closed_card_with_a_red_proof_row_is_still_refused_as_card_state |
| E7 | a proposed card with a red-proof row (never weaker) | refused `verdict-card-state` | refused `verdict-card-state` | tests/core/test_mw117_verdict_window_core.py::test_a_proposed_card_with_a_red_proof_row_is_still_refused_as_card_state |
| E8 | a waiting-owner card with a red-proof row (never weaker) | refused `verdict-card-state` | refused `verdict-card-state` | tests/core/test_mw117_verdict_window_core.py::test_a_waiting_owner_card_with_a_red_proof_row_is_still_refused_as_card_state |
| E9 | the card-state refusal text | says: waiting, or open with no holder | names the status and no longer a holder as the reason | tests/core/test_mw117_verdict_window_core.py::test_the_card_state_text_no_longer_names_a_holder_as_the_reason |
| E10 | the caller took the card once (never weaker) | refused `verdict-by-holder` | refused `verdict-by-holder` | tests/core/test_mw117_verdict_window_core.py::test_the_session_that_took_the_card_is_still_refused_as_by_holder |
| E11 | watch mode, no red-proof row | not a refusal | allowed and listed as watched | tests/core/test_mw117_verdict_window_core.py::test_in_watch_mode_a_missing_red_proof_row_is_allowed_and_listed |
| E12 | a red-proof row of a commit of HEAD | no such fact | fact `red_proven` true | tests/shell/test_mw117_verdict_window_shell.py::test_a_red_record_whose_tree_is_a_commit_of_head_reads_red_proven |
| E13 | no red-proof row for the card | no such fact | `red_proven` false | tests/shell/test_mw117_verdict_window_shell.py::test_a_card_with_no_red_record_reads_not_red_proven |
| E14 | a red-proof row of another card | no such fact | `red_proven` false | tests/shell/test_mw117_verdict_window_shell.py::test_a_red_record_of_another_card_reads_not_red_proven |
| E15 | a red-proof row whose tree is no commit of HEAD | no such fact | `red_proven` false | tests/shell/test_mw117_verdict_window_shell.py::test_a_red_record_whose_tree_is_no_commit_of_head_reads_not_red_proven |
| E16 | way out of `verdict-no-red-proof`: the red commit, the card still held | none | refused, then after the red-proof row the same call writes the row | tests/shell/test_mw117_verdict_window_shell.py::test_the_way_out_of_verdict_no_red_proof_is_the_red_commit |
| E17 | the Acceptance extract of one node | none | its row, cells trimmed, joined by a bar with spaces | tests/shell/test_mw117_verdict_window_shell.py::test_the_extract_of_a_node_is_its_acceptance_rows_as_one_text |
| E18 | a reworded Must-be cell | none | the extract of that node changes | tests/shell/test_mw117_verdict_window_shell.py::test_a_changed_must_be_cell_changes_the_extract_of_its_node |
| E19 | the row of another node reworded (nearest allow of E18) | none | the extract is the same | tests/shell/test_mw117_verdict_window_shell.py::test_a_change_in_the_row_of_another_node_leaves_the_extract_unchanged |
| E20 | extra spaces around the cells | none | the extract is the same | tests/shell/test_mw117_verdict_window_shell.py::test_extra_spaces_in_a_row_leave_the_extract_unchanged |
| E21 | the verdict-written record | no extract | `acceptance_sha`: {node: sha256 of that node's extract} | tests/shell/test_mw117_verdict_window_shell.py::test_the_add_record_holds_the_sha256_of_each_nodes_extract |
| E22 | a test edited after the verdict, at close (a pin: the binding of MW-101 already refuses it) | unproven | unproven, names the node | tests/shell/test_mw117_verdict_window_shell.py::test_a_test_edited_after_the_verdict_is_stale_at_close |
| E23 | an Acceptance row of the node changed after the verdict, at close | the verdict holds | `verdict-stale`, names the node and says Acceptance | tests/shell/test_mw117_verdict_window_shell.py::test_an_acceptance_row_changed_after_the_verdict_is_verdict_stale_and_names_the_node |
| E24 | the Acceptance rows unchanged (nearest allow of E23) | proven | proven | tests/shell/test_mw117_verdict_window_shell.py::test_an_unchanged_acceptance_row_leaves_the_verdict_proven |
| E25 | the row of another node changed | proven | proven | tests/shell/test_mw117_verdict_window_shell.py::test_a_change_in_the_acceptance_row_of_another_node_leaves_the_verdict_proven |
| E26 | a record written before this card (no `acceptance_sha`) | proven | proven: nothing to compare, never guessed (named gap) | tests/shell/test_mw117_verdict_window_shell.py::test_a_record_with_no_acceptance_sha_is_not_judged_by_the_extract |
| E27 | a caller that passes no card text | proven | proven (the extract is not judged) | tests/shell/test_mw117_verdict_window_shell.py::test_no_card_text_skips_the_acceptance_binding |
| E28 | the close, Acceptance change | id `verdict-unproven` | id `verdict-stale` | tests/core/test_mw117_verdict_window_core.py::test_the_close_refuses_an_acceptance_change_with_the_id_verdict_stale |
| E29 | the close, any other unproven row (nearest allow of E28) | `verdict-unproven` | `verdict-unproven` | tests/core/test_mw117_verdict_window_core.py::test_the_close_keeps_the_id_verdict_unproven_for_any_other_why |
| E30 | the commit gate, Acceptance change | id `verdict-unproven` | id `verdict-stale` | tests/core/test_mw117_verdict_window_core.py::test_the_commit_refuses_an_acceptance_change_with_the_id_verdict_stale |
| E31 | the commit gate, any other unproven row (nearest allow of E30) | `verdict-unproven` | `verdict-unproven` | tests/core/test_mw117_verdict_window_core.py::test_the_commit_keeps_the_id_verdict_unproven_for_any_other_why |
| E32 | way out of `verdict-card-state` through the real command and hooks: a proposed card is opened (MW117-D1, replaces the old way out: a card with no holder) | release the holder | opening the card lets the same call write the row | tests/test_mw113_command_e2e.py::test_the_way_out_of_verdict_card_state_is_opening_a_proposed_card |
| E33 | the old row: an open card with a holder is refused (MW117-D1) | refused | allowed after the red commit | tests/core/test_verdict_add_decide.py::test_an_open_card_with_a_holder_is_allowed_after_the_red_commit |
| E34 | register, changelog, card folder | none | the row and the line | tests/test_mw117_docs.py::test_register_changelog_and_card_name_the_card |
| E35 | README verdict-timing sentence | waiting, or open with no holder | names the window and `verdict-no-red-proof` | tests/test_mw117_docs.py::test_the_readme_states_the_window_and_the_new_refusal |
| E36 | manifest `commit_files` | `verdict-unproven` only | also `verdict-stale` | tests/test_mw117_docs.py::test_the_manifest_lists_verdict_stale_for_the_commit_gate |
| E37 | the real commit hook, an orderer commits a verdict file after the Acceptance row of its node changed | `verdict-unproven` or allow | deny `verdict-stale`, names the node | tests/test_mw102_e2e.py::test_the_orderer_commits_a_verdict_whose_acceptance_row_changed_and_the_real_hook_denies_verdict_stale |

## 8. Log

One line per step. No re-run of a check or an agent round without a new input named in the Log row.

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-16 | start: step 0 (folder, branch t137, base 6c3b48b, clean); the binding that makes a verdict stale when the test file changes read in code | 6c3b48b | `verdicts._meaning_problem` (MW-101, R253), called from `_row_problem` at close; the ruling cites verdicts.py:127-136, which is `committers_of`; the red-proof check is not in the code at HEAD, so `verdict-no-red-proof` is new (decision MW117-D1); files added by MW117-D2 |
| 2026-11-16 | red commit, tests only: the new core, shell and docs tests, the two HEAD tests of MW117-D1 changed, the setup helper of tests/_mw080.py seeds the red-proof row (`red=False` leaves none) | 038eef2 | first run of the two new test files: 29 failed, 2 passed (the 2 passed are the nearest allows of E29 and E31); every new id red for a missing field, keyword or function. E22 (test edited after the verdict) was changed to call the close proof without the new keyword and passed before any engine change: it is a PIN, not a red test (CORRECTIONS 2). Not weakened: no refusal assert is removed |
| 2026-11-16 | second tests-only commit: the commit_files reason set gains `verdict-stale`, the add reason set gains `verdict-no-red-proof`, the add budget facts carry `red_proven` true (all under MW117-D1 and MW117-D2; sets only grow) | a2ce340 | red against the engine of 038eef2: found by the first run of the run set (15 failed, 3 errors) |
| 2026-11-16 | third tests-only commit: tests/test_mw102_e2e.py seeds the red-proof row in its setup (3 setup errors of the first run) and gains E37, the real hook denies `verdict-stale`; tests/test_e2e_gates.py names `verdict-stale` in its exemption table with the test that shows it | e251959 | E37 red at that commit |
| 2026-11-16 | engine commit: `core_verdict_add.py` (Facts `red_proven`, Node `acceptance`, new refusal `verdict-no-red-proof`, card state allows waiting and open whether held or not), `verdict_add.py` (the red-proof fact from `red_proof.jsonl`, `acceptance_sha` in the record), `verdicts.py` (`acceptance_extract`, `acceptance_sha`, `_acceptance_problem`, optional `card_text`), `core_verdicts.py` and `core.py` (a why that begins `verdict-stale:` gives the id `verdict-stale` at close and at commit; core.py named here as MW117-D2 accepted), `cardtool.py` and `gate_commit.py` (one argument each: the card text), `manifest.json` (`verdict-stale` in commit_files), `concept.py` (row `verdict-no-red-proof` with its way-out test, row `verdict-card-state` way out now E32), README, CHANGELOG | this commit | recut is not touched (CORRECTIONS 4) |
| 2026-11-16 | never-weaker (CORRECTIONS 5): `verdict-card-state` still refuses a closed, a proposed and a waiting-owner card (E6 to E8); it stops refusing only an open card that a builder holds, because R272 G3 supersedes R194. A card with no red-proof row, before: allowed when waiting; now refused `verdict-no-red-proof` (a new refusal, stricter). `verdict-by-holder`, `verdict-by-committer`, `verdict-by-owner` unchanged (E10). The binding of a verdict to the test file is the existing MW-101 binding (`verdicts._meaning_problem`); a sibling test edited in the same file stays fresh by design | this commit | named gap: a record written before this card has no `acceptance_sha` and its Acceptance rows are not compared (E26) |
| 2026-11-16 | case map: two renamed rows named in case_map.md of this card (the rows of MW-080 and MW-113 keep their text, those cards are not edited) | this commit | tests/test_meta_cards.py passes |
| 2026-11-16 | run set, -n 2: tests/core, tests/shell, test_concept, every test_mw*_docs, test_keys, test_meta_cards, test_register, test_repo_scan, test_install, test_mw029_fast_guard and the verdict e2e files, term scan inside test_repo_scan | this commit | first run 4563 passed, 15 failed, 3 errors, 854 s (add budget setup, two reason sets, two card rows that name renamed tests, 3 setup errors of test_mw102_e2e); second run after the fixes 4578 passed, 3 errors, 868 s (the errors: test_mw102_e2e setup); then test_mw102_e2e 4 passed, and test_e2e_gates, test_mw107_owner_meta, test_mw068*, test_mw071* 154 passed, 1 failed (the exemption table), fixed, 1 passed. The last full run was before the E37 and exemption commit; the files those two commits touch were re-run on their own |
