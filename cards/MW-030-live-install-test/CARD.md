# MW-030: Live install test is the release gate: no version is tagged before it passes

| | |
|---|---|
| **Appetite** | 2 hours — from 2026-11-11 |
| **Status** | proposed |
| **Created / updated** | 2026-11-11 / 2026-11-11 |
| **Waiting for** | owner: opens the card |
| **Form** | card |
| **Decisions** | none new: the rule «no version is tagged or recommended to the owner before this test passes» comes from the order that carries this card |
| **Canon** | none for the live install layout: the basis is the five defects found in the first real install |
| **Paths** | `tests/test_mw030_live_install.py`, `cards/REGISTER.md`, `CHANGELOG.md`, `cards/MW-030-live-install-test/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository. The test is the deliverable: a row that is red names an engine defect, and no engine code changes here.

## 1. Goal

The first real install, in a sparse linked worktree with an untracked task folder, hit five defects that no scratch
test had met. One test now reproduces that layout in the pytest temp folder only (fixture repository, linked worktree
made with `--no-checkout`, cone `task/<Task>`, task folder by mkdir), installs the engine, runs `mkway check` from the
task folder with no `--root` and no `CLAUDE_PROJECT_DIR`, and walks one card through the installed hooks as a lead
session and a builder session. It is the release gate: no version is tagged or recommended to the owner before it
passes. `mkway check` has no flag that skips its inner test run, so the engine source of the test is this
repository's engine files with its own tests cut to the one fixture test; every other line of `check` is the real one.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | `mkway check` from the task folder, no `--root`, no variable | not tried in this layout | exit 0, tests green, copy hash matches, no warning line | tests/test_mw030_live_install.py::test_the_check_run_from_the_task_folder_is_clean |
| E2 | lead: register, card new, write CARD.md and ORDER.md, open (approver orderer); builder: take, write, edit in Paths, commit; lead closes | not tried through the installed hooks | no hook refuses, the commit carries the card id, the register says closed | tests/test_mw030_live_install.py::test_the_lead_and_builder_path_has_no_refusal |
| E3 | files of the main worktree and of the linked worktree outside the task folder | not compared | unchanged, but for the shared state named in E4 | tests/test_mw030_live_install.py::test_nothing_else_is_written_outside_the_task_root |
| E4 | the shared state (leads registry, inboxes) of a linked worktree | written to the main worktree | nothing in the main worktree changes (MW-026, on master) | tests/test_mw030_live_install.py::test_the_shared_state_stays_inside_the_task_root |
| E5 | the starter profile and the bundle ignore file | not asserted in this layout | `vcs` git; `mkway/.gitignore` exists and ignores `state/` | tests/test_mw030_live_install.py::test_the_profile_says_git_and_the_bundle_ignore_file_exists |
| E6 | the start block of a lead and of a builder session | not read | no profile error, no dispatcher error, zero logged gate errors | tests/test_mw030_live_install.py::test_the_start_block_has_no_error_line |
| E7 | the run time | not measured | under 90 s (the card aims at about 60) | tests/test_mw030_live_install.py::test_the_run_stays_inside_the_time_limit |
| E8 | register, changelog | no word | register row, a changelog line, under the release that names the card, saying «release gate» | tests/test_mw030_live_install.py::test_register_changelog_and_card_name_the_card |
| E9 | `git status --porcelain` in the linked worktree after the flow; the settings file | run-time files offered, hooks in the local file | no run-time file under `mkway/state`, `mkway/locks`, no bytecode; `.claude/settings.json` holds the hooks (MW-027) | tests/test_mw030_live_install.py::test_the_first_status_offers_no_runtime_file_and_the_settings_hold_the_hooks |
| E10 | the install committed in the fixture, a second worktree of that commit | needs its own install | its start hook works with no install, no drift (MW-027) | tests/test_mw030_live_install.py::test_a_second_worktree_of_the_install_commit_starts_with_no_install |

## 8. Log

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-11 | test written and run, rows E1 to E8; the test is the deliverable, no engine code changed | the commit that carries this line | 6 green, E1 red, E4 xfail. The whole flow takes about 17 s (limit 90 s) |
| 2026-11-11 | E1 red, engine defect: `mkway check` prints `git builtins: warning: the engine list differs from git` (only in git: backfill, diff-pairs, last-modified, repo, survey; only in the list: env--helper), the stale built-in list in `engine/defaults.json` against this machine's git; a warning line on the owner's first check. Not an open card: needs a fix card | - | red, kept red |
| 2026-11-11 | E4 xfail, MW-026: the linked worktree's shared state (`leads.json`, `sessions.jsonl`) is written to `task/<Task>/mkway/state` of the main worktree, outside the task root; E3 pins that nothing else is written outside | - | xfail, strict off |
| 2026-11-11 | the engine source of the test is this repository's engine files with its tests cut to one fixture test: `mkway check` has no flag to skip its inner run, which takes minutes. E5 asserts `mkway/.gitignore` exists (MW-027 not needed: the install writes it today) | - | reading, to confirm |
| 2026-11-11 | whole suite, `python -m pytest`, term scan included | the commit that carries this line | 852 passed, 1 failed (E1, kept red), 1 xfailed in 626 s; no term-scan exception added |
| 2026-11-11 | ported onto master bd787bd (MW-026 and MW-029 merged): the E4 xfail is removed, E4 must pass; E1 is marked xfail strict, reason «MW-031 in flight», so it shows when MW-031 lands | the commit that carries this line | whole suite, `python -m pytest`, term scan included: 869 passed, 1 xfailed (E1) in 439 s; E4 passed; no term-scan exception added |
| 2026-11-11 | MW-027 ported onto master 4fd59c6: row E8 said «under the top release», which cannot hold once `## 0.2.7` (MW-027) sits above the release that names this card; the row now says «under the release that names the card» and the test finds that section, the «release gate» assert is kept. The test also reads the hooks from the committed `.claude/settings.json`, E5 asserts the run-time ignore lines and no `engine/` line, E2 reads the builder's commit subject taken before the install commit, and two rows are added in the test file, E9 (the first status offers no run-time file, the settings hold the hooks) and E10 (the install committed in the fixture, a second worktree of that commit starts with no install) | the commit that carries this line | whole suite, `python -m pytest`, term scan included: see the MW-027 Log |
