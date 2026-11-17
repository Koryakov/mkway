"""Card MW-105 (rulings R257h, R260, R260a, R260b, R260c): the pure part of the lock gate's guard of the upgrade folder, which
lies outside the repository. `core_lock.decide` reads one more fact for each path, its class (`upgrade`, `unc` or none), and
refuses on it; the pure text rules in `helpers` decide the class from the raw path text. One test id is one rule; each
refusal has a deny case and the nearest allow case. Expected values are literals or parametrize values, never the code's
own answer. No disk, no git, no clock. Synthetic folder names only; the Windows forms are built by `win` from a `|` mark."""
import pytest

import _engine  # noqa: F401  (puts the engine folder on the import path)
import core_lock as core
import helpers
from _no_io import no_io

FOLDER = "C:/cfg/mkway/upgrade/"
RAW = "C:/cfg/mkway/upgrade/green.jsonl"
GLOB = "C:/cfg/mkway/upgrade/gre*"
REPO_ENGINE = core.Target("engine", ("mkway/engine/",), True)
REPO_STATE = core.Target("state", ("mkway/state/",), True)
UPGRADE = core.Target("upgrade", (FOLDER,), True)
TARGETS = (REPO_ENGINE, REPO_STATE, UPGRADE)
ONLY_ABSOLUTE = (UPGRADE,)
QUIET = {("engine_call",): None, ("calls",): (), ("parse_ok",): True, ("names_commit",): False, ("carrier",): None,
         ("form",): None, ("env",): None, ("cdpath",): False, ("expanded_text",): "", ("commits",): (),
         ("unknown_shape",): ""}
ENGINE_ONLY = "only the engine's own commands write it"


def win(text):
    """A Windows path text from the `|` mark, so no backslash is written by hand."""
    return text.replace("|", chr(92))


def edit(*rows, targets=TARGETS):
    """A Write whose paths are rows of (raw text, repo path, class)."""
    return core.Facts(tool_name="Write", targets=targets, session_id="s1", edit_rels=tuple(r[1] for r in rows),
                      edit_classes=tuple((r[0], r[2]) for r in rows), reads={})


def shell(paths, command="x", targets=TARGETS, tool="Bash"):
    """A shell command whose reader found `paths`, each a tuple of (text, repo path) or (text, repo path, class)."""
    return core.Facts(tool_name=tool, command=command, targets=targets, session_id="s1", reads={
        **QUIET, ("writes",): core.WriteFacts(None, tuple(paths))})


def run(f):
    with no_io():
        return core.decide(f)


@pytest.fixture(autouse=True, scope="module")
def _warm_imports():
    """The first call imports lazily; that stays out of the guard."""
    core.decide(core.Facts(tool_name="Write", targets=TARGETS, session_id="s1", edit_rels=("src/a.py",)))


# ==== the class decides first =====================================================================================================

def test_an_edit_path_of_class_upgrade_is_refused_naming_the_target():
    """Catches: E1, an edit path the shell classed as inside the upgrade folder that is let through for want of a repo path."""
    v = run(edit((RAW, None, "upgrade")))
    assert (v.kind, v.reason, "'upgrade'" in v.text, ENGINE_ONLY in v.text, RAW in v.text) == (
        "refuse", "lock-closed-edit", True, True, True)


def test_an_edit_path_with_no_class_is_allowed():
    """Checks: E2, an edit path with no class and no repo path (outside every guarded folder) is allowed."""
    assert run(edit((RAW, None, None))).kind == "allow"


def test_a_second_edit_path_of_class_upgrade_is_found():
    """Catches: E3, a second path key (`notebook_path` after `file_path`) whose class is not read."""
    v = run(edit(("src/a.py", "src/a.py", None), (RAW, None, "upgrade")))
    assert (v.kind, v.reason, RAW in v.text) == ("refuse", "lock-closed-edit", True)


def test_a_shell_path_of_class_upgrade_is_refused_naming_the_target():
    """Catches: E4, a shell write the shell classed as inside the upgrade folder that is let through."""
    v = run(shell([(RAW, None, "upgrade")]))
    assert (v.kind, v.reason, "'upgrade'" in v.text, ENGINE_ONLY in v.text) == ("refuse", "lock-closed-shell", True, True)


def test_a_shell_path_with_two_items_has_no_class_and_is_allowed():
    """Checks: E5, a shell path entry of two items (no class) is judged as before: outside the repo it is allowed."""
    assert run(shell([(RAW, None)])).kind == "allow"


def test_an_edit_path_of_class_unc_is_refused_with_the_network_text():
    """Catches: E6, a network path in an edit tool that is let through, or refused with a text that names a target."""
    path = win("||host|share|x")
    v = run(edit((path, None, "unc")))
    assert (v.kind, v.reason, "network path" in v.text, "cannot be checked" in v.text, "closed lock" in v.text,
            "'upgrade'" in v.text) == ("refuse", "lock-closed-edit", True, True, False, False)


def test_a_shell_path_of_class_unc_is_refused_with_the_network_text():
    """Catches: E7, a network path in a shell write that is let through, or refused with a text that names a target."""
    v = run(shell([("//host/share/x", None, "unc")]))
    assert (v.kind, v.reason, "network path" in v.text, "cannot be checked" in v.text, "closed lock" in v.text,
            "'upgrade'" in v.text) == ("refuse", "lock-closed-shell", True, True, False, False)


def test_the_unc_class_is_decided_before_the_variable_check():
    """Catches: E8, a network path that also holds a variable (`$h`) that is only logged, or named as the upgrade target."""
    v = run(shell([("//$h/share/x", None, "unc")]))
    assert (v.kind, v.reason, "network path" in v.text, "'upgrade'" in v.text) == ("refuse", "lock-closed-shell", True, False)


def test_the_upgrade_class_is_decided_before_the_glob_branch():
    """Catches: E9, a glob write into the upgrade folder that falls to the glob branch, which skips absolute entries."""
    v = run(shell([(GLOB, None, "upgrade")]))
    assert (v.kind, v.reason, "'upgrade'" in v.text) == ("refuse", "lock-closed-shell", True)


@pytest.mark.parametrize("ask", [
    pytest.param(lambda t: core.glob_target(t, "up*"), id="glob-up-star"),
    pytest.param(lambda t: core.glob_target(t, "A*"), id="glob-capital-a-star"),
    pytest.param(lambda t: core.glob_target(t, "C*"), id="glob-c-star-like-the-drive"),
    pytest.param(lambda t: core.closed_target(t, "upgrade/x"), id="a-repo-path-named-upgrade"),
    pytest.param(lambda t: core.held_target(t, ".", lambda rel, entry: None), id="the-root-holds-no-outside-folder"),
])
def test_the_relative_matchers_skip_an_absolute_entry(ask):
    """Checks: E10, the repo matchers give the verdict they give without the absolute entry (never weaker, literal_diff)."""
    assert ask(ONLY_ABSOLUTE) is None


@pytest.mark.parametrize("command, path", [
    pytest.param(win("Set-Content $env:APPDATA|mkway|upgrade|green.jsonl x"), "$env:APPDATA/mkway/upgrade/green.jsonl",
                 id="powershell-env-variable"),
    pytest.param(win("echo x >> %APPDATA%|mkway|upgrade|x"), "%APPDATA%mkwayupgradex", id="percent-variable-in-bash"),
    pytest.param(win("echo x > $A|mkway|upgrade|x"), "$A/mkway/upgrade/x", id="plain-variable-then-folder"),
])
def test_a_variable_path_naming_the_upgrade_folder_is_refused_by_literal_reach(command, path):
    """Checks: E11, an unreadable write that names the upgrade folder is refused by the existing literal-reach rule (R260a 1)."""
    v = run(shell([(path, None)], command=command))
    assert (v.kind, v.reason, "'upgrade'" in v.text, "write literal paths" in v.text) == (
        "refuse", "lock-closed-shell", True, True)


@pytest.mark.parametrize("command, path", [
    pytest.param(win("Set-Content $env:APPDATA|mkway|upgrade2|x y"), "$env:APPDATA/mkway/upgrade2/x", id="upgrade2"),
    pytest.param(win("Set-Content $x|green.jsonl y"), "$x/green.jsonl", id="variable-then-file-name"),
])
def test_a_variable_path_not_naming_the_upgrade_folder_is_only_logged(command, path):
    """Checks: E12, a variable path that does not name the folder stays a log row (the named gap of R260a 1)."""
    assert run(shell([(path, None)], command=command)).kind == "log"


# ==== the pure text rules =========================================================================================================

@pytest.mark.parametrize("text, unc", [
    pytest.param(win("||host|share|x"), True, id="two-backslashes-host"),
    pytest.param(win("||localhost|c$|x"), True, id="admin-share"),
    pytest.param("//host/share/x", True, id="two-slashes"),
    pytest.param("//localhost/c$/x", True, id="two-slashes-admin-share"),
    pytest.param(win("||?|UNC|h|s|x"), True, id="extended-unc"),
    pytest.param("//?/UNC/h/s/x", True, id="extended-unc-slashes"),
    pytest.param(win("||$h|share|x"), True, id="host-with-a-variable"),
    pytest.param(win("||?|Volume{1}|x"), True, id="extended-not-a-drive"),
    pytest.param(win("||?|C:|x"), False, id="extended-drive"),
    pytest.param(win("||.|C:|x"), False, id="device-drive"),
    pytest.param("//?/C:/x", False, id="extended-drive-slashes"),
    pytest.param("//./c:/x", False, id="device-drive-slashes"),
    pytest.param(win("C:|x"), False, id="drive-backslashes"),
    pytest.param("C:/x", False, id="drive-slashes"),
    pytest.param("/c/x", False, id="git-bash-form"),
    pytest.param("/x/y", False, id="one-leading-slash"),
    pytest.param("x/y", False, id="relative"),
    pytest.param("~/x", False, id="tilde"),
    pytest.param("", False, id="empty"),
])
def test_the_unc_class_is_read_from_the_raw_text(text, unc):
    """Catches: E13, a network path read as local (no check) or a local extended path read as a network path (a false refusal)."""
    assert helpers.is_unc(text) is unc


@pytest.mark.parametrize("text, stripped", [
    pytest.param(win("||?|C:|x"), win("C:|x"), id="extended-prefix"),
    pytest.param(win("||.|C:|x"), win("C:|x"), id="device-prefix"),
    pytest.param("//?/C:/x", "C:/x", id="extended-slashes"),
    pytest.param("//./c:/x", "c:/x", id="device-slashes"),
    pytest.param(win("||?|C:"), "C:", id="drive-only"),
    pytest.param(win("||?|UNC|h|s|x"), win("||?|UNC|h|s|x"), id="unc-stays"),
    pytest.param(win("||?|Volume{1}|x"), win("||?|Volume{1}|x"), id="not-a-drive-stays"),
    pytest.param(win("||host|s|x"), win("||host|s|x"), id="plain-unc-stays"),
    pytest.param(win("C:|x"), win("C:|x"), id="no-prefix"),
    pytest.param("x/y", "x/y", id="relative"),
])
def test_the_device_prefix_is_stripped_before_a_drive_letter(text, stripped):
    """Catches: E14, a `\\\\?\\` or `\\\\.\\` prefix left on (realpath keeps one of them), so the same folder is not met."""
    assert helpers.strip_device_prefix(text) == stripped


@pytest.mark.parametrize("path, folder", [
    pytest.param("C:/cfg/mkway/upgrade/gre*", "C:/cfg/mkway/upgrade", id="partial-name-in-the-folder"),
    pytest.param("C:/cfg/mkway/upgrade/*", "C:/cfg/mkway/upgrade", id="star-in-the-folder"),
    pytest.param("C:/cfg/mkway/up*", "C:/cfg/mkway", id="partial-name-in-the-parent"),
    pytest.param("C:/cfg/*", "C:/cfg", id="star-in-the-grandparent"),
    pytest.param("C:/*", "C:", id="star-at-the-drive-root"),
    pytest.param("C:/cfg/a?b", "C:/cfg", id="question-mark"),
    pytest.param("C:/cfg/[ab]", "C:/cfg", id="bracket"),
    pytest.param("/cfg/*", "/cfg", id="posix-star"),
    pytest.param("/*", "", id="posix-star-at-the-root"),
    pytest.param("C:/cfg/other/*", "C:/cfg/other", id="other-folder"),
])
def test_the_folder_of_a_glob_head_is_read(path, folder):
    """Catches: E15, a glob read by its whole text (never inside the folder) instead of the folder in front of its wildcard."""
    assert helpers.glob_head_folder(path) == folder


@pytest.mark.parametrize("path, cut", [
    pytest.param("C:/cfg/mkway/upgrade/green.jsonl:s", "C:/cfg/mkway/upgrade/green.jsonl", id="stream-on-a-file"),
    pytest.param("C:/cfg/mkway/upgrade:s", "C:/cfg/mkway/upgrade", id="stream-on-the-folder"),
    pytest.param("C:/cfg/x:s:$DATA", "C:/cfg/x", id="stream-with-a-type"),
    pytest.param(win("C:|cfg|x:s"), win("C:|cfg|x"), id="backslashes"),
    pytest.param("x:s", "x", id="relative"),
    pytest.param("~/x:s", "~/x", id="tilde"),
    pytest.param("C:x:s", "C:x", id="drive-relative"),
    pytest.param("C:/cfg/a:b/c", "C:/cfg/a:b/c", id="colon-in-a-middle-part-stays"),
    pytest.param("C:/cfg/x", "C:/cfg/x", id="no-stream"),
    pytest.param("C:/", "C:/", id="drive-root"),
    pytest.param("C:", "C:", id="drive-only"),
])
def test_a_stream_suffix_is_cut_from_the_last_component(path, cut):
    """Catches: E16, a `:stream` suffix that hides the real file name (or the folder's own name) from the compare."""
    assert helpers.strip_stream(path) == cut


@pytest.mark.parametrize("folder, path, caught", [
    pytest.param("c:/cfg/mkway/upgrade", "c:/cfg/mkway/upgrade", True, id="equal"),
    pytest.param("c:/cfg/mkway/upgrade", "c:/cfg/mkway/upgrade/", True, id="equal-with-a-trailing-slash"),
    pytest.param("c:/cfg/mkway/upgrade", "c:/cfg/mkway/upgrade/green.jsonl", True, id="a-file-below"),
    pytest.param("c:/cfg/mkway/upgrade", "c:/cfg/mkway/upgrade/a/b", True, id="deep-below"),
    pytest.param("c:/cfg/mkway/upgrade", "c:/cfg/mkway", True, id="the-parent"),
    pytest.param("c:/cfg/mkway/upgrade", "c:/cfg", True, id="the-grandparent"),
    pytest.param("c:/cfg/mkway/upgrade", "c:", True, id="the-drive-root"),
    pytest.param("/cfg/mkway/upgrade", "/", True, id="the-posix-root"),
    pytest.param("/cfg/mkway/upgrade", "/cfg", True, id="the-posix-ancestor"),
    pytest.param("c:/cfg/mkway/upgrade", "c:/cfg/mkway/upgrade2", False, id="sibling-with-the-same-prefix"),
    pytest.param("c:/cfg/mkway/upgrade", "c:/cfg/mkway/upgrade2/x", False, id="below-a-sibling"),
    pytest.param("c:/cfg/mkway/upgrade", "c:/cfg/mkway/x", False, id="a-file-beside-the-folder"),
    pytest.param("c:/cfg/mkway/upgrade", "c:/cfg/other", False, id="another-folder"),
    pytest.param("c:/cfg/mkway/upgrade", "c:/cfgx", False, id="a-bare-prefix-of-an-ancestor"),
    pytest.param("c:/cfg/mkway/upgrade", "d:/cfg/mkway/upgrade", False, id="another-drive"),
    pytest.param("c:/cfg/mkway/upgrade", "c:/cfg/mkway/upgra", False, id="a-bare-prefix-of-the-folder"),
    pytest.param("/cfg/mkway/upgrade", "/cfgx", False, id="a-posix-bare-prefix"),
])
def test_a_path_equal_below_or_above_the_folder_is_caught(folder, path, caught):
    """Catches: E17, a bare-prefix compare (`upgrade2` caught) or a compare that misses the folder's own parents."""
    assert helpers.touches_folder(folder, path) is caught
