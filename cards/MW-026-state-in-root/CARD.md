# MW-026: State never outside the mkway root

| | |
|---|---|
| **Appetite** | 60 minutes — from 2026-11-11 |
| **Status** | proposed |
| **Created / updated** | 2026-11-11 / 2026-11-11 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | the ruling of the chief session: the engine never writes outside the mkway root by its own path logic; sharing state across worktrees is opt-in by an absolute path the owner sets |
| **Canon** | none: the basis is the gap found in the owner's first real install (the standing rule «a gap found in real work gets its own fix card at once») |
| **Paths** | `engine/profiles.py`, `engine/install.py`, `engine/mkway.py`, `engine/schema_check.py`, `engine/profile.schema.json`, `engine/KEYS.md`, `README.md`, `CHANGELOG.md`, `VERSION`, `pytest.ini`, `tests/`, `cards/REGISTER.md`, `cards/MW-026-state-in-root/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository.

## 1. Goal

The leads, inbox, sessions, pings, dead-letter and lock-marker files stay under the root's own state folder. In the first
real install the task root was a subfolder of a linked worktree, and `profiles.shared_state_dir` (MW-017, MW-022) mapped
it to the same path in the main worktree, so the engine wrote into another checkout of the product repository. Now the
shared state dir is the root's own `state.dir`, unless the owner sets the absolute path `state.shared_dir` in the profile
or runs `mkway install --shared <path>`. `mkway check` warns `state-outside-root` for files that 0.2.0 or 0.2.1 left in the
main worktree's mirror of the root, names the folder, and never removes anything.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | root below a linked worktree (sparse where git allows): install, session start, `lead register`, `send`, `hold` | files in the main worktree | no file above the root | tests/test_mw026_state_in_root.py::test_a_root_below_a_linked_worktree_writes_nothing_above_itself |
| E2 | root at the repository top, same steps | nothing above | still nothing above | tests/test_mw026_state_in_root.py::test_a_root_at_the_repository_top_writes_nothing_above_itself |
| E3 | root with no git, same steps | nothing above | still nothing above | tests/test_mw026_state_in_root.py::test_a_root_with_no_git_writes_nothing_above_itself |
| E4 | the lookup | git's main worktree | `state_dir`, or the absolute `state.shared_dir`; anything else ignored and a schema error | tests/test_mw026_state_in_root.py::test_the_shared_dir_is_the_state_dir_unless_the_profile_names_an_absolute_path |
| E5 | key set | no key | the shared files live there, the rest stays in the root | tests/test_mw026_state_in_root.py::test_with_the_key_set_the_shared_files_live_there_and_the_rest_stays_in_the_root |
| E6 | `install --shared <path>` | no flag | writes the key (new or existing profile); a relative path refused, nothing written | tests/test_mw026_state_in_root.py::test_install_shared_writes_the_key_into_the_profile |
| E7 | `check`, files in the main worktree's mirror | silent | warning `state-outside-root` with the folder, exit unchanged, nothing removed | tests/test_mw026_state_in_root.py::test_check_warns_state_outside_root_for_files_in_the_main_worktrees_mirror |
| E7 | the same through the whole `mkway check` | silent | the line in the output, exit 0 | tests/test_mw026_state_in_root.py::test_check_prints_the_state_outside_root_line |
| E8 | register, changelog, version, KEYS, README | no word | register row, `## 0.2.6` on top, `VERSION` 0.2.6, `state.shared_dir` row (default unset), README opt-in sentences | tests/test_mw026_state_in_root.py::test_register_changelog_version_keys_and_readme_name_the_card |

## 8. Log

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-11 | the other stray folder of the first install, `<git top>/mkway/state/check/pytest.ini`, came from `mkway check` run without `--root` before MW-024 (the root fell back to the git top, and check wrote its pytest.ini there before it failed); MW-024 already stops check at a root with no install before any write; nothing to build here | — | recorded only |
| 2026-11-11 | red: rows E1 to E8; the MW-017 and MW-022 tests that assumed the mapping now set `state.shared_dir` in their profiles | 6947ee8 | 7 tests red, 2 pass before the code (E2, E3 guard today's answers) |
| 2026-11-11 | the MW-017 test «git failing gives the state dir and the answer is resolved once» no longer has a subject (the lookup starts no git, no cache): replaced by `test_the_lookup_never_asks_git`, same file; the `_fresh_cache` fixtures of MW-017 and MW-022 went with the cache; the conftest guard stays and now fails a test whose shared dir lies outside the repository | the commit that carries this line | reading, to confirm |
| 2026-11-11 | the expected set of added keys in the schema (`tests/test_keys.py`, MW-002 E19) gains `state.shared_dir`: the new key is a schema leaf and a KEYS.md row, so the set that must equal the schema's leaves has one more item; no other change to that test | the commit that carries this line | reading, to confirm |
| 2026-11-11 | `VERSION` pin `0.2.1` changed to `0.2.3` in the tests of MW-016, MW-017, MW-018, MW-022, MW-023, MW-024 (a patch release); MW-025 builds 0.2.2 in parallel, the operator merges the two version lines | the commit that carries this line | reading, to confirm |
| 2026-11-11 | whole suite, `python -m pytest`, term scan included | the commit that carries this line | 840 passed in 412 s (831 on the base, 9 new); no term-scan exception added |
| 2026-11-11 | ported onto master d02df9f (MW-028 merged, MW-029 ported before it): the release is `0.2.6`, not `0.2.3`; row E8 and its test now read `## 0.2.6` and `VERSION` 0.2.6; the version pins of MW-016, MW-017, MW-018, MW-022, MW-023, MW-024, MW-025, MW-028 read 0.2.6 where they check the current version; the changelog line of MW-029 moved from `## 0.2.2` to `## 0.2.6`, so MW-029 row E8 and its test read `## 0.2.6` | the commit that carries this line | reading, to confirm |
