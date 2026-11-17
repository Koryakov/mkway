"""Card MW-049: every ledger row the engine writes on a card move names who made the move: `session:<id>` when a session
ran it, `owner` only from the owner's terminal. Synthetic roots only."""
from pathlib import Path

from _engine import cli
import ledger
from _mw017 import lead_root, new_card, profile_of, register_lead, session_run
from _mw020 import deliverable, green, make_root
from _mw098_mw011 import ORD, _close, _profile, _ready
from _mw098_ledger import bare_ledger_writes
import cardtool

ENGINE = Path(__file__).resolve().parent.parent / "engine"


def _by(root):
    return [r["by"] for r in ledger.read(root, profile_of(root))]


def test_open_by_a_lead_writes_the_session_and_the_owner_writes_none(tmp_path):
    """Catches: a lead's move labelled as the owner's. E1: a registered lead's card open of its own card writes a ledger row with by session:<id>; the owner's open from the terminal writes no session label."""
    root = lead_root(tmp_path)
    register_lead(root, "lead-a")
    mine = new_card(root, "lead-a", "Mine")
    code, _out, err = session_run(root, "lead-a", "card", "open", mine)
    assert code == 0, err
    assert _by(root) == ["session:lead-a"]
    owner_root = lead_root(tmp_path / "owner")
    other = new_card(owner_root, "lead-a", "Mine")
    assert cli(owner_root, "card", "open", other)[0] == 0
    assert all(by == "owner" for by in _by(owner_root))


def test_close_by_the_orderer_writes_the_session_and_the_owner_writes_none(tmp_path):
    """Catches: an orderer's close labelled as the owner's. E2: the orderer's card close writes a ledger row with by session:<id>; the owner's close from the terminal writes no session label."""
    root = _ready(tmp_path / "s")
    assert _close(root, ORD)[:2] == ("ok", None)
    assert _by(root) == [f"session:{ORD}"]
    owner_root = _ready(tmp_path / "o", creator=None)
    assert cli(owner_root, "card", "close", "CARD-001")[0] == 0
    assert all(by == "owner" for by in _by(owner_root))
    assert _profile(owner_root)


def test_built_by_a_session_and_by_the_owner(tmp_path):
    """Checks: built writes by session:<id> from a session and owner from the owner's terminal. E3."""
    root = make_root(tmp_path / "s")
    green(root)
    rel = deliverable(root)
    cardtool.issue_by_permit(root / "mkway" / "state", "s1")
    assert cli(root, "built", rel, session=True)[0] == 0
    assert _by(root) == ["session:s1"]
    owner_root = make_root(tmp_path / "o")
    green(owner_root)
    rel = deliverable(owner_root)
    assert cli(owner_root, "built", rel)[0] == 0
    assert _by(owner_root) == ["owner"]


def test_delivered_give_and_release_write_no_session_labelled_owner_row(tmp_path):
    """Catches: a ledger row that a session could be mistaken for. E4: delivered and give from the owner's terminal write no such row; any row they write is owner."""
    root = make_root(tmp_path)
    green(root)
    rel = deliverable(root)
    assert cli(root, "built", rel)[0] == 0
    before = _by(root)
    assert cli(root, "delivered", rel)[0] == 0
    assert _by(root) == before
    assert all(by == "owner" for by in _by(root))


def test_every_engine_ledger_write_names_its_by():
    """Catches: a future move that writes a row with no caller named. E5: no engine call of ledger.add leaves by to the default owner."""
    assert bare_ledger_writes(ENGINE) == []
