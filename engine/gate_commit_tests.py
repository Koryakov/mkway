"""The commit gate (card MW-005): tests before a commit, red test first, no red commit.

A `git commit` of a session (PreToolUse, Bash and PowerShell, shell group, after the lock gate) runs the project's tests
first, and the tests run on the STAGED tree, never on the working tree (an untracked conftest must not make a commit
pass). The index is exported with `git checkout-index -a -f --prefix=<folder>/` into a folder under the state
dir, the suite runs there, and the folder is removed. The rules:
- a commit that takes more than the index is read as git will take it: `-a` is the index plus `git add -u`, a pathspec
  is HEAD plus those paths (with `-i`, the index plus those paths), all in a temporary index file; the real index is
  never changed;
- every staged file under `test_roots`: the red-first commit, which may be red, so no run;
- every staged file matches `paths.docs`: no run;
- otherwise the command (`tests.command`, default `python -m pytest -q` over the `test_roots`) runs with the
  environment names of `test_env` and `ENGINE_TERMS_FILE` only; a red run refuses `commit-tests-failed` and names the
  first 10 failing test ids and the way out; a run over `gates.commit_tests.budget_seconds` is stopped and refused
  `commit-tests-over-budget`; a command that cannot start, or any git read that fails, refuses `commit-tests-not-run`
  (fail closed);
- one run per staged tree and command: a row of `<state.dir>/commit_tests.jsonl` holds the tree hash, the result and
  the duration; the same index is not run twice. A budget raised above the one an `over-budget` row ran under runs
  again;
- a staging command in the same shell command as the commit (`git add ... && git commit`) is refused
  `commit-tests-chained`: the index is read before the command runs, so it would be the wrong tree.
The program the engine runs is git or the profile's Python only (`runner`). No task name is in this file.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import stat
import time
from pathlib import Path

import gate
import helpers
import logs
import profiles
import runner

STATE_FILE = "commit_tests.jsonl"
FOLDER = "commit_tests"  # `<state.dir>/commit_tests/`: the exports and temporary index files of a run
MAX_IDS = 10
HOOK_LIMIT = 840  # seconds: the manifest's hook timeout (900) less a margin for the exports and the log
GIT_SECONDS = 30
INDEX_CHANGERS = {"add", "rm", "mv", "restore", "reset", "checkout", "switch", "apply", "stash", "merge", "rebase",
                  "cherry-pick", "revert", "am", "pull", "update-index", "read-tree"}
SESSION_ENV = ("PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP", "TMPDIR", "HOME", "USERPROFILE",
               "LANG", "LC_ALL")
ALWAYS_ENV = ("ENGINE_TERMS_FILE",)
FAILED = re.compile(r"^(?:FAILED|ERROR) (\S+)", re.M)
OUT = "A refused commit changes nothing: the index and the working tree stay as they are."


class NotRun(Exception):
    """The tests could not be started or the staged tree could not be read: the commit is refused."""


def _git(folder, *args, env=None, text=True):
    proc = runner.run(runner.GIT + ["-C", str(folder), *args], capture_output=True, text=text,
                      timeout=GIT_SECONDS, env=env)
    return proc


def _read(folder, *args, env=None, text=True):
    proc = _git(folder, *args, env=env, text=text)
    if proc.returncode != 0:
        raise NotRun(f"git {args[0]} failed (exit {proc.returncode}), so the staged tree could not be read")
    return proc.stdout


def staged_key(listing: bytes) -> str:
    """The `tree` key of a row: the sha256 of `git ls-files -s -z` as the gate reads the staged index (card MW-023)."""
    return hashlib.sha256(listing).hexdigest()


def _listing(root, rev):
    """The bytes `git ls-files -s -z` prints for the index that equals commit `rev` (taken from `ls-tree -r -z`, which
    holds the same entries in the same order), or None when git cannot tell."""
    try:
        proc = runner.git(root, "ls-tree", "-r", "-z", rev, text=False, timeout=GIT_SECONDS)
    except (OSError, runner.TimeoutExpired, ValueError, runner.Refused):
        return None
    if proc.returncode != 0:
        return None
    out = []
    for entry in proc.stdout.split(b"\0"):
        if not entry:
            continue
        head, _tab, path = entry.partition(b"\t")
        parts = head.split(b" ")
        if len(parts) != 3:
            return None
        out.append(parts[0] + b" " + parts[2] + b" 0\t" + path + b"\0")
    return b"".join(out)


def tree_keys(root, rev="HEAD") -> list:
    """The keys a row of `commit_tests.jsonl` may use for the tree of commit `rev`: its git tree id, then the digest
    the gate writes (`staged_key`). The one definition every reader uses (card MW-023); `[]` when git cannot tell."""
    try:
        proc = runner.git(root, "rev-parse", f"{rev}^{{tree}}", timeout=GIT_SECONDS)
    except (OSError, runner.TimeoutExpired, ValueError, runner.Refused):
        return []
    tree = proc.stdout.strip()
    if proc.returncode != 0 or not tree:
        return []
    listing = _listing(root, rev)
    return [tree] if listing is None else [tree, staged_key(listing)]


def trees_of_keys(root, keys, limit=100) -> dict:
    """{key: git tree id} for the keys that name a recent commit of HEAD (`limit` commits, newest first) in either form;
    a key no commit names is left out. Stops once every key is found."""
    wanted = {k for k in keys if isinstance(k, str) and k}
    found = {}
    try:
        proc = runner.git(root, "rev-list", f"--max-count={limit}", "HEAD", timeout=GIT_SECONDS)
    except (OSError, runner.TimeoutExpired, ValueError, runner.Refused):
        return found
    for commit in proc.stdout.split() if proc.returncode == 0 else []:
        have = tree_keys(root, commit)
        for key in have:
            if key in wanted:
                found.setdefault(key, have[0])
        if wanted <= set(found):
            break
    return found


def _chained(command: str, shell: str):
    """The name of an index-changing git command that comes before the commit in the same shell command, or None."""
    try:
        simples = helpers.parse(command, shell)
    except helpers.ParseError:
        return None
    for s in simples:
        argv = helpers._argv(s.words)
        if helpers._prog(argv) != "git":
            continue
        sub = helpers._git_sub(argv)[0]
        if sub == "commit":
            return None
        if sub in INDEX_CHANGERS:
            return sub
    return None


def check(event, ctx):
    profile = ctx.profile if isinstance(ctx.profile, dict) else {}
    tool_input = ctx.tool_input if isinstance(ctx.tool_input, dict) else {}
    command = tool_input.get("command")
    if profiles.vcs(profile) != "git" or not isinstance(command, str) or "commit" not in command.lower():
        return gate.allow()
    commits = ctx.commit_cmd(command)
    if not commits:
        return gate.allow()
    shell = "powershell" if ctx.tool_name == "PowerShell" else "bash"
    sub = _chained(command, shell)
    if sub or len(commits) > 1:
        what = f"`git {sub}`" if sub else "another commit"
        return gate.refuse("commit-tests-chained",
                           f"{what} and the commit are one shell command: the tests run on the index as it is before "
                           f"the command starts, which is not the tree this commit would take. Run {what} alone "
                           f"first, then the commit alone")
    try:
        return _gate(ctx, profile, commits[0])
    except NotRun as exc:
        return gate.refuse("commit-tests-not-run", f"the tests were not run, so the commit is refused: {exc}")
    except runner.TimeoutExpired as exc:
        return gate.refuse("commit-tests-not-run", f"a git read did not answer within {exc.timeout:g} s, so the "
                                                   f"staged tree could not be tested; run the commit again")
    except runner.Refused as exc:
        return gate.refuse("commit-tests-not-run", f"the tests were not run, so the commit is refused: {exc}")


def _gate(ctx, profile, commit):
    if commit.folder_unreadable:
        raise NotRun("the commit runs in a folder the gate cannot read; `cd` to a literal folder")
    folder = Path(ctx.root)
    if commit.cwd:
        rel = ctx.norm(commit.cwd)
        if rel is None:
            return gate.allow()  # a commit in another project is not this project's
        folder = folder if rel == "." else folder / rel
    top = Path(_read(folder, "rev-parse", "--show-toplevel").strip())
    prefix = helpers.top_prefix(ctx.root)
    state = profiles.state_dir(ctx.root, profile)
    work = state / FOLDER / f"run-{os.getpid()}-{int(time.time() * 1000)}"
    started = time.perf_counter()
    budget = profiles.commit_tests_budget(profile)
    limit = min(budget, HOOK_LIMIT)
    try:
        env = None
        index = None
        if commit.paths or commit.all:
            index = work / "index"
            work.mkdir(parents=True, exist_ok=True)
            env = _temp_index(folder, top, index, commit)
        rels = _staged(folder, top, prefix, env, commit)
        if not rels:
            return gate.allow()
        roots = profiles.test_roots(profile)
        if all(any(helpers.matches(r, root) for root in roots) for r in rels):
            return gate.allow()  # the red-first commit: tests alone may be red
        if profiles.docs_only(profile, rels):
            return gate.allow()
        argv = _argv(profile, roots)
        tree = staged_key(_read(folder, "ls-files", "-s", "-z", env=env, text=False))
        cached = _cached(state, tree, " ".join(argv), limit)
        if cached is not None:
            return _verdict(cached, roots, limit)
        work.mkdir(parents=True, exist_ok=True)
        _read(top, "checkout-index", "-a", "-f", f"--prefix={(work / 'tree').as_posix()}/", env=env)
        cwd = work / "tree" / prefix if prefix else work / "tree"
        if not cwd.is_dir():
            raise NotRun(f"the staged tree has no folder {prefix or '.'}, so there is nothing to run in")
        remaining = limit - (time.perf_counter() - started)
        code, out, err = (None, b"", b"")
        if remaining > 0:
            code, out, err = runner.run_tree(argv, timeout=remaining, python=_python(profile), cwd=str(cwd),
                                             env=_environment(ctx, profile))
        row = _row(ctx, tree, argv, code, out, err, time.perf_counter() - started, budget)
        logs.append_jsonl(state / STATE_FILE, row)
        return _verdict(row, roots, limit)
    finally:
        _remove(work, state)


def _temp_index(folder, top, index: Path, commit):
    """The environment of a temporary index that holds what this commit takes, built from the real one. The real
    index is not changed."""
    env = dict(os.environ)
    env["GIT_INDEX_FILE"] = str(index)
    has_head = _git(folder, "rev-parse", "--verify", "-q", "HEAD").returncode == 0
    if commit.paths and not commit.include:  # `--only`: HEAD plus the working-tree content of these paths
        _read(folder, "read-tree", *(["HEAD"] if has_head else ["--empty"]), env=env)
    else:
        real = Path(_read(folder, "rev-parse", "--git-path", "index").strip())
        real = real if real.is_absolute() else Path(folder) / real
        if real.is_file():
            shutil.copyfile(real, index)
    if commit.paths:
        _read(folder, "add", "-A", "--", *commit.paths, env=env)
    else:
        _read(top, "add", "-u", env=env)
    return env


def _staged(folder, top, prefix, env, commit) -> list:
    """The paths this commit changes, relative to the task root; a path outside the root is kept as `../<path>`."""
    has_head = _git(folder, "rev-parse", "--verify", "-q", "HEAD").returncode == 0
    base = None
    if has_head:
        base = "HEAD"
        if commit.amend:
            base = "HEAD^" if _git(folder, "rev-parse", "--verify", "-q", "HEAD^").returncode == 0 else None
    if base:
        raw = _read(top, "diff-index", "--cached", "--name-only", "--no-renames", "-z", base, env=env)
    else:
        raw = _read(top, "ls-files", "-z", env=env)
    out = []
    for name in (n for n in raw.split("\0") if n):
        if not prefix:
            out.append(name)
        elif name.startswith(prefix + "/"):
            out.append(name[len(prefix) + 1:])
        else:
            out.append("../" + name)
    return out


def _python(profile):
    value = (profile.get("python") or {}).get("command") if isinstance(profile.get("python"), dict) else None
    return value if isinstance(value, str) and value else "python"


def _argv(profile, roots) -> list:
    py = _python(profile)
    command = profiles.tests_command(profile)
    if command is None:
        return [py, "-m", "pytest", "-q", *roots]
    try:
        words = shlex.split(command, posix=False)
    except ValueError as exc:
        raise NotRun(f"tests.command cannot be read ({exc})")
    words = [w[1:-1] if len(w) >= 2 and w[0] == w[-1] and w[0] in "\"'" else w for w in words]
    if not words:
        raise NotRun("tests.command is empty")
    if words[0].lower() in ("python", "python3"):
        words[0] = py
    if not runner.allowed(words[0], py):
        raise NotRun(f"tests.command starts with {words[0]!r}, which is neither the profile's Python nor git; the "
                     f"engine runs no other program, so the command cannot run")
    return words


def _environment(ctx, profile) -> dict:
    """Only the names the run needs: the system essentials, `ENGINE_TERMS_FILE` and the profile's `test_env`."""
    source = {k.upper(): (k, v) for k, v in {**os.environ, **dict(ctx.env or {})}.items()}
    wanted = [*SESSION_ENV, *ALWAYS_ENV, *profiles.test_env(profile)]
    env = {}
    for name in wanted:
        if name.upper() in source:
            key, value = source[name.upper()]
            env[key] = value
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _cached(state, tree, command, limit):
    """The last row of this staged tree and command that still stands, or None."""
    path = Path(state) / STATE_FILE
    if not path.is_file():
        return None
    found = None
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("tree") == tree and row.get("command") == command:
            found = row
    if found is None:
        return None
    if found.get("result") == "over-budget" and limit > float(found.get("limit_seconds") or 0):
        return None  # a raised budget runs again
    return found if found.get("result") in ("pass", "fail", "over-budget") else None


def _row(ctx, tree, argv, code, out, err, duration, budget) -> dict:
    text = (out or b"").decode("utf-8", "replace") + "\n" + (err or b"").decode("utf-8", "replace")
    ids = FAILED.findall(text)
    tail = [ln.strip() for ln in text.splitlines() if ln.strip()][-4:]
    result = "over-budget" if code is None else ("pass" if code == 0 else "fail")
    return {"time": logs.now().isoformat(timespec="milliseconds"), "session": ctx.session_id, "tree": tree,
            "command": " ".join(argv), "result": result, "duration_seconds": round(duration, 3),
            "budget_seconds": budget, "limit_seconds": min(budget, HOOK_LIMIT), "exit_code": code,
            "failed_count": len(ids), "failing": ids[:MAX_IDS], "tail": " | ".join(tail)[:600]}


def _verdict(row, roots, limit):
    if row["result"] == "pass":
        return gate.allow()
    if row["result"] == "over-budget":
        return gate.refuse("commit-tests-over-budget",
                           f"the tests of the staged tree did not finish within the budget of "
                           f"{row.get('limit_seconds', limit):g} s (gates.commit_tests.budget_seconds), so the commit "
                           f"is refused. Either the owner raises the budget in the profile, in their own terminal "
                           f"(a session cannot), or you shrink the commit and split it. {OUT}")
    ways = (f"Fix them and stage the fix, or commit the tests alone as the red-first commit (every staged file under "
            f"{', '.join(roots)}; that commit may be red). {OUT}")
    if row["failing"]:
        count = row["failed_count"]
        shown = f"first {len(row['failing'])} of {count}" if count > len(row["failing"]) else f"all {count}"
        return gate.refuse("commit-tests-failed",
                           f"the tests of the staged tree are red: {count} failing ({shown}): "
                           f"{'; '.join(row['failing'])}. {ways}")
    return gate.refuse("commit-tests-failed", f"the tests of the staged tree did not pass: the run exited "
                                              f"{row['exit_code']} and named no failing test ({row['tail']}). {ways}")


def _remove(work: Path, state: Path) -> None:
    """Remove this run's folder, only when it is inside `<state.dir>/commit_tests/`."""
    try:
        if work.exists() and Path(work).resolve().parent == (Path(state) / FOLDER).resolve():
            def writable(func, path, _info):
                os.chmod(path, stat.S_IWRITE)
                func(path)
            try:
                shutil.rmtree(work, onexc=writable)  # Python 3.12 and later
            except TypeError:
                shutil.rmtree(work, onerror=writable)
    except OSError:
        pass
