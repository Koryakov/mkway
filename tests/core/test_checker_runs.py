"""Card MW-071 (decision: R181), layer core: at most two checker runs per card, and verdict rows only for the nodes new or
changed in the card's own commits. A run is a reader agent run counted per node since its last recut (`Facts.runs`, {node: runs}, R251b); `changed`
is the set of nodes new or changed in the card's commits, None when the shell cannot tell. No disk, no git, no clock."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/: `_engine` puts engine/ on the path
import _engine  # noqa: E402,F401
from core_verdicts import Facts, Row, decide  # noqa: E402

NODE = "tests/test_a.py::test_one"
OTHER = "tests/test_a.py::test_two"
GOOD = Row(NODE, "true", "one clause, one case", "session:reader")


def facts(runs=(), changed=None, nodes=(NODE,), rows=(GOOD,)):
    return Facts(nodes=tuple(nodes), rows=tuple(rows), authors={}, holder="session:holder",
                 runs={NODE: tuple(runs)} if runs else {}, changed=changed)


def reasons(verdict):
    return [r.reason for r in verdict.refusals]


def test_two_checker_runs_on_a_card_are_allowed():
    """Checks: the nearest allow of the third-run refusal, with one run less."""
    assert decide(facts(runs=("s2", "s3"))).allowed


def test_a_third_checker_run_is_refused_as_runs_exceeded():
    """Catches: a card re-judged round after round, a third reader run until a verdict passes, the cost the owner's rule forbids."""
    verdict = decide(facts(runs=("s2", "s3", "s4")))
    assert not verdict.allowed
    assert reasons(verdict) == ["verdict-runs-exceeded"]


def test_the_runs_exceeded_text_names_the_two_earlier_runs():
    """Catches: a refusal that does not say which two runs were spent, so the lead cannot find them in the record."""
    text = decide(facts(runs=("s2", "s3", "s4"))).refusals[0].text
    assert "s2" in text
    assert "s3" in text


def test_a_card_naming_no_node_is_not_refused_for_its_runs():
    """Checks: a card that names no test node is allowed, whatever its reader runs."""
    assert decide(facts(runs=("s2", "s3", "s4"), nodes=(), rows=())).allowed


def test_a_node_changed_in_the_card_with_no_row_is_refused_as_missing():
    """Catches: a node changed in the card with no verdict row is refused as verdict-missing, the nearest deny of the unchanged-node allow."""
    assert reasons(decide(facts(changed=frozenset({NODE}), rows=()))) == ["verdict-missing"]


def test_a_node_not_changed_in_the_card_needs_no_row():
    """Checks: a node the card did not touch (an older test) is allowed with no verdict row."""
    assert decide(facts(changed=frozenset({OTHER}), rows=())).allowed


def test_with_no_change_information_every_named_node_needs_a_row():
    """Catches: no git or no commit naming the card read as nothing changed, so every node passes with no verdict."""
    assert reasons(decide(facts(changed=None, rows=()))) == ["verdict-missing"]
