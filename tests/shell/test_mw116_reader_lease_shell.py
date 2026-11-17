"""Card MW-116, lease (ruling R295): the allow file carries the start time of the run. `reader start` takes over a lock older than
30 minutes (an engine constant, no profile key) and records the takeover with the id `reader-lease-expired`, naming the old
run; within the 30 minutes the lock stays `reader-busy` and the way out is to wait. A real small task root; synthetic sessions."""
import datetime
import hashlib
import json

import pytest

import _engine  # noqa: F401  (puts the engine folder on the import path)
import reader_allow
from _mw116 import CARD, SESSION, allow_doc, make_world, runs_rows, start, state_of


@pytest.fixture
def world(tmp_path):
    return make_world(tmp_path)


def _age(root, minutes):
    """Rewrite the start time of the session's lock to `minutes` ago; returns the file's sha256 as it is then."""
    path = state_of(root) / "reader_allow" / f"{SESSION}.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    then = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=minutes)
    doc["started"] = then.isoformat(timespec="milliseconds")
    path.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest(), doc["started"]


def test_the_lease_is_thirty_minutes_an_engine_constant():
    """Catches: a lease taken from a profile key or set to another length."""
    assert reader_allow.LEASE_MINUTES == 30


def test_a_lock_older_than_thirty_minutes_is_taken_over_and_the_takeover_is_recorded(world):
    """Catches: a lock of a run that never ended (a crashed reader, an untrusted folder) holding the session for ever, or a
    takeover that leaves no record: the row names the old run (session, card, start time, sha256 of the old allow file)."""
    start(world)
    old_sha, old_started = _age(world, 31)
    doc = start(world)
    assert doc["files"] != [] and doc["started"] > old_started
    rows = [r for r in runs_rows(world) if r.get("kind") == "reader-lease-expired"]
    assert len(rows) == 1
    assert (rows[0]["session_id"], rows[0]["card"], rows[0]["old_started"], rows[0]["old_allow_sha256"]) == (
        SESSION, CARD, old_started, old_sha)
    assert allow_doc(world)["started"] == doc["started"]


def test_a_lock_younger_than_thirty_minutes_is_refused_and_says_to_wait(world):
    """Catches: a takeover of a run that is still within its lease (two readers at once in one session), or a refusal text
    that does not name the wait and the 30 minutes."""
    start(world)
    _age(world, 29)
    with pytest.raises(reader_allow.ReaderError) as seen:
        start(world)
    assert seen.value.reason == "reader-busy"
    assert "30 minutes" in seen.value.text and "wait" in seen.value.text
    assert [r for r in runs_rows(world) if r.get("kind") == "reader-lease-expired"] == []


def test_a_lock_whose_start_time_cannot_be_read_stays_busy(world):
    """Catches: a lock with an unreadable start time counted as expired: a time that cannot be read is never a reason to take
    a run over (fail closed)."""
    start(world)
    path = state_of(world) / "reader_allow" / f"{SESSION}.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["started"] = "not a time"
    path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(reader_allow.ReaderError) as seen:
        start(world)
    assert seen.value.reason == "reader-busy"
    assert "start time cannot be read" in seen.value.text and "mkway reader end --session" in seen.value.text
