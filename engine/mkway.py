"""mkway command line (card MW-002; card MW-003).

    mkway.py hook <event> --group <name> [--root <path>] [--profile <path>]
    mkway.py hook-wait [--root <path>] [--profile <path>]   the inbox waiter, a Stop handler (MW-078)
    mkway.py install --from <engine repo> [--ref <sha or tag>] [--vcs git|none] [--python <command>]
                     [--shared <absolute folder>] [--root <path>] [--profile <path>]
    mkway.py check [--root <path>] [--profile <path>]
    mkway.py upgrade --target <repo> [--root <name>] [--dry-run] [--from-head]   the owner's: install the newest proven-green
                                    engine release into the granted task root, one ledger row, one commit; prints one JSON
                                    object; --from-head is internal (MW-104)
    mkway.py green record --repo <path> --into <branch> --branch <name> --from <sha> --sha <sha> --command <text>
                          --kind full|narrow [--rule <n>] [--seconds <n>]   the owner's: one line of the green record (MW-104)
    mkway.py card new <title> | list | resync [--add-ordered-by] | take <id> | release <id> [--force] | open <id>
                  | close <id> | set <id> open|waiting|closed | release-red <test id> --to <card>
    mkway.py give <card> <who>      the owner's: who ordered a card (a session id prefix, or `owner`; card MW-011); a
                                    registered lead's give of a card it ordered is a hand-off (MW-017)
    mkway.py lead register | accept <card> | add <id-prefix> | remove <id-prefix>   the lead role (MW-017); add and
                                    remove are the owner's
    mkway.py ack <id>               a session clears one row of its own inbox (the owner's terminal: any inbox; MW-017, MW-018)
    mkway.py send --to <id-prefix> --kind <kind> (--file <body> | --text "<body>") [--reply-to <id>] a message into a session's inbox, in the
                                    star per card; prints the ping line to send with SendMessage (MW-018)
    mkway.py inbox <id>             shows one row of the caller's own inbox (the owner's terminal: any row; MW-018)
    mkway.py board                  inboxes, cards and asks in one view (MW-018)
    mkway.py leads                  every lead: cards ordered, overdue, last activity, unacked notices (MW-017)
    mkway.py sessions               the owner's view: every session id seen, its card, the cards it ordered
    mkway.py lock open <name> [--minutes N] | close <name> [--minutes N, ignored] | list
    mkway.py gate off <name> | on <name> | watch <name>   (watch: a form gate only; `on` ends it; card MW-012)
    mkway.py delete --list <file>
    mkway.py trash list | empty --older-than <days>
    mkway.py ledger add --card <id> --topic <text> (--quote <verbatim> | --quote-file <path>) --source <text> [--replaces <row id>]
                        [--status <text>] [--by <text>]     (topic: plain words, letters, digits, spaces, dashes)
    mkway.py verdict add <card> <node>... <true|weak|wrong> <reason>   a blind reader's verdict rows: the only writer of
                                    tests/verdicts/<card>.md; the caller is the lock gate's permit (MW-080)
    mkway.py verdict recut <card> <node> <reason>   the card's orderer re-cuts a weak or wrong verdict: a `recut` row, a
                                    record and a ledger row; a fresh blind verdict follows (MW-100)
    mkway.py search <words>...
    mkway.py asks                   the board of the ask files (MW-014)
    mkway.py outbox                 the files made for someone outside the session, the state of each check (MW-019)
    mkway.py built <path>           a result file built on a clean, tested HEAD: the provenance row (MW-020)
    mkway.py delivered <path>       the owner's: a result file went out; a copy is kept as the base (MW-020)
    mkway.py deliverables           the result files: sha prefix, built state, delivered base (MW-020)

Run it through the root launcher `mkway.py`: in the engine repository and in a task's copy alike the path is
`mkway/engine/mkway.py` under the task root (decision C12). The root is `--root`, else `$CLAUDE_PROJECT_DIR`,
else the top of the git work tree; never the engine's own folder. Exit codes and output of `hook` follow Claude
Code's documented hook contract (dispatch.render). A crash there follows the group rule of R13c: exit 2 in `edit`
and `shell`, exit 0 in every other group; the root launcher applies the same rule to start-up failures.

Who runs a command (card MW-003, C44): a session's shell carries `CLAUDECODE`; the owner's own terminal does not.
A session's successful card or search command prints `mkway-ok <kind> <value> <nonce>` for the `post` group, which
records it with the session id; an owner's command appends its own `by: owner` record. The owner-only commands
(lock, gate, install, upgrade, green record, give, card open / close / resync, release --force; with `cards.approver: orderer` a
session's `card close` is the orderer's, checked by the lock gate and the CLI) are refused to a session by the lock
gate before they run, and by this CLI itself when `CLAUDECODE` is present (close-fix 1, a tripwire: a session can
strip it); the owner's way out is their own terminal, where no hook runs (decision 4).
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from pathlib import Path

_HERE = str(Path(__file__).resolve().parent)  # the engine's own modules; never the task root
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import asks  # noqa: E402
import cardtool  # noqa: E402
import core_ping  # noqa: E402
import core_session  # noqa: E402
import dispatch  # noqa: E402
import gatemode  # noqa: E402
import install  # noqa: E402
import leads  # noqa: E402
import ledger  # noqa: E402
import locks  # noqa: E402
import logs  # noqa: E402
import deliverables  # noqa: E402
import messages  # noqa: E402
import outbox  # noqa: E402
import paths  # noqa: E402
import profiles  # noqa: E402
import records  # noqa: E402
import register  # noqa: E402
import rules  # noqa: E402
import scorecard  # noqa: E402
import search  # noqa: E402
import sessions  # noqa: E402
import trash  # noqa: E402
import upgrade  # noqa: E402
import waiter  # noqa: E402


def _place(parser):
    parser.add_argument("--root")
    parser.add_argument("--profile")


class _Parser(argparse.ArgumentParser):
    """No abbreviated long options on any parser (close-fix 8, A-M1): `add_subparsers` builds every subparser with
    the parser's own class, so `--prof` is never taken for `--profile`."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("allow_abbrev", False)
        super().__init__(*args, **kwargs)


def _parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="mkway")
    sub = parser.add_subparsers(dest="command", required=True)
    hook = sub.add_parser("hook", help="run the gates of one event and group (called by Claude Code)")
    hook.add_argument("event")
    hook.add_argument("--group", required=True)
    _place(hook)
    wait = sub.add_parser("hook-wait", help="the inbox waiter: a Stop handler that wakes an idle session when a new row "
                          "reaches its inbox (called by Claude Code, installed with asyncRewake; MW-078)")
    _place(wait)
    inst = sub.add_parser("install", help="copy the engine into a task root and generate its hook entries")
    inst.add_argument("--from", dest="source", required=True)
    inst.add_argument("--ref")
    inst.add_argument("--vcs", choices=("git", "none"))
    inst.add_argument("--python", help="per-machine interpreter command, recorded in state/machine.json only; the "
                      "committed hook entries use the profile's python.command")
    inst.add_argument("--commit", action="store_true",
                      help="the owner's: run the two printed git lines (add, commit) after install (MW-027)")
    inst.add_argument("--shared", help="absolute folder for the state shared across worktrees; written into the "
                      "profile as state.shared_dir (opt-in, MW-026)")
    _place(inst)
    chk = sub.add_parser("check", help="compare the copy with its lock, run its tests and the term scan")
    _place(chk)
    upg = sub.add_parser("upgrade", help="the owner's: install the newest proven-green engine release into the granted task "
                         "root, with one ledger row and one commit (MW-104)")
    upg.add_argument("--target", help="the one folder the owner's grant names")
    upg.add_argument("--root", help="the task root inside the target, when the grant lists several")
    upg.add_argument("--dry-run", action="store_true", help="run every check and print the plan; change nothing")
    upg.add_argument("--from-head", action="store_true", help="internal: install the engine HEAD when the green record "
                     "proves it, by a full run or by the narrow route")
    green = sub.add_parser("green", help="the owner's: the green record the upgrade reads (MW-104)")
    green_sub = green.add_subparsers(dest="green_command", required=True)
    rec = green_sub.add_parser("record", help="append one line to the green record")
    for flag in ("repo", "into", "branch", "from", "sha", "command", "kind", "rule", "seconds"):
        rec.add_argument("--" + flag, dest=flag + "_")  # `command_`: never the subcommand's own `command`
    card = sub.add_parser("card", help="the cards tool")
    card_sub = card.add_subparsers(dest="card_command", required=True)
    new = card_sub.add_parser("new")
    new.add_argument("title", nargs="+")
    _place(new)
    lst = card_sub.add_parser("list")
    _place(lst)
    resync = card_sub.add_parser("resync", help="the owner's: show the register diff and rewrite its seal")
    resync.add_argument("--add-ordered-by", action="store_true",
                        help="the owner's: also add the `Ordered by` column to a register that has none")
    _place(resync)
    for name in ("take", "open", "close"):
        one = card_sub.add_parser(name, allow_abbrev=False)
        one.add_argument("card_id")
        _place(one)
    rel = card_sub.add_parser("release", allow_abbrev=False)
    rel.add_argument("card_id")
    rel.add_argument("--force", action="store_true", help="the owner's: free a card another session holds")
    _place(rel)
    rred = card_sub.add_parser("release-red", allow_abbrev=False,
                               help="the orderer's: move one red test the card inherited at its take to another open card")
    rred.add_argument("test_id", help="the whole test id, as `card take` recorded it")
    rred.add_argument("--to", required=True, dest="to_card", help="the open card that now owns the red")
    _place(rred)
    cset = card_sub.add_parser("set", allow_abbrev=False)
    cset.add_argument("card_id")
    cset.add_argument("status")
    _place(cset)
    give = sub.add_parser("give", help="the owner's: set who ordered a card (a session id prefix, or `owner`)")
    give.add_argument("card_id", help="a card id, or a bare number that takes the profile's card prefix")
    give.add_argument("who", help="a prefix of one session id seen in the state records, or `owner`")
    _place(give)
    sess = sub.add_parser("sessions", help="the owner's view: every session id seen, with its card and its orders")
    _place(sess)
    lead_p = sub.add_parser("lead", help="the lead role: register, accept a hand-off; the owner adds and removes")
    lead_sub = lead_p.add_subparsers(dest="lead_command", required=True)
    _place(lead_sub.add_parser("register", help="a session declares itself a lead"))
    lacc = lead_sub.add_parser("accept", help="the new lead takes over a card another lead gave it")
    lacc.add_argument("card_id", help="a card id, or a bare number that takes the profile's card prefix")
    _place(lacc)
    for word, text in (("add", "the owner's: make a session seen in the state records a lead"),
                       ("remove", "the owner's: end a registered lead's role")):
        lone = lead_sub.add_parser(word, help=text)
        lone.add_argument("who", help="a prefix of one session id")
        _place(lone)
    ack_p = sub.add_parser("ack", help="a session clears one row of its own inbox")
    ack_p.add_argument("notice_id")
    _place(ack_p)
    send_p = sub.add_parser("send", help="put a message into a session's inbox; prints the ping line to send")
    send_p.add_argument("--to", required=True, help="a session id, or a prefix that starts exactly one")
    send_p.add_argument("--kind", required=True, choices=messages.KINDS)
    send_body = send_p.add_mutually_exclusive_group(required=True)
    send_body.add_argument("--file", help="the file that holds the body")
    send_body.add_argument("--text", help="the body itself, literal (no `$(...)`, backtick or `$name`); for a session "
                                          "that cannot write a file (MW-055)")
    send_p.add_argument("--reply-to", dest="reply_to", help="the id of a row of your own inbox this answers")
    _place(send_p)
    inbox_p = sub.add_parser("inbox", help="show one row of your own inbox")
    inbox_p.add_argument("row_id")
    _place(inbox_p)
    _place(sub.add_parser("board", help="inboxes, cards and asks in one view"))
    _place(sub.add_parser("scorecard", help="what the process cost the task: refusals per reason, test seconds, hook time, asks (MW-112)"))
    _place(sub.add_parser("leads", help="every lead: cards ordered, overdue, last activity, unacked notices"))
    gate_p = sub.add_parser("gate", help="the owner's switch of one gate in the profile")
    gate_sub = gate_p.add_subparsers(dest="gate_command", required=True)
    for name in ("off", "on", "watch"):  # `watch` (MW-012): a form gate still runs but never blocks; `on` ends it
        g = gate_sub.add_parser(name)
        g.add_argument("name")
        if name == "watch":  # MW-112 (R284a): the one lever for another end date than the engine's 7 days
            g.add_argument("--until", default=None, metavar="YYYY-MM-DD", help="the end date of the watch")
        _place(g)
    lock = sub.add_parser("lock", help="the owner's lock files")
    lock_sub = lock.add_subparsers(dest="lock_command", required=True)
    lopen = lock_sub.add_parser("open")
    lopen.add_argument("name")
    lopen.add_argument("--minutes", type=float, default=60)
    _place(lopen)
    lclose = lock_sub.add_parser("close")
    lclose.add_argument("name")
    lclose.add_argument("--minutes", type=float, default=60)  # ignored: a close has no end (the owner hold, MW-010)
    _place(lclose)
    llist = lock_sub.add_parser("list")
    _place(llist)
    for word, text in (("hold", "the owner's: `lock close hold`"), ("go", "the owner's: `lock open hold`")):
        _place(sub.add_parser(word, help=text))  # the short forms (MW-010, R123)
    led = sub.add_parser("ledger", help="the decision ledger")
    led_sub = led.add_subparsers(dest="ledger_command", required=True)
    ladd = led_sub.add_parser("add", help="append one row: today's date, the next id, the owner's words verbatim")
    ladd.add_argument("--card", required=True, type=_text)
    ladd.add_argument("--topic", required=True, type=_text,
                      help="plain words: letters, digits, spaces and dashes")
    quote = ladd.add_mutually_exclusive_group(required=True)
    quote.add_argument("--quote", type=_text, help="a plain quote, as the owner wrote it")
    quote.add_argument("--quote-file", dest="quote", type=_quote_file, metavar="PATH",
                       help="a file with the verbatim quote (e.g. <bundle.root>/ledger/quote.txt); one trailing "
                            "line break is stripped; the file is not deleted")
    ladd.add_argument("--source", required=True, type=_text)
    ladd.add_argument("--status", default=ledger.IN_FORCE, type=_status)
    ladd.add_argument("--replaces", type=_text, metavar="ID",
                      help="the id of an earlier row this row replaces; that row then reads as superseded")
    ladd.add_argument("--by", type=_status, help="who wrote the row; default `session:<session id>`; `owner` only "
                                                 "from the owner's terminal")
    _place(ladd)
    _place(sub.add_parser("rules", help="the rule cards: id, card, test, exists or missing, last green tree (MW-021)"))
    board = sub.add_parser("asks", help="the board of the ask files: id, card, age, deadline, default, status, blocked")
    _place(board)
    box = sub.add_parser("outbox", help="the files under outbox.dir: file, sha prefix, check state, checker, time")
    _place(box)
    bld = sub.add_parser("built", help="record that a result file was built on a clean, tested HEAD (MW-020)")
    bld.add_argument("path")
    _place(bld)
    dlv = sub.add_parser("delivered", help="the owner's: record that a result file went out, and keep a copy (MW-020)")
    dlv.add_argument("path")
    _place(dlv)
    _place(sub.add_parser("deliverables", help="the result files: sha prefix, built state, delivered base (MW-020)"))
    ask_p = sub.add_parser("ask", help="a session's commands on its ask: take the default, or record the answer")
    ask_sub = ask_p.add_subparsers(dest="ask_command", required=True)
    adef = ask_sub.add_parser("default", help="reversible ask past its deadline: take the default, ledger row")
    adef.add_argument("ask_id")
    _place(adef)
    aans = ask_sub.add_parser("answered", help="the owner answered: status answered, ledger row with the owner's words")
    aans.add_argument("ask_id")
    aquote = aans.add_mutually_exclusive_group(required=True)
    aquote.add_argument("--quote", type=_text, help="a plain quote, as the owner wrote it")
    aquote.add_argument("--quote-file", dest="quote", type=_quote_file, metavar="PATH",
                        help="a file with the verbatim quote; one trailing line break is stripped")
    _place(aans)
    srch = sub.add_parser("search", help="search the ledger and the knowledge files before asking the owner")
    srch.add_argument("words", nargs="+", type=_text)
    _place(srch)
    dele = sub.add_parser("delete", help="delete exact repo paths from a list file: backed up, recorded")
    dele.add_argument("--list", dest="list_file", required=True, help="a file with one exact repo path per line")
    _place(dele)
    trash_p = sub.add_parser("trash", help="the owner's view of the backups of deletes")
    trash_sub = trash_p.add_subparsers(dest="trash_command", required=True)
    tlist = trash_sub.add_parser("list")
    _place(tlist)
    tempty = trash_sub.add_parser("empty")
    tempty.add_argument("--older-than", dest="older_than", type=float, required=True, help="days")
    _place(tempty)
    ver = sub.add_parser("verdict", help="a blind reader's verdict rows (MW-080)")
    ver_sub = ver.add_subparsers(dest="verdict_command", required=True)
    vadd = ver_sub.add_parser("add", allow_abbrev=False, help="write the verdict rows of one reader run: the only writer")
    vadd.add_argument("card_id", help="a card id, or a bare number that takes the profile's card prefix")
    vadd.add_argument("items", nargs="+", type=_text, metavar="NODE... WORD REASON",
                      help="one or more test nodes the card names, then true, weak or wrong, then the reason")
    _place(vadd)
    vrecut = ver_sub.add_parser("recut", allow_abbrev=False, help="re-cut a weak or wrong verdict: the card's orderer only")
    vrecut.add_argument("card_id", help="a card id, or a bare number that takes the profile's card prefix")
    vrecut.add_argument("node", type=_text, help="the one test node the card names whose last verdict is weak or wrong")
    vrecut.add_argument("reason", type=_text, help="what changed in the row's words or in the test")
    _place(vrecut)
    reader = sub.add_parser("reader", help="the reader's allowlist: one run at a time per session (MW-116)")
    reader_sub = reader.add_subparsers(dest="reader_command", required=True)
    rstart = reader_sub.add_parser("start", allow_abbrev=False,
                                   help="write the allow file of this session: the test files of the card's nodes and the extract")
    rstart.add_argument("card_id", help="a card id, or a bare number that takes the profile's card prefix")
    _place(rstart)
    rend = reader_sub.add_parser("end", allow_abbrev=False, help="empty the allow list of this session (the owner names one)")
    rend.add_argument("--session", dest="target_session", default=None, help="the owner's terminal: the session whose list to empty")
    _place(rend)
    return parser


def _text(value: str) -> str:
    """A ledger argument: at least one character that is not white space (a usage error otherwise)."""
    if not value.strip():
        raise argparse.ArgumentTypeError("it must not be empty")
    return value


def _quote_file(value: str) -> str:
    """`--quote-file <path>`: the file's text, one trailing line break stripped; an unreadable or empty file is a usage
    error."""
    try:
        text = ledger.quote_from_file(value)
    except OSError as exc:
        raise argparse.ArgumentTypeError(f"cannot read the quote file ({exc.__class__.__name__})")
    return _text(text)


def _status(value: str) -> str:
    """A ledger status: one line, no pipe (it is a table cell)."""
    if not value.strip() or "|" in value or "\n" in value or "\r" in value:
        raise argparse.ArgumentTypeError("it must be one non-empty line with no `|`")
    return value.strip()


def _read_stdin() -> str:
    data = sys.stdin.buffer.read() if hasattr(sys.stdin, "buffer") else sys.stdin.read().encode("utf-8")
    return data.decode("utf-8", errors="replace")


def _fail(message: str) -> int:
    sys.stderr.write(f"mkway: {message}\n")
    return 1


class Run:
    """One command run: the root, the profile, and who runs it."""

    def __init__(self, root: Path, profile, env):
        self.root = root
        self.profile = profile
        self.env = env
        self.session = records.SESSION_ENV in env
        self.state = profiles.state_dir(root, profile)
        self.shared = profiles.shared_state_dir(root, profile)  # MW-017: leads, inboxes and sessions cross work trees

    def done(self, kind: str, value: str) -> None:
        """Record a successful command: a session's through the `post` group, the owner's here (deliverable 2)."""
        if self.session:
            nonce = records.issue(self.state, kind, value)
            print(f"mkway-ok {kind} {value} {nonce}")
        else:
            records.append(self.state, None, kind, value, by="owner")

    def refusal(self, reason: str, target=None) -> None:
        try:
            logs.write_refusal(self.state, logs.row(session=None, event="command", tool=None, gate="cards",
                                                    reason_id=reason, target=target, kind="refuse"))
        except OSError:
            pass


IN_SESSION = "run it in your own terminal, not inside a Claude chat"
HOLD_WORDS = {"hold": "close", "go": "open"}  # the short forms of `lock close hold` and `lock open hold` (R123)
HOLD_TARGET = "hold"


def _owner_only(args, profile=None, root=None):
    """The owner-only command `args` names, or None (close-fix 1, A-M5, R37 (a) H4): the same list and the same
    `cards.owner_moves` rule as the lock gate's `owner-only-command`. `card open|close|set` need the profile; without
    it they are not judged here. The holder's `card set <id> open` of a `waiting` card passes, as in the gate
    (R19c); the gate checks the holder."""
    command = args.command
    if command == "install":
        return "install"
    if command == "upgrade":  # MW-104: the owner's grant is never used by a session
        return "upgrade"
    if command == "green":
        return "green record"
    if command == "lock" and args.lock_command in ("open", "close"):
        return f"lock {args.lock_command}"
    if command in HOLD_WORDS:
        return command
    if command == "gate":
        return f"gate {args.gate_command}"
    if command == "lead" and args.lead_command in ("add", "remove"):  # MW-017: only the owner makes or ends a lead
        return f"lead {args.lead_command}"
    # `give` is judged in `_give`: a registered lead's give is a hand-off, any other session's is refused there (MW-017)
    if command == "trash":  # MW-009: a session never reads or empties the backups of its own deletes
        return f"trash {args.trash_command}"
    if command == "delivered":  # MW-020: only the owner says what went out, so no session picks its own base
        return "delivered"
    if command != "card":
        return None
    sub = args.card_command
    if sub == "resync":
        return "card resync"
    if sub == "release":
        return "card release --force" if args.force else None
    if sub not in ("open", "close", "set") or profile is None:
        return None
    if cardtool.approver(profile) == "orderer":  # MW-011: a session's close is the orderer's, decided in `_move`;
        if sub == "close":                      # `card set <id> closed` stays the owner's: no second door
            return None
        if sub == "open" and "open" in cardtool.owner_moves(profile):  # MW-028: a lead's open of its own proposed
            return None                                                 # card, decided in `_move` by the permit
        if sub == "set" and args.status == "closed":
            return "card set closed"
    status = {"open": "open", "close": "closed"}.get(sub) or args.status
    if status not in cardtool.owner_moves(profile):
        return None
    if sub == "set" and status == "open":
        try:  # the sealed register's status, as the gate reads it
            register.check(root, profile)
            row = register.find(register.read(root, profile), args.card_id)
        except (OSError, register.RegisterError):
            row = None
        if row and row.get("status") == "waiting":
            return None
    return f"card set {status}" if sub == "set" else f"card {sub}"


def _refuse_in_session(what: str) -> int:
    return _fail(f"owner-only-command: `mkway {what}` is the owner's command; {IN_SESSION}")


def main(argv=None, env=None) -> int:
    env = os.environ if env is None else env
    args = _parser().parse_args(argv)
    session = records.SESSION_ENV in env  # present with any value, the empty value included
    if session and _owner_only(args):
        return _refuse_in_session(_owner_only(args))
    if args.command == "hook-wait":  # MW-078: before dispatch.run, which must answer fast; the waiter lives for hours
        try:
            return waiter.main(_read_stdin(), args.root, args.profile, env)
        except Exception:
            return 0  # the waiter never blocks and never fails a Stop
    if args.command == "hook":
        result = dispatch.run(args.event, args.group, _read_stdin(), root_arg=args.root, profile_arg=args.profile)
        if result.stdout:
            sys.stdout.write(result.stdout)
        if result.stderr:
            sys.stderr.write(result.stderr)
        return result.exit_code
    if args.command == "upgrade":  # MW-104: no task root of its own; the grant names the root
        code, answer = upgrade.run_upgrade(args.target, args.root, args.dry_run, args.from_head, env, upgrade.ENGINE_FILE)
        print(json.dumps(answer, indent=2))
        return code
    if args.command == "green":
        fields = {k: getattr(args, k + "_") for k in
                  ("repo", "into", "branch", "from", "sha", "command", "kind", "rule", "seconds")}
        code, text = upgrade.record_green(fields, env, upgrade.ENGINE_FILE)
        if code:
            return _fail(text)
        print(text)
        return 0
    try:
        root = paths.find_root(env=env, root_arg=args.root, vcs=getattr(args, "vcs", None), env_needs_cwd=True)
    except paths.RootNotFound as exc:
        return _fail(str(exc))
    if args.command == "install":
        try:
            report = install.install(root, Path(args.source), ref=args.ref, profile_arg=args.profile, vcs=args.vcs,
                                     python=args.python, shared=args.shared, commit=args.commit)
        except install.InstallError as exc:
            return _fail(str(exc))
        print("\n".join(report))
        return 0
    if args.command == "check":
        code, lines = install.check(root, profile_arg=args.profile)
        print("\n".join(lines))
        return code
    profile, _errors = profiles.load(paths.profile_path(root, args.profile))
    if args.command == "search":  # MW-008: no profile and no ledger still leave a record (0 hits)
        return _search(root, profile if isinstance(profile, dict) else {}, args, env, session)
    if profile is None:
        if not paths.profile_path(root, args.profile).is_file():  # MW-024
            return _fail(install.no_install_line(root))
        return _fail("the profile cannot be read: " + "; ".join(_errors))
    if session and _owner_only(args, profile, root):
        return _refuse_in_session(_owner_only(args, profile, root))
    if args.command in HOLD_WORDS:
        if HOLD_TARGET not in locks.default_open_names(root, profile):
            return _fail(f"no hold target: the profile has no lock target named `{HOLD_TARGET}` that is open by "
                         f"default. Add to the profile: locks.targets: [{{\"name\": \"{HOLD_TARGET}\", \"paths\": "
                         f"[\"**\"], \"open_by_default\": true}}]")
        args.lock_command, args.command, args.name, args.minutes = HOLD_WORDS[args.command], "lock", HOLD_TARGET, 60
    run = Run(root, profile, env)
    run.profile_file = paths.profile_path(root, args.profile)
    try:
        if args.command == "delete":
            return _delete(run, args)
        if args.command == "trash":
            return _trash(run, args)
        if args.command == "lock":
            return _lock(run, args)
        if args.command == "gate":
            return _gate(run, args)
        if args.command == "ledger":
            return _ledger(run, args)
        if args.command == "verdict":
            return _verdict(run, args)
        if args.command == "reader":
            return _reader(run, args)
        if args.command == "give":
            return _give(run, args)
        if args.command == "lead":
            return _lead(run, args)
        if args.command == "ack":
            return _ack(run, args)
        if args.command == "send":
            return _send(run, args)
        if args.command == "inbox":
            return _inbox(run, args)
        if args.command == "board":
            print(chr(10).join(messages.board_lines(run.root, run.profile)))
            return 0
        if args.command == "scorecard":  # MW-112: read-only, a session's command too
            print("\n".join(scorecard.lines(run.root, run.profile)))
            return 0
        if args.command == "leads":
            print("\n".join(leads.view_lines(run.root, run.profile)))
            return 0
        if args.command == "sessions":
            return _sessions(run)
        if args.command == "ask":
            return _ask(run, args)
        if args.command == "rules":  # MW-021: read-only, a session's command too
            print(chr(10).join(rules.lines(run.root, run.profile)))
            return 0
        if args.command == "asks":
            print(chr(10).join(asks.board_lines(run.root, run.profile)))
            return 0
        if args.command == "outbox":  # MW-019: read only, any terminal
            print(chr(10).join(outbox.board_lines(run.root, run.profile)))
            return 0
        if args.command == "deliverables":  # MW-020: read only, any terminal
            print(chr(10).join(deliverables.lines(run.root, run.profile)))
            return 0
        if args.command in ("built", "delivered"):  # MW-020
            return _deliverable(run, args)
        return _card(run, args)
    except register.RegisterError as exc:
        run.refusal(exc.reason)
        return _fail(f"{exc.reason}: {exc.message}")
    except cardtool.CardError as exc:
        if exc.reason != "card-error":
            run.refusal(exc.reason)
            return _fail(f"{exc.reason}: {exc}")
        return _fail(str(exc))
    except locks.LockError as exc:
        return _fail(str(exc))
    except (leads.LeadError, messages.MessageError) as exc:
        run.refusal(exc.reason)
        return _fail(f"{exc.reason}: {exc.message}")


def _delete(run: Run, args) -> int:
    """`delete --list <file>` (MW-009): a session's command, never owner-only; the gate passes it. Any bad line of the
    list deletes nothing. The CLI knows no session id, so the record row says `by` instead."""
    try:
        text = Path(args.list_file).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        return _fail(f"the list file cannot be read ({exc.__class__.__name__})")
    code, lines = trash.delete_list(run.root, run.profile, run.profile_file, text,
                                    max_mb=profiles.delete_settings(run.profile)["max_backup_mb"],
                                    by="session" if run.session else "owner")
    if code:
        for line in lines:
            sys.stderr.write(f"mkway: {line}\n")
        return code
    print("\n".join(lines))
    return 0


def _trash(run: Run, args) -> int:
    """`trash list` and `trash empty --older-than <days>` (MW-009): the owner's, refused to a session before this."""
    if args.trash_command == "list":
        print("\n".join(trash.listing(run.root, run.state)))
        return 0
    if args.older_than < 0:
        return _fail("--older-than takes a number of days, not below 0")
    try:
        removed, freed = trash.empty(run.root, run.state, args.older_than)
    except (OSError, trash.BackupError) as exc:
        return _fail(f"the trash could not be emptied ({getattr(exc, 'message', exc.__class__.__name__)})")
    print(f"removed {len(removed)} folder(s), {freed / trash.MB:.2f} MB freed")
    return 0


def _lock(run: Run, args) -> int:
    if args.lock_command == "list":
        print(f"lock markers read from: {locks.lock_folder(run.root, run.profile)} (shared by every work tree of the "
              f"repository)")
        for line in locks.marker_warnings(run.root, run.profile):
            print(line)
        for name, until in locks.open_locks(run.root, run.profile):
            print(f"{name} open until {until}")
        for line in locks.hold_lines(run.root, run.profile):
            print(line)
        return 0
    data = locks.set_lock(run.root, run.profile, args.name, "open" if args.lock_command == "open" else "closed",
                          minutes=getattr(args, "minutes", 60))
    if args.name in locks.default_open_names(run.root, run.profile):
        print(f"lock {data['name']} {data['state']} (hold by the owner; no end time)")
    else:
        print(f"lock {data['name']} {data['state']} until {data['until']}")
    return 0


def _search(root: Path, profile: dict, args, env, session: bool) -> int:
    """`search <words>` (MW-008): print the hits, append the record; a session's run then prints the `mkway-ok` line
    the `post` group turns into that session's `search` record."""
    try:
        lines, row = search.run(root, profile, args.words, env)
    except OSError as exc:
        return _fail(f"the search record was not written ({exc.__class__.__name__}); a question needs it")
    print("\n".join(lines))
    Run(root, profile, env).done("search", row["id"])
    return 0


def _ask_log(run: Run, reason: str, ask_id: str, kind: str) -> None:
    try:
        logs.write_refusal(run.state, logs.row(session=None, event="command", tool=None, gate="owner_ask",
                                               reason_id=reason, target=ask_id, kind=kind))
    except OSError:
        pass


def _ask(run: Run, args) -> int:
    """`ask default <id>` and `ask answered <id>` (MW-014): a session's commands, never owner-only. The refusal is the
    reason id and its text, logged; a success is logged and leaves the ledger row."""
    try:
        if args.ask_command == "default":
            ask, row = asks.take_default(run.root, run.profile, args.ask_id, by=_by(run))
            reason, text = "ask-default-taken", f"ask {ask.id} default taken: {ask.default}"
        else:
            caller = (cardtool.take_by_permit(run.state) or "") if run.session else None  # MW-119: None = owner's terminal
            ask, row = asks.answer(run.root, run.profile, args.ask_id, args.quote, caller=caller,
                                   lead=bool(caller) and leads.is_lead(run.shared, caller), state=run.state)
            reason, text = "ask-answered", f"ask {ask.id} answered"
    except asks.AskError as exc:
        _ask_log(run, exc.reason, args.ask_id, "refuse")
        return _fail(f"{exc.reason}: {exc.message}")
    except OSError as exc:
        return _fail(f"the ask was not changed ({exc.__class__.__name__}); nothing is half done but check `mkway asks`")
    _ask_log(run, reason, ask.id, "log")
    print(f"{text}; ledger {row['id']} added")
    if args.ask_command == "default":
        _notify_default(run, ask)
        run.done(asks.DEFAULT_RECORD, ask.id)  # a session's record comes through the post group; the owner's is here
    return 0


def _notify_default(run: Run, ask) -> None:
    """MW-017: a default taken is a notice to the lead that ordered the card of the asking session; with that card not
    established, to every lead; a card the owner (or a session that is no lead) ordered tells no lead. Never fails."""
    try:
        body = (f"ask {ask.id} default taken: {ask.default}; the owner had not answered by the deadline, so the work "
                f"went on with the default (see the ledger row of ask {ask.id})")
        card = asks.card_of(run.root, run.profile, ask.id)
        if card == asks.UNKNOWN:
            leads.notify_all(run.shared, body)
        else:
            leads.notify_orderer(run.root, run.profile, card, body)
    except Exception:
        pass


def _by(run: Run, requested=None) -> str:
    """The `by` of a ledger row (MW-015): the owner's terminal writes `owner` (or the `--by` it typed); a session writes
    `session:<session id>`, the id from the one-use permit of the lock gate, `session:unknown` with none."""
    if not run.session:
        return requested or ledger.formats()["owner_who"]
    session = cardtool.take_by_permit(run.state)  # taken (removed) at every session run, used or not
    return requested or f"session:{session or 'unknown'}"


def _deliverable(run: Run, args) -> int:
    """`built` (a session's command and the owner's) and `delivered` (the owner's; a session never gets here, `main`
    refuses it first), MW-020. A session's id is the lock gate's one-use permit, `owner` is the owner's terminal."""
    who = (cardtool.take_by_permit(run.state) or cardtool.NE) if run.session else ledger.formats()["owner_who"]
    try:
        if args.command == "delivered":
            row = deliverables.deliver(run.root, run.profile, args.path)
            print(f"delivered {row['path']} {row['sha256'][:8]}")
            return 0
        row = deliverables.build(run.root, run.profile, args.path, who)
    except deliverables.Refused as exc:
        run.refusal(exc.reason, args.path)
        return _fail(f"{exc.reason}: {exc.message}")
    text = deliverables.built_text(row)
    try:
        ledger.add(run.root, run.profile, card="-", topic="built", quote=text, source="mkway built", status="built",
                   by=f"session:{who}" if run.session else who)
    except OSError as exc:
        sys.stderr.write(f"mkway: the ledger row was not written ({exc.__class__.__name__})\n")
    print(text)
    return 0


def _ledger(run: Run, args) -> int:
    """`ledger add` (MW-008): a session's command and the owner's alike; it never refuses for what a row says, except
    that a session never writes `by` as the owner (`ledger-by-owner`, MW-015)."""
    if run.session and args.by and args.by.strip().lower() == ledger.formats()["owner_who"].lower():
        run.refusal("ledger-by-owner")
        return _fail("ledger-by-owner: only the owner's terminal writes by=owner")
    try:
        row = ledger.add(run.root, run.profile, card=args.card, topic=args.topic, quote=args.quote,
                         source=args.source, status=args.status, by=_by(run, args.by),
                         replaces=(args.replaces or "").strip())
    except ledger.UnknownRow as exc:
        run.refusal("ledger-replaces-unknown")
        return _fail(f"ledger-replaces-unknown: no row {exc} in the ledger")
    except OSError as exc:
        return _fail(f"the ledger row was not written ({exc.__class__.__name__})")
    print(f"ledger {row['id']} added to {ledger.path(run.root, run.profile).relative_to(run.root).as_posix()}")
    return 0


VERDICT_USAGE = "mkway verdict add <card> <node>... <true|weak|wrong> <reason>"


def _verdict(run: Run, args) -> int:
    """`verdict add` or `verdict recut` (MW-080, MW-100)."""
    return _verdict_recut(run, args) if args.verdict_command == "recut" else _verdict_add(run, args)


def _verdict_outcome(run: Run, caller: str, card_id: str, verdict, mode_key: str = "tests.verdict_add.mode"):
    """The exit code of a refused verdict command (1), else None. Each refusal watch mode let through is a `would-refuse`
    row in the refusal log and a printed `watch:` line; a blocking refusal is a refusal row each and one failure line."""
    for seen in verdict.watched:
        logs.write_refusal(run.state, logs.row(session=caller or None, event="command", tool=None, gate="cards",
                                               reason_id=seen.reason, target=card_id, kind=gatemode.WOULD_REFUSE,
                                               message=seen.text))
        print(f"watch: {seen.text} (allowed: {mode_key} is watch)")
    if verdict.allowed:
        return None
    for refusal in verdict.refusals:
        run.refusal(refusal.reason, card_id)
    return _fail(" | ".join(r.text for r in verdict.refusals))


def _verdict_recut(run: Run, args) -> int:
    """`verdict recut` (MW-100; R251, R251a, R251b): the card's orderer answers a weak or wrong verdict with a re-cut. The
    caller is the lock gate's one-use permit, as in `verdict add`; the owner's terminal has none and is refused."""
    import verdict_add
    import verdict_recut
    caller = (cardtool.take_by_permit(run.state) or "") if run.session else ""
    card_id = cardtool.card_ref(run.profile, args.card_id)
    node = verdict_add.node_of(args.node)
    try:
        verdict = verdict_recut.apply(run.root, run.profile, run.state, card_id, node, args.reason, caller, not run.session)
    except OSError as exc:
        return _fail(f"the recut was not written ({exc.__class__.__name__}); check the verdict file and the ledger of {card_id}")
    failed = _verdict_outcome(run, caller, card_id, verdict)
    if failed is not None:
        return failed
    print(chr(10).join(verdict_recut.report(card_id, node, verdict)))
    return 0


def _verdict_add(run: Run, args) -> int:
    """`verdict add` (MW-080; R194, R196, R196a): the only writer of a verdict row. The caller is the lock gate's one-use
    permit (taken at every session run, used or not); the owner's terminal has none and is refused by the decision. A
    refusal is a row in the refusal log and exit 1; in watch mode a refusal outside the independence ones is a `would-refuse`
    row and the call goes ahead."""
    import verdict_add
    caller = (cardtool.take_by_permit(run.state) or "") if run.session else ""
    items = list(args.items)
    word = items[-2].strip().casefold() if len(items) > 1 else ""
    if len(items) < 3 or word not in verdict_add.WORDS:
        sys.stderr.write(f"mkway: usage: {VERDICT_USAGE}: the verdict word is true, weak or wrong, then the reason"
                         + chr(10))
        return 2
    card_id = cardtool.card_ref(run.profile, args.card_id)
    nodes = list(dict.fromkeys(verdict_add.node_of(i) for i in items[:-2]))
    try:
        verdict = verdict_add.apply(run.root, run.profile, run.state, card_id, nodes, word, items[-1], caller,
                                    not run.session)
    except OSError as exc:
        return _fail(f"the verdict rows were not written ({exc.__class__.__name__}); check the verdict file of {card_id}")
    failed = _verdict_outcome(run, caller, card_id, verdict)
    if failed is not None:
        return failed
    print(chr(10).join(verdict_add.report(card_id, nodes, word, verdict)))
    return 0


def _reader(run: Run, args) -> int:
    """`reader start <card>` and `reader end` (MW-116; R287, R287c): the allow file of the reader's allowlist hook. The id is
    the spawning session's own, proved as a messaging command proves it (`_message_session`: the launcher's variable and the
    lock gate's permit). The owner's terminal has no session: it can only end a named session's run (`--session`), the
    orderer's release that the busy refusal names."""
    import reader_allow
    state = run.state
    if args.reader_command == "end":
        if run.session and args.target_session:
            return _fail("`mkway reader end --session` is the owner's command; a session empties its own list with "
                         "`mkway reader end`")
        if not run.session and not args.target_session:
            return _fail("the owner's terminal names the session whose run ends: `mkway reader end --session <id>`")
        session = _message_session(run) if run.session else args.target_session
        if not reader_allow.end(state, session):
            print(f"session {session} has no allow file: nothing to empty")
            return 0
        print(f"the allow list of session {session} is empty")
        return 0
    if not run.session:
        return _fail("`mkway reader start` is a session's command: the allow file is keyed by the id of the spawning "
                     "session, and the owner's terminal has none; the owner empties a run with `mkway reader end --session <id>`")
    session = _message_session(run)
    card_id = cardtool.card_ref(run.profile, args.card_id)
    try:
        doc = reader_allow.start(run.root, run.profile, state, session, card_id)
    except reader_allow.ReaderError as exc:
        run.refusal(exc.reason, card_id)
        return _fail(exc.text)
    print(f"allow file written for session {session}: {len(doc['files'])} files (the test files of {card_id} and the extract of "
          f"its Acceptance rows); start the reader now, one run at a time; `mkway reader end` empties the list")
    return 0


def _card(run: Run, args) -> int:
    root, profile = run.root, run.profile
    if args.card_command == "new":
        folder = cardtool.new_card(root, profile, " ".join(args.title))
        card_id = folder.name.split("-", 2)[0] + "-" + folder.name.split("-", 2)[1]
        if run.session:  # MW-017: a lead's new card gets its order file; the lock gate's permit names the session
            maker = cardtool.take_by_permit(run.state)
            if maker and leads.is_lead(run.shared, maker):
                leads.write_order(folder, card_id)
        print(folder.relative_to(root).as_posix())
        run.done("new", card_id)
        return 0
    if args.card_command in ("take", "release", "open", "close", "set"):
        return _move(run, args)
    if args.card_command == "release-red":
        return _release_red(run, args)
    if args.card_command == "resync":
        diff = register.reseal(root, profile, add_orderer=args.add_ordered_by)
        print("\n".join(diff) if diff else "register: no difference against register.last")
        print("register: seal rewritten")
        return 0
    for row in cardtool.list_cards(root, profile):
        print("  ".join(row[:3]))
    return 0


def _give(run: Run, args) -> int:
    """The owner's `give` (card MW-011, rule 2): who ordered a card. The owner's own record is `give <card> <value>`.
    A session's give (MW-017) is a registered lead's hand-off: the session id is the lock gate's one-use permit, never
    a word of the command; any other session is refused as before."""
    if run.session:
        lead = cardtool.take_by_permit(run.state)
        if not lead or not leads.is_lead(run.shared, lead):
            return _refuse_in_session("give")
        card_id, target = leads.give(run.root, run.profile, run.shared, lead, args.card_id, args.who)
        print(f"{card_id} offered to {target}; it changes hands when that lead runs `mkway lead accept {card_id}`")
        return 0
    card_id, value = cardtool.give(run.root, run.profile, run.state, args.card_id, args.who)
    print(f"{card_id} ordered by {value}")
    run.done("give", f"{card_id} {value}")
    return 0


def _lead_session(run: Run) -> str:
    """The session id of a session's lead command: the one-use permit of the lock gate (the hook input is the only
    source of an id). `lead-no-session` when there is none."""
    session = cardtool.take_by_permit(run.state)
    if not session:
        raise leads.LeadError("lead-no-session", f"no hook check of this call was found (none, used, or older than "
                                                 f"{cardtool.PERMIT_SECONDS} s), so the session id is not "
                                                 f"established; run the command alone, in its plain form, in a session "
                                                 f"with the engine hooks, or the owner runs `mkway lead add "
                                                 f"<id-prefix>`")
    return session


def _lead(run: Run, args) -> int:
    """`lead register|accept` (a session's; the id comes from the permit) and `lead add|remove` (the owner's terminal,
    refused to a session before this; card MW-017)."""
    sub = args.lead_command
    if sub in ("add", "remove"):
        if sub == "add":
            sid = leads.resolve_seen(run.state, args.who, run.shared)
            leads.register_lead(run.shared, sid)
            print(f"{sid} is a lead")
        else:
            sid = leads.resolve_lead(run.shared, args.who)
            leads.remove_lead(run.shared, sid)
            print(f"{sid} is no longer a lead")
        run.done("lead", f"{sub} {sid}")
        return 0
    if not run.session:
        raise leads.LeadError("lead-session-only", f"`mkway lead {sub}` is a session's command: the lead runs it in its "
                                                   f"own Claude session; the owner makes a lead with `mkway lead add "
                                                   f"<id-prefix>`")
    session = _lead_session(run)
    if sub == "register":
        added = leads.register_lead(run.shared, session)
        print(f"session {session} is a lead" + ("" if added else " (already registered)"))
        run.done("lead", "register")
        return 0
    card_id, was = leads.accept(run.root, run.profile, run.shared, session, args.card_id)
    print(f"{card_id} ordered by {session} (was {was})")
    run.done("lead", f"accept {card_id}")
    return 0


def _message_session(run: Run) -> str:
    """The session id of a messaging command (card MW-110, rulings R279 and R279c): the variable is never the proof alone. The
    lock gate's one-use permit, written for the plain engine call with the hook-verified session id under the session's own
    id (`permits/<session id>.json`), is the proof. With the variable set, only the file it names is opened and consumed,
    used or not; the id inside must equal the variable, else `session-id-mismatch`. With no own permit the variable counts
    only while the period is not over (`core_session.watch_passed`: `messaging.session_id_watch_until` is not past and can
    be read), with one warn row `session-id-unset`; after it, `session-id-unverified`. With no variable, before the end
    date, the single most recent fresh permit is taken with a warn row that names the limit (two sessions at once); after
    it `session-id-unverified`; with no permit either `message-no-session`. The decision is the pure
    `core_session.decide_sender`."""
    name = core_session.SESSION_ENV
    env_id = str(run.env.get(name) or "").strip()
    day, until = logs.now().date().isoformat(), profiles.session_id_watch_until(run.profile)
    bad = profiles.session_id_watch_unreadable(run.profile)
    own = messages.take_message_permit(run.state, env_id) if env_id else None  # R279c: only the file the variable names
    latest = None
    if not env_id and not core_session.watch_passed(day, until, bad):
        latest = messages.take_latest_message_permit(run.state)
    decided = core_session.decide_sender(core_session.SenderFacts(
        env_name=name, env_id=env_id, own_permit=own, latest_permit=latest, day=day, watch_until=until, watch_bad=bad,
        launcher=core_session.launcher_line(name), permit_seconds=cardtool.PERMIT_SECONDS))
    if decided.reason:
        raise messages.MessageError(decided.reason, decided.text)
    if decided.warn:  # the id is not proven by its own permit: one warn row that names the limit
        try:
            logs.write_refusal(run.state, logs.row(session=decided.session, event="command", tool=None,
                                                   gate="message.session", reason_id="session-id-unset", target=None,
                                                   kind="warn", note=decided.note))
        except OSError:
            pass
    return decided.session


def _ack(run: Run, args) -> int:
    """`ack <id>` (card MW-017, MW-018): a session clears one row of its own inbox, a builder as well as a lead; a row of
    another inbox is `ack-not-yours`; the owner's terminal acks any row. Record R1 is written first (R279c Q3)."""
    session = _message_session(run) if run.session else None
    row = messages.ack(run.shared, session, args.notice_id)
    print(f"{row.get('kind', 'notice')} {row['id']} acked")
    return 0


def _read_body(root: Path, name: str) -> str:
    for candidate in (Path(name), Path(root) / name):
        try:
            return candidate.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError):
            continue
    raise messages.MessageError("message-no-file", f"the body file {name!r} cannot be read; write the message into a "
                                                   f"file and name it with `--file <path>`")


def _send(run: Run, args) -> int:
    """`send` (card MW-018): a session's command; the sender is the hook's session id, never a word of the command. The
    row goes into the recipient's inbox; the ping line is printed for the sender to send with SendMessage."""
    if not run.session:
        raise messages.MessageError("send-session-only", "`mkway send` is a session's command: the owner has no inbox "
                                                         "and reads `mkway board`; the owner tells a lead through a "
                                                         "session")
    sender = _message_session(run)
    if args.text is not None:  # MW-055: the CLI writes the body itself; no file a refused session could not write
        problem = messages.text_problem(args.text)
        if problem:
            raise messages.MessageError("message-text-unsafe", problem)
        body = args.text
    else:
        body = _read_body(run.root, args.file)
    file = args.file if args.text is None else "--text"  # record R1 is written before the delivery (R279c Q3)
    sent = messages.send(run.root, run.profile, run.shared, sender, args.to, args.kind, body, args.reply_to,
                         record=lambda row: messages.record_send(run.shared, row, sender, file))
    print(f"{args.kind} {sent.row['id']} is in the inbox of {sent.target}")
    line = messages.ping_line(sent.row["id"])
    print(line)
    print(f"root: {sent.root or cardtool.NE}")
    name = messages.target_name(run.root, run.profile, run.shared, sent.target, sender)  # MW-076: R185, R188
    if name:
        print(core_ping.send_ping_text(name, line))
    else:
        print("next: in ListAgents find the session that runs in that root folder and send it exactly the ping line above, "
              f"nothing else, with SendMessage (a ref is not a session id; no socket is used); {core_ping.CLAUSE}")
    return 0


def _inbox(run: Run, args) -> int:
    """`inbox <id>` (card MW-018): shows one row to the session it is addressed to; the owner's terminal reads any."""
    session = _message_session(run) if run.session else None
    print(chr(10).join(messages.show_lines(messages.show(run.shared, session, args.row_id))))
    return 0


def _sessions(run: Run) -> int:
    """The owner's view (card MW-011, rule 3), read-only: every session id seen in the state records, its last-seen
    time, the card it holds and the cards it ordered. The engine knows ids, never chat names."""
    seen, missing = cardtool.seen_sessions(run.state, run.shared)  # MW-017: the shared sessions file counts too
    roots = {sid: root for sid, (_ts, root) in sessions.latest(run.shared).items()}
    rows = register.read(run.root, run.profile)
    closed = register.closed_ids(run.root, run.profile)
    for sid in sorted(seen, key=lambda s: (seen[s], s), reverse=True):
        held = records.session_card(run.state, sid, closed) or "none"
        ordered = ", ".join(r["id"] for r in rows if r.get(register.ORDERED) == sid) or "none"
        print(f"{sid}  last seen {seen[sid] or cardtool.NE}  holds {held}  ordered {ordered}  "
              f"root {roots.get(sid) or cardtool.NE}")
    if not seen:
        print("no session id seen in the state records")
    if missing:
        print(f"{cardtool.NE}: {missing} row{'s' if missing != 1 else ''} without a session id")
    return 0


def _gate(run: Run, args) -> int:
    """The owner's switch (deliverable 9): `gates.<name>.on` in the tracked profile; the hook entries change at the
    next `mkway install`."""
    import json
    known = {e.get("gate") for e in dispatch.load_manifest(dispatch.ENGINE_DIR) if e.get("function")}
    if args.name not in known:
        return _fail(f"unknown gate {args.name!r}; gates with code: {', '.join(sorted(known))}")
    until = replaced = None
    if args.gate_command == "watch":  # MW-012: a marker; MW-112: and the end date in the profile
        if gatemode.gate_class(dispatch.load_manifest(dispatch.ENGINE_DIR), args.name) != gatemode.FORM:
            run.refusal("gate-watch-integrity", args.name)
            return _fail(f"gate-watch-integrity: integrity gates never watch; {args.name} is an integrity gate and "
                         f"always blocks; to try a gate without blocking watch a form gate, for example "
                         f"`mkway gate watch message`")
        if args.until is not None and gatemode.until_date(args.until) is None:
            return _fail(f"--until {args.until!r} is not a date (YYYY-MM-DD); the profile was not changed")
        until = args.until or (logs.now().date() + datetime.timedelta(days=gatemode.WATCH_DAYS)).isoformat()
        old = gatemode.watch_until(run.profile, args.name)
        replaced = old if gatemode.until_date(old) is not None else None
    profile = dict(run.profile)
    gates = dict(profile.get("gates") or {})
    entry = dict(gates.get(args.name) or {})
    if args.gate_command == "watch":
        entry["watch_until"] = until
    else:
        entry["on"] = args.gate_command == "on"
        if args.gate_command == "on":
            entry.pop("watch_until", None)  # MW-112: a gate that is on has no trial date
    gates[args.name] = entry
    profile["gates"] = gates
    errors = profiles.validate(profile)
    if errors:  # C53 (R64): an engine writer never writes a profile the schema refuses
        return _fail("the profile was not changed: the result would be invalid: " + "; ".join(errors[:5]) + ". The "
                     "owner fixes the profile in their own editor first; `mkway check` prints the same error")
    target = Path(run.profile_file)
    tmp = target.with_name(target.name + ".tmp")
    try:  # a temp file, then replace: never a half-written tracked profile (close check L5)
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(profile, indent=2) + "\n")
        os.replace(tmp, target)
    except OSError as exc:
        return _fail(f"the profile was not changed ({exc.__class__.__name__}); {tmp.name} may be left beside it")
    if args.gate_command == "watch":
        gatemode.write_marker(run.state, args.name, "owner")
        logs.write_refusal(run.state, gatemode.transition_row(args.name, "gate-watch", cause="owner",
                                                              **{"from": replaced, "until": until}))
        print(f"gate {args.name} watch until {until}: it still runs, a refusal is logged as would-refuse and the call goes "
              f"ahead; `mkway gate on {args.name}` returns it to blocking")
        return 0
    if args.gate_command == "on":  # MW-012: the only way back from watch, and it is the owner's
        had = gatemode.remove_marker(run.state, args.name)
        logs.write_refusal(run.state, gatemode.transition_row(args.name, gatemode.ON_ROW, cause="owner",
                                                              was_watch=had))
    print(f"gate {args.name} {args.gate_command} in {run.profile_file.name}; run `mkway install` to change the hook "
          f"entries")
    return 0


def _release_stale(run: Run, card_id: str) -> None:
    """MW-045: before a take, free each stale holder that blocks it (the holder of `card_id`, or of an open card) with
    a release row by `stale` and the Log row `stale holder <8 characters> released`. The taking session itself (the
    gate's permit names it) is never freed."""
    root, profile = run.root, run.profile
    held = records.holders(run.state, register.closed_ids(root, profile))
    stale = cardtool.stale_holders(root, profile, held)
    if not stale:
        return
    taker = cardtool.take_by_permit(run.state) if run.session else None
    rows = register.read(root, profile)
    hours = profiles.cards_stale_hours(profile)
    for card, who in stale.items():
        row = register.find(rows, card) or {}
        if who == taker or (card != card_id and row.get("status") != "open"):
            continue
        records.append(run.state, taker, "release", card, by="stale")
        cardtool.append_log_row(root, profile, card, f"stale holder {who[:8]} released",
                                f"last seen over {hours:g} h ago; freed when another session took {card_id}")
        print(f"stale holder {who[:8]} of {card} released")


def _notify_orderer(root, profile, card_id, body, caller, cmd) -> None:
    """The notice to a card's orderer for a move a session made (MW-017, MW-076). `caller`: the session id of the lock
    gate's one-use permit (the MW-049 mechanism), the notice's `by`; with none, the record keeps `cmd` and the card id
    for the ping gate's fallback (R189). Never fails the command."""
    try:
        leads.notify_orderer(root, profile, card_id, body, by=caller, cmd=cmd)
    except Exception:
        pass


def _release_red(run: Run, args) -> int:
    """`card release-red <test id> --to <card>` (MW-108, R283 4): the card's orderer moves an inherited red to another open
    card. A session's id is the lock gate's one-use by-permit, never a word of the command; the owner's terminal orders the
    cards that name no session. The card tool decides who may and writes the row."""
    caller = cardtool.take_by_permit(run.state) if run.session else None
    if run.session and not caller:
        raise cardtool.CardError(f"no hook check of this call was found (none, used, or older than "
                                 f"{cardtool.PERMIT_SECONDS} s), so the orderer is not established; run `mkway card "
                                 f"release-red` alone, in its plain form, in a session with the engine hooks, or the "
                                 f"owner runs it in their own terminal", reason="close-not-orderer")
    print(cardtool.release_red(run.root, run.profile, run.state, args.test_id.replace("\\", "/"), args.to_card, caller))
    return 0


def _move(run: Run, args) -> int:
    """take, release, open, close, set (deliverable 4). Who may run which is the lock gate's (owner-only commands);
    the chain and the close rule are checked here, for the owner's terminal too."""
    root, profile, card_id, sub = run.root, run.profile, args.card_id, args.card_command
    caller = cardtool.take_by_permit(run.state) if run.session and sub in ("set", "release") else None  # MW-076, R189
    if sub == "take":
        if register.find(register.read(root, profile), card_id) is None:
            raise cardtool.CardError(f"{card_id} is not in the register", reason="card-unknown")
        if not run.session:
            return _fail("`card take` is a session's command: the owner's terminal holds no card")
        _release_stale(run, card_id)  # MW-045: a holder unseen for `cards.stale_hours` is freed first
        if card_id in records.holders(run.state, register.closed_ids(root, profile)):
            raise cardtool.CardError(f"{card_id} is held by a session; the owner or the card's orderer frees it with "
                                     f"`card release {card_id}`", reason="card-not-yours")
        try:  # MW-108: the red at HEAD inside the card's Paths is recorded; a take never fails because of it
            note = cardtool.record_inherited_red(root, profile, card_id)
        except (OSError, ValueError) as exc:
            note = (f"inherited red: the take row could not be written ({exc.__class__.__name__}); the take goes on and "
                    f"every red in the Paths of {card_id} counts as new red for this card")
        run.done("take", card_id)  # the ok line stays the first line of the output (MW-054 contract); the note follows
        print(note)
        return 0
    if sub == "release":
        holder = records.holders(run.state, register.closed_ids(root, profile)).get(card_id)
        if holder is None:
            print(f"no one holds {card_id}; nothing changed")
            return 0
        if run.session:
            orderer = cardtool.take_close_permit(run.state, card_id, "release")  # MW-045: the gate's permit names it
            if orderer is None:
                run.done("release", card_id)  # the holder's own release; any other session's row frees nothing
                _notify_orderer(root, profile, card_id, f"builder released {card_id}: it holds the card no more; read its "
                                                        f"Log, then give it to a new builder or close it", caller,
                                "card release")  # MW-076, R189: the orderer must act on a release
                return 0
            row = register.find(register.read(root, profile), card_id) or {}
            if holder == orderer or (row.get(register.ORDERED) or register.OWNER) != orderer:
                raise cardtool.CardError(f"{card_id} was not ordered by this session; only its orderer, or the owner "
                                         f"in their own terminal, frees a card another session holds",
                                         reason="card-not-yours")
            records.append(run.state, orderer, "release", card_id, by="orderer")
            cardtool.append_log_row(root, profile, card_id, "release", f"released by the orderer {orderer[:8]}")
            print(f"{card_id} released by its orderer")
            return 0
        run.done("release", card_id)  # the owner's terminal, with or without `--force`
        cardtool.append_log_row(root, profile, card_id, "release", "released by the owner")
        return 0
    if sub == "set":
        target = args.status
        record = False  # H1: `card set` never re-records Paths; only the first open from `proposed` does
    else:
        target = "open" if sub == "open" else "closed"
        record = sub == "open"
    if sub == "close" and run.session and cardtool.approver(profile) == "orderer":
        # MW-011: only the lock gate (the hook) knows the session id; it leaves a one-use permit that names it
        closer = cardtool.take_close_permit(run.state, card_id)
        if closer is None:
            raise cardtool.CardError(f"{card_id}: no hook check of this close was found (none, used, or older than "
                                     f"{cardtool.PERMIT_SECONDS} s): run `mkway card close {card_id}` alone, in its "
                                     f"plain form, in a session with the engine hooks; or {cardtool.OWNER_TERMINAL}",
                                     reason="close-not-orderer")
        written = cardtool.move(root, profile, card_id, "closed", session=True, record_paths=False, closer=closer,
                                state=run.state)
        print(f"{card_id} {written}")
        for note in cardtool.take_notes():  # MW-068, ruling R179
            print(note)
        run.done(sub, card_id)
        return 0
    if sub == "open" and run.session and cardtool.approver(profile) == "orderer" \
            and "open" in cardtool.owner_moves(profile):
        # MW-028: only the lock gate (the hook) knows the session id and that it is a registered lead; the permit names it
        opener = cardtool.take_close_permit(run.state, card_id, "open")
        if opener is None:
            return _refuse_in_session("card open")
        written = cardtool.move(root, profile, card_id, "open", session=True, record_paths=True, opener=opener,
                                state=run.state)
        print(f"{card_id} {written}")
        run.done(sub, card_id)
        return 0
    light = not cardtool.owner_moves(profile)  # light mode: a session may make the owner's moves (close check L2)
    written = cardtool.move(root, profile, card_id, target, session=run.session, record_paths=record, light=light)
    if run.session and sub == "set" and written == "waiting":  # MW-017: the builder finished; the orderer is told
        _notify_orderer(root, profile, card_id, f"builder finished: {card_id} went to waiting; read its Log, then close "
                                                f"it with `mkway card close {card_id}` once its tests pass", caller,
                        "card set")
    print(f"{card_id} {written}")
    for note in cardtool.take_notes():  # MW-068, ruling R179
        print(note)
    run.done(sub, card_id if sub != "set" else f"{card_id} {written}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
