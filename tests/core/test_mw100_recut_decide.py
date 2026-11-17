"""Card MW-100 (decisions: R251, R251a, R251b), layer core: `core_verdict_recut.decide(facts)` as a table. A weak or wrong
verdict is answered by a re-cut: the card's orderer changes the row's words or the test, then runs the command. The decision
reads one `Facts` record (the caller, the card's state and orderer, the sessions that took it, the profile's switches and one
`Node`: its last row, the run that row answers, whether a commit changed the cut since that run ended, the files that differ
from HEAD, the recuts so far). No disk, no git, no clock. One test id is one case; each refusal has a deny and the nearest allow."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/: `_engine` puts engine/ on the path
import _engine  # noqa: E402,F401
from core_verdict_recut import Facts, Node, decide  # noqa: E402

NODE = "tests/test_a.py::test_one"


def node(**kw):
    base = {"known": True, "committers": frozenset(), "last": "weak", "answered": "agent-1",
            "ended": "2026-11-11T10:02:00+00:00", "stale": (), "changed": True, "recuts": 0}
    base.update(kw)
    return Node(NODE, **base)


def facts(**kw):
    base = {"caller": "lead", "orderer": "lead", "status": "waiting", "holder": "", "ever_held": frozenset(),
            "node": node(), "mode": "trip"}
    base.update(kw)
    return Facts(**base)


def reasons(verdict):
    return [r.reason for r in verdict.refusals]


def watched(verdict):
    return [r.reason for r in verdict.watched]


# ---- the allows and the nothing-to-answer refusals ---------------------------------------------------------------------

def test_a_lead_with_a_weak_row_and_a_changed_cut_is_allowed():
    """Checks: the card's orderer, a waiting card, a weak last row with its recorded run and a changed cut give an allow naming the run."""
    verdict = decide(facts())
    assert verdict.allowed
    assert verdict.answered == "agent-1"


def test_a_wrong_row_is_allowed_as_well():
    """Checks: the nearest allow of the nothing refusals: a wrong last row is answered by a recut like a weak one."""
    assert decide(facts(node=node(last="wrong"))).allowed


def test_a_node_with_no_row_is_refused_as_nothing():
    """Catches: a recut of a node nobody judged, a waiver in disguise."""
    assert reasons(decide(facts(node=node(last="", answered="")))) == ["verdict-recut-nothing"]


def test_a_node_whose_last_row_is_true_is_refused_as_nothing():
    """Catches: a recut of a node whose verdict is true, which would throw a good verdict away."""
    assert reasons(decide(facts(node=node(last="true")))) == ["verdict-recut-nothing"]


def test_a_node_whose_last_row_is_a_recut_is_refused_as_nothing():
    """Catches: two recuts in a row with no fresh verdict between them."""
    assert reasons(decide(facts(node=node(last="recut")))) == ["verdict-recut-nothing"]


def test_a_weak_row_with_no_recorded_run_is_refused_as_nothing():
    """Catches: a recut of a typed row, which names no reader run it answers."""
    assert reasons(decide(facts(node=node(answered="")))) == ["verdict-recut-nothing"]


# ---- the cut must really change -----------------------------------------------------------------------------------------

def test_a_cut_that_did_not_change_is_refused_as_no_change():
    """Catches: a recut with the test and the card unchanged since the answered run ended, a waiver in disguise."""
    assert reasons(decide(facts(node=node(changed=False)))) == ["verdict-recut-no-change"]


def test_the_no_change_text_names_the_answered_run():
    """Catches: a refusal that does not say which run the recut would answer."""
    assert "agent-1" in decide(facts(node=node(changed=False))).refusals[0].text


def test_a_test_file_that_differs_from_head_is_refused_as_recut_stale():
    """Catches: a recut over a test file with an uncommitted change, which the next reader would not read."""
    found = decide(facts(node=node(stale=((NODE.partition("::")[0], "aaa111", "bbb222"),))))
    assert reasons(found) == ["verdict-recut-stale"]


def test_the_recut_stale_text_names_the_file_and_both_shas():
    """Catches: a refusal that does not name the file and the two shas, so nobody can see what differs."""
    text = decide(facts(node=node(stale=(("tests/test_a.py", "aaa111", "bbb222"),)))).refusals[0].text
    assert ("tests/test_a.py" in text, "aaa111" in text, "bbb222" in text) == (True, True, True)


def test_a_card_file_that_differs_from_head_is_refused_as_recut_stale():
    """Catches: a recut over a card file with an uncommitted change."""
    found = decide(facts(node=node(stale=(("cards/CARD-001-x/CARD.md", "", "ccc333"),))))
    assert reasons(found) == ["verdict-recut-stale"]


# ---- one recut per node -------------------------------------------------------------------------------------------------

def test_a_second_recut_of_a_node_is_refused_as_exceeded():
    """Catches: a third attempt at a node that a second independent reader still calls weak."""
    assert reasons(decide(facts(node=node(recuts=1)))) == ["verdict-recut-exceeded"]


def test_the_exceeded_text_says_split_or_withdraw_the_card():
    """Catches: a refusal that leaves the lead with no way out."""
    assert "split or withdraw the card" in decide(facts(node=node(recuts=1))).refusals[0].text


# ---- who may recut ------------------------------------------------------------------------------------------------------

def test_a_session_that_is_not_the_orderer_is_refused_as_not_lead():
    """Catches: any session, not only the card's orderer, answering a verdict with a recut."""
    assert reasons(decide(facts(caller="other"))) == ["verdict-recut-not-lead"]


def test_an_owner_ordered_card_is_refused_as_not_lead_with_the_give_text():
    """Catches: a card the owner ordered, whose recut names no way for a lead to take it over."""
    text = decide(facts(orderer="owner")).refusals[0].text
    assert "verdict-recut-not-lead" in text
    assert "mkway give" in text


def test_the_current_holder_is_refused_as_by_holder():
    """Catches: the builder that holds the card re-cutting its own tests."""
    assert "verdict-by-holder" in reasons(decide(facts(holder="lead", ever_held=frozenset({"lead"}))))


def test_a_former_holder_is_refused_as_by_holder():
    """Catches: a session that built the card once and released it re-cutting it."""
    assert reasons(decide(facts(ever_held=frozenset({"lead"})))) == ["verdict-by-holder"]


def test_a_committer_of_the_test_file_is_refused_as_by_committer():
    """Catches: the session that committed the test re-cutting the test it wrote."""
    assert reasons(decide(facts(node=node(committers=frozenset({"lead"}))))) == ["verdict-by-committer"]


def test_another_session_that_committed_is_allowed():
    """Checks: the nearest allow of the committer refusal: a different session committed the test file."""
    assert decide(facts(node=node(committers=frozenset({"builder"})))).allowed


def test_the_owners_terminal_is_refused_as_by_owner():
    """Catches: the owner's terminal writing a recut (the verdict route is never the owner's)."""
    assert reasons(decide(facts(owner=True, caller=""))) == ["verdict-by-owner"]


def test_a_call_with_no_caller_is_refused_as_no_caller():
    """Catches: a session whose id the gate left no permit for, so no `by` can be written."""
    assert reasons(decide(facts(caller=""))) == ["verdict-no-caller"]


def test_an_open_card_with_a_holder_is_refused_as_card_state():
    """Catches: a recut while a builder still works the card."""
    assert reasons(decide(facts(status="open", holder="builder"))) == ["verdict-card-state"]


def test_an_open_card_with_no_holder_is_allowed():
    """Checks: the nearest allow of the card-state refusal: a released card takes a recut from its orderer."""
    assert decide(facts(status="open", holder="")).allowed


def test_a_node_the_card_does_not_name_is_refused_as_node_unknown():
    """Catches: a recut row written for a node the card's Acceptance rows do not name."""
    assert reasons(decide(facts(node=node(known=False)))) == ["verdict-node-unknown"]


def test_a_profile_with_no_checkers_is_refused_as_not_enforced():
    """Catches: a recut where no reader can be proved, because the profile names no checker."""
    found = decide(facts(checkers_missing=True))
    assert reasons(found) == ["verdict-not-enforced"]
    assert "outbox.checkers" in found.refusals[0].text


def test_a_profile_with_verdicts_off_is_refused_as_not_enforced():
    """Catches: a recut where the close does not read verdicts at all."""
    found = decide(facts(verdicts_off=True))
    assert reasons(found) == ["verdict-not-enforced"]
    assert "cards.verdicts" in found.refusals[0].text


# ---- the modes ----------------------------------------------------------------------------------------------------------

def test_in_watch_mode_by_holder_is_still_refused():
    """Catches: watch mode letting a former holder re-cut."""
    assert reasons(decide(facts(mode="watch", ever_held=frozenset({"lead"})))) == ["verdict-by-holder"]


def test_in_watch_mode_by_committer_is_still_refused():
    """Catches: watch mode letting the committer of the test re-cut it."""
    assert reasons(decide(facts(mode="watch", node=node(committers=frozenset({"lead"}))))) == ["verdict-by-committer"]


def test_in_watch_mode_by_owner_is_still_refused():
    """Catches: watch mode letting the owner's terminal write a recut."""
    assert reasons(decide(facts(mode="watch", owner=True, caller=""))) == ["verdict-by-owner"]


def test_in_watch_mode_no_caller_is_still_refused():
    """Catches: watch mode writing a recut row with no `by`."""
    assert reasons(decide(facts(mode="watch", caller=""))) == ["verdict-no-caller"]


def test_in_watch_mode_no_change_is_still_refused():
    """Catches: watch mode letting a recut through with no change of the cut (R251b F)."""
    assert reasons(decide(facts(mode="watch", node=node(changed=False)))) == ["verdict-recut-no-change"]


def test_in_watch_mode_recut_stale_is_still_refused():
    """Catches: watch mode letting a recut through over a file that differs from HEAD (R251b F)."""
    found = decide(facts(mode="watch", node=node(stale=(("tests/test_a.py", "aaa111", "bbb222"),))))
    assert reasons(found) == ["verdict-recut-stale"]


def test_in_watch_mode_not_lead_is_allowed_and_listed():
    """Checks: watch mode lets a non-lead through and lists the reason."""
    found = decide(facts(mode="watch", caller="other"))
    assert (found.allowed, watched(found)) == (True, ["verdict-recut-not-lead"])


def test_in_watch_mode_nothing_is_allowed_and_listed():
    """Checks: watch mode lets a recut of a true row through and lists the reason."""
    found = decide(facts(mode="watch", node=node(last="true")))
    assert (found.allowed, watched(found)) == (True, ["verdict-recut-nothing"])


def test_in_watch_mode_exceeded_is_allowed_and_listed():
    """Checks: watch mode lets a second recut through and lists the reason."""
    found = decide(facts(mode="watch", node=node(recuts=1)))
    assert (found.allowed, watched(found)) == (True, ["verdict-recut-exceeded"])


def test_in_watch_mode_card_state_is_allowed_and_listed():
    """Checks: watch mode lets a recut on a closed card through and lists the reason."""
    found = decide(facts(mode="watch", status="closed"))
    assert (found.allowed, watched(found)) == (True, ["verdict-card-state"])


def test_in_watch_mode_node_unknown_is_allowed_and_listed():
    """Checks: watch mode lets a node the card does not name through and lists the reason."""
    found = decide(facts(mode="watch", node=node(known=False)))
    assert (found.allowed, watched(found)) == (True, ["verdict-node-unknown"])


def test_in_watch_mode_not_enforced_is_allowed_and_listed():
    """Checks: watch mode lets a profile with no checker through and lists the reason."""
    found = decide(facts(mode="watch", checkers_missing=True))
    assert (found.allowed, watched(found)) == (True, ["verdict-not-enforced"])


def test_with_no_mode_the_recut_behaves_as_trip():
    """Catches: a profile with no `tests.verdict_add.mode` key letting a non-lead through (the key is optional)."""
    assert reasons(decide(facts(mode="", caller="other"))) == ["verdict-recut-not-lead"]


def test_in_trip_mode_the_same_non_lead_is_refused():
    """Catches: trip mode letting a non-lead through, the nearest deny of the watch case."""
    assert reasons(decide(facts(mode="trip", caller="other"))) == ["verdict-recut-not-lead"]
