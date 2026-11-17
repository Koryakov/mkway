"""Card MW-038: one scenario that replays the shape of a real task setup, step after step, driving the engine the way
Claude Code and the owner do (the command lines of the generated `.claude/settings.json` fed a JSON payload on stdin,
the owner's own commands from a terminal), never by calling engine functions.

Why it exists: the owner's reports of 11 and 12 November came from shapes no test built. This one builds them in the
pytest temp folder only (synthetic names, ids and files):

S1 a product repository with 200+ files in several folders, and a LINKED worktree with a sparse checkout of only
   `task/<Name>/` (the task folder two levels down, about 2 per cent of the files present);
S2 an OLDER install in that task folder: the 0.2.1 layout (the engine copy named in the bundle `.gitignore`, the
   entries in `settings.local.json`), built from the 0.2.1 commit of this repository when reachable, else by hand;
S3 a REINSTALL from the working tree with `--commit`, a profile with `commit.message_prefix`, `ids.card_prefix`,
   `vcs git` and `cards.approver orderer`, and a file of another session already staged;
S4 the hooks of the generated settings: session start, `card take` of an open card by builder A, builder B's
   `card take` in the same root;
S5 builder A runs a script that writes a text file and a PNG under its card's Paths, adds and commits them; a staged
   file outside the Paths is refused;
S6 `mkway check --root <root>` run from ANOTHER folder: passes and leaves no file in the copy;
S7 a second linked worktree made from the commit: the start hook works with no install.

The flow runs once (module fixture); each step is its own test. A step that fails on the engine of the day is marked
`xfail(strict=True, reason="MW-038 finding: ...")` and reported; this card fixes no engine file.

The engine source is built from this repository's working tree with its own `tests/` cut to the one fixture test (as
`test_install.make_light_source`), so the inner run of `mkway check` takes seconds, not minutes.

A deny of a PreToolUse hook is exit 0 with `permissionDecision: deny` on stdout (`dispatch.render`); the driver below
reads it. (`test_mw030_live_install.Sessions.fire` reads only the exit code, so a refusal passes there unseen.)
"""
import io
import json
import os
import re
import shlex
import subprocess
import sys
import tarfile
import time
import traceback
from pathlib import Path

import pytest

from _engine import REPO
from _red_project import seed_record_at
from test_install import GIT_ID, make_light_source
from test_mw030_live_install import _env, _git

pytestmark = pytest.mark.engine_repo

TASK = "Alpha"                     # the task folder: <worktree>/task/Alpha
OTHER = "Beta"                     # a sibling task folder the sparse checkout leaves out
PREFIX = "#90001"                  # the product rule: every commit message starts with `#<taskId>` (synthetic)
CARD_PREFIX = "ZZ"                 # `ids.card_prefix` (synthetic)
CARD_A, CARD_B = f"{CARD_PREFIX}-001", f"{CARD_PREFIX}-002"
LEAD, BUILDER_A, BUILDER_B = "session-lead-x", "session-builder-a", "session-builder-b"
PATHS_A = ("tools/gen.py", "tests/test_gen.py", "out/summary.txt", "out/chart.png")
PATHS_B = ("other/b.txt",)
TEST_NODE = "tests/test_gen.py::test_gen"
TIME_LIMIT_SECONDS = 60
CLI = "python mkway/engine/mkway.py"

GEN_SCRIPT = r'''"""A builder's own script: writes a text file and a PNG (binary) under the card's Paths."""
import struct
import sys
import zlib
from pathlib import Path

out = Path(__file__).resolve().parent.parent / "out"
out.mkdir(exist_ok=True)
(out / "summary.txt").write_text("total " + (sys.argv[1] if len(sys.argv) > 1 else "3") + "\n", encoding="utf-8")


def chunk(kind, data):
    body = kind + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
       + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00")) + chunk(b"IEND", b""))
(out / "chart.png").write_bytes(png)
'''


# ---- the driver: hooks as Claude Code runs them ---------------------------------------------------------------------

class Ran:
    """What one tool call did: the hook denials (reason texts), the exit code and output of the action."""

    def __init__(self, denied, code=None, out="", err=""):
        self.denied, self.code, self.out, self.err = denied, code, out, err

    @property
    def reasons(self):
        return [m.group(1) for text in self.denied for m in re.finditer(r"\[mkway \S+ ([a-z0-9-]+)\]", text)]

    @property
    def ok(self):
        return not self.denied and self.code == 0

    def __repr__(self):
        return f"Ran(denied={self.denied!r}, code={self.code}, out={self.out[-300:]!r}, err={self.err[-300:]!r})"


class Hooks:
    """Runs the hook entries of `<root>/.claude/settings.json`, one process each, with the payload on stdin."""

    def __init__(self, base: Path, root: Path):
        self.base, self.root = base, root
        settings = json.loads((root / ".claude" / "settings.json").read_text(encoding="utf-8"))
        self.entries = [(event, group.get("matcher"), handler["command"])
                        for event, groups in settings["hooks"].items() for group in groups
                        for handler in group["hooks"]]
        self.errors = []   # a dispatcher error line, a non-zero exit that is not a refusal, unreadable output

    def fire(self, event, session, tool=None, tool_input=None, tool_response=None):
        payload = {"session_id": session, "hook_event_name": event, "cwd": str(self.root), "transcript_path": ""}
        if tool:
            payload.update(tool_name=tool, tool_input=tool_input)
        if tool_response is not None:
            payload["tool_response"] = tool_response
        denied, outs = [], []
        for entry_event, matcher, command in self.entries:
            if entry_event != event or (tool and matcher and not re.fullmatch(matcher, tool)):
                continue
            argv = shlex.split(command.replace("${CLAUDE_PROJECT_DIR}", self.root.as_posix()))
            proc = subprocess.run(argv, input=json.dumps(payload), capture_output=True, text=True,
                                  cwd=str(self.root), env=_env(self.base, self.root, session=True), timeout=600)
            outs.append(proc.stdout)
            if "mkway dispatcher-error:" in proc.stdout + proc.stderr:
                self.errors.append(f"{event}: dispatcher error: {proc.stdout}{proc.stderr}")
            if proc.returncode == 2:
                denied.append(proc.stderr.strip())
            elif proc.returncode != 0:
                self.errors.append(f"{event}: exit {proc.returncode}: {proc.stderr or proc.stdout}")
            elif proc.stdout.strip():
                try:
                    data = json.loads(proc.stdout)
                except ValueError:
                    self.errors.append(f"{event}: output is not JSON: {proc.stdout[:200]}")
                    continue
                specific = data.get("hookSpecificOutput") or {}
                if specific.get("permissionDecision") == "deny":
                    denied.append(specific.get("permissionDecisionReason", "deny"))
                if data.get("decision") == "block":
                    denied.append(data.get("reason", "block"))
        return denied, outs

    def tool(self, session, tool, tool_input, act):
        denied, _ = self.fire("PreToolUse", session, tool, tool_input)
        if denied:
            return Ran(denied)
        code, out, err, response = act()
        denied, _ = self.fire("PostToolUse", session, tool, tool_input, response)
        return Ran(denied, code, out, err)

    def bash(self, session, command):
        def act():
            proc = subprocess.run(shlex.split(command), capture_output=True, text=True, cwd=str(self.root),
                                  env=_env(self.base, self.root, session=True), timeout=600)
            return proc.returncode, proc.stdout, proc.stderr, {"stdout": proc.stdout, "stderr": proc.stderr,
                                                                "exit_code": proc.returncode}
        return self.tool(session, "Bash", {"command": command}, act)

    def write(self, session, rel, content):
        path = self.root / rel

        def act():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")
            return 0, "", "", {"filePath": str(path), "type": "create"}
        return self.tool(session, "Write", {"file_path": str(path), "content": content}, act)


# ---- the owner's side ------------------------------------------------------------------------------------------------

def _owner(base, root, *args, script=None, cwd=None):
    """The owner's own terminal: no session variable, the launcher of the working tree (or of the copy)."""
    return subprocess.run([sys.executable, str(script or (REPO / "mkway.py")), *args], capture_output=True, text=True,
                          cwd=str(cwd or root), env=_env(base, root, session=False), timeout=900)


def _listing(folder: Path) -> dict:
    """{posix path below `folder`: (size, mtime_ns)} of every file, the `.git` entry left out."""
    found = {}
    for path in sorted(folder.rglob("*")):
        rel = path.relative_to(folder).as_posix()
        if rel == ".git" or rel.startswith(".git/") or not path.is_file():
            continue
        stat = path.stat()
        found[rel] = (stat.st_size, stat.st_mtime_ns)
    return found


def _old_layout_source(base: Path):
    """The 0.2.1 release as an install source, read from this repository's history (a read form, nothing written
    there): (folder, short sha), or None when the commit is not reachable (a shallow clone)."""
    git = ["git", "--no-optional-locks", "-C", str(REPO)]
    found = subprocess.run([*git, "log", "-1", "--format=%H", "--grep=^MW-024 green"], capture_output=True, text=True)
    sha = found.stdout.strip()
    if found.returncode != 0 or not sha:
        return None
    packed = subprocess.run([*git, "archive", "--format=tar", sha], capture_output=True)
    if packed.returncode != 0:
        return None
    dest = base / "old-src"
    with tarfile.open(fileobj=io.BytesIO(packed.stdout)) as tar:
        for member in tar.getmembers():
            if member.isfile() and ".." not in Path(member.name).parts:
                target = dest / member.name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(tar.extractfile(member).read())
    return dest, sha[:7]


def _card_text(template: str, paths, node, goal) -> str:
    text = template.replace("| **Paths** | |", "| **Paths** | " + ", ".join(f"`{p}`" for p in paths) + " |")
    text = text.replace("«the owner's words, quoted» — owner, YYYY-MM-DD.", goal)
    return text.replace("| E1 | item id | value today | value after the change | tests/test_x.py::test_y |",
                        f"| E1 | the item | absent | present | {node} |")


class Shape:
    """What the one scenario did, filled step by step; a step that could not run leaves its error in `failed`."""

    def __init__(self):
        self.failed = {}
        self.seconds = None


def _step(shape, name, run):
    try:
        run()
    except Exception:  # noqa: BLE001 - recorded, the test of the step fails with it
        shape.failed[name] = traceback.format_exc()


def _need(shape, *names):
    for name in names:
        if name in shape.failed:
            pytest.fail(f"step {name} of the scenario could not run: {shape.failed[name]}")


# ---- S1 ---------------------------------------------------------------------------------------------------------------

def _s1(shape):
    base, main, wt = shape.base, shape.main, shape.wt
    for folder in range(8):
        for number in range(26):
            path = main / "modules" / f"m{folder}" / f"f{number}.txt"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"module {folder} file {number}\n", encoding="utf-8")
    (main / "task" / OTHER).mkdir(parents=True)
    (main / "task" / OTHER / "b.txt").write_text("b\n", encoding="utf-8")
    (main / "task" / TASK / "notes").mkdir(parents=True)
    (main / "task" / TASK / "README.txt").write_text("the task\n", encoding="utf-8")
    (main / "task" / TASK / "notes" / "n1.txt").write_text("n1\n", encoding="utf-8")
    (main / "top.txt").write_text("t\n", encoding="utf-8")
    _git(base, "init", "-q", str(main))
    _git(main, "add", "-A")
    _git(main, "commit", "-q", "-m", "base")
    _git(main, "worktree", "add", "-q", "--no-checkout", str(wt), "-b", "work")
    _git(wt, "sparse-checkout", "set", "--cone", f"task/{TASK}")
    _git(wt, "checkout", "-q", "-f", "work")
    shape.total = len(_git(main, "ls-files").split())
    shape.present = len(_listing(wt))


# ---- S2 ---------------------------------------------------------------------------------------------------------------

def _s2(shape):
    base, root = shape.base, shape.root
    shape.old_kind = None
    old = _old_layout_source(base)
    if old is not None:
        def old_install():
            return _owner(base, root, "install", "--from", str(old[0]), "--root", str(root), script=old[0] / "mkway.py")

        proc = old_install()
        shape.old_output = proc.stdout + proc.stderr
        if proc.returncode == 0:
            shape.old_kind = f"the 0.2.1 commit {old[1]}"
            profile_path = root / "mkway" / "profile.json"
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            if profile.get("vcs") != "git":  # 0.2.1 read `none` below the git top (MW-028); the owner sets git, installs again
                profile["vcs"] = "git"
                profile_path.write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")
                proc = old_install()
                shape.old_output += proc.stdout + proc.stderr
                if proc.returncode != 0:
                    shape.old_kind = None
    if shape.old_kind is None:  # not reachable (or it did not install): an old-style bundle written by hand
        proc = _owner(base, root, "install", "--from", str(shape.src), "--ref", "HEAD", "--root", str(root))
        assert proc.returncode == 0, proc.stdout + proc.stderr
        bundle = root / "mkway"
        (bundle / ".gitignore").write_text("engine/\nlocks/\nstate/\n__pycache__/\n", encoding="utf-8")
        old_state = shape.main / "task" / TASK / "mkway" / "state"  # the old layout: shared state in the main checkout
        old_state.mkdir(parents=True, exist_ok=True)
        (old_state / "machine.json").write_text("{}\n", encoding="utf-8")
        shape.old_kind = "a bundle written by hand (the 0.2.1 commit is not reachable)"
    ignore = root / "mkway" / ".gitignore"
    shape.old_ignore = ignore.read_text(encoding="utf-8").splitlines() if ignore.is_file() else []
    _git(root, "add", "-A", ".")  # the owner commits what the old install wrote; the engine copy stays out (ignored)
    _git(root, "commit", "-q", "-m", f"{PREFIX} old install")
    shape.old_tracked_engine = _git(root, "ls-files", "mkway/engine").split()
    shape.main_after_s2 = _listing(shape.main)


# ---- S3 ---------------------------------------------------------------------------------------------------------------

def _s3(shape):
    base, root = shape.base, shape.root
    profile_path = root / "mkway" / "profile.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    profile["vcs"] = "git"
    profile.setdefault("ids", {})["card_prefix"] = CARD_PREFIX
    profile["cards"] = {"approver": "orderer"}
    profile["commit"] = {"message_prefix": PREFIX}
    profile_path.write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")
    _git(root, "add", "mkway/profile.json")
    _git(root, "commit", "-q", "-m", f"{PREFIX} profile", "--", "mkway/profile.json")  # the owner commits their file
    (root / "foreign.txt").write_text("another session's file\n", encoding="utf-8")
    _git(root, "add", "foreign.txt")  # another session's file already staged in the shared index
    proc = _owner(base, root, "install", "--from", str(shape.src), "--ref", "HEAD", "--root", str(root), "--commit")
    shape.reinstall = (proc.returncode, proc.stdout + proc.stderr)
    shape.reinstall_subject = _git(root, "log", "-1", "--format=%s").strip()
    shape.reinstall_taken = _git(root, "show", "--name-only", "--format=", "--relative", "HEAD").split()
    shape.reinstall_staged = _git(root, "diff", "--cached", "--name-only", "--relative").split()
    shape.engine_tracked = _git(root, "ls-files", "mkway/engine/mkway.py").split()
    shape.ignore_after = (root / "mkway" / ".gitignore").read_text(encoding="utf-8").splitlines()
    local = root / ".claude" / "settings.local.json"
    shape.local_settings = json.loads(local.read_text(encoding="utf-8")) if local.is_file() else {}


# ---- S4 and S5 ----------------------------------------------------------------------------------------------------------

def _make_cards(shape, hooks):
    """The lead registers, writes two cards and opens them (approver orderer): the owner's real order of work."""
    steps = [("lead register", lambda: hooks.bash(LEAD, f"{CLI} lead register")),
             ("card new A", lambda: hooks.bash(LEAD, f"{CLI} card new Report one")),
             ("card new B", lambda: hooks.bash(LEAD, f"{CLI} card new Report two"))]
    for name, run in steps:
        ran = run()
        assert ran.ok, f"{name}: {ran!r}"
    for card, paths, node in ((CARD_A, PATHS_A, TEST_NODE), (CARD_B, PATHS_B, "tests/test_b.py::test_b")):
        folder = next((shape.root / "mkway" / "cards").glob(f"{card}-*"))
        rel = folder.relative_to(shape.root).as_posix()
        template = (folder / "CARD.md").read_text(encoding="utf-8")
        for name, ran in (("write CARD.md", hooks.write(LEAD, f"{rel}/CARD.md", _card_text(
                template, paths, node, "A synthetic goal: the scenario of MW-038 walks one card through the gates."))),
                          ("write ORDER.md", hooks.write(LEAD, f"{rel}/ORDER.md", "Order: write the files.\n")),
                          ("card open", hooks.bash(LEAD, f"{CLI} card open {card}"))):
            assert ran.ok, f"{card} {name}: {ran!r}"


def _s4(shape):
    root = shape.root
    hooks = shape.hooks = Hooks(shape.base, root)
    shape.start = {}
    for session in (LEAD, BUILDER_A, BUILDER_B):
        denied, outs = hooks.fire("SessionStart", session)
        shape.start[session] = (denied, "\n".join(outs))
    _make_cards(shape, hooks)
    shape.take_a = hooks.bash(BUILDER_A, f"{CLI} card take {CARD_A}")
    shape.take_b = hooks.bash(BUILDER_B, f"{CLI} card take {CARD_B}")


def _s5(shape):
    root, hooks = shape.root, shape.hooks
    paths = " ".join(PATHS_A)
    assert hooks.write(BUILDER_A, "tools/gen.py", GEN_SCRIPT).ok, "write the script"
    assert hooks.write(BUILDER_A, "tests/test_gen.py", 'def test_gen():\n    """Checks: one plus one is two."""\n    assert 1 + 1 == 2\n').ok, "write the test"
    shape.script = hooks.bash(BUILDER_A, "python tools/gen.py")  # not the Write tool: no hook sees the files written
    shape.add = hooks.bash(BUILDER_A, f"git add {paths}")
    # R217a: seeded red record for an id that never ran red here: a precondition of this step, whose subject is the mixed
    # four-path commit and the stray-file refusals, never a gate set to watch; the later commits of this step use the same record
    seed_record_at(root, CARD_A, lambda *args: _git(root, *args), red=[TEST_NODE])
    command = f'git commit -m "{PREFIX} {CARD_A} add the generated report" -- {paths}'
    shape.foreign_staged_at_commit = "foreign.txt" in _git(root, "diff", "--cached", "--name-only", "--relative").split()
    shape.commit = hooks.bash(BUILDER_A, command)
    shape.commit_retried = False
    if shape.commit.denied and shape.foreign_staged_at_commit:
        # the owner clears the shared index so that the rest of the step can run; the first attempt stays recorded
        _git(root, "restore", "--staged", "foreign.txt")
        shape.commit_retried = True
        shape.commit_second = hooks.bash(BUILDER_A, command)
    final = shape.commit_second if shape.commit_retried else shape.commit
    if final.ok:
        shape.head_subject = _git(root, "log", "-1", "--format=%s").strip()
        shape.head_taken = _git(root, "show", "--name-only", "--format=", "--relative", "HEAD").split()
        shape.png_committed = subprocess.run(["git", *GIT_ID, "show", "HEAD:./out/chart.png"], cwd=str(root),
                                             capture_output=True).stdout
        shape.png_on_disk = (root / "out" / "chart.png").read_bytes()
    # a staged file outside the Paths, then a commit of a file inside them
    (root / "stray.txt").write_text("outside the card\n", encoding="utf-8")
    shape.stray_add = hooks.bash(BUILDER_A, "git add stray.txt")
    shape.script2 = hooks.bash(BUILDER_A, "python tools/gen.py 4")
    shape.add2 = hooks.bash(BUILDER_A, "git add out/summary.txt")
    # changed after MW-043: `--` takes the named paths alone, so this commit is allowed beside the staged stray file
    shape.stray_commit = hooks.bash(BUILDER_A, f'git commit -m "{PREFIX} {CARD_A} change the total" -- out/summary.txt')
    # the staged-list form takes stray.txt; a named path outside the Paths is refused in the `--` form too
    shape.stray_plain = hooks.bash(BUILDER_A, f'git commit -m "{PREFIX} {CARD_A} plain commit"')
    shape.stray_named = hooks.bash(BUILDER_A, f'git commit -m "{PREFIX} {CARD_A} name the stray file" -- stray.txt')
    # MW-061: the shape of a real report: a real newline and an empty line inside the double quotes, a trailer line with
    # angle brackets, the named paths after `--` (the stray file is still staged; the commit names its own path only)
    shape.script3 = hooks.bash(BUILDER_A, "python tools/gen.py 5")
    shape.add3 = hooks.bash(BUILDER_A, "git add out/summary.txt")
    shape.multiline = hooks.bash(BUILDER_A, f'git commit -m "{PREFIX} {CARD_A} change the total again\n\n'
                                            f'  Trailer: second paragraph <angle text>" -- out/summary.txt')
    shape.multiline_body = _git(root, "log", "-1", "--format=%B").strip()


# ---- S6 and S7 ----------------------------------------------------------------------------------------------------------

def _s6(shape):
    base, root = shape.base, shape.root
    elsewhere = base / "elsewhere"
    elsewhere.mkdir()
    copy = root / "mkway" / "engine"
    shape.copy_before = _listing(copy)
    proc = _owner(base, root, "check", "--root", str(root), script=copy / "mkway.py", cwd=elsewhere)
    shape.check = (proc.returncode, proc.stdout + proc.stderr)
    shape.copy_after = _listing(copy)
    shape.elsewhere_files = sorted(p.name for p in elsewhere.iterdir())


def _s7(shape):
    base, main = shape.base, shape.main
    wt2 = base / "wt2"
    _git(main, "worktree", "add", "-q", str(wt2), "-b", "second", "work")
    root2 = shape.root2 = wt2 / "task" / TASK
    shape.copy_in_second = (root2 / "mkway" / "engine" / "mkway.py").is_file()
    hooks = shape.hooks2 = Hooks(base, root2)
    denied, outs = hooks.fire("SessionStart", "session-second")
    shape.start_second = (denied, "\n".join(outs))
    shape.main_at_end = _listing(main)


def _s8(shape):
    """MW-053: the lead that ordered CARD_B commits its folder and the register, alone, from the task root, in the
    command shape of the real install: `git commit -m "<prefix> <card> card and order" -- <folder> <register>`."""
    root, hooks = shape.root, shape.hooks
    folder = next((root / "mkway" / "cards").glob(f"{CARD_B}-*")).relative_to(root).as_posix()
    shape.lead_paths = [folder, "mkway/cards/REGISTER.md"]
    shape.lead_add = hooks.bash(LEAD, f"git add {' '.join(shape.lead_paths)}")
    shape.lead_builder_commit = hooks.bash(BUILDER_B, f'git commit -m "{PREFIX} {CARD_B} not mine" -- {folder}')
    command = f'git commit -m "{PREFIX} {CARD_B} card and order" -- {" ".join(shape.lead_paths)}'
    shape.lead_commit = hooks.bash(LEAD, command)
    shape.lead_folder_files = sorted(p.relative_to(root).as_posix() for p in (root / folder).rglob("*") if p.is_file())
    shape.lead_taken = _git(root, "show", "--name-only", "--format=", "--relative", "HEAD").split()
    shape.lead_subject = _git(root, "log", "-1", "--format=%s").strip()


@pytest.fixture(scope="module")
def shape(tmp_path_factory):
    started = time.perf_counter()
    result = Shape()
    base = result.base = tmp_path_factory.mktemp("shape")
    result.main, result.wt = base / "product", base / "wt"
    result.root = result.wt / "task" / TASK
    _step(result, "S1", lambda: _s1(result))
    if "S1" not in result.failed:
        src = result.src = make_light_source(base)
        _git(src, "init", "-q")
        _git(src, "add", "-A")
        _git(src, "commit", "-q", "-m", "engine source")
        _step(result, "S2", lambda: _s2(result))
        if "S2" not in result.failed:
            _step(result, "S3", lambda: _s3(result))
            if "S3" not in result.failed:
                _step(result, "S4", lambda: _s4(result))
                if "S4" not in result.failed:
                    _step(result, "S5", lambda: _s5(result))
                _step(result, "S6", lambda: _s6(result))
                _step(result, "S7", lambda: _s7(result))
                if "S4" not in result.failed and "S5" not in result.failed:
                    _step(result, "S8", lambda: _s8(result))
    result.seconds = time.perf_counter() - started
    return result


# ---- the steps, one test each -------------------------------------------------------------------------------------------

def test_s1_a_sparse_linked_worktree_of_a_bigger_repository(shape):
    """S1: the product repository holds 200+ files in several folders; the linked worktree has only the task folder
    (and the top files) checked out, about 2 per cent of the files, and the task folder is two levels down."""
    _need(shape, "S1")
    assert shape.total >= 200, f"S1: the product repository has {shape.total} files"
    assert 0 < shape.present <= shape.total * 0.05, f"S1: {shape.present} of {shape.total} files are present"
    assert (shape.root / "README.txt").is_file(), "S1: the task folder is not checked out"
    assert not (shape.wt / "modules").exists(), "S1: the sparse checkout holds a folder outside the task"
    assert shape.root.relative_to(shape.wt).as_posix() == f"task/{TASK}", "S1: the task folder is not two levels down"
    assert (shape.wt / ".git").is_file(), "S1: the worktree is not a linked one (its .git is not a file)"


def test_s2_an_older_install_is_in_place(shape):
    """S2: before the reinstall the bundle is in the old layout: `engine/` named in the bundle `.gitignore`, the engine
    copy not tracked, the install itself committed by the owner."""
    _need(shape, "S1", "S2")
    assert "engine/" in shape.old_ignore, f"S2: ({shape.old_kind}) the bundle .gitignore holds {shape.old_ignore}"
    assert shape.old_tracked_engine == [], f"S2: ({shape.old_kind}) the engine copy is tracked: {shape.old_tracked_engine}"
    assert (shape.root / "mkway" / "engine" / "mkway.py").is_file(), f"S2: ({shape.old_kind}) no engine copy"
    assert (shape.root / "mkway" / "profile.json").is_file(), f"S2: ({shape.old_kind}) no profile"


def test_s3_the_reinstall_commit_takes_only_the_install_paths(shape):
    """S3: `install --commit` over the older install, with the profile above and a foreign file staged: exit 0, the
    engine copy tracked, no `engine/` line, the message starts with the product's prefix, the commit holds only the
    paths install writes, and the foreign file is still staged and not in the commit."""
    _need(shape, "S1", "S2", "S3")
    code, text = shape.reinstall
    assert code == 0, f"S3: the reinstall exits {code}: {text}"
    assert shape.engine_tracked == ["mkway/engine/mkway.py"], f"S3: the engine copy is not tracked: {shape.engine_tracked}"
    assert "engine/" not in shape.ignore_after, f"S3: the stale `engine/` line is still there: {shape.ignore_after}"
    assert shape.reinstall_subject.startswith(PREFIX), f"S3: the commit message is {shape.reinstall_subject!r}"
    own = (".claude/settings.json", "mkway/.gitignore", "mkway/.gitattributes", "mkway/mkway.lock", ".claude/agents/fresh-reader.md")
    taken = shape.reinstall_taken
    assert taken, "S3: the install commit holds no file"
    stray = [p for p in taken if p not in own and not p.startswith("mkway/engine/")]
    assert not stray, f"S3: the install commit holds more than install's paths: {stray}"
    assert ".claude/settings.json" in taken and "mkway/mkway.lock" in taken, f"S3: the commit lacks install's own files: {taken}"
    assert "foreign.txt" not in taken, f"S3: the foreign staged file rode into the install commit: {taken}"
    assert shape.reinstall_staged == ["foreign.txt"], f"S3: the foreign file is no longer staged: {shape.reinstall_staged}"


def test_s3_the_old_local_settings_no_longer_run_the_hooks_twice(shape):
    """S3 (older install): after the reinstall `.claude/settings.local.json` holds no hook entry of the bundle, as the
    committed `.claude/settings.json` holds them; two copies of an entry would run every gate twice."""
    _need(shape, "S1", "S2", "S3")
    entries = [h["command"] for groups in (shape.local_settings.get("hooks") or {}).values() for g in groups
               for h in g.get("hooks", []) if "mkway" in h.get("command", "")]
    assert not entries, f"S3: {shape.old_kind}: settings.local.json still holds {len(entries)} mkway entries"


def test_s4_start_hooks_and_the_second_builder_in_one_root(shape):
    """S4: through the generated settings: the start hook of every session prints the start block with no error; builder
    A takes the open card; builder B's `card take` in the same root is refused `take-root-busy`."""
    _need(shape, "S1", "S2", "S3", "S4")
    for session, (denied, block) in shape.start.items():
        assert "mkway v" in block, f"S4: no start block for {session}: {block!r} {denied}"
        for bad in ("profile-invalid", "drift-machine", "mkway dispatcher-error:"):
            assert bad not in block, f"S4: the start block of {session} holds {bad}: {block}"
    assert shape.take_a.ok, f"S4: builder A's card take of the open card {CARD_A}: {shape.take_a!r}"
    assert shape.take_b.reasons == ["take-root-busy"], f"S4: builder B's card take: {shape.take_b!r}"
    assert not shape.hooks.errors, f"S4: hook errors: {shape.hooks.errors}"


def test_s5_a_script_written_text_and_png_commit_through_the_gates(shape):
    """S5: builder A runs its own script (not the Write tool) that writes a text and a PNG under its Paths, adds them,
    and runs `git commit -m "<prefix> <card> ..." -- <paths>`: allowed, with the file of another session still staged
    in the shared index."""
    _need(shape, "S1", "S2", "S3", "S4", "S5")
    assert shape.script.ok, f"S5: the script run: {shape.script!r}"
    assert shape.add.ok, f"S5: git add: {shape.add!r}"
    assert shape.commit.ok, (f"S5: the commit of the card's own files is refused (foreign file staged at that moment: "
                             f"{shape.foreign_staged_at_commit}): {shape.commit!r}")


def test_s5_the_commit_holds_the_paths_the_png_bytes_and_the_prefix(shape):
    """S5: the commit exists, its message starts with the product's prefix and names the card, it holds exactly the
    card's Paths, and the PNG in the commit is the file on disk, byte for byte."""
    _need(shape, "S1", "S2", "S3", "S4", "S5")
    final = shape.commit_second if shape.commit_retried else shape.commit
    assert final.ok, f"S5: no commit was made: {final!r}"
    assert shape.head_subject.startswith(PREFIX) and CARD_A in shape.head_subject, f"S5: {shape.head_subject!r}"
    assert sorted(shape.head_taken) == sorted(PATHS_A), f"S5: the commit holds {shape.head_taken}"
    assert shape.png_committed == shape.png_on_disk and shape.png_on_disk.startswith(b"\x89PNG"), "S5: the PNG differs"


def test_s5_a_staged_file_outside_the_paths_is_refused(shape):
    """S5 (changed after MW-043): with a file outside the card's Paths staged, a commit that names only inside paths
    after `--` takes those alone and is allowed; a plain commit takes the staged list and is refused `file-not-in-card`
    naming the file; a commit that names a path outside the Paths after `--` is refused `file-not-in-card` too."""
    _need(shape, "S1", "S2", "S3", "S4", "S5")
    assert shape.stray_add.ok and shape.add2.ok, f"S5: the setup of the refusal failed: {shape.stray_add!r} {shape.add2!r}"
    assert shape.stray_commit.ok, f"S5: the `-- <inside path>` commit is refused: {shape.stray_commit!r}"
    assert shape.stray_plain.reasons == ["file-not-in-card"], f"S5: {shape.stray_plain!r}"
    assert "stray.txt" in " ".join(shape.stray_plain.denied), f"S5: the refusal does not name the file: {shape.stray_plain!r}"
    assert shape.stray_named.reasons == ["file-not-in-card"], f"S5: {shape.stray_named!r}"
    assert "stray.txt" in " ".join(shape.stray_named.denied), f"S5: the refusal does not name the file: {shape.stray_named!r}"


def test_s5_a_commit_message_with_a_newline_inside_the_quotes_passes_the_gates(shape):
    """S5 (MW-061): the builder's `git commit -m "<line>\\n\\n  <trailer>" -- <path>` with a real newline and an empty line
    inside the quotes is allowed through the real hooks, the stray file staged beside it stays out, and the commit
    message holds both paragraphs."""
    _need(shape, "S1", "S2", "S3", "S4", "S5")
    assert shape.script3.ok and shape.add3.ok, f"S5: the setup failed: {shape.script3!r} {shape.add3!r}"
    assert shape.multiline.ok, f"S5: the multi-line commit is refused: {shape.multiline!r}"
    assert "change the total again" in shape.multiline_body and "Trailer: second paragraph" in shape.multiline_body, \
        f"S5: the commit message is {shape.multiline_body!r}"


def test_s6_check_from_another_folder_passes_and_leaves_the_copy_alone(shape):
    """S6: `mkway check --root <root>` run from ANOTHER folder exits 0, its test run is green, and the engine copy
    holds the same files with the same sizes and times after it as before it."""
    _need(shape, "S1", "S2", "S3", "S6")
    code, text = shape.check
    assert code == 0, f"S6: check exits {code}: {text}"
    assert re.search(r"tests: \d+ passed", text), f"S6: no green test line: {text}"
    assert shape.copy_after == shape.copy_before, (
        "S6: check changed the copy: "
        f"{sorted(set(shape.copy_after) ^ set(shape.copy_before)) or [k for k in shape.copy_after if shape.copy_after[k] != shape.copy_before.get(k)]}")
    assert shape.elsewhere_files == [], f"S6: check wrote into the folder it ran from: {shape.elsewhere_files}"


def test_s7_a_second_worktree_of_the_commit_starts_with_no_install(shape):
    """S7: a second linked worktree made from the commit: the engine copy is in it, the start hook of its generated
    settings prints the start block, with no drift, no profile error and no dispatcher error."""
    _need(shape, "S1", "S2", "S3", "S7")
    assert shape.copy_in_second, "S7: the engine copy is not in the second worktree (it was not committed)"
    denied, block = shape.start_second
    assert "mkway v" in block, f"S7: no start block: {block!r} {denied}"
    for bad in ("profile-invalid", "drift-machine", "mkway dispatcher-error:"):
        assert bad not in block, f"S7: the start block holds {bad}: {block}"
    assert not shape.hooks2.errors, f"S7: hook errors: {shape.hooks2.errors}"


def test_s8_the_lead_commits_the_card_folder_it_ordered(shape):
    """S8 (MW-053): the lead holds no card; `git commit -m "<prefix> <card> card and order" -- <folder> <register>` of the
    card it ordered is allowed, the commit holds the folder's files and the register; a builder's commit of the same
    folder is refused `file-not-in-card`."""
    _need(shape, "S1", "S2", "S3", "S4", "S5", "S8")
    assert shape.lead_add.ok, f"S8: git add: {shape.lead_add!r}"
    assert shape.lead_commit.ok, f"S8: the lead's commit of the card folder it ordered is refused: {shape.lead_commit!r}"
    assert shape.lead_subject.startswith(PREFIX) and CARD_B in shape.lead_subject, f"S8: {shape.lead_subject!r}"
    assert set(shape.lead_folder_files) <= set(shape.lead_taken) and "mkway/cards/REGISTER.md" in shape.lead_taken, \
        f"S8: the commit holds {shape.lead_taken}"
    assert shape.lead_builder_commit.reasons == ["file-not-in-card"], f"S8: {shape.lead_builder_commit!r}"


def test_nothing_in_the_scenario_wrote_into_the_main_checkout(shape):
    """After the older install: no file of the main checkout changes through the reinstall, the sessions, the check and
    the second worktree (the state of a linked worktree stays in its own task root, MW-026)."""
    _need(shape, "S1", "S2", "S7")
    before, after = shape.main_after_s2, shape.main_at_end
    changed = sorted(rel for rel in set(before) | set(after) if before.get(rel) != after.get(rel))
    assert not changed, f"the main checkout changed after S2: {changed}"


@pytest.mark.perf
def test_the_scenario_runs_inside_the_time_limit(shape):
    """The whole scenario, repository to second worktree, takes about a minute.
    A wall-clock check, marked perf and kept out of commit and merge runs (R172)."""
    assert shape.seconds < TIME_LIMIT_SECONDS, f"{shape.seconds:.0f} s (limit {TIME_LIMIT_SECONDS} s)"
