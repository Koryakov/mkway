"""Card MW-076, ruling R197 B: a ping of an engine notice that has no `by` is refused (nobody caused it, so nothing can be
proven; the lead sees it at its next Stop); the session that caused a notice with a `by` may ping it. The pure decision of
the message gate (`core_session.decide_send`) as a table test. Synthetic ids only."""
import _engine  # noqa: F401  (puts the engine folder on the import path)
import core_session as core

PING = {"to": "dd-lead", "message": "mkway inbox n-1"}


def test_a_ping_of_an_engine_notice_with_no_by_passes_and_records_nothing():
    """Catches: MW-110: a ping line of a notice nobody caused recorded as a ping, or refused as before."""
    got = core.decide_send(core.MessageFacts(tool_name="SendMessage", tool_input=PING, session_id="b1",
                                             row_is_senders=False, row_no_by=True))
    assert (got.kind, got.records) == ("allow", ())


def test_a_ping_of_a_notice_by_the_session_that_caused_it_is_allowed():
    """Checks: the nearest allow of the refusal above: the notice has a `by` that is this session, so it is its row."""
    got = core.decide_send(core.MessageFacts(tool_name="SendMessage", tool_input=PING, session_id="b1",
                                             row_is_senders=True, row_no_by=False))
    assert got.kind == "allow"
    assert got.records == (("ping", {"id": "n-1", "session": "b1"}),)
