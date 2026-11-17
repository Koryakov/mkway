# MW-070: card close runs the named test nodes on HEAD's tree

| | |
|---|---|
| **Appetite** | 2 hours — from 2026-11-12 |
| **Status** | proposed |
| **Created / updated** | 2026-11-12 / 2026-11-12 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | none new: the ruling of the task brief carries it, quoted in the Goal |
| **Canon** | none: the basis is a real install where a card closed with its tests green on the working tree and red at HEAD |
| **Paths** | `engine/cardtool.py`, `tests/`, `README.md`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-070-close-on-head-tree/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository. `VERSION` is not changed here. The change stays inside the step of `engine/cardtool.py` that runs the
Acceptance nodes (`tests_problem`); the export of HEAD's tree is the one `engine/gate_commit_tests.py` makes for the
commit gate (MW-060), called, not copied. `engine/helpers.py`, `engine/core.py` and `engine/gate_commit.py` are not
touched.

## 1. Goal

«Root cause: `card close` ran the named nodes on the working tree, so a card closed on a register that was only
staged; close must run the nodes on an export of HEAD's tree, nothing staged or untracked, the same tree rule as MW-060
for commits.» — the chief's ruling R176, 2026-11-12. In the real case the card's tests read a register file that another
card had only staged; the close was green, and at HEAD the same tests were red, so a closed card left red tests.

## Acceptance examples

Each row becomes a test; `card close` needs every row to name one. Rows E1 to E9 run the node step on a real small git
repository; E10 runs the real close command through the real hooks on an install.

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | a register file that is only staged | the node read it and the close passed | the node does not find it: the close is refused | tests/test_mw070_head_tree.py::test_a_register_file_that_is_only_staged_refuses_the_close |
| E2 | a register file that is only untracked | the node read it and the close passed | the node does not find it: the close is refused | tests/test_mw070_head_tree.py::test_a_register_file_that_is_only_untracked_refuses_the_close |
| E3 | a file red at HEAD, edited in the working tree and not staged | the edit was read, the close passed | the node reads HEAD's version: the close is refused | tests/test_mw070_head_tree.py::test_a_file_modified_but_not_staged_is_read_as_it_is_at_head_and_the_red_stays |
| E4 | a file green at HEAD, broken in the working tree and not staged | the close was refused | the node reads HEAD's version: the close passes | tests/test_mw070_head_tree.py::test_a_file_broken_in_the_working_tree_only_does_not_refuse_a_close_that_is_green_at_head |
| E5 | the register file committed green (nearest allow of E1, E2) | the close passed | the close passes | tests/test_mw070_head_tree.py::test_a_register_file_committed_green_lets_the_close_pass |
| E6 | the refusal text | named the red nodes | names the red node by its full id and says it ran on HEAD's tree | tests/test_mw070_head_tree.py::test_the_refusal_names_the_red_node_and_says_it_ran_on_heads_tree |
| E7 | the export of HEAD's tree | none | removed after the run: nothing of it is left under the state folder | tests/test_mw070_head_tree.py::test_the_export_of_heads_tree_is_removed_after_the_run |
| E8 | a root with `vcs: none` | nodes run where they are | unchanged: there is no HEAD, the nodes run on the files as they are | tests/test_mw070_head_tree.py::test_a_root_with_no_git_still_runs_the_nodes_where_they_are |
| E9 | a git repository with no commit | nodes ran on the working tree | there is no tree of HEAD: the close is refused and says so | tests/test_mw070_head_tree.py::test_a_repository_with_no_commit_refuses_the_close_saying_there_is_no_head |
| E10 | the real close command, a register file only staged, task folder below the git top | closed green | exits non-zero, `close-tests-failing`, names the node, says HEAD's tree, the card stays open | tests/test_mw070_e2e.py::test_a_register_that_another_card_only_staged_refuses_the_real_close_command |

## 8. Log

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-12 | start checks, each alone: `pwd` = the worktree, HEAD d1b4d69, `git status --short` = clean | d1b4d69 | base of the card |
| 2026-11-12 | red: rows E1 to E10, card, register row, changelog line, tests only | 370b600 | 7 of 10 new tests failed for the right reason: the node step ran in the working tree, so a staged only, untracked or edited register file was read (E1 E2 E3 E4 E6), a repository with no commit was not refused (E9), and the real close command closed the card over a register file that was only staged (E10, the real case replayed). E5 E7 E8 are guards that pass before and after. Whole suite not run for a red commit |
| 2026-11-12 | green: `tests_problem` runs the nodes in an export of HEAD's tree with `vcs: git`, made by `gate_commit_tests._head_folder` (the export of the commit gate, called, not copied; `helpers.py`, `core.py`, `gate_commit.py` untouched) and removed after the run; the refusal says the tests ran on HEAD's tree; no commit is a refusal; `vcs: none` runs in the root as before; README clause | the commit that carries this line | rows E1 to E10 green: 10 passed in 24 s. Close, MW-060, meta-card, gate, helper, seal and docs tests: 189 passed in 97 s, then 114 passed in 76 s. The whole suite and the live install test were NOT run here (the brief limited the run); the owner's whole-suite run before the merge is still due. Readings: (a) the core table is not used, the decision is not pure (one fact, HEAD or not, read from the repository); (b) a root with `vcs: none` has no HEAD and keeps the working-tree run; (c) the owner's own `card close` runs no node, so it is unchanged. `VERSION` unchanged |
