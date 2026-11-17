"""Card MW-104: the engine homes on real small git repositories: H0 (which repository the command runs from), H1 (the config
folder is refused inside a tree unless ignored), H3 (release.json is read from HEAD's commit, never from the working file) and
the proof that the hermetic fixture is active. Synthetic files only; every repository lies under tmp_path."""
import json
import os
from pathlib import Path

import pytest

import _mw104
from _mw104 import World, git


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch, tmp_path):
    _mw104.hermetic(monkeypatch, tmp_path)


def standard(tmp_path, **kw):
    world = World(tmp_path, **kw)
    world.standard()
    return world


# ---- H0 ---------------------------------------------------------------------------------------------------------------------------

def test_a_run_from_an_installed_copy_is_refused(tmp_path):
    """Catches: an upgrade run from an installed copy (a mkway.lock beside its engine folder) instead of the engine repository."""
    world = standard(tmp_path)
    before = world.tree_state()
    code, res = world.run(engine_file=world.root / "mkway" / "engine" / "mkway.py")
    assert code == 1
    assert res["error"] == "run mkway upgrade from the engine repository, not from an installed copy; nothing was changed"
    assert world.tree_state() == before


def test_a_run_from_a_repository_with_no_release_json_is_refused(tmp_path):
    """Catches: an upgrade run from a repository whose top holds no release.json (not an engine repository)."""
    world = standard(tmp_path)
    other = tmp_path / "not-an-engine"
    (other / "engine").mkdir(parents=True)
    (other / "engine" / "mkway.py").write_text("x = 1\n", encoding="utf-8")
    git(tmp_path, "init", "-q", "-b", "main", str(other))
    code, res = world.run(engine_file=other / "engine" / "mkway.py")
    assert code == 1
    assert res["error"] == "run mkway upgrade from the engine repository, not from an installed copy; nothing was changed"


def test_a_run_from_the_engine_repository_finds_it(tmp_path):
    """Checks: the nearest allow of the installed-copy refusal: run from the engine repository, the upgrade finds it and its checks pass."""
    world = standard(tmp_path)
    code, res = world.run(dry_run=True)
    assert code == 0, res
    assert Path(res["engine"]).resolve() == world.engine.resolve()


# ---- H1 ---------------------------------------------------------------------------------------------------------------------------

def test_an_upgrade_folder_inside_a_tree_and_not_ignored_is_refused(tmp_path):
    """Catches: a config folder inside a git working tree that does not ignore it (a grant or a green record there would travel with the repository)."""
    world = standard(tmp_path)
    inside = world.target / "cfg-dir"
    before = world.tree_state()
    code, res = world.run(env=world.env(MKWAY_UPGRADE_DIR=str(inside)))
    assert code == 1
    assert res["error"].startswith(f"the upgrade folder {inside} is inside a git working tree (")
    assert res["error"].endswith(") and is not ignored by it; put it outside every repository or ignore it; nothing was changed")
    assert world.tree_state()[:2] == before[:2]
    assert not inside.exists()


@pytest.mark.parametrize("how", [pytest.param("ignored", id="inside-a-tree-and-ignored"),
                                 pytest.param("outside", id="outside-every-tree")])
def test_an_upgrade_folder_ignored_or_outside_every_tree_is_allowed(tmp_path, how):
    """Checks: the nearest allow of the in-tree refusal: the same folder when the tree ignores it, or a folder no repository holds."""
    world = standard(tmp_path)
    folder = {"ignored": world.target / "cfg-dir", "outside": tmp_path / "outside" / "up"}[how]
    (world.target / ".gitignore").write_text("cfg-dir/\n", encoding="utf-8")
    git(world.target, "add", ".gitignore")
    git(world.target, "commit", "-q", "-m", "ignore the config folder")
    world.move_cfg(folder)
    world.grant()
    world.green(world.sha("B"))
    env = world.env(MKWAY_UPGRADE_DIR=str(folder), GIT_CEILING_DIRECTORIES=str(tmp_path))
    code, res = world.run(dry_run=True, env=env)
    assert code == 0, res
    assert res["ok"] is True


def test_the_override_is_printed_and_in_the_ledger_quote(tmp_path):
    """Checks: when the override folder is used, its path is in the answer and in the ledger quote; the default folder is named in neither quote."""
    world = standard(tmp_path)
    code, res = world.run()
    assert code == 0, res
    assert res["upgradeDir"] == str(world.cfg)
    row = [x for x in (world.target / "app" / "mkway" / "ledger" / "ledger.md").read_text(encoding="utf-8").splitlines()
           if x.startswith("{")][-1]
    assert row.count("upgrade dir " + json.dumps(str(world.cfg))[1:-1]) == 1


def test_the_default_folder_is_not_named_in_the_ledger_quote(tmp_path):
    """Checks: the nearest allow of the override rule: with no override the default folder is used and the quote has no upgrade dir part."""
    world = World(tmp_path)
    default = Path(os.environ["APPDATA" if os.name == "nt" else "XDG_CONFIG_HOME"]) / "mkway" / "upgrade"
    world.move_cfg(default)
    world.standard()
    env = {k: v for k, v in world.env().items() if k != "MKWAY_UPGRADE_DIR"}
    code, res = world.run(env=env)
    assert code == 0, res
    assert Path(res["upgradeDir"]) == default
    row = [x for x in (world.target / "app" / "mkway" / "ledger" / "ledger.md").read_text(encoding="utf-8").splitlines()
           if x.startswith("{")][-1]
    assert "upgrade dir" not in row


# ---- H3 ---------------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("how, expected", [
    pytest.param("missing", "release.json is missing at HEAD. Nothing was changed.", id="missing-at-head"),
    pytest.param("invalid", "release.json is invalid: not valid JSON (", id="invalid-at-head"),
])
def test_a_missing_or_invalid_release_json_at_head_is_refused(tmp_path, how, expected):
    """Catches: an upgrade when HEAD's commit has no release.json, or one that is not valid (a working file that is ignored or equal does not stand in)."""
    world = standard(tmp_path)
    world.commit("C", version="0.1.2", release=False, files={".gitignore": "release.json\n"} if how == "missing" else {
        "release.json": "{"}, untrack=("release.json",) if how == "missing" else ())
    before = world.tree_state()
    code, res = world.run()
    assert code == 1
    assert expected in res["error"]
    assert world.tree_state() == before


def test_a_dirty_working_release_json_is_refused_unread(tmp_path):
    """Catches: a release.json read from the working file: a changed (here invalid) working file must be refused as an unclean checkout, never read."""
    world = standard(tmp_path)
    (world.engine / "release.json").write_text("{", encoding="utf-8")
    before = world.tree_state()
    code, res = world.run()
    assert code == 1
    assert "is not clean (1 changed or untracked files). Nothing was changed." in res["error"]
    assert "release.json is invalid" not in res["error"]
    assert world.tree_state() == before


def test_a_valid_committed_release_json_is_read_from_head(tmp_path):
    """Checks: the nearest allow of the release.json refusals: a valid committed file is read from HEAD, and its branch (here `trunk`) is the one the engine must be on."""
    world = World(tmp_path, branch="trunk")
    world.standard()
    code, res = world.run(dry_run=True)
    assert code == 0, res
    assert res["branch"] == "trunk"


# ---- the hermetic fixture ---------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["MKWAY_UPGRADE_DIR", "APPDATA", "XDG_CONFIG_HOME", "HOME", "USERPROFILE", "TEMP", "TMP",
                                  "TMPDIR", "GIT_CONFIG_GLOBAL"])
def test_the_hermetic_fixture_is_active(tmp_path, name):
    """Checks: the autouse fixture points the upgrade folder, the app data folders, the home, the temp folders and git's config under tmp_path, so even a default can only land there."""
    assert Path(os.environ[name]).resolve().is_relative_to(tmp_path.resolve())
    assert os.environ["GIT_CONFIG_NOSYSTEM"] == "1"
