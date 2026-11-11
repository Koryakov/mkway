# MW-003 hand-off (2026-11-10 14:45, paused for the owner's usage limit; resume after 16:30)

The remainder runs under the work order v4 (24 items; its sha256 is cited in the close report), plus R111 (a), the
isolated hook Python, as one more item. Mode (the owner's order, 10.11 about 15:00, relayed by the operator): for each
item the test, red, commit; then the code, the targeted tests green, commit; the full suite at each group end; no
waiting for checks; one line to the operator after each group. Stop only for a guard refusal that names no way out,
or at 19:30. The card does not close while a must-fix item is open.

## Where the work stands
- HEAD: the green R111 (a) commit (the one after `5508b46`). Clean tree.
- Full suite with the term scan at `77bab85` (green item 8): 290 passed, 0 failed. Since then only R111 (a), whose
  targeted run (test_mw003_remainder, test_install, test_startline) passed 44.
- Card: `cards/MW-003-gates-min/CARD.md`, rows E82-E90, Log rows Y0-Y9.

## Done and left
| Item | Finding | State | Card row | Red / green |
|---|---|---|---|---|
| 1 | (2a) commit visibility, H8, O6 | done | E82 | 6b2c858 / 8cc4d92 |
| 2 | (3a) engine calls, H9 | done | E83 | c1788e6 / 8927941 |
| 3 | close-fix 17, A-H1 | done, its Known-limit line removed | E84 | 2652e3f / a2ad155 |
| 4 | (4a) globs by segment, H14, M1 | done | E85 | 1ce683a / 6284f2b |
| 5 | H10 PowerShell dashes, splats | done | E86 | 44df458 / 98b1537 |
| 6 | H11 `-t` for four copy programs | done | E87 | e8e3dc2 / 000f1d8 |
| 7 | H12 `git restore` | done | E88 | fd64a55 / 80d0970 |
| 8 | H7 `env` chain | done | E89 | cccc779 / 77bab85 |
| R111 (a) | `python -I -X utf8` in hook commands | done; 3 install assertions changed, logged (Y9) | E90 | 5508b46 / the next commit |
| 9 | M2, verify first | next: the test is written but not in the file (it was taken out so the install check's copy suite stayed green); re-add it as below | — | — |
| 10-14 | group 2: (1b) shapes, H13, H4b, H5a, M3 | not started | — | — |
| 15-18 | group 3: O2, O1/O5 candidates, O3 reason text, O4 | not started | — | — |
| 19-20 | group 4: the acceptance figure (the operator runs it on the group-3 HEAD) | not started | — | — |
| 21-24 | group 5: close-fix 19, L1 Known-limit lines, O8 rows, the close report | not started | — | — |

## Item 9's test, to re-add on resume (`tests/test_mw003_remainder.py`)
`test_verify_first_gpg_sign_takes_only_an_attached_value(gtask)`: append a newline to `mkway/profile.json` (changed
in the working tree, index clean); assert `shell(gtask, "git commit -m x --gpg-sign mkway/profile.json")` refuses
`lock-closed-commit`; assert `helpers.commit_cmd("git commit -m x --gpg-sign=KEY -- a.py")` paths are `[["a.py"]]`.
Expected red at the base (the path is read as the key id). Green: take `--gpg-sign` out of `_COMMIT_VALUE_LONG`
(its value is attached only).

## Notes for group 2 (item 10)
The shapes, from the order and the cost model (write the patterns anew, do not copy the retro script's code): a `#`
word with a separator later on its line, or `#` right after `;&|()`; the words `case`, `function`, `trap`; `<(`/`>(`;
`CDPATH`; a compound opener after `then`/`do`/`else`/`elif`/`{`/`!`. Search them in `helpers.unquoted_text`. Effect:
every folder and name unknown; writes `everywhere` (literal reach refuses, else a log row); a named git commit
refuses `commit-folder-unreadable`; `CDPATH` with a `cd` refuses `command-unparsed`; `set -o posix` joins only if
its red test is red at the base. The B19 table test: one row per shape, through `commit_cmd` and `shell_writes`.

## Rulings and points for the close report
- The owner's test rule (Log Y0) and the later mode (above); the guard refusal of a `python -c` probe naming git and
  the operator's named form (a scratch test under `.pytest_tmp/`, Y0).
- A commit message with parentheses was refused by the guard; the standing plain form was used.
- Item 1: a PowerShell encoded command refuses with `vcs: git` only (it sits in the commit-visibility check).
- Item 3 also fixed `_script_index` for `-Ic`-style clusters.
- R111 (a): an install made before it shows start-line drift until re-installed.
