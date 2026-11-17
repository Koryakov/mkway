# MW-144: release 0.4.0: raise VERSION, list the cards merged after 0.3.0

| | |
|---|---|
| **Appetite** | 1 hour - from 2026-11-17 |
| **Status** | proposed |
| **Created / updated** | 2026-11-17 / 2026-11-17 |
| **Waiting for** | us |
| **Form** | card |
| **Decisions** | none new: the basis is the order of 2026-11-17 |
| **Canon** | none for the release: the basis is the order of 2026-11-17 |
| **Paths** | `VERSION`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-144-release-040/CARD.md` |

## 1. Goal

«We should fix it in some version, apply it to DDAP and to process documentation. That's it.» — owner, 2026-11-17. VERSION becomes 0.4.0 and the changelog gets a 0.4.0 section holding the cards merged after the 0.3.0 release. No engine file and no test change; the release is tagged v0.4.0 on its merge commit by the operator's route.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | VERSION | 0.3.0 | 0.4.0 | checked by reading: VERSION |
| E2 | the changelog | the cards merged after 0.3.0 listed under 0.3.0 | a section 0.4.0 above 0.3.0 holds those cards, one line each, unchanged, and the line of MW-144; 0.3.0 keeps MW-133 | checked by reading: CHANGELOG.md |

## 8. Log

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-17 | change | this commit | VERSION 0.4.0; moved to 0.4.0 from the 0.3.0 section, taken from `git log --first-parent` since 0beaf4b (merges t135, t136, t139, t134, t141, t137, t140): MW-140, MW-139, MW-135, MW-137, MW-136, MW-134, MW-141; MW-133 stays in 0.3.0; line for MW-144 added |
| 2026-11-17 | gates | - | no new test, no engine file, no test change; the existing check MW133-D1 (top changelog section equals VERSION) is run as it is |
| 2026-11-17 | test line | this commit | MW144-D1: in tests/test_mw060_docs.py::test_register_changelog_and_card_name_the_card the MW-060 line must sit in exactly one changelog section that is a released version (the section that holds it, not the top one); the MW133-D1 line (top section's first line equals VERSION) is unchanged; no other test changed |
| 2026-11-17 | red merge | this commit | the merge of t144 into master ran red (11 failed, 7169 passed; kept as refs/mkcl/failed/t144). Fixed: the MW-144 changelog line now equals the register title; MW144-D2 (rulings_R200_R202, «## MW144-D2»): in test_mw054_decisions, test_mw056_docs, test_mw061_docs, test_mw068_docs, test_mw080_docs, test_mw100_docs, test_mw101_docs, test_mw102_docs, test_mw117_docs and test_mw103_outside_docs only the top-section check changed to: the line sits in exactly one section that is a released x.y.z. Run wide (56 files reading VERSION, CHANGELOG or REGISTER, plus tests/core): 4199 passed |
