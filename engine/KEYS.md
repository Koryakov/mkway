# Engine keys

Two lists. **Profile keys**: the 75 draft keys of the branch profile, each «in schema now» (with the schema path it
maps to) or «later (stays a knot)». **Engine defaults**: the 31 engine-default keys of the port map, one engine
constant (`lock_gate.git_builtins`, MW-003) and one engine default that is also a profile key (`locks.targets`,
MW-018), each in `defaults.json` or marked with the reason it is not.

Notes:
- «In schema now» = the keys slice 1 reads (bundle, items, gates, product checks, Python command, state folder, ids)
  plus the one per-machine slot. The later groups `ledger`, `locks`, `handback` are declared optional and
  empty in `profile.schema.json`; the group `outbox` has its three keys (MW-019).
- The Q2 frame names «statuses» under `items`; no draft key holds it today, so it is not declared (no key is invented).

## Profile keys (75)

| # | Key | Verdict | Schema path | Reason |
|---|---|---|---|---|
| 1 | `test_roots` | in schema now | `test_roots` | the close rule and the gate `commit_tests` read the test folders: a commit whose staged files all lie in them may be red (the red-first commit), any other commit needs a green run there (MW-003, MW-005); default `["tests"]` |
| 2 | `derived.root` | later (stays a knot) | - | derived-files gate; not slice 1 |
| 3 | `derived.files` | later (stays a knot) | - | derived-files gate; the render marker is also hard-wired in three files today |
| 4 | `card.id_pattern` | later (stays a knot) | - | the card layout is fixed in the engine until a second layout exists (MW-003, D-8) |
| 5 | `card.path_glob` | later (stays a knot) | - | the card layout is fixed in the engine until a second layout exists (MW-003, D-8) |
| 6 | `register.file` | later (stays a knot) | - | the register sits beside the cards; fixed in the engine (MW-003, D-8) |
| 7 | `rule.short_pattern` | later (stays a knot) | - | text-matching pattern of the downstream gate |
| 8 | `rule.in_text_pattern` | later (stays a knot) | - | text-matching pattern of the downstream gate |
| 9 | `owner_edit.name_pattern` | later (stays a knot) | - | downstream gate configuration |
| 10 | `owner_edit.dirs` | later (stays a knot) | - | downstream gate configuration |
| 11 | `owner_edit.card_globs` | later (stays a knot) | - | downstream gate configuration |
| 12 | `open.owner_pattern` | later (stays a knot) | - | a text-matching anchor in a config; downstream gate |
| 13 | `open.count_pattern` | later (stays a knot) | - | a text-matching anchor in a config; downstream gate |
| 14 | `downstream.kinds` | later (stays a knot) | - | downstream gate configuration |
| 15 | `downstream.universe` | later (stays a knot) | - | downstream gate configuration |
| 16 | `downstream.change_list` | later (stays a knot) | - | downstream gate configuration |
| 17 | `downstream.checklist` | later (stays a knot) | - | downstream gate configuration |
| 18 | `downstream.chain` | later (stays a knot) | - | downstream gate configuration |
| 19 | `downstream.delivered` | later (stays a knot) | - | task data in form; downstream gate |
| 20 | `downstream.vocabulary` | later (stays a knot) | - | holds word terms (task data in form); downstream gate |
| 21 | `locks.record` | later (stays a knot) | - | the `locks` group stays empty until the lock hooks are ported |
| 22 | `locks.names` | later (stays a knot) | - | the `locks` group stays empty until the lock hooks are ported |
| 23 | `locks.marker` | later (stays a knot) | - | the `locks` group stays empty until the lock hooks are ported |
| 24 | `outbox.dir` | in schema now | `outbox.dir` | the folder of the files made for someone outside the session (the owner, a customer); a relative path; no default: with no folder there is no outbox, no start line and no check (MW-019) |
| 25 | `outbox.id_patterns_file` | in schema now | `outbox.id_patterns_file` | a task-supplied file of regexes, one per line (blank lines and `#` lines skipped), that a checked text must not match; the engine never holds a pattern; no default: with no file there is no scan (MW-019) |
| 26 | `outbox.checkers` | in schema now | `outbox.checkers` | the agent types that may sign a check, a non-empty list of strings; no default: with none, no check is valid (MW-019) |
| 27 | `plan.always` | later (stays a knot) | - | plan gate; not slice 1 |
| 28 | `number_bases.bases` | later (stays a knot) | - | data of a product checker; no hook reads it |
| 29 | `number_bases.shapes` | later (stays a knot) | - | data of a product checker; no hook reads it |
| 30 | `customer_ids` | in schema now | `outbox.id_patterns_file` | no key of its own: a product's id patterns are lines of the file `outbox.id_patterns_file` names, so the key folds into it; default none (MW-019) |
| 31 | `decision_search.ledger` | later (stays a knot) | - | decision search tool; not slice 1 |
| 32 | `decision_search.log_file` | later (stays a knot) | - | decision search tool; not slice 1 |
| 33 | `decision_search.cache_dir` | later (stays a knot) | - | decision search tool; not slice 1 |
| 34 | `decision_search.noise_paths` | later (stays a knot) | - | decision search tool; not slice 1 |
| 35 | `decision_search.ledger_id_prefixes` | later (stays a knot) | - | decision search tool; may derive from `ids.decision_row` |
| 36 | `decision_search.process_card` | later (stays a knot) | - | decision search tool; names a card (task data in form) |
| 37 | `decision_search.standing` | later (stays a knot) | - | decision search tool; not slice 1 |
| 38 | `decision_search.source_aliases` | later (stays a knot) | - | decision search tool; not slice 1 |
| 39 | `delete.generated_state` | later (stays a knot) | - | the delete-list format becomes an engine contract first (R4(4)) |
| 40 | `bundle.root` | in schema now | `bundle.root` | the root resolver reads it; any depth |
| 41 | `registration.file` | later (stays a knot) | - | the install target is the owner's call (Q3); the installer is order 2 |
| 42 | `ledger.file` | later (stays a knot) | - | the `ledger` group stays empty until a gate that reads it is ported |
| 43 | `ledger.parts_dir` | later (stays a knot) | - | the `ledger` group stays empty until a gate that reads it is ported |
| 44 | `state.dir` | in schema now | `state.dir` | slice 1 reads the state folder |
| 45 | `knowledge.files` | in schema now | `knowledge.files` | `mkway search` reads the knowledge files after the ledger (MW-003, MW-008) |
| 46 | `gates` | in schema now | `gates` | the install reads the switch per gate |
| 47 | `product_checks` | in schema now | `product_checks` | the schema takes the branch's product checks; MW-005 makes `mkway install` register them (D-2) |
| 48 | `python.command` | in schema now | `python.command` | every generated command starts with it |
| 49 | `ids.decision_row` | in schema now | `ids.decision_row` | id forms are read by slice 1 (`ids.*`); `mkway ledger add` writes the next row id in this form (MW-008) |
| 50 | `ids.rule_card` | in schema now | `ids.rule_card` | id forms are read by slice 1 (`ids.*`) |
| 51 | `ids.work_item` | in schema now | `ids.work_item` | id forms are read by slice 1 (`ids.*`) |
| 52 | `ids.evidence` | in schema now | `ids.evidence` | id forms are read by slice 1 (`ids.*`) |
| 53 | `locks.open_files` | later (stays a knot) | - | the `locks` group stays empty until the lock hooks are ported |
| 54 | `user.settings_paths` | later (stays a knot) | - | an engine default by judgment (the platform's own layout), not a profile key; under the user's home folder (R4) |
| 55 | `user.protected_hooks` | in schema now | `user.protected_hooks` | the per-machine slot (R4(2)): optional, existence-checked, off by default |
| 56 | `lock.rules.folder` | later (stays a knot) | - | target of a lock hook; not slice 1 |
| 57 | `lock.rules.card_name_pattern` | later (stays a knot) | - | target of a lock hook; not slice 1 |
| 58 | `lock.rules.guarded_files` | later (stays a knot) | - | target of a lock hook; not slice 1 |
| 59 | `lock.rules.record_dirs` | later (stays a knot) | - | target of a lock hook; not slice 1 |
| 60 | `lock.rules_code.folder` | later (stays a knot) | - | target of a lock hook; not slice 1 |
| 61 | `lock.rules_code.whitelist_file` | later (stays a knot) | - | target of a lock hook; not slice 1 |
| 62 | `lock.code.file` | later (stays a knot) | - | its gate is off today |
| 63 | `freeze.pages` | later (stays a knot) | - | discussion freeze target; not slice 1 |
| 64 | `freeze.folder_pattern` | later (stays a knot) | - | discussion freeze target; not slice 1 |
| 65 | `handback.checkers` | later (stays a knot) | - | the `handback` group stays empty; its gate is off today |
| 66 | `cards.path` | later (stays a knot) | - | a product file reader; not slice 1 |
| 67 | `cards.before_switch` | later (stays a knot) | - | a product file reader; not slice 1 |
| 68 | `rule_source.folders` | later (stays a knot) | - | a product adapter; not slice 1 |
| 69 | `rule_source.branch_check_dir` | later (stays a knot) | - | a product adapter; not slice 1 |
| 70 | `evidence.store` | later (stays a knot) | - | an adapter to untie first |
| 71 | `evidence.adapter_path` | later (stays a knot) | - | an adapter to untie first |
| 72 | `golden.cases_file` | later (stays a knot) | - | an adapter to untie first |
| 73 | `golden.report` | later (stays a knot) | - | an adapter to untie first |
| 74 | `golden.fields` | later (stays a knot) | - | an adapter to untie first |
| 75 | `ledger.columns` | later (stays a knot) | - | the `ledger` group stays empty until a gate that reads it is ported |

Split: 12 in schema now, 63 later (changed by MW-003).

## Added keys (R8, 2026-11-09; MW-002, MW-003)

Not in the map's 75. Verdicts: «in schema now» (with its schema path), «later (stays a knot)», «proposed» (not in the schema; no code reads it), «no key».

| Key | Verdict | Schema path | Values | Reason |
|---|---|---|---|---|
| `vcs` | in schema now | `vcs` | `git` or `none`; required, no default | git is optional: with `none` every git step is off, and the start line says so (R8) |
| `ids.card_prefix` | in schema now | `ids.card_prefix` | capital letters and digits; optional, no default; `mkway install` writes `CARD` into the starter profile | the prefix of `mkway card new` (R8) |
| `gates.<name>.budget_seconds` | in schema now | `gates` | seconds (a number); the values stay «not established» until a gate needs one | the dispatcher passes it in `ctx` and logs `over-budget` (R11 point 4) |
| `gates.<name>.watch_until` | in schema now | `gates` | a date `YYYY-MM-DD`; no default (the key is absent until the owner runs `gate watch`) | written by `mkway gate watch <name>` (7 days from today, or `--until`); the start line says «watch ends <date>» and after it «watch ended: <name>: enforce or remove» with the would-refuse count; `mkway gate on <name>` removes it; a value that is no date counts as ended (MW-112, R284a) |
| `gates.trip.min_calls` | in schema now | `gates` | a whole number above 0; default `20` | the calls a form gate needs in the last 24 hours before it can trip into watch (MW-012); read under the name `trip` only |
| `gates.trip.share` | in schema now | `gates` | a number above 0; default `0.34` | a form gate trips into watch when its refusals are more than this share of its calls in the last 24 hours (MW-012); `error` rows count as neither; read under the name `trip` only |
| `cards.owner_moves` | in schema now | `cards.owner_moves` | statuses; default `["open","closed"]`; `[]` is the light mode | the moves only the owner's terminal may make (MW-003, R15 A1) |
| `cards.approver` | in schema now | `cards.approver` | `owner-only` (the default) or `orderer`; an unknown value is profile-invalid | who closes a card for a session: `owner-only` the owner's terminal only; `orderer` the session that ordered it, when it is not the holder and the card's tests pass (MW-011), and a registered lead may also `card open` a proposed card it ordered (MW-028); MW-008 adds `other-session` (MW-003) |
| `cards.verdicts` | in schema now | `cards.verdicts` | `required` (the default) or `off`; an unknown value is profile-invalid | `required`: `card close` (the owner's and the orderer's) refuses `verdict-missing`, `verdict-by-author`, `verdict-weak` or `verdict-wrong` while a test node an Acceptance row names has no good row in `tests/verdicts/<card>.md` by a reader who did not write the test (the authors of the file are the names `git log --format=%an` gives); also `verdict-by-holder` (the session that holds the card), `verdict-by-committer` (a session in the commit gate's records of the file, matched by the commit's tree sha; a file with no record is judged by the holder check alone) and `verdict-unproven` (a row counts only with the record of its own session writing it through a write tool and a fresh reader agent of an `outbox.checkers` type, the same read as the outbox; a profile that names no `outbox.checkers` is not enforced, ruling R179: the close passes and says «blind verdict not enforced: outbox.checkers missing in profile» in its output and in the verdict record, and a lead's Stop repeats it until the key is set; a fresh install writes `outbox.checkers: ["critic"]`); a card that names no node is not affected; `off` skips the check (MW-068) |
| `cards.stale_hours` | in schema now | `cards.stale_hours` | hours, a number above 0; default `4` | a holder whose last row in `sessions.jsonl` is older than this is released when another session takes a card, with a Log row `stale holder <id> released`; with no row the age of its take counts (MW-045) |
| `register.columns` | in schema now | `register.columns` | five strings for id, title, status, paths, folder, and optionally a sixth for who ordered the card; default `Id`, `Title`, `Status`, `Paths`, `Folder`, and `Ordered by` as the sixth | the register's column names are profile strings; the sixth column is written when the profile names six columns, or `cards.approver` is `orderer`, or the register already has it (MW-003, R18; MW-011) |
| `locks.targets` | in schema now | `locks.targets` | a list of `{name, paths}`; paths are repo paths or globs; default none beside the built-in targets | the profile's own lock targets, closed until the owner's `mkway lock open` (MW-003) |
| `paths.docs` | in schema now | `paths.docs` | globs; default `<bundle.root>/cards/**`, `<bundle.root>/ledger/**`, `*.md` | a commit holding only these paths runs no tests: the gate `commit_tests` reads it (MW-003, MW-005) |
| `paths.exempt` | in schema now | `paths.exempt` | globs; default none | paths the subtask gate always allows (MW-003) |
| `test_env` | in schema now | `test_env` | environment variable names; default none (`ENGINE_TERMS_FILE` always passes) | passed to the test run of the gate `commit_tests`; nothing else of the session's environment reaches the run (MW-003, MW-005) |
| `questions.files` | in schema now | `questions.files` | globs; default none | a write to a question file needs a search record, like `AskUserQuestion` (MW-003); the gate `search` reads it (MW-008) |
| `owner_ask.dir` | in schema now | `owner_ask.dir` | a repo-relative folder; default `<bundle.root>/asks` | the folder of the ask files `<name>_ask.md`; the edit gate needs `<name>_sources.md` beside each (MW-007) |
| `owner_ask.markers` | in schema now | `owner_ask.markers` | non-empty list of strings; default one marker, `Request:` | a final reply with a line that starts with a marker (after spaces and an optional `**`) must have written an ask file in the turn; the marker is config, never a word in the code (MW-007) |
| `owner_ask.sources` | in schema now | `owner_ask.sources` | non-empty list of names, no space and no colon; default one name, `ledger` | each name is a count line `<source>: N contradictions` and at least one quote line `> <source>: <verbatim>` of a `kind: substance` sources file (MW-007); the name `ledger` has its own lines: `ledger: N hits` and a `> ledger: <verbatim>` line, or `ledger: 0 hits` and `search: <record id>` (MW-008) |
| `owner_ask.max_open` | in schema now | `owner_ask.max_open` | a whole number from 1; default `1` | how many asks with `status: open` one session may have; a new ask file while the session has that many is refused `ask-already-open`: add to the open ask, or wait (MW-014) |
| `owner_ask.tool_allowed` | in schema now | `owner_ask.tool_allowed` | `true` or `false`; default `false` | `false`: the pop-up question tool `AskUserQuestion` is refused `ask-tool-off` and the text names the file route; `true`: the gate allows it, and the search gate still judges it (MW-014) |
| `notify.command` | in schema now | `notify.command` | a command line with the placeholders `{file}` (the ask file) and `{line}` (the question, the default and the deadline); default none: nothing runs | run after an ask file is written, read by the engine and never by a shell, 10 seconds at most; a failure is logged `notify-failed` and never blocks; the engine ships no channel (MW-014) |
| `leads.escalate_hours` | in schema now | `leads.escalate_hours` | hours, a number above 0; default `4` | a notice in a lead's inbox that stays unacked this long shows in `mkway leads` and in the start block of a session that is no lead (MW-017) |
| `leads.max_cards` | in schema now | `leads.max_cards` | a whole number from 1; default `5` | a lead with more cards ordered and not closed than this gets a warning line in `mkway leads`; never a refusal (MW-017) |
| `paths.outside_writable` | in schema now | `paths.outside_writable` | an array of patterns, each an absolute path or starting with `<home>/` or `<temp>/`, `*` one folder name, `**` any depth, no `..` part; default the engine's three: `<home>/.claude/projects/*/memory/**`, `<home>/.claude/plans/**`, `<temp>/claude/**` | the folders outside the session's root that every session may write (MW-103, R255, R255b; R274 moved the key from `leads` to `paths` and widened it to every session): the harness's own state, not task outputs; any other path outside the root, and any other checkout of the same repository, is `write-outside-root` for every session, in the edit tools and in a shell write; the old key `leads.outside_writable` is read as an alias until `mkway upgrade` renames it in the profile (kept until the next major, removed with it); a profile list ADDS to the three and cannot remove one; `<home>/.claude/settings*.json` and any path with a `.claude` folder followed by `hooks` match nothing, whatever the patterns say; `<home>` is the user's home, `<temp>` is `TEMP`, else `TMP`, else the system temp folder, both read at each call; paths are compared as real paths (links, `..` and 8.3 short names resolved), case-folded on Windows |
| `messaging.duplicate_window_hours` | in schema now | `messaging.duplicate_window_hours` | hours, a number above 0; default `1` | the same body (white space around it ignored) sent to a second recipient inside this window is refused `message-duplicate`; the same body to one recipient is not (MW-018) |
| `messaging.dead_hours` | in schema now | `messaging.dead_hours` | hours, a number above 0; default `12` | a session last seen (the shared `sessions.jsonl`) longer ago than this is dead: `mkway send` writes the message to `dead-letter.jsonl` and tells the sender's lead (MW-018) |
| `messaging.ack_reminder_minutes` | in schema now | `messaging.ack_reminder_minutes` | minutes, a number above 0; default `30` | a Stop with an unacked order older than this gets a reminder line `orders-unacked`; never a block (MW-018) |
| `messaging.session_id_watch_until` | in schema now | `messaging.session_id_watch_until` | a date `YYYY-MM-DD`; default empty (no expiry) | the end of the transition to the launcher's session id (MW-110): empty, or a day not yet past: a shell call whose environment has no `MKWAY_SESSION_ID` is a warn `session-id-unset`, once per session, and the call goes ahead through the one-use permit; a day already past: such a call is refused `session-id-mismatch` and the text names the launcher line; the owner sets it by hand in the profile after the launcher sets the variable; an unusable value (words, an impossible date) counts as passed (R279c: fail closed): the refusal text, the start line and `mkway check` name it |
| `gates.ping.mode` | in schema now | `gates` | `trip` or `watch`; default `trip` | the ping gate (MW-076, R185 to R188): `trip` refuses a session's Stop once when the turn caused an inbox write to another session and no SendMessage followed (the reason is the ping line with the target's name); `watch` writes the record row and the reason line but allows; a task lead sets `watch` when the gate blocks wrongly; read under the name `ping` only |
| `sessions.file` | in schema now | `sessions.file` | a path, absolute or relative to the root; default none | mkcl's `sessions.json` (R178a): the engine reads it, never writes it, to find the SendMessage name of a lead (by its `resumeId`, else the `starter` of the builder row of the sender's card); a missing or damaged file is a silent fall-back to the ListAgents line (MW-076, R185) |
| `agents.cap_minutes` | in schema now | `agents.cap_minutes` | minutes, a number above 0; default 30 | the start block lists each agent of the session that ran longer, or has a start row with no end row (MW-004) |
| `deliverables.paths` | in schema now | `deliverables.paths` | globs of result files made for others; non-empty list; default none (no deliverables, no start line) | `mkway built <path>` records where such a file came from; `card close` refuses `close-deliverable-unbuilt` for an Acceptance row that names one that was not built; may overlap `outbox.dir` (MW-020) |
| `deliverables.require_base` | in schema now | `deliverables.require_base` | globs of paths; non-empty list; default none | a file that matches needs the line `base: <sha8>` in its check file, equal to a row of `delivered.jsonl`, else `base-unknown` (MW-020) |
| `rules.cards` | in schema now | `rules.cards` | globs of rule-card files; non-empty list; default none (the check is off until both `rules` keys are set) | the id of a card is read from its file name by the form `ids.rule_card`; a commit that adds or changes a card must take its test too, else `rule-without-test` (MW-021) |
| `rules.test_for` | in schema now | `rules.test_for` | a test path that holds `{id}`; default none | the path of a card's test, `{id}` replaced by the card id; `mkway rules` lists each card with this test and the last green tree (MW-021) |
| `commit.junk` | in schema now | `commit.junk` | non-empty list of patterns; a name or glob matches at any depth, a trailing `/` names a folder; default `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.pytest_tmp/`, `*.log`, `*.tmp`, `*.orig`, `*.rej`, `.DS_Store`, `Thumbs.db` | files a commit never holds: `junk-file-staged` (MW-006) |
| `commit.data_patterns` | in schema now | `commit.data_patterns` | non-empty list of patterns, by extension; default `*.csv`, `*.tsv`, `*.xlsx`, `*.xls`, `*.parquet`, `*.db`, `*.sqlite`, `*.sqlite3`, `*.bak`, `*.dump` | data files a commit never holds, whatever `.gitignore` says: `data-file-staged` (MW-006) |
| `commit.max_file_kb` | in schema now | `commit.max_file_kb` | a number above 0; default `1024` | the largest file, in KB, a commit may hold: `file-too-large` (MW-006) |
| `commit.message_prefix` | in schema now | `commit.message_prefix` | a string of letters, digits and `# _ . : / -`, no spaces; default none | the start of the install commit message, for example `#10536`: `<prefix> mkway <version>: install` (MW-035) |
| `tests.command` | in schema now | `tests.command` | the whole command line of the run, roots included; its first word is the profile's Python (the engine runs only git and the configured Python); default `python -m pytest -q` followed by the `test_roots` | the gate `commit_tests` runs it in the exported staged tree before a session's commit (MW-005) |
| `tests.shape.mode` | in schema now | `tests.shape.mode` | `trip` (the default) or `watch`; any other value reads as `trip` | the gate `tests.shape` judges the shape rules S1 to S7 on the test functions a commit adds or changes: `trip` refuses `test-shape`; `watch` writes its row in `test_shape.jsonl` and the reason line and allows (MW-073) |
| `gates.commit_tests.budget_seconds` | in schema now | `gates` | seconds (a number above 0); default `780`; the manifest hook timeout is 900, so a run is stopped at 840 s at most | a run over it refuses the commit (`commit-tests-over-budget`); the owner raises it in the profile in their own terminal (MW-005) |
| `delete.max_backup_mb` | in schema now | `delete.max_backup_mb` | a number above 0; default `5120` | the largest backup, in MB, a delete may make before it runs; above it the delete is refused `delete-too-large` (MW-009) |
| `delete.sql_allowed` | in schema now | `delete.sql_allowed` | a boolean; default `false` | `true` turns off the refusal of destructive SQL `delete-sql`, for a task with a scratch database (MW-009) |
| `tests.verdict_add.mode` | in schema now | `tests.verdict_add.mode` | `trip` or `watch`; default and missing key: `trip` | the refusals of `mkway verdict add`: in `trip` every refusal blocks; in `watch` a refusal other than `verdict-by-holder`, `verdict-by-committer`, `verdict-by-owner`, `verdict-stale` and `verdict-no-caller` is logged as a `would-refuse` row and the row is written (those five decide independence or make a row impossible, so they refuse in both modes); not in `defaults.json` (MW-080, R196a) |
| `state.shared_dir` | in schema now | `state.shared_dir` | an absolute path; default unset: the shared files live in the root's own `state.dir` | opt-in (MW-026): the folder of the files that cross worktrees (`leads.json`, `inbox/`, `sessions.jsonl`, `pings.jsonl`, `dead-letter.jsonl`, lock markers); the owner sets it, or `mkway install --shared <path>` writes it; the engine never maps the root to another worktree by itself; not absolute = ignored; a task that uses worktrees sets `state.shared_dir`; without it card records, like the inbox and the locks, are per checkout (MW-129: the red proof is a card record, `mkway upgrade` copies the old rows into the shared folder) |
| `lock_gate.git_builtins_extra` | in schema now | `lock_gate.git_builtins_extra` | an array of git command names; default none | MW-031: names added to the engine list `lock_gate.git_builtins`, for a git that has a built-in the list lacks; `mkway check` shows those names as info and names this key; the gate then lets `git <name>` through the form reader |
| lock marker folder | no key | - | `<shared state dir>/locks/<name>.json`, the shared state folder of `profiles.shared_state_dir` (the root's own state folder unless `state.shared_dir` is set); an older `<bundle.root>/locks/<name>.json` is still read for one version, closed wins | with `state.shared_dir` set, the hold and every lock target reach every work tree that names the same folder (MW-022, MW-026) |
| `bundle.track_copy` | proposed | - | `true` or `false`; `false` would keep today's behaviour | tracking the engine copy is the owner's call per project (R9); with `true`, `mkway install` would leave `engine/` out of the bundle's ignore lines. Proposed by the MW-002 order; not built |
| profile location | no key | - | by convention `<root>/mkway/profile.json`, or `--profile <path>` (a relative path is read from the root) | no profile key holds the profile's location (MW-002 closes the earlier «not established») |
| `tests.hermetic_dirs` | in schema now | `tests.hermetic_dirs` | a list of folder paths; default `["tests/core"]`; `[]` means none | the folders whose small tests are hermetic and run shuffled: a test there that starts a process, opens a socket, sleeps or writes a file outside its tmp_path fails «hermetic test: <call> is not allowed in <folder>»; the folder holds a `conftest.py` that is a copy of the engine's `tests/core/conftest.py`, and the task owns that copy (the engine reads this key nowhere; `[]` is the dedup profile until its lead decides) (MW-074, R177) |
| `wake.mode` | in schema now | `wake.mode` | `on` or `off`; default `on` | the inbox waiter (MW-078): `on` installs the Stop handler `hook-wait` (`asyncRewake`) that wakes an idle lead or card holder when a new row reaches its inbox; `off` leaves it out and the command exits at once; nothing is ever refused |
| `wake.deadline_seconds` | in schema now | `wake.deadline_seconds` | seconds, a whole number above 0; default `14400` | how long one waiter waits; at the deadline it exits 2 with the line `no new rows, end the turn`, the session wakes, does nothing and stops, and the Stop arms a new waiter; `mkway install` sets the hook timeout to this plus 60 (MW-078) |
| `wake.poll_seconds` | in schema now | `wake.poll_seconds` | seconds, a number above 0; default `5` | the pause between two looks at the inbox and at the waiter's pid file (MW-078) |
| `tests.red_proof.mode` | in schema now | `tests.red_proof.mode` | `trip` or `watch`; default `trip`; any other value is refused by the schema and read as `trip` | `trip`: the commit gate refuses with `red-not-proven`, `red-ids-still-red`, `red-not-recorded` or `test-without-red-proof` (and, since MW-090, the five `case-map-*` ids); `watch`: it writes the record row and the reason line (a warning) and allows; a task lead sets `watch` if the gate blocks wrongly on first live use (MW-072) |
| `tests.red_proof.decision_pattern` | in schema now | `tests.red_proof.decision_pattern` | a regular expression string; a key that is present stays as written, an empty one included (an explicit off, it stays off); a missing key reads `ids.decision_row` when the root has a ledger file, else the ledger's default form `D-\d+`; no ledger file: empty; a value that is not a string or does not compile means no decision | the matches of the pattern in a commit message are the decisions it names, and a match must be a whole id (no word character or hyphen directly before or after it); a line of the card's `case_map.md` that is new against HEAD is honoured only in a commit that names a decision that counts (in a root with a ledger file: a row that is not closed and not by the committing session; with no ledger file the pattern alone decides), else the gate refuses `case-map-no-decision`; since MW-134 a valid line whose left id the card's red record holds retires that id in a commit with no code file, and then the decision must be a ledger row (`retire-*` reasons); in `watch` mode a refusal is a warning (MW-090, R222, R225; MW-134, R347, R348a) |

Defaults the dispatcher falls back to when the profile is missing or its value is unusable: `bundle.root` = `mkway`,
`state.dir` = `mkway/state`. Both keys stay required in the schema; `mkway install` writes these values into the
starter profile. The engine copy is `<root>/<bundle.root>/engine/`.

Decided (R279, 16.11): `SESSION_ENV` is the engine's contract with the launcher, the name of the variable (`MKWAY_SESSION_ID`) the launcher sets: it stays a module constant of the engine and is not a profile key, so no key is looked for to change it. The variable is never the proof of a session alone: the lock gate's one-use permit is; `messaging.session_id_watch_until` also ends the time in which a messaging command takes the variable without a permit (`session-id-unverified` after it).

Decided (R64, 10.11): while the profile is invalid, every edit and shell call of a session is refused; the refusal
carries the schema error (key path and message) so the session can tell the owner exactly what to fix; the owner fixes
it in their editor or terminal, where no hook runs; `mkway check` prints the same error. The profile file has no
exemption: it is a built-in lock target. Every engine writer of the profile validates its result before it replaces
the file (card MW-003, C53).

## Engine defaults (32)

Values read at the pin on 2026-11-09 (the read form was allowed by the owner). A value that is a host name, a
path or folder name of the source task, a product name or natural-language text is not copied: it stays later.

A defaults.json key that is not in the schema is an engine constant: the profile cannot set it, and `profile-invalid` names such an attempt (R12 point 4, retro-chief10, 09.11).

| Config | Key | Verdict | Reason |
|---|---|---|---|
| `bash_speed_guard` | `marker` | later (names a process-rule id of the source task) | the value's prefix is the source's rule id; a neutral marker is the engine's choice when the speed guard is ported |
| `bash_speed_guard` | `sleep_limit_seconds` | in defaults.json | read at the pin |
| `quality_gate` | `operators` | in defaults.json | read at the pin |
| `quality_gate` | `compare` | in defaults.json | read at the pin |
| `quality_gate` | `max_mutants` | in defaults.json | read at the pin |
| `quality_gate` | `budget_seconds` | in defaults.json | read at the pin |
| `quality_gate` | `workers` | in defaults.json | read at the pin |
| `quality_gate` | `cpu_reserve` | in defaults.json | read at the pin |
| `quality_gate` | `temp_dir` | in defaults.json | read at the pin |
| `quality_gate` | `max_equivalent` | in defaults.json | read at the pin |
| `quality_gate` | `mutant_timeout_min` | in defaults.json | read at the pin |
| `quality_gate` | `mutant_timeout_factor` | in defaults.json | read at the pin |
| `quality_gate` | `listed_max` | in defaults.json | read at the pin |
| `quality_gate` | `equivalent_prefix` | in defaults.json | read at the pin |
| `quality_gate` | `acceptance_heading` | in defaults.json | read at the pin; names the `Acceptance examples` heading of the one-page card form, which the engine template now is (R12); nothing reads it in MW-001 (`quality_gate` is off-today) |
| `st_tests` | `budget_seconds` | in defaults.json | read at the pin |
| `st_tests` | `startup_margin_seconds` | in defaults.json | read at the pin |
| `st_tests` | `shared_run_max_cmdline` | in defaults.json | read at the pin |
| `outbox_check` | `check_suffix` | in defaults.json | read at the pin |
| `outbox_check` | `artifact_hosts` | later (a host name; needs an owner read) | the value is a host name, which the NDA list excludes |
| `outbox_check` | `write_tools` | in defaults.json | read at the pin; the platform's tool names |
| `outbox_check` | `shell_tools` | in defaults.json | read at the pin; the platform's tool names |
| `outbox_check` | `lines` | in defaults.json | read at the pin; the check-file line format |
| `decision_search` | `log_env` | in defaults.json | read at the pin |
| `decision_search` | `cache_env` | in defaults.json | read at the pin |
| `decision_search` | `noise_dir_names` | later (folder names of the source task) | the list names data folders of the source task |
| `decision_search` | `noise_files` | later (file paths of the source task) | the list names files of the source task's bundle |
| `decision_search` | `noise_suffixes` | later (names a database product; needs an owner read) | one suffix is a database product's name |
| `decision_search` | `formats` | in defaults.json | read at the pin; the ledger and record-key format |
| `decision_search` | `language` | later (natural-language content; needs an owner read) | natural-language text at the pin; never copied |
| `decision_search` | `texts` | later (natural-language content; needs an owner read) | natural-language text at the pin; never copied |
| `locks` | `targets` | in defaults.json | an engine default of MW-018, not from the port map: the lock target `inbox` (`<state.dir>/inbox/**` and `<state.dir>/pings.jsonl`, `<state.dir>` taken at the profile's state folder), closed like every lock, so only `mkway send` and `mkway ack` write the rows; the key is in the schema too, so a profile adds its own targets beside it, and a profile target named `inbox` is ignored |
| `lock_gate` | `git_builtins` | in defaults.json | an engine constant (MW-003 close-fix 8, R90), not from the port map: git's built-in commands; a subcommand not in it refuses `command-unparsed`. MW-031: the first list plus a git's `--list-cmds=builtins`, without the internal helper `env--helper`; `mkway check` compares it with that command in the owner's terminal and warns only on a name in the list that this git lacks (the gate would trust it as a built-in; fix: update mkway); a name only in git is an info part of the line (an over-refusal, safe; allow it with the profile key `lock_gate.git_builtins_extra`) |
| `wake` | `mode` | in defaults.json | an engine default of MW-078, not from the port map; the key is in the schema too |
| `wake` | `deadline_seconds` | in defaults.json | an engine default of MW-078, not from the port map; the key is in the schema too |
| `wake` | `poll_seconds` | in defaults.json | an engine default of MW-078, not from the port map; the key is in the schema too |
| `paths` | `outside_writable` | in defaults.json | an engine default of MW-103 (R255b), not from the port map: the three narrow patterns of the harness's own state folders; the key is in the schema too, a profile adds to the list |

Split: 30 in `defaults.json`, 7 later, 0 not established (`locks.targets` is the engine's own default of MW-018; the three `wake` keys are those of MW-078; `paths.outside_writable` is that of MW-103, moved from `leads` by R274).

## release.json keys (MW-104)

`release.json` is a file at the top of the engine repository, not a profile: it is tracked, never installed (it is not in the
install set), and read by `mkway upgrade` from HEAD's commit, never from the working file. Exactly four keys; an unknown or
missing key is a refusal. Only the owner edits it.

| key | value | meaning |
|---|---|---|
| `branch` | a branch name | the release branch: the engine must be on it, a tag must lie on its first-parent chain, and a green row's `into` must equal it |
| `full_command` | a command line, or a list of words | the full test run a green row must have used, compared as its display form (the words joined by spaces, a word with white space or a quote wrapped in double quotes). It is distinct from the profile key `tests.command`, which is the commit gate's run in a task copy and never read here |
| `narrow_paths` | a non-empty list of non-empty lists of path patterns | the narrow route's rules: a pattern is an exact path or a folder with a trailing `/**`, case-sensitive, forward slashes; ONE rule must cover every path changed since the full-green head |
| `narrow_command` | a command line, or a list of words | the narrow test run a mkcl merge of such a change runs; read for the record, not run by the upgrade |

