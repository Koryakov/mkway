"""`mkway install` and the register seal (card MW-003, deliverable 3; R19a, R19c). Synthetic tasks built from this
repository's working tree, so these run only in the engine repository (marker `engine_repo`)."""
import subprocess

import pytest

from _engine import jsonl  # noqa: F401
from test_install import GIT_ID, clean_env, make_source, make_task, mkway

pytestmark = pytest.mark.engine_repo

REG = "mkway/cards/REGISTER.md"
ROW = "| CARD-001 | First | open |  | `mkway/cards/CARD-001-first` |\n"
HEAD_TEXT = "# Card register\n\n| Id | Title | Status | Paths | Folder |\n|---|---|---|---|---|\n"


def _git(cwd, *args):
    return subprocess.run(["git", *GIT_ID, *args], cwd=str(cwd), capture_output=True, text=True, check=True).stdout


def test_install_writes_gitattributes_and_seals_only_the_head_register(tmp_path):
    """E19: install creates the bundle `.gitattributes` with the register's `-text` line when the file or the line
    is missing, and keeps other lines; it writes `register.sha` only when the register equals HEAD's blob,
    otherwise it says the register differs from HEAD and leaves the seal missing.
    Catches: a seal written over an uncommitted (possibly forged) register, or a missing `-text` line on a
    Windows clone."""
    src = make_source(tmp_path, vcs="none")
    task = make_task(tmp_path, vcs="git")
    env = clean_env(tmp_path)
    (task / "mkway" / "cards").mkdir(parents=True)
    (task / REG).write_bytes((HEAD_TEXT + ROW).encode("utf-8"))
    (task / "mkway" / ".gitattributes").write_text("*.png binary\n", encoding="utf-8")
    _git(task, "add", "-A")
    _git(task, "commit", "-q", "-m", "start")
    proc = mkway(task, env, "install", "--from", str(src))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    attrs = (task / "mkway" / ".gitattributes").read_text(encoding="utf-8").splitlines()
    assert "*.png binary" in attrs and "cards/REGISTER.md -text" in attrs
    sha = task / "mkway" / "state" / "register.sha"
    assert sha.is_file()
    sha.write_text("", encoding="utf-8")
    sha.replace(task / "mkway" / "state" / "old.sha")
    (task / REG).write_bytes((HEAD_TEXT + ROW.replace("open", "closed")).encode("utf-8"))
    proc = mkway(task, env, "install", "--from", str(src))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "differs from HEAD" in proc.stdout
    assert not sha.exists()


def test_install_without_git_seals_the_current_register(tmp_path):
    """E19 (C45): with `vcs: none` there is no HEAD; install, the owner's command, seals the register as it is.
    Catches: a vcs-none task whose first card command is refused as tampered."""
    src = make_source(tmp_path, vcs="none")
    task = make_task(tmp_path, vcs="none")
    env = clean_env(tmp_path)
    (task / "mkway" / "cards").mkdir(parents=True)
    (task / REG).write_bytes((HEAD_TEXT + ROW).encode("utf-8"))
    proc = mkway(task, env, "install", "--from", str(src), "--vcs", "none")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (task / "mkway" / "state" / "register.sha").is_file()
