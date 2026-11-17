"""Card MW-102 (decision: R254), replay of the real case: a card was closed, its lead (the orderer, holding no card) then staged
`tests/verdicts/<card>.md` and the commit gate refused `file-not-in-card` ("this session holds no open card (no card is
taken)"), because no session could commit a verdict file. The shape here: a closed card the session `lead` ordered, a verdict
file whose rows were written by the real `verdict add`. Synthetic names only."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/: the shared helpers and `_engine`
import _mw102 as v  # noqa: E402


def test_replay_the_orderer_of_a_closed_card_commits_its_verdict_file(tmp_path):
    """Catches: the real case, the orderer of a closed card refused its own card's verdict file with `file-not-in-card`."""
    root = v.verdict_root(tmp_path)
    v.add(root, v.N1, v.N2, v.N3, v.B1)
    v.close_card(root)
    v.stage(root)
    assert v.decide(root) == ("allow", "")


def test_replay_a_session_that_ordered_no_card_is_refused_the_file(tmp_path):
    """Catches: a session that ordered no card committing this card's verdict file; the nearest deny of the replay."""
    root = v.verdict_root(tmp_path)
    v.add(root, v.N1)
    v.close_card(root)
    v.stage(root)
    reason, text = v.decide(root, session="other")
    assert (reason, "orderer of CARD-001" in text) == ("file-not-in-card", True)
