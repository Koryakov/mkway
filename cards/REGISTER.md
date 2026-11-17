# Card register

| Id | Title | Status | Folder |
|---|---|---|---|
| MW-001 | Engine skeleton | closed | `cards/MW-001-engine-skeleton` |
| MW-002 | mkway v1 part 1, the core | closed | `cards/MW-002-core` |
| MW-003 | mkway v1 part 2, the minimum gates | open | `cards/MW-003-gates-min` |
| MW-004 | Agent records, a saved result and a time for every helper agent | open | `cards/MW-004-agent-record` |
| MW-005 | Tests before a commit | proposed | `cards/MW-005-tests-before-commit` |
| MW-006 | Commit checks | proposed | `cards/MW-006-commit-checks` |
| MW-007 | Questions to the owner go one way | proposed | `cards/MW-007-owner-ask` |
| MW-008 | Decision ledger, search before asking | proposed | `cards/MW-008-decision-ledger` |
| MW-009 | Deletes: explicit, backed up, logged | proposed | `cards/MW-009-deletes` |
| MW-010 | Owner hold | proposed | `cards/MW-010-owner-hold` |
| MW-011 | Card close by the one who ordered it | proposed | `cards/MW-011-card-close` |
| MW-012 | Form gates: watch mode and trip | proposed | `cards/MW-012-watch-mode` |
| MW-013 | The check tests run a fixture test set | proposed | `cards/MW-013-check-tests-fixture` |
| MW-014 | Asks that do not stop the work | proposed | `cards/MW-014-asks` |
| MW-015 | A session never writes the owner's words in the ledger | proposed | `cards/MW-015-ledger-by` |
| MW-016 | Version in code, tag in git | proposed | `cards/MW-016-version` |
| MW-017 | Lead role | proposed | `cards/MW-017-lead-role` |
| MW-018 | Messaging order | proposed | `cards/MW-018-messaging-order` |
| MW-019 | Outbox check: a text leaves only after a fresh reader | proposed | `cards/MW-019-outbox-check` |
| MW-020 | Deliverables: built from tested code, compared with a named base | proposed | `cards/MW-020-deliverables` |
| MW-021 | Rule cards paired with tests | proposed | `cards/MW-021-rule-tests` |
| MW-022 | Locks reach every worktree | proposed | `cards/MW-022-locks-shared` |
| MW-023 | One tree key for green test rows | proposed | `cards/MW-023-green-tree-key` |
| MW-024 | Commands find the task root below the git top | proposed | `cards/MW-024-task-root-below-top` |
| MW-025 | The install check runs only tests that fit a copy | proposed | `cards/MW-025-copy-check` |
| MW-026 | State never outside the mkway root | proposed | `cards/MW-026-state-in-root` |
| MW-028 | A lead authors its own proposed cards, and a root below the git top reads vcs git | proposed | `cards/MW-028-lead-authors` |
| MW-029 | The copy guard is fast | proposed | `cards/MW-029-fast-copy-guard` |
| MW-030 | Live install test is the release gate: no version is tagged before it passes | proposed | `cards/MW-030-live-install-test` |
| MW-031 | git built-in list current, check warns only on the risky side | proposed | `cards/MW-031-git-builtins-current` |
| MW-032 | Reinstall never fails half-way, check leaves nothing in the copy | proposed | `cards/MW-032-reinstall-safe` |
| MW-027 | Install: one step to a committed fence | proposed | `cards/MW-027-install-commit` |
| MW-033 | The commit message names the card anywhere in the first line | proposed | `cards/MW-033-commit-msg-card-anywhere` |
| MW-034 | The commit check reads what the commit takes; one builder per root | proposed | `cards/MW-034-staged-paths` |
| MW-035 | Install finishes its own commit in one correct step | proposed | `cards/MW-035-install-one-line` |
| MW-036 | The install commit takes only what install writes | proposed | `cards/MW-036-install-own-paths` |
| MW-037 | The whole suite runs well under the merge limit | proposed | `cards/MW-037-suite-speed` |
| MW-043 | A commit is judged by what git will put in it | proposed | `cards/MW-043-commit-takes` |
| MW-045 | A crashed card holder never blocks the root | proposed | `cards/MW-045-stale-holder` |
| MW-041 | The printed install line works from any folder; ignore cleanup is CRLF-safe | proposed | `cards/MW-041-install-line-root` |
| MW-038 | A test that replays the owner's real task setup | proposed | `cards/MW-038-real-shape-test` |
| MW-039 | Every gate's refusal is proven through the real hook command | proposed | `cards/MW-039-real-hook-denies` |
| MW-049 | Every ledger row names who really made the move | proposed | `cards/MW-049-ledger-by-moves` |
| MW-048 | The owner's words can be recorded verbatim | proposed | `cards/MW-048-quoted-args` |
| MW-051 | Install hashes the copy while writing it | proposed | `cards/MW-051-copy-hash-once` |
| MW-050 | Ledger add can replace an earlier row | proposed | `cards/MW-050-ledger-replaces` |
| MW-040 | Card rows and tests stay in step | proposed | `cards/MW-040-meta-cards-tests` |
| MW-053 | The orderer commits the card folder it ordered | proposed | `cards/MW-053-orderer-commits-card` |
| MW-055 | A session whose writes are refused can still report | proposed | `cards/MW-055-report-without-write` |
| MW-054 | A builder in a git worktree copy can take and work its card | proposed | `cards/MW-054-copy-works` |
| MW-056 | A commit is refused only for new red | proposed | `cards/MW-056-new-red-only` |
| MW-057 | The commit test run sees what the working tree sees, and says why it failed | proposed | `cards/MW-057-export-sees-tree` |
| MW-058 | A message-only amend takes no files | proposed | `cards/MW-058-amend-only-message` |
| MW-060 | commit_tests tests the tree git will commit | proposed | `cards/MW-060-taken-tree` |
| MW-059 | The topology refusal names the new-session route | proposed | `cards/MW-059-topology-route` |
| MW-061 | A command with a newline inside quotes is read whole | proposed | `cards/MW-061-quoted-newline` |
| MW-062 | A test absent at HEAD is judged by its owner card | proposed | `cards/MW-062-absent-at-head` |
| MW-052 | commit_files decides in a pure core | proposed | `cards/MW-052-commit-core` |
| MW-063 | The lock gate decides from facts, and its tests are fast and true | proposed | `cards/MW-063-lock-core` |
| MW-064 | The delete gate decides on facts and its tests run by layer | proposed | `cards/MW-064-delete-core` |
| MW-065 | The ask family decides in a pure core | proposed | `cards/MW-065-ask-core` |
| MW-066 | The session gates decide in a pure core | proposed | `cards/MW-066-session-core` |
| MW-067 | Install decisions are a pure core, and the install tests are fast and true | proposed | `cards/MW-067-install-core` |
| MW-069 | A test file that fails collection at HEAD is red at HEAD for its ids | proposed | `cards/MW-069-collection-red-at-head` |
| MW-070 | card close runs the named test nodes on HEAD's tree | proposed | `cards/MW-070-close-on-head-tree` |
| MW-068 | A test node named by a card has a blind verdict before close | proposed | `cards/MW-068-test-verdicts` |
| MW-071 | The blind verdict checker is a read-only reader, never critic | proposed | `cards/MW-071-read-only-checker` |
| MW-074 | Small tests are hermetic and run in a shuffled order | proposed | `cards/MW-074-hermetic-core` |
| MW-077 | The remaining wall-clock limits are perf checks | proposed | `cards/MW-077-perf-rest` |
| MW-084 | A term hit in a closed card's text | proposed | `cards/MW-084-term-line` |
| MW-082 | Append-only files merge without conflicts | proposed | `cards/MW-082-union-merge` |
| MW-083 | The suite runs in parallel | proposed | `cards/MW-083-parallel-suite` |
| MW-075 | A Stop warning never wakes the session again | proposed | `cards/MW-075-stop-warn-never-wakes` |
| MW-078 | An inbox waiter wakes an idle session | waiting | `cards/MW-078-inbox-waiter` |
| MW-080 | A verdict row is written only by the engine command | proposed | `cards/MW-080-verdict-add` |
| MW-086 | A docs test checks that its changelog line is present, not that it is last | proposed | `cards/MW-086-docs-presence` |
| MW-079 | Test files may share a name across tests/shell and the flat folders | proposed | `cards/MW-079-shell-package` |
| MW-087 | The no-disk guard of the core tests lets the coverage tracer's own file calls through | proposed | `cards/MW-087-no-io-coverage` |
| MW-085 | Shared test templates and the runtime guard | proposed | `cards/MW-085-test-templates` |
| MW-076 | A session that caused an inbox write to another session also pings it | proposed | `cards/MW-076-ping-lead` |
| MW-073 | A test added or changed in a commit is judged for its shape | proposed | `cards/MW-073-test-shape` |
| MW-072 | red proof: a new test fails before the code and passes after | proposed | `cards/MW-072-red-proof` |
| MW-088 | The test shape rule S4 accepts a one-line Pins: docstring | proposed | `cards/MW-088-s4-pins` |
| MW-089 | One reader for case_map.md: a pure parser in core_red that every case_map test uses | proposed | `cards/MW-089-case-map-parser` |
| MW-090 | The red proof judges the card's case_map lines under a named decision | proposed | `cards/MW-090-case-map-gate` |
| MW-095 | Test rewrite group 3: shape rules S1-S7, hermetic, parallel-safe | closed | `cards/MW-095-rewrite-g3` |
| MW-098 | Test rewrite group 6: shape rules S1-S7, hermetic, parallel-safe | closed | `cards/MW-098-rewrite-g6` |
| MW-094 | Test rewrite group 2: shape rules S1-S7, hermetic, parallel-safe | closed | `cards/MW-094-rewrite-g2` |
| MW-097 | Test rewrite group 5: shape rules S1-S7, hermetic, parallel-safe | closed | `cards/MW-097-rewrite-g5` |
| MW-093 | Test rewrite group 1: shape rules S1-S7, hermetic, parallel-safe | closed | `cards/MW-093-rewrite-g1` |
| MW-096 | Test rewrite group 4: shape rules S1-S7, hermetic, parallel-safe | closed | `cards/MW-096-rewrite-g4` |
| MW-099 | Tests that start a nested pytest run in their own xdist group: hypothesis measured and disproved | closed | `cards/MW-099-nested-lane` |
| MW-100 | A weak or wrong verdict is answered by a re-cut, never by an acceptance | proposed | `cards/MW-100-verdict-recut` |
| MW-101 | A verdict stays fresh while its node's meaning is unchanged, read from git | proposed | `cards/MW-101-node-fresh` |
| MW-102 | The orderer commits the verdict file of a card it ordered, under the close's row proof | proposed | `cards/MW-102-verdict-commit` |
| MW-103 | A registered lead's write outside the repository is lead-no-edit, except a narrow default list of the harness's own state folders | proposed | `cards/MW-103-lead-outside` |
| MW-104 | `mkway upgrade`: the owner's command installs a proven-green engine release into a granted task root, with one ledger row and one commit (a Python rewrite of mkup 1.0.0) | proposed | `cards/MW-104-upgrade` |
| MW-105 | the lock gate guards the upgrade folder outside the repository | proposed | `cards/MW-105-upgrade-lock` |
| MW-106 | the concept base: CONCEPT.md, the reason table and its four tests | proposed | `cards/MW-106-concept-base` |
| MW-110 | the send tool: a session sends with one engine call and no one-use permit | proposed | `cards/MW-110-send-tool` |
| MW-113 | Way-out tests for the owner-ask lane and the reader's inputs (K7 and K3) | proposed | `cards/MW-113-way-out-k7-k3` |
| MW-109 | fail-closed wiring: a refusal that names the hook, the error and the repair, a record the engine cannot write refuses with its path, and a way-out test for each K1 and K8 refusal | proposed | `cards/MW-109-fail-closed` |
| MW-114 | the node id readers take the whole id, also when it holds a space | proposed | `cards/MW-114-nodeid-parser` |
| MW-107 | one owner per file kind: the owner table, a write outside the root refused for every session | proposed | `cards/MW-107-owner-table` |
| MW-127 | the merged tests obey the engine test rules; first step: the pinned-sha test runs only in the engine repository | proposed | `cards/MW-127-test-conformance` |
| MW-116 | The reader of a test is held to its two inputs: an allowlist hook, one record row per call, no verdict without it | proposed | `cards/MW-116-reader-allowlist` |
| MW-117 | a verdict is allowed any time after the red commit, held or not, until the card closes; a test or an Acceptance row edited after it makes it stale at close | proposed | `cards/MW-117-verdict-window` |
| MW-112 | reminders once, trial end dates, the board, the cost record, the instruction lines | proposed | `cards/MW-112-reminders-board` |
| MW-115 | the ask lane and search refuse from the first install: class integrity, no watch at install, no trip | proposed | `cards/MW-115-ask-lane-integrity` |
| MW-119 | ask answered runs only in the lead, and its record is the lead's | proposed | `cards/MW-119-answer-intake` |
| MW-108 | this-commit judgement with inherited red: the commit gate refuses only the new red of the commit, an old red is shown with its owner, a red at take is the card inherited red | proposed | `cards/MW-108-this-commit` |
| MW-128 | a refusal that ends a turn is delivered to the orderer by the Stop hook itself: an inbox record and one block, no model in the loop | proposed | `cards/MW-128-refusal-delivery` |
| MW-130 | verdict add finds a card's red-proof row in the whole history of HEAD, however many commits followed it; the row records its git tree | proposed | `cards/MW-130-tree-search-bound` |
| MW-129 | card records have one home per task, the shared folder: a record written in any checkout is read by every gate in every checkout | proposed | `cards/MW-129-shared-records` |
| MW-131 | the commit gate finds a card's own red record in the whole history of HEAD, however many unrelated commits followed the red commit | proposed | `cards/MW-131-own-record-search` |
| MW-132 | a builder holding an open card never ends a turn silently: at its first stop the engine writes its last message into the orderer's inbox and blocks once, asking only for the ping line | proposed | `cards/MW-132-no-silent-turn-end` |
| MW-133 | release 0.3.0: clean card paths, raise VERSION | proposed | `cards/MW-133-release-030` |
| MW-139 | the refusal for a red the take record does not hold names the route that works: release the card, take it again | proposed | `cards/MW-139-take-wayout-text` |
| MW-135 | the commit gate's refusal of a red test that exists at HEAD and was green there says so and names the two ways out, not the red-first commit | proposed | `cards/MW-135-red-wayout-text` |
| MW-136 | the refusal text of card-paths-changed names the routes that work today: restore the recorded Paths, or a new card opened by its orderer | proposed | `cards/MW-136-paths-wayout-text` |
| MW-134 | a recorded red id is retired by a valid case_map line of its card, in a tests-only commit, under a decision of the ledger that another session wrote | proposed | `cards/MW-134-retire-red-id` |
