"""The shape gate of the tests a commit adds or changes (card MW-073, ruling R177, plan gate G7): the shell around the pure
`core_shape.decide`.

A `git commit` of a session (PreToolUse, Bash and PowerShell, shell group; one manifest entry `tests.shape`) is judged by
the tree git will commit, which `gate_commit_tests.tree_id` builds (the reader the commit records use), against the tree
it is compared with: HEAD, the parent of HEAD for an `--amend`, the empty tree for a first commit. Each test file
(`test_*.py` under the profile's `test_roots`) that the commit adds or modifies goes to the core as `Source(path, new,
old)`; the core judges only the test functions that are new or changed. A breach refuses `test-shape` and the text names
file, function and rule. `tests.shape.mode` is `trip` (default) or `watch` (the reason line is a warn and the commit
goes through). Every judged commit with a breach writes one row to `<state.dir>/test_shape.jsonl`, in both modes.
A commit the gate cannot read (a git read fails, a message-only amend, a folder it cannot parse) is allowed: the commit
gates that read the same tree refuse such a commit themselves.
"""
from __future__ import annotations

from pathlib import Path

import core_shape
import gate
import gate_commit_tests
import helpers
import logs
import profiles
import runner

EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"  # git's own empty tree
ROW_FILE = "test_shape.jsonl"
GIT_SECONDS = 30


def check(event, ctx):
    profile = ctx.profile if isinstance(ctx.profile, dict) else {}
    tool_input = ctx.tool_input if isinstance(ctx.tool_input, dict) else {}
    command = tool_input.get("command")
    if profiles.vcs(profile) != "git" or not isinstance(command, str) or "commit" not in command.lower():
        return gate.allow()
    commits = ctx.commit_cmd(command)
    if len(commits) != 1:
        return gate.allow()  # no commit, or several (the test gate refuses a chained commit)
    try:
        return _judge(ctx, profile, commits[0])
    except (OSError, ValueError, runner.TimeoutExpired, runner.Refused):
        return gate.allow()


def _git(top, *args) -> str:
    proc = runner.git(top, *args, text=False, timeout=GIT_SECONDS)
    if proc.returncode != 0:
        raise ValueError(f"git {args[0]} failed")
    return proc.stdout.decode("utf-8", "replace")


def _base(top, amend: bool) -> str:
    """The tree the commit is compared with."""
    has_head = runner.git(top, "rev-parse", "--verify", "-q", "HEAD").returncode == 0
    parent = runner.git(top, "rev-parse", "--verify", "-q", "HEAD^").returncode == 0
    return "HEAD^" if amend and parent else (EMPTY_TREE if amend or not has_head else "HEAD")


def _changed(top, base: str, tree: str) -> list:
    """[(status, path relative to the git top)] of the files added or modified between `base` and `tree`."""
    parts = _git(top, "diff-tree", "-r", "--name-status", "--no-renames", "-z", base, tree).split("\0")
    return [(parts[i][:1], parts[i + 1]) for i in range(0, len(parts) - 1, 2) if parts[i][:1] in ("A", "M")]


def _sources(ctx, profile, top, tree: str, base: str) -> tuple:
    prefix = helpers.top_prefix(ctx.root)
    roots = profiles.test_roots(profile)
    found = []
    for status, path in _changed(top, base, tree):
        rel = path[len(prefix) + 1:] if prefix and path.startswith(prefix + "/") else (None if prefix else path)
        if rel is None or not core_shape.is_test_file(rel) or not any(helpers.matches(rel, r) for r in roots):
            continue
        old = _git(top, "show", f"{base}:{path}") if status == "M" else None
        found.append(core_shape.Source(rel, _git(top, "show", f"{tree}:{path}"), old))
    return tuple(found)


def _judge(ctx, profile, commit):
    folder = Path(ctx.root)
    if commit.cwd:
        rel = ctx.norm(commit.cwd)
        if rel is None:
            return gate.allow()  # a commit in another project is not this project's
        folder = folder if rel == "." else folder / rel
    tree = gate_commit_tests.tree_id(ctx, commit)
    if tree is None:
        return gate.allow()
    top = Path(_git(folder, "rev-parse", "--show-toplevel").strip())
    base = _base(top, commit.amend)
    verdict = core_shape.decide(core_shape.Facts(_sources(ctx, profile, top, tree, base)))
    if verdict.allowed:
        return gate.allow()
    mode = profiles.shape_mode(profile)
    logs.append_jsonl(profiles.state_dir(ctx.root, profile) / ROW_FILE, _row(ctx, mode, tree, verdict))
    text = core_shape.refusal_text(verdict)
    if mode == "watch":
        return gate.warn("test-shape", f"watch mode (tests.shape.mode), the commit is allowed; it would be refused: {text}")
    return gate.refuse("test-shape", text)


def _row(ctx, mode: str, tree: str, verdict) -> dict:
    return {"time": logs.now().isoformat(timespec="milliseconds"), "session": ctx.session_id, "mode": mode, "tree": tree,
            "judged": verdict.judged, "count": len(verdict.breaches),
            "breaches": [{"file": b.file, "function": b.function, "rule": b.rule} for b in verdict.breaches]}
