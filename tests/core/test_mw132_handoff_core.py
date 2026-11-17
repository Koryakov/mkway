"""Card MW-132 (rulings R337, R337a, R338, R338a): the pure decision of the handoff notice (`engine/core_handoff.py`): a builder that
holds an open card and ends a turn with no `mkway send` to its orderer gets its last message delivered to the orderer by the Stop
hook itself, with one block asking only for the ping line. Table tests on Facts -> Decision; no disk, no process, no clock. One
test id is one case or one parametrized family of one rule; no body loops or branches, except the one flood row that walks a
list of stops. Expected values are literals written from the order, never computed by the code under test. Synthetic names only."""
import ast
from pathlib import Path

import pytest

import _engine  # noqa: F401  (puts the engine folder on the import path)
import core_handoff as core

CORE = Path(__file__).resolve().parents[2] / "engine" / "core_handoff.py"
ALLOWED_IMPORTS = {"__future__", "dataclasses", "datetime", "typing"}
BANNED_CALLS = {"open", "print", "input", "exec", "eval", "__import__", "compile"}
BANNED_ATTRS = {"now", "today", "utcnow", "read_text", "write_text", "is_file", "exists", "getenv", "environ"}

T0 = "2026-11-17T10:00:00.000+00:00"  # the turn's boundary row
T1 = "2026-11-17T10:00:05.000+00:00"
T0_MINUS = "2026-11-17T09:59:59.999+00:00"
T0_PLUS = "2026-11-17T10:00:00.001+00:00"
T1_Z = "2026-11-17T10:00:05.000Z"


def facts(**over):
    base = dict(session="build-1", card="CARD-9", orderer="lead-1", role="builder", turn_start=T0, sends=(),
                delivered=False, hook_active=False)
    base.update(over)
    return core.Facts(**base)


def test_a_first_stop_with_no_handoff_writes_the_notice_and_blocks_once():
    """Checks: a builder holding a card, no send to the orderer in the turn, nothing delivered, not continued: notice and one block."""
    got = core.decide(facts())
    assert (got.action, got.card, got.orderer, got.block) == ("notice", "CARD-9", "lead-1", True)


def test_a_first_stop_that_continues_after_a_hook_writes_the_notice_but_does_not_block():
    """Catches: a second block in a row: with stop_hook_active true the notice is written and the stop passes (R338 1)."""
    got = core.decide(facts(hook_active=True))
    assert (got.action, got.block) == ("notice", False)


@pytest.mark.parametrize("hook_active", [False, True])
def test_a_notice_already_delivered_for_this_turn_allows_with_or_without_stop_hook_active(hook_active):
    """Catches: a second notice, or a second block, at a later stop of one turn (one write per turn end)."""
    assert core.decide(facts(delivered=True, hook_active=hook_active)).action == "allow"


def test_a_send_to_the_orderer_in_the_turn_is_a_handoff_and_costs_nothing():
    """Checks: (h) a session with a handoff pays nothing: no notice, no block."""
    assert core.decide(facts(sends=((T1, "lead-1"),))).action == "allow"


def test_a_send_to_the_orderer_with_a_z_time_is_read_as_a_time():
    """Checks: a send time written with a trailing Z (a transcript's form) is read as the same instant as `+00:00`."""
    assert core.decide(facts(sends=((T1_Z, "lead-1"),))).action == "allow"


def test_a_send_to_another_session_than_the_orderer_is_no_handoff():
    """Catches: R2-1: a send to a colleague hiding a silent turn end from the orderer."""
    assert core.decide(facts(sends=((T1, "build-2"),))).action == "notice"


def test_a_send_of_the_previous_turn_is_no_handoff():
    """Catches: R2-2: a send before the turn's boundary row counted for this turn."""
    assert core.decide(facts(sends=((T0_MINUS, "lead-1"),))).action == "notice"


def test_a_send_at_the_same_millisecond_as_the_boundary_is_no_handoff():
    """Pins: R2-2: the send must be strictly later than the boundary row; the same millisecond is the previous turn's."""
    assert core.decide(facts(sends=((T0, "lead-1"),))).action == "notice"


def test_a_send_one_millisecond_after_the_boundary_is_a_handoff():
    """Pins: the nearest allow of the row above: strictly later counts."""
    assert core.decide(facts(sends=((T0_PLUS, "lead-1"),))).action == "allow"


def test_a_send_whose_time_cannot_be_read_is_no_handoff():
    """Pins: reader 2: a send record whose time is unreadable cannot show it is in this turn; it must not excuse a silent turn end."""
    assert core.decide(facts(sends=(("not a time", "lead-1"),))).action == "notice"


def test_a_send_with_no_time_at_all_is_no_handoff():
    """Pins: the nearest case of the row above: a send record with a null time is no handoff either."""
    assert core.decide(facts(sends=((None, "lead-1"),))).action == "notice"


@pytest.mark.parametrize("orderer", [None, "build-1"])
def test_an_orderer_that_is_the_owner_or_empty_or_this_session_gets_one_record_row_and_no_block(orderer):
    """Checks: R2-6 and (b): no session to write to: one record row, never a block (the owner is no inbox)."""
    got = core.decide(facts(orderer=orderer))
    assert (got.action, got.block) == ("no-orderer", False)


def test_a_no_orderer_turn_already_recorded_is_silent():
    """Catches: the no-orderer row written again at a later stop of the same turn (once per turn end)."""
    assert core.decide(facts(orderer=None, delivered=True)).action == "allow"


def test_no_card_means_nothing():
    """Checks: (b) a session holding no card is none of this card's business."""
    assert core.decide(facts(card=None, orderer=None)).action == "allow"


def test_a_registered_lead_holding_a_card_is_never_judged():
    """Checks: (b) and R2-14: the lead's own stops pass, even when its card names another session as orderer."""
    assert core.decide(facts(role="lead")).action == "allow"


def test_a_session_whose_orderer_is_not_a_lead_gets_the_notice_but_never_the_block():
    """Checks: R338a: the printed ping line would not work for a role that is no builder: the notice is the core, the block the extra."""
    got = core.decide(facts(role="none"))
    assert (got.action, got.block) == ("notice", False)


def test_a_turn_with_no_boundary_row_is_not_judged():
    """Pins: R1-17: with no boundary row the engine cannot tell what the turn is, so it judges nothing."""
    assert core.decide(facts(turn_start=None)).action == "allow"


def test_background_work_is_no_exemption():
    """Checks: R338 3: a turn ending while the session's own background work runs is judged the same way."""
    got = core.decide(facts(background_tasks=2))
    assert (got.action, got.block) == ("notice", True)


def test_a_written_notice_blocks_and_is_recorded_as_delivered():
    """Checks: what the shell records after a good write: the block (once) and the delivered mark."""
    out = core.finish(core.decide(facts()), True)
    assert (out.block, out.delivered, out.error) == (True, True, False)


def test_a_failed_notice_write_allows_the_stop_and_is_not_recorded_as_delivered():
    """Checks: R338 6: a Stop hook cannot fail closed: no block, no delivered mark, an error for the shell."""
    out = core.finish(core.decide(facts()), False)
    assert (out.block, out.delivered, out.error) == (False, False, True)


def test_a_decision_to_allow_finishes_with_nothing():
    """Checks: nothing decided, nothing recorded."""
    out = core.finish(core.decide(facts(delivered=True)), True)
    assert (out.block, out.delivered, out.error) == (False, False, False)


def test_the_block_reason_is_the_binding_text_with_the_exact_ping_line():
    """Pins: R338 1 / DESIGN 4: the block text, exactly, with the card and the inbox row id."""
    assert core.block_reason("CARD-9", "m-1") == (
        "you ended your turn holding CARD-9 without a message to your orderer; your last message was sent to your "
        "orderer as inbox row m-1; tell your orderer: mkway inbox m-1")


def test_the_notice_body_has_the_fixed_first_words_then_the_last_message():
    """Pins: R2-17 and R337 3(e): one exact body: the session, the card, the fixed words, then the last message."""
    assert core.notice_body("build-1", "CARD-9", "Should I change those four nodes?") == (
        "build-1 ended its turn holding CARD-9 without a message to you\n"
        "last message: Should I change those four nodes?")


@pytest.mark.parametrize("value", [None, 7, ["a"], {"a": 1}, True])
def test_a_last_message_that_is_not_a_string_reads_not_established(value):
    """Checks: R2-5: absent, null or not a string: the body field says «not established», no error."""
    assert core.notice_body("build-1", "CARD-9", value).endswith("last message: not established")


def test_a_blank_last_message_reads_not_established():
    """Pins: an empty or blank message carries nothing to the orderer; the field says «not established»."""
    assert core.cut_message("  \n ") == "not established"


def test_the_named_limit_of_the_last_message_is_two_thousand_characters():
    """Pins: the named limit of the last message in the notice body."""
    assert core.LAST_MESSAGE_LIMIT == 2000


def test_a_long_last_message_is_cut_to_the_named_limit_and_the_cut_is_marked():
    """Checks: a message of 2050 characters keeps its first 2000 and ends with the mark."""
    assert core.cut_message("x" * 2050) == "x" * 2000 + " [cut]"


def test_a_last_message_at_the_limit_is_not_cut():
    """Checks: the nearest allow of the cut: exactly the limit stays whole."""
    assert core.cut_message("x" * 2000) == "x" * 2000


def _stops_of_three_turns():
    """(notices, blocks) per turn for three turns of three stops each: the first stop plain, the others continued by the hook."""
    notices, blocks = [], []
    for _turn in range(3):
        delivered, n, b = False, 0, 0
        for hook_active in (False, True, True):
            got = core.decide(facts(delivered=delivered, hook_active=hook_active))
            out = core.finish(got, True)
            n += got.action == "notice"
            b += out.block
            delivered = delivered or out.delivered
        notices.append(n)
        blocks.append(b)
    return notices, blocks


def test_one_notice_and_at_most_one_block_per_turn_over_many_turns_and_stops():
    """Checks: R1-13 flood bound: over three turns of three stops each, one notice and one block per turn, never more."""
    assert _stops_of_three_turns() == ([1, 1, 1], [1, 1, 1])


def test_the_reason_ids_of_the_card():
    """Pins: the four ids the card adds to the concept table."""
    assert (core.NOTICE_ID, core.NO_ORDERER_ID, core.FAILED_ID, core.NO_TURN_START_ID) == (
        "handoff-notice", "handoff-no-orderer", "handoff-notice-failed", "handoff-no-turn-start")


def test_the_orderers_inbox_file_names_the_handoff_notice_among_the_engine_writers():
    """Checks: the owner row that covers the orderer's inbox file names the Stop hook's handoff notice too (R338: an engine writer)."""
    import owners
    row = owners.kind_of("mkway/state/inbox/lead1.jsonl", {})
    assert (row.name, row.role, "handoff notice" in row.command) == ("inbox", "engine", True)


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
    """Catches: an import in the handoff core of a module that reaches the disk, a process, the environment or the clock."""
    modules, _calls, _attrs = _scan(CORE.read_text(encoding="utf-8"))
    assert modules <= ALLOWED_IMPORTS, f"core_handoff.py imports {sorted(modules - ALLOWED_IMPORTS)}"


def test_the_core_calls_no_io_function_and_reads_no_clock():
    """Catches: a call in the handoff core of open, print or input, or a read of the clock, the disk or the environment."""
    _modules, calls, attrs = _scan(CORE.read_text(encoding="utf-8"))
    assert (calls & BANNED_CALLS, attrs & BANNED_ATTRS) == (set(), set())
