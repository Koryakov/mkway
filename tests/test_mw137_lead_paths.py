"""Card MW-137: the lead role re-records the Paths of an open card it ordered (`mkway card paths <id> --add ... --remove ...`).
Each refusal names a way out that works, and a test runs it (lesson L12). Synthetic roots and session ids only."""
import json
import re

import pytest

from _engine import cli, gate_call
from _mw017 import inbox, lead_root, new_card, profile_of, register_lead, row_of, session_run, state
import cardtool
import gate_subtask
import leads
import records
import register

RECORD_FILE = "paths_changes.jsonl"


def _set_file_paths(root, card_id, value):
    """The Paths cell of the card file, written by whoever may write the file (the holder, the owner)."""
    (folder,) = [p for p in (root / "mkway" / "cards").iterdir() if p.name.startswith(card_id + "-")]
    path = folder / "CARD.md"
    text = re.sub(r"^\| \*\*Paths\*\* \|.*\|$", f"| **Paths** | {value} |", path.read_text(encoding="utf-8"), flags=re.M)
    path.write_text(text, encoding="utf-8")


def _edit_register_paths(root, card_id, value):
    """The owner's register edit: the Paths cell of one row, every other byte kept."""
    target = root / "mkway" / "cards" / "REGISTER.md"
    out = []
    with open(target, encoding="utf-8", newline="") as fh:
        lines = fh.readlines()
    for line in lines:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and cells[0] == card_id:
            end = line[len(line.rstrip("\r\n")):]
            cells[3] = value
            line = "| " + " | ".join(cells) + " |" + end
        out.append(line)
    with open(target, "w", encoding="utf-8", newline="") as fh:
        fh.writelines(out)


def _world(tmp_path, recorded="`src/a.py`", file=None, holder="s1", lead="lead-a", **over):
    """A lead and its card, with Paths `recorded` opened by the lead and held by `holder`; then the card file's Paths
    become `file` (the holder's edit), when given."""
    root = lead_root(tmp_path, **over)
    register_lead(root, lead)
    card = new_card(root, lead, "Mine")
    _set_file_paths(root, card, recorded)
    if holder:
        records.append(state(root), holder, "take", card)
    code, _out, err = session_run(root, lead, "card", "open", card)
    assert code == 0, err
    if file is not None:
        _set_file_paths(root, card, file)
    return root, card


def _paths(root, session, card, *flags):
    return session_run(root, session, "card", "paths", card, *flags)


def _recorded(root, card):
    return cardtool.paths_set(row_of(root, card)["paths"])


def _edit(root, path, session="s1"):
    return gate_call(gate_subtask.check, root, tool="Edit", tool_input={"file_path": path}, session=session)


def _rows(root):
    path = state(root) / RECORD_FILE
    if not path.is_file():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def _why(err):
    """The reason id of a refusal, from the hook's form `<id>: <text>` or the command's form `mkway: <id>: <text>`."""
    m = re.match(r"(?:mkway: )?([a-z-]+):", err)
    return m.group(1) if m else None


# ---- the move itself -----------------------------------------------------------------------------------------------------

def test_a_lead_widens_the_paths_and_the_later_edit_of_the_new_file_passes(tmp_path):
    """Catches: a re-record that does not let the builder edit the file the decision widened the card to. E1"""
    root, card = _world(tmp_path, file="`src/a.py`, `src/b.py`")
    assert _edit(root, "src/b.py").reason_id == "card-paths-changed"
    code, _out, err = _paths(root, "lead-a", card, "--add", "src/b.py")
    assert code == 0, err
    assert _recorded(root, card) == {"src/a.py", "src/b.py"}
    assert _edit(root, "src/b.py").kind == "allow"


def test_a_lead_narrows_the_paths_with_the_same_command(tmp_path):
    """Catches: narrowing that is not the same move, or that leaves the dropped file editable. E2"""
    root, card = _world(tmp_path, recorded="`src/a.py`, `src/b.py`", file="`src/a.py`")
    assert _edit(root, "src/a.py").reason_id == "card-paths-changed"
    code, _out, err = _paths(root, "lead-a", card, "--remove", "src/b.py")
    assert code == 0, err
    assert _recorded(root, card) == {"src/a.py"}
    assert (_edit(root, "src/a.py").kind, _edit(root, "src/b.py").reason_id) == ("allow", "file-not-in-card")


def test_the_holder_cannot_change_the_paths_of_its_own_card_also_when_it_is_a_lead(tmp_path):
    """Catches: a holder that widens its own card by also registering as a lead. E3"""
    root, card = _world(tmp_path, file="`src/a.py`, `src/b.py`")
    register_lead(root, "s1")
    code, _out, err = _paths(root, "s1", card, "--add", "src/b.py")
    assert (code, _why(err)) == (None, "paths-by-holder"), err
    assert _recorded(root, card) == {"src/a.py"}


def test_a_session_that_is_no_lead_is_refused(tmp_path):
    """Catches: any session re-recording a card's Paths. E4"""
    root, card = _world(tmp_path, file="`src/a.py`, `src/b.py`")
    code, _out, err = _paths(root, "builder-2", card, "--add", "src/b.py")
    assert (code, _why(err)) == (None, "paths-not-lead"), err
    assert _recorded(root, card) == {"src/a.py"}


def test_a_card_ordered_by_the_owner_stays_the_owners(tmp_path):
    """Catches: a lead re-recording the Paths of a card the owner ordered. E5"""
    root, _mine = _world(tmp_path)
    assert cli(root, "card", "new", "Owned")[0] == 0
    owned = "CARD-002"
    _set_file_paths(root, owned, "`src/o.py`")
    assert cli(root, "card", "open", owned)[0] == 0
    _set_file_paths(root, owned, "`src/o.py`, `src/p.py`")
    code, _out, err = _paths(root, "lead-a", owned, "--add", "src/p.py")
    assert (code, _why(err)) == (None, "paths-not-orderer"), err
    assert _recorded(root, owned) == {"src/o.py"}


def test_a_card_ordered_by_a_session_that_never_was_a_lead_is_refused(tmp_path):
    """Catches: the lead role reaching a card ordered by a plain session. E31"""
    root, card = _world(tmp_path, file="`src/a.py`, `src/b.py`")
    register.set_ordered(root, profile_of(root), card, "builder-9")
    code, _out, err = _paths(root, "lead-a", card, "--add", "src/b.py")
    assert (code, _why(err)) == (None, "paths-not-orderer"), err
    assert _recorded(root, card) == {"src/a.py"}


def test_a_card_ordered_by_an_earlier_lead_session_is_refused_for_the_current_lead(tmp_path):
    """Catches: the lead role, not the orderer's own session, deciding who re-records (R356); the owner's give is the way out. E6"""
    root, card = _world(tmp_path, file="`src/a.py`, `src/b.py`")
    assert cli(root, "lead", "remove", "lead-a")[0] == 0
    assert not leads.is_lead(state(root), "lead-a")
    register_lead(root, "lead-b")
    code, _out, err = _paths(root, "lead-b", card, "--add", "src/b.py")
    assert (code, _why(err)) == (None, "paths-not-orderer"), err
    assert "give" in err and "owner" in err, err
    assert _recorded(root, card) == {"src/a.py"}
    assert cli(root, "give", card, "lead-b")[0] == 0  # the owner's give needs no accept
    code, _out, err = _paths(root, "lead-b", card, "--add", "src/b.py")
    assert code == 0, err
    assert _recorded(root, card) == {"src/a.py", "src/b.py"}


def test_the_way_out_of_paths_not_orderer_for_another_leads_card_is_the_hand_off(tmp_path):
    """Catches: a refusal for another lead's card that names no working way; the planned restart is give and lead accept. E36"""
    root, card = _world(tmp_path, file="`src/a.py`, `src/b.py`")
    register_lead(root, "lead-b")
    code, _out, err = _paths(root, "lead-b", card, "--add", "src/b.py")  # both are registered leads; lead-a ordered it
    assert (code, _why(err)) == (None, "paths-not-orderer"), err
    assert "give" in err and "lead accept" in err, err
    assert _recorded(root, card) == {"src/a.py"}
    code, _out, err = session_run(root, "lead-a", "give", card, "lead-b")
    assert code == 0, err
    assert _paths(root, "lead-b", card, "--add", "src/b.py")[0] is None  # offered, not yet accepted
    code, _out, err = session_run(root, "lead-b", "lead", "accept", card)
    assert code == 0, err
    assert row_of(root, card)["ordered"] == "lead-b"
    code, _out, err = _paths(root, "lead-b", card, "--add", "src/b.py")
    assert code == 0, err
    assert _recorded(root, card) == {"src/a.py", "src/b.py"}


@pytest.mark.parametrize("entry", [pytest.param(".", id="whole-repository"), pytest.param("tests", id="test-root")])
def test_a_too_wide_entry_is_refused_by_the_shared_check(tmp_path, entry):
    """Catches: a re-record that lets a lead name the whole repository or a test root, which the first open refuses. E7"""
    root, card = _world(tmp_path, file="`src/a.py`")
    code, _out, err = _paths(root, "lead-a", card, "--add", entry)
    assert (code, _why(err)) == (1, "card-paths-too-wide"), err
    assert _recorded(root, card) == {"src/a.py"}
    assert _rows(root) == []


def test_the_command_judges_the_paths_with_cardtool_recorded_paths_not_a_copy(tmp_path, monkeypatch):
    """Catches: a second copy of the Paths check that drifts from the one the first open runs. E32"""
    root, card = _world(tmp_path, file="`src/a.py`, `src/b.py`")
    seen, real = [], cardtool.recorded_paths

    def spy(root_, profile_, card_id):
        seen.append(card_id)
        return real(root_, profile_, card_id)

    monkeypatch.setattr(cardtool, "recorded_paths", spy)
    code, _out, err = cli(root, "card", "paths", card, "--add", "src/b.py")
    assert code == 0, err
    assert seen == [card]


def test_removing_every_entry_is_refused_because_an_empty_set_is_no_file_rule(tmp_path):
    """Catches: a narrowing that ends in an empty Paths, which would let every file through. E33"""
    root, card = _world(tmp_path, file="")
    code, _out, err = _paths(root, "lead-a", card, "--remove", "src/a.py")
    assert code == 1 and _why(err) == "card-paths-too-wide", err
    assert _recorded(root, card) == {"src/a.py"}


def test_a_call_that_names_no_entry_changes_nothing(tmp_path):
    """Catches: a re-record with nothing named that rewrites the register or writes a row. E35"""
    root, card = _world(tmp_path)
    code, _out, err = cli(root, "card", "paths", card)
    assert code != 0 and "--add" in err
    assert (_recorded(root, card), _rows(root)) == ({"src/a.py"}, [])


# ---- what the move leaves behind -----------------------------------------------------------------------------------------

def test_the_record_row_names_card_old_set_new_set_who_and_time(tmp_path):
    """Catches: a re-record that leaves no row, or a row that does not say what changed and who did it. E8"""
    root, card = _world(tmp_path, file="`src/a.py`, `src/b.py`")
    assert _paths(root, "lead-a", card, "--add", "src/b.py")[0] == 0
    (row,) = _rows(root)
    assert (row["card"], sorted(row["old"]), sorted(row["new"]), row["by"]) == (card, ["src/a.py"], ["src/a.py", "src/b.py"], "lead-a")
    assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", row["time"])


def test_the_holder_gets_one_notice_and_nobody_else_is_pinged(tmp_path):
    """Catches: a holder that is never told its card widened, or a ping to the owner or another session. E9"""
    root, card = _world(tmp_path, file="`src/a.py`, `src/b.py`")
    code, out, err = _paths(root, "lead-a", card, "--add", "src/b.py")
    assert code == 0, err
    (notice,) = inbox(root, "s1")
    assert (notice["kind"], notice["from"], notice["to"]) == ("notice", "lead-a", "s1")
    assert card in notice["body"] and "src/b.py" in notice["body"]
    assert len(leads.all_rows(state(root))) == 1
    assert f"mkway inbox {notice['id']}" in out


def test_with_no_holder_the_row_is_written_and_no_notice_is_sent(tmp_path):
    """Catches: a re-record of a card nobody holds that fails, or that writes a notice to nobody. E10"""
    root, card = _world(tmp_path, holder=None, file="`src/a.py`, `src/b.py`")
    code, _out, err = _paths(root, "lead-a", card, "--add", "src/b.py")
    assert code == 0, err
    assert (len(_rows(root)), leads.all_rows(state(root))) == (1, [])


def test_the_owner_view_shows_a_line_for_a_re_recorded_card(tmp_path):
    """Catches: a re-record the owner cannot see without reading the record file. E11"""
    root, card = _world(tmp_path, file="`src/a.py`, `src/b.py`")
    assert _paths(root, "lead-a", card, "--add", "src/b.py")[0] == 0
    code, out, err = cli(root, "board")
    assert code == 0, err
    (line,) = [x.strip() for x in out.splitlines() if x.strip().startswith(f"paths of {card} re-recorded")]
    assert line.startswith(f"paths of {card} re-recorded 1 time") and "src/b.py" in line and "lead-a" in line


def test_the_scorecard_counts_the_re_records_of_each_card(tmp_path):
    """Catches: a scorecard that does not count how often a card's Paths were re-recorded. E12"""
    root, card = _world(tmp_path, file="`src/a.py`, `src/b.py`")
    assert _paths(root, "lead-a", card, "--add", "src/b.py")[0] == 0
    _set_file_paths(root, card, "`src/a.py`")
    assert _paths(root, "lead-a", card, "--remove", "src/b.py")[0] == 0
    code, out, err = cli(root, "scorecard")
    assert code == 0, err
    assert f"paths re-recorded {card}: 2" in out.splitlines()


# ---- the hole (R353 h): the holder writes the card file ------------------------------------------------------------------

def test_the_holder_adds_an_entry_to_the_file_and_the_lead_names_another_refused_with_the_difference(tmp_path):
    """Catches: a re-record taken from the card file that carries the holder's own addition in. E13"""
    root, card = _world(tmp_path, file="`src/a.py`, `src/b.py`, `src/c.py`")
    code, _out, err = _paths(root, "lead-a", card, "--add", "src/b.py")
    assert (code, _why(err)) == (1, "paths-file-differs"), err
    assert "src/c.py" in err
    assert (_recorded(root, card), _rows(root), inbox(root, "s1")) == ({"src/a.py"}, [], [])


def test_the_call_before_the_holder_edited_the_file_is_refused_naming_the_missing_entry(tmp_path):
    """Catches: a re-record whose intent is taken from the call alone, with the file still at the old set. E14"""
    root, card = _world(tmp_path)
    code, _out, err = _paths(root, "lead-a", card, "--add", "src/b.py")
    assert _why(err) == "paths-file-differs" and "src/b.py" in err, err
    assert (_recorded(root, card), _rows(root)) == ({"src/a.py"}, [])


# ---- the states (R353 k) -------------------------------------------------------------------------------------------------

def test_the_holders_own_waiting_is_allowed(tmp_path):
    """Catches: a re-record refused while the builder has paused its own card. E15"""
    root, card = _world(tmp_path, file="`src/a.py`, `src/b.py`")
    assert session_run(root, "s1", "card", "set", card, "waiting")[0] == 0
    assert row_of(root, card)["status"] == "waiting"
    code, _out, err = _paths(root, "lead-a", card, "--add", "src/b.py")
    assert code == 0, err
    assert _recorded(root, card) == {"src/a.py", "src/b.py"}


def test_the_pause_the_owner_set_is_refused(tmp_path):
    """Catches: a lead that re-records a card the owner paused. E16"""
    root, card = _world(tmp_path, file="`src/a.py`, `src/b.py`")
    assert cli(root, "card", "set", card, "waiting")[0] == 0
    assert row_of(root, card)["status"] == "waiting-owner"
    code, _out, err = _paths(root, "lead-a", card, "--add", "src/b.py")
    assert (code, _why(err)) == (None, "paths-card-state"), err
    assert _recorded(root, card) == {"src/a.py"}


def test_under_the_owner_only_approver_a_lead_is_refused_and_the_owner_runs_it(tmp_path):
    """Catches: a lead that re-records Paths in a root whose profile gives leads no card authority. E17"""
    root = lead_root(tmp_path, cards={})
    register_lead(root, "lead-a")
    card = new_card(root, "lead-a", "Mine")
    _set_file_paths(root, card, "`src/a.py`")
    assert cli(root, "card", "open", card)[0] == 0
    _set_file_paths(root, card, "`src/a.py`, `src/b.py`")
    code, _out, err = _paths(root, "lead-a", card, "--add", "src/b.py")
    assert (code, _why(err)) == (None, "owner-only-command"), err
    assert _recorded(root, card) == {"src/a.py"}
    assert cli(root, "card", "paths", card, "--add", "src/b.py")[0] == 0
    assert _recorded(root, card) == {"src/a.py", "src/b.py"}


# ---- the ways out, each run (R353 j, lesson L12) --------------------------------------------------------------------------

def test_the_way_out_of_paths_no_permit_is_the_plain_call_through_the_hook(tmp_path):
    """Catches: a call that claims a session id with no one-use permit being believed, or a refusal with no working way. E18"""
    root, card = _world(tmp_path, file="`src/a.py`, `src/b.py`")
    code, _out, err = cli(root, "card", "paths", card, "--add", "src/b.py", session=True)
    assert (code, _why(err)) == (1, "paths-no-permit"), err
    assert "plain form" in err and "owner" in err
    assert _recorded(root, card) == {"src/a.py"}
    code, _out, err = _paths(root, "lead-a", card, "--add", "src/b.py")
    assert code == 0, err
    assert _recorded(root, card) == {"src/a.py", "src/b.py"}


def test_the_card_tool_judges_again_with_the_session_the_permit_names(tmp_path):
    """Catches: a card tool that trusts the hook's pass, so a permit left for a session that is no lead re-records. E34"""
    root, card = _world(tmp_path, file="`src/a.py`, `src/b.py`")
    assert cardtool.issue_close_permit(state(root), card, "builder-2", kind="paths")
    code, _out, err = cli(root, "card", "paths", card, "--add", "src/b.py", session=True)
    assert (code, _why(err)) == (1, "paths-not-lead"), err
    assert _recorded(root, card) == {"src/a.py"}


def test_the_way_out_of_paths_not_lead_is_the_owner_terminal(tmp_path):
    """Catches: a refusal of a session that is no lead whose named way does not work. E19"""
    root, card = _world(tmp_path, file="`src/a.py`, `src/b.py`")
    code, _out, err = _paths(root, "builder-2", card, "--add", "src/b.py")
    assert _why(err) == "paths-not-lead" and "owner runs it in their own terminal" in err, err
    code, _out, err = cli(root, "card", "paths", card, "--add", "src/b.py")
    assert code == 0, err
    assert _recorded(root, card) == {"src/a.py", "src/b.py"}


def test_the_way_out_of_paths_not_orderer_is_the_register_edit_and_card_resync(tmp_path):
    """Catches: a refusal for an owner-ordered card that names a re-open, which records nothing. E20"""
    root, _mine = _world(tmp_path)
    assert cli(root, "card", "new", "Owned")[0] == 0
    owned = "CARD-002"
    _set_file_paths(root, owned, "`src/o.py`")
    assert cli(root, "card", "open", owned)[0] == 0
    code, _out, err = _paths(root, "lead-a", owned, "--add", "src/p.py")
    assert _why(err) == "paths-not-orderer"
    assert "register" in err and "card resync" in err and "card open" not in err, err
    _edit_register_paths(root, owned, "src/o.py; src/p.py")
    code, _out, err = cli(root, "card", "resync")
    assert code == 0, err
    assert _recorded(root, owned) == {"src/o.py", "src/p.py"}
    _set_file_paths(root, owned, "`src/o.py`, `src/p.py`")
    assert _edit(root, "src/p.py", "s1").reason_id != "card-paths-changed"


def test_the_way_out_of_paths_by_holder_is_the_orderer_call(tmp_path):
    """Catches: a holder's refusal that names no one who can do it. E21"""
    root, card = _world(tmp_path, file="`src/a.py`, `src/b.py`")
    register_lead(root, "s1")
    code, _out, err = _paths(root, "s1", card, "--add", "src/b.py")
    assert _why(err) == "paths-by-holder" and "lead-a" in err, err
    code, _out, err = _paths(root, "lead-a", card, "--add", "src/b.py")
    assert code == 0, err
    assert _recorded(root, card) == {"src/a.py", "src/b.py"}


def _proposed(tmp_path):
    root = lead_root(tmp_path)
    register_lead(root, "lead-a")
    card = new_card(root, "lead-a", "Mine")
    _set_file_paths(root, card, "`src/a.py`, `src/b.py`")
    return root, card


def _closed(tmp_path):
    root, card = _world(tmp_path, file="`src/a.py`, `src/b.py`")
    register.set_status(root, profile_of(root), card, "closed")
    return root, card


def _owner_paused(tmp_path):
    root, card = _world(tmp_path, file="`src/a.py`, `src/b.py`")
    assert cli(root, "card", "set", card, "waiting")[0] == 0
    return root, card


@pytest.mark.parametrize("make, way", [
    pytest.param(_proposed, ("lead-a", "open"), id="proposed"),
    pytest.param(_closed, (None, "open"), id="closed"),
    pytest.param(_owner_paused, (None, "open"), id="owner-pause"),
])
def test_the_way_out_of_paths_card_state(tmp_path, make, way):
    """Catches: a card in a state a re-record does not fit, refused with a way that does not work. E22"""
    root, card = make(tmp_path)
    code, _out, err = _paths(root, "lead-a", card, "--add", "src/b.py")
    assert _why(err) == "paths-card-state" and f"card open {card}" in err, err
    session, move = way
    if session:
        code, _out, err = session_run(root, session, "card", move, card)
    else:
        code, _out, err = cli(root, "card", move, card)
    assert code == 0, err
    assert row_of(root, card)["status"] == "open"
    if _recorded(root, card) != {"src/a.py", "src/b.py"}:  # a closed or paused card keeps its old set: the lead now re-records
        code, _out, err = _paths(root, "lead-a", card, "--add", "src/b.py")
        assert code == 0, err
    assert _recorded(root, card) == {"src/a.py", "src/b.py"}


def test_the_way_out_of_paths_file_differs_is_the_file_made_to_match(tmp_path):
    """Catches: a difference refusal that does not say what to change, or a repeat that still fails. E23"""
    root, card = _world(tmp_path, file="`src/a.py`, `src/b.py`, `src/c.py`")
    code, _out, err = _paths(root, "lead-a", card, "--add", "src/b.py")
    assert _why(err) == "paths-file-differs" and "src/c.py" in err and "repeat" in err, err
    _set_file_paths(root, card, "`src/a.py`, `src/b.py`")
    code, _out, err = _paths(root, "lead-a", card, "--add", "src/b.py")
    assert code == 0, err
    assert _recorded(root, card) == {"src/a.py", "src/b.py"}


def test_the_way_out_of_paths_record_failed_is_a_writable_state_folder(tmp_path):
    """Catches: a re-record that goes ahead when its row cannot be written, or a refusal that names no way. E24"""
    root, card = _world(tmp_path, file="`src/a.py`, `src/b.py`")
    blocker = state(root) / RECORD_FILE
    blocker.mkdir()
    code, _out, err = _paths(root, "lead-a", card, "--add", "src/b.py")
    assert _why(err) == "paths-record-failed" and "writable" in err, err
    assert _recorded(root, card) == {"src/a.py"}
    blocker.rmdir()
    code, _out, err = _paths(root, "lead-a", card, "--add", "src/b.py")
    assert code == 0, err
    assert _recorded(root, card) == {"src/a.py", "src/b.py"}


def test_the_way_out_of_card_paths_changed_names_the_lead_re_record_and_it_runs(tmp_path):
    """Catches: a card-paths-changed text that omits the lead's re-record, or names a command that does not work. E25"""
    root, card = _world(tmp_path, file="`src/a.py`, `src/b.py`")
    message = _edit(root, "src/a.py").message
    for kept in ("restore them to the recorded set", "new card", "lead that orders it opens it"):
        assert kept in message, message  # the wording of card MW-136 stays
    found = re.search(r"`python mkway/engine/mkway\.py (card paths (\S+) --add <entry>)`", message)
    assert found and found.group(2) == card, message
    code, _out, err = session_run(root, "lead-a", *found.group(1).replace("<entry>", "src/b.py").split())
    assert code == 0, err
    assert _edit(root, "src/a.py").kind == "allow"


def test_the_way_out_of_file_not_in_card_of_the_edit_gate_is_the_leads_card_paths_and_the_same_edit_passes(tmp_path):
    """Catches: an edit-gate refusal that names a re-open, or a named route that does not let the same edit through. E39"""
    root, card = _world(tmp_path)
    refused = _edit(root, "src/b.py")
    assert refused.reason_id == "file-not-in-card" and "ask the owner to `card open" not in refused.message, refused.message
    found = re.search(r"`python mkway/engine/mkway\.py (card paths (\S+) --add <entry>)`", refused.message)
    assert found and found.group(2) == card, refused.message
    _set_file_paths(root, card, "`src/a.py`, `src/b.py`")  # the holder names the file in the card file first
    code, _out, err = session_run(root, "lead-a", *found.group(1).replace("<entry>", "src/b.py").split())
    assert code == 0, err
    assert _edit(root, "src/b.py").kind == "allow"
