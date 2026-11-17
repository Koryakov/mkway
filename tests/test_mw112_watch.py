"""Card MW-112 part (ii) (rulings R284a, MW112-D2): a trial gate has an end date. `mkway gate watch <gate>` writes
`gates.<gate>.watch_until` into the profile (7 days from today, or `--until YYYY-MM-DD`) and a record row (gate, from, until,
session); the start line says «watch ends <date>», and after the date «watch ended: <gate>: enforce or remove» with the
would-refuse count. Synthetic task roots under tmp_path."""
import datetime
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))  # tests/: the shared helpers and `_engine`
from _engine import cli, jsonl, task_root  # noqa: E402
import dispatch  # noqa: E402
import gatemode  # noqa: E402


def _today():
    return datetime.datetime.now(datetime.timezone.utc).date()


def _profile(root):
    return json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))


def _until(root, gate="message"):
    return (_profile(root).get("gates") or {}).get(gate, {}).get("watch_until")


def _rows(root):
    return [r for r in jsonl(root / "mkway" / "state" / "refusals.jsonl") if r["reason_id"] == "gate-watch"]


def _line(root, until, today):
    manifest = dispatch.load_manifest(dispatch.ENGINE_DIR)
    profile = {"gates": {"message": {"watch_until": until}}} if until else {}
    return gatemode.watch_line(root, root / "mkway" / "state", manifest, "message", profile=profile, today=today)


def test_the_default_watch_is_seven_days(tmp_path):
    """Catches: a watch with no end date, or an end date that is not seven days from today."""
    root = task_root(tmp_path)
    assert cli(root, "gate", "watch", "message")[0] == 0
    assert _until(root) == (_today() + datetime.timedelta(days=7)).isoformat()


def test_until_sets_the_end_date(tmp_path):
    """Catches: the --until date ignored, so a trial can not be set to another length."""
    root = task_root(tmp_path)
    assert cli(root, "gate", "watch", "message", "--until", "2031-02-03")[0] == 0
    assert _until(root) == "2031-02-03"


def test_an_until_that_is_no_date_changes_nothing(tmp_path):
    """Catches: an unreadable end date written to the profile, where it would count as passed at once."""
    root = task_root(tmp_path)
    before = _profile(root)
    code, _out, err = cli(root, "gate", "watch", "message", "--until", "next-week")
    assert (code, "YYYY-MM-DD" in err, _profile(root)) == (1, True, before)


def test_the_watch_record_row_names_gate_from_until_and_session(tmp_path):
    """Catches: a watch row without its end date, so the record can not tell what the owner set."""
    root = task_root(tmp_path)
    cli(root, "gate", "watch", "message", "--until", "2031-02-03")
    (row,) = _rows(root)
    assert (row["gate"], row["from"], row["until"], "session" in row) == ("message", None, "2031-02-03", True)


def test_a_renewed_watch_row_names_the_date_it_replaces(tmp_path):
    """Catches: a renewal that writes no row, or a row that does not say which end date it replaced."""
    root = task_root(tmp_path)
    cli(root, "gate", "watch", "message", "--until", "2031-02-03")
    cli(root, "gate", "watch", "message", "--until", "2031-03-04")
    assert [(r["from"], r["until"]) for r in _rows(root)] == [(None, "2031-02-03"), ("2031-02-03", "2031-03-04")]


def test_gate_on_ends_the_date(tmp_path):
    """Catches: a gate switched on that keeps its old end date, which a later watch would read as a renewal."""
    root = task_root(tmp_path)
    cli(root, "gate", "watch", "message", "--until", "2031-02-03")
    assert cli(root, "gate", "on", "message")[0] == 0
    assert _until(root) is None


def test_the_start_line_says_when_the_watch_ends(tmp_path):
    """Catches: a start line that shows a watch with no end date."""
    root = task_root(tmp_path)
    line = _line(root, "2031-02-03", datetime.date(2031, 2, 3))
    assert "watch ends 2031-02-03" in line and "watch ended" not in line


def test_the_start_line_after_the_date_says_enforce_or_remove(tmp_path):
    """Catches: a watch that goes on silently after its date (the nearest allow is the test above, one day earlier)."""
    root = task_root(tmp_path)
    line = _line(root, "2031-02-03", datetime.date(2031, 2, 4))
    assert "watch ended: message: enforce or remove" in line and "watch ends" not in line


def test_the_ended_line_counts_the_would_refuse_rows_of_the_gate(tmp_path):
    """Catches: an ended watch that does not say what the gate would have refused."""
    root = task_root(tmp_path)
    rows = [{"time": "2031-01-01T00:00:00.000+00:00", "gate": g, "reason_id": "x-y", "kind": "would-refuse"}
            for g in ("message.send", "message.send", "other")]
    path = root / "mkway" / "state" / "refusals.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    assert "would-refuse: 2" in _line(root, "2031-02-03", datetime.date(2031, 2, 4))


@pytest.mark.parametrize("bad", ["not-a-date", 5])
def test_an_unreadable_end_date_counts_as_ended(tmp_path, bad):
    """Catches: a bad end date read as no date, so a trial gate stays in watch for ever (fail closed, as R279c)."""
    root = task_root(tmp_path)
    assert "watch ended: message: enforce or remove" in _line(root, bad, datetime.date(2031, 2, 4))
