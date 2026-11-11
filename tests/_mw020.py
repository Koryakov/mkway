"""Shared helpers for the MW-020 tests (deliverables). Not a test module. Synthetic values only.

A root here is a real git work tree (the `built` command reads HEAD), with a profile that names the deliverable globs."""
import hashlib
import json
import subprocess
from pathlib import Path

from _commit_fixture import git, make_task, save
from _engine import cli
import cardtool

OUT = "out"
PATHS = [f"{OUT}/*.md"]
BASE_PATHS = [f"{OUT}/base-*.md"]
TEXT = "Alpha beta gamma. Twelve items.\n"


def make_root(tmp_path, *, deliverables="default", name="dtask", **over):
    """A git task root, one commit made, whose profile names the deliverable globs; `deliverables=None` leaves them out."""
    if deliverables == "default":
        deliverables = {"paths": PATHS, "require_base": BASE_PATHS}
    if deliverables is not None:
        over["deliverables"] = deliverables
    root = make_task(tmp_path, name=name, **over)
    save(root, "src/a.py", "x = 1\n")
    return root


def state(root) -> Path:
    return Path(root) / "mkway" / "state"


def rows(root, name) -> list:
    path = state(root) / name
    if not path.is_file():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def sha_of(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def head(root) -> str:
    return git(root, "rev-parse", "HEAD").strip()


def head_tree(root) -> str:
    return git(root, "rev-parse", "HEAD^{tree}").strip()


def index_digest(root) -> str:
    """What the commit gate writes as `tree`: the sha256 of `git ls-files -s -z`."""
    out = subprocess.run(["git", "-C", str(root), "ls-files", "-s", "-z"], capture_output=True, check=True).stdout
    return hashlib.sha256(out).hexdigest()


def green(root, tree=None, result="pass"):
    """A row of `commit_tests.jsonl` as the commit gate writes it; the tree is HEAD's by default."""
    row = {"time": "2026-11-11T00:00:00.000+00:00", "session": "s1", "tree": tree or head_tree(root),
           "command": "x", "result": result, "duration_seconds": 1.0}
    with (state(root) / "commit_tests.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def deliverable(root, name="a.md", text=TEXT, commit=False) -> str:
    """A result file under the deliverable folder (untracked unless `commit`)."""
    rel = f"{OUT}/{name}"
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="")
    if commit:
        save(root, rel, text)
    return rel


def built(root, rel, *, session="s1"):
    """`mkway built <rel>` as a session runs it (the lock gate's one-use permit names the session)."""
    cardtool.issue_by_permit(state(root), session)
    return cli(root, "built", rel, session=True)


def ready(root, rel, *, session="s1"):
    """A green row for HEAD, then a successful `built`."""
    green(root)
    code, out, err = built(root, rel, session=session)
    assert code == 0, err
