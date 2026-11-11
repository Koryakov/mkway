"""The subtask gate (card MW-003, deliverable 5; spec section 2 and its addendum; replaces reg 9). Synthetic task
roots only; the gate is called with the dispatcher's own context."""
import json

import pytest

from _engine import cli, gate_call, task_root
from test_cardmoves import _card_file, set_paths
import gate_subtask
import records
import register


def _profile(root):
    return json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))


def edit(root, path, session="s1"):
    v = gate_call(gate_subtask.check, root, tool="Edit", tool_input={"file_path": path}, session=session)
    return v.reason_id if v.kind == "refuse" else "allow"


@pytest.fixture
def task(tmp_path):
    root = task_root(tmp_path, paths={"exempt": ["notes/**"]})
    assert cli(root, "card", "new", "First", session=True)[0] == 0
    set_paths(root, "CARD-001", "`src/a.py`, `lib/`")
    return root


def test_precedence_and_status_from_the_register(task):
    """E27 (R15 A1; spec S1-S2): no taken card is `no-open-card`; a taken card that is not `open` in the register is
    `card-not-open` (the card file's own Status line is never read); then `file-not-in-card`. The messages name
    `card new` and `card take`, and the status with the command that moves it.
    Catches: a gate that reads the status from the card header, or lets a proposed card edit."""
    state = task / "mkway" / "state"
    assert edit(task, "src/a.py") == "no-open-card"
    v = gate_call(gate_subtask.check, task, tool_input={"file_path": "src/a.py"})
    assert "card new" in v.message and "card take" in v.message
    records.append(state, "s1", "take", "CARD-001")
    card = _card_file(task, "CARD-001")
    card.write_text(card.read_text(encoding="utf-8").replace("| **Status** | proposed |", "| **Status** | open |"),
                    encoding="utf-8")
    v = gate_call(gate_subtask.check, task, tool_input={"file_path": "src/a.py"})
    assert v.reason_id == "card-not-open" and "proposed" in v.message and "card open" in v.message
    assert cli(task, "card", "open", "CARD-001")[0] == 0
    assert edit(task, "src/a.py") == "allow"
    assert edit(task, "lib/deep/x.py") == "allow"
    assert edit(task, "src/b.py") == "file-not-in-card"
    assert edit(task, "other/src/a.py") == "file-not-in-card"
    assert edit(task, "src/a.py", session="s2") == "no-open-card"
    register.set_status(task, _profile(task), "CARD-001", "waiting")
    assert edit(task, "src/a.py") == "card-not-open"


def test_exempt_paths_and_card_files(task):
    """E27 (spec S3-S4): card files and the profile's exempt paths are allowed, even with no taken card; an empty
    `Paths` means no file rule. Catches: a session that cannot write its own new card before the owner opens it."""
    assert edit(task, "mkway/cards/CARD-001-first/CARD.md") == "allow"
    assert edit(task, "notes/today.md") == "allow"
    records.append(task / "mkway" / "state", "s1", "take", "CARD-001")
    set_paths(task, "CARD-001", "")
    assert cli(task, "card", "open", "CARD-001")[0] == 0
    assert edit(task, "anything/at/all.py") == "allow"


def test_paths_changed_until_the_owner_opens_again(task):
    """E28 (v3.1): when the card's `Paths` set differs from the recorded set (entries normalised, order, blanks and
    spaces ignored), edits are refused `card-paths-changed` until the text is restored; the session's own card
    file stays editable, so it can restore the text. Changed by MW-003 close-fix 10 (A(c)): Paths are recorded once,
    so the owner's `card open` of the open card records nothing and the edits stay refused. Catches: a session that
    widens its own scope by editing the card, which is an exempt file."""
    records.append(task / "mkway" / "state", "s1", "take", "CARD-001")
    assert cli(task, "card", "open", "CARD-001")[0] == 0
    set_paths(task, "CARD-001", "`./lib/` ,  `src/a.py`")
    assert edit(task, "src/a.py") == "allow"  # same set: order, spaces and `./` do not count
    set_paths(task, "CARD-001", "`src/a.py`, `lib/`, `src/b.py`")
    assert edit(task, "src/a.py") == "card-paths-changed"
    assert edit(task, "mkway/cards/CARD-001-first/CARD.md") == "allow"
    set_paths(task, "CARD-001", "`src/a.py`, `lib/`")
    assert edit(task, "src/a.py") == "allow"
    set_paths(task, "CARD-001", "`src/b.py`")
    assert edit(task, "src/b.py") == "card-paths-changed"
    assert cli(task, "card", "open", "CARD-001")[0] == 0
    assert edit(task, "src/b.py") == "card-paths-changed"  # close-fix 10: a re-open records nothing
    set_paths(task, "CARD-001", "`src/a.py`, `lib/`")
    assert edit(task, "src/a.py") == "allow"


def test_tampered_register_refuses_every_edit(task):
    """E28 (R19a): the gate checks the register's seal before it reads it; a difference refuses every edit
    (`register-tampered`), so a session that writes `open` into its own row cannot edit. Catches: a status read
    from an unsealed register."""
    records.append(task / "mkway" / "state", "s1", "take", "CARD-001")
    reg = task / "mkway" / "cards" / "REGISTER.md"
    reg.write_bytes(reg.read_bytes().replace(b"proposed", b"open"))
    assert edit(task, "src/a.py") == "register-tampered"
