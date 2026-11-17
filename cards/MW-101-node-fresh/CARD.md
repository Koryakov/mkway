# MW-101: A verdict stays fresh while its node's meaning is unchanged, read from git

| | |
|---|---|
| **Appetite** | 2 hours — from 2026-11-13 |
| **Status** | proposed |
| **Created / updated** | 2026-11-13 / 2026-11-13 |
| **Waiting for** | nothing |
| **Form** | card |
| **Decisions** | R196, R181, R253 — ids only, no text copied from the ledger; a commit that changes a test names one |
| **Canon** | none for node freshness at close: the basis is a real close that refused three unchanged nodes after a sibling node was recut, and rulings R196, R181, R253 |
| **Paths** | `engine/core_node_fresh.py`, `engine/verdicts.py`, `engine/proof.py`, `tests/`, `README.md`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-101-node-fresh/CARD.md` |

## 1. Goal

«at close a row is fresh when, since the commit of its record, neither the node's function source nor any non-test code of its own file (module level, fixtures, helpers, imports) changed, read from git; a change in another test function of the file does not make it stale.» — R253, 2026-11-13. Close side only: `verdict add` and the outbox are unchanged. The close reads the record's reader agent and the record's file blob, never the file's mtime (R196). No new refusal id: a stale row reads `verdict-unproven` with a new text. Named gap: cross-file helpers (`tests/_*.py` kits, `conftest.py`) are not read (R253).

## Acceptance examples

Each row becomes a test; `card close` needs every row to name one. E1 to E28: the pure core; E29 to E44: the shell on a real git repo; E45 to E47: the real close and the replay of the real case; E48 to E49: the documents; E50 and E51: the two branches the coverage run found untested (added after the code, see the Log).

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | equal old and new text | n/a | fresh | tests/core/test_mw101_node_fresh_core.py::test_equal_text_is_fresh |
| E2 | a sibling test function changed | n/a | fresh | tests/core/test_mw101_node_fresh_core.py::test_a_sibling_test_function_changed_is_fresh |
| E3 | the node's body changed | n/a | stale, kind `node` | tests/core/test_mw101_node_fresh_core.py::test_the_node_body_changed_is_stale |
| E4 | the node's decorator changed | n/a | stale, kind `node` | tests/core/test_mw101_node_fresh_core.py::test_the_node_decorator_changed_is_stale |
| E5 | the node's docstring changed | n/a | stale, kind `node` | tests/core/test_mw101_node_fresh_core.py::test_the_node_docstring_changed_is_stale |
| E6 | an in-file fixture changed | n/a | stale, kind `code` | tests/core/test_mw101_node_fresh_core.py::test_an_in_file_fixture_changed_is_stale |
| E7 | an in-file helper changed | n/a | stale, kind `code` | tests/core/test_mw101_node_fresh_core.py::test_an_in_file_helper_changed_is_stale |
| E8 | an import changed | n/a | stale, kind `code` | tests/core/test_mw101_node_fresh_core.py::test_an_import_changed_is_stale |
| E9 | a module constant changed | n/a | stale, kind `code` | tests/core/test_mw101_node_fresh_core.py::test_a_module_constant_changed_is_stale |
| E10 | a comment between statements changed (nearest allow of E6 to E9) | n/a | fresh | tests/core/test_mw101_node_fresh_core.py::test_a_comment_between_statements_is_fresh |
| E11 | a blank line added between statements (nearest allow of E6 to E9) | n/a | fresh | tests/core/test_mw101_node_fresh_core.py::test_a_blank_line_between_statements_is_fresh |
| E12 | a sibling method of the node's class changed | n/a | fresh | tests/core/test_mw101_node_fresh_core.py::test_a_sibling_method_of_the_class_changed_is_fresh |
| E13 | a non-test method of the node's class changed | n/a | stale, kind `code` | tests/core/test_mw101_node_fresh_core.py::test_a_non_test_method_of_the_class_changed_is_stale |
| E14 | the same name in another class changed (the right class is found) | n/a | fresh | tests/core/test_mw101_node_fresh_core.py::test_the_same_name_in_another_class_changed_is_fresh |
| E15 | a fixture named test_root (call form) changed | n/a | stale, kind `code` | tests/core/test_mw101_node_fresh_core.py::test_a_fixture_named_test_root_changed_is_stale |
| E16 | a fixture named test_bare (bare decorator) changed | n/a | stale, kind `code` | tests/core/test_mw101_node_fresh_core.py::test_a_fixture_named_test_bare_changed_is_stale |
| E17 | a comment inside a fixture changed | n/a | stale, kind `code` | tests/core/test_mw101_node_fresh_core.py::test_a_comment_inside_a_fixture_is_stale |
| E18 | a parametrized node, a sibling changed | n/a | fresh | tests/core/test_mw101_node_fresh_core.py::test_a_parametrized_node_with_a_sibling_changed_is_fresh |
| E19 | a parametrized node, its function changed | n/a | stale, kind `node` | tests/core/test_mw101_node_fresh_core.py::test_a_parametrized_node_with_its_function_changed_is_stale |
| E20 | the old text does not parse | n/a | stale, kind `unreadable` | tests/core/test_mw101_node_fresh_core.py::test_an_old_text_that_does_not_parse_is_stale |
| E21 | the new text does not parse | n/a | stale, kind `unreadable` | tests/core/test_mw101_node_fresh_core.py::test_a_new_text_that_does_not_parse_is_stale |
| E22 | the node is missing in the new text | n/a | stale, kind `missing` | tests/core/test_mw101_node_fresh_core.py::test_a_node_missing_in_the_new_text_is_stale |
| E23 | the node is missing in the old text | n/a | stale, kind `missing` | tests/core/test_mw101_node_fresh_core.py::test_a_node_missing_in_the_old_text_is_stale |
| E24 | a top-level node, only the same name in a class changed | n/a | fresh | tests/core/test_mw101_node_fresh_core.py::test_a_top_level_node_is_not_the_method_of_a_class |
| E25 | the class header (a base) changed | n/a | stale, kind `code` | tests/core/test_mw101_node_fresh_core.py::test_a_class_header_changed_is_stale |
| E26 | an async sibling test changed | n/a | fresh | tests/core/test_mw101_node_fresh_core.py::test_an_async_sibling_changed_is_fresh |
| E27 | a node nested deeper than one class | n/a | stale, kind `missing` | tests/core/test_mw101_node_fresh_core.py::test_a_node_nested_deeper_than_one_class_is_stale |
| E28 | the core module imports | n/a | no I/O module, only `ast` and typing | tests/core/test_mw101_node_fresh_core.py::test_the_core_imports_no_io_module |
| E29 | the record's blob, HEAD changed only in a sibling test | stale by mtime | proven | tests/shell/test_mw101_node_fresh_facts.py::test_a_sibling_only_change_at_head_leaves_the_row_proven |
| E30 | HEAD changed in a fixture | proven or stale by mtime | unproven, the text names both blobs | tests/shell/test_mw101_node_fresh_facts.py::test_a_fixture_change_at_head_is_unproven_and_names_both_blobs |
| E31 | the node's own body changed at HEAD | n/a | unproven, the text names the node | tests/shell/test_mw101_node_fresh_facts.py::test_a_node_body_change_at_head_is_unproven_and_names_the_node |
| E32 | the file touched (mtime newer), content equal (R196) | unproven | proven | tests/shell/test_mw101_node_fresh_facts.py::test_a_newer_mtime_with_equal_content_leaves_the_row_proven |
| E33 | the reader proof: the record's agent ended in its session before the record | n/a | proven | tests/shell/test_mw101_node_fresh_facts.py::test_the_records_agent_ended_before_the_record_is_proven |
| E34 | no end row for the record's agent | n/a | unproven | tests/shell/test_mw101_node_fresh_facts.py::test_an_agent_with_no_end_row_is_unproven |
| E35 | the agent ended in another session | n/a | unproven | tests/shell/test_mw101_node_fresh_facts.py::test_an_agent_that_ended_in_another_session_is_unproven |
| E36 | the agent is not of a checker type | n/a | unproven | tests/shell/test_mw101_node_fresh_facts.py::test_an_agent_of_a_non_checker_type_is_unproven |
| E37 | the agent ended after the record's time | n/a | unproven | tests/shell/test_mw101_node_fresh_facts.py::test_an_agent_that_ended_after_the_record_is_unproven |
| E38 | a record with no `agent` key | proven by any run | unproven | tests/shell/test_mw101_node_fresh_facts.py::test_a_record_with_no_agent_key_is_unproven |
| E39 | a record with no `tests` blob for the file | n/a | unproven | tests/shell/test_mw101_node_fresh_facts.py::test_a_record_without_a_tests_blob_is_unproven |
| E40 | a `tests` blob git cannot read (a made-up sha) | n/a | unproven | tests/shell/test_mw101_node_fresh_facts.py::test_a_blob_git_cannot_read_is_unproven |
| E41 | the test file gone at HEAD | n/a | unproven | tests/shell/test_mw101_node_fresh_facts.py::test_a_file_missing_at_head_is_unproven |
| E42 | a `tests` value that is no sha (an option word) | n/a | unproven, git never sees it as an option | tests/shell/test_mw101_node_fresh_facts.py::test_a_blob_that_is_no_sha_is_unproven |
| E43 | the outbox judges a check file by its mtime | by mtime | by mtime, unchanged | tests/shell/test_mw101_node_fresh_facts.py::test_the_outbox_still_judges_a_check_file_by_its_mtime |
| E44 | `fresh_reader_problem` with an explicit `changed` time | the mtime only | the given time replaces the mtime | tests/shell/test_mw101_node_fresh_facts.py::test_an_explicit_changed_time_replaces_the_mtime |
| E45 | `card close` on a DD-008 shape: three unchanged nodes, one recut node with a new true row | refused `verdict-unproven` | the verdict check passes | tests/shell/test_mw101_node_fresh_close.py::test_card_close_passes_with_three_unchanged_nodes_and_one_recut_node |
| E46 | the same repo, a fixture changed after the rows | refused | refused `verdict-unproven` for the nodes of that file | tests/shell/test_mw101_node_fresh_close.py::test_card_close_refuses_unproven_after_a_fixture_change |
| E47 | replay of the real case: three true rows, a sibling node changed, recut, fresh true row | refused `verdict-unproven` on A, B, C | no refusal | tests/shell/test_mw101_node_fresh_close.py::test_replay_a_sibling_recut_leaves_three_rows_fresh |
| E48 | register row, changelog line, card | none | present, the changelog line last in the top section | tests/test_mw101_docs.py::test_register_changelog_and_card_name_the_card |
| E49 | the README paragraph | none | last paragraph of the section of the verdict command paragraph; names the rule and the gap | tests/test_mw101_docs.py::test_the_readme_paragraph_names_the_rule_and_the_gap |
| E50 | git cannot start `cat-file` for the record's blob | n/a | unproven, "cannot be read from git" | tests/shell/test_mw101_node_fresh_facts.py::test_a_git_that_cannot_read_the_blob_leaves_the_row_unproven |
| E51 | git cannot start `rev-parse` for HEAD's blob | n/a | unproven, "is not in HEAD" | tests/shell/test_mw101_node_fresh_facts.py::test_a_git_that_cannot_name_the_head_blob_leaves_the_row_unproven |

## 8. Log

One line per step. No re-run of a check or an agent round without a new input named in the Log row.

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-13 | start checks, each alone: `pwd` = the worktree, HEAD 57b2314, `git status --short` = clean; owner of this run, 13.11: only my own files plus tests/core, tests/test_meta_cards.py and tests/test_register.py, no whole suite (void of the common rule); no new refusal id, so no profile switch and no manifest id | none | acceptance table written before any test |
| 2026-11-13 | named gap (R253): cross-file helpers (`tests/_*.py` kits, `conftest.py`) are not read; a change there leaves a row fresh; closed when an incident shows it | none | open |
| 2026-11-13 | red proof, `python -m pytest -n 4 --dist loadgroup` on the four new files: 21 failed and 1 collection error (the core file, red by missing module `core_node_fresh`, so its 28 ids), 7.71 s; the first run had 3 passed (E36, E37 and E46: the old rule refused or proved them too), changed so the old rule would prove the row and only the new rule refuses, and re-run red | fb0c0a2 | every new id red: yes |
| 2026-11-13 | first green run showed the close world of E45 and E47 refused: its fix to the fourth test added a module constant, which is non-test code, so the refusal was right and the test was wrong; re-run with only the function body changed passes (3 passed); a test change, so a tests-only commit naming R253 | 68be431 | cause removed, re-run green: 3 passed |
| 2026-11-13 | existing tests that read the old close rule, found by running the files that touch the verdict check: the shared record helper `tests/_mw068.py` now commits the test file and records its blob as the command does (a record with no blob is unproven by the rule); one record fixture names its agent; one expected text names the new reader refusal; two MW-100 document checks no longer require their changelog line and README paragraph to be last; 18 failed before, 0 after; tests only, naming R253 and why | af72a59 | re-run green: 16 passed in the two shell and e2e files, 5 in the two docs files |
| 2026-11-13 | green: `engine/core_node_fresh.py` (new, pure), `engine/verdicts.py` (`_reader_problem`, `_meaning_problem`, `_blob_text`, `_head_blob`), `engine/proof.py` (`changed` time and `agent` id as optional parameters, default unchanged, so `outbox.py` is untouched), README paragraph at the end of the section of the verdict command paragraph, register row, changelog line; the `agent` id parameter is one more than the order named: without it `fresh_reader_problem` would accept any fresh agent of the session as the record's reader (a test showed it), and the existing test that requires both the outbox and the close to read the proof through that one helper stays true | 82c705a | rows E1 to E49 green |
| 2026-11-13 | coverage run on the three code test files, `python -m coverage run --branch -m pytest`: the first run missed 320-321 and 330-331 of `engine/verdicts.py` (git fails to start for the blob and for the head blob); two tests added, each shown red by breaking its `except` branch (both failed) and green again with the branch restored; after: `engine/core_node_fresh.py` 100 percent, every changed line of `engine/verdicts.py` and `engine/proof.py` run, both arms of each new if; the lines still missed in those two files are older code, not changed here (verdicts 280-283, 287, 291; proof 30-31, 61) | c92dda1 | missed lines of the changed code: none |
| 2026-11-13 | the whole run of the order, `python -m pytest -n 4 --dist loadgroup`: tests/core, the four new files, tests/test_meta_cards.py, tests/test_register.py and the six existing files touched by the tests-only commits: 2237 passed in 27.51 s; no whole suite, no term scan run (owner 13.11: the merge gate runs the whole suite once) | c92dda1 | 2237 passed, 28.6 s wall |
| 2026-11-13 | acceptance E1 | 82c705a | tests/core/test_mw101_node_fresh_core.py::test_equal_text_is_fresh: red seen yes (missing module), green yes |
| 2026-11-13 | acceptance E2 | 82c705a | tests/core/test_mw101_node_fresh_core.py::test_a_sibling_test_function_changed_is_fresh: red seen yes (missing module), green yes |
| 2026-11-13 | acceptance E3 | 82c705a | tests/core/test_mw101_node_fresh_core.py::test_the_node_body_changed_is_stale: red seen yes (missing module), green yes |
| 2026-11-13 | acceptance E4 | 82c705a | tests/core/test_mw101_node_fresh_core.py::test_the_node_decorator_changed_is_stale: red seen yes (missing module), green yes |
| 2026-11-13 | acceptance E5 | 82c705a | tests/core/test_mw101_node_fresh_core.py::test_the_node_docstring_changed_is_stale: red seen yes (missing module), green yes |
| 2026-11-13 | acceptance E6 | 82c705a | tests/core/test_mw101_node_fresh_core.py::test_an_in_file_fixture_changed_is_stale: red seen yes (missing module), green yes |
| 2026-11-13 | acceptance E7 | 82c705a | tests/core/test_mw101_node_fresh_core.py::test_an_in_file_helper_changed_is_stale: red seen yes (missing module), green yes |
| 2026-11-13 | acceptance E8 | 82c705a | tests/core/test_mw101_node_fresh_core.py::test_an_import_changed_is_stale: red seen yes (missing module), green yes |
| 2026-11-13 | acceptance E9 | 82c705a | tests/core/test_mw101_node_fresh_core.py::test_a_module_constant_changed_is_stale: red seen yes (missing module), green yes |
| 2026-11-13 | acceptance E10 | 82c705a | tests/core/test_mw101_node_fresh_core.py::test_a_comment_between_statements_is_fresh: red seen yes (missing module), green yes |
| 2026-11-13 | acceptance E11 | 82c705a | tests/core/test_mw101_node_fresh_core.py::test_a_blank_line_between_statements_is_fresh: red seen yes (missing module), green yes |
| 2026-11-13 | acceptance E12 | 82c705a | tests/core/test_mw101_node_fresh_core.py::test_a_sibling_method_of_the_class_changed_is_fresh: red seen yes (missing module), green yes |
| 2026-11-13 | acceptance E13 | 82c705a | tests/core/test_mw101_node_fresh_core.py::test_a_non_test_method_of_the_class_changed_is_stale: red seen yes (missing module), green yes |
| 2026-11-13 | acceptance E14 | 82c705a | tests/core/test_mw101_node_fresh_core.py::test_the_same_name_in_another_class_changed_is_fresh: red seen yes (missing module), green yes |
| 2026-11-13 | acceptance E15 | 82c705a | tests/core/test_mw101_node_fresh_core.py::test_a_fixture_named_test_root_changed_is_stale: red seen yes (missing module), green yes |
| 2026-11-13 | acceptance E16 | 82c705a | tests/core/test_mw101_node_fresh_core.py::test_a_fixture_named_test_bare_changed_is_stale: red seen yes (missing module), green yes |
| 2026-11-13 | acceptance E17 | 82c705a | tests/core/test_mw101_node_fresh_core.py::test_a_comment_inside_a_fixture_is_stale: red seen yes (missing module), green yes |
| 2026-11-13 | acceptance E18 | 82c705a | tests/core/test_mw101_node_fresh_core.py::test_a_parametrized_node_with_a_sibling_changed_is_fresh: red seen yes (missing module), green yes |
| 2026-11-13 | acceptance E19 | 82c705a | tests/core/test_mw101_node_fresh_core.py::test_a_parametrized_node_with_its_function_changed_is_stale: red seen yes (missing module), green yes |
| 2026-11-13 | acceptance E20 | 82c705a | tests/core/test_mw101_node_fresh_core.py::test_an_old_text_that_does_not_parse_is_stale: red seen yes (missing module), green yes |
| 2026-11-13 | acceptance E21 | 82c705a | tests/core/test_mw101_node_fresh_core.py::test_a_new_text_that_does_not_parse_is_stale: red seen yes (missing module), green yes |
| 2026-11-13 | acceptance E22 | 82c705a | tests/core/test_mw101_node_fresh_core.py::test_a_node_missing_in_the_new_text_is_stale: red seen yes (missing module), green yes |
| 2026-11-13 | acceptance E23 | 82c705a | tests/core/test_mw101_node_fresh_core.py::test_a_node_missing_in_the_old_text_is_stale: red seen yes (missing module), green yes |
| 2026-11-13 | acceptance E24 | 82c705a | tests/core/test_mw101_node_fresh_core.py::test_a_top_level_node_is_not_the_method_of_a_class: red seen yes (missing module), green yes |
| 2026-11-13 | acceptance E25 | 82c705a | tests/core/test_mw101_node_fresh_core.py::test_a_class_header_changed_is_stale: red seen yes (missing module), green yes |
| 2026-11-13 | acceptance E26 | 82c705a | tests/core/test_mw101_node_fresh_core.py::test_an_async_sibling_changed_is_fresh: red seen yes (missing module), green yes |
| 2026-11-13 | acceptance E27 | 82c705a | tests/core/test_mw101_node_fresh_core.py::test_a_node_nested_deeper_than_one_class_is_stale: red seen yes (missing module), green yes |
| 2026-11-13 | acceptance E28 | 82c705a | tests/core/test_mw101_node_fresh_core.py::test_the_core_imports_no_io_module: red seen yes (missing module), green yes |
| 2026-11-13 | acceptance E29 | 82c705a | tests/shell/test_mw101_node_fresh_facts.py::test_a_sibling_only_change_at_head_leaves_the_row_proven: red seen yes, green yes |
| 2026-11-13 | acceptance E30 | 82c705a | tests/shell/test_mw101_node_fresh_facts.py::test_a_fixture_change_at_head_is_unproven_and_names_both_blobs: red seen yes, green yes |
| 2026-11-13 | acceptance E31 | 82c705a | tests/shell/test_mw101_node_fresh_facts.py::test_a_node_body_change_at_head_is_unproven_and_names_the_node: red seen yes, green yes |
| 2026-11-13 | acceptance E32 | 82c705a | tests/shell/test_mw101_node_fresh_facts.py::test_a_newer_mtime_with_equal_content_leaves_the_row_proven: red seen yes, green yes |
| 2026-11-13 | acceptance E33 | 82c705a | tests/shell/test_mw101_node_fresh_facts.py::test_the_records_agent_ended_before_the_record_is_proven: red seen yes, green yes |
| 2026-11-13 | acceptance E34 | 82c705a | tests/shell/test_mw101_node_fresh_facts.py::test_an_agent_with_no_end_row_is_unproven: red seen yes, green yes |
| 2026-11-13 | acceptance E35 | 82c705a | tests/shell/test_mw101_node_fresh_facts.py::test_an_agent_that_ended_in_another_session_is_unproven: red seen yes, green yes |
| 2026-11-13 | acceptance E36 | 82c705a | tests/shell/test_mw101_node_fresh_facts.py::test_an_agent_of_a_non_checker_type_is_unproven: red seen yes, green yes |
| 2026-11-13 | acceptance E37 | 82c705a | tests/shell/test_mw101_node_fresh_facts.py::test_an_agent_that_ended_after_the_record_is_unproven: red seen yes, green yes |
| 2026-11-13 | acceptance E38 | 82c705a | tests/shell/test_mw101_node_fresh_facts.py::test_a_record_with_no_agent_key_is_unproven: red seen yes, green yes |
| 2026-11-13 | acceptance E39 | 82c705a | tests/shell/test_mw101_node_fresh_facts.py::test_a_record_without_a_tests_blob_is_unproven: red seen yes, green yes |
| 2026-11-13 | acceptance E40 | 82c705a | tests/shell/test_mw101_node_fresh_facts.py::test_a_blob_git_cannot_read_is_unproven: red seen yes, green yes |
| 2026-11-13 | acceptance E41 | 82c705a | tests/shell/test_mw101_node_fresh_facts.py::test_a_file_missing_at_head_is_unproven: red seen yes, green yes |
| 2026-11-13 | acceptance E42 | 82c705a | tests/shell/test_mw101_node_fresh_facts.py::test_a_blob_that_is_no_sha_is_unproven: red seen yes, green yes |
| 2026-11-13 | acceptance E43 | 82c705a | tests/shell/test_mw101_node_fresh_facts.py::test_the_outbox_still_judges_a_check_file_by_its_mtime: red seen yes, green yes |
| 2026-11-13 | acceptance E44 | 82c705a | tests/shell/test_mw101_node_fresh_facts.py::test_an_explicit_changed_time_replaces_the_mtime: red seen yes, green yes |
| 2026-11-13 | acceptance E45 | 82c705a | tests/shell/test_mw101_node_fresh_close.py::test_card_close_passes_with_three_unchanged_nodes_and_one_recut_node: red seen yes, green yes |
| 2026-11-13 | acceptance E46 | 82c705a | tests/shell/test_mw101_node_fresh_close.py::test_card_close_refuses_unproven_after_a_fixture_change: red seen yes, green yes |
| 2026-11-13 | acceptance E47 | 82c705a | tests/shell/test_mw101_node_fresh_close.py::test_replay_a_sibling_recut_leaves_three_rows_fresh: red seen yes, green yes |
| 2026-11-13 | acceptance E48 | 82c705a | tests/test_mw101_docs.py::test_register_changelog_and_card_name_the_card: red seen yes, green yes |
| 2026-11-13 | acceptance E49 | 82c705a | tests/test_mw101_docs.py::test_the_readme_paragraph_names_the_rule_and_the_gap: red seen yes, green yes |
| 2026-11-13 | acceptance E50 | c92dda1 | tests/shell/test_mw101_node_fresh_facts.py::test_a_git_that_cannot_read_the_blob_leaves_the_row_unproven: red seen by breaking the branch, green yes |
| 2026-11-13 | acceptance E51 | c92dda1 | tests/shell/test_mw101_node_fresh_facts.py::test_a_git_that_cannot_name_the_head_blob_leaves_the_row_unproven: red seen by breaking the branch, green yes |
