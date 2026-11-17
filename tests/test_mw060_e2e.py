"""Card MW-060, through the REAL hook command: one engine install (module fixture, a scratch git repository, the task
folder below the git top), one open card, another card's breaking file staged. The verdict is read from the hook's JSON
(`tests/_hook_driver.py::decision`). Synthetic names only."""
import sys

import pytest

from _hook_driver import decision, install_project
from _red_project import seed_record_file

# MW-085 (R213): engine_repo again (the install reads this repository), but not the shared lane; its module fixture builds once, on one worker
pytestmark = [pytest.mark.engine_repo, pytest.mark.xdist_group("test_mw060_e2e")]

CLI = "python mkway/engine/mkway.py"
BUILDER = "b1"
ONE = "CARD-001"
GUARD = ("from pathlib import Path\n\n\ndef test_no_draft_folder():\n"
         "    assert not (Path(__file__).resolve().parent.parent / 'src' / 'pkg' / 'draft').exists()\n")


def _card_text(template, paths):
    text = template.replace("| **Paths** | |", "| **Paths** | " + ", ".join(f"`{x}`" for x in paths) + " |")
    text = text.replace("«the owner's words, quoted» — owner, YYYY-MM-DD.", "A synthetic goal for the hook rows.")
    return text.replace("| E1 | item id | value today | value after the change | tests/test_x.py::test_y |",
                        "| E1 | the thing | absent | present | tests/test_a.py::test_a |")


@pytest.fixture(scope="module")
def proj(tmp_path_factory):
    p = install_project(tmp_path_factory.mktemp("taken"))
    p.profile(**{"python.command": sys.executable, "gates.trip": {"min_calls": 100000}})
    p.owner("card", "new", "Builder card")
    card_file = next((p.root / "mkway" / "cards").glob(f"{ONE}-*")) / "CARD.md"
    card_file.write_text(_card_text(card_file.read_text(encoding="utf-8"), ("src/", "tests/test_a.py", "tests/test_guard.py")), encoding="utf-8",
                         newline="\n")
    p.owner("card", "open", ONE)
    decision(p.fire("SessionStart", BUILDER))
    p.session_shell(BUILDER, f"{CLI} card take {ONE}")
    p.write("src/a.py", "VALUE = 1\n")
    p.write("src/pkg/m.py", "V = 1\n")
    p.write("tests/test_a.py", "from src.a import VALUE\n\n\ndef test_a():\n    assert VALUE == 1\n")
    p.write("tests/test_guard.py", GUARD)
    p.git("add", "-f", "--", "src/a.py", "src/pkg/m.py", "tests/test_a.py", "tests/test_guard.py")
    p.git("add", "-A", "mkway/cards", "mkway/profile.json")
    p.git("commit", "-q", "-m", "baseline of the taken-tree rows")
    seed_record_file(p, ONE)  # MW-072: this fixture commits its baseline with git, so the card has a red record
    return p


@pytest.fixture
def other_cards_break(proj):
    """Another card's file, staged, breaks the card's test; the builder's own folder has an edit and an untracked
    folder inside it."""
    proj.write("src/a.py", "VALUE = 2\n")
    proj.git("add", "-f", "--", "src/a.py")
    proj.write("src/pkg/m.py", "V = 4\n")
    proj.write("src/pkg/draft/n.txt", "untracked\n")
    yield proj
    proj.git("reset", "-q", "--", "src/a.py", check=False)
    proj.write("src/a.py", "VALUE = 1\n")
    proj.write("src/pkg/m.py", "V = 1\n")
    (proj.root / "src" / "pkg" / "draft" / "n.txt").unlink()
    (proj.root / "src" / "pkg" / "draft").rmdir()


def test_a_commit_of_the_builders_own_folder_is_allowed_through_the_real_hook(other_cards_break):
    """Checks: another card's breaking file is staged, and the builder's own folder-scoped commit passes the real hook. E10"""
    # another card's breaking file is staged and a folder of untracked files lies inside the builder's folder; the builder's
    # folder-scoped commit passes the real hook. The real-install refusal named tests none of the builder's files could break.
    command = 'git commit -m "CARD-001 change the package\n\nsecond line" -- src/pkg'
    got = decision(other_cards_break.fire("PreToolUse", BUILDER, "Bash", {"command": command}))
    assert got.kind == "allow", got


def test_the_same_state_as_a_plain_commit_is_denied_through_the_real_hook(other_cards_break):
    """Catches: a gate that stopped testing the index for a plain commit, through the real hook. E11"""
    # the plain commit of the same state takes the staged breaking file, so the hook denies commit-tests-failed and names the test as new.
    got = decision(other_cards_break.fire("PreToolUse", BUILDER, "Bash", {"command": 'git commit -m "CARD-001 change"'}))
    assert got.kind == "deny", got
    assert (got.gate, got.reason_id) == ("commit_tests", "commit-tests-failed")
    assert "tests/test_a.py::test_a" in got.text
    assert "new red" in got.text
