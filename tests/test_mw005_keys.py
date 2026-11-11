"""Tests before a commit (card MW-005, part A): the profile keys and the readers the commit gate uses. Synthetic
profiles only; no task data."""
import copy
import json

from _engine import FIXTURES, REPO, make_profile
from _keys_md import section_rows, unquote
import profiles
import schema_check

NOW = "in schema now"


def _good():
    return json.loads((FIXTURES / "profile_depth2.json").read_text(encoding="utf-8"))


def test_tests_command_is_in_the_schema():
    """E1 (part A): the schema takes `tests.command`, a non-empty string; a non-string, an empty string and an
    unknown key under `tests` are profile-invalid, each error naming its key.
    Catches: a key the gate reads that the schema refuses, or a value the gate cannot run."""
    good = _good()
    assert schema_check.check(dict(good, tests={"command": "python -m pytest -q tests"})) == []
    assert schema_check.check(dict(good, tests={})) == []
    for bad in ({"command": ""}, {"command": 3}, {"command": ["python"]}, {"nope": 1}):
        errors = schema_check.check(dict(good, tests=copy.deepcopy(bad)))
        assert errors and all(e.startswith("tests") for e in errors), (bad, errors)


def test_test_roots_env_and_command_defaults_and_overrides():
    """E2 (part A): `profiles.test_roots` is `["tests"]` unless the profile names folders (posix form, no trailing
    slash); `profiles.test_env` is the valid variable names, default none; `profiles.tests_command` is None (the
    gate then builds `python -m pytest -q` over the roots) unless the profile holds a non-empty string. A value that
    is not usable falls back to the default, so a gate never crashes on a bad key.
    Catches: a default hard-coded in the gate, an override that is ignored, a crash on a bad value."""
    assert profiles.test_roots(make_profile()) == ["tests"]
    assert profiles.test_roots(None) == ["tests"]
    assert profiles.test_roots(make_profile(test_roots=["a\\b/", "c"])) == ["a/b", "c"]
    for bad in ([], "tests", [""], [3], ["/abs"], ["../up"]):
        assert profiles.test_roots(make_profile(test_roots=bad)) == ["tests"], bad
    assert profiles.test_env(make_profile()) == []
    assert profiles.test_env(make_profile(test_env=["ALPHA", "b_2"])) == ["ALPHA", "b_2"]
    for bad in ("ALPHA", [3], ["1x"], ["a b"]):
        assert profiles.test_env(make_profile(test_env=bad)) == [], bad
    assert profiles.tests_command(make_profile()) is None
    assert profiles.tests_command(None) is None
    assert profiles.tests_command(make_profile(tests={"command": " python -m pytest -q x "})) == "python -m pytest -q x"
    for bad in ({"command": ""}, {"command": "  "}, {"command": 3}, "text", []):
        assert profiles.tests_command(make_profile(tests=bad)) is None, bad


def test_commit_tests_budget_default_and_override():
    """E3 (part A): the budget of the commit gate is `gates.commit_tests.budget_seconds`, default 780 (a number
    above 0); a value that is not a number above 0 (zero, negative, a bool, a text) falls back to 780.
    Catches: an over-budget refusal with no default, or a budget of 0 that refuses every run."""
    assert profiles.COMMIT_TESTS_BUDGET == 780
    assert profiles.commit_tests_budget(make_profile()) == 780
    assert profiles.commit_tests_budget(None) == 780
    assert profiles.commit_tests_budget(make_profile(gates={"commit_tests": {"budget_seconds": 90}})) == 90
    assert profiles.commit_tests_budget(make_profile(gates={"commit_tests": {"budget_seconds": 2.5}})) == 2.5
    for bad in (0, -5, True, "90", None):
        assert profiles.commit_tests_budget(make_profile(gates={"commit_tests": {"budget_seconds": bad}})) == 780, bad
    assert profiles.commit_tests_budget(make_profile(gates={"other": {"budget_seconds": 5}})) == 780


def test_paths_docs_has_a_reader_with_the_documented_default():
    """E4 (part A): `profiles.docs_globs` is the profile's `paths.docs`, else the documented default
    (`<bundle.root>/cards/**`, `<bundle.root>/ledger/**`, `*.md`); `profiles.docs_only(profile, rels)` is true when
    there is at least one path and every path matches a glob (a card file, a ledger file, a Markdown file in any
    folder), and false for an empty list or when one path matches none. An unusable `paths.docs` falls back.
    Catches: a key in the schema that nothing reads, a docs commit that runs tests, a code file taken for a doc."""
    assert profiles.docs_globs(make_profile()) == ["mkway/cards/**", "mkway/ledger/**", "*.md"]
    deep = make_profile(bundle={"root": "tools/mk"})
    assert profiles.docs_globs(deep) == ["tools/mk/cards/**", "tools/mk/ledger/**", "*.md"]
    assert profiles.docs_globs(make_profile(paths={"docs": ["notes/**", "*.txt"]})) == ["notes/**", "*.txt"]
    for bad in ({"docs": []}, {"docs": "x"}, {"docs": [""]}, {"docs": [3]}, {}):
        assert profiles.docs_globs(make_profile(paths=bad)) == ["mkway/cards/**", "mkway/ledger/**", "*.md"], bad
    p = make_profile()
    assert profiles.docs_only(p, ["README.md"])
    assert profiles.docs_only(p, ["sub/dir/NOTES.md", "mkway/cards/X-001/CARD.md", "mkway/ledger/rows.csv"])
    assert not profiles.docs_only(p, [])
    assert not profiles.docs_only(p, ["README.md", "src/app.py"])
    assert not profiles.docs_only(p, ["mkway/cards.py"])
    own = make_profile(paths={"docs": ["notes/**", "*.txt"]})
    assert profiles.docs_only(own, ["notes/a.md", "b.txt"])
    assert not profiles.docs_only(own, ["README.md"])


def test_the_commit_tests_keys_are_lines_of_keys_md_with_their_defaults():
    """E5 (part A): `tests.command` and `gates.commit_tests.budget_seconds` are lines of the «Added keys» table of
    KEYS.md, «in schema now» with their schema path and their default named; the lines of `paths.docs`, `test_roots`
    and `test_env` say the commit gate reads them (the earlier «(MW-003)» wording named a reader that did not exist).
    Catches: a key with no default written down, which would make the default a value nobody can find."""
    rows = {unquote(r[0]): r for r in section_rows("Added keys")}
    assert rows["tests.command"][1:3] == [NOW, "`tests.command`"]
    assert "`python -m pytest -q`" in rows["tests.command"][3]
    assert rows["gates.commit_tests.budget_seconds"][1:3] == [NOW, "`gates`"]
    assert "`780`" in rows["gates.commit_tests.budget_seconds"][3]
    for key in ("paths.docs", "test_env"):
        assert "commit_tests" in " ".join(rows[key]), key
    profile_rows = {unquote(r[1]): r for r in section_rows("Profile keys")}
    assert "commit_tests" in " ".join(profile_rows["test_roots"])
    assert (REPO / "engine" / "KEYS.md").is_file()
