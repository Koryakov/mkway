"""Card MW-012, part 3: a first install starts the form gates in watch; the owner's `gate watch` and `gate on`.
Synthetic task roots and engine sources under the pytest temp folder only."""
import json

import pytest

from _engine import cli, gate_call, jsonl, make_profile, task_root, write_profile
from _mw012 import write_marker
import gate_lock

STATE = ("mkway", "state")


def _state(root):
    return root.joinpath(*STATE)


def _marker(root, gate):
    path = _state(root) / "gate_mode" / f"{gate}.watch"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def _rows(root, reason):
    return [r for r in jsonl(_state(root) / "refusals.jsonl") if r["reason_id"] == reason]


def _install(tmp_path, gates=None):
    from test_install import make_source, make_task
    import install
    src = make_source(tmp_path, vcs="none")
    task = make_task(tmp_path, vcs="none")
    write_profile(task, make_profile(gates))
    install.install(task, src, vcs="none")
    return src, task


@pytest.mark.engine_repo  # the engine repository is the install source
def test_a_first_install_writes_a_watch_marker_for_each_form_gate_that_is_on(tmp_path):
    """E10 (rule 5): the first install (no state folder yet) writes a marker, cause `installed`, for `owner_ask` and
    `search`, the form gates that are on, and for no integrity gate; a form gate the profile turns off gets none; each
    marker has a `gate-watch-installed` log row with a time. Catches: a new rule that blocks from its first day, or a
    marker beside a lock."""
    _src, task = _install(tmp_path / "on")
    folder = _state(task) / "gate_mode"
    assert sorted(p.name for p in folder.iterdir()) == ["owner_ask.watch", "search.watch"]
    assert {_marker(task, g)["cause"] for g in ("owner_ask", "search")} == {"installed"}
    rows = _rows(task, "gate-watch-installed")
    assert sorted(r["gate"] for r in rows) == ["owner_ask", "search"] and all(r["time"] for r in rows)
    _src, off = _install(tmp_path / "off", gates={"search": {"on": False}})
    assert sorted(p.name for p in (_state(off) / "gate_mode").iterdir()) == ["owner_ask.watch"]


@pytest.mark.engine_repo
def test_a_re_install_keeps_the_modes(tmp_path):
    """E11 (rule 5): a second install writes no marker: a marker the owner removed stays removed, a marker that is
    there is not rewritten. Catches: an install (an upgrade) that quietly puts an enforcing gate back into watch."""
    import install
    src, task = _install(tmp_path)
    before = _marker(task, "owner_ask")
    (_state(task) / "gate_mode" / "search.watch").unlink()
    install.install(task, src, vcs="none")
    assert _marker(task, "search") is None
    assert _marker(task, "owner_ask") == before
    assert len(_rows(task, "gate-watch-installed")) == 2


def test_gate_watch_writes_an_owner_marker(tmp_path):
    """E12 (rule 6): the owner's `mkway gate watch search` writes a marker with cause `owner` and a `gate-watch` row
    with a time; the profile is not changed. Catches: a switch that edits the profile, or one that leaves no trace."""
    root = task_root(tmp_path)
    profile = (root / "mkway" / "profile.json").read_text(encoding="utf-8")
    code, out, err = cli(root, "gate", "watch", "search")
    assert code == 0, err
    assert _marker(root, "search")["cause"] == "owner" and _marker(root, "search")["time"]
    rows = _rows(root, "gate-watch")
    assert [(r["gate"], r["cause"]) for r in rows] == [("search", "owner")] and rows[0]["time"]
    assert (root / "mkway" / "profile.json").read_text(encoding="utf-8") == profile


def test_gate_on_removes_the_marker(tmp_path):
    """E13 (rule 6): `mkway gate on search` removes the marker, sets `gates.search.on` true as before, and writes a
    `gate-on` row with a time. Catches: a gate that stays in watch after the owner turned it on."""
    root = task_root(tmp_path, gates={"search": {"on": False}})
    write_marker(root, "search", cause="tripped")
    code, out, err = cli(root, "gate", "on", "search")
    assert code == 0, err
    assert _marker(root, "search") is None
    assert json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))["gates"]["search"]["on"] is True
    assert [r["gate"] for r in _rows(root, "gate-on")] == ["search"] and _rows(root, "gate-on")[0]["time"]


def test_an_integrity_gate_never_watches(tmp_path):
    """E14 (rule 6): `gate watch lock` is refused with «integrity gates never watch», writes no marker and changes no
    profile. Catches: a way to weaken a lock by hand-switching it to watch."""
    root = task_root(tmp_path)
    code, out, err = cli(root, "gate", "watch", "lock")
    assert code == 1 and "integrity gates never watch" in err
    assert _marker(root, "lock") is None and not (_state(root) / "gate_mode").exists()


def test_a_session_cannot_run_gate_watch(tmp_path):
    """E15 (rule 6): a session's `gate watch` is refused by the lock gate (`owner-only-command`, any spelling that
    `gate off` has) and by the CLI itself when `CLAUDECODE` is present; no marker is written. Catches: a session that
    switches its own refusing gate to watch."""
    root = task_root(tmp_path)
    for cmd in ("python mkway/engine/mkway.py gate watch search", 'py -3 "mkway/engine/mkway.py" gate watch search'):
        v = gate_call(gate_lock.check, root, tool="Bash", tool_input={"command": cmd})
        assert v.kind == "refuse" and v.reason_id == "owner-only-command", cmd
    code, out, err = cli(root, "gate", "watch", "search", session=True)
    assert code == 1 and "owner-only-command" in err
    assert _marker(root, "search") is None
