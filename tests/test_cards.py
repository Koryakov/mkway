"""The cards tool: `mkway card new <title>`, `mkway card list` (card MW-002, rows E25-E28). Synthetic task roots."""
import json
import subprocess
import sys

import pytest

from _engine import REPO, make_profile, write_profile
import cardtool as cards

TEMPLATE = REPO / "cards" / "_TEMPLATE" / "CARD.md"


@pytest.fixture
def task(tmp_path):
    root = tmp_path / "task"
    root.mkdir()
    write_profile(root, make_profile(ids={"card_prefix": "CARD"}))
    return root


def _mkway(root, *args):
    return subprocess.run([sys.executable, str(REPO / "mkway.py"), *args, "--root", str(root)],
                          capture_output=True, text=True, timeout=60)


def _register_rows(root):
    text = (root / "mkway" / "cards" / "REGISTER.md").read_text(encoding="utf-8")
    return [[c.strip() for c in line.strip().strip("|").split("|")] for line in text.splitlines()
            if line.startswith("| ") and not line.startswith("| Id ")]


def test_card_new_numbers_and_register(task):
    """E25: `card new` writes <bundle.root>/cards/<PREFIX>-NNN-<slug>/CARD.md from the one-page form, with the id
    and title in its first line, and adds the register row beside the cards; `card list` prints the rows.
    Changed by MW-003 (R15 A1, R18): a new card is `proposed`, and the register has a `Paths` column, empty until
    the owner's `card open` records it."""
    proc = _mkway(task, "card", "new", "First thing: a test")
    assert proc.returncode == 0, proc.stderr
    card = task / "mkway" / "cards" / "CARD-001-first-thing-a-test" / "CARD.md"
    assert card.is_file()
    lines = card.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "# CARD-001: First thing: a test"
    assert lines[1:] == TEMPLATE.read_text(encoding="utf-8").splitlines()[1:]
    assert _mkway(task, "card", "new", "Second").returncode == 0
    assert _register_rows(task) == [
        ["CARD-001", "First thing: a test", "proposed", "", "`mkway/cards/CARD-001-first-thing-a-test`"],
        ["CARD-002", "Second", "proposed", "", "`mkway/cards/CARD-002-second`"],
    ]
    listed = _mkway(task, "card", "list")
    assert listed.returncode == 0
    assert "CARD-001" in listed.stdout and "CARD-002" in listed.stdout and "Second" in listed.stdout


def test_card_ids_never_repeat_and_pass_999(task):
    """E26: the next id is one past the highest id in the register or in the folder names, so an id never repeats
    (a row whose folder is gone still counts), and ids go past 999.
    Changed by MW-003 (R19a): the hand-written register is sealed first, as the owner's `card resync` does; an
    unsealed register is refused as tampered (E14)."""
    import register
    profile = json.loads((task / "mkway" / "profile.json").read_text(encoding="utf-8"))
    folder = task / "mkway" / "cards"
    folder.mkdir(parents=True)
    (folder / "REGISTER.md").write_text("# Card register\n\n| Id | Title | Status | Folder |\n|---|---|---|---|\n"
                                        "| CARD-005 | gone | closed | `mkway/cards/CARD-005-gone` |\n",
                                        encoding="utf-8")
    register.reseal(task, profile)
    assert cards.new_card(task, profile, "after five").name == "CARD-006-after-five"
    (folder / "CARD-999-big").mkdir()
    assert cards.new_card(task, profile, "big").name == "CARD-1000-big"
    assert cards.new_card(task, profile, "bigger").name == "CARD-1001-bigger"


def test_card_form_comes_from_the_engine_copy_only(task):
    """E27: the form is read from the engine copy (`cards/_TEMPLATE/CARD.md` beside the engine), never from the
    task's own cards folder, and is never copied into it."""
    planted = task / "mkway" / "cards" / "_TEMPLATE" / "CARD.md"
    planted.parent.mkdir(parents=True)
    planted.write_text("# <ID>: <title>\n\nA changed form.\n", encoding="utf-8")
    profile = json.loads((task / "mkway" / "profile.json").read_text(encoding="utf-8"))
    path = cards.new_card(task, profile, "Form check") / "CARD.md"
    assert "A changed form." not in path.read_text(encoding="utf-8")
    assert path.read_text(encoding="utf-8").splitlines()[1:] == TEMPLATE.read_text(encoding="utf-8").splitlines()[1:]
    assert cards.template_path() == TEMPLATE


def test_card_new_without_prefix_fails(tmp_path):
    """E28: with no `ids.card_prefix` in the profile, `card new` fails, names the key, and writes nothing."""
    root = tmp_path / "task"
    write_profile(root, make_profile())
    proc = _mkway(root, "card", "new", "x")
    assert proc.returncode == 1
    assert "ids.card_prefix" in proc.stderr
    assert not (root / "mkway" / "cards").exists()
