# MW-016: Version in code, tag in git

| | |
|---|---|
| **Appetite** | 30 minutes — from 2026-11-11 |
| **Status** | proposed |
| **Created / updated** | 2026-11-11 / 2026-11-11 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | none new: ruling R136 carries the design |
| **Canon** | none for versioning: the basis is ruling R136 |
| **Paths** | `VERSION`, `CHANGELOG.md`, `README.md`, `engine/install.py`, `engine/startline.py`, `tests/`, `cards/REGISTER.md`, `cards/MW-016-version/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository.

## 1. Goal

The version lives in a `VERSION` file in the code; the git tag `v<version>` is the owner's and is never written by the
engine. The start block shows the version, the lock carries it, `mkway check` warns when the tag at HEAD is missing or
differs, and a changelog cannot drift from the register — ruling R136.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | `VERSION` file | none | root file, one line, one semantic version (see VERSION) | tests/test_mw016_version.py::test_the_version_file_is_semver |
| E2 | start block, first line | `mkway <tag or unversioned>; profile: ...` | `mkway v<VERSION of the copy> (<sha or ref>); profile: ...`, read from the copy's own `VERSION` | tests/test_mw016_version.py::test_the_start_block_shows_the_copys_version |
| E3 | `mkway.lock` | version (tag), source sha, date, hash | also `semver`, the source's `VERSION` text, beside the sha; the copy holds `VERSION` | tests/test_mw016_version.py::test_the_lock_carries_the_version |
| E4 | `mkway check`, tag at HEAD missing or different from `v<version>` | silent | a warning line naming the expected tag; a matching tag gives a plain line; no tag is ever written | tests/test_mw016_version.py::test_check_warns_on_a_missing_or_a_different_tag; tests/test_mw016_version.py::test_check_prints_the_tag_line |
| E5 | `CHANGELOG.md` | none | the top heading is the VERSION text and older releases stand below it; every register card id with its title on one line, so it cannot drift | tests/test_mw016_version.py::test_the_changelog_covers_the_register |
| E6 | README | no versioning text | section `## Versioning` with the bump rule (patch, minor, major) and the owner's tags | tests/test_mw016_version.py::test_the_readme_has_the_versioning_section |

## 8. Log

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-11 | red: rows E1 to E6 | c13f57a | 7 tests red |
| 2026-11-11 | green: `VERSION`, `CHANGELOG.md`, README `## Versioning`, `semver` in the lock, `VERSION` in the install set, start line `mkway v<version> (<sha or ref>)`, `version_tag_line` in `check` | the commit that carries this line | 7 targeted tests green; one test helper fixed (a missing parent folder in the scratch repo helper), no check weakened |
| 2026-11-11 | expectations changed by the rule: `test_install.py` lock key set gains `semver`; `test_e2e.py` and `test_startline.py` first line now `mkway v<VERSION> (<ref>)` | the commit that carries this line | expectation only, as the rule changes it; no check removed |
| 2026-11-11 | whole suite, `python -m pytest`, term scan included | the commit that carries this line | 630 passed in 219 s (was 623 on the base); no term-scan exception added |
| 2026-11-11 | landed statuses for the changelog test: every register row counts, whatever its status (closed, open, waiting, proposed): a row exists once the card is in the tree, and the status is the owner's, not a sign of landing | — | reading, to confirm |
| 2026-11-11 | reading: the tag line is printed by `check` when the root holds a `VERSION` file and the profile's vcs is git (so the engine repository, not an ordinary task root); the lock keeps `version` (the tag or `unversioned`) and adds `semver`; no tag is created in any run | — | to confirm |
| 2026-11-12 | MW-040: row E1, E5 named a release number or an old VERSION | the commit that carries this line | the row says «see VERSION» and «the release that names the card»; its test reads the VERSION file and finds the card's changelog line (`tests/_docs.py`), no release number is pinned |
