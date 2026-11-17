"""Card MW-038: the guard of the real-shape scenario. The scenario (`tests/test_mw038_real_shape.py`) is the gate that
decides what reaches the owner; it must not be removed, nor silenced with a skip. A step that fails on the engine of
the day is an `xfail(strict=True, reason="MW-038 finding: ...")` and is reported, never skipped.
"""
import ast
import re
from pathlib import Path

import pytest

import _docs as docs
from _engine import REPO

pytestmark = pytest.mark.engine_repo

SCENARIO = REPO / "tests" / "test_mw038_real_shape.py"
SKIP_NAMES = {"skip", "skipif", "importorskip", "skipTest", "SkipTest", "skipUnless", "skipIf"}
STEPS = ("test_s1_", "test_s2_", "test_s3_", "test_s4_", "test_s5_", "test_s6_", "test_s7_")


def _tree():
    assert SCENARIO.is_file(), "tests/test_mw038_real_shape.py is missing: the real-shape scenario must stay"
    return ast.parse(SCENARIO.read_text(encoding="utf-8"))


def test_the_real_shape_scenario_exists_and_holds_no_skip():
    """Catches: a skip of any form in the real-shape scenario file, which must stay unskipped (E8)."""
    tree = _tree()
    found = sorted({(node.attr if isinstance(node, ast.Attribute) else node.id)
                    for node in ast.walk(tree)
                    if (isinstance(node, ast.Attribute) and node.attr in SKIP_NAMES)
                    or (isinstance(node, ast.Name) and node.id in SKIP_NAMES)})
    assert not found, f"{SCENARIO.relative_to(REPO).as_posix()} holds a skip: {found}"


def _xfail_problems(tree):
    """The xfail calls of the scenario that are not strict, or whose reason does not start with the finding marker."""
    problems = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "xfail":
            keywords = {k.arg: k.value for k in node.keywords}
            strict = keywords.get("strict")
            if not (isinstance(strict, ast.Constant) and strict.value is True):
                problems.append("an xfail that is not strict=True")
            reason = ast.literal_eval(keywords["reason"]) if "reason" in keywords else ""
            if not reason.startswith("MW-038 finding:"):
                problems.append(f"an xfail reason does not start `MW-038 finding:`: {reason!r}")
    return problems


@pytest.mark.parametrize("step", [pytest.param(s, id=s.rstrip("_")) for s in STEPS])
def test_every_step_has_a_test_and_every_xfail_is_a_strict_finding(step):
    """Catches: a step with no test, or an xfail that is not strict or whose reason does not start with the MW-038 finding marker (E8)."""
    tree = _tree()
    names = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    assert any(name.startswith(step) for name in names), f"no test for the step {step[5:7].upper()}"
    problems = _xfail_problems(tree)
    assert not problems, problems


def test_the_card_register_and_changelog_name_mw038():
    """Checks: the register row, one changelog line under 0.2.7 with the register's title, and the card file are there, and the version file is unchanged (E9)."""
    register = (REPO / "cards" / "REGISTER.md").read_text(encoding="utf-8")
    row = re.search(r"^\| MW-038 \| (.+?) \| proposed \| `cards/MW-038-[a-z0-9-]+` \|\r?$", register, re.M)
    assert row, "no register row of MW-038"
    changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    section = docs.changelog_section(changelog, "MW-038")
    assert f"- MW-038: {row.group(1)}" in section.splitlines(), "no changelog line of MW-038 under 0.2.7"
    docs.assert_version_file()
    assert list((REPO / "cards").glob("MW-038-*/CARD.md"))
