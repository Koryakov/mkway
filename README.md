# Process engine

A portable process for a code branch: the gates (hooks) that guard how work is carried and committed, the card
register that carries the work, and the checks that keep task data out of the engine. One engine serves many branches;
each branch tunes it through its own profile.

## Three layers
1. **Engine** (this repository). The hook code, `engine/manifest.json` (per hook: event, matcher, timeout,
   onFailure, mode), `engine/defaults.json` (engine-default values) and `engine/profile.schema.json`. The same for
   every branch.
2. **Branch profile** (one tracked file per branch). Where the branch keeps its bundle, cards, state folder and ids,
   which gates are on, and the branch's own product checks. It is checked against the schema
   (`engine/schema_check.py`) and overrides the engine defaults.
3. **Machine** (untracked, per machine). The generated hook registration and any per-machine values. It is made from
   the tracked profile; a drift between the two is reported.

## State
Card MW-002 (the core): the gate interface, the dispatcher with its logs, the root and profile reader, the cards
tool, install and check, the start line and the drift check. Card MW-003 (the minimum gates): the lock gate, the
subtask gate and the `post` records are `on`; the other manifest entries are `planned` or `off-today`, with no code.

## Moving cards
A card's status lives in the sealed register (`proposed`, `open`, `waiting`, `waiting-owner`, `closed`); a session's
`card new` writes `proposed` and `card take <id>` makes it the session's card. There are three ways to move cards:
1. **The owner's terminal** (the default, `cards.owner_moves: ["open","closed"]`). The owner runs
   `python mkway/engine/mkway.py card open <id>` and `card close <id>` in their own terminal, where no hook runs; the
   lock gate refuses these commands to a session. A session pauses its own card (`card set <id> waiting`) and lifts
   its own pause; a pause the owner sets is `waiting-owner`, which only the owner lifts.
2. **Light mode** (`cards.owner_moves: []`). A session may make the owner's moves itself; the close rule still holds
   (every Acceptance row names a test that exists).
3. **The session that ordered the card closes it** (`cards.approver: orderer`; see «Closing cards»). **Another
   session approves** (`cards.approver: other-session`) is later, card MW-008.

## Closing cards
Who may close a card is the profile's `cards.approver`. The default is `owner-only`: only the owner's terminal closes
a card, as in «Moving cards», and nothing below applies. With `orderer`, a card also closes by the session that
ordered it, so the owner's attention is not the bottleneck.

**Who ordered a card.** The register's sixth column `Ordered by` (the sixth name of `register.columns`, default
`Ordered by`) holds a session id, or `owner`. It is inside the register's seal. `card new` run in a session writes
the session id the hook input gives (the `post` group writes it after the command proves itself); run in the owner's
terminal it writes `owner`. A register without the column reads every card as `owner` and is not migrated by a write;
the owner adds the column with `card resync --add-ordered-by` in their own terminal. A new register has the column
when the profile names six columns or has `cards.approver: orderer`.

**The close.** A session's `card close <id>` passes only when all of these hold: the closing session's id equals
`Ordered by`; it is not the holder (the session that took the card); the card is `open` or `waiting`; every
Acceptance row's test passes now (the named node ids are run when the command runs; a missing test is a failure; a
`checked by reading` row runs nothing). The result is status `closed` and a Log row «closed by <session id>; ordered
by <value>»; the start block's card changes show it. A sub-agent is the `session_id` its hook input gives, beside its
`agent_id`. A card whose `Ordered by` is `owner` closes only in the owner's terminal, until the owner gives it.
`card set <id> closed` stays the owner's, with `orderer` as well.

**Refusals**, each naming the way out: `close-not-orderer` (another session, no session id in the hook input, or the
card is ordered by the owner), `close-by-holder` (the orderer is also the holder: a session never approves its own
work), `close-tests-failing` (a named test is red or missing). A card that is not `open` or `waiting` is `card-bad-move`.

**The owner's two commands.** `mkway give <card> <who>` sets `Ordered by`: `<card>` is a card id or a bare number
(the profile's card prefix is added); `<who>` is `owner` or a prefix of one session id seen in the state records; a
prefix that matches several ids is `give-ambiguous` and lists them, an unknown one is `give-unknown`, a register
without the column is `give-no-column`. `mkway sessions` is the owner's read-only view: every session id seen in the
state records (shell records, agents, searches), when it was last seen, the card it holds and the cards it ordered.
The engine knows ids, never chat names; a record with no session id is counted as «not established».

## Method: red proof against code already in the tree
When a commit's tests must be shown red while the code that makes them green is already in the working tree, export
the index into the ignored test folder and run the suite there:
`git checkout-index -a -f --prefix=.pytest_tmp/redcheck/`, then `python -m pytest` inside it. It writes no
repository state (no ref, no index change, nothing tracked).

## Questions to the owner
Questions to the owner go one way: a session may ask the owner only after it has written down the sources it checked.
The gate `owner_ask` holds this in two places (two manifest entries, one profile switch `gates.owner_ask`):
1. **Edit gate.** Writing `<asks dir>/<name>_ask.md` needs `<name>_sources.md` beside it, with a line `kind: substance`,
   `kind: session` or `kind: lock`. Substance: for each name in `owner_ask.sources` (default `ledger`) a count line
   such as `review: N contradictions` and at least one quote line such as `> review: <verbatim>`, with the name
   written as the source; the name `ledger` has its own lines
   (see «Decisions: search before asking»). Session: `checked: ListAgents`.
   Lock: `checked: <lock state>`. Otherwise the write is refused (`ask-sources-missing`, `ask-sources-kind`,
   `ask-sources-lines`) and the text names the missing line. The subtask gate decides first: a branch whose cards do
   not cover its asks folder lists it in `paths.exempt`.
2. **Stop gate.** If the final reply has a line that starts with a marker of `owner_ask.markers` (default `Request:`),
   the session must have written an ask file since the last user message, and the file must exist; otherwise the
   reply is blocked (`ask-not-written`). With `stop_hook_active` it never blocks. To see the writes the gate reads the
   transcript file the hook input names (`transcript_path`); when it cannot be read, a marker line is still blocked.

The keys are `owner_ask.dir` (the asks folder; default `<bundle.root>/asks`), `owner_ask.markers` and
`owner_ask.sources`; each has a default and the engine holds no task name in the gate (`engine/KEYS.md`). A gate that
is off is named on the start block (`gates off:`). Method: a fresh reader checks an ask before it goes. C-24 = the owner
closes the commit lock while the owner questions a flaw.

## Decisions: search before asking
The rule: a session asks the owner only after it has searched the past decisions. What the owner has decided is
written down once, in the ledger, and found again by a search.
- **Ledger.** The file `<bundle.root>/ledger/ledger.md`: the heading `## Ledger` and one table, one row for each decision
  (id, date, card, topic, quote, by, source, asked, replaces, status, note). A row whose status is `superseded` or
  `withdrawn` is closed; any other row is in force. A session adds a row with
  `mkway ledger add --card <id> --topic <text> --quote <verbatim> --source <text>` (optional `--status <text>`): it
  writes today's date and the next id (the form of `ids.decision_row`, else `D-<n>`), and never refuses for what a row
  says; a missing or empty argument is a usage error. `--by <text>` (MW-015) sets the `by` column: by default
  `session:<session id>` (the id the lock gate left in a one-use permit; `session:unknown` with none); `owner` is
  written only by the owner's terminal (no `CLAUDECODE`) or by `mkway ask answered`, and a session that passes
  `--by owner` is refused `ledger-by-owner`; `mkway ask default` writes `session:<session id>`. `--topic` is plain words: letters, digits, spaces and dashes.
  A quote with special characters or several lines is not typed on the command line: the session writes it verbatim
  into `<bundle.root>/ledger/quote.txt` and runs the same command with `--quote-file <bundle.root>/ledger/quote.txt`
  in place of `--quote`; the row's quote is the file's text with one trailing line break stripped, and the command
  deletes nothing. `--quote` stays for plain quotes.
- **Search.** `mkway search <words>` reads the ledger and every file of `knowledge.files` (default: the ledger only).
  A hit holds any of the words, case does not matter, there is no ranking. Hits are grouped by file and by status:
  in force first, then withdrawn, then superseded. Each run appends one record to `<state.dir>/searches.jsonl`
  (session, time, words, hit count, hit ids), also when nothing is found or there is no ledger.
- **Gate `search`** (`gates.search`; edit group). `AskUserQuestion`, and a write to a path that matches
  `questions.files`, is refused `search-missing` unless this session has a search record newer than the last user
  message: run `mkway search <words>` first, then ask. The gate fails open: when the turn boundary cannot be read the
  question goes through and the log gets a row `search-unverified`.
- **Ask lines.** In the sources file of an ask with `kind: substance` (see «Questions to the owner»; the default of
  `owner_ask.sources` is `ledger`) the session writes `ledger: N hits` and at least one line
  `> ledger: <verbatim>`, or `ledger: 0 hits` and a line `search: <record id>`, the id of its search record.
- **Start block.** When the ledger file exists the block has the line `ledger: N rows, M in force`, and `search` is
  named under `gates on:` or `gates off:`.

## Asks that do not stop the work
A session that asks the owner must not wait for the answer with nothing to do. An ask is a file, it carries a fallback
and a deadline, the owner is told at once, and the session goes on with the work that does not depend on the answer.
The gate `owner_ask` holds this (profile switch `gates.owner_ask`); the sources rules of «Questions to the owner»
stay.
- **Fields.** Every `<asks dir>/<name>_ask.md` holds the lines `default: <text or none>`, `deadline: <ISO local time or
  none>`, `blocked: <what waits, or none>`, `reversible: yes|no` and `status: open`. A write that leaves one out, or
  gives it no usable value, is refused `ask-fields-missing`, and the text names each missing line. The later statuses
  are `answered`, `default-taken` and `withdrawn`: the owner sets them in an editor, or the commands below do.
- **One open ask.** A session with an ask whose status is open may not write a second ask file: `ask-already-open`
  (add to the open ask, or wait). `owner_ask.max_open` (default 1) is the number. Who wrote an ask is a record the
  engine writes after the write (the owner of an ask is its first writer); a failed record is `ask-record-failed`.
- **No pop-up.** The pop-up question tool `AskUserQuestion` is refused `ask-tool-off`, and the text names the file
  route. `owner_ask.tool_allowed: true` lets it through to the search gate.
- **Notify.** `notify.command` is a command line with the placeholders `{file}` (the ask file) and `{line}` (the
  question, the default and the deadline). After an ask file is written the engine runs it, 10 seconds at most, and logs
  `notify-sent` or `notify-failed`; a failure never blocks. The line is split into words before the placeholders are
  filled, and no shell reads it, so a question text runs nothing. The default is none: nothing runs. The engine ships no
  channel. An example only, for an HTTP push service: `curl -s -d "{line}" https://push.example.com/<topic>`.
- **Board.** `mkway asks`, from any terminal, prints one row for each ask file: id, card, age, deadline, default,
  status and the blocked part (the age is the file's). The start block has the line `open asks: N (oldest <age>); past
  deadline: M; defaults taken since the owner's last re-seal: K`. At the next prompt a session that owns an ask past its
  deadline is reminded (`ask-past-deadline`): take the default if the ask is reversible, else keep waiting.
- **Default and answer.** `mkway ask default <id>` is allowed only for `reversible: yes` and a deadline that has passed:
  it writes the ledger row «default taken: <default text>, ask <id>», sets `default-taken`, leaves the record
  `ask-default` that the start line counts, and logs. Otherwise it is refused: `ask-not-reversible` (it stays waiting;
  the owner decides), `ask-deadline-not-passed`, `ask-not-open`, `ask-unknown` or `ask-no-default`.
  `mkway ask answered <id>` sets `answered` and writes the ledger row with the owner's words, from the file
  named by `--quote-file` (the form of `ledger add`) or from `--quote`. The ledger row's `by` column reads as the owner's rows do; the
  quote of a default says `default taken`.
- **Never taken by default** (a method rule, not code: the session writes `reversible: no`): anything irreversible,
  anything that leaves the task, deletes, locks and windows, and the owner's own words. These stay waiting, and the
  session parks the part that is blocked.
The keys are `owner_ask.max_open`, `owner_ask.tool_allowed` and `notify.command` (`engine/KEYS.md`).

## The lead role
A lead is a session that orders work and does not do it. The engine knows it by its session id, the one the hook input
carries, never by a name in a text. The gate `lead` (profile switch `gates.lead`) holds the role; it is a form gate
(«Watch mode and trip»), so a first install starts it in watch, and the owner makes it block with `mkway gate on lead`.
- **Register.** `mkway lead register`, run in a session, writes `{session_id, role: lead, since}` into `leads.json` in
  the state folder (a second run changes nothing). The owner's terminal can make or end a lead: `mkway lead add
  <id-prefix>` (a session id seen in the state records) and `mkway lead remove <id-prefix>`. Both are owner-only, like
  `mkway give`. Refusals: `lead-no-session` (no hook check names the session: run it alone, in its plain form),
  `lead-session-only` (register is a session's command), `lead-unknown` and `lead-ambiguous` (an id prefix that names
  none or several), `lead-not-registered` (the session is no lead).
- **What a lead may.** Make cards (`mkway card new`; the card's `Ordered by` is the lead, and its folder gets an
  `ORDER.md` from the engine's template with the four headings `Objective`, `Output form`, `Time-box` and `Boundary`),
  write that `ORDER.md` of the cards it ordered and the asks folder, close the cards it ordered (the rule of «Closing
  cards» is unchanged), and receive notices. It hands a card it ordered to another lead with `mkway give <card>
  <id-prefix>`; the card changes hands only when the new lead runs `mkway lead accept <card>`. The owner's `give` needs
  no accept. Refusals: `lead-give-not-yours` (a card another orderer has), `lead-give-not-lead` (the target is no
  lead), `lead-give-self`, `lead-accept-none` (no hand-off waits for this session), `lead-accept-stale` (the orderer
  changed since the offer; the offer is dropped).
- **What a lead may not.** Write any other path: `lead-no-edit` refuses it in the edit tools and in the shell (a
  redirect, a copy, a delete, a program that may write anywhere; a path outside the repository is not judged). Hold a
  card: `lead-no-take` refuses `mkway card take`. The owner's commands (locks, hold, `gate on|off`, `lead add|remove`,
  consent) stay the owner's. A lead's message is never the owner's consent, and no gate reads a message.
- **Notices.** The engine appends a row with the fields `id`, `from`, `to`, `kind`, `reply_to`, `ts`, `ack_ts`, `body` (the kind is
  `notice`) to `inbox/<lead id>.jsonl` in the state folder, when a card of the lead is past its Appetite (the cell's amount from
  its date, in whole days; once for each card), when a gate tripped into watch (every lead), when a default was taken on
  an ask (the lead that ordered the asking session's card; every lead when that card is not established), and when a
  builder finished (its `card set <id> waiting`; the card's orderer). A lead sees its unacked rows in its start block and
  at each prompt (`lead-notices-unacked`) and clears one with `mkway ack <id>` (`ack-unknown` when there is none;
  `ack-not-yours` for a row of another inbox; `lead-bad-id` when an inbox name is not a plain id; any session may ack its
  own rows, see «Messaging order»). A notice unacked for `leads.escalate_hours` (default 4) shows in
  `mkway leads` and in the start block of a session that is no lead, which is how it reaches the owner.
- **The view.** `mkway leads` prints, for each lead: its id, the cards it ordered and has not closed, those past their
  Appetite, its last activity, and its unacked and escalated notices, with each unacked row below. A lead with more cards
  than `leads.max_cards` (default 5) gets a warning line; nothing is ever refused for the number.
- **Shared state.** Sessions of several git work trees of one repository must see the same leads. `leads.json`,
  `inbox/<lead id>.jsonl` and `sessions.jsonl` therefore live in the shared state folder: in a linked work tree it is
  the main work tree's state folder (the same path below the top of the work tree, then `state.dir`); in the main work
  tree, with no git, or when git fails it is the ordinary state folder. The answer is resolved once for each process.
  Everything else (records, calls log, permits, once-store, lock markers) stays in each work tree's own state folder.
  `sessions.jsonl` gets a row `{session_id, root, ts}` at each session start and a fresh one at a prompt when the
  session's last row is ten minutes old; `mkway sessions` lists from it and prints the `root` folder of each session
  (`root not established` for a session that only the records know).
The keys are `leads.escalate_hours` and `leads.max_cards` (`engine/KEYS.md`).

## Messaging order
Sessions that message each other one by one, to anyone, with no record, give anarchy: the same body to two recipients, an
order relayed and rewritten, statuses to the owner from several sessions. The order is **a star per card**, and every
message is a row in an inbox. The owner reads one view, `mkway board`, so nobody sends the owner a status.
- **Who may send to whom.** A lead is a registered lead («The lead role»). A builder is the session that holds a card a
  lead ordered. A lead writes to another lead and to the builders of the cards it ordered; a builder writes to the lead
  of its card only, never to another builder; a session with no role writes to a lead only. The engine reads the
  holder of a card in the work tree the session runs in (the shared `sessions.jsonl` names it). Every other pair is
  refused `message-topology`, and the text names the way. The same body to a second recipient inside
  `messaging.duplicate_window_hours` is refused `message-duplicate` (the same body to one recipient is not).
- **The kinds.** `order` (a lead's), `question`, `answer`, `notice` and `result`. An order and a question are commands and
  need an ack; the receiver treats a row id it has seen as the same message. A `notice` and a `result` are events: they
  go to a lead (the lead of the sender's card) and are never relayed on. The kind for finished work is `result`.
- **The inbox.** One append-only file for each session, `inbox/<session id>.jsonl` in the shared state folder (the
  file «The lead role» made for notices), keyed by session id, never by a name. A row has the fields `id`, `from`, `to`,
  `kind`, `reply_to`, `ts`, `ack_ts`, `body`. The rows are written only by `mkway send` and `mkway ack`: the engine default
  lock target `inbox` (in `defaults.json`, `locks.targets`: `<state.dir>/inbox/**` and `<state.dir>/pings.jsonl`) is
  closed like every lock, so a row written by hand is refused by the lock gate.
- **Send.** `mkway send --to <id-prefix> --kind <kind> --file <body> [--reply-to <id>]`. The sender is the session id of
  the hook input (the lock gate's one-use permit), never a name in the text. The prefix is matched against
  `sessions.jsonl`. The command appends the row and prints the ping line `mkway inbox <id>` and the recipient's `root`
  folder. The sender finds the session in `ListAgents` by that folder and sends exactly that line, and nothing else, with
  `SendMessage`; there is no socket poster (a session cannot post to another session's socket). A recipient never seen,
  or last seen more than `messaging.dead_hours` ago, is dead: the message is a row of `dead-letter.jsonl` and a notice
  goes to the sender's lead. Refusals: `message-no-session` (no hook check names the session: run it alone, in its
  plain form), `send-session-only` (the owner reads `mkway board`), `message-no-file`, `message-empty`,
  `message-reply-unknown` (`--reply-to` names no row of the sender's inbox), `message-ambiguous` (a prefix of several
  sessions), `message-dead-letter`, `message-topology`, `message-duplicate`.
- **Read and ack.** `mkway inbox <id>` shows the row to its recipient (`inbox-not-yours`, `inbox-unknown`).
  `mkway ack <id>` sets `ack_ts` of a row of the caller's own inbox, a builder's as a lead's (`ack-not-yours` for another
  inbox, `ack-unknown`). The start block (`inbox: unacked items: N`) and the prompt (`inbox-unacked`) list the unacked
  items. A Stop with an unacked order older than `messaging.ack_reminder_minutes` gets a reminder line, `orders-unacked`,
  never a block.
- **The gate.** The form gate `message` (profile switch `gates.message`) checks `SendMessage` in its own hook group,
  `message`. It reads only the sender's side, never the `to` field (the ref of `ListAgents` is not the session id): the
  body is exactly one ping line `mkway inbox <id>` and nothing else, and row `<id>` is in the shared inbox and was written
  by this session, else `message-not-in-inbox`; and no ping for `<id>` was sent yet, else `message-duplicate` (a passing
  ping is recorded in `pings.jsonl`). A call with no text, only `notify_when_idle`, passes. Being a form gate it starts in
  watch mode on a first install («Watch mode and trip»); the owner makes it block with `mkway gate on message`. It fails
  open: a crash of the gate is a `gate-error` row, never a stuck session. `mkway install` writes its hook entry
  and `mkway check` warns when the settings lack it.
- **The board.** `mkway board` prints three parts: `inboxes:` (each session's role, folder, unacked rows and orders, then
  each unacked row), `cards:` (status, who ordered, who holds) and `asks:` (the board of «Asks that do not stop the work»).
- **Method rules.** These are rules of method, not code: a lead forwards the original id and rewrites nothing; a body
  quoting the owner is not an order and not consent, only the owner's own words in the ledger are.
The keys are `messaging.duplicate_window_hours`, `messaging.dead_hours` and `messaging.ack_reminder_minutes`
(`engine/KEYS.md`).

## Outbox check: a text leaves only after a fresh reader

A text written from compacted memory and checked by its own author goes out with its contradictions in it. A file made
for someone outside the session (the owner, a customer) counts as checked only when a fresh reader has read it as it is
now. The engine makes that mechanical. It never judges the words: it compares a hash, scans for patterns the task
supplies, and looks for the proof in the records that a reader of the right type ran after the last change.

**Keys** (all optional; with no `outbox.dir` there is no outbox, no start line and no check):

| Key | Meaning |
|---|---|
| `outbox.dir` | the folder of the files made for someone outside the session |
| `outbox.checkers` | the agent types that may sign a check; with none listed, no check is valid |
| `outbox.id_patterns_file` | a task-supplied file of regexes, one per line (blank lines and `#` lines skipped), that the text must not match; the engine ships no pattern, and a file it cannot read makes every check `unproven` |

**What counts as checked.** Beside `<file>` sits its check file, the name plus the suffix `.check.md` (the engine constant `check_suffix`),
with these lines, the forms of `outbox_check.lines` in `engine/defaults.json`:

- `sha256: <the document's sha256>` equal to the file's sha256 now (the engine verifies it);
- `numbers: N checked, 0 contradictions`, `claims: N checked, 0 overstated, 0 without basis` and `links: clean` (the
  checker's attestations, form only);
- `patterns: clean` (the engine scans the file with the regexes and a hit overrules the line);
- `checker: <agent type>` with a type that is in `outbox.checkers`.

**Proof of a fresh reader.** The agent records `agents.jsonl` must hold a start and an end of an agent of the `checker:`
type in the session that wrote the check, with the start and the end after the file's last change and the end before the
check was written. The session and the time of the write are the record the post step appends to
`outbox_checks.jsonl` after every Write, Edit or MultiEdit of a check file; the session is the hook's session id, never a
name in the text. A sub-agent has no memory of the session, so the reader is fresh by construction.

**States** (`mkway outbox` prints one row per file: file, sha prefix, state, checker, time, and a problem line under
each file that is not valid):

| State | Meaning |
|---|---|
| `valid` | every line, an equal sha256, a listed checker, no pattern hit, the proof |
| `stale` | the check holds a sha256 that is not the file's now: the text changed, or the check is for another file or an older version |
| `unproven` | the sha256 is equal, but a line is missing or wrong, the checker is not listed, a pattern matches, or the proof is missing |
| `missing` | no check file |

**Where it bites** (mechanical places only, no words):

- the write gate `outbox_check.pre` refuses `check-sha-mismatch`: a write that leaves a check file whose `sha256:` line is
  missing or is not the document's now; the text gives the line to write, so a stale check cannot be forged by hand;
- `card close` refuses `close-unchecked-outbox` while an Acceptance row names a file under `outbox.dir` whose check is not
  `valid`, for the owner's close and for the orderer's (card MW-011);
- the Stop gate adds a reminder `outbox-changed-after-check`, never a block, for a file whose text changed after its
  check, once per session and set of files;
- the post step records the write; when it cannot, it warns `check-record-failed` and the check reads `unproven`;
- the start block has the line `outbox: N files, M unchecked`.

**What stays refused or unproven**: a document edited after the check (`stale`); the sha line of an older version
(`stale`); a check copied from another file (`stale`, or `unproven` when the text is the same, because no session wrote
it with a write tool); a check made by a shell or changed after its write (`unproven`); a checker type that is not on the
list, or no list; no agent row of that type in the session, or one that started before the last change or ended after
the check; a pattern present while the line says clean; any line in the wrong form.

**Class.** The write gate has class `form` (card MW-012): a first install starts it in watch mode, where a refusal is a
`would-refuse` row and the write goes ahead, until the owner's `mkway gate on outbox_check.pre`. The record step and
the Stop reminder never refuse and have class `integrity`.

## Deliverables: built from tested code, compared with a named base

A result file made for others is ready only when it exists at a named path, with its sha256, built on the final HEAD
from code whose tests passed, past its gates and the fresh-reader check (the outbox check above). A status, a plan or a
checklist is not a deliverable. A number that says «changed» or «now» names its base: a delivered file, never an
internal run. The engine records and compares hashes and commits; it knows no task and judges no words.

**Keys** (both optional; with no `deliverables.paths` there is no deliverable, no start line and no check):

| Key | Meaning |
|---|---|
| `deliverables.paths` | globs of the result files made for others; may overlap `outbox.dir` |
| `deliverables.require_base` | globs of the paths whose check file must name a delivered base |

**`mkway built <path>`** (any session) records where a file came from. It refuses `built-dirty` while a tracked file has
uncommitted changes (an untracked file, the result itself, does not count), `built-untested` while `commit_tests.jsonl`
holds no green row for the tree of HEAD (the commit check of «Tests before a commit» writes that row: commit a change
outside the test roots, or fix the red tests, then run the command again), and `built-no-file` for a path with no file.
Otherwise it appends {path, sha256, head, tree, time, session} to `deliverables.jsonl` (the session is the hook's
session id, `owner` in the owner's terminal) and a ledger row `built <path> <sha8> at <head8>`.

**`mkway delivered <path>`** is the owner's command: it appends {path, sha256, time} to `delivered.jsonl` and keeps a
copy at `<state>/delivered/<name>.<sha8>`, the base of every later comparison; an older copy is never overwritten. A
session's call is refused `owner-only-command` by the command and by the lock gate, so no session picks its own base; a
path with no file is `delivered-no-file`.

**The base line.** The check file of the outbox check may hold one more line, `base: <sha8>` (the optional line of
`outbox_check.lines`, read by the same parser). It must be the first eight digits of a delivered row, else the check is
`unproven` and the problem names `base-unknown`; for the paths of `deliverables.require_base` the line is required.

**Where it bites** (each a command check, strict like the close of the outbox check; no hook entry, so no watch mode):

- `card close` refuses `close-deliverable-unbuilt` while an Acceptance row names a path of `deliverables.paths` and no
  provenance row holds the file's current sha256 with a head that is HEAD or an ancestor of HEAD; the text names
  `mkway built <path>`;
- `card close` refuses `base-unknown` for a named path of `deliverables.require_base` whose check file (the name plus
  `.check.md`) has no `base: <sha8>` line, or names a base no delivered row holds; the text names `mkway delivered`;
- `mkway deliverables` lists each file: path, sha prefix, state (`built`; `changed`, a file that was changed after it
  was built; `unbuilt`) and the sha prefix of its newest delivered row; the start block has the line
  `deliverables: N built, M changed since built, K delivered`.

**What stays refused**: a result built from a dirty tree or untested code; a file changed after it was built (its hash
has no provenance row); a provenance copied from another history (its head is no ancestor of HEAD); a base that was
never delivered, or an internal run named as the base; a session that delivers.

## Agent records
Every helper agent's result is saved with its start and end time, so none is lost and none runs unseen.
- The `post` group records `SubagentStart` and `SubagentStop` (gate `agents`, on by default; `gates.agents.on: false`
  turns both off; `mkway install` writes both hook entries). The hook never blocks and adds no context.
- `<state.dir>/agents.jsonl` gets a `start` row (session, agent id and type, start time) and, when the agent ends, an
  `end` row: start and end time, `elapsed_seconds` and the result in full. The result is the payload's
  `last_assistant_message`, else the last assistant message of the file `agent_transcript_path` names
  (`result_source` says which). A value that cannot be established, such as the start of an agent whose start row is
  missing, is «not established». A failed write is the warn row `agent-record-failed` in `refusals.jsonl`.
- `agents.cap_minutes` (profile, a number above 0, default 30): the start block shows one line for each agent of the
  session that ran longer, or whose last row is a `start` row. A resumed or compacted session keeps its id, so it
  sees its agents; a new session has none yet.

## Commit checks
A session's `git commit` is read by one gate before it runs: `commit_files`, three manifest entries and one profile
switch, `gates.commit_files` (with `vcs: none` nothing is checked; the owner's own terminal runs no hook, so nothing is
gated there). The gate takes the files each form of the commit would stage (`-- <paths>`, the index, `-a`, `-i`,
`--amend`) and refuses, in this order, naming the files and the way out:
1. **Right files only** (`file-not-in-card`). Every file must lie inside the Paths of the session's open card, or be
   always allowed: the card's own folder, the register, `<bundle.root>/ledger/` and `paths.exempt`. An empty Paths is
   no file rule; a session with no open card (none taken, or the card is not `open`) may commit only the always-allowed
   files. Way out: `git restore --staged <file>` (under `-a` or `--`, the text says how), or add the file to the card and
   ask the owner to `card open` it again.
2. **Own changes only** (`ride-in-file`). A file this session never wrote is a ride-in from another session. What a
   session wrote is recorded, one row per path, in `<state.dir>/touched.jsonl` by two recorder entries on the same
   gate: `touched.edit` (Write, Edit, MultiEdit, NotebookEdit) and `touched.shell` (the paths the lock gate's reader
   finds in a shell command; a glob is kept as a glob). A shell write whose target cannot be read is recorded as
   `unresolved`, and then every file counts as written (the gate cannot tell which one was). A recorder that cannot
   write its row warns `touch-record-failed`; the commit gate then refuses what it cannot show. The always-allowed
   files are exempt. Way out: `git restore --staged <file>`, or leave the file out of the paths.
3. **No junk** (`junk-file-staged`), **no force-added ignored file** (`ignored-file-staged`): a new file that
   `git check-ignore` matches was added with `git add -f`; the ignore file is never overridden by a commit.
4. **No data files** (`data-file-staged`, by extension) and **nothing too large** (`file-too-large`). The three keys of
   the profile group `commit` replace the defaults, each alone: `commit.junk` (default `__pycache__/`, `*.pyc`,
   `.pytest_cache/`, `.pytest_tmp/`, `*.log`, `*.tmp`, `*.orig`, `*.rej`, `.DS_Store`, `Thumbs.db`; a name or glob
   matches at any depth, a trailing `/` names folders), `commit.data_patterns` (default `*.csv`, `*.tsv`, `*.xlsx`,
   `*.xls`, `*.parquet`, `*.db`, `*.sqlite`, `*.sqlite3`, `*.bak`, `*.dump`) and `commit.max_file_kb` (default `1024`).
   Deleting such a file is never refused. Way out: unstage it, keep the data outside the repository, or ask the owner
   to change the key.
5. **The message names the open card** (`commit-message-card`): the card's whole id, in the `ids.card_prefix` form, in
   a `-m`, a `-F -` here-document or a readable message file. On by default; `gates.commit_files.message_card.on` set
   to `false` turns this rule off and nothing else.
6. **A rule card goes in with its test** (`rule-without-test`), when the profile sets `rules.cards` and
   `rules.test_for`: see «Rule cards paired with tests» below.

The gate fails closed (`commit-unreadable`): a commit it cannot read (a folder from a variable, a carried command, an
unknown option or git form, a message it cannot read, a git read that fails or times out) is refused, and so is a
commit in a command that also runs a git subcommand that changes what is staged (`add`, `rm`, `mv`, `restore`,
`reset`, ...): the hook reads the index before the command runs, so run that command in a call of its own, then the
commit alone. A register that differs from its seal refuses `register-tampered`; the owner runs `card resync`.

Limits: a file written by a script the reader cannot follow (`python script.py`) leaves no row, so staging it is a
ride-in: write it through the Write tool or a plain redirect; the ignore check is for new files, so an edit to a file
already in the repository is not refused for it; the record is written before the write, so a write that then fails
still counts as written; a guard against slips, not a wall (`engine/KEYS.md` lists the keys).

## Tests before a commit
Tests before a commit, red test first, no red commit. The gate `commit_tests` (shell group, PreToolUse on Bash and
PowerShell, after the lock gate, `onFailure: block`, one profile switch `gates.commit_tests`) runs when a session
starts a `git commit`.
- **The staged tree.** The tests run on the staged tree, never on the working tree, so an untracked file cannot make
  a commit pass. The index is exported with `git checkout-index -a -f --prefix` into a folder under the state dir,
  the suite runs there, and the folder is removed. `git commit -a` and `git commit -- <path>` are read as git will
  take them, in a temporary index; the real index is never changed.
- **What runs.** The command is `tests.command`; the default is `python -m pytest -q` over the `test_roots`
  (default `tests`). The run sees the environment names of `test_env` and `ENGINE_TERMS_FILE`, the system essentials
  and nothing else. The engine runs only git and the profile's Python, so the first word of `tests.command` is that
  Python.
- **Red-first.** A commit whose staged files all lie under `test_roots` may be red and runs no tests. Any other
  commit needs a green run, else it is refused `commit-tests-failed`; the text names the first 10 failing test ids
  and the way out: fix and stage the fix, or commit the tests alone as the red-first commit.
- **Docs only.** A commit whose staged files all match `paths.docs` runs no tests. The default globs are
  `<bundle.root>/cards/**`, `<bundle.root>/ledger/**` and `*.md`.
- **Budget.** A run is stopped at `gates.commit_tests.budget_seconds` (default `780`; never more than 840 s, because
  the hook timeout is 900) and the commit is refused `commit-tests-over-budget`, fail closed. The way out: the owner
  raises the budget in the profile in their own terminal, or the session shrinks the commit. A command that cannot
  start, or a git read that fails, refuses `commit-tests-not-run`.
- **One run per staged tree.** The state folder `<state.dir>` gets the file `commit_tests.jsonl` with one row per run: the staged-tree hash, the
  command, the result (`pass`, `fail` or `over-budget`) and the duration. The same index with the same command does
  not run again and gives the same verdict; a changed index runs again, and so does an `over-budget` tree after the
  budget is raised.
- **Chained commands.** `git add ... && git commit` is refused `commit-tests-chained`: the index is read before the
  command runs, so it is not the tree the commit would take. Run the staging command alone, then the commit alone.
- **Not gated.** The owner's own terminal is not gated: no hook runs there. A gate that is off is named on the start
  block (`gates off:`); the engine's own tests use a tiny fixture project and never run the engine's own suite.

## Watch mode and trip
Every manifest entry has a `class`: `integrity` or `form`; an entry with no class is `integrity`. The form gates today
are the owner-ask gate (edit and stop entries) and the search gate; the locks, the subtask gate, the commit checks, the
delete gate, the card-close gate and the record gates are integrity. A form gate checks how a thing is written, not
whether it is safe, so it may stop blocking when it is wrong too often. An integrity gate never does.

In watch the form gate still runs. Its refusal is written as a `would-refuse` row in `refusals.jsonl` (the same reason
id and text) and the call goes ahead. Every gate that runs adds one row (time, gate, verdict `allow`, `refuse`, `log` or
`error`) to `gate_calls.jsonl` in the state folder; a gate is in watch while its marker file
`gate_mode/<gate>.watch` in the state folder exists (a JSON object: cause `installed`, `tripped` or `owner`, the time,
the counts). Integrity gates never read it.

What trips. After a refusal by a form gate that is enforcing, the dispatcher counts that gate's rows of the last 24
hours. With at least `gates.trip.min_calls` calls (default `20`) and a refusal share above `gates.trip.share` (default
`0.34`, so 7 of 20 trips and 6 of 20 does not) the marker is written with cause `tripped` and a `gate-tripped` row is
logged. The call that tripped it stays refused; watch starts with the next call. An `error` row is neither a call nor a
refusal here: a gate that crashes is shown at once by its own rows, and it must not look like a rule that is too strict.

Shadow by default. The first install (no state folder yet) starts every form gate that is on in watch, cause `installed`;
a re-install keeps the modes as they are. Every change of mode is a log row with a time: `gate-tripped`,
`gate-watch` (the owner's switch), `gate-on`, `gate-watch-installed`.

Who resets. Only the owner, in their own terminal: `mkway gate on <name>` removes the marker (and turns the gate on if it
was off); `mkway gate watch <name>` puts a form gate in watch by hand, cause `owner`. There is no automatic return to
blocking (no automatic return, ever): a rule that flaps between the two would be harder to trust than either. A session cannot run either command
(`owner-only-command`).

Why integrity gates never degrade. A refusal storm can be forced by anyone who can trigger a rule, so letting it switch
a gate off would let a session switch off a lock. `mkway gate watch <name>` on an integrity gate is refused: integrity
gates never watch. The start block names every form gate in watch, in every session until the owner's `gate on`:
`gate <name>: WATCH since <time> (<cause>; <refused> of <calls> in 24 h); would-refuse today: <n>; log: <path>`, and
the `gates on:` list marks it `(watch)`. Not built: a notice at Stop, an automatic reset.

## Owner hold
Profile line: `locks.targets: [{"name": "hold", "paths": ["**"], "open_by_default": true}]` (profile targets only;
a built-in name with the flag is refused). Open until the owner runs, in their own terminal, `mkway hold` (a marker
file); `mkway go` removes it; the long forms are `mkway lock close hold` and `mkway lock open hold`. Closed, it stops
every session write and commit; it does not stop reading, answering, or a word in a message.
The marker is in the shared state folder: a hold reaches every worktree of the repository.

## Deletes
A session's delete is read by one gate before it runs: `delete`, one manifest entry (shell group, `onFailure: block`, so
a crash blocks the call) and one profile switch, `gates.delete`; it is on the start line's `gates on:` and, when the
profile turns it off, on `gates off:`. The gate reads the program of each simple command, so the same words in a quoted
echo, a commit message or a `grep` pattern are no delete. The forms are `rm`, `rmdir`, `unlink`, `del`, `erase`, `rd`,
`Remove-Item` and its aliases, `find -delete`, `xargs rm`, the Python calls `os.remove`, `os.unlink`, `os.rmdir`,
`shutil.rmtree` and `Path.unlink`, the git forms below and the SQL words below; each is read in every position (a
chain, a pipe, parentheses, `$( )`, backticks, `bash -c`, `cmd /c`, `pwsh -c`, `xargs`, `find -exec`). It refuses, in
this order per target, naming the target and the way out:
1. **A literal path inside the root that exists** (`delete-target-unknown`). A variable, a substitution, an unknown
   PowerShell parameter, a splat, `find -delete`, `xargs rm`, a missing path, and the root, the state folder or a
   folder that holds or lies in it are refused: name the exact paths, or use `mkway delete --list <file>`. A variable
   assigned a literal earlier in the same command is read.
2. **Not outside the root** (`delete-outside-root`): always refused, even when the path exists; the owner deletes it in
   their own terminal.
3. **No wildcard** (`delete-wildcard`): `*`, `?`, `[..]`, and a PowerShell `-Include`, `-Exclude` or `-Filter`. The way
   out is the list command.
4. **Backup first.** Every target is copied into `<state.dir>/trash/<timestamp>/<repo path>` (an ignored folder) and one
   row is appended to `<state.dir>/deletes.jsonl` (session, time, targets, backup folder) before the tool runs. The
   total size is limited by `delete.max_backup_mb` (default `5120`; a size equal to it passes): above it the delete is
   refused `delete-too-large`, which needs the owner's terminal. A copy, a trash folder or a record row that cannot be
   made is `delete-backup-failed`; there is never a delete without its backup.
5. **SQL** (`delete-sql`): `DROP`, `DELETE FROM` and `TRUNCATE` in the arguments, heredoc or piped text of a SQL client
   (`psql`, `sqlite3`, `duckdb`, `mysql`, `sqlcmd` and similar) or in a Python string passed to `execute`,
   `executemany`, `executescript`, `sql` or `read_sql`. `delete.sql_allowed: true` (default `false`) turns this family
   off, for a task with a scratch database.
6. **Uncommitted work** (`delete-uncommitted`), with `vcs: git`: `git clean` with force (always, `vcs: none` too: an
   untracked file is in no commit), `git reset --hard` when a tracked file has a change, `git restore` and
   `git checkout --` on a path with a change, `git rm` of a changed file. A deletion is no work to lose; `git restore
   --staged`, `git rm --cached` and a dry run are no deletes. `git rm` of a clean tracked file is allowed with a record
   row and no copy, because git keeps it. A git read that fails or times out refuses.

The commands. `mkway delete --list <file>` is a session's command and the gate never refuses it: the file (anywhere)
holds one exact repo path per line; each must exist, lie inside the root, hold no wildcard and lie in or hold neither a
closed lock target nor the state folder. Any bad line deletes nothing and is named by its number; otherwise the paths
are backed up, deleted and recorded in one row (`via: list`; the command knows no session id, so the row says `by:
session` or `by: owner`). `mkway trash list` and `mkway trash empty --older-than <days>` are the owner's: a session's
call is refused `owner-only-command` by the gate and, through the `CLAUDECODE` tripwire, by the CLI. Emptying removes
the folders older than the days by the stamp in their name (`0` removes all) and writes one row (`via: trash-empty`);
the engine never empties the trash by itself. The keys are `delete.max_backup_mb` and `delete.sql_allowed`
(`engine/KEYS.md`).

Limits: SQL read from a file or stdin is not seen; an encoded command is not read (PowerShell `-EncodedCommand`); `git checkout -f`,
`git switch --discard-changes`, `git stash` and a delete inside a script file are not read (a script's own `os.remove`
passes when the script is run by name); a quoted wildcard is read as a wildcard; the owner's own terminal runs no hook,
so nothing is gated there; the backup is a copy in the working tree's state folder, so a disk loss takes both: a guard
against slips, not a wall.

## Rule cards paired with tests
A rule card and its test travel together. Two profile keys switch the check on, both with no default, so it is off until
a branch sets them: `rules.cards` (globs of the rule-card files) and `rules.test_for` (the path of a card's test, with
`{id}` for the card id, e.g. `tests/rules/{id}/test_{id}.py`). The id of a card is read from its file name by the
existing form `ids.rule_card`: the whole name without its extension, else the part before the first `-`, `_`, `.` or
space. A file that matches a glob but holds no id in its name is not a rule card, and with no `ids.rule_card` nothing is
refused.
- **The commit check** is one more rule of the gate `commit_files` (class integrity, as the other commit checks): a
  commit that adds or changes a rule card must take its test file too, new or changed, or it is refused
  `rule-without-test`. A card whose test file does not exist is refused the same way. A test changed without its card, a
  deleted card and a file outside the globs are allowed. The text names the card, the test path and the fix: write the
  test (red first), stage it with `git add <test>` (with `-- <paths>`, name it after `--` as well), or leave the card out.
  The tests then run before the commit, as always (the gate `commit_tests`).
- **`mkway rules`** (a session may run it; it only reads): one line per card, with the card path, the test path,
  `exists` or `missing`, and the last green tree: the newest `pass` row of `<state.dir>/commit_tests.jsonl` whose tree
  holds the test file (8 characters, or `none`). With the keys unset it prints one line that names them.
- **The start block** adds `rules: N cards, M without tests` when the keys are set.

## Known limits
- A chain or pipe with an engine call is refused: run the mkway command alone, in its plain form (H4).
- A shell write the lock gate cannot read (`unparsed`, or `capable`: a computed path, a variable, a program that can
  write anywhere) is refused only when the command names a closed lock target literally; otherwise it is logged
  (`write-target-unresolved`), reminded at the next prompt and counted on the start line. A glob write whose literal
  folder lies inside a closed target refuses; any other glob write is allowed, not logged. A lock-target path built
  without its literal is not seen (R43). What backs this up until MW-021: for the tracked targets (the profile, the
  register, the bundle `.gitignore` and `.gitattributes`, `mkway.lock`) the commit check refuses a commit that carries
  a change (`lock-closed-commit`), at commit time only; for `engine/`, `locks/`, the state folder and
  `.claude/settings.local.json`, which are git-ignored, there is no commit check: only the owner's review and the OS
  permissions remain.
- A Python write with a computed path that never names a target passes (logged `write-target-unresolved`), the same
  class as `python script.py`. `engine/`, `locks/` and the state folder are git-ignored, so no commit check backs them
  up (R44).
- The git time limit is 10 s per git call, not per gate; one commit check can make up to six calls (B3; close-fix item
  19, not built).
- The shell gate reads the command text only: a script file that runs an owner-only mkway command is not read by it,
  as a Python file is not for the lock gate (R43). The CLI's own refusal below then applies.
- A commit inside another program is not read. With `vcs: git`, a carrier (`bash`/`sh -c`, `cmd /c`,
  `pwsh`/`powershell -c`/`-Command`, `xargs`, `find -exec`/`-execdir`/`-ok`, `eval`, `script -c`, python, perl or
  node `-c`/`-e`) whose argument text, quotes and backslashes removed, holds a `git` token (or a `$` or backtick word)
  followed by `commit` is refused `command-unparsed`: run the commit alone, in its plain form. A commit started from a
  script file is not seen (close-fix 3).
- The gates see Edit, Write, MultiEdit and the shell; other tools that write or publish are not checked; deny them in
  settings if needed.
- `CLAUDECODE` tells a session's shell from the owner's terminal; it is seen, not documented. `mkway.py` refuses every
  owner-only command when it is present, with any value, the empty value included: «run it in your own terminal, not
  inside a Claude chat». A `!` command typed inside a Claude chat carries it too, so it is refused there. A session
  can strip the variable (`env -u CLAUDECODE`, `unset`), so this layer is a tripwire that teaches the route, not a
  wall; the wall is the OS permission on the lock state, the profile and the install record (owner).

## Use in a task
```
python <engine repo>/mkway.py install --from <engine repo> [--ref <tag or sha>] --root <task root>
python mkway/engine/mkway.py check
python mkway/engine/mkway.py card new "<title>"
```
`install` copies the engine's fixed file set into `<task root>/mkway/engine/` (the bundle root is the profile's
`bundle.root`, `mkway` by default) and writes `mkway/mkway.lock`, a starter `mkway/profile.json`, the folders `cards/`,
`ledger/`, `locks/`, `state/`, and the hook entries into `.claude/settings.local.json`. Every hook entry runs
`python "${CLAUDE_PROJECT_DIR}/mkway/engine/mkway.py" hook <event> --group <group>`; the path is the same in this
repository (the root launcher `mkway.py`) and in the copy. At each session start the dispatcher prints one start
block: the version, the gates, the drift check and the logged errors.
Live check after install: open a card (`card open <id>` in your own terminal), then start a session; you should see
the line «mkway: card changes since the owner's last re-seal: …» as a message, and the start block lists the same
change. If the message does not show, the start block's line is the only route; report it (card MW-021: another
route to the owner). `card resync` accepts the changes and moves the baseline.

## Versioning
The version is the `VERSION` file at the root (semantic versioning, for example `0.2.0`); the start block's first line shows it
(`mkway v0.2.0 (<sha or ref>)`, read from the copy's own file) and `mkway install` writes it into `mkway.lock` as
`semver`, beside the pinned sha. `CHANGELOG.md` lists the cards of each release; a test keeps it in step with the
register. Bump rule:
- patch: a fix that changes no behaviour a user relies on;
- minor: a new gate, command or profile key;
- major: an existing profile or install must change to keep working.

The owner makes the git tag `v<version>` at each release. `mkway check`, in the owner's terminal, warns when the tag at
HEAD is missing or differs from `VERSION`; the engine never writes a tag.

## Run the checks
```
python -m pytest
```
The term scan needs a term file: set `ENGINE_TERMS_FILE`, or name one in `tools/term_scan.json`. Without one the
suite fails with «term list missing».
