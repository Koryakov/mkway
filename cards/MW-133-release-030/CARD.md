# MW-133: release 0.3.0: clean card paths, raise VERSION

| | |
|---|---|
| **Appetite** | 1 hour - from 2026-11-17 |
| **Status** | proposed |
| **Created / updated** | 2026-11-17 / 2026-11-17 |
| **Waiting for** | us |
| **Form** | card |
| **Decisions** | none new: the basis is the order of 2026-11-17 |
| **Canon** | none for the release: the basis is the order of 2026-11-17 |
| **Paths** | `cards/MW-072-red-proof/CARD.md`, `cards/MW-085-test-templates/CARD.md`, `cards/MW-093-rewrite-g1/CARD.md`, `cards/MW-094-rewrite-g2/ownset_run.txt`, `cards/MW-096-rewrite-g4/CARD.md`, `cards/MW-097-rewrite-g5/CARD.md`, `cards/MW-098-rewrite-g6/CARD.md`, `cards/MW-098-rewrite-g6/ownset_run.txt`, `VERSION`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-133-release-030/CARD.md` |

## 1. Goal

«lets push mkway» — owner, 2026-11-17. The publish scan refuses machine paths, and the published version 0.2.7 cannot be published again: the local folder prefix in eight card files is written as `<work>/`, VERSION becomes 0.3.0, and the changelog gets a 0.3.0 section. No engine code change. One test line changes under decision row MW133-D1: the check in tests/test_mw060_docs.py that pinned the version "0.2.7" now checks that the first line of the top changelog section equals VERSION.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | a local folder path in the eight card files | machine paths in 102 lines | the same lines with the prefix `<work>/`, nothing else changed in them; `git grep -i` for the folder name prints nothing | checked by reading: cards/MW-094-rewrite-g2/ownset_run.txt |
| E2 | VERSION | 0.2.7 | 0.3.0 | checked by reading: VERSION |
| E3 | the changelog | the cards after 0.2.7 listed under 0.2.7 | a section 0.3.0 above 0.2.7 holds those cards, one line each; 0.2.7 keeps its own card | checked by reading: CHANGELOG.md |

## 8. Log

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-17 | change | this commit | prefix replaced in the eight files; VERSION 0.3.0; the lines of the cards merged after 0.2.7 moved from the 0.2.7 section to a new 0.3.0 section (0.2.7 as published held only MW-027) |
| 2026-11-17 | gates | - | no new test and no engine code; one existing test line was changed under MW133-D1 (the "0.2.7" pin became a check that the top changelog section's first line equals VERSION); red-proof and coverage items do not apply |
| 2026-11-17 | test line | this commit | MW133-D1: the last line of tests/test_mw060_docs.py::test_register_changelog_and_card_name_the_card now checks that the first line of the top CHANGELOG section equals the VERSION text, instead of the literal 0.2.7; no other test changed |
