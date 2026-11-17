# MW-135: the way-out text of commit-tests-failed for a changed existing test

| | |
|---|---|
| **Appetite** | 1 hour - from 2026-11-17 |
| **Status** | proposed |
| **Created / updated** | 2026-11-17 / 2026-11-17 |
| **Waiting for** | us |
| **Form** | card |
| **Decisions** | none new: the basis is ruling R347 and the order of 2026-11-17 |
| **Canon** | none for the refusal text: the basis is the order of 2026-11-17 |
| **Paths** | `engine/gate_commit_tests.py`, `tests/test_mw135_wayout.py`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-135-red-wayout-text/CARD.md` |

## 1. Goal

A tests-only red-first commit that changes the assert of a test that exists at HEAD and was green there is refused (the red proof excuses only a test the commit defines new), but the refusal text sent the builder to the red-first commit and its «tests only» plain form, which the builder had already done. The text now says the test exists at HEAD and was green there, names the two ways out, and does not offer the plain form for it. Text only: what is allowed or refused does not change.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | refusal of a tests-only commit whose only red test exists at HEAD and was green there | «new red, not red at HEAD», then «commit the tests alone as the red-first commit» and the plain form | says the test exists at HEAD and was green there, so a red-first commit does not excuse it; names the two ways (same commit as the code change; or a new test name in the red-first commit, old test changed or removed in the green commit); no plain form | tests/test_mw135_wayout.py::test_a_tests_only_commit_of_a_changed_existing_test_says_it_exists_at_head_and_names_two_ways |
| E2 | refusal of a new red test that HEAD does not have | the old text | the old text, word for word | tests/test_mw135_wayout.py::test_a_new_red_test_that_is_not_at_head_keeps_the_old_refusal_text_exactly |
| E3 | the two ways out | - | the change committed with the code change passes the gate; the new expectation under a new test name passes as the red-first commit | tests/test_mw135_wayout.py::test_the_two_ways_out_of_the_changed_existing_test_pass_the_gate |

## 8. Log

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-17 | red tests | c85bc16 | tests/test_mw135_wayout.py: E1 red (the old text); E2 and E3 green at once (they pin what must not change) |
| 2026-11-17 | code | this commit | `_refusal` takes the ids of the new red that HEAD collects (`_head_ids`, read in `_new_red`) and says so; nothing allowed or refused changed; the label starts «new red (not red at HEAD: ...» because four older tests (test_mw062_shell x2, test_mw056_e2e, test_mw060_e2e) pin the words «new red» and «not red at HEAD», unchanged; full suite: 6983 passed, 2 xfailed |
