# MW-085: Shared test templates and the runtime guard

| | |
|---|---|
| **Appetite** | 3 hours — from 2026-11-13 |
| **Status** | proposed |
| **Created / updated** | 2026-11-13 / 2026-11-13 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | R204, R207, R209, R213, R214 |
| **Canon** | none: the basis is the order of R209a and the rulings R207 Q2 to Q4, R209 D2 |
| **Paths** | `tests/conftest.py`, `tests/_hermetic.py`, `tests/_template*.py`, `tests/test_mw085_templates.py`, `tests/test_mw038_real_shape.py`, `tests/test_mw030_live_install.py`, `tests/test_e2e_gates.py`, `tests/test_mw068_records_e2e.py`, `tests/test_mw061_e2e.py`, `tests/test_mw056_e2e.py`, `tests/test_mw070_e2e.py`, `tests/test_mw062_e2e.py`, `tests/test_mw060_e2e.py`, `tests/shell/test_hermetic_run.py`, `tests/shell/test_mw083_parallel_run.py`, `cards/MW-085-test-templates/**`, `cards/REGISTER.md`, `CHANGELOG.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository. `VERSION` is not changed. There is no refusal reason, no hook gate and no profile switch of the engine: the
templates and the guard are test support, so the common-rule items `tests.<key>.mode`, reason ids, e2e deny and the time per
commit do not apply (the guard has its own mode constant, below). Per R204 the builder runs only its own files plus
`tests/core` locally, never the whole suite; the whole suite runs once per merge in the merge gate. This replaces the line
«Before every commit run the whole suite» of `CLAUDE.md` for this card, and the Log says which files were run.

## 1. Goal

«I NEED TO FIX TESTS FIRST!! ALL BAD THINGS like reading real repo, real installation etc etc - you must carefully check
tests! So we must fix tests (align with rules) and make them to parallel work.» and «we spend A LOT of time for each tests
runs!!!» — owner, 2026-11-13. A session-scoped fixture builds each costly real install once per worker as a read-only
template, every test gets a writable copy in its own `tmp_path`, and a runtime guard (G8) decides every write, process and
socket of a test outside the fixture: it warns outside `tests/core` (one machine-readable row per test id, act and path),
raises inside it, and raises everywhere for a write into a template folder.

Design (binding, R207 Q3, R209 D2):

- `tests/_hermetic.py` stays standard library only. `install` keeps its name and its default `raise`; the new function
  `decide(op, target, cwd, argv, test_tmp, template_dirs, engine_root, engine_repo_test, mode)` answers `allow`, `warn` or
  `refuse` and touches no disk. `tests/core/conftest.py` is not edited and keeps raising.
- One constant decides the mode outside `tests/core`: `OUTSIDE_CORE_MODE = "warn"` in `tests/conftest.py`. R209's later
  one-line card changes it to `"raise"`; the fresh-install default for task roots stays raise, warn is the engine
  repository's own migration state only.
- A write into a template folder RAISES in every mode (the one exception to warn). On Windows a read-only flag on a folder
  does not stop new files, so the guard, not chmod, is the protection. A copy is made with `shutil.copytree` and
  `copy_function=shutil.copyfile` (copy2 would copy the read-only flag), so a copy is writable.
- A process whose working folder is inside the test's own `tmp_path` is allowed; `cwd=None` is refused (or warned). A test
  marked `engine_repo` may run only `log`, `show`, `ls-files`, `rev-parse`, `diff` and `cat-file` in the engine repository;
  it writes only inside its own `tmp_path` and never elsewhere in the base temp folder. A git command's subcommand is the
  first word after `git` that is not an option (`-C <path>` counts as its working folder, and `-c` takes a value).
- The cwd rule cannot see what a child process writes by absolute path; the AST scanner of R207 Q4 covers absolute paths in command arguments, so the two together are the net.
- Warning rows: a worker records `{"id","act","path"}` in the test report's `user_properties`; only the controller, and only
  for `report.when == "teardown"`, writes them, deduplicated by (id, act, path), to `g8_warnings.jsonl` in the folder named by
  `MKWAY_G8_WARN_DIR` when set (file name `g8_warnings_<YYYYmmdd-HHMMSS>.jsonl`), else in the controller's basetemp. The run
  prints `G8 warnings: N`, the file's path and the first 200 rows as `G8 <act> <id> <path>`.
- The session fixture `_shared_engine_sources` is treated like a template: read-only for tests, its build is a guard exit.
- README's G8 text (`README.md`, «tests/core» only) goes stale with this card; the later switch card updates it.
- R211 (option 1), after the cost check: the template code, `decide` and the guard stay as built, because the six rewrite
  cards need them. The nine files do not use a template: a template that has seen a session start cannot be copied (the
  engine writes the absolute root into `state/sessions.jsonl`), and the seven install-based files start sessions in their
  fixture. Six of them (those whose grep for `REPO` is empty) leave the group `shared_real` and take their own
  `xdist_group`, so the nine files spread over the workers; the acceptance row «0 warnings» became «every warning listed
  per test id in `g8_wave_c_input.jsonl`» (temporary, recorded in the Log). The wave C target for these seven files is
  per-test setup, not per-module setup; the later engine card «state records relative to the root» removes the obstacle.

## Acceptance examples

Each row becomes a test; `card close` needs every row to name one. E1 to E11 are the new file; E12 to E20 name, per file,
the test node that requests the template (or why the file keeps building); E21 to E24 are read from the Log.

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | one template asked through two fixtures | no template fixture | the same folder, build count 1 | tests/test_mw085_templates.py::test_a_template_is_built_once_and_two_fixtures_see_the_same_folder |
| E2 | a copy of a template whose file is read-only | no copy fixture | a writable copy of its own; the template unchanged | tests/test_mw085_templates.py::test_a_copy_is_its_own_and_writable |
| E3 | `decide`, write into a template folder, mode warn | n/a | `refuse` | tests/test_mw085_templates.py::test_decide_refuses_a_write_into_a_template_folder_in_warn_mode |
| E4 | a real run outside `tests/core` overwrites a template file | nothing stops it | the test fails with `HermeticError` naming the template | tests/test_mw085_templates.py::test_live_a_template_file_overwritten_outside_core_raises |
| E5 | HOME, USERPROFILE, GIT_CEILING_DIRECTORIES and CLAUDECODE at the template build | the real ones | the first three inside the base temp folder, the last absent | tests/test_mw085_templates.py::test_the_build_saw_a_tmp_home |
| E6 | a copy of a clean template | n/a | no text file names the template folder (nearest allow of E7) | tests/test_mw085_templates.py::test_a_copy_holds_no_template_path |
| E7 | a copy of a template that names its own folder | n/a | refused with `TemplateHoldsItsPath`, the test keeps building | tests/test_mw085_templates.py::test_a_template_that_holds_its_own_path_is_refused_for_copies |
| E8 | the `decide` table: 21 cases in both modes (write, process, socket, engine repo, git subcommands, template; the 21st is E30) | n/a | the verdicts of the table | tests/test_mw085_templates.py::test_decide_table |
| E9 | a real run outside `tests/core`, one test writing the same outside path twice | the write passes unseen | the test passes, one row, `G8 warnings: 1` | tests/test_mw085_templates.py::test_outside_core_a_write_outside_the_tmp_path_passes_and_leaves_one_row |
| E10 | the same act in a folder named `tests/core` (nearest deny of E9) | fails (guard of MW-074) | still fails | tests/test_mw085_templates.py::test_in_core_the_same_write_fails |
| E11 | a real run on two workers, two such tests | n/a | two rows, no duplicate, `G8 warnings: 2` | tests/test_mw085_templates.py::test_two_workers_write_two_rows_and_no_duplicate |
| E12 | tests/test_mw038_real_shape.py uses the template | builds in a module fixture, `engine_repo` | still builds in its module fixture, keeps `engine_repo` (grep: `REPO` read, 3 matches) | none: keeps building, the scenario replay is the subject and its linked worktrees hold their own folder (R211) |
| E13 | tests/test_mw030_live_install.py uses the template | builds in a module fixture, `engine_repo` | still builds in its module fixture, keeps `engine_repo` (grep: `REPO` read, 2 matches) | none: keeps building, the scenario replay is the subject and its linked worktrees hold their own folder (R211) |
| E14 | tests/test_e2e_gates.py uses the template | builds in a module fixture, `engine_repo` | still builds in its module fixture, keeps `engine_repo` (grep: `REPO` read, 5 matches) | none: keeps building, its fixture starts sessions and the engine writes the absolute root into state/sessions.jsonl, so a template cannot be copied (R211) |
| E15 | tests/test_mw068_records_e2e.py uses the template | builds in a module fixture, `engine_repo` | still builds in its module fixture, no `engine_repo`, `xdist_group("test_mw068_records_e2e")` (grep for `REPO`: empty) | none: keeps building, its fixture starts sessions and the engine writes the absolute root into state/sessions.jsonl, so a template cannot be copied (R211) |
| E16 | tests/test_mw061_e2e.py uses the template | builds in a module fixture, `engine_repo` | same, `xdist_group("test_mw061_e2e")` (grep for `REPO`: empty) | none: keeps building, its fixture starts sessions and the engine writes the absolute root into state/sessions.jsonl, so a template cannot be copied (R211) |
| E17 | tests/test_mw056_e2e.py uses the template | builds in a module fixture, `engine_repo` | same, `xdist_group("test_mw056_e2e")` (grep for `REPO`: empty) | none: keeps building, its fixture starts sessions and the engine writes the absolute root into state/sessions.jsonl, so a template cannot be copied (R211) |
| E18 | tests/test_mw070_e2e.py uses the template | builds in a module fixture, `engine_repo` | same, `xdist_group("test_mw070_e2e")` (grep for `REPO`: empty) | none: keeps building, its fixture starts sessions and the engine writes the absolute root into state/sessions.jsonl, so a template cannot be copied (R211) |
| E19 | tests/test_mw062_e2e.py uses the template | builds in a module fixture, `engine_repo` | same, `xdist_group("test_mw062_e2e")` (grep for `REPO`: empty) | none: keeps building, its fixture starts sessions and the engine writes the absolute root into state/sessions.jsonl, so a template cannot be copied (R211) |
| E20 | tests/test_mw060_e2e.py uses the template | builds in a module fixture, `engine_repo` | same, `xdist_group("test_mw060_e2e")` (grep for `REPO`: empty) | none: keeps building, its fixture starts sessions and the engine writes the absolute root into state/sessions.jsonl, so a template cannot be copied (R211) |
| E21 | the nine files, seconds (lower of two runs, 2 workers) | 237.21 s | at most 60 percent: 142.33 s; measured 139.09 s (58.6 percent) | checked by reading: cards/MW-085-test-templates/CARD.md |
| E22 | the lane `engine_repo or real_shared_state`, collected tests | 370 | fewer: 355 | checked by reading: cards/MW-085-test-templates/CARD.md |
| E23 | `G8 warnings` of a run of the nine files (R211 b: «0» became «every warning listed per test id in the wave C input file», temporary) | n/a | 413 rows of 94 test ids, all listed in `g8_wave_c_input.jsonl` | checked by reading: cards/MW-085-test-templates/g8_wave_c_input.jsonl |
| E24 | tests outside the Paths whose writes or processes do not use the temp folder | unknown | listed as «G8 may warn: <id> <file:line>» under `### Fallout` | checked by reading: cards/MW-085-test-templates/CARD.md |
| E25 | the folder named by `MKWAY_G8_WARN_DIR`, seen by a child run (an inner `mkway check`) and by an xdist worker | stays in the environment | removed from the environment when the run starts; one rows file in the folder | tests/test_mw085_templates.py::test_a_child_of_the_run_does_not_inherit_the_rows_folder |
| E26 | the test id in a warning row of a run with `--dist loadgroup` | ends in `@<group>` (the suffix xdist puts on a worker's id) | the plain test id, no suffix | tests/test_mw085_templates.py::test_a_row_id_has_no_xdist_group_suffix |
| E27 | a test marked `engine_repo` alone (R213 A1), in the xdist group `shared_real` | in the group (a test that only reads the working tree is kept on one worker) | in no group; only `real_shared_state` puts a test in `shared_real`; the six end-to-end files keep their own `xdist_group` | tests/test_mw085_templates.py::test_only_real_shared_state_goes_in_the_shared_lane |
| E28 | a write into the engine repository by an `engine_repo` test without `real_shared_state` (R213 A2, R213a, R213c) | a warning row in mode warn | the test fails with `HermeticError`, in every mode; a test that also carries `real_shared_state`, and a write into the test's own `tmp_path`, pass | tests/test_mw085_templates.py::test_an_engine_repo_test_that_writes_the_engine_repo_fails |
| E29 | `decide` for a write into the engine root, with the argument `scratch_root` (R213c) | warn in mode warn for every write outside the test's tmp folder | refuse in every mode for an `engine_repo` test outside `scratch_root`; inside `scratch_root` the mode decides; `scratch_root=None` (a `real_shared_state` test) follows the mode | tests/test_mw085_templates.py::test_decide_table_for_a_write_into_the_engine_repository |
| E30 | `decide` for a read-only git subcommand (R214: `rev-parse` here) with `-C` inside a template or the shared sources | refuse in every mode (any process there) | allow in every mode; every other process there stays refused (row `process-cwd-in-a-template` of E8) | tests/test_mw085_templates.py::test_decide_table[git-C-rev-parse-in-a-template] |

## 8. Log

One line per step. No re-run of a check or an agent round without a new input named in the Log row.

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-13 | start checks, each alone: `pwd` = the worktree, HEAD 5b627c2, `git status --short` = clean, `python -c "import xdist"` printed nothing | 5b627c2 | base of the card |
| 2026-11-13 | 2a base, twice: `MKWAY_TEST_WORKERS=2 python -m pytest -q -n auto --dist loadgroup --durations=15 <the nine files>` | 5b627c2 | run 1 `123 passed in 237.21s (0:03:57)`, run 2 `123 passed in 274.61s (0:04:34)`: the base time of the nine files is 237.21 s (the lower). All 123 ids run on one worker: each file carries `engine_repo` by `pytestmark`, so the group `shared_real` holds them and the second worker idles. Durations under `### Base facts` |
| 2026-11-13 | 2b lane before: `python -m pytest --collect-only -q -m "engine_repo or real_shared_state" tests --ignore=tests/test_mw085_templates.py` and the last line (this `-m` replaces the addopts `-m "not perf"`, so perf tests count; `--ignore` leaves out the new red file, which is not collectable at base) | 5b627c2 | `370/3593 tests collected (3223 deselected) in 4.93s`: lane before = 370 |
| 2026-11-13 | 2c base pass set: `MKWAY_TEST_WORKERS=2 python -m pytest -q -n auto --dist loadgroup <the nine files> tests/core tests/test_mw029_fast_guard.py tests/test_meta_cards.py` | 5b627c2 | `1 failed, 1954 passed in 230.11s (0:03:50)`. The one failure, `tests/test_mw029_fast_guard.py::test_no_collected_test_reads_a_path_a_copy_lacks`, is caused by my own uncommitted red file: that test collects all of `tests/` in a child run and printed `ERROR collecting tests/test_mw085_templates.py ... ModuleNotFoundError: No module named '_template'`. Without that file it passes, so the base pass set is all 1955 ids; the run was not repeated without the file (no new input) |
| 2026-11-13 | 2d inventory by reading and 2e per file: under `### Base facts` | 5b627c2 | no run |
| 2026-11-13 | measured by hand before the red commit (a throw-away script, its folders under `.pytest_tmp`, nothing committed): one `_hook_driver.install_project` build: 5.0 s alone, 467 files (244 in the repository folder, 223 in the engine source folder `src-none`, `home` and `transcripts` empty); no file outside the object store of the repository names the build folder (three spellings searched); `shutil.copytree(..., copy_function=shutil.copyfile)` of the whole base took 2.5 s cold and 0.71 s twice warm, of the repository folder alone 0.37 s | 5b627c2 | these numbers feed the cost check of step 4; the real check uses the `--durations=0` setup time of test E2 |
| 2026-11-13 | red: this card with its Acceptance table (E1 to E24), the register row, the changelog line, and tests only: `tests/test_mw085_templates.py` (E1 to E11: 10 test functions, the table E8 has 21 cases; decisions: R204, R207, R209) | the commit that carries this line | every id of the file is red by a missing module: `ModuleNotFoundError: No module named '_template'` at the import on line 21 of the file (collection error, `1 error in 9.56s`; no id is collected, so none can pass). The missing fixtures `shared_templates` and `template_copy` and the missing function `_hermetic.decide` are further reds behind it. The run is under `### Red run`. The live tests E4, E9, E10 and E11 carry the mark `g8_off`: their subject is the guard, and they start real child runs whose working folder is the pytester folder, which the guard of the outer run would warn on. A test that sets the mark is a test that the guard does not judge; the mark is registered in `tests/conftest.py` in the green commit and is used only by this file |
| 2026-11-13 | correction to the red row: the file holds 11 test functions (one per row E1 to E11), 31 ids with the 21 cases of E8 | 94d172e | no change to any test |
| 2026-11-13 | green: `tests/_hermetic.py` (`decide`, `git_parts`, `guard_exit`, `Guard`, `install_guard`; `install` unchanged and still the guard of `tests/core`, whose conftest is not edited), `tests/_template.py` (new: `Templates`, `copy_template`, `files_holding`, `build_environment`, `TemplateHoldsItsPath`), `tests/conftest.py` (`OUTSIDE_CORE_MODE = "warn"`, the collector `G8Rows`, the fixtures `shared_templates`, `template_copy`, `_g8_guard`, the mark `g8_off`, `_shared_engine_sources` protected like a template with its build a guard exit). No test file was edited in this commit; decisions: R204, R207, R209. On Windows a read-only flag on a folder does not stop new files, so the guard, not chmod, protects a template; a copy is made with `copy_function=shutil.copyfile`, so a copy is writable | the commit that carries this line | `MKWAY_TEST_WORKERS=2 python -m pytest -q -n auto --dist loadgroup tests/test_mw085_templates.py tests/core tests/test_mw029_fast_guard.py tests/test_meta_cards.py tests/test_register.py tests/test_repo_scan.py`: `1867 passed in 21.31s` (the 31 ids of E1 to E11 pass; the rest is the base pass set 1832 of `tests/core`, test_mw029 and test_meta_cards plus 4). Run output ends `G8 warnings: 2`: the two warned acts are in `tests/test_mw029_fast_guard.py` (a process with the repository as working folder; outside my Paths, listed in step 7) |
| 2026-11-13 | the nine files run under the new guard, before any rewrite: `MKWAY_TEST_WORKERS=2 python -m pytest -q -n auto --dist loadgroup --durations=0 --durations-min=1 <the nine files>` | the commit that carries this line | `123 passed in 243.57s (0:04:03)` (base 237.21 s: the guard itself costs next to nothing) and `G8 warnings: 413`: writes by the tests into the module fixture's project folder, processes started with it as working folder, and the session transcripts. The 200 rows printed are all in `tests/test_e2e_gates.py`; the other 213 were not printed and the rows file was overwritten by the next run, so their files are not established here |
| 2026-11-13 | cost check of step 4. The setup time of E2 is below 0.05 s (a three-line demo template), so it says nothing about a real install; measured by hand instead: one real `install_project` base is 467 files, 5.0 s to build; a copy with `copyfile` takes 0.37 s (repository folder only, 244 files) to 0.71 to 0.87 s (whole base), 2.5 s cold. Ids needing a copy of their own: test_e2e_gates 84, test_mw068 4, test_mw061 5, test_mw056 2, test_mw070 1, test_mw062 1, test_mw060 2 (test_mw038 and test_mw030: the scenario is the subject, 0). File times from the guarded run (setup plus calls, sum not printed per file; estimates): gates about 57 s, mw068 about 24, mw061 about 28, mw056 about 18, mw070 about 13, mw062 about 17, mw060 about 16 | the commit that carries this line | arithmetic of the order: gates 84 x 0.37 to 0.87 s = 31 to 73 s against 60 percent of 57 s = 34 s: over from about 0.4 s a copy; the other six small files pass (1 to 5 copies). That alone is not «most files». The decisive finding is another: a template that has seen a session start is not copyable. A throw-away build of the gates fixture's own setup (card new, card open, four session starts, lead register, card take, gate on) took 7.0 s on top of the 5.5 s install, and its files `state/sessions.jsonl` (the field `root`, the absolute task folder) name the build folder, so `files_holding` lists it and `template_copy` refuses it (R207 Q2, 3e: it keeps building). All seven install-based files start sessions in their fixture. The clean template is the install alone (5 s), and the setup of each file on top of it costs about 7 s per test, more than one module build today. So templates give no speed for these seven files, and without them their tests keep writing into module folders (the 413 rows). STOP before step 5, numbers to retro-oper10 |
| 2026-11-13 | R211 (option 1) in step 5: grep `\bREPO\b\|real_shared_state` over the nine files: test_mw060, test_mw061, test_mw056, test_mw070, test_mw062 and test_mw068 have no match (empty result); test_e2e_gates has 5 matches (lines 26, 44, 827, 829, 833), test_mw030_live_install 2, test_mw038_real_shape 3. So those six drop `engine_repo` and take `pytestmark = pytest.mark.xdist_group("<file stem>")` (their module fixture builds once, on one worker); the three others keep `engine_repo` (their reason: the grep matches, and they are the ones that read the engine repository) | 0305263, 79a5d9d | after each commit of three files: `MKWAY_TEST_WORKERS=2 python -m pytest -q -n auto --dist loadgroup <the three files> tests/core tests/test_mw085_templates.py tests/test_mw029_fast_guard.py tests/test_register.py`: `1869 passed in 44.70s` and `1866 passed in 35.07s`, no failure |
| 2026-11-13 | defect found by the first after-run, with `MKWAY_G8_WARN_DIR=.pytest_cache/g8` (a relative folder): `tests/test_mw038_real_shape.py::test_s6_check_from_another_folder_passes_and_leaves_the_copy_alone` failed (`S6: check changed the copy: ['.pytest_cache/g8/g8_warnings_...jsonl']`). The inner `mkway check` of the engine copy runs the copy's own `tests/conftest.py` (a copy of this one), inherited the variable and wrote its rows file into the copy. Fix: the controller removes the variable from the environment when the run is configured (before xdist starts its workers); new row E25 and red test `test_a_child_of_the_run_does_not_inherit_the_rows_folder` (an inner run with `-p xdist -n 2` and an absolute rows folder: its test asserts the variable is absent, and exactly one rows file is in the folder) | the commit that carries this line | red: `1 failed, 31 passed in 8.76s`, the one failure is the new id (`assert os.environ.get("MKWAY_G8_WARN_DIR") is None` fails inside the inner run). Tests and this card only; the code is in the next commit |
| 2026-11-13 | red for row E26 (made after the E25 green row below): found while writing the wave C input file from the nine-file rows: every row id ended in `@<group>` (`--dist loadgroup` renames a worker's test id), which is not the id the six rewrite cards use. New row E26 and red test `test_a_row_id_has_no_xdist_group_suffix` (an inner run `-p xdist -n 2 --dist loadgroup` of one grouped test that writes outside its tmp_path; the ids are compared from `tests/suite/` on, because that inner run takes the rootdir of the outer repository from its `pytest.ini`) | the commit that carries this line | red: `1 failed, 32 passed`; the failure: `'test_grouped.py::test_writes_outside_its_tmp_path@grp' != 'test_grouped.py::test_writes_outside_its_tmp_path'`. Tests and this card only |
| 2026-11-13 | green for row E26: `tests/conftest.py`, `_g8_guard` records the plain test id (`re.sub(r"@[^\[\]]*$", "", nodeid)`; a parameter id in brackets never matches); no test file edited in this commit; decision: R207 | the commit that carries this line | `MKWAY_TEST_WORKERS=2 python -m pytest -q -n auto --dist loadgroup tests/test_mw085_templates.py tests/core tests/test_mw029_fast_guard.py tests/test_meta_cards.py tests/test_register.py`: `1867 passed in 20.90s`, the new id passes |
| 2026-11-13 | green for row E25: `tests/conftest.py`, `G8Rows.__init__` takes `MKWAY_G8_WARN_DIR` out of the environment (`os.environ.pop`); no test file edited in this commit; decision: R207 | the commit that carries this line | `MKWAY_TEST_WORKERS=2 python -m pytest -q -n auto --dist loadgroup tests/test_mw085_templates.py tests/core tests/test_mw029_fast_guard.py tests/test_meta_cards.py tests/test_register.py`: `1866 passed in 16.78s`, the new id passes |
| 2026-11-13 | step 6 after-facts, 2a twice at HEAD 93d8a91: `MKWAY_G8_WARN_DIR=.pytest_cache/g8final MKWAY_TEST_WORKERS=2 python -m pytest -q -n auto --dist loadgroup --durations=15 <the nine files>` | 93d8a91 | run 1 `123 passed in 165.58s (0:02:45)`, run 2 `123 passed in 139.09s (0:02:19)`; after time = 139.09 s (the lower) = 58.6 percent of the base 237.21 s (the 60 percent line is 142.33 s). Earlier pairs, same command at earlier commits: at 4c199e5 `139.27 s` and `149.06 s`; at 79a5d9d `135.86 s` and `160.80 s` with one failure, `test_mw038_real_shape.py::test_s6...`, caused by my relative rows folder (see the E25 rows). The last line of the runs: `G8 warnings: 413` in every run. The setup times are the same as at base (mw038 41.6 s, mw030 26.3 s, the six small files 8 to 11 s each, gates 10.7 s): the speed comes only from the second worker now taking the six files that left the group `shared_real`, not from a template |
| 2026-11-13 | step 6, 2b at HEAD: `python -m pytest --collect-only -q -m "engine_repo or real_shared_state" tests` and the last line | 93d8a91 | `355/3626 tests collected (3271 deselected)`: lane after 355, before 370 (the 15 ids of the six files left it) |
| 2026-11-13 | R211 b, the relaxation of R207 Q2 for these files is temporary: the acceptance row «0 warnings» of the order became «every warning listed per test id in the wave C input file». The number is 413 warning rows of 94 test ids (319 writes, 94 processes) in the nine files: test_e2e_gates 309, test_mw061 45, test_mw060 18, test_mw068 18, test_mw056 12, test_mw062 6, test_mw070 5, and none in test_mw038 and test_mw030 (their scenario builds in a module fixture, outside the guard). The reason: these seven files cannot use a template (next row), so their tests keep writing into the project folder their module fixture built, outside their own `tmp_path`. This is a recorded temporary state, not a new rule | 93d8a91 | the file `cards/MW-085-test-templates/g8_wave_c_input.jsonl`: one row `{id, act, path}` per warning, 413 rows, written from the rows file of the last run at HEAD (the two runs at HEAD wrote the same 413 rows; the rows of four runs at two commits were equal). Paths are relative to the worktree root and the worker folder is written `popen-gwN`; the ids are the plain test ids (row E26) |
| 2026-11-13 | R211 e: the wave C target for these seven files (test_e2e_gates, test_mw068_records_e2e, test_mw061_e2e, test_mw056_e2e, test_mw070_e2e, test_mw062_e2e, test_mw060_e2e) is per-test setup, not per-module setup. A template which has seen a session start cannot be copied, because the engine writes the absolute root into its state (`state/sessions.jsonl`, field `root`); the later engine card «state records relative to the root» removes that. Until then only the bare install is a clean template (5 s), and a per-test setup on top of it costs about 7 s | 93d8a91 | no run; measured numbers are in the cost-check row above |
| 2026-11-13 | R204: `CLAUDE.md` line 43 («Before every commit run the whole suite») is replaced for this card by R204: builders run only their own files plus `tests/core` locally, the whole suite runs once per merge in the merge gate. The whole suite was never run here. Files and sets run in this card: `tests/test_mw085_templates.py`, `tests/core`, `tests/test_mw029_fast_guard.py`, `tests/test_meta_cards.py`, `tests/test_register.py`, `tests/test_repo_scan.py` (term scan), the nine files, and per commit the files it changed. Last runs: `1867 passed in 20.90s` (the set above without the nine files) and the nine files `123 passed in 139.09s` | 93d8a91 | `README.md` is not in the Paths; its G8 text (README:523-525, «tests/core» only) is stale with this card, and the later switch card updates it. `tests/core/conftest.py`, `pytest.ini`, `engine/`, `tools/`, `fixtures/` were not touched. No file outside the Paths was changed |
| 2026-11-13 | the live tests E4, E9, E10, E11, E25, E26 carry the mark `g8_off`: they start real child runs whose working folder is the pytester folder (under the base temp folder, not the test's own `tmp_path`), which the guard of the outer run would warn on; the mark is registered in `tests/conftest.py` and used only by `tests/test_mw085_templates.py` | 93d8a91 | read: `grep g8_off` finds only that file and the conftest |
| 2026-11-13 | step 7, fallout: 35 entries «G8 may warn: <id> <file:line>» under `### Fallout (step 7)` below. The two entries in `tests/test_mw029_fast_guard.py` were seen in the runs (`G8 warnings: 2`); the rest are by reading | 93d8a91 | no run of the other tests; the merge gate's rows give the real ones |
| 2026-11-13 | caveat for the owner's decision on the mark: the six files that dropped `engine_repo` never read `REPO` themselves, but `_hook_driver.install_project` reads this repository's working tree as the engine source (`install.folder_files(REPO)`) and starts `mkway.py` from it. In a task's copy without the engine repository they would fail where `mkway check` used to leave them out. The grep criterion of R211 d is met; the indirect read is not covered by it | 93d8a91 | named here so R211's author can decide whether a helper-level mark is needed |
| 2026-11-13 | acceptance E1 | 73080e2 | tests/test_mw085_templates.py::test_a_template_is_built_once_and_two_fixtures_see_the_same_folder: red seen yes (94d172e, missing module), green yes |
| 2026-11-13 | acceptance E2 | 73080e2 | tests/test_mw085_templates.py::test_a_copy_is_its_own_and_writable: red seen yes, green yes |
| 2026-11-13 | acceptance E3 | 73080e2 | tests/test_mw085_templates.py::test_decide_refuses_a_write_into_a_template_folder_in_warn_mode: red seen yes, green yes |
| 2026-11-13 | acceptance E4 | 73080e2 | tests/test_mw085_templates.py::test_live_a_template_file_overwritten_outside_core_raises: red seen yes, green yes |
| 2026-11-13 | acceptance E5 | 73080e2 | tests/test_mw085_templates.py::test_the_build_saw_a_tmp_home: red seen yes, green yes |
| 2026-11-13 | acceptance E6 | 73080e2 | tests/test_mw085_templates.py::test_a_copy_holds_no_template_path: red seen yes, green yes |
| 2026-11-13 | acceptance E7 | 73080e2 | tests/test_mw085_templates.py::test_a_template_that_holds_its_own_path_is_refused_for_copies: red seen yes, green yes |
| 2026-11-13 | acceptance E8 | 73080e2 | tests/test_mw085_templates.py::test_decide_table: red seen yes (21 cases), green yes |
| 2026-11-13 | acceptance E9 | 73080e2 | tests/test_mw085_templates.py::test_outside_core_a_write_outside_the_tmp_path_passes_and_leaves_one_row: red seen yes, green yes |
| 2026-11-13 | acceptance E10 | 73080e2 | tests/test_mw085_templates.py::test_in_core_the_same_write_fails: red seen yes, green yes |
| 2026-11-13 | acceptance E11 | 73080e2 | tests/test_mw085_templates.py::test_two_workers_write_two_rows_and_no_duplicate: red seen yes, green yes |
| 2026-11-13 | acceptance E12 to E14 | 79a5d9d | none: keeps building (mw038 and mw030: the scenario is the subject; gates: sessions state names the root); mw038, mw030 and gates keep `engine_repo` by the grep; no red, no template node |
| 2026-11-13 | acceptance E15 to E20 | 0305263, 79a5d9d | none: keeps building (sessions state names the root); test_mw068, test_mw061, test_mw056, test_mw070, test_mw062, test_mw060 dropped `engine_repo` (grep for `REPO`: empty) and took their own `xdist_group`; no red, no template node |
| 2026-11-13 | acceptance E21 | 93d8a91 | checked by reading the 2a row above: 139.09 s of 237.21 s = 58.6 percent, at most 60 percent holds; no red |
| 2026-11-13 | acceptance E22 | 93d8a91 | checked by reading the 2b row above: 370 before, 355 after, smaller holds; no red |
| 2026-11-13 | acceptance E23 | 93d8a91 | checked by reading `g8_wave_c_input.jsonl`: 413 rows of 94 test ids, equal to `G8 warnings: 413` of the runs; no red |
| 2026-11-13 | acceptance E24 | 93d8a91 | checked by reading `### Fallout (step 7)`: 35 entries; no red |
| 2026-11-13 | acceptance E25 | 4c199e5 | tests/test_mw085_templates.py::test_a_child_of_the_run_does_not_inherit_the_rows_folder: red seen yes (e43838a), green yes |
| 2026-11-13 | acceptance E26 | 93d8a91 | tests/test_mw085_templates.py::test_a_row_id_has_no_xdist_group_suffix: red seen yes (e4fb013), green yes |
| 2026-11-13 | green for R213, R213a, R213c rows E27 to E29: `tests/_hermetic.py` (`decide` takes `scratch_root`: a write into the engine root outside it by an `engine_repo` test is refused in every mode; `Guard` takes `scratch_root`, and its refusal text says «into the engine repository»), `tests/conftest.py` (the group `shared_real` by `real_shared_state` alone; `_g8_guard` passes the base temp folder as `scratch_root`, and `None` for a `real_shared_state` test), and the mark `engine_repo` is back on the six files test_mw060_e2e, test_mw061_e2e, test_mw056_e2e, test_mw070_e2e, test_mw062_e2e, test_mw068_records_e2e, each with its own `xdist_group("<file stem>")`. No `engine_repo` test writes the engine repository today, so no test carries `real_shared_state` for that reason, and no new marker exists. No test file was edited but the six marks. Decisions: R213, R213a, R213c | the commit that carries this line | `MKWAY_TEST_WORKERS=2 python -m pytest -q -n auto --dist loadgroup tests/test_mw085_templates.py tests/core tests/test_mw029_fast_guard.py tests/test_meta_cards.py tests/test_register.py tests/test_repo_scan.py tests/test_mw083_real_repo.py`: `1882 passed in 34.39s`, run output ends `G8 warnings: 4` (two in tests/test_mw029_fast_guard.py and two in tests/test_mw083_real_repo.py: a child pytest started with the repository as working folder, a process; outside the Paths of the order, the merge gate's rows name the real ones). The nine files are measured in the next rows |
| 2026-11-13 | acceptance E27 | the commit that carries this line | tests/test_mw085_templates.py::test_only_real_shared_state_goes_in_the_shared_lane: red seen yes (68276f5), green yes |
| 2026-11-13 | acceptance E28 | the commit that carries this line | tests/test_mw085_templates.py::test_an_engine_repo_test_that_writes_the_engine_repo_fails: red seen yes (68276f5), green yes |
| 2026-11-13 | acceptance E29 | the commit that carries this line | tests/test_mw085_templates.py::test_decide_table_for_a_write_into_the_engine_repository: red seen yes (68276f5), green yes |
| 2026-11-13 | R213 step 5, 2a twice at HEAD c608d8d: `MKWAY_TEST_WORKERS=2 python -m pytest -q -n auto --dist loadgroup --durations=5 <the nine files>` | c608d8d | run 1 `123 passed in 160.98s (0:02:41)`, run 2 `123 passed in 145.75s (0:02:26)`; the lower, 145.75 s, is 61.4 percent of the base 237.21 s: the 60 percent line (142.33 s) is NOT met, by 3.42 s. Both runs end `G8 warnings: 413` (the same 413 rows as before the rule). The structure is the one of 93d8a91 (the six files hold their own groups, the three others keep `engine_repo` and now run spread over the workers too), whose runs were 139.09 s and 165.58 s; the spread between runs of the same code is 15 to 26 s, so 3.42 s is inside the noise, and the card does not claim the line. No third run (no new input named) |
| 2026-11-13 | R213 step 5, lane count (2b) at HEAD c608d8d: `python -m pytest --collect-only -q -m "engine_repo or real_shared_state" tests` and the same with `-m real_shared_state` | c608d8d | `370/3633 tests collected` for `engine_repo or real_shared_state`: equal to the base 370, because the mark `engine_repo` is back on the six files (at 93d8a91 it was 355). That number counts a mark, no longer a lane: the group `shared_real` now holds `real_shared_state` tests only, `30/3633 tests collected` for `-m real_shared_state`. The lane before this card was 370 tests on one worker, now it is 30 |
| 2026-11-13 | R213, R213a, R213c red, tests and this card only: rule R213 A1 (the group `shared_real` by `real_shared_state` alone) is row E27; the meta test of R213a is row E28; R213c ruled the guard fix A: `decide` takes the new argument `scratch_root` (the base temp folder), a write into the engine root outside it by an `engine_repo` test without `real_shared_state` is refused in every mode, as a template write is (R209a P1), and `scratch_root=None` (a `real_shared_state` test) follows the mode (row E29). `.pytest_tmp` lies inside the engine root, which is the only reason `scratch_root` is needed; moving the base temp folder out of the repository is a later `pytest.ini` change under R203, not now. Facts sent to the operator before this row (R213a): `decide` only warned for that case (`warn` in mode warn, `refuse` in mode raise) and could not tell a scratch file from an engine file; no `engine_repo` test writes the engine repository today (0 of the 413 rows lie outside `.pytest_tmp`; no test reads `REPO` into a write call), so no test needs `real_shared_state` for that reason and no new marker exists. Test changes: `tests/test_mw083_real_repo.py` (written yes, MW-083 rows E18 and E19; its two tests keep their names): `shared` is `real_shared_state` alone, and the second test demands only that no unshared test is in `shared_real`; `tests/test_mw085_templates.py`: every `decide` call takes `scratch_root`, and the row `engine-repo-test-writes-the-engine-repo` of E8 (it said warn, refuse) moved to the new table of E29 with its new verdict (refuse, refuse), by R213c | the commit that carries this line | red: `30 failed, 16 passed` in `tests/test_mw085_templates.py` and `tests/test_mw083_real_repo.py`. The 27 ids of the decide tests (1 + 20 + 6) fail with `TypeError: decide() got an unexpected keyword argument 'scratch_root'` (the signature is the change, so the old table is red with it, not only the new rows); the new ids E27 (`passed: 1 failed: 1`, the `engine_repo`-alone test gets the group) and E28 (the inner `engine_repo` write passes, `passed: 3` where 1 failed and 2 passed are wanted) are red; and `tests/test_mw083_real_repo.py::test_no_other_test_is_in_the_shared_group` is red, because the `engine_repo`-only tests (the three kept files and this module) are in `shared_real` today. `test_every_engine_repo_and_shared_state_test_is_in_the_shared_group` passes already: the `real_shared_state` tests hold `[['shared_real']]` today |
| 2026-11-13 | R214 gate failure, cause A (7 ids of the merge gate of t103: 4 in test_mw026_state_in_root, 1 in test_mw003_fixlist, 2 in test_mw012_commands): each calls `install.install` in process with a source from the shared folder, which `tests/conftest.py` protects as a template; `decide` refused every process whose `-C` folder lies in a template, in every mode. Fix: inside the template branch, a subcommand of `READ_ONLY_GIT` is allowed, every other process stays refused (`tests/_hermetic.py`, docstring updated) | the commit that carries this line | confirmed single process, one file at a time (`-p no:xdist`): all 7 ids fail with the same text `_hermetic.HermeticError: hermetic test: process ['git', '--no-optional-locks', '-C', '<base temp>\shared-sources0\kind0\src-none', 'rev-parse', '--show-toplevel'] with working folder None is not allowed in tests` (4 failed in mw026, 1 in mw003_fixlist, 2 in mw012); fix in the green commit of E30, 43b1802 |
| 2026-11-13 | R214 gate failure, cause B (11 ids: all 9 of tests/shell/test_hermetic_run.py, 2 of tests/shell/test_mw083_parallel_run.py): the inner pytest projects copy only conftest.py, _markers.py, _hermetic.py (and _xdist_cfg.py), and `tests/conftest.py:16` now imports `_template`. Fix: `_template.py` added to the two copy lists (the copy that runs without the guard is the thing refused, so no tolerant import), tests only | the commit that carries this line | confirmed: test_hermetic_run 9 failed, the inner output reads `tests\conftest.py:16: in <module> import _template` and `ModuleNotFoundError: No module named '_template'`; test_mw083_parallel_run 2 failed (`assert ({}, 0) == ({}, 1)` and `assert [] == ['gw0.txt', 'gw1.txt']`: the inner run died on the same import, so it printed nothing). Red proof of this fix is that output; fix in 635b8c6; the 11 ids pass in the step 6 run |
| 2026-11-13 | R214 task copy check: `engine/core_install.py:27` `SET_DIRS = ("engine/", "tools/", "tests/", "fixtures/synthetic/")`, lines 89 to 91 `in_set` = not skipped and (a SET_FILES name or a SET_DIRS prefix), line 28 `SKIP_PARTS = {".git", "__pycache__", ".pytest_tmp", ".pytest_cache"}`; `git ls-files tests/_template.py` prints `tests/_template.py` | the commit that carries this line | read, no run: a task copy receives every tracked file under `tests/` by the directory rule (no explicit list), so `_template.py` travels with it and `mkway check` finds it; no install edit |
| 2026-11-13 | R214 red for row E30: the new case `git-C-rev-parse-in-a-template` of the `decide` table (git, `-C` inside a template, subcommand `rev-parse`; allow in both modes); card edits: row E30, E8 count text, Decisions R213 and R214, Paths with the two shell test files (R214 and the operator's yes) | f8c3af9 | `python -m pytest -q -p no:xdist tests/test_mw085_templates.py`: `1 failed, 40 passed`; the failure is `tests/test_mw085_templates.py::test_decide_table[git-C-rev-parse-in-a-template]` with `assert ('refuse', 'refuse') == ('allow', 'allow')` |
| 2026-11-13 | acceptance E30 | 43b1802 | tests/test_mw085_templates.py::test_decide_table[git-C-rev-parse-in-a-template]: red seen yes (f8c3af9), green yes |
| 2026-11-13 | T7 decision R214 for the changed row E8/E29 behaviour (C1) and for the two committed test files outside the card Paths, tests/shell/test_hermetic_run.py and tests/shell/test_mw083_parallel_run.py (C2, copy lists only); the operator's yes for the two files is given in the order of this session | f8c3af9, 635b8c6 | R214 and the written order; no other file outside the Paths was changed |
| 2026-11-13 | R214 step 6 run: `MKWAY_TEST_WORKERS=2 python -m pytest -q -n auto --dist loadgroup tests/test_mw026_state_in_root.py tests/test_mw003_fixlist.py tests/test_mw012_commands.py tests/shell tests/test_mw085_templates.py tests/test_mw083_real_repo.py tests/test_mw029_fast_guard.py tests/test_meta_cards.py tests/test_register.py tests/test_repo_scan.py tests/core` | 43b1802 | `2645 passed in 128.73s (0:02:08)`, no failed, no error; the run output ends `G8 warnings: 329` (warnings, not failures; the gate's rows name them). The whole suite was not run (R204) |
| 2026-11-13 | why the gate found these five files: the card companion set (the nine files, tests/core, test_mw029, test_meta_cards, test_register, test_repo_scan, test_mw083_real_repo) had not held test_mw026_state_in_root, test_mw003_fixlist, test_mw012_commands, tests/shell/test_hermetic_run and tests/shell/test_mw083_parallel_run, so no run of the card touched them | 43b1802 | by reading the Log rows of the card; no run |
| 2026-11-13 | for wave C: an in-process install from a shared source of kind git would still be refused at `git describe` and `git archive` (not read-only); no test does that today. Named row `residual-R214a` in `g8_wave_c_input.jsonl` (R214a) | the commit that carries this line | by reading; no run |
| 2026-11-13 | the shell append of the row `residual-R214a` to `g8_wave_c_input.jsonl` was refused by the shell hook (READ-ONLY REVIEW: git-hidden, the note text names git); the operator allowed the Edit tool, and the line went in by Edit | the commit that carries this line | no run; the file now holds 414 lines, the last is the named row |

### Red run

`MKWAY_TEST_WORKERS=2 python -m pytest -q -n auto --dist loadgroup tests/test_mw085_templates.py`, base 5b627c2 plus the card and the new test file, 2026-11-13:

```
=================================== ERRORS ====================================
_______________ ERROR collecting tests/test_mw085_templates.py ________________
ImportError while importing test module '<work>/mkway-t103\tests\test_mw085_templates.py'.
Traceback:
tests\test_mw085_templates.py:21: in <module>
    import _template  # absent until the green commit: every id of this file is red by a missing module
E   ModuleNotFoundError: No module named '_template'
=========================== short test summary info ===========================
ERROR tests/test_mw085_templates.py - ImportError while importing test module...
1 error in 9.56s
```

### Base facts

2a run 1 (`123 passed in 237.21s (0:03:57)`, seed 1794533998):

```
45.01s setup    tests/test_mw038_real_shape.py::test_s1_a_sparse_linked_worktree_of_a_bigger_repository@shared_real
28.23s setup    tests/test_mw030_live_install.py::test_the_check_run_from_the_task_folder_is_clean@shared_real
11.34s setup    tests/test_mw068_records_e2e.py::test_a_real_install_writes_the_default_checker_into_the_profile@shared_real
10.87s setup    tests/test_mw062_e2e.py::test_cases_that_appear_with_the_creating_cards_files_are_allowed_through_the_real_hook@shared_real
10.43s setup    tests/test_e2e_gates.py::test_a_file_level_failure_shows_its_error_line_through_the_real_hook@shared_real
10.43s setup    tests/test_mw070_e2e.py::test_a_register_that_another_card_only_staged_refuses_the_real_close_command@shared_real
10.16s setup    tests/test_mw060_e2e.py::test_a_commit_of_the_builders_own_folder_is_allowed_through_the_real_hook@shared_real
9.34s setup    tests/test_mw056_e2e.py::test_a_new_red_is_denied_through_the_real_hook@shared_real
8.93s setup    tests/test_mw061_e2e.py::test_the_real_multiline_commit_is_allowed_through_the_real_hook[lf]@shared_real
6.26s call     tests/test_mw060_e2e.py::test_the_same_state_as_a_plain_commit_is_denied_through_the_real_hook@shared_real
5.74s call     tests/test_mw062_e2e.py::test_cases_that_appear_with_the_creating_cards_files_are_allowed_through_the_real_hook@shared_real
5.52s call     tests/test_mw056_e2e.py::test_a_new_red_is_denied_through_the_real_hook@shared_real
4.04s call     tests/test_mw061_e2e.py::test_the_same_state_as_a_plain_multiline_commit_is_denied@shared_real
3.76s call     tests/test_e2e_gates.py::test_refusal_through_the_real_hook[commit_tests_over_budget]@shared_real
3.53s call     tests/test_mw056_e2e.py::test_another_cards_old_red_is_allowed_through_the_real_hook@shared_real
123 passed in 237.21s (0:03:57)
```

2a run 2 (`123 passed in 274.61s (0:04:34)`, seed 1794534253):

```
53.38s setup    tests/test_mw038_real_shape.py::test_s1_a_sparse_linked_worktree_of_a_bigger_repository@shared_real
34.90s setup    tests/test_mw030_live_install.py::test_the_check_run_from_the_task_folder_is_clean@shared_real
14.11s setup    tests/test_e2e_gates.py::test_a_file_level_failure_shows_its_error_line_through_the_real_hook@shared_real
12.23s setup    tests/test_mw068_records_e2e.py::test_a_real_install_writes_the_default_checker_into_the_profile@shared_real
9.28s setup    tests/test_mw056_e2e.py::test_a_new_red_is_denied_through_the_real_hook@shared_real
8.93s setup    tests/test_mw070_e2e.py::test_a_register_that_another_card_only_staged_refuses_the_real_close_command@shared_real
8.61s setup    tests/test_mw062_e2e.py::test_cases_that_appear_with_the_creating_cards_files_are_allowed_through_the_real_hook@shared_real
8.54s setup    tests/test_mw061_e2e.py::test_the_real_multiline_commit_is_allowed_through_the_real_hook[lf]@shared_real
8.07s setup    tests/test_mw060_e2e.py::test_a_commit_of_the_builders_own_folder_is_allowed_through_the_real_hook@shared_real
5.41s call     tests/test_e2e_gates.py::test_a_file_level_failure_shows_its_error_line_through_the_real_hook@shared_real
4.16s call     tests/test_e2e_gates.py::test_refusal_through_the_real_hook[commit_tests_over_budget]@shared_real
4.14s call     tests/test_mw056_e2e.py::test_a_new_red_is_denied_through_the_real_hook@shared_real
4.11s call     tests/test_mw061_e2e.py::test_the_same_state_as_a_plain_multiline_commit_is_denied@shared_real
3.73s call     tests/test_mw062_e2e.py::test_cases_that_appear_with_the_creating_cards_files_are_allowed_through_the_real_hook@shared_real
3.63s call     tests/test_mw060_e2e.py::test_the_same_state_as_a_plain_commit_is_denied_through_the_real_hook@shared_real
123 passed in 274.61s (0:04:34)
```

2d inventory (by reading, no run). «Mutated» = a test changes what the builder made; «abs path» = the result holds a path of its own folder.

| Builder | file:line | Scope | Builds | Used by | Mutated | Abs path |
|---|---|---|---|---|---|---|
| `_shared_engine_sources` | tests/conftest.py:103 | session, autouse | folder `shared-sources`; `test_install.make_source` fills it lazily with one engine source per kind (no repository, or one commit) | every test that only installs from a source, read only | no (`fresh=True` builds a private one) | no |
| `make_light_source`, `make_source`, `_build_source` | tests/test_install.py:35, 50, 66 | function helpers | the engine files of this repository's working tree, `tests/` cut to one fixture test; `fresh=True` for these | `_hook_driver.make_source`, test_mw030_live_install.py:205, test_mw038_real_shape.py:459 | the light one deletes files of its private copy | no |
| `make_source` | tests/_hook_driver.py:299 | function helper | the light source plus a repository with one commit | `install_project` | no | no |
| `install_project` | tests/_hook_driver.py:309 | function helper, called from a module fixture `proj` | a scratch repository with one commit, `mkway install` of the light source into `task/T1`, five `gate on`, a commit | test_e2e_gates.py:188 (84 ids + 1 perf), test_mw068_records_e2e.py:37 (4), test_mw061_e2e.py:31 (5), test_mw056_e2e.py:38 (2), test_mw070_e2e.py:31 (1), test_mw062_e2e.py:22 (1), test_mw060_e2e.py:28 (2); also test_e2e_wake_waiter.py, test_mw054_copy_e2e.py, test_mw058_e2e.py (outside my Paths) | yes: each file's `proj` fixture adds cards, commits, stages files and puts them back after a row; mw068 and mw070 close a card (the last test) | no: a throw-away build showed no file naming its own folder (a plain repository, no linked worktree) |
| `live` | tests/test_mw030_live_install.py:184 | module | a fixture repository, a LINKED worktree with a sparse checkout, `mkway install`, `mkway check`, a lead and a builder session through the hooks, a second linked worktree: one flow | 11 ids + 1 perf, all read the one result | no after the flow | yes: a linked worktree's pointer file and the main repository's `worktrees` entry name the folders |
| `shape` | tests/test_mw038_real_shape.py:451 | module | S1 to S8: a product repository with 200+ files, a sparse linked worktree, an old install, a reinstall, hooks, commits, `mkway check`, a second linked worktree | 13 ids + 1 perf, all read the one result | no after the flow | yes: linked worktrees as above |
| small repository helpers | tests/_commit_project.py:49, tests/_commit_fixture.py:21 | function helpers | small scratch repositories | tests outside the nine files | n/a | n/a |

2e per file (build time = the `setup` line of the first test, run 1 / run 2; ids without the perf test; «copies» = ids that would need a copy of their own if the file used a template per test):

| File | Ids | Build, run 1 / run 2 | Copies needed | Note |
|---|---|---|---|---|
| tests/test_mw038_real_shape.py | 13 + 1 perf | 45.01 / 53.38 s | 0 | the scenario is the subject (a replay of one real flow, linked worktrees with their own folder in repository files): keeps building |
| tests/test_mw030_live_install.py | 11 + 1 perf | 28.23 / 34.90 s | 0 | same: keeps building |
| tests/test_e2e_gates.py | 84 + 1 perf | 10.43 / 14.11 s | 84 | one real install, rows restore their changes |
| tests/test_mw068_records_e2e.py | 4 | 11.34 / 12.23 s | 4 | tests run in file order, the last closes the card |
| tests/test_mw061_e2e.py | 5 | 8.93 / 8.54 s | 5 | |
| tests/test_mw056_e2e.py | 2 | 9.34 / 9.28 s | 2 | |
| tests/test_mw070_e2e.py | 1 | 10.43 / 8.93 s | 1 | |
| tests/test_mw062_e2e.py | 1 | 10.87 / 8.61 s | 1 | |
| tests/test_mw060_e2e.py | 2 | 10.16 / 8.07 s | 2 | |

### Fallout (step 7)

By reading (an AST scan of every test file outside the Paths and `tests/core`: a process call with no `cwd`, a process whose `cwd` is written with `REPO`, a write by a test that names no temp fixture, in any function of the file; the scan sees no act that hides in another module's function). Nothing was run. The merge gate's run gives the real rows. 35 entries:

```
G8 may warn: tests/test_dispatch.py::test_cli_and_launcher_run_a_hook tests/test_dispatch.py:531
G8 may warn: tests/test_mw003_closefix.py::test_only_plain_top_level_folder_changes_count tests/test_mw003_closefix.py:266
G8 may warn: tests/test_mw003_closefix.py::test_the_refusal_way_out_is_allowed tests/test_mw003_closefix.py:304
G8 may warn: tests/test_mw003_closefix.py::test_git_bash_folder_is_converted_before_the_join tests/test_mw003_closefix.py:322
G8 may warn: tests/test_mw003_fixlist.py::test_check_prints_the_profile_error tests/test_mw003_fixlist.py:93
G8 may warn: tests/test_mw003_fixlist.py::test_commits_follow_folder_changes tests/test_mw003_fixlist.py:269
G8 may warn: tests/test_mw003_fixlist.py::test_replay_case_stays_a_pass tests/test_mw003_fixlist.py:337
G8 may warn: tests/test_mw003_remainder.py::test_a_shape_with_no_closed_target_and_no_commit_is_only_logged tests/test_mw003_remainder.py:308
G8 may warn: tests/test_mw026_state_in_root.py::test_a_root_below_a_linked_worktree_writes_nothing_above_itself tests/test_mw026_state_in_root.py:76
G8 may warn: tests/test_mw056_judge.py::test_the_owner_is_read_from_the_file_of_the_id_and_a_folder_entry_counts tests/test_mw056_judge.py:92
G8 may warn: tests/test_mw057_export.py::test_the_error_line_is_read_from_output_with_windows_line_ends tests/test_mw057_export.py:197
G8 may warn: tests/test_mw057_export.py::test_a_backslash_path_is_shown_with_slashes tests/test_mw057_export.py:212
G8 may warn: tests/test_mw082_attributes.py::test_git_reads_union_for_both_files tests/test_mw082_attributes.py:21
G8 may warn: tests/test_profile.py::test_root_from_arg_env_or_git tests/test_profile.py:23
G8 may warn: tests/_hook_driver.py::install_project tests/_hook_driver.py:325
G8 may warn: tests/_mw020.py::index_digest tests/_mw020.py:56
G8 may warn: tests/shell/test_install_facts.py::_mkway tests/shell/test_install_facts.py:45
G8 may warn: tests/test_cards.py::_mkway tests/test_cards.py:23
G8 may warn: tests/test_dispatch.py::_hook tests/test_dispatch.py:371
G8 may warn: tests/test_e2e.py::_run_command tests/test_e2e.py:48
G8 may warn: tests/test_install.py::_start_context tests/test_install.py:183
G8 may warn: tests/test_install.py::mkway tests/test_install.py:107
G8 may warn: tests/test_mw024_task_root.py::_repo tests/test_mw024_task_root.py:16
G8 may warn: tests/test_mw028_lead_authors.py::_worktree_root tests/test_mw028_lead_authors.py:79
G8 may warn: tests/test_mw028_lead_authors.py::_worktree_root tests/test_mw028_lead_authors.py:80
G8 may warn: tests/test_mw028_lead_authors.py::_worktree_root tests/test_mw028_lead_authors.py:81
G8 may warn: tests/test_mw028_lead_authors.py::_worktree_root tests/test_mw028_lead_authors.py:82
G8 may warn: tests/test_mw028_lead_authors.py::_worktree_root tests/test_mw028_lead_authors.py:83
G8 may warn: tests/test_mw057_export.py::user_site tests/test_mw057_export.py:99
G8 may warn: tests/test_stop_warn_e2e.py::_stop tests/test_stop_warn_e2e.py:24
G8 may warn: tests/test_e2e.py::test_engine_repo_marker_selects_the_repository_only_tests tests/test_e2e.py:159
G8 may warn: tests/test_mw083_real_repo.py::_run tests/test_mw083_real_repo.py:48
G8 may warn: tests/test_mw083_real_repo.py::collected tests/test_mw083_real_repo.py:60
G8 may warn: tests/test_mw029_fast_guard.py::test_no_collected_test_reads_a_path_a_copy_lacks (seen in the runs: process, working folder = the repository)
G8 may warn: tests/test_mw029_fast_guard.py::test_the_guard_fails_when_a_marker_is_dropped (seen in the runs: process, working folder = the repository)
```
