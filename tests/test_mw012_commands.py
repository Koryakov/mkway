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
    """Checks: a first install writes a watch marker for each form gate that is on, and none for an integrity gate. E10 rule 5"""
    # the first install (no state folder yet) writes a marker, cause installed, for owner_ask and search, the form gates
    # that are on, and for no integrity gate; a form gate the profile turns off gets none; each marker has a
    # gate-watch-installed log row with a time.
    _src, task = _install(tmp_path / "on")
    folder = _state(task) / "gate_mode"
    # changed by MW-017 (E8): the lead gate is a form gate too, so it starts in watch as well
    # changed by MW-019 (E16): the outbox write gate `outbox_check.pre` is a form gate too
    # changed by MW-018 (E12): the message gate is a form gate too
    # changed by MW-115 (decision: MW115-D1): the outbox write gate and the owner-ask gate are integrity, no marker
    # changed by MW-115 (decision: MW115-D1a, R287c): the search gate is integrity too: three markers are left
    assert sorted(p.name for p in folder.iterdir()) == ["lead.watch", "message.watch",
                                                        "ping.watch"]  # MW-076: `ping` is a form gate
    assert {_marker(task, g)["cause"] for g in ("lead", "message", "ping")} == {"installed"}
    rows = _rows(task, "gate-watch-installed")
    assert sorted(r["gate"] for r in rows) == ["lead", "message", "ping"]
    assert all(r["time"] for r in rows)
    _src, off = _install(tmp_path / "off", gates={"ping": {"on": False}})  # changed by MW-115: ping, not search
    assert sorted(p.name for p in (_state(off) / "gate_mode").iterdir()) == ["lead.watch", "message.watch"]


@pytest.mark.engine_repo
def test_a_re_install_keeps_the_modes(tmp_path):
    """Checks: an upgrade install leaves the enforcing gates out of watch and logs one row per marker. E11 rule 5"""
    # a second install writes no marker: a marker the owner removed stays removed, a marker that is there is not rewritten.
    import install
    src, task = _install(tmp_path)
    before = _marker(task, "message")  # changed by MW-115 (decision: MW115-D1): owner_ask has no marker
    (_state(task) / "gate_mode" / "ping.watch").unlink()  # changed by MW-115 (decision: MW115-D1a): ping, not search
    install.install(task, src, vcs="none")
    assert _marker(task, "ping") is None
    assert _marker(task, "message") == before
    assert len(_rows(task, "gate-watch-installed")) == 3  # changed by MW-076: ping; changed by MW-017 (E8), MW-019 and MW-018 (E12): lead, message, outbox_check.pre, owner_ask, search


def test_gate_watch_writes_an_owner_marker(tmp_path):
    """Checks: the owner's switch of a gate to watch writes a marker with cause owner and a time. E12 rule 6"""
    # the owner's mkway gate watch message writes a marker with cause owner and a gate-watch row with a time; the profile
    # is changed only by gates.message.watch_until, a date 7 days after today (MW112-D2, card MW-112).
    # (changed by MW-115, decision: MW115-D1b: message, a form gate, instead of search)
    import datetime
    root = task_root(tmp_path)
    profile = json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))
    code, out, err = cli(root, "gate", "watch", "message")
    assert code == 0, err
    assert _marker(root, "message")["cause"] == "owner"
    assert _marker(root, "message")["time"]
    rows = _rows(root, "gate-watch")
    assert [(r["gate"], r["cause"]) for r in rows] == [("message", "owner")]
    assert rows[0]["time"]
    due = (datetime.datetime.now(datetime.timezone.utc).date() + datetime.timedelta(days=7)).isoformat()
    profile.setdefault("gates", {}).setdefault("message", {})["watch_until"] = due
    assert json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8")) == profile


def test_gate_on_removes_the_marker(tmp_path):
    """Checks: a gate the owner turns on leaves watch, and the profile and the gate-on log show it. E13 rule 6"""
    # mkway gate on search removes the marker, sets gates.search.on true as before, and writes a gate-on row with a time.
    root = task_root(tmp_path, gates={"search": {"on": False}})
    write_marker(root, "search", cause="tripped")
    code, out, err = cli(root, "gate", "on", "search")
    assert code == 0, err
    assert _marker(root, "search") is None
    assert json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))["gates"]["search"]["on"] is True
    assert [r["gate"] for r in _rows(root, "gate-on")] == ["search"]
    assert _rows(root, "gate-on")[0]["time"]


def test_an_integrity_gate_never_watches(tmp_path):
    """Catches: a way to weaken a lock by hand-switching it to watch. E14 rule 6"""
    # gate watch lock is refused with integrity gates never watch, writes no marker and changes no profile.
    root = task_root(tmp_path)
    code, out, err = cli(root, "gate", "watch", "lock")
    assert code == 1
    assert "integrity gates never watch" in err
    assert _marker(root, "lock") is None
    assert not (_state(root) / "gate_mode").exists()


@pytest.mark.parametrize("cmd", [
    pytest.param("python mkway/engine/mkway.py gate watch search", id="python-path"),
    pytest.param('py -3 "mkway/engine/mkway.py" gate watch search', id="py-launcher"),
])
def test_a_session_cannot_run_gate_watch(tmp_path, cmd):
    """Catches: a session that switches its own refusing gate to watch. E15 rule 6"""
    # a session's gate watch is refused by the lock gate (owner-only-command, any spelling that gate off has) and by the
    # CLI itself when CLAUDECODE is present; no marker is written.
    root = task_root(tmp_path)
    v = gate_call(gate_lock.check, root, tool="Bash", tool_input={"command": cmd})
    assert v.kind == "refuse", cmd
    assert v.reason_id == "owner-only-command", cmd
    code, out, err = cli(root, "gate", "watch", "search", session=True)
    assert code == 1
    assert "owner-only-command" in err
    assert _marker(root, "search") is None
