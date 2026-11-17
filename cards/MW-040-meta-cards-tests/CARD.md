# MW-040: Card rows and tests stay in step

| | |
|---|---|
| **Appetite** | 1 hour — from 2026-11-12 |
| **Status** | proposed |
| **Created / updated** | 2026-11-12 / 2026-11-12 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | none new: the test-concept ruling of 2026-11-12 carries it, quoted in the Goal |
| **Canon** | none for card rows: the basis is the blind audit of 2026-11-12 |
| **Paths** | `tests/`, `cards/`, `CHANGELOG.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository. `VERSION` is not changed here. No engine code changes.

## 1. Goal

«Every old case must keep a home»: the migration cards move tests between files, and a card row that names a test that
no longer exists proves nothing. The audit found rows naming tests that were replaced (MW-006 E4-E6, E10-E11; MW-017
E22), rows out of date after later cards (MW-022: shared state is opt-in since MW-026), and nothing that checks it.
Now `tests/test_meta_cards.py` reads every `cards/MW-*/CARD.md`: each node id (`file::test`) or whole-cell bare test
name that an example row (first cell E1, S2, ...) names must exist in `tests/` (collected by AST, once per session), or a
`cards/MW-*/case_map.md` line maps it. Case map format, one line per old case:
`old_file::old_test -> new_file::new_test`, or `old_file::old_test -> dropped: <why>`; every right side must exist.
Also: no test pins a release number; they read `VERSION` and find the card's own changelog line (`tests/_docs.py`).

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | a test id named by a card row | nothing checked it | fails unless the test exists or a case_map line maps it | tests/test_meta_cards.py::test_every_test_id_a_card_row_names_exists_or_has_a_case_map_line; tests/test_meta_cards.py::test_the_checker_catches_a_missing_id_and_accepts_a_mapped_one |
| E2 | case_map.md lines | no such file | each line well formed, each right side exists or says `dropped: <why>` | tests/test_meta_cards.py::test_every_case_map_line_is_well_formed_and_its_right_side_exists |
| E3 | version pins in tests | `== "0.2.7"` and `## 0.2.x` splits | the VERSION file is read and checked as one semver line; the card's changelog line is found in whichever section holds it; release order is read once | tests/test_meta_cards.py::test_changelog_releases_run_newest_first; tests/test_mw016_version.py::test_the_version_file_is_semver |
| E4 | register, changelog, card | no MW-040 | register row; a line under the release that names the card; VERSION: see VERSION | tests/test_meta_cards.py::test_register_changelog_and_card_name_the_card |

## 8. Log

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-12 | stale rows fixed: MW-006 E4, E5, E6, E10, E11 (to the MW-034 and MW-043 tests), MW-017 E22 (to the lookup that starts no git), MW-022 E1-E3 (shared state is opt-in since MW-026); every version row that named a release now says «see VERSION» and «the release that names the card»; each changed card has its own MW-040 Log row | the commit that carries this line | the meta-test found exactly the six ids the audit named; MW-022 held no missing id, only wrong claims |
| 2026-11-12 | VERSION pins replaced by reads of the VERSION file (`docs.assert_version_file()`) and the changelog section found by the card's own line (`docs.changelog_section`): `test_mw016_version.py` (E1), `test_mw017_docs.py`, `test_mw018_docs.py`, `test_mw022_locks_shared.py`, `test_mw023_green_tree.py`, `test_mw024_task_root.py`, `test_mw025_copy_check.py`, `test_mw026_state_in_root.py`, `test_mw027_install_commit.py`, `test_mw028_lead_authors.py`, `test_mw029_fast_guard.py`, `test_mw031_git_builtins.py`, `test_mw032_reinstall_safe.py`, `test_mw033_commit_gate.py`, `test_mw034_staged_paths.py`, `test_mw035_install_line.py`, `test_mw036_install_own_paths.py`, `test_mw038_guard.py`, `test_mw041_install_line_root.py`, `test_mw043_commit_takes.py`, `test_mw045_stale_holder.py`; the ordering asserts between two release headings were dropped there, `test_changelog_releases_run_newest_first` reads the order once | the commit that carries this line | docstrings of those tests may still name a release as history; no assertion does |
| 2026-11-12 | tests and the doc fixes in one commit (no engine change, so no separate green commit; precedent: MW-038); no `case_map.md` exists yet, the migration cards write the first | the commit that carries this line | whole suite result is in the next row |
