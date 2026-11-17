"""Card MW-068 (ruling R173 items 1 and 2), layer shell: a verdict row counts only with its proof, and the whole check on a
real repository: a test committed by session S1 through the commit gate, a verdict by S1 refused, by S2 with proof allowed,
by S2 without proof refused. Real files, real git, synthetic sessions. The proof is what `tests/_mw068.py` leaves: the engine
command's record of the rows (decision: R196) and a fresh reader agent."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/: the shared helpers and `_engine`
from _commit_fixture import check, git, make_task, reason, stage, work  # noqa: E402
from _engine import task_root  # noqa: E402
from _mw068 import post, prove  # noqa: E402
import verdicts  # noqa: E402

NODE = "tests/test_a.py::test_one"
FILE = "tests/test_a.py"
HEADER = "| Node | Verdict | Reason | By |\n|---|---|---|---|\n"
CHECKERS = ["critic"]


def _verdict_file(root, *rows):
    folder = Path(root) / "tests" / "verdicts"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "CARD-001.md").write_text(HEADER + "".join(f"| {r} |\n" for r in rows), encoding="utf-8")


def _row(by, reason="fine"):
    return f"{NODE} | true | {reason} | session:{by}"


def _root(tmp_path):
    root = task_root(tmp_path, outbox={"checkers": CHECKERS})
    (root / "tests").mkdir()
    (root / "tests" / "test_a.py").write_text("def test_one():\n    pass\n", encoding="utf-8")
    return root


def _problems(root):
    return verdicts.proof_problems(root, root / "mkway" / "state", CHECKERS, "CARD-001",
                                   verdicts.rows_of(root, "CARD-001"))


def test_a_row_written_by_its_session_after_a_fresh_reader_is_proven(tmp_path):
    """Checks: the nearest allow of the unproven denies below, a row written by its session after a fresh reader is proven."""
    root = _root(tmp_path)
    _verdict_file(root, _row("s2"))
    prove(root, "CARD-001", FILE, "s2")
    assert _problems(root) == {}


def test_a_row_with_no_record_of_a_write_is_unproven(tmp_path):
    """Catches: a row typed by a shell, copied, or written by the code under check, counted as a reader's verdict."""
    root = _root(tmp_path)
    _verdict_file(root, _row("s2"))
    assert "no record" in _problems(root)[NODE]


def test_a_row_written_by_another_session_is_unproven(tmp_path):
    """Catches: a row that names the reader `s2` in its `by` while another session wrote the file."""
    root = _root(tmp_path)
    _verdict_file(root, _row("s2"))
    prove(root, "CARD-001", FILE, "s1")
    assert "no record" in _problems(root)[NODE]


def test_a_row_changed_after_its_write_record_is_unproven(tmp_path):
    """Catches: a row edited after the proof (a `weak` made `true`, a reason changed) still counted as the reader's."""
    root = _root(tmp_path)
    _verdict_file(root, _row("s2", "fine"))
    prove(root, "CARD-001", FILE, "s2")
    _verdict_file(root, _row("s2", "fine, and more"))
    assert "no record" in _problems(root)[NODE]


def test_a_row_stays_proven_when_another_session_adds_its_own_row_later(tmp_path):
    """Catches: the proof of an earlier row lost when a later write changes the file (the proof is per row, not per file)."""
    root = _root(tmp_path)
    other = "tests/test_b.py::test_two"
    _verdict_file(root, _row("s2"))
    prove(root, "CARD-001", FILE, "s2")
    _verdict_file(root, _row("s2"), f"{other} | true | fine | session:s3")
    (root / "tests" / "test_b.py").write_text("def test_two():\n    pass\n", encoding="utf-8")
    prove(root, "CARD-001", "tests/test_b.py", "s3")
    assert _problems(root) == {}


def test_a_row_with_no_fresh_reader_agent_is_unproven(tmp_path):
    """Catches: a write record alone counted, with no isolated reader behind the verdict."""
    root = _root(tmp_path)
    _verdict_file(root, _row("s2"))
    prove(root, "CARD-001", FILE, "s2", agent=False)
    assert "names no reader agent of a checker type" in _problems(root)[NODE]


def test_a_profile_with_no_checkers_proves_nothing(tmp_path):
    """Catches: every row counted as proven when the profile names no checker type, the same refusal the outbox gives."""
    root = _root(tmp_path)
    _verdict_file(root, _row("s2"))
    prove(root, "CARD-001", FILE, "s2")
    problems = verdicts.proof_problems(root, root / "mkway" / "state", [], "CARD-001", verdicts.rows_of(root, "CARD-001"))
    assert "outbox.checkers" in problems[NODE]


def test_a_write_of_another_file_leaves_no_verdict_record(tmp_path):
    """Catches: a verdict record written for any file the session writes, not only a verdict file."""
    root = _root(tmp_path)
    post(root, "tests/test_a.py", "s2")
    path = root / "mkway" / "state" / "outbox_checks.jsonl"
    assert not path.is_file() or "verdict-written" not in path.read_text(encoding="utf-8")


def test_the_facts_hold_the_proof_problem_of_each_named_row(tmp_path):
    """Catches: facts built with no proof problems, so the core never sees an unproven row."""
    root = _root(tmp_path)
    _verdict_file(root, _row("s2"))
    built = verdicts.build_facts(root, "CARD-001", [NODE], state=root / "mkway" / "state", checkers=CHECKERS)
    assert set(built.unproven) == {NODE}


# ---- the whole check on a real repository: S1 commits the test through the commit gate -----------------------------------

def _committed_by_s1(tmp_path):
    """A git task root where session S1 committed the test file through the real commit gate, then released the card."""
    import records
    root = make_task(tmp_path, card_paths="`tests/test_a.py`", session="S1", outbox={"checkers": CHECKERS})
    work(root, FILE, "def test_one():\n    pass\n")
    stage(root, FILE)
    assert reason(check(root, "git commit -m 'CARD-001 add the test'", session="S1")) == "allow"
    git(root, "commit", "-q", "-m", "CARD-001 add the test")
    records.append(root / "mkway" / "state", "S1", "release", "CARD-001")
    return root


def _verdict_problem(root):
    return verdicts.problem(root, "CARD-001", [NODE], "", root / "mkway" / "state", CHECKERS)


def test_a_verdict_by_the_session_that_committed_the_test_is_refused(tmp_path):
    """Catches: the session that committed the test judging it, although it has the proof of a reader."""
    root = _committed_by_s1(tmp_path)
    _verdict_file(root, _row("S1"))
    prove(root, "CARD-001", FILE, "S1")
    assert _verdict_problem(root)[0] == "verdict-by-committer"


def test_a_verdict_by_another_session_with_proof_is_allowed(tmp_path):
    """Checks: the nearest allow of the two denies around it, where only the reader's session differs from the refused one."""
    root = _committed_by_s1(tmp_path)
    _verdict_file(root, _row("S2"))
    prove(root, "CARD-001", FILE, "S2")
    assert _verdict_problem(root) is None


def test_a_verdict_by_another_session_without_proof_is_refused(tmp_path):
    """Catches: a row naming a reader who never wrote it (typed, copied or made by a shell) closing the card."""
    root = _committed_by_s1(tmp_path)
    _verdict_file(root, _row("S2"))
    assert _verdict_problem(root)[0] == "verdict-unproven"
