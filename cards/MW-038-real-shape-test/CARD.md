# MW-038: A test that replays the owner's real task setup

| | |
|---|---|
| **Appetite** | 90 minutes — from 2026-11-12 |
| **Status** | proposed |
| **Created / updated** | 2026-11-12 / 2026-11-12 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | none new: the standing rule «a gap found in real work gets its own fix card at once» carries it |
| **Canon** | none for install and gates: the basis is the owner's report of 12 November |
| **Paths** | `tests/`, `cards/REGISTER.md`, `CHANGELOG.md`, `cards/MW-038-real-shape-test/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository. `VERSION` is not changed here. No engine file is changed: a step that fails on the engine of the day is an
`xfail(strict=True, reason="MW-038 finding: ...")` and is reported.

## 1. Goal

«every time you report me ... tests pass, but when I apply your version of MKW, I have a problems ... your tests ...
don't cover functionality» — owner, 2026-11-12. One scenario in the pytest temp folder, steps in order, replays the
shape of the real setup: a sparse linked worktree of a bigger repository, a reinstall over a 0.2.1 install, files
written by a builder's own script, a second builder and a foreign staged file in one index, a product rule on the
commit message prefix, the owner's commands run from another folder. The hooks run from the generated settings with
a JSON payload on stdin, as Claude Code runs them. Synthetic ids only: the task id is `#90001`, the card prefix `ZZ`.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | S1: product repository of 200+ files, linked worktree, sparse checkout of `task/<Name>/` only | no test built this shape | built: under 5 per cent of the files present, task folder two levels down | tests/test_mw038_real_shape.py::test_s1_a_sparse_linked_worktree_of_a_bigger_repository |
| E2 | S2: an older install in that folder | no test started from an older install | the 0.2.1 layout (from its commit; by hand if unreachable): `engine/` in the bundle `.gitignore`, copy untracked | tests/test_mw038_real_shape.py::test_s2_an_older_install_is_in_place |
| E3 | S3: reinstall with `--commit`, prefix profile, a foreign file staged | live test had no prefix, no older layout | exit 0, engine tracked, no `engine/` line, message starts with the prefix, only install's paths, foreign file still staged; no hook entry left in `settings.local.json` | tests/test_mw038_real_shape.py::test_s3_the_reinstall_commit_takes_only_the_install_paths; tests/test_mw038_real_shape.py::test_s3_the_old_local_settings_no_longer_run_the_hooks_twice |
| E4 | S4: hooks of the generated settings, builder A takes an open card, builder B takes in the same root | no test read a hook refusal (exit 0 with a deny) | start blocks clean; A takes; B refused `take-root-busy` | tests/test_mw038_real_shape.py::test_s4_start_hooks_and_the_second_builder_in_one_root |
| E5 | S5: a script writes a text and a PNG under the Paths; the commit; a staged file outside the Paths | no test commits script-written files with a foreign file staged | commit allowed (FINDING F1: refused on today's engine, xfail strict), commit holds the Paths and the PNG bytes, prefix kept; a staged outside file is refused `file-not-in-card` | tests/test_mw038_real_shape.py::test_s5_a_script_written_text_and_png_commit_through_the_gates; tests/test_mw038_real_shape.py::test_s5_the_commit_holds_the_paths_the_png_bytes_and_the_prefix; tests/test_mw038_real_shape.py::test_s5_a_staged_file_outside_the_paths_is_refused |
| E6 | S6: `mkway check --root <root>` from another folder | check run only from the task folder | exit 0, green tests, the copy unchanged, nothing written where it ran | tests/test_mw038_real_shape.py::test_s6_check_from_another_folder_passes_and_leaves_the_copy_alone |
| E7 | S7: a second linked worktree from the commit; the main checkout; the time | start hook of a fresh worktree tested in one flow only | start hook works with no install; no file of the main checkout changed; the scenario under 60 s | tests/test_mw038_real_shape.py::test_s7_a_second_worktree_of_the_commit_starts_with_no_install; tests/test_mw038_real_shape.py::test_nothing_in_the_scenario_wrote_into_the_main_checkout; tests/test_mw038_real_shape.py::test_the_scenario_runs_inside_the_time_limit |
| E8 | the guard | the scenario could be removed or skipped | fails when the scenario file is missing, holds a skip, lacks a step, or holds an xfail that is not strict with a `MW-038 finding:` reason | tests/test_mw038_guard.py::test_the_real_shape_scenario_exists_and_holds_no_skip; tests/test_mw038_guard.py::test_every_step_has_a_test_and_every_xfail_is_a_strict_finding |
| E9 | register, changelog | no MW-038 | a register row; a line under the release that names the card; VERSION: see VERSION | tests/test_mw038_guard.py::test_the_card_register_and_changelog_name_mw038 |

## 8. Log

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-12 | tests, scenario and guard in one commit (no engine change, so no separate green commit); first run on master 1180e9d: 11 of 12 scenario tests passed in 31 s; E5 step 1 failed: FINDING F1, the commit gate refuses the builder's `git commit -- <card paths>` as `file-not-in-card` while another session's file is staged (git takes only the named paths of that form); marked xfail strict. FINDING F2: `test_mw030_live_install.Sessions.fire` reads only the exit code, and a PreToolUse refusal is exit 0 with a JSON deny, so the MW-030 live test cannot see a refusal; the MW-038 driver reads it. The 0.2.1 install read vcs none below the git top (MW-028), so the scenario sets git and installs it again, as the owner did | the commit that carries this line | whole suite, `python -m pytest`, term scan included, no exception added: 936 passed, 1 xfailed (F1) in 695 s. The task id `#90001` and the card prefix `ZZ` are synthetic by the NDA rule, not the real ones named in the task text |
| 2026-11-12 | ported onto master a8af9f6 after MW-043: F1 is fixed, the xfail mark of `test_s5_a_script_written_text_and_png_commit_through_the_gates` is removed; E5 refusal row moved to the staged-list form | the MW-038 port commit | S5 refusal row moved to the staged-list form after MW-043; the `--` form takes only the named paths. The test `test_s5_a_staged_file_outside_the_paths_is_refused` now asserts (1) a foreign file staged and a plain `git commit -m ...` with no paths is refused `file-not-in-card` naming it, (2) `git commit -m ... -- <path outside the card Paths>` is refused `file-not-in-card`; the `-- <inside path>` commit stays as an allowed step |
| 2026-11-12 | MW-040: row E9 named a release number or an old VERSION | the commit that carries this line | the row says «see VERSION» and «the release that names the card»; its test reads the VERSION file and finds the card's changelog line (`tests/_docs.py`), no release number is pinned |
