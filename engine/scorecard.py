"""The cost record read back (card MW-112, record R4): `mkway scorecard` prints, for the task root, what the process cost.

Read-only; every number is counted from a file in the state folder, and a file that is missing or a row that cannot be
read counts as nothing (never as zero seconds). Lines:
- `refusals <reason>: <n>`: rows of `refusals.jsonl` of kind `refuse`, per reason id (a warn, a log row and a would-refuse
  row are not refusals);
- `a/b: real catches <a>, false blocks <b>`: only when `<state>/classification.jsonl` exists; a row is
  `{"reason_id": ..., "class": "a" or "b"}` (the operator writes it; the engine never does);
- `test runs: <n> trees, <s> s in all, <s> s mean, <s> s longest`: rows of `commit_tests.jsonl` with `duration_seconds`,
  one per tree (the last row of a tree: a row appended again with the old red of a commit is the same run);
- `hook time per call: <n> calls, <ms> ms mean, <ms> ms longest`: rows of `gate_calls.jsonl` with `duration_ms`;
- `asks to the owner: <n>`: the ask files of the asks folder;
- `unreadable writes that passed and named the state folder: <n>`: log rows `write-target-unread` whose target names the
  state folder (R279d); the start line shows the same count when it is above zero.
"""
from __future__ import annotations

import json
from pathlib import Path

import asks
import gatemode
import logs
import profiles

CLASSIFICATION = "classification.jsonl"
COMMIT_TESTS = "commit_tests.jsonl"
UNREAD = "write-target-unread"


def read_rows(path) -> list:
    """The JSON objects of a jsonl file in order; a missing file, an unreadable line or a line that is no object is left out."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return []
    rows = []
    for line in text.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0 else None


def refusals_per_reason(state) -> dict:
    counts: dict = {}
    for row in read_rows(Path(state) / logs.REFUSALS):
        if row.get("kind") == "refuse" and isinstance(row.get("reason_id"), str):
            counts[row["reason_id"]] = counts.get(row["reason_id"], 0) + 1
    return dict(sorted(counts.items()))


def classification(state):
    """(real catches, false blocks) from the operator's file, or None when the file does not exist."""
    path = Path(state) / CLASSIFICATION
    if not path.is_file():
        return None
    rows = read_rows(path)
    return sum(r.get("class") == "a" for r in rows), sum(r.get("class") == "b" for r in rows)


def test_run_seconds(state) -> list:
    """The seconds of each tree's run: the last row of a tree that holds `duration_seconds`."""
    last: dict = {}
    for row in read_rows(Path(state) / COMMIT_TESTS):
        seconds = _number(row.get("duration_seconds"))
        if seconds is not None and row.get("tree") is not None:
            last[row["tree"]] = seconds
    return list(last.values())


def hook_milliseconds(state) -> list:
    return [m for m in (_number(r.get("duration_ms")) for r in read_rows(gatemode.calls_path(state))) if m is not None]


def ask_count(root, profile) -> int:
    try:
        return len(asks.all_asks(root, profile))
    except Exception:
        return 0


def unread_state_writes(root, state) -> int:
    """MW-112 (R279d): log rows `write-target-unread` whose target names the state folder (an unreadable shell write that passed)."""
    try:
        name = Path(state).resolve().relative_to(Path(root).resolve()).as_posix()
    except (OSError, ValueError):
        name = Path(state).as_posix()
    return sum(1 for r in read_rows(Path(state) / logs.REFUSALS)
               if r.get("reason_id") == UNREAD and name in str(r.get("target") or "").replace("\\", "/"))


def lines(root, profile) -> list:
    state = profiles.state_dir(root, profile)
    out = ["scorecard"]
    out += [f"refusals {reason}: {n}" for reason, n in refusals_per_reason(state).items()]
    found = classification(state)
    if found is not None:
        out.append(f"a/b: real catches {found[0]}, false blocks {found[1]}")
    seconds = test_run_seconds(state)
    if seconds:
        out.append(f"test runs: {len(seconds)} trees, {sum(seconds):.1f} s in all, {sum(seconds) / len(seconds):.1f} s mean, "
                   f"{max(seconds):.1f} s longest")
    millis = hook_milliseconds(state)
    if millis:
        out.append(f"hook time per call: {len(millis)} calls, {sum(millis) / len(millis):.1f} ms mean, {max(millis):.1f} ms longest")
    out.append(f"asks to the owner: {ask_count(root, profile)}")
    out.append(f"unreadable writes that passed and named the state folder: {unread_state_writes(root, state)}")
    return out
