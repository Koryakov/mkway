"""Card MW-105 (rulings R260, R260a, R260b, R260c): the Windows rules of the lock gate's guard of the upgrade folder: 8.3 short
names, the `\\\\?\\` and `\\\\.\\` prefixes, the Git Bash `/c/...` form, other casing, stream names and UNC paths. The platform
condition is the one the MW-103 shell tests use (`tests/shell/test_mw103_outside_facts.py:19`). The 8.3 rows have one capability
condition, `short_names_on` (R260c 2): rows run when this machine generates short names, are reported skipped with the reason
`8.3 names not generated on tmp` or `... on home` when it does not; no other skip, no xfail. Folders are under tmp_path; the one
real-home row reads the real home path from the process environment at import time (before any hermetic env), writes
nothing and creates nothing there. No test touches the network: a UNC path is decided on the raw text. Synthetic names only."""
import ctypes
import os
from pathlib import Path

import pytest

from _mw105 import ALLOW, CLASS_ONLY, by_class, by_tool, expected, make_world, seen, win

WINDOWS = pytest.mark.skipif(os.name != "nt", reason="Windows path rules")
pytestmark = WINDOWS
REAL_HOME = os.environ.get("USERPROFILE") or os.environ.get("HOME") or ""  # read before any hermetic environment is applied
MISSING = "mkway-test-folder-that-does-not-exist"
TOOLS = ["Write", "Bash"]


def short_of(path) -> str:
    """The 8.3 form of an existing path (every long part shortened), or "" when the call gives none."""
    buffer = ctypes.create_unicode_buffer(1024)
    ctypes.windll.kernel32.GetShortPathNameW(str(path), buffer, 1024)
    return buffer.value


def short_names_on(folder) -> bool:
    """The one capability helper (R260c 2): True when `folder`, an existing folder, has an 8.3 name unlike its own."""
    if os.name != "nt":
        return False
    short = short_of(folder)
    return bool(short) and short.lower() != str(folder).lower()


SHORT_ON_HOME = bool(REAL_HOME) and short_names_on(REAL_HOME)
HOME_ROWS = pytest.mark.skipif(not SHORT_ON_HOME, reason="8.3 names not generated on home")


def git_bash_form(path) -> str:
    """`/c/Users/...` for `C:\\Users\\...`."""
    text = Path(path).as_posix()
    return "/" + text[0].lower() + text[2:]


def admin_share_form(path) -> str:
    """`\\\\localhost\\c$\\Users\\...` for `C:\\Users\\...`."""
    text = str(path)
    return win("||localhost|") + text[0].lower() + "$" + text[2:]


@pytest.fixture
def world(tmp_path, monkeypatch):
    return make_world(tmp_path, monkeypatch)


@pytest.fixture(scope="module")
def tmp_short_names(tmp_path_factory):
    """The 8.3 capability of the folder the rows use (R260c 2, reader B 2 and 7): a long-named folder under the pytest base temp, the
    one `tmp_path` lives in, is asked for its short name; the rows are skipped with the reason when it has none. Nothing is made in
    the system temp folder."""
    if not short_names_on(tmp_path_factory.mktemp("a_long_folder_name_probe")):
        pytest.skip("8.3 names not generated on tmp")


def with_appdata(world, appdata):
    """The world's environment with APPDATA and XDG_CONFIG_HOME at `appdata`."""
    return dict(world.env, APPDATA=str(appdata), XDG_CONFIG_HOME=str(appdata))


# ==== 8.3 short names (R260 b: realpath resolves an existing short part on both sides) =============================================

@pytest.mark.parametrize("tool", TOOLS)
@pytest.mark.parametrize("appdata_short", [True, False], ids=["appdata-short-write-long", "appdata-long-write-short"])
def test_an_8_3_short_name_in_tmp_is_caught_both_ways(world, tmp_path, tmp_short_names, tool, appdata_short):
    """Catches: E38, the same folder named by its short and its long form that is met only when both sides use one form."""
    long_base = tmp_path / "a_long_folder_name"
    long_base.mkdir()
    short_base = short_of(long_base)
    assert short_base.lower() != str(long_base).lower()
    appdata, written = {True: (short_base, long_base), False: (long_base, short_base)}[appdata_short]
    target = Path(written) / "mkway" / "upgrade" / "green.jsonl"
    v = by_tool(world, tool, str(target), env=with_appdata(world, appdata))
    assert by_class(v) == expected(tool) + CLASS_ONLY


@HOME_ROWS
@pytest.mark.parametrize("tool", TOOLS)
@pytest.mark.parametrize("appdata_short", [True, False], ids=["appdata-short-write-long", "appdata-long-write-short"])
def test_an_8_3_short_name_of_the_real_home_is_caught_both_ways(world, tool, appdata_short):
    """Catches: E39, the real home named by its short and its long form that is met only when both sides use one form; nothing is created."""
    short_home = short_of(REAL_HOME)
    assert short_home.lower() != REAL_HOME.lower()
    appdata_home, written_home = {True: (short_home, REAL_HOME), False: (REAL_HOME, short_home)}[appdata_short]
    appdata = Path(appdata_home) / MISSING / "Roaming"
    target = Path(written_home) / MISSING / "Roaming" / "mkway" / "upgrade" / "green.jsonl"
    v = by_tool(world, tool, str(target), env=with_appdata(world, appdata))
    assert (by_class(v), (Path(REAL_HOME) / MISSING).exists()) == (expected(tool) + CLASS_ONLY, False)


# ==== the extended prefixes (R260b 1) =============================================================================================

@pytest.mark.parametrize("tool", TOOLS)
def test_the_extended_length_prefix_form_is_refused_with_the_upgrade_text(world, tool):
    """Catches: E40, the `\\\\?\\C:\\...` form of the green record that is let through (realpath keeps this prefix); the refusal names `upgrade`."""
    assert by_class(by_tool(world, tool, win("||?|") + str(world.dir / "green.jsonl"))) == expected(tool) + CLASS_ONLY


@pytest.mark.parametrize("tool", TOOLS)
def test_the_device_prefix_form_is_refused_with_the_upgrade_text(world, tool):
    """Catches: E41, the `\\\\.\\C:\\...` form of the green record that is let through; the refusal names `upgrade`."""
    assert by_class(by_tool(world, tool, win("||.|") + str(world.dir / "green.jsonl"))) == expected(tool) + CLASS_ONLY


@pytest.mark.parametrize("tool", TOOLS)
def test_the_extended_length_prefix_form_beside_the_folder_is_allowed(world, tool):
    """Checks: E47, the `\\\\?\\` form of a file in the parent of the folder is allowed (the prefix is read, not refused)."""
    assert seen(by_tool(world, tool, win("||?|") + str(world.base / "mkway" / "x"))) == ALLOW


# ==== the other path forms ========================================================================================================

@pytest.mark.parametrize("tool", TOOLS)
def test_the_git_bash_drive_form_is_refused(world, tool):
    """Catches: E42, the Git Bash form `/c/...` of the green record that is not read as the drive path."""
    assert by_class(by_tool(world, tool, git_bash_form(world.dir / "green.jsonl"))) == expected(tool) + CLASS_ONLY


@pytest.mark.parametrize("tool", TOOLS)
def test_another_casing_is_refused(world, tool):
    """Catches: E43, the same folder in capitals that is met only in the case it was resolved in."""
    assert by_class(by_tool(world, tool, str(world.dir / "green.jsonl").upper())) == expected(tool) + CLASS_ONLY


@pytest.mark.parametrize("tool, suffix", [
    pytest.param("Write", win("|green.jsonl:s"), id="stream-on-a-file-of-the-folder"),
    pytest.param("Write", ":s", id="stream-on-the-folder-itself"),
    pytest.param("Bash", win("|x:s"), id="stream-in-a-bash-append"),
])
def test_a_stream_name_on_the_upgrade_folder_or_a_file_in_it_is_refused(world, tool, suffix):
    """Catches: E44, a `:stream` name that hides the file (or the folder itself, met only after the suffix is cut) from the compare."""
    assert by_class(by_tool(world, tool, str(world.dir) + suffix)) == expected(tool) + CLASS_ONLY


@pytest.mark.parametrize("tool", TOOLS)
def test_a_stream_name_on_a_file_beside_the_folder_is_allowed(world, tool):
    """Checks: E45, a stream on a file in the parent of the folder is allowed (the suffix is cut, the base name is judged)."""
    assert seen(by_tool(world, tool, str(world.base / "mkway" / "x") + ":s")) == ALLOW


# ==== UNC (R260a, R260b 3): decided on the raw text, no network ===================================================================

@pytest.mark.parametrize("tool, text", [
    pytest.param("Write", lambda w: admin_share_form(w.dir / "green.jsonl"), id="write-admin-share-of-the-folder"),
    pytest.param("Write", lambda w: win("||host|share|x"), id="write-host-and-share"),
    pytest.param("Write", lambda w: win("||?|UNC|h|s|x"), id="write-extended-unc"),
    pytest.param("Bash", lambda w: win("||localhost|c$|x"), id="bash-admin-share"),
    pytest.param("Bash", lambda w: win("||$h|share|x"), id="bash-host-variable-quoted"),
    pytest.param("Bash", lambda w: "//host/share/x", id="bash-two-slashes"),
    pytest.param("Bash", lambda w: win("||?|UNC|h|s|x"), id="bash-extended-unc"),
])
def test_a_network_path_is_refused_with_the_network_text(world, tool, text):
    """Catches: E46, a network path that is let through, only logged, or refused with a text that names the upgrade target."""
    v = by_tool(world, tool, text(world))
    assert (seen(v), "network path" in v.message, "closed lock" in v.message, "'upgrade'" in v.message) == (expected(tool), True, False, False)
