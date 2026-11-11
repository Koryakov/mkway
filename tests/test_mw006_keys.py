"""Commit checks (card MW-006), part 1: the profile keys `commit.junk`, `commit.data_patterns` and
`commit.max_file_kb`, their defaults and their KEYS.md lines. Synthetic values only."""
import copy
import json

from _engine import FIXTURES, REPO, make_profile
from _keys_md import section_rows, unquote
import profiles
import schema_check

NOW = "in schema now"
JUNK = ["__pycache__/", "*.pyc", ".pytest_cache/", ".pytest_tmp/", "*.log", "*.tmp", "*.orig", "*.rej", ".DS_Store",
        "Thumbs.db"]
DATA = ["*.csv", "*.tsv", "*.xlsx", "*.xls", "*.parquet", "*.db", "*.sqlite", "*.sqlite3", "*.bak", "*.dump"]


def _good():
    return json.loads((FIXTURES / "profile_depth2.json").read_text(encoding="utf-8"))


def test_commit_keys_are_in_the_schema():
    """E1 (part 1): the schema takes `commit.junk` and `commit.data_patterns` (non-empty lists of non-empty
    strings) and `commit.max_file_kb` (a number above 0); an unknown key under `commit` is profile-invalid.
    Catches: a key the gate reads that the schema refuses, or a limit of 0 that would refuse every file."""
    good = _good()
    full = dict(good, commit={"junk": ["*.swp"], "data_patterns": ["*.csv", "*.json.gz"], "max_file_kb": 512})
    assert schema_check.check(full) == []
    assert schema_check.check(dict(good, commit={})) == []
    assert schema_check.check(dict(good, commit={"max_file_kb": 0.5})) == []
    for bad in ({"junk": []}, {"junk": [""]}, {"junk": "*.pyc"}, {"data_patterns": []}, {"data_patterns": [3]},
                {"max_file_kb": 0}, {"max_file_kb": -1}, {"max_file_kb": "big"}, {"nope": 1}):
        errors = schema_check.check(dict(good, commit=copy.deepcopy(bad)))
        assert errors and all(e.startswith("commit") for e in errors), (bad, errors)


def test_commit_defaults_and_overrides():
    """E2 (part 1): with no `commit` in the profile the settings are the defaults of the order (ten junk patterns,
    ten data extensions, 1024 KB); the profile's own values replace them, each key alone; a value that is not usable
    falls back to the default, so the gate never crashes on a bad key.
    Catches: a default hard-coded in the gate body, or an override that is ignored."""
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
    for bad in ({"junk": [], "data_patterns": [""], "max_file_kb": 0}, {"junk": "x", "data_patterns": 5,
                                                                         "max_file_kb": True},
                {"max_file_kb": -3}, {"max_file_kb": "9"}, "text", []):
        assert gate_commit.settings(make_profile(commit=bad)) == default, bad
    assert profiles.validate(own) == []


def test_commit_keys_are_lines_of_keys_md_with_their_defaults():
    """E3 (part 1): each key is a line of the «Added keys» table of KEYS.md, «in schema now» with its own schema
    path and its default named. Catches: a key with no default written down."""
    rows = {unquote(r[0]): r for r in section_rows("Added keys")}
    for key in ("commit.junk", "commit.data_patterns", "commit.max_file_kb"):
        assert rows[key][1:3] == [NOW, f"`{key}`"], key
    for pattern in JUNK:
        assert f"`{pattern}`" in rows["commit.junk"][3], pattern
    for pattern in DATA:
        assert f"`{pattern}`" in rows["commit.data_patterns"][3], pattern
    assert "`1024`" in rows["commit.max_file_kb"][3]
    assert (REPO / "engine" / "KEYS.md").is_file()
