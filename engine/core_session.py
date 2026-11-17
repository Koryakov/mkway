"""The pure core of the session family's gates (card MW-066): the subtask gate, the lead gate, the message gate, the
records step of the `post` group and the agent records. Each decision is a pure function of a `Facts` record the shell
built and returns a `Verdict`; the shell (`gate_subtask`, `gate_lead`, `gate_message`, `gate_records`, `gate_agents`)
reads the register, the records, the leads file, the inbox and the hook input, calls the decision, and writes what the
verdict says.

This module reads nothing: no file, no process, no environment, no clock. `tests/core/test_session_decide.py` fails if
it imports an I/O module, and every table test of it runs under a guard that fails on any disk, process or clock access.
`helpers` is the one engine module it imports: `helpers.matches` is a pure function on text.

A fact the shell could not read is passed as what it is (an empty set, `None`), never as an exception. The verdict is
data: allow, refuse(reason, text) or allow-with-line(reason, text) (the gate's warn), and `records`, the rows the shell
writes. No task name and no natural-language word list is in this file.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

import helpers

CLI = "python mkway/engine/mkway.py"
SHOWN = 5  # items named in one reminder; the rest are counted
PATH_KEYS = ("file_path", "notebook_path", "path")
SEND_TOOL = "SendMessage"
PING_PREFIX = "mkway inbox "
ID_PATTERN = r"[A-Za-z0-9][A-Za-z0-9._-]*"
PING_LINE = re.compile(re.escape(PING_PREFIX) + "(" + ID_PATTERN + ")")
OK_LINE = re.compile(r"^mkway-ok (\S+) (.+) ([0-9a-f]{32})\s*$", re.M)
_VARIABLE = re.compile(r"[$`%(){}]")
_GLOB = re.compile(r"[*?\[]")

SUBTASK_REASONS = ("no-open-card", "register-tampered", "card-not-open", "card-paths-changed", "file-not-in-card")
OUTSIDE_REASONS = ("write-outside-root",)  # MW-107 (R274e): the outside check is the gate `outside`, not the subtask gate's
LEAD_REASONS = ("lead-no-edit", "lead-no-take", "lead-notices-unacked", "write-outside-root")
OWNER_NOTE = "Owner table:"  # MW-107: the sentence of `owners.describe` is appended to a refusal after this label
WAY_OUT_OUTSIDE = ("write the file inside {root}; a file the task needs elsewhere is a folder the owner adds to "
                   "paths.outside_writable")  # = owners.WAY_OUT_OUTSIDE (R274 5.3); `{root}` is the root, or "your root"
WAY_OUT_CHECKOUT = ("For a brief or an order for a builder session: write it in the orderer's own checkout (the card folder, "
                    "committed before the worktree is made) or send it with `mkway send`; never write into another session's "
                    "checkout.")  # R274a 8.4: said after the R274 text when the path lies in another checkout of the same repository
MESSAGE_REASONS = ("message-duplicate", "inbox-unacked", "orders-unacked", "session-id-mismatch", "session-id-unset")  # MW-110: message-not-in-inbox is removed
# The one place that names the launcher's variable (MW-110): the shell passes it in as a fact, the decision holds no literal.
SESSION_ENV = "MKWAY_SESSION_ID"
LAUNCHER_FLAG = "--session-id"
WATCH_KEY = "messaging.session_id_watch_until"  # the profile key of the end date, named in the texts that refuse
RECORD_REASONS = ("post-record-failed",)
AGENT_REASONS = ("agent-record-failed",)

ALLOW, REFUSE, ALLOW_LINE = "allow", "refuse", "allow-with-line"


@dataclass(frozen=True)
class Verdict:
    """allow | refuse(reason, text) | allow-with-line(reason, text), plus the rows the shell writes: `records` is a tuple
    of (what, row dict), `what` one of `ping`, `record`, `ordered`."""
    kind: str = ALLOW
    reason: Optional[str] = None
    text: str = ""
    records: tuple = ()

    def __post_init__(self):
        if self.kind not in (ALLOW, REFUSE, ALLOW_LINE):
            raise ValueError(f"unknown verdict kind: {self.kind!r}")
        if self.kind != ALLOW and not (self.reason and self.text):
            raise ValueError("a refuse or an allow-with-line needs a reason and a text")


def allow(records: tuple = ()) -> Verdict:
    return Verdict(ALLOW, records=records)


def refuse(reason: str, text: str) -> Verdict:
    return Verdict(REFUSE, reason, text)


def allow_with_line(reason: str, text: str) -> Verdict:
    return Verdict(ALLOW_LINE, reason, text)


def _plural(n: int, noun: str) -> str:
    return f"{n} {noun}{'s' if n != 1 else ''}"


def _noted(text: str, notes, key) -> str:
    """MW-107: the refusal text with the owner note of `key` (a path) after it, when the shell gave one."""
    note = notes.get(key) if key is not None and notes else None
    return f"{text} {OWNER_NOTE} {note}" if note else text


def readable_path(raw: str) -> bool:
    """True when a shell path holds no variable, substitution or wildcard, so the gate can place it."""
    return not (_VARIABLE.search(raw) or _GLOB.search(raw))


# ---- the subtask gate ---------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class SubtaskFacts:
    """One edit-tool call. `paths`: the repository-relative form of each path key of the tool input, in key order (None:
    outside the repository). `card_files`: the glob of the card files; `exempt`: the profile's `paths.exempt`;
    `lead_may_write`: the paths a registered lead of this session may write (empty for a session that is no lead);
    `card_id`: the card this session holds by its latest `take`; `register_problem`: why the sealed register cannot be
    trusted (None when sound); `card_found`, `card_status`, `recorded`: the register row of the card (its Paths as a set);
    `now_paths`: the Paths set of the card file now (None when the file could not be read). MW-107: a path that is None (outside the
    root) is no business of the card rules: the outside gate judges it (R274e). `owner_notes`: {repository path: the owner
    table's sentence}."""
    paths: tuple = ()
    card_files: str = ""
    exempt: tuple = ()
    lead_may_write: frozenset = frozenset()
    card_id: Optional[str] = None
    register_problem: Optional[str] = None
    card_found: bool = False
    card_status: Optional[str] = None
    recorded: frozenset = frozenset()
    now_paths: Optional[frozenset] = None
    owner_fix: str = ""
    report_route: str = ""
    cli: str = CLI
    owner_notes: Mapping = field(default_factory=dict)


def _free(facts: SubtaskFacts, rel) -> bool:
    """The paths no card rule applies to: outside the repository, the root itself, a card file, an exempt path, and a
    path a registered lead may write (its order file and the asks folder)."""
    if rel is None or rel == ".":
        return True
    if facts.card_files and helpers.matches(rel, facts.card_files):
        return True
    if any(helpers.matches(rel, e) for e in facts.exempt):
        return True
    return rel in facts.lead_may_write


def pending(facts: SubtaskFacts) -> tuple:
    """The paths the card rules still have to judge. The shell asks it with the cheap facts first: a call with none left
    needs no register, no records and no card file."""
    return tuple(rel for rel in facts.paths if not _free(facts, rel))


def outside_refusal(record, outside_list, root="") -> Verdict:
    """MW-107 (R274 5.3): a write whose target lies outside the session's root and that the shell did not match against the
    outside-writable list: one reason and one text for every session, a lead included: the path as written, the root, the
    list and the way out. A path with no record is refused too, so a shell that forgot the fact never opens the gate."""
    listed = "; ".join(outside_list) or "none"
    raw = record.raw if record is not None and record.raw else "a path outside the root"
    where = root or "your root"
    more = f" {WAY_OUT_CHECKOUT}" if record is not None and record.checkout else ""
    return refuse("write-outside-root", f"{raw} is outside your root ({where}): a session writes only inside its root and in "
                                        f"these folders: {listed}. Way out: {WAY_OUT_OUTSIDE.format(root=where)}{more}")


def decide_write_outside(paths, records, outside_list, root="") -> Optional[Verdict]:
    """The refusal for the first path of `paths` (repository form, None outside the root) that lies outside the root and has
    no matched record in `records` (one per None path, in order); None when every outside path is matched."""
    found = iter(records)
    for rel in paths:
        if rel is None:
            record = next(found, None)
            if record is None or not record.matched:
                return outside_refusal(record, outside_list, root)
    return None


def decide_subtask(facts: SubtaskFacts) -> Verdict:
    """The subtask gate (entry `subtask`): an edit inside the root needs an open card whose Paths name the file. A path
    outside the root is the outside gate's (`decide_write_outside`, MW-107, R274e). Refuses `no-open-card`,
    `register-tampered`, `card-not-open`, `card-paths-changed`, `file-not-in-card`; everything else is allowed. An empty
    `Paths` means no file rule. The first path the rules refuse decides."""
    for rel in facts.paths:
        if _free(facts, rel):
            continue
        verdict = _card_rules(facts, rel)
        if verdict is not None:
            return verdict
    return allow()


def _card_rules(facts: SubtaskFacts, rel: str) -> Optional[Verdict]:
    cli, card_id, notes = facts.cli, facts.card_id, facts.owner_notes
    if not card_id:
        return refuse("no-open-card", _noted(f"{rel}: this session holds no card. Write one with `{cli} card new "
                                             f"<title>` and take it with `{cli} card take <id>`; the owner opens it. "
                                             f"{facts.report_route}", notes, rel))
    if facts.register_problem:
        return refuse("register-tampered", f"{facts.register_problem}; nothing is edited until the owner checks it: "
                                           f"{facts.owner_fix}")
    status = facts.card_status if facts.card_found else "not in the register"
    if status != "open":
        how = (f"the owner's `{cli} card open {card_id}`" if status != "waiting"
               else f"`{cli} card set {card_id} open` (or the owner's `card open {card_id}`)")
        return refuse("card-not-open", f"{rel}: {card_id} is {status} in the register; edits need it open: "
                                       f"{how}. {facts.report_route}")
    recorded = facts.recorded
    if facts.now_paths != recorded:
        return refuse("card-paths-changed", f"{rel}: the Paths of {card_id} differ from the set the owner's "
                                            f"`card open` recorded ({'; '.join(sorted(recorded)) or 'none'}); "
                                            f"restore them, or ask the owner to run `{cli} card open "
                                            f"{card_id}` again")
    if recorded and not any(helpers.matches(rel, e) for e in recorded):
        return refuse("file-not-in-card", _noted(f"{rel} is not in the Paths of {card_id} "
                                                 f"({'; '.join(sorted(recorded))}); add it to the card and ask the "
                                                 f"owner to `card open {card_id}` again, or write a new card", notes, rel))
    return None


# ---- the lead gate ------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class OutsideRecord:
    """One path outside the repository, as the shell decided it (MW-103): `raw` the path as written, `abs` its absolute
    form, `matched` true when `abs` is in the list of folders a lead may write outside the repository and is not caught
    by the shell's deny. The core never reads a folder: it takes `matched` as given. `checkout` (MW-107, R274a 8.4): the path
    lies in another checkout of the same repository, so the refusal also says how a brief for that session travels."""
    raw: str = ""
    abs: str = ""
    matched: bool = False
    checkout: bool = False


@dataclass(frozen=True)
class LeadFacts:
    """What the lead gate reads. `is_lead`: the session id is in the registry of leads. Edit: `paths` as in
    `SubtaskFacts`. Shell: `takes_card` (an engine call `card take` is in the command), `writes` ((raw path, repository-
    relative form or None), ...) the paths the command may write, `writes_anywhere` (the reader found a computed path, a
    variable, or a program that can write anywhere). `writable`: the repository paths this lead may write. `ask_dir`:
    the asks folder. Outside the repository (MW-103): `outside` one `OutsideRecord` for each path of `paths` or `writes`
    whose repository form is None, in the same order; a path with no record is refused. `outside_list`: the expanded
    list of folders the shell matched against, printed in the refusal. Remind: `unacked`: the unacked notices of the
    lead's inbox, ({id, body}, ...)."""
    is_lead: bool = False
    paths: tuple = ()
    writable: frozenset = frozenset()
    ask_dir: str = ""
    takes_card: bool = False
    writes: tuple = ()
    writes_anywhere: bool = False
    unacked: tuple = ()
    outside: tuple = ()
    outside_list: tuple = ()
    notes: Mapping = field(default_factory=dict)  # MW-107: {repository path: the owner table's sentence}
    root: str = ""  # MW-107 (R274): the session's root as a real path, printed in an outside refusal


def _allowed(facts: LeadFacts) -> str:
    return (f"`<card folder>/ORDER.md` of a card it ordered, `<card folder>/CARD.md` of a card it ordered while the "
            f"card is proposed (after `mkway card open` the card commands or the owner change it), and the asks "
            f"folder `{facts.ask_dir}`")


def _no_edit(facts: LeadFacts, what: str) -> Verdict:
    return refuse("lead-no-edit", _noted(f"{what}: a lead orders work and does not do it; it writes only {_allowed(facts)}. "
                                         f"Write the order there and hand the work to a builder (`mkway card new "
                                         f"<title>`), or the owner ends the lead role with `mkway lead remove "
                                         f"<id-prefix>` in their own terminal", facts.notes, what))


def _outside(facts: LeadFacts, record: Optional[OutsideRecord]) -> Optional[Verdict]:
    """A path outside the repository (MW-103, R274 5.6): refused unless its record says the shell matched it against the list,
    with the common reason and text of every session; a path with no record is refused, so a shell that forgot the fact never
    opens the gate."""
    if record is not None and record.matched:
        return None
    return outside_refusal(record, facts.outside_list, facts.root)


def decide_lead_edit(facts: LeadFacts) -> Verdict:
    """Entry `lead.edit`: a registered lead writes only what `facts.writable` holds; any other path inside the
    repository is `lead-no-edit`. A path outside the repository is `lead-no-edit` unless its record is matched
    (MW-103). A session that is no lead is not judged."""
    if not facts.is_lead:
        return allow()
    records = iter(facts.outside)
    for rel in facts.paths:
        if rel is None:
            verdict = _outside(facts, next(records, None))
            if verdict is not None:
                return verdict
            continue
        if rel == "." or rel not in facts.writable:
            return _no_edit(facts, rel)
    return allow()


def decide_lead_shell(facts: LeadFacts) -> Verdict:
    """Entry `lead.shell`: a registered lead's command may not `card take` (`lead-no-take`), and may write only
    `facts.writable` (`lead-no-edit`) and the outside paths whose record is matched (MW-103); a write the reader cannot
    read, a glob or a variable path is refused first."""
    if not facts.is_lead:
        return allow()
    if facts.takes_card:
        return refuse("lead-no-take", "a lead orders work and holds no card: `mkway card take` is the builder's "
                                      "command. Hand the work to a builder session (write its order, then `mkway "
                                      "card new <title>`), or the owner ends the lead role with `mkway lead remove "
                                      "<id-prefix>` in their own terminal")
    records = iter(facts.outside)
    for raw, rel in facts.writes:
        if _VARIABLE.search(raw) or _GLOB.search(raw):
            return _no_edit(facts, f"{raw} (a path the gate cannot read: write a plain path with no variable or wildcard, or "
                                   f"use the edit tool)")
        if rel is None:
            verdict = _outside(facts, next(records, None))
            if verdict is not None:
                return verdict
            continue
        if rel == "." or rel not in facts.writable:
            return _no_edit(facts, rel)
    if facts.writes_anywhere:
        return _no_edit(facts, "this command may write anywhere (a computed path, a variable, or a program that can "
                               "write anywhere)")
    return allow()


def decide_lead_remind(facts: LeadFacts) -> Verdict:
    """Entry `lead.remind` (the prompt): a registered lead with unacked notices is reminded, never blocked."""
    if not facts.is_lead or not facts.unacked:
        return allow()
    rows = facts.unacked
    text = " | ".join(f"{r.get('id')}: {r.get('body')} (`mkway ack {r.get('id')}`)" for r in rows[:SHOWN])
    more = f" | and {len(rows) - SHOWN} more: `mkway leads`" if len(rows) > SHOWN else ""
    return allow_with_line("lead-notices-unacked", f"you have {_plural(len(rows), 'unacked notice')}: {text}{more}")


# ---- the message gate ---------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class MessageFacts:
    """What the message gate reads. Send: `tool_name`, `tool_input`, `session_id` as the hook gave them;
    `row_is_senders`: some inbox holds the row the body names and this session wrote it; `pinged`: a ping for that row
    was recorded. Remind: `is_lead`, `unacked`: one formatted line for each unacked inbox item (`messages.item_line`),
    `report_route`. Stop: `minutes` (`messaging.ack_reminder_minutes`), `old_orders`: ({id, from, first}, ...) the
    unacked orders older than that, `first` the first line of the body."""
    tool_name: Optional[str] = None
    tool_input: Any = None
    session_id: Any = None
    row_is_senders: bool = False
    row_no_by: bool = False  # MW-076 (R197 B): the row is an engine notice with no `by`: nobody caused it
    pinged: bool = False
    is_lead: bool = False
    unacked: tuple = ()
    minutes: float = 30.0
    old_orders: tuple = ()
    report_route: str = ""


def ping_row_id(tool_input) -> Optional[str]:
    """The id of the row a SendMessage body names, when the body is exactly one ping line `mkway inbox <id>` (a final
    line break allowed); None for anything else. The shell asks it to know which row to look up."""
    message = tool_input.get("message") if isinstance(tool_input, dict) else None
    if not isinstance(message, str):
        return None
    found = PING_LINE.fullmatch(message.strip())
    return found.group(1) if found else None


def decide_send(facts: MessageFacts) -> Verdict:
    """Entry `message.send`: the sender's side only. Free text passes (card MW-110: `message-not-in-inbox` is removed; the
    inbox file stays the record of orders and results). Only a body that is exactly the ping line of a row this session
    wrote is judged: a second ping for the same row is `message-duplicate`, the first allows and carries the ping row to
    record. A ping line of another session's row, of an engine notice nobody caused, a call with no readable session id,
    a pure idle subscription (`notify_when_idle` with no text) and every other tool pass, and record nothing. The `to`
    field is never read."""
    if facts.tool_name != SEND_TOOL:
        return allow()
    tool_input = facts.tool_input if isinstance(facts.tool_input, dict) else {}
    message = tool_input.get("message")
    if not isinstance(message, str):
        return allow()
    found = PING_LINE.fullmatch(message.strip())
    session = facts.session_id
    if not found or not isinstance(session, str) or not session.strip() or facts.row_no_by or not facts.row_is_senders:
        return allow()
    row_id = found.group(1)
    if facts.pinged:
        return refuse("message-duplicate", f"the ping for {row_id} was already sent: the recipient has it "
                                           f"(`mkway inbox {row_id}`). To say more, write another row with "
                                           f"`mkway send --to <id-prefix> --kind <kind> --file <body> --reply-to "
                                           f"<id>` and send its ping line")
    return allow(records=(("ping", {"id": row_id, "session": session}),))


def decide_message_remind(facts: MessageFacts) -> Verdict:
    """Entry `message.remind` (the prompt): a session that is no lead is reminded of its unacked inbox items; a lead has
    its own reminder; a session with no id is not judged."""
    if not isinstance(facts.session_id, str) or not facts.session_id or facts.is_lead:
        return allow()
    rows = facts.unacked
    if not rows:
        return allow()
    text = " | ".join(rows[:SHOWN])
    more = f" | and {len(rows) - SHOWN} more: `mkway board`" if len(rows) > SHOWN else ""
    return allow_with_line("inbox-unacked", f"you have {_plural(len(rows), 'unacked inbox item')}: {text}{more}")


def decide_message_stop(facts: MessageFacts) -> Verdict:
    """Entry `message.stop` (Stop): an unacked order older than `messaging.ack_reminder_minutes` is a reminder line,
    never a block."""
    if not isinstance(facts.session_id, str) or not facts.session_id:
        return allow()
    rows = facts.old_orders
    if not rows:
        return allow()
    text = " | ".join(f"{r.get('id')} from {r.get('from')}: {r.get('first')} "
                      f"(`mkway inbox {r.get('id')}`, then `mkway ack {r.get('id')}`)" for r in rows[:SHOWN])
    return allow_with_line("orders-unacked", f"{_plural(len(rows), 'order')} unacked for more than "
                                             f"{facts.minutes:g} minutes: {text}")


# ---- the session id of a shell call (card MW-110) -----------------------------------------------------------------------

@dataclass(frozen=True)
class SessionEnvFacts:
    """What the session-id check of a shell call reads. `session_id`: the hook's own id. `env_name`: the name of the
    launcher's variable (a fact, never a literal here). `env_id`: its value in the hook's environment, None or empty when
    unset. `command`: the command text (None when the call has none). `day` and `watch_until`: ISO dates; `watch_until`
    is the profile value `messaging.session_id_watch_until`, empty meaning no expiry. `launcher`: the line that starts a
    session with the variable set, printed as the way out."""
    session_id: Any = None
    env_name: str = ""
    env_id: Optional[str] = None
    command: Optional[str] = None
    day: str = ""
    watch_until: str = ""
    launcher: str = ""
    watch_bad: str = ""  # R279c Q2: the profile value as written when it is not a date; it counts as passed


def watch_passed(day: str, watch_until: str, watch_bad: str = "") -> bool:
    """True when the transition period is over: the end date is before `day` (ISO dates compare as text), or the profile
    value cannot be read (`watch_bad`, R279c Q2: it counts as passed, fail closed, so a typo never makes the trial endless).
    No date and no bad value: not passed."""
    return bool(watch_bad) or bool(watch_until and day > watch_until)


def _passed_text(watch_until: str, watch_bad: str) -> str:
    """Why the period counts as over, for a refusal: the unreadable value as written, or the end date that has passed."""
    if watch_bad:
        return (f"{WATCH_KEY} holds {watch_bad!r}, which is not a date, so it counts as passed; the owner sets a date "
                f"as YYYY-MM-DD or empties it")
    return f"the end date {watch_until} of the transition has passed"


def launcher_line(env_name: str) -> str:
    """The line that starts a session with its own id in the environment: a fresh id, the variable set to it, and the
    session started with the same id, so the hook's id and the environment's id are one."""
    return f"$id = [guid]::NewGuid().ToString(); $env:{env_name} = $id; claude {LAUNCHER_FLAG} $id"


def assigns_variable(command, name: str) -> bool:
    """True when the command text assigns the variable `name`: `NAME=x` (also after `export`, `env`, `set`), `$env:NAME = x`,
    `environ['NAME'] = x`, `SetEnvironmentVariable('NAME', ...)`, `putenv` and `setx NAME`. A read (`$NAME`, `${NAME}`, a
    test with `==`) and a longer name that holds `name` (`NAME_X=1`, `PRE_NAME=1`) are not an assignment."""
    if not isinstance(command, str) or not name:
        return False
    word = re.escape(name)
    assign = re.search(r"(?<![A-Za-z0-9_$])" + word + r"['\"\]\s]*=(?!=)", command)
    setter = re.search(r"(?:SetEnvironmentVariable|putenv|setx)\W+" + word + r"(?![A-Za-z0-9_])", command, re.I)
    return bool(assign or setter)


def decide_session_env(facts: SessionEnvFacts) -> Verdict:
    """Entry `message.session` (the shell group, every shell call): the id the launcher put in the environment is the
    hook's own id. Refuses `session-id-mismatch` for a command that assigns the variable, for an environment id that is
    not the hook's, and for an unset variable once the period has passed (`watch_passed`: the date is past or cannot be
    read, R279c Q2); warns `session-id-unset` (allows) for an unset variable before that, or with no date. A hook input with no session id is not judged. Every refusal and the
    warn name the launcher line."""
    name, way = facts.env_name, f"start the session with the launcher line: {facts.launcher}"
    if assigns_variable(facts.command, name):
        return refuse("session-id-mismatch", f"the command assigns {name}: the id of a session comes from its launcher and "
                                             f"is never set in a command. Remove the assignment; to start a session with "
                                             f"the variable set, {way}")
    session = facts.session_id
    if not isinstance(session, str) or not session.strip():
        return allow()
    if facts.env_id:
        if facts.env_id == session:
            return allow()
        return refuse("session-id-mismatch", f"{name} holds {facts.env_id}, the hook's session id is {session}: the two "
                                             f"must be one. Start the session with the launcher line: {facts.launcher}")
    if watch_passed(facts.day, facts.watch_until, facts.watch_bad):
        return refuse("session-id-mismatch", f"{name} is not set ({_passed_text(facts.watch_until, facts.watch_bad)}): {way}")
    until = f"until {facts.watch_until}" if facts.watch_until else "until the owner sets an end date"
    return allow_with_line("session-id-unset", f"{name} is not set, so this session is known through the one-use permit "
                                               f"{until}. Next time {way}")


@dataclass(frozen=True)
class SenderFacts:
    """What the engine's messaging commands read to know who runs them (rulings R279 and R279c). `own_permit`: the session id
    held by the one-use permit file named by the variable (`permits/<id>.json`, taken once; None when there is none, it was
    used, or it is too old). `latest_permit`: the session id of the most recent fresh messaging permit of any session, read
    only when the variable is unset and the period is not over (None otherwise). `env_id`: the launcher's variable in the
    command's environment. `env_name`, `launcher`, `day`, `watch_until`, `watch_bad`: as in `SessionEnvFacts`;
    `permit_seconds`: how long a permit lives, named in the text of `message-no-session`."""
    env_name: str = ""
    env_id: Optional[str] = None
    own_permit: Optional[str] = None
    latest_permit: Optional[str] = None
    day: str = ""
    watch_until: str = ""
    watch_bad: str = ""
    launcher: str = ""
    permit_seconds: int = 0


@dataclass(frozen=True)
class Sender:
    """The id a messaging command acts as, or the refusal. `warn`: the id is not proven by its own permit (the variable alone,
    or the most recent permit), so the shell writes one warn row `session-id-unset` with `note` as its text."""
    session: Optional[str] = None
    reason: Optional[str] = None
    text: str = ""
    warn: bool = False
    note: str = ""


def decide_sender(facts: SenderFacts) -> Sender:
    """Who runs a messaging command (rulings R279 and R279c). The proof is the permit the hook wrote under the session's own
    id; the command opens only the file its variable names, and a variable that differs from the id inside is
    `session-id-mismatch`. With the variable set and no own permit the variable counts only while the period is not over
    (`watch_passed`), with a warn; after it, `session-id-unverified`. With no variable, before the end date the single most
    recent permit is taken, with a warn that names the limit (two sessions at once); after it, `session-id-unverified`;
    with no permit either, `message-no-session`. Another session's permit never proves a variable. Every refusal names the
    launcher line."""
    name, way = facts.env_name, f"Start the session with the launcher line: {facts.launcher}"
    declared = (facts.env_id or "").strip()
    own = (facts.own_permit or "").strip()
    latest = (facts.latest_permit or "").strip()
    passed = watch_passed(facts.day, facts.watch_until, facts.watch_bad)
    if declared and own:
        if declared != own:
            return Sender(reason="session-id-mismatch", text=f"{name} holds {declared}, the hook's session id is {own}: "
                                                             f"the two must be one. {way}")
        return Sender(session=own)
    if passed:
        when = _passed_text(facts.watch_until, facts.watch_bad)
        what = f"{name} holds {declared}" if declared else f"{name} is not set"
        return Sender(reason="session-id-unverified", text=f"{what}, but no hook check of this call was found and the "
                                                           f"variable alone proves nothing ({when}). Run the command "
                                                           f"alone, in its plain form, in a session with the engine hooks. "
                                                           f"{way}")
    until = f"until {facts.watch_until}" if facts.watch_until else "until the owner sets an end date"
    if declared:
        return Sender(session=declared, warn=True, note=f"{name} was taken alone, with no hook check of this call, {until}. "
                                                        f"Run the command alone, in its plain form. {way}")
    if latest:
        return Sender(session=latest, warn=True, note=f"{name} is not set, so the most recent permit was taken, {until}: two "
                                                      f"sessions at once can take each other's permit, and the end date "
                                                      f"{WATCH_KEY} ends it. {way}")
    return Sender(reason="message-no-session", text=f"{name} is not set and no hook check of this call was found (none, "
                                                    f"used, or older than {facts.permit_seconds} s), so the session id is "
                                                    f"not established. {way}; until then run the command alone, in its "
                                                    f"plain form, in a session with the engine hooks")


# ---- the records step of the `post` group -------------------------------------------------------------------------------

def response_text(response) -> str:
    """The stdout text of a tool response: a string (PowerShell), or the `stdout` or `output` key of a mapping."""
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        for key in ("stdout", "output"):
            if isinstance(response.get(key), str):
                return response[key]
    return ""


def ok_lines(response) -> tuple:
    """((kind, value, nonce), ...): each `mkway-ok <kind> <value> <nonce>` line of the tool's stdout, in order. A line is
    only a claim: the shell asks the nonce store whether the nonce was issued for exactly that kind and value."""
    return tuple(OK_LINE.findall(response_text(response)))


def granted(kind: str, value: str, session_id) -> tuple:
    """The rows to write for an `mkway-ok` line whose nonce was issued: the session record, and for `new` (a card the
    session wrote) the register's `Ordered by` cell, when the hook input carries a session id. The shell writes the cell
    only when the register has the column; a card with no orderer cell reads `owner`."""
    rows = [("record", {"kind": kind, "value": value})]
    if kind == "new" and isinstance(session_id, str) and session_id.strip():
        rows.append(("ordered", {"card": value, "session": session_id}))
    return tuple(rows)


REPAIR = "report it to the operator: the owner repairs the file or folder, then the call is repeated"


def record_failed(exc_name: str, path: str) -> Verdict:
    """The session record could not be written (R271c-D1): the tool already ran, but the session must not go on believing
    it recorded, so the step refuses and names the path the engine could not write."""
    return refuse("post-record-failed", f"the session record could not be written ({exc_name}): {path} is not "
                                        f"written, so a gate that needs it will refuse next; {REPAIR}")


def ordered_failed(exc_name: str, card_id: str, path: str) -> Verdict:
    """The record stands but the card's `Ordered by` cell could not be written: it refuses and names the register
    (R271c-D1); the card reads `owner`, the safe side, until the cell is written."""
    return refuse("post-record-failed", f"the card's Ordered by cell could not be written ({exc_name}): {path} is "
                                        f"not written, so {card_id} reads owner; {REPAIR}")


# ---- the agent records --------------------------------------------------------------------------------------------------

def agent_record_failed(exc_name: str, path: str, event: str) -> Verdict:
    """An agent row could not be written (R271c). `SubagentStart` refuses, naming the path: nothing is running yet, so
    nothing loops. `SubagentStop` never refuses (a block there would keep a finished agent going): it is a visible line
    naming the path."""
    text = (f"the agent record could not be written ({exc_name}): {path} is not written, so the agent's "
            f"{'start' if event == 'SubagentStart' else 'result'} is not saved; {REPAIR}")
    if event == "SubagentStart":
        return refuse("agent-record-failed", text)
    return allow_with_line("agent-record-failed", text)
