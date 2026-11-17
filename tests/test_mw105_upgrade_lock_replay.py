"""Card MW-105 (R260 f, fix list T4), through the REAL installed hook command: the engine is installed into a scratch repository
(`install_project`), and each call runs the command lines of the generated `.claude/settings.json` through the shell, the way
`tests/_hook_driver.py::Project.fire` does it: the JSON of a real hook payload (an absolute path, the task folder as `cwd`) on
stdin, `CLAUDE_PROJECT_DIR` and `CLAUDECODE` in the environment as a session has them. The environment is the hermetic set of
the MW-104 tests (APPDATA, XDG_CONFIG_HOME, HOME, USERPROFILE, TEMP, TMP, TMPDIR and GIT_CONFIG_GLOBAL under the scratch folder;
no `MKWAY_UPGRADE_DIR`): the real folders are never read. The verdict is `hookSpecificOutput.permissionDecision` read as the hook
wrote it: `deny` exactly (the driver's `decision` maps `ask` to `deny` too, so it is not enough). Synthetic names only."""
import pytest

from _hook_driver import decision, install_project

pytestmark = pytest.mark.engine_repo

HERMETIC = {"APPDATA": "cfg", "XDG_CONFIG_HOME": "cfg", "TEMP": "tmp", "TMP": "tmp", "TMPDIR": "tmp"}


@pytest.fixture(scope="module")
def proj(tmp_path_factory):
    """The installed project, whose hook environment is the hermetic set (the folder that holds `mkway` is `<base>/cfg`)."""
    project = install_project(tmp_path_factory.mktemp("upgrade-replay"))
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
    decision(project.fire("SessionStart", "s1"))
    return project


def fired(proj, tool, tool_input):
    """(exit code, every permissionDecision the hooks wrote as they wrote it, the driver's decision) of one PreToolUse call."""
    result = proj.fire("PreToolUse", "s1", tool, tool_input)
    raw = [((run.json or {}).get("hookSpecificOutput") or {}).get("permissionDecision") for run in result.runs]
    return result.exit_code, [x for x in raw if x], decision(result)


def test_the_real_hook_refuses_a_write_into_the_upgrade_folder(proj):
    """Catches: E48, the installed hook command that lets a Write of the green record through: exit 0, permissionDecision `deny` exactly, `lock-closed-edit`, the upgrade target named."""
    path = proj.base / "cfg" / "mkway" / "upgrade" / "green.jsonl"
    code, raw, got = fired(proj, "Write", {"file_path": str(path), "content": "x"})
    assert (code, raw, got.reason_id, "'upgrade'" in got.text) == (0, ["deny"], "lock-closed-edit", True)


def test_the_real_hook_refuses_a_bash_append_into_the_upgrade_folder(proj):
    """Catches: E49, the installed hook command that lets a Bash append to the green record through: exit 0, permissionDecision `deny` exactly, `lock-closed-shell`, the upgrade target named."""
    command = f"echo x >> {(proj.base / 'cfg' / 'mkway' / 'upgrade' / 'green.jsonl').as_posix()}"
    code, raw, got = fired(proj, "Bash", {"command": command})
    assert (code, raw, got.reason_id, "'upgrade'" in got.text) == (0, ["deny"], "lock-closed-shell", True)


def test_the_real_hook_allows_a_write_next_to_the_upgrade_folder(proj):
    """Checks: E50, R274-D2 item 6 (the card names this node, so it keeps its name): a Write beside the folder, outside the root and no lock target, is write-outside-root through the installed hook, never lock-closed-shell."""
    code, raw, got = fired(proj, "Write", {"file_path": str(proj.base / "cfg" / "mkway" / "x"), "content": "x"})
    assert (code, raw, got.reason_id) == (0, ["deny"], "write-outside-root")
    assert got.gate == "outside.edit"  # R274-D2 (9), round-2 reader item 3: the outside gate answered, not a lock entry
