"""Card MW-107 (rulings R270c, R270c-D1): a write outside the session's root is refused for every session, through the REAL
hook command (stdin JSON in, exit code and permissionDecision out), with the lead gate on. The fake home is the one the hook
driver sets (`<base>/home`); the notes folder is a temporary folder outside the test repository. Synthetic names only."""
import pytest

from _hook_driver import decision, install_project

pytestmark = pytest.mark.engine_repo

CLI = "python mkway/engine/mkway.py"
LEAD, OTHER = "L1", "n1"


@pytest.fixture(scope="module")
def proj(tmp_path_factory):
    p = install_project(tmp_path_factory.mktemp("owner"))
    for session in (LEAD, OTHER):
        decision(p.fire("SessionStart", session))
    p.session_shell(LEAD, f"{CLI} lead register")
    return p


def write_decision(p, session, path):
    return decision(p.fire("PreToolUse", session, "Write", {"file_path": str(path), "content": "x"}))


def shell_decision(p, session, command):
    return decision(p.fire("PreToolUse", session, "Bash", {"command": command}))


def test_the_real_hook_refuses_a_session_edit_outside_the_root(proj):
    """Catches: a session that is no lead writes a 12-byte file into another checkout outside the root and the real hook lets it through."""
    got = write_decision(proj, OTHER, proj.base / "another-checkout" / "conftest.py")
    assert (got.kind, got.reason_id, got.gate) == ("deny", "write-outside-root", "outside.edit")  # R274e: the session check is its own gate


def test_the_real_hook_refuses_a_session_shell_write_outside_the_root(proj):
    """Catches: a session that is no lead redirects text into a file outside the root and the real hook lets it through."""
    got = shell_decision(proj, OTHER, f"echo xxxxxxxxxxxx > {(proj.base / 'another-checkout' / 'conftest.py').as_posix()}")
    assert (got.kind, got.reason_id, got.gate) == ("deny", "write-outside-root", "outside.shell")  # R274e


def test_the_real_hook_allows_a_session_write_to_the_harness_memory_folder(proj):
    """Checks: the nearest allow, a session's write to its memory folder under the home is not refused by the owner table."""
    got = write_decision(proj, OTHER, proj.base / "home" / ".claude" / "projects" / "p" / "memory" / "m.md")
    assert got.kind == "allow"


def test_the_real_hook_gives_a_lead_the_common_reason(proj):
    """Catches: a registered lead's write outside the root that keeps a reason of its own (R274, R274-D1: one reason, one text); the lead gate runs first."""
    got = write_decision(proj, LEAD, proj.base / "another-checkout" / "conftest.py")
    assert (got.kind, got.reason_id, got.gate) == ("deny", "write-outside-root", "lead.edit")
