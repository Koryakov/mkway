"""Card MW-105, the fix list of the first review (ruling R260d, items C1 to C7): the lock gate's guard of the upgrade folder through
the real gate on a synthetic task root, as the hook asks it (`tests/_mw105.py`). Every folder is under tmp_path; the real ones are
never read. C1 a `~` of a `cd` target, C2 the five folder variables expanded from the call's environment, C3 `~` is HOME first,
C4 a canonical form that starts with two slashes is a network path and a network guard entry is never resolved on disk, C6 a home
that cannot be found, C7 a relative override. Synthetic names only; the Windows forms are built by `win` from a `|` mark."""
import json
import os
from pathlib import Path

import pytest

from _mw105 import (ALLOW, CLASS_ONLY, DENY_EDIT, DENY_SHELL, LOGGED, by_class, by_tool, context, expected, make_world, seen,
                    shell, win, write)
import gate_lock
import helpers
import locks
import logs
import profiles
import startline

PROBLEM = "write-target-unresolved"
MAPPED, MAPPED_REAL = "Z:/mapped/x", "//host/share/x"  # a mapped drive and the real network path it resolves to
SHARE_ENTRY, SLASHES = "//host/share/up", "//"


@pytest.fixture
def world(tmp_path, monkeypatch):
    return make_world(tmp_path, monkeypatch)


def rows(world) -> list:
    """The rows of the task's refusals log with the reason id `write-target-unresolved` (the hook's log rows for a path it cannot read)."""
    path = profiles.state_dir(world.root, world.profile) / logs.REFUSALS
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    return [row for row in map(json.loads, lines) if row.get("reason_id") == PROBLEM]


@pytest.fixture
def roaming(world, monkeypatch):
    """The environment in which APPDATA and XDG_CONFIG_HOME are `<home>/AppData/Roaming`, a folder that holds `mkway` (so a `cd`
    into it reads as a folder that exists); the guarded folder is `<home>/AppData/Roaming/mkway/upgrade`."""
    folder = world.home / "AppData" / "Roaming"
    (folder / "mkway").mkdir(parents=True)
    for name in ("APPDATA", "XDG_CONFIG_HOME"):
        monkeypatch.setenv(name, str(folder))
    return dict(os.environ)


# ==== C1: a `~` of a cd target (R260d C1) =========================================================================================

@pytest.mark.parametrize("command", [
    pytest.param("cd ~/AppData/Roaming/mkway && rm -rf upgrade", id="cd-into-the-parent-then-rm-the-folder"),
    pytest.param("cd ~ && rm -rf AppData/Roaming/mkway", id="cd-home-then-rm-the-parent"),
    pytest.param("cd ~/AppData/Roaming/mkway && echo x >> upgrade/green.jsonl", id="cd-into-the-parent-then-append-to-a-file"),
])
def test_a_cd_to_a_tilde_form_then_a_write_into_the_upgrade_folder_is_refused(world, roaming, command):
    """Catches: E56 (C1), a `cd` to `~` or `~/...` that leaves the folder unknown, so the relative write after it is only logged."""
    assert by_class(shell(world, command, env=roaming)) == DENY_SHELL + CLASS_ONLY


@pytest.mark.parametrize("command", [
    pytest.param("cd ~/AppData/Roaming/mkway && rm -rf other", id="cd-into-the-parent-then-rm-another-folder"),
    pytest.param("cd ~ && echo x > y.txt", id="cd-home-then-write-a-home-file"),
])
def test_a_cd_to_a_tilde_form_then_a_write_beside_the_upgrade_folder_is_allowed(world, roaming, command):
    """Catches: E57 (C1), the nearest allow of the refusals: a write beside the folder after the same `cd` is judged by its real path."""
    assert seen(shell(world, command, env=roaming)) == ALLOW


def test_a_cd_to_a_user_form_stays_unread(world, roaming):
    """Checks: E58 (C1), no `~user` form: the folder after `cd ~other/...` stays unknown, the write is logged as unreadable (today's verdict)."""
    assert seen(shell(world, "cd ~other/AppData/Roaming/mkway && rm -rf upgrade", env=roaming)) == LOGGED


# ==== C2: the five folder variables expand from the environment of the call (R260d C2) ============================================

@pytest.mark.parametrize("tool, command", [
    pytest.param("PowerShell", win("Remove-Item -Recurse -Force $env:APPDATA|mkway"), id="powershell-env-appdata"),
    pytest.param("PowerShell", win("Remove-Item -Recurse -Force ${env:APPDATA}|mkway"), id="powershell-braced-env-appdata"),
    pytest.param("Bash", 'rm -rf "$APPDATA/mkway"', id="bash-quoted-appdata"),
    pytest.param("Bash", "rm -rf ${APPDATA}/mkway", id="bash-braced-appdata"),
    pytest.param("Bash", "rm -rf '%APPDATA%/mkway'", id="percent-appdata"),
    pytest.param("PowerShell", win("Remove-Item -Recurse %APPDATA%|mkway"), id="powershell-percent-appdata"),
    pytest.param("Bash", 'rm -rf "$XDG_CONFIG_HOME/mkway"', id="bash-xdg"),
])
def test_a_variable_path_that_expands_to_the_parent_of_the_upgrade_folder_is_refused_by_the_class(world, tool, command):
    """Catches: E59 (C2), a path built from APPDATA or XDG_CONFIG_HOME that reaches the parent of the folder and is only logged."""
    assert by_class(shell(world, command, tool)) == DENY_SHELL + CLASS_ONLY


@pytest.fixture
def home_only(world, monkeypatch, tmp_path):
    """No APPDATA and no XDG_CONFIG_HOME; HOME and USERPROFILE are one folder; the guarded folder is `<home>/.config/mkway/upgrade`."""
    home = tmp_path / "home-only"
    home.mkdir()
    for name in ("APPDATA", "XDG_CONFIG_HOME"):
        monkeypatch.delenv(name, raising=False)
    for name in ("HOME", "USERPROFILE"):
        monkeypatch.setenv(name, str(home))
    return dict(os.environ)


@pytest.mark.parametrize("command", [
    pytest.param("echo x >> $HOME/.config/mkway/upgrade/green.jsonl", id="home-variable"),
    pytest.param("echo x >> ${USERPROFILE}/.config/mkway/upgrade/green.jsonl", id="userprofile-variable"),
])
def test_a_home_variable_path_into_the_upgrade_folder_is_refused_by_the_class(world, home_only, command):
    """Catches: E60 (C2), HOME and USERPROFILE as forms of the folder path that are not expanded from the call's environment."""
    assert by_class(shell(world, command, env=home_only)) == DENY_SHELL + CLASS_ONLY


def test_the_override_variable_into_the_override_folder_is_refused_by_the_class(world, monkeypatch, tmp_path):
    """Catches: E61 (C2), MKWAY_UPGRADE_DIR as the form of the override folder that is not expanded from the call's environment."""
    other = tmp_path / "owner-wide"
    other.mkdir()
    monkeypatch.setenv("MKWAY_UPGRADE_DIR", str(other))
    assert by_class(shell(world, 'echo x >> "$MKWAY_UPGRADE_DIR/green.jsonl"', env=dict(os.environ))) == DENY_SHELL + CLASS_ONLY


@pytest.mark.parametrize("tool, command", [
    pytest.param("PowerShell", win("Set-Content $env:APPDATA|mkway|other|x y"), id="a-folder-beside-the-upgrade-folder"),
    pytest.param("Bash", 'echo x >> "$APPDATA/mkway/x"', id="a-file-in-the-parent"),
    pytest.param("PowerShell", win("Remove-Item -Recurse $env:OTHERVAR|mkway"), id="a-variable-that-is-not-one-of-the-five"),
])
def test_a_variable_path_beside_the_upgrade_folder_is_only_logged(world, tool, command):
    """Checks: E62 (C2), a variable path that expands beside the folder, or a variable that is not expanded, is logged, not refused; the core reads the raw variable text."""
    assert seen(shell(world, command, tool)) == LOGGED


def test_an_assigned_variable_stays_a_variable(world):
    """Catches: E63 (C2, R260f), a name the command assigns that stops the expansion: APPDATA is expanded from the environment whatever the command does to it, so the removal of the parent folder is refused on the real folder (the id is kept, the old expectation was a log)."""
    command = win("$env:APPDATA='D:|t'; Remove-Item -Recurse $env:APPDATA|mkway")
    assert by_class(shell(world, command, "PowerShell")) == DENY_SHELL + CLASS_ONLY


def test_an_assigned_variable_that_names_the_folder_keeps_todays_refusal(world):
    """Catches: E64 (C2, R260f), an assigned APPDATA with a path that names `mkway|upgrade`: refused, now by the class on the real folder (the id is kept, the old expectation was a refusal by the raw text of the unreadable path)."""
    command = win("$env:APPDATA='D:|t'; Set-Content $env:APPDATA|mkway|upgrade|x y")
    assert by_class(shell(world, command, "PowerShell")) == DENY_SHELL + CLASS_ONLY


# ==== C3: `~` is HOME first, then USERPROFILE (R260d C3) ==========================================================================

@pytest.fixture
def two_homes(world, monkeypatch, tmp_path):
    """The setup of E28: no APPDATA, no XDG_CONFIG_HOME, HOME and USERPROFILE two folders; returns the environment."""
    for name, folder in (("HOME", "home-first"), ("USERPROFILE", "home-second")):
        (tmp_path / folder).mkdir()
        monkeypatch.setenv(name, str(tmp_path / folder))
    for name in ("APPDATA", "XDG_CONFIG_HOME"):
        monkeypatch.delenv(name, raising=False)
    return dict(os.environ)


def test_the_tilde_form_is_read_from_home_before_userprofile(world, two_homes):
    """Catches: E65 (C3), `~/.config/mkway/upgrade/...` read from USERPROFILE while the guarded folder is under HOME (an edit-tool path and a Bash append)."""
    path = "~/.config/mkway/upgrade/green.jsonl"
    got = (by_class(write(world, path, env=two_homes)), by_class(shell(world, f"echo x >> {path}", env=two_homes)))
    assert got == (DENY_EDIT + CLASS_ONLY, DENY_SHELL + CLASS_ONLY)


def test_the_tilde_form_beside_the_folder_is_allowed_when_the_homes_differ(world, two_homes):
    """Checks: E66 (C3), the nearest allow: a home file is not judged as the folder when HOME and USERPROFILE differ."""
    assert (seen(write(world, "~/x.txt", env=two_homes)), seen(shell(world, "echo x > ~/x.txt", env=two_homes))) == (ALLOW, ALLOW)


# ==== C4: a canonical form that starts with two slashes is a network path (R260d C4) ==============================================

@pytest.mark.parametrize("tool", ["Write", "Bash"])
def test_a_path_whose_real_form_is_a_network_path_is_refused_with_the_network_text(world, monkeypatch, tool):
    """Catches: E67 (C4), a mapped drive whose real path is `//host/share/...` that is compared with the folders and let through, or refused with the upgrade text."""
    real = helpers._canon
    monkeypatch.setattr(helpers, "_canon", lambda path: MAPPED_REAL if MAPPED.lower() in path.lower() else real(path))
    v = by_tool(world, tool, MAPPED)
    assert (seen(v), "network path" in v.message, "'upgrade'" in v.message) == (expected(tool), True, False)


def test_a_network_guard_entry_is_compared_as_text_and_never_resolved_on_disk(world, monkeypatch):
    """Catches: E68 (C4), `os.path.realpath` run on a guard entry that is a network path (it would touch the share on every hook call)."""
    monkeypatch.setenv("MKWAY_UPGRADE_DIR", SHARE_ENTRY)
    env = dict(os.environ)
    resolved = []
    monkeypatch.setattr(helpers, "_canon", lambda path: resolved.append(path) or path)
    outside = gate_lock.Outside(context(world, "Bash", {"command": "x"}), locks.core_targets(world.root, world.profile, env=env))
    got = (helpers._fold(SHARE_ENTRY) in outside.folders, any(p.startswith(SLASHES) for p in resolved))
    assert got == (True, False)


# ==== C6: a home that cannot be found (R260d C6) ==================================================================================

def no_home(cls):
    raise RuntimeError("Could not determine home directory.")


@pytest.fixture
def no_home_world(world, monkeypatch, tmp_path):
    """No HOME, USERPROFILE, APPDATA or XDG_CONFIG_HOME and a `Path.home()` that raises: the default upgrade folder cannot be
    resolved; the override folder (`<tmp>/owner-wide`) can. Returns (that folder, the environment)."""
    for name in ("HOME", "USERPROFILE", "APPDATA", "XDG_CONFIG_HOME"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(Path, "home", classmethod(no_home))
    other = tmp_path / "owner-wide"
    other.mkdir()
    monkeypatch.setenv("MKWAY_UPGRADE_DIR", str(other))
    return other, dict(os.environ)


def test_with_no_home_the_gate_guards_the_folder_it_can_resolve(world, no_home_world):
    """Catches: E69 (C6), a hook that crashes (fails every call) when the home cannot be found, or that leaves the folder it can resolve open."""
    other, env = no_home_world
    got = (by_class(write(world, other / "green.jsonl", env=env)), seen(write(world, other.parent / "elsewhere" / "x", env=env)))
    assert got == (DENY_EDIT + CLASS_ONLY, ALLOW)


def test_with_no_home_the_gate_writes_one_log_line_per_call(world, no_home_world):
    """Catches: E70 (C6), a folder the hook could not resolve that leaves no trace: one `write-target-unresolved` log row naming the home."""
    other, env = no_home_world
    write(world, other / "green.jsonl", env=env)
    got = [(r["kind"], r["session"], "home" in r.get("note", "")) for r in rows(world)]
    assert got == [("log", "s1", True)]


def test_with_no_home_the_name_only_callers_do_not_crash(world, no_home_world):
    """Catches: E71 (C6), a caller that needs only the target names (a lock name check, a `lock open`, the trash gate's target lookups) that crashes on the home."""
    got = (len(locks.profile_targets(world.root, world.profile)) >= 0,
           locks.closed_target(world.root, world.profile, "mkway/engine/x").name,
           locks.set_lock(world.root, world.profile, "engine", "open", 1)["state"])
    assert got == (True, "engine", "open")


def test_the_unresolved_path_reminder_does_not_count_the_guards_own_log_line(world, no_home_world):
    """Catches: E78 (C6), the reminder at the next prompt that tells a session its shell commands wrote to unreadable targets because the hook logged a folder it could not resolve."""
    other, env = no_home_world
    write(world, other / "green.jsonl", env=env)
    assert seen(gate_lock.remind("UserPromptSubmit", context(world, "Bash", {"command": "x"}, env))) == ("allow", None)


# ==== C7: only an absolute override is guarded (R260d C7) =========================================================================

def test_a_relative_override_is_not_a_guard_entry(world, monkeypatch):
    """Catches: E72 (C7), `MKWAY_UPGRADE_DIR=up` that gives the entry `up/`, which the gate then reads as a folder of the repository."""
    monkeypatch.setenv("MKWAY_UPGRADE_DIR", "up")
    got = [t.entries for t in locks.core_targets(world.root, world.profile, env=dict(os.environ)) if t.name == "upgrade"]
    assert got == [[world.dir.as_posix() + "/"]]


def test_a_write_to_a_repo_folder_named_like_a_relative_override_is_allowed(world, monkeypatch):
    """Catches: E73 (C7), a repo folder `up` that is refused as the upgrade target because the override is the relative text `up`."""
    monkeypatch.setenv("MKWAY_UPGRADE_DIR", "up")
    assert seen(write(world, world.root / "up" / "x", env=dict(os.environ))) == ALLOW


def test_a_relative_override_leaves_one_log_line(world, monkeypatch):
    """Catches: E74 (C7), a relative override that the command accepts but the hook cannot guard, with no trace: one log row naming MKWAY_UPGRADE_DIR."""
    monkeypatch.setenv("MKWAY_UPGRADE_DIR", "up")
    write(world, world.root / "up" / "x", env=dict(os.environ))
    got = [(r["kind"], r["session"], "MKWAY_UPGRADE_DIR" in r.get("note", "")) for r in rows(world)]
    assert got == [("log", "s1", True)]


def test_an_absolute_override_leaves_no_log_line(world, monkeypatch, tmp_path):
    """Checks: E75 (C7), the nearest allow: an absolute override and a resolved home leave no `write-target-unresolved` row."""
    monkeypatch.setenv("MKWAY_UPGRADE_DIR", str(tmp_path / "owner-wide"))
    write(world, tmp_path / "owner-wide" / "x", env=dict(os.environ))
    assert rows(world) == []


# ==== found by the branch coverage run of the fixes: the changed branches no earlier row reached (R183) ===========================

def failing_write(state, data):
    raise OSError("the state folder cannot be written")


def forbidden(env=None):
    raise AssertionError("the upgrade folder was resolved by a caller that needs only target names")


def test_a_variable_that_expands_to_a_network_path_is_refused_with_the_network_text(world, monkeypatch):
    """Catches: E79 (C2), APPDATA that is a network path: the expanded text compared as a local folder, resolved on disk (the share is touched), or refused with the upgrade text."""
    monkeypatch.setenv("APPDATA", SHARE_ENTRY)
    resolved = []
    monkeypatch.setattr(helpers, "_canon", lambda path: resolved.append(path) or path)
    v = shell(world, 'echo x >> "$APPDATA/mkway/x"', env=dict(os.environ))
    got = (seen(v), "network path" in v.message, "'upgrade'" in v.message, any(p.startswith(SLASHES) for p in resolved))
    assert got == (DENY_SHELL, True, False, False)


def test_a_failed_log_write_does_not_fail_the_gate_call(world, no_home_world, monkeypatch):
    """Catches: E80 (C6), the guard's log row that cannot be written (the state folder is read-only) and fails the whole lock gate call."""
    other, env = no_home_world
    monkeypatch.setattr(logs, "write_refusal", failing_write)
    assert by_class(write(world, other / "green.jsonl", env=env)) == DENY_EDIT + CLASS_ONLY


def test_an_override_that_equals_the_default_folder_is_one_entry(world, monkeypatch):
    """Checks: E81 (C7), the override and the default resolve to one folder: one entry, and no log row."""
    monkeypatch.setenv("MKWAY_UPGRADE_DIR", str(world.dir))
    env = dict(os.environ)
    got = ([t.entries for t in locks.core_targets(world.root, world.profile, env=env) if t.name == "upgrade"], locks.upgrade_resolution(env)[1])
    assert got == ([[world.dir.as_posix() + "/"]], [])


def test_the_name_only_callers_never_resolve_the_upgrade_folder(world, monkeypatch):
    """Catches: E82 (C6), a caller that needs only target names or repo paths (the engine and profile target lists, the closed, held and glob lookups, `lock open`) that resolves the upgrade folder."""
    monkeypatch.setattr(locks, "upgrade_resolution", forbidden)
    got = (isinstance(locks.engine_targets(world.root, world.profile), list), isinstance(locks.profile_targets(world.root, world.profile), list),
           locks.closed_target(world.root, world.profile, "mkway/engine/x").name, locks.held_target(world.root, world.profile, ".")[0].name,
           locks.glob_target(world.root, world.profile, "mkway/eng*")[0].name, locks.set_lock(world.root, world.profile, "engine", "open", 1)["state"])
    assert got == (True, True, "engine", "engine", "engine", "open")


# ==== fix list 2 (R260d, R260e: the review of fix list 1) =========================================================================

def key_error_home(cls):
    raise KeyError("getpwuid(): uid not found")


def test_a_repo_path_is_never_a_network_path_by_its_real_path(world, monkeypatch):
    """Catches: E83 (F1), a repo on a mapped drive (its real path starts with two slashes) whose every write is refused as a network path."""
    real, root_text = helpers._canon, world.root.as_posix()
    monkeypatch.setattr(helpers, "_canon", lambda path: MAPPED_REAL if root_text in path.replace("\\", "/") else real(path))
    got = (seen(write(world, world.root / "src" / "a.txt")), seen(shell(world, "echo x > src/a.txt")))
    assert got == (ALLOW, ALLOW)


@pytest.mark.parametrize("tool, command", [
    pytest.param("Bash", 'rm -rf "$APPDATA/mkway"; echo "ready for reinstall"', id="a-word-for-in-a-later-string"),
    pytest.param("PowerShell", win("Remove-Item -Recurse -Force $env:APPDATA|mkway; Read-Host"), id="the-word-read-in-a-later-command"),
    pytest.param("Bash", 'LOCALAPPDATA=x; rm -rf "$APPDATA/mkway"', id="another-name-that-ends-with-the-name"),
])
def test_a_word_elsewhere_or_another_name_does_not_make_the_variable_assigned(world, tool, command):
    """Catches: E84 (F2, R260f), a binder word anywhere in the text, or a longer name that ends in the name, that stops the expansion of the variable (no assigned check exists any more: the name is always expanded, the id is kept)."""
    assert by_class(shell(world, command, tool)) == DENY_SHELL + CLASS_ONLY


@pytest.mark.parametrize("tool, command", [
    pytest.param("Bash", 'export APPDATA; rm -rf "$APPDATA/mkway"', id="export-name"),
    pytest.param("Bash", 'set APPDATA=D:/t; rm -rf "$APPDATA/mkway"', id="set-name-equals"),
    pytest.param("PowerShell", win("$env:APPDATA += 'x'; Remove-Item -Recurse $env:APPDATA|mkway"), id="plus-equals"),
    pytest.param("PowerShell", win("New-Item Env:APPDATA -Value x; Remove-Item -Recurse $env:APPDATA|mkway"), id="new-item-env"),
    pytest.param("Bash", 'read APPDATA; rm -rf "$APPDATA/mkway"', id="read-name"),
    pytest.param("Bash", 'APPDATA=/x rm -rf "$APPDATA/mkway"', id="prefix-assignment"),
])
def test_a_variable_the_command_binds_stays_a_variable(world, tool, command):
    """Catches: E85 (F2, R260f), each form that binds the name (export, set, `+=`, New-Item Env:, read, a prefix assignment): the name is expanded from the environment of the call whatever the command does to it, so the path is refused on the real folder (the id is kept, the old expectation was a log, the old assigned check is gone)."""
    assert by_class(shell(world, command, tool)) == DENY_SHELL + CLASS_ONLY


def test_the_context_reads_the_tilde_from_userprofile_first(world, monkeypatch, tmp_path):
    """Catches: E86 (F3), the dispatcher's context that reads `~` from HOME first for every gate (only this card's classify does)."""
    monkeypatch.setenv("HOME", str(tmp_path / "elsewhere"))
    monkeypatch.setenv("USERPROFILE", str(world.root))
    assert context(world, "Bash", {"command": "x"}, dict(os.environ)).norm("~/a.txt") == "a.txt"


def test_the_start_line_count_skips_the_guards_own_rows(world):
    """Catches: E87 (F4), the start line that counts the guard's own log row (it carries a `note`) as a shell command that wrote to an unreadable target."""
    state = profiles.state_dir(world.root, world.profile)
    state.mkdir(parents=True, exist_ok=True)
    data = [{"reason_id": PROBLEM, "kind": "log"}, {"reason_id": PROBLEM, "kind": "log", "note": "the home folder cannot be found"}]
    (state / logs.REFUSALS).write_text("\n".join(map(json.dumps, data)) + "\n", encoding="utf-8")
    assert startline._unresolved_count(state) == 1


def test_a_key_error_from_the_home_lookup_is_caught_too(world, no_home_world, monkeypatch):
    """Catches: E88 (F4), a home lookup that fails with a KeyError (no entry for the user on POSIX) that crashes the hook."""
    other, env = no_home_world
    monkeypatch.setattr(Path, "home", classmethod(key_error_home))
    got = (by_class(write(world, other / "green.jsonl", env=env)), len(rows(world)))
    assert got == (DENY_EDIT + CLASS_ONLY, 1)


def test_a_chain_with_a_command_before_the_cd_is_read(world, roaming):
    """Checks: E90 (F6), `ls && cd ~ && rm -rf ...`: a plain command in front of the `cd` does not hide the folder."""
    assert by_class(shell(world, "ls && cd ~ && rm -rf AppData/Roaming/mkway", env=roaming)) == DENY_SHELL + CLASS_ONLY


# ==== fix list 3 (R260f: the five names always expand; R260d F1: the root canon condition) ========================================

@pytest.mark.parametrize("tool, command", [
    pytest.param("PowerShell", win("New-Item -Path $env:APPDATA|mkway|upgrade|x"), id="new-item-path-into-the-folder"),
    pytest.param("PowerShell", win("ni $env:APPDATA|mkway"), id="ni-the-parent"),
    pytest.param("Bash", 'rm -rf "$APPDATA/mkway" # APPDATA=', id="the-name-in-a-comment"),
    pytest.param("PowerShell", win("$APPDATA='x'; Remove-Item -Recurse $env:APPDATA|mkway"), id="a-script-variable-of-the-same-name"),
    pytest.param("Bash", 'APPDATA=$APPDATA rm -rf "$APPDATA/mkway"', id="a-prefix-assignment-from-the-name-itself"),
])
def test_a_name_the_command_binds_is_still_expanded_from_the_environment(world, tool, command):
    """Catches: E92 (G2, R260f), a command that mentions or binds the name (a comment, a script variable, a prefix assignment, New-Item) that switches the expansion off, so the write under the real folder is only logged."""
    assert by_class(shell(world, command, tool)) == DENY_SHELL + CLASS_ONLY


def test_a_lower_case_home_variable_does_not_stop_the_expansion_of_home(world, home_only):
    """Catches: E93 (G2, R260f), `home=/tmp` (another name on POSIX) that switches the expansion of `$HOME` off, so the write under the real folder is only judged by its text."""
    assert by_class(shell(world, 'home=/tmp; rm -rf "$HOME/.config/mkway/upgrade"', env=home_only)) == DENY_SHELL + CLASS_ONLY


@pytest.mark.parametrize("tool", ["Write", "Bash"])
def test_an_in_repo_path_whose_real_path_leaves_the_repo_for_a_share_is_a_network_path(world, monkeypatch, tool):
    """Catches: E94 (G3), a repo path that is a link to a share (its real path starts with two slashes and is not under the repo's real path) that escapes both the network class and the upgrade compare."""
    real = helpers._canon
    monkeypatch.setattr(helpers, "_canon", lambda path: MAPPED_REAL if path.replace("\\", "/").endswith("src/a.txt") else real(path))
    v = write(world, world.root / "src" / "a.txt") if tool == "Write" else shell(world, "echo x > src/a.txt")
    assert (seen(v), "network path" in v.message) == (expected(tool), True)


def test_two_paths_with_a_share_real_path_in_one_call_are_both_network_paths(world, monkeypatch):
    """Checks: E95 (G3, found by the branch coverage run), the repo's real path is read once for a call and the second path is judged with it: both are network paths."""
    real = helpers._canon
    monkeypatch.setattr(helpers, "_canon", lambda path: MAPPED_REAL if "mapped" in path.lower() else real(path))
    outside = gate_lock.Outside(context(world, "Bash", {"command": "x"}), locks.core_targets(world.root, world.profile, env=world.env))
    assert [outside.classify(text, shell=True) for text in (MAPPED, MAPPED.replace("x", "y"))] == ["unc", "unc"]


# ==== fix list 4 (R260g): the Env prefix in any case, PowerShell HOME, the default and alternative forms, and the H5 inputs =========

@pytest.fixture
def xdg_other(world, home_only, tmp_path):
    """The `home_only` environment with XDG_CONFIG_HOME at another folder: the guarded folder is `<other>/mkway/upgrade`."""
    return dict(home_only, XDG_CONFIG_HOME=str(tmp_path / "other-config"))


@pytest.mark.parametrize("command", [
    pytest.param(win("Remove-Item -Recurse -Force $Env:APPDATA|mkway"), id="env-mixed-case"),
    pytest.param(win("Remove-Item -Recurse -Force $ENV:APPDATA|mkway"), id="env-upper-case"),
    pytest.param(win("Remove-Item -Recurse -Force ${Env:XDG_CONFIG_HOME}|mkway"), id="braced-env-mixed-case"),
])
def test_the_env_prefix_is_read_in_any_case(world, command):
    """Catches: E96 (H1, R260g), `$Env:` or `$ENV:` (the Env: drive is case-insensitive in PowerShell) that is not expanded, so the removal of the parent folder is only logged."""
    assert by_class(shell(world, command, "PowerShell")) == DENY_SHELL + CLASS_ONLY


def test_a_powershell_home_falls_back_to_userprofile(world, roaming):
    """Catches: E97 (H2, R260g), PowerShell `$HOME` (the profile folder) that is not expanded when the environment has no HOME, so the removal of the parent folder is only logged."""
    env = {k: v for k, v in roaming.items() if k.upper() != "HOME"}
    assert by_class(shell(world, win("Remove-Item -Recurse $HOME|AppData|Roaming|mkway"), "PowerShell", env=env)) == DENY_SHELL + CLASS_ONLY


def test_a_bash_home_missing_from_the_environment_is_only_logged(world, roaming):
    """Checks: E98 (H2, H4), a name missing from the environment of the call is not expanded: the Bash `$HOME` stays a variable and is logged (a named gap)."""
    env = {k: v for k, v in roaming.items() if k.upper() != "HOME"}
    assert seen(shell(world, 'rm -rf "$HOME/AppData/Roaming/mkway"', env=env)) == LOGGED


@pytest.mark.parametrize("command", [
    pytest.param('rm -rf "${XDG_CONFIG_HOME:-$HOME/.config}/mkway"', id="colon-minus"),
    pytest.param('rm -rf "${XDG_CONFIG_HOME:=$HOME/.config}/mkway"', id="colon-equals"),
    pytest.param('rm -rf "${XDG_CONFIG_HOME-$HOME/.config}/mkway"', id="minus"),
])
def test_a_default_form_with_the_name_unset_expands_its_default_again(world, home_only, command):
    """Catches: E99 (H3, R260g), `${X:-d}`, `${X:=d}` and `${X-d}` with X unset that are not expanded (the text d is expanded once more), so the removal of the parent folder is only logged."""
    assert by_class(shell(world, command, env=home_only)) == DENY_SHELL + CLASS_ONLY


def test_a_default_form_with_the_name_set_uses_its_value(world, xdg_other):
    """Catches: E100 (H3, R260g), `${X:-d}` with X set that takes the default d instead of the value of X (the guarded folder is under X here, so only its value reaches it)."""
    assert by_class(shell(world, 'rm -rf "${XDG_CONFIG_HOME:-$HOME/.config}/mkway"', env=xdg_other)) == DENY_SHELL + CLASS_ONLY


def test_a_default_form_with_the_name_set_is_judged_on_its_value(world, xdg_other):
    """Checks: E101 (H3), the nearest allow of E100: a file beside the folder, named through the same form, is not refused (the core logs the variable)."""
    assert seen(shell(world, 'echo x >> "${XDG_CONFIG_HOME:-$HOME/.config}/mkway/x"', env=xdg_other)) == LOGGED


@pytest.mark.parametrize("command, want", [
    pytest.param('rm -rf "${XDG_CONFIG_HOME:-$HOME/.config}/mkway"', DENY_SHELL + CLASS_ONLY, id="colon-minus-takes-the-default-for-an-empty-name"),
    pytest.param('rm -rf "${XDG_CONFIG_HOME-$HOME/.config}/mkway"', LOGGED + (False, False, False), id="minus-keeps-the-empty-value"),
])
def test_an_empty_name_is_unset_only_for_the_colon_forms(world, home_only, command, want):
    """Catches: E102 (H3, R260g), an empty X that `${X:-d}` takes as set (it must take d) or `${X-d}` takes as unset (it must keep the empty value)."""
    assert by_class(shell(world, command, env=dict(home_only, XDG_CONFIG_HOME=""))) == want


def test_a_plus_form_gives_its_word_when_the_name_is_set_and_nothing_when_not(world, home_only):
    """Catches: E103 (H3, R260g), `${X:+w}` that is not expanded: w when X is set (here the parent folder), nothing when it is not (the path is then only logged)."""
    command = 'rm -rf "${APPDATA:+$APPDATA}/mkway"'
    got = (by_class(shell(world, command, env=dict(home_only, APPDATA=str(world.base)))), seen(shell(world, command, env=home_only)))
    assert got == (DENY_SHELL + CLASS_ONLY, LOGGED)


def test_a_question_form_gives_the_value(world):
    """Catches: E104 (H3, R260g), `${X:?d}` that is not expanded: it is the value of X."""
    assert by_class(shell(world, 'rm -rf "${APPDATA:?gone}/mkway"')) == DENY_SHELL + CLASS_ONLY


@pytest.mark.parametrize("command", [
    pytest.param('rm -rf "${APPDATA%/*}/mkway"', id="percent"),
    pytest.param('rm -rf "${APPDATA#/}/mkway"', id="hash"),
    pytest.param('rm -rf "${APPDATA//a/b}/mkway"', id="slash-slash"),
    pytest.param('rm -rf "${APPDATA^^}/mkway"', id="caret"),
])
def test_the_trim_replace_and_case_operators_stay_unexpanded(world, command):
    """Checks: E105 (H3, H4), `%`, `#`, `//` and `^` operators are not expanded: the path is only logged (a named gap)."""
    assert seen(shell(world, command)) == LOGGED


def test_an_unexpanded_operator_that_names_the_folder_is_refused_by_the_raw_text(world):
    """Checks: E112 (H3), `${APPDATA%/Roaming}/Roaming/mkway/upgrade` (an operator that is not expanded) names the folder in its text, so the raw-text rule refuses it as today: only the paths that do not name it are the logged gap of E105."""
    assert seen(shell(world, "echo x >> ${APPDATA%/Roaming}/Roaming/mkway/upgrade")) == DENY_SHELL


def test_a_re_point_that_lands_in_the_folder_is_only_logged(world, home_only):
    """Checks: E106 (H4), `HOME=$HOME/.config; rm -rf "$HOME/mkway"` is judged on the environment's HOME, not the re-pointed one, so it is only logged (a named gap of the qualifier); when the path names `mkway/upgrade` the raw-text rule refuses it, as today."""
    got = (seen(shell(world, 'HOME=$HOME/.config; rm -rf "$HOME/mkway"', env=home_only)),
           seen(shell(world, 'HOME=$HOME/.config; rm -rf "$HOME/mkway/upgrade"', env=home_only)))
    assert got == (LOGGED, DENY_SHELL)


@pytest.mark.parametrize("tool, command, want", [
    pytest.param("Bash", 'rm -rf "$(echo $APPDATA)/mkway"', LOGGED, id="command-substitution"),
    pytest.param("PowerShell", "Remove-Item -Recurse (Join-Path $env:APPDATA 'mkway')", ALLOW, id="join-path"),
    pytest.param("PowerShell", win("Remove-Item -Recurse ([Environment]::GetEnvironmentVariable('APPDATA') + '|mkway')"), ALLOW,
                 id="get-environment-variable"),
])
def test_a_path_built_by_a_command_is_not_expanded(world, tool, command, want):
    """Checks: E107 (H4), a path built by `$(...)`, `Join-Path` or `[Environment]::GetEnvironmentVariable` is not expanded: the Bash substitution is logged, the two PowerShell expressions are not read as a path at all and are allowed (named gaps)."""
    assert seen(shell(world, command, tool)) == want


@pytest.mark.parametrize("tool, command", [
    pytest.param("Bash", '[ "$APPDATA" = x ] && rm -rf "$APPDATA/mkway"', id="a-test-of-the-name"),
    pytest.param("Bash", 'echo --home=1; rm -rf "$APPDATA/mkway"', id="an-option-that-ends-in-home"),
    pytest.param("Bash", 'echo "see http://h/?APPDATA=1"; rm -rf "$APPDATA/mkway"', id="the-name-in-a-url"),
    pytest.param("Bash", 'echo "please read APPDATA"; rm -rf "$APPDATA/mkway"', id="the-word-read-in-prose"),
    pytest.param("Bash", 'declare APPDATA=x; rm -rf "$APPDATA/mkway"', id="declare"),
    pytest.param("Bash", 'local APPDATA=x; rm -rf "$APPDATA/mkway"', id="local"),
    pytest.param("Bash", 'typeset APPDATA=x; rm -rf "$APPDATA/mkway"', id="typeset"),
    pytest.param("PowerShell", win("Set-Variable APPDATA x; Remove-Item -Recurse $env:APPDATA|mkway"), id="set-variable"),
    pytest.param("PowerShell", win("Set-Content Env:APPDATA x; Remove-Item -Recurse $env:APPDATA|mkway"), id="set-content-env"),
    pytest.param("PowerShell", win("${env:APPDATA}='x'; Remove-Item -Recurse $env:APPDATA|mkway"), id="braced-env-assignment"),
])
def test_the_forms_the_review_listed_as_binding_or_mentioning_a_name_are_refused(world, tool, command):
    """Catches: E108 (H5, R260g), each input of the second and third review that mentions or binds APPDATA (a test, an option, a URL, prose, declare, local, typeset, Set-Variable, Set-Content Env:, a braced assignment) and that must be refused on the real folder."""
    assert by_class(shell(world, command, tool)) == DENY_SHELL + CLASS_ONLY


@pytest.mark.parametrize("command", [
    pytest.param('read -r home; rm -rf "$HOME/.config/mkway/upgrade"', id="read-a-lower-case-name"),
    pytest.param('echo export HOME; rm -rf "$HOME/.config/mkway/upgrade"', id="the-word-export-in-prose"),
])
def test_the_home_forms_the_review_listed_are_refused(world, home_only, command):
    """Catches: E109 (H5, R260g), `read -r home` and `echo export HOME` (the third review) that switch the expansion of HOME off."""
    assert by_class(shell(world, command, env=home_only)) == DENY_SHELL + CLASS_ONLY


def test_a_file_beside_the_folder_through_ni_is_only_logged(world):
    """Checks: E110 (H5), `ni $env:APPDATA|mkway|x` as the second review wrote it names a file beside the folder: the class is none, the core logs the variable."""
    assert seen(shell(world, win("ni $env:APPDATA|mkway|x"), "PowerShell")) == LOGGED


def test_a_tilde_override_is_not_a_guard_entry(world, monkeypatch):
    """Checks: E111 (H5), `MKWAY_UPGRADE_DIR=~/up` is a relative text for the command's reader and is not a guard entry (the first review, item 11): the default folder only."""
    monkeypatch.setenv("MKWAY_UPGRADE_DIR", "~/up")
    got = [t.entries for t in locks.core_targets(world.root, world.profile, env=dict(os.environ)) if t.name == "upgrade"]
    assert got == [[world.dir.as_posix() + "/"]]


@pytest.mark.parametrize("tool, command", [
    pytest.param("Bash", 'echo "APPDATA=x"; rm -rf "$APPDATA/mkway"', id="the-assignment-text-in-an-echo"),
    pytest.param("Bash", 'git commit -m "APPDATA=x"; rm -rf "$APPDATA/mkway"', id="the-assignment-text-in-a-commit-message"),
    pytest.param("Bash", '[ $APPDATA = x ] && rm -rf "$APPDATA/mkway"', id="an-unquoted-test-of-the-name"),
    pytest.param("Bash", 'XDG_CONFIG_HOME=x; rm -rf "$APPDATA/mkway"', id="another-guarded-name-assigned-first"),
    pytest.param("PowerShell", win("$APPDATA = 'x'; Remove-Item -Recurse $env:APPDATA|mkway"), id="a-script-variable-with-spaces"),
])
def test_the_exact_inputs_of_the_second_review_that_had_no_row_are_refused(world, tool, command):
    """Checks: E114 (H5, R260g), an input the second review listed with no row of its own (the text in an echo or a commit message, an unquoted test, another of the five names assigned first, a spaced script variable) that switches the expansion off."""
    assert by_class(shell(world, command, tool)) == DENY_SHELL + CLASS_ONLY


def test_a_loop_over_a_lower_case_home_does_not_stop_the_expansion_of_home(world, home_only):
    """Checks: E115 (H5, R260g), `for home in ...` (the second review: it counted as assigning HOME on POSIX) that switches the expansion of `$HOME` off."""
    assert by_class(shell(world, 'for home in a b; do echo $home; done; rm -rf "$HOME/.config/mkway/upgrade"', env=home_only)) == DENY_SHELL + CLASS_ONLY
