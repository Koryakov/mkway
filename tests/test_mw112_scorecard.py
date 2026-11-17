"""Card MW-112 part (iv): the cost record (record R4) and `mkway scorecard`. gate_calls rows carry duration_ms; the scorecard
prints, per task, the refusals per reason, the a/b counts when the operator's classification file exists, the seconds per
test run, the hook time per call, the asks to the owner and the unreadable writes that passed naming the state folder.
Synthetic state folders under tmp_path; every expected line is written out by hand."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # tests/: the shared helpers and `_engine`
from _engine import cli, jsonl, task_root  # noqa: E402
import dispatch  # noqa: E402
import gatemode  # noqa: E402


def _state(root):
    return root / "mkway" / "state"


def _write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def _lines(root):
    code, out, err = cli(root, "scorecard")
    assert (code, err) == (0, "")
    return out.splitlines()


def test_append_call_writes_the_duration_it_is_given(tmp_path):
    """Catches: a calls-log row with no duration, so the hook time per call can not be read from it."""
    gatemode.append_call(tmp_path, "search", "allow", duration_ms=12.5)
    (row,) = jsonl(tmp_path / gatemode.CALLS)
    assert (row["gate"], row["verdict"], row["duration_ms"]) == ("search", "allow", 12.5)


def test_every_calls_row_of_a_real_dispatcher_run_carries_a_duration(tmp_path):
    """Catches: the dispatcher writing the calls row without the milliseconds it measured for the gate."""
    root = task_root(tmp_path)
    payload = {"session_id": "s-1", "hook_event_name": "Stop", "stop_hook_active": False}
    dispatch.run("Stop", "stop", json.dumps(payload), env={"CLAUDE_PROJECT_DIR": str(root)})
    rows = jsonl(_state(root) / gatemode.CALLS)
    assert rows and all(isinstance(r.get("duration_ms"), (int, float)) and r["duration_ms"] >= 0 for r in rows)


def test_the_scorecard_counts_the_refusals_of_each_reason(tmp_path):
    """Catches: refusals not counted per reason, or a would-refuse or warn row counted as a refusal."""
    root = task_root(tmp_path)
    base = {"gate": "g", "tool": "Edit", "session": "s", "target": "x"}
    _write(_state(root) / "refusals.jsonl", [
        {**base, "reason_id": "file-not-in-card", "kind": "refuse"}, {**base, "reason_id": "file-not-in-card", "kind": "refuse"},
        {**base, "reason_id": "lock-closed-edit", "kind": "refuse"}, {**base, "reason_id": "inbox-unacked", "kind": "warn"},
        {**base, "reason_id": "lock-closed-edit", "kind": "would-refuse"}])
    lines = _lines(root)
    assert [x for x in lines if x.startswith("refusals ")] == ["refusals file-not-in-card: 2", "refusals lock-closed-edit: 1"]


def test_the_scorecard_prints_the_a_b_counts_only_when_the_classification_file_exists(tmp_path):
    """Catches: a/b counts printed with no classification file (an invented number), or not printed when the file is there."""
    root = task_root(tmp_path)
    assert not any(x.startswith("a/b") for x in _lines(root))
    _write(_state(root) / "classification.jsonl", [{"reason_id": "r", "class": "a"}, {"reason_id": "r", "class": "a"},
                                                   {"reason_id": "r", "class": "b"}])
    assert [x for x in _lines(root) if x.startswith("a/b")] == ["a/b: real catches 2, false blocks 1"]


def test_the_scorecard_sums_the_seconds_of_each_test_run_once_per_tree(tmp_path):
    """Catches: a tree whose row was appended again (old red) counted as a second run, or a missing duration counted as zero."""
    root = task_root(tmp_path)
    _write(_state(root) / "commit_tests.jsonl", [
        {"tree": "t1", "result": "pass", "duration_seconds": 10.0},
        {"tree": "t2", "result": "fail", "duration_seconds": 30.0},
        {"tree": "t2", "result": "fail", "duration_seconds": 30.0, "old_red": []},
        {"tree": "t3", "result": "pass"}])
    assert [x for x in _lines(root) if x.startswith("test runs")] == ["test runs: 2 trees, 40.0 s in all, 20.0 s mean, 30.0 s longest"]


def test_the_scorecard_prints_the_hook_time_per_call(tmp_path):
    """Catches: a mean over the rows with no duration, or a longest call that is not the maximum."""
    root = task_root(tmp_path)
    _write(_state(root) / gatemode.CALLS, [
        {"gate": "a", "verdict": "allow", "duration_ms": 10.0}, {"gate": "b", "verdict": "allow", "duration_ms": 30.0},
        {"gate": "b", "verdict": "refuse"}])
    assert [x for x in _lines(root) if x.startswith("hook time")] == ["hook time per call: 2 calls, 20.0 ms mean, 30.0 ms longest"]


def test_the_scorecard_counts_the_asks_to_the_owner(tmp_path):
    """Catches: the asks to the owner not counted, so the fourth number of the scorecard is missing."""
    root = task_root(tmp_path)
    asks = root / "mkway" / "asks"
    asks.mkdir(parents=True, exist_ok=True)
    (asks / "one_ask.md").write_text("Request: x\n", encoding="utf-8")
    (asks / "two_ask.md").write_text("Request: y\n", encoding="utf-8")
    (asks / "notes.md").write_text("not an ask\n", encoding="utf-8")
    assert [x for x in _lines(root) if x.startswith("asks to the owner")] == ["asks to the owner: 2"]


def test_the_scorecard_counts_the_unreadable_writes_that_passed_naming_the_state_folder(tmp_path):
    """Catches: R279d: a passed unreadable write that names the state folder not counted, or one that names another folder counted."""
    root = task_root(tmp_path)
    base = {"gate": "outside", "tool": "Bash", "session": "s", "kind": "log", "reason_id": "write-target-unread"}
    _write(_state(root) / "refusals.jsonl", [
        {**base, "target": "run x > mkway/state/commit_tests.jsonl"}, {**base, "target": "run x > other/out.txt"}])
    assert [x for x in _lines(root) if x.startswith("unreadable writes")] == [
        "unreadable writes that passed and named the state folder: 1"]
