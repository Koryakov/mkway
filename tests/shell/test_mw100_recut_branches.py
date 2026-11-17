"""Card MW-100, layer shell: the branches of the new code that the first coverage run found untested (rows E106 to E115, added
after the code, see the card Log). Real small git repository, synthetic sessions and names only."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/: the shared helpers and `_engine`
import _mw080 as w  # noqa: E402
import _mw100 as m  # noqa: E402
import cardtool  # noqa: E402
import verdict_add  # noqa: E402
import verdict_recut  # noqa: E402
import verdicts  # noqa: E402

REASON = "the row now says LF line ends"


def _ready(tmp_path, **kw):
    root = m.lead_root(tmp_path, **kw)
    m.weak_run(root)
    m.change_cut(root, 130)
    return root


def test_the_command_in_process_prints_the_recut_and_exits_zero(tmp_path):
    """Checks: an allowed `verdict recut` run in process exits 0 and prints the node and that it was re-cut."""
    root = _ready(tmp_path)
    code, out, _err = w.run_cli(root, "verdict", "recut", w.CARD, w.N1, REASON, session=True, caller=m.LEAD)
    assert code == 0
    assert (w.N1 in out, "recut" in out, "agent-1" in out) == (True, True, True)


def test_a_write_error_is_reported_as_not_written(tmp_path, monkeypatch):
    """Catches: a failed write of the verdict file crashing the command instead of a one-line failure."""
    root = _ready(tmp_path)

    def broken(*_args, **_kw):
        raise OSError("disk full")

    monkeypatch.setattr(verdict_add, "put_rows", broken)
    code, _out, err = w.run_cli(root, "verdict", "recut", w.CARD, w.N1, REASON, session=True, caller=m.LEAD)
    assert code == 1
    assert "not written" in err


def test_a_typed_weak_row_has_no_answered_run(tmp_path):
    """Catches: a weak row that no add record holds read as answering some run."""
    root = m.lead_root(tmp_path)
    verdict_add.put_rows(root, w.CARD, [verdicts.Row(w.N1, "weak", "typed by hand", "session:reader")])
    assert m.facts(root).node.answered == ""


def test_an_answered_run_with_no_end_row_reads_no_end_and_no_change(tmp_path):
    """Catches: a run whose end row is missing read as ended, so a change is invented without a bound."""
    root = _ready(tmp_path)
    (w.state_of(root) / "agents.jsonl").write_text("", encoding="utf-8")
    found = m.facts(root).node
    assert (found.answered, found.ended, found.changed) == ("agent-1", "", False)


def test_a_card_not_in_the_register_is_card_unknown(tmp_path):
    """Catches: a recut for a card that is not in the register reaching the git reads."""
    root = _ready(tmp_path)
    with pytest.raises(cardtool.CardError) as caught:
        verdict_recut.read_facts(root, w.profile_of(root), w.state_of(root), "CARD-099", w.N1, m.LEAD)
    assert caught.value.reason == "card-unknown"


def test_a_card_with_no_card_file_is_card_unknown(tmp_path):
    """Catches: a registered card whose folder holds no card file reaching the git reads."""
    root = _ready(tmp_path)
    w.lose_card_file(root)
    with pytest.raises(cardtool.CardError) as caught:
        verdict_recut.read_facts(root, w.profile_of(root), w.state_of(root), w.CARD, w.N1, m.LEAD)
    assert caught.value.reason == "card-unknown"


def test_a_refusal_watch_mode_let_through_is_named_in_the_record(tmp_path, monkeypatch):
    """Checks: in watch mode a non-lead is let through, and the recut record lists the refusal that was watched."""
    root = _ready(tmp_path, mode="watch")
    assert m.recut(root, monkeypatch, caller="other").allowed
    assert m.recut_records(root)[0]["watched"] == ["verdict-recut-not-lead"]


def test_an_older_true_row_restored_by_hand_is_recut_pending_at_close(tmp_path, monkeypatch):
    """Catches: a true row of a reader, older than the node's recut, restored by hand and read as the new verdict (R251b E)."""
    root = m.lead_root(tmp_path)
    m.weak_run(root, word="true")
    m.change_cut(root, 130)
    w.add_agent(root, session="reader2", agent_type=w.CHECKER, agent_id="agent-2", started=140, ended=190, guard=w.CARD)
    assert w.apply(root, "reader2", [m.N1], "weak", "still weak").allowed
    m.change_cut(root, 192)
    assert m.recut(root, monkeypatch, at=200).allowed
    reason = "row E4 says byte for byte, but the test replaces CRLF with LF"
    verdict_add.put_rows(root, w.CARD, [verdicts.Row(m.N1, "true", reason, "session:reader")])
    m.old_mtimes(root)
    assert m.close_reason(root)[0] == "verdict-recut-pending"


def test_a_recut_of_another_node_does_not_touch_the_count(tmp_path):
    """Catches: a recut record of one node changing the cut of a node it does not name."""
    root = w.make_root(tmp_path)
    m.add_record(root, "a1")
    w.logs.append_jsonl(w.state_of(root) / w.PROOF, {"kind": m.RECUT_KIND, "doc": w.VERDICT_REL, "node": m.N1,
                                                     "agent": "a1", "reason": "r", "session": m.LEAD, "time": w.iso(5)})
    assert m.cuts(root, (m.N2,))[m.N2].runs == ("a1",)


def test_a_proof_line_that_is_not_json_is_skipped(tmp_path):
    """Catches: one damaged line of the proof file hiding the records that follow it."""
    root = w.make_root(tmp_path)
    m.add_record(root, "a1")
    with open(w.state_of(root) / w.PROOF, "a", encoding="utf-8") as handle:
        handle.write("this line is not json\n")
    m.add_record(root, "a2")
    assert m.cuts(root)[m.N1].runs == ("a1", "a2")
