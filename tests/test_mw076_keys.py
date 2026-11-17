"""Card MW-076 (decisions: R185 to R188): the profile keys `gates.ping.mode` and `sessions.file`, the manifest entry, and the
README paragraph. Synthetic profile only."""
import copy
import json
import sys

import pytest

from _engine import REPO
from _keys_md import section_rows, unquote

sys.path.insert(0, str(REPO / "engine"))

import schema_check  # noqa: E402

BASE = json.loads((REPO / "fixtures" / "synthetic" / "profile_depth2.json").read_text(encoding="utf-8"))


def _check(**keys):
    profile = copy.deepcopy(BASE)
    profile.update(keys)
    return schema_check.check(profile)


def test_the_mode_trip_is_a_valid_gates_ping_mode():
    """Checks: `gates.ping.mode: trip` (the default) is accepted."""
    assert _check(gates={"ping": {"mode": "trip"}}) == []


def test_the_mode_watch_is_a_valid_gates_ping_mode():
    """Checks: `gates.ping.mode: watch` (the task lead's switch when the gate blocks wrongly) is accepted."""
    assert _check(gates={"ping": {"mode": "watch"}}) == []


def test_another_word_is_not_a_valid_gates_ping_mode():
    """Catches: a mode that is neither `trip` nor `watch`; the error names the key and the two words."""
    assert _check(gates={"ping": {"mode": "loud"}}) == ["gates.ping.mode: not one of trip, watch"]


def test_a_path_is_a_valid_sessions_file(tmp_path):
    """Checks: `sessions.file`, the path of mkcl's sessions.json, is accepted."""
    assert _check(sessions={"file": str(tmp_path / "sessions.json")}) == []


def test_a_number_is_not_a_valid_sessions_file():
    """Catches: a non-string `sessions.file`; the error names the key."""
    assert _check(sessions={"file": 3}) == ["sessions.file: expected string"]


def test_keys_md_names_both_keys_with_their_defaults():
    """Checks: KEYS.md has an added-keys row for each key, the mode row names trip as the default and the file row says the engine only reads it."""
    rows = {unquote(r[0]): r for r in section_rows("Added keys")}
    assert "default `trip`" in rows["gates.ping.mode"][3]
    assert "reads" in rows["sessions.file"][4]


def test_the_manifest_declares_the_three_reason_ids_of_the_ping_gate():
    """Checks: one Stop entry `ping.stop` on the gate `ping`, class form, declares the three reasons; the dispatcher loads only entries that declare reasons."""
    manifest = json.loads((REPO / "engine" / "manifest.json").read_text(encoding="utf-8"))
    (entry,) = [e for e in manifest["entries"] if e["name"] == "ping.stop"]
    assert (entry["gate"], entry["class"], entry["event"], entry["function"]) == ("ping", "form", "Stop",
                                                                                 "gate_ping:stop")
    assert entry["reason_ids"] == ["ping-not-sent", "ping-skipped", "ping-skipped-listed"]


@pytest.mark.engine_repo  # the README is not in a copy
@pytest.mark.parametrize("word", ["stop_hook_active", "gates.ping.mode", "inbox-writes.jsonl", "ping-skipped",
                                  "sessions.file"])
def test_the_readme_paragraph_on_the_ping_gate_names(word):
    """Checks: the README paragraph names the refuse-once field, the switch, the record file, the row and the key."""
    text = (REPO / "README.md").read_text(encoding="utf-8")
    start = text.index("**The builder pings its lead (MW-076")
    assert word in text[start:text.index(chr(10) * 2, start)]
