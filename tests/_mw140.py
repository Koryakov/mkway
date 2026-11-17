"""World for card MW-140 (git's file names are read against the git top). Not a test module. Synthetic values only.

The task root lies BELOW the git top: the top is `<tmp>/top`, the root is `<tmp>/top/task/x`, so git names every file from
the top (`task/x/src/a.py` for an in-root file, `README.md` for a file of the top itself).
"""
import re
import shlex
import subprocess

from _commit_fixture import check, git, reason, stage, work
from _engine import cli, task_root
from test_cardmoves import set_paths
import records

ROOT_REL = "task/x"
COMMIT = "git commit -m 'CARD-001 work'"
CARD_PATHS = "`README.md`, `scripts/`, `src/`, `docs/`"


def make_world(tmp_path, *, card_paths=CARD_PATHS, **over):
    """(top, root): a git repository whose top holds `other/b.py` and `README.md`... committed, and a task root `task/x`
    below it whose session s1 holds the open card CARD-001 with the given Paths; `src/a.py` of the root is committed."""
    top = tmp_path / "top"
    top.mkdir()
    git(top, "init", "-q")
    root = task_root(top, vcs="git", name=ROOT_REL, **over)
    (root / "mkway" / ".gitignore").write_text("engine/\nlocks/\nstate/\n", encoding="utf-8")
    assert cli(root, "card", "new", "First", session=True)[0] == 0
    set_paths(root, "CARD-001", card_paths)
    code, out, err = cli(root, "card", "open", "CARD-001")
    assert code == 0, (out, err)
    records.append(root / "mkway" / "state", "s1", "take", "CARD-001")
    work(root, "src/a.py", "a = 1\n")
    work(top, "other/b.py", "b = 1\n")
    git(top, "add", "-A")
    git(top, "commit", "-q", "-m", "start")
    return top, root


def put(top, rel, text="x\n"):
    """A file written below `top` (no git step)."""
    work(top, rel, text)


def stage_top(top, *rels):
    """`git add -f` of top-relative names, run at the top."""
    stage(top, *rels)


def way_out_command(text):
    """The `git restore --staged ...` command a refusal text names, as an argument list; None when it names none."""
    found = re.search(r"`(git restore --staged [^`]+)`", text)
    return shlex.split(found.group(1)) if found else None


def run_in(cwd, argv):
    """Run a git argument list (the first word is `git`) in `cwd`."""
    return subprocess.run(["git", *argv[1:]], cwd=str(cwd), capture_output=True, text=True, check=True).stdout


__all__ = ["check", "git", "reason", "make_world", "put", "stage_top", "way_out_command", "run_in", "COMMIT", "ROOT_REL"]
