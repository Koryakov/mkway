"""Card MW-078: the decision of the inbox waiter, table tests of the pure core (`engine/core_wake.py`). No disk, no
process, no clock: every case is facts written by hand and the verdict the card row names. The waiter that reads the
facts is proven in `tests/shell/test_wake_waiter_facts.py`."""
import pytest

import _engine  # noqa: F401  (puts the engine on sys.path)
import core_wake as core

ME = "lead-1"
NEW = core.Row(id="m-1", writer="build-1", to=ME, acked=False)
LEAD = {"is_lead": True}
HOLDER = {"holds_card": True}
LAST = {"last_holder_unclosed": True}


def facts(rows=(), woken=(), now=0, deadline=10, **kw):
    """Facts of the session ME; a lead unless the case says otherwise through `kw`."""
    base = {"is_lead": False}
    base.update(kw)
    return core.Facts(session=ME, rows=tuple(rows), woken=tuple(woken), now=now, deadline=deadline, **base)


def test_a_lead_with_a_new_row_is_woken_by_that_row():
    """Checks: a registered lead with one new unacked row from another session wakes on that row (E1)."""
    v = core.decide(facts([NEW], **LEAD))
    assert (v.kind, v.row_id) == ("wake", "m-1")


def test_a_card_holder_with_a_new_row_is_woken_by_that_row():
    """Checks: a session that holds a card (no lead) wakes on a new row (E2)."""
    v = core.decide(facts([NEW], **HOLDER))
    assert (v.kind, v.row_id) == ("wake", "m-1")


def test_the_last_holder_of_a_released_unclosed_card_is_woken_by_a_row():
    """Checks: a session that released a card not yet closed waits for the lead's close or fix message and wakes (E3)."""
    v = core.decide(facts([NEW], **LAST))
    assert (v.kind, v.row_id) == ("wake", "m-1")


def test_a_session_that_is_no_lead_and_holds_no_card_quits_quietly():
    """Catches: a waiter that arms for the owner's tab or a `-p` run and wakes a session that is no mkway session (E4)."""
    v = core.decide(facts([NEW]))
    assert (v.kind, v.row_id) == ("quiet-exit", None)


def test_mode_off_quits_quietly_even_for_a_lead():
    """Catches: `wake.mode` off that still waits and wakes a lead (E5)."""
    v = core.decide(facts([NEW], mode="off", **LEAD))
    assert (v.kind, v.row_id) == ("quiet-exit", None)


def test_a_row_written_by_the_session_itself_does_not_wake_it():
    """Catches: a session woken by its own message to a lead that is itself, a loop of wakes (E6)."""
    own = core.Row(id="m-2", writer=ME, to=ME, acked=False)
    v = core.decide(facts([own], **LEAD))
    assert (v.kind, v.row_id) == ("wait", None)


def test_an_acked_row_does_not_wake():
    """Catches: a session woken for a row it has already acknowledged (E7)."""
    acked = core.Row(id="m-3", writer="build-1", to=ME, acked=True)
    v = core.decide(facts([acked], **LEAD))
    assert (v.kind, v.row_id) == ("wait", None)


def test_a_row_that_already_woke_the_session_does_not_wake_it_again():
    """Catches: the same unacked row waking the session after every Stop, an endless loop of turns (E8)."""
    v = core.decide(facts([NEW], woken=["m-1"], **LEAD))
    assert (v.kind, v.row_id) == ("wait", None)


def test_a_woken_row_is_skipped_for_the_next_unwoken_one():
    """Checks: the nearest allow of E8: with a woken row first and a new row behind it, the new row wakes (E9)."""
    later = core.Row(id="m-4", writer="build-1", to=ME, acked=False)
    v = core.decide(facts([NEW, later], woken=["m-1"], **LEAD))
    assert (v.kind, v.row_id) == ("wake", "m-4")


def test_a_row_unacked_at_arm_time_wakes_at_once():
    """Checks: a row that was in the inbox before the waiter started wakes it on the first look (E10)."""
    v = core.decide(facts([NEW], now=0, deadline=14400, **LEAD))
    assert (v.kind, v.row_id) == ("wake", "m-1")


def test_the_oldest_of_two_rows_wakes_first():
    """Checks: two unwoken rows: the first in the file, the oldest, is the one (E11)."""
    newer = core.Row(id="m-5", writer="build-2", to=ME, acked=False)
    v = core.decide(facts([NEW, newer], **LEAD))
    assert (v.kind, v.row_id) == ("wake", "m-1")


def test_the_deadline_with_no_row_is_a_heartbeat():
    """Checks: nothing arrived and the deadline is reached (E12)."""
    v = core.decide(facts([], now=10, deadline=10, **LEAD))
    assert (v.kind, v.row_id) == ("heartbeat", None)


def test_before_the_deadline_with_no_row_the_waiter_goes_on_waiting():
    """Checks: the nearest allow of E12: nothing arrived and the deadline is not reached (E13)."""
    v = core.decide(facts([], now=9, deadline=10, **LEAD))
    assert (v.kind, v.row_id) == ("wait", None)


def test_a_row_wins_over_the_heartbeat_at_the_deadline():
    """Catches: a heartbeat that says `no new rows` while a new row is in the inbox (E14)."""
    v = core.decide(facts([NEW], now=10, deadline=10, **LEAD))
    assert (v.kind, v.row_id) == ("wake", "m-1")


def test_a_row_addressed_to_another_session_does_not_wake():
    """Catches: a row of another session's inbox, a mis-read folder, waking this session (E15)."""
    other = core.Row(id="m-6", writer="build-1", to="lead-2", acked=False)
    v = core.decide(facts([other], **LEAD))
    assert (v.kind, v.row_id) == ("wait", None)


def test_a_session_id_that_is_no_plain_id_quits_quietly():
    """Catches: an id the inbox path refuses, such as `..` or a slash, that still arms a waiter (E16)."""
    v = core.decide(facts([NEW], safe_id=False, **LEAD))
    assert (v.kind, v.row_id) == ("quiet-exit", None)


def test_the_heartbeat_line_is_the_ruled_text():
    """Checks: the heartbeat line of ruling R191, letter for letter (E17)."""
    assert core.HEARTBEAT_LINE == "no new rows, end the turn"


@pytest.mark.parametrize("kind", ["wake", "heartbeat", "quiet-exit", "wait"])
def test_a_verdict_of_a_known_kind_is_built(kind):
    """Checks: the four kinds are the only ones a verdict may have (E18)."""
    assert core.Verdict(kind).kind == kind


@pytest.mark.parametrize("kind", ["sleep", "", "WAKE"])
def test_a_verdict_of_an_unknown_kind_is_refused(kind):
    """Catches: a verdict with a kind nothing handles (E19)."""
    with pytest.raises(ValueError):
        core.Verdict(kind)


@pytest.mark.parametrize("steps, closed, expected", [
    ([("take", "s1", "session"), ("release", "s1", "session")], False, "s1"),
    ([("take", "s1", "session")], False, None),
    ([("take", "s1", "session"), ("release", "s2", "session")], False, None),
    ([("take", "s1", "session"), ("release", None, "owner")], False, "s1"),
    ([("take", "s1", "session"), ("release", "s1", "session"), ("take", "s2", "session")], False, None),
    ([("take", "s1", "session"), ("release", "s1", "session"), ("take", "s2", "session"),
      ("release", "s2", "session")], False, "s2"),
    ([("take", "s1", "session"), ("release", "s1", "session")], True, None),
    ([], False, None),
])
def test_the_last_holder_of_a_released_card_is_read_from_the_records(steps, closed, expected):
    """Checks: the last holder of a released card is read by replaying its take and release rows (E20)."""
    rows = [{"kind": kind, "value": "C-1", "session_id": who, "by": by} for kind, who, by in steps]
    assert core.last_holder(rows, "C-1", closed) == expected


def test_the_records_of_another_card_do_not_count():
    """Catches: a release of another card read as the release of this one (E21)."""
    rows = [{"kind": "take", "value": "C-1", "session_id": "s1", "by": "session"},
            {"kind": "release", "value": "C-2", "session_id": "s1", "by": "session"}]
    assert core.last_holder(rows, "C-1", False) is None
