"""Card MW-103 (rulings R255, R255b): the lead gate refuses a registered lead's write outside the repository, through the REAL
hook command (stdin JSON in, exit code and permissionDecision out), with the lead gate on. The fake home is the one the
hook driver sets (`<base>/home`); the notes folder is a temporary folder of the shape of the real case, outside the test
repository. Synthetic names only."""
import pytest

from _hook_driver import decision, install_project

pytestmark = pytest.mark.engine_repo

CLI = "python mkway/engine/mkway.py"
LEAD, OTHER = "L1", "n1"


@pytest.fixture(scope="module")
def proj(tmp_path_factory):
    p = install_project(tmp_path_factory.mktemp("outside"))
    for session in (LEAD, OTHER):
        decision(p.fire("SessionStart", session))
    p.session_shell(LEAD, f"{CLI} lead register")
    return p


def write_decision(p, session, path):
    return decision(p.fire("PreToolUse", session, "Write", {"file_path": str(path), "content": "x"}))


def test_the_real_hook_refuses_a_lead_write_to_the_notes_folder(proj):
    """Catches: E25, a lead's Write to a folder outside the repository that the real hook lets through."""
    got = write_decision(proj, LEAD, proj.base / "project_x" / "analysis" / "notes" / "a.md")
    assert (got.kind, got.reason_id, got.gate) == ("deny", "write-outside-root", "lead.edit")  # R274-D1: the common reason


def test_the_real_hook_allows_a_lead_write_to_its_memory_folder(proj):
    """Checks: E26, the nearest allow of E25, a lead's Write to its memory folder under the home."""
    got = write_decision(proj, LEAD, proj.base / "home" / ".claude" / "projects" / "p" / "memory" / "m.md")
    assert got.kind == "allow"


def test_the_real_hook_allows_a_non_lead_write_outside(proj):
    """Catches: E27 (R270c-D1), a session that is no lead writes to the notes folder outside the root and the hook lets it through."""
    got = write_decision(proj, OTHER, proj.base / "project_x" / "analysis" / "notes" / "a.md")
    assert (got.kind, got.reason_id) == ("deny", "write-outside-root")


@pytest.mark.parametrize("name", ["note_one", "note_two", "note_three", "note_four"])
def test_replay_a_lead_with_no_card_writing_note_files_outside_is_refused(proj, name):
    """Catches: E28, the real case: a registered lead holding no card wrote note files into a folder outside the repository and the gate let them pass."""
    got = write_decision(proj, LEAD, proj.base / "project_x" / "analysis" / "notes" / f"{name}.md")
    assert (got.kind, got.reason_id) == ("deny", "write-outside-root")  # R274-D1: the common reason
