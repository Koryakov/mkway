"""Card MW-129 (R310 3, R312): the upgrade copies the card record files of the main checkout and of every live work tree into
the shared folder, as the LAST step before the install command, also when the engine is already up to date; a dry run prints the
same plan and writes nothing; a failed copy leaves the task on the old engine with a clean tree. Real small git repositories under
tmp_path with a real linked work tree, the stub engine of the MW-104 harness. Synthetic files only."""
import json
from pathlib import Path

import pytest

import _mw104
from _mw104 import World, git

RED = "red_proof.jsonl"
T1, T2, T3 = (f"2026-11-1{n}T10:00:00.000+00:00" for n in (1, 2, 3))
A = {"time": T1, "session": "s", "card": "C-1", "tree": "t-a", "red": ["x::y"], "pins": [], "checks": [], "missing": {},
     "would_refuse": [], "mode": "trip"}
B = {**A, "time": T3, "tree": "t-b"}
D = {**A, "time": T2, "card": "C-2", "tree": "t-d"}
FILE_LINE = f"{RED}: rows found 3, copied 3, already present 0, broken lines skipped 0, turned away by the key 0"
SECOND_LINE = f"{RED}: rows found 3, copied 0, already present 3, broken lines skipped 0, turned away by the key 0"
NOOP = "the shared folder is the state folder of the main checkout: nothing to migrate"


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch, tmp_path):
    _mw104.hermetic(monkeypatch, tmp_path)


def put(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8", newline="\n")


def shared_rows(tmp_path):
    path = tmp_path / "shared" / RED
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()] if path.is_file() else []


def world_of(tmp_path, *, shared=True, latest="B"):
    """The customer repository with the root `app` installed at A (or at B, for an up-to-date run), a linked work tree `cwt`
    of it, one red row in the main state (A, B) and one in the work tree's state (D)."""
    profile = {"state": {"dir": "mkway/state", "shared_dir": str(tmp_path / "shared")}} if shared else {"state": {"dir": "mkway/state"}}
    world = World(tmp_path)
    a = world.commit("A", version="0.1.0", tag="v0.0.1", mark="a")
    world.green(a)
    if latest == "B":
        b = world.commit("B", version="0.1.1", tag="v0.0.2", mark="b")
        world.green(b)
    world.install_at("A" if latest == "B" else "A", profile=profile)
    world.grant()
    git(world.target, "worktree", "add", "-q", "-b", "other", str(tmp_path / "cwt"))
    put(world.target / "app" / "mkway" / "state" / RED, [A, B])
    put(tmp_path / "cwt" / "app" / "mkway" / "state" / RED, [D])
    return world


def test_the_upgrade_copies_the_card_records_and_prints_the_per_file_and_per_worktree_lines(tmp_path):
    """Catches: an upgrade that installs without copying, or prints no migration lines, or lists no work tree."""
    world = world_of(tmp_path)
    code, res = world.run()
    assert code == 0, res
    assert res["updated"] is True
    assert shared_rows(tmp_path) == [A, D, B]
    mig = res["migration"]
    assert mig["lines"][0] == FILE_LINE
    assert mig["files"] == [{"file": RED, "found": 3, "copied": 3, "present": 0, "skipped": 0, "turnedAway": 0}]
    assert [(Path(x["path"]).resolve(), x["state"]) for x in mig["worktrees"]] == [
        (world.target.resolve(), "read"), ((tmp_path / "cwt").resolve(), "read")]
    assert mig["dryRun"] is False and mig["noop"] is False


def test_a_second_upgrade_run_copies_nothing(tmp_path):
    """Catches: a migration that copies again on a second run of the same owner line (the engine is then up to date)."""
    world = world_of(tmp_path)
    assert world.run()[0] == 0
    code, res = world.run()
    assert code == 0, res
    assert res["upToDate"] is True
    assert res["migration"]["lines"][0] == SECOND_LINE
    assert shared_rows(tmp_path) == [A, D, B]


def test_an_up_to_date_engine_still_runs_the_migration_and_says_up_to_date(tmp_path):
    """Catches: R312, a migration that runs only when the engine is updated; an up-to-date task would keep its records in the
    work tree."""
    world = world_of(tmp_path, latest="A")
    code, res = world.run()
    assert code == 0, res
    assert res["upToDate"] is True and res["updated"] is False
    assert res["summary"] == f"The engine in {Path(res['target'])} is up to date ({world.sha('A')[:8]})."
    assert res["migration"]["lines"][0] == FILE_LINE
    assert shared_rows(tmp_path) == [A, D, B]


def test_a_dry_run_prints_the_same_plan_and_writes_nothing(tmp_path):
    """Catches: R310 3d, a dry run that writes into the shared folder, or prints no plan."""
    world = world_of(tmp_path)
    before = world.tree_state()
    code, res = world.run(dry_run=True)
    assert code == 0, res
    assert res["migration"]["lines"][0] == FILE_LINE
    assert res["migration"]["dryRun"] is True
    assert not (tmp_path / "shared").exists()
    assert world.tree_state() == before


def test_a_failed_copy_leaves_the_task_on_the_old_engine_and_the_same_line_works_again(tmp_path):
    """Catches: R310 3c, a migration that fails after the install, or leaves a half-installed tree. The way out: the same
    owner line again once the shared folder can be written."""
    world = world_of(tmp_path)
    (tmp_path / "shared").write_text("not a folder", encoding="utf-8")
    before = world.tree_state()
    lock_before = world.lock()["source_sha"]
    code, res = world.run()
    assert code == 1
    assert res["ok"] is False and res["updated"] is False
    assert res["error"].startswith("the shared card records could not be copied")
    assert world.tree_state() == before
    assert world.lock()["source_sha"] == lock_before
    (tmp_path / "shared").unlink()
    code, res = world.run()
    assert code == 0, res
    assert res["updated"] is True
    assert shared_rows(tmp_path) == [A, D, B]


def test_guard_a_failing_pre_check_copies_nothing(tmp_path):
    """GUARD (item 8 a, green from the start): the migration runs after every pre-check: a root whose install paths hold a
    change that is not the update's is refused and the shared folder stays empty."""
    world = world_of(tmp_path)
    (world.target / "app" / "mkway" / "engine").mkdir(parents=True, exist_ok=True)
    (world.target / "app" / "mkway" / "engine" / "stray.txt").write_text("x", encoding="utf-8")
    code, res = world.run()
    assert code == 1
    assert res["ok"] is False
    assert not (tmp_path / "shared").exists()


def test_the_shared_folder_comes_from_the_profile_the_upgrade_is_about_to_write(tmp_path):
    """Catches: item 8 b (R310 3 c), a migration that reads the shared folder of the old profile on disk, when the owner's
    grant names another one and the install writes that into the profile (install --shared)."""
    world = world_of(tmp_path)
    old = tmp_path / "old-shared"
    new = tmp_path / "new-shared"
    profile = json.loads((world.target / "app" / "mkway" / "profile.json").read_text(encoding="utf-8"))
    profile["state"]["shared_dir"] = str(old)
    (world.target / "app" / "mkway" / "profile.json").write_text(json.dumps(profile), encoding="utf-8")
    git(world.target, "add", "app/mkway/profile.json")
    git(world.target, "commit", "-q", "-m", "old shared folder")
    world.grant(shared=str(new))
    code, res = world.run()
    assert code == 0, res
    assert res["migration"]["sharedDir"] == str(new)
    assert [json.loads(x) for x in (new / RED).read_text(encoding="utf-8").splitlines()] == [A, D, B]
    assert not old.exists()


def test_with_no_shared_folder_the_upgrade_says_nothing_is_migrated(tmp_path):
    """Checks: the shared folder is the state folder: the step is a no-op and says so."""
    world = world_of(tmp_path, shared=False)
    code, res = world.run()
    assert code == 0, res
    assert res["migration"]["noop"] is True
    assert res["migration"]["lines"] == [NOOP]
    assert not (tmp_path / "shared").exists()
