"""Card MW-066: the session family's decisions (`engine/core_session.py`) as table tests on Facts -> Verdict. No disk, no
git: each row builds a Facts record and reads the verdict; every call runs under a guard that fails on any file, process
or clock access, and a scan fails if the core imports an I/O module. One test id is one case (parametrize ids); no body
loops over cases or branches on its input. For each refusal reason a deny row and the nearest allow row (the smallest
change that flips the verdict); a decision with four facts or fewer has every combination. Expected values are written
from the rule (the card rows, the gate docstrings), never computed by the code under test. Synthetic values only."""
import ast
import builtins
import contextlib
import io
import os
import pathlib
import subprocess
import time
from pathlib import Path

import pytest

import _engine  # noqa: F401  (puts the engine folder on the import path)
import core_session as core
from _no_io import no_io

CORE = Path(__file__).resolve().parents[2] / "engine" / "core_session.py"
ALLOWED_IMPORTS = {"__future__", "re", "dataclasses", "typing", "helpers"}
BANNED_NAMES = {"os", "pathlib", "subprocess", "time", "datetime", "shutil", "sys", "json", "io", "tempfile", "glob",
                "socket", "logging", "gate", "register", "records", "cardtool", "profiles", "logs", "leads", "messages",
                "sessions", "agents", "locks"}
BANNED_CALLS = {"open", "print", "input", "exec", "eval", "__import__", "compile"}
BANNED_ATTRS = {"now", "today", "utcnow", "read_text", "write_text", "read_bytes", "write_bytes", "is_file", "is_dir",
                "exists", "stat", "resolve", "getenv", "environ", "perf_counter", "monotonic"}
ROUTE = "REPORT-ROUTE"
FIX = "OWNER-FIX"
ORDER = "mkway/cards/CARD-001-first/ORDER.md"
ASKS = "mkway/asks"
CARD_FILE = "mkway/cards/CARD-001-first/CARD.md"


def run(function, *args):
    with no_io():
        return function(*args)


def case(id_, *values):
    return pytest.param(*values, id=id_)


# ---- the core is pure ---------------------------------------------------------------------------------------------------

def _scan(source: str):
    tree = ast.parse(source)
    modules, calls, attrs = set(), set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            modules.add((node.module or "").split(".")[0])
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            calls.add(node.func.id)
        elif isinstance(node, ast.Attribute):
            attrs.add(node.attr)
    return modules, calls, attrs


def test_the_core_imports_only_the_pure_modules():
    """Catches: a decision that imports `os`, `pathlib`, a clock or an engine I/O module, so it reads the world itself."""
    modules, _calls, _attrs = _scan(CORE.read_text(encoding="utf-8"))
    assert modules <= ALLOWED_IMPORTS
    assert not modules & BANNED_NAMES


def test_the_core_calls_no_io_function_and_reads_no_clock():
    """Catches: an `open`, a `print` or a clock read inside a decision."""
    _modules, calls, attrs = _scan(CORE.read_text(encoding="utf-8"))
    assert not calls & BANNED_CALLS
    assert not attrs & BANNED_ATTRS


@pytest.mark.parametrize("source, what", [
    case("os", "import os\n", "os"), case("pathlib", "from pathlib import Path\n", "pathlib"),
    case("subprocess", "import subprocess\n", "subprocess"), case("datetime", "import datetime\n", "datetime"),
    case("leads", "import leads\n", "leads"), case("register", "from register import find\n", "register"),
    case("inside-a-function", "def f():\n    import os\n", "os")])
def test_the_scan_catches_each_banned_import(source, what):
    """Catches: a purity scan that lets an I/O import through (each source here must be caught)."""
    modules, _calls, _attrs = _scan(source)
    assert what in modules
    assert not modules <= ALLOWED_IMPORTS


@pytest.mark.parametrize("touch", [case("open", lambda: open("x")), case("clock", lambda: time.time()),
                                   case("stat", lambda: os.stat("."))])
def test_the_guard_fails_on_disk_and_clock_access(touch):
    """Catches: a guard that lets a table test pass while the decision reads the disk or the clock."""
    with pytest.raises(AssertionError, match="touched the disk"):
        run(lambda: touch())


# ---- the subtask gate: the verdict --------------------------------------------------------------------------------------

def subtask(*paths, **kw):
    """The facts of an edit by a session that holds an open card `CARD-001` with Paths `src/a.py` and `lib/`."""
    base = dict(paths=tuple(paths) or ("src/a.py",), card_files="mkway/cards/*/CARD.md", exempt=("notes/**",),
                card_id="CARD-001", card_found=True, card_status="open", recorded=frozenset({"src/a.py", "lib/"}),
                now_paths=frozenset({"src/a.py", "lib/"}), owner_fix=FIX, report_route=ROUTE)
    base.update(kw)
    return core.SubtaskFacts(**base)


def holds_nothing(*paths, **kw):
    return subtask(*paths, card_id=None, card_found=False, card_status=None, recorded=frozenset(),
                   now_paths=None, **kw)


@pytest.mark.parametrize("facts, reason", [
    # S1 no-open-card: deny, and the nearest allow (the same edit with a card held)
    case("no-card-denies", holds_nothing("src/a.py"), "no-open-card"),
    case("a-card-held-allows", subtask("src/a.py"), None),
    # R19a register-tampered: deny (even when the status reads open) and the nearest allow
    case("seal-differs-denies", subtask(register_problem="the seal differs"), "register-tampered"),
    case("seal-differs-wins-over-status", subtask(register_problem="the seal differs", card_status="proposed"),
         "register-tampered"),
    case("seal-sound-allows", subtask(register_problem=None), None),
    # S2 card-not-open: proposed, closed, waiting, no row deny; open allows
    case("proposed-denies", subtask(card_status="proposed"), "card-not-open"),
    case("closed-denies", subtask(card_status="closed"), "card-not-open"),
    case("waiting-denies", subtask(card_status="waiting"), "card-not-open"),
    case("no-register-row-denies", subtask(card_found=False, card_status="open"), "card-not-open"),
    case("open-allows", subtask(card_status="open"), None),
    # v3.1 card-paths-changed: a wider set, a different set, an empty set, an unreadable card file deny; equal allows
    case("wider-set-denies", subtask(now_paths=frozenset({"src/a.py", "lib/", "src/b.py"})), "card-paths-changed"),
    case("different-set-denies", subtask(now_paths=frozenset({"src/b.py"})), "card-paths-changed"),
    case("emptied-set-denies", subtask(now_paths=frozenset()), "card-paths-changed"),
    case("unreadable-card-file-denies", subtask(now_paths=None), "card-paths-changed"),
    case("equal-set-allows", subtask(now_paths=frozenset({"lib/", "src/a.py"})), None),
    case("own-card-file-stays-editable-while-paths-differ", subtask(CARD_FILE, now_paths=frozenset()), None),
    # file-not-in-card: a file outside, a file with the same tail elsewhere deny; a file and a folder's file allow
    case("file-outside-denies", subtask("src/b.py"), "file-not-in-card"),
    case("same-tail-elsewhere-denies", subtask("other/src/a.py"), "file-not-in-card"),
    case("file-inside-allows", subtask("src/a.py"), None),
    case("file-in-folder-at-depth-allows", subtask("lib/deep/x.py"), None),
    case("the-folder-itself-allows", subtask("lib/"), None),
    case("empty-paths-is-no-file-rule", subtask("any/file.py", recorded=frozenset(), now_paths=frozenset()), None),
    # S3-S4 and the rest: no card rule applies
    case("a-card-file-with-no-card-allows", holds_nothing(CARD_FILE), None),
    case("another-cards-file-with-no-card-allows", holds_nothing("mkway/cards/CARD-009-other/CARD.md"), None),
    case("an-exempt-path-with-no-card-allows", holds_nothing("notes/today.md"), None),
    case("an-exempt-path-at-depth-allows", holds_nothing("notes/deep/er/x.md"), None),
    case("outside-the-repository-allows", holds_nothing(None), None),
    case("the-root-itself-allows", holds_nothing("."), None),
    # MW-017 / MW-028: a path the lead may write passes with no card; not on its list it is no-open-card
    case("a-path-the-lead-may-write-allows", holds_nothing(ORDER, lead_may_write=frozenset({ORDER})), None),
    case("the-same-path-for-a-session-that-may-not-denies", holds_nothing(ORDER), "no-open-card"),
    case("a-lead-path-list-that-lacks-it-denies", holds_nothing(ORDER, lead_may_write=frozenset({"mkway/asks/q.md"})),
         "no-open-card"),
    # several paths: the first one the rules refuse decides
    case("first-refused-path-decides", subtask("src/a.py", "notes/x.md", "src/b.py", "src/c.py"), "file-not-in-card"),
])
def test_the_subtask_verdict(facts, reason):
    """Catches: an edit allowed without a card, with a tampered register, on a card that is not open, with Paths the owner did not record, or outside the Paths; and the same edit refused when the card is held, sound, open, recorded and inside."""
    assert run(core.decide_subtask, facts).reason == reason


@pytest.mark.parametrize("facts, fragment", [
    case("no-card-names-card-new", holds_nothing("src/a.py"), "src/a.py: this session holds no card. Write one with "
         "`python mkway/engine/mkway.py card new <title>`"),
    case("no-card-names-card-take", holds_nothing("src/a.py"), "and take it with `python mkway/engine/mkway.py card take <id>`"),
    case("no-card-ends-with-the-report-route", holds_nothing("src/a.py"), f"the owner opens it. {ROUTE}"),
    case("tampered-names-the-owners-way", subtask(register_problem="the seal differs"),
         f"the seal differs; nothing is edited until the owner checks it: {FIX}"),
    case("proposed-names-the-command", subtask(card_status="proposed"),
         "src/a.py: CARD-001 is proposed in the register; edits need it open: the owner's "
         "`python mkway/engine/mkway.py card open CARD-001`."),
    case("waiting-has-its-own-command", subtask(card_status="waiting"),
         "edits need it open: `python mkway/engine/mkway.py card set CARD-001 open` (or the owner's `card open CARD-001`)."),
    case("not-in-the-register-says-so", subtask(card_found=False), "CARD-001 is not in the register"),
    case("paths-changed-lists-the-recorded-set", subtask(now_paths=frozenset()),
         "the Paths of CARD-001 differ from the set the owner's `card open` recorded (lib/; src/a.py); restore them"),
    case("paths-changed-reads-none-for-an-empty-record", subtask(recorded=frozenset(), now_paths=frozenset({"x"})),
         "recorded (none)"),
    case("outside-names-the-paths-and-the-way-out", subtask("src/b.py"),
         "src/b.py is not in the Paths of CARD-001 (lib/; src/a.py); the lead that ordered the card adds it to its Paths: "
         "`python mkway/engine/mkway.py card paths CARD-001 --add <entry>` (the card file's Paths must already name it), "
         "or write a new card"),
    case("the-first-refused-path-is-the-one-named", subtask("src/a.py", "src/b.py", "src/c.py"),
         "src/b.py is not in the Paths"),
])
def test_the_subtask_refusal_names_the_path_the_state_and_the_way_out(facts, fragment):
    """Catches: a refusal that does not say what is wrong or how the session gets out (the card commands, the owner's `card open`, the Paths the owner recorded)."""
    assert fragment in run(core.decide_subtask, facts).text


@pytest.mark.parametrize("facts, expected", [
    case("only-the-judged-paths", subtask("notes/x.md", "src/a.py", None, ".", CARD_FILE, ORDER, "src/b.py",
                                          lead_may_write=frozenset({ORDER})), ("src/a.py", "src/b.py")),
    case("nothing-left", subtask("notes/x.md", None), ()),
])
def test_pending_lists_only_the_paths_the_card_rules_still_judge(facts, expected):
    """Catches: a shell that reads the register for a call whose paths no card rule judges, or skips one that is judged."""
    assert core.pending(facts) == expected


# ---- the lead gate ------------------------------------------------------------------------------------------------------

def lead(**kw):
    base = dict(is_lead=True, ask_dir=ASKS, writable=frozenset({ORDER, "mkway/asks/q_ask.md", "mkway/asks/q_sources.md"}))
    base.update(kw)
    return core.LeadFacts(**base)


@pytest.mark.parametrize("facts, reason", [
    # every combination of: is a lead x the path (outside the repository, the root, a path it may write, another path)
    case("lead-outside", lead(paths=(None,)), "write-outside-root"),  # changed by MW-103 (R255): an outside path with no matched record is refused; R274-D2: the common reason
    case("lead-root", lead(paths=(".",)), "lead-no-edit"),
    case("lead-own-order", lead(paths=(ORDER,)), None),
    case("lead-asks-file", lead(paths=("mkway/asks/q_ask.md",)), None),
    case("lead-code", lead(paths=("src/app.py",)), "lead-no-edit"),
    case("lead-card-file-of-an-open-card", lead(paths=(CARD_FILE,)), "lead-no-edit"),
    case("lead-other-leads-order", lead(paths=("mkway/cards/CARD-002-theirs/ORDER.md",)), "lead-no-edit"),
    case("lead-register", lead(paths=("mkway/cards/REGISTER.md",)), "lead-no-edit"),
    case("lead-path-that-climbs-out-of-asks", lead(paths=("mkway/asks/sub/deep.md.bak/../../../x.py",)), "lead-no-edit"),
    case("no-lead-outside", lead(is_lead=False, paths=(None,)), None),
    case("no-lead-root", lead(is_lead=False, paths=(".",)), None),
    case("no-lead-own-order", lead(is_lead=False, paths=(ORDER,)), None),
    case("no-lead-code", lead(is_lead=False, paths=("src/app.py",)), None),
    # several paths: the second decides when the first is fine; an outside path never counts
    case("lead-two-allowed", lead(paths=(ORDER, "mkway/asks/q_ask.md")), None),
    case("lead-allowed-then-code", lead(paths=(ORDER, "src/app.py")), "lead-no-edit"),
    case("lead-outside-then-allowed", lead(paths=(None, ORDER)), "write-outside-root"),  # changed by MW-103 (R255): the outside path is refused first; R274-D2: the common reason
])
def test_the_lead_edit_verdict(facts, reason):
    """Catches: a registered lead that writes code, a card file after it is opened, another lead's order or the register; a lead locked out of its own order or the asks; and a session that is no lead judged by the lead rule."""
    assert run(core.decide_lead_edit, facts).reason == reason


@pytest.mark.parametrize("fragment", [
    case("names-the-path", "src/app.py: a lead orders work and does not do it;"),
    case("names-the-order-file", "it writes only `<card folder>/ORDER.md` of a card it ordered"),
    case("names-the-card-file-rule", "`<card folder>/CARD.md` of a card it ordered while the card is proposed"),
    case("names-the-asks-folder", "and the asks folder `mkway/asks`"),
    case("names-the-owners-way", "the owner ends the lead role with `mkway lead remove <id-prefix>` in their own terminal"),
    case("names-the-builder-route", "hand the work to a builder (`mkway card new <title>`)"),
])
def test_the_lead_edit_refusal_says_what_a_lead_may_write_and_how_to_end_the_role(fragment):
    """Catches: a lead refusal that does not name the allowed paths or the owner's way out."""
    assert fragment in run(core.decide_lead_edit, lead(paths=("src/app.py",))).text


def shell(*writes, **kw):
    return lead(writes=tuple((p, p) for p in writes), **kw)


@pytest.mark.parametrize("facts, reason", [
    case("no-lead-everything-at-once", lead(is_lead=False, takes_card=True, writes=(("src/app.py", "src/app.py"),),
                                            writes_anywhere=True), None),
    case("lead-reads-only", lead(), None),
    case("lead-card-take", lead(takes_card=True), "lead-no-take"),
    case("lead-take-wins-over-a-bad-write", lead(takes_card=True, writes=(("src/app.py", "src/app.py"),)), "lead-no-take"),
    case("lead-writes-its-order", shell(ORDER), None),
    case("lead-writes-an-asks-file", shell("mkway/asks/q_ask.md"), None),
    case("lead-writes-outside", lead(writes=(("/dev/null", None),)), "write-outside-root"),  # changed by MW-103 (R255): an outside write with no matched record is refused; R274-D2: the common reason
    case("lead-redirects-into-code", shell("src/app.py"), "lead-no-edit"),
    case("lead-copies-into-code", shell("src/b.txt"), "lead-no-edit"),
    case("lead-appends-to-the-register", shell("mkway/cards/REGISTER.md"), "lead-no-edit"),
    case("lead-writes-the-root", lead(writes=((".", "."),)), "lead-no-edit"),
    case("lead-order-then-code", shell(ORDER, "src/c.py"), "lead-no-edit"),
    case("lead-program-that-writes-anywhere", lead(writes_anywhere=True), "lead-no-edit"),
    case("lead-computed-path-with-an-outside-form", lead(writes=(("x", None),), writes_anywhere=True), "write-outside-root"),  # R274-D2: the common reason
    case("lead-variable-path", lead(writes=(("$HOME/x.py", ORDER),)), "lead-no-edit"),
    case("lead-glob-star-path", lead(writes=(("src/*.py", ORDER),)), "lead-no-edit"),
    case("lead-glob-class-path", lead(writes=(("src/[ab].py", ORDER),)), "lead-no-edit"),
    case("lead-backtick-path", lead(writes=(("`pwd`/x", ORDER),)), "lead-no-edit"),
    case("lead-percent-path", lead(writes=(("%TEMP%/x", ORDER),)), "lead-no-edit"),
    case("lead-substitution-path", lead(writes=(("$(pwd)/x", ORDER),)), "lead-no-edit"),
    case("lead-brace-path", lead(writes=(("{a,b}.py", ORDER),)), "lead-no-edit"),
    case("lead-plain-path-that-looks-alike", lead(writes=(("src/a.py", ORDER),)), None),
])
def test_the_lead_shell_verdict(facts, reason):
    """Catches: a lead whose command takes a card, writes code or the register, runs a program that can write anywhere, or writes a path the gate cannot read; and a lead or a builder blocked from reads and from its own files."""
    assert run(core.decide_lead_shell, facts).reason == reason


@pytest.mark.parametrize("facts, fragment", [
    case("take-names-the-builders-command", lead(takes_card=True), "`mkway card take` is the builder's command"),
    case("take-names-the-owners-way", lead(takes_card=True), "or the owner ends the lead role with `mkway lead remove <id-prefix>`"),
    case("unreadable-path-is-named", lead(writes=(("$HOME/x.py", ORDER),)),
         "$HOME/x.py (a path the gate cannot read: write a plain path with no variable or wildcard, or use the edit tool)"),  # R274-D2: the old fragment plus the R274a 8.7 way out
    case("anywhere-is-explained", lead(writes_anywhere=True),
         "this command may write anywhere (a computed path, a variable, or a program that can write anywhere)"),
    case("other-path-names-the-owners-way", shell("src/app.py"), "`mkway lead remove <id-prefix>`"),
])
def test_the_lead_shell_refusal_names_the_reason_and_the_way_out(facts, fragment):
    """Catches: a refusal that does not say why the command is refused or who can end the lead role."""
    assert fragment in run(core.decide_lead_shell, facts).text


def notices(n):
    return tuple({"id": f"n{i}", "body": f"body {i}"} for i in range(n))


@pytest.mark.parametrize("facts, reason", [
    case("lead-with-notices", lead(unacked=notices(1)), "lead-notices-unacked"),
    case("lead-with-none", lead(unacked=()), None),
    case("no-lead-with-notices", lead(is_lead=False, unacked=notices(1)), None),
    case("no-lead-with-none", lead(is_lead=False, unacked=()), None),
])
def test_the_lead_reminder_verdict(facts, reason):
    """Catches: a reminder to a session that is no lead, or silence for a lead with unacked notices."""
    assert run(core.decide_lead_remind, facts).reason == reason


@pytest.mark.parametrize("n, text", [
    case("one-notice", 1, "you have 1 unacked notice: n0: body 0 (`mkway ack n0`)"),
    case("three-notices", 3, "you have 3 unacked notices: n0: body 0 (`mkway ack n0`) | n1: body 1 (`mkway ack n1`) | "
                             "n2: body 2 (`mkway ack n2`)"),
    case("five-notices-no-more-line", 5, "you have 5 unacked notices: n0: body 0 (`mkway ack n0`) | n1: body 1 "
                                         "(`mkway ack n1`) | n2: body 2 (`mkway ack n2`) | n3: body 3 (`mkway ack n3`) | "
                                         "n4: body 4 (`mkway ack n4`)"),
    case("seven-notices-five-shown", 7, "you have 7 unacked notices: n0: body 0 (`mkway ack n0`) | n1: body 1 "
                                        "(`mkway ack n1`) | n2: body 2 (`mkway ack n2`) | n3: body 3 (`mkway ack n3`) | "
                                        "n4: body 4 (`mkway ack n4`) | and 2 more: `mkway leads`"),
])
def test_the_lead_reminder_text_shows_five_notices_at_most_and_counts_the_rest(n, text):
    """Catches: a reminder that floods the prompt with every notice, or drops the count of the rest."""
    verdict = run(core.decide_lead_remind, lead(unacked=notices(n)))
    assert (verdict.kind, verdict.text) == (core.ALLOW_LINE, text)


# ---- the message gate ---------------------------------------------------------------------------------------------------

MINE = "m-20261112000000-aaaaaa"


def send(message=f"mkway inbox {MINE}", **kw):
    tool_input = kw.pop("tool_input", {"to": "somebody", "message": message})
    base = dict(tool_name="SendMessage", tool_input=tool_input, session_id="lead-a", row_is_senders=True,
                pinged=False, report_route=ROUTE)
    base.update(kw)
    return core.MessageFacts(**base)


@pytest.mark.parametrize("facts, reason", [
    # MW-110: `message-not-in-inbox` is removed (R269c): every body that is not a first ping of the sender's own row passes
    case("ping-line-allows", send(f"mkway inbox {MINE}"), None),
    case("ping-line-with-a-final-newline-allows", send(f"mkway inbox {MINE}\n"), None),
    case("ping-line-with-padding-allows", send(f"  mkway inbox {MINE}  \n"), None),
    case("ping-line-with-crlf-allows", send(f"mkway inbox {MINE}\r\n"), None),
    case("words-after-the-line", send(f"mkway inbox {MINE} please build it"), None),
    case("words-before-the-line", send(f"Hi!\nmkway inbox {MINE}"), None),
    case("a-second-text-line", send(f"mkway inbox {MINE}\nand also this"), None),
    case("a-code-fence", send(f"`mkway inbox {MINE}`"), None),
    case("a-prefix-in-front", send(f"run: mkway inbox {MINE}"), None),
    case("a-double-space", send(f"mkway  inbox {MINE}"), None),
    case("a-chained-command", send(f"mkway inbox {MINE};ls"), None),
    case("no-id", send("mkway inbox"), None),
    case("an-id-that-climbs", send("mkway inbox ../x"), None),
    case("two-ids", send("mkway inbox a b"), None),
    case("an-empty-body", send(""), None),
    case("a-blank-body", send("   "), None),
    case("plain-words", send("build the thing"), None),
    case("two-ping-lines", send(f"mkway inbox {MINE}\r\nmkway inbox {MINE}"), None),
    case("a-body-that-is-none", send(None), None),
    case("a-body-that-is-a-number", send(7), None),
    case("a-body-that-is-a-list", send([f"mkway inbox {MINE}"]), None),
    case("no-message-field", send(tool_input={"to": "x"}), None),
    case("no-tool-input", send(tool_input=None), None),
    # the sender: a session id the hook gave, and a row the session wrote
    case("no-session-id", send(session_id=None), None),
    case("empty-session-id", send(session_id=""), None),
    case("blank-session-id", send(session_id="   "), None),
    case("session-id-not-text", send(session_id=5), None),
    case("a-row-that-is-not-the-senders", send(row_is_senders=False), None),
    case("a-row-that-is-the-senders", send(row_is_senders=True), None),
    # message-duplicate: a ping already recorded denies, the first ping allows
    case("second-ping-denies", send(pinged=True), "message-duplicate"),
    case("second-ping-with-another-to-denies", send(tool_input={"to": "another name [3fa9c1]", "message": f"mkway inbox {MINE}"},
                                                    pinged=True), "message-duplicate"),
    case("first-ping-allows", send(pinged=False), None),
    # the cases that are not this gate's
    case("another-tool-allows", send("hello", tool_name="Write"), None),
    case("idle-subscription-with-an-empty-message-allows", send(tool_input={"to": "x", "message": "", "notify_when_idle": True}), None),
    case("idle-subscription-with-no-message-allows", send(tool_input={"to": "x", "notify_when_idle": True}), None),
    case("empty-message-without-the-flag-passes", send(tool_input={"message": "", "notify_when_idle": False}),
         None),
    case("text-with-the-flag-passes", send(tool_input={"message": "hello", "notify_when_idle": True}),
         None),
])
def test_the_send_verdict(facts, reason):
    """Catches: MW-110: free text, another sender's row, no row or no readable sender refused as before (`message-not-in-inbox` is removed); a second ping for one row let through; a good ping, an idle subscription or another tool refused."""
    assert run(core.decide_send, facts).reason == reason


@pytest.mark.parametrize("facts, fragment", [
    case("duplicate-names-the-id", send(pinged=True), f"the ping for {MINE} was already sent: the recipient has it"),
    case("duplicate-names-the-way", send(pinged=True), "write another row with `mkway send --to <id-prefix> --kind <kind> "
                                                      "--file <body> --reply-to <id>` and send its ping line"),
])
def test_the_send_refusal_names_the_reason_and_the_way_out(facts, fragment):
    """Catches: a refusal of a second ping that does not name the id and the way out (MW-110: the not-in-inbox texts left with that refusal)."""
    assert fragment in run(core.decide_send, facts).text


@pytest.mark.parametrize("facts, records", [
    case("allowed-ping-carries-its-row", send(f"mkway inbox {MINE}\n"), (("ping", {"id": MINE, "session": "lead-a"}),)),
    case("duplicate-carries-none", send(pinged=True), ()),
    case("another-senders-row-carries-none", send(row_is_senders=False), ()),
    case("words-carry-none", send("words"), ()),
    case("idle-subscription-carries-none", send(tool_input={"to": "x", "notify_when_idle": True}), ()),
])
def test_only_an_allowed_ping_carries_the_row_the_shell_records(facts, records):
    """Catches: a refused ping that is recorded (the row would then block the real one), or an allowed ping that is not."""
    assert run(core.decide_send, facts).records == records


@pytest.mark.parametrize("tool_input, row_id", [
    case("exact-line", {"message": f"mkway inbox {MINE}"}, MINE),
    case("line-with-a-final-newline", {"message": f"mkway inbox {MINE}\n"}, MINE),
    case("line-with-words", {"message": f"mkway inbox {MINE} x"}, None),
    case("message-none", {"message": None}, None),
    case("no-message", {}, None),
    case("no-input", None, None),
    case("input-is-text", "text", None),
    case("message-is-a-number", {"message": 7}, None),
])
def test_the_row_id_the_shell_looks_up_is_named_only_for_a_body_the_gate_accepts(tool_input, row_id):
    """Catches: a shell that looks up a row for a body the gate refuses, or a gate that judges another id than the one looked up."""
    assert core.ping_row_id(tool_input) == row_id


def items(n):
    return tuple(f"m{i} order from lead-a: work {i} (`mkway inbox m{i}`, then `mkway ack m{i}`)" for i in range(n))


@pytest.mark.parametrize("facts, reason", [
    # every combination of: a session id x a lead x an unacked item
    case("session-no-lead-item", core.MessageFacts(session_id="build-a1", unacked=items(1)), "inbox-unacked"),
    case("session-no-lead-nothing", core.MessageFacts(session_id="build-a1"), None),
    case("session-lead-item", core.MessageFacts(session_id="lead-a", is_lead=True, unacked=items(1)), None),
    case("session-lead-nothing", core.MessageFacts(session_id="lead-a", is_lead=True), None),
    case("no-id-no-lead-item", core.MessageFacts(session_id=None, unacked=items(1)), None),
    case("no-id-no-lead-nothing", core.MessageFacts(session_id=None), None),
    case("no-id-lead-item", core.MessageFacts(session_id=None, is_lead=True, unacked=items(1)), None),
    case("no-id-lead-nothing", core.MessageFacts(session_id=None, is_lead=True), None),
    case("empty-id-item", core.MessageFacts(session_id="", unacked=items(1)), None),
    case("number-id-item", core.MessageFacts(session_id=5, unacked=items(1)), None),
])
def test_the_prompt_reminder_verdict(facts, reason):
    """Catches: a lead told twice (its own reminder exists), a session with no id judged, or a session with unacked items left unwarned."""
    assert run(core.decide_message_remind, facts).reason == reason


@pytest.mark.parametrize("n, text", [
    case("one-item", 1, "you have 1 unacked inbox item: " + items(1)[0]),
    case("five-items-no-more-line", 5, "you have 5 unacked inbox items: " + " | ".join(items(5))),
    case("six-items-five-shown", 6, "you have 6 unacked inbox items: " + " | ".join(items(6)[:5]) + " | and 1 more: `mkway board`"),
])
def test_the_prompt_reminder_text_shows_five_items_at_most_and_counts_the_rest(n, text):
    """Catches: a reminder that floods the prompt, or drops the count of the rest."""
    verdict = run(core.decide_message_remind, core.MessageFacts(session_id="build-a1", unacked=items(n)))
    assert (verdict.kind, verdict.text) == (core.ALLOW_LINE, text)


def orders(n):
    return tuple({"id": f"o{i}", "from": "lead-a", "first": f"work {i}"} for i in range(n))


@pytest.mark.parametrize("facts, reason", [
    # every combination of: a session id x an old unacked order
    case("session-with-an-old-order", core.MessageFacts(session_id="build-a1", old_orders=orders(1)), "orders-unacked"),
    case("session-with-none", core.MessageFacts(session_id="build-a1"), None),
    case("no-id-with-an-old-order", core.MessageFacts(session_id=None, old_orders=orders(1)), None),
    case("no-id-with-none", core.MessageFacts(session_id=None), None),
    case("empty-id-with-an-old-order", core.MessageFacts(session_id="", old_orders=orders(1)), None),
])
def test_the_stop_reminder_verdict(facts, reason):
    """Catches: a Stop that stays silent about an order unacked past the limit, or a session with no id judged."""
    assert run(core.decide_message_stop, facts).reason == reason


@pytest.mark.parametrize("facts, text", [
    case("one-order-default-minutes", core.MessageFacts(session_id="s", minutes=30.0, old_orders=orders(1)),
         "1 order unacked for more than 30 minutes: o0 from lead-a: work 0 (`mkway inbox o0`, then `mkway ack o0`)"),
    case("two-orders-fractional-minutes", core.MessageFacts(session_id="s", minutes=1.5, old_orders=orders(2)),
         "2 orders unacked for more than 1.5 minutes: o0 from lead-a: work 0 (`mkway inbox o0`, then `mkway ack o0`) | "
         "o1 from lead-a: work 1 (`mkway inbox o1`, then `mkway ack o1`)"),
    case("seven-orders-five-shown", core.MessageFacts(session_id="s", minutes=30.0, old_orders=orders(7)),
         "7 orders unacked for more than 30 minutes: " + " | ".join(
             f"o{i} from lead-a: work {i} (`mkway inbox o{i}`, then `mkway ack o{i}`)" for i in range(5))),
])
def test_the_stop_reminder_text_names_each_order_the_age_and_the_two_commands(facts, text):
    """Catches: a reminder that leaves out the id, the sender, the age limit or the `inbox` and `ack` commands, or shows more than five."""
    verdict = run(core.decide_message_stop, facts)
    assert (verdict.kind, verdict.text) == (core.ALLOW_LINE, text)


# ---- the records step of the post group ---------------------------------------------------------------------------------

N1, N2 = "0123456789abcdef0123456789abcdef", "fedcba9876543210fedcba9876543210"
TWO = f"noise\nmkway-ok new CARD-001 {N1}\nmore\nmkway-ok take CARD-001 {N2}  \n"


@pytest.mark.parametrize("response, claims", [
    case("two-lines-in-a-text", TWO, (("new", "CARD-001", N1), ("take", "CARD-001", N2))),
    case("two-lines-in-stdout", {"stdout": TWO}, (("new", "CARD-001", N1), ("take", "CARD-001", N2))),
    case("two-lines-in-output", {"output": TWO}, (("new", "CARD-001", N1), ("take", "CARD-001", N2))),
    case("stdout-not-text-falls-to-output", {"stdout": 5, "output": TWO}, (("new", "CARD-001", N1), ("take", "CARD-001", N2))),
    case("none", None, ()),
    case("empty-text", "", ()),
    case("empty-mapping", {}, ()),
    case("stdout-a-number", {"stdout": 5}, ()),
    case("a-number", 7, ()),
    case("short-nonce", f"mkway-ok new CARD-001 {N1[:-1]}", ()),
    case("line-not-at-the-start", f"x mkway-ok new CARD-001 {N1}", ()),
    case("no-value", f"mkway-ok new {N1}", ()),
    case("nonce-not-hex", "mkway-ok new CARD-001 NOT-HEX", ()),
])
def test_each_ok_line_of_the_stdout_is_a_claim_read_in_order(response, claims):
    """Catches: a post group that reads a forged, truncated or mid-line `mkway-ok` text as a claim, misses a PowerShell string response, or reads the lines in another order."""
    assert run(core.ok_lines, response) == claims


@pytest.mark.parametrize("kind, session, rows", [
    case("new-with-a-session", "new", "s1", (("record", {"kind": "new", "value": "V"}), ("ordered", {"card": "V", "session": "s1"}))),
    case("new-with-no-session", "new", None, (("record", {"kind": "new", "value": "V"}),)),
    case("new-with-an-empty-session", "new", "", (("record", {"kind": "new", "value": "V"}),)),
    case("new-with-a-blank-session", "new", "  ", (("record", {"kind": "new", "value": "V"}),)),
    case("new-with-a-number-session", "new", 5, (("record", {"kind": "new", "value": "V"}),)),
    case("take", "take", "s1", (("record", {"kind": "take", "value": "V"}),)),
    case("release", "release", "s1", (("record", {"kind": "release", "value": "V"}),)),
    case("search", "search", "s1", (("record", {"kind": "search", "value": "V"}),)),
    case("ask-default", "ask-default", "s1", (("record", {"kind": "ask-default", "value": "V"}),)),
])
def test_a_granted_line_writes_the_record_and_only_a_new_card_asks_for_the_orderer_cell(kind, session, rows):
    """Catches: a `new` card that keeps reading `owner` although the session is known, an orderer cell written with no session id, or an orderer cell for a kind that is no new card."""
    assert run(core.granted, kind, "V", session) == rows


@pytest.mark.parametrize("verdict, kind, reason, path", [
    case("record-failed", core.record_failed("OSError", "mkway/state/records.jsonl"), core.REFUSE, "post-record-failed",
         "mkway/state/records.jsonl"),
    case("orderer-cell-failed", core.ordered_failed("RegisterError", "CARD-003", "cards/REGISTER.md"), core.REFUSE,
         "post-record-failed", "cards/REGISTER.md"),
    case("agent-record-failed-start", core.agent_record_failed("OSError", "mkway/state/agents.jsonl", "SubagentStart"),
         core.REFUSE, "agent-record-failed", "mkway/state/agents.jsonl"),
    case("agent-record-failed-stop", core.agent_record_failed("OSError", "mkway/state/agents.jsonl", "SubagentStop"),
         core.ALLOW_LINE, "agent-record-failed", "mkway/state/agents.jsonl"),
])
def test_a_record_that_cannot_be_written_is_a_warn_line_and_never_a_refusal(verdict, kind, reason, path):
    """Catches: a failed record that lets the session go on believing it recorded (R271c-D1), a text that does not name the path the engine could not write, or a refusal on `SubagentStop` (it keeps a finished agent going)."""
    assert (verdict.kind, verdict.reason, path in verdict.text) == (kind, reason, True)


@pytest.mark.parametrize("bad", [
    case("refuse-without-reason", dict(kind=core.REFUSE)),
    case("line-without-text", dict(kind=core.ALLOW_LINE, reason="r")),
    case("unknown-kind", dict(kind="block", reason="r", text="t")),
])
def test_a_refuse_or_a_line_needs_a_reason_and_a_text_and_the_kind_is_known(bad):
    """Catches: a verdict built without the reason id the manifest declares or the text the session reads."""
    with pytest.raises(ValueError):
        core.Verdict(**bad)
