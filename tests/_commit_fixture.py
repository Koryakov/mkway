"""Shared fixture for the commit gate tests (card MW-006). Not a test module. Synthetic values only."""
import subprocess

from _engine import cli, gate_call, task_root
from test_cardmoves import set_paths
import records

GIT_ID = ["-c", "user.name=mkway-test", "-c", "user.email=mkway-test"]
COMMIT = "git commit -m 'CARD-001 work'"


def git(cwd, *args):
    return subprocess.run(["git", *GIT_ID, *args], cwd=str(cwd), capture_output=True, text=True, check=True).stdout


def make_task(tmp_path, *, card_paths="`src/`, `lib/a.py`", session="s1", name="gtask", **over):
    """A git task root whose session holds CARD-001, open, with the given card Paths; one commit made (`start`).
    `over` are profile keys (for example `paths={"exempt": [...]}`)."""
    root = task_root(tmp_path, vcs="git", name=name, **over)
    (root / "mkway" / ".gitignore").write_text("engine/\nlocks/\nstate/\n", encoding="utf-8")
    git(root, "init", "-q")
    assert cli(root, "card", "new", "First", session=True)[0] == 0
    set_paths(root, "CARD-001", card_paths)
    assert cli(root, "card", "open", "CARD-001")[0] == 0
    records.append(root / "mkway" / "state", session, "take", "CARD-001")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "start")
    return root


def work(root, rel, text="x\n"):
    """Write a working-tree file (creating its folder); no git step."""
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def stage(root, *rels):
    git(root, "add", "-f", "--", *rels)


def save(root, rel, text="x\n"):
    """A file written, staged and committed with git directly (the test's own step, no gate)."""
    work(root, rel, text)
    stage(root, rel)
    git(root, "commit", "-q", "-m", f"add {rel}")


def touch(root, *rels, session="s1", tool="Write"):
    """The recorder's rows for these paths, as the edit gate group writes them."""
    import gate_commit
    for rel in rels:
        gate_call(gate_commit.touch, root, tool=tool, tool_input={"file_path": rel}, session=session)


def check(root, command, session="s1", tool="Bash", **payload):
    import gate_commit
    return gate_call(gate_commit.check, root, tool=tool, tool_input={"command": command}, session=session, **payload)


def reason(verdict):
    return verdict.reason_id if verdict.kind == "refuse" else "allow"
