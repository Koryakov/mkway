"""Card MW-068, layer e2e: `card close` through the real CLI, one deny per refusal reason of the verdict check and the
nearest allow. Synthetic task roots, each its own small git repository, with a test file committed by a synthetic
author. No test file is imported."""
import re
import subprocess

import pytest

from _engine import cli, task_root
from _mw068 import prove

NODE = "tests/test_a.py::test_one"
HEADER = "| Node | Verdict | Reason | By |\n|---|---|---|---|\n"


def _git(root, *args):
    subprocess.run(["git", "-c", "commit.gpgsign=false", *args], cwd=root, check=True, capture_output=True, timeout=20)


def _card_file(root):
    (folder,) = [p for p in (root / "mkway" / "cards").iterdir() if p.name.startswith("CARD-001-")]
    return folder / "CARD.md"


def _set_card(root, cell):
    path = _card_file(root)
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"^\| \*\*Paths\*\* \|.*\|$", "| **Paths** | `src/a.py` |", text, flags=re.M)
    head = "| # | Item | Was | Must be | Test |\n|---|---|---|---|---|\n"
    start = text.index(head) + len(head)
    end = text.index("\n\n", start)
    path.write_text(text[:start] + f"| E1 | x | a | b | {cell} |" + text[end:], encoding="utf-8")


def _verdicts(root, *rows, proved=True):
    """The verdict file, and (R173 item 2) the proof of each reader session in it: its write record and a fresh reader
    agent. `proved=False` leaves the rows with no proof."""
    folder = root / "tests" / "verdicts"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "CARD-001.md").write_text(HEADER + "".join(f"| {r} |\n" for r in rows), encoding="utf-8")
    if proved:
        for by in dict.fromkeys(r.rsplit("|", 1)[1].strip().removeprefix("session:") for r in rows):
            prove(root, "CARD-001", "tests/test_a.py", by)


def _status(root):
    return re.search(r"\| CARD-001 \| .*? \| (\S+) \|", (root / "mkway" / "cards" / "REGISTER.md").read_text(
        encoding="utf-8")).group(1)


def _reason(err):
    found = re.search(r"mkway: ([a-z-]+):", err)
    return found.group(1) if found else None


def _make(tmp_path, **over):
    """An open card whose one row names `NODE`; the test file was committed by the author `writer`."""
    root = task_root(tmp_path, cards={"verdicts": "required"}, **over)
    (root / "tests").mkdir()
    (root / "tests" / "test_a.py").write_text("def test_one():\n    pass\n", encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "add", "tests/test_a.py")
    _git(root, "-c", "user.name=writer", "-c", "user.email=mkway-test", "commit", "-m", "add the test")
    assert cli(root, "card", "new", "First")[0] == 0
    _set_card(root, NODE)
    assert cli(root, "card", "open", "CARD-001")[0] == 0
    return root


@pytest.fixture
def task(tmp_path):
    return _make(tmp_path, outbox={"checkers": ["critic"]})


def test_close_passes_and_says_so_when_outbox_checkers_is_missing(tmp_path):
    """Catches: a close that passes without saying the blind verdict was not enforced, in its output and its record. Ruling R179 condition 1."""
    root = _make(tmp_path)
    code, out, err = cli(root, "card", "close", "CARD-001")
    assert code == 0, err
    assert "blind verdict not enforced: outbox.checkers missing in profile" in out + err
    assert _status(root) == "closed"
    records = (root / "mkway" / "state" / "outbox_checks.jsonl").read_text(encoding="utf-8")
    assert "verdict-not-enforced" in records
    assert "CARD-001" in records


def test_close_is_refused_while_a_named_node_has_no_verdict_row(task):
    """Catches: a card that closes on a test no reader judged (no verdict file, or a file with no row for the node)."""
    code, _out, err = cli(task, "card", "close", "CARD-001")
    assert code != 0
    assert _reason(err) == "verdict-missing"
    assert NODE in err, err
    _verdicts(task, "tests/test_other.py::test_x | true | fine | session:reader")
    code, _out, err = cli(task, "card", "close", "CARD-001")
    assert code != 0
    assert _reason(err) == "verdict-missing"
    assert NODE in err, err
    assert _status(task) == "open"


def test_close_is_refused_when_the_reader_is_an_author_of_the_test_file(task):
    """Catches: a test judged by the person who wrote it passing as a blind verdict."""
    _verdicts(task, f"{NODE} | true | fine | writer")
    code, _out, err = cli(task, "card", "close", "CARD-001")
    assert code != 0
    assert _reason(err) == "verdict-by-author"
    assert NODE in err
    assert "writer" in err, err
    assert _status(task) == "open"


def test_close_is_refused_on_a_weak_verdict(task):
    """Catches: a card closed on a test the reader called weak; the reason of the row is shown."""
    _verdicts(task, f"{NODE} | weak | no Catches line | session:reader")
    code, _out, err = cli(task, "card", "close", "CARD-001")
    assert code != 0
    assert _reason(err) == "verdict-weak"
    assert NODE in err
    assert "no Catches line" in err, err
    assert _status(task) == "open"


def test_close_is_refused_on_a_wrong_verdict(task):
    """Catches: a card closed on a test the reader called wrong; the reason of the row is shown."""
    _verdicts(task, f"{NODE} | wrong | expects the code's own output | session:reader")
    code, _out, err = cli(task, "card", "close", "CARD-001")
    assert code != 0
    assert _reason(err) == "verdict-wrong"
    assert NODE in err
    assert "own output" in err, err
    assert _status(task) == "open"


def test_a_true_row_by_another_reader_lets_the_card_close(task):
    """Checks: a true row by another reader lets the card close, the nearest allow of the four denies above."""
    _verdicts(task, f"{NODE} | true | one clause, one case | session:reader")
    code, _out, err = cli(task, "card", "close", "CARD-001")
    assert code == 0, err
    assert _status(task) == "closed"


def test_close_is_refused_when_the_true_row_has_no_proof(task):
    """Catches: a true row nobody proved closing the card, ruling R173 item 2."""
    _verdicts(task, f"{NODE} | true | one clause, one case | session:reader", proved=False)
    code, _out, err = cli(task, "card", "close", "CARD-001")
    assert code != 0
    assert _reason(err) == "verdict-unproven"
    assert NODE in err, err
    assert _status(task) == "open"


def test_a_card_checked_by_reading_closes_with_no_verdict_file(task):
    """Catches: a card that names no test node refused for a verdict file it cannot have."""
    _set_card(task, "checked by reading: tests/test_a.py")
    code, _out, err = cli(task, "card", "close", "CARD-001")
    assert code == 0, err
    assert _status(task) == "closed"


def test_cards_verdicts_off_skips_the_check(tmp_path):
    """Catches: a profile that switched the check off still refused (the key is read and obeyed)."""
    root = task_root(tmp_path, cards={"verdicts": "off"})
    (root / "tests").mkdir()
    (root / "tests" / "test_a.py").write_text("def test_one():\n    pass\n", encoding="utf-8")
    assert cli(root, "card", "new", "First")[0] == 0
    _set_card(root, NODE)
    assert cli(root, "card", "open", "CARD-001")[0] == 0
    code, _out, err = cli(root, "card", "close", "CARD-001")
    assert code == 0, err
