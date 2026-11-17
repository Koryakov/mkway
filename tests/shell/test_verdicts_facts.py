"""Card MW-068, layer shell: the readers that build the facts of the verdict check, on real git and real files.
Synthetic names only; each repository is built here, in the test's own temp folder."""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/: `_engine` puts engine/ on the path
import _engine  # noqa: E402,F401
import verdicts  # noqa: E402
from core_verdicts import Row  # noqa: E402

NODE = "tests/case_a.py::test_one"
HEADER = "| Node | Verdict | Reason | By |\n|---|---|---|---|\n"


def git(root, *args):
    subprocess.run(["git", "-c", "commit.gpgsign=false", *args], cwd=root, check=True, capture_output=True, timeout=20)


def commit(root, name, message):
    git(root, "add", "-A")
    git(root, "-c", f"user.name={name}", "-c", "user.email=mkway-test", "commit", "-m", message)


def repo(tmp_path):
    root = tmp_path / "repo"
    (root / "tests").mkdir(parents=True)
    git(root, "init", "-q")
    return root


def test_the_authors_of_a_file_are_read_from_real_git(tmp_path):
    """Catches: only the last committer read, so an earlier author of the test file may judge it."""
    root = repo(tmp_path)
    (root / "tests" / "case_a.py").write_text("def test_one():\n    pass\n", encoding="utf-8")
    (root / "tests" / "case_b.py").write_text("def test_two():\n    pass\n", encoding="utf-8")
    commit(root, "writer-one", "first")
    (root / "tests" / "case_a.py").write_text("def test_one():\n    assert True\n", encoding="utf-8")
    commit(root, "writer-two", "second")
    (root / "tests" / "case_b.py").write_text("def test_two():\n    assert 1\n", encoding="utf-8")
    commit(root, "writer-three", "third")
    assert verdicts.authors_of(root, "tests/case_a.py") == frozenset({"writer-one", "writer-two"})


def test_an_untracked_file_and_a_folder_with_no_git_have_no_author(tmp_path):
    """Catches: a crash, or a made-up author, where git has nothing to say."""
    root = repo(tmp_path)
    (root / "tests" / "case_new.py").write_text("def test_n():\n    pass\n", encoding="utf-8")
    plain = tmp_path / "plain"
    (plain / "tests").mkdir(parents=True)
    (plain / "tests" / "case_a.py").write_text("def test_one():\n    pass\n", encoding="utf-8")
    assert verdicts.authors_of(root, "tests/case_new.py") == frozenset()
    assert verdicts.authors_of(plain, "tests/case_a.py") == frozenset()


def test_the_verdict_file_rows_are_read(tmp_path):
    """Catches: the header or the separator read as a row, a backtick left in a node id, a cell cut at the wrong bar."""
    folder = tmp_path / "tests" / "verdicts"
    folder.mkdir(parents=True)
    (folder / "CARD-001.md").write_text(
        "# Verdicts of CARD-001\n\n" + HEADER
        + f"| `{NODE}` | true | one clause, one case | session:reader-1 |\n"
        + "| tests/case_b.py::test_two | Weak | no Catches line | session:reader-1 |\n", encoding="utf-8")
    assert verdicts.rows_of(tmp_path, "CARD-001") == [
        Row(NODE, "true", "one clause, one case", "session:reader-1"),
        Row("tests/case_b.py::test_two", "weak", "no Catches line", "session:reader-1")]


def test_a_missing_verdict_file_has_no_rows(tmp_path):
    """Catches: a crash, or a refusal that names the wrong problem, when the verdict file does not exist."""
    assert verdicts.rows_of(tmp_path, "CARD-001") == []


def test_the_facts_hold_the_nodes_the_rows_and_the_authors(tmp_path):
    """Catches: facts that miss an author of one named file, or a row of the card's verdict file."""
    root = repo(tmp_path)
    (root / "tests" / "case_a.py").write_text("def test_one():\n    pass\n", encoding="utf-8")
    commit(root, "writer-one", "first")
    folder = root / "tests" / "verdicts"
    folder.mkdir()
    (folder / "CARD-001.md").write_text(HEADER + f"| {NODE} | true | fine | session:reader-1 |\n", encoding="utf-8")
    built = verdicts.build_facts(root, "CARD-001", [NODE])
    assert built.nodes == (NODE,)
    assert built.rows == (Row(NODE, "true", "fine", "session:reader-1"),)
    assert built.authors == {"tests/case_a.py": frozenset({"writer-one"})}
