"""Card MW-103 (rulings R255, R255b): the lead gate's shell decides each path outside the repository (the real expansion of
`<home>` and `<temp>`, the real match, the deny of the settings files and the hooks folders) and hands the core one record
per path. Fake home and temp folders only (USERPROFILE, HOME, TEMP and TMP point at tmp_path); the real ones are never
read. Synthetic names only."""
import copy
import ctypes
import json
import os
from collections import namedtuple

import pytest

from _engine import gate_call
from _mw017 import lead_root, session_run
import gate_lead
import profiles

World = namedtuple("World", "root home temp elsewhere")
WINDOWS = pytest.mark.skipif(os.name != "nt", reason="Windows path rules")


@pytest.fixture(scope="module")
def lead_repo(tmp_path_factory):
    root = lead_root(tmp_path_factory.mktemp("repo"))
    code, _out, err = session_run(root, "lead-a", "lead", "register")
    assert code == 0, err
    return root


@pytest.fixture
def world(lead_repo, tmp_path, monkeypatch):
    home, temp, elsewhere = tmp_path / "home", tmp_path / "temp", tmp_path / "elsewhere"
    for folder in (home, temp, elsewhere):
        folder.mkdir()
    for name in ("USERPROFILE", "HOME"):
        monkeypatch.setenv(name, str(home))
    for name in ("TEMP", "TMP"):
        monkeypatch.setenv(name, str(temp))
    return World(lead_repo, home, temp, elsewhere)


def verdict_of(verdict):
    return verdict.reason_id if verdict.kind == "refuse" else "allow"


def write(world, path, session="lead-a", profile=None, **payload):
    """The lead's Write of `path` (text), judged by the real lead gate."""
    return verdict_of(gate_call(gate_lead.edit, world.root, tool="Write", tool_input={"file_path": str(path), "content": "x"},
                                session=session, profile=profile, **payload))


def listed(path, profile=None):
    """The shell's own match of one absolute path against the expanded list (the fact it hands the core)."""
    return gate_lead.outside_allowed(str(path), profile)


def redirect(world, target):
    command = f"echo x > {target}"
    return verdict_of(gate_call(gate_lead.shell, world.root, tool="Bash", tool_input={"command": command}, session="lead-a"))


def test_a_lead_write_to_its_memory_folder_is_allowed(world):
    """Checks: E8, a lead's Write to the harness memory folder under the home is allowed (R255b)."""
    path = world.home / ".claude" / "projects" / "p" / "memory" / "m.md"
    assert (write(world, path), listed(path)) == ("allow", True)


def test_a_lead_write_to_the_settings_file_is_refused(world):
    """Catches: E9, a lead that rewrites the harness settings file under the home."""
    assert write(world, world.home / ".claude" / "settings.json") == "write-outside-root"  # R274-D1


def test_a_lead_write_to_the_local_settings_file_is_refused(world):
    """Catches: E10, a lead that rewrites the local settings file under the home."""
    assert write(world, world.home / ".claude" / "settings.local.json") == "write-outside-root"  # R274-D1


def test_a_lead_write_to_the_home_hooks_folder_is_refused(world):
    """Catches: E11, a lead that writes a hook script under the home."""
    assert write(world, world.home / ".claude" / "hooks" / "x.py") == "write-outside-root"  # R274-D1


def test_the_hooks_deny_beats_the_temp_pattern(world):
    """Catches: E12, a hooks folder reached through the harness temp pattern `<temp>/claude/**`."""
    assert write(world, world.temp / "claude" / "x" / ".claude" / "hooks" / "h.py") == "write-outside-root"  # R274-D1


def test_a_lead_write_to_the_plans_folder_is_allowed(world):
    """Checks: E13, a lead's Write to the harness plans folder under the home is allowed."""
    path = world.home / ".claude" / "plans" / "a.md"
    assert (write(world, path), listed(path)) == ("allow", True)


def test_a_lead_write_to_the_harness_temp_folder_is_allowed(world):
    """Checks: E14, a lead's Write to `<temp>/claude/...` is allowed."""
    path = world.temp / "claude" / "s" / "x.txt"
    assert (write(world, path), listed(path)) == ("allow", True)


def test_a_lead_write_to_another_temp_folder_is_refused(world):
    """Catches: E15, a lead that writes into the temp folder outside the harness's own subfolder."""
    assert write(world, world.temp / "other" / "x.txt") == "write-outside-root"  # R274-D1


def test_a_path_that_climbs_out_of_memory_to_the_settings_file_is_refused(world):
    """Catches: E16, a `..` path that starts in the memory folder and ends at the settings file."""
    climbing = f"{world.home}/.claude/projects/p/memory/../../../settings.json"
    assert write(world, climbing) == "write-outside-root"  # R274-D1


def test_a_relative_path_is_joined_to_the_cwd_and_refused(world):
    """Catches: E17, a relative path out of the repository that is read from the wrong base and let through."""
    inside = world.root / "src"
    assert (write(world, "../notes/a.md", cwd=str(inside)), redirect_from(world, inside, "../notes/a.md")) == (
        "lead-no-edit", "lead-no-edit")


def redirect_from(world, cwd, target):
    command = f"echo x > {target}"
    return verdict_of(gate_call(gate_lead.shell, world.root, tool="Bash", tool_input={"command": command}, session="lead-a",
                                cwd=str(cwd)))


def test_a_tilde_path_is_read_from_the_home_and_allowed(world):
    """Checks: E18, `~/.claude/plans/a.md` is read from the fake home and allowed."""
    path = world.home / ".claude" / "plans" / "a.md"
    assert (write(world, "~/.claude/plans/a.md"), listed(path)) == ("allow", True)


@WINDOWS
def test_windows_mixed_case_and_backslashes_match_the_same_path(world):
    """Checks: E19, upper case and backslashes name the same memory path as the lower case form."""
    mixed = str(world.home).upper() + "\\.CLAUDE\\Projects\\p\\MEMORY\\m.md"
    assert (write(world, mixed), listed(mixed)) == ("allow", True)


def short_name(path):
    """The 8.3 name of an existing folder; skips the test when the volume keeps no short names."""
    buffer = ctypes.create_unicode_buffer(1024)
    ctypes.windll.kernel32.GetShortPathNameW(str(path), buffer, 1024)
    if not buffer.value or buffer.value.lower() == str(path).lower():
        pytest.skip("this volume has no 8.3 short name for the fake folder")
    return buffer.value


@WINDOWS
def test_windows_short_and_long_temp_names_both_match(world):
    """Checks: E20, the 8.3 short name of a folder in the fake temp and its long name are the same path."""
    long_folder = world.temp / "claude" / "a_long_folder_name"
    long_folder.mkdir(parents=True)
    short = short_name(long_folder)
    short_file = os.path.join(short, "x.txt")
    assert (write(world, long_folder / "x.txt"), write(world, short_file), listed(long_folder / "x.txt"), listed(short_file)) == (
        "allow", "allow", True, True)


def test_a_profile_adds_a_folder_and_cannot_reopen_the_settings_files(world):
    """Catches: E21, a profile list that is ignored, that removes a default, or that re-allows the settings files."""
    profile = json.loads((world.root / "mkway" / "profile.json").read_text(encoding="utf-8"))
    profile["paths"] = {**profile.get("paths", {}),  # R274-D1: the key moved to `paths`
                        "outside_writable": [world.elsewhere.as_posix() + "/**", "<home>/.claude/settings*.json"]}
    got = (listed(world.elsewhere / "n" / "a.md", profile), listed(world.elsewhere / "n" / "a.md"),
           write(world, world.elsewhere / "n" / "a.md", profile=profile),
           write(world, world.home / ".claude" / "plans" / "a.md", profile=profile),
           write(world, world.home / ".claude" / "settings.json", profile=profile),
           write(world, world.elsewhere / "n" / "a.md"))
    assert got == (True, False, "allow", "allow", "write-outside-root", "write-outside-root")  # R274-D1


@pytest.mark.parametrize("value, bad", [
    pytest.param(["notes/**"], True, id="a-relative-pattern"),
    pytest.param([""], True, id="an-empty-string"),
    pytest.param("/abs/notes/**", True, id="not-a-list"),
    pytest.param([7], True, id="a-number-in-the-list"),
    pytest.param(["/abs/../etc/**"], True, id="a-pattern-with-a-dotdot-part"),
    pytest.param(["/abs/notes/**", "<home>/x/**", "<temp>/y/**"], False, id="a-good-list"),
])
def test_a_bad_outside_writable_list_is_profile_invalid(value, bad):
    """Catches: E22, a profile whose `paths.outside_writable` is relative, empty, not a list or climbs with `..`; a good list stays valid."""
    profile = {"vcs": "none", "bundle": {"root": "mkway"}, "gates": {}, "state": {"dir": "mkway/state"},
               "python": {"command": "python"}, "paths": {"outside_writable": value}}  # R274-D1: the key moved to `paths`
    errors = profiles.validate(copy.deepcopy(profile))
    assert bool(errors) is bad
    assert not [e for e in errors if "not allowed here" in e], "the key must be declared, not an unknown key"
    assert {e.startswith("paths.outside_writable") for e in errors} == ({True} if bad else set())


def test_a_lead_redirect_to_the_harness_temp_folder_is_allowed(world):
    """Checks: E23, a Bash redirect to `<temp>/claude/s/x.txt` is allowed."""
    target = world.temp / "claude" / "s" / "x.txt"
    assert (redirect(world, target.as_posix()), listed(target)) == ("allow", True)


def test_a_lead_redirect_to_the_notes_folder_is_refused(world):
    """Catches: E24, a Bash redirect into a notes folder outside the repository (the real case's shape)."""
    assert redirect(world, (world.elsewhere / "project_x" / "analysis" / "notes" / "a.md").as_posix()) == "write-outside-root"  # R274-D1


def test_the_accessor_skips_unusable_items_and_repeats_no_default():
    """Checks: E32, a profile's unusable items (relative, text that is not a path, a `..` part, a number) and a repeat of a default are skipped; a usable item is added after the three defaults."""
    given = ["notes/**", 7, "/abs/../x", "<home>/.claude/plans/**", "/abs/notes/**"]
    assert profiles.outside_writable({"paths": {"outside_writable": given}}) == [  # R274-D1: the key moved to `paths`
        "<home>/.claude/projects/*/memory/**", "<home>/.claude/plans/**", "<temp>/claude/**", "/abs/notes/**"]
