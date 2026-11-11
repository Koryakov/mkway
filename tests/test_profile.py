"""The root, the profile and its schema (card MW-002, rows E17-E20, E24). Synthetic profiles only."""
import subprocess
from pathlib import Path

import pytest

from _engine import REPO, make_profile, write_profile
import paths
import profiles as mkprofile
import schema_check


def test_root_from_arg_env_or_git(tmp_path):
    """E17: the root is --root, else $CLAUDE_PROJECT_DIR, else (vcs git) `git rev-parse --show-toplevel`; with
    vcs none and neither given there is no root. It is never computed from the engine's own folder."""
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    assert paths.find_root(env={"CLAUDE_PROJECT_DIR": str(a)}) == a.resolve()
    assert paths.find_root(env={"CLAUDE_PROJECT_DIR": str(a)}, root_arg=str(b)) == b.resolve()
    repo = tmp_path / "repo"
    (repo / "x" / "y").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    assert paths.find_root(env={}, cwd=repo / "x" / "y") == repo.resolve()
    with pytest.raises(paths.RootNotFound):
        paths.find_root(env={}, vcs="none", cwd=repo / "x")
    src = (REPO / "engine" / "paths.py").read_text(encoding="utf-8")
    assert "__file__" not in src


def test_profile_by_convention_or_arg(tmp_path):
    """E18: the profile is <root>/mkway/profile.json, or --profile <path> (a relative path is read from the root)."""
    root = tmp_path / "root"
    root.mkdir()
    assert paths.profile_path(root) == root / "mkway" / "profile.json"
    assert paths.profile_path(root, "conf/p.json") == root / "conf" / "p.json"
    other = tmp_path / "elsewhere.json"
    assert paths.profile_path(root, str(other)) == other
    write_profile(root, make_profile())
    profile, errors = mkprofile.load(paths.profile_path(root))
    assert errors == [] and profile["vcs"] == "none"
    profile, errors = mkprofile.load(root / "missing.json")
    assert profile is None and errors == ["(profile): not found"]


def test_schema_takes_the_new_keys():
    """E19: `vcs` (git | none, required, no default), `ids.card_prefix` (capital letters and digits, optional) and
    `gates.<name>.budget_seconds` (a number) are in the schema; a wrong value names its key."""
    good = make_profile({"g": {"on": True, "budget_seconds": 5}}, ids={"card_prefix": "CARD"})
    assert schema_check.check(good) == []
    cases = []
    p = make_profile(); p["vcs"] = "svn"; cases.append((p, "vcs"))
    p = make_profile(); del p["vcs"]; cases.append((p, "vcs"))
    p = make_profile(ids={"card_prefix": "card-1"}); cases.append((p, "ids.card_prefix"))
    p = make_profile({"g": {"on": True, "budget_seconds": "5"}}); cases.append((p, "gates.g.budget_seconds"))
    for profile, key in cases:
        errors = schema_check.check(profile)
        assert any(e.split(":", 1)[0] == key for e in errors), (key, errors)


def test_engine_constant_named_by_profile_invalid():
    """E20: a defaults.json key that is not in the schema is an engine constant; a profile that sets one is invalid,
    and the error names it as an engine constant."""
    p = make_profile(quality_gate={"acceptance_heading": "## Other"})
    errors = mkprofile.validate(p)
    assert "quality_gate.acceptance_heading: engine constant, the profile cannot set it" in errors
    assert mkprofile.validate(make_profile()) == []


def test_tmp_path_is_inside_the_engine(tmp_path):
    """E24: test temp files stay inside the engine repository (`--basetemp=.pytest_tmp`)."""
    assert Path(tmp_path).resolve().is_relative_to((REPO / ".pytest_tmp").resolve())
