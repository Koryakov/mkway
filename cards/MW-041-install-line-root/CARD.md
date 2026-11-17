# MW-041: The printed install line works from any folder; ignore cleanup is CRLF-safe

| | |
|---|---|
| **Appetite** | 45 minutes — from 2026-11-12 |
| **Status** | proposed |
| **Created / updated** | 2026-11-12 / 2026-11-12 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | none new: the standing rule «a gap found in real work gets its own fix card at once» carries it |
| **Canon** | none for install: the basis is the gap a live task's install found |
| **Paths** | `engine/install.py`, `tests/`, `README.md`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-041-install-line-root/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository. `VERSION` is not changed here.

## 1. Goal

The owner pasted the line install prints from another folder; its paths are relative to the task root, so nothing
happened. Now the line names the absolute root in both commands, `git -C "<root>" add <paths>; git -C "<root>" commit
-m "<message>" -- <paths>`, root quoted (it may hold spaces), so it works pasted anywhere in PowerShell and bash.
`--commit` is unchanged. Second gap: the stale `engine/` ignore line of an earlier install was removed only on an
exact LF match; a CRLF file (`engine/` + `\r`), `/engine/` or `engine` stayed. Now all three spellings go (after
stripping spaces and `\r`), every other line stays, and the file keeps its own line ending style.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | the printed line run by a real shell (bash; PowerShell) from a different folder | `git add <relative paths>` did nothing outside the root | it commits install's paths in the task | tests/test_mw041_install_line_root.py::test_the_printed_line_commits_install_paths_from_another_folder |
| E2 | a task folder with a space in its path | not covered | the root is quoted in both commands and the line commits | tests/test_mw041_install_line_root.py::test_the_printed_line_works_when_the_root_holds_a_space |
| E3 | a CRLF `.gitignore` with `engine/` | the line stayed | the line goes, other lines stay, every line end is CRLF | tests/test_mw041_install_line_root.py::test_a_crlf_ignore_file_loses_the_engine_line_and_keeps_its_line_ends |
| E4 | the lines `/engine/`, `engine`, with spaces, CRLF or LF | stayed | removed, other lines stay, the file's line ending style is kept | tests/test_mw041_install_line_root.py::test_the_other_spellings_of_the_engine_line_are_removed |
| E5 | README, register, changelog | no MW-041 | one sentence says the line works from any folder; register row; a line under the release that names the card; VERSION: see VERSION | tests/test_mw041_install_line_root.py::test_readme_register_changelog_and_card_name_the_card |

## 8. Log

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-12 | red: rows E1 to E5; older tests changed to the new line (MW-027 E5, MW-035 E3 and E4, MW-036 E2), none dropped | 65bd6c3 | E1 failed for the right reason (the printed line had no `git -C "<root>"`) |
| 2026-11-12 | green: `commit_lines` names the root, stale engine ignore line matched on three spellings, ignore file read and written with its own line ends, README, register, changelog | the commit that carries this line | rows E1 to E5 green; whole suite, `python -m pytest`, term scan included, no exception added: 933 passed in 657 s |
| 2026-11-12 | MW-040: row E5 named a release number or an old VERSION | the commit that carries this line | the row says «see VERSION» and «the release that names the card»; its test reads the VERSION file and finds the card's changelog line (`tests/_docs.py`), no release number is pinned |
