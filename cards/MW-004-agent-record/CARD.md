# MW-004: agent records, a saved result and a time for every helper agent

| | |
|---|---|
| **Appetite** | 1.5 hours — from 2026-11-10 |
| **Status** | open |
| **Created / updated** | 2026-11-10 / 2026-11-10 |
| **Waiting for** | nothing |
| **Form** | card |
| **Decisions** | none: the order «only group A» is the whole scope |
| **Canon** | none for agent records: the engine has no ledger |
| **Paths** | `engine/`, `tests/`, `README.md`, `cards/REGISTER.md`, `cards/MW-004-agent-record/` |

## 1. Goal

«only group A» — owner, 2026-11-10. As relayed in the task for this card: every helper agent's result is saved
automatically, with its start and end time (a source task measured most helper results never collected, and one
agent idle for hours). Four parts: (1) a `post` record for `SubagentStart` and `SubagentStop` into
`<state>/agents.jsonl`; (2) the profile key `agents.cap_minutes` (default 30) and one start-block line per agent of
the session that ran over it or never ended; (3) install writes the hook entries; (4) a README section.

## Acceptance examples

Rows are added with the red tests of each part. A time the hook cannot establish is the text «not established».

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | `SubagentStart` row | no record of an agent start | one appended line `{kind: start, session_id, agent_id, agent_type, started}` in `<state>/agents.jsonl` | tests/test_mw004_agents.py::test_start_row_is_appended |
| E2 | `SubagentStop` row, result from the payload | the result is lost when the agent ends | one line `{kind: end, session_id, agent_id, agent_type, started, ended, elapsed_seconds, result, result_source: payload}`; `started` is that agent's start row, `result` is `last_assistant_message` in full | tests/test_mw004_agents.py::test_stop_row_carries_the_result_and_the_times |
| E3 | `SubagentStop` row, result from the transcript | none | with no `last_assistant_message`, `result` is the text of the last assistant message of the file `agent_transcript_path` names, in full, `result_source: transcript` | tests/test_mw004_agents.py::test_result_comes_from_the_agent_transcript_when_the_payload_has_none |
| E4 | no result anywhere | none | the row is still written: `result` and `result_source` say «not established» / `none` | tests/test_mw004_agents.py::test_no_result_is_not_established |
| E5 | stop with no start row | none | `started` and `elapsed_seconds` are «not established», `ended` is set | tests/test_mw004_agents.py::test_stop_without_a_start_row_has_no_times |
| E6 | two agents, two sessions | none | a stop pairs with the start of the same session and agent id only | tests/test_mw004_agents.py::test_a_stop_pairs_with_its_own_start |
| E7 | a record that cannot be written | none | exit 0, nothing on stdout (a warn on `SubagentStop` must never keep the agent going), a `warn` row `agent-record-failed` in the refusal log | tests/test_mw004_agents.py::test_a_failed_record_never_blocks_and_adds_no_context |
| E8 | a payload with no agent id | none | a row is still written, the id is «not established» | tests/test_mw004_agents.py::test_a_payload_without_an_agent_id_is_still_recorded |
| E9 | gates on, through the dispatcher | no gate on these events | two `on` manifest entries, group `post`, events `SubagentStart` and `SubagentStop`, no matcher, `onFailure: none`; the dispatcher writes the rows, exit 0, empty stdout | tests/test_manifest.py::test_on_entries_carry_function_reasons_and_on_failure_reason; tests/test_mw004_agents.py::test_the_dispatcher_records_both_events |
| E10 | `agents.cap_minutes` in the schema | no `agents` group | a number above 0; 0, a negative, a string, a boolean, null, a list are profile errors naming the key; any other key in `agents` is refused | tests/test_mw004_cap.py::test_schema_takes_a_positive_cap; tests/test_mw004_cap.py::test_schema_refuses_an_unusable_cap; tests/test_mw004_cap.py::test_schema_refuses_another_agents_key |
| E11 | the cap's default | none | 30 when the key, the group or the profile is missing; the profile's value otherwise | tests/test_mw004_cap.py::test_cap_default_and_profile_value |
| E12 | start block, over the cap | no agent line | one line for each agent of this session whose end row is longer than the cap (strictly), with its type, id, minutes and the cap; none at the cap, under it, for another session, or with no known time | tests/test_mw004_cap.py::test_start_block_lists_an_agent_over_the_cap; tests/test_mw004_cap.py::test_profile_cap_sets_the_limit |
| E13 | start block, no end row | no agent line | one line for each agent of this session whose last row is a start row: the start time and the minutes so far; a finished agent gets none | tests/test_mw004_cap.py::test_start_block_lists_an_agent_with_no_end_row |
| E14 | start block, nothing to report | none | no agent line and no header when there is no file or every agent finished under the cap | tests/test_mw004_cap.py::test_start_block_has_no_agent_line_when_there_is_nothing |
| E15 | a damaged `agents.jsonl` | none | a line that is not JSON and a row of the wrong shape are skipped; the block is still shown, exit 0 | tests/test_mw004_cap.py::test_a_damaged_agents_file_is_skipped_not_fatal |
| E16 | KEYS.md | no row | `agents.cap_minutes` in the added keys: in schema now, default 30 | tests/test_mw004_cap.py::test_keys_md_lists_the_cap; tests/test_keys.py::test_keys_md_has_one_line_per_draft_key |
| E17 | generated entries | none for the agent events | one whole entry for each of `SubagentStart` and `SubagentStop`, group `post`, after `PostToolUse`: command `python -I -X utf8 "${CLAUDE_PROJECT_DIR}/mkway/engine/mkway.py" hook <event> --group post`, no matcher, no onFailure, timeout 25 | tests/test_mw004_install.py::test_generate_entries_has_both_agent_events |
| E18 | the gate switch | none | `gates.agents.on: false` leaves out both agent entries and no other | tests/test_mw004_install.py::test_the_gate_switch_drops_both_entries |
| E19 | the settings file | none | a group with no matcher under each event; a second write changes nothing; a foreign hook under the same event is kept | tests/test_mw004_install.py::test_settings_hold_the_agent_entries_once |
| E20 | a real install | none | `mkway install` writes both entries; the generated commands run as Claude Code runs them exit 0 with empty stdout and append the start and the end row; the start block says `drift: none` and lists both gates | tests/test_mw004_install.py::test_a_real_install_records_an_agent |
| E21 | README | no section on agent records | one `## Agent records` section, at most 16 lines: the two events, `agents.jsonl`, `agents.cap_minutes` with default 30, the switch `gates.agents.on`, the two result sources, «not established», and that the hook never blocks | tests/test_mw004_readme.py::test_readme_has_a_short_agent_records_section |

## 8. Log

One line per step. No re-run of a check or an agent round without a new input named in the Log row.

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-10 | A0 | — | start checks, each alone: `pwd` is the worktree, `git log -1` is 58e36c1, `git status --short` is clean. Baseline full suite at 58e36c1: 301 passed |
| 2026-11-10 | A0 | — | payload fields read from the Claude Code changelog, read-only: `SubagentStart` carries `session_id`, `agent_id`, `agent_type`; `SubagentStop` adds `agent_transcript_path` and `last_assistant_message`. A fixture of a real payload is not in the engine; the tests use synthetic payloads with these fields |
| 2026-11-10 | A1 | (this commit) | red part 1 (E1-E9): the tests fail for the right reason: no gate runs on these events, so no `agents.jsonl` row is written, and the manifest has no entries for them. Targeted run: 10 failed (9 in `tests/test_mw004_agents.py`, 1 in `tests/test_manifest.py`). Test change: the `ON` list of `tests/test_manifest.py::test_on_entries_carry_function_reasons_and_on_failure_reason` gains the two new entries (the list is the expected set of `on` gates; adding a gate changes it) |
| 2026-11-10 | A1 | 4e7803b | the «(this commit)» row above is 4e7803b |
| 2026-11-10 | A1 | — | test change, E6: the expected elapsed time of the pair (s1, a1) was written 1800 s; the test's clock is absolute, the start is minute 0 and the stop minute 20, so the independent value is 1200 s. The code was right, the row was wrong; changed 1800.0 to 1200.0 in `tests/test_mw004_agents.py::test_a_stop_pairs_with_its_own_start`, nothing else. Test change, interface: `tests/test_gate.py::test_fixture_gates_prove_the_interface` pins the field set of the gate context; it gains `payload` (the whole hook input, which the new gates read for `agent_id`, `agent_type`, `agent_transcript_path`, `last_assistant_message`) |
| 2026-11-10 | A1 | (this commit) | green part 1 (E1-E9): `engine/agents.py` (the rows, the pairing, the result from the payload or the transcript), `engine/gate_agents.py` (`start`, `stop`; never refuse; a write failure is the warn `agent-record-failed`), two `on` manifest entries (`agent_start`, `agent_stop`; group `post`, no matcher, onFailure none), the context field `payload`. The two events stay out of `CONTEXT_EVENTS`, so a warn renders nothing (a context on `SubagentStop` keeps the agent going). Targeted (ten files): 96 passed |
| 2026-11-10 | A1 | 061e257 | the «(this commit)» row above is 061e257 |
| 2026-11-10 | A2 | (this commit) | red part 2 (E10-E16): the tests fail for the right reason: the schema has no `agents` group, `agents.cap_minutes()` does not exist, the start block has no agent lines, KEYS.md has no row. Targeted run: 18 failed, 2 passed. E14 passes today by design: it guards against a header or an empty line added to every start block, and fails the day one is. Test change: the set of added keys pinned in `tests/test_keys.py::test_keys_md_has_one_line_per_draft_key` gains `agents.cap_minutes` |
| 2026-11-10 | A2 | 527e815 | the «(this commit)» row above is 527e815 |
| 2026-11-10 | A2 | — | test change, found by the targeted run: `tests/test_schema.py::test_schema_declares_the_q2_groups` pins the exact set of schema groups; it gains `agents` (E10). Nothing else in it changed |
| 2026-11-10 | A2 | (this commit) | green part 2 (E10-E16): `agents` group in `engine/profile.schema.json` with `cap_minutes` (number, `exclusiveMinimum: 0`, a word `engine/schema_check.py` now reads); `agents.cap_minutes()` (default 30) and `agents.report()` in `engine/agents.py`; `startline._agent_lines` adds the lines after the cards lines and never fails the block; KEYS.md row. The default 30 is a code constant, not a `defaults.json` key: that file is pinned to the port map's keys (`tests/test_defaults.py`), like the `cards.owner_moves` default in `engine/cardtool.py`. An unfinished agent is listed whatever the cap, as the order says. Targeted (eleven files): 100 passed |
| 2026-11-10 | A2 | d8abfa9 | the «(this commit)» row above is d8abfa9 |
| 2026-11-10 | A3 | (this commit) | red part 3 (E17-E20): the tests fail for the right reason: `install.EVENT_ORDER` does not list the two events, so the manifest's agent entries are not loadable on install and no entry is generated or written. Targeted run: 4 failed. E18 first passed vacuously (nothing generated, nothing to drop); it now asserts the entries exist by default before the switch drops them |
| 2026-11-10 | A3 | 5431ede | the «(this commit)» row above is 5431ede |
| 2026-11-10 | A3 | (this commit) | green part 3 (E17-E20): `engine/install.py` `EVENT_ORDER` lists `SubagentStart` and `SubagentStop`; nothing else in install changed: the entries come from the manifest's two `on` entries (part 1), through the same generator, so the command is the root launcher with `python -I -X utf8`, the group table gives no onFailure, and the drift check compares them like the others. Targeted (six files, the real install included): 49 passed in 245 s |
| 2026-11-10 | A3 | 615bfd7 | the «(this commit)» row above is 615bfd7 |
| 2026-11-10 | A4 | (this commit) | red part 4 (E21): the test fails for the right reason: the README has no `## Agent records` section. Targeted run: 1 failed. Part 3's wider check, before this step: `tests/test_e2e.py` 9 passed (it runs every generated hook command, the two new ones included) |
| 2026-11-10 | A4 | 1791bf1 | the «(this commit)» row above is 1791bf1 |
| 2026-11-10 | A4 | (this commit) | green part 4 (E21): README section «Agent records», 14 lines, before «Known limits». Targeted (README test, repo scan, term scan): 13 passed |
| 2026-11-10 | A4 | bf09b4b | the «(this commit)» row above is bf09b4b |
| 2026-11-10 | A5 | (this commit) | fix found by the full suite (the targeted runs could not see it): at bf09b4b `tests/test_install.py::test_check_compares_hash_runs_tests_and_skips_scan` and `::test_check_runs_the_term_scan_when_a_term_file_is_set` failed, 2 failed, 331 passed. `mkway check` runs the tests of an installed copy, and the copy has no `README.md`, so `tests/test_mw004_readme.py` failed there (1 failed, 297 passed, 35 deselected). The test now carries the `engine_repo` marker, as the other tests that read repository-only files do. No assertion changed. The two install tests, rerun: 2 passed |
| 2026-11-10 | A5 | 08b2902 | the «(this commit)» row above is 08b2902 |
| 2026-11-10 | A6 | (this commit) | full suite with the term scan, `python -m pytest`, at 08b2902: 333 passed in 329 s (baseline at 58e36c1: 301; the 32 new tests are 9 in `test_mw004_agents.py`, 18 in `test_mw004_cap.py`, 4 in `test_mw004_install.py`, 1 in `test_mw004_readme.py`). Not done, by the order's scope: no review round, no agent. Not built: a live check inside a running Claude Code session; the payload fields come from the changelog and the tests use synthetic payloads with them, so the first real `SubagentStop` should be looked at once (`<state>/agents.jsonl`, and `refusals.jsonl` for `agent-record-failed`). The card stays `open` for the owner |
| 2026-11-10 | A6 | cde2bed | the «(this commit)» row above is cde2bed (the last source commit) |
| 2026-11-10 | P1 | (this commit) | port of the branch t3 onto master 681f5ec (MW-007 content kept): the source commits are 58e36c1..cde2bed (4e7803b, 061e257, 527e815, d8abfa9, 5431ede, 615bfd7, 1791bf1, bf09b4b, 08b2902, cde2bed), re-applied by hand as one change, no merge and no cherry-pick. Files from t3 as they are: `engine/agents.py`, `engine/gate_agents.py`, this card, the four `tests/test_mw004_*.py`. Edited in place, both sides kept: README (section «Agent records» after «Questions to the owner»), `cards/REGISTER.md`, `engine/KEYS.md`, `engine/dispatch.py`, `engine/gate.py`, `engine/install.py`, `engine/manifest.json`, `engine/profile.schema.json`, `engine/schema_check.py`, `engine/startline.py`, `tests/test_gate.py`, `tests/test_keys.py`, `tests/test_manifest.py`, `tests/test_schema.py` |
| 2026-11-10 | P1 | — | what the combination broke, found by the full suite (first run: 4 failed, 361 passed): master's MW-007 installs a `Stop` hook entry by default, so the expected event lists of `tests/test_mw004_install.py::test_generate_entries_has_both_agent_events` (E17) and `::test_the_gate_switch_drops_both_entries` (E18) were one entry short. Each list gains `Stop` at its end; no assertion weakened. The two `tests/test_install.py` check tests failed only because `mkway check` runs the copy's own tests, these two included; no change to them |
| 2026-11-10 | P1 | — | note for the owner: the context now carries two fields with the same content, `hook_input` (MW-007) and `payload` (this card), both set to the whole hook input by the dispatcher; `engine/gate_agents.py` reads `payload`. Kept both by the order («keep both sides»); a later change could fold `payload` into `hook_input` (the code, `tests/test_gate.py` and the card E-rows that name `payload` would change together) |
| 2026-11-10 | P1 | — | full suite with the term scan, `python -m pytest`, after the port, before the commit: 365 passed in 332 s (the first run at the same tree before the two test-list fixes: 4 failed, 361 passed) |
| 2026-11-10 | P1 | 57c196e | the «(this commit)» row of P1 above is 57c196e, the port commit. The guard hook refused the commit message while it held parentheses; the message was written without them |
