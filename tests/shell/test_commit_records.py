"""Card MW-068 (ruling R173 item 1), layer shell: the commit gate writes one record per allowed commit (the session, the
tree git commits, the paths) and the verdict check reads the committers of a test file back by that tree. Real throwaway
git repositories, synthetic sessions. The expected tree is what git says after the real commit, never what the gate says."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/: `_commit_fixture` and `_engine`
from _commit_fixture import check, git, make_task, reason, save, stage, work  # noqa: E402
from _engine import jsonl  # noqa: E402
import records  # noqa: E402
import verdicts  # noqa: E402

NODE = "tests/test_a.py::test_one"
FILE = "tests/test_a.py"
OTHER = "tests/test_b.py"
HEADER = "| Node | Verdict | Reason | By |\n|---|---|---|---|\n"


def _task(tmp_path):
    return make_task(tmp_path, card_paths="`tests/test_a.py`, `tests/test_b.py`, `src/`", session="S1")


def _state(root):
    return root / "mkway" / "state"


def _rows(root):
    path = _state(root) / "commit_records.jsonl"
    return jsonl(path) if path.is_file() else []


def test_an_allowed_commit_writes_one_record_keyed_by_the_tree_git_commits(tmp_path):
    """Catches: no record of an allowed commit, or a record whose tree differs from the tree git then commits."""
    root = _task(tmp_path)
    work(root, FILE)
    stage(root, FILE)
    assert reason(check(root, "git commit -m 'CARD-001 add the test'", session="S1")) == "allow"
    git(root, "commit", "-q", "-m", "CARD-001 add the test")
    rows = _rows(root)
    assert len(rows) == 1
    assert (rows[0]["kind"], rows[0]["session"], rows[0]["paths"]) == ("commit", "S1", [FILE])
    assert rows[0]["tree"] == git(root, "rev-parse", "HEAD^{tree}").strip()


def test_a_commit_of_named_paths_records_the_tree_that_commit_makes(tmp_path):
    """Catches: the index tree recorded for a `-- <paths>` commit, which commits HEAD plus the named paths only."""
    root = _task(tmp_path)
    save(root, FILE, "v1\n")
    work(root, FILE, "v2\n")
    work(root, OTHER)
    # another file staged by someone else is no part of it
    stage(root, OTHER)
    command = f"git commit -m 'CARD-001 edit the test' -- {FILE}"
    assert reason(check(root, command, session="S1")) == "allow"
    git(root, "commit", "-q", "-m", "CARD-001 edit the test", "--", FILE)
    rows = _rows(root)
    assert len(rows) == 1
    assert rows[0]["paths"] == [FILE]
    assert rows[0]["tree"] == git(root, "rev-parse", "HEAD^{tree}").strip()


def test_a_refused_commit_writes_no_record(tmp_path):
    """Catches: a record written for a commit the gate refused (the message names no card), naming a session as committer."""
    root = _task(tmp_path)
    work(root, FILE)
    stage(root, FILE)
    assert reason(check(root, "git commit -m 'add the test'", session="S1")) == "commit-message-card"
    assert _rows(root) == []


def test_the_committers_of_a_file_are_the_sessions_whose_record_tree_is_a_commit_of_it(tmp_path):
    """Catches: committers read from the git author name (mkway-test here) instead of the record matching the commit tree."""
    root = _task(tmp_path)
    work(root, FILE)
    stage(root, FILE)
    assert reason(check(root, "git commit -m 'CARD-001 add the test'", session="S1")) == "allow"
    git(root, "commit", "-q", "-m", "CARD-001 add the test")
    assert verdicts.committers_of(root, _state(root), FILE) == frozenset({"S1"})


def test_a_second_session_that_commits_another_file_is_the_committer_of_that_file_only(tmp_path):
    """Catches: every session of every record named as a committer of every test file."""
    root = _task(tmp_path)
    work(root, FILE)
    stage(root, FILE)
    assert reason(check(root, "git commit -m 'CARD-001 add a'", session="S1")) == "allow"
    git(root, "commit", "-q", "-m", "CARD-001 add a")
    records.append(_state(root), "S1", "release", "CARD-001")
    records.append(_state(root), "S2", "take", "CARD-001")
    work(root, OTHER)
    stage(root, OTHER)
    assert reason(check(root, "git commit -m 'CARD-001 add b'", session="S2")) == "allow"
    git(root, "commit", "-q", "-m", "CARD-001 add b")
    assert verdicts.committers_of(root, _state(root), OTHER) == frozenset({"S2"})
    assert verdicts.committers_of(root, _state(root), FILE) == frozenset({"S1"})


def test_a_file_committed_with_no_record_has_no_committer(tmp_path):
    """Catches: a legacy test committed before the record existed, or by the owner's terminal, given a made-up committer."""
    root = _task(tmp_path)
    save(root, FILE)
    assert verdicts.committers_of(root, _state(root), FILE) == frozenset()


def test_a_record_of_a_tree_that_never_became_a_commit_names_no_committer(tmp_path):
    """Catches: a record matched to a file by its paths alone, so a commit the session never made still names it."""
    root = _task(tmp_path)
    work(root, FILE)
    stage(root, FILE)
    assert reason(check(root, "git commit -m 'CARD-001 add the test'", session="S1")) == "allow"
    assert len(_rows(root)) == 1
    save(root, FILE, "another content\n")  # the file is committed in another tree: the record's tree is no commit
    assert verdicts.committers_of(root, _state(root), FILE) == frozenset()


def test_the_facts_hold_the_committers_of_each_named_file(tmp_path):
    """Catches: facts built with no committers, so the core never sees the commit records of the named test files."""
    root = _task(tmp_path)
    work(root, FILE)
    stage(root, FILE)
    assert reason(check(root, "git commit -m 'CARD-001 add the test'", session="S1")) == "allow"
    git(root, "commit", "-q", "-m", "CARD-001 add the test")
    folder = root / "tests" / "verdicts"
    folder.mkdir()
    (folder / "CARD-001.md").write_text(HEADER + f"| {NODE} | true | fine | session:S2 |\n", encoding="utf-8")
    built = verdicts.build_facts(root, "CARD-001", [NODE], state=_state(root))
    assert built.committers == {FILE: frozenset({"S1"})}
