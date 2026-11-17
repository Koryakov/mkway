"""Card MW-080 (decisions: R194, R196, R196a), layer core: `core_verdict_add.decide(facts)` as a table. A verdict row is
written by the engine command only; the decision reads one `Facts` record (the caller, the card's state, the sessions that
held it, per node the committers, the last commit, the two blobs, the checker runs of the caller's session and the runs
fresh against the last commit, the runs already used for the card, the mode). No disk, no git, no clock. One test id is
one case; each refusal reason has a deny case and the nearest allow case."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/: `_engine` puts engine/ on the path
import _engine  # noqa: E402,F401
from core_verdict_add import Facts, Node, decide  # noqa: E402

NODE = "tests/test_a.py::test_one"
OTHER = "tests/test_b.py::test_two"


def node(name=NODE, **kw):
    base = {"known": True, "committers": frozenset(), "commit": "c0ffee1", "head_blob": "b1", "file_blob": "b1",
            "readers": ("r1",), "fresh": ("r1",)}
    base.update(kw)
    return Node(name, **base)


def facts(**kw):
    base = {"caller": "reader", "status": "waiting", "holder": "", "ever_held": frozenset(), "nodes": (node(),),
            "mode": "trip", "red_proven": True}
    base.update(kw)
    return Facts(**base)


def reasons(verdict):
    return [r.reason for r in verdict.refusals]


def watched(verdict):
    return [r.reason for r in verdict.watched]


# ---- the allows and the run limit -------------------------------------------------------------------------------------

def test_a_waiting_card_with_one_fresh_run_is_allowed():
    """Checks: a caller that never took the card, a waiting card and one fresh reader run give an allow with that run."""
    verdict = decide(facts())
    assert verdict.allowed
    assert verdict.run == "r1"


def test_the_same_run_a_second_time_is_allowed():
    """Checks: the nearest allow of the third-run deny: the run already used for the card is used again."""
    verdict = decide(facts(nodes=(node(used=("r1",)),)))
    assert verdict.allowed
    assert verdict.run == "r1"


def test_a_second_distinct_run_is_allowed():
    """Checks: the nearest allow of the third-run deny: one earlier run, a new distinct run."""
    verdict = decide(facts(nodes=(node(readers=("r2",), fresh=("r2",), used=("r1",)),)))
    assert verdict.allowed
    assert verdict.run == "r2"


def test_a_third_distinct_run_is_refused_as_runs_exceeded():
    """Catches: a card judged again and again by new reader runs until one verdict passes."""
    verdict = decide(facts(nodes=(node(readers=("r3",), fresh=("r3",), used=("r1", "r2")),)))
    assert reasons(verdict) == ["verdict-runs-exceeded"]


def test_the_runs_exceeded_text_names_the_two_earlier_runs():
    """Catches: a refusal that does not say which two runs were spent, so nobody can find them in the record."""
    text = decide(facts(nodes=(node(readers=("r3",), fresh=("r3",), used=("r1", "r2")),))).refusals[0].text
    assert "r1" in text
    assert "r2" in text


def test_a_run_already_used_is_chosen_before_a_new_one():
    """Checks: two runs spent and a used run and a new run both fresh: the used run is chosen, so the call is allowed."""
    verdict = decide(facts(nodes=(node(readers=("r1", "r3"), fresh=("r1", "r3"), used=("r1", "r2")),)))
    assert verdict.run == "r1"
    assert verdict.allowed


# ---- the card state ---------------------------------------------------------------------------------------------------

def test_an_open_card_with_no_holder_is_allowed():
    """Checks: a released card (open, nobody holds it) takes a verdict from a caller that never held it."""
    assert decide(facts(status="open", holder="")).allowed


def test_an_open_card_with_a_holder_is_allowed_after_the_red_commit():
    """Checks: MW117-D1 (R272 G3 supersedes R194): a builder may still hold the open card; the red-proof row is there, so a
    reader that never held the card gives a verdict. The card-state refusals that stay are the tests below."""
    assert decide(facts(status="open", holder="builder")).allowed


def test_a_waiting_owner_card_is_refused_as_card_state():
    """Catches: a verdict written on a card the owner paused."""
    assert reasons(decide(facts(status="waiting-owner"))) == ["verdict-card-state"]


def test_a_closed_card_is_refused_as_card_state():
    """Catches: a verdict written on a closed card."""
    assert reasons(decide(facts(status="closed"))) == ["verdict-card-state"]


def test_a_proposed_card_is_refused_as_card_state():
    """Catches: a verdict written on a card nobody has opened."""
    assert reasons(decide(facts(status="proposed"))) == ["verdict-card-state"]


def test_the_card_state_text_names_the_status():
    """Catches: a refusal that does not say which state the card is in."""
    assert "closed" in decide(facts(status="closed")).refusals[0].text


# ---- who may write ----------------------------------------------------------------------------------------------------

def test_a_former_holder_after_release_is_refused_as_by_holder():
    """Catches: the builder of the card judging its own tests after it released the card."""
    verdict = decide(facts(status="open", holder="", ever_held=frozenset({"reader"})))
    assert reasons(verdict) == ["verdict-by-holder"]


def test_the_current_holder_is_refused_as_by_holder():
    """Catches: the session that holds the card judging its own tests; the holder reason comes first."""
    verdict = decide(facts(status="open", holder="reader", ever_held=frozenset({"reader"})))
    assert reasons(verdict)[0] == "verdict-by-holder"


def test_a_committer_of_the_test_file_is_refused_as_by_committer():
    """Catches: the session that committed the test file judging it (the commit gate's record names it)."""
    verdict = decide(facts(nodes=(node(committers=frozenset({"reader"})),)))
    assert reasons(verdict) == ["verdict-by-committer"]


def test_a_committer_of_another_file_is_allowed():
    """Checks: the nearest allow of the committer deny: the committers of this test file are other sessions."""
    assert decide(facts(nodes=(node(committers=frozenset({"someone-else"})),))).allowed


def test_the_owners_terminal_is_refused_as_by_owner():
    """Catches: the owner's terminal writing a verdict (the verdict is never the owner's, R181)."""
    assert reasons(decide(facts(caller="", owner=True))) == ["verdict-by-owner"]


def test_a_call_with_no_caller_is_refused_as_no_caller():
    """Catches: a session whose id is not established writing a row with no `by`."""
    assert reasons(decide(facts(caller="", owner=False))) == ["verdict-no-caller"]


def test_a_node_the_card_does_not_name_is_refused_as_node_unknown():
    """Catches: a verdict row for a test the card's Acceptance rows do not name."""
    assert reasons(decide(facts(nodes=(node(known=False),)))) == ["verdict-node-unknown"]


# ---- the text the verdict is about -------------------------------------------------------------------------------------

def test_a_test_file_that_differs_from_head_is_refused_as_stale():
    """Catches: a verdict about a text that is not the committed one (an uncommitted change of the test file)."""
    assert reasons(decide(facts(nodes=(node(file_blob="b2"),)))) == ["verdict-stale"]


def test_the_stale_text_names_both_blob_shas():
    """Catches: a refusal that does not name the two shas, the committed blob and the file as it is now."""
    text = decide(facts(nodes=(node(file_blob="b2"),))).refusals[0].text
    assert "b1" in text
    assert "b2" in text


def test_an_uncommitted_test_file_is_refused_as_stale():
    """Catches: a verdict about a test file git has no commit for."""
    assert reasons(decide(facts(nodes=(node(commit="", head_blob="", file_blob="b2"),)))) == ["verdict-stale"]


def test_a_run_that_started_before_the_last_commit_is_refused_as_stale():
    """Catches: a reader that read the text before the last commit, so its verdict is about another text."""
    assert reasons(decide(facts(nodes=(node(readers=("r1",), fresh=()),)))) == ["verdict-stale"]


def test_the_stale_run_text_names_the_last_commit():
    """Catches: a refusal that does not name the last commit of the test file the run must start after."""
    assert "c0ffee1" in decide(facts(nodes=(node(readers=("r1",), fresh=()),))).refusals[0].text


def test_a_session_with_no_checker_run_is_refused_as_no_reader_run():
    """Catches: a verdict from a session that never ran a checker agent, so nothing proves a blind reader."""
    assert reasons(decide(facts(nodes=(node(readers=(), fresh=()),)))) == ["verdict-no-reader-run"]


def test_two_nodes_with_no_common_fresh_run_are_refused_as_stale():
    """Catches: one call that mixes two test files no single reader run was fresh for."""
    nodes = (node(readers=("r1", "r2"), fresh=("r1",)), node(OTHER, readers=("r1", "r2"), fresh=("r2",)))
    assert reasons(decide(facts(nodes=nodes))) == ["verdict-stale"]


def test_two_nodes_with_one_common_fresh_run_are_allowed():
    """Checks: the nearest allow of the deny above: both nodes have the run r2 fresh, so r2 is the run of the call."""
    nodes = (node(readers=("r1", "r2"), fresh=("r1", "r2")), node(OTHER, readers=("r2",), fresh=("r2",)))
    verdict = decide(facts(nodes=nodes))
    assert verdict.run == "r2"
    assert verdict.allowed


# ---- the profile ------------------------------------------------------------------------------------------------------

def test_a_profile_with_no_checkers_is_refused_as_not_enforced_naming_the_key():
    """Catches: a verdict row written where no checker type is configured, so no reader can be proved."""
    verdict = decide(facts(checkers_missing=True))
    assert reasons(verdict) == ["verdict-not-enforced"]
    assert "outbox.checkers" in verdict.refusals[0].text


def test_a_profile_with_verdicts_off_is_refused_as_not_enforced_naming_the_key():
    """Catches: a verdict row written where the card close does not read verdicts at all."""
    verdict = decide(facts(verdicts_off=True))
    assert reasons(verdict) == ["verdict-not-enforced"]
    assert "cards.verdicts" in verdict.refusals[0].text


# ---- the mode: watch allows the refusals that do not decide independence --------------------------------------------------

NO_READER = {"nodes": (node(readers=(), fresh=()),)}


def test_in_watch_mode_a_missing_reader_run_is_allowed_and_listed():
    """Checks: watch mode lets the call through and lists the reason it would have refused."""
    verdict = decide(facts(mode="watch", **NO_READER))
    assert verdict.allowed
    assert watched(verdict) == ["verdict-no-reader-run"]


def test_in_trip_mode_the_same_missing_reader_run_is_refused():
    """Catches: trip mode letting a verdict through that has no reader run (the nearest deny of the watch allow)."""
    assert reasons(decide(facts(mode="trip", **NO_READER))) == ["verdict-no-reader-run"]


def test_with_no_mode_in_the_profile_the_command_behaves_as_trip():
    """Catches: a profile without `tests.verdict_add.mode` read as watch (ruling R196a: the missing key is trip)."""
    assert reasons(decide(facts(mode="", **NO_READER))) == ["verdict-no-reader-run"]


def test_in_watch_mode_a_card_state_refusal_is_allowed_and_listed():
    """Checks: the card state is not an independence rule, so watch mode lets it through and lists it."""
    verdict = decide(facts(mode="watch", status="closed"))
    assert verdict.allowed
    assert watched(verdict) == ["verdict-card-state"]


def test_in_watch_mode_by_holder_is_still_refused():
    """Catches: watch mode letting the builder of a card judge its own tests."""
    verdict = decide(facts(mode="watch", status="open", ever_held=frozenset({"reader"})))
    assert reasons(verdict) == ["verdict-by-holder"]


def test_in_watch_mode_by_committer_is_still_refused():
    """Catches: watch mode letting the committer of a test file judge it."""
    verdict = decide(facts(mode="watch", nodes=(node(committers=frozenset({"reader"})),)))
    assert reasons(verdict) == ["verdict-by-committer"]


def test_in_watch_mode_by_owner_is_still_refused():
    """Catches: watch mode letting the owner's terminal write a verdict."""
    assert reasons(decide(facts(mode="watch", caller="", owner=True))) == ["verdict-by-owner"]


def test_in_watch_mode_stale_is_still_refused():
    """Catches: watch mode letting a verdict about another text through."""
    assert reasons(decide(facts(mode="watch", nodes=(node(file_blob="b2"),)))) == ["verdict-stale"]


def test_in_watch_mode_no_caller_is_still_refused():
    """Catches: watch mode writing a row for a caller that is not established (no `by` can be written)."""
    assert reasons(decide(facts(mode="watch", caller="", owner=False))) == ["verdict-no-caller"]
