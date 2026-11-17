# MW-079: Test files may share a name across tests/shell and the flat folders

| | |
|---|---|
| **Appetite** | 1 hour — from 2026-11-12 |
| **Status** | proposed |
| **Created / updated** | 2026-11-12 / 2026-11-13 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | R192a, R193 |
| **Canon** | none: the basis is the pytest documentation on same-named test files and the chief ruling R192a |
| **Paths** | `tests/`, `README.md`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-079-shell-package/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository. `VERSION` is not changed here. There is no refusal reason, no hook and no engine code: the gate items of
the common rules (the `tests.<key>.mode` switch, reason ids, the e2e deny, the manifest, the time added per commit,
coverage of engine lines) do not apply. The change is one empty `tests/shell/__init__.py` plus guards.

## 1. Goal

«test files may share a name across tests/shell and the flat folders» — retro-oper10 order, ruling R192a, 2026-11-12.
Real case (card MW-073 on t90): `tests/core/test_shape_edges.py` and `tests/shell/test_shape_edges.py` could not both
be collected. `tests/shell` becomes a package; `tests/core` stays flat, because `engine/core.py` is imported as `core`
by tests of `tests/core` and `tests/shell`, and a `tests/core` package would shadow it.

## Acceptance examples

Each row becomes a test; `card close` needs every row to name one. E1 is the red id; E2 to E6 are green on the base
(synthetic tree, or the real tree before the change) and stay green: they are «Checks:» rows next to the red E1.

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | the module name of a test file in `tests/shell` | the bare file name | the file name below the package `shell` | tests/shell/test_mw079_package.py::test_a_shell_test_module_belongs_to_the_shell_package |
| E2 | replay of the real clash: `tests/core/test_x.py` and `tests/shell/test_x.py`, shell without `__init__.py`, parametrize case `without_init` | collection error | exit code 2 and the output names `import file mismatch` | tests/shell/test_mw079_same_name.py::test_same_named_files_clash_without_a_package_and_collect_with_one |
| E3 | the same tree, shell with `__init__.py` (nearest allow of E2), case `with_init` | collection error | exit code 0 and `2 passed` | tests/shell/test_mw079_same_name.py::test_same_named_files_clash_without_a_package_and_collect_with_one |
| E4 | guard 1: a test subfolder with `__init__.py` named like an engine module (`engine/*.py` basenames) | n/a | none exists | tests/test_mw079_layout.py::test_no_test_package_is_named_like_an_engine_module |
| E5 | guard 2: a `test_*.py` basename shared by two flat test folders (`tests/` root and `tests/core`: folders with test modules and no `__init__.py`) | n/a | none shared | tests/test_mw079_layout.py::test_no_flat_test_folder_shares_a_test_file_name_with_another |
| E6 | guard 3: `tests/__init__.py` and `tests/core/__init__.py` | n/a | do not exist | tests/test_mw079_layout.py::test_tests_root_and_tests_core_stay_flat |
| E7 | the README | none | one line at the end of «Tests before a commit»: shell is a package, core is flat because `engine/core.py` is imported as `core`; same-name files allowed between shell and the flat folders, never inside the flat ones | checked by reading: README.md |

## 8. Log

One line per step. No re-run of a check or an agent round without a new input named in the Log row.

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-12 | step 0, first check was wrong: `import shell` with `engine` and `tests` on the path succeeded, because Python finds `tests/shell` itself as a namespace package (no `__init__.py`); the check was stopped and the lead corrected it | none | corrected check from the repo root: `python -c "import sys; sys.path[:0]=['engine']; import importlib.util; print(importlib.util.find_spec('shell'))"` printed `None`: no other module named `shell` in `engine/` or installed |
| 2026-11-12 | scope: no refusal, no engine code; the gate items of the common rules (mode switch, reason ids, e2e deny, manifest, time per commit) and coverage (rule e) do not apply | none | said here as the order asks |
| 2026-11-12 | red commit: tests only (3 test files) plus the card, register row and changelog line; red proof: `python -m pytest -q` on the 3 files printed `1 failed, 5 passed`, the failed id E1 `assert 'test_mw079_package' == 'shell.test_mw079_package'`; E2 to E6 are «Checks:» rows, green on the base (R183). Whole suite before the commit: 4 failed, 3421 passed, 2120 s: the red id, a card cell fixed after the run (E1 Was cell read as a bare test name; `tests/test_meta_cards.py` passes after), and the two time-limit tests (below) | d6558db | red seen for E1 |
| 2026-11-12 | green commit: the empty `tests/shell/__init__.py` and one README line; `tests/` and `tests/core` get no `__init__.py`. Grep in `tests/shell` for `from conftest import`, `import conftest`, relative imports: no match. Runs on the green tree: the 3 files, `tests/core`, `tests/shell`, `tests/test_meta_cards.py` and the four core purity checks together: 2432 passed in 240 s. Whole suite once: 1 failed, 3424 passed, 1 deselected, 1358 s; the one failure is `tests/test_mw038_real_shape.py::test_the_scenario_runs_inside_the_time_limit` | this commit | E1 green |
| 2026-11-12 | known failures, not this card: `test_mw030_live_install.py::test_the_run_stays_inside_the_time_limit` (failed once under load, passed on re-run) and `test_mw038_real_shape.py::test_the_scenario_runs_inside_the_time_limit` (88 s against 60 s on a loaded machine): load failures; master 8cc1d84 already marks both perf (MW-077), this base 5343c1c predates that | none | named as the lead asked |
| 2026-11-12 | not applicable: coverage (rule e) as no engine code changed; no mode switch, reason id, e2e deny, manifest entry or time added per commit | none | said here |
| 2026-11-12 | known limit, not fixed: `tests/test_meta_cards.py` indexes test files by basename (lines 36 and 37), so after this card a row `test_x.py::name` matches a same-named file in either folder | none | reported |
| 2026-11-12 | acceptance E1 | 7fcac76 | tests/shell/test_mw079_package.py::test_a_shell_test_module_belongs_to_the_shell_package: red seen yes, green yes |
| 2026-11-12 | acceptance E2 | 7fcac76 | tests/shell/test_mw079_same_name.py::test_same_named_files_clash_without_a_package_and_collect_with_one[without_init]: red seen: Checks row, green on the base; green yes |
| 2026-11-12 | acceptance E3 | 7fcac76 | tests/shell/test_mw079_same_name.py::test_same_named_files_clash_without_a_package_and_collect_with_one[with_init]: red seen: Checks row, green on the base; green yes |
| 2026-11-12 | acceptance E4 | 7fcac76 | tests/test_mw079_layout.py::test_no_test_package_is_named_like_an_engine_module: red seen: Checks row, green on the base; green yes |
| 2026-11-12 | acceptance E5 | 7fcac76 | tests/test_mw079_layout.py::test_no_flat_test_folder_shares_a_test_file_name_with_another: red seen: Checks row, green on the base; green yes |
| 2026-11-12 | acceptance E6 | 7fcac76 | tests/test_mw079_layout.py::test_tests_root_and_tests_core_stay_flat: red seen: Checks row, green on the base; green yes |
| 2026-11-12 | acceptance E7 | 7fcac76 | checked by reading: README.md; red seen n/a, green yes |
| 2026-11-13 | the acceptance table moved into Log rows: test_register refuses a second table in the Log (mkcl gate of t97, 13.11; R210, R204) | this commit | test_register, test_meta_cards, tests/core and the term scan pass |
