# MW-036: The install commit takes only what install writes

| | |
|---|---|
| **Appetite** | 45 minutes — from 2026-11-12 |
| **Status** | proposed |
| **Created / updated** | 2026-11-12 / 2026-11-12 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | none new: the standing rule «a gap found in real work gets its own fix card at once» carries it |
| **Canon** | none for install: the basis is the gap a live task's install found |
| **Paths** | `engine/`, `tests/`, `README.md`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-036-install-own-paths/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository. `VERSION` is not changed here.

## 1. Goal

MW-035 limited the install commit to the settings file and the whole bundle folder. In a live task the bundle also
holds files sessions write: a lead's `asks/*.md`, edits to `cards/<id>/CARD.md`, ledger rows. They rode into the
install commit. Now the printed line and `--commit` name only what install itself writes: the committed settings file,
`<bundle>/.gitignore`, `<bundle>/.gitattributes`, `<bundle>/mkway.lock`, `<bundle>/engine`, and the profile only when
this run created it (the starter). Nothing else in the bundle. A profile that already existed is not named, even when
`--shared` changed it: the owner's file is committed by the owner.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | `install --commit` with a modified `cards/<id>/CARD.md` and an untracked `asks/x.md` in the bundle | both rode into the commit | both stay out: the card still modified, the ask still untracked | tests/test_mw036_install_own_paths.py::test_install_commit_leaves_session_files_of_the_bundle_out |
| E2 | the line install prints | `git add <settings> <bundle>; ...` | names `.claude/settings.json`, `<bundle>/.gitignore`, `.gitattributes`, `mkway.lock`, `engine`, plus `profile.json` only on the run that created it | tests/test_mw036_install_own_paths.py::test_the_printed_line_names_only_installs_paths |
| E3 | the live install flow | no session file in the bundle at the reinstall | an untracked `asks/x.md` stays out of the reinstall commit | tests/test_mw030_live_install.py::test_a_reinstall_commit_takes_only_the_install_paths |
| E4 | README, register, changelog | the install section named the bundle | one sentence names install's own paths; register row; a line under the release that names the card; VERSION: see VERSION | tests/test_mw036_install_own_paths.py::test_readme_register_changelog_and_card_name_the_card |

## 8. Log

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-12 | red: rows E1 to E4 | 3f3d864 | E1, E2, E4 failed for the right reason (the card and the ask were in the commit, the bundle folder was named, README, register row and changelog line missing); E3 is one added step of the live test |
| 2026-11-12 | green: `install_paths`, line and `--commit` limited to install's paths, README, register, changelog | the commit that carries this line | rows E1 to E4 green; whole suite, `python -m pytest`, term scan included, no exception added: 922 passed in 530 s. Test E1 corrected after the red commit (a reinstall of an identical source has nothing to commit; the test now commits an older lock date first and asserts the commit holds only `mkway/mkway.lock`). Older tests changed to the new rule, none dropped: MW-027 E5 and MW-035 E3 and E4 (the path list) |
| 2026-11-12 | MW-040: row E4 named a release number or an old VERSION | the commit that carries this line | the row says «see VERSION» and «the release that names the card»; its test reads the VERSION file and finds the card's changelog line (`tests/_docs.py`), no release number is pinned |
