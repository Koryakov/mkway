"""Card MW-136: the refusal `card-paths-changed` names the routes that work today, and each route is run. Synthetic roots only."""
import re

from _engine import cli, gate_call
from _mw017 import lead_root, new_card, register_lead, session_run
import gate_subtask
import records


def _state(root):
    return root / "mkway" / "state"


def _set_paths(root, card_id, value):
    (folder,) = [p for p in (root / "mkway" / "cards").iterdir() if p.name.startswith(card_id + "-")]
    path = folder / "CARD.md"
    text = re.sub(r"^\| \*\*Paths\*\* \|.*\|$", f"| **Paths** | {value} |", path.read_text(encoding="utf-8"), flags=re.M)
    path.write_text(text, encoding="utf-8")


def _edit(root, path, session):
    return gate_call(gate_subtask.check, root, tool="Edit", tool_input={"file_path": path}, session=session)


def _world(tmp_path):
    """A lead, its card A (Paths `src/a.py`) opened by the owner and held by session s1, then A's Paths widened."""
    root = lead_root(tmp_path)
    register_lead(root, "lead-a")
    card = new_card(root, "lead-a", "Mine")
    _set_paths(root, card, "`src/a.py`")
    records.append(_state(root), "s1", "take", card)
    assert cli(root, "card", "open", card)[0] == 0
    _set_paths(root, card, "`src/a.py`, `src/b.py`")
    return root, card


def test_the_refusal_no_longer_names_the_owners_reopen(tmp_path):
    """Catches: a refusal that sends the owner to a re-open, which records nothing on an open card."""
    root, card = _world(tmp_path)
    verdict = _edit(root, "src/a.py", "s1")
    assert (verdict.reason_id, "again" in verdict.message, f"card open {card}" in verdict.message) == ("card-paths-changed", False, False)


def test_the_refusal_names_the_restore_and_the_new_card_routes(tmp_path):
    """Catches: a refusal that names no route that works today."""
    root, _card = _world(tmp_path)
    message = _edit(root, "src/a.py", "s1").message
    assert ("restore them to the recorded set" in message, "new card" in message, "lead that orders it opens it" in message) == (True, True, True)


def test_restoring_the_recorded_paths_makes_the_same_edit_pass(tmp_path):
    """Catches: a named restore that does not let the same edit through."""
    root, card = _world(tmp_path)
    assert _edit(root, "src/a.py", "s1").kind == "refuse"
    _set_paths(root, card, "`src/a.py`")
    assert _edit(root, "src/a.py", "s1").kind == "allow"


def test_a_new_card_opened_by_its_orderer_lets_an_extra_file_pass(tmp_path):
    """Catches: a named new-card route that does not let the extra file's edit through under the new card."""
    root, _card = _world(tmp_path)
    new = new_card(root, "lead-a", "Extra")
    _set_paths(root, new, "`src/b.py`")
    code, _out, err = session_run(root, "lead-a", "card", "open", new)
    assert code == 0, err
    records.append(_state(root), "s2", "take", new)
    assert _edit(root, "src/b.py", "s2").kind == "allow"
