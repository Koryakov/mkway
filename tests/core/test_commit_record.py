"""Card MW-068 (ruling R173 item 1), layer core: the row the commit gate writes for an allowed commit, as a table. No disk,
no git, no clock. Synthetic sessions, trees and paths only. Each expected value is written from the card row, never from
`commit_record`."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/: `_engine` puts engine/ on the path
import _engine  # noqa: E402,F401
import core  # noqa: E402

TREE = "a" * 40
TAKEN = (("A", "tests/test_a.py", "index"), ("M", "src/b.py", "work"), ("D", "old.py", "index"))


def test_an_allowed_commit_with_a_session_and_a_tree_has_one_record():
    """Checks: the nearest allow of every deny below, the file name, the session, the tree and every path taken."""
    assert core.commit_record("s1", TREE, TAKEN) == (
        "commit_records.jsonl", {"kind": "commit", "session": "s1", "tree": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                                 "paths": ["tests/test_a.py", "src/b.py", "old.py"]})


@pytest.mark.parametrize("session", ["", "   ", None, "not established"])
def test_a_commit_of_no_known_session_has_no_record(session):
    """Catches: a record that names no session (or `not established`), which a later close would match to nobody and could never refuse."""
    assert core.commit_record(session, TREE, TAKEN) is None


@pytest.mark.parametrize("tree", ["", "   ", None])
def test_a_commit_with_no_tree_has_no_record(tree):
    """Catches: a record with no tree sha, which no commit can be matched to afterwards."""
    assert core.commit_record("s1", tree, TAKEN) is None


def test_a_commit_that_takes_no_file_has_no_record():
    """Catches: a record with no path, which can be matched to no test file."""
    assert core.commit_record("s1", TREE, ()) is None


def test_a_commit_whose_files_could_not_be_read_has_no_record():
    """Catches: a crash, or a record of invented paths, when git did not say what the commit takes."""
    assert core.commit_record("s1", TREE, core.Unread()) is None
