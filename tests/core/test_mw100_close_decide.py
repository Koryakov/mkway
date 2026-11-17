"""Card MW-100 (decisions: R251, R251a points 4 and 5, R251b B, D, E), layer core: the close check counts reader runs per node
per cut (`Facts.runs` is {node: the reader runs since its last recut}), refuses a last row `recut` as `verdict-recut-pending`
(also a true row older than the node's last recut record, `Facts.before_recut`), and a recut row with no record as unproven.
No disk, no git, no clock. One test id is one case."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/: `_engine` puts engine/ on the path
import _engine  # noqa: E402,F401
from core_verdicts import Facts, Row, decide  # noqa: E402

N1 = "tests/test_a.py::test_one"
N2 = "tests/test_a.py::test_two"
N3 = "tests/test_a.py::test_three"
GOOD = Row(N1, "true", "one clause, one case", "session:reader")
CUT = Row(N1, "recut", "answers agent-1: the row said byte for byte", "session:lead")


def facts(runs=None, rows=(GOOD,), nodes=(N1,), **kw):
    return Facts(nodes=tuple(nodes), rows=tuple(rows), authors={}, holder="session:holder", runs=runs or {}, **kw)


def reasons(verdict):
    return [r.reason for r in verdict.refusals]


# ---- the budget per node at close -------------------------------------------------------------------------------------

def test_a_third_reader_run_of_a_node_is_refused_as_runs_exceeded_at_close():
    """Catches: a node judged by a third reader run since its cut, accepted at close."""
    assert reasons(decide(facts(runs={N1: ("a", "b", "c")}))) == ["verdict-runs-exceeded"]


def _rows(*nodes):
    return tuple(Row(n, "true", "one clause, one case", "session:reader") for n in nodes)


def test_two_reader_runs_of_a_node_are_allowed_at_close():
    """Checks: the nearest allow of the third-run refusal: each of three nodes has two reader runs, at the limit."""
    three = facts(runs={N1: ("a", "b"), N2: ("a", "b"), N3: ("a", "b")}, rows=_rows(N1, N2, N3), nodes=(N1, N2, N3))
    assert decide(three).allowed


def test_d1_two_nodes_with_two_and_one_run_are_allowed_at_close():
    """Checks: case D1 at close: N1 has two reader runs, N2 and N3 one each (four per card, which the per-card count refused)."""
    three = facts(runs={N1: ("a", "c"), N2: ("b",), N3: ("d",)}, rows=_rows(N1, N2, N3), nodes=(N1, N2, N3))
    assert decide(three).allowed


def test_the_close_runs_exceeded_text_names_the_recut_command():
    """Catches: a refusal that promises the lead's word or a ledger row instead of naming the recut."""
    text = decide(facts(runs={N1: ("a", "b", "c")})).refusals[0].text
    assert ("mkway verdict recut" in text, N1 in text) == (True, True)
    assert "the lead's word" not in text


# ---- the recut row and the date at close ------------------------------------------------------------------------------

def test_a_last_row_recut_is_refused_as_recut_pending():
    """Catches: a card that closes while the last row of a node is the recut and no fresh verdict followed it."""
    assert reasons(decide(facts(rows=(CUT,)))) == ["verdict-recut-pending"]


def test_a_true_row_after_the_recut_is_allowed():
    """Checks: the nearest allow of the pending refusals: a true row dated after the node's last recut."""
    assert decide(facts(rows=(CUT, GOOD), before_recut=frozenset())).allowed


def test_a_true_row_older_than_the_recut_is_refused_as_recut_pending():
    """Catches: an older true row (restored by hand) read as the verdict of a node that was recut after it (R251b E)."""
    assert reasons(decide(facts(before_recut=frozenset({N1})))) == ["verdict-recut-pending"]


def test_a_recut_row_with_no_record_is_refused_as_unproven():
    """Catches: a recut row typed by hand, which no `mkway verdict recut` record backs."""
    assert reasons(decide(facts(rows=(CUT,), unproven={N1: "no record of a recut"}))) == ["verdict-unproven"]


def test_the_pending_text_names_the_fresh_verdict_to_run():
    """Catches: a refusal that does not say that a fresh blind reader must run `verdict add` on the new cut."""
    text = decide(facts(rows=(CUT,))).refusals[0].text
    assert ("mkway verdict add" in text, N1 in text) == (True, True)
