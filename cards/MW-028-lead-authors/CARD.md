# MW-028: A lead authors its own proposed cards, and a root below the git top reads vcs git

| | |
|---|---|
| **Appetite** | 2 hours — from 2026-11-11 |
| **Status** | proposed |
| **Created / updated** | 2026-11-11 / 2026-11-11 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | none new: the ruling «a lead authors its own proposed cards» and the standing rule «a gap found in real work gets its own fix card at once» carry it |
| **Canon** | none for the lead's paths and the install's vcs word: the basis is the gap found in the owner's first real task |
| **Paths** | `engine/leads.py`, `engine/cardtool.py`, `engine/gate_lock.py`, `engine/gate_lead.py`, `engine/mkway.py`, `engine/install.py`, `engine/startline.py`, `engine/KEYS.md`, `README.md`, `CHANGELOG.md`, `VERSION`, `tests/`, `cards/REGISTER.md`, `cards/MW-028-lead-authors/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository.

## 1. Goal

A lead can author an order. In the first real task a lead could write no card at all: the subtask gate refused its
`ORDER.md` (`no-open-card`), the lead gate refused its `card take` and every write to `CARD.md`, so Goal, Acceptance,
Appetite and Paths had no writer before `card open`. Now a registered lead writes `CARD.md` and `ORDER.md` of a card
whose Ordered by is its own session id while the card is `proposed`, holding nothing; after `card open` the card file
is sealed to it again and `ORDER.md` stays its own; with `cards.approver: orderer` the lead also opens the proposed
cards it ordered (an owner-ordered card keeps every move owner-only). The same install also wrote `vcs: none` for a
task root that lies inside a git work tree below its top; `detect_vcs` now answers git for any folder inside a work
tree, and the start block gives one reason when the vcs is none.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | a lead writes CARD.md and ORDER.md of its own proposed card | lead gate `lead-no-edit` on CARD.md | both gates allow both files | tests/test_mw028_lead_authors.py::test_a_lead_writes_card_and_order_of_its_proposed_card |
| E2 | the same CARD.md after the card is open | refused | refused `lead-no-edit`; ORDER.md still allowed in both gates | tests/test_mw028_lead_authors.py::test_after_open_card_is_sealed_to_the_lead_and_order_stays_its_own |
| E3 | CARD.md and ORDER.md of a proposed card another lead ordered | refused | refused (`lead-no-edit`; the subtask gate `no-open-card`) | tests/test_mw028_lead_authors.py::test_another_leads_proposed_card_stays_refused |
| E4 | a builder with no card, on the order file of a proposed card | `no-open-card` | `no-open-card`, the lead gate does not judge it | tests/test_mw028_lead_authors.py::test_a_builder_on_a_proposed_card_is_unchanged |
| E5 | a lead opens its own proposed card | owner-only | opened with `orderer` (Paths recorded); `owner-only-command` with `owner-only` | tests/test_mw028_lead_authors.py::test_a_lead_opens_its_own_card_with_approver_orderer |
| E6 | a lead opens an owner-ordered card, another lead's card; a builder opens its own | owner-only | refused `owner-only-command`, status unchanged | tests/test_mw028_lead_authors.py::test_a_lead_never_opens_an_owner_ordered_card_or_another_leads |
| E7 | `detect_vcs` of an untracked folder two levels below the top of a sparse linked worktree | none | git; a folder in no work tree stays none | tests/test_mw028_lead_authors.py::test_detect_vcs_answers_git_for_a_root_below_the_top_of_a_sparse_linked_worktree |
| E8 | the starter profile a first install writes at that root | `vcs` none | `vcs` git, the bundle `.gitignore` written | tests/test_mw028_lead_authors.py::test_a_first_install_below_the_top_writes_vcs_git_and_the_ignore_file |
| E9 | the start block's vcs line when the profile says none | the bare words | one line with the reason: inside a git work tree, or in none | tests/test_mw028_lead_authors.py::test_the_start_block_says_in_one_line_why_vcs_is_none |
| E10 | register, changelog, version | no word | register row, a line under the release that names the card, VERSION: see VERSION | tests/test_mw028_lead_authors.py::test_register_changelog_version_and_card_name_the_card |

## 8. Log

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-11 | red: rows E1 to E10 | 895481a | 6 red (E1, E5, E7, E8, E9, E10), 4 green (E2, E3, E4, E6 pin behaviour that stays) |
| 2026-11-11 | green, lead: `leads.writable` adds `<folder>/CARD.md` while the sealed register says `proposed` and the seal holds; `cardtool.open_problem` and `move(opener=...)`; the lock gate leaves an `open` permit only for a registered lead's open of a proposed card it ordered, with `cards.approver: orderer`; the CLI reads it, records the Paths, writes a Log row and a ledger row. The subtask gate already lets any session write a CARD.md (S3/S4), so the lead gate is what seals CARD.md after open | the commit that carries this line | E1 to E6 green. A lead opens only a `proposed` card (a reopen stays the owner's); the open by a session that is no registered lead, or of another's card, is `owner-only-command` |
| 2026-11-11 | cause of the vcs gap: `install.detect_vcs` answered git only when `rev-parse --show-toplevel` equalled the root itself, so any root below the top (the shape MW-024 made normal: linked worktree, sparse cone, folder made by mkdir) read `none`; git answered from the subfolder correctly. It was not a first-install-before-checkout, sparse-cone or untracked-folder effect. Fix: git when the root is inside the top. The start block says why when the vcs is none (inside a work tree: set `vcs` to `git`, then `mkway install`; or in no work tree) | the commit that carries this line | E7 to E9 green. A profile already written with `none` is not rewritten: the owner sets `vcs` to `git` by hand |
| 2026-11-11 | the suite's temp folder lies inside this repository, so with the fix every scratch folder read as a work tree: `tests/conftest.py` sets `GIT_CEILING_DIRECTORIES` to the temp folder for every test (scratch repositories made by tests still work) | the commit that carries this line | the install, start block and root tests stay green |
| 2026-11-11 | row changed: MW-017 test `test_a_lead_edit_of_any_other_path_is_lead_no_edit` expected a lead's write to the CARD.md of its own proposed card to be refused; the ruling makes that wrong, so the test opens the card first and the refusal is asserted after the open. Version pins of MW-016, MW-017, MW-018, MW-022, MW-023, MW-024, MW-025 changed `0.2.2` to `0.2.5` (README patch-release rule); README lead section and `engine/KEYS.md` `cards.approver` state the new rule | the commit that carries this line | reading, to confirm |
| 2026-11-11 | open for the architect: the live refusal of the lead's ORDER.md (`no-open-card`) would also arise if the card's `Ordered by` cell stayed `owner` (a register with no such column, so the post step could not write it); not reproduced here | - | not established |
| 2026-11-11 | whole suite, `python -m pytest`, term scan included | the commit that carries this line | 846 passed in 663 s (836 on the base, 10 new); no term-scan exception added |
| 2026-11-12 | MW-040: row E10 named a release number or an old VERSION | the commit that carries this line | the row says «see VERSION» and «the release that names the card»; its test reads the VERSION file and finds the card's changelog line (`tests/_docs.py`), no release number is pinned |
