# MW-034: The commit check reads what the commit takes; one builder per root

| | |
|---|---|
| **Appetite** | 90 minutes — from 2026-11-11 |
| **Status** | proposed |
| **Created / updated** | 2026-11-11 / 2026-11-11 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | none new: the standing rule «a gap found in real work gets its own fix card at once» carries it |
| **Canon** | none for the commit check: the basis is the gap the owner's own task found |
| **Paths** | `engine/`, `tests/`, `README.md`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-034-staged-paths/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository. `VERSION` is not changed here.

## 1. Goal

In a real task the per-file write record refused 79 files that a builder's own script had written in one
`python <script>.py` call, because the record cannot see a script's writes. The only real ride-in of the day passed:
two builders shared one worktree and one index, and the other card's test file went into the first card's commit,
because the record is about who wrote a path, not about what is staged. Now the record, its rule `ride-in-file`, its
two hook entries and their text are gone. The commit check reads the files the commit really takes: git's staged list
always, whatever paths the command names, plus the files a `--`, `-a` or `-i` form adds; any file outside the Paths of
the card the session holds is refused `file-not-in-card`. `card take` is refused `take-root-busy` while another
session holds an open card in the same task root, so there is one builder per worktree and index.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | a staged file outside the Paths | refused `file-not-in-card` only after the ownership check | refused `file-not-in-card`, naming it; a plain commit of files inside passes | tests/test_mw034_staged_paths.py::test_a_staged_file_outside_the_paths_is_refused |
| E2 | files a script wrote inside the Paths | refused `ride-in-file` (no record) | allowed, plain and with `--` | tests/test_mw034_staged_paths.py::test_files_a_script_wrote_inside_the_paths_are_allowed |
| E3 | a file staged by an earlier `git add` outside the Paths | `-- <inside file>` passed it | refused in the forms that take the staged list (`-i`, `-a`, `--amend`, plain), also after a separate `git add -A`; `-- <inside file>` takes the named path alone and passes (changed by MW-043) | tests/test_mw034_staged_paths.py::test_a_file_staged_earlier_outside_the_paths_is_judged_by_what_git_takes |
| E4 | a second session's `card take` in a busy root | allowed | refused `take-root-busy`, naming the holder (8 characters), its card and the way out | tests/test_mw034_staged_paths.py::test_a_second_session_cannot_take_a_card_in_a_busy_root |
| E5 | the holder takes its own card again | allowed | allowed | tests/test_mw034_staged_paths.py::test_the_same_session_may_take_its_own_card_again |
| E6 | a take after the holder's card closed | allowed | allowed | tests/test_mw034_staged_paths.py::test_a_take_after_the_holders_card_closed_is_allowed |
| E7 | README, register, changelog | the README described the record and `ride-in-file` | no record text, `take-root-busy` named; register row; a line under the release that names the card; VERSION: see VERSION | tests/test_mw034_staged_paths.py::test_readme_register_changelog_and_card_name_the_card |
| E8 | the recorder is gone | entries `touched.edit` and `touched.shell`, `touch`, `touched` | none of them in the manifest or the module; a write leaves no `touched.jsonl` | tests/test_mw006_touched.py::test_the_recorder_and_the_ride_in_rule_are_gone |

## 8. Log

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-11 | red: rows E1 to E7 | c3008df | six failed for the right reason (`ride-in-file` refused a script's file, a staged outside file passed after `--`, no `take-root-busy`, no register row); E5 passed, as the same session was never refused, and pins that behaviour |
| 2026-11-11 | green: rule `ride-in-file`, the recorder and its hook entries removed, `_taken` always reads the staged list, `take-root-busy` in the lock gate, README, card, register, changelog | the commit that carries this line | rows E1 to E8 green; whole suite, `python -m pytest`, term scan included, no exception added: 912 passed in 432 s. Older tests changed to the new rule, none dropped: MW-006 E9, E10 and E11 now judge by the Paths and the staged list, the recorder tests of `test_mw006_touched.py` became E8, the manifest, gate-order and README tests lost the two entries and the reason; the commit fixture `touch` writes nothing now. One step added to `tests/test_mw030_live_install.py`: a file written by `python src/make.py` inside the Paths commits. The sessions view already printed `root` per session, so it needed no change |
| 2026-11-12 | row E3 changed by MW-043: the test is renamed and judges by what the commit takes | the MW-043 green commit | the ruling of the chief replaces «refused in every form»: `-- <paths>` takes the named paths alone, so a foreign staged file is no fault of it; the refusals for `-i`, `-a`, `--amend` and the plain commit stay, and the test keeps its cases |
| 2026-11-12 | MW-040: row E7 named a release number or an old VERSION | the commit that carries this line | the row says «see VERSION» and «the release that names the card»; its test reads the VERSION file and finds the card's changelog line (`tests/_docs.py`), no release number is pinned |
