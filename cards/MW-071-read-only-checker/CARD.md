# MW-071: The blind verdict checker is a read-only reader, never critic

| | |
|---|---|
| **Appetite** | 2 hours — from 2026-11-12 |
| **Status** | proposed |
| **Created / updated** | 2026-11-12 / 2026-11-12 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | R180, R181 |
| **Canon** | none: the basis is the owner's rule of 2026-09-26 that forbids critic agents, and the approval of 2026-11-04 of a reader with a file list |
| **Paths** | `engine/core_verdicts.py`, `engine/verdicts.py`, `engine/core_install.py`, `tests/`, `README.md`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-071-read-only-checker/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository. `VERSION` is not changed here. The decision is pure (`core_verdicts.decide` reads one `Checker` fact per
configured checker: name, tools list or none, found flag); the shell (`engine/verdicts.py`) finds the agent definition
and reads its `tools:` line. The outbox board (`engine/outbox.py`) is not touched.

## 1. Goal

«Never «critic»: the default checker is the blind reader type the owner approved on 04.11 (the owner's yes to a reader
with a file list): fresh-reader, Sonnet, effort medium, tools Read and Grep only, allowlist = the test file, the card, the
criteria; one run per card close, no rounds; a second run only on the lead's word. Add one engine check: a configured
checker whose agent definition lists any tool beyond Read and Grep is refused (checker-not-read-only), keyed on the agent
file's tools line. Change the fresh-install default to that type and name it in the dedup recipe.» — ruling R180.

Addition, ruling R181: inputs of the checker are the test file, the card and the criteria file, never the code; at most
two runs per card (a third is refused `verdict-runs-exceeded`); verdict rows only for the nodes new or changed in the
card's own commits; the run count is in the engine record, the token count in the card's Log row.

## Acceptance examples

Each row becomes a test; `card close` needs every row to name one. Rows E1 to E9 are the pure core table, E10 to E15 run
on real files, E16 and E17 run the real close command, E18 and E19 are the fresh-install default, E20 is the README.

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | a checker whose tools are Read, Grep | not judged | allowed | tests/core/test_checker_read_only.py::test_a_checker_that_lists_read_and_grep_is_allowed |
| E2 | a checker whose tools are Read only (nearest allow of E3) | not judged | allowed | tests/core/test_checker_read_only.py::test_a_checker_that_lists_read_only_is_allowed |
| E3 | a checker whose tools are Read, Grep, Bash | allowed | refused `checker-not-read-only` | tests/core/test_checker_read_only.py::test_a_checker_that_lists_bash_is_refused_as_not_read_only |
| E4 | a checker with no tools line (all tools) | allowed | refused `checker-not-read-only` | tests/core/test_checker_read_only.py::test_a_checker_with_no_tools_line_is_refused_as_not_read_only |
| E5 | a checker with no agent file | allowed | refused `checker-not-found` | tests/core/test_checker_read_only.py::test_a_checker_with_no_agent_file_is_refused_as_not_found |
| E6 | the refusal text of E3 | none | names the checker and the tool beyond Read and Grep | tests/core/test_checker_read_only.py::test_the_not_read_only_text_names_the_checker_and_the_extra_tool |
| E7 | the refusal text of E5 | none | names the checker and both paths searched | tests/core/test_checker_read_only.py::test_the_not_found_text_names_the_checker_and_the_paths_searched |
| E8 | two checkers, one lists Bash | allowed | refused: every configured checker must be read-only | tests/core/test_checker_read_only.py::test_one_checker_that_is_not_read_only_refuses_among_good_ones |
| E9 | a card that names no test node, a checker with Bash | allowed | allowed: the check is not run for it | tests/core/test_checker_read_only.py::test_a_card_naming_no_node_is_not_refused_for_its_checker |
| E10 | the task folder has `.claude/agents/fresh-reader.md` (Read, Grep) | not judged | the close decision passes | tests/shell/test_checker_agent.py::test_a_task_with_a_read_only_fresh_reader_passes_the_close_check |
| E11 | the task folder has `.claude/agents/critic.md` (has Bash), same row and proof | passed | refused `checker-not-read-only` | tests/shell/test_checker_agent.py::test_a_task_whose_checker_has_bash_is_refused_at_the_close_check |
| E12 | the definition is only in the user's folder, named by the environment | not found | found, read-only: passes | tests/shell/test_checker_agent.py::test_a_definition_only_in_the_user_folder_is_found_through_the_environment |
| E13 | both folders hold the type, the task's is read-only, the user's has Bash | n/a | the task's is read first: passes | tests/shell/test_checker_agent.py::test_the_task_definition_is_read_before_the_user_definition |
| E14 | no agent file in either folder | n/a | refused `checker-not-found`, both paths in the text | tests/shell/test_checker_agent.py::test_no_agent_file_in_either_folder_is_refused_and_names_both_paths |
| E15 | an agent file with no `tools:` line | n/a | refused `checker-not-read-only` | tests/shell/test_checker_agent.py::test_an_agent_file_with_no_tools_line_is_refused_as_not_read_only |
| E16 | the real close command, the checker lists Bash | closed | exits non-zero, `checker-not-read-only`, the card stays open | tests/test_mw071_close_e2e.py::test_the_real_close_is_refused_when_the_checker_lists_bash |
| E17 | the real close command, the checker lists Read, Grep (nearest allow of E16) | closed | closes | tests/test_mw071_close_e2e.py::test_the_real_close_passes_when_the_checker_lists_read_and_grep |
| E18 | the starter profile of a fresh install | `["critic"]` | `["fresh-reader"]` | tests/core/test_install_decide.py::test_no_profile_gives_the_starter_with_the_card_prefix_and_no_path |
| E19 | a real `mkway install` | wrote `["critic"]` | writes `["fresh-reader"]` | tests/test_mw068_records_e2e.py::test_a_real_install_writes_the_default_checker_into_the_profile |
| E20 | the README verdict paragraph | named critic | names fresh-reader, Sonnet, medium, Read and Grep, one run per close, no rounds | checked by reading: README.md |
| E21 | two checker runs on a card (nearest allow of E22) | not judged | allowed | tests/core/test_checker_runs.py::test_two_checker_runs_on_a_card_are_allowed |
| E22 | a third checker run | allowed | refused `verdict-runs-exceeded` | tests/core/test_checker_runs.py::test_a_third_checker_run_is_refused_as_runs_exceeded |
| E23 | the refusal text of E22 | none | names the two earlier runs | tests/core/test_checker_runs.py::test_the_runs_exceeded_text_names_the_two_earlier_runs |
| E24 | a card naming no test node, three runs | allowed | allowed | tests/core/test_checker_runs.py::test_a_card_naming_no_node_is_not_refused_for_its_runs |
| E25 | a node changed in the card's commits, no row (nearest deny of E26) | refused | refused `verdict-missing` | tests/core/test_checker_runs.py::test_a_node_changed_in_the_card_with_no_row_is_refused_as_missing |
| E26 | a node not changed in the card's commits, no row | refused | allowed | tests/core/test_checker_runs.py::test_a_node_not_changed_in_the_card_needs_no_row |
| E27 | no change information (no git, no commit naming the card) | refused | still refused: every named node needs a row | tests/core/test_checker_runs.py::test_with_no_change_information_every_named_node_needs_a_row |
| E28 | two reader sessions on real files | not judged | the close decision passes | tests/shell/test_checker_run_count.py::test_two_reader_sessions_on_a_card_let_the_close_pass |
| E29 | three reader sessions on real files | passed | refused `verdict-runs-exceeded`, the two earlier named | tests/shell/test_checker_run_count.py::test_three_reader_sessions_on_a_card_are_refused_naming_the_two_earlier |
| E30 | the post step's record of a verdict write | no run count | holds `run` 1, 2 | tests/shell/test_checker_run_count.py::test_the_proof_record_of_a_write_holds_the_run_number |
| E31 | a node the card's own commit did not change, real git | refused | allowed with no row | tests/shell/test_checker_run_count.py::test_a_node_the_card_commits_did_not_change_needs_no_verdict_row |
| E32 | a node the card's own commit added, real git (nearest deny of E31) | refused | refused `verdict-missing` | tests/shell/test_checker_run_count.py::test_a_node_the_card_commits_added_needs_a_verdict_row |
| E33 | the README: inputs and token count | none | names the test file, the card and the criteria, never the code, the token count in the card's Log row, at most two runs | checked by reading: README.md |

## 8. Log

One line per step. No re-run of a check or an agent round without a new input named in the Log row.

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-12 | start checks, each alone: `pwd` = the worktree, HEAD cf03e56, `git status --short` = clean | cf03e56 | base of the card |
| 2026-11-12 | red: card, register row, changelog line, tests (core table, shell on real agent files, the real close, the default `fresh-reader`; the shared `task_root` writes a read-only definition for each configured checker, the conftest points HOME and USERPROFILE at an empty scratch folder), decision: R180 | 9ea1256 | 6 tests failed for the right reason and the core file did not import (no `Checker` fact, no refusal, the starter key was critic) |
| 2026-11-12 | green for E1 to E20: `core_verdicts.Checker` and `checker_refusal`, `verdicts.checker_facts` and `parse_tools` (task root first, then the user folder from the environment), the default `fresh-reader`, README clause; one legacy shell test got a read-only definition, decision: R180. The outbox board (`outbox.py`) is not changed: the refusal is at the card close only (a reading of the ruling) | the commit that carries this line | whole suite 3371 passed, 2 failed in 812 s (Cyrillic in this card's quote, repo scan); after the fix the repo scan, meta-card and shell tests 15 passed. Red commit 9ea1256 |
| 2026-11-12 | ruling R181 added: red rows E21 to E33, the core table of the run limit and of the changed nodes, shell tests on real files and real git (tests only, with the rows) | the commit that carries this line | 10 of 12 new tests fail for the right reason: no `runs` or `changed` fact, no `verdict-runs-exceeded`, no `run` in the record, no change reading |
| 2026-11-12 | green for E21 to E33: `Facts.runs` and `Facts.changed`, `verdict-runs-exceeded` in the core, `verdicts.runs_of`, `run` in the verdict write record, `verdicts.changed_nodes` (the function source of each named node compared with its parent in each commit that names the card, by `ast`; `git log -L` was tried and counts trailing blank lines as part of the function); README clause. Reading: a run is a reader session that wrote verdict rows; the limit is checked at the close | the commit that carries this line | core, shell and close tests 2413 passed in 126 s. Red commit 6de84d1 |
