"""Card MW-071 (decision: R181), layer shell: the run count of a card and the nodes changed in the card's own commits, on real
files and real git. Synthetic sessions, authors and names."""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/: the shared helpers and `_engine`
from _engine import task_root  # noqa: E402
from _mw068 import prove  # noqa: E402
import profiles  # noqa: E402
import verdicts  # noqa: E402

CHECKER = "fresh-reader"
FILE = "tests/test_a.py"
OLD, NEW = f"{FILE}::test_old", f"{FILE}::test_new"
HEADER = "| Node | Verdict | Reason | By |\n|---|---|---|---|\n"
TESTS = "def test_old():\n    assert True\n\n\ndef test_new():\n    assert True\n"


def _git(root, *args):
    subprocess.run(["git", "-c", "commit.gpgsign=false", "-c", "user.name=writer", "-c", "user.email=x", *args],
                   cwd=root, check=True, capture_output=True, timeout=20)


def _root(tmp_path):
    root = task_root(tmp_path, outbox={"checkers": [CHECKER]})
    (root / "tests").mkdir()
    (root / FILE).write_text(TESTS, encoding="utf-8")
    return root


def _runs(root, sessions):
    """Each session in `sessions` writes a `true` row for NEW and has its proof, in order (the last row is the verdict)."""
    folder = root / "tests" / "verdicts"
    folder.mkdir(parents=True, exist_ok=True)
    text = HEADER
    for session in sessions:
        text += f"| {NEW} | true | fine | session:{session} |\n"
        (folder / "CARD-001.md").write_text(text, encoding="utf-8")
        prove(root, "CARD-001", FILE, session, agent_type=CHECKER)
    return verdicts.problem(root, "CARD-001", [NEW], "", root / "mkway" / "state", [CHECKER])


def test_two_reader_sessions_on_a_card_let_the_close_pass(tmp_path):
    """Checks: two reader sessions on a card let the close pass, the nearest allow of the third-run deny."""
    assert _runs(_root(tmp_path), ["s2", "s3"]) is None


def test_three_reader_sessions_on_a_card_are_refused_naming_the_two_earlier(tmp_path):
    """Catches: a third reader run accepted, so a card is judged again and again until one verdict passes."""
    problem = _runs(_root(tmp_path), ["s2", "s3", "s4"])
    assert problem is not None
    assert problem[0] == "verdict-runs-exceeded"
    assert "s2" in problem[1]
    assert "s3" in problem[1]


def test_the_proof_record_of_a_write_holds_the_run_number(tmp_path):
    """Catches: the run count left out of the engine record, so nobody can see how many runs a card has had."""
    root = _root(tmp_path)
    _runs(root, ["s2", "s3"])
    profile = json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))
    rows = [json.loads(x) for x in (profiles.state_dir(root, profile) / "outbox_checks.jsonl").read_text(
        encoding="utf-8").splitlines()]
    assert [r["run"] for r in rows if r.get("kind") == "verdict-written"] == [1, 2]


def _repo_with_old_test_and_a_card_commit(tmp_path):
    """The test file with `test_old` is committed by an older commit; the card's own commit (its message names the card)
    adds `test_new` only."""
    root = _root(tmp_path)
    (root / FILE).write_text("def test_old():\n    assert True\n", encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "add", FILE)
    _git(root, "commit", "-q", "-m", "an older test")
    (root / FILE).write_text(TESTS, encoding="utf-8")
    _git(root, "add", FILE)
    _git(root, "commit", "-q", "-m", "CARD-001 add the new test")
    return root


def test_a_node_the_card_commits_did_not_change_needs_no_verdict_row(tmp_path):
    """Catches: an older test the card never touched refused for a verdict nobody must write."""
    root = _repo_with_old_test_and_a_card_commit(tmp_path)
    assert verdicts.problem(root, "CARD-001", [OLD], "", None, None) is None


def test_a_node_the_card_commits_added_needs_a_verdict_row(tmp_path):
    """Catches: a node the card's commit added closed without a verdict row."""
    root = _repo_with_old_test_and_a_card_commit(tmp_path)
    problem = verdicts.problem(root, "CARD-001", [NEW], "", None, None)
    assert problem is not None
    assert problem[0] == "verdict-missing"
