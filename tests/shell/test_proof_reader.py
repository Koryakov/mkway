"""Card MW-068 (ruling R173 item 2), layer shell: the ONE helper that reads the fresh-reader proof, `proof.fresh_reader_problem`,
on real files. The outbox gate and the verdict check at close both call it; no copy. Times are seconds after `_mw019.T0`:
the document's last change at 0, a checker agent started at 60 and ended at 120, the write at 180. Synthetic values only."""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/: the shared helpers and `_engine`
from _mw019 import add_agent, iso, make_root, state_dir, write_doc  # noqa: E402
import proof  # noqa: E402

ENGINE = Path(__file__).resolve().parents[2] / "engine"


def _case(tmp_path, **agent):
    """A document changed at 0, and (unless `agent` is None) a checker agent in session s1."""
    root = make_root(tmp_path)
    rel = write_doc(root)
    if agent.get("none") is not True:
        add_agent(root, **agent)
    return root, Path(root) / rel


def test_a_checker_agent_that_ran_in_the_session_between_the_change_and_the_write_is_a_proof(tmp_path):
    """Checks: the nearest allow of every deny below: started after the change, ended after it and before the write."""
    root, doc = _case(tmp_path)
    assert proof.fresh_reader_problem(state_dir(root), doc, "s1", iso(180), "critic") is None


def test_no_agent_row_is_no_proof(tmp_path):
    """Catches: a write accepted with no fresh reader behind it."""
    root, doc = _case(tmp_path, none=True)
    problem = proof.fresh_reader_problem(state_dir(root), doc, "s1", iso(180), "critic")
    assert problem
    assert "no agent of type `critic`" in problem


def test_an_agent_of_another_type_is_no_proof(tmp_path):
    """Catches: any agent counted, not one of the checker type."""
    root, doc = _case(tmp_path, agent_type="explorer")
    assert "no agent of type `critic`" in proof.fresh_reader_problem(state_dir(root), doc, "s1", iso(180), "critic")


def test_an_agent_of_another_session_is_no_proof(tmp_path):
    """Catches: a reader run by one session proving the write of another."""
    root, doc = _case(tmp_path, session="s2")
    assert "no agent of type `critic`" in proof.fresh_reader_problem(state_dir(root), doc, "s1", iso(180), "critic")


def test_an_agent_that_ended_after_the_write_is_no_proof(tmp_path):
    """Catches: a write that came before the reader finished."""
    root, doc = _case(tmp_path)
    assert "no agent of type `critic`" in proof.fresh_reader_problem(state_dir(root), doc, "s1", iso(100), "critic")


def test_an_agent_that_started_before_the_last_change_is_no_proof(tmp_path):
    """Catches: a reader that read an older text than the document now holds."""
    root, doc = _case(tmp_path, started=-30, ended=120)
    assert "no agent of type `critic`" in proof.fresh_reader_problem(state_dir(root), doc, "s1", iso(180), "critic")


@pytest.mark.parametrize("session, written", [("", "t"), ("not established", "t"), ("s1", None), ("s1", "not a time")])
def test_a_write_record_with_no_session_or_no_time_is_no_proof(tmp_path, session, written):
    """Catches: a record that names no session or no time accepted as a write, the one case the helper cannot place."""
    root, doc = _case(tmp_path)
    when = iso(180) if written == "t" else written
    problem = proof.fresh_reader_problem(state_dir(root), doc, session, when, "critic")
    assert problem
    assert "names no session or no time" in problem


def test_the_outbox_and_the_verdict_check_read_the_proof_through_one_helper():
    """Catches: a second copy of the fresh-reader read (the outbox and the close each with their own), which would drift."""
    outbox, verdicts, helper = [(ENGINE / n).read_text(encoding="utf-8") for n in ("outbox.py", "verdicts.py", "proof.py")]
    assert "proof.fresh_reader_problem(" in outbox
    assert "proof.fresh_reader_problem(" in verdicts
    assert not re.search(r"agents\.rows\(", outbox), "outbox.py"
    assert not re.search(r"agents\.rows\(", verdicts), "verdicts.py"
    assert "agents.rows(" in helper
