# MW-057: The commit test run sees what the working tree sees, and says why it failed

| | |
|---|---|
| **Appetite** | 2 hours — from 2026-11-12 |
| **Status** | proposed |
| **Created / updated** | 2026-11-12 / 2026-11-12 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | none new: the lead's task carries it, quoted in the Goal |
| **Canon** | none: the basis is a real install where a code commit was refused with whole files and not test ids |
| **Paths** | `engine/`, `tests/`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-057-export-sees-tree/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository. `VERSION` is not changed here. The change stays in the run's environment, the export and the refusal text;
the red or green decision of the gate (card MW-056) is not touched.

## 1. Goal

A code commit of a real install was refused with whole files and no test ids: «the tests of the staged tree are red:
4 failing (all 4): <four test files>». All four files pass in the working tree. A commit of only `.md` files passed.
The ruling: «The exported staged tree collects exactly as the working tree does for tracked content. Untracked files
stay out (the staged tree is the truth); if a test needs an untracked file, the refusal says so. A refusal for a
file-level failure (collection or import error) shows its first error line per file, so the lead sees the cause without
reading transcripts.» — the lead's task, 2026-11-12.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | a test that finds its root through git, through a `.git` folder above it, or imports a sibling folder whose scripts are staged and not committed | not established as a cause: these shapes already collect in the export (the export is inside the repository) | still allowed, so the shapes stay covered | tests/test_mw057_export.py::test_the_export_collects_what_the_working_tree_collects |
| E2 | a test that reads a data file by an absolute path outside the repository | not established as a cause | still allowed | tests/test_mw057_export.py::test_a_data_file_by_an_absolute_path_outside_the_repo_is_read |
| E3 | a test that imports a package which lives only in the person's user site (Python finds it through `APPDATA`) | refused: the run's environment has no `APPDATA`, so the import fails in the export and passes in the working tree | allowed: the run's environment carries the names Python and Windows need to find installed packages | tests/test_mw057_export.py::test_a_package_of_the_user_site_is_found_in_the_export; tests/test_mw057_export.py::test_the_environment_of_the_run_carries_what_python_needs_to_find_its_packages |
| E4 | a test that needs a file that is in the working tree and not in the index | refused with a file name only | refused, and the refusal names the untracked file and the module or file that was not found | tests/test_mw057_export.py::test_a_test_that_needs_an_untracked_file_is_refused_and_the_refusal_says_so |
| E5 | refusal text for a file-level failure (module not found, file not found, syntax) | the file name only | the file name and its first error line, per file; a test-level failure keeps its text | tests/test_mw057_export.py::test_a_file_level_failure_shows_its_first_error_line_per_file; tests/test_mw057_export.py::test_the_error_line_is_read_from_the_short_summary_when_there_is_no_section; tests/test_mw057_export.py::test_the_error_line_is_read_from_output_with_windows_line_ends; tests/test_mw057_export.py::test_a_section_header_relative_to_the_rootdir_joins_the_summary_id_by_its_path_end; tests/test_mw057_export.py::test_a_backslash_path_is_shown_with_slashes; tests/test_mw057_export.py::test_a_test_level_failure_keeps_its_text_unchanged |
| E6 | the untracked-files clause | none | only with a file-level failure, at most 5 names and a count of the rest | tests/test_mw057_export.py::test_untracked_files_are_named_only_for_a_file_level_failure; tests/test_mw057_export.py::test_the_untracked_list_is_capped_and_says_how_many_more |
| E7 | a staged test that cannot be imported, through the real hook | deny naming the file | deny naming the file and `ModuleNotFoundError: No module named '...'` | tests/test_e2e_gates.py::test_a_file_level_failure_shows_its_error_line_through_the_real_hook |

## 8. Log

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-12 | red: rows E1 to E7 | af93a3f | the shapes of E1 and E2 pass today (the export lies inside the repository, so git and `.git` lookups find the real one); E3, E4, E5, E6, E7 fail for the right reason |
| 2026-11-12 | cause, established by the E3 reproduction: the run's environment is a short list of names that lacks `APPDATA` and `LOCALAPPDATA`, so Python in the export does not see the packages installed for the user and a test file that imports them fails at collection, while the same file passes in the working tree | the commit that carries this line | git lookups, `.git` above, sibling folders, rootdir, conftest and absolute data paths are ruled out (E1, E2 pass today); not checked against the real install: «not established» there, the new first error line per file shows it at the next refusal |
| 2026-11-12 | tests added after the red commit, none weakened: output with CRLF line ends, a section header relative to pytest's rootdir that differs from the summary id (seen in the real hook run), a backslash path; they surfaced when the parser met real pytest output | the commit that carries this line | the parser reads the last exception line of a file's section, joins it to the summary id by path end, shows ids with `/` |
| 2026-11-12 | green: environment names, `file_errors` in the row, the error line in the refusal, the untracked-files clause (a hint, never a refusal of its own); README and gate docstring | the commit that carries this line | rows E1 to E7 green; the red or green decision of the gate is not touched; whole suite `python -m pytest`: 1157 passed in 551.46 s |
