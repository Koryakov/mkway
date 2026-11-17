"""Card MW-105 (rulings R257h, R259c, R260, R260a, R260b, R260c): the lock gate guards the upgrade folder, which lies outside the
repository, through the real gate on a synthetic task root. Every folder is under tmp_path (APPDATA, XDG_CONFIG_HOME, the
home and the temp folders point there; the real ones are never read); the gate is asked as the hook asks it, with the
environment of the call in `ctx.env` (`tests/_mw105.py`). These rows run on every OS; the Windows rules are
`test_mw105_upgrade_lock_windows.py`. Synthetic names only; the Windows variable forms are built by `win` from a `|` mark."""
import os

import pytest

from _engine import cli, make_profile
from _mw105 import (ALLOW, CLASS_ONLY, DENY_EDIT, DENY_SHELL, ENGINE_ONLY, LOGGED, by_class, context, make_world, seen, shell, win,
                    write)
import gate_lead
import gate_lock
import helpers
import locks
import schema_check

FIXED = "/zz/memo"
EDIT_TOOLS = ["Write", "Edit", "MultiEdit", "NotebookEdit"]


@pytest.fixture
def world(tmp_path, monkeypatch):
    return make_world(tmp_path, monkeypatch)


def fill(world, template):
    """A command from a template: `{d}` the upgrade folder, `{a}` the folder that holds `mkway`, both in slash form."""
    return template.format(d=world.dir.as_posix(), a=world.base.as_posix())


# ==== the edit tools ==============================================================================================================

@pytest.mark.parametrize("tool", EDIT_TOOLS)
@pytest.mark.parametrize("name", ["green.jsonl", "policy.json", "new.txt"])
def test_an_edit_tool_write_into_the_upgrade_folder_is_refused(world, tool, name):
    """Catches: E18, a session that writes the green record or the grant, or a new file, in the upgrade folder with an edit tool."""
    v = write(world, world.dir / name, tool)
    assert by_class(v) == DENY_EDIT + CLASS_ONLY


@pytest.mark.parametrize("path", [
    pytest.param(lambda w: w.base / "mkway" / "upgrade2" / "x", id="a-sibling-folder-with-the-same-prefix"),
    pytest.param(lambda w: w.base / "mkway" / "x", id="a-file-in-the-parent"),
    pytest.param(lambda w: w.dir.as_posix() + "/../x", id="a-dotdot-path-that-leaves-the-folder"),
    pytest.param(lambda w: "~/x.txt", id="a-file-in-the-home"),
])
def test_an_edit_tool_write_next_to_the_upgrade_folder_is_allowed(world, path):
    """Checks: E19, a write beside the folder (sibling, parent file, dotdot, home file) is allowed."""
    assert seen(write(world, path(world))) == ALLOW


# ==== the shell ===================================================================================================================

@pytest.mark.parametrize("template", [
    pytest.param("echo x >> {d}/green.jsonl", id="append-redirect"),
    pytest.param("tee {d}/x", id="tee"),
    pytest.param("cp x {d}/", id="cp-into-the-folder"),
    pytest.param("mv {d}/green.jsonl x", id="mv-the-green-record-out"),
    pytest.param("rm {d}/*", id="rm-every-file"),
    pytest.param("rm {d}/gre*", id="rm-a-glob-in-the-folder"),
    pytest.param("rm {a}/mkway/up*", id="rm-a-glob-in-the-parent"),
])
def test_a_bash_write_into_the_upgrade_folder_is_refused(world, template):
    """Catches: E20, a Bash redirect, tee, cp, mv or rm that reaches the upgrade folder, a glob included."""
    v = shell(world, fill(world, template))
    assert by_class(v) == DENY_SHELL + CLASS_ONLY


@pytest.mark.parametrize("template", [
    pytest.param("Set-Content {d}/x y", id="set-content"),
    pytest.param("Add-Content {d}/x y", id="add-content"),
    pytest.param("Out-File {d}/x", id="out-file"),
])
def test_a_powershell_write_into_the_upgrade_folder_is_refused(world, template):
    """Catches: E21, a PowerShell Set-Content, Add-Content or Out-File into the upgrade folder."""
    v = shell(world, fill(world, template), "PowerShell")
    assert by_class(v) == DENY_SHELL + CLASS_ONLY


@pytest.mark.parametrize("tool, template", [
    pytest.param("Bash", "mv {d} {a}/mkway/old", id="mv-the-folder"),
    pytest.param("PowerShell", "Rename-Item {d} new", id="rename-the-folder"),
    pytest.param("Bash", "mv {a}/mkway z", id="mv-the-parent"),
    pytest.param("PowerShell", "Remove-Item -Recurse {a}/mkway", id="remove-the-parent"),
    pytest.param("Bash", "rm -r {a}", id="rm-the-grandparent"),
])
def test_a_write_that_holds_the_upgrade_folder_is_refused(world, tool, template):
    """Catches: E22, a rename or a removal of the upgrade folder or of one of its parents."""
    v = shell(world, fill(world, template), tool)
    assert by_class(v) == DENY_SHELL + CLASS_ONLY


@pytest.mark.parametrize("template", [
    pytest.param("rm {a}/other/*", id="rm-in-another-folder"),
    pytest.param("echo x > {a}/mkway/x", id="a-file-in-the-parent"),
    pytest.param("echo x > {a}/mkway/upgrade2/x", id="a-sibling-folder-with-the-same-prefix"),
    pytest.param("echo x > ~/x.txt", id="a-file-in-the-home"),
])
def test_a_bash_write_next_to_the_upgrade_folder_is_allowed(world, template):
    """Checks: E23, a Bash write beside the folder (another folder, a parent file, a sibling, a home file) is allowed."""
    assert seen(shell(world, fill(world, template))) == ALLOW


def test_the_tilde_form_into_the_upgrade_folder_is_refused(world, monkeypatch):
    """Catches: E24, the `~/...` form of a folder under the home, as a Write and as a Bash append."""
    base = world.home / "cfg"
    base.mkdir()
    monkeypatch.setenv("APPDATA", str(base))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(base))
    env = dict(os.environ)
    got = (by_class(write(world, "~/cfg/mkway/upgrade/green.jsonl", env=env)),
           by_class(shell(world, "echo x >> ~/cfg/mkway/upgrade/green.jsonl", env=env)))
    assert got == (DENY_EDIT + CLASS_ONLY, DENY_SHELL + CLASS_ONLY)


@pytest.mark.parametrize("tool, command", [
    pytest.param("PowerShell", win("Set-Content $env:APPDATA|mkway|upgrade|green.jsonl x"), id="powershell-env-variable"),
    pytest.param("Bash", win("echo x >> %APPDATA%|mkway|upgrade|x"), id="percent-variable"),
    pytest.param("Bash", win("echo x >> '%APPDATA%|mkway|upgrade|x'"), id="percent-variable-quoted"),
])
def test_a_variable_path_naming_the_upgrade_folder_is_refused_by_the_gate(world, tool, command):
    """Catches: E25, an unreadable write path that names the upgrade folder (R260a 1) that is only logged."""
    env = {k: v for k, v in world.env.items() if k.upper() != "APPDATA"}
    v = shell(world, command, tool, env=env)
    assert (seen(v), "'upgrade'" in v.message, "write literal paths" in v.message) == (DENY_SHELL, True, True)


@pytest.mark.parametrize("command", [
    pytest.param(win("Set-Content $env:APPDATA|mkway|upgrade2|x y"), id="a-sibling-folder-with-the-same-prefix"),
    pytest.param(win("Set-Content $x|green.jsonl y"), id="a-variable-then-the-file-name"),
])
def test_a_variable_path_not_naming_the_upgrade_folder_is_only_logged_by_the_gate(world, command):
    """Checks: E26, a variable path that does not name the folder is logged, not refused (the named gap of R260a 1)."""
    assert seen(shell(world, command, "PowerShell")) == LOGGED


# ==== which folders are guarded ===================================================================================================

def test_with_the_override_set_both_folders_are_guarded(world, monkeypatch, tmp_path):
    """Catches: E27, an owner-wide MKWAY_UPGRADE_DIR that unguards the real default folder, or one that leaves the override open."""
    other = tmp_path / "owner-wide"
    other.mkdir()
    monkeypatch.setenv("MKWAY_UPGRADE_DIR", str(other))
    env = dict(os.environ)
    got = (by_class(write(world, other / "green.jsonl", env=env)), by_class(write(world, world.dir / "green.jsonl", env=env)),
           by_class(shell(world, f"echo x >> {other.as_posix()}/green.jsonl", env=env)),
           by_class(shell(world, f"echo x >> {world.dir.as_posix()}/green.jsonl", env=env)),
           seen(write(world, tmp_path / "elsewhere" / "x", env=env)))
    assert got == (DENY_EDIT + CLASS_ONLY, DENY_EDIT + CLASS_ONLY, DENY_SHELL + CLASS_ONLY, DENY_SHELL + CLASS_ONLY, ALLOW)


def test_with_no_appdata_and_no_xdg_the_home_config_folder_is_guarded(world, monkeypatch, tmp_path):
    """Catches: E28, a guarded folder resolved from the wrong home (the one `mkway upgrade` reads is HOME, then USERPROFILE)."""
    first, second = tmp_path / "home-first", tmp_path / "home-second"
    first.mkdir()
    second.mkdir()
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setenv("HOME", str(first))
    monkeypatch.setenv("USERPROFILE", str(second))
    env = dict(os.environ)
    got = (seen(write(world, first / ".config" / "mkway" / "upgrade" / "green.jsonl", env=env)),
           seen(write(world, second / ".config" / "mkway" / "upgrade" / "green.jsonl", env=env)))
    assert got == (DENY_EDIT, ALLOW)


# ==== the target ==================================================================================================================

def test_lock_open_upgrade_is_refused_for_the_owner_too(world):
    """Catches: E29, `lock open upgrade` that opens (or does not know) the target: it is never open, only the engine writes it."""
    code, out, err = cli(world.root, "lock", "open", "upgrade")
    assert (code != 0, ENGINE_ONLY in out + err) == (True, True)


def test_schema_refuses_open_by_default_on_the_upgrade_target():
    """Catches: E30, a profile that holds the upgrade target open by default (R260b 2); the same target without the flag is no business of this check."""
    flagged = make_profile(locks={"targets": [{"name": "upgrade", "paths": ["x"], "open_by_default": True}]})
    plain = make_profile(locks={"targets": [{"name": "upgrade", "paths": ["x"]}]})
    errors = schema_check.check(flagged)
    assert (any("upgrade" in e and "open_by_default" in e and "built-in" in e for e in errors),
            schema_check.check(plain)) == (True, [])


def test_a_profile_target_named_upgrade_is_ignored(world):
    """Catches: E31, a profile target that takes the name `upgrade` and points the guard at a folder of its own."""
    profile = dict(world.profile, locks={"targets": [{"name": "upgrade", "paths": ["docs/"]}]})
    assert [t.entries for t in locks.profile_targets(world.root, profile) if t.name == "upgrade"] == []


def test_the_repo_state_file_keeps_its_verdict_beside_the_new_target(world):
    """Checks: E32, a write to the repo's own state folder is judged as before: refused for `state`, never for `upgrade`."""
    v = write(world, world.root / "mkway" / "state" / "x.jsonl")
    assert (seen(v), "'state'" in v.message, "'upgrade'" in v.message) == (DENY_EDIT, True, False)


@pytest.mark.parametrize("command", [pytest.param("rm up*", id="rm-up-star"), pytest.param("rm A*", id="rm-capital-a-star")])
def test_a_repo_glob_keeps_todays_verdict_beside_an_absolute_entry(world, command):
    """Checks: E33, a glob in the repo is judged as before: the absolute entry does not make `up*` or `A*` match (never weaker)."""
    assert seen(shell(world, command)) == ALLOW


# ==== the facts the shell reads ===================================================================================================

def test_the_write_facts_carry_the_class_of_an_upgrade_path(world):
    """Catches: E34, a shell reader that hands the core no class for a path inside the upgrade folder."""
    target = f"{world.dir.as_posix()}/green.jsonl"
    command = f"echo x >> {target}"
    reader = gate_lock.Reader(context(world, "Bash", {"command": command}), world.profile, command)
    assert reader.fact_writes().paths == ((target, None, "upgrade"),)


def test_the_write_facts_of_a_repo_path_have_two_items(world):
    """Checks: E35, a repo path is handed over with its two items, as before: no third item for no class."""
    command = "echo x > src/a.txt"
    reader = gate_lock.Reader(context(world, "Bash", {"command": command}), world.profile, command)
    assert reader.fact_writes().paths == (("src/a.txt", "src/a.txt"),)


def test_the_lead_gate_reads_paths_through_the_helpers_canon(monkeypatch):
    """Catches: E36, a lead gate that keeps a canon of its own (R260 b: one `_canon`, moved to helpers, MW-103's tests unchanged)."""
    monkeypatch.setattr(helpers, "_canon", lambda path: FIXED)
    assert gate_lead.outside_allowed("anything", {"paths": {"outside_writable": [FIXED]}}) is True  # R274-D1: the key moved to `paths`


def test_the_upgrade_target_is_last_and_holds_one_folder_entry(world):
    """Catches: E37, a target list without `upgrade`, or with it first (the first closed target names the refusal), or with an entry that is not a folder."""
    targets = locks.built_in(world.root, world.profile, env=world.env)
    assert (targets[-1].name, targets[-1].entries, targets[-1].built_in) == ("upgrade", [world.dir.as_posix() + "/"], True)


def test_a_blank_write_path_has_no_class(world):
    """Checks: E55, a blank write path (`echo x > ""`) names no path, so it has no class; found by the coverage run of `Outside.classify`."""
    outside = gate_lock.Outside(context(world, "Bash", {"command": "x"}), locks.core_targets(world.root, world.profile, env=world.env))
    assert [outside.classify(text, shell=True) for text in ("", "  ")] == [None, None]
