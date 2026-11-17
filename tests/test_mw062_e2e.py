"""Card MW-062, through the REAL hook command: one engine install, two open cards, the red-first test file of one card
parametrized over a folder the other card creates; a real pytest run on the staged tree, on HEAD's tree and the listing
of HEAD's cases. The verdict is read from the hook's JSON (`tests/_hook_driver.py::decision`). Synthetic names only."""
import sys

import pytest

from _hook_driver import decision, install_project
from _red_project import seed_record_file
from test_mw056_e2e import _new_card
from test_mw062_shell import TEST_B

# MW-085 (R213): engine_repo again (the install reads this repository), but not the shared lane; its module fixture builds once, on one worker
pytestmark = [pytest.mark.engine_repo, pytest.mark.xdist_group("test_mw062_e2e")]

CLI = "python mkway/engine/mkway.py"
BUILDER = "b1"
ONE, TWO = "CARD-001", "CARD-002"
COMMIT = 'git commit -m "CARD-001 change"'


@pytest.fixture(scope="module")
def proj(tmp_path_factory):
    p = install_project(tmp_path_factory.mktemp("absent"))
    p.profile(**{"python.command": sys.executable, "gates.trip": {"min_calls": 100000}})
    assert _new_card(p, "Creator card", ("src/", "items/")) == ONE
    assert _new_card(p, "Checker card", ("tests/test_b.py",)) == TWO
    decision(p.fire("SessionStart", BUILDER))
    p.session_shell(BUILDER, f"{CLI} card take {ONE}")
    p.write("src/a.py", "VALUE = 1\n")
    p.write("tests/test_b.py", TEST_B)
    p.git("add", "-f", "--", "src/a.py", "tests/test_b.py")
    p.git("add", "-A", "mkway/cards", "mkway/profile.json")
    p.git("commit", "-q", "-m", "baseline of the absent-at-head rows")
    seed_record_file(p, ONE)  # MW-072: this fixture commits its baseline with git, so the card has a red record
    return p


def test_cases_that_appear_with_the_creating_cards_files_are_allowed_through_the_real_hook(proj):
    """E12: the checker's red-first file is committed, the creator's files make its cases appear red; the real hook
    allows the creator's commit and the allow line says `2 cases absent at HEAD, owned by CARD-002`. Catches: a gate that
    decides in process and refuses as installed (the real-install refusal of 12.11)."""
    proj.write("items/a.txt", "todo\n")
    proj.write("items/b.txt", "todo\n")
    proj.git("add", "-f", "--", "items/a.txt", "items/b.txt")
    fired = proj.fire("PreToolUse", BUILDER, "Bash", {"command": COMMIT})
    got = decision(fired)
    assert got.kind == "allow", got
    assert "2 cases absent at HEAD, owned by CARD-002" in fired.stdout
    assert "commit-tests-still-red" in fired.stdout
