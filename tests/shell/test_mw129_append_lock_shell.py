"""Card MW-129 (R310 1), layer shell: the append lock of `logs.append_jsonl_locked`, built like the register's lock: a marker
file BESIDE the file (never under the lock folder of the owners), a stale time, a bounded wait, a release in `finally`, a check
that the lock is still held just before the append, and a new line first when the file does not end with one. Synthetic
values only."""
import json
import os
import time

import pytest

import _engine  # noqa: F401  (puts the engine folder on the import path)
import logs


def lines(path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def adding(row):
    return lambda _text: row


def test_the_wait_and_the_stale_time_are_the_registers_numbers():
    """Checks: P1, the values of register.py:43-44 as named constants of logs.py."""
    assert (logs.APPEND_WAIT_SECONDS, logs.APPEND_STALE_SECONDS) == (5, 30)


def test_the_marker_lies_beside_the_file(tmp_path):
    """Checks: R310 1 (f), the marker is next to the file, named after it."""
    assert logs.append_lock_path(tmp_path / "sub" / "red.jsonl") == tmp_path / "sub" / "red.jsonl.lock"


def test_a_locked_append_writes_one_complete_line_and_removes_the_marker(tmp_path):
    """Catches: a lock left behind, or a row that is not one complete line."""
    path = tmp_path / "f.jsonl"
    written = logs.append_jsonl_locked(path, adding({"a": 1}))
    assert written == {"a": 1}
    assert path.read_bytes() == b'{"a": 1}\n'
    assert not logs.append_lock_path(path).exists()


def test_a_build_that_returns_none_writes_nothing_and_still_releases(tmp_path):
    """Catches: the one-row-per-key check that skips the write but keeps the lock."""
    path = tmp_path / "f.jsonl"
    assert logs.append_jsonl_locked(path, lambda _t: None) is None
    assert not path.exists()
    assert not logs.append_lock_path(path).exists()


def test_the_lock_is_released_when_the_build_raises(tmp_path):
    """Catches: R310 1 (b), a release that is not in `finally`."""
    path = tmp_path / "f.jsonl"

    def boom(_text):
        raise ValueError("x")
    with pytest.raises(ValueError):
        logs.append_jsonl_locked(path, boom)
    assert not logs.append_lock_path(path).exists()


def test_a_file_that_does_not_end_with_a_newline_gets_a_new_line_first(tmp_path):
    """Catches: R310 1 (h), a row glued to a cut-off line."""
    path = tmp_path / "f.jsonl"
    path.write_bytes(b'{"a": 1}\n{"b"')
    logs.append_jsonl_locked(path, adding({"c": 3}))
    assert path.read_bytes() == b'{"a": 1}\n{"b"\n{"c": 3}\n'


def test_a_lock_held_beyond_the_wait_raises_append_busy_and_writes_nothing(tmp_path, monkeypatch):
    """Catches: a silent drop, or a write without the lock, while another writer holds it."""
    monkeypatch.setattr(logs, "APPEND_WAIT_SECONDS", 0.2)
    path = tmp_path / "f.jsonl"
    logs.append_lock_path(path).write_text("other", encoding="utf-8")
    with pytest.raises(logs.AppendBusy):
        logs.append_jsonl_locked(path, adding({"a": 1}))
    assert not path.exists()
    assert logs.append_lock_path(path).read_text(encoding="utf-8") == "other"


def test_a_marker_released_during_the_wait_lets_the_append_through(tmp_path, monkeypatch):
    """Item W3: a writer that waits gets the lock when the holder finishes; a writer that never waits fails this."""
    monkeypatch.setattr(logs, "APPEND_WAIT_SECONDS", 5)
    path = tmp_path / "f.jsonl"
    marker = logs.append_lock_path(path)
    marker.write_text("other", encoding="utf-8")
    waits = []

    def wait_step(seconds):
        # the holder finishes during the writer's first wait: no timer, no thread, no wall clock
        waits.append(seconds)
        if marker.exists():
            marker.unlink()

    monkeypatch.setattr(logs.time, "sleep", wait_step)
    assert logs.append_jsonl_locked(path, adding({"a": 1})) == {"a": 1}
    assert len(waits) == 1  # the writer waited once; a writer that never waits fails here
    assert lines(path) == [{"a": 1}]


def test_a_stale_marker_is_taken_over_and_the_row_is_written(tmp_path):
    """Checks: the nearest allow of the busy refusal: a marker older than the stale time is another writer's dead lock."""
    path = tmp_path / "f.jsonl"
    marker = logs.append_lock_path(path)
    marker.write_text("dead", encoding="utf-8")
    old = time.time() - logs.APPEND_STALE_SECONDS - 5
    os.utime(marker, (old, old))
    assert logs.append_jsonl_locked(path, adding({"a": 1})) == {"a": 1}
    assert lines(path) == [{"a": 1}]
    assert not marker.exists()


def test_after_a_takeover_in_the_middle_the_writer_acquires_again_before_it_appends(tmp_path):
    """Catches: R310 1 (c), an append made after another writer took the stale lock over: the lock is checked again just
    before the append, and the build runs again under the new lock."""
    path = tmp_path / "f.jsonl"
    marker = logs.append_lock_path(path)
    calls = []

    def build(_text):
        calls.append(1)
        if len(calls) == 1:  # another writer takes our lock over, and its marker is stale at once
            marker.write_text("taker", encoding="utf-8")
            old = time.time() - logs.APPEND_STALE_SECONDS - 5
            os.utime(marker, (old, old))
        return {"n": len(calls)}
    assert logs.append_jsonl_locked(path, build) == {"n": 2}
    assert lines(path) == [{"n": 2}]
    assert len(calls) == 2
