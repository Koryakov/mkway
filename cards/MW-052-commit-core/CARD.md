# MW-052: commit_files decides in a pure core

| | |
|---|---|
| **Appetite** | 2 hours — from 2026-11-12 |
| **Status** | proposed |
| **Created / updated** | 2026-11-12 / 2026-11-12 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | none new: the test-concept ruling of 2026-11-12 carries it, quoted in the Goal |
| **Canon** | none for the test layers: the basis is the ruling's facts boundary and its migration order (commit_files first) |
| **Paths** | `engine/`, `tests/`, `pytest.ini`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-052-commit-core/CARD.md`, `cards/MW-052-commit-core/case_map.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository. `VERSION` is not changed here. First card of the test-concept migration; the next ones take the lock gate,
then subtask and lead, then owner_ask and search, then the rest. Each Acceptance row names one test node (criterion T1);
a node with `parametrize` holds one case per id (T2).

## 1. Goal

The owner: «it looks like wrong tests concept». The ruling: a test proves a behaviour at the layer where its fault can
live; decisions are a pure core with table tests; reading facts is a shell tested on real git (20 s per test); the
contract with Claude Code is e2e (one deny per reason, plus the real-shape replay); documents are never evidence.
`decide(event, facts) -> verdict` reads only a Facts record the shell built, never disk, git, env or time; the verdict
is data (allow, refuse(reason, text), allow-with-line, plus the rows to append) and the shell writes it. This card moves
the `commit_files` gate there, first: `engine/core.py` holds `Facts`, `Verdict` and `decide_commit`; `gate_commit.py`
keeps the manifest entry `gate_commit:check`, reads the facts and writes the verdict. Behaviour does not change. The gate
has since gained the orderer rule (MW-053), the message-only amend (MW-058) and the one taken-paths reader shared with
`commit_tests` (MW-060); the core holds them too.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | the core imports | `gate_commit` mixed git, disk, register and decisions | `engine/core.py` imports no I/O module (os, pathlib, subprocess, time, datetime, the engine's I/O modules) | tests/core/test_core_is_pure.py::test_core_imports_only_the_pure_modules |
| E2 | the core calls | a decision that opened files and read the clock | `engine/core.py` calls no `open` and reads no clock | tests/core/test_core_is_pure.py::test_core_calls_no_io_function_and_reads_no_clock |
| E3 | the guard of the table tests | none | a guard that fails any disk, process or clock access inside a row | tests/core/test_commit_decide.py::test_the_guard_fails_on_disk_access |
| E4 | files outside the card | decided in a function that read git | a staged file outside the card's Paths is refused `file-not-in-card`, naming it; inside, allowed | tests/core/test_commit_decide.py::test_outside_files |
| E5 | what each commit form takes | read inside the decision | plain, `-i`, `-a`, `--amend` and `-- <paths>` are judged by the files they take | tests/core/test_commit_decide.py::test_each_commit_form_is_judged_by_what_it_takes |
| E6 | junk | decided with the git read | junk is refused `junk-file-staged` at any depth; a name that only looks like junk passes | tests/core/test_commit_decide.py::test_junk_files_are_refused_at_any_depth |
| E7 | a force-added ignored file | decided with the git read | a new staged file git ignores is refused `ignored-file-staged` | tests/core/test_commit_decide.py::test_a_force_added_ignored_file_is_refused |
| E8 | data files | decided with the git read | a data file is refused `data-file-staged` by its extension | tests/core/test_commit_decide.py::test_data_files_are_refused_by_extension |
| E9 | size | decided with the git read | a file over `max_file_kb` is refused `file-too-large`, one under passes | tests/core/test_commit_decide.py::test_a_file_over_the_size_limit_is_refused_and_one_under_passes |
| E10 | the profile keys | read inside the decision | each key replaces its own default alone | tests/core/test_commit_decide.py::test_the_profile_overrides_replace_the_defaults_each_alone |
| E11 | the message names the card | decided with the card read | a message without the open card's id is refused `commit-message-card` | tests/core/test_commit_decide.py::test_a_message_that_does_not_name_the_open_card_is_refused |
| E12 | the message rule, every combination of its facts | rows for some | card open or not, message naming it or not, rule on or off: a refusal only for open, unnamed, on | tests/core/test_commit_decide.py::test_the_message_rule_in_every_combination_of_its_facts |
| E13 | unreadable commits | an exception inside the decision | a commit the reader cannot read is refused `commit-unreadable` | tests/core/test_commit_decide.py::test_a_commit_the_reader_cannot_read_fails_closed |
| E14 | staging in the same command | decided with the git read | an add or reset in the same command as the commit is refused, naming the two calls | tests/core/test_commit_decide.py::test_staging_in_the_same_command_is_refused |
| E15 | the register seal | read inside the decision | a register the engine did not write is refused `register-tampered`, naming the owner's way out | tests/core/test_commit_decide.py::test_a_tampered_register_refuses_and_names_the_owners_way_out |
| E16 | a rule card with no test | decided with the git read | a rule card without its test is refused `rule-without-test`; with its test allowed | tests/core/test_commit_decide.py::test_a_new_rule_card_with_no_test_file_is_refused_and_with_its_test_allowed |
| E17 | the taken list of each form on real git | read inside the decision | the list and its source as git takes them on a plain repository, a linked worktree and a sparse checkout | tests/shell/test_commit_facts.py::test_the_taken_list_of_each_form_on_each_kind_of_repository |
| E18 | the ignore answer | read inside the decision | git's ignore answer covers the added paths only | tests/shell/test_commit_facts.py::test_the_ignore_answer_covers_the_added_paths_only |
| E19 | the paths form | a guess of what git does | the reader's list is what real git commits for `-- <path>` | tests/shell/test_commit_facts.py::test_the_paths_form_agrees_with_what_real_git_commits |
| E20 | a read that fails | an exception inside the decision | a git read that times out is an Unread fact whose text says to run it again | tests/shell/test_commit_facts.py::test_a_git_read_that_times_out_is_an_unread_fact_with_the_way_out |
| E21 | the core on an unread fact | an exception inside the decision | an Unread taken list is refused `commit-unreadable` with the shell's text or the core's | tests/core/test_commit_decide.py::test_a_git_read_that_failed_refuses_with_its_text_or_the_default |
| E22 | the rows of a verdict | a gate verdict built in the decision | the shell writes the rows a verdict carries, in order | tests/shell/test_commit_facts.py::test_the_shell_writes_the_records_of_a_verdict_and_maps_the_kinds |
| E23 | the kinds of a verdict | built in the decision | allow, refuse and allow-with-line map to the gate's allow, refuse and log | tests/shell/test_commit_facts.py::test_a_verdict_maps_to_the_gates_kind |
| E24 | the entry | one function | `gate_commit:check` is the reader plus the core | tests/shell/test_commit_facts.py::test_the_gate_is_the_reader_plus_the_core |
| E25 | the manifest | the manifest test sat among the message tests | the entry declares exactly the nine reasons of the card | tests/shell/test_commit_wiring.py::test_the_manifest_declares_exactly_the_reasons_the_core_can_return |
| E26 | the dispatcher | the same | the dispatcher tags a refusal with its reason and writes its row | tests/shell/test_commit_wiring.py::test_the_gate_refuses_through_the_dispatcher_with_its_tag_and_a_switch |
| E27 | the old commit_files tests | 46 tests over real repositories, and the commit-gate tests of MW-053, MW-058 and MW-060 added later | every case mapped to a new test, dropped (`dropped: doc` for a document check) or kept; a mapped old test is removed | tests/test_mw052_case_map.py::test_every_old_case_has_a_new_home_or_is_dropped_or_kept_and_nothing_is_unmapped |
| E28 | the layer markers are known | none | `e2e` and `shell` are registered markers | tests/core/test_core_is_pure.py::test_the_markers_are_registered |
| E29 | the layer markers by place | none | `e2e` and `shell` are put on tests by the place of the file | tests/core/test_core_is_pure.py::test_the_markers_are_assigned_by_the_place_of_the_file |
| E30 | the default run | none | the default run excludes no layer | tests/core/test_core_is_pure.py::test_the_default_run_excludes_nothing |
| E31 | the 20 s cap of a shell test | a rule in the ruling | an autouse fixture of `tests/shell` fails a test over 20 s | checked by reading: tests/shell/conftest.py |
| E32 | the one e2e deny per reason | MW-039 | unchanged: `tests/test_e2e_gates.py` and `tests/test_mw038_real_shape.py` stay as they are | checked by reading: tests/test_e2e_gates.py |
| E33 | the orderer commits its card folder (MW-053) | decided in the gate with the register read inside | `CARD.md`, `ORDER.md` and the register of an ordered card pass without holding it | tests/core/test_commit_decide.py::test_the_orderer_commits_card_md_order_md_and_the_register_without_holding_the_card |
| E34 | a mixed orderer commit | the same | a file outside the ordered folders is refused, named, with the orderer sentence | tests/core/test_commit_decide.py::test_a_mixed_commit_is_refused_naming_the_files_that_do_not_belong |
| E35 | the holder's files | the same | a file the card's Paths cover is the holder's: refused, naming the holder | tests/core/test_commit_decide.py::test_a_file_under_the_holders_paths_is_the_holders_and_names_the_holder |
| E36 | holders that cannot be read | an exception | unread holders fail closed only when a file outside the held card needs them | tests/core/test_commit_decide.py::test_holders_that_could_not_be_read_fail_closed_only_when_they_are_needed |
| E37 | the orderer's facts | read inside the decision | the cards the session ordered (id, folder, Paths) and who holds them, from the real register | tests/shell/test_commit_facts.py::test_the_orderer_facts_are_the_cards_the_session_ordered_and_who_holds_them |
| E38 | the orderer through the gate | the same | the real register and index: the orderer is allowed, a stranger refused | tests/shell/test_commit_facts.py::test_the_gate_lets_the_orderer_commit_its_card_folder_and_refuses_the_stranger |
| E39 | the form of a message-only amend (MW-058) | decided in the reader | `--amend` with `--only` or `-o` and no paths takes no file, in every spelling | tests/core/test_commit_decide.py::test_a_message_only_amend_takes_no_files |
| E40 | what the shell read for it | the same | whatever the shell read, a message-only amend is not judged by files | tests/core/test_commit_decide.py::test_the_files_the_shell_read_for_a_message_only_amend_are_not_judged |
| E41 | the lists of the amend forms on real git | the same | the files each amend form takes, as the reader reads them | tests/shell/test_commit_facts.py::test_the_files_an_amend_takes_follow_its_form |
| E42 | a message-only amend reads no git | the same | no git call, and an empty (not unread) ignore answer and sizes | tests/shell/test_commit_facts.py::test_a_message_only_amend_reads_no_git_and_takes_no_files |
| E43 | the table of what a commit takes (MW-060) | `combine` beside the git reads | `combine` is pure and lives in the core | tests/core/test_commit_decide.py::test_the_reader_combines_the_lists_as_git_takes_them |
| E44 | one reader | the gate's own copy | `gate_commit.taken` stays the one reader both gates call | tests/test_mw060_taken_tree.py::test_commit_files_still_reads_the_same_list_through_the_shared_reader |
| E45 | the e2e time limit | a limit on the whole module under load | the test stays an `e2e` test by its file place; its reason is in the Log | checked by reading: tests/_markers.py |

## 8. Log

One line per step. No re-run of a check or an agent round without a new input named in the Log row.

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-12 | port onto master 109dd7c: red tests, the orderer, message-only amend and combine rows, case map in the MW-040 line form | 775f4e7 | red as planned: the new rows could not be collected without the core's new records |
| 2026-11-12 | green: `engine/core.py` (orderer on `ordered` and `holders`, `message_only_amend`, pure `combine`), thin shell `engine/gate_commit.py` (one reader `taken` kept for `commit_tests`), `git_form_problem` takes the built-in list as an argument; mapped old modules emptied to one docstring line; rows E1 to E45 | this commit | tests/core: 286 passed in 8 s (the decision tables about 1.5 s); subset of 24 commit-gate files with tests/shell and the case-map and card meta tests: 576 passed in 351.89 s; e2e files (gates, plain, real shape, MW-058, MW-060, MW-061): 115 passed in 233.27 s and 1 failed (a marker-selection test that printed file names from my parametrize ids), fixed by ids with no file name, the test then passed |
| 2026-11-12 | e2e time limit: `tests/test_e2e_gates.py::test_the_rows_stay_inside_the_time_limit` measures the wall time of a whole module of real hook runs (limit 120 s), which failed at 147 s under machine load while it passed alone at 77.80 s; it is an `e2e` test by its file place (`tests/_markers.py`), not a decision test; no per-row limit is established, so the limit is unchanged | this commit | not changed; the default run still excludes nothing, so it can fail again under load until the merge selects layers |
| 2026-11-12 | case map: the table became one `old -> new` line per pair, as the card meta test of MW-040 reads it (that test is copied from branch t73); `# kept:` lines mark the kept tests | this commit | 10 old modules in the map: 7 emptied to one docstring line, 3 reduced to the kept tests (lock gate, start block and check, one real-git proof of the amend) |
| 2026-11-12 | Re-checked against test_criteria_FINAL T1-T8: 60 tests changed (multi-case bodies split into one case per id, a «Catches:» line added, expected values written as literals, an import of another test file removed), 21 added (108 to 129 test functions), 0 dropped | this commit | blind verdict T6 is for a separate reader |
