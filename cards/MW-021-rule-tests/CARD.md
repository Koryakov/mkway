# MW-021: Rule cards paired with tests

| | |
|---|---|
| **Appetite** | 90 minutes — from 2026-11-11 |
| **Status** | proposed |
| **Created / updated** | 2026-11-11 / 2026-11-11 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | none new: the order of 2026-11-11 (card E) carries the design |
| **Canon** | none for rule cards and their tests: the basis is the order of 2026-11-11 |
| **Paths** | `engine/rules.py`, `engine/gate_commit.py`, `engine/mkway.py`, `engine/startline.py`, `engine/profile.schema.json`, `engine/manifest.json`, `engine/KEYS.md`, `README.md`, `CHANGELOG.md`, `tests/`, `cards/REGISTER.md`, `cards/MW-021-rule-tests/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository.

## 1. Goal

A rule card and its test travel together: a commit that adds or changes a rule card must stage its test file too, a
card whose test file does not exist is refused, and `mkway rules` and the start block show which cards have no test —
order of 2026-11-11, card E. The version is not changed here: the owner sets it once for the release.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | profile keys `rules.cards`, `rules.test_for` | none | schema: `cards` a non-empty list of globs, `test_for` a string with `{id}`; unknown key refused | tests/test_mw021_keys.py::test_the_schema_takes_the_two_rules_keys |
| E2 | the settings | none | empty and off without both keys; a bad value falls back to off | tests/test_mw021_keys.py::test_the_settings_default_to_off_and_tolerate_a_bad_value |
| E3 | KEYS.md | no lines | one «in schema now» line per key, default `none` named | tests/test_mw021_keys.py::test_keys_md_has_a_line_for_each_key_with_its_default |
| E4 | commit adds a card, test file missing | allowed | refused `rule-without-test`, text names card, test path and `git add <test>` | tests/test_mw021_commit.py::test_a_new_rule_card_with_no_test_file_is_refused |
| E5 | commit changes a card, its test not staged | allowed | refused `rule-without-test` ("not staged"); card with its test, in the index or in `-- <paths>`, allowed | tests/test_mw021_commit.py::test_a_changed_card_needs_its_test_staged_too; tests/test_mw021_commit.py::test_the_named_paths_form_is_read_too |
| E6 | what stays allowed; the gate class | — | a test changed alone, a deleted card, a file outside the globs, a name with no id, a profile with one key or no `ids.rule_card`: allowed; reason declared on `commit_files`, class integrity | tests/test_mw021_commit.py::test_what_is_allowed; tests/test_mw021_commit.py::test_the_check_is_off_without_both_keys_and_without_the_id_form; tests/test_mw021_commit.py::test_the_manifest_declares_the_reason_in_the_integrity_commit_gate |
| E7 | `mkway rules` | none | per card: id, card path, test path, `exists`/`missing`, last green tree (8 characters or `none`) from `commit_tests.jsonl`; a line naming the keys when off | tests/test_mw021_command.py::test_rules_lists_each_card_with_its_test_and_its_last_green_tree; tests/test_mw021_command.py::test_rules_says_what_to_set_when_the_check_is_off |
| E8 | start block | no line | `rules: N cards, M without tests`, only when the keys are set | tests/test_mw021_command.py::test_the_start_block_counts_the_cards_and_the_ones_without_tests |
| E9 | README | no text | section `## Rule cards paired with tests` | tests/test_mw021_readme.py::test_one_section_with_a_body; tests/test_mw021_readme.py::test_the_section_names_the_keys_the_reason_the_command_and_the_start_line |

## 8. Log

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-11 | red: rows E1 to E9 | 3b4c3c6 | 14 tests red |
| 2026-11-11 | green: `engine/rules.py`, rule 6 `rule-without-test` in `gate_commit.py`, `rules` in the schema and the manifest, `mkway rules`, the start line, KEYS lines, README section | the commit that carries this line | 14 targeted tests green |
| 2026-11-11 | setup fixes in the red tests, no check weakened: the test card's Paths named `tests/`, a test root that `card open` refuses as too wide, now `tests/rules/`; a removal is recorded as the session's own write before the delete test | the commit that carries this line | same assertions |
| 2026-11-11 | expectations changed by the rule: `test_keys.py` (two keys), `test_schema.py` (group `rules`), `test_mw006_commit_message.py` and `test_mw006_readme.py` (reason `rule-without-test`, 11 reasons), `test_mw016_version.py` (the changelog test counts the lines of every release section, as cards now fall under `## 0.2.0`); README Commit checks gains point 6 | the commit that carries this line | expectation only, as the rule changes it; no check removed |
| 2026-11-11 | whole suite, `python -m pytest`, term scan included | the commit that carries this line | 644 passed in 283 s (was 630 on the base); no term-scan exception added |
| 2026-11-11 | ported onto master 72cea05 (MW-017 merged) by editing files; `test_mw017_docs.py` line 88 now checks that the MW-017 line is a member of the `## 0.2.0` section, not that it is the only line, as MW-021 also lands under 0.2.0 (change authorised in the port task) | the commit that carries this line | expectation only; the MW-017 line is still required |
| 2026-11-11 | `VERSION` not changed, as ordered: the changelog row sits under `## 0.2.0`, and the owner sets the version once for the release | — | reading, to confirm |
| 2026-11-11 | reading: with no `ids.rule_card` no file name holds an id, so nothing is refused and the keys alone do not switch the check on; the last green tree is the newest `pass` row whose tree holds the card's test file (a tree has no per-card result), looked at over the newest 50 green rows | — | to confirm |
| 2026-11-11 | the order's incident ids (task chain, work items, rule numbers) are not copied here: the repository holds no id of another task's process | — | reading, to confirm |
