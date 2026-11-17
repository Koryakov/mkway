"""Card MW-039: every gate's refusal is proven through the REAL hook command.

`test_e2e.py` promises this file; until now every refusal was tested in process (`gate_call`, `dispatch.run`, the
in-process CLI). Here one engine install (module fixture, a scratch git repository, the task folder below the git top)
runs each gate's refusal the way Claude Code does: the generated command line, through the shell, `CLAUDE_PROJECT_DIR`
in the environment, the working folder the task folder, a real hook payload on stdin with absolute paths. The verdict
is read from the hook's JSON (`tests/_hook_driver.py::decision`): a PreToolUse refusal is exit 0 plus
`permissionDecision: deny`, a Stop refusal exit 0 plus `decision: block`; the exit code alone says nothing.

One parametrized row per refusal reason id the manifest declares for a PreToolUse or a Stop gate; each row names the
manifest entry and the exact reason id. One allow row per gate. The meta-test fails when a declared reason id has no
row and no stated exemption. Synthetic names and ids only.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pytest

from _engine import REPO
from _hook_driver import Decision, Fired, HookRun, decision, install_project

pytestmark = pytest.mark.engine_repo

CLI = "python mkway/engine/mkway.py"
BUILDER, OTHER, LEAD, NOCARD = "b1", "b2", "L1", "n1"
STOP_ASK, STOP_PING_NO, STOP_FREE, STOP_PING_YES = "n8", "b8", "n9", "b9"  # one fresh session per Stop case (R213 B, R213b)
CARD = "CARD-001"
# MW-072: `tests/test_n.py` for the red proof rows; MW-090 (T7 decision: R225): `tests/test_m.py`, the two tests at HEAD the case_map rows move
CARD_PATHS = ("src/", "tests/test_a.py", "tests/test_n.py", "tests/test_m.py", "out/")
VALID_ASK = "default: none\ndeadline: none\nblocked: none\nreversible: yes\nstatus: open\n"
SESSION_SOURCES = "kind: session\nchecked: ListAgents\n"
TIME_LIMIT_SECONDS = 120


# ---- the declared reason ids --------------------------------------------------------------------------------------

def declared() -> set:
    """{(manifest entry name, reason id)} of every gate that has code and runs on PreToolUse or Stop."""
    manifest = json.loads((REPO / "engine" / "manifest.json").read_text(encoding="utf-8"))
    return {(e["name"], r) for e in manifest["entries"]
            if e.get("status") == "on" and e.get("function") and e.get("event") in ("PreToolUse", "Stop")
            for r in e.get("reason_ids") or []}


# (entry, reason id) -> why no row can show a refusal. Every one of them is a verdict that is not a refusal, or one
# that no real command can reach.
EXEMPT = {
    ("lock.shell", "write-target-unresolved"):
        "a `log` verdict: the dispatcher writes a row and the call goes ahead; it is never a refusal",
    ("search", "search-unverified"):
        "a `log` verdict: the search gate fails open and writes a row; it is never a refusal",
    ("message.stop", "orders-unacked"):
        "a `warn` verdict: the Stop gate says it is a reminder line and never a block",
    ("reader_allowlist", "reader-read-refused"):
        "MW116-D2: the hook of the reader agent's frontmatter, no settings hook: a refusal through the real hook process "
        "is shown by tests/test_mw116_way_out.py::test_the_way_out_of_reader_read_refused_is_a_listed_file",
    ("reader_allowlist", "reader-busy"):
        "MW116-D2: the refusal of the command `mkway reader start`, no hook call: shown by "
        "tests/test_mw116_way_out.py::test_the_way_out_of_reader_busy_is_to_end_the_run_and_start_again",
    ("reader_allowlist", "verdict-reader-unguarded"):
        "MW116-D2: the refusal of the command `mkway verdict add`, no hook call: shown by "
        "tests/test_mw116_way_out.py::test_the_way_out_of_verdict_reader_unguarded_is_a_guarded_rerun",
    ("message.session", "session-id-unset"):
        "a `warn` verdict (MW-110): the transition line for a session whose launcher sets no variable; it is never a "
        "refusal, and tests/test_mw110_e2e.py shows it through the real hook",
    ("outbox_check.stop", "outbox-changed-after-check"):
        "a `warn` verdict: the Stop gate says it is a reminder and never a block",
    ("outbox_check.stop", "verdict-not-enforced"):
        "a `warn` verdict: the Stop gate says the blind verdict is not enforced and never blocks (MW-068, decision: R179)",
    ("ping.stop", "ping-skipped"):
        "a `log` verdict: the second Stop of a turn passes and writes the record row (MW-076, decision: R186); it is "
        "never a refusal",
    ("ping.stop", "ping-skipped-listed"):
        "a `warn` verdict: the lead's Stop lists a skipped ping once and never blocks (MW-076, decision: R186)",
    ("lock.shell", "gate-git-timeout"):
        "needs a git read that does not answer within the gate's limit; no real command makes git hang on demand",
    ("commit_tests", "commit-tests-still-red"):
        "a `warn` verdict (MW-056): the allow line of a commit that leaves another open card's old red; it is never a "
        "refusal, and tests/test_mw056_e2e.py shows it through the real hook",
    ("commit_tests", "shared-record-busy"):
        "a refusal when the append lock of a shared card record file stays busy beyond the wait (MW-129, R310 1 a): no real "
        "call can hold another writer's lock through the real hook; its way out (release the lock, repeat the call) is run "
        "by tests/shell/test_mw129_shared_records_shell.py::test_the_way_out_of_shared_record_busy_is_to_repeat_the_call",
    ("commit_tests", "red-record-partial"):
        "a `warn` verdict (MW-131, R322): an allow line, not a refusal, for the legacy rows of the card's own red record that "
        "the search limit left out after a row was found; tests/shell/test_mw131_own_record_shell.py::"
        "test_the_limit_running_out_after_a_found_row_allows_with_the_found_rows_and_one_line asserts that the call is allowed "
        "and that the line is exact",
    ("commit_tests", "retire-no-decision"):
        "a refusal of a retirement commit (MW-134, R347, R348): it needs a card with a red record, a history of commits with its "
        "rows and a ledger, which a real hook call cannot build on demand; its way out is run by "
        "tests/shell/test_mw134_retire_shell.py::test_the_way_out_of_retire_no_decision_is_a_message_that_names_a_decision",
    ("commit_tests", "retire-decision-not-in-ledger"):
        "a refusal of a retirement commit (MW-134, R347, R348): it needs a card with a red record, a history of commits with its "
        "rows and a ledger, which a real hook call cannot build on demand; its way out is run by "
        "tests/shell/test_mw134_retire_shell.py::test_the_way_out_of_retire_decision_not_in_ledger_is_a_decision_that_is_a_row_of_the_ledger",
    ("commit_tests", "retire-decision-closed"):
        "a refusal of a retirement commit (MW-134, R347, R348): it needs a card with a red record, a history of commits with its "
        "rows and a ledger, which a real hook call cannot build on demand; its way out is run by "
        "tests/shell/test_mw134_retire_shell.py::test_the_way_out_of_retire_decision_closed_is_a_decision_that_is_in_force",
    ("commit_tests", "retire-decision-by-self"):
        "a refusal of a retirement commit (MW-134, R347, R348): it needs a card with a red record, a history of commits with its "
        "rows and a ledger, which a real hook call cannot build on demand; its way out is run by "
        "tests/shell/test_mw134_retire_shell.py::test_the_way_out_of_retire_decision_by_self_is_a_decision_another_session_wrote",
    ("commit_tests", "retire-no-ledger"):
        "a refusal of a retirement commit (MW-134, R347, R348): it needs a card with a red record, a history of commits with its "
        "rows and a ledger, which a real hook call cannot build on demand; its way out is run by "
        "tests/shell/test_mw134_retire_shell.py::test_the_way_out_of_retire_no_ledger_is_a_ledger_row_of_another_session",
    ("commit_tests", "retire-right-not-red"):
        "a refusal of a retirement commit (MW-134, R347, R348): it needs a card with a red record, a history of commits with its "
        "rows and a ledger, which a real hook call cannot build on demand; its way out is run by "
        "tests/shell/test_mw134_retire_shell.py::test_the_way_out_of_retire_right_not_red_is_a_right_side_that_was_seen_red",
    ("commit_tests", "retire-left-failing"):
        "a refusal of a retirement commit (MW-134, R347, R348): it needs a card with a red record, a history of commits with its "
        "rows and a ledger, which a real hook call cannot build on demand; its way out is run by "
        "tests/shell/test_mw134_retire_shell.py::test_the_way_out_of_retire_left_failing_is_a_file_that_collects",
    ("commit_files", "verdict-unproven"):
        "a refusal of the commit of a verdict file whose rows have no record of `verdict add`; it needs a card with real "
        "verdict records, so tests/test_mw102_e2e.py shows it through the real hook",
    ("commit_files", "verdict-stale"):
        "a refusal of the commit of a verdict file whose node's Acceptance rows changed after the verdict (MW-117); it needs a "
        "card with real verdict records, so tests/test_mw102_e2e.py shows it through the real hook",
    ("lock.shell", "register-busy"):
        "raised only by a register WRITE waiting for the register lock; the gate only reads the register (seal check), "
        "so no hook call can reach it",
}


# ---- what a row yields --------------------------------------------------------------------------------------------

@dataclass
class Call:
    event: str
    session: str
    tool: Optional[str] = None
    tool_input: Optional[dict] = None
    extra: dict = field(default_factory=dict)


def bash(command, session=BUILDER) -> Call:
    return Call("PreToolUse", session, "Bash", {"command": command})


def write(p, rel, content="x\n", session=BUILDER) -> Call:
    return Call("PreToolUse", session, "Write", {"file_path": p.path(rel), "content": content})


def commit(message="CARD-001 change", session=BUILDER) -> Call:
    return bash(f'git commit -m "{message}"', session)


ROWS = []    # (function, entry, reason id)
ALLOWS = []  # (function, entry)


def refusal(entry, reason):
    def mark(fn):
        ROWS.append(pytest.param(fn, entry, reason, id=fn.__name__))
        return fn
    return mark


def allowed(entry):
    def mark(fn):
        ALLOWS.append(pytest.param(fn, entry, id=fn.__name__))
        return fn
    return mark


class staged:
    """Files staged with `git add -f` (the way a builder stages them), unstaged again after the row."""

    def __init__(self, p, files):
        self.p, self.files = p, files

    def __enter__(self):
        for rel, content in self.files.items():
            if isinstance(content, bytes):
                self.p.write(rel, binary=content)
            else:
                self.p.write(rel, content)
            self.p.git("add", "-f", "--", rel)
        return self

    def __exit__(self, *_):
        for rel in self.files:
            self.p.git("rm", "--cached", "-q", "-f", "--", rel, check=False)
            try:
                (self.p.root / rel).unlink()
            except OSError:
                pass


class lead_orders_card:
    """MW-053: the owner gives CARD to LEAD (the `Ordered by` column added first, `cards.approver` orderer); the card's
    `CARD.md` is changed in the working tree. Everything is put back after the row: the bytes, the order, the profile."""

    def __init__(self, p):
        self.p = p
        self.card = next((p.root / "mkway" / "cards").glob(f"{CARD}-*"))
        self.rel = self.card.relative_to(p.root).as_posix()

    def __enter__(self):
        self.old = self.p.profile(**{"cards.approver": "orderer"})
        self.p.owner("card", "resync", "--add-ordered-by", check=False)  # the column `give` writes; a second run is a no-op
        self.p.owner("give", CARD, LEAD)
        self.bytes = (self.card / "CARD.md").read_bytes()
        (self.card / "CARD.md").write_bytes(self.bytes + b"\nan order change\n")
        return self

    def __exit__(self, *_):
        (self.card / "CARD.md").write_bytes(self.bytes)
        self.p.owner("give", CARD, "owner")
        self.p.restore_profile(self.old)


class profile_set:
    """The owner's profile edit for one row; the old profile is put back after it."""

    def __init__(self, p, **changes):
        self.p, self.changes = p, changes

    def __enter__(self):
        self.old = self.p.profile(**self.changes)

    def __exit__(self, *_):
        self.p.restore_profile(self.old)


M_FILE = "tests/test_m.py"  # MW-090: two tests at HEAD that the case_map rows remove from the tree
M1, M2 = f"{M_FILE}::test_m1", f"{M_FILE}::test_m2"
N_ID = "tests/test_n.py::test_n"
N_MISSING = "tests/test_n.py::test_missing"
N_RED = 'def test_n():\n    """Catches: a thing."""\n    assert 1 + 1 == 3\n'
DECISION_MESSAGE = "CARD-001 DEC-1 rename"


class deleted:
    """A file of HEAD removed from the index and the working tree for one row, put back after it."""

    def __init__(self, p, rel):
        self.p, self.rel = p, rel

    def __enter__(self):
        self.p.git("rm", "-q", "--", self.rel)
        return self

    def __exit__(self, *_):
        self.p.git("reset", "-q", "HEAD", "--", self.rel)
        self.p.git("checkout", "--", self.rel)


def case_map_rel(p):
    """The case_map.md of the card, relative to the task root."""
    card = next((p.root / "mkway" / "cards").glob(f"{CARD}-*"))
    return card.relative_to(p.root).as_posix() + "/case_map.md"


def decided(p):
    """The profile names a decision pattern, so a commit message with DEC-1 names a decision (no ledger file: the pattern decides)."""
    return profile_set(p, **{"tests.red_proof": {"decision_pattern": "DEC-[0-9]+"}})


# ---- the one install of the module --------------------------------------------------------------------------------

def _card_text(template):
    text = template.replace("| **Paths** | |", "| **Paths** | " + ", ".join(f"`{x}`" for x in CARD_PATHS) + " |")
    text = text.replace("«the owner's words, quoted» — owner, YYYY-MM-DD.", "A synthetic goal for the hook rows.")
    return text.replace("| E1 | item id | value today | value after the change | tests/test_x.py::test_y |",
                        "| E1 | the thing | absent | present | tests/test_a.py::test_a |")


@pytest.fixture(scope="module")
def proj(tmp_path_factory):
    import time
    started = time.perf_counter()
    p = install_project(tmp_path_factory.mktemp("gates"))
    p.owner("card", "new", "Gate card")
    card = next((p.root / "mkway" / "cards").glob(f"{CARD}-*"))
    card_file = card / "CARD.md"
    card_file.write_text(_card_text(card_file.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    p.owner("card", "open", CARD)
    for session in (BUILDER, OTHER, LEAD, NOCARD):  # a start hook each: the sessions are known to the engine
        decision(p.fire("SessionStart", session))
    p.session_shell(LEAD, f"{CLI} lead register")
    p.session_shell(BUILDER, f"{CLI} card take {CARD}")
    p.owner("gate", "on", "lead")  # a registered lead's refusal is only logged while the gate is in watch mode
    p.owner("gate", "on", "ping")  # MW-076: the same for the ping gate, a form gate that starts in watch
    # the trip (a form gate that refuses a third of its calls goes to watch) would hide later rows: switch it off here
    p.profile(**{"gates.trip": {"min_calls": 100000}})
    p.write("src/a.py", "VALUE = 1\n")
    p.write("tests/test_a.py", "def test_a():\n    assert True\n")
    p.write(M_FILE, "def test_m1():\n    assert True\n\n\ndef test_m2():\n    assert True\n")  # MW-090 (T7 decision: R225)
    p.write("red.py", "raise SystemExit(1)\n")
    p.write("green.py", "raise SystemExit(0)\n")
    p.write("slow.py", "import time\ntime.sleep(60)\n")
    p.write("out/d.md", "the document\n")
    p.write("out/del_me.txt", "x\n")
    p.write("msg/body.txt", "a question\n")
    p.write("mkway/asks/.keep-dir", "")
    p.git("add", "-f", "--", "src/a.py", "tests/test_a.py", M_FILE, "red.py", "green.py", "slow.py", "out/d.md")
    p.git("add", "-A", "mkway/cards", "mkway/profile.json")
    p.git("commit", "-q", "-m", "baseline of the hook rows")
    p.started = started
    return p


def _run(p, gen):
    """The row's arrangement runs up to its yield; the real hook runs; the cleanup after the yield runs."""
    try:
        call = next(gen)
        got = decision(p.fire(call.event, call.session, call.tool, call.tool_input, **call.extra))
    finally:
        try:
            next(gen)
        except StopIteration:
            pass
    return got


# ==== refusal rows: the edit group ======================================================================================

@refusal("lock.edit", "lock-closed-edit")
def lock_closed_edit(p):
    yield write(p, "mkway/engine/mkway.py")


@refusal("lock.edit", "lock-closed-edit")
def hold_closed_edit(p):
    """The owner hold (a profile lock target open by default; `mkway hold` closes it)."""
    with profile_set(p, **{"locks.targets": [{"name": "hold", "paths": ["src/hold/"], "open_by_default": True}]}):
        p.owner("hold")
        try:
            yield write(p, "src/hold/h.py")
        finally:
            p.owner("go")


@refusal("lock.edit", "lock-file-by-session")
def lock_file_by_session_edit(p):
    yield write(p, "mkway/locks/x.json")


@refusal("subtask", "no-open-card")
def no_open_card(p):
    yield write(p, "src/a.py", session=NOCARD)


@refusal("outside.edit", "write-outside-root")
def outside_write_outside_root_edit(p):
    yield Call("PreToolUse", BUILDER, "Write", {"file_path": outside_file(p), "content": "x\n"})  # R274e: the session check is its own gate


@refusal("subtask", "card-not-open")
def card_not_open(p):
    p.owner("card", "set", CARD, "waiting")
    try:
        yield write(p, "src/a.py")
    finally:
        p.owner("card", "open", CARD)


@refusal("subtask", "card-paths-changed")
def card_paths_changed(p):
    card_file = next((p.root / "mkway" / "cards").glob(f"{CARD}-*")) / "CARD.md"
    old = card_file.read_bytes()
    card_file.write_bytes(old.replace(b"`out/`", b"`out/`, `docs/`"))
    try:
        yield write(p, "src/a.py")
    finally:
        card_file.write_bytes(old)


@refusal("subtask", "file-not-in-card")
def file_not_in_card_edit(p):
    yield write(p, "docs/x.md")


@refusal("subtask", "register-tampered")
def register_tampered_edit(p):
    register = p.root / "mkway" / "cards" / "REGISTER.md"
    old = register.read_bytes()
    register.write_bytes(old + b" ")
    try:
        yield write(p, "src/a.py")
    finally:
        register.write_bytes(old)


@refusal("lead.edit", "lead-no-edit")
def lead_no_edit_edit(p):
    yield write(p, "src/x.py", session=LEAD)


def outside_file(p) -> str:
    """R274-D2: a file next to the root (never in the list of folders a session may write outside the root)."""
    return (p.root.parent / "outside-the-root" / "a.md").as_posix()


@refusal("lead.edit", "write-outside-root")
def lead_write_outside_root_edit(p):
    yield Call("PreToolUse", LEAD, "Write", {"file_path": outside_file(p), "content": "x\n"})  # R274-D2: the common reason


@refusal("owner_ask.edit", "ask-sources-missing")
def ask_sources_missing(p):
    yield write(p, "mkway/asks/s1_ask.md", VALID_ASK, LEAD)


@refusal("owner_ask.edit", "ask-sources-kind")
def ask_sources_kind(p):
    p.write("mkway/asks/s2_sources.md", "the sources, with no kind line\n")
    yield write(p, "mkway/asks/s2_ask.md", VALID_ASK, LEAD)


@refusal("owner_ask.edit", "ask-sources-lines")
def ask_sources_lines(p):
    p.write("mkway/asks/s3_sources.md", "kind: session\n")
    yield write(p, "mkway/asks/s3_ask.md", VALID_ASK, LEAD)


@refusal("owner_ask.edit", "ask-fields-missing")
def ask_fields_missing(p):
    p.write("mkway/asks/s4_sources.md", SESSION_SOURCES)
    yield write(p, "mkway/asks/s4_ask.md", "just text, no field lines\n", LEAD)


@refusal("owner_ask.edit", "ask-already-open")
def ask_already_open(p):
    p.write("mkway/asks/s5_sources.md", SESSION_SOURCES)
    p.write("mkway/asks/s6_sources.md", SESSION_SOURCES)
    p.session_write(LEAD, "mkway/asks/s5_ask.md", VALID_ASK)  # the lead's first ask: written and recorded by the hooks
    try:
        yield write(p, "mkway/asks/s6_ask.md", VALID_ASK, LEAD)
    finally:
        p.write("mkway/asks/s5_ask.md", VALID_ASK.replace("status: open", "status: answered"))


@refusal("owner_ask.edit", "ask-tool-off")
def ask_tool_off(p):
    yield Call("PreToolUse", BUILDER, "AskUserQuestion", {"questions": [{"question": "which one?"}]})


@refusal("search", "search-missing")
def search_missing(p):
    with profile_set(p, **{"owner_ask.tool_allowed": True}):
        yield Call("PreToolUse", OTHER, "AskUserQuestion", {"questions": [{"question": "which one?"}]})


@refusal("outbox_check.pre", "check-sha-mismatch")
def check_sha_mismatch(p):
    with profile_set(p, **{"outbox": {"dir": "out", "checkers": ["checker"]}}):
        yield write(p, "out/d.md.check.md", "numbers: 1 checked, 0 contradictions\n")


@refusal("outbox_check.pre", "verdict-file-by-command")
def verdict_file_by_command(p):  # MW-080 (decision: R196): a verdict row has one writer, the engine command
    with profile_set(p, **{"paths.exempt": ["tests/verdicts/*.md"]}):
        yield write(p, "tests/verdicts/CARD-001.md", "| Node | Verdict | Reason | By |\n")


# ==== refusal rows: the message group and the Stop event ================================================================

@refusal("message.send", "message-duplicate")
def message_duplicate(p):  # MW-110: the row that proved message-not-in-inbox is gone with that refusal; this one stays
    ping = _ping(p)
    first = decision(p.fire("PreToolUse", BUILDER, "SendMessage", {"to": LEAD, "message": ping}))
    assert first.kind == "allow", first
    yield Call("PreToolUse", BUILDER, "SendMessage", {"to": LEAD, "message": ping})


@refusal("message.session", "session-id-mismatch")
def session_id_mismatch(p):  # MW-110: the variable assigned inline in the command, whatever the hook's environment holds
    yield bash(f"MKWAY_SESSION_ID=another-session {CLI} board")


def _ping(p) -> str:
    proc = p.session_shell(BUILDER, f"{CLI} send --to {LEAD} --kind question --file msg/body.txt")
    found = re.search(r"mkway inbox \S+", proc.stdout)
    assert found, proc.stdout + proc.stderr
    return found.group(0)


@refusal("message.send", "message-duplicate")
def message_duplicate(p):
    ping = _ping(p)
    first = decision(p.fire("PreToolUse", BUILDER, "SendMessage", {"to": LEAD, "message": ping}))
    assert first.kind == "allow", first  # the first ping of a row is allowed and recorded
    yield Call("PreToolUse", BUILDER, "SendMessage", {"to": LEAD, "message": ping})


@refusal("owner_ask.stop", "ask-not-written")
def ask_not_written(p):
    decision(p.fire("SessionStart", STOP_ASK))
    yield Call("Stop", STOP_ASK, extra={"stop_hook_active": False, "last_assistant_message": "Request: choose one\n"})


def _ping_transcript(p, *, pinged, session=BUILDER):
    """The builder's turn as Claude Code keeps it: a real send through the hooks (the engine's record of the inbox
    write), the Bash call around the write, and with `pinged` a SendMessage call after it."""
    p.session_shell(session, f'{CLI} send --to {LEAD} --kind result --text "the card is finished"')
    written = [json.loads(x) for x in (p.root / "mkway" / "state" / "inbox-writes.jsonl").read_text(
        encoding="utf-8").splitlines() if x.strip()][-1]
    import datetime

    def at(seconds):
        when = datetime.datetime.fromisoformat(written["ts"]) + datetime.timedelta(seconds=seconds)
        return when.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    def use(cid, tool, ts, **inp):
        return {"type": "assistant", "timestamp": ts,
                "message": {"content": [{"type": "tool_use", "id": cid, "name": tool, "input": inp}]}}
    rows = [{"type": "user", "timestamp": at(-5), "message": {"content": "finish the card"}},
            use("t1", "Bash", at(-1), command=f"{CLI} send --to {LEAD} --kind result"),
            {"type": "user", "timestamp": at(1),
             "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": "sent"}]}}]
    if pinged:
        rows.append(use("p1", "SendMessage", at(3), to=LEAD, message=f"mkway inbox {written['id']}"))
    path = p.transcripts / f"ping-{'yes' if pinged else 'no'}.jsonl"
    path.write_text(chr(10).join(json.dumps(r) for r in rows) + chr(10), encoding="utf-8")
    return str(path)


@refusal("ping.stop", "ping-not-sent")
def ping_not_sent(p):
    decision(p.fire("SessionStart", STOP_PING_NO))
    yield Call("Stop", STOP_PING_NO, extra={"stop_hook_active": False,
                                            "transcript_path": _ping_transcript(p, pinged=False, session=STOP_PING_NO)})


# ==== refusal rows: the shell group =====================================================================================

@refusal("lead.shell", "lead-no-take")
def lead_no_take(p):
    yield bash(f"{CLI} card take {CARD}", LEAD)


@refusal("lead.shell", "lead-no-edit")
def lead_no_edit_shell(p):
    yield bash("echo x > src/x.py", LEAD)


@refusal("lead.shell", "write-outside-root")
def lead_write_outside_root_shell(p):
    yield bash(f"echo x > {outside_file(p)}", LEAD)  # R274-D2: the common reason


@refusal("outside.shell", "write-outside-root")
def outside_write_outside_root_shell(p):
    yield bash(f"echo x > {outside_file(p)}")  # R274e: the session check is its own gate, hard from install


@refusal("lock.shell", "lock-closed-shell")
def lock_closed_shell(p):
    yield bash("echo x > mkway/engine/x.txt")


@refusal("lock.shell", "lock-closed-commit")
def lock_closed_commit(p):
    yield bash('git commit -m "CARD-001 engine" -- mkway/engine/mkway.py')


@refusal("lock.shell", "lock-file-by-session")
def lock_file_by_session_shell(p):
    yield bash("echo x > mkway/locks/y.json")


@refusal("lock.shell", "owner-only-command")
def owner_only_command_lock(p):
    yield bash(f"{CLI} lock open engine")


@refusal("lock.shell", "close-not-orderer")
def close_not_orderer(p):
    with profile_set(p, **{"cards.approver": "orderer"}):
        yield bash(f"{CLI} card close {CARD}", NOCARD)


@refusal("lock.shell", "close-by-holder")
def close_by_holder(p):
    with profile_set(p, **{"cards.approver": "orderer"}):
        p.owner("card", "resync", "--add-ordered-by", check=False)  # the column `give` writes; a second run is a no-op
        p.owner("give", CARD, BUILDER)
        try:
            yield bash(f"{CLI} card close {CARD}", BUILDER)
        finally:
            p.owner("give", CARD, "owner")


@refusal("lock.shell", "session-has-card")
def session_has_card(p):
    yield bash(f"{CLI} card take CARD-002", BUILDER)


@refusal("lock.shell", "take-root-busy")
def take_root_busy(p):
    yield bash(f"{CLI} card take CARD-002", OTHER)


@refusal("lock.shell", "card-not-yours")
def card_not_yours(p):
    yield bash(f"{CLI} card take {CARD}", OTHER)


@refusal("lock.shell", "register-tampered")
def register_tampered_shell(p):
    register = p.root / "mkway" / "cards" / "REGISTER.md"
    old = register.read_bytes()
    register.write_bytes(old + b" ")
    try:
        yield bash(f"{CLI} card take CARD-009", BUILDER)
    finally:
        register.write_bytes(old)


@refusal("lock.shell", "engine-call-not-plain")
def engine_call_not_plain(p):
    yield bash(f"{CLI} card list | cat")


@refusal("lock.shell", "quote-file-outside")
def quote_file_outside(p):  # MW-048
    yield bash(f"{CLI} ledger add --card C-1 --topic t --source s --quote-file src/q.txt")


@refusal("lock.shell", "command-unparsed")
def command_unparsed(p):
    yield bash('git commit -m "CARD-001 x')


@refusal("lock.shell", "commit-folder-unreadable")
def commit_folder_unreadable(p):
    yield bash('cd $X && git commit -m "CARD-001 x"')


@refusal("lock.shell", "pathspec-unparsed")
def pathspec_unparsed(p):
    yield bash('git commit -m "CARD-001 x" -- $F')


@refusal("commit_files", "file-not-in-card")
def file_not_in_card_commit(p):
    with staged(p, {"docs/x.txt": "x\n"}):
        yield commit()


@refusal("commit_files", "file-not-in-card")
def file_not_in_card_orderer_commit(p):
    """MW-053: the orderer's commit of its card folder with a file of src/ beside it is refused."""
    old = (p.root / "src" / "a.py").read_bytes()
    p.write("src/a.py", "VALUE = 2\n")
    try:
        with lead_orders_card(p) as card:
            yield bash(f'git commit -m "{CARD} order" -- {card.rel}/CARD.md src/a.py', LEAD)
    finally:
        (p.root / "src" / "a.py").write_bytes(old)


@refusal("commit_files", "junk-file-staged")
def junk_file_staged(p):
    with staged(p, {"src/j.pyc": b"\0"}):
        yield commit()


@refusal("commit_files", "ignored-file-staged")
def ignored_file_staged(p):
    p.write("src/.gitignore", "*.keep\n")
    with staged(p, {"src/i.keep": "x\n"}):
        yield commit()


@refusal("commit_files", "data-file-staged")
def data_file_staged(p):
    with staged(p, {"src/d.csv": "a,b\n"}):
        yield commit()


@refusal("commit_files", "file-too-large")
def file_too_large(p):
    with staged(p, {"src/big.txt": b"a" * (1100 * 1024)}):
        yield commit()


@refusal("commit_files", "rule-without-test")
def rule_without_test(p):
    with profile_set(p, **{"ids.rule_card": "R[0-9]+", "rules.cards": ["src/rules/*.md"],
                           "rules.test_for": "tests/test_{id}.py"}):
        with staged(p, {"src/rules/R1-x.md": "a rule card\n"}):
            yield commit()


@refusal("commit_files", "commit-message-card")
def commit_message_card(p):
    with staged(p, {"src/m.py": "M = 1\n"}):
        yield commit("add m")


@refusal("commit_files", "commit-unreadable")
def commit_unreadable(p):
    with staged(p, {"src/n.py": "N = 1\n"}):
        yield bash("git commit")


@refusal("commit_files", "register-tampered")
def register_tampered_commit(p):
    register = p.root / "mkway" / "cards" / "REGISTER.md"
    old = register.read_bytes()
    register.write_bytes(old + b" ")
    try:
        with staged(p, {"src/t.py": "T = 1\n"}):
            yield commit()
    finally:
        register.write_bytes(old)


@refusal("commit_tests", "commit-tests-failed")
def commit_tests_failed(p):
    with profile_set(p, **{"tests.command": "python red.py"}), staged(p, {"src/c.py": "C = 1\n"}):
        yield commit()


def commit_tests_collect_error(p):
    """MW-057: a staged test that cannot be imported; the real refusal shows the error line, not only the file."""
    with profile_set(p, **{"tests.command": "python -m pytest -q -p no:cacheprovider src/test_gone.py"}), \
            staged(p, {"src/c.py": "C = 1\n", "src/test_gone.py": "import no_such_module_mw057\n"}):
        yield commit()


def test_a_file_level_failure_shows_its_error_line_through_the_real_hook(proj):
    """MW-057 E8: the deny of a commit whose staged tree has a test file that fails to import names the file and its
    first error line (a module that is not found), read from the hook's JSON."""
    got = _run(proj, commit_tests_collect_error(proj))
    assert (got.kind, got.reason_id, got.gate) == ("deny", "commit-tests-failed", "commit_tests"), f"{got}: {got.text}"
    assert "src/test_gone.py (ModuleNotFoundError: No module named 'no_such_module_mw057')" in got.text, got.text


@refusal("commit_tests", "commit-tests-over-budget")
def commit_tests_over_budget(p):
    with profile_set(p, **{"tests.command": "python slow.py", "gates.commit_tests": {"budget_seconds": 3}}), \
            staged(p, {"src/c.py": "C = 1\n"}):
        yield commit()


@refusal("commit_tests", "commit-tests-not-run")
def commit_tests_not_run(p):
    with profile_set(p, **{"tests.command": "node x.js"}), staged(p, {"src/c.py": "C = 1\n"}):
        yield commit()


@refusal("commit_tests", "commit-tests-chained")
def commit_tests_chained(p):
    with profile_set(p, **{"tests.command": "python green.py"}), staged(p, {"src/c.py": "C = 1\n"}):
        yield bash('git commit -m "CARD-001 c"; git commit -m "CARD-001 d"')


# R217 (T7 decisions R217, R217a): the two texts are red tests, as the red-first commit of a correct card holds; SHAPE_BAD still
# breaks S1 (a loop in the body), SHAPE_GOOD breaks no rule
SHAPE_BAD = 'def test_x():\n    """Catches: a thing."""\n    for n in (1,):\n        assert n == 2\n'
SHAPE_GOOD = 'def test_x():\n    """Catches: a thing."""\n    assert 1 + 1 == 3\n'
GREEN_NEW_TEST = 'def test_n():\n    """Checks: a thing."""\n    assert 1 + 1 == 2\n'  # MW-072: a new test that passes before any code


@refusal("tests.shape", "test-shape")
def shape_bad_test_added(p):
    """MW-073: a commit that adds a test with a loop; `src` is made the test root so the commit is a tests-only one."""
    with profile_set(p, test_roots=["src"]), staged(p, {"src/test_shape_x.py": SHAPE_BAD}):
        yield commit()


@refusal("commit_tests", "red-not-proven")
def red_not_proven(p):
    with staged(p, {"tests/test_n.py": GREEN_NEW_TEST}):
        yield commit()


@refusal("commit_tests", "test-without-red-proof")
def new_test_committed_with_its_code(p):
    with staged(p, {"src/c.py": "C = 1\n", "tests/test_n.py": GREEN_NEW_TEST}):
        yield commit()


@refusal("commit_tests", "red-not-recorded")
def red_not_recorded(p):
    with staged(p, {"src/c.py": "C = 1\n"}):
        yield commit()


@refusal("commit_tests", "red-ids-still-red")
def red_ids_still_red(p):
    """The card's red record holds a test the tree no longer has (a green commit that made it vanish)."""
    record = p.root / "mkway" / "state" / "red_proof.jsonl"
    row = {"card": CARD, "tree": p.git("rev-parse", "HEAD^{tree}").strip(), "red": ["tests/test_gone.py::test_gone"]}
    record.write_text(json.dumps(row) + "\n", encoding="utf-8")
    try:
        with staged(p, {"src/c.py": "C = 1\n"}):
            yield commit()
    finally:
        record.unlink()


@refusal("commit_tests", "case-map-no-decision")
def case_map_no_decision(p):
    """MW-090: a docs-only commit that stages a mapping line, the message names no decision."""
    with staged(p, {case_map_rel(p): f"{M1} -> {N_ID}\n"}):
        yield commit()


@refusal("commit_tests", "case-map-unknown-left")
def case_map_unknown_left(p):
    with decided(p), staged(p, {case_map_rel(p): f"{M_FILE}::test_gone -> {N_ID}\n"}):
        yield commit(DECISION_MESSAGE)


@refusal("commit_tests", "case-map-unknown-right")
def case_map_unknown_right(p):
    with decided(p), deleted(p, M_FILE), staged(p, {case_map_rel(p): f"{M1} -> {N_MISSING}\n"}):
        yield commit(DECISION_MESSAGE)


@refusal("commit_tests", "case-map-merge")
def case_map_merge(p):
    with decided(p), deleted(p, M_FILE), staged(p, {case_map_rel(p): f"{M1} -> {N_ID}\n{M2} -> {N_ID}\n",
                                                    "tests/test_n.py": N_RED}):
        yield commit(DECISION_MESSAGE)


@refusal("commit_tests", "case-map-malformed")
def case_map_malformed(p):
    with decided(p), staged(p, {case_map_rel(p): "this is not a map line\n"}):
        yield commit(DECISION_MESSAGE)


@refusal("delete", "delete-target-unknown")
def delete_target_unknown(p):
    yield bash("rm src/missing.txt")


@refusal("delete", "delete-wildcard")
def delete_wildcard(p):
    yield bash("rm src/*.txt")


@refusal("delete", "delete-outside-root")
def delete_outside_root(p):
    yield bash(f"rm {p.base.as_posix()}/outside.txt")


@refusal("delete", "delete-sql")
def delete_sql(p):
    yield bash('psql -c "DROP TABLE x"')


@refusal("delete", "owner-only-command")
def owner_only_command_delete(p):
    yield bash(f"{CLI} trash empty")


@refusal("delete", "delete-uncommitted")
def delete_uncommitted(p):
    a = p.root / "src" / "a.py"
    old = a.read_bytes()
    a.write_bytes(old + b"VALUE = 2\n")
    try:  # `rm` of a changed file is backed up and allowed; a git command that drops the change is what is refused
        yield bash("git checkout -- src/a.py")
    finally:
        a.write_bytes(old)


@refusal("delete", "delete-too-large")
def delete_too_large(p):
    p.write("out/big.bin", binary=b"a" * 4096)
    with profile_set(p, **{"delete.max_backup_mb": 0.001}):
        yield bash("rm out/big.bin")


@refusal("delete", "delete-backup-failed")
def delete_backup_failed(p):
    trash = p.root / "mkway" / "state" / "trash"
    assert not trash.exists(), "an earlier row made the trash folder"
    trash.write_text("a file where the trash folder belongs\n", encoding="utf-8")
    try:
        yield bash("rm out/del_me.txt")
    finally:
        trash.unlink()


# ==== allow rows: the nearest legitimate call of each gate ==============================================================

@allowed("lock.edit")
def allow_lock_edit(p):
    yield write(p, "src/a.py")


@allowed("hold")
def allow_hold_open(p):
    """The hold target exists and the owner has not closed it: the same write is allowed."""
    with profile_set(p, **{"locks.targets": [{"name": "hold", "paths": ["src/hold/"], "open_by_default": True}]}):
        yield write(p, "src/hold/h.py")


@allowed("subtask")
def allow_subtask(p):
    yield write(p, "tests/test_a.py")


@allowed("outside.edit")
def allow_outside_edit(p):
    yield write(p, "src/a.py")  # R274e: a file inside the root is no business of the outside gate


@allowed("outside.shell")
def allow_outside_shell(p):
    yield bash("echo x > src/a.py")


@allowed("lead.edit")
def allow_lead_asks_folder(p):
    yield write(p, "mkway/asks/z_note.txt", "a note\n", LEAD)


@allowed("lead.shell")
def allow_lead_reads(p):
    yield bash("git status", LEAD)


@allowed("owner_ask.edit")
def allow_ask(p):
    p.write("mkway/asks/s7_sources.md", SESSION_SOURCES)
    yield write(p, "mkway/asks/s7_ask.md", VALID_ASK, LEAD)


@allowed("search")
def allow_search_after_a_search(p):
    with profile_set(p, **{"owner_ask.tool_allowed": True}):
        p.session_shell(OTHER, f"{CLI} search nothing")
        yield Call("PreToolUse", OTHER, "AskUserQuestion", {"questions": [{"question": "which one?"}]})


@allowed("outbox_check.pre")
def allow_check_with_the_sha(p):
    sha = hashlib.sha256((p.root / "out" / "d.md").read_bytes()).hexdigest()
    with profile_set(p, **{"outbox": {"dir": "out", "checkers": ["checker"]}}):
        yield write(p, "out/d.md.check.md", f"sha256: {sha}\n")


@allowed("message.session")
def allow_shell_call_of_a_session(p):  # MW-110: a plain engine call; the variable is unset here, so it is a warn, never a block
    yield bash(f"{CLI} board", NOCARD)


@allowed("message.send")
def allow_ping(p):
    yield Call("PreToolUse", BUILDER, "SendMessage", {"to": LEAD, "message": _ping(p)})


@allowed("message.send")
def allow_text_send_then_ping(p):  # MW-055: a session with no card reports with no write at all
    sent = decision(p.fire("PreToolUse", NOCARD, "Bash",
                           {"command": f'{CLI} send --to {LEAD} --kind notice --text "my writes are refused"'}))
    assert sent.kind == "allow", sent
    proc = p.session_shell(NOCARD, f'{CLI} send --to {LEAD} --kind notice --text "my writes are refused"')
    found = re.search(r"mkway inbox \S+", proc.stdout)
    assert found, proc.stdout + proc.stderr
    yield Call("PreToolUse", NOCARD, "SendMessage", {"to": LEAD, "message": found.group(0)})


@allowed("lock.shell")
def allow_shell_write_in_paths(p):
    yield bash("echo x > src/ok.txt")


@allowed("commit_files")
def allow_commit(p):
    with profile_set(p, **{"tests.command": "python green.py"}), staged(p, {"src/ok.py": "OK = 1\n"}):
        yield commit()


@allowed("commit_files")
def allow_orderer_commits_its_card_folder(p):
    """MW-053: the orderer, holding no card, commits the folder of the card it ordered and the register."""
    with lead_orders_card(p) as card:
        yield bash(f'git commit -m "{CARD} order" -- {card.rel} mkway/cards/REGISTER.md', LEAD)


@allowed("tests.shape")
def allow_good_test_added(p):
    """MW-073: the same commit with the loop taken out; the allow counts only when the shape gate is installed."""
    assert "tests.shape" in (p.root / "mkway" / "engine" / "engine" / "manifest.json").read_text(encoding="utf-8")
    with profile_set(p, test_roots=["src"]), staged(p, {"src/test_shape_x.py": SHAPE_GOOD}):
        yield commit()


@allowed("delete")
def allow_delete_with_backup(p):
    yield bash("rm out/del_me.txt")


@allowed("owner_ask.stop")
def allow_stop_without_a_request(p):
    decision(p.fire("SessionStart", STOP_FREE))
    yield Call("Stop", STOP_FREE, extra={"stop_hook_active": False, "last_assistant_message": "All done.\n"})


@allowed("ping.stop")
def allow_stop_after_the_ping(p):
    decision(p.fire("SessionStart", STOP_PING_YES))
    yield Call("Stop", STOP_PING_YES, extra={"stop_hook_active": False,
                                             "transcript_path": _ping_transcript(p, pinged=True, session=STOP_PING_YES)})


def test_a_ping_of_an_engine_notice_with_no_by_passes_the_real_message_gate(proj):
    """Checks: MW-110 (the removal of `message-not-in-inbox`, R269c): through the real hook command a SendMessage that
    carries the ping line of a notice the engine wrote with no `by` passes."""
    row = {"id": "n-20261112000000-aaaaaa", "from": "engine", "to": LEAD, "kind": "notice", "reply_to": None,
           "ts": "2026-11-12T00:00:00.000+00:00", "ack_ts": None, "body": "a card is past its Appetite"}
    proj.write("mkway/state/inbox/" + LEAD + ".jsonl", json.dumps(row) + chr(10))
    got = decision(proj.fire("PreToolUse", BUILDER, "SendMessage", {"to": LEAD, "message": "mkway inbox " + row["id"]}))
    assert got.kind == "allow"


# ==== the tests =========================================================================================================

@pytest.mark.parametrize("fn, entry, reason", ROWS)
def test_refusal_through_the_real_hook(proj, fn, entry, reason):
    """Each declared refusal, through the generated hook command: the verdict, read from the hook's JSON, is a deny
    (a block for Stop) with this reason id, from this manifest entry."""
    got = _run(proj, fn(proj))
    want = "block" if entry.endswith(".stop") else "deny"
    assert (got.kind, got.reason_id, got.gate) == (want, reason, entry), f"{got}: {got.text}"


@pytest.mark.parametrize("fn, entry", ALLOWS)
def test_allow_through_the_real_hook(proj, fn, entry):
    """The nearest legitimate call of each gate is allowed through the same real hook command (no false block)."""
    got = _run(proj, fn(proj))
    assert got.kind == "allow", f"{entry}: {got}: {got.text}"


def test_every_declared_reason_has_a_row_or_a_stated_exemption():
    """A reason id a PreToolUse or Stop gate declares in the manifest has a refusal row, or an exemption that says why
    no real call can show it; an exemption for an id the manifest no longer declares is stale."""
    have = {(p.values[1], p.values[2]) for p in ROWS}
    want = declared()
    assert not (want - have - set(EXEMPT)), f"no row and no exemption: {sorted(want - have - set(EXEMPT))}"
    assert not (have - want), f"a row for a reason the manifest does not declare: {sorted(have - want)}"
    assert not (set(EXEMPT) - want), f"stale exemption: {sorted(set(EXEMPT) - want)}"
    assert not (set(EXEMPT) & have), f"exempt and tested: {sorted(set(EXEMPT) & have)}"
    assert all(len(why) > 20 for why in EXEMPT.values())
    assert {e for e, _r in want} >= {"lock.edit", "lock.shell", "subtask", "commit_files", "commit_tests", "delete",
                                     "owner_ask.edit", "owner_ask.stop", "search", "lead.edit", "lead.shell",
                                     "message.send", "outbox_check.pre"}


def test_every_gate_has_an_allow_row():
    entries = {p.values[1] for p in ALLOWS}
    manifest = json.loads((REPO / "engine" / "manifest.json").read_text(encoding="utf-8"))
    frontmatter = {e["name"] for e in manifest["entries"] if e.get("frontmatter")}  # MW116-D2: a hook of an agent file, no settings gate
    need = {e for e, _r in declared() if e not in ("message.stop", "outbox_check.stop") and e not in frontmatter}
    assert not (need - entries - {"commit_tests"}), sorted(need - entries)
    # a frontmatter entry has no allow row; each of its reasons is exempt with a real test node named, and that test exists
    for entry, reason in declared():
        if entry in frontmatter:
            nodes = re.findall(r"tests/[\w/]+\.py::\w+", EXEMPT.get((entry, reason), ""))
            assert nodes, f"{entry}/{reason}: the exemption names no test node"
            for node in nodes:
                file, _, name = node.partition("::")
                assert f"def {name}(" in (REPO / file).read_text(encoding="utf-8"), f"{node} does not exist"


def test_the_driver_reads_the_json_not_only_the_exit_code():
    """The driver's verdict: exit 0 with `permissionDecision: deny` is a deny; exit 0 with `decision: block` a block;
    exit 0 with an empty stdout an allow; a dispatcher error line, or an exit other than 0, is an error."""
    tag = "[mkway lock.edit lock-closed-edit] text"
    deny = json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                               "permissionDecisionReason": tag}})
    block = json.dumps({"decision": "block", "reason": "[mkway owner_ask.stop ask-not-written] text"})
    context = json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": "a note"}})
    assert tuple(decision(HookRun("edit", "c", 0, deny, "", 0.0)))[:3] == ("deny", "lock-closed-edit", "lock.edit")
    assert tuple(decision(HookRun("stop", "c", 0, block, "", 0.0)))[:3] == ("block", "ask-not-written", "owner_ask.stop")
    assert decision(HookRun("edit", "c", 0, "", "", 0.0)).kind == "allow"
    assert decision(HookRun("edit", "c", 0, context, "", 0.0)).kind == "allow"
    assert decision(HookRun("edit", "c", 2, "", "mkway dispatcher-error: X", 0.0)).kind == "error"
    assert decision(Fired("PreToolUse", [HookRun("edit", "c", 0, "", "", 0.0), HookRun("edit", "c", 0, deny, "", 0.0)])
                    ).kind == "deny"


# ==== step 4: the owner-only tripwire through a real subprocess ========================================================

OWNER_ONLY = (("lock", "open", "engine"), ("gate", "off", "search"), ("hold",), ("card", "open", CARD))


@pytest.mark.parametrize("args", OWNER_ONLY, ids=lambda a: "-".join(a))
def test_the_owner_only_tripwire_through_a_real_subprocess(proj, args):
    """An owner command run in a process that carries the `CLAUDECODE` variable Claude Code sets is refused: a non-zero
    exit, the refusal named, and nothing changed (the profile and the lock folder keep their bytes). The same program
    in the owner's terminal (no variable) is not refused by the tripwire."""
    profile = proj.root / "mkway" / "profile.json"
    before = (profile.read_bytes(), sorted(p.name for p in (proj.root / "mkway" / "locks").glob("*")))
    env = proj.env(session=True)
    assert env.get("CLAUDECODE") == "1"
    proc = subprocess.run([sys.executable, str(proj.root / "mkway" / "engine" / "mkway.py"), *args], cwd=str(proj.root),
                          capture_output=True, text=True, env=env, timeout=120)
    assert proc.returncode != 0, proc.stdout + proc.stderr
    assert "owner-only-command" in proc.stdout + proc.stderr, proc.stdout + proc.stderr
    assert before == (profile.read_bytes(), sorted(p.name for p in (proj.root / "mkway" / "locks").glob("*")))


def test_the_same_owner_command_runs_in_the_owner_terminal(proj):
    """The contrast of the tripwire: no `CLAUDECODE`, the owner's `gate watch` and `gate on` are not refused."""
    assert "CLAUDECODE" not in proj.env(session=False)
    assert proj.owner("gate", "watch", "message", check=False).returncode == 0  # changed by MW-115 (decision: MW115-D1b)
    assert proj.owner("gate", "on", "search", check=False).returncode == 0


# ==== the card and the clock ============================================================================================

def test_register_changelog_and_card_name_the_card():
    """E7: the register row, a line under the top release of the changelog, the card folder; VERSION unchanged by it."""
    register = (REPO / "cards" / "REGISTER.md").read_text(encoding="utf-8")
    assert re.search(r"^\| MW-039 \|.*`cards/MW-039-[a-z0-9-]+`", register, re.M)
    text = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    section = next(s for s in text.split("\n## ")[1:] if "MW-039" in s)
    line = next(x for x in section.splitlines() if "MW-039" in x)
    assert "hook" in line.lower()
    assert list((REPO / "cards").glob("MW-039-*/CARD.md"))


@pytest.mark.perf
def test_the_rows_stay_inside_the_time_limit(proj):
    """The install, the setup and every row above, one install for the module, stay within the limit of the card.
    A wall-clock check, marked perf and kept out of commit and merge runs (R172)."""
    import time
    assert time.perf_counter() - proj.started < TIME_LIMIT_SECONDS, \
        f"{time.perf_counter() - proj.started:.0f} s (limit {TIME_LIMIT_SECONDS} s)"
