# MW-033: The commit message names the card anywhere in the first line

| | |
|---|---|
| **Appetite** | 45 minutes — from 2026-11-11 |
| **Status** | proposed |
| **Created / updated** | 2026-11-11 / 2026-11-11 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | none new: the standing rule «a gap found in real work gets its own fix card at once» carries it |
| **Canon** | none for the commit message rule: the basis is the gap the owner's own task found |
| **Paths** | `engine/`, `tests/`, `README.md`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-033-commit-msg-card-anywhere/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository. `VERSION` is not changed here.

## 1. Goal

In a real task the commit gate refused a message that held the open card's id after the product repository's own
leading task number, and a card made before the profile prefix changed could never commit, because the open card's own
id was tried only when no prefix was set. Now the gate always accepts the open card's own id, literally, as a whole
word in the message, wherever it stands and whatever the prefix is now. No id, a longer number (`CARD-0011` for
`CARD-001`) or the id of a card the session does not hold is still refused. The refusal says to put the id anywhere in
the first line. A chained add and commit is refused with the fix named: run them as two separate calls. The README
says each in one line.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | the id after another leading token | refused when the prefix was not the card's | `#10536 CARD-001 text` and `CARD-001 #10536 text` pass; no id, `CARD-0011`, another card refused | tests/test_mw033_commit_gate.py::test_the_id_may_stand_anywhere_in_the_subject |
| E2 | a card made under an earlier prefix | prefix DD, open card CARD-001: always refused | `#10536 CARD-001 text` passes; `DD-007` and no id refused | tests/test_mw033_commit_gate.py::test_the_open_card_id_passes_whatever_the_prefix_is_now |
| E3 | text of `commit-message-card` | «start it with the id» | «put the card id anywhere in the first line, for example -m "<id> <what changed>"» | tests/test_mw033_commit_gate.py::test_the_refusal_says_the_id_may_stand_anywhere_in_the_first_line |
| E4 | text of `commit-unreadable` on a chained add and commit | did not say to split the call | names «run git add and git commit as two separate calls», for `&&` and `;` | tests/test_mw033_commit_gate.py::test_a_chained_add_and_commit_says_to_use_two_calls |
| E5 | README, register, changelog | no word | one README line on each rule, register row, a line under the release that names the card, VERSION: see VERSION | tests/test_mw033_commit_gate.py::test_readme_register_changelog_and_card_name_the_card |

## 8. Log

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-11 | red: rows E1 and E2 | 6994234 | E2 failed for the right reason (the open card id refused under prefix DD). E1 was not red: with prefix CARD the id was already found anywhere in the message, so E1 pins that behaviour |
| 2026-11-11 | green: rows E1 and E2, the open card's own id always accepted as a whole word in the message | 7eb262c | rows E1 and E2 green, with the MW-006 commit tests. The id is searched in the whole message, not only the first line, so a second `-m` paragraph still passes as before (MW-006 E20) |
| 2026-11-11 | red: rows E3 to E5 | dfb83ae | all three failed for the right reason (old texts, no README line, no register row) |
| 2026-11-11 | green: refusal texts of E3 and E4, README lines, card, register, changelog | 5c8952f | rows E3 to E5 green; whole suite, `python -m pytest`, term scan included, no exception added: 891 passed in 436 s. The E5 test got the `engine_repo` mark (the MW-029 guard: it reads the README), the assertions are unchanged |
| 2026-11-11 | port onto master 28b7ab6 (MW-027 merged): row E5 changed, the changelog line goes under `## 0.2.7` and VERSION is 0.2.7 | the commit that carries this line | the row named `## 0.2.6` and VERSION 0.2.6, true on the branch base f77c7da, wrong on master; the E5 test and this row now name 0.2.7, no other assertion changed; the other rows and the gate are as on 5c8952f; whole suite, `python -m pytest`, term scan included, no exception added: 906 passed in 439 s |
| 2026-11-12 | MW-040: row E5 named a release number or an old VERSION | the commit that carries this line | the row says «see VERSION» and «the release that names the card»; its test reads the VERSION file and finds the card's changelog line (`tests/_docs.py`), no release number is pinned |
