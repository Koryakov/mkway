"""Card MW-100 (decisions: R251, R251a, R251b A, B), layer shell: `mkway verdict recut <card> <node> <reason>` on a real small git
repository: the table row, the record (kind `verdict-recut`) and the ledger row it writes, the facts it reads from git, the
budget after a recut, the proof at close, and the command run in process (owner, usage). Synthetic sessions and names only."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/: the shared helpers and `_engine`
import _mw080 as w  # noqa: E402
import _mw100 as m  # noqa: E402
import verdicts  # noqa: E402

REASON = "the row now says LF line ends"
ANSWER = f"answers agent-1: {REASON}"


def _ready(tmp_path, **kw):
    """The card committed, one weak verdict by a reader run, and a commit after that run ended: a recut may follow."""
    root = m.lead_root(tmp_path, **kw)
    m.weak_run(root)
    m.change_cut(root, 130)
    return root


def _reasons(verdict):
    return [r.reason for r in verdict.refusals]


def _new_run(root, session, agent, started, ended):
    w.add_agent(root, session=session, agent_type=w.CHECKER, agent_id=agent, started=started, ended=ended, guard=w.CARD)
    return w.apply(root, session, [m.N1], "weak", "still weak")


# ---- what an allowed recut writes -------------------------------------------------------------------------------------

def test_an_allowed_recut_writes_the_row_the_record_and_the_ledger_row(tmp_path, monkeypatch):
    """Checks: an allowed recut leaves the typed row in the verdict file, one verdict-recut record and one ledger row."""
    root = _ready(tmp_path)
    assert m.recut(root, monkeypatch).allowed
    last = verdicts.rows_of(root, w.CARD)[-1]
    assert ((last.node, last.verdict), len(m.recut_records(root)), len(m.card_ledger_rows(root))) == (
        (w.N1, "recut"), 1, 1)


def test_the_row_reason_names_the_answered_agent_and_no_run_number(tmp_path, monkeypatch):
    """Catches: a reason cell that carries a run number (R196 keeps numbers in the record) or lacks the agent id (R251b A)."""
    root = _ready(tmp_path)
    m.recut(root, monkeypatch)
    assert verdicts.rows_of(root, w.CARD)[-1].reason == ANSWER


def test_the_recut_record_has_kind_verdict_recut_and_its_fields(tmp_path, monkeypatch):
    """Catches: a recut record that lacks the node, the answered agent, the reason, the session or the time (R251b B)."""
    root = _ready(tmp_path)
    m.recut(root, monkeypatch, at=200)
    (record,) = m.recut_records(root)
    assert (record["node"], record["agent"], record["reason"], record["session"], record["time"]) == (
        w.N1, "agent-1", REASON, m.LEAD, w.iso(200))


def test_a_refused_recut_writes_nothing(tmp_path, monkeypatch):
    """Catches: a refused recut that still changes the verdict file, the proof file or the ledger."""
    root = _ready(tmp_path)
    found = m.recut(root, monkeypatch, caller="other")
    assert (_reasons(found), verdicts.rows_of(root, w.CARD)[-1].verdict, m.recut_records(root),
            m.card_ledger_rows(root)) == (["verdict-recut-not-lead"], "weak", [], [])


# ---- the cut must change (real git) -----------------------------------------------------------------------------------

def test_a_recut_with_no_change_is_refused_in_process(tmp_path, monkeypatch):
    """Catches: a recut with no commit since the answered run ended, a waiver in disguise."""
    root = m.lead_root(tmp_path)
    m.weak_run(root)
    assert _reasons(m.recut(root, monkeypatch)) == ["verdict-recut-no-change"]


def test_a_card_file_commit_alone_allows_the_recut(tmp_path, monkeypatch):
    """Checks: the nearest allow of the no-change refusal: only the card file (the row's words) was committed after the run."""
    root = m.lead_root(tmp_path)
    m.weak_run(root)
    m.change_cut(root, 150, card_only=True)
    assert m.recut(root, monkeypatch).allowed


def test_an_uncommitted_test_file_is_refused_as_recut_stale(tmp_path, monkeypatch):
    """Catches: a recut over a test file that is not HEAD's text, which the fresh reader would not read."""
    root = _ready(tmp_path)
    (root / w.FILE).write_text("def test_one():\n    assert 1 == 1\n", encoding="utf-8")
    assert _reasons(m.recut(root, monkeypatch)) == ["verdict-recut-stale"]


# ---- the recut row at close -------------------------------------------------------------------------------------------

def test_the_recut_row_is_proved_at_close_by_its_record(tmp_path, monkeypatch):
    """Checks: a recut row the command wrote has proof at close: its record, not a reader run (the lead is no reader)."""
    root = _ready(tmp_path)
    m.recut(root, monkeypatch)
    rows = verdicts.rows_of(root, w.CARD)
    assert verdicts.proof_problems(root, w.state_of(root), [w.CHECKER], w.CARD, rows) == {}


def test_a_typed_recut_row_reads_verdict_unproven_at_close(tmp_path):
    """Catches: a recut row typed by hand, with no recut record, read as proven at close."""
    root = _ready(tmp_path)
    import verdict_add
    verdict_add.put_rows(root, w.CARD, [verdicts.Row(w.N1, "recut", ANSWER, f"session:{m.LEAD}")])
    reason, _text = m.close_reason(root)
    assert reason == "verdict-unproven"


# ---- the budget after a recut and the second recut --------------------------------------------------------------------

def test_after_a_recut_two_new_runs_are_allowed_and_a_third_is_refused(tmp_path, monkeypatch):
    """Catches: the budget not starting again at the recut, or never closing again: two runs on the new cut, not three."""
    root = _ready(tmp_path)
    m.recut(root, monkeypatch, at=200)
    first = _new_run(root, "s1", "ra", 260, 300)
    second = _new_run(root, "s2", "rb", 310, 350)
    third = _new_run(root, "s3", "rc", 360, 400)
    assert (first.allowed, second.allowed, _reasons(third)) == (True, True, ["verdict-runs-exceeded"])


def test_a_second_recut_is_refused_as_exceeded_in_process(tmp_path, monkeypatch):
    """Catches: a third cut of a node that the second independent reader still calls weak."""
    root = _ready(tmp_path)
    m.recut(root, monkeypatch, at=200)
    _new_run(root, "s1", "ra", 260, 300)
    m.change_cut(root, 320)
    assert _reasons(m.recut(root, monkeypatch, at=400)) == ["verdict-recut-exceeded"]


# ---- the ledger row and the command -----------------------------------------------------------------------------------

def test_the_ledger_row_holds_the_card_the_node_the_run_and_the_reason(tmp_path, monkeypatch):
    """Checks: the engine-written ledger row has topic verdict recut, the lead as `by`, and the card, node, run and reason in the quote."""
    root = _ready(tmp_path)
    m.recut(root, monkeypatch)
    (row,) = m.card_ledger_rows(root)
    assert [part in row for part in (w.CARD, w.N1, "agent-1", REASON, f"session:{m.LEAD}")] == [True] * 5


def test_the_owners_terminal_is_refused_as_by_owner_in_process(tmp_path):
    """Catches: the owner's terminal writing a recut."""
    root = _ready(tmp_path)
    code, _out, err = w.run_cli(root, "verdict", "recut", w.CARD, w.N1, REASON, session=False)
    assert code == 1
    assert "verdict-by-owner" in err


def test_a_call_with_no_reason_is_a_usage_error(tmp_path):
    """Catches: a recut with a node and no reason, which would write a row nobody can read the cause of."""
    root = _ready(tmp_path)
    code, _out, err = w.run_cli(root, "verdict", "recut", w.CARD, w.N1, session=True, caller=m.LEAD)
    assert code == 2
    assert "reason" in err


def test_in_watch_mode_the_recut_pending_close_still_refuses(tmp_path, monkeypatch):
    """Catches: the close letting a card through on a last row recut because the profile's mode is watch (the close has no mode)."""
    root = _ready(tmp_path, mode="watch")
    m.recut(root, monkeypatch)
    reason, _text = m.close_reason(root)
    assert reason == "verdict-recut-pending"
