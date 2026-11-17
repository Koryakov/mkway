"""Card MW-104: the refusals of the upgrade shell that the case table of spec section 8 does not reach: a root the grant does not
list, a lock or a repository that cannot be read, a failing git or engine command, a ledger that is not tracked, a log that
cannot be written on an up-to-date run, and a green record that cannot be written. Every repository lies under tmp_path;
`_mw104.hermetic` points the upgrade folder, the app data folders, the home and git's config there too. Synthetic files only."""
import os
import sys

import pytest

import _mw104
from _mw104 import World


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch, tmp_path):
    _mw104.hermetic(monkeypatch, tmp_path)


def standard(tmp_path):
    world = World(tmp_path)
    a, b = world.standard()
    return world, a, b


def two_roots(tmp_path):
    world = World(tmp_path)
    a = world.commit("A", version="0.1.0", tag="v0.0.1")
    world.green(a)
    world.install_at("A", roots=("app", "app2"))
    b = world.commit("B", version="0.1.1", tag="v0.0.2")
    world.green(b)
    world.grant(roots=["app", "app2"], root=None)
    return world


@pytest.mark.parametrize("asked, expected", [
    pytest.param(None, "root is required: the policy lists 2 roots (app, app2); name the one to update.", id="no-root-named"),
    pytest.param("other", "root other is not in the policy's list (app, app2). Only listed roots are updated.",
                 id="a-root-not-listed"),
])
def test_a_root_that_is_not_named_or_not_listed_is_refused(tmp_path, asked, expected):
    """Catches: a grant of two roots updated with no root named, or with a root the grant does not list."""
    world = two_roots(tmp_path)
    before = world.tree_state()
    code, res = world.run(root=asked)
    assert code == 1
    assert res["error"] == expected
    assert world.tree_state() == before


@pytest.mark.parametrize("text", [pytest.param("{", id="not-json"), pytest.param("[]", id="not-an-object")])
def test_a_lock_that_is_not_a_json_object_is_refused(tmp_path, text):
    """Catches: an update over a mkway.lock that cannot be parsed or is not an object, which must be refused before anything is written."""
    world, _a, _b = standard(tmp_path)
    (world.root / "mkway" / "mkway.lock").write_text(text, encoding="utf-8")
    code, res = world.run()
    assert code == 1
    assert res["error"].startswith(f"The lock {world.root.resolve() / 'mkway' / 'mkway.lock'} cannot be read (")


def test_a_target_that_is_not_the_top_of_a_work_tree_is_refused(tmp_path):
    """Catches: a granted target that is a subfolder of a repository (not its top), where the commit would take the wrong paths."""
    world, _a, _b = standard(tmp_path)
    inner = world.root / "inner" / "mkway"
    inner.mkdir(parents=True)
    (inner / "mkway.lock").write_text((world.root / "mkway" / "mkway.lock").read_text(encoding="utf-8"), encoding="utf-8")
    world.grant(target=str(world.root), root="inner")
    code, res = world.run(target=world.root)
    assert code == 1
    assert res["error"] == f"{world.root.resolve()} is not the top folder of a git working tree."


def test_an_engine_repository_that_git_cannot_read_is_refused(tmp_path):
    """Catches: an engine repository whose index is damaged, taken as clean because the status command failed."""
    world, _a, _b = standard(tmp_path)
    (world.engine / ".git" / "index").write_bytes(b"not an index")
    code, res = world.run()
    assert code == 1
    assert res["error"].startswith(f"The engine repository {world.engine.resolve()} cannot be read (")


def test_a_task_root_that_git_cannot_read_is_refused(tmp_path):
    """Catches: a customer repository whose index is damaged, taken as free of changes because the status command failed."""
    world, _a, _b = standard(tmp_path)
    (world.target / ".git" / "index").write_bytes(b"not an index")
    code, res = world.run()
    assert code == 1
    assert res["error"].startswith(f"The task root {world.root.resolve()} cannot be read (")


def test_a_failing_archive_is_refused_before_a_write(tmp_path, monkeypatch):
    """Catches: a release whose code cannot be exported (git archive fails), which must be refused before any install."""
    import upgrade
    world, a, _b = standard(tmp_path)
    real = upgrade._git
    monkeypatch.setattr(upgrade, "_git", lambda cwd, args, env, data=False: (1, b"", "boom") if "archive" in args
                        else real(cwd, args, env, data))
    code, res = world.run()
    assert code == 1
    assert res["error"] == f"The engine repository {world.engine.resolve()} cannot be read (boom)."
    assert world.lock()["source_sha"] == a


def test_an_interpreter_that_cannot_start_is_refused(tmp_path, monkeypatch):
    """Catches: a ledger command that cannot be started (the interpreter is missing), reported as a missing --by option."""
    world, a, _b = standard(tmp_path)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "no-such-python"))
    code, res = world.run()
    assert code == 1
    assert "could not run the engine's ledger command (" in res["error"]
    assert world.lock()["source_sha"] == a


def test_a_program_that_cannot_start_has_no_exit_code(tmp_path):
    """Pins: the process helper answers no exit code and the reason when the program does not exist."""
    import upgrade
    code, out, err = upgrade._run(["no-such-program-for-the-test"], tmp_path, dict(os.environ), 5)
    assert (code, out) == (None, "")
    assert "FileNotFoundError" in err


def test_a_git_add_that_fails_commits_nothing(tmp_path):
    """Catches: a failing `git add` after the install (here an index lock held) that still leaves a commit, or no note that files were written."""
    world, _a, _b = standard(tmp_path)
    (world.target / ".git" / "index.lock").write_text("", encoding="utf-8")
    head = world.customer_head()
    code, res = world.run()
    assert code == 1
    assert "git add failed:" in res["error"]
    assert "The install may have written files in " in res["error"]
    assert world.customer_head() == head


def test_a_ledger_that_is_not_tracked_is_not_committed(tmp_path):
    """Checks: the ledger is committed only when git tracks it: an untracked ledger gets its row but is not in the commit."""
    world, _a, _b = standard(tmp_path)
    _mw104.git(world.target, "rm", "-q", "--cached", "app/mkway/ledger/ledger.md")
    _mw104.git(world.target, "commit", "-q", "-m", "stop tracking the ledger")
    code, res = world.run()
    assert code == 0, res
    assert "mkway/ledger/ledger.md" not in res["files"]
    assert "app/mkway/ledger/ledger.md" not in world.files_of("HEAD")


def test_a_log_that_cannot_be_written_on_an_up_to_date_run_is_reported(tmp_path):
    """Catches: an up-to-date run that says nothing when its log line cannot be written."""
    world = World(tmp_path)
    a = world.commit("A", version="0.1.0", tag="v0.0.1")
    world.green(a)
    world.install_at("A")
    world.grant()
    world.log_file.mkdir()
    code, res = world.run()
    assert code == 1
    assert res["error"].startswith("Cannot write the log (")


def test_a_green_record_that_cannot_be_written_is_refused(tmp_path):
    """Catches: a green record whose file cannot be written (here the path is a folder) that reports success."""
    import upgrade
    world = World(tmp_path)
    world.commit("A")
    world.cfg.mkdir(parents=True, exist_ok=True)
    world.green_file.mkdir()
    fields = {"repo": str(world.engine.resolve()), "into": "main", "branch": "t1", "from": "a" * 40, "sha": "b" * 40,
              "command": "python -m pytest", "kind": "full", "rule": None, "seconds": None}
    code, text = upgrade.record_green(fields, world.env(), engine_file=world.engine / "engine" / "mkway.py")
    assert code == 1
    assert text.startswith("green record refused: cannot write ")
