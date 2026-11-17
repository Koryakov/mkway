# MW-031: git built-in list current, check warns only on the risky side

| | |
|---|---|
| **Appetite** | 40 minutes — from 2026-11-11 |
| **Status** | proposed |
| **Created / updated** | 2026-11-11 / 2026-11-11 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | none new: the standing rule «a gap found in real work gets its own fix card at once» carries it |
| **Canon** | none for the git built-in list: the basis is the gap the live-install test (MW-030) found |
| **Paths** | `engine/`, `tests/`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-031-git-builtins-current/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository. `VERSION` is not changed here.

## 1. Goal

`mkway check` on this machine's git printed a warning at every owner's first check: git has five built-ins the engine
list lacks (`backfill`, `diff-pairs`, `last-modified`, `repo`, `survey`), the list has one git lacks (`env--helper`),
and the fix asked the owner to edit an engine file. Now the list in `engine/defaults.json` is the old list plus the
five names, without `env--helper` (an internal helper). The risky side is a name only in the list: the gate trusts it
as a built-in although git may run an alias or an external command; `check` warns on it and the fix is to update
mkway. A name only in git is an over-refusal, the safe side: an info part of the line, and the owner may allow it with
the new profile key `lock_gate.git_builtins_extra`, read by the check and by the lock and commit gates. On this
machine `check` prints no warning.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | the list | lacks five git built-ins, holds `env--helper` | holds the five, no `env--helper`, no name twice | tests/test_mw031_git_builtins.py::test_the_list_holds_the_names_this_git_added_and_keeps_the_old_one |
| E2 | a name only in the list | a warning asking for an engine file edit | a warning naming it, fix: update mkway | tests/test_mw031_git_builtins.py::test_a_name_only_in_the_list_warns_and_the_fix_is_to_update_mkway |
| E3 | a name only in git | a warning asking for an engine file edit | an info part naming the name and the profile key, no warning | tests/test_mw031_git_builtins.py::test_a_name_only_in_git_is_info_and_names_the_profile_key |
| E4 | the profile key | none | extends the list for the check and the git form reader; an unusable value is no key | tests/test_mw031_git_builtins.py::test_the_profile_key_extends_the_list_for_the_check_and_the_gate |
| E5 | the schema | no `lock_gate` group | `lock_gate.git_builtins_extra` is an array of names | tests/test_mw031_git_builtins.py::test_the_schema_accepts_the_key_and_refuses_a_wrong_type |
| E6 | KEYS.md | engine row says «unverified»; no profile key row | added-keys row; engine row names MW-031 | tests/test_mw031_git_builtins.py::test_keys_md_names_the_key_and_the_direction |
| E7 | register, changelog | no word | register row, a line under the release that names the card; VERSION: see VERSION | tests/test_mw031_git_builtins.py::test_register_changelog_and_card_name_the_card |
| E8 | the check on this machine's list | a warning | the plain match line, no warning | tests/test_mw031_git_builtins.py::test_the_list_gives_this_machine_no_warning |

## 8. Log

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-11 | red: rows E1 to E7 | 4a02694 | 7 failed, each for the right reason (five names missing; `extra` unknown; no `lock_gate` in the schema; no row, no card) |
| 2026-11-11 | the git call `git --list-cmds=builtins` was refused by the session's guard hook, naming no way out; the union uses the five names of the task order (what `mkway check` printed on this machine's git: only in git) | — | the list is the old list plus those five; a new git may add more, and the check then warns with the profile-key fix |
| 2026-11-11 | which direction matters (how the gate uses the list, R90): `helpers.git_form_problem` refuses `git <sub>` as `command-unparsed` when `<sub>` is not in the list. A name in git and not in the list: a plain built-in is refused, so the owner's own command is blocked until the list is extended: that is what the warning is for. A name in the list and not in this git: the gate lets `git <name>` through as a built-in although this git does not know it; it would only matter when a configured alias or an external `git-<name>` carries that name, and the one such name is `env--helper`, a built-in of older git versions. So the risky side is «only in the list», not the task order's first direction; see the next row | — | the orderer confirmed the reading (2026-11-11) |
| 2026-11-11 | rows E1 to E3 were wrong (they warned on «only in git» and kept `env--helper`): changed by the orderer's order after the direction analysis above; row E8 added; the three tests changed with them, then the code. Not weakened: each row still checks one direction and the fix text | c2f32f3 | red 2: 3 failed for the right reason (`env--helper` still listed; «only in the list» no warning; «only in git» still a warning) |
| 2026-11-11 | green 2: `env--helper` out of the list; the check line reversed (warn on «only in the list», fix: update mkway; «only in git» an info part naming `lock_gate.git_builtins_extra`); KEYS.md, schema text | the commit that carries this line | rows E1 to E8 green; whole suite, `python -m pytest`, term scan included, no exception added: 870 passed in 380 s |
| 2026-11-11 | green: list, `profiles.git_builtins_extra`, `helpers.git_form_problem(extra)`, `git_builtins_line(extra)`, schema group, KEYS.md rows, `tests/test_keys.py` expected set gains `lock_gate.git_builtins_extra` and `tests/test_schema.py` expected groups gain `lock_gate` (test changes for the new key: same checks, one more expected entry each, not weakened); register row, changelog line | the commit that carries this line | rows E1 to E7 green |
| 2026-11-11 | whole suite, `python -m pytest`, term scan included; no term-scan exception added | the commit that carries this line | 869 passed in 419 s |
| 2026-11-11 | MW-027 ported onto master 4fd59c6: it bumps VERSION to 0.2.7, so row E7's «VERSION still 0.2.6» cannot hold; the row and the version pin in the test read 0.2.7, the same change MW-027 makes in the version pins of the older cards; the register and changelog asserts are kept | the commit that carries this line | see the MW-027 Log |
| 2026-11-12 | MW-040: row E7 named a release number or an old VERSION | the commit that carries this line | the row says «see VERSION» and «the release that names the card»; its test reads the VERSION file and finds the card's changelog line (`tests/_docs.py`), no release number is pinned |
