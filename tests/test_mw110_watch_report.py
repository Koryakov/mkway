"""Card MW-110 (ruling R279c Q2): a `messaging.session_id_watch_until` that cannot be read counts as PASSED (the trial is over,
fail closed). Besides the refusal text, two places say so: the start line (one extra line, only when the value cannot be read)
and `mkway check` (a profile error). Synthetic task roots only."""
import json
import os

import pytest

import _engine  # noqa: F401  (puts the engine folder on the import path)
from _engine import task_root
import install
import profiles
import startline

KEY = "messaging.session_id_watch_until"


def _profile_of(root):
    return json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))


def _start_lines(root):
    text = startline.render(root, root / "mkway" / "profile.json", _profile_of(root), [], [], {"CLAUDECODE": "1"})
    return [line for line in text.splitlines() if line.startswith(KEY)]


@pytest.mark.parametrize("value", [
    pytest.param("next week", id="words"),
    pytest.param("2026-13-45", id="not-a-calendar-date"),
    pytest.param("26-11-16", id="a-short-form"),
])
def test_the_start_line_has_one_line_for_a_watch_date_that_cannot_be_read(tmp_path, value):
    """Catches: R279c Q2: a session that is never told its trial is over: one line names the key, the value as written and that
    it counts as passed."""
    root = task_root(tmp_path, messaging={"session_id_watch_until": value})
    (line,) = _start_lines(root)
    assert [f for f in (value, "not a date", "counts as passed") if f not in line] == []


@pytest.mark.parametrize("messaging", [
    pytest.param({}, id="no-key"),
    pytest.param({"session_id_watch_until": ""}, id="empty"),
    pytest.param({"session_id_watch_until": "2999-01-01"}, id="a-future-date"),
    pytest.param({"session_id_watch_until": "2020-01-01"}, id="a-past-date"),
])
def test_the_start_line_is_silent_for_a_readable_or_absent_watch_date(tmp_path, messaging):
    """Checks: the nearest allow: no extra line for no key, an empty value, or a date that can be read, past or not."""
    root = task_root(tmp_path, messaging=messaging)
    assert _start_lines(root) == []


def _check(root):
    (root / "mkway" / "engine" / "tests").mkdir(parents=True)  # an empty copy: the check's test run ends at once
    env = {k: v for k, v in os.environ.items() if k != "ENGINE_TERMS_FILE"}  # no term scan of the empty copy
    return install.check(root, env=env)


def test_mkway_check_reports_a_watch_date_that_cannot_be_read_as_a_profile_error(tmp_path):
    """Catches: R279c Q2: a check that is green with a date it cannot read: the line names the key, the value and that it counts
    as passed, and the check is not green."""
    root = task_root(tmp_path, messaging={"session_id_watch_until": "next week"})
    code, lines = _check(root)
    found = [line for line in lines if line.startswith(f"profile: {KEY}")]
    assert code != 0
    assert len(found) == 1
    assert [f for f in ("next week", "counts as passed") if f not in found[0]] == []


@pytest.mark.parametrize("messaging", [pytest.param({}, id="no-key"), pytest.param({"session_id_watch_until": "2999-01-01"}, id="a-date")])
def test_mkway_check_has_no_such_line_for_a_readable_or_absent_date(tmp_path, messaging):
    """Checks: the nearest allow: no line about the key when it is absent or can be read."""
    root = task_root(tmp_path, messaging=messaging)
    _code, lines = _check(root)
    assert [line for line in lines if KEY in line] == []


@pytest.mark.parametrize("value, expected", [
    pytest.param("next week", "next week", id="words"),
    pytest.param("2026-13-45", "2026-13-45", id="not-a-calendar-date"),
    pytest.param("", "", id="empty"),
    pytest.param("2026-12-31", "", id="a-date"),
])
def test_the_unreadable_accessor_returns_the_value_that_cannot_be_read(value, expected):
    """Catches: an accessor that hides a bad date as no expiry: it returns the text as written, and nothing for an empty or a
    readable value."""
    assert profiles.session_id_watch_unreadable({"messaging": {"session_id_watch_until": value}}) == expected


@pytest.mark.parametrize("profile", [pytest.param(None, id="no-profile"), pytest.param({}, id="no-messaging"),
                                     pytest.param({"messaging": {}}, id="no-key"), pytest.param({"messaging": "x"}, id="not-an-object")])
def test_the_unreadable_accessor_is_empty_for_an_absent_key(profile):
    """Checks: nothing is unreadable when there is nothing there."""
    assert profiles.session_id_watch_unreadable(profile) == ""
