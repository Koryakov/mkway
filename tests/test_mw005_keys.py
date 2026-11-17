"""Tests before a commit (card MW-005, part A): the profile keys and the readers the commit gate uses. Synthetic
profiles only; no task data."""
import copy
import json

import pytest

from _engine import FIXTURES, REPO, make_profile
from _keys_md import section_rows, unquote
import profiles
import schema_check

NOW = "in schema now"


def _good():
    return json.loads((FIXTURES / "profile_depth2.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("bad", [{"command": ""}, {"command": 3}, {"command": ["python"]}, {"nope": 1}],
                         ids=["empty", "number", "list", "unknown-key"])
def test_tests_command_is_in_the_schema(bad):
    """Catches: a tests.command that is not a non-empty string is accepted; each bad value is profile-invalid and the error names its key (E1)."""
    # Catches: a key the gate reads that the schema refuses, or a value the gate cannot run
    good = _good()
    assert schema_check.check(dict(good, tests={"command": "python -m pytest -q tests"})) == []
    assert schema_check.check(dict(good, tests={})) == []
    errors = schema_check.check(dict(good, tests=copy.deepcopy(bad)))
    assert errors
    assert all(e.startswith("tests") for e in errors), (bad, errors)


def test_test_roots_env_and_command_defaults_and_overrides(tmp_path):
    """Checks: test_roots, test_env and tests_command take their defaults, their overrides, and fall back on a bad value (E2)."""
    # test_roots is ["tests"] unless the profile names folders (posix form, no trailing slash); test_env is the valid
    # variable names, default none; tests_command is None unless the profile holds a non-empty string
    # Catches: a default hard-coded in the gate, an override that is ignored, a crash on a bad value
    assert profiles.test_roots(make_profile()) == ["tests"]
    assert profiles.test_roots(None) == ["tests"]
    assert profiles.test_roots(make_profile(test_roots=["a\\b/", "c"])) == ["a/b", "c"]
    drive_form = str(tmp_path)  # the absolute drive form, built from the test's own folder
    leading_slash_form = "/" + tmp_path.relative_to(tmp_path.anchor).as_posix()  # the absolute leading-slash form
    bad_roots = [bad for bad in ([], "tests", [""], [3], [leading_slash_form], [drive_form], ["../up"])
                 if profiles.test_roots(make_profile(test_roots=bad)) != ["tests"]]
    assert not bad_roots, bad_roots
    assert profiles.test_env(make_profile()) == []
    assert profiles.test_env(make_profile(test_env=["ALPHA", "b_2"])) == ["ALPHA", "b_2"]
    bad_env = [bad for bad in ("ALPHA", [3], ["1x"], ["a b"]) if profiles.test_env(make_profile(test_env=bad)) != []]
    assert not bad_env, bad_env
    assert profiles.tests_command(make_profile()) is None
    assert profiles.tests_command(None) is None
    assert profiles.tests_command(make_profile(tests={"command": " python -m pytest -q x "})) == "python -m pytest -q x"
    bad_command = [bad for bad in ({"command": ""}, {"command": "  "}, {"command": 3}, "text", [])
                   if profiles.tests_command(make_profile(tests=bad)) is not None]
    assert not bad_command, bad_command


def test_commit_tests_budget_default_and_override():
    """Checks: the commit gate budget is gates.commit_tests.budget_seconds, default 780, and a bad value falls back (E3)."""
    # a value that is not a number above 0 (zero, negative, a bool, a text) falls back to 780
    # Catches: an over-budget refusal with no default, or a budget of 0 that refuses every run
    assert profiles.COMMIT_TESTS_BUDGET == 780
    assert profiles.commit_tests_budget(make_profile()) == 780
    assert profiles.commit_tests_budget(None) == 780
    assert profiles.commit_tests_budget(make_profile(gates={"commit_tests": {"budget_seconds": 90}})) == 90
    assert profiles.commit_tests_budget(make_profile(gates={"commit_tests": {"budget_seconds": 2.5}})) == 2.5
    bad_budget = [bad for bad in (0, -5, True, "90", None)
                  if profiles.commit_tests_budget(make_profile(gates={"commit_tests": {"budget_seconds": bad}})) != 780]
    assert not bad_budget, bad_budget
    assert profiles.commit_tests_budget(make_profile(gates={"other": {"budget_seconds": 5}})) == 780


def test_paths_docs_has_a_reader_with_the_documented_default():
    """Checks: paths.docs is read with its documented default, and docs_only is true only for documents (E4)."""
    # the default is <bundle.root>/cards/**, <bundle.root>/ledger/**, *.md; an unusable paths.docs falls back
    # Catches: a key in the schema that nothing reads, a docs commit that runs tests, a code file taken for a doc
    assert profiles.docs_globs(make_profile()) == ["mkway/cards/**", "mkway/ledger/**", "*.md"]
    deep = make_profile(bundle={"root": "tools/mk"})
    assert profiles.docs_globs(deep) == ["tools/mk/cards/**", "tools/mk/ledger/**", "*.md"]
    assert profiles.docs_globs(make_profile(paths={"docs": ["notes/**", "*.txt"]})) == ["notes/**", "*.txt"]
    bad_docs = [bad for bad in ({"docs": []}, {"docs": "x"}, {"docs": [""]}, {"docs": [3]}, {})
                if profiles.docs_globs(make_profile(paths=bad)) != ["mkway/cards/**", "mkway/ledger/**", "*.md"]]
    assert not bad_docs, bad_docs
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
    """Checks: tests.command and gates.commit_tests.budget_seconds are KEYS.md lines in schema now, with their defaults (E5)."""
    # the lines of paths.docs, test_roots and test_env say the commit gate reads them
    # Catches: a key with no default written down, which would make the default a value nobody can find
    rows = {unquote(r[0]): r for r in section_rows("Added keys")}
    assert rows["tests.command"][1:3] == [NOW, "`tests.command`"]
    assert "`python -m pytest -q`" in rows["tests.command"][3]
    assert rows["gates.commit_tests.budget_seconds"][1:3] == [NOW, "`gates`"]
    assert "`780`" in rows["gates.commit_tests.budget_seconds"][3]
    missing_readers = [key for key in ("paths.docs", "test_env") if "commit_tests" not in " ".join(rows[key])]
    assert not missing_readers, missing_readers
    profile_rows = {unquote(r[1]): r for r in section_rows("Profile keys")}
    assert "commit_tests" in " ".join(profile_rows["test_roots"])
    assert (REPO / "engine" / "KEYS.md").is_file()
