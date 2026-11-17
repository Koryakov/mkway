"""Card MW-071 (decision: R180), layer e2e: `card close` through the real CLI, with the agent definition of the checker on
disk: one deny (the checker lists Bash) and its nearest allow (Read, Grep). Synthetic task roots; the true verdict row has
its proof, so only the checker's definition decides. No test file is imported."""
import re

from _engine import agent_file, cli, task_root
from _mw068 import prove

NODE = "tests/test_a.py::test_one"
HEADER = "| Node | Verdict | Reason | By |\n|---|---|---|---|\n"


def _open_card(tmp_path, checker, tools):
    """An open card whose one row names `NODE`, a true verdict row by `s2` with its proof, and the checker's definition."""
    root = task_root(tmp_path, cards={"verdicts": "required"}, outbox={"checkers": [checker]}, agent_tools=None)
    agent_file(root, checker, tools)
    (root / "tests" / "verdicts").mkdir(parents=True)
    (root / "tests" / "test_a.py").write_text("def test_one():\n    pass\n", encoding="utf-8")
    assert cli(root, "card", "new", "First")[0] == 0
    (folder,) = [p for p in (root / "mkway" / "cards").iterdir() if p.name.startswith("CARD-001-")]
    text = (folder / "CARD.md").read_text(encoding="utf-8")
    text = re.sub(r"^\| \*\*Paths\*\* \|.*\|$", "| **Paths** | `src/a.py` |", text, flags=re.M)
    head = "| # | Item | Was | Must be | Test |\n|---|---|---|---|---|\n"
    start = text.index(head) + len(head)
    (folder / "CARD.md").write_text(text[:start] + f"| E1 | x | a | b | {NODE} |" + text[text.index("\n\n", start):],
                                    encoding="utf-8")
    assert cli(root, "card", "open", "CARD-001")[0] == 0
    (root / "tests" / "verdicts" / "CARD-001.md").write_text(HEADER + f"| {NODE} | true | fine | session:s2 |\n",
                                                             encoding="utf-8")
    prove(root, "CARD-001", "tests/test_a.py", "s2", agent_type=checker)
    return root


def _status(root):
    return re.search(r"\| CARD-001 \| .*? \| (\S+) \|", (root / "mkway" / "cards" / "REGISTER.md").read_text(
        encoding="utf-8")).group(1)


def test_the_real_close_is_refused_when_the_checker_lists_bash(tmp_path):
    """Catches: a card closed on a verdict whose checker has a shell (the old critic), the read-only rule not enforced."""
    root = _open_card(tmp_path, "critic", "Read, Grep, Bash")
    code, _out, err = cli(root, "card", "close", "CARD-001")
    assert code != 0
    assert "checker-not-read-only" in err
    assert "critic" in err
    assert "Bash" in err, err
    assert _status(root) == "open"


def test_the_real_close_passes_when_the_checker_lists_read_and_grep(tmp_path):
    """Checks: the nearest allow of the deny above, only the checker definition differs."""
    root = _open_card(tmp_path, "fresh-reader", "Read, Grep")
    code, _out, err = cli(root, "card", "close", "CARD-001")
    assert code == 0, err
    assert _status(root) == "closed"
