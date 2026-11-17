"""Card MW-104: `mkway green record` writes one line to the green record and never rewrites it; an unreadable record refuses the
upgrade. The shell function on a real small folder under tmp_path; the owner-only refusal through the CLI is proven in
`tests/test_mw104_upgrade_e2e.py`. Synthetic values only."""
import json

import pytest

import _mw104
from _mw104 import World


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch, tmp_path):
    _mw104.hermetic(monkeypatch, tmp_path)


def fields(world, **over):
    base = {"repo": str(world.engine.resolve()), "into": "main", "branch": "t121", "from": "a" * 40, "sha": "b" * 40,
            "command": "python -m pytest", "kind": "full", "rule": None, "seconds": "42"}
    base.update(over)
    return base


def record(world, **over):
    import upgrade
    return upgrade.record_green(fields(world, **over), world.env(), engine_file=world.engine / "engine" / "mkway.py")


def seeded(tmp_path):
    world = World(tmp_path)
    world.commit("A")
    world.green("c" * 40)
    world.green("d" * 40, kind="narrow", frm="c" * 40)
    return world


@pytest.mark.parametrize("over, part", [
    pytest.param({"sha": "xyz"}, "sha must be 40 lowercase hex characters", id="bad-sha"),
    pytest.param({"kind": "half"}, "kind must be full or narrow", id="bad-kind"),
    pytest.param({"into": None}, "into is required", id="missing-field"),
    pytest.param({"seconds": "soon"}, "seconds must be a number", id="bad-seconds"),
])
def test_a_bad_green_record_is_refused_and_writes_nothing(tmp_path, over, part):
    """Catches: a green record with a bad sha, kind, seconds or a missing field that is appended, or that touches the earlier bytes."""
    world = seeded(tmp_path)
    before = world.green_file.read_bytes()
    code, text = record(world, **over)
    assert code == 1
    assert text == "green record refused: " + part
    assert world.green_file.read_bytes() == before


def test_a_good_green_record_appends_one_line(tmp_path):
    """Checks: the nearest allow of the refusals: a good record appends exactly one line and leaves every earlier byte unchanged."""
    world = seeded(tmp_path)
    before = world.green_file.read_bytes()
    code, text = record(world, kind="narrow", rule="0")
    assert code == 0, text
    after = world.green_file.read_bytes()
    assert after.startswith(before)
    added = after[len(before):].decode("utf-8")
    assert added.count("\n") == 1
    row = json.loads(added)
    assert row["sha"] == "b" * 40
    assert row["from"] == "a" * 40
    assert row["kind"] == "narrow"
    assert row["rule"] == 0
    assert row["seconds"] == 42.0
    assert row["branch"] == "t121"
    assert row["command"] == "python -m pytest"
    assert set(row) == {"kind", "repo", "into", "branch", "from", "sha", "command", "rule", "seconds", "time", "version"}


def test_a_batch_branch_list_is_stored_as_given(tmp_path):
    """Checks: a batch merge's `--branch` of several names joined by `, ` is written as one text, and the line stays one line."""
    world = seeded(tmp_path)
    code, text = record(world, branch="t121, t122")
    assert code == 0, text
    assert json.loads(world.green_file.read_text(encoding="utf-8").splitlines()[-1])["branch"] == "t121, t122"


def test_a_record_after_a_file_without_a_line_break_starts_a_new_line(tmp_path):
    """Catches: a record glued onto the last line of a file that lacks a final line break, which would lose both rows."""
    world = World(tmp_path)
    world.commit("A")
    world.cfg.mkdir(parents=True, exist_ok=True)
    world.green_file.write_bytes(b'{"old": 1}')
    code, text = record(world)
    assert code == 0, text
    lines = world.green_file.read_text(encoding="utf-8").splitlines()
    assert lines[0] == '{"old": 1}'
    assert json.loads(lines[1])["sha"] == "b" * 40
    assert len(lines) == 2


def test_an_unreadable_green_record_refuses_the_upgrade(tmp_path):
    """Catches: an upgrade that goes on when the green record cannot be read (here the path is a folder), instead of refusing."""
    world = World(tmp_path)
    a = world.commit("A", version="0.1.0", tag="v0.0.1")
    world.install_at("A")
    world.commit("B", version="0.1.1", tag="v0.0.2")
    world.cfg.mkdir(parents=True, exist_ok=True)
    world.green_file.mkdir()
    world.grant()
    before = world.customer_head()
    code, res = world.run()
    assert code == 1
    assert res["error"].startswith(f"Cannot read the green record {world.green_file} (")
    assert world.customer_head() == before
    assert a != ""
