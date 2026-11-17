"""Commit checks (card MW-006), part 1: the profile keys `commit.junk`, `commit.data_patterns` and
`commit.max_file_kb`, their defaults and their KEYS.md lines. Synthetic values only."""
import copy
import json

import pytest

from _engine import FIXTURES, REPO, make_profile
from _keys_md import section_rows, unquote
import profiles
import schema_check

NOW = "in schema now"
JUNK = ["__pycache__/", "*.pyc", ".pytest_cache/", ".pytest_tmp/", "*.log", "*.tmp", "*.orig", "*.rej", ".DS_Store",
        "Thumbs.db"]
DATA = ["*.csv", "*.tsv", "*.xlsx", "*.xls", "*.parquet", "*.db", "*.sqlite", "*.sqlite3", "*.bak", "*.dump"]
BAD_COMMIT = [
    pytest.param({"junk": []}, id="junk-empty"),
    pytest.param({"junk": [""]}, id="junk-empty-item"),
    pytest.param({"junk": "*.pyc"}, id="junk-text"),
    pytest.param({"data_patterns": []}, id="data-empty"),
    pytest.param({"data_patterns": [3]}, id="data-not-text"),
    pytest.param({"max_file_kb": 0}, id="max-zero"),
    pytest.param({"max_file_kb": -1}, id="max-negative"),
    pytest.param({"max_file_kb": "big"}, id="max-text"),
    pytest.param({"nope": 1}, id="unknown-key"),
]
BAD_SETTINGS = [
    pytest.param({"junk": [], "data_patterns": [""], "max_file_kb": 0}, id="empty-and-zero"),
    pytest.param({"junk": "x", "data_patterns": 5, "max_file_kb": True}, id="wrong-types"),
    pytest.param({"max_file_kb": -3}, id="negative"),
    pytest.param({"max_file_kb": "9"}, id="text-number"),
    pytest.param("text", id="text-profile"),
    pytest.param([], id="list-profile"),
]
KEYS_MD_CASES = (
    [pytest.param("commit.junk", p, id=f"junk-{p}") for p in JUNK]
    + [pytest.param("commit.data_patterns", p, id=f"data-{p}") for p in DATA]
    + [pytest.param("commit.max_file_kb", "1024", id="max-file-kb-default")]
)


def _good():
    return json.loads((FIXTURES / "profile_depth2.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("bad", BAD_COMMIT)
def test_commit_keys_are_in_the_schema(bad):
    """Catches: a key the gate reads that the schema refuses, or a limit of 0 that would refuse every file (E1 part 1: the schema takes commit.junk and commit.data_patterns as non-empty lists of non-empty strings and commit.max_file_kb as a number above 0; an unknown key under commit is profile-invalid)."""
    good = _good()
    full = dict(good, commit={"junk": ["*.swp"], "data_patterns": ["*.csv", "*.json.gz"], "max_file_kb": 512})
    assert schema_check.check(full) == []
    assert schema_check.check(dict(good, commit={})) == []
    assert schema_check.check(dict(good, commit={"max_file_kb": 0.5})) == []
    errors = schema_check.check(dict(good, commit=copy.deepcopy(bad)))
    assert errors
    assert all(e.startswith("commit") for e in errors), (bad, errors)


@pytest.mark.parametrize("bad", BAD_SETTINGS)
def test_commit_defaults_and_overrides(bad):
    """Checks: the defaults hold in the gate body and each override replaces its own default (E2 part 1: with no commit key the settings are the defaults of the order, ten junk patterns, ten data extensions and 1024 KB; the profile's own values replace them, each key alone; a value that is not usable falls back to the default)."""
    import gate_commit
    default = {"junk": JUNK, "data_patterns": DATA, "max_file_kb": 1024}
    assert gate_commit.settings(make_profile()) == default
    assert gate_commit.settings(None) == default
    assert gate_commit.settings(make_profile(commit={})) == default
    own = make_profile(commit={"junk": ["*.swp"], "data_patterns": ["*.json.gz"], "max_file_kb": 64})
    assert gate_commit.settings(own) == {"junk": ["*.swp"], "data_patterns": ["*.json.gz"], "max_file_kb": 64}
    assert gate_commit.settings(make_profile(commit={"max_file_kb": 2.5}))["max_file_kb"] == 2.5
    only = gate_commit.settings(make_profile(commit={"junk": ["*.swp"]}))
    assert only == {"junk": ["*.swp"], "data_patterns": DATA, "max_file_kb": 1024}
    assert gate_commit.settings(make_profile(commit=bad)) == default
    assert profiles.validate(own) == []


@pytest.mark.parametrize("key, pattern", KEYS_MD_CASES)
def test_commit_keys_are_lines_of_keys_md_with_their_defaults(key, pattern):
    """Checks: each key has its default written down (E3 part 1: each key is a line of the Added keys table of KEYS.md, in schema now, with its own schema path and its default named)."""
    rows = {unquote(r[0]): r for r in section_rows("Added keys")}
    assert rows[key][1:3] == [NOW, f"`{key}`"]
    assert f"`{pattern}`" in rows[key][3]
    assert (REPO / "engine" / "KEYS.md").is_file()
