"""Card MW-031: the git built-in list is current, and `mkway check` warns only on the risky side. Synthetic names and
fake git output only (no git process)."""
import json
import re

import pytest

from _engine import REPO
import helpers
import install
import profiles

pytestmark = pytest.mark.engine_repo  # reads the repository's own defaults, KEYS.md, register and changelog

NEW_IN_GIT = ["backfill", "diff-pairs", "last-modified", "repo", "survey"]
BASE = {"vcs": "none", "bundle": {"root": "mkway"}, "gates": {}, "python": {"command": "python"},
        "state": {"dir": "mkway/state"}}


def _list():
    data = json.loads((REPO / "engine" / "defaults.json").read_text(encoding="utf-8"))
    return data["lock_gate"]["git_builtins"]


def _git_says(names):
    return lambda: "\n".join(names) + "\n"


def test_the_list_holds_the_names_this_git_added_and_keeps_the_old_one():
    """E1: the list is the union of the old list and this git's built-ins minus the internal helper `env--helper`
    (a name only in the list is the risky side): the five new names are in, `env--helper` is out, no name twice."""
    names = _list()
    for name in NEW_IN_GIT + ["commit"]:
        assert name in names, name
    assert "env--helper" not in names
    assert len(names) == len(set(names))


def test_a_name_only_in_the_list_warns_and_the_fix_is_to_update_mkway(tmp_path):
    """E2: git's output lacks one name of the list: a warning that names it (the gate would trust it as a built-in
    although git may run an alias or an external command); the fix is to update mkway, not a profile key."""
    names = _list()
    line = install.git_builtins_line(tmp_path, run=_git_says([n for n in names if n != "tag"]))
    assert line.startswith("git builtins: warning"), line
    assert "tag" in line and "update mkway" in line, line
    assert "git_builtins_extra" not in line and "engine/defaults.json" not in line, line
    same = install.git_builtins_line(tmp_path, run=_git_says(names))
    assert "warning" not in same and "info" not in same, same


def test_a_name_only_in_git_is_info_and_names_the_profile_key(tmp_path):
    """E3: git has one name the list lacks (an over-refusal, the safe side): no warning; an info part names the name
    and the profile key `lock_gate.git_builtins_extra`, never an engine file."""
    line = install.git_builtins_line(tmp_path, run=_git_says(_list() + ["zz-new"]))
    assert "warning" not in line, line
    assert "info" in line and "zz-new" in line and "lock_gate.git_builtins_extra" in line, line
    assert "engine/defaults.json" not in line and "engine file" not in line, line


def test_the_profile_key_extends_the_list_for_the_check_and_the_gate(tmp_path):
    """E4: a name in the profile key is known to the check (the line matches, no info) and to the git form reader
    (no `command-unparsed`); without the key the reader still objects; an unusable value counts as no key."""
    out = _git_says(_list() + ["zz-new"])
    assert install.git_builtins_line(tmp_path, run=out, extra={"zz-new"}).startswith("git builtins: the engine list")
    assert "info" not in install.git_builtins_line(tmp_path, run=out, extra={"zz-new"})
    assert helpers.git_form_problem("git zz-new status") is not None
    assert helpers.git_form_problem("git zz-new status", "bash", extra={"zz-new"}) is None
    assert profiles.git_builtins_extra({"lock_gate": {"git_builtins_extra": ["zz-new"]}}) == {"zz-new"}
    for bad in ({}, {"lock_gate": {}}, {"lock_gate": {"git_builtins_extra": ["zz-new", 5]}},
                {"lock_gate": {"git_builtins_extra": "zz-new"}}, None):
        assert profiles.git_builtins_extra(bad) == set(), bad


def test_the_schema_accepts_the_key_and_refuses_a_wrong_type():
    """E5: `lock_gate.git_builtins_extra` is an array of names in the profile schema."""
    good = dict(BASE, lock_gate={"git_builtins_extra": ["zz-new"]})
    assert profiles.validate(good) == []
    bad = dict(BASE, lock_gate={"git_builtins_extra": "zz-new"})
    assert any("lock_gate.git_builtins_extra" in e for e in profiles.validate(bad))


def test_the_list_gives_this_machine_no_warning(tmp_path):
    """E8: git's built-ins of this machine as the order names them (the old list minus `env--helper`, plus the five
    new names) equal the list: the line is the plain match."""
    names = _list()
    line = install.git_builtins_line(tmp_path, run=_git_says(names))
    assert line == f"git builtins: the engine list matches git ({len(names)} commands)", line


def test_keys_md_names_the_key_and_the_direction():
    """E6: KEYS.md has an added-keys row for the profile key, and the engine-constant row no longer says the list
    was written from knowledge alone."""
    text = (REPO / "engine" / "KEYS.md").read_text(encoding="utf-8")
    assert re.search(r"^\| `lock_gate\.git_builtins_extra` \| in schema now \| `lock_gate\.git_builtins_extra` \|",
                     text, re.M)
    row = next(r for r in text.splitlines() if r.startswith("| `lock_gate` | `git_builtins` |"))
    assert "MW-031" in row and "unverified" not in row


def test_register_changelog_and_card_name_the_card():
    """E7: the register row, a line under the top changelog section, the card folder; VERSION is untouched."""
    register = (REPO / "cards" / "REGISTER.md").read_text(encoding="utf-8")
    assert re.search(r"^\| MW-031 \| .*\|.*`cards/MW-031-[a-z0-9-]+`", register, re.M)
    changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    top = changelog.split("\n## 0.2.6\n", 1)[1].split("\n## ", 1)[0]
    assert re.search(r"^- MW-031: ", top, re.M)
    assert list((REPO / "cards").glob("MW-031-*/CARD.md"))
    assert (REPO / "VERSION").read_text(encoding="utf-8").strip() == "0.2.7"  # changed by MW-027: 0.2.7
