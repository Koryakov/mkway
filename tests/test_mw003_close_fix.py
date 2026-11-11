"""Fixes from the batch-2 close check of card MW-003 (H2, H3, M2, M3, L1-L6). Synthetic task roots only; a
session's command runs as `cli(..., session=True)`, a gate as the dispatcher calls it."""
import json

import pytest

from _engine import cli, gate_call, task_root
from test_cardmoves import _card_file, _reason, _row, set_paths, set_tests
import gate_lock
import gate_subtask
import mkway as engine_cli
import records
import register
import startline

CLI = "python mkway/engine/mkway.py"


def _profile(root):
    return json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))


def _light(root):
    p = _profile(root)
    p["cards"] = {"owner_moves": []}
    (root / "mkway" / "profile.json").write_text(json.dumps(p), encoding="utf-8")


def _edit(root, path, session="s1"):
    v = gate_call(gate_subtask.check, root, tool="Edit", tool_input={"file_path": path}, session=session)
    return v.reason_id if v.kind == "refuse" else "allow"


def _shell(root, command, session="s2"):
    v = gate_call(gate_lock.check, root, tool="Bash", tool_input={"command": command}, session=session)
    return v.reason_id if v.kind == "refuse" else "allow"


@pytest.fixture
def task(tmp_path):
    root = task_root(tmp_path, test_roots=["tests"])
    (root / "tests").mkdir()
    (root / "tests" / "test_a.py").write_text("def test_one():\n    pass\n", encoding="utf-8")
    assert cli(root, "card", "new", "First", session=True)[0] == 0
    assert cli(root, "card", "new", "Second", session=True)[0] == 0
    return root


def test_paths_separators_and_every_path_globs(task):
    """H2 (close check): `card open` and the subtask gate read Paths with one separator rule (`,` and `;`), and an
    entry that matches every path (`**`, `?*`, `*?`, `**?`, `?**`, also after a `;`) is `card-paths-too-wide`.
    Catches: a `;`-joined `**` that slips past the check and opens the card to every path."""
    for entry in ("`src/a.py`; `**`", "`src/a.py`;`**`", "`?*`", "`*?`", "`**?`", "`?**`", "`src/a.py`, `**/?*`"):
        set_paths(task, "CARD-001", entry)
        code, _out, err = cli(task, "card", "open", "CARD-001")
        assert code != 0 and _reason(err) == "card-paths-too-wide", entry
        assert _row(task, "CARD-001")["status"] == "proposed"
    set_paths(task, "CARD-001", "`src/a.py`; `lib/`")
    assert cli(task, "card", "open", "CARD-001")[0] == 0
    assert _row(task, "CARD-001")["paths"] == "src/a.py; lib"
    records.append(task / "mkway" / "state", "s1", "take", "CARD-001")
    assert _edit(task, "lib/x.py") == "allow"
    assert _edit(task, "deep/any/file.py") == "file-not-in-card"


def test_a_take_never_overrides_a_holder(task):
    """H3 (close check): the records ignore a `take` of a card another session holds, and a `take` by a session that
    holds a card that is not closed; the CLI's `card take` of a held card refuses `card-not-yours`.
    Catches: a session that takes over another session's card with a spelling the shell gate does not read."""
    state = task / "mkway" / "state"
    records.append(state, "s1", "take", "CARD-001")
    records.append(state, "s2", "take", "CARD-001")
    assert records.holders(state) == {"CARD-001": "s1"}
    records.append(state, "s1", "take", "CARD-002")  # s1 still holds CARD-001, which is not closed
    assert records.holders(state, closed=set()) == {"CARD-001": "s1"}
    assert records.session_card(state, "s1") == "CARD-001"
    assert records.holders(state, closed={"CARD-001"}) == {"CARD-001": "s1", "CARD-002": "s1"}
    code, out, err = cli(task, "card", "take", "CARD-001", session=True)
    assert code != 0 and _reason(err) == "card-not-yours" and "mkway-ok" not in out


def test_a_session_pauses_only_its_own_card(task):
    """M2 (close check): a session's `card set <id> waiting` passes the lock gate only for the card it holds; on a
    card another session holds, or no one holds, it is `card-not-yours`. Catches: a session that pauses another
    session's card, which its holder then cannot reopen."""
    state = task / "mkway" / "state"
    assert cli(task, "card", "open", "CARD-001")[0] == 0
    records.append(state, "s1", "take", "CARD-001")
    assert _shell(task, f"{CLI} card set CARD-001 waiting", session="s2") == "card-not-yours"
    assert _shell(task, f"{CLI} card set CARD-002 waiting", session="s2") == "card-not-yours"
    assert _shell(task, f"{CLI} card set CARD-001 waiting", session="s1") == "allow"


def test_a_session_release_of_another_sessions_card_changes_nothing(task):
    """M3 (close check): a `release` row a session writes for a card another session holds leaves the holder in
    place; the holder's own release frees it. Catches: a holder rule that drops a card on anyone's release."""
    state = task / "mkway" / "state"
    records.append(state, "s1", "take", "CARD-001")
    records.append(state, "s2", "release", "CARD-001")
    assert records.holders(state) == {"CARD-001": "s1"}
    records.append(state, "s1", "release", "CARD-001")
    assert records.holders(state) == {}


def test_the_owners_release_of_a_held_card_needs_force(task):
    """L1 (close check; E22 as written): the owner's plain `card release <id>` of a card a session holds refuses and
    names `--force`; `--force` frees it. Catches: a `--force` flag that is parsed and never read."""
    state = task / "mkway" / "state"
    records.append(state, "s1", "take", "CARD-001")
    code, _out, err = cli(task, "card", "release", "CARD-001")
    assert code != 0 and _reason(err) == "card-not-yours" and "--force" in err
    assert records.holders(state) == {"CARD-001": "s1"}
    assert cli(task, "card", "release", "CARD-001", "--force")[0] == 0
    assert records.holders(state) == {}


def test_light_mode_lets_a_session_make_the_owners_moves(task):
    """L2 (close check; the order's light mode): with `cards.owner_moves: []` a session may lift the owner's pause
    (`waiting-owner` -> `open`) like the owner. Catches: a light mode that still keeps owner-only chain moves."""
    assert cli(task, "card", "open", "CARD-001")[0] == 0
    assert cli(task, "card", "set", "CARD-001", "waiting")[0] == 0
    assert _row(task, "CARD-001")["status"] == "waiting-owner"
    assert cli(task, "card", "set", "CARD-001", "open", session=True)[0] != 0  # the default mode: refused
    _light(task)
    assert cli(task, "card", "set", "CARD-001", "open", session=True)[0] == 0
    assert _row(task, "CARD-001")["status"] == "open"


def test_close_rule_resolves_dot_dot(task):
    """L3 (close check): a Test cell path is resolved before the `test_roots` check, so `tests/../src/fake.py` is
    outside the test roots. Catches: a close whose test sits outside the test folders."""
    (task / "src").mkdir()
    (task / "src" / "fake.py").write_text("def test_x():\n    pass\n", encoding="utf-8")
    assert cli(task, "card", "open", "CARD-001")[0] == 0
    set_tests(task, "CARD-001", ["tests/../src/fake.py::test_x"])
    code, _out, err = cli(task, "card", "close", "CARD-001")
    assert code != 0 and _reason(err) == "close-row-without-test"


def test_only_card_files_are_exempt(task):
    """L4 (close check; spec S3): the subtask gate exempts `<bundle.root>/cards/*/CARD.md` (and the profile's exempt
    paths), not the whole cards folder. Catches: a session that writes any file under `cards/` with no card."""
    assert _edit(task, "mkway/cards/CARD-001-first/CARD.md") == "allow"
    assert _edit(task, "mkway/cards/tool.py") == "no-open-card"
    assert _edit(task, "mkway/cards/CARD-001-first/notes.py") == "no-open-card"


def test_gate_switch_replaces_the_profile_whole(task, monkeypatch):
    """L5 (close check): `gate off|on` writes the profile to a temp file, then replaces it; a failed replace leaves
    the profile as it was and fails. Catches: a switch that leaves a half-written tracked profile."""
    before = (task / "mkway" / "profile.json").read_bytes()

    def boom(*_a, **_k):
        raise OSError("planted replace failure")
    monkeypatch.setattr(engine_cli.os, "replace", boom)
    code, _out, _err = cli(task, "gate", "off", "lock")
    assert code != 0
    assert (task / "mkway" / "profile.json").read_bytes() == before


def test_change_line_pins_the_record_kind_to_the_status(task):
    """L6 (close check; E29): a status change counts a record only when its kind gives that status (`open` -> open,
    `close` -> closed, `set <id> <status>` -> that status); another record of the same card is `(no record)`.
    Catches: a change line that takes any record of the card as the reason. Changed by MW-003 batch 3 (M1): the
    baseline is the owner's `card resync`, so the forge writes the register and its seal together."""
    from test_mw003_batch3 import forge_status
    root = task
    assert cli(root, "card", "open", "CARD-001")[0] == 0
    render = lambda: startline.render(root, root / "mkway" / "profile.json", _profile(root), [], [],  # noqa: E731
                                      {"CLAUDECODE": "1"}, session="s9")
    assert cli(root, "card", "resync")[0] == 0
    assert cli(root, "card", "set", "CARD-001", "waiting")[0] == 0  # a `set CARD-001 waiting-owner` record
    forge_status(root, "CARD-001", "waiting-owner", "closed")
    (line,) = [x for x in render().splitlines() if x.startswith("card changes since")]
    assert "CARD-001 open -> closed (no record)" in line
