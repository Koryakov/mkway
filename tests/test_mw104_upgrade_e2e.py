"""Card MW-104, end to end: the owner-only check through the CLI, and the real engine upgrading a real task root. The engine
repository is built by copying the files of the running checkout on disk (the install set plus release.json) into tmp_path;
the customer repository is built there too; the upgrade folder, the app data folders and git's config point there as well
(`_mw104.hermetic`). Every subprocess runs without CLAUDECODE (the owner's terminal). Synthetic data only."""
import contextlib
import io
import json
import sys

import pytest

import _mw104
from _mw104 import git, out, sh

pytestmark = pytest.mark.e2e

FULL_DISPLAY = "python -m pytest -n auto --dist loadgroup --cov=engine --cov-branch --cov-report=term"
SESSION = {"CLAUDECODE": "1"}
GREEN_ARGS = ["green", "record", "--repo", "x", "--into", "main", "--branch", "t1", "--from", "a" * 40, "--sha", "b" * 40,
              "--command", "pytest", "--kind", "full"]


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch, tmp_path):
    _mw104.hermetic(monkeypatch, tmp_path)


def main_of(argv, env):
    """`mkway.main(argv, env)` in process: (exit code, stdout, stderr)."""
    import mkway
    so, se = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(so), contextlib.redirect_stderr(se):
        code = mkway.main(argv, env=env)
    return code, so.getvalue(), se.getvalue()


@pytest.mark.parametrize("argv, what", [
    pytest.param(["upgrade", "--target", "x"], "upgrade", id="upgrade"),
    pytest.param(GREEN_ARGS, "green record", id="green-record"),
])
def test_upgrade_and_green_record_are_refused_in_a_session(tmp_path, argv, what):
    """Catches: `upgrade` or `green record` that runs while CLAUDECODE is present (even the empty value), where the owner's grant must never be used."""
    code, _out, err = main_of(argv, {**SESSION, "PATH": ""})
    assert code == 1
    assert f"owner-only-command: `mkway {what}` is the owner's command" in err
    assert not (tmp_path / "upgrade-dir").exists()


@pytest.mark.parametrize("marker", [pytest.param("1", id="a-value"), pytest.param("", id="the-empty-value")])
def test_the_marker_is_refused_with_any_value(tmp_path, marker):
    """Catches: a session marker with the empty value that slips past the owner check (the CLI tripwire reads presence, not truth)."""
    code, _out, err = main_of(["upgrade", "--target", "x"], {"CLAUDECODE": marker})
    assert code == 1
    assert "owner-only-command" in err


def test_upgrade_and_green_record_pass_the_owner_check_without_the_marker(tmp_path, monkeypatch):
    """Checks: the nearest allow of the owner-only refusal: with no marker both commands run; upgrade prints one JSON object and exits 1 on a refusal, green record appends a row."""
    import upgrade
    world = _mw104.World(tmp_path)
    world.commit("A", version="0.1.0")
    world.grant()
    monkeypatch.setattr(upgrade, "ENGINE_FILE", world.engine / "engine" / "mkway.py")
    env = _mw104.env_for_children()
    code, printed, err = main_of(["upgrade", "--target", str(world.target)], env)
    assert code == 1
    assert "owner-only-command" not in err
    answer = json.loads(printed)
    assert answer["ok"] is False
    code, _printed, err = main_of([*GREEN_ARGS[:3], str(world.engine), *GREEN_ARGS[4:]], env)
    assert code == 0, err
    assert len(_mw104.lines_of(world.green_file)) == 1


# ---- the real engine -------------------------------------------------------------------------------------------------------------

def e2e_world(tmp_path):
    """The real engine at commit A (v0.0.1) installed in a customer repository; commit B (v0.0.2) green by the real command."""
    engine = _mw104.real_engine(tmp_path)
    branch = json.loads((engine / "release.json").read_text(encoding="utf-8"))["branch"]
    git(engine, "add", "-A")
    git(engine, "commit", "-q", "-m", "A")
    git(engine, "tag", "v0.0.1")
    a = out(engine, "rev-parse", "HEAD")
    (engine / "tests" / "_mw104_marker.txt").write_text("b\n", encoding="utf-8")
    git(engine, "add", "-A")
    git(engine, "commit", "-q", "-m", "B")
    git(engine, "tag", "v0.0.2")
    b = out(engine, "rev-parse", "HEAD")
    customer = tmp_path / "customer"
    git(tmp_path, "init", "-q", "-b", "main", str(customer))
    git(customer, "commit", "-q", "--allow-empty", "-m", "start")
    root = customer / "app"
    root.mkdir()
    env = _mw104.env_for_children()
    sh([sys.executable, engine / "engine" / "mkway.py", "install", "--from", engine, "--ref", a, "--root", root, "--commit"],
       root, env=env)
    sh([sys.executable, root / "mkway" / "engine" / "mkway.py", "ledger", "add", "--card", "-", "--topic", "setup", "--quote",
        "the start row", "--source", "test", "--by", "tool:test", "--root", root], root, env=env)
    git(customer, "add", "-A")
    git(customer, "commit", "-q", "-m", "ledger")
    record = sh([sys.executable, engine / "mkway.py", "green", "record", "--repo", engine, "--into", branch, "--branch", "t1",
                 "--from", a, "--sha", b, "--command", FULL_DISPLAY, "--kind", "full", "--seconds", "1"], engine, env=env)
    cfg = tmp_path / "upgrade-dir"
    (cfg / "policy.json").write_text(json.dumps({"target": str(customer), "root": "app"}), encoding="utf-8")
    return engine, customer, root, a, b, env, record


def upgrade_cli(engine, customer, env, *flags):
    return sh([sys.executable, engine / "mkway.py", "upgrade", "--target", customer, "--root", "app", *flags], engine, env=env,
              check=False)


def test_e2e_a_dry_run_lists_checks_and_changes_nothing(tmp_path):
    """Checks: run 1: the real engine's dry run lists the checks and the commands, prints one JSON object, and leaves the customer repository and the grant as they were."""
    engine, customer, _root, _a, b, env, _record = e2e_world(tmp_path)
    grant = (tmp_path / "upgrade-dir" / "policy.json").read_bytes()
    state = (out(customer, "rev-parse", "HEAD"), out(customer, "status", "--porcelain", "--untracked-files=all"))
    proc = upgrade_cli(engine, customer, env, "--dry-run")
    assert proc.returncode == 0, (proc.stdout, proc.stderr)
    answer = json.loads(proc.stdout)
    assert answer["ok"] is True
    assert answer["updated"] is False
    assert answer["release"] == "v0.0.2"
    assert answer["newSha"] == b
    assert len(answer["checks"]) >= 6
    assert len(answer["commands"]) == 4
    assert (out(customer, "rev-parse", "HEAD"), out(customer, "status", "--porcelain", "--untracked-files=all")) == state
    assert (tmp_path / "upgrade-dir" / "policy.json").read_bytes() == grant


def test_e2e_the_real_upgrade_picks_the_proven_release(tmp_path):
    """Checks: run 2: the real upgrade picks v0.0.2, makes one commit with only the printed paths plus the ledger, leaves a pre-staged file staged and out, and records the ledger row by the tool with the release."""
    engine, customer, root, a, b, env, _record = e2e_world(tmp_path)
    (customer / "other.txt").write_text("other\n", encoding="utf-8")
    git(customer, "add", "other.txt")
    head = out(customer, "rev-parse", "HEAD")
    proc = upgrade_cli(engine, customer, env)
    assert proc.returncode == 0, (proc.stdout, proc.stderr)
    answer = json.loads(proc.stdout)
    assert answer["updated"] is True
    assert answer["release"] == "v0.0.2"
    assert out(customer, "rev-parse", "HEAD~1") == head
    files = out(customer, "show", "--name-only", "--format=", "HEAD").splitlines()
    fixed = {"app/mkway/mkway.lock", "app/mkway/ledger/ledger.md"}
    printed = fixed | {"app/.claude/settings.json", "app/mkway/.gitignore", "app/mkway/.gitattributes"}
    assert fixed <= set(files)
    assert {".claude/settings.json", "mkway/.gitignore", "mkway/.gitattributes"} <= set(answer["files"])
    assert all(f in printed or f.startswith("app/mkway/engine/") for f in files), files
    assert out(customer, "diff", "--cached", "--name-only") == "other.txt"
    assert json.loads((root / "mkway" / "mkway.lock").read_text(encoding="utf-8"))["source_sha"] == b
    ledger = (root / "mkway" / "ledger" / "ledger.md").read_text(encoding="utf-8")
    assert "tool:mkway-upgrade" in ledger
    assert f"engine updated {a[:8]} -> {b[:8]}, grant policy.json, dry run ok, release v0.0.2, upgrade dir " in ledger
    assert (root / "mkway" / "engine" / "mkway.py").is_file()
    assert (tmp_path / "hermetic" / "tmp").is_dir()
    assert list((tmp_path / "hermetic" / "tmp").iterdir()) == []
