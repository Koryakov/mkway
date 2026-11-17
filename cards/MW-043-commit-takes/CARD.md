# MW-043: A commit is judged by what git will put in it

| | |
|---|---|
| **Appetite** | 60 minutes — from 2026-11-12 |
| **Status** | proposed |
| **Created / updated** | 2026-11-12 / 2026-11-12 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | none new: the ruling of the chief carries it («judge the commit by what git will put in it») |
| **Canon** | none for the commit check: the basis is the gap a real-shape replay found |
| **Paths** | `engine/`, `tests/`, `README.md`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-043-commit-takes/CARD.md`, `cards/MW-034-staged-paths/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository. `VERSION` is not changed here.

## 1. Goal

MW-034 made the commit gate read git's staged list in every form. A real-shape replay found the cost: with another
session's file staged, `git commit -m "<id> x" -- <card paths>` was refused `file-not-in-card`, although in that form
git commits only the named paths. Now the gate judges a commit by what git will put in it: `-- <paths>` (git's
`--only`, the default when paths are named) the named paths alone; `-i -- <paths>` the staged list plus the named
paths; a plain commit the staged list; `-a` the staged list plus every modified tracked file; `--amend` the same rule
and nothing else. A foreign file left staged is not a commit fault. The start block says `staged outside your card: N`
(a session with an open card, N > 0) and `mkway check` says `staged files: N outside every open card's Paths`; both
are lines, never a refusal.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | a foreign file staged, `-- <inside>` (also `-o`, `--only`) | refused `file-not-in-card` | allowed; real git leaves the foreign file staged and uncommitted | tests/test_mw043_commit_takes.py::test_a_foreign_staged_file_does_not_stop_a_commit_that_names_its_own_paths |
| E2 | a foreign file staged, plain commit | refused | refused, naming the file and the way out | tests/test_mw043_commit_takes.py::test_a_plain_commit_takes_the_staged_list_and_is_refused_for_a_foreign_file |
| E3 | a foreign file staged, `-i -- <inside>` (also `--include`) | refused | refused; with only inside files staged, allowed | tests/test_mw043_commit_takes.py::test_an_include_commit_takes_the_staged_list_plus_the_named_paths |
| E4 | `-a` with a modified tracked file outside the card | refused only when staged | refused, nothing staged; a foreign staged file too; allowed with only inside files modified | tests/test_mw043_commit_takes.py::test_an_all_commit_takes_the_staged_list_plus_every_modified_tracked_file |
| E5 | `--amend` | judged with the staged list in every form | the same rule per form, nothing else: a plain amend with nothing staged passes | tests/test_mw043_commit_takes.py::test_an_amend_follows_the_same_rule_and_judges_nothing_else |
| E6 | `-- <outside>` | refused | refused, with the way out `leave them out of the paths after --` | tests/test_mw043_commit_takes.py::test_a_named_path_outside_the_card_is_still_refused |
| E7 | the start block | no word of a foreign staged file | `staged outside your card: N` for a session with an open card and N > 0; no line otherwise | tests/test_mw043_commit_takes.py::test_the_start_block_counts_the_files_staged_outside_the_card |
| E8 | the count | none | `gate_commit.staged_outside`: outside one card's Paths, or outside every open card's | tests/test_mw043_commit_takes.py::test_staged_outside_counts_against_one_card_or_every_open_card |
| E9 | `mkway check` | no word of a foreign staged file | `staged files: N outside every open card's Paths` when N > 0; the result code unchanged | tests/test_mw043_commit_takes.py::test_check_prints_the_staged_files_outside_every_open_card |
| E10 | README, register, changelog | the README said the staged list is read always | the rule per form and the two lines named; register row; a line under the release that names the card; VERSION: see VERSION | tests/test_mw043_commit_takes.py::test_readme_register_changelog_and_card_name_the_card |
| E11 | MW-034 E3 (changed, not dropped) | «refused in every form» | judged by what git takes: refused in the forms that take the staged list, allowed for `-- <inside>` | tests/test_mw034_staged_paths.py::test_a_file_staged_earlier_outside_the_paths_is_judged_by_what_git_takes |

## 8. Log

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-12 | red: rows E1 to E11 | 16a071e | E1, E5, E7, E8, E9, E10 and the changed MW-034 E3 (E11) failed for the right reason (a `--` commit was refused for a foreign staged file; no `staged_outside`, no lines, no README text, no register row); E2, E3, E4, E6 passed already and pin the refusals that stay |
| 2026-11-12 | green: `_taken` per form, `staged_outside`, start block line, check line, README, register, changelog | the commit that carries this line | rows E1 to E11 green; whole suite, `python -m pytest`, term scan included, no exception added: 932 passed in 608 s. Older test changed to the new rule, none dropped: MW-006 E9 (`test_every_commit_form_reads_the_files_it_would_stage`: `-- <paths>` is allowed beside a foreign staged file; the named outside path, `-i`, plain and `--amend` stay refused). The base holds no real-shape replay file, so there is no F1 xfail to remove |
| 2026-11-12 | MW-040: row E10 named a release number or an old VERSION | the commit that carries this line | the row says «see VERSION» and «the release that names the card»; its test reads the VERSION file and finds the card's changelog line (`tests/_docs.py`), no release number is pinned |
| 2026-11-12 | MW-034 E3 row changed: the test is renamed and its body follows the ruling | the commit that carries this line | the old row said «refused in every form», which the ruling of the chief replaces: `--` takes the named paths alone; the row in `cards/MW-034-staged-paths/CARD.md` names the new test and carries a Log line |
