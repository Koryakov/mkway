"""Card MW-078, rows K1 to K10 and D1 to D5: the profile keys `wake.mode`, `wake.deadline_seconds`, `wake.poll_seconds`,
their defaults, their KEYS.md rows, the manifest entry of the waiter and the README paragraph. Synthetic profile only."""
import copy
import json
import re
import sys

import pytest

from _engine import REPO
from _keys_md import section_rows, unquote

sys.path.insert(0, str(REPO / "engine"))

import profiles  # noqa: E402
import schema_check  # noqa: E402

BASE = json.loads((REPO / "fixtures" / "synthetic" / "profile_depth2.json").read_text(encoding="utf-8"))


def _added_row(key):
    return [r for r in section_rows("Added keys") if unquote(r[0]) == key][0]


def _default_counts():
    """(rows «in defaults.json», rows «later (...)») of the engine defaults table."""
    rows = section_rows("Engine defaults")
    return (sum(1 for r in rows if r[2] == "in defaults.json"), sum(1 for r in rows if r[2].startswith("later (")))


def _split_line():
    text = (REPO / "engine" / "KEYS.md").read_text(encoding="utf-8")
    return [x for x in text.splitlines() if x.startswith("Split: ") and "defaults.json" in x][0]


def _readme_paragraph():
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    return [p for p in readme.split("\n\n") if "hook-wait" in p][0]


def _with(value):
    profile = copy.deepcopy(BASE)
    profile["wake"] = value
    return schema_check.check(profile)


def test_all_three_wake_keys_are_valid():
    """Checks: K1, the three keys with usable values are accepted."""
    assert _with({"mode": "off", "deadline_seconds": 3, "poll_seconds": 0.5}) == []


def test_an_empty_wake_object_is_valid():
    """Checks: K2, every key has a default, so the object may be empty."""
    assert _with({}) == []


def test_a_mode_that_is_neither_on_nor_off_is_refused():
    """Catches: K3, a mode the waiter does not know."""
    assert _with({"mode": "sometimes"}) == ["wake.mode: not one of on, off"]


def test_a_deadline_of_zero_is_refused():
    """Catches: K4, a deadline of 0 s (a waiter that sends a heartbeat at once and loops)."""
    assert _with({"deadline_seconds": 0}) == ["wake.deadline_seconds: must be greater than 0"]


def test_a_poll_that_is_not_a_number_is_refused():
    """Catches: K5, a poll written as text."""
    assert _with({"poll_seconds": "5"}) == ["wake.poll_seconds: expected number"]


def test_an_unknown_wake_key_is_refused():
    """Catches: K6, a misspelt key in the object, which would silently keep the default."""
    assert _with({"deadline": 5}) == ["wake.deadline: not allowed here"]


def test_the_wake_settings_of_a_profile_with_no_wake_object_are_the_defaults():
    """Checks: K7, mode on, a deadline of 14400 s (four hours), a poll of 5 s."""
    assert profiles.wake_settings({}) == {"mode": "on", "deadline_seconds": 14400, "poll_seconds": 5}


@pytest.mark.parametrize("raw", [{"mode": "x", "deadline_seconds": True, "poll_seconds": -1},
                                 {"mode": 1, "deadline_seconds": "9", "poll_seconds": 0},
                                 {"deadline_seconds": 0, "poll_seconds": None}])
def test_an_unusable_wake_value_takes_its_default(raw):
    """Catches: K8, a gate-side reader that fails on a bad value instead of using the default."""
    assert profiles.wake_settings({"wake": raw}) == {"mode": "on", "deadline_seconds": 14400, "poll_seconds": 5}


def test_a_usable_wake_value_is_kept():
    """Checks: K9, the nearest allow of K8: usable values are read as written."""
    assert profiles.wake_settings({"wake": {"mode": "off", "deadline_seconds": 7, "poll_seconds": 0.5}}) == {
        "mode": "off", "deadline_seconds": 7, "poll_seconds": 0.5}


def test_defaults_json_holds_the_same_wake_values():
    """Checks: K10, the engine defaults file and the accessor agree."""
    data = json.loads((REPO / "engine" / "defaults.json").read_text(encoding="utf-8"))
    assert data["wake"] == {"mode": "on", "deadline_seconds": 14400, "poll_seconds": 5}


@pytest.mark.parametrize("key, default", [("wake.mode", "default `on`"), ("wake.deadline_seconds", "default `14400`"),
                                          ("wake.poll_seconds", "default `5`")])
def test_keys_md_has_a_row_for_each_wake_key_with_its_default(key, default):
    """Checks: K11, each key is a row of the added keys, «in schema now», with its default in the values cell."""
    row = _added_row(key)
    assert (row[1], unquote(row[2]), default in row[3]) == ("in schema now", key, True)


def test_the_closing_count_line_of_the_engine_defaults_counts_the_rows():
    """Catches: D1, the `Split:` line of the engine defaults that no longer matches its table (30 and 7 now, changed by MW-103)."""
    kept, later = _default_counts()
    assert (kept, later, _split_line().startswith("Split: 30 in `defaults.json`, 7 later, 0 not established")) == (
        30, 7, True)


@pytest.mark.parametrize("key", ["mode", "deadline_seconds", "poll_seconds"])
def test_each_wake_default_is_a_row_of_the_engine_defaults(key):
    """Checks: D2, the engine defaults table lists the key as «in defaults.json»."""
    rows = {(unquote(r[0]), unquote(r[1])): r[2] for r in section_rows("Engine defaults")}
    assert rows[("wake", key)] == "in defaults.json"


def _manifest_waiters():
    entries = json.loads((REPO / "engine" / "manifest.json").read_text(encoding="utf-8"))["entries"]
    return [e for e in entries if e.get("waiter")]


def test_the_manifest_has_one_waiter_entry_on_the_stop_event():
    """Checks: D3, one entry `inbox_waiter`, event Stop, group `wake`, no function, no reason id, on by default."""
    (entry,) = _manifest_waiters()
    assert (entry["name"], entry["event"], entry["group"], entry["function"], entry["reason_ids"],
            entry["default_on"], entry["status"]) == ("inbox_waiter", "Stop", "wake", None, [], True, "on")


def test_the_manifest_groups_name_the_wake_group_with_no_blocking():
    """Checks: D4, the group table has `wake` and a failure of the waiter never blocks."""
    data = json.loads((REPO / "engine" / "manifest.json").read_text(encoding="utf-8"))
    assert data["groups"]["wake"] == {}


@pytest.mark.engine_repo  # the README is not copied by install
def test_the_readme_has_a_paragraph_on_the_inbox_waiter():
    """Checks: D5, the paragraph names the field, the three keys and the heartbeat line."""
    paragraph = _readme_paragraph()
    found = set(re.findall(r"asyncRewake|wake\.mode|wake\.deadline_seconds|wake\.poll_seconds|no new rows, end the turn",
                           paragraph))
    assert found == {"asyncRewake", "wake.mode", "wake.deadline_seconds", "wake.poll_seconds",
                     "no new rows, end the turn"}
