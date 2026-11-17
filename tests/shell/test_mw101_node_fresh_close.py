"""Card MW-101 (decisions: R196, R253), layer shell: `card close` on the shape of a real case. A card of four test nodes in one
file; one reader run says all four true, a second says the fourth is weak; the lead changes only the fourth test and recuts
it; a new reader writes its row true. Before this card the close refused the three untouched nodes, because the test file's
mtime was newer than their reader. The close is the real command (the owner's terminal) and the real verdict check, on a
real small git repository. Synthetic names only."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/: the shared helpers and `_engine`
import _mw080 as w  # noqa: E402
import _mw100 as m  # noqa: E402
import cardtool  # noqa: E402
import register  # noqa: E402

FIXTURE = chr(64) + "pytest.fixture"
SRC = ("import pytest" + "\n" * 3 + FIXTURE + chr(10) + "def box():\n    return 1\n\n\n"
       "def test_one(box):\n    assert box == 1\n\n\ndef test_two():\n    assert True\n\n\ndef test_three():\n    assert True\n\n\n"
       "def test_four():\n    assert 4 == 4\n")
NODES = [f"{w.FILE}::test_{name}" for name in ("one", "two", "three", "four")]
FOURTH = NODES[3]
TEXT = ("# CARD-001: First\n\n## Acceptance examples\n\n| # | Item | Was | Must be | Test |\n|---|---|---|---|---|\n"
        + "".join(f"| E{n} | item | was | must | {node} |\n" for n, node in enumerate(NODES, 1))
        + "\n## 8. Log\n\n| Date | Step | Commit | Result |\n|---|---|---|---|\n")


def _commit(root, text, when):
    (Path(root) / w.FILE).write_text(text, encoding="utf-8")
    w.git(root, "add", "-f", "--", w.FILE)
    w.git(root, "commit", "-q", "-m", f"{w.CARD} the file changes", when=when)


def _world(tmp_path, monkeypatch):
    """Run 1 (agent-1): four true. Run 2 (agent-2): the fourth weak. The fix to the fourth test only, the records as an older
    engine wrote them (no `nodes`), the lead's recut of the fourth, then run 3 (agent-3): the fourth true."""
    root = w.make_root(tmp_path)
    cardtool.card_file(root, w.profile_of(root), w.CARD).write_text(TEXT, encoding="utf-8")
    (Path(root) / w.FILE).write_text(SRC, encoding="utf-8")
    w.git(root, "add", "-f", "--", w.FILE, m.card_rel(root))
    w.git(root, "commit", "-q", "-m", f"{w.CARD} the card and the tests", when=-3000)
    assert w.cli(root, "card", "resync", "--add-ordered-by")[0] == 0
    register.set_ordered(root, w.profile_of(root), w.CARD, m.LEAD)
    w.add_agent(root, session="reader1", agent_type=w.CHECKER, agent_id="agent-1", started=60, ended=120, guard=w.CARD)
    m.clock(monkeypatch, 125)
    assert w.apply(root, "reader1", NODES, "true", "one clause, one case").allowed
    w.add_agent(root, session="reader2", agent_type=w.CHECKER, agent_id="agent-2", started=140, ended=190, guard=w.CARD)
    m.clock(monkeypatch, 195)
    assert w.apply(root, "reader2", [FOURTH], "weak", "the row says four, the test compares four with itself").allowed
    _commit(root, SRC.replace("assert 4 == 4", 'assert len("four") == 4'), 192)
    m.strip_nodes(root)
    assert m.recut(root, monkeypatch, node=FOURTH, reason="the test now compares the count", at=200).allowed
    w.add_agent(root, session="reader3", agent_type=w.CHECKER, agent_id="agent-3", started=260, ended=300, guard=w.CARD)
    m.clock(monkeypatch, 320)
    assert w.apply(root, "reader3", [FOURTH], "true", "the new cut reads fine").allowed
    return root


def test_card_close_passes_with_three_unchanged_nodes_and_one_recut_node(tmp_path, monkeypatch):
    """Checks: the real `card close` passes the verdict check on three untouched nodes plus one recut node with a new true row."""
    root = _world(tmp_path, monkeypatch)
    code, _out, err = w.cli(root, "card", "close", w.CARD)
    assert (code, "verdict-unproven" in err, register.find(register.read(root, w.profile_of(root)), w.CARD)["status"]) == (
        0, False, "closed")


def test_card_close_refuses_unproven_after_a_fixture_change(tmp_path, monkeypatch):
    """Catches: R253, a fixture changed after the rows and the close still passing; every node of the file is named."""
    root = _world(tmp_path, monkeypatch)
    text = (Path(root) / w.FILE).read_text(encoding="utf-8")
    _commit(root, text.replace("return 1", "return 7", 1), 400)
    code, _out, err = w.cli(root, "card", "close", w.CARD)
    assert (code != 0, "mkway: verdict-unproven:" in err, "non-test code" in err, [n in err for n in NODES]) == (
        True, True, True, [True] * 4)


def test_replay_a_sibling_recut_leaves_three_rows_fresh(tmp_path, monkeypatch):
    """Catches: the real case, three true rows refused `verdict-unproven` because the file's mtime was newer than their reader."""
    root = _world(tmp_path, monkeypatch)
    assert m.close_reason(root) == ("", "")
