# Changelog

Each release lists its cards, one line each, with the id and the title of the register (`cards/REGISTER.md`). A test
keeps this file and the register in step.

## 0.4.0
- MW-140: A file outside the task root is outside: git's names are read against the git top
- MW-139: the refusal for a red the take record does not hold names the route that works: release the card, take it again
- MW-135: the commit gate's refusal of a red test that exists at HEAD and was green there says so and names the two ways out, not the red-first commit
- MW-137: the lead that ordered an open card re-records its Paths: mkway card paths --add and --remove, the same checks as the first open, never the holder
- MW-136: the refusal text of card-paths-changed names the routes that work today: restore the recorded Paths, or a new card opened by its orderer
- MW-134: a recorded red id is retired by a valid case_map line of its card, in a tests-only commit, under a decision of the ledger that another session wrote
- MW-141: a test's row ages are measured when the test runs, not when its module is imported
- MW-144: release 0.4.0: raise VERSION, list the cards merged after 0.3.0

## 0.3.0
- MW-033: The commit message names the card anywhere in the first line
- MW-034: The commit check reads what the commit takes; one builder per root
- MW-035: Install finishes its own commit in one correct step
- MW-036: The install commit takes only what install writes
- MW-037: The whole suite runs well under the merge limit
- MW-043: A commit is judged by what git will put in it
- MW-045: A crashed card holder never blocks the root
- MW-051: Install hashes the copy while writing it
- MW-041: The printed install line works from any folder; ignore cleanup is CRLF-safe
- MW-049: Every ledger row names who really made the move
- MW-050: Ledger add can replace an earlier row
- MW-038: A test that replays the owner's real task setup
- MW-039: Every gate's refusal is proven through the real hook command
- MW-040: Card rows and tests stay in step
- MW-048: The owner's words can be recorded verbatim
- MW-053: The orderer commits the card folder it ordered
- MW-055: A session whose writes are refused can still report
- MW-054: A builder in a git worktree copy can take and work its card
- MW-056: A commit is refused only for new red
- MW-057: The commit test run sees what the working tree sees, and says why it failed
- MW-058: A message-only amend takes no files
- MW-060: commit_tests tests the tree git will commit
- MW-059: The topology refusal names the new-session route
- MW-061: A command with a newline inside quotes is read whole
- MW-068: A test node named by a card has a blind verdict before close
- MW-062: A test absent at HEAD is judged by its owner card
- MW-052: commit_files decides in a pure core
- MW-063: The lock gate decides from facts, and its tests are fast and true
- MW-064: The delete gate decides on facts and its tests run by layer
- MW-065: The ask family decides in a pure core
- MW-066: The session gates decide in a pure core
- MW-067: Install decisions are a pure core, and the install tests are fast and true
- MW-069: A test file that fails collection at HEAD is red at HEAD for its ids
- MW-070: card close runs the named test nodes on HEAD's tree
- MW-071: The blind verdict checker is a read-only reader, never critic
- MW-074: Small tests are hermetic and run in a shuffled order
- MW-077: The remaining wall-clock limits are perf checks
- MW-084: A term hit in a closed card's text
- MW-082: Append-only files merge without conflicts
- MW-083: The suite runs in parallel
- MW-075: A Stop warning never wakes the session again
- MW-078: An inbox waiter wakes an idle session
- MW-080: A verdict row is written only by the engine command
- MW-086: A docs test checks that its changelog line is present, not that it is last
- MW-079: Test files may share a name across tests/shell and the flat folders
- MW-087: The no-disk guard of the core tests lets the coverage tracer's own file calls through
- MW-085: Shared test templates and the runtime guard
- MW-076: A session that caused an inbox write to another session also pings it
- MW-073: A test added or changed in a commit is judged for its shape
- MW-072: red proof: a new test fails before the code and passes after
- MW-088: The test shape rule S4 accepts a one-line Pins: docstring
- MW-089: One reader for case_map.md: a pure parser in core_red that every case_map test uses. VERSION unchanged.
- MW-090: The red proof judges the card's case_map lines under a named decision.
- MW-096: Test rewrite group 4: shape rules S1-S7, hermetic, parallel-safe.
- MW-095: Test rewrite group 3: shape rules S1-S7, hermetic, parallel-safe
- MW-098: Test rewrite group 6: shape rules S1-S7, hermetic, parallel-safe.
- MW-094: Test rewrite group 2: shape rules S1-S7, hermetic, parallel-safe.
- MW-097: Test rewrite group 5: shape rules S1-S7, hermetic, parallel-safe.
- MW-093: Test rewrite group 1: shape rules S1-S7, hermetic, parallel-safe.
- MW-099: Tests that start a nested pytest run in their own xdist group: hypothesis measured and disproved.
- MW-100: A weak or wrong verdict is answered by a re-cut, never by an acceptance
- MW-101: A verdict stays fresh while its node's meaning is unchanged, read from git
- MW-102: The orderer commits the verdict file of a card it ordered, under the close's row proof
- MW-103: A registered lead's write outside the repository is lead-no-edit, except a narrow default list of the harness's own state folders
- MW-104: `mkway upgrade`: the owner's command installs a proven-green engine release into a granted task root, with one ledger row and one commit (a Python rewrite of mkup 1.0.0)
- MW-105: the lock gate guards the upgrade folder outside the repository
- MW-106: the concept base: CONCEPT.md, the reason table and its four tests
- MW-110: the send tool: a session sends with one engine call and no one-use permit
- MW-113: Way-out tests for the owner-ask lane and the reader's inputs (K7 and K3)
- MW-109: fail-closed wiring: a refusal that names the hook, the error and the repair, a record the engine cannot write refuses with its path, and a way-out test for each K1 and K8 refusal
- MW-114: the node id readers take the whole id, also when it holds a space; cached listing and failing-run rows carry a `reader` key, and a row of another reader version is not reused
- MW-116: The reader of a test is held to its two inputs: an allowlist hook, one record row per call, no verdict without it
- MW-107: one owner per file kind: the owner table, a write outside the root refused for every session; the profile key `leads.outside_writable` is now `paths.outside_writable`, `mkway upgrade` renames it, and the old key is an alias kept until the next major; removed with it
- MW-127: the merged tests obey the engine test rules; first step: the pinned-sha test runs only in the engine repository
- MW-117: a verdict is allowed any time after the red commit, held or not, until the card closes; a test or an Acceptance row edited after it makes it stale at close
- MW-112: reminders once, trial end dates, the board, the cost record, the instruction lines
- MW-115: the ask lane and search refuse from the first install: class integrity, no watch at install, no trip; the gates owner_ask, outbox_check.pre and search are class integrity, so a first install writes no watch marker for them and they never trip; an old marker is ignored and the start line names the change once; a crashing Stop gate allows with a start-line notice (named limit K8)
- MW-119: ask answered runs only in the lead, and its record is the lead's
- MW-108: this-commit judgement with inherited red: the commit gate refuses only the new red of the commit, an old red is shown with its owner, a red at take is the card inherited red; `card take` writes `inherited_red.jsonl` from the kept rows and never runs the suite, `card release-red <test id> --to <card id>` is the orderer's, the commit row gets the key `old_red`
- MW-128: a refusal that ends a turn is delivered to the orderer by the Stop hook itself: an inbox record and one block, no model in the loop
- MW-130: verdict add finds a card's red-proof row in the whole history of HEAD, however many commits followed it; the row records its git tree
- MW-129: card records have one home per task, the shared folder: a record written in any checkout is read by every gate in every checkout
- MW-131: the commit gate finds a card's own red record in the whole history of HEAD, however many unrelated commits followed the red commit
- MW-132: a builder holding an open card never ends a turn silently: at its first stop the engine writes its last message into the orderer's inbox and blocks once, asking only for the ping line
- MW-133: release 0.3.0: clean card paths, raise VERSION

## 0.2.7
- MW-027: Install: one step to a committed fence

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
