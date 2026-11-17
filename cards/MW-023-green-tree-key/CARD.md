# MW-023: One tree key for green test rows

| | |
|---|---|
| **Appetite** | 1 hour — from 2026-11-11 |
| **Status** | proposed |
| **Created / updated** | 2026-11-11 / 2026-11-11 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | none new: the standing rule «a gap found in real work gets its own fix card at once» carries it |
| **Canon** | none for tree keys: the basis is the gap found building MW-020 |
| **Paths** | `engine/gate_commit_tests.py`, `engine/deliverables.py`, `engine/rules.py`, `CHANGELOG.md`, `tests/`, `cards/REGISTER.md`, `cards/MW-023-green-tree-key/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository.

## 1. Goal

The commit gate writes the `tree` of a `commit_tests.jsonl` row as the sha256 of `git ls-files -s -z`. `mkway rules`
read that field as a git tree id and so never found a green row that exists; `mkway built` accepted both forms through
its own copy of the logic. One helper beside the gate's own computation names the keys of a commit, and every reader
calls it — standing rule of the owner, 2026-11-11.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | `mkway rules`, a row written as the commit gate writes it | `last green tree none` | the git tree id of the commit the digest names, 8 hex characters | tests/test_mw023_green_tree.py::test_rules_finds_a_green_row_written_as_the_commit_gate_writes_it |
| E2 | the same row, HEAD moved on | `none` | the tree of the older commit the row names; a card whose test no green commit holds stays `none` | tests/test_mw023_green_tree.py::test_rules_finds_the_green_row_of_an_older_commit |
| E3 | `mkway built` on the same row | passes with its own copy of the key logic | still passes through the helper; a digest of another commit still refuses `built-untested` | tests/test_mw023_green_tree.py::test_built_still_passes_on_the_same_row |
| E4 | the rules view, either form of the key | the digest form never shown | 8 hex characters of the git tree id for a tree id row and a digest row alike | tests/test_mw023_green_tree.py::test_the_rules_view_shows_eight_hex_characters_whichever_form_the_row_used |
| E5 | the code | the key logic in `deliverables.py` only | one function `gate_commit_tests.tree_keys` (and `trees_of_keys` over it); `deliverables.py` and `rules.py` hold no second copy | tests/test_mw023_green_tree.py::test_one_helper_serves_the_writer_and_every_reader |
| E6 | register, changelog, version | no word on it | the register has the row, the changelog lists the card, VERSION: see VERSION | tests/test_mw023_green_tree.py::test_the_register_changelog_and_card_name_the_card |

## 8. Log

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-11 | red: rows E1 to E6 | 50388a9 | 5 tests red, 1 passes before the code (E3: `built` already took both forms) |
| 2026-11-11 | design: `gate_commit_tests.tree_keys(root, rev)` returns the git tree id and the digest of the commit (the digest rebuilt from `ls-tree -r -z`, same entries and order as `ls-files -s -z`); `trees_of_keys` maps keys to git tree ids over the newest 100 commits; `deliverables.build` and `rules.last_green_tree` call them, the gate writes its key with `staged_key`; the rules view shows the git tree id of the commit the row names, 8 characters, for both forms | the commit that carries this line | reading, to confirm |
| 2026-11-11 | whole suite, `python -m pytest`, term scan included | the commit that carries this line | 825 passed in 328 s (819 on the base, 6 new); no term-scan exception added |
| 2026-11-12 | MW-040: row E6 named a release number or an old VERSION | the commit that carries this line | the row says «see VERSION» and «the release that names the card»; its test reads the VERSION file and finds the card's changelog line (`tests/_docs.py`), no release number is pinned |
