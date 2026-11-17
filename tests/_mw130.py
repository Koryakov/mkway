"""Shared fixture for the MW-130 tests (the search for a card's red-proof row in the history of HEAD). Not a test module.
Synthetic names, sessions and files only.

`gated` is a task root whose red commit was made through the real commit gate (a tests-only commit, `run_gate`, then `git
commit`) and that a reader session may call `verdict add` on. `light` is the small root of `_mw080` with a reader run, for the
tests that seed the rows by hand. `chain` adds commits with ONE `git fast-import` process, one distinct tree per commit and the
committer dates `step` seconds apart. `digest_of` is an independent read of the digest the gate writes: `git ls-files -s -z`
of a temporary index that holds the commit, hashed with sha256."""
import datetime
import hashlib
import json
import os
import subprocess
from pathlib import Path

import _mw080 as w
from _commit_project import run_gate, set_profile, stage
from _engine import agent_file
import gate_commit_tests as gct
import shared_records
from _red_project import APP_MUL, RED_MUL, red_project  # noqa: F401  (APP_MUL is used by the tests)

NEW_FILE = "tests/test_new.py"
NEW = f"{NEW_FILE}::test_mul"
RED_AT = -3600  # seconds after T0: the committer date of the gate-made red commit, before every fresh reader run
FAR = "f" * 40  # a git tree id no commit has
WHY = "one clause, one case"


def red_file(root) -> Path:
    """The red-proof file where MW-129 keeps it: the shared folder of the task (the state folder when no `state.shared_dir`)."""
    return shared_records.shared_path(root, w.profile_of(root), gct.RED_FILE)


def add(root):
    """The real command, in process, as the session `reader` runs it: (exit code, stdout, stderr)."""
    return w.run_cli(root, "verdict", "add", w.CARD, NEW, "true", WHY, session=True, caller="reader")


def add_n1(root):
    """The same for the first node of the `_mw080` root."""
    return w.run_cli(root, "verdict", "add", w.CARD, w.N1, "true", WHY, session=True, caller="reader")


def gated(tmp_path, *, side=False):
    """A root whose red commit was made through the real gate: one open card held by session `s1` that names `NEW`, the
    tests-only commit allowed by the gate and then committed (dated at `RED_AT`), and a fresh reader run of session `reader`.
    `side=True` makes the red commit on a branch `side` that is merged with `--no-ff` into a main that moved on by one commit."""
    root = red_project(tmp_path, row=f"| E1 | item | was | must | {NEW} |")
    set_profile(root, outbox={"checkers": [w.CHECKER]})
    agent_file(root, w.CHECKER, "Read, Grep")  # a checker type needs its tool-limited agent definition (MW-071)
    main = w.git(root, "rev-parse", "--abbrev-ref", "HEAD")
    if side:
        w.git(root, "checkout", "-q", "-b", "side")
    stage(root, NEW_FILE, RED_MUL)
    verdict = run_gate(root)
    assert verdict.kind == "allow", verdict.message
    w.git(root, "commit", "-q", "-m", "CARD-001 red", when=RED_AT)
    if side:
        w.git(root, "checkout", "-q", main)
        (Path(root) / "other.txt").write_text("other\n", encoding="utf-8")
        w.git(root, "add", "--", "other.txt")
        w.git(root, "commit", "-q", "-m", "main moves on")
        w.git(root, "merge", "-q", "--no-ff", "-m", "merge side", "side")
    w.reader(root, "reader", "agent-1")
    return root


def light(tmp_path, *, name="vroot"):
    """The `_mw080` root with no red-proof row and one fresh reader run of session `reader`."""
    root = w.make_root(tmp_path, red=False, name=name)
    w.reader(root, "reader", "a1")
    return root


def _data(text: str) -> bytes:
    raw = text.encode("utf-8")
    return b"data %d\n" % len(raw) + raw


def chain(root, count: int, *, start: int = -3500, step: int = 60) -> list:
    """`count` commits on the current branch made by one `git fast-import` process: each changes `data/f.txt`, so every
    commit has its own tree; the committer date of commit i is `start + step * i` seconds after T0. The working tree and the
    index are reset to the new HEAD (the index only, a mixed reset). Returns the shas, oldest first."""
    head = w.git(root, "rev-parse", "HEAD")
    ref = w.git(root, "symbolic-ref", "HEAD")
    parts = []
    for i in range(count):
        stamp = int(w.at(start + step * i).timestamp())
        parts += [f"commit {ref}\n".encode(), f"committer mkway-test <mkway-test> {stamp} +0000\n".encode(),
                  _data(f"unrelated {i}\n")]
        if i == 0:
            parts.append(f"from {head}\n".encode())
        parts += [b"M 100644 inline data/f.txt\n", _data(f"{i}\n"), b"\n"]
    env = dict(os.environ, GIT_AUTHOR_NAME="mkway-test", GIT_AUTHOR_EMAIL="mkway-test", GIT_COMMITTER_NAME="mkway-test",
               GIT_COMMITTER_EMAIL="mkway-test")
    subprocess.run(["git", "fast-import", "--quiet"], cwd=str(root), input=b"".join(parts), check=True, env=env,
                   capture_output=True, timeout=300)
    w.git(root, "reset", "-q", "--mixed", "HEAD")  # the index follows HEAD; the working tree (the root's profile) is kept
    return w.git(root, "rev-list", "--reverse", f"--max-count={count}", "HEAD").split()


def committer_time(root, rev) -> int:
    return int(w.git(root, "log", "-1", "--format=%ct", rev))


def iso_at(epoch: int) -> str:
    """A row time as the gate writes it: ISO, UTC, milliseconds."""
    return datetime.datetime.fromtimestamp(epoch, datetime.timezone.utc).isoformat(timespec="milliseconds")


def digest_of(root, rev) -> str:
    """The digest of the tree of `rev` as the gate writes it for a staged tree, read independently of the engine."""
    index = Path(root).parent / f"digest-index-{rev[:12]}"
    env = dict(os.environ, GIT_INDEX_FILE=str(index))
    try:
        subprocess.run(["git", "read-tree", rev], cwd=str(root), check=True, env=env, capture_output=True, timeout=60)
        listing = subprocess.run(["git", "ls-files", "-s", "-z"], cwd=str(root), check=True, env=env, capture_output=True,
                                 timeout=60).stdout
    finally:
        index.unlink(missing_ok=True)
    return hashlib.sha256(listing).hexdigest()


def seed(root, *, tree, git_tree=None, time=None, card=w.CARD) -> None:
    """One red-proof row written by hand (a row the gate wrote earlier). `git_tree` None: a legacy row, digest only."""
    row = {"time": time or iso_at(int(w.at(0).timestamp())), "session": "s1", "card": card, "tree": tree, "red": [w.N1],
           "pins": [], "checks": [], "missing": {}, "would_refuse": [], "mode": "trip"}
    if git_tree is not None:
        row["git_tree"] = git_tree
    path = red_file(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def rows(root) -> list:
    path = red_file(root)
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def rewrite(root, change) -> None:
    """Rewrite every row of the red-proof file with `change(row)` (the test edits what the gate wrote)."""
    out = []
    for row in rows(root):
        change(row)
        out.append(json.dumps(row))
    red_file(root).write_text("\n".join(out) + "\n", encoding="utf-8")


def count_digests(monkeypatch) -> list:
    """The git tree ids whose digest the search computes, in order: the calls of the one function that computes a digest from a
    tree id (`gate_commit_tests.digest_of_tree`, where the search lives since MW-130 R320)."""
    calls = []
    real = gct.digest_of_tree

    def counted(root, tree):
        calls.append(tree)
        return real(root, tree)
    monkeypatch.setattr(gct, "digest_of_tree", counted)
    return calls
