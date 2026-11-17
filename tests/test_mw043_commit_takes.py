"""Card MW-043: the start block and `mkway check` say how many files are staged outside the card, and never refuse. The
cases of the commit gate itself (what each commit form takes, judged by the Paths) moved to the pure core and the fact
reader in MW-052 (see `cards/MW-052-commit-core/case_map.md`); the start block and `check` cases stay here until their
own migration card. Synthetic task roots only, real throwaway git repositories."""
import json
import os

import pytest

from _commit_fixture import git, make_task, stage, work
from _engine import REPO
import dispatch
import gate_commit
import install
import startline

ENV = {"CLAUDECODE": "1"}


def _profile(root):
    return json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))


def _block(root, session="s1"):
    manifest = dispatch.load_manifest(dispatch.ENGINE_DIR)
    return startline.render(root, root / "mkway" / "profile.json", _profile(root), [], manifest, ENV, session=session)


def test_the_start_block_counts_the_files_staged_outside_the_card(tmp_path):
    """Checks: the start block prints the staged-outside count for a card holder, nothing for a session without one, never a refusal. E7."""
    root = make_task(tmp_path, card_paths="`src/`")
    work(root, "src/a.py")
    stage(root, "src/a.py")
    assert "staged outside your card" not in _block(root)
    work(root, "other/b.py")
    work(root, "other/c.py")
    stage(root, "other/b.py", "other/c.py")
    lines = _block(root).splitlines()
    assert "staged outside your card: 2" in lines
    assert "staged outside your card" not in _block(root, session="nobody")


def test_staged_outside_counts_against_one_card_or_every_open_card(tmp_path):
    """Catches: a count that includes the card's own files, or misses a foreign staged file. E8: gate_commit.staged_outside lists the files outside one card's Paths, or outside every open card's Paths with no row."""
    import register
    root = make_task(tmp_path, card_paths="`src/`")
    profile = _profile(root)
    work(root, "src/a.py")
    work(root, "other/b.py")
    stage(root, "src/a.py", "other/b.py")
    row = register.find(register.read(root, profile), "CARD-001")
    assert gate_commit.staged_outside(root, profile, row) == ["other/b.py"]
    assert gate_commit.staged_outside(root, profile) == ["other/b.py"]
    git(root, "restore", "--staged", "--", "other/b.py")
    assert gate_commit.staged_outside(root, profile, row) == []


def _copy_source(tmp_path):
    src = tmp_path / "src"
    for rel, data in install.folder_files(REPO).items():
        if rel.startswith("tests/") and rel.rsplit("/", 1)[-1].startswith("test_"):
            continue  # the copy's tests are the fixture's alone
        path = src / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    (src / "tests").mkdir(exist_ok=True)
    (src / "tests" / "test_fixture_ok.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    return src


@pytest.mark.engine_repo  # builds a copy from the repository's own files
def test_check_prints_the_staged_files_outside_every_open_card(tmp_path):
    """Checks: mkway check prints the staged-files line for a foreign staged file, nothing when none is staged, result unchanged. E9."""
    task = tmp_path / "task"
    task.mkdir()
    git(task, "init", "-q")
    install.install(task, _copy_source(tmp_path), vcs="git")
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_PROJECT_DIR", "ENGINE_TERMS_FILE")}
    code, lines = install.check(task, env=env)
    assert not [x for x in lines if x.startswith("staged files:")]
    (task / "x.txt").write_text("x\n", encoding="utf-8")
    git(task, "add", "-f", "--", "x.txt")
    code_after, lines = install.check(task, env=env)
    assert "staged files: 1 outside every open card's Paths" in lines
    assert code_after == code
