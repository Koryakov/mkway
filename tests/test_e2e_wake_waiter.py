"""Card MW-078, rows X1 to X9: the inbox waiter through a REAL install and the REAL hook command line.

One scratch project is installed once for the module (as the other e2e files do): its first install carries the default
deadline; then the profile gets a short deadline (3 s, poll 1 s) and the engine is installed over it again. The waiter
is started the way Claude Code starts a Stop handler: the command line of the settings file, through the shell, with a
Stop payload on stdin. Synthetic session ids and text only."""
import json
import os
from dataclasses import dataclass

import pytest

import _wake_world as wake
from _hook_driver import install_project, make_source
import dispatch
import leads
import paths
import profiles
import startline


@dataclass
class World:
    project: object
    first: list    # the waiter handlers of the settings file after the first install
    second: list   # the same after the profile got the short deadline and the engine was installed again
    stops_first: int
    stops_second: int


def stop_handlers(project) -> list:
    """Every Stop handler of the settings file."""
    settings = json.loads((project.root / ".claude" / "settings.json").read_text(encoding="utf-8"))
    return [h for group in settings["hooks"].get("Stop", []) for h in group["hooks"]]


def waiters_of(handlers) -> list:
    return [h for h in handlers if " hook-wait" in h["command"]]


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    project = install_project(tmp_path_factory.mktemp("wake"))
    first = stop_handlers(project)
    project.profile(**{"wake.deadline_seconds": wake.DEADLINE, "wake.poll_seconds": wake.POLL})
    source = make_source(tmp_path_factory.mktemp("source"))
    project.owner("install", "--from", str(source), "--ref", "HEAD", "--root", str(project.root))
    second = stop_handlers(project)
    return World(project, waiters_of(first), waiters_of(second), len(first), len(second))


@pytest.fixture
def pool():
    processes = wake.Pool()
    yield processes
    processes.kill_all()


def _drift_items(world, settings_text, tmp_path):
    """The `hook entries` drift items of the start line's check against a copy of the settings file."""
    copy = tmp_path / "settings.json"
    copy.write_text(settings_text, encoding="utf-8")
    root = world.project.root
    profile, errors = profiles.load(paths.profile_path(root))
    manifest = dispatch.load_manifest(root / "mkway" / "engine" / "engine")  # the copy holds the whole source set
    items = startline.drift(root, profile, errors, manifest, settings=copy)
    return [i for i in items if i.startswith("hook entries")]


def _changed(world, change):
    """The settings text with `asyncRewake` of the waiter handler removed (`change` None) or set to `change`."""
    text = (world.project.root / ".claude" / "settings.json").read_text(encoding="utf-8")
    data = json.loads(text)
    for group in data["hooks"]["Stop"]:
        for handler in group["hooks"]:
            if " hook-wait" in handler["command"]:
                handler.pop("asyncRewake", None)
                if change is not None:
                    handler["asyncRewake"] = change
    return json.dumps(data, indent=2)


def test_install_writes_one_waiter_handler_with_async_rewake_and_the_default_timeout(world):
    """Checks: X1, the first install writes one Stop handler `hook-wait` with asyncRewake true and timeout 14400 plus 60."""
    (handler,) = world.first
    assert (handler["type"], handler["asyncRewake"], handler["timeout"]) == ("command", True, 14460)


def test_the_waiter_command_is_the_engine_hook_wait_with_the_isolated_interpreter(world):
    """Checks: X2, the command is the engine copy's `mkway.py hook-wait`, run with `-I -X utf8` like the other entries."""
    (handler,) = world.first
    assert handler["command"].endswith(' -I -X utf8 "${CLAUDE_PROJECT_DIR}/mkway/engine/mkway.py" hook-wait')


def test_a_reinstall_leaves_one_waiter_and_the_same_number_of_stop_handlers(world):
    """Catches: X3, a reinstall that adds a second waiter handler (the old one is owned and must be replaced)."""
    assert (len(world.second), world.stops_second) == (1, world.stops_first)


def test_a_profile_deadline_gives_the_reinstalled_handler_its_timeout(world):
    """Checks: X4, `wake.deadline_seconds` 3 in the profile: the reinstalled handler has a timeout of 3 plus 60."""
    (handler,) = world.second
    assert (handler["asyncRewake"], handler["timeout"]) == (True, 63)


def test_no_hook_entry_drift_when_the_settings_are_as_installed(world, tmp_path):
    """Checks: X5, the nearest allow of X6: the settings file as installed shows no hook entry drift."""
    text = (world.project.root / ".claude" / "settings.json").read_text(encoding="utf-8")
    assert _drift_items(world, text, tmp_path) == []


@pytest.mark.parametrize("change", [None, False])
def test_a_missing_or_changed_async_rewake_field_shows_as_drift(world, tmp_path, change):
    """Catches: X6, a drift check that ignores `asyncRewake`, so a waiter that cannot wake a session goes unnoticed."""
    items = _drift_items(world, _changed(world, change), tmp_path)
    assert items == ["hook entries: 1 missing or changed, 1 not generated"]


def test_the_real_command_with_a_lead_and_one_unacked_row_exits_2_with_that_rows_line(world):
    """Checks: X7, the settings file's own command with a lead's Stop payload and one unacked row exits 2 with its line."""
    project = world.project
    state = project.root / "mkway" / "state"
    leads.register_lead(state, "lead-1")
    leads.append_notice(state, "lead-1", "the builder result is ready")
    row_id = leads.unacked(state, "lead-1")[0]["id"]
    (handler,) = world.second
    run = project.run_command(handler["command"], project.payload("Stop", "lead-1"), 60)
    expected = (f"{row_id} notice from engine: the builder result is ready "
                f"(`mkway inbox {row_id}`, then `mkway ack {row_id}`)\n")
    assert (run.exit_code, run.stdout, run.stderr) == (2, "", expected)


def test_after_a_heartbeat_exit_a_new_stop_payload_arms_a_new_waiter(world, pool):
    """Checks: X8, after a heartbeat exit (pid file gone) the next Stop payload arms a waiter with a new pid file."""
    project = world.project
    state = project.root / "mkway" / "state"
    leads.register_lead(state, "lead-2")
    (handler,) = world.second
    pid_file = state / "wake" / "lead-2.pid"
    env = project.env(session=True)
    command = [project.bash, "-c", handler["command"]]
    payload = json.dumps(project.payload("Stop", "lead-2"))
    one = pool.spawn(command, payload, cwd=str(project.root), env=env)
    assert wake.wait_for(pid_file.is_file)
    old = pid_file.read_text(encoding="utf-8").strip()
    ended = wake.finish(one)
    two = pool.spawn(command, payload, cwd=str(project.root), env=env)
    assert wake.wait_for(lambda: pid_file.is_file() and pid_file.read_text(encoding="utf-8").strip() != old)
    assert (ended, wake.finish(two), os.path.exists(pid_file)) == (
        (2, "", wake.HEARTBEAT), (2, "", wake.HEARTBEAT), False)


def test_a_session_that_is_no_lead_and_holds_no_card_exits_0_through_the_real_command(world):
    """Catches: X9, the real command waiting for a session that is no lead and holds no card."""
    project = world.project
    (handler,) = world.second
    run = project.run_command(handler["command"], project.payload("Stop", "free-9"), 60)
    assert (run.exit_code, run.stdout, run.stderr,
            (project.root / "mkway" / "state" / "wake" / "free-9.pid").exists()) == (0, "", "", False)
