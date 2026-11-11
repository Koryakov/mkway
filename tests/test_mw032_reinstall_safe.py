"""Card MW-032: reinstall never fails half-way, check leaves nothing in the copy. Synthetic roots and engine sources
under the pytest temp folder only.

The engine source is a light one (`make_light_source`) whose one test writes a read-only file into its own pytest temp
folder, as the git object files of a test repository are on Windows: the shape of the owner's gap.
"""
import json
import os
import re
import shutil
import stat
import sys

import pytest

from _engine import REPO
import install
from test_install import clean_env, make_light_source, make_task, mkway

pytestmark = pytest.mark.engine_repo

SCRATCH_TEST = '''"""MW-032 fixture: a test that leaves a read-only file in its temp folder."""
import os
import stat


def test_leaves_a_read_only_file(tmp_path):
    folder = tmp_path / "gtask" / ".git" / "objects" / "03"
    folder.mkdir(parents=True)
    target = folder / "3e8f"
    target.write_text("x", encoding="utf-8")
    os.chmod(target, stat.S_IREAD)
'''


def _source(tmp_path):
    src = make_light_source(tmp_path)
    (src / "tests" / "test_fixture_pass.py").write_text(SCRATCH_TEST, encoding="utf-8")
    return src


def _installed(tmp_path):
    src = _source(tmp_path)
    task = make_task(tmp_path, vcs="none")
    env = clean_env(tmp_path)
    proc = mkway(task, env, "install", "--from", str(src), "--vcs", "none")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return src, task, env


def _listing(folder):
    """Every file and folder below `folder`: posix path -> size (None for a folder)."""
    found = {}
    for path in sorted(folder.rglob("*")):
        found[path.relative_to(folder).as_posix()] = path.stat().st_size if path.is_file() else None
    return found


def _writable(func, path, _exc):
    os.chmod(path, stat.S_IWRITE)
    func(path)


def _rmtree(path):
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_writable)
    else:
        shutil.rmtree(path, onerror=_writable)


def _plant_read_only(copy):
    folder = copy / ".pytest_tmp" / "test_x0" / "gtask" / ".git" / "objects" / "03"
    folder.mkdir(parents=True)
    target = folder / "3e8f"
    target.write_text("x", encoding="utf-8")
    os.chmod(target, stat.S_IREAD)
    return target


def _root_cleanup(task):
    for path in (task / "mkway" / "state" / "check" / "tmp",):
        if path.exists():
            _rmtree(path)


def test_check_leaves_nothing_in_the_copy(tmp_path):
    """E1: `mkway check` runs the copy's tests, and the copy holds the same files and folders after as before."""
    _src, task, env = _installed(tmp_path)
    copy = task / "mkway" / "engine"
    before = _listing(copy)
    proc = mkway(task, env, "check")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "tests: 1 passed" in proc.stdout
    assert _listing(copy) == before
    _root_cleanup(task)


def test_check_scratch_lives_under_the_state_folder(tmp_path):
    """E2: the read-only file the copy's test wrote is found under `<state>/check/tmp`, not under the copy."""
    _src, task, env = _installed(tmp_path)
    assert mkway(task, env, "check").returncode == 0
    scratch = task / "mkway" / "state" / "check" / "tmp"
    found = [p for p in scratch.rglob("3e8f")] if scratch.exists() else []
    assert len(found) == 1, f"the test scratch is not under {scratch}"
    assert not list((task / "mkway" / "engine").rglob("3e8f"))
    _root_cleanup(task)


def test_reinstall_after_check_succeeds(tmp_path):
    """E3: install, check, install again: exit 0, no traceback, the lock matches the copy, no leftover folder."""
    src, task, env = _installed(tmp_path)
    assert mkway(task, env, "check").returncode == 0
    proc = mkway(task, env, "install", "--from", str(src), "--vcs", "none")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "Traceback" not in proc.stdout + proc.stderr
    bundle = task / "mkway"
    lock = json.loads((bundle / "mkway.lock").read_text(encoding="utf-8"))
    assert lock["hash"] == install.copy_hash(bundle / "engine")
    assert sorted(p.name for p in bundle.iterdir() if p.name.startswith("engine")) == ["engine"]
    _root_cleanup(task)


def test_reinstall_over_a_read_only_scratch_file_succeeds(tmp_path):
    """E4: a copy that holds a read-only file under `.pytest_tmp` (what an older check left) is replaced: exit 0, no
    traceback, the planted file is gone, the new copy is complete."""
    src, task, env = _installed(tmp_path)
    copy = task / "mkway" / "engine"
    planted = _plant_read_only(copy)
    proc = mkway(task, env, "install", "--from", str(src), "--vcs", "none")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "Traceback" not in proc.stdout + proc.stderr
    assert not planted.exists() and not (copy / ".pytest_tmp").exists()
    assert (copy / "mkway.py").is_file() and (copy / "engine" / "mkway.py").is_file()
    assert sorted(p.name for p in (task / "mkway").iterdir() if p.name.startswith("engine")) == ["engine"]


def test_a_failed_removal_leaves_the_new_copy_and_names_the_leftover(tmp_path, monkeypatch):
    """E5: the old copy cannot be removed: install still ends with the new copy in place and the lock matching it,
    and one report line names the leftover folder, which holds the old copy."""
    src, task, _env = _installed(tmp_path)
    bundle = task / "mkway"
    old_marker = bundle / "engine" / "OLD-MARKER.txt"
    old_marker.write_text("old\n", encoding="utf-8")

    def refuse(*_args, **_kwargs):
        raise PermissionError(5, "Access is denied")
    monkeypatch.setattr(install.shutil, "rmtree", refuse)
    report = install.install(task, src, vcs="none")
    monkeypatch.undo()
    leftovers = [p for p in bundle.iterdir() if p.name.startswith("engine") and p.name != "engine"]
    assert len(leftovers) == 1, leftovers
    assert (leftovers[0] / "OLD-MARKER.txt").is_file()
    assert not (bundle / "engine" / "OLD-MARKER.txt").exists()
    lock = json.loads((bundle / "mkway.lock").read_text(encoding="utf-8"))
    assert lock["hash"] == install.copy_hash(bundle / "engine")
    lines = [line for line in report if leftovers[0].name in line]
    assert len(lines) == 1, report
    assert "leftover" in lines[0] and "\n" not in lines[0]


def test_a_failed_swap_leaves_the_old_copy_working(tmp_path, monkeypatch):
    """E6: the rename that puts the new copy in place fails: install refuses with one InstallError line, the old
    copy is back and unchanged (its hash matches the lock), and no staging folder is left."""
    src, task, _env = _installed(tmp_path)
    bundle = task / "mkway"
    copy = bundle / "engine"
    (copy / "OLD-MARKER.txt").write_text("old\n", encoding="utf-8")
    lock_text = (bundle / "mkway.lock").read_text(encoding="utf-8")
    json.loads(lock_text)
    # the marker is a file of the copy, so the lock hash no longer matches: record the copy as it is now
    before = _listing(copy)
    real = os.replace

    def failing(source, target, *args, **kwargs):
        if os.path.basename(os.fspath(source)) == "engine.new":
            raise PermissionError(5, "Access is denied")
        return real(source, target, *args, **kwargs)
    monkeypatch.setattr(install.os, "replace", failing)
    with pytest.raises(install.InstallError) as info:
        install.install(task, src, vcs="none")
    monkeypatch.undo()
    assert "\n" not in str(info.value)
    assert _listing(copy) == before
    assert (bundle / "mkway.lock").read_text(encoding="utf-8") == lock_text
    assert sorted(p.name for p in bundle.iterdir() if p.name.startswith("engine")) == ["engine"]


def test_register_changelog_and_card_name_the_card():
    """E8: the register row, a line under the top changelog section, the card folder; VERSION is untouched."""
    register = (REPO / "cards" / "REGISTER.md").read_text(encoding="utf-8")
    assert re.search(r"^\| MW-032 \| .*\|.*`cards/MW-032-[a-z0-9-]+`", register, re.M)
    changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    top = changelog.split("\n## 0.2.6\n", 1)[1].split("\n## ", 1)[0]
    assert re.search(r"^- MW-032: ", top, re.M)
    assert list((REPO / "cards").glob("MW-032-*/CARD.md"))
    assert (REPO / "VERSION").read_text(encoding="utf-8").strip() == "0.2.7"  # changed by MW-027: 0.2.7
