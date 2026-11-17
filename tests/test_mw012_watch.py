"""Card MW-012, part 2: the watch marker and the trip. Synthetic task roots and synthetic gates only."""
import pytest

from _engine import make_profile
from _mw012 import (calls, denied, form_entry, integrity_entry, make_root, marker, refusals, run, seed_calls,
                    state, unclassed_entry, write_marker)
import gatemode
import profiles

BAD = "src/bad.py"
GOOD = "src/a.py"
DEFAULT_TRIP = (20, 0.34)


def _schema_misses():
    """The bad `gates.trip` values that the schema does not refuse with a gates.trip error."""
    misses = []
    for bad in ({"min_calls": 0}, {"min_calls": 2.5}, {"min_calls": "3"}, {"share": 0}, {"share": "x"},
                {"share": True}):
        errors = profiles.validate(make_profile(gates={"trip": bad}))
        if not (errors and all(e.startswith("gates.trip") for e in errors)):
            misses.append((bad, errors))
    return misses


def _fallback_misses():
    """The bad `gates.trip` values that do not fall back to the default trip numbers."""
    misses = []
    for bad in ({"min_calls": 0, "share": 0}, {"min_calls": True, "share": True}, {"min_calls": "9", "share": "1"},
                "text", []):
        if gatemode.trip_settings(make_profile(gates={"trip": bad})) != DEFAULT_TRIP:
            misses.append(bad)
    return misses


def test_a_watch_marker_turns_a_form_refuse_into_would_refuse(tmp_path):
    """Catches: a watch that skips the gate, one that keeps blocking, or a row that loses the reason (E4, rule 3)."""
    root = make_root(tmp_path)
    gates = [form_entry("f1")]
    assert denied(run(root, gates, BAD))  # enforcing before the marker
    write_marker(root, "f1", cause="owner")
    res = run(root, gates, BAD)
    assert (res.exit_code, res.stdout) == (0, "")
    row = [r for r in refusals(root) if r["kind"] == "would-refuse"]
    assert len(row) == 1
    assert (row[0]["gate"], row[0]["reason_id"], row[0]["message"]) == (
        "f1", "fixture-refuse", "fixture gate: refuses a bad target")
    assert run(root, gates, GOOD).stdout == ""
    assert [c["verdict"] for c in calls(root)] == ["refuse", "refuse", "allow"]


def test_an_integrity_gate_never_reads_a_marker_and_never_trips(tmp_path):
    """Catches: a marker that can weaken a lock, or a trip that a flood of refusals can force on a gate that must not degrade (E5, rule 3, rule 4)."""
    root = make_root(tmp_path)
    write_marker(root, "i1", cause="owner")
    assert denied(run(root, [integrity_entry("i1")], BAD)), "i1"
    seed_calls(root, "i1", allow=13, refuse=6)
    assert denied(run(root, [integrity_entry("i1")], BAD)), "i1"
    write_marker(root, "u1", cause="owner")
    assert denied(run(root, [unclassed_entry("u1")], BAD)), "u1"
    seed_calls(root, "u1", allow=13, refuse=6)
    assert denied(run(root, [unclassed_entry("u1")], BAD)), "u1"
    assert [r for r in refusals(root) if r["kind"] == "would-refuse"] == []
    (state(root) / "gate_mode" / "i1.watch").unlink()
    seed_calls(root, "i1", allow=13, refuse=6)
    assert denied(run(root, [integrity_entry("i1")], BAD))
    assert marker(root, "i1") is None
    assert [r for r in refusals(root) if r["kind"] == "would-refuse"] == []
    (state(root) / "gate_mode" / "u1.watch").unlink()
    seed_calls(root, "u1", allow=13, refuse=6)
    assert denied(run(root, [integrity_entry("u1")], BAD))
    assert marker(root, "u1") is None


def test_a_form_gate_trips_at_20_calls_with_7_refusals(tmp_path):
    """Catches: a trip that never fires, one that lets the tripping call through, or one that leaves no row (E6, rule 4)."""
    root = make_root(tmp_path)
    gates = [form_entry("f1")]
    seed_calls(root, "f1", allow=13, refuse=6)
    assert denied(run(root, gates, BAD))
    data = marker(root, "f1")
    assert data["cause"] == "tripped"
    assert (data["calls"], data["refused"]) == (20, 7)
    assert data["time"]
    tripped = [r for r in refusals(root) if r["reason_id"] == "gate-tripped"]
    assert len(tripped) == 1
    assert tripped[0]["gate"] == "f1"
    assert tripped[0]["time"]
    assert tripped[0]["kind"] == "log"
    res = run(root, gates, BAD)
    assert (res.exit_code, res.stdout) == (0, "")
    assert [r["kind"] for r in refusals(root)].count("would-refuse") == 1


@pytest.mark.parametrize(
    "name, allow, refuse, ago",
    [
        pytest.param("few", 12, 6, 30, id="few"),
        pytest.param("share", 14, 5, 30, id="share"),
        pytest.param("old", 13, 6, 60 * 30, id="old"),
    ],
)
def test_no_trip_below_20_calls_or_at_or_under_the_share(tmp_path, name, allow, refuse, ago):
    """Catches: an off-by-one at 20, a share compared with >= instead of >, or a window that is not 24 hours (E7, rule 4)."""
    root = make_root(tmp_path / name)
    gates = [form_entry("f1")]
    seed_calls(root, "f1", allow=allow, refuse=refuse, minutes_ago=ago)
    assert denied(run(root, gates, BAD)), name
    assert marker(root, "f1") is None, name


def test_error_rows_never_count_for_the_trip(tmp_path):
    """Catches: a gate that crashes often and so trips, when the owner must see a crash and not a rule that is too strict (E8, rule 4)."""
    root = make_root(tmp_path / "calls")
    seed_calls(root, "f1", allow=12, refuse=6, error=1)
    assert denied(run(root, [form_entry("f1")], BAD))
    assert marker(root, "f1") is None
    root = make_root(tmp_path / "share")
    seed_calls(root, "f1", allow=14, refuse=5, error=6)
    assert denied(run(root, [form_entry("f1")], BAD))
    assert marker(root, "f1") is None


def test_the_trip_numbers_come_from_the_profile(tmp_path):
    """Catches: a number hard-coded in the gate, or a key the schema refuses (E9, rule 4)."""
    root = make_root(tmp_path, gates={"trip": {"min_calls": 3, "share": 0.5}})
    seed_calls(root, "f1", allow=1, refuse=1)
    assert denied(run(root, [form_entry("f1")], BAD))
    assert marker(root, "f1")["cause"] == "tripped"
    assert profiles.validate(make_profile(gates={"trip": {"min_calls": 3, "share": 0.5}})) == []
    assert _schema_misses() == []
    assert gatemode.trip_settings(make_profile()) == DEFAULT_TRIP
    assert gatemode.trip_settings(None) == DEFAULT_TRIP
    assert gatemode.trip_settings(make_profile(gates={"trip": {"min_calls": 5, "share": 0.1}})) == (5, 0.1)
    assert _fallback_misses() == []
