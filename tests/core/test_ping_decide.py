"""Card MW-076 (decisions: R185, R186, R187, R188): the pure decisions of the ping gate (`engine/core_ping.py`), as table
tests on Facts -> Verdict. No disk, no git, no process: the core gets parsed transcript entries, the engine's record of
inbox writes and plain facts. One test id is one case or one parametrized family of one rule; no body loops or branches.
Expected values are literals written from the rule, never computed by the code under test. Synthetic names and ids."""
import ast
from pathlib import Path

import pytest

import _engine  # noqa: F401  (puts the engine folder on the import path)
import core_ping as core

CORE = Path(__file__).resolve().parents[2] / "engine" / "core_ping.py"
ALLOWED_IMPORTS = {"__future__", "re", "datetime", "dataclasses", "typing"}

CLAUSE = "if SendMessage is not loaded, load it first with ToolSearch query select:SendMessage"
START = "2026-11-12T10:00:00.000Z"
SEND = 'python mkway/engine/mkway.py send --to 63fcc7cf --kind result --text "done"'
WAITING = "python mkway/engine/mkway.py card set DD-008 waiting"


def use(cid, name, ts, **tool_input):
    return {"type": "assistant", "timestamp": ts,
            "message": {"content": [{"type": "tool_use", "id": cid, "name": name, "input": tool_input}]}}


def bash(cid, command, ts="2026-11-12T10:00:01.000Z"):
    return use(cid, "Bash", ts, command=command)


def result(cid, text="ok\n", ts="2026-11-12T10:00:03.000Z"):
    return {"type": "user", "timestamp": ts,
            "message": {"content": [{"type": "tool_result", "tool_use_id": cid, "content": text}]}}


def ping(ts="2026-11-12T10:00:05.000Z", cid="p1", id_="m-1"):  # changed by MW-110 (decision MW110-D3): the ping line names the row
    return use(cid, "SendMessage", ts, to="dd-lead", message=f"mkway inbox {id_}")


def write(id_="m-1", frm="b1", to="63fcc7cf", kind="result", ts="2026-11-12T10:00:02.000+00:00", name="dd-lead", **more):
    return {"id": id_, "from": frm, "to": to, "kind": kind, "ts": ts, "name": name, **more}


def facts(entries, writes, **over):
    base = dict(session_id="b1", entries=tuple(entries), writes=tuple(writes), turn_start=START)
    base.update(over)
    return core.PingFacts(**base)


CALL = (bash("t1", SEND), result("t1"))
TEXT = f"ping your lead: {CLAUSE}; then SendMessage to dd-lead: mkway inbox m-1"
ROW = ("ping-skipped", {"kind": "result", "inbox_id": "m-1", "to": "63fcc7cf", "name": "dd-lead"})


# ---- the refusals: an inbox write to another session this turn, then no ping ---------------------------------------

def test_a_send_with_no_ping_after_it_is_refused():
    """Catches: a builder that ran `mkway send` (an inbox write) and stopped with no SendMessage after it."""
    got = core.decide_stop(facts(CALL, [write()]))
    assert (got.kind, got.reason, got.text) == ("refuse", "ping-not-sent", TEXT)


def test_a_send_with_a_ping_after_it_is_allowed():
    """Checks: the nearest allow of the refusal above, the same turn with a SendMessage call after the write."""
    assert core.decide_stop(facts([*CALL, ping()], [write()])).kind == "allow"


def test_a_notice_the_engine_wrote_in_a_bash_call_with_no_ping_is_refused():
    """Catches: `card set <card> waiting` (U06): the engine wrote a notice to the lead naming this session, with no ping after it (R189, the MW-049 caller); the trigger is the engine's own record."""
    notice = write(id_="n-1", frm="engine", kind="notice", by="b1")
    got = core.decide_stop(facts([bash("t1", WAITING), result("t1")], [notice]))
    assert (got.kind, got.reason) == ("refuse", "ping-not-sent")
    assert got.text == f"ping your lead: {CLAUSE}; then SendMessage to dd-lead: mkway inbox n-1"


def test_a_notice_the_engine_wrote_with_a_ping_after_it_is_allowed():
    """Checks: the nearest allow of the notice refusal, a SendMessage call after the engine's notice."""
    notice = write(id_="n-1", frm="engine", kind="notice", by="b1")
    assert core.decide_stop(facts([bash("t1", WAITING), result("t1"), ping(id_="n-1")], [notice])).kind == "allow"  # MW110-D3


RELEASE = "python mkway/engine/mkway.py card release DD-008"


def test_a_release_notice_the_engine_wrote_for_the_orderer_with_no_ping_is_refused():
    """Catches: R189 (1): a `card release` notice to the orderer, with no ping, is refused like a sent one."""
    notice = write(id_="n-2", frm="engine", kind="notice", by="b1", cmd="card release", card="DD-008")
    got = core.decide_stop(facts([bash("t1", RELEASE), result("t1")], [notice]))
    assert (got.kind, got.reason) == ("refuse", "ping-not-sent")
    assert got.text == f"ping your lead: {CLAUSE}; then SendMessage to dd-lead: mkway inbox n-2"


def test_a_notice_caused_by_another_session_is_not_this_sessions_even_inside_its_bash_call():
    """Catches: R189 (2): a `by` that names another session attributed to this session by the time window."""
    notice = write(id_="n-1", frm="engine", kind="notice", by="b2", cmd="card set", card="DD-008")
    assert core.decide_stop(facts([bash("t1", WAITING), result("t1")], [notice])).kind == "allow"


def test_with_no_by_the_window_the_command_text_and_the_card_id_together_attribute_the_notice():
    """Catches: R189 (2): the fallback path, taken when no `by` can be read, attributes a notice only with all three facts together (the Bash call, the card and the command words)."""
    notice = write(id_="n-1", frm="engine", kind="notice", cmd="card set", card="DD-008")
    got = core.decide_stop(facts([bash("t1", WAITING), result("t1")], [notice]))
    assert (got.kind, got.reason) == ("refuse", "ping-not-sent")


@pytest.mark.parametrize("notice, command", [
    pytest.param(write(frm="engine", kind="notice"), WAITING, id="window-alone"),
    pytest.param(write(frm="engine", kind="notice", cmd="card set", card="DD-008"), "git status",
                 id="window-and-card-but-another-command"),
    pytest.param(write(frm="engine", kind="notice", cmd="card set", card="DD-009"), WAITING,
                 id="window-and-command-but-another-card"),
    pytest.param(write(frm="engine", kind="notice", cmd="card set", card="DD-008", ts="2026-11-12T10:00:09.000+00:00"),
                 WAITING, id="command-and-card-but-outside-the-window"),
])
def test_a_notice_with_no_by_and_less_than_all_three_facts_is_not_attributed(notice, command):
    """Checks: the nearest allows of the fallback: the window alone, or any two of the three, attribute nothing."""
    assert core.decide_stop(facts([bash("t1", command), result("t1")], [notice])).kind == "allow"


def test_a_ping_sent_before_the_write_does_not_count():
    """Catches: a SendMessage that came BEFORE the inbox write taken as the ping of that write."""
    early = ping(ts="2026-11-12T10:00:00.500Z", cid="p0")
    got = core.decide_stop(facts([early, *CALL], [write()]))
    assert (got.kind, got.reason) == ("refuse", "ping-not-sent")


def test_only_the_write_with_no_ping_after_it_is_named():
    """Catches: one ping between two writes that covers both, or a refusal that names the pinged one."""
    entries = [*CALL, ping(ts="2026-11-12T10:00:04.000Z"), bash("t2", SEND, "2026-11-12T10:00:06.000Z"),
               result("t2", ts="2026-11-12T10:00:08.000Z")]
    later = write(id_="m-2", ts="2026-11-12T10:00:07.000+00:00")
    got = core.decide_stop(facts(entries, [write(), later]))
    assert got.text == f"ping your lead: {CLAUSE}; then SendMessage to dd-lead: mkway inbox m-2"


def test_two_writes_with_no_ping_are_both_named_in_order():
    """Catches: a refusal that names only the first of two unanswered writes."""
    entries = [*CALL, bash("t2", SEND, "2026-11-12T10:00:06.000Z"), result("t2", ts="2026-11-12T10:00:08.000Z")]
    later = write(id_="m-2", to="aaaa", name="dd-other", ts="2026-11-12T10:00:07.000+00:00")
    got = core.decide_stop(facts(entries, [write(), later]))
    assert got.text == (f"ping your lead: {CLAUSE}; then SendMessage to dd-lead: mkway inbox m-1 | "
                        f"SendMessage to dd-other: mkway inbox m-2")


def test_an_unknown_name_keeps_the_listagents_instruction():
    """Catches: a refusal with no target when no name is known; the text must still say how to find the session."""
    got = core.decide_stop(facts(CALL, [write(name=None)]))
    assert got.reason == "ping-not-sent"
    assert got.text.startswith(f"ping your lead: {CLAUSE}; then ")
    assert "ListAgents" in got.text
    assert got.text.endswith("exactly: mkway inbox m-1")


# ---- the allows: nothing to ping -----------------------------------------------------------------------------------

@pytest.mark.parametrize("entries, writes", [
    pytest.param([], [], id="empty-turn"),
    pytest.param([bash("t1", "git status"), result("t1")], [], id="no-write-at-all"),
    pytest.param([bash("t1", "git status"), result("t1")], [write(ts="2026-11-12T09:59:00.000+00:00")],
                 id="a-write-of-an-earlier-turn"),
    pytest.param(list(CALL), [write(frm="b2")], id="a-write-of-another-session"),
    pytest.param(list(CALL), [write(to="b1")], id="a-write-to-the-own-inbox"),
    pytest.param([bash("t1", "git status"), result("t1")],
                 [write(frm="engine", kind="notice", ts="2026-11-12T10:00:09.000+00:00")],
                 id="an-engine-notice-outside-every-bash-call"),
])
def test_a_turn_with_no_write_to_another_session_is_allowed(entries, writes):
    """Checks: no inbox write to another session caused by this session's Bash call this turn: the Stop passes."""
    assert core.decide_stop(facts(entries, writes)).kind == "allow"


def test_an_unreadable_transcript_is_allowed():
    """Checks: a transcript that cannot be read gives no fact, so the gate never blocks on it (fails open)."""
    assert core.decide_stop(core.PingFacts(session_id="b1", entries=None, writes=(write(),))).kind == "allow"


def test_a_turn_with_no_known_start_is_allowed():
    """Checks: with no real user message the turn has no start, so no write can be put in it (fails open)."""
    assert core.decide_stop(facts(CALL, [write()], turn_start=None)).kind == "allow"


def test_a_lead_session_is_never_judged():
    """Checks: a registered lead that sent with no ping is exempt (leads and operators, as the lead register knows)."""
    assert core.decide_stop(facts(CALL, [write()], is_lead=True)).kind == "allow"


def test_a_session_with_no_id_is_not_judged():
    """Checks: a hook input with no session id names no builder, so the gate allows."""
    assert core.decide_stop(facts(CALL, [write()], session_id=None)).kind == "allow"


# ---- the second Stop of the turn (R186: the documented stop_hook_active field) --------------------------------------

def test_the_second_stop_passes_and_writes_the_ping_skipped_row():
    """Catches: a Stop that blocks again when `stop_hook_active` is true (a loop), or one that leaves no record."""
    got = core.decide_stop(facts(CALL, [write()], hook_active=True))
    assert (got.kind, got.reason, got.records) == ("log", "ping-skipped", (ROW,))


def test_the_second_stop_with_nothing_to_ping_writes_no_row():
    """Checks: `stop_hook_active` is true because of another gate; the turn has no unanswered write: no record."""
    got = core.decide_stop(facts([bash("t1", "git status"), result("t1")], [], hook_active=True))
    assert (got.kind, got.records) == ("allow", ())


def test_the_second_stop_with_the_ping_sent_writes_no_row():
    """Checks: the nearest allow of the record: the builder pinged after the block, so nothing is skipped."""
    got = core.decide_stop(facts([*CALL, ping()], [write()], hook_active=True))
    assert (got.kind, got.records) == ("allow", ())


# ---- the profile switch gates.ping.mode ----------------------------------------------------------------------------

def test_in_watch_mode_the_gate_warns_with_the_reason_line_and_writes_the_row_but_allows():
    """Catches: a watch mode that blocks, or one that writes no record row."""
    got = core.decide_stop(facts(CALL, [write()], mode="watch"))
    assert (got.kind, got.reason, got.text, got.records) == ("warn", "ping-not-sent", TEXT, (ROW,))


def test_in_watch_mode_a_turn_with_a_ping_is_silent():
    """Checks: watch mode changes only what a refusal does; an answered write is allowed and writes nothing."""
    got = core.decide_stop(facts([*CALL, ping()], [write()], mode="watch"))
    assert (got.kind, got.records) == ("allow", ())


# ---- R188: the fixed clause in both texts --------------------------------------------------------------------------

def test_the_fixed_clause_is_in_the_printed_ping_line_and_in_the_refusal_reason():
    """Catches: a text that drops the clause that tells a session whose SendMessage is only deferred how to load it."""
    printed = core.send_ping_text("dd-lead", "mkway inbox m-1")
    refused = core.decide_stop(facts(CALL, [write()])).text
    assert printed == f"ping: {CLAUSE}; then SendMessage to dd-lead: mkway inbox m-1"
    assert CLAUSE in printed
    assert CLAUSE in refused


# ---- the lead's Stop (R186 b, R187) ---------------------------------------------------------------------------------

ROW_A = {"id": "ps-1", "builder": "dd-b", "inbox_id": "m-1", "origin": "session"}
LINE = "builder dd-b wrote to the inbox and did not ping: read mkway inbox m-1"


def test_a_lead_is_shown_an_unseen_ping_skipped_row_as_one_warn_line():
    """Catches: a ping-skipped row that stays silent, or a line that is not the ruled text."""
    got = core.decide_lead_stop(core.LeadStopFacts(is_lead=True, rows=(ROW_A,)))
    assert (got.kind, got.reason, got.text) == ("warn", "ping-skipped-listed", LINE)
    assert got.records == (("seen", {"ids": ["ps-1"]}),)


def test_the_same_row_the_second_time_is_silent():
    """Catches: a row listed at every Stop of the lead instead of once."""
    got = core.decide_lead_stop(core.LeadStopFacts(is_lead=True, rows=(ROW_A,), seen=frozenset({"ps-1"})))
    assert (got.kind, got.records) == ("allow", ())


def test_a_session_that_is_no_lead_is_not_shown_the_rows():
    """Checks: only a registered lead's Stop lists the rows."""
    assert core.decide_lead_stop(core.LeadStopFacts(is_lead=False, rows=(ROW_A,))).kind == "allow"


def test_a_lead_with_no_rows_is_silent():
    """Checks: nothing recorded, nothing said."""
    assert core.decide_lead_stop(core.LeadStopFacts(is_lead=True)).kind == "allow"


def test_an_engine_notice_that_no_session_pinged_is_listed_as_the_dead_letter_line():
    """Catches: a dead-letter or appetite notice (U05, U07: no sending session) that never reaches the lead's list."""
    row = {"id": "ps-2", "builder": None, "inbox_id": "n-7", "origin": "engine"}
    got = core.decide_lead_stop(core.LeadStopFacts(is_lead=True, rows=(row,)))
    assert got.text == "the engine wrote a notice that no session pinged: read mkway inbox n-7"


def test_two_unseen_rows_are_both_listed_in_order_and_one_seen_row_is_left_out():
    """Catches: a list that drops a row, repeats a seen one or changes the order."""
    rows = (ROW_A, {"id": "ps-2", "builder": "dd-c", "inbox_id": "m-2", "origin": "session"},
            {"id": "ps-3", "builder": "dd-d", "inbox_id": "m-3", "origin": "session"})
    got = core.decide_lead_stop(core.LeadStopFacts(is_lead=True, rows=rows, seen=frozenset({"ps-2"})))
    assert got.text == LINE + " | builder dd-d wrote to the inbox and did not ping: read mkway inbox m-3"
    assert got.records == (("seen", {"ids": ["ps-1", "ps-3"]}),)


# ---- the name in mkcl's sessions file (R178a) ----------------------------------------------------------------------

def _file(*rows):
    return {"version": 1, "sessions": list(rows)}


LEAD_ROW = {"name": "dd-lead", "kind": "lead", "card": None, "state": "alive", "resumeId": "63fcc7cf-1111"}
BUILDER_ROW = {"name": "dd-008-builder", "starter": "dd-lead", "kind": "builder", "card": "DD-008", "state": "alive",
               "resumeId": None}


@pytest.mark.parametrize("data, target, card", [
    pytest.param(_file(LEAD_ROW), "63fcc7cf-1111", None, id="by-resume-id"),
    pytest.param(_file(BUILDER_ROW), "63fcc7cf-1111", "DD-008", id="by-the-builders-card-starter"),
    pytest.param(_file(LEAD_ROW, BUILDER_ROW), "63fcc7cf-1111", "DD-008", id="both-agree"),
])
def test_the_lead_name_is_read_from_the_sessions_file(data, target, card):
    """Checks: the name by the lead's resume id, or by the `starter` of the live builder row of the sender's card."""
    assert core.sessions_name(data, target, card) == "dd-lead"


@pytest.mark.parametrize("data, target, card", [
    pytest.param(_file(LEAD_ROW), "other-id", None, id="no-such-id"),
    pytest.param(_file({**LEAD_ROW, "state": "closed"}), "63fcc7cf-1111", None, id="closed-row"),
    pytest.param(_file({**BUILDER_ROW, "state": "closed"}), "x", "DD-008", id="closed-builder-row"),
    pytest.param(_file(BUILDER_ROW), "x", "DD-009", id="other-card"),
    pytest.param(_file({"kind": "lead", "resumeId": "63fcc7cf-1111"}), "63fcc7cf-1111", None, id="row-with-no-name"),
    pytest.param({"sessions": "not a list"}, "x", None, id="sessions-not-a-list"),
    pytest.param(["not", "an", "object"], "x", None, id="not-an-object"),
    pytest.param(None, "x", None, id="nothing"),
])
def test_an_unknown_or_unusable_sessions_file_gives_no_name(data, target, card):
    """Catches: a name taken from a closed row, another card, a damaged file; the caller then keeps ListAgents."""
    assert core.sessions_name(data, target, card) is None


# ---- the core is pure ----------------------------------------------------------------------------------------------

def test_the_core_imports_no_io_module():
    """Catches: a core that imports os, pathlib, json or an engine module that reads files (the core stays pure)."""
    tree = ast.parse(CORE.read_text(encoding="utf-8"))
    names = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    names |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert names <= ALLOWED_IMPORTS


# ---- readings that fail open (coverage of the time and window reads) ---------------------------------------------------

def test_a_write_with_a_time_that_cannot_be_read_is_not_judged():
    """Checks: a record row whose `ts` is not an ISO time is left out, so the gate never blocks on a damaged row."""
    assert core.decide_stop(facts(CALL, [write(ts="not a time")])).kind == "allow"


def test_a_bash_result_with_no_time_leaves_the_window_open_for_the_fallback():
    """Checks: R189 fallback: a tool result with no time means the call's end is not known, so the window stays open."""
    entries = [bash("t1", WAITING), {"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": "t1", "content": "ok"}]}}]
    notice = write(id_="n-1", frm="engine", kind="notice", cmd="card set", card="DD-008")
    assert core.decide_stop(facts(entries, [notice])).kind == "refuse"
