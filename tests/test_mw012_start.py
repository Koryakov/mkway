"""Card MW-012, part 4: the start block names every form gate in watch. Synthetic task roots and gates only."""
import datetime
import json

from _mw012 import form_entry, integrity_entry, make_root, run, seed_calls, state, write_marker
import logs

SINCE = "2026-11-10T08:00:00.000+00:00"


def _context(root, entries):
    res = run(root, entries, event="SessionStart", group="start")
    return json.loads(res.stdout)["hookSpecificOutput"]["additionalContext"]


def _would_refuse(root, gate, *, days_ago=0):
    when = logs.now() - datetime.timedelta(days=days_ago)
    row = logs.row(session="s1", event="PreToolUse", tool="Edit", gate=gate, reason_id="fixture-refuse", target="x",
                   kind="would-refuse", message="fixture gate: refuses a bad target")
    row["time"] = when.isoformat(timespec="milliseconds")
    logs.append_jsonl(state(root) / "refusals.jsonl", row)


def test_the_start_block_has_a_line_for_each_gate_in_watch(tmp_path):
    """Checks: one start-block line for each form gate in watch, its counts read from the last 24 hours (E16, rule 7)."""
    root = make_root(tmp_path)
    write_marker(root, "f1", cause="tripped", time=SINCE)
    write_marker(root, "i1", cause="owner", time=SINCE)
    seed_calls(root, "f1", allow=13, refuse=7)
    seed_calls(root, "f1", allow=5, refuse=5, minutes_ago=60 * 30)  # older than a day: not counted
    _would_refuse(root, "f1")
    _would_refuse(root, "f1")
    # yesterday's row is not today's count
    _would_refuse(root, "f1", days_ago=1)
    _would_refuse(root, "f2")
    context = _context(root, [form_entry("f1"), form_entry("f2"), integrity_entry("i1")])
    lines = [line for line in context.splitlines() if line.startswith("gate ")]
    assert lines == [f"gate f1: WATCH since {SINCE} (tripped; 7 of 20 in 24 h); would-refuse today: 2; "
                     "log: mkway/state/refusals.jsonl"]


def test_the_gates_on_list_marks_a_gate_in_watch(tmp_path):
    """Checks: the gates on line marks a form gate in watch with (watch) (E17, rule 7)."""
    root = make_root(tmp_path)
    entries = [form_entry("f1"), form_entry("f2"), integrity_entry("i1")]
    # with no marker the block shows no (watch) at all
    assert "(watch)" not in _context(root, entries)
    write_marker(root, "f1", cause="installed", time=SINCE)
    write_marker(root, "i1", cause="owner", time=SINCE)
    # every other entry is unchanged; an integrity gate with a marker is not marked
    on = [line for line in _context(root, entries).splitlines() if line.startswith("gates on:")]
    assert len(on) == 1
    assert on[0].startswith("gates on: f1 (watch), f2, i1;")
