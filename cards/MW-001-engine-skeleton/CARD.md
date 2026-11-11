# MW-001: Engine skeleton

| | |
|---|---|
| **Status** | Done |
| **Created / updated** | 2026-11-09 / 2026-11-09 |
| **Waiting for** | nothing |

Folder: `cards/MW-001-engine-skeleton/`. Form: `cards/_TEMPLATE/CARD.md` (cleaned from the source template at the pin).

## 1. Goal

The engine repository exists with its rails, its own card register, the engine manifest, the engine defaults, the
branch-profile schema with its checker, and a term scan that keeps task data out. No hook code and no installer.

## 2. Scope

| In scope | Out of scope (non-goals) |
|---|---|
| `CLAUDE.md`, `README.md`, `.gitignore`, `.claude/settings.json`, `tools/term_scan.py`, `cards/`, `engine/manifest.json`, `engine/defaults.json`, `engine/KEYS.md`, `engine/profile.schema.json`, `engine/schema_check.py`, `fixtures/synthetic/`, `tests/` | hook code, the installer, the drift line, the root resolver, the item model, any port of a source file |

## 2b. Risks and consequences

Task data enters the engine: noticed by the term scan over every tracked file before every commit and the
English-only test. A write lands outside the repository: prevented by the launch-settings fence and the `CLAUDE.md`
rail. A value is guessed: prevented by marking it «not established» in `KEYS.md` or here.

## 2c. Start conditions

| # | Start condition | Input read | Test |
|---|---|---|---|
| S1 | The session runs in an empty engine folder | the engine folder | checked by the session at start (`pwd`, listing); no test file |
| S2 | A term file is given by env | `ENGINE_TERMS_FILE` | `tests/test_repo_scan.py` (fails «term list missing» without it) |
| S3 | The source configs and the card template can be read at the pin | the pin read form | none; refused at start, allowed by the owner later on 2026-11-09 (Log) |

## 3. Requirements

| # | Requirement | Source (decision / rule) |
|---|---|---|
| R1 | Rails: `CLAUDE.md`, `README.md`, `.gitignore`, tracked machine-independent deny rules | work order §0, deliverable 1 |
| R2 | Term scan from an env or config term file; empty default list; fails «term list missing»; allow marker; prints `path:line` and group/index only | work order deliverable 1 |
| R3 | Register and this card; cleaned template saved as `cards/_TEMPLATE/CARD.md` | work order deliverable 2 |
| R4 | Manifest: 27 planned + 7 off-today entries; product checks left out; the home-folder reader off by default | work order deliverable 3 |
| R5 | Defaults: the 31 engine-default keys, values read at the pin; natural-language ones «later» | work order deliverable 4 |
| R6 | Profile schema of the Q2 groups, checker, two synthetic profiles (depth 2, depth 3), `KEYS.md` 75 lines | work order deliverable 5 |
| R7 | Every Test cases row has its test; the manifest names no product check and no home path | work order deliverable 6 |

## 4. Guardrails

| # | Rule |
|---|---|
| SG1 | Write only inside the repository, by any means |
| SG2 | Read the source repository only at the pin, with the one read form; copy no file and no code block |
| SG3 | No task data, no Cyrillic, synthetic fixtures only |
| SG4 | Never open the term file; only the scan reads it |
| SG5 | Red tests first; never weaken a test |

## 5. Validation criteria

| # | Given / When / Then | Covers | Script | Severity | Result (date, numbers) |
|---|---|---|---|---|---|
| V1 | Given the repository / When the full suite runs / Then all Test cases rows pass and the term scan reports 0 hits | R1-R7 | `python -m pytest` | error | see Log |
| V2 | Given a temporary clone / When each red commit is checked out / Then its new tests fail | SG5 | operator check | error | operator |

## 5b. Test cases

| # | Test | Real result checked | Expected (bool / count) | Test file |
|---|---|---|---|---|
| E1 | `test_missing_term_list_fails` | no file and an empty default list → «term list missing», exit 2 | true | `tests/test_term_scan.py` |
| E2 | `test_planted_literal_found` | a planted literal in a temp file is found at its line | 1 hit | `tests/test_term_scan.py` |
| E3 | `test_cyrillic_group_found` | a `re:` Cyrillic group finds a planted Cyrillic letter | 1 hit | `tests/test_term_scan.py` |
| E4 | `test_allow_marker_counts_exception` | a line with the allow marker is an exception, not a hit | 1 hit, 1 exception | `tests/test_term_scan.py` |
| E5 | `test_hit_output_never_shows_term` | the report shows `path:line group <G> #<n>`, never the term | true | `tests/test_term_scan.py` |
| E6 | `test_config_names_term_file_when_env_absent` | with no env, the config's `terms_file` is used | 1 entry | `tests/test_term_scan.py` |
| E7 | `test_scan_covers_tracked_files_only` | the repository walk lists tracked files and skips untracked ones | true | `tests/test_term_scan.py` |
| E8 | `test_repository_has_no_term_hits` | the repository has 0 hits; with no term file it fails «term list missing» | 0 hits | `tests/test_repo_scan.py` |
| E9 | `test_repository_is_english_only` | no tracked file holds a Cyrillic letter | 0 lines | `tests/test_repo_scan.py` |
| E10 | `test_register_row_points_to_card_folder` | the register has the id/title/status/folder table and each row's folder holds `CARD.md` | true | `tests/test_register.py` |
| E11 | `test_card_has_template_sections` | (changed for R12) `cards/_TEMPLATE/CARD.md` is the cleaned one-page form: 8 header labels, sections Goal · Acceptance examples · Log, their columns, at most 40 lines before the log; every card after R12 has the same (MW-001 is history, C8) | true | `tests/test_register.py` |
| E12 | `test_planned_entries_are_the_27_registered_engine_commands` | 27 planned entries with the map's event, matcher, timeout, onFailure and mode | 27 (14 block) | `tests/test_manifest.py` |
| E13 | `test_off_today_entries_are_the_7_unregistered_gates` | 7 off-today entries, event and matcher «not established» | 7 | `tests/test_manifest.py` |
| E14 | `test_entries_carry_all_fields` | each entry has name, script, event, matcher, timeout, onFailure, mode, status, default_on | 34 | `tests/test_manifest.py` |
| E15 | `test_manifest_names_no_product_check_and_no_home_path` | no product check; no home path except in `default_on: false` entries | true | `tests/test_manifest.py` |
| E16 | `test_home_folder_reader_is_off_by_default` | `own_files_stop` has `default_on: false` and the note «platform store, undocumented» | true | `tests/test_manifest.py` |
| E17 | `test_every_default_key_is_placed_once` | each of the 31 keys is in `defaults.json` or marked in `KEYS.md`, never both | 31 | `tests/test_defaults.py` |
| E18 | `test_natural_language_defaults_are_later` | `language` and `texts` are «later (natural-language content; needs an owner read)» | true | `tests/test_defaults.py` |
| E19 | `test_depth2_profile_passes` | the depth-2 synthetic profile passes the check | 0 errors | `tests/test_schema.py` |
| E20 | `test_depth3_profile_passes` | the depth-3 synthetic profile passes the check | 0 errors | `tests/test_schema.py` |
| E21 | `test_broken_profile_fails_naming_key` | a broken profile fails, and the error names the key | 7 cases | `tests/test_schema.py` |
| E22 | `test_schema_declares_the_q2_groups` | the 11 groups are declared; the later ones optional and empty | true | `tests/test_schema.py` |
| E23 | `test_keys_md_has_one_line_per_draft_key` | 75 lines, each «in schema now» or «later», matching the schema | 75 (13 / 62) | `tests/test_keys.py` |
| E24 | `test_defaults_read_at_pin_have_map_types` | no default stays «not established»; each value has the map's type | 0 not established | `tests/test_defaults.py` |

### Red and green commits

| # | Red commit | Green commit |
|---|---|---|
| E1-E10 | d7cfef3 | 122a89e |
| E11 | e39714d, then (R12) e475add | 96f1c57, then (R12) c3240bc |
| E12-E16 | f08b8e7 | 4166fb4 |
| E17-E23 | 807dc73 | bf1ec2d |
| E24 | e39714d | 96f1c57 |

## 6. Plan

| Step | What | Data write | Rollback | Approval |
|---|---|---|---|---|
| 1 | Rails, card, red term-scan and register tests (E1-E10) | no | revert commit | — |
| 2 | Term scan, register (E1-E10 green) | no | revert commit | — |
| 3 | Red manifest tests, then the manifest (E12-E16) | no | revert commit | — |
| 4 | Red defaults, schema and keys tests, then defaults, schema, checker, fixtures, `KEYS.md` (E17-E23) | no | revert commit | — |
| 5 | Pin read: cleaned template and default values (E11, E24) | no | revert commit | given 2026-11-09 (the read rule) |

## 7. Decisions

| Date | Decision | By |
|---|---|---|
| 2026-11-09 | C1: commit 1 is split: rails + red tests first, the scan second; red-first must be provable, and the scan cannot be red after it exists | session |
| 2026-11-09 | C2: `onFailure` keeps the map's word `none`; `matcher: null` stands for the map's «(all)»; whether the registration omits the key is not established | session |
| 2026-11-09 | C3: `session_start` stays on by default; R4(3): its read of the user layer becomes information only, never required | session |
| 2026-11-09 | C4: off-today entries also have timeout, onFailure and mode «not established» and `default_on: false`; no registration exists for them | session |
| 2026-11-09 | C5: `engine/defaults.json` carries `_about` only; the 29 values wait for the pin read; no consumer may rely on defaults before then (pin read refused 09.11). Closed by the green commit after e39714d | operator |
| 2026-11-09 | C6: of the 31 defaults, 24 go in with their pin values; 7 stay later: a host name, two lists of the source task's folder and file names, a suffix list that names a database product, the two natural-language keys, and a marker that carries a source rule id | session |
| 2026-11-09 | C7: the card's commit columns and its card id move under a ### subheading, because the template's tables are fixed | session |
| 2026-11-09 | C8: the engine ships the one-page card form (R12); this card keeps the long form it was written in | retro-chief10 R12, 09.11 |

## 8. Log

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-09 | start | — | empty engine folder; `git init`. The pin read form was refused by the session's permission classifier; reported to the operator |
| 2026-11-09 | 1 | d7cfef3 | rails + red E1-E10: 2 collection errors (`term_scan` missing: E1-E9), `test_register.py` 1 failed (E10). Red as intended (C1) |
| 2026-11-09 | 2 | 122a89e | green E1-E10: 10 passed, 0 failed. Term scan: 92 entries, 0 hits, 0 exceptions |
| 2026-11-09 | 2 | 122a89e | test change `tests/test_repo_scan.py:17` (E9): commit 1 held the two Cyrillic block boundary letters as literal characters (the file tool turned the escapes into letters); E8 and E9 caught them. The regex is now built from code points; the check is unchanged. The letters remain in commit 1's history (no rewrite) |
| 2026-11-09 | 2 | 122a89e | progress: deliverable 1 done (rails, term scan and its tests) |
| 2026-11-09 | 3 | f08b8e7 | red E12-E16: 5 failed (no manifest), 10 passed |
| 2026-11-09 | 3 | 4166fb4 | green E12-E16: 15 passed, 0 failed; term scan 0 hits, 0 exceptions. Progress: deliverable 3 done |
| 2026-11-09 | 4 | 807dc73 | red E17-E23: 3 failed (E17, E18, E23), 1 collection error (E19-E22), 15 passed |
| 2026-11-09 | 4 | bf1ec2d | green E17-E23: 22 passed, 0 failed; term scan 0 hits, 0 exceptions. Progress: deliverable 5 done (13 now, 62 later); deliverable 4 partly done (29 not established) |
| 2026-11-09 | 4 | 2fcb3e0 | the Test cases rows name their red and green commits |
| 2026-11-09 | — | e958778 | decision C5 added (operator fix F2) |
| 2026-11-09 | — | 0245d8d | `KEYS.md`: the two R8 keys (`vcs`, profile location) as later |
| 2026-11-09 | — | a65f601 | `CLAUDE.md`: the template is pending the pin read (operator fix F1, owner yes) |
| 2026-11-09 | 5 | — | the owner allowed the pin read form. Read at the pin, in the tool output only: the card template and the 5 configs of the defaults (6 files, one per call) |
| 2026-11-09 | 5 | e39714d | red E11, E24: 2 failed (E11: no template; E24: 29 keys «not established»), 22 passed |
| 2026-11-09 | 5 | (this commit) | template replacements, in `cards/_TEMPLATE/CARD.md`: the card id form → `<ID>`; process-rule ids and their bundle-rules path references → removed (the rule text kept); «all ST tests» → «all card tests»; «STATUS and the index» → «the register row»; «owner yes» / «a new yes» → «approval» / «a new approval»; the hook name of the start gate with its arguments → «the start gate»; «subtask» → «card»; the workstream list and «5 categories» → «<one of the branch's workstreams>»; the guard id → removed; the S1 example (a property count and a database file name) → «the input file holds N records», `inputs/sample.csv`; the general guardrails file name → «the general guardrails» (heading text moved to a line below it); the rollback example «retire run Y» → removed; «test hook passes» / «hook green» → «tests pass»; plan columns «Store write» → «Data write», «Owner yes» → «Approval» |
| 2026-11-09 | 5 | (this commit) | this card reshaped to the template (C7); defaults: 25 in `defaults.json`, 6 later, 0 not established (C6) |
| 2026-11-09 | 5 | 96f1c57 | green E11, E24: 24 passed, 0 failed; term scan 92 entries, 0 hits, 0 exceptions. The two «(this commit)» rows above are 96f1c57 |
| 2026-11-09 | 5 | 96f1c57 | progress: deliverables 2 and 4 done (template; 25 defaults, 6 later; 24 and 7 after the delta-check fix below) |
| 2026-11-09 | — | (this commit) | delta content check, fix F1: `bash_speed_guard.marker` is a task string (its prefix is a source process-rule id); removed from `defaults.json`, «later» in `KEYS.md`; C6 updated; split 24 in `defaults.json`, 7 later. No test counts the 24/25 split (E17 counts the 31 keys, E24 the types), so no test changes and no red commit is needed |
| 2026-11-09 | — | (this commit) | test change, comment only (fix F2): `tests/test_defaults.py` `MAP_TYPES` comment now says the map gives the types of 23 keys and the 8 `decision_search` types come from the pin values. No assertion changed |
| 2026-11-09 | — | (this commit) | `KEYS.md` `acceptance_heading` reason made fuller (delta check row 10); the value stays in `defaults.json` |
| 2026-11-09 | — | 1d45a15 | the three «(this commit)» rows above are 1d45a15: 24 passed, 0 failed; term scan 92 entries, 0 hits, 0 exceptions |
| 2026-11-09 | 6 | (this commit) | E11 row and test changed (R12, retro-chief10 09.11: the engine ships the one-page card form, not the long form). The test now asserts the one-page header labels, the three sections, their columns and the one-page limit; MW-001 is exempt as history (C8). Red against the long template; to be re-checked by a reader who has not seen it |
| 2026-11-09 | 6 | e475add | red E11: 1 failed (E11, long template), 23 passed |
| 2026-11-09 | 6 | — | read at the pin (tool output only): the template folder listing, the card-document hook, the card-fields note and the one-page template (4 calls) |
| 2026-11-09 | 6 | (this commit) | one-page template replacements, in `cards/_TEMPLATE/CARD.md`: the card id form → `<ID>`; decision ids in the Appetite, Form, Canon and how-to text → removed; Form value «card (step and decision ids)» → «card»; Decisions example (decision and case ids) → `<decision ids>`; Canon value (non-English word anchors, a work-item id, a decision id, two tool names) → «`<ledger ids> — settles / does not settle: …` or `none for <terms>`, after a ledger search»; Paths «a pipeline file» → «a covered file»; the copy path and register file name → `cards/<ID>-<slug>/CARD.md`, «the register row»; the field-note path → removed; the line pointing to the long template → removed (R12: it does not ship); the report-tests paragraph (a source report slice) → removed; the text-only card line → removed; the reader-checklist path → «the reader checklist»; «golden id» / «golden case» → removed (tests only); Acceptance columns «Property» → «Item», «Golden or test» → «Test», and the example row to match |
| 2026-11-09 | 6 | (this commit) | `KEYS.md` `acceptance_heading` reason: the template now carries the heading (R12); verdict stays «in defaults.json» |
| 2026-11-09 | 6 | c3240bc | the «(this commit)» rows above are c3240bc: green E11, 24 passed, 0 failed; term scan 92 entries, 0 hits, 0 exceptions. Progress: R12 template swap done |
| 2026-11-09 | — | (this commit) | red/green table: E11 now names e475add / c3240bc (R12) after e39714d / 96f1c57. `KEYS.md`: a defaults.json key outside the schema is an engine constant (R12 point 4, confirmed by retro-chief10) |
| 2026-11-09 | — | 2ba8023 | the «(this commit)» row above is 2ba8023: 24 passed, 0 failed; term scan 92 entries, 0 hits, 0 exceptions |
| 2026-11-09 | — | (this commit) | test change E11, blind-check fix 1: the template's headings must be exactly the title plus `## 1. Goal`, `## Acceptance examples`, `## 8. Log` (a long-form section as `###` or `#`, or after the Log, passed before). It tightens the test; the current template passes it, so no red commit |
| 2026-11-09 | — | (this commit) | test change E11, blind-check fix 2: the ban on the «Store write» and «Owner yes» columns is restored (R12 did not justify removing it). It tightens the test; the current template passes it, so no red commit |
| 2026-11-09 | — | (this commit) | test change E11, blind-check fix 3: the history exemption is bound to the id and the folder (`MW-001`, `cards/MW-001-engine-skeleton`), so a duplicate MW-001 row is checked. It tightens the test; the current register passes it, so no red commit |
| 2026-11-09 | — | 064e38f | the three «(this commit)» rows above are 064e38f: 24 passed, 0 failed; term scan 92 entries, 0 hits, 0 exceptions |
| 2026-11-09 | — | (this commit) | `CLAUDE.md`: the card form is the one-page form, fixed by E11; MW-001 keeps the long form (operator fix F3, owner yes) |
| 2026-11-09 | — | 7169a1e | the «(this commit)» row above is 7169a1e: 24 passed, 0 failed; term scan 92 entries, 0 hits, 0 exceptions |
| 2026-11-09 | close | (this commit) | closed on retro-chief10's word: status Done in this card and in `cards/REGISTER.md` («Done» is the form's closed status). Suite before the commit: 24 passed, 0 failed; term scan 92 entries, 0 hits, 0 exceptions. No more work in this card |
