# MW-035: Install finishes its own commit in one correct step

| | |
|---|---|
| **Appetite** | 60 minutes — from 2026-11-11 |
| **Status** | proposed |
| **Created / updated** | 2026-11-11 / 2026-11-11 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | none new: the standing rule «a gap found in real work gets its own fix card at once» carries it |
| **Canon** | none for install: the basis is the gap the owner's own reinstall found |
| **Paths** | `engine/`, `tests/`, `README.md`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-035-install-one-line/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository. `VERSION` is not changed here.

## 1. Goal

«I want to have SIMPLE instruction!» — owner, 2026-11-11. A reinstall over an earlier install printed that the bundle
`.gitignore` still ignored `engine/` and left the line, so the engine copy stayed untracked until the owner edited
the file by hand. It then printed two commit lines; the index already held a builder's 79 staged files, so a plain
`git commit` would have taken them into the install commit. The product repository needs every commit message to start
with the task id, and the printed message did not. Now install removes that one stale line and says so. The commit
step commits only install's own paths (`git commit -m "<message>" -- <settings> <bundle>`), whatever else is staged;
`--commit` runs exactly that, and without it install prints one line to paste (both commands joined with `;`). The
message starts with the profile key `commit.message_prefix` when it is set.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | a bundle `.gitignore` with the line `engine/` from an earlier install | reported, line left | the exact line `engine/` is removed, every other line stays; one report line `ignore: removed engine/ (from an earlier install)` | tests/test_mw035_install_line.py::test_a_stale_engine_ignore_line_is_removed_and_the_others_stay |
| E2 | `install --commit` while another file is staged | the commit took the staged file too | only install's paths are committed; the other file stays staged | tests/test_mw035_install_line.py::test_install_commit_takes_only_its_own_paths |
| E3 | the line install prints without `--commit` | two lines, the commit line indented | one line, no leading space: `git add <settings> <bundle>; git commit -m "<message>" -- <settings> <bundle>` | tests/test_mw035_install_line.py::test_the_printed_commit_step_is_one_line_without_a_leading_space |
| E4 | profile key `commit.message_prefix` set (for example `#10536`) | no key | the message is `<prefix> mkway <version>: install`, printed and committed; unset: `mkway <version>: install` as before | tests/test_mw035_install_line.py::test_the_message_prefix_starts_the_install_message |
| E5 | the key in the schema and KEYS.md | absent | in the schema (a string without spaces or shell characters) and a line of KEYS.md | tests/test_mw035_install_line.py::test_the_message_prefix_key_is_in_the_schema_and_keys |
| E6 | the live install flow | no reinstall with a stale line and a staged foreign file | reinstall with `--commit` over an install whose `.gitignore` holds `engine/` while a foreign file is staged: engine tracked, foreign file still staged and not in the commit | tests/test_mw030_live_install.py::test_a_reinstall_commit_takes_only_the_install_paths |
| E7 | README, register, changelog | the install section named two lines | `install ... --commit` is the one-step way; register row; a line under `## 0.2.7`; VERSION still 0.2.7 | tests/test_mw035_install_line.py::test_readme_register_changelog_and_card_name_the_card |

## 8. Log

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-11 | red: rows E1 to E7 | e588b3f | nine tests failed for the right reason (stale line kept, two lines printed, staged file taken, no prefix, key not in schema, README and register row missing) |
| 2026-11-12 | green: stale `engine/` line removed, one pasted line, commit limited to install's paths, `commit.message_prefix` in schema and KEYS.md, README, register, changelog | the commit that carries this line | rows E1 to E7 green; whole suite, `python -m pytest`, term scan included, no exception added: 919 passed in 501 s. Older tests changed to the new rule, none dropped: MW-027 E5 (one line) and E9 (line removed, not reported), `test_install_names_old_ignore_lines_for_cards_and_ledger` (every old line kept except `engine/`), `test_keys` (the new key in the schema list). README commit-gate section names the key as not a gate key (its test lists every `commit.*` key). One step added to `tests/test_mw030_live_install.py` (E6) |
