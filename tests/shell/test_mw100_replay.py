"""Card MW-100 (decisions: R251, R251a, R251b C, D), layer shell: replays of the real case on a real small git repository. A
card of four test nodes: run 1 of a reader says all true; a fix to one test follows; run 2 of a second reader says that one
node is weak. Before this card the close refused `verdict-weak`, a third run was refused, and no code read the lead's word or
a ledger row that the two texts promised, so the card could never close. Replay 1: the old records (no `nodes` key) still
count for the node, and both refusals name the recut. Replay 2: the route that closes it. Synthetic names only."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/: the shared helpers and `_engine`
import _mw080 as w  # noqa: E402
import _mw100 as m  # noqa: E402
import verdicts  # noqa: E402

ALL = [w.N1, w.N2, w.N3, w.B1]


def _run_one_and_two(tmp_path, monkeypatch):
    """Run 1 (agent-1): all four true. The fix commit. Run 2 (agent-2): the first node weak. Both records, then old-style."""
    root = m.lead_root(tmp_path)
    w.add_agent(root, session="reader1", agent_type=w.CHECKER, agent_id="agent-1", started=60, ended=120, guard=w.CARD)
    m.clock(monkeypatch, 125)
    assert w.apply(root, "reader1", ALL, "true", "one clause, one case").allowed
    m.change_cut(root, 130)
    m.old_mtimes(root)
    w.add_agent(root, session="reader2", agent_type=w.CHECKER, agent_id="agent-2", started=140, ended=190, guard=w.CARD)
    m.clock(monkeypatch, 195)
    assert w.apply(root, "reader2", [w.N1], "weak", "row E4 says byte for byte, but the test replaces CRLF with LF").allowed
    m.strip_nodes(root)
    return root


def test_replay_one_old_records_count_and_both_refusals_name_the_recut(tmp_path, monkeypatch):
    """Catches: the old runs not counted for the node (a third run allowed), or a refusal that leaves no way out of the weak verdict."""
    root = _run_one_and_two(tmp_path, monkeypatch)
    w.add_agent(root, session="reader3", agent_type=w.CHECKER, agent_id="agent-3", started=260, ended=300, guard=w.CARD)
    third = w.apply(root, "reader3", [w.N1], "weak", "still weak")
    reason, close_text = m.close_reason(root)
    assert ([r.reason for r in third.refusals], reason, "mkway verdict recut" in third.refusals[0].text,
            "mkway verdict recut" in close_text) == (["verdict-runs-exceeded"], "verdict-weak", True, True)


def test_replay_two_the_recut_route_lets_the_verdict_check_pass(tmp_path, monkeypatch):
    """Checks: after run 2 is weak, the cut changed and the lead's recut, a run that started before the recut is refused, a
    fresh run writes `true`, and the close-time verdict check passes."""
    root = _run_one_and_two(tmp_path, monkeypatch)
    m.change_cut(root, 192)
    assert m.recut(root, monkeypatch, at=200).allowed
    w.add_agent(root, session="reader-old", agent_type=w.CHECKER, agent_id="agent-old", started=193, ended=196)
    before = w.apply(root, "reader-old", [w.N1], "true", "the new cut reads fine")
    w.add_agent(root, session="reader3", agent_type=w.CHECKER, agent_id="agent-3", started=260, ended=300, guard=w.CARD)
    m.clock(monkeypatch, 320)
    fresh = w.apply(root, "reader3", [w.N1], "true", "the new cut reads fine")
    m.old_mtimes(root)
    assert ([r.reason for r in before.refusals], fresh.allowed, m.close_reason(root)[0],
            verdicts.rows_of(root, w.CARD)[-1].verdict) == (["verdict-run-before-recut"], True, "", "true")
