"""Card MW-070, through the REAL close command: one engine install (a scratch git repository, the task folder below the
git top), a card that the orderer session closes, an Acceptance test that reads a register file another card only
staged. The command is run as a session's shell runs it, with the real hooks before and after. Synthetic names only."""
import re
import sys

import pytest

from _hook_driver import decision, install_project

# MW-085 (R213): engine_repo again (the install reads this repository), but not the shared lane; its module fixture builds once, on one worker
pytestmark = [pytest.mark.engine_repo, pytest.mark.xdist_group("test_mw070_e2e")]

CLI = "python mkway/engine/mkway.py"
ORDERER, BUILDER = "s-orderer", "s-builder"
ONE = "CARD-001"
NODE = "tests/test_reg.py::test_the_register_is_done"
READS = ("from pathlib import Path\n\n\ndef test_the_register_is_done():\n"
         "    path = Path(__file__).resolve().parent.parent / 'data' / 'register.txt'\n"
         "    assert path.read_text(encoding='utf-8').strip() == 'done'\n")


def _card_text(template):
    text = template.replace("| **Paths** | |", "| **Paths** | `data/` |")
    text = text.replace("«the owner's words, quoted» — owner, YYYY-MM-DD.", "A synthetic goal for the close.")
    return text.replace("| E1 | item id | value today | value after the change | tests/test_x.py::test_y |",
                        f"| E1 | the register | absent | done | {NODE} |")


@pytest.fixture(scope="module")
def proj(tmp_path_factory):
    p = install_project(tmp_path_factory.mktemp("close"))
    p.profile(**{"python.command": sys.executable, "gates.trip": {"min_calls": 100000}, "cards.approver": "orderer",
                 "cards.verdicts": "off"})  # MW-068, R173 item 3: this flow judges the HEAD-tree run, not the verdict check
    p.owner("card", "new", "Register card")
    card_file = next((p.root / "mkway" / "cards").glob(f"{ONE}-*")) / "CARD.md"
    card_file.write_text(_card_text(card_file.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    p.write("tests/test_reg.py", READS)
    p.git("add", "-f", "--", "tests/test_reg.py")
    p.git("commit", "-q", "-m", "the test that reads the register")
    p.owner("card", "open", ONE)
    for session in (BUILDER, ORDERER):
        decision(p.fire("SessionStart", session))
    p.session_shell(BUILDER, f"{CLI} card take {ONE}")
    p.owner("card", "resync", "--add-ordered-by", check=False)
    p.owner("give", ONE, ORDERER)
    return p


def test_a_register_that_another_card_only_staged_refuses_the_real_close_command(proj):
    """Catches: a card closed green over a register file that was only staged, through the real close command and hooks. E10"""
    # the register file is in the index and not in HEAD; the orderer's card close through the real hooks exits non-zero
    # with close-tests-failing, names the node, says it ran on HEAD's tree, and the card stays open.
    proj.write("data/register.txt", "done\n")
    proj.git("add", "-f", "--", "data/register.txt")
    proc = proj.session_shell(ORDERER, f"{CLI} card close {ONE}", expect_ok=False)
    assert proc.returncode != 0, proc.stdout
    assert "close-tests-failing" in proc.stderr, proc.stderr
    assert NODE in proc.stderr, proc.stderr
    assert "HEAD's tree" in proc.stderr, proc.stderr
    register = (proj.root / "mkway" / "cards" / "REGISTER.md").read_text(encoding="utf-8")
    assert re.search(rf"^\| {ONE} \|.*\| open \|", register, re.M), register
