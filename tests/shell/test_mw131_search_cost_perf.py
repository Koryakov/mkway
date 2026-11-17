"""MW-131, DESIGN 4: the wall-clock numbers behind the search limit of the commit gate (R317 3). Not a correctness test: it prints
the seconds and asserts only that both calls return. Run alone, once: `python -m pytest tests/shell/test_mw131_search_cost_perf.py
-m perf -s -p no:randomly` with MKWAY_SESSION_ID unset. The work-repository half only READS the engine repository (git read
calls); everything the test writes lives in tmp_path. Synthetic names only."""
import os
import statistics
import subprocess
import time
from pathlib import Path

import pytest

import _engine  # noqa: F401  (puts the engine folder on the import path)
import gate_commit_tests as gct

pytestmark = [pytest.mark.perf, pytest.mark.shell, pytest.mark.engine_repo]

ENGINE_REPO = Path(__file__).resolve().parents[2]
COMMITS = 5000
FILES = 40  # files in every tree of the synthetic history
SAMPLE = 30  # trees whose digest is timed
NEVER = "0" * 64  # a digest no commit has: the row of a never-committed red commit


def _data(text: str) -> bytes:
    raw = text.encode("utf-8")
    return b"data %d\n" % len(raw) + raw + b"\n"


def _build(root: Path) -> None:
    """COMMITS commits by one `git fast-import` process, one minute apart, each changing data/f.txt (a distinct tree each)."""
    env = dict(os.environ, GIT_AUTHOR_NAME="mkway-test", GIT_AUTHOR_EMAIL="mkway-test", GIT_COMMITTER_NAME="mkway-test",
               GIT_COMMITTER_EMAIL="mkway-test")
    subprocess.run(["git", "init", "-q", str(root)], check=True, env=env, capture_output=True, timeout=60)
    parts = []
    for i in range(COMMITS):
        parts += [b"commit refs/heads/master\n", f"committer mkway-test <mkway-test> {1700000000 + 60 * i} +0000\n".encode(),
                  _data(f"c{i}")]
        if i == 0:
            for k in range(FILES):
                parts += [f"M 100644 inline src/mod{k}.py\n".encode(), _data(f"print({k})")]
        parts += [b"M 100644 inline data/f.txt\n", _data(str(i)), b"\n"]
    subprocess.run(["git", "-C", str(root), "fast-import", "--quiet"], input=b"".join(parts), check=True, env=env,
                   capture_output=True, timeout=300)
    subprocess.run(["git", "-C", str(root), "symbolic-ref", "HEAD", "refs/heads/master"], check=True, env=env,
                   capture_output=True, timeout=60)


def _git(root, *args) -> str:
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True, timeout=120).stdout


def _measure(root: Path, label: str) -> None:
    commits = _git(root, "rev-list", "--count", "HEAD").strip()
    first = None
    for call in (1, 2):  # the second call has the files in the cache
        began = time.perf_counter()
        found = gct.trees_of_keys(root, {NEVER}, limit=gct.TREE_LIMIT)
        took = time.perf_counter() - began
        first = took if first is None else first
        print(f"(a) {label} ({commits} commits): a gate call that finds nothing today (rev-list + {gct.TREE_LIMIT} x 2 git calls), "
              f"call {call}: {took:.2f} s")
        assert found == {}
    revs = _git(root, "rev-list", "HEAD").split()
    sample = revs[::max(1, len(revs) // SAMPLE)][:SAMPLE]
    trees = [_git(root, "rev-parse", f"{r}^{{tree}}").strip() for r in sample]
    seconds = []
    for tree in trees:
        began = time.perf_counter()
        digest = gct.digest_of_tree(root, tree)
        seconds.append(time.perf_counter() - began)
        assert digest is not None
    files = len(_git(root, "ls-tree", "-r", trees[0]).splitlines())
    print(f"(b) {label}: {len(seconds)} digests: mean {statistics.mean(seconds):.3f} s, median {statistics.median(seconds):.3f} s, "
          f"max {max(seconds):.3f} s, files in the first tree {files}")


def test_the_cost_of_a_search_that_finds_nothing_and_of_one_digest_on_5000_commits(tmp_path):
    root = tmp_path / "syn5000"
    began = time.perf_counter()
    _build(root)
    print(f"built {COMMITS} commits in {time.perf_counter() - began:.1f} s")
    _measure(root, "synthetic")


def test_the_cost_of_a_search_that_finds_nothing_and_of_one_digest_on_the_engine_repository():
    _measure(ENGINE_REPO, "engine repository")
