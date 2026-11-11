"""A tiny synthetic project for the commit gate's tests (card MW-005). Not a test module. Its own suite is one test
that runs in about a second; the engine's own suite is never run inside a test. Synthetic values only."""
import json
import subprocess
import sys
from pathlib import Path

from _engine import gate_call, jsonl, task_root

GIT_ID = ["-c", "user.name=mkway-test", "-c", "user.email=mkway-test"]
OK_TEST = "from app import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n"
FILES = {
    "pytest.ini": "[pytest]\npythonpath = .\n",
    "app.py": "def add(a, b):\n    return a + b\n",
    "README.md": "# fixture project\n",
    "tests/test_ok.py": OK_TEST,
    ".gitignore": "mkway/state/\n.pytest_tmp/\n.pytest_cache/\n__pycache__/\n",
}
MANY_FAILING = "".join(f"def test_f{n:02d}():\n    assert False\n\n\n" for n in range(1, 13))


def git(root, *args):
    return subprocess.run(["git", *GIT_ID, *args], cwd=str(root), capture_output=True, text=True,
                          check=True).stdout


def write(root, rel, text):
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def stage(root, rel, text):
    write(root, rel, text)
    git(root, "add", "--", rel)


def make_project(tmp_path, *, name="proj", top=False, commit=True, vcs="git", **over):
    """A task root with a valid profile (Python = the running interpreter), the files above and one commit.
    `top=True` puts the repository one folder above the task root; `commit=False` leaves the first commit to the
    test (a repository with no HEAD)."""
    holder = tmp_path / f"{name}-top" if top else None
    base = holder if top else tmp_path
    over.setdefault("python", {"command": sys.executable})
    root = task_root(base, vcs=vcs, name="task" if top else name, **over)
    for rel, text in FILES.items():
        write(root, rel, text)
    git(holder if top else root, "init", "-q")
    git(holder if top else root, "add", "-A")
    if commit:
        git(holder if top else root, "commit", "-q", "-m", "start")
    return root


def set_profile(root, **changes):
    path = Path(root) / "mkway" / "profile.json"
    profile = json.loads(path.read_text(encoding="utf-8"))
    profile.update(changes)
    path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    return profile


def run_gate(root, command="git commit -m x", *, tool="Bash", session="s1"):
    import gate_commit_tests
    return gate_call(gate_commit_tests.check, root, tool=tool, tool_input={"command": command}, session=session,
                     gate="commit_tests")


def rows(root):
    return jsonl(Path(root) / "mkway" / "state" / "commit_tests.jsonl")


def reason(verdict):
    return verdict.reason_id if verdict.kind == "refuse" else "allow"
