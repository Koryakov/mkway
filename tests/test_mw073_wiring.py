"""Card MW-073 (decision: R177): the shape gate is wired: manifest entry and reason id, the profile key `tests.shape.mode` in the
schema and in KEYS.md, and the mode read with `trip` as the default. Documents are read here only."""
import json

import pytest

import _engine  # noqa: F401
from _engine import REPO
from _keys_md import section_rows, unquote
import profiles

MANIFEST = REPO / "engine" / "manifest.json"
SCHEMA = REPO / "engine" / "profile.schema.json"


def test_the_manifest_declares_the_shape_gate_and_its_reason():
    """Checks: one `tests.shape` entry, shell group, both shell tools, blocking, the reason `test-shape`, on."""
    entries = json.loads(MANIFEST.read_text(encoding="utf-8"))["entries"]
    (entry,) = [e for e in entries if e["name"] == "tests.shape"]
    assert (entry["group"], entry["event"], entry["matcher"], entry["onFailure"]) == (
        "shell", "PreToolUse", "Bash|PowerShell", "block")
    assert (entry["function"], entry["reason_ids"], entry["status"]) == ("gate_test_shape:check", ["test-shape"], "on")


def test_the_mode_key_is_in_the_schema_and_in_keys_md():
    """Catches: a profile key the gate reads that the schema rejects or KEYS.md does not list."""
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    mode = schema["properties"]["tests"]["properties"]["shape"]["properties"]["mode"]
    assert mode["enum"] == ["trip", "watch"]
    added = {unquote(r[0]): r for r in section_rows("Added keys")}
    assert added["tests.shape.mode"][1:3] == ["in schema now", "`tests.shape.mode`"]


@pytest.mark.parametrize("profile, want", [
    ({}, "trip"),
    ({"tests": {}}, "trip"),
    ({"tests": {"shape": {"mode": "watch"}}}, "watch"),
    ({"tests": {"shape": {"mode": "trip"}}}, "trip"),
    ({"tests": {"shape": {"mode": "loud"}}}, "trip"),
    ({"tests": {"shape": "watch"}}, "trip"),
], ids=["no-tests", "no-shape", "watch", "trip", "unusable-word", "not-an-object"])
def test_the_mode_reads_trip_unless_the_profile_says_watch(profile, want):
    """Checks: `watch` is the only word that changes the mode; any missing or unusable value reads as `trip`."""
    assert profiles.shape_mode(profile) == want
