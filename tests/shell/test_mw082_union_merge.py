"""Card MW-082 (decisions: R197 A, R197a), rows E3 to E7, layer shell: two branches each append a line at the end of the
same section of a file; a real merge in a small synthetic git repository (core.autocrlf true, as in the engine's own
repository) with the engine's real .gitattributes. Synthetic files only, all inside tmp_path."""
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.engine_repo  # reads the real .gitattributes, which a copy of the engine lacks

REAL_ATTRIBUTES = Path(__file__).resolve().parents[2] / ".gitattributes"

CHANGELOG_BASE = "# Changes\n\n## 0.2.7\n- MW-001: one\n- MW-002: two\n\n## 0.2.6\n- MW-000: old\n"
CHANGELOG_OURS = CHANGELOG_BASE.replace("- MW-002: two\n", "- MW-002: two\n- MW-010: ours\n")
CHANGELOG_THEIRS = CHANGELOG_BASE.replace("- MW-002: two\n", "- MW-002: two\n- MW-011: theirs\n")
CHANGELOG_MERGED = "# Changes\n\n## 0.2.7\n- MW-001: one\n- MW-002: two\n- MW-010: ours\n- MW-011: theirs\n\n" \
                   "## 0.2.6\n- MW-000: old\n"

HEAD = "# Card register\n\n| Id | Title | Status | Folder |\n|---|---|---|---|\n| MW-001 | one | closed | `a` |\n"
LAST = "| MW-002 | two | proposed | `b` |"
REGISTER_BASE = HEAD + LAST  # the last row has no final newline, as on master
REGISTER_OURS = HEAD + LAST + "\n| MW-010 | ours | proposed | `c` |\n"
REGISTER_THEIRS = HEAD + LAST + "\n| MW-011 | theirs | proposed | `d` |\n"
REGISTER_MERGED = HEAD + LAST + "\n| MW-010 | ours | proposed | `c` |\n| MW-011 | theirs | proposed | `d` |\n"


def _git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, timeout=15)


def _write(repo, name, text):
    target = repo / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(text.encode("utf-8"))


def _commit(repo, message):
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)


def _merge(tmp_path, name, base, ours, theirs, attributes_as=".gitattributes"):
    """Build the repository (the real attributes file is copied in as `attributes_as`), merge `theirs` into
    `ours`, and return (exit code of the merge, the merged file with LF line ends)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.name", "tester")
    _git(repo, "config", "user.email", "tester")
    _git(repo, "config", "core.autocrlf", "true")
    _git(repo, "config", "commit.gpgsign", "false")
    _write(repo, name, base)
    shutil.copy(REAL_ATTRIBUTES, repo / attributes_as)
    _commit(repo, "base")
    _git(repo, "checkout", "-q", "-b", "other")
    _write(repo, name, theirs)
    _commit(repo, "theirs")
    _git(repo, "checkout", "-q", "main")
    _write(repo, name, ours)
    _commit(repo, "ours")
    done = _git(repo, "merge", "--no-ff", "--no-edit", "other")
    return done.returncode, (repo / name).read_bytes().decode("utf-8").replace("\r\n", "\n")


def test_changelog_merge_exits_zero(tmp_path):
    """Catches: two appended changelog lines at the end of one section that still conflict."""
    code, _text = _merge(tmp_path, "CHANGELOG.md", CHANGELOG_BASE, CHANGELOG_OURS, CHANGELOG_THEIRS)
    assert code == 0


def test_changelog_merge_keeps_each_line_once_and_the_heading(tmp_path):
    """Catches: a merged changelog that drops a line, repeats one, or damages the heading after the section."""
    _code, text = _merge(tmp_path, "CHANGELOG.md", CHANGELOG_BASE, CHANGELOG_OURS, CHANGELOG_THEIRS)
    assert text == CHANGELOG_MERGED


def test_register_merge_exits_zero(tmp_path):
    """Catches: two appended register rows after a last row without a final newline that still conflict."""
    code, _text = _merge(tmp_path, "cards/REGISTER.md", REGISTER_BASE, REGISTER_OURS, REGISTER_THEIRS)
    assert code == 0


def test_register_merge_keeps_each_row_once_on_its_own_line(tmp_path):
    """Catches: a merged register that repeats the base row, drops a row, or joins two rows on one line."""
    _code, text = _merge(tmp_path, "cards/REGISTER.md", REGISTER_BASE, REGISTER_OURS, REGISTER_THEIRS)
    assert text == REGISTER_MERGED


def test_register_merge_without_the_attributes_conflicts(tmp_path):
    """Catches: a register merge without the attributes file still conflicts, so the union driver is not applied."""
    # the union driver is what removes the conflict
    code, _text = _merge(tmp_path, "cards/REGISTER.md", REGISTER_BASE, REGISTER_OURS, REGISTER_THEIRS, "attributes.off")
    assert code != 0
