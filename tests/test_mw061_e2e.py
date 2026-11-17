"""Card MW-061, through the REAL hook command: one engine install (module fixture, a scratch git repository, the task
folder below the git top), one open card, another card's red test staged. The command is the exact shape of the real
report: a commit message with a real newline and an empty line inside double quotes, then `-- <folder> <folder>`.
The verdict is read from the hook's JSON (`tests/_hook_driver.py::decision`). Synthetic names only."""
import json
import sys

import pytest

from _hook_driver import decision, install_project
from _red_project import seed_record_file

# MW-085 (R213): engine_repo again (the install reads this repository), but not the shared lane; its module fixture builds once, on one worker
pytestmark = [pytest.mark.engine_repo, pytest.mark.xdist_group("test_mw061_e2e")]

CLI = "python mkway/engine/mkway.py"
BUILDER = "b1"
ONE = "CARD-001"
RED = 'def test_other():\n    """Catches: a red test of another card."""\n    assert 1 == 2\n'
BASE_P = 'def test_p():\n    """Checks: the baseline of the builder card test."""\n    assert 1 == 1\n'  # R216: a shape-conforming text
REAL = ('git commit -m "#90001 CARD-001 Add the totals report plan\n\n'
        '  Trailer: second paragraph <angle text>" -- report tests/report_plan')


def _card_text(template, paths):
    text = template.replace("| **Paths** | |", "| **Paths** | " + ", ".join(f"`{x}`" for x in paths) + " |")
    text = text.replace("«the owner's words, quoted» — owner, YYYY-MM-DD.", "A synthetic goal for the hook rows.")
    return text.replace("| E1 | item id | value today | value after the change | tests/test_x.py::test_y |",
                        "| E1 | the thing | absent | present | tests/report_plan/test_p.py::test_p |")


@pytest.fixture(scope="module")
def proj(tmp_path_factory):
    p = install_project(tmp_path_factory.mktemp("multiline"))
    p.profile(**{"python.command": sys.executable, "gates.trip": {"min_calls": 100000}})
    p.owner("card", "new", "Builder card")
    card_file = next((p.root / "mkway" / "cards").glob(f"{ONE}-*")) / "CARD.md"
    card_file.write_text(_card_text(card_file.read_text(encoding="utf-8"), ("report/", "tests/report_plan/", "tests/other_card/")),
                         encoding="utf-8", newline="\n")
    p.owner("card", "open", ONE)
    decision(p.fire("SessionStart", BUILDER))
    p.session_shell(BUILDER, f"{CLI} card take {ONE}")
    p.write("report/m.py", "V = 1\n")
    p.write("tests/report_plan/test_p.py", BASE_P)
    p.git("add", "-f", "--", "report/m.py", "tests/report_plan/test_p.py")
    p.git("add", "-A", "mkway/cards", "mkway/profile.json")
    p.git("commit", "-q", "-m", "baseline of the multi-line rows")
    # R217a: seeded red record, a precondition of the judged multi-line code commit (its subject), never a gate set to watch
    seed_record_file(p, ONE)
    return p


@pytest.fixture
def other_cards_red(proj):
    """Another card's red test is staged (it would be `new red` in a whole-index commit); the builder's own folders
    hold an edit each."""
    proj.write("tests/other_card/test_o.py", RED)
    proj.write("report/m.py", "V = 2\n")
    proj.git("add", "-f", "--", "tests/other_card/test_o.py", "report/m.py")
    proj.write("tests/report_plan/test_p.py", 'def test_p():\n    """Checks: the builder card test."""\n    assert 2 == 2\n')
    yield proj
    proj.git("reset", "-q", "--", "tests/other_card/test_o.py", "report/m.py", check=False)
    (proj.root / "tests" / "other_card" / "test_o.py").unlink()
    (proj.root / "tests" / "other_card").rmdir()
    proj.write("report/m.py", "V = 1\n")
    proj.write("tests/report_plan/test_p.py", BASE_P)


MARKER = ('git commit -m "#90001 CARD-001 the reader skips a <<EOF marker\n\nnot a here-doc: it is quoted text" '
          '-- report tests/report_plan')


@pytest.mark.parametrize("command", [REAL, REAL.replace("\n", "\r\n"), MARKER], ids=["lf", "crlf", "quoted-marker"])
def test_the_real_multiline_commit_is_allowed_through_the_real_hook(other_cards_red, command):
    """Checks: the exact real command, a newline and an empty line inside the double quotes and two folders after the dashes, passes every gate of the real hook while another card's red test is staged (E5)."""
    # guards the real-install refusal that took the whole index (40 `new red` tests of other cards) because the command was cut at its first newline
    got = decision(other_cards_red.fire("PreToolUse", BUILDER, "Bash", {"command": command}))
    assert got.kind == "allow", got


def test_the_same_state_as_a_plain_multiline_commit_is_denied(other_cards_red):
    """Catches: a gate that stopped reading the commit after the fix: the plain commit of the same state takes the staged red test and the real hook denies it commit-tests-failed (E5)."""
    command = 'git commit -m "#90001 CARD-001 change\n\n  second paragraph"'
    got = decision(other_cards_red.fire("PreToolUse", BUILDER, "Bash", {"command": command}))
    assert got.kind == "deny", got
    assert got.reason_id == "commit-tests-failed", got


def test_a_refusal_row_holds_the_whole_command(other_cards_red):
    """Catches: a refused multi-line command logged with its target cut at the first newline instead of whole with its newlines written as backslash n (E4)."""
    command = 'git commit -m "#90001 CARD-001 change\n\n  second paragraph"'
    got = decision(other_cards_red.fire("PreToolUse", BUILDER, "Bash", {"command": command}))
    assert got.kind == "deny", got
    log = other_cards_red.root / "mkway" / "state" / "refusals.jsonl"
    rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
    mine = [r for r in rows if r.get("reason_id") == "commit-tests-failed"]
    assert mine, rows
    assert mine[-1]["target"] == 'git commit -m "#90001 CARD-001 change\\n\\n  second paragraph"', mine[-1]
