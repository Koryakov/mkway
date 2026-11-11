"""Card MW-012, part 2: the watch marker and the trip. Synthetic task roots and synthetic gates only."""
from _engine import make_profile
from _mw012 import (calls, denied, form_entry, integrity_entry, make_root, marker, refusals, run, seed_calls,
                    state, unclassed_entry, write_marker)
import profiles

BAD = "src/bad.py"
GOOD = "src/a.py"


def test_a_watch_marker_turns_a_form_refuse_into_would_refuse(tmp_path):
    """E4 (rule 3): with a marker for the gate, a form gate still runs, its refusal becomes a `would-refuse` row with
    the same reason id and text, and the call is allowed (no output, exit 0); a call the gate allows stays an allow;
    the calls log still counts the refusal. Catches: a watch that skips the gate (no data), one that keeps blocking,
    or a row that loses the reason."""
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
    """E5 (rule 3, rule 4): a marker beside an integrity gate (explicit class, or none) changes nothing: it still
    refuses; past the trip numbers an integrity gate writes no marker. Catches: a marker that can weaken a lock, or a
    trip that a flood of refusals can force on a gate that must not degrade."""
    root = make_root(tmp_path)
    for name, e in (("i1", integrity_entry("i1")), ("u1", unclassed_entry("u1"))):
        write_marker(root, name, cause="owner")
        assert denied(run(root, [e], BAD)), name
        seed_calls(root, name, allow=13, refuse=6)
        assert denied(run(root, [e], BAD)), name
    for name in ("i1", "u1"):
        assert [r for r in refusals(root) if r["kind"] == "would-refuse"] == []
        (state(root) / "gate_mode" / f"{name}.watch").unlink()
        seed_calls(root, name, allow=13, refuse=6)
        assert denied(run(root, [integrity_entry(name)], BAD))
        assert marker(root, name) is None


def test_a_form_gate_trips_at_20_calls_with_7_refusals(tmp_path):
    """E6 (rule 4): the 20th call in the last day, with 7 refusals (0.35, above 0.34), is itself refused and writes the
    marker with cause `tripped` and its counts, and a `gate-tripped` log row with a time; the next call is a
    `would-refuse` and allowed. Catches: a trip that never fires, one that lets the tripping call through, or one
    that leaves no row."""
    root = make_root(tmp_path)
    gates = [form_entry("f1")]
    seed_calls(root, "f1", allow=13, refuse=6)
    assert denied(run(root, gates, BAD))
    data = marker(root, "f1")
    assert data["cause"] == "tripped" and (data["calls"], data["refused"]) == (20, 7) and data["time"]
    tripped = [r for r in refusals(root) if r["reason_id"] == "gate-tripped"]
    assert len(tripped) == 1 and tripped[0]["gate"] == "f1" and tripped[0]["time"] and tripped[0]["kind"] == "log"
    res = run(root, gates, BAD)
    assert (res.exit_code, res.stdout) == (0, "")
    assert [r["kind"] for r in refusals(root)].count("would-refuse") == 1


def test_no_trip_below_20_calls_or_at_or_under_the_share(tmp_path):
    """E7 (rule 4): 19 calls with 7 refusals (too few calls), 20 calls with 6 refusals (0.30, not above 0.34) and 20
    calls with 7 refusals that are all older than 24 hours (not in the window) write no marker; the call stays
    refused. Catches: an off-by-one at 20, a share compared with `>=` instead of `>`, or a window that is not 24
    hours."""
    for name, (allow, refuse, ago) in {"few": (12, 6, 30), "share": (14, 5, 30), "old": (13, 6, 60 * 30)}.items():
        root = make_root(tmp_path / name)
        gates = [form_entry("f1")]
        seed_calls(root, "f1", allow=allow, refuse=refuse, minutes_ago=ago)
        assert denied(run(root, gates, BAD)), name
        assert marker(root, "f1") is None, name


def test_error_rows_never_count_for_the_trip(tmp_path):
    """E8 (rule 4): `error` rows are neither calls nor refusals. 19 real calls (7 refused) plus an error row is not 20
    calls; 20 real calls (6 refused) plus six error rows is not a share above 0.34. Catches: a gate that crashes
    often and so trips (the owner must see a crash, not a rule that is too strict)."""
    root = make_root(tmp_path / "calls")
    seed_calls(root, "f1", allow=12, refuse=6, error=1)
    assert denied(run(root, [form_entry("f1")], BAD))
    assert marker(root, "f1") is None
    root = make_root(tmp_path / "share")
    seed_calls(root, "f1", allow=14, refuse=5, error=6)
    assert denied(run(root, [form_entry("f1")], BAD))
    assert marker(root, "f1") is None


def test_the_trip_numbers_come_from_the_profile(tmp_path):
    """E9 (rule 4): `gates.trip.min_calls` and `gates.trip.share` replace the defaults 20 and 0.34; the schema takes
    them (a whole number above 0, a number above 0) and refuses a wrong type; an unusable value in a profile that
    got past the validator falls back to the default. Catches: a number hard-coded in the gate, or a key the schema
    refuses."""
    import gatemode
    root = make_root(tmp_path, gates={"trip": {"min_calls": 3, "share": 0.5}})
    seed_calls(root, "f1", allow=1, refuse=1)
    assert denied(run(root, [form_entry("f1")], BAD))
    assert marker(root, "f1")["cause"] == "tripped"
    assert profiles.validate(make_profile(gates={"trip": {"min_calls": 3, "share": 0.5}})) == []
    for bad in ({"min_calls": 0}, {"min_calls": 2.5}, {"min_calls": "3"}, {"share": 0}, {"share": "x"},
                {"share": True}):
        errors = profiles.validate(make_profile(gates={"trip": bad}))
        assert errors and all(e.startswith("gates.trip") for e in errors), (bad, errors)
    default = (20, 0.34)
    assert gatemode.trip_settings(make_profile()) == default
    assert gatemode.trip_settings(None) == default
    assert gatemode.trip_settings(make_profile(gates={"trip": {"min_calls": 5, "share": 0.1}})) == (5, 0.1)
    for bad in ({"min_calls": 0, "share": 0}, {"min_calls": True, "share": True}, {"min_calls": "9", "share": "1"},
                "text", []):
        assert gatemode.trip_settings(make_profile(gates={"trip": bad})) == default, bad
