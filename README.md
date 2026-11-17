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

`CHANGELOG.md` and `cards/REGISTER.md` merge with git's `union` driver (`.gitattributes`, card MW-082, R197 A): the lines of both branches are kept. An existing register row is edited only on master by the orderer; branches only add rows.

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
work), `close-tests-failing` (a named test is red or missing; with `vcs: git` the tests run on an export of HEAD's tree, so a file that is only staged, modified or untracked is not seen). A card that is not `open` or `waiting` is `card-bad-move`.

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
  written only by the owner's terminal (no `CLAUDECODE`; a session's `mkway ask answered` writes `session:<lead id>`, MW-119), and a session that passes
  `--by owner` is refused `ledger-by-owner`; `mkway ask default` writes `session:<session id>`. `--topic` is plain words: letters, digits, spaces and dashes.
  A quote with special characters or several lines is not typed on the command line: the session writes it verbatim
  into `<bundle.root>/ledger/quote.txt` and runs the same command with `--quote-file <bundle.root>/ledger/quote.txt`
  in place of `--quote`; the row's quote is the file's text with one trailing line break stripped, and the command
  deletes nothing. `--quote` stays for plain quotes. `--replaces <row id>` (MW-050) writes that id in the new row's
  `replaces` column; the id must be in the ledger, else the add is refused `ledger-replaces-unknown` and nothing is
  written. The replaced row's line is never edited: a row that a later row names in `replaces` reads as superseded.
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
  engine writes after the write (the owner of an ask is its first writer); a failed record is the refusal `ask-record-failed`, which names the path it could not write (MW-109).
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
  named by `--quote-file` (the form of `ledger add`) or from `--quote`. It runs only in the intake role, the lead (MW-119,
  R272 G5): any other session is refused `ask-answered-not-lead`, and the text says the lead records the answer. The lead's
  row is `by: session:<lead id>`, its source starts with `owner`, and it is never `by: owner`; one record of kind `ask-answered`
  (`ask`, `session`, `source: owner`, `quote`, `time`) goes to `outbox_checks.jsonl` so the board can list every answer
  recorded in the owner's name. Named limit: the lead types the quote, and the engine does not compare it with the owner's
  message (no transcript checks, R243); the board line makes every such answer visible to the owner. Three cases (R287b): the owner's own
  terminal (no session) may answer with `by: owner`; the lead answers with `by: session:<lead id>`, source `owner` and the
  quote; every other session is refused. A session with no session variable could write `by: owner` until the date in the profile key
  `messaging.session_id_watch_until`; while it is empty, the limit has no end date. The session-id gate closes it, with no new
  code (`tests/core/test_mw110_session_env_core.py`, case unset-after-window-refuses). The quote of a default says `default taken`.
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
  cards» is unchanged), and receive notices. **It authors its own card** (MW-028): while a card it ordered is
  `proposed`, the lead writes that card's `CARD.md` (Goal, Acceptance, Appetite, Paths) as well, with no card held;
  both the lead gate and the subtask gate allow exactly that. With `cards.approver: orderer` the lead also runs
  `mkway card open <card>` on a proposed card it ordered, and the Paths are recorded as at the owner's open; with
  `owner-only` the open stays the owner's. After the open `CARD.md` is sealed to the lead again (the card commands or
  the owner change it) and `ORDER.md` stays the lead's. A card the owner ordered, or another lead ordered, is never
  written or opened by a lead. It hands a card it ordered to another lead with `mkway give <card>
  <id-prefix>`; the card changes hands only when the new lead runs `mkway lead accept <card>`. The owner's `give` needs
  no accept. Refusals: `lead-give-not-yours` (a card another orderer has), `lead-give-not-lead` (the target is no
  lead), `lead-give-self`, `lead-accept-none` (no hand-off waits for this session), `lead-accept-stale` (the orderer
  changed since the offer; the offer is dropped).
- **What a lead may not.** Write any other path: `lead-no-edit` refuses it in the edit tools and in the shell (a
  redirect, a copy, a delete, a program that may write anywhere; a path outside the repository is `write-outside-root`). Hold a
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
- **Shared state.** The engine never writes outside the mkway root by its own path logic: `leads.json`,
  `inbox/<lead id>.jsonl`, `sessions.jsonl`, `pings.jsonl`, `dead-letter.jsonl` and the lock markers live in the shared
  state folder, which is the root's own state folder. To share them across the worktrees of one task (a linked work
  tree), the owner sets the absolute path `state.shared_dir` in the profile, or runs `mkway install --shared <path>`,
  which writes that key; `mkway check` warns `state-outside-root` when 0.2.0 or 0.2.1 left such files in the main work
  tree and names the folder, and never removes anything.
  Everything else (records, calls log, permits, once-store) stays in the root's own state folder.
  `sessions.jsonl` gets a row `{session_id, root, ts}` at each session start and a fresh one at a prompt when the
  session's last row is ten minutes old; `mkway sessions` lists from it and prints the `root` folder of each session
  (`root not established` for a session that only the records know).
The keys are `leads.escalate_hours` and `leads.max_cards` (`engine/KEYS.md`).

A registered lead's write outside the repository is `write-outside-root` (MW-103, R255, R255b; R274 gave every session the
one reason and the one text), in the edit tools and in a shell write: a lead orders work and its notes are task output, so a
folder next to the repository is refused as the repository's own code is. The exception is a narrow list of the harness's own
state folders, `paths.outside_writable` (it was `leads.outside_writable`; `mkway upgrade` renames the old key in the profile,
and the old key is read as an alias until the next major): the engine ships `<home>/.claude/projects/*/memory/**`,
`<home>/.claude/plans/**` and `<temp>/claude/**` in `defaults.json`, and a profile may add folders (it cannot remove one).
`<home>/.claude/settings*.json` and any path with a `.claude` folder followed by `hooks` match nothing, whatever the list says.
The shell expands `<home>` and `<temp>`, compares real paths and passes the core one fact for each path; the refusal names the
path, the root, the expanded list and the way out. A lead's unreadable shell write stays refused (`lead-no-edit`, with the way
out: a plain path, or the edit tool). The rule for every session is in the owner table below.

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
- **Send.** `mkway send --to <id-prefix> --kind <kind> --file <body> [--reply-to <id>]`. The sender is the session id
  of the launcher's variable `MKWAY_SESSION_ID` (see «The session id» below), never a name in the text; results and
  orders go by `--file`, the inbox row is the record. The prefix is matched against
  `sessions.jsonl`. The command appends the row and prints the ping line `mkway inbox <id>` and the recipient's `root`
  folder. The sender finds the session in `ListAgents` by that folder and sends exactly that line, and nothing else, with
  `SendMessage`; there is no socket poster (a session cannot post to another session's socket). A recipient never seen,
  or last seen more than `messaging.dead_hours` ago, is dead: the message is a row of `dead-letter.jsonl` and a notice
  goes to the sender's lead. Refusals: `message-no-session` (no variable and no hook permit: the text names the launcher line), `send-session-only` (the owner reads `mkway board`), `message-no-file`, `message-empty`,
  `message-reply-unknown` (`--reply-to` names no row of the sender's inbox), `message-ambiguous` (a prefix of several
  sessions), `message-dead-letter`, `message-topology`, `message-duplicate`.
- **Read and ack.** `mkway inbox <id>` shows the row to its recipient (`inbox-not-yours`, `inbox-unknown`).
  `mkway ack <id>` sets `ack_ts` of a row of the caller's own inbox, a builder's as a lead's (`ack-not-yours` for another
  inbox, `ack-unknown`). The start block (`inbox: unacked items: N`) and the prompt (`inbox-unacked`) list the unacked
  items. A Stop with an unacked order older than `messaging.ack_reminder_minutes` gets a reminder line, `orders-unacked`,
  never a block.
- **The gate.** The form gate `message` (profile switch `gates.message`) checks `SendMessage` in its own hook group,
  `message`. It reads only the sender's side, never the `to` field (the ref of `ListAgents` is not the session id):
  free text passes (`message-not-in-inbox` is removed, MW-110); a body that is exactly one ping line `mkway inbox <id>` of a row
  this session wrote is its ping, and no ping for `<id>` may have been sent yet, else `message-duplicate` (a passing
  ping is recorded in `pings.jsonl`). A ping line of another session's row passes and records nothing. A call with no
  text, only `notify_when_idle`, passes. The Stop gate of the ping (`ping-not-sent`) is unchanged. Being a form gate it starts in
  watch mode on a first install («Watch mode and trip»); the owner makes it block with `mkway gate on message`. It fails
  open: a crash of the gate is a `gate-error` row, never a stuck session. `mkway install` writes its hook entry
  and `mkway check` warns when the settings lack it.
- **The session id (MW-110, ruling R279).** A session is known by the variable `MKWAY_SESSION_ID` that its launcher sets.
  `SESSION_ENV` is the engine's contract with the launcher: one module constant of the engine, not a profile key.
  Every shell call is checked by the entry `message.session`, its own gate `session_id` of the integrity class (it never
  watches): the variable in the hook's environment must equal the hook's own session id, else `session-id-mismatch`; a
  command text that assigns the variable (`MKWAY_SESSION_ID=x ...`, `export`, `$env:...`, `setx`,
  `SetEnvironmentVariable`) is refused the same way, as the cheap first wall.
  The variable is never the proof alone. `mkway send`, `inbox` and `ack` take the id from the lock gate's one-use permit,
  which the gate writes for the plain engine call with the hook-verified session id, under the session's own id:
  `permits/<session id>.json` (ruling R279c; the shared permit of every other command is unchanged). The command reads
  the variable and opens only its own file; the one-use permit is the proof. A variable that differs from the id in the
  permit is `session-id-mismatch` and nothing is written. With no permit the variable
  alone counts only before `messaging.session_id_watch_until` (a date `YYYY-MM-DD`, empty by default: no expiry), which
  the command reads itself, with one warn row `session-id-unset`; after that date no permit is
  `session-id-unverified`, and the way out is to run the command in a session with the hooks, started with the launcher
  line. With no variable, before the end date, the command takes the single most recent permit with a warn row that names
  the limit (two sessions at once can take each other's permit; the end date ends it); after the end date an unset variable
  is `session-id-unverified`. With no variable and no permit the command is refused `message-no-session` and names the
  launcher line. A `messaging.session_id_watch_until` that cannot be read (words, an impossible date) counts as passed: the
  refusal text, the start line (one extra line) and `mkway check` (a profile error) name the value.
  The limit (ruling R279d): a script that builds the path to the state folder itself can write a permit the reader cannot
  see; that write passes with a LOG row (the reach rule, R274 §5.5). The gates catch mistakes and drift, not an adversary.
  The launcher line, for the owner's own start command of a lead: `$id = [guid]::NewGuid().ToString(); $env:MKWAY_SESSION_ID = $id; claude --session-id $id`;
  mkcl 0.7.0 does the same for the sessions it starts
  (checked with mkcl 0.7.0 in pwsh 7 and 5.1; live when mkcl 0.7.0 is live). Transition: while the variable is unset, the hook allows the call with one warn `session-id-unset` per session; the owner ends it by setting
  `messaging.session_id_watch_until` once the launcher sets the variable; after that date an unset variable is refused at the hook as `session-id-mismatch` and the text names the launcher line.
- **The record (R1).** The inbox file alone is not the record. The engine writes one row to `message-record.jsonl` in the
  shared state folder for each delivered send (the sender's session id, the recipient, the file as named or `--text`, the
  sha256 of the body, a time) and one for each acknowledgement (the acking session, `owner` for the owner's terminal, the
  row id, a time). A refused send or ack writes none. The record is written first (ruling R279c): a record that cannot be
  written refuses `send-record-failed`, names the file and the state folder, and nothing is delivered (an ack: the row
  stays unacked); the way out is to make the state folder writable.
- **The ping.** The Stop gate counts a `SendMessage` as the ping of an inbox write only when its text is exactly
  `mkway inbox <id>` for that write's id (one final line break allowed, no other space); free text and a ping for another row do not
  (ruling R279a). The send tool prints the exact line.
- **The board.** `mkway board` prints three parts: `inboxes:` (each session's role, folder, unacked rows and orders, then
  each unacked row), `cards:` (status, who ordered, who holds) and `asks:` (the board of «Asks that do not stop the work»).
- **Method rules.** These are rules of method, not code: a lead forwards the original id and rewrites nothing; a body
  quoting the owner is not an order and not consent, only the owner's own words in the ledger are.
The keys are `messaging.duplicate_window_hours`, `messaging.dead_hours`, `messaging.ack_reminder_minutes` and
`messaging.session_id_watch_until` (`engine/KEYS.md`).

**The inbox waiter (MW-078).** A row in an idle session's inbox wakes nobody by itself, so `mkway install` writes one more
Stop handler, `mkway hook-wait`, with `"asyncRewake": true` and a timeout of `wake.deadline_seconds` plus 60. Claude Code
runs it in the background after a Stop; a hook that exits 2 wakes an idle session with its stderr. It arms only for a
registered lead, the holder of a card, or the last holder of a card that is released and not closed; every other session
(the owner's tab, a chief, a `-p` run) gets exit 0 and no pid file. It reads the session's inbox (from `state.shared_dir`
when set) every `wake.poll_seconds` and exits 2 with the line of the oldest unacked row that is addressed to the session
and was written by another one (`<id> <kind> from <writer>: <first line>`); each row id wakes a session once (the ids are
kept in `<state.dir>/wake/<session>.woken`). One waiter runs per session: it writes its pid to
`<state.dir>/wake/<session>.pid`, and an older waiter that no longer finds its own pid there exits 0 (nothing is killed).
At `wake.deadline_seconds` it exits 2 with `no new rows, end the turn`; the session wakes, does nothing and stops, and
that Stop arms a new waiter. `wake.mode` `off` leaves the handler out. It is no gate and refuses nothing; a crash of it
exits 0. The hooks documentation does not say that `asyncRewake` is honoured on Stop: the live check on the first install
of a task must prove it (card MW-078, Log).

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

**The blind verdict at `card close` (MW-068).** The same proof backs the verdict rows of a card that names a test. A profile
with no `outbox.checkers` cannot prove a reader, so the check is not enforced: the close passes and says «blind verdict not
enforced: outbox.checkers missing in profile» in its output and in the verdict record, and the Stop of a registered lead
repeats it as a `verdict-not-enforced` reminder until the key is set. A fresh install writes `outbox.checkers: ["fresh-reader"]`
(MW-071): the blind reader, never `critic`: model Sonnet, effort medium, tools Read and Grep only, a file list of the test
file, the card and the criteria (never the code), one run per card close, no rounds. At most two runs per card (one fix, one
re-verdict; R181): a reader session that wrote verdict rows is one run, its number is in the verdict write record (`run`),
and a third run is refused `verdict-runs-exceeded` naming the two earlier ones; a further run is the lead's ledger row or a
re-cut of the card, never the owner's. The token count of the run goes in the card's Log row. Rows are needed only for the
Acceptance nodes whose test function is new or changed in the commits whose message names the card (older unchanged nodes
need none; with no git or no such commit every named node needs a row). The close refuses
a configured checker whose agent definition lists any tool beyond Read and Grep, or no tools line (`checker-not-read-only`),
and one with no definition (`checker-not-found`); the definition is `.claude/agents/<name>.md` in the task root, else the same
path in the user folder (from the environment), and its `tools:` line is read.

**The verdict command (MW-080).** A verdict row is written only by the command `mkway verdict add`: `mkway verdict add <card> <node>... <true|weak|wrong> <reason>` (several nodes in one call: repeat the node argument; one verdict word per call). The row's `by` is the caller: the session id from the lock gate's one-use permit (MW-049), never a word of the command; the owner's terminal is refused `verdict-by-owner` and a call with no permit `verdict-no-caller`. The row is written any time after the red commit (the card has a red-proof row of a commit of HEAD; with none the call is refused `verdict-no-red-proof`, and the way out is the red commit of the card's tests), while the card is `waiting` or `open`, held or not (MW-117, R272 G3 supersedes R194); a closed, a proposed or a waiting-owner card is refused `verdict-card-state`. The verdict stays bound to the test file (per node, read from git) and to the Acceptance rows of its node (the sha256 of the engine's extract, `acceptance_sha` in the record): at `card close` a test edited after the verdict reads `verdict-unproven` and a changed Acceptance row of the node `verdict-stale`, and a fresh reader run with `mkway verdict add` is the way out. A session that ever took the card is still refused as below; a session that ever took the card, not only the holder now, is refused `verdict-by-holder`, and a committer of the node's test file (the commit gate's records) `verdict-by-committer`; a node the card's Acceptance rows do not name is `verdict-node-unknown`. The proof is the reader run of MW-071, read from git, never from a file's mtime (R196): the session needs an end row of a configured checker (`outbox.checkers`) in `agents.jsonl` that started after the last commit that touched the node's test file, and the file must equal HEAD at the call, else `verdict-stale` names the two shas (`verdict-no-reader-run` when the session ran no checker at all). A run is one checker agent run; a node may use two since its last recut, a third is `verdict-runs-exceeded`, a recut node needs a run that started after the recut record (`verdict-run-before-recut`, MW-100), and calls with the same run are fine. The command writes the table row (the row of the same node is replaced; a pipe in the reason becomes `/`, a line break a space) and a `verdict-written` record in `outbox_checks.jsonl` with the row keys, the agent, its run number and the blob of each test file. The post step of the outbox gate records nothing for `tests/verdicts/<card>.md`, so a row typed with Write, Edit or MultiEdit reads `verdict-unproven` at `card close` in every gate mode, and the pre step refuses such a write `verdict-file-by-command`, a helpful message under the existing mode of `outbox_check.pre`. A profile with no `outbox.checkers`, or with `cards.verdicts` off, gets `verdict-not-enforced` naming the key. `tests.verdict_add.mode` is `trip` (the default; a missing key is `trip`) or `watch`: in `watch` a refusal is logged as a `would-refuse` row and the row is written, except `verdict-by-holder`, `verdict-by-committer`, `verdict-by-owner`, `verdict-stale` and `verdict-no-caller`, which refuse in both modes because they decide independence or make a row impossible. The command does not read git author names (the close's `verdict-by-author` stays at the close). The command's reason ids are listed in the module docstring of `engine/verdict_add.py`; only `verdict-file-by-command` is a manifest reason.

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
- the post step records the write; when it cannot, it refuses `check-record-failed`, naming the path, and the check reads `unproven` (MW-109);
- the start block has the line `outbox: N files, M unchecked`.

**What stays refused or unproven**: a document edited after the check (`stale`); the sha line of an older version
(`stale`); a check copied from another file (`stale`, or `unproven` when the text is the same, because no session wrote
it with a write tool); a check made by a shell or changed after its write (`unproven`); a checker type that is not on the
list, or no list; no agent row of that type in the session, or one that started before the last change or ended after
the check; a pattern present while the line says clean; any line in the wrong form.

**Class.** The write gate had class `form` (card MW-012): a first install started it in watch mode, where a refusal is
a `would-refuse` row and the write went ahead. Since card MW-115 it has class `integrity`: it refuses from the first
install, never starts in watch and never trips; `mkway gate watch outbox_check.pre` is refused. An old install that
holds a watch marker for it refuses at once, and the start line names the change once. The record step and the Stop
reminder never refuse and have class `integrity` too.

A Stop warning never wakes the session again (MW-075): on `Stop` a warn is printed as a `systemMessage` (shown to the
user, does not continue the turn), never as `additionalContext` or a block, so the `verdict-not-enforced` reminder costs
no turn. A refuse keeps `decision: block` and `reason`. The same Stop warn text is shown once per session; its record
row is still written at every Stop. Every other event keeps its output.

**The verdict recut (MW-100).** A weak or wrong verdict is answered by a re-cut, never by an acceptance (R251): the command `mkway verdict recut` (`mkway verdict recut <card> <node> <reason>`, one node per call) is the card's orderer's only; a card the owner ordered is refused `verdict-recut-not-lead` with the text that the owner gives the card to a lead with `mkway give`, and that lead runs the recut. It is allowed only when the node's last row is weak or wrong and a recorded reader run answers it (`verdict-recut-nothing` otherwise), once per node (`verdict-recut-exceeded`: split or withdraw the card), and only when the cut really changed: since the answered run ended (its end, read in the session of the add record that wrote the row), a commit touched the node's test file or the card's `CARD.md`, and both files equal HEAD (`verdict-recut-no-change` and `verdict-recut-stale`, which refuse in both modes, as do the independence refusals). It reuses the ids of `verdict add`: `verdict-by-holder`, `verdict-by-committer`, `verdict-by-owner`, `verdict-no-caller`, `verdict-card-state`, `verdict-node-unknown` and `verdict-not-enforced`. `tests.verdict_add.mode` applies as for `verdict add` and there is no new key: in `watch` the other refusals are logged as `would-refuse` rows and the call goes ahead; a missing key is `trip`. The command writes a `recut` row whose reason reads `answers <agent id>: <reason>`, a `verdict-recut` record in `outbox_checks.jsonl` (a recut is never a run and the lead never a reader) and one ledger row with the topic `verdict recut`. The budget is counted per node per cut: a node takes two reader runs since its last recut, counted from the agent of each record (`verdict-runs-exceeded`, at `verdict add` and at `card close`; a record with no `nodes` key counts for the nodes of the files in its `tests`, one with neither for every node of the card, one with no agent for none); after a recut `verdict add` needs a reader run that started after the recut record (`verdict-run-before-recut`). `card close` refuses a node whose last row is a recut, or whose true row is older than its last recut, as `verdict-recut-pending`, in every mode. The ids are listed in the module docstrings of `engine/core_verdict_recut.py` and `engine/verdict_recut.py`; none is a manifest reason.

**Node freshness at close (MW-101).** At `card close` a verdict row written by `mkway verdict add` stays fresh while its node's meaning is unchanged, read from git, never the file's mtime (R196, R181, R253); a stale row reads `verdict-unproven` with a text that names what changed and both blob shas, and there is no new reason id and no profile switch. The proof has two parts. The record's own `agent` must have an end row of a checker type in the record's session, ended before the record's time (a record with no `agent` is unproven; `verdict add` already checked freshness against the file from git). The node's meaning must be unchanged since the blob of its test file that the record holds: the blobs are equal, or the node's own source (function, decorators, docstring) and the non-test code of its file (module level, fixtures, helpers, imports, the other members of a class that are no test) are equal as text, so a change in another test function of the file leaves the row fresh. A blob git cannot read, a text that does not parse, a node that is not found, or a record with no blob is unproven, never guessed as unchanged. The decision is the pure `engine/core_node_fresh.py`; the git reads stay in `engine/verdicts.py`. Named gap: cross-file helpers (`tests/_*.py` kits, `conftest.py`) are not read, so a change there leaves a row fresh, closed when an incident shows it (R253). `verdict add` and the outbox are unchanged.

**The verdict file commit (MW-102).** The recommended sequence for a card is: the reader's rows are written with `verdict add`, then the orderer commits the verdict file, then the card is closed, then the status commit follows (R240). The commit gate lets the orderer of a card commit `tests/verdicts/<card>.md` of every card it ordered (its card id joins the ids the message rule looks for, as for `CARD.md`). No other session may: the holder never commits its own card's verdict file, a holder whose Paths cover another card's verdict file is refused too, and the reader holds nothing and gets no commit right; every such refusal is `file-not-in-card` (R254, R194 unchanged). A commit that takes the file runs the row proof of the close on the rows of the content the commit takes (the staged blob for a plain commit, the working file for the `-- <paths>` form): every row whose node an Acceptance row of the card names must have its record from `verdict add` (R196, MW-080), else the commit is refused `verdict-unproven`, naming the row's node and the proof text. As at close, a profile with no `outbox.checkers`, or with `cards.verdicts` off, skips the proof. The reason `verdict-unproven` is declared in the manifest entry `commit_files`; there is no new profile key, no mode and no new guard level, and no verdict logic changes (the close check is reused as it is).

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
  missing, is «not established». A failed write refuses a `SubagentStart` with `agent-record-failed`, naming the path; on a `SubagentStop` it is a visible message that names the path, never a refusal, because a block there keeps a finished agent going (MW-109).
- `agents.cap_minutes` (profile, a number above 0, default 30): the start block shows one line for each agent of the
  session that ran longer, or whose last row is a `start` row. A resumed or compacted session keeps its id, so it
  sees its agents; a new session has none yet.

## The reader's allowlist

The reader that judges a test (the checker, `fresh-reader`) reads **the test file and the Acceptance rows of the named nodes only**: the
test files of the nodes the card's Acceptance rows name, and an extract of those rows that the engine writes. It never reads the
card file or the code. Since card MW-116 the engine enforces it instead of asking for it (concept K3, rulings R272, R287c).

- **The agent.** The install writes `.claude/agents/fresh-reader.md` from the template `engine/templates/fresh-reader.md`: tools
  `Read` and `Grep`, and a `PreToolUse` hook in its own frontmatter that runs `engine/reader_hook.py` of the installed copy. A
  reinstall keeps a file that exists. The hook is no settings entry; the manifest lists it with `frontmatter: true`.
- **Start.** The spawning session runs `mkway reader start <card>` in its own shell (a plain call; the session id is the launcher's
  `MKWAY_SESSION_ID`, proved as for `mkway send`). It writes `<state>/reader_allow/<session id>.json`: the test files of the
  card's nodes and the extract (`<session id>.extract.md`, the Acceptance rows of the named nodes, from the one function
  `verdicts.acceptance_extract`), and a start row with the sha256 of the allow file in `<state>/reader_runs.jsonl`. One reader run
  at a time per session: while the list is not empty a second start is refused `reader-busy`; the way out is to wait for your own
  run or the orderer's release: `mkway reader end` empties your own list, and the owner's terminal empties a named session's
  with `mkway reader end --session <id>`. Different sessions never share a file. The lock carries the start time of the run:
  within 30 minutes (an engine constant, no profile key; ruling R295) a second start stays `reader-busy` and the way out is to
  wait (the end of the reader's run empties the list); a lock older than 30 minutes is taken over by the next start, which
  writes a record row `reader-lease-expired` that names the old run (its session, card, start time and allow file sha256).
  A lock whose start time cannot be read is never taken over.
- **The hook.** For every tool call of the reader it reads the allow file of the hook input's `session_id` (inside a subagent the
  spawning session's id; the call also carries `agent_id` and `agent_type`). `Read` and `Grep` on a listed file pass, and so does
  `SubagentHandback` (the tool that delivers the reader's report: the reader can always answer). Every other path and tool, and
  every call of a session with no usable allow file, is refused `reader-read-refused`; the text names the cause (unlisted path,
  unlisted tool, no allow file for the session, or a crash of the hook) and the way out (the listed files, or the start command).
  Every call leaves one row in `reader_runs.jsonl`, written together with the decision, naming the session, the agent, the tool,
  the path and `allow` or `refuse`; a record that cannot be written refuses the call. The hook never exits with a code other
  than 0 or 2.
- **End.** The end row of a checker agent (the `SubagentStop` record) empties the list of its session; another agent type or
  another session leaves it. The file stays, with no files.
- **The verdict.** `mkway verdict add` refuses `verdict-reader-unguarded` (in trip and in watch mode) for a reader run that has no
  allowed Read or Grep row in `reader_runs.jsonl`, or whose start row did not list exactly the card's two inputs, or that was
  started for another card, or whose extract is not the card's Acceptance rows as they are now. The verdict record carries the
  `agent` and the `allow_sha256` of the allow file the run read under. The way out: accept the trust dialog, run
  `mkway reader start <card>`, run a fresh reader, then add the verdict again.
- **The trust dialog.** Claude Code runs a project agent's frontmatter hooks only after the workspace trust dialog for the folder of
  the agent file was accepted once (sub-agents.md, «Hooks in subagent frontmatter»): «These hooks only run while that specific
  subagent is active and are cleaned up when it finishes.» and «Until you trust the folder, the subagent still runs, but Claude
  Code skips its frontmatter hooks and logs an error to the debug log explaining how to trust the folder. This is a stricter rule
  than the one for hooks in settings files: trusting a parent folder isn't enough, and a `-p` session doesn't count as trusted.»
  The install report says so. The guard is the record: a reader whose hook did not run leaves no row, so its verdict is refused.
- **Scope.** The allowlist is for the test checker only. A reader of outbox texts is out of scope of this card. No transcript is
  read (R243).

## Commit checks
A session's `git commit` is read by one gate before it runs: `commit_files`, one manifest entry and one profile
switch, `gates.commit_files` (with `vcs: none` nothing is checked; the owner's own terminal runs no hook, so nothing is
gated there). The gate judges a commit by what git will put in it, form by form: `-- <paths>` (git's `--only`, the
default when paths are named) takes the named paths alone; `-i -- <paths>` takes the staged list plus the named paths;
a plain commit takes the staged list; `-a` takes the staged list plus every modified tracked file; `--amend` follows
the same rule and adds nothing. It refuses, in this order, naming the files and the way out:
1. **Right files only** (`file-not-in-card`). Every file the commit takes must lie inside the Paths of the session's
   open card, or be always allowed: the card's own folder, the register, `<bundle.root>/ledger/` and `paths.exempt`. An
   empty Paths is no file rule; a session with no open card (none taken, or the card is not `open`) may commit only the
   always-allowed files. A file another session left staged is no fault of a `-- <paths>` commit, which does not take
   it; the start block says `staged outside your card: N` and `mkway check` says `staged files: N outside every open
   card's Paths`, as lines, never a refusal. Way out: `git restore --staged <file>` (under `-a` or `--`, the text says
   how), or add the file to the card and ask the owner to `card open` it again.
2. **One builder per task root** (`take-root-busy`, in the lock gate). A ride-in comes from two builders sharing one
   worktree and one index, so `card take` is refused while another session holds an open card in the same task root.
   The refusal names the holding session (its first 8 characters) and its card; the way out is that the holder closes
   or hands off its card, or that the builder works in its own worktree. A holder that crashed never blocks the root
   (MW-045), two ways: `card release <id>` by the owner's terminal or by the session that ordered the card (any other
   session is refused `card-not-yours`), and an automatic release at the take when the holder's last row in
   `sessions.jsonl` is older than `cards.stale_hours` (default 4; with no row, when its take is that old), which
   writes the Log row `stale holder <8 characters> released`. The same session may take its own card
   again. `mkway sessions` shows the root of each session. There is no record of who wrote a file: the gate judges
   what the commit takes, and a script's own output inside the Paths commits.
3. **No junk** (`junk-file-staged`), **no force-added ignored file** (`ignored-file-staged`): a new file that
   `git check-ignore` matches was added with `git add -f`; the ignore file is never overridden by a commit.
4. **No data files** (`data-file-staged`, by extension) and **nothing too large** (`file-too-large`). The three keys of
   the profile group `commit` replace the defaults, each alone: `commit.junk` (default `__pycache__/`, `*.pyc`,
   `.pytest_cache/`, `.pytest_tmp/`, `*.log`, `*.tmp`, `*.orig`, `*.rej`, `.DS_Store`, `Thumbs.db`; a name or glob
   matches at any depth, a trailing `/` names folders), `commit.data_patterns` (default `*.csv`, `*.tsv`, `*.xlsx`,
   `*.xls`, `*.parquet`, `*.db`, `*.sqlite`, `*.sqlite3`, `*.bak`, `*.dump`) and `commit.max_file_kb` (default `1024`).
   (`commit.message_prefix` is not a gate key: it starts the message of install's own commit, MW-035.)
   Deleting such a file is never refused. Way out: unstage it, keep the data outside the repository, or ask the owner
   to change the key.
5. **The message names the open card** (`commit-message-card`): the card's whole id, in the `ids.card_prefix` form, in
   a `-m`, a `-F -` here-document or a readable message file. On by default; `gates.commit_files.message_card.on` set
   to `false` turns this rule off and nothing else. The open card's own id counts whatever the prefix is now, and it
   may stand anywhere in the first line (`#10536 CARD-002 text`).
6. **A rule card goes in with its test** (`rule-without-test`), when the profile sets `rules.cards` and
   `rules.test_for`: see «Rule cards paired with tests» below.

The gate fails closed (`commit-unreadable`): a commit it cannot read (a folder from a variable, a carried command, an
unknown option or git form, a message it cannot read, a git read that fails or times out) is refused, and so is a
commit in a command that also runs a git subcommand that changes what is staged (`add`, `rm`, `mv`, `restore`,
`reset`, ...): the hook reads the index before the command runs, so run that command in a call of its own, then the
commit alone. A chained `git add ... && git commit ...` (or with `;`) is refused for this reason:
run them as two separate calls. A register that differs from its seal refuses `register-tampered`; the owner runs `card resync`.

Limits: the ignore check is for new files, so an edit to a file already in the repository is not refused for it; a
guard against slips, not a wall (`engine/KEYS.md` lists the keys).

## Tests before a commit
Tests before a commit, red test first, no red commit. The gate `commit_tests` (shell group, PreToolUse on Bash and
PowerShell, after the lock gate, `onFailure: block`, one profile switch `gates.commit_tests`) runs when a session
starts a `git commit`.
- **The staged tree.** The tests run on the staged tree, never on the working tree, so an untracked file cannot make
  a commit pass. The tree that is tested is the tree git will commit (card MW-060), whatever else is staged. It is
  read through `gate_commit`, the one function `commit_files` uses, so the two gates never disagree. A plain commit
  and `--amend` test the index; `-a` the index plus every modified tracked file; `-i -- <paths>`
  the index plus the named paths; `-- <paths>`, `--only` and `-o` HEAD plus the named paths as the working tree has
  them, with nothing else of the index (a file another card staged is not in it). A file that git does not track and
  that is not staged, inside a named folder too, is untracked and not in the tree: git commits none. The tree is
  built in a temporary index (the real index is never changed), exported with `git checkout-index -a -f --prefix`
  into a folder under the state dir, the suite runs there, and the folder is removed. The key of the kept result is
  the digest of the tree it built, never the index. A message-only amend (`--amend` with `--only` or `-o` and no
  paths) changes no file, so nothing is tested.
- **What runs.** The command is `tests.command`; the default is `python -m pytest -q` over the `test_roots`
  (default `tests`). The run sees the environment names of `test_env` and `ENGINE_TERMS_FILE`, the system essentials
  (the folders Python finds its installed packages in included: `APPDATA`, `LOCALAPPDATA`, `PYTHONUSERBASE`) and
  nothing else (MW-057). The engine runs only git and the profile's Python, so the first word of `tests.command` is
  that Python. A test file that fails to import or collect is shown with its first error line; when the working tree
  holds untracked files, the refusal names them (a test that needs one fails in the staged tree: stage it).
- **Red-first.** A commit whose staged files all lie under `test_roots` runs the suite and is judged by the red proof
  (below) when the session holds a card and the command is pytest; otherwise it may be red and runs no tests. Any other
  commit may not add red: see the next item. A refusal is `commit-tests-failed`; the text
  names the first 10 failing test ids and the way out: fix and stage the fix, or commit the tests alone as the
  red-first commit.
- **Only new red refuses** (card MW-056). A green staged tree passes. A red one is compared with the tree of HEAD,
  which is run once. A test that is red in the staged tree and not red at HEAD is **new red** and refuses, whoever
  owns it. A red test inside the Paths of the card that commits refuses too, unless its take recorded it red (card MW-108, below). A test red at HEAD and still red does
  not refuse when it lies in the Paths of another **open card** (only an open card owns a test; a `waiting` or
  closed card owns nothing): the commit passes and the gate answers with a warn, `commit-tests-still-red`, whose
  text reads `<test id> still red, owned by <card id>`. A test red at HEAD and still red that lies in no open
  card's Paths has **no owner**; until card MW-108 it refused, so that a card must take it, and since MW-108 it is only
  shown (below). The owner of a test is read from the file of its id. Running only the card's own tests is not an option: it would miss the breakage of others. A red run that
  names no failing test is refused as before, since old and new cannot be told apart; in a repository with no HEAD
  every red is new.
- **Absent at HEAD** (card MW-062). A red test that HEAD never collected (for example a parametrised case over
  files another card creates) is judged by the open card whose Paths hold its file: another open card's file does not
  refuse and the allow line counts the cases per owner (`40 cases absent at HEAD, owned by <card id>`); the committing
  card's file refuses; a file no open card holds refuses as new red. A test that HEAD collected and kept green is
  still new red. The runs continue past a file that fails at collection (`--continue-on-collection-errors`), so one
  such file at HEAD hides no other red test of HEAD. The ids HEAD collects are kept in `commit_tests_collect.jsonl`.
- **This commit only, with the red a card inherits** (card MW-108; concept lines 2 and 5, kind K2; rulings R270a and
  R283). A gate judges only what this commit changes: **only a new red refuses**. A test red at HEAD and still red inside
  no open card's Paths (an orphan) never refuses. One inside the committing card's Paths refuses only when the card did
  not **inherit** it: `card take <id>` writes a take row into `<state>/inherited_red.jsonl` with the red ids at HEAD that lie
  in the card's Paths. The take never runs the suite: `gate_commit_tests.head_red` (the one function that makes the list)
  reads the rows the gate kept (`commit_tests_head.jsonl`, `commit_tests.jsonl`, keyed by tree) along HEAD's history, newest
  first within 60 commits, same command, profile and reader; the nearest row decides, and an id that only an older row
  listed is recorded green. A take with no usable row is **not established**: the row says so, the take prints it and goes
  on, and the consequence is fail-closed: every red in the card's Paths counts as new red at its commits, and its close
  refuses any red in the test files of its Paths. A red in the card's Paths that the take recorded green, or holds no
  record of, is new red too; the refusal says which, and names the way out: the plain form of the red-first commit,
  `git commit -m "<card id> tests only: <what>" -- <test files>`, run alone, and for a record that is missing «the next
  merge writes the row; until then every red counts as new for this card». An old red is allowed and shown as
  `old red: <test id>, owner <card id>` (`owner none` for an orphan, with the closed card when its file failed at
  collection), the warn is `commit-tests-still-red`. The run's row in `commit_tests.jsonl` gets the key `old_red`, a list
  of `{"test": <whole id>, "card": <owner card id or null>}` in the order of the run (null: no open card owns it; the board
  of card 7 reads it); a card taken before this record existed has no take row and keeps the old rules. The orderer's
  `card close` runs the card's inherited ids with the Acceptance rows' tests; a deleted or renamed test counts as red; the
  refusal is `close-tests-failing`. `mkway card release-red <test id> --to <card id>` is the orderer's: it moves one
  inherited id to another **open** card, named, never to nobody, and writes a `release-red` row (from card, to card,
  test id, session, `by`); the first card then closes with that test red and the other card's close needs it green.
  The lock gate leaves the one-use by-permit for it, the card tool refuses with `close-not-orderer`, `card-unknown` or
  `card-bad-move`. The merge (full green, K5) and the install keep the full-green rule.
- **Same file name in two test folders (MW-079).** `tests/shell` is a package (it has an `__init__.py`); `tests/core` is
  flat, because `engine/core.py` is imported as `core` and a `tests/core` package would shadow it. A test file in
  `tests/shell` may share its name with a file of a flat folder (`tests/`, `tests/core`), never two files inside the flat ones.
- **HEAD results.** The result for the tree of HEAD is kept in `commit_tests_head.jsonl` in the state folder, one
  row per run, so a second commit on the same HEAD costs one run (the staged tree). A kept result is ignored, and
  HEAD runs again, when `tests.command` or the profile changes.
- **The key `tests.verdict_add` (MW-080).** Its one field `tests.verdict_add.mode` (`trip` or `watch`; a missing key is
  `trip`) belongs to the command `mkway verdict add`, not to this gate; see «Outbox check».
- **Docs only.** A commit whose staged files all match `paths.docs` runs no tests. The default globs are
  `<bundle.root>/cards/**`, `<bundle.root>/ledger/**` and `*.md`.
- **Budget.** A run is stopped at `gates.commit_tests.budget_seconds` (default `780`; never more than 840 s, because
  the hook timeout is 900) and the commit is refused `commit-tests-over-budget`, fail closed. The way out: the owner
  raises the budget in the profile in their own terminal, or the session shrinks the commit. A command that cannot
  start, or a git read that fails, refuses `commit-tests-not-run`.
- **The builder pings its lead (MW-076, rulings R185 to R189).** Every row the engine puts in an inbox (a `send`, a
  notice such as `card set <id> waiting` or a `card release` by the holder) is also one row of the record
  `<shared>/inbox-writes.jsonl`; a notice carries the session that caused it as `by` (the lock gate's by-permit, as
  MW-049), and with no `by` the record keeps the command and the card id for a fallback that needs the Bash call's time
  window, the command text and the card id together. A Stop of a session that is no lead is refused once,
  `ping-not-sent`, when the turn caused such a write to another session and no SendMessage call came after it: the
  reason is `ping your lead:`, the clause «if SendMessage is not loaded, load it first with ToolSearch query
  select:SendMessage», then `SendMessage to <name>: mkway inbox <id>`. The next Stop of the same turn passes
  (`stop_hook_active`, the field Claude Code documents; no counter of ours) and writes the log row and a row in
  `<shared>/ping-skipped.jsonl`, `ping-skipped`. A lead's Stop lists each such row, and each engine notice nobody pinged,
  once: «builder <name> wrote to the inbox and did not ping: read mkway inbox <id>». `mkway send` prints the same
  ready line `ping: <clause>; then SendMessage to <name>: <ping line>` when the name is known: the `name` of the lead's
  row in `leads.json`, else mkcl's sessions file named by the profile key `sessions.file` (read only: by `resumeId`, else
  the `starter` of the live builder row of the sender's card), else the ListAgents instruction stays. The profile key
  `gates.ping.mode` is `trip` (default) or `watch` (the row and the reason line, no block).
- **One run per staged tree.** The state folder `<state.dir>` gets the file `commit_tests.jsonl` with one row per run: the staged-tree hash, the
  command, the result (`pass`, `fail` or `over-budget`) and the duration. The same index with the same command does
  not run again and gives the same verdict; a changed index runs again, and so does an `over-budget` tree after the
  budget is raised.
- **Chained commands.** `git add ... && git commit` is refused `commit-tests-chained`: the index is read before the
  command runs, so it is not the tree the commit would take. Run the staging command alone, then the commit alone.
- **Not gated.** The owner's own terminal is not gated: no hook runs there. A gate that is off is named on the start
  block (`gates off:`); the engine's own tests use a tiny fixture project and never run the engine's own suite.
- **Small tests are hermetic and shuffled (MW-074, G8).** `tests/core/conftest.py` makes every test of its folder fail,
  with «hermetic test: <call> is not allowed in tests/core», when it starts a process (`subprocess.run`, `Popen`, `call`,
  `check_call`, `check_output`), opens a socket, sleeps, or opens a file for writing outside its own `tmp_path`, and
  runs the tests of that folder in a shuffled order. The run prints its seed (`hermetic seed: N`, also with `-q`);
  `--seed N` repeats an order. In-house, standard library only. The profile key `tests.hermetic_dirs` (default
  `["tests/core"]`; `[]` none) lists the folders; the engine reads it nowhere: a task owns the copy of the conftest in
  each folder it names, and the dedup profile sets `[]` until its lead decides.
- **The suite runs in parallel (MW-083, R199, R200).** `python -m pytest -n auto --dist loadgroup` runs the whole suite on
  pytest-xdist workers, with the same pass and fail set as the serial `python -m pytest` (the Log of the card holds
  both runs with three seeds each). The packages are pinned with their hashes in `tools/requirements-test.txt`; the owner
  installs them, a session never does. `-n` is never in `addopts`, so a plain run stays serial and works without
  xdist. `tests/conftest.py` sets the number of workers behind `-n auto`: half the logical cores (at least one), or the
  whole number in the environment variable `MKWAY_TEST_WORKERS`; any other text in it stops the run with «MKWAY_TEST_WORKERS
  must be a whole number above 0». The hook overrides `auto`, so `-n auto` means half the cores, and xdist's own
  `PYTEST_XDIST_AUTO_NUM_WORKERS` is ignored. The controller makes the seed once (from `--seed`, else the clock) and
  hands it to every worker, so all of them shuffle `tests/core` in one order. Every test marked `engine_repo` or
  `real_shared_state` is in the xdist group `shared_real` (by marker) and runs on one worker. Each worker has its own
  temp folder below `--basetemp`. The commit gate of the engine and the profile's `tests.command` stay serial; the
  merge runs the parallel command through the owner's policy key `test-command`.

**The shape of the tests a commit adds (MW-073, gate `tests.shape`, reason `test-shape`).** A `git commit` is judged by the
tree git will commit against HEAD (the parent of HEAD for an `--amend`, the empty tree for a first commit): only a test
function that is new or changed is judged, never a whole old file. Rules: S1 no `for`, `while` or `if` in a test body
(use `pytest.mark.parametrize`); S2 at least one `assert` or `pytest.raises`; S3 no `assert True`, `assert False`, no
`assert a and b`; S4 a one-line docstring that starts `Catches:`, `Checks:` or `Pins:`; S5 no import of another test module
(a helper that starts with `_` is allowed) and no literal that names another test file; S6 no `time.sleep`, `socket`,
`requests`, `urllib`, `http`, no absolute path literal; S7 in a test under `tests/core` the expected side of `==` is a
literal or a parametrize argument, never a call. The refusal names file, function and rule. The profile key
`tests.shape.mode` is `trip` (default) or `watch`: in watch the gate writes its row in `<state.dir>/test_shape.jsonl` and
the reason line and allows. `python engine/shape_report.py tests` is the one-off report: the test functions of a folder
that break a rule, counted per rule and per file; it is not a gate and writes nothing.
- **The red proof** (card MW-072, rulings R177 and R183). A new test must be seen to fail before the code that makes it pass.
  It applies to a session that holds a card, with a pytest command; any other command or no card leaves the commit to the
  checks above. A tests-only commit runs the suite on the committed tree, and each new test id (a test the changed test
  files define and HEAD's version of them does not, read by `ast`, no extra collection run) must be red: a failing test is red; a test file that cannot import a module the card's own Paths will create is red
  by missing that module (any other collection error, a setup error, or a file with no new test is `red-not-proven`, with
  the error line). A missing package counts as the card's own when a Paths entry lies in its folder (`src` for `src/feature.py`, R217a). A new id that passes is refused `red-not-proven`, except a `Checks:` guard beside a red id of the same
  commit, and a pin of a card whose header row `| **Kind** | refactor |` (or `migration`) is set, with a `Pins:` docstring
  and an Acceptance row that names it as pinning. The red ids are written to `red_proof.jsonl` in the state folder, by card.
  A commit with code needs that record in this root (`red-not-recorded`, one text per cause: the card has no row, so
  commit the failing tests first, alone (the gate runs them and records the red), then the code, or the code in the
  checkout where they were committed; rows exist but none belongs to a commit in the history of HEAD, so commit the code
  where the red tests were committed, or, if they were never committed, a failing test of the card first, alone; the
  search limit ran out with no row found, so a further tests-only red commit of the card renews the record; the git history of HEAD
  could not be read, so repeat the call; the card's record is searched in the WHOLE history of HEAD, however many
  commits followed the red commit, with one `git log` call, and a row of a commit that was never made counts for
  nothing; a row written before MW-130 has no `git_tree` and is found by its digest, nearest commit first, within
  3 seconds in all), and every recorded id must now pass: one that was deleted, renamed, skipped or still fails is
  `red-ids-still-red`. A new test id committed with its code is refused `test-without-red-proof` unless the record holds it
  or it is a declared pin. A red suite is still refused `commit-tests-failed` first.
  The case_map rules (card MW-090, rulings R219 to R225; refusals only, a valid line retires a recorded red id since MW-134, see below): a commit that
  stages the card's `case_map.md` has its lines judged, a documents-only commit too (it runs no suite). Only lines new
  against HEAD's file are judged (set difference on the stripped text); blank and comment lines never are. A new mapping or
  dropped line needs a decision: a match of the profile pattern `tests.red_proof.decision_pattern` in the commit message,
  and, in a root whose ledger file exists, a ledger row with that id that is not closed (withdrawn, superseded) and whose
  by is not the committing session; with no ledger file the pattern alone decides, and an empty or uncompilable pattern is
  no decision. Without one the commit is refused `case-map-no-decision`, and the text says why each named decision did not
  count. Under a decision, the left side of a mapping or dropped line must be a function-level test id of its file at HEAD
  under a test root, gone from the committed tree and in no other card's red record, else `case-map-unknown-left`; the
  right side of a mapping must be a test id of its file in the committed tree under a test root, else
  `case-map-unknown-right`; one right side appears in at most one mapping line and never names a test that exists at HEAD,
  else `case-map-merge` (write `A -> N` and `B -> dropped: merged into N, <why>`); a new line the parser reads as
  malformed, a side with a `[case]` suffix, and a left side that is not in exactly one kind of line (all mappings, a split,
  or one dropped line) are `case-map-malformed`. These five come before the reasons above, and at most ten lines are
  named per reason, the rest counted. The profile key `tests.red_proof` has two settings: `mode`, `trip` (default) or
  `watch` (the record row and the reason line, a warning, are written and the commit is allowed; it covers the five
  case_map reasons too), and `decision_pattern`, a regular expression string (a key that is present stays as written, an empty one included, an
  explicit off; a missing key reads the ledger's id form, `ids.decision_row` else `D-<n>`, when the root has a ledger file,
  and is empty when it has none; a match must stand alone, never inside a longer token). The red proof is a card
  record kept in the shared folder (`state.shared_dir`, else the state folder) under an append lock; when another writer
  holds that lock beyond the wait the gate writes nothing and refuses `shared-record-busy`: repeat the call.
  When that 3-second limit runs out after at least one row was found, the check goes on with the rows found and the
  gate allows with one warning line, `red-record-partial`, naming the count and the times of the older rows left out;
  it is not a refusal and needs no action (the commit may still be refused for another reason).
  The retirement of a recorded red id (card MW-134, rulings R347, R348, R348a). When a requirement changes after the red
  commit, a recorded id that is gone makes every code commit of the card refuse `red-ids-still-red`. The way out is explicit:
  write a line `<id> -> <new test id>` or `<id> -> dropped: <why>` in the card's `case_map.md` and commit it in a commit with
  no code file (a tests-only commit, or one that stages documents alone), whose message names a decision of the ledger that
  is not closed and that another session wrote (a session cannot retire its own failing test); then commit the code. The
  line retires the id only in that commit and never in a code commit; nothing is inferred from a missing test; an id that is
  present and fails, or whose file fails to collect (a syntax or import error), is failing and never retired; a rename's right
  side must be recorded red (earlier, or red in this commit). A left the record holds needs no presence at HEAD, and a right
  the record holds may exist at HEAD: the replacement is usually recorded red by an earlier commit. The refusals, each with
  its way out in the text: `retire-no-decision`, `retire-decision-not-in-ledger`, `retire-decision-closed`,
  `retire-decision-by-self`, `retire-no-ledger` (no ledger file: its `by` cannot be checked), `retire-right-not-red`,
  `retire-left-failing`; they replace `case-map-no-decision` for a line that would retire, and stand after the case_map ones.
  A commit that is refused for any reason, and a `watch` commit with a refusal, retires nothing. Each retired id is one
  row of `red_proof.jsonl` (card, left, right or `dropped`, decision, the decision's `by`, session, time, the commit's tree;
  no `red`, `pins` or `missing` key, so an older reader skips it) and one `notice` inbox row to the card's orderer; a notice
  that cannot be written never refuses the commit (a calls-log error row `retire-notice-failed`). A retired id that a later
  tests-only commit records red again is in the record again. `red-ids-still-red` names this way out only for an id that is
  absent (the collection ran clean and the id is not in it); an id that fails, or sits in a file that does not collect, gets
  no such text. `mkway scorecard` prints `retirements <card>: <n>`.

## Watch mode and trip
Every manifest entry has a `class`: `integrity` or `form`; an entry with no class is `integrity`. The class follows the
refusal reasons of the gate in `engine/concept.py` (cards MW-115, rulings R287a and R287c): a gate with any KIND row
(K1 to K8) is integrity; an entry whose reasons are all exit rows (tool, instruction, record) may be form. The owner-ask
gate (edit, stop and notify entries; the reminder keeps its label but follows the gate), the search gate, the outbox
write gate, the locks, the subtask gate, the commit checks, the delete gate, the card-close gate and the record gates are
integrity: they refuse from the first install, and a first install writes no watch marker for them. The form gates today
are the lead, message and ping gates (the lead gate carries kind rows and is judged by a later card). A form gate checks how a thing is written, not whether it is safe, so it may stop
blocking when it is wrong too often. An integrity gate never does. An install from before this rule that holds a watch
marker for a gate that is now integrity refuses at once, with no grace for an open card; the start line names the
change once (`changed: gate <name> was in watch and now refuses from the first call`) and the old marker is removed.
Named limit (K8): a Stop-event gate cannot be wired fail-closed, since a crashing Stop hook cannot block and Claude Code
ends the turn after eight blocks in a row; the crash path of the owner-ask Stop check allows, with an `error` row in the
calls log, a `gate-error` row in the refusal log and a start-line notice.

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

## Reminders once, the board, the scorecard and the role files (MW-112)

A reminder says its thing once. The reminders of an unacked notice (`lead-notices-unacked`), an unacked inbox item
(`inbox-unacked`), an old unacked order (`orders-unacked`) and the lead's blind-verdict notice (`verdict-not-enforced`) are
shown, and logged as one row, the first time a session meets that event; the same event at every later prompt or Stop writes
neither a line nor a row, and a new event (a new unacked item) is a new line. The unacked items stay on `mkway board` with
their age until they are acked: the reminder fires once, the board never forgets.

A trial gate has an end date. `mkway gate watch <gate>` writes `gates.<gate>.watch_until` into the profile: seven days from
today (an engine constant, no profile key), or the date of `--until YYYY-MM-DD`; every watch, first or renewed, writes a
`gate-watch` row with `gate`, `from` (the date it replaces), `until` and `session`. The start line says `watch ends <date>`,
and after the date `watch ended: <gate>: enforce or remove` with the count of the gate's would-refuse rows; a date that is
no date counts as ended. `mkway gate on <gate>` removes the date.

`mkway board` shows, under `cards:`, the old red of the last commit record with its owner card (`old red: <test> (owner
card <id>)`, read from the `old_red` key of the last row of `commit_tests.jsonl`), the uncommitted files of every open card a
session holds with the holder and the orderer (the files of a stale holder as `files of an ended session`), `card <id>: no
DONE file` for a held card whose holder sent no `result` row since it took the card, and the agent record that could not be
written until an agent row is written again (the start line carries that line too). `mkway scorecard` prints, for the task:
the refusals per reason, `a/b: real catches <a>, false blocks <b>` when the operator's `classification.jsonl` exists, the
seconds of each test run (one per tree), the hook time per call (`duration_ms` of the rows of `gate_calls.jsonl`), the asks to
the owner, and the unreadable shell writes that passed and named the state folder (the start line shows that count when it is
above zero).

The engine ships three role files, `engine/roles/lead.md`, `builder.md` and `operator.md`: one tagged line for each rule that
needs judgment and is no hook (`- [id] ...`), within the engine's budget of 40, 30 and 30 lines. The start block prints
`role file: <path>, N/<budget> lines` for each and never stops on the number. The two rows of the reason table that keep
refusing until a live incident orders otherwise (`close-row-without-test`, `take-root-busy`) have their line there; the tool
ids of card 7 (the validation errors of the card, give, deliver, built and install commands) name the correct form in the
error text and have a way-out test each, and `close-log-failed` is a hard stop that names the card file it could not write.

## Owner hold
Profile line: `locks.targets: [{"name": "hold", "paths": ["**"], "open_by_default": true}]` (profile targets only;
a built-in name with the flag is refused). Open until the owner runs, in their own terminal, `mkway hold` (a marker
file); `mkway go` removes it; the long forms are `mkway lock close hold` and `mkway lock open hold`. Closed, it stops
every session write and commit; it does not stop reading, answering, or a word in a message.
The marker is in the shared state folder; with `state.shared_dir` set, a hold reaches every worktree of the repository.

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
  register, the bundle `.gitignore` and `.gitattributes`, `mkway.lock`, and since MW-027 the engine copy and
  `.claude/settings.json`) the commit check refuses a commit that carries a change (`lock-closed-commit`), at commit
  time only; for `locks/`, the state folder and the owner's `.claude/settings.local.json` (git-ignored by Claude Code) there is no
  commit check: only the owner's review and the OS permissions remain.
- A Python write with a computed path that never names a target passes (logged `write-target-unresolved`), the same
  class as `python script.py`. `locks/` and the state folder are git-ignored, so no commit check backs them up (R44).
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
1. Make a worktree of the task's repository (or use the checkout you have) and open a terminal in the task folder.
2. Install and commit in one step, in your own terminal: `python <engine repo>/mkway.py install --from <engine repo> [--ref <tag or sha>] [--shared <absolute folder>] --commit --root <task root>`. The commit takes only the paths install writes (the settings file, the bundle's `.gitignore`, `.gitattributes`, `mkway.lock` and `engine`, and the profile when this run created it), never the cards, asks or ledger rows sessions write in the bundle, whatever else is staged; a profile that sets `commit.message_prefix` (for example `#10536`) starts the message with it.
3. Commit: already done by `--commit`. Without it, install prints one line to paste from any folder (`git -C "<root>" add <install's paths>; git -C "<root>" commit -m "mkway <version>: install" -- <install's paths>`; the root is the absolute task folder).
4. Open the lead: start Claude Code in the task folder and register the lead (`python mkway/engine/mkway.py lead add`).
5. Done: every worktree made from that commit has the copy and the hooks, with no install of its own.
```
python mkway/engine/mkway.py check
python mkway/engine/mkway.py card new "<title>"
```
`install` copies the engine's fixed file set into `<task root>/mkway/engine/` (the bundle root is the profile's
`bundle.root`, `mkway` by default) and writes `mkway/mkway.lock`, a starter `mkway/profile.json`, the folders `cards/`,
`ledger/`, `locks/`, `state/`, a bundle `.gitignore` (state, locks, bytecode and check temp folders; the engine copy is
tracked) and the hook entries into the committed `.claude/settings.json` (merged with what is there; a reinstall
replaces only mkway's own entries and strips them from an older `.claude/settings.local.json`; a per-machine
interpreter given with `--python` stays in `state/machine.json`). Every hook entry runs
`python "${CLAUDE_PROJECT_DIR}/mkway/engine/mkway.py" hook <event> --group <group>`; the path is the same in this
repository (the root launcher `mkway.py`) and in the copy. At each session start the dispatcher prints one start
block: the version, the gates, the drift check and the logged errors.
When the task folder sits below the repository top, run the commands from the task folder or pass `--root <task folder>`, and start Claude Code in the task folder (the hooks read `$CLAUDE_PROJECT_DIR`).
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
Before a tag, run the module with the perf test alone (`python -m pytest tests/test_e2e_gates.py -m perf`) and write its seconds into the release record (R172).

## Upgrade: the owner's command installs a proven-green release (MW-104)
`mkway upgrade` (`mkway upgrade --target <repo> [--root <name>] [--dry-run]`) is the owner's command: it installs the newest engine release that a
full test run has proven into one granted task root, with one ledger row (`by` = `tool:mkway-upgrade`) and one commit that
takes only the paths install printed and the ledger. It prints exactly one JSON object, also on a refusal, and exits 0 only when
`ok` is true. It is owner-only: a session's shell is refused by the lock gate and by the command itself while `CLAUDECODE` is
present. It runs the engine repository's own code (never an installed copy) and the RELEASE's own `install` and `ledger add`,
taken from a `git archive` of the chosen commit in a temp folder that is removed afterwards. It never runs a test; it only
reads what a merge recorded.

- **Modes.** The default (release mode) takes the newest tag `vN.N.N` in version order that sits on the first-parent chain of
  the release branch and is proven by a full green row; newer tags it passed over are named in the answer's checks. A narrow
  chain never proves a tag. `--from-head` is internal: it installs the engine HEAD, proven by a full row or by the narrow
  route (a chain of narrow merges back to a full-green head, every changed path covered by ONE `narrow_paths` rule).
- **`release.json`**, tracked at the engine top and read from HEAD's commit (never the working file), never installed, holds
  four keys: `branch` (the release branch), `full_command` (the command a full run must have used), `narrow_paths` (the path
  rules of the narrow route) and `narrow_command` (what a narrow run runs). Only the owner edits it. See `engine/KEYS.md`.
- **The upgrade folder** (`MKWAY_UPGRADE_DIR`, else `%APPDATA%\mkway\upgrade` on Windows, else `$XDG_CONFIG_HOME/mkway/upgrade`,
  else `~/.config/mkway/upgrade`) holds three files and must lie outside every git working tree, or be ignored by it:
  `policy.json` (the owner's grant: `target`, `root` or `roots`, `shared`; unknown keys are errors), `green.jsonl` (the green
  record, one line per merge; written only by `mkway green record`) and `updates.jsonl` (the log of every try).
- **`mkway green record`** (owner-only; `--repo --into --branch --from --sha --command --kind full|narrow [--rule] [--seconds]`)
  appends one line and never rewrites the file; `--branch` of a batch merge may list several names joined by `, `. A row
  proves a sha only when the sha, the kind, the repository, the target branch and the exact command all match.
- **The downgrade guard**: an install already at the chosen commit is up to date; a release older than the install, a diverged
  one, an install with no source commit, a lower version and a new major are refused, all with «Nothing was changed.».
- **Gap H7 (R257h).** the lock gate cannot yet hold `green.jsonl` and `policy.json`, because they lie outside the repository
  and the gate reads targets only inside the root. The owner-only refusal covers the command line, not a write to the file:
  a process outside Claude Code can still write `green.jsonl`. A follow-up card adds lock targets for absolute paths.
  Nothing of the grant or the record is travelling in git. MW-105 closes this gap.

The `upgrade` target (MW-105). The built-in never-open lock target `upgrade` guards the whole upgrade folder, which lies outside the
repository: the folder `mkway upgrade` resolves (`MKWAY_UPGRADE_DIR`, else `%APPDATA%\mkway\upgrade`, else
`$XDG_CONFIG_HOME/mkway/upgrade`, else `~/.config/mkway/upgrade`), and, when `MKWAY_UPGRADE_DIR` is set and differs, the default
folder too, so an owner-wide override never unguards the real one. Nothing in it is a session's to write: its only writers are
`mkway green record` and the owner. An edit-tool path and a shell write (a redirect, `cp`, `mv`, `tee`, `Set-Content`,
`Add-Content`, `Out-File`) are compared by real path (links, `..` and 8.3 short names resolved, case folded on Windows only; the
prefixes `\\?\` and `\\.\`, the Git Bash form `/c/...`, `~` and a `:stream` suffix read to the same path; `~` is the home that
`mkway upgrade` reads, `HOME`, then `USERPROFILE`, also after a `cd ~` or `cd ~/...`) with a separator boundary, never a bare
prefix: a path equal to the folder, below it, or one of its parent folders (`mv`, `rm -r` or `Remove-Item -Recurse` of the folder
or its parent) is refused `lock-closed-edit` or `lock-closed-shell`, with the text of a never-open target; no reason id is new,
so there is no watch switch. A glob write is judged by its literal head (the part before the first `*`, `?` or `[`): a head
folder at or below the upgrade folder, or a parent of it, is refused. A UNC path (`\\host\share\...`, `\\?\UNC\...`, an admin
share) is refused with a text that says a network path cannot be checked, decided on the raw text, so the check names no network path;
but the real path of a mapped drive is read from the disk and may touch its share, and a real path that starts with two slashes is a
network path too; a network guard entry is compared as text and never resolved; a profile list could allow it if a task ever
writes to a share. An unreadable write (a variable path) that names any
`/upgrade/` folder is refused as `/state/` is today, and says to write literal paths; `$x\green.jsonl` stays logged, a named gap,
as does a script that opens the file itself (`python -c`, `node`). A path built from `APPDATA`, `USERPROFILE`, `HOME`,
`XDG_CONFIG_HOME` or `MKWAY_UPGRADE_DIR` (`$env:X`, with the prefix `env:` read in any case on every OS, `${env:X}`, `$X`, `${X}`,
`%X%`, and the default and alternative forms `${X:-d}`, `${X-d}`, `${X:=d}`, `${X=d}`, `${X:?d}` and `${X:+w}`) is always expanded
from the environment of the call and then compared like a literal path, whatever the command does to the name: a command that
re-points one of them and then writes under it is refused on the real folder, fail-closed; the way out is to write the literal path.
In `${X:-d}`, `${X-d}`, `${X:=d}` and `${X=d}` the value of X is used when X is set (non-empty for the forms with a colon), else the
text d, expanded once more; `${X:?d}` is the value of X; `${X:+w}` is w when X is set, else empty. In a PowerShell call `$HOME` and
`${HOME}` read `HOME`, else `USERPROFILE` (R260g). A repo path written as
`//host/...` or `\\host\...` text stays a network path (decided on the raw text); the real-path rule skips a path only when its
real path lies under the repository's real path. A home that cannot be found (no `HOME`, no
`USERPROFILE`, no home folder) leaves the default folder unguarded for that call and writes one `write-target-unresolved` log line,
the folder that can be resolved stays guarded; only an absolute `MKWAY_UPGRADE_DIR` is guarded, a relative one (which `mkway upgrade`
accepts) is a named gap and the hook writes one log line when it meets one. The hook prevents accidents: on native Windows Claude Code runs
commands unsandboxed, so the OS file permissions on the folder are the real boundary. Only this folder is guarded outside the
repository; general absolute paths in a profile's lock targets stay off (R4).

Named gaps of the upgrade guard (MW-105 review). Not closed by this card; each is left to a follow-up card. `Move-Item
-LiteralPath` is not read as a write; `cmd /c` text is re-read as Bash, and its removal builtins `rd`, `del` and `erase` are
unknown to the reader; `curl -o`, `rsync` and `tar -C` stay unknown (a decided limit). A two-step symlink (a link made by one
command and written through by the next) and a hard link are not seen, because `..` is collapsed before the real path is read. A
PowerShell provider path (`FileSystem::` followed by a drive path) is read as a path of the repository. The `upgrade` target refuses by base name a
capable command that carries the word as a part of a path, such as `git switch feature/upgrade`, the same shape as `feature/state`
today; the way out is a branch name that is not a lock target's base name. The parent rule over-refuses by design: `cp x ~`,
`mkdir -p ~/.config` where the folder resolves under `~/.config`, and root globs when the repository is the home. A path that starts
with two slashes, such as `//tmp`, counts as a network path on POSIX too. A relative `MKWAY_UPGRADE_DIR` is not guarded (see above).
A `cd` inside a subshell, a group or a command substitution, a bare `cd`, and `cd "$VAR"` leave the folder unknown, so the relative
write after them is only logged. A prefix assignment (`APPDATA=/x rm ...`) is not read: the name is expanded from the environment
of the call, never from the assignment. A re-point that lands in the folder (`HOME=$HOME/.config; rm -rf "$HOME/mkway"`) is logged
only, because the path is judged on the HOME of the environment of the call, and a name missing from the environment of the call
(a `$HOME` with no `HOME` in a Bash call) is logged only. A path built by `$(...)`, by `Join-Path` or by
`[Environment]::GetEnvironmentVariable` is not expanded: the Bash substitution is logged, the two PowerShell expressions are not read
as a path at all. The operators `%`, `%%`, `#`, `##`, `//`, `/`, `^` and `,` of `${X...}` are not expanded; the path stays
unreadable and is logged only (R260g). In PowerShell `%APPDATA%` is literal text and `$APPDATA` a script variable; both are still expanded and so may be
refused, on the fail-closed side (R260d). If the home or APPDATA is on a network share, the guarded folder is itself a `//` path,
and a write outside the repository whose real path is on a share is refused as a network path, fail-closed (R260e).

Rulings: R257, R257b, R257c, R257e, R257f, R257g, R257h (card `MW-104-upgrade`).

## The concept

`engine/CONCEPT.md` is the one page every session reads first: the yardstick, the eight lines, the eight hard-gate kinds
K1 to K8, the four records R1 to R4, and the next cards. It sits under `engine/`, so the existing `engine` lock target
covers it. `engine/concept.py` is the same concept as data: one row per refusal reason id of the engine source, with its kind or
exit, the card that implements the exit, and its way-out test or its gap. Four tests in `tests/test_concept.py` keep them
true: every reason in the source has a row and every row a reason; every row is one of the eight kinds or one of the four
exits; every row has a way-out test or a gap, and the number of gaps may only shrink (`GAPS_ALLOWED`); the page holds its
parts in order. Every order names its place in the concept (card `MW-106-concept-base`).

## Fail-closed wiring (MW-109)

The hook entries of the `edit` and `shell` groups carry `onFailure: block`, and every entry's timeout is the sum of the budgets
its gates declare plus a margin (the shell entry leaves the 780 s commit-tests budget and the margin), so a crash or a timeout
of the dispatcher blocks the call and a slow gate is never cut off mid-run. `tests/test_hooks_fail_closed.py` pins this at matcher
level only (it reads the entries the install generates, never the code of a hook): the entries, the registration of every gate
the manifest turns on, and tool names as the only matchers. A failed hook refuses with the hook, the error line and the repair: run
`mkway check`, report its output to the operator; the owner repairs the settings or the engine copy. A record the engine cannot write
(`post-record-failed`, `ask-record-failed`, `check-record-failed`, `agent-record-failed` on a start) is a refusal that names the path.
The same file holds one way-out test for each K1 and K8 refusal the card touches.

The owner table (MW-107). `engine/owners.py` is one table of the file kinds: each row names one role that writes and commits the kind
(`owner`, `orderer`, `holder`, `reader`, `engine`, or `any` for the profile's `paths.exempt` and the outside-writable folders), the command that
writes it, and where it lies, built from the profile. `owner_of` (given a path and the profile) answers with the role. Three places read this one source and
keep no list of their own: the subtask gate (the card files and the exempt paths a session may always write), the lead gate (`leads.writable`:
the order files `ORDER*.md`, so also `ORDER_fix1.md`, the asks and the quote files of a card the lead ordered, and `CARD.md` while the card is
proposed) and the commit scope (an orderer commits what the table gives it, whatever the card's Paths say; any other file stays the holder's). A
path no row matches has no owner and is refused, and the text names the way out: a card whose Paths hold it, or the profile names the kind
(`paths.exempt`). Every refusal of these gates ends with the owner role and the command that writes the file. A meta test fails the suite when a
profile key that names a folder or a pattern has neither an owner row nor a stated reason. A write outside the session's root is refused for every
session, by an edit tool or by the shell, with `write-outside-root`, unless the path lies in the outside-writable list (the three folders of the
harness and the profile's `paths.outside_writable`); the text names the path as written, the root, the list and the way out: write the file inside the
root, or the owner adds the folder to `paths.outside_writable` (the profile is read at each call, so an addition counts at the next call with no
restart). The root is the install root, whether or not it is a git repository, and the start block says it in one line: `root: <path>; every path you
write starts here`. Another checkout of the same repository, a linked worktree below the root included, is outside. A registered lead has the same
reason and the same text. A shell shape the reader cannot place (a variable in a target) passes for a session, with a calls-log row
`write-target-unread`, and stays refused for a lead; a quoted `>`, a heredoc body, a path in a message, `>/dev/null`, `NUL` and `2>&1` name no write
target and pass; a command that holds one of those shapes and also a real write position outside the root is refused. The target of a delete program
is left to the delete gate, whose `delete-outside-root` text says what to do next: name the path in your DONE line; the owner removes it; every other
simple command of the same line is judged (`rm x; echo y > <outside>` is refused). A write into another session's checkout also says how a brief for
that session travels: in the orderer's own checkout, or with `mkway send`. The check is its own gate `outside` (`outside.edit` and `outside.shell`, class
integrity), after the lock check of its group, so the lock answers first at a lock target. It is hard from install, on purpose (R274a 8.6): a protected
target is a hard kind (K1), there is no watch date, and no form gate's mode (watch, off) reaches it; the open cards are not stranded because their Paths
are repository paths, inside the root by construction. `mkway upgrade` renames the old key `leads.outside_writable` in the profile in its own commit
and its dry run prints the rule and the list the task will have; a malformed old value is shown as ignored. The upgrade step checks the list first
(R274a 8.5): the lead confirms that the list holds every outside folder the open cards write, before the owner installs.

## Run the checks
```
python -m pytest -n auto --dist loadgroup
python -m pytest
```
The first command runs on workers when `tools/requirements-test.txt` is installed (the merge runs it); the second is the
serial run that works without it. The term scan needs a term file: set `ENGINE_TERMS_FILE`, or name one in `tools/term_scan.json`. Without one the
suite fails with «term list missing».
