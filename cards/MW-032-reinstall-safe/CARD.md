# MW-032: Reinstall never fails half-way, check leaves nothing in the copy

| | |
|---|---|
| **Appetite** | 60 minutes — from 2026-11-11 |
| **Status** | proposed |
| **Created / updated** | 2026-11-11 / 2026-11-11 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | none new: the standing rule «a gap found in real work gets its own fix card at once» carries it |
| **Canon** | none for reinstall and check scratch: the basis is the gap the owner's own reinstall found |
| **Paths** | `engine/`, `tests/`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-032-reinstall-safe/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository. `VERSION` is not changed here.

## 1. Goal

`mkway install --ref master` over a 0.2.1 install crashed with a traceback in `shutil.rmtree(copy)`: a read-only file
under `mkway/engine/.pytest_tmp/` could not be removed on Windows, because `mkway check` had run the copy's tests with
its scratch folder inside the copy, and the removal stopped at the first folder. Now `check` keeps its test scratch
under the root's state folder (`state/check/tmp`), so it leaves no file in the copy. Install builds the new copy beside
the old one (`engine.new` in the bundle), swaps by rename, and removes the old copy with a remover that clears the
read-only bit and retries. If the removal still fails, the new copy is in place and install prints one line naming the
leftover folder. A failed swap leaves the old copy working. Never a traceback, never a half-deleted copy.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | what check leaves in the copy | test scratch under `mkway/engine/.pytest_tmp` | no file or folder added to the copy | tests/test_mw032_reinstall_safe.py::test_check_leaves_nothing_in_the_copy |
| E2 | where check keeps its scratch | inside the copy | under `state/check/tmp` of the root | tests/test_mw032_reinstall_safe.py::test_check_scratch_lives_under_the_state_folder |
| E3 | reinstall after a check | traceback on a read-only scratch file | succeeds, new copy, lock matches, no leftover folder | tests/test_mw032_reinstall_safe.py::test_reinstall_after_check_succeeds |
| E4 | reinstall over a copy holding a read-only file under `.pytest_tmp` | traceback, half-deleted copy | succeeds, the file is gone with the old copy | tests/test_mw032_reinstall_safe.py::test_reinstall_over_a_read_only_scratch_file_succeeds |
| E5 | the old copy cannot be removed | traceback | new copy in place, one line naming the leftover folder, exit 0 | tests/test_mw032_reinstall_safe.py::test_a_failed_removal_leaves_the_new_copy_and_names_the_leftover |
| E6 | the swap fails | half-deleted copy | the old copy works as before, a one-line refusal, no staging folder left | tests/test_mw032_reinstall_safe.py::test_a_failed_swap_leaves_the_old_copy_working |
| E7 | the live install flow | no reinstall step | a reinstall over an install whose check has run, no problem | tests/test_mw030_live_install.py::test_a_reinstall_over_a_checked_install_succeeds |
| E8 | register, changelog | no word | register row, a line under the release that names the card; VERSION: see VERSION | tests/test_mw032_reinstall_safe.py::test_register_changelog_and_card_name_the_card |

## 8. Log

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-11 | red: rows E1 to E6 and the E7 step | 17c5972 | E1 to E6 failed for the right reason (scratch inside the copy; `PermissionError` traceback on the read-only file; no swap; no leftover line). E7 and E8 were not red in the working tree: the light source of the live flow writes no scratch, and the register, changelog and card files were already written; at the red commit E8 lacks them |
| 2026-11-11 | green: `check` basetemp `<state>/check/tmp`, no bytecode in the copy; install builds `engine.new`, swaps by rename, removes the old copy with a read-only-aware remover, names a leftover `engine.old`, puts the old copy back on a failed swap; the swap test fails the rename of `engine.new` only (a name the card fixes) | the commit that carries this line | rows E1 to E8 green; whole suite, `python -m pytest`, term scan included, no exception added: 886 passed in 422 s. A leftover `engine.old` is not in the bundle ignore file: the leftover line tells the owner to remove it |
| 2026-11-11 | MW-027 ported onto master f77c7da: it bumps VERSION to 0.2.7, so row E8's «VERSION still 0.2.6» cannot hold; the row and the version pin in the test read 0.2.7, the same change MW-027 makes in MW-031 row E7 and the older cards; the register and changelog asserts are kept | the commit that carries this line | see the MW-027 Log |
| 2026-11-12 | MW-040: row E8 named a release number or an old VERSION | the commit that carries this line | the row says «see VERSION» and «the release that names the card»; its test reads the VERSION file and finds the card's changelog line (`tests/_docs.py`), no release number is pinned |
