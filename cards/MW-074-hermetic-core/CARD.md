# MW-074: Small tests are hermetic and run in a shuffled order

| | |
|---|---|
| **Appetite** | 1.5 hours — from 2026-11-12 |
| **Status** | proposed |
| **Created / updated** | 2026-11-12 / 2026-11-12 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | R177 |
| **Canon** | none: the basis is the test enforcement plan, gate G8, and the chief review R177 section 4 |
| **Paths** | `tests/`, `engine/profile.schema.json`, `engine/KEYS.md`, `README.md`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-074-hermetic-core/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository. `VERSION` is not changed here. There is no refusal reason and no hook: the guard is a test fixture, so a
test that breaks it fails as a test. The task owns the copy of the conftest in its own hermetic dirs (see the Log).

## 1. Goal

«Small tests are hermetic at run time (subprocess, socket, sleep, file writes raise) and run in a shuffled order with a
printed seed; in-house, no new dependency; scope tests/core only.» — plan gate G8 with ruling R177 section 4, 2026-11-12.

## Acceptance examples

Each row becomes a test; `card close` needs every row to name one. E1 to E10 run in `tests/core` under the guard itself,
E11 to E15 are the pure shuffle, E16 to E24 run a real pytest on a small synthetic project, E25 to E28 are the key.

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | a core test calls `subprocess.run` | runs | refused: `hermetic test: subprocess.run is not allowed in tests/core` | tests/core/test_hermetic_guard.py::test_a_subprocess_call_is_refused |
| E2 | a core test calls `subprocess.list2cmdline` (nearest allow of E1) | runs | runs | tests/core/test_hermetic_guard.py::test_a_subprocess_helper_that_starts_nothing_is_allowed |
| E3 | a core test opens a socket | opens | refused: `hermetic test: socket.socket is not allowed in tests/core` | tests/core/test_hermetic_guard.py::test_a_socket_is_refused |
| E4 | a core test sleeps | sleeps | refused: `hermetic test: time.sleep is not allowed in tests/core` | tests/core/test_hermetic_guard.py::test_a_sleep_is_refused |
| E5 | a core test opens a file for writing outside its tmp_path | writes | refused: `hermetic test: file write outside tmp_path (<path>) is not allowed in tests/core` | tests/core/test_hermetic_guard.py::test_an_open_for_write_outside_tmp_path_is_refused |
| E6 | a core test writes text through `Path.write_text` outside its tmp_path | writes | refused with the same text | tests/core/test_hermetic_guard.py::test_a_path_write_text_outside_tmp_path_is_refused |
| E7 | a core test writes a file inside its tmp_path (nearest allow of E5) | writes | writes | tests/core/test_hermetic_guard.py::test_a_write_inside_tmp_path_is_allowed |
| E8 | a core test reads a file outside its tmp_path (nearest allow of E5) | reads | reads | tests/core/test_hermetic_guard.py::test_a_read_outside_tmp_path_is_allowed |
| E9 | a core test writes through a file opened by descriptor number (not a path write; nearest allow of E5) | writes | writes: only paths are judged | tests/core/test_hermetic_guard.py::test_a_write_through_a_descriptor_is_allowed |
| E10 | the refusal text | none | begins `hermetic test: ` and ends `is not allowed in tests/core` | tests/core/test_hermetic_guard.py::test_the_refusal_text_has_the_fixed_form |
| E11 | the same seed on the same tests | n/a | the same order | tests/core/test_hermetic_shuffle.py::test_the_same_seed_gives_the_same_order |
| E12 | two seeds on ten tests (nearest deny of E11) | n/a | two orders | tests/core/test_hermetic_shuffle.py::test_two_seeds_give_two_orders |
| E13 | a shuffle | n/a | every test once, none lost | tests/core/test_hermetic_shuffle.py::test_a_shuffle_keeps_every_test_exactly_once |
| E14 | tests outside the hermetic folder | n/a | keep their places | tests/core/test_hermetic_shuffle.py::test_tests_outside_the_folder_keep_their_places |
| E15 | the seed: given, or from the clock | n/a | the given one; else the whole seconds of the clock | tests/core/test_hermetic_shuffle.py::test_the_seed_is_the_given_one_or_the_clock |
| E16 | replay: a real pytest run of a core test that calls subprocess | passed | fails with the hermetic text | tests/shell/test_hermetic_run.py::test_a_core_test_that_calls_subprocess_fails_with_the_hermetic_text |
| E17 | the same core test without the call (nearest allow of E16) | passed | passes | tests/shell/test_hermetic_run.py::test_the_same_core_test_without_the_call_passes |
| E18 | a test outside the hermetic folders calls subprocess | passed | passes: the scope is the folder | tests/shell/test_hermetic_run.py::test_a_test_outside_the_hermetic_folder_may_start_a_process |
| E19 | `--seed 7` twice | any order | the same order both times | tests/shell/test_hermetic_run.py::test_the_same_seed_repeats_the_order_in_a_real_run |
| E20 | `--seed 7` and `--seed 8` | any order | two orders | tests/shell/test_hermetic_run.py::test_two_seeds_give_two_orders_in_a_real_run |
| E21 | the report header | none | `hermetic seed: 7` | tests/shell/test_hermetic_run.py::test_the_header_prints_the_given_seed |
| E22 | a quiet run (`-q`), the usual run of the gates | none | the summary prints `hermetic seed: 7` | tests/shell/test_hermetic_run.py::test_a_quiet_run_still_prints_the_seed |
| E23 | a run with no `--seed` | none | prints a whole-number seed | tests/shell/test_hermetic_run.py::test_a_run_without_a_seed_prints_the_seed_it_chose |
| E24 | the printed seed given back | n/a | the same order as the first run | tests/shell/test_hermetic_run.py::test_the_printed_seed_repeats_the_order |
| E25 | profile `tests.hermetic_dirs`, a list of paths | unknown key | valid | tests/test_mw074_keys.py::test_a_list_of_folders_is_a_valid_hermetic_dirs |
| E26 | profile `tests.hermetic_dirs` empty (the dedup profile) | unknown key | valid | tests/test_mw074_keys.py::test_an_empty_list_is_a_valid_hermetic_dirs |
| E27 | profile `tests.hermetic_dirs` a string (nearest deny of E25) | not allowed here | `tests.hermetic_dirs: expected array` | tests/test_mw074_keys.py::test_a_string_is_not_a_valid_hermetic_dirs |
| E28 | KEYS.md | no row | a row with the default `["tests/core"]` | tests/test_mw074_keys.py::test_keys_md_names_the_default_folder |
| E29 | the README | none | one paragraph: the guard, the shuffle, `--seed`, the key, the task owns its copy | checked by reading: README.md |

## 8. Log

One line per step. No re-run of a check or an agent round without a new input named in the Log row.

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-12 | start checks, each alone: `pwd` = the worktree, HEAD 8fc6a2e, `git status --short` = clean | 8fc6a2e | base of the card |
| 2026-11-12 | red: card with its Acceptance table (rows E1 to E29), register row, changelog line, tests only: `tests/core/test_hermetic_guard.py` (16 ids), `tests/core/test_hermetic_shuffle.py` (5 ids), `tests/shell/test_hermetic_run.py` (9 ids), `tests/test_mw074_keys.py` (4 ids), the key added to the expected set of `tests/test_keys.py`, decision: R177 | the commit that carries this line | red by missing module `_hermetic` for the 21 core ids (both core files fail collection: `ModuleNotFoundError: No module named '_hermetic'`); 9 shell ids FAILED (the project copy finds no `_hermetic.py` or `tests/core/conftest.py`); 4 key ids FAILED (`tests.hermetic_dirs: not allowed here`, no KEYS row); `tests/test_keys.py::test_keys_md_has_one_line_per_draft_key` FAILED. Every new id fails; the first draft of E27 passed before the code (it expected only the key name) and was fixed to expect `expected array` |
| 2026-11-12 | green for E1 to E28: `tests/_hermetic.py` (the guard `install`, `shuffle_under`, `seed_for`, `run_seed`, `HermeticError`), `tests/core/conftest.py` (autouse fixture and the shuffle hook for its folder), the key `tests.hermetic_dirs` in the schema and in KEYS.md (added keys, last row), README paragraph (E29). Engine side: the task owns its copy of the conftest and the engine reads the key nowhere: the smaller change, as `tests/` is already an install set dir and a copy rule would need a new install step and tests; decision: R177 | the commit that carries this line | red ids 35 now pass; tests/core with seeds 1, 2, 3: 1746 passed each (16.0 s, 17.2 s, 18.0 s); no test failed by order or by a hermetic call, so there is no defect to list or fix; whole suite 3419 passed, 1 deselected in 972 s |
| 2026-11-12 | `tests/conftest.py` is shared by every card: it got only `pytest_addoption` (`--seed`), `pytest_report_header` and `pytest_terminal_summary` (the seed line, because -q hides the header) and one import; the shuffle and the guard stay in `tests/core/conftest.py`. Why at the root: an option must exist before a folder's conftest loads, and a `--seed` given to a bare `pytest` run would otherwise be an unknown option | the commit that carries this line | the shell tests copy this file into the synthetic project, so the real hooks are the ones tested |
| 2026-11-12 | coverage, `python -m coverage run --branch -m pytest` on the four new test files, `coverage report -m` over `tests/_hermetic.py` and `tests/core/conftest.py` (the engine code of this card is a schema key and text) | the commit that carries this line | 100 percent, 10 branches, missed lines: none. Time added per commit: the guard adds no measurable time to tests/core (16.5 s before, 16.0 to 18.0 s after); the new tests add about 13 s (9 shell runs of a small pytest). No refusal reason and no profile mode switch: the guard is a test fixture; a task opts out with `tests.hermetic_dirs` empty and no conftest copy |
| 2026-11-12 | table, Acceptance row -> test node -> red seen -> green: E1 `tests/core/test_hermetic_guard.py::test_a_subprocess_call_is_refused` yes yes; E2 `::test_a_subprocess_helper_that_starts_nothing_is_allowed` yes yes; E3 `::test_a_socket_is_refused` yes yes; E4 `::test_a_sleep_is_refused` yes yes; E5 `::test_an_open_for_write_outside_tmp_path_is_refused` yes yes; E6 `::test_a_path_write_text_outside_tmp_path_is_refused` yes yes; E7 `::test_a_write_inside_tmp_path_is_allowed` yes yes; E8 `::test_a_read_outside_tmp_path_is_allowed` yes yes; E9 `::test_a_write_through_a_descriptor_is_allowed` yes yes; E10 `::test_the_refusal_text_has_the_fixed_form` yes yes; E11 to E15 `tests/core/test_hermetic_shuffle.py` five ids yes yes; E16 to E24 `tests/shell/test_hermetic_run.py` nine ids yes yes; E25 to E28 `tests/test_mw074_keys.py` four ids yes yes (E27 fixed before the red commit); E29 checked by reading README.md, no red | the commit that carries this line | all rows green |
