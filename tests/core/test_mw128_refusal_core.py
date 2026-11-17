"""Card MW-128 (rulings R301, R301a): the pure decision of the refusal delivery (`engine/core_refusal.py`): when a session's
turn ends on a refused engine call and nothing was sent on, the Stop hook delivers the refusal to the orderer itself. Table
tests on Facts -> Decision; no disk, no process, no clock. One test id is one case or one parametrized family of one rule;
no body loops or branches. Expected values are literals written from the order, never computed by the code under test.
Synthetic names and ids only."""
import ast
from pathlib import Path

import pytest

import _engine  # noqa: F401  (puts the engine folder on the import path)
import core_refusal as core

CORE = Path(__file__).resolve().parents[2] / "engine" / "core_refusal.py"
ALLOWED_IMPORTS = {"__future__", "dataclasses", "datetime", "typing"}
BANNED_CALLS = {"open", "print", "input", "exec", "eval", "__import__", "compile"}
BANNED_ATTRS = {"now", "today", "utcnow", "read_text", "write_text", "is_file", "exists", "getenv", "environ"}

T0 = "2026-11-16T10:00:00.000+00:00"
T1 = "2026-11-16T10:00:05.000+00:00"
T2 = "2026-11-16T10:00:09.000+00:00"
T1_PLUS_1MS = "2026-11-16T10:00:05.001+00:00"
T2_Z = "2026-11-16T10:00:09.000Z"
COMMAND = "python mkway/engine/mkway.py card take X-1"
LINE = "[mkway lock.shell take-root-busy] the root is held"


def call(call_id, time, refused=False, row_id=None):
    return core.Call(call_id, time, refused, row_id)


REFUSED = call("c1", T1, True, "gc-1")
ALLOWED = call("c2", T2, False, None)


def facts(**over):
    base = dict(calls=(REFUSED,), sends=(), orderer="lead-1", delivered=frozenset(), hook_active=False)
    base.update(over)
    return core.Facts(**base)


def summary(decided):
    return (decided.action, decided.refusal_id, decided.orderer, decided.block)


def test_a_turn_ending_refusal_with_an_orderer_is_delivered_and_blocks_once():
    """Catches: a refused last call of the turn that the Stop hook does not deliver to the orderer, or delivers without the one block."""
    assert summary(core.decide(facts())) == ("deliver", "gc-1", "lead-1", True)


def test_a_continued_stop_delivers_but_never_blocks():
    """Catches: a second block when Claude Code already continues because of a stop hook (stop_hook_active true)."""
    assert summary(core.decide(facts(hook_active=True))) == ("deliver", "gc-1", "lead-1", False)


@pytest.mark.parametrize("calls", [
    pytest.param((), id="no-engine-call-in-the-turn"),
    pytest.param((ALLOWED,), id="the-last-call-was-allowed"),
    pytest.param((REFUSED, ALLOWED), id="an-engine-call-follows-the-refusal"),
    pytest.param((call("c1", T1, True, None),), id="a-refused-call-with-no-row-id"),
])
def test_condition_a_fails_so_the_stop_is_allowed_silently(calls):
    """Checks: no delivery and no block unless the last engine call of the turn has a gate refusal row and no call follows it."""
    assert summary(core.decide(facts(calls=calls))) == ("allow", None, None, False)


@pytest.mark.parametrize("sends", [
    pytest.param((T2,), id="a-send-after-the-refusal"),
    pytest.param((T1_PLUS_1MS,), id="a-send-one-millisecond-after-the-refusal"),
    pytest.param((T2_Z,), id="a-send-with-a-zulu-time-after-the-refusal"),
])
def test_condition_b_fails_when_a_send_followed_the_refusal(sends):
    """Checks: a session that sent the refusal on itself is not told again and not blocked."""
    assert summary(core.decide(facts(sends=sends))) == ("allow", None, None, False)


def test_a_send_at_the_same_time_as_the_refusal_is_not_after_it():
    """Catches: a send of the same millisecond, earlier in the log, hiding the refusal: after means strictly later."""
    assert summary(core.decide(facts(sends=(T1,)))) == ("deliver", "gc-1", "lead-1", True)


def test_a_send_before_the_refusal_does_not_count_as_the_send_of_it():
    """Catches: an earlier send hiding a later refusal, so the orderer never hears of it."""
    assert summary(core.decide(facts(sends=(T0,)))) == ("deliver", "gc-1", "lead-1", True)


@pytest.mark.parametrize("hook_active", [False, True])
def test_condition_e_fails_for_an_id_that_is_already_delivered(hook_active):
    """Catches: a second record or a second block for the same gate refusal row id."""
    assert summary(core.decide(facts(delivered=frozenset({"gc-1"}), hook_active=hook_active))) == (
        "allow", None, None, False)


def test_another_delivered_id_does_not_hide_this_refusal():
    """Checks: the delivered set is matched by the row id, so a different delivered id leaves this refusal delivered."""
    assert summary(core.decide(facts(delivered=frozenset({"gc-0"})))) == ("deliver", "gc-1", "lead-1", True)


@pytest.mark.parametrize("orderer", [None, ""])
def test_condition_c_fails_with_no_orderer_so_one_record_row_and_no_block(orderer):
    """Catches: a block that nobody can resolve, when the session holds no card or its orderer column is empty (R301a 3)."""
    assert summary(core.decide(facts(orderer=orderer))) == ("no-orderer", "gc-1", None, False)


@pytest.mark.parametrize("over", [
    pytest.param(dict(calls=(), orderer=None), id="condition-a-false"),
    pytest.param(dict(sends=(T2,), orderer=None), id="condition-b-false"),
    pytest.param(dict(delivered=frozenset({"gc-1"}), orderer=None), id="condition-e-false"),
])
def test_the_no_orderer_record_applies_only_when_a_b_and_e_hold(over):
    """Checks: with no orderer and one of the conditions a, b, e false the stop is allowed silently, no record row."""
    assert summary(core.decide(facts(**over))) == ("allow", None, None, False)


@pytest.mark.parametrize("hook_active, block", [(False, True), (True, False)])
def test_a_written_record_is_recorded_as_delivered_and_blocks_only_when_not_continued(hook_active, block):
    """Checks: after a successful write the id is recorded as delivered and the block follows stop_hook_active."""
    decided = core.decide(facts(hook_active=hook_active))
    done = core.finish(decided, True)
    assert (done.block, done.delivered, done.error) == (block, True, False)


@pytest.mark.parametrize("hook_active", [False, True])
def test_a_failed_inbox_write_allows_the_stop_and_is_not_recorded_as_delivered(hook_active):
    """Catches: a block after a failed write (a Stop hook cannot fail closed), or an id marked delivered that never was."""
    decided = core.decide(facts(hook_active=hook_active))
    done = core.finish(decided, False)
    assert (done.block, done.delivered, done.error) == (False, False, True)


def test_the_no_orderer_record_is_recorded_once_and_never_blocks():
    """Checks: the no-orderer decision is recorded under its id, with no block and no error."""
    done = core.finish(core.decide(facts(orderer=None)), True)
    assert (done.block, done.delivered, done.error) == (False, True, False)


def test_the_block_reason_is_the_binding_text_with_the_exact_ping_line():
    """Pins: the reason text of the one block, exactly as ruled (R301a: it carries `mkway inbox <id>`)."""
    assert core.block_reason("m-20261116100005-abc123") == (
        "your refusal was sent to your orderer as inbox row m-20261116100005-abc123; "
        "tell your orderer: mkway inbox m-20261116100005-abc123")


def test_the_inbox_record_holds_the_exact_command_the_exact_refusal_line_and_the_session():
    """Pins: the body of the inbox refusal record: session, command, refusal line and the gate refusal row id."""
    assert core.inbox_body("sess-1", COMMAND, LINE, "gc-1") == (
        "refusal delivered by the engine: the session stopped after this refusal and sent nothing\n"
        "session: sess-1\n"
        "command: python mkway/engine/mkway.py card take X-1\n"
        "refusal: [mkway lock.shell take-root-busy] the root is held\n"
        "gate refusal row: gc-1")


def test_the_reason_ids_of_the_card():
    """Pins: the three ids the card adds to the concept table."""
    assert (core.DELIVERED, core.NO_ORDERER_ID, core.FAILED) == (
        "refusal-delivered", "refusal-no-orderer", "refusal-delivery-failed")


def test_the_owner_table_has_an_engine_row_for_the_refusal_delivery_record():
    """Checks: the delivered-id record of the Stop hook has its one owner row, the engine's (R301a, card 2 meta test)."""
    import owners
    row = owners.kind_of("mkway/state/refusal-delivered.jsonl", {})
    assert (row.name, row.role) == ("inbox-refusal", "engine")


def test_the_orderers_inbox_file_is_owned_by_the_engine_and_names_the_stop_hook_as_a_writer():
    """Checks: the owner row that covers the orderer's inbox file names the Stop hook next to `mkway send` (R301a, item 7)."""
    import owners
    row = owners.kind_of("mkway/state/inbox/lead1.jsonl", {})
    assert (row.name, row.role, "Stop hook" in row.command, "`mkway send`" in row.command) == ("inbox", "engine", True, True)


def _scan(source):
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


def test_the_core_imports_only_pure_modules():
    """Catches: an import in the refusal core of a module that reaches the disk, a process, the environment or the clock."""
    modules, _calls, _attrs = _scan(CORE.read_text(encoding="utf-8"))
    assert modules <= ALLOWED_IMPORTS, f"core_refusal.py imports {sorted(modules - ALLOWED_IMPORTS)}"


def test_the_core_calls_no_io_function_and_reads_no_clock():
    """Catches: a call in the refusal core of open, print or input, or a read of the clock, the disk or the environment."""
    _modules, calls, attrs = _scan(CORE.read_text(encoding="utf-8"))
    assert (calls & BANNED_CALLS, attrs & BANNED_ATTRS) == (set(), set())
