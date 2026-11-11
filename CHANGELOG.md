# Changelog

Each release lists its cards, one line each, with the id and the title of the register (`cards/REGISTER.md`). A test
keeps this file and the register in step.

## 0.2.7
- MW-027: Install: one step to a committed fence
- MW-033: The commit message names the card anywhere in the first line
- MW-034: The commit check reads what the commit takes; one builder per root
- MW-035: Install finishes its own commit in one correct step

## 0.2.6
- MW-026: State never outside the mkway root
- MW-029: The copy guard is fast
- MW-030: Live install test is the release gate: no version is tagged before it passes
- MW-031: git built-in list current, check warns only on the risky side
- MW-032: Reinstall never fails half-way, check leaves nothing in the copy

## 0.2.5
- MW-028: A lead authors its own proposed cards, and a root below the git top reads vcs git

## 0.2.2
- MW-025: The install check runs only tests that fit a copy

## 0.2.1
- MW-024: Commands find the task root below the git top

## 0.2.0
- MW-017: Lead role
- MW-018: Messaging order
- MW-019: Outbox check: a text leaves only after a fresh reader
- MW-020: Deliverables: built from tested code, compared with a named base
- MW-021: Rule cards paired with tests
- MW-022: Locks reach every worktree
- MW-023: One tree key for green test rows

## 0.1.0
- MW-001: Engine skeleton
- MW-002: mkway v1 part 1, the core
- MW-003: mkway v1 part 2, the minimum gates
- MW-004: Agent records, a saved result and a time for every helper agent
- MW-005: Tests before a commit
- MW-006: Commit checks
- MW-007: Questions to the owner go one way
- MW-008: Decision ledger, search before asking
- MW-009: Deletes: explicit, backed up, logged
- MW-010: Owner hold
- MW-011: Card close by the one who ordered it
- MW-012: Form gates: watch mode and trip
- MW-013: The check tests run a fixture test set
- MW-014: Asks that do not stop the work
- MW-015: A session never writes the owner's words in the ledger
- MW-016: Version in code, tag in git
