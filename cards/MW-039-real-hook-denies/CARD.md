# MW-039: Every gate's refusal is proven through the real hook command

| | |
|---|---|
| **Appetite** | 90 minutes — from 2026-11-12 |
| **Status** | proposed |
| **Created / updated** | 2026-11-12 / 2026-11-12 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | none new: the standing rule «a gap found in real work gets its own fix card at once» carries it |
| **Canon** | none for hooks: the basis is the blind coverage audit of 2026-11-12 |
| **Paths** | `tests/`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-039-real-hook-denies/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository. `VERSION` is not changed here. No engine code changes: a refusal that fails on master is an xfail.

## 1. Goal

«every gate's refusal is proven through the real hook command» — task MW-039, 2026-11-12. Every refusal was tested in
process only; `test_e2e.py` promised `test_e2e_gates.py`, which did not exist, and the live release test read only the
exit code, while a PreToolUse refusal is exit 0 plus `permissionDecision: deny`. Now one driver runs the generated hook
command through the shell with `CLAUDE_PROJECT_DIR` in the environment and a real payload on stdin, and reads the verdict
from the JSON; one row per declared reason id, one allow row per gate, a meta-test over the manifest.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | the driver's verdict | an exit code only | deny, block, allow or error, read from the hook JSON | tests/test_e2e_gates.py::test_the_driver_reads_the_json_not_only_the_exit_code |
| E2 | each reason id a PreToolUse or Stop gate declares | refused in process only | a deny (a block for Stop) with that reason id from that entry, through the real command | tests/test_e2e_gates.py::test_refusal_through_the_real_hook |
| E3 | the nearest legitimate call of each gate | no real-command allow row | allowed through the real command | tests/test_e2e_gates.py::test_allow_through_the_real_hook; tests/test_e2e_gates.py::test_every_gate_has_an_allow_row |
| E4 | a declared reason id with no row | nothing noticed | the meta-test fails unless a row or a stated exemption exists | tests/test_e2e_gates.py::test_every_declared_reason_has_a_row_or_a_stated_exemption |
| E5 | the live install test's session | a deny was invisible | a deny is a problem of the flow | tests/test_mw030_live_install.py::test_the_live_session_reads_a_refusal_from_the_hook_json |
| E6 | the owner-only tripwire | in process only | a real subprocess with `CLAUDECODE` is refused and changes nothing | tests/test_e2e_gates.py::test_the_owner_only_tripwire_through_a_real_subprocess; tests/test_e2e_gates.py::test_the_same_owner_command_runs_in_the_owner_terminal |
| E7 | register, changelog | no row | register row; a hook line under the release that names the card; VERSION: see VERSION; the new tests stay under 90 s | tests/test_e2e_gates.py::test_register_changelog_and_card_name_the_card; tests/test_e2e_gates.py::test_the_rows_stay_inside_the_time_limit |

## 8. Log

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-12 | red: rows E1 to E7 | 7055e20 | the tests alone; with the driver absent the module fails to import (no tests collected, 1 error) |
| 2026-11-12 | green: `tests/_hook_driver.py`, live test flow corrected, card, register row, changelog | the commit that carries this line | finding: the live flow's card Paths lacked `src/make.py` and `src/generated.py`, so the subtask and commit gates refused the MW-034 steps unseen; Paths corrected, no engine change. Exempt reason ids (listed with why in the test): write-target-unresolved, search-unverified, orders-unacked, outbox-changed-after-check, gate-git-timeout, register-busy. Rows E1 to E7 green; whole suite, `python -m pytest`, term scan included, no exception added: 1003 passed in 613.56 s (the new gate tests alone about 70 s) |
| 2026-11-12 | MW-040: row E7 named a release number or an old VERSION | the commit that carries this line | the row says «see VERSION» and «the release that names the card»; its test reads the VERSION file and finds the card's changelog line (`tests/_docs.py`), no release number is pinned |
