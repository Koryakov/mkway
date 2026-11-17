# MW-083: The suite runs in parallel

| | |
|---|---|
| **Appetite** | 3.5 hours — from 2026-11-13 |
| **Status** | proposed |
| **Created / updated** | 2026-11-13 / 2026-11-13 |
| **Waiting for** | owner: installs the pinned packages, opens the card and closes it |
| **Form** | card |
| **Decisions** | R198, R199, R200, R203 |
| **Canon** | none: the basis is the xdist research, the conditions S1 to S11 and the proposal P1 to P9, accepted by R200 |
| **Paths** | `tests/_xdist_cfg.py`, `tests/conftest.py`, `tests/_hermetic.py`, `tests/core/test_mw083_workers.py`, `tests/shell/test_mw083_parallel_run.py`, `tests/test_mw083_real_repo.py`, `tools/requirements-test.txt`, `CLAUDE.md`, `README.md`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-083-parallel-suite/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository. `VERSION` is not changed here. There is no refusal reason, no hook gate and no profile switch: the parallel
run is a way to run pytest, so the common-rule items `tests.<key>.mode`, reason ids, e2e deny and the time per commit
do not apply. The engine's own commit gate (`engine/gate_commit_tests.py`) stays serial in this card; the owner's
`policy.json` `test-command` changes after the merge (one line, in the Log).

## 1. Goal

«you should stop all tests running. and first - you must apply parallelism» — owner, 2026-11-13; «may mkway use
pytest-xdist - yes if it safe» — owner, 2026-11-12. The whole suite runs on parallel workers with the same pass and fail
set as the serial run, and still runs serially when the package is absent.

## Acceptance examples

Each row becomes a test; `card close` needs every row to name one. E1 to E10 are pure (`tests/core`), E11 to E13 run a
real pytest with workers on a small synthetic project, E14 to E21 read or run the real repository.

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | worker count, 16 cores, no variable | n/a | 8: half the cores | tests/core/test_mw083_workers.py::test_workers_default_to_half_the_cores |
| E2 | worker count, 1 core, no variable (nearest allow of E1) | n/a | 1: never below one | tests/core/test_mw083_workers.py::test_workers_default_to_half_the_cores |
| E3 | worker count, the machine gave no core count | n/a | 1 | tests/core/test_mw083_workers.py::test_workers_default_to_half_the_cores |
| E4 | worker count, `MKWAY_TEST_WORKERS=3` on 16 cores | n/a | 3: the variable wins | tests/core/test_mw083_workers.py::test_the_variable_overrides_the_cores |
| E5 | `MKWAY_TEST_WORKERS=0` | n/a | refused: `MKWAY_TEST_WORKERS must be a whole number above 0` | tests/core/test_mw083_workers.py::test_a_bad_variable_is_refused_with_the_fixed_text |
| E6 | `MKWAY_TEST_WORKERS=x` (second deny of E5) | n/a | refused with the same text | tests/core/test_mw083_workers.py::test_a_bad_variable_is_refused_with_the_fixed_text |
| E7 | the controller hands its seed to a worker | no key in the worker input | the key holds the seed | tests/core/test_mw083_workers.py::test_the_controller_seed_is_put_in_the_worker_input |
| E8 | a worker's seed, the worker input holds one | the clock | the handed seed | tests/core/test_mw083_workers.py::test_run_seed_takes_the_seed_handed_to_a_worker |
| E9 | the seed of a serial run, no worker input (nearest allow of E8) | the option, else the clock | unchanged | tests/core/test_mw083_workers.py::test_run_seed_of_a_serial_run_is_the_given_option |
| E10 | a worker whose input holds no seed (nearest allow of E8) | the option, else the clock | unchanged | tests/core/test_mw083_workers.py::test_a_worker_without_a_handed_seed_uses_the_option |
| E11 | real run, `-n 2`, no `--seed`: the seed each worker uses | each worker takes the clock | both workers use the seed the controller printed | tests/shell/test_mw083_parallel_run.py::test_every_worker_uses_the_seed_the_controller_printed |
| E12 | real run, `-n auto` with `MKWAY_TEST_WORKERS=2` and `PYTEST_XDIST_AUTO_NUM_WORKERS=5` | the xdist variable counts | two workers: only `MKWAY_TEST_WORKERS` counts | tests/shell/test_mw083_parallel_run.py::test_auto_takes_its_count_from_the_variable_only |
| E13 | real run, `-n 2`, each worker's temp folder | n/a | different folders, all below the given `--basetemp` | tests/shell/test_mw083_parallel_run.py::test_each_worker_has_its_own_temp_folder_under_the_basetemp |
| E14 | `tools/requirements-test.txt` | no file | the two pinned lines with their hashes | tests/test_mw083_real_repo.py::test_the_requirements_file_pins_the_two_packages |
| E15 | `python -m pytest -p no:xdist tests/core` on the real conftest (S4) | green | green: the new hooks are optional | tests/test_mw083_real_repo.py::test_the_core_tests_run_without_xdist |
| E16 | the real `pytest.ini` addopts (S4) | no `-n`, no `--dist` | unchanged | tests/test_mw083_real_repo.py::test_the_default_options_hold_no_worker_option |
| E17 | `python -m pytest -n 2 tests/core`, the hermetic guard under workers (S3) | n/a | green | tests/test_mw083_real_repo.py::test_the_core_tests_run_in_parallel_with_the_guard_on |
| E18 | every `engine_repo` and `real_shared_state` test (S7) | no group | in `xdist_group("shared_real")` | tests/test_mw083_real_repo.py::test_every_engine_repo_and_shared_state_test_is_in_the_shared_group |
| E19 | any other test (nearest allow of E18) | no group | in no group | tests/test_mw083_real_repo.py::test_no_other_test_is_in_the_shared_group |
| E20 | replay: the whole suite through the exact text `python -m pytest -n auto --dist loadgroup` (R200), and the serial and two other seeded pairs | serial only | the same pass and fail set in each pair | checked by reading: cards/MW-083-parallel-suite/CARD.md |
| E21 | CLAUDE.md lines 22 and 42, the README paragraph and command list | serial text | both commands named, the worker count rule stated | checked by reading: CLAUDE.md; README.md |

## 8. Log

One line per step. No re-run of a check or an agent round without a new input named in the Log row.

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-13 | start checks, each alone: `pwd` = the worktree, HEAD 8cc1d84, `git status --short` = clean | 8cc1d84 | base of the card |
| 2026-11-13 | `python -c "import xdist"` failed at the start (`ModuleNotFoundError`; execnet missing too): stop reported to the lead, no run with `-n` before the install | 8cc1d84 | the owner installed both packages with hash checks; `import xdist` then printed 3.8.0 (checked here before the first `-n` run) |
| 2026-11-13 | red: this card with its Acceptance table (E1 to E21), register row, changelog line, tests only: `tests/core/test_mw083_workers.py` (10 ids), `tests/shell/test_mw083_parallel_run.py` (3 ids), `tests/test_mw083_real_repo.py` (6 ids), decisions: R199, R200 | the commit that carries this line | red ids: the 10 core ids (E1 to E10) fail, red by missing module `_xdist_cfg` (collection error); E11 FAILED (worker seeds `1794525488` and `1794525490` differ from each other and from the printed seed: each worker took its own clock); E12 FAILED (`-n auto` started five workers, gw0 to gw4: the xdist variable counted); E14 FAILED (`tools/requirements-test.txt` absent); E15 FAILED (exit 2) and E17 FAILED (exit 1) only because their child run of `tests/core` collects the red core file above (on base without that file: `-p no:xdist tests/core` 1746 passed in 14.9 s and `-n 2 --seed 3 tests/core` 1746 passed in 9.3 s, so both are green on base); E18 FAILED (no test carries `xdist_group` yet). Checks green on base: E13 (each worker has its own temp folder under a given `--basetemp`: four different paths, none outside it, so `pytest.ini` stays as it is, R203), E16 (the addopts hold no worker option), E19 (no test is grouped). Child runs use `--basetemp` below tmp_path, never `.pytest_tmp`. In E17 the order's command gets `--seed 3`, so the row does not depend on the clock (E11 proves the no-seed case). The red run is under `### Red run` below |
| 2026-11-13 | not applicable here: `tests.<key>.mode` switch, reason ids, e2e deny, time per commit (no refusal, no engine gate; the engine's commit gate stays serial) | n/a | the parallel run is a pytest option, not a gate |
| 2026-11-13 | green for E1 to E19: `tests/_xdist_cfg.py` (`worker_count`, `put_seed`, `handed_seed`), `tests/conftest.py` (`pytest_xdist_auto_num_workers`, `pytest_configure_node`, both `optionalhook=True`; `pytest_configure` registers the mark `xdist_group`; `pytest_collection_modifyitems` puts `xdist_group("shared_real")` on every `engine_repo` and `real_shared_state` test by marker, and runs first so xdist reads the group), `tests/_hermetic.py` (`run_seed` takes the seed a worker was handed; the helper is imported only by a worker, so a serial run and the older copies in `tests/shell/test_hermetic_run.py` are unchanged), `tools/requirements-test.txt`; decisions: R199, R200, R203. `tests/` files were not edited in this commit | the commit that carries this line | the 19 ids of the red commit pass (`test_mw083_workers.py` 10, `test_mw083_parallel_run.py` 3, `test_mw083_real_repo.py` 6: 19 passed in 43.6 s); `tests/shell/test_hermetic_run.py`, `tests/core` and `tests/test_meta_cards.py` 1770 passed in 31.9 s. `pytest.ini` is untouched (R203): the fixed `--basetemp` does not break under workers, E13 shows four different folders below it |
| 2026-11-13 | execnet: `tools/requirements-test.txt` pins `execnet==2.1.2` beside `pytest-xdist==3.8.0`. execnet is the required dependency of xdist (`execnet>=2.1`), not an extra package in the sense of S1; the owner installed both with hash checks | the commit that carries this line | S1 holds: one source (PyPI), exact versions, hashes, nothing else new |
| 2026-11-13 | coverage, `python -m coverage run --branch -m pytest tests/core/test_mw083_workers.py`, then `coverage report -m --include=tests/_xdist_cfg.py` | the commit that carries this line | `tests/_xdist_cfg.py` 13 statements, 4 branches, missed lines: none (100 percent). The run of `run_seed` in `tests/_hermetic.py` is covered by the same file (the lines it misses are the guard of MW-074, run by other tests). Hook lines run only in a controller or a worker, so coverage of this process cannot see them; the named subprocess tests do: `pytest_xdist_auto_num_workers` by `tests/shell/test_mw083_parallel_run.py::test_auto_takes_its_count_from_the_variable_only`; `pytest_configure_node` by `tests/shell/test_mw083_parallel_run.py::test_every_worker_uses_the_seed_the_controller_printed`; the group lines of `pytest_collection_modifyitems` by `tests/test_mw083_real_repo.py::test_every_engine_repo_and_shared_state_test_is_in_the_shared_group` and `::test_no_other_test_is_in_the_shared_group`; `pytest_configure` and the optional hooks without xdist by `tests/test_mw083_real_repo.py::test_the_core_tests_run_without_xdist` |
| 2026-11-13 | proof P1, the exact planned policy text, exit code and final summary line verbatim. Machine: 8 logical cores, so `-n auto` started 4 workers (half). Command: `python -m pytest -n auto --dist loadgroup` | the commit that carries this line | seed 1794525787 (read from the printed `hermetic seed: 1794525787`); exit code 1; final line `================= 1 failed, 3434 passed in 569.08s (0:09:29) ==================`; failed: `tests/test_repo_scan.py::test_repository_has_no_term_hits` (printed `@shared_real` after the id by `--dist loadgroup`) |
| 2026-11-13 | proof P2: `python -m pytest -q -n auto --dist loadgroup --seed 4101` | the commit that carries this line | seed 4101; passed 3434; failed 1; 540.80 s; failed: `tests/test_repo_scan.py::test_repository_has_no_term_hits` |
| 2026-11-13 | proof P3: `python -m pytest -q -n auto --dist loadgroup --seed 4202` | the commit that carries this line | seed 4202; passed 3434; failed 1; 520.04 s; failed: `tests/test_repo_scan.py::test_repository_has_no_term_hits` |
| 2026-11-13 | proof S1, the serial twin of P1, xdist absent (the S4 path, S11): `python -m pytest -q -p no:xdist --seed 1794525787`. R204 (3+1: the serial run is the baseline set, its seed equals the seed of P1 so one exact twin pair exists; ruled for the owner's speed) replaced the three serial runs of the order | the commit that carries this line | seed 1794525787; passed 3434; failed 1; 4 deselected (the perf tests); 982.20 s; failed: `tests/test_repo_scan.py::test_repository_has_no_term_hits` |
| 2026-11-13 | result of the proof: the pass and fail sets of P1, P2, P3 and S1 are equal (3434 passed, the same one failed id in all four); no test differs between modes or between seeds, so no test got `xdist_group` and no run was repeated. The one failure is the same in both modes and is not fixed here: the term scan hit at `cards/MW-077-perf-rest/CARD.md:42` (known, MW-084 removes it; not mine, no file of MW-077 edited). `-p no:cacheprovider` ran with xdist in every parallel run (it is in `addopts`; S6): no run failed by it. The three parallel runs took 521 to 571 s against 982 s serial, a factor of 1.7 on 4 workers; each parallel log names one seed (P1 twice, in the header and in the summary, the same number) and none holds xdist's «Different tests were collected» error | the commit that carries this line | S2 and S11 hold for the four runs; no term file or term printed |
| 2026-11-13 | docs: `CLAUDE.md` line 22 (packages pinned in `tools/requirements-test.txt`, installed by the owner) and line 42 (both commands, the merge runs the parallel one, the worker count is set only by `MKWAY_TEST_WORKERS`, `PYTEST_XDIST_AUTO_NUM_WORKERS` is ignored, R203); README one paragraph at the end of «Tests before a commit» and both commands under «Run the checks»; REGISTER row and CHANGELOG line at the end of their sections. The hook `pytest_xdist_auto_num_workers` overrides `-n auto`, so `auto` means half the logical cores | the commit that carries this line | E21 checked by reading |
| 2026-11-13 | the line for the owner's policy.json: `"test-command": "python -m pytest -n auto --dist loadgroup"` | the commit that carries this line | exact text, as run in P1 |
| 2026-11-13 | table, Acceptance row -> test node -> red seen -> green: E1 to E3 `tests/core/test_mw083_workers.py::test_workers_default_to_half_the_cores` yes yes; E4 `::test_the_variable_overrides_the_cores` yes yes; E5 and E6 `::test_a_bad_variable_is_refused_with_the_fixed_text` yes yes; E7 `::test_the_controller_seed_is_put_in_the_worker_input` yes yes; E8 `::test_run_seed_takes_the_seed_handed_to_a_worker` yes yes; E9 `::test_run_seed_of_a_serial_run_is_the_given_option` yes (red by the missing module) yes; E10 `::test_a_worker_without_a_handed_seed_uses_the_option` yes (red by the missing module) yes; E11 `tests/shell/test_mw083_parallel_run.py::test_every_worker_uses_the_seed_the_controller_printed` yes yes; E12 `::test_auto_takes_its_count_from_the_variable_only` yes yes; E13 `::test_each_worker_has_its_own_temp_folder_under_the_basetemp` no (a check, green on base) yes; E14 `tests/test_mw083_real_repo.py::test_the_requirements_file_pins_the_two_packages` yes yes; E15 `::test_the_core_tests_run_without_xdist` yes (exit 2 by the red core file) yes; E16 `::test_the_default_options_hold_no_worker_option` no (a check, green on base) yes; E17 `::test_the_core_tests_run_in_parallel_with_the_guard_on` yes (exit 1 by the red core file) yes; E18 `::test_every_engine_repo_and_shared_state_test_is_in_the_shared_group` yes yes; E19 `::test_no_other_test_is_in_the_shared_group` no (a check, green on base) yes; E20 checked by reading the rows above, no red; E21 checked by reading CLAUDE.md and README.md, no red | the commit that carries this line | all rows green |

### Red run

Base 8cc1d84 plus the three new test files, pytest 9.1.1, pytest-xdist 3.8.0, 2026-11-13.

```
$ python -m pytest -q tests/core/test_mw083_workers.py
E   ModuleNotFoundError: No module named '_xdist_cfg'
ERROR tests/core/test_mw083_workers.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.36s

$ python -m pytest -q -rf tests/shell/test_mw083_parallel_run.py tests/test_mw083_real_repo.py --tb=no
FF.FF.FF.
FAILED tests/shell/test_mw083_parallel_run.py::test_every_worker_uses_the_seed_the_controller_printed
FAILED tests/shell/test_mw083_parallel_run.py::test_auto_takes_its_count_from_the_variable_only
FAILED tests/test_mw083_real_repo.py::test_the_requirements_file_pins_the_two_packages
FAILED tests/test_mw083_real_repo.py::test_the_core_tests_run_without_xdist
FAILED tests/test_mw083_real_repo.py::test_the_core_tests_run_in_parallel_with_the_guard_on
FAILED tests/test_mw083_real_repo.py::test_every_engine_repo_and_shared_state_test_is_in_the_shared_group
6 failed, 3 passed in 27.12s
```

The three passing ids are checks that are green on base: `test_each_worker_has_its_own_temp_folder_under_the_basetemp` (E13),
`test_the_default_options_hold_no_worker_option` (E16), `test_no_other_test_is_in_the_shared_group` (E19).
