"""Card MW-082 (decisions: R197 A, R197a), rows E1, E2, E16: the repository's own .gitattributes names the union merge
driver for the two append-only files. Reads the real repository."""
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.mark.engine_repo
def test_the_attributes_file_holds_the_two_union_lines():
    """Catches: a repository without the union attribute for the changelog and the register."""
    lines = (REPO / ".gitattributes").read_text(encoding="utf-8").splitlines()
    assert lines == ["CHANGELOG.md merge=union", "cards/REGISTER.md merge=union"]


@pytest.mark.engine_repo
def test_git_reads_union_for_both_files():
    """Catches: an attribute line that git does not apply to the two files."""
    done = subprocess.run(["git", "check-attr", "merge", "--", "CHANGELOG.md", "cards/REGISTER.md"], cwd=REPO,
                          capture_output=True, text=True, timeout=20)
    assert done.stdout.splitlines() == ["CHANGELOG.md: merge: union", "cards/REGISTER.md: merge: union"]


def _last_bytes(*names):
    return [(REPO / name).read_bytes()[-1:] for name in names]


@pytest.mark.engine_repo
def test_both_union_files_end_with_a_newline():
    """Catches: a union file whose last line has no newline, which two branches then both change."""
    assert _last_bytes("CHANGELOG.md", "cards/REGISTER.md") == [b"\n", b"\n"]
