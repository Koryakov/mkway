"""Card MW-100 (decisions: R251a points 3 and 4, R251b C, D), layer core: the budget of `verdict add` is counted per node per
cut. A `Node` carries the reader runs already used for it since its last recut (`used`) and, for a recut node, the readers
that started after the recut record (`since_recut`; None: the node was never recut). A run used before a recut can never be
used again. No disk, no git, no clock. One test id is one case."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/: `_engine` puts engine/ on the path
import _engine  # noqa: E402,F401
from core_verdict_add import Facts, Node, decide  # noqa: E402

NODE = "tests/test_a.py::test_one"
OTHER = "tests/test_a.py::test_two"


def node(name=NODE, **kw):
    base = {"known": True, "committers": frozenset(), "commit": "c0ffee1", "head_blob": "b1", "file_blob": "b1",
            "readers": ("r1",), "fresh": ("r1",), "used": (), "since_recut": None}
    base.update(kw)
    return Node(name, **base)


def facts(*nodes, **kw):
    base = {"caller": "reader", "status": "waiting", "holder": "", "ever_held": frozenset(),
            "nodes": nodes or (node(),), "mode": "trip", "red_proven": True}  # MW117-D1: the card has its red-proof row
    base.update(kw)
    return Facts(**base)


def reasons(verdict):
    return [r.reason for r in verdict.refusals]


def new_run(run, **kw):
    return node(readers=(run,), fresh=(run,), **kw)


# ---- the budget per node ------------------------------------------------------------------------------------------------

def test_a_node_with_one_run_takes_a_second_distinct_run():
    """Checks: the nearest allow of the third-run deny: the node has one earlier run, a new distinct run is its second."""
    verdict = decide(facts(new_run("r2", used=("r1",))))
    assert verdict.allowed
    assert verdict.number == 2


def test_a_node_with_two_runs_refuses_a_third_as_runs_exceeded():
    """Catches: a node judged again and again by new reader runs until one verdict passes."""
    assert reasons(decide(facts(new_run("r3", used=("r1", "r2"))))) == ["verdict-runs-exceeded"]


def test_the_runs_exceeded_text_names_the_node_the_runs_and_the_recut_command():
    """Catches: a refusal that promises the lead's word or a ledger row, which no code reads, instead of the recut."""
    text = decide(facts(new_run("r3", used=("r1", "r2")))).refusals[0].text
    assert (NODE in text, "r1" in text, "r2" in text, "mkway verdict recut" in text) == (True, True, True, True)
    assert "the lead's word" not in text


def test_d1_a_run_on_the_first_node_after_a_run_on_the_second_is_allowed():
    """Checks: case D1, runs r1 on N1, r2 on N2, r3 on N1: each node has its own budget, so the third call is allowed."""
    assert decide(facts(new_run("r3", used=("r1",)))).allowed


def test_a_node_that_was_recut_starts_with_an_empty_budget():
    """Checks: after a recut the node has no used run, and a reader that started after the recut is its first run."""
    verdict = decide(facts(new_run("r5", used=(), since_recut=("r5",))))
    assert verdict.allowed
    assert verdict.number == 1


def test_a_run_used_for_the_node_is_chosen_again_at_the_limit():
    """Checks: two runs spent, one of them fresh again: the used run is chosen, so the call is allowed."""
    verdict = decide(facts(node(readers=("r1", "r3"), fresh=("r1", "r3"), used=("r1", "r2"))))
    assert (verdict.allowed, verdict.run) == (True, "r1")


# ---- a run that started before the recut ------------------------------------------------------------------------------

def test_a_fresh_run_that_started_before_the_recut_is_refused_as_run_before_recut():
    """Catches: a reader that read the old cut, started after its last commit but before the recut, judging the new cut."""
    assert reasons(decide(facts(new_run("r4", since_recut=())))) == ["verdict-run-before-recut"]


def test_a_run_that_started_after_the_recut_is_allowed():
    """Checks: the nearest allow of the run-before-recut deny: the same run started after the recut record."""
    assert decide(facts(new_run("r4", since_recut=("r4",)))).allowed


def test_the_run_before_recut_text_names_the_node():
    """Catches: a refusal that does not say which node was recut, so the reader cannot tell what to wait for."""
    assert NODE in decide(facts(new_run("r4", since_recut=()))).refusals[0].text


def test_in_watch_mode_run_before_recut_is_allowed_and_listed():
    """Checks: watch mode lets a run that started before the recut through and lists the reason."""
    found = decide(facts(new_run("r4", since_recut=()), mode="watch"))
    assert (found.allowed, [r.reason for r in found.watched]) == (True, ["verdict-run-before-recut"])


def test_in_trip_mode_the_same_run_before_recut_is_refused():
    """Catches: trip mode letting the run through, the nearest deny of the watch case."""
    assert reasons(decide(facts(new_run("r4", since_recut=()), mode="trip"))) == ["verdict-run-before-recut"]


def test_a_call_with_two_nodes_needs_a_run_after_the_recut_of_the_recut_node():
    """Catches: one run common to two nodes accepted for a node that was recut after that run started."""
    both = facts(node(readers=("r4",), fresh=("r4",), since_recut=()), node(OTHER, readers=("r4",), fresh=("r4",)))
    assert reasons(decide(both)) == ["verdict-run-before-recut"]
