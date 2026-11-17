# The concept

This page is the one every session reads first. Every order names its place here: «Concept: line N, kind Kx / record Rx /
exit». The table of every refusal reason is `engine/concept.py`; four tests in `tests/test_concept.py` fail when the engine
and this page drift apart.

## a. The yardstick

The process is straight and as simple as possible; it helps the work on tasks; it is a strong helper, never a guard dog.

## b. The eight lines

1. Only eight hard stops: protected files; a new test must fail first and tests never get weaker; an independent reader
   before a close and before a customer text leaves; no confidential data in git; full green tests at merge and install;
   one owner per file kind; no ask to the owner without its sources; every gate fails closed. Everything else is a tool
   that does it right, or a written rule.
2. A gate judges only what this action changes. Old problems are shown with their owner and never block. The merge still
   needs all green.
3. Every refusal names a way out that works, and a test proves it. A refusal with no way out is a bug of the guard, fixed
   in the engine, never by a workaround.
4. A trial gate has an end date, then it is enforced or removed. Reminders fire once.
5. A new gate never breaks a card already in progress.
6. Wrong content with green gates is not a guard problem. It gets its own concept after the current task's work. Today
   the card form carries it.
7. After every task, one scorecard with four numbers: real catches, false blocks, hours lost to the process per card, asks
   to the owner per week. A gate with more false blocks than catches is changed or removed.
8. Before any concept change reaches the owner, a fresh reader checks it against the lessons of the earlier task.

## c. The eight hard-gate kinds

A kind row in `engine/concept.py` means the hook keeps refusing: it is one of the eight hard stops. An exit row means the
hook stops refusing when the named card lands: `tool` means the tool makes the error impossible or harmless;
`instruction` means one line in a role file replaces it; `record` means a log line once per event; `remove` means it is
deleted. A check that stays in the hook and gets a tool as its way out is a kind, with the tool as its way-out test.

- **K1** protected targets, with reach: hooks, settings, profile, engine, the upgrade folder, deletes outside the task, writes outside the task and
  the owner's lever are closed. Reach rule: a shell shape the gate cannot read is judged by what it names; if it names a
  protected target or carries a gated action (a commit, a state-changing engine call) it fails closed and the refusal
  names the tool that does it in plain form; a shape that names no target and carries no gated action passes.
- **K2** red before green, never weaker, with provenance. Shape rule: the expected side of an assert is a literal or a
  parametrize value, never a call into the module under test, and a test's docstring names what it catches. A test
  already red at a card's take is that card's inherited red.
- **K3** blind verdict before close, with its witness: the verdict is written by a session that neither holds the card nor
  committed the test, and the engine checks the session ids. Outbox text: the independent reader judges tests before a
  close and outbox texts before they leave; a verdict that cannot fail is no verdict;
  the reader reads the test file and the Acceptance rows of the named nodes only: a hook of its own agent file refuses every
  other path and tool, and no verdict counts for a run the hook did not record.
- **K4** confidential content: the term scan on commits, data paths from the profile (a file under a data path is refused
  at commit, `git add -f` included), and the size limit.
- **K5** full green at merge and install, on the committed tree: every test run of the engine reads a committed or staged
  tree, never the working folder.
- **K6** the card rule with one owner table: one open card per session, no Paths overlap between open cards, one owner
  per file kind.
- **K7** the owner-ask lane: no ask reaches the owner without its sources file, and no `Request:` line without that file.
- **K8** fail-closed wiring: every hard gate's hook blocks on failure and has a timeout that refuses; the install test
  asserts both and that every hook is registered; the start line names every gate that is off or in watch; proof is a
  record, never a self-reported row.
  Named limit (K8): (i) onFailure has no effect on Stop hooks, "The field has no effect on these hooks: `Stop`, ..."
  (hooks.md:983), so a crashing Stop hook cannot block; (ii) "after stop hooks have continued the turn eight times in a
  row, Claude Code overrides the next block and ends the turn. The count of consecutive continuations resets each time
  Claude calls a tool" (hooks.md:2842); the engine does not set `CLAUDE_CODE_STOP_HOOK_BLOCK_CAP`. The crash path of a
  Stop gate allows, with a calls-log error row and a start-line notice.

## d. The four records

- **R1** agent records: start, end, elapsed and the result in full, per agent.
- **R2** the ledger with an author: every row carries who wrote it; the owner's words enter as a row with the quote.
- **R3** the card board: every old red, every uncommitted own file and every file of an ended session, shown with its owner.
- **R4** the cost record: seconds per test run, hook time per call and refusals per reason, per task.

## e. The content principles

Marked «the task-content concept, later»: they are stated so they are not lost, and are built after the current task.

1. The expectation is fixed before the output is seen, by a party other than the one who implements.
2. A test pins the requirement's words, never hand-set facts.
3. Nothing reaches the owner about the subject of a task except from a card's file.

## f. The next cards

Card 1 is the base: this page, the table and its four tests. The cards after it, each with the line and the kind it
implements. A tool card carries line 1 (the tool is the «everything else») and line 3 (the tool is the way out):

2. One owner per file kind: line 1, kind K6.
3. This-commit judgement with inherited red: line 2, line 5; kind K2.
4. Fail-closed wiring and the start line: line 1, kind K8.
5. The send tool, messages and pings: line 1, line 3; exit `tool`; record R1.
6. The commit tool, command form and commit message: line 1, line 3; exit `tool`.
7. Reminders once, trial end dates, the board, the cost record, and the instruction lines in the role files the engine
   ships: lines 4 and 7, records R3 and R4, the exits `record` and `instruction`.
8. Audits of the ask lane and the reader's inputs: line 1, kinds K7 and K3.
