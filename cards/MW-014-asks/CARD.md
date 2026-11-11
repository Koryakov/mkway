# MW-014: Asks that do not stop the work

| | |
|---|---|
| **Appetite** | 2 hours — from 2026-11-10 |
| **Status** | proposed |
| **Created / updated** | 2026-11-10 / 2026-11-11 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | none new: the order of 2026-11-10 carries the design |
| **Canon** | none for asks: the engine has no ledger; the basis is the order of 2026-11-10 and its research note |
| **Paths** | `engine/asks.py`, `engine/gate_owner_ask.py`, `engine/startline.py`, `engine/mkway.py`, `engine/manifest.json`, `engine/profile.schema.json`, `engine/profiles.py`, `engine/KEYS.md`, `README.md`, `tests/`, `cards/REGISTER.md`, `cards/MW-014-asks/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository. The card was written on a base without the watch-mode `class` field of the manifest; the port onto master
(2026-11-11) adds it: see the Log.

## 1. Goal

A builder asked the owner a question and waited for hours while the owner believed work was in progress. An ask must be a
file that carries a default, a deadline, what waits and whether it can be undone; it must reach the owner at once; a
session may have one open ask; and at the deadline a reversible ask takes its default, logged, while an irreversible
one stays waiting — order of 2026-11-10.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | ask with a missing field line | any `_ask.md` passed with its sources | refused `ask-fields-missing`, the text names each missing line of `default`, `deadline`, `blocked`, `reversible`, `status: open` | tests/test_mw014_gate.py::test_a_missing_field_line_is_refused_and_named; tests/test_mw014_gate.py::test_an_ask_with_no_field_names_all_five |
| E2 | field with no usable value | no check | an empty value, a deadline that is not ISO or `none`, a `reversible` other than yes or no, a status other than `open` count as missing | tests/test_mw014_gate.py::test_a_field_with_an_unusable_value_counts_as_missing |
| E3 | complete ask, Edit and MultiEdit | not judged | allowed by every write tool; an edit is judged on the file it leaves; sources first; other files untouched | tests/test_mw014_gate.py::test_a_complete_ask_is_allowed_by_every_write_tool; tests/test_mw014_gate.py::test_an_edit_is_judged_on_the_file_it_leaves; tests/test_mw014_gate.py::test_the_fields_come_after_the_sources_and_leave_other_files_alone |
| E4 | second open ask of a session | allowed | refused `ask-already-open` (add to the open ask, or wait); other session, closed ask, existing ask, `owner_ask.max_open` and a missing file handled; the post step records the writer | tests/test_mw014_gate.py::test_a_second_open_ask_by_the_same_session_is_refused; tests/test_mw014_gate.py::test_an_ask_that_is_no_longer_open_frees_the_session; tests/test_mw014_gate.py::test_max_open_comes_from_the_profile; tests/test_mw014_gate.py::test_a_session_without_an_id_and_a_missing_file_do_not_count; tests/test_mw014_gate.py::test_the_post_step_records_who_wrote_an_ask |
| E5 | `AskUserQuestion` | reached the search gate | refused `ask-tool-off` with the file route; `owner_ask.tool_allowed: true` allows | tests/test_mw014_gate.py::test_the_pop_up_question_tool_is_refused_with_the_file_route; tests/test_mw014_gate.py::test_the_switch_lets_the_pop_up_question_tool_through |
| E6 | wiring of the edit entry | matcher of three write tools | the entry `owner_ask.edit` also matches `AskUserQuestion`, declares the new reasons, runs before `search` | tests/test_mw014_gate.py::test_the_dispatcher_refuses_the_pop_up_tool_before_the_search_gate; tests/test_mw014_keys.py::test_the_edit_entry_also_matches_the_question_tool_and_declares_the_new_reasons |
| E7 | notify command | none | after an ask file is written `notify.command` runs with `{file}` and `{line}` filled, no shell; nothing without a command or for other files; the post entry is wired | tests/test_mw014_notify.py::test_the_command_runs_with_the_file_and_the_line_filled; tests/test_mw014_notify.py::test_nothing_runs_without_a_command_or_for_other_files; tests/test_mw014_notify.py::test_the_post_group_runs_the_notify_entry_and_writes_the_log_row; tests/test_mw014_notify.py::test_the_manifest_entry_of_the_notify_step |
| E8 | notify failure | none | a failing or slow (10 s) command is logged `notify-failed` and never blocks | tests/test_mw014_notify.py::test_a_failing_command_is_logged_and_never_blocks; tests/test_mw014_notify.py::test_a_slow_command_is_stopped_at_the_limit |
| E10 | board | none | `mkway asks` prints one row per ask file: id, card, age, deadline, default, status, blocked | tests/test_mw014_board.py::test_the_board_has_one_row_per_ask_file; tests/test_mw014_board.py::test_the_board_with_no_ask_and_with_an_unreadable_one |
| E11 | start block line | none | `open asks: N (oldest <age>); past deadline: M; defaults taken since the owner's last re-seal: K` | tests/test_mw014_board.py::test_the_start_block_counts_the_open_asks_with_their_age |
| E12 | reminder | none | only the owning session, only past the deadline, only an open ask | tests/test_mw014_board.py::test_the_reminder_is_for_the_session_that_owns_an_ask_past_its_deadline; tests/test_mw014_board.py::test_the_prompt_group_carries_the_reminder_through_the_dispatcher |
| E13 | default before the deadline | none | `mkway ask default` refused `ask-deadline-not-passed` (also with no deadline); nothing changes | tests/test_mw014_commands.py::test_the_default_is_refused_before_the_deadline_and_with_no_deadline |
| E14 | default of an irreversible ask | none | refused `ask-not-reversible`, «stays waiting; the owner decides» | tests/test_mw014_commands.py::test_the_default_of_an_irreversible_ask_stays_waiting |
| E15 | default taken | none | ledger row «default taken: <default text>, ask <id>», `status: default-taken`, log row, `ask-default` record; other refusals named; file otherwise unchanged; not owner-only | tests/test_mw014_commands.py::test_other_refusals_name_their_reason; tests/test_mw014_commands.py::test_the_default_is_taken_when_reversible_and_past_the_deadline; tests/test_mw014_commands.py::test_the_status_line_keeps_the_file_otherwise; tests/test_mw014_commands.py::test_the_ask_commands_are_not_owner_only |
| E16 | answered | none | `mkway ask answered <id>` sets `answered` and writes the ledger row with the quote file's text | tests/test_mw014_commands.py::test_answered_writes_the_owners_words_from_the_quote_file |
| E17 | README | no section | the section «Asks that do not stop the work»: fields, one-open rule, never-default list, notify example, board, every reason and key | tests/test_mw014_readme.py::test_one_section_with_a_body; tests/test_mw014_readme.py::test_the_section_names_every_reason_key_and_command; tests/test_mw014_readme.py::test_the_section_states_the_never_default_list_and_marks_the_example |
| E19 | keys | none | `owner_ask.max_open`, `owner_ask.tool_allowed`, `notify.command` in the schema, the accessors and KEYS.md | tests/test_mw014_keys.py::test_the_schema_takes_max_open_and_tool_allowed; tests/test_mw014_keys.py::test_the_accessor_defaults_and_tolerates_a_bad_value; tests/test_mw014_keys.py::test_keys_md_has_a_line_for_each_new_ask_key; tests/test_mw014_notify.py::test_the_schema_and_the_accessor_for_notify_command; tests/test_mw014_notify.py::test_keys_md_has_a_line_for_notify_command |

## 8. Log

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-10 | red: part 1, rows E1 E2 E3 E4 E5 E6 E19 | d89cb8d | 33 tests red, the older ask tests send a complete ask |
| 2026-11-10 | green: part 1, `engine/asks.py`, gate fields, one-open rule, `ask-tool-off`, keys `max_open` and `tool_allowed` | fcd7612 | targeted tests green; older owner-ask defaults and README tests widened for the new keys (expectation only) |
| 2026-11-10 | red: part 2, rows E7 E8 E19 | 977088f | notify tests red |
| 2026-11-10 | green: part 2, notify step, `notify.command`, manifest entry `owner_ask.notify` | d891e76 | targeted tests green; start-block off list names the new entry |
| 2026-11-10 | red: part 3, rows E10 E11 E12 | 0bdce60 | board, start line and reminder tests red |
| 2026-11-10 | green: part 3, `mkway asks`, start line, entry `owner_ask.remind` | 5117571 | targeted tests green |
| 2026-11-10 | red: part 4, rows E13 E14 E15 E16 | 8becd25 | command tests red |
| 2026-11-10 | green: part 4, `mkway ask default` and `mkway ask answered` | 7616281 | targeted tests green; one assertion on the ledger row's source text corrected to name the ask file, as the row does |
| 2026-11-10 | red: part 5, row E17 | d257b85 | README tests red |
| 2026-11-10 | green: part 5, README section | 1d3b01a | README tests green |
| 2026-11-10 | known limit: the ledger row of a default has `by` = the owner's label, as `ledger.add` sets it; the quote says `default taken` | — | to settle at the port (an optional `by` argument of `ledger.add`) |
| 2026-11-11 | search gate test fixture allows the pop-up tool: `owner_ask.tool_allowed: true` in `tests/test_mw008_gate.py` | — | expectation only, the search gate rows are unchanged |
| 2026-11-11 | whole suite, `python -m pytest`, term scan included | — | 596 passed in 214 s (was 518 on the base); no term-scan exception added |
| 2026-11-11 | port onto master 5316a02: source commits 0718ca8..312ad40 (the ten MW-014 commits d89cb8d to 1d3b01a and the card commit 312ad40) | the commit that carries this line | files master had not changed copied from t12; README, KEYS, REGISTER, mkway, schema, startline, manifest and the two test files merged by hand |
| 2026-11-11 | port: classes chosen, ruling R129 rule 3 and R126 rule 1: `owner_ask.edit` form (it now also matches `AskUserQuestion`); `owner_ask.notify` (PostToolUse) and `owner_ask.remind` (UserPromptSubmit) integrity, as they never block, like records and agents | the commit that carries this line | `class` added to the three manifest entries |
| 2026-11-11 | notify and remind are class form, so the owner_ask gate stays form; they never refuse, so watch has no effect on them | the commit that carries this line | replaces the integrity class of the previous line for these two entries; two MW-012 tests expect owner_ask to be a form gate |
| 2026-11-11 | `tests/test_mw012_class.py` FORM set widened by the entries `owner_ask.notify` and `owner_ask.remind` | the commit that carries this line | expectation only: the set names the entries of the form gate owner_ask; no check removed |
| 2026-11-11 | port: whole suite, `python -m pytest`, term scan included | the commit that carries this line | 616 passed in 230 s; no term-scan exception added |
| 2026-11-11 | Known limit: a default's ledger row is labelled by=owner, because ledger.add has no by argument | — | kept as is |
