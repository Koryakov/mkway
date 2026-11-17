"""Card MW-107 (rulings R274d and R274-D2 item 6), through the REAL installed hook command: the order of the two answers at a
write outside the root (R274e: the lock check runs first; when it refuses that is the answer, when it allows the outside check
runs). A session is answered by the lock at the upgrade folder and by the outside gate everywhere else outside; a lead is
answered by its own gate first, as before MW-103 (the lead gates stand before the lock in the manifest). The environment is the hermetic set of the MW-105 replay (the folder that
holds `mkway` is `<base>/cfg`; no `MKWAY_UPGRADE_DIR`); the real folders are never read. Synthetic names only."""
import pytest

from _hook_driver import decision, install_project

pytestmark = pytest.mark.engine_repo

CLI = "python mkway/engine/mkway.py"
HERMETIC = {"APPDATA": "cfg", "XDG_CONFIG_HOME": "cfg", "TEMP": "tmp", "TMP": "tmp", "TMPDIR": "tmp"}
SESSION, LEAD = "s1", "L1"


@pytest.fixture(scope="module")
def proj(tmp_path_factory):
    project = install_project(tmp_path_factory.mktemp("lock-order"))
    base = project.base
    (base / "gitconfig").write_text("", encoding="utf-8")
    for folder in set(HERMETIC.values()):
        (base / folder).mkdir(exist_ok=True)
    original = project.env

    def hermetic_env(*, session):
        env = original(session=session)
        env.pop("MKWAY_UPGRADE_DIR", None)
        env.update({name: str(base / folder) for name, folder in HERMETIC.items()})
        env.update(GIT_CONFIG_GLOBAL=str(base / "gitconfig"), GIT_CONFIG_NOSYSTEM="1")
        return env

    project.env = hermetic_env
    for session in (SESSION, LEAD):
        decision(project.fire("SessionStart", session))
    project.session_shell(LEAD, f"{CLI} lead register")
    return project


def fired(proj, session, tool, tool_input):
    return decision(proj.fire("PreToolUse", session, tool, tool_input))


def upgrade_file(proj) -> str:
    return (proj.base / "cfg" / "mkway" / "upgrade" / "green.jsonl").as_posix()


def beside_file(proj) -> str:
    return (proj.base / "cfg" / "mkway" / "x").as_posix()


@pytest.mark.parametrize("session, reason, gate", [
    pytest.param(SESSION, "lock-closed-shell", "lock.shell", id="session"),
    pytest.param(LEAD, "write-outside-root", "lead.shell", id="lead"),  # R274e: the lead gate keeps its place before the lock, as before MW-103
])
def test_a_shell_append_into_the_upgrade_folder_is_the_lock_gates_not_the_outside_rule(proj, session, reason, gate):
    """Catches: R274e, E1, a shell write at the lock target that the outside check answers first for a session (the lock answers first); a lead is refused by its own gate as before, never weaker."""
    got = fired(proj, session, "Bash", {"command": f"echo x >> {upgrade_file(proj)}"})
    assert (got.kind, got.reason_id, got.gate) == ("deny", reason, gate)


@pytest.mark.parametrize("session, reason, gate", [
    pytest.param(SESSION, "lock-closed-edit", "lock.edit", id="session"),
    pytest.param(LEAD, "write-outside-root", "lead.edit", id="lead"),
])
def test_an_edit_into_the_upgrade_folder_is_the_lock_gates_not_the_outside_rule(proj, session, reason, gate):
    """Catches: R274e, E2, an edit-tool write at the lock target that the outside check answers first for a session; a lead is refused by its own gate as before."""
    got = fired(proj, session, "Write", {"file_path": upgrade_file(proj), "content": "x"})
    assert (got.kind, got.reason_id, got.gate) == ("deny", reason, gate)


@pytest.mark.parametrize("session, gate", [
    pytest.param(SESSION, "outside.edit", id="session"),
    pytest.param(LEAD, "lead.edit", id="lead"),
])
def test_a_write_beside_the_upgrade_folder_is_the_outside_rule_not_the_lock(proj, session, gate):
    """Catches: R274e, E3, the other half of the order: a path outside the root that is no lock target is write-outside-root from the outside check, never lock-closed; the lock allowed it first."""
    got = fired(proj, session, "Write", {"file_path": beside_file(proj), "content": "x"})
    assert (got.kind, got.reason_id, got.gate) == ("deny", "write-outside-root", gate)


@pytest.mark.parametrize("tool, payload, gate", [
    pytest.param("Write", lambda p: {"file_path": beside_file(p), "content": "x"}, "outside.edit", id="edit"),
    pytest.param("Bash", lambda p: {"command": f"echo x > {beside_file(p)}"}, "outside.shell", id="shell"),
])
def test_the_outside_check_still_runs_after_the_lock_allows(proj, tool, payload, gate):
    """Catches: R274e, an outside write that passes because the lock check allowed it (the lock is open or the path is no target): the lock answers first, and when it allows, the outside check runs and refuses."""
    got = fired(proj, SESSION, tool, payload(proj))
    assert (got.kind, got.reason_id, got.gate) == ("deny", "write-outside-root", gate)


# ---- one base for a relative edit path (round-2 reader item 1) ---------------------------------------------------------

def fired_from(proj, folder, session, path):
    return decision(proj.fire("PreToolUse", session, "Write", {"file_path": path, "content": "x"},
                              cwd=str(proj.root / folder)))


@pytest.mark.parametrize("folder, path", [
    pytest.param("mkway/engine", "x.txt", id="a-plain-name-from-a-locked-folder"),
    pytest.param("task", "../mkway/engine/x.txt", id="a-parent-path-into-a-locked-folder"),
])
def test_a_relative_write_from_a_lock_target_is_refused_by_the_lock_gate(proj, folder, path):
    """Catches: round-2 reader item 1, the cwd base split: the lock gate read a relative edit path from the root while the other gates read it from the cwd, so a session started in a locked folder wrote `x.txt` into it; every gate reads the one base."""
    got = fired_from(proj, folder, SESSION, path)
    assert (got.kind, got.reason_id, got.gate) == ("deny", "lock-closed-edit", "lock.edit")


def test_a_relative_name_from_the_root_is_no_lock_target(proj):
    """Checks: the near miss of the row above: the same name with the cwd at the root is not a lock target, the lock gate answers nothing (the card rules are the subtask gate's)."""
    got = fired_from(proj, "", SESSION, "x.txt")
    assert got.gate != "lock.edit"
