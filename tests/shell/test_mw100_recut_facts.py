"""Card MW-100 (decisions: R251a points 2 to 4, R251b C, D, H), layer shell: the facts the recut and the budget read, on real
files and real git: the reader runs counted per node per cut from the proof records (old records without `nodes` included),
the bound of the answered run (its END, read in the session of its add record), the files that differ from HEAD, and the readers
that started after a recut. Synthetic sessions, agents and names only."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/: the shared helpers and `_engine`
import _mw080 as w  # noqa: E402
import _mw100 as m  # noqa: E402


def _recut_record(root, node=m.N1, agent="agent-1", at=200):
    w.logs.append_jsonl(w.state_of(root) / w.PROOF, {"kind": m.RECUT_KIND, "doc": w.VERDICT_REL, "node": node,
                                                     "agent": agent, "reason": "r", "session": m.LEAD,
                                                     "time": w.iso(at)})


# ---- the counting of reader runs (R251b C and D) ----------------------------------------------------------------------

def test_an_old_record_with_tests_and_no_nodes_counts_for_the_nodes_of_its_files(tmp_path):
    """Catches: an old record (no `nodes`) counted for a node of a file it never judged, or for none of its own file's nodes."""
    root = w.make_root(tmp_path)
    m.add_record(root, "a1", tests={w.FILE: "blob"})
    found = m.cuts(root, (m.N1, m.B1))
    assert (found[m.N1].runs, found[m.B1].runs) == (("a1",), ())


def test_an_old_record_with_neither_nodes_nor_tests_counts_for_every_node(tmp_path):
    """Catches: the oldest records (no `nodes`, no `tests`) dropped, so a card's old runs stop counting."""
    root = w.make_root(tmp_path)
    m.add_record(root, "a1")
    found = m.cuts(root, (m.N1, m.B1))
    assert (found[m.N1].runs, found[m.B1].runs) == (("a1",), ("a1",))


def test_a_record_with_nodes_counts_for_those_nodes_only(tmp_path):
    """Catches: a record that names its nodes counted for the other nodes of the card too."""
    root = w.make_root(tmp_path)
    m.add_record(root, "a1", nodes=[m.N2], tests={w.FILE: "blob"})
    found = m.cuts(root, (m.N1, m.N2))
    assert (found[m.N1].runs, found[m.N2].runs) == ((), ("a1",))


def test_a_record_with_no_agent_is_never_a_run(tmp_path):
    """Catches: a record with no `agent` key (no reader run behind it) counted as a reader run."""
    root = w.make_root(tmp_path)
    m.add_record(root, None)
    assert m.cuts(root)[m.N1].runs == ()


def test_d2_two_reader_agents_of_one_session_are_two_runs(tmp_path):
    """Catches: two reader agents of one session counted as one run (the old count of sessions), so the budget is too loose."""
    root = w.make_root(tmp_path)
    m.add_record(root, "a1", session="same")
    m.add_record(root, "a2", session="same")
    assert m.cuts(root)[m.N1].runs == ("a1", "a2")


def test_a_recut_record_ends_the_count_of_its_node(tmp_path):
    """Catches: runs before a recut still counted against the node's budget after it."""
    root = w.make_root(tmp_path)
    m.add_record(root, "a1")
    _recut_record(root)
    m.add_record(root, "a2")
    found = m.cuts(root)[m.N1]
    assert (found.runs, found.recuts) == (("a2",), 1)


def test_a_recut_record_is_never_a_run(tmp_path):
    """Catches: the recut record, which carries the answered agent id, counted as a reader run (the lead as a reader)."""
    root = w.make_root(tmp_path)
    _recut_record(root)
    assert m.cuts(root)[m.N1].runs == ()


# ---- the bound of the answered run (R251b H) --------------------------------------------------------------------------

def test_a_commit_between_the_start_and_the_end_of_the_run_is_not_a_change(tmp_path):
    """Catches: a commit made while the answered reader was still running counted as the change that answers it."""
    root = m.lead_root(tmp_path)
    m.weak_run(root)
    m.change_cut(root, when=90)
    assert m.facts(root).node.changed is False


def test_a_commit_after_the_end_of_the_run_is_a_change(tmp_path):
    """Checks: the nearest allow of the case above: the same commit made after the run ended is a change."""
    root = m.lead_root(tmp_path)
    m.weak_run(root)
    m.change_cut(root, when=150)
    assert m.facts(root).node.changed is True


def test_the_end_of_the_run_is_read_in_the_session_of_its_add_record(tmp_path):
    """Catches: the end of the answered run looked up in the lead's session, where no reader ran, so it is never found."""
    root = m.lead_root(tmp_path)
    m.weak_run(root, session="reader-session")
    found = m.facts(root, caller=m.LEAD).node
    assert (found.answered, found.ended.startswith("2026-11-11T10:02:00")) == ("agent-1", True)


def test_an_uncommitted_test_file_reads_as_a_stale_file(tmp_path):
    """Catches: a test file that differs from HEAD read as equal, so the next reader would read another text."""
    root = m.lead_root(tmp_path)
    m.weak_run(root)
    m.change_cut(root, when=150)
    (root / w.FILE).write_text("def test_one():\n    assert 1 == 1\n", encoding="utf-8")
    assert [entry[0] for entry in m.facts(root).node.stale] == [w.FILE]


def test_a_card_file_commit_alone_is_a_change(tmp_path):
    """Checks: a commit of the card file alone (the row's words changed) is a change of the cut."""
    root = m.lead_root(tmp_path)
    m.weak_run(root)
    m.change_cut(root, when=150, card_only=True)
    assert m.facts(root).node.changed is True


def test_the_readers_that_started_after_the_recut_are_the_only_ones_since_the_recut(tmp_path, monkeypatch):
    """Catches: a reader that started before the recut record counted as a run on the new cut."""
    root = m.lead_root(tmp_path)
    m.weak_run(root)
    m.change_cut(root, when=130)
    assert m.recut(root, monkeypatch, at=200).allowed
    w.add_agent(root, session="rx", agent_type=w.CHECKER, agent_id="a-early", started=135, ended=150)
    w.add_agent(root, session="rx", agent_type=w.CHECKER, agent_id="a-late", started=260, ended=300)
    assert w.read(root, "rx", [m.N1]).nodes[0].since_recut == ("a-late",)
