"""Card MW-058: a message-only amend takes no files. `git commit --amend --only` (or `-o`) with no paths rewrites the
message of the last commit and takes NOTHING from the index. The decision cases of this card (the table of forms, the
message checks on the new message) moved to the pure core and the fact reader in MW-052 (see
`cards/MW-052-commit-core/case_map.md`); the one case that proves what real git does stays here. Synthetic task roots
only, real throwaway git repositories."""
import pytest

from _commit_fixture import git, make_task, save, stage, work


def _root(tmp_path):
    """A task root: `src/a.py` and `other/b.py` staged (new), `other/c.py` committed and then modified in the tree."""
    root = make_task(tmp_path, card_paths="`src/`")
    save(root, "other/c.py")
    work(root, "other/c.py", "changed\n")
    work(root, "src/a.py")
    work(root, "other/b.py")
    stage(root, "src/a.py", "other/b.py")
    return root


@pytest.mark.parametrize(
    "flags",
    [
        pytest.param(["--amend", "--only", "-m", "CARD-001 one"], id="only-long-form"),
        pytest.param(["--amend", "-om", "CARD-001 two"], id="only-short-form"),
    ],
)
def test_real_git_takes_nothing_for_a_message_only_amend(tmp_path, flags):
    """Checks: a message-only amend with real git keeps the tree and the index and takes no file (E2)."""
    root = _root(tmp_path)
    staged_before = git(root, "diff", "--cached", "--name-only")
    tree = git(root, "rev-parse", "HEAD^{tree}")
    git(root, "commit", "-q", *flags)
    assert git(root, "rev-parse", "HEAD^{tree}") == tree
    assert git(root, "diff", "--cached", "--name-only") == staged_before
    assert git(root, "log", "-1", "--format=%s").strip() == flags[-1]
    # --amend --only -- src/a.py takes that path alone and leaves the other staged file staged
    git(root, "commit", "-q", "--amend", "--only", "-m", "CARD-001 three", "--", "src/a.py")
    assert "src/a.py" in git(root, "show", "--name-only", "--format=", "HEAD").split()
    assert "other/b.py" not in git(root, "show", "--name-only", "--format=", "HEAD").split()
    assert git(root, "diff", "--cached", "--name-only").split() == ["other/b.py"]
