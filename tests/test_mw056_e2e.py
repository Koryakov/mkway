"""Card MW-056, through the REAL hook command: one engine install (module fixture, a scratch git repository, the task
folder below the git top), two open cards, a real pytest run on the staged tree and on HEAD's tree. The verdict is read
from the hook's JSON (`tests/_hook_driver.py::decision`). Synthetic names only."""
import sys

import pytest

from _hook_driver import decision, install_project
from _red_project import seed_record_file

# MW-085 (R213): engine_repo again (the install reads this repository), but not the shared lane; its module fixture builds once, on one worker
pytestmark = [pytest.mark.engine_repo, pytest.mark.xdist_group("test_mw056_e2e")]

CLI = "python mkway/engine/mkway.py"
BUILDER = "b1"
ONE, TWO = "CARD-001", "CARD-002"
GREEN = "def test_other():\n    assert True\n"
RED = "def test_other():\n    assert False\n"
COMMIT = 'git commit -m "CARD-001 change"'


def _card_text(template, paths):
    text = template.replace("| **Paths** | |", "| **Paths** | " + ", ".join(f"`{x}`" for x in paths) + " |")
    text = text.replace("«the owner's words, quoted» — owner, YYYY-MM-DD.", "A synthetic goal for the hook rows.")
    return text.replace("| E1 | item id | value today | value after the change | tests/test_x.py::test_y |",
                        "| E1 | the thing | absent | present | tests/test_a.py::test_a |")


def _new_card(p, title, paths):
    p.owner("card", "new", title)
    card_id = f"CARD-{len(list((p.root / 'mkway' / 'cards').glob('CARD-*'))):03d}"
    card_file = next((p.root / "mkway" / "cards").glob(f"{card_id}-*")) / "CARD.md"
    card_file.write_text(_card_text(card_file.read_text(encoding="utf-8"), paths), encoding="utf-8", newline="\n")
    p.owner("card", "open", card_id)
    return card_id


@pytest.fixture(scope="module")
def proj(tmp_path_factory):
    p = install_project(tmp_path_factory.mktemp("newred"))
    p.profile(**{"python.command": sys.executable, "gates.trip": {"min_calls": 100000}})
    assert _new_card(p, "Builder card", ("src/", "tests/test_a.py")) == ONE
    assert _new_card(p, "Other card", ("tests/test_other.py",)) == TWO
    decision(p.fire("SessionStart", BUILDER))
    p.session_shell(BUILDER, f"{CLI} card take {ONE}")
    p.write("src/a.py", "VALUE = 1\n")
    p.write("tests/test_a.py", "from src.a import VALUE\n\n\ndef test_a():\n    assert VALUE == 1\n")
    p.write("tests/test_other.py", GREEN)
    p.git("add", "-f", "--", "src/a.py", "tests/test_a.py", "tests/test_other.py")
    p.git("add", "-A", "mkway/cards", "mkway/profile.json")
    p.git("commit", "-q", "-m", "baseline of the new-red rows")
    seed_record_file(p, ONE)  # MW-072: this fixture commits its baseline with git, so the card has a red record
    return p


class staged:
    """One file changed and staged the way a builder stages it; unstaged and put back after the row."""

    def __init__(self, p, rel, text):
        self.p, self.rel, self.text = p, rel, text

    def __enter__(self):
        path = self.p.root / self.rel
        self.old = path.read_text(encoding="utf-8") if path.is_file() else None
        self.p.write(self.rel, self.text)
        self.p.git("add", "-f", "--", self.rel)

    def __exit__(self, *_):
        self.p.git("reset", "-q", "--", self.rel, check=False)
        path = self.p.root / self.rel
        if self.old is None:
            path.unlink()
        else:
            path.write_text(self.old, encoding="utf-8", newline="\n")


def test_a_new_red_is_denied_through_the_real_hook(proj):
    """Catches: a gate that works in process and not as installed; HEAD is green and the staged change of the card's own file turns the card's test red, so the real hook denies the commit commit-tests-failed and names the test as new (E13)."""
    with staged(proj, "src/a.py", "VALUE = 2\n"):
        got = decision(proj.fire("PreToolUse", BUILDER, "Bash", {"command": COMMIT}))
    assert got.kind == "deny", got
    assert (got.gate, got.reason_id) == ("commit_tests", "commit-tests-failed")
    assert "tests/test_a.py::test_a" in got.text
    assert "new red" in got.text
    assert "not red at HEAD" in got.text


def test_another_cards_old_red_is_allowed_through_the_real_hook(proj):
    """Checks: the red-first test of another open card is committed red at HEAD and the builder's commit of its own file passes the real hook, and the allow line says still red, owned by the card id; catches the real-install bug where one card mid-way stopped every other card (E14)."""
    proj.write("tests/test_other.py", RED)
    proj.git("add", "-f", "--", "tests/test_other.py")
    proj.git("commit", "-q", "-m", "red first of the other card")
    try:
        with staged(proj, "src/b.py", "VALUE = 3\n"):
            fired = proj.fire("PreToolUse", BUILDER, "Bash", {"command": COMMIT})
            got = decision(fired)
    finally:
        proj.write("tests/test_other.py", GREEN)
        proj.git("add", "-f", "--", "tests/test_other.py")
        proj.git("commit", "-q", "-m", "the other card goes green")
    assert got.kind == "allow", got
    assert "tests/test_other.py::test_other still red, owned by CARD-002" in fired.stdout
    assert "commit-tests-still-red" in fired.stdout
