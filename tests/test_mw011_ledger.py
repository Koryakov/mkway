"""Card MW-011, part 4: a successful close by the orderer also writes a decision ledger row (card MW-008's ledger)
with the same text as the Log row. Synthetic task roots only."""
import json

from test_mw011_close import ORD, _close, _log, _ready, _row
import ledger

TEXT = "closed by s-ord; ordered by s-ord"


def _profile(root):
    return json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))


def test_a_close_by_the_orderer_also_writes_a_ledger_row(tmp_path):
    """E25 (rule 5): on a successful close by the orderer the ledger gets one row for the card whose quote is the same
    text as the Log row, «closed by <session id>; ordered by <value>»; a refused close writes no ledger row.
    Catches: a close that leaves the decision ledger without its trace."""
    refused = _ready(tmp_path / "refused", cells=("tests/test_bad.py::test_bad",))
    assert _close(refused, ORD)[:2] == ("cli", "close-tests-failing")
    assert ledger.read(refused, _profile(refused)) == []
    root = _ready(tmp_path / "ok")
    assert _close(root, ORD)[:2] == ("ok", None)
    assert _row(root)["status"] == "closed" and TEXT in _log(root)
    rows = ledger.read(root, _profile(root))
    assert len(rows) == 1
    assert rows[0]["card"] == "CARD-001" and rows[0]["quote"] == TEXT
