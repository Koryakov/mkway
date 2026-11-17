"""Card MW-140, the name form of `git diff`: a git setting `diff.relative=true` makes `git diff` print names relative to the
CURRENT folder and leave out every file outside it. With the current folder below the task root that hides an in-root file
outside the folder AND every file outside the root, so a gate that reads `git diff` never sees them. Each `git diff` read
of a name pins its name form (`-c diff.relative=false`), so the repository's or the user's setting changes nothing. Real git,
the setting written into the repository's own config. One test id is one case. Synthetic values only."""
import json

from _engine import gate_call
from _mw140 import COMMIT, check, git, make_world, put, stage_top
import dispatch
import gate_commit
import gate_lock

REASON = "file-outside-root"
IN_SRC = "cd src && " + COMMIT


def relative_on(top):
    git(top, "config", "diff.relative", "true")


def lock_ctx(root):
    profile = json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))
    return dispatch.make_context(profile=profile, root=root, session_id="s1", event="PreToolUse", gate="g",
                                 tool_name="Bash", tool_input={"command": COMMIT}, budget_seconds=None,
                                 once=lambda t: True, tool_response=None, env={}), profile


def test_a_top_file_is_still_outside_when_diff_relative_is_true_and_the_folder_is_below_the_root(tmp_path):
    """Catches: `diff.relative=true` with the commit run from `<root>/src` leaving the staged `<top>/README.md` out of the
    list, so the commit takes a file of the top unseen."""
    top, root = make_world(tmp_path)
    relative_on(top)
    put(top, "README.md")
    stage_top(top, "README.md")
    verdict = check(root, IN_SRC)
    assert (verdict.kind, verdict.reason_id) == ("refuse", REASON), (verdict.kind, verdict.reason_id)


def test_an_in_root_file_outside_the_current_folder_is_still_judged_when_diff_relative_is_true(tmp_path):
    """Catches: `diff.relative=true` with the commit run from `<root>/src` leaving the staged in-root `notes/n.md` (outside the
    folder, outside the card Paths) out of the list, so it is committed unjudged."""
    top, root = make_world(tmp_path)
    relative_on(top)
    put(root, "notes/n.md")
    stage_top(top, "task/x/notes/n.md")
    verdict = check(root, IN_SRC)
    assert (verdict.kind, verdict.reason_id, "notes/n.md" in verdict.message) == ("refuse", "file-not-in-card", True)


def test_the_staged_outside_names_are_still_read_when_diff_relative_is_true(tmp_path):
    """Catches: the start line's reader of the staged outside files seeing none because `diff.relative=true` hides them."""
    top, root = make_world(tmp_path)
    relative_on(top)
    put(top, "README.md")
    stage_top(top, "README.md")
    assert gate_commit.staged_outside_root(root) == ["README.md"]


def test_the_pathspec_expansion_of_the_lock_gate_keeps_the_root_names_when_diff_relative_is_true(tmp_path):
    """Catches: `_expand` run from `<root>/src` returning `a.py` (relative to the folder) and none of `docs/m.md`, so the lock
    targets are matched against the wrong names."""
    top, root = make_world(tmp_path)
    put(root, "docs/m.md")
    stage_top(top, "task/x/docs/m.md")
    git(top, "commit", "-q", "-m", "docs")
    put(root, "docs/m.md", "2\n")
    put(root, "src/a.py", "a = 2\n")
    relative_on(top)
    ctx, _profile = lock_ctx(root)
    assert gate_lock._expand(ctx, root / "src", [".", "../docs"]) == (["docs/m.md", "src/a.py"], None)
