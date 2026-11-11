"""Card MW-030: the live install test, the release gate. No version is tagged or recommended before this passes.

It reproduces the layout of a real first install, in the pytest temp folder only: a fixture git repository with one
commit, a LINKED worktree of it made with `worktree add --no-checkout`, `sparse-checkout set --cone task/<Task>`, a
checkout, and the task folder made by mkdir (untracked). Then `mkway install --from <engine source> --ref HEAD --root
<task folder>`, `mkway check` run from the task folder with no `--root` and no `CLAUDE_PROJECT_DIR`, and a lead
session and a builder session that run through the HOOKS the install wrote (the committed `.claude/settings.json`,
MW-027), each hook a real process fed a hook payload, exactly as Claude Code runs it. At the end the install is
committed in the fixture, a second linked worktree is made from that commit, and the start hook runs there with no
install (MW-027).

One flow runs once (module fixture); each Test cases row reads its part. Synthetic names and ids only.

The engine source is a git repository built from this repository's engine files with its own `tests/` cut to the one
fixture test (as `test_install.make_light_source`): `mkway check` has no flag that skips its inner run of the copy's
tests, and the whole inner run takes minutes, not the minute this test may take. Every other line of `check` is the
real one.
"""
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

import pytest

from _engine import REPO
from test_install import GIT_ID, make_light_source

pytestmark = pytest.mark.engine_repo

TASK = "Task1"  # the synthetic task folder: <worktree>/task/Task1
LEAD, BUILDER = "session-lead-a", "session-builder-b"
CARD_ID = "CARD-001"
CARD_TITLE = "Live install check"
PATHS = ("src/feature.py", "tests/test_live.py")
TEST_NODE = "tests/test_live.py::test_live_feature"
TIME_LIMIT_SECONDS = 90  # the card says about 60; the gate fails the run only past this
SHARED_STATE = f"task/{TASK}/mkway/state"  # where MW-026 (state in root) puts the linked worktree's shared state


def _git(cwd, *args):
    return subprocess.run(["git", *GIT_ID, *args], cwd=str(cwd), capture_output=True, text=True, check=True).stdout


def _listing(folder: Path, skip) -> dict:
    """{posix path below `folder`: (size, mtime_ns)} of every file, minus the `.git` entry and what `skip` names."""
    found = {}
    for path in sorted(folder.rglob("*")):
        rel = path.relative_to(folder).as_posix()
        if rel == ".git" or rel.startswith(".git/") or skip(rel) or not path.is_file():
            continue
        stat = path.stat()
        found[rel] = (stat.st_size, stat.st_mtime_ns)
    return found


class Live:
    """What the one flow did: the refusals and failures in order, the outputs, the listings, the clock."""

    def __init__(self):
        self.problems = []   # (step, what the engine said): any entry fails the path
        self.outputs = {}
        self.seconds = None
        self.builder_commit = ""  # MW-027: the subject of the last commit before the install commit
        self.status = ""     # MW-027: `git status --porcelain` of the task folder after the flow
        self.second = None   # MW-027: the second worktree's own Live, set when the install succeeded
        self.reinstall_commit = None  # MW-035: what a `--commit` reinstall with a stale ignore line and a staged file did

    def problem(self, step, text):
        self.problems.append((step, text.strip()))

    def message(self):
        return "; ".join(f"[{step}] {text}" for step, text in self.problems)


def _env(base: Path, root: Path, *, session: bool):
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_PROJECT_DIR", "ENGINE_TERMS_FILE", "CLAUDECODE")}
    home = base / "home"
    home.mkdir(exist_ok=True)
    env.update(HOME=str(home), USERPROFILE=str(home), GIT_CEILING_DIRECTORIES=str(base.resolve()),
               GIT_AUTHOR_NAME="live-test", GIT_AUTHOR_EMAIL="live-test", GIT_COMMITTER_NAME="live-test",
               GIT_COMMITTER_EMAIL="live-test", PYTHONDONTWRITEBYTECODE="1")
    if session:  # what a session's shell carries
        env.update(CLAUDECODE="1", CLAUDE_PROJECT_DIR=str(root))
    return env


class Sessions:
    """Runs hooks and tool calls the way Claude Code does, against the entries the install wrote."""

    def __init__(self, base: Path, root: Path, live: Live):
        self.base, self.root, self.live = base, root, live
        settings = json.loads((root / ".claude" / "settings.json").read_text(encoding="utf-8"))
        self.entries = [(event, group.get("matcher"), handler["command"])
                        for event, groups in settings["hooks"].items() for group in groups
                        for handler in group["hooks"]]

    def fire(self, step, event, session, tool=None, tool_input=None, tool_response=None) -> list:
        """Every hook entry of `event` whose matcher fits `tool`, one process each; returns the stdout texts. An exit 2
        (a refusal) or a dispatcher error line is a problem; the first refusal is returned as None."""
        payload = {"session_id": session, "hook_event_name": event, "cwd": str(self.root), "transcript_path": ""}
        if tool:
            payload.update(tool_name=tool, tool_input=tool_input)
        if tool_response is not None:
            payload["tool_response"] = tool_response
        outs = []
        for entry_event, matcher, command in self.entries:
            if entry_event != event or (tool and matcher and not re.fullmatch(matcher, tool)):
                continue
            argv = shlex.split(command.replace("${CLAUDE_PROJECT_DIR}", self.root.as_posix()))
            proc = subprocess.run(argv, input=json.dumps(payload), capture_output=True, text=True, cwd=str(self.root),
                                  env=_env(self.base, self.root, session=True), timeout=600)
            group = argv[argv.index("--group") + 1] if "--group" in argv else "?"
            if proc.returncode != 0:
                self.live.problem(step, f"{event}/{group} exit {proc.returncode}: {proc.stderr or proc.stdout}")
                return None
            if "mkway dispatcher-error:" in proc.stdout + proc.stderr:  # the dispatcher's own line (R13c)
                self.live.problem(step, f"{event}/{group} dispatcher error: {proc.stdout}{proc.stderr}")
                return None
            outs.append(proc.stdout)
        return outs

    def tool(self, step, session, tool, tool_input, act):
        """PreToolUse hooks, the action, PostToolUse hooks. Returns the action's result, or None after a refusal."""
        if self.fire(step, "PreToolUse", session, tool, tool_input) is None:
            return None
        result = act()
        if result is None:
            return None
        if self.fire(step, "PostToolUse", session, tool, tool_input, result) is None:
            return None
        return result

    def bash(self, step, session, command, *, expect_ok=True):
        def act():
            proc = subprocess.run(shlex.split(command), capture_output=True, text=True, cwd=str(self.root),
                                  env=_env(self.base, self.root, session=True), timeout=600)
            if expect_ok and proc.returncode != 0:
                self.live.problem(step, f"`{command}` exit {proc.returncode}: {proc.stdout}{proc.stderr}")
                return None
            return {"stdout": proc.stdout, "stderr": proc.stderr, "exit_code": proc.returncode}
        return self.tool(step, session, "Bash", {"command": command}, act)

    def write(self, step, session, rel, content):
        path = self.root / rel

        def act():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")
            return {"filePath": str(path), "type": "create"}
        return self.tool(step, session, "Write", {"file_path": str(path), "content": content}, act)

    def edit(self, step, session, rel, old, new):
        path = self.root / rel

        def act():
            text = path.read_text(encoding="utf-8")
            path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")
            return {"filePath": str(path)}
        return self.tool(step, session, "Edit", {"file_path": str(path), "old_string": old, "new_string": new}, act)


def _card_text(template: str) -> str:
    text = template.replace("| **Paths** | |", "| **Paths** | " + ", ".join(f"`{p}`" for p in PATHS) + " |")
    text = text.replace("«the owner's words, quoted» — owner, YYYY-MM-DD.",
                        "A synthetic goal: the live install test walks one card through every gate.")
    return text.replace("| E1 | item id | value today | value after the change | tests/test_x.py::test_y |",
                        f"| E1 | the feature | absent | present | {TEST_NODE} |")


@pytest.fixture(scope="module")
def live(tmp_path_factory):
    started = time.perf_counter()
    result = Live()
    base = tmp_path_factory.mktemp("live")
    main, wt = base / "main", base / "wt"
    root = wt / "task" / TASK
    (main / "task" / "other").mkdir(parents=True)
    (main / "task" / "other" / "a.txt").write_text("a\n", encoding="utf-8")
    (main / "top.txt").write_text("t\n", encoding="utf-8")
    _git(base, "init", "-q", str(main))
    _git(main, "add", "-A")
    _git(main, "commit", "-q", "-m", "base")
    _git(main, "worktree", "add", "-q", "--no-checkout", str(wt), "-b", "work")
    _git(wt, "sparse-checkout", "set", "--cone", f"task/{TASK}")
    _git(wt, "checkout", "-q", "-f", "work")
    root.mkdir(parents=True)  # made by mkdir, untracked
    result.base, result.main, result.wt, result.root = base, main, wt, root
    in_root = lambda rel: rel == f"task/{TASK}" or rel.startswith(f"task/{TASK}/")  # noqa: E731
    before_main = _listing(main, lambda rel: False)
    before_wt = _listing(wt, in_root)

    src = make_light_source(base)  # the engine source: this repository's engine files, one fixture test
    _git(src, "init", "-q")
    _git(src, "add", "-A")
    _git(src, "commit", "-q", "-m", "engine source")

    def owner(*args):
        return subprocess.run([sys.executable, str(REPO / "mkway.py"), *args], capture_output=True, text=True,
                              cwd=str(root), env=_env(base, root, session=False), timeout=900)

    proc = owner("install", "--from", str(src), "--ref", "HEAD", "--root", str(root))
    result.outputs["install"] = proc.stdout + proc.stderr
    if proc.returncode != 0:
        result.problem("install", f"exit {proc.returncode}: {proc.stdout}{proc.stderr}")
        result.check = (None, "install failed")
        result.before_main, result.before_wt = before_main, before_wt
        result.after_main, result.after_wt = _listing(main, lambda rel: False), _listing(wt, in_root)
        result.seconds = time.perf_counter() - started
        return result
    launcher = [sys.executable, str(root / "mkway" / "engine" / "mkway.py")]
    proc = subprocess.run([*launcher, "check"], capture_output=True, text=True, cwd=str(root),
                          env=_env(base, root, session=False), timeout=900)  # from the task folder: no --root, no variable
    result.check = (proc.returncode, proc.stdout + proc.stderr)
    proc = owner("install", "--from", str(src), "--ref", "HEAD", "--root", str(root))  # MW-032: over a checked install
    result.outputs["reinstall"] = proc.stdout + proc.stderr
    result.reinstall = (proc.returncode, proc.stdout + proc.stderr)
    if proc.returncode != 0 or "Traceback" in proc.stdout + proc.stderr:
        result.problem("reinstall", f"exit {proc.returncode}: {proc.stdout}{proc.stderr}")
    # the owner's own edit of the profile: leads open the cards they ordered
    profile_path = root / "mkway" / "profile.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    profile["cards"] = {"approver": "orderer"}
    profile_path.write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")

    s = Sessions(base, root, result)
    for session in (LEAD, BUILDER):
        outs = s.fire("start", "SessionStart", session)
        result.outputs[f"start-{session}"] = "\n".join(outs or [])
    steps = [
        ("lead register", lambda: s.bash("lead register", LEAD, "python mkway/engine/mkway.py lead register")),
        ("card new", lambda: s.bash("card new", LEAD, f"python mkway/engine/mkway.py card new {CARD_TITLE}")),
    ]
    for _name, run in steps:
        if run() is None:
            break
    else:
        card_dir = next((root / "mkway" / "cards").glob(f"{CARD_ID}-*"), None)
        if card_dir is None:
            result.problem("card new", f"no folder {CARD_ID}-* under mkway/cards")
        else:
            rel_dir = card_dir.relative_to(root).as_posix()
            template = (card_dir / "CARD.md").read_text(encoding="utf-8")
            flow = [
                lambda: s.write("write CARD.md", LEAD, f"{rel_dir}/CARD.md", _card_text(template)),
                lambda: s.write("write ORDER.md", LEAD, f"{rel_dir}/ORDER.md",
                                "Order: write the feature and its test inside the card's Paths.\n"),
                lambda: s.bash("card open", LEAD, f"python mkway/engine/mkway.py card open {CARD_ID}"),
                lambda: s.bash("card take", BUILDER, f"python mkway/engine/mkway.py card take {CARD_ID}"),
                lambda: s.write("write test", BUILDER, "tests/test_live.py",
                                "def test_live_feature():\n    assert 1 + 1 == 2\n"),
                lambda: s.write("write feature", BUILDER, "src/feature.py", "VALUE = 1\n"),
                lambda: s.edit("edit feature", BUILDER, "src/feature.py", "VALUE = 1", "VALUE = 2"),
                lambda: s.bash("git add", BUILDER, "git add src/feature.py tests/test_live.py"),
                lambda: s.bash("git commit", BUILDER,
                               f'git commit -m "{CARD_ID} add the feature and its test" -- src/feature.py tests/test_live.py'),
                # MW-034: a file a `python <script>` call wrote inside the Paths commits (no write record exists)
                lambda: s.write("write script", BUILDER, "src/make.py",
                                "from pathlib import Path\n"
                                "(Path(__file__).parent / 'generated.py').write_text('X = 1\\n', encoding='utf-8')\n"),
                lambda: s.bash("run script", BUILDER, "python src/make.py"),
                lambda: s.bash("git add script", BUILDER, "git add src/make.py src/generated.py"),
                lambda: s.bash("git commit script", BUILDER,
                               f'git commit -m "{CARD_ID} add the generated file" -- src/make.py src/generated.py'),
                lambda: s.bash("card close", LEAD, f"python mkway/engine/mkway.py card close {CARD_ID}"),
            ]
            for run in flow:
                if run() is None:
                    break
    result.after_main, result.after_wt = _listing(main, lambda rel: False), _listing(wt, in_root)
    result.before_main, result.before_wt = before_main, before_wt
    # MW-027: what git offers for commit in the linked worktree, then the install committed and a second worktree
    result.builder_commit = _git(wt, "log", "--format=%s", "-1").strip()
    result.status = _git(root, "status", "--porcelain", "-uall", "--", ".")
    second = result.second = Live()
    second.root = None
    try:
        _git(root, "add", "-A", ".")
        _git(root, "commit", "-q", "-m", "mkway install")
        wt2 = base / "wt2"
        _git(main, "worktree", "add", "-q", str(wt2), "-b", "second", "work")
        second.root = wt2 / "task" / TASK
        outs = Sessions(base, second.root, second).fire("start second", "SessionStart", "session-second")
        result.outputs["start-second"] = "\n".join(outs or [])
    except (subprocess.CalledProcessError, OSError, KeyError, ValueError) as exc:
        second.problem("second worktree", f"{type(exc).__name__}: {getattr(exc, 'stderr', '') or exc}")
    # MW-035: reinstall with --commit over an install whose .gitignore holds `engine/`, a foreign file staged
    try:
        ignore = root / "mkway" / ".gitignore"
        ignore.write_text("engine/\nlocks/\nstate/\n", encoding="utf-8")  # the shape an earlier install wrote
        (root / "foreign.txt").write_text("f\n", encoding="utf-8")
        _git(root, "add", "foreign.txt")
        proc = owner("install", "--from", str(src), "--ref", "HEAD", "--root", str(root), "--commit")
        result.reinstall_commit = (proc.returncode, proc.stdout + proc.stderr,
                                   _git(root, "show", "--name-only", "--format=", "HEAD").split(),
                                   _git(root, "diff", "--cached", "--name-only").split(),
                                   _git(root, "ls-files", "mkway/engine/mkway.py").split(),
                                   ignore.read_text(encoding="utf-8").splitlines())
    except (subprocess.CalledProcessError, OSError) as exc:
        result.problem("reinstall commit", f"{type(exc).__name__}: {getattr(exc, 'stderr', '') or exc}")
    result.seconds = time.perf_counter() - started
    return result


def test_the_check_run_from_the_task_folder_is_clean(live):
    """E1: `mkway check` run from the task folder, no `--root`, no `CLAUDE_PROJECT_DIR`: exit 0, tests green, and no line
    that reads as a warning, a difference, a missing lock or an invalid profile."""
    assert "install" not in dict(live.problems), live.message()
    code, text = live.check
    lines = text.splitlines()
    assert code == 0, text
    assert any(re.fullmatch(r"tests: \d+ passed", line) for line in lines), text
    assert any(line.startswith("copy hash: matches the lock") for line in lines), text
    dirty = [line for line in lines if re.search(r"warning|differs|invalid|not green|no lock|not compared|error|failed",
                                                  line, re.I)]
    assert not dirty, "unclean lines: " + " | ".join(dirty)


def test_a_reinstall_over_a_checked_install_succeeds(live):
    """MW-032 E7: `mkway install` run again over an install whose `mkway check` has already run: exit 0, no traceback,
    the new copy matches the lock, no leftover engine folder beside the copy."""
    assert "install" not in dict(live.problems), live.message()
    code, text = live.reinstall
    assert code == 0 and "Traceback" not in text, text
    bundle = live.root / "mkway"
    lock = json.loads((bundle / "mkway.lock").read_text(encoding="utf-8"))
    import install
    assert lock["hash"] == install.copy_hash(bundle / "engine")
    assert sorted(p.name for p in bundle.iterdir() if p.name.startswith("engine")) == ["engine"]
    assert "reinstall" not in dict(live.problems), live.message()


def test_a_reinstall_commit_takes_only_the_install_paths(live):
    """MW-035 E6: `install --commit` over an install whose bundle `.gitignore` holds `engine/`, while a foreign file is
    staged: the line is gone, the engine copy is tracked, the foreign file is still staged and not in the commit."""
    assert "reinstall commit" not in dict(live.problems), live.message()
    assert live.reinstall_commit is not None, live.message()
    code, text, taken, staged, tracked, ignore = live.reinstall_commit
    assert code == 0, text
    assert "engine/" not in ignore and "locks/" in ignore, ignore
    assert tracked == ["mkway/engine/mkway.py"], tracked  # `ls-files` answers relative to the task folder
    assert f"task/{TASK}/mkway/.gitignore" in taken, taken
    assert not [p for p in taken if p.endswith("foreign.txt")], taken
    assert staged == [f"task/{TASK}/foreign.txt"], staged


def test_the_lead_and_builder_path_has_no_refusal(live):
    """E2: lead register, card new, Write of CARD.md and ORDER.md, card open (approver orderer); builder card take, an
    Edit inside the Paths, a commit through the commit gates; the lead closes the card. Any refusal fails the path."""
    assert not live.problems, live.message()
    rows = (live.root / "mkway" / "cards" / "REGISTER.md").read_text(encoding="utf-8")
    assert re.search(rf"^\| {CARD_ID} \|.*\| closed \|", rows, re.M), rows
    assert live.builder_commit.startswith(CARD_ID)  # the builder's commit, taken before the install commit (MW-027)


def test_nothing_else_is_written_outside_the_task_root(live):
    """E3: the fixture repository's main worktree and the linked worktree's top (outside the task folder) hold the same
    files after the flow as before it, except the shared state of the linked worktree (E4, MW-026)."""
    shared = lambda rel: rel == SHARED_STATE or rel.startswith(SHARED_STATE + "/")  # noqa: E731
    changed = {where: sorted(rel for rel in set(after) | set(before)
                             if after.get(rel) != before.get(rel) and not (where == "main" and shared(rel)))
               for where, after, before in (("main", live.after_main, live.before_main),
                                            ("worktree top", live.after_wt, live.before_wt))}
    assert changed == {"main": [], "worktree top": []}, f"written outside the task root: {changed}"


def test_the_shared_state_stays_inside_the_task_root(live):
    """E4: no file of the main worktree changes at all: the leads registry and the inboxes live inside the task root."""
    changed = sorted(rel for rel in set(live.after_main) | set(live.before_main)
                     if live.after_main.get(rel) != live.before_main.get(rel))
    assert not changed, f"written to the main worktree: {changed}"


def test_the_profile_says_git_and_the_bundle_ignore_file_exists(live):
    """E5: the starter profile reads vcs git; `mkway/.gitignore` exists and ignores the bundle's machine folders."""
    profile = json.loads((live.root / "mkway" / "profile.json").read_text(encoding="utf-8"))
    assert profile["vcs"] == "git"
    ignore = live.root / "mkway" / ".gitignore"
    assert ignore.is_file(), "the install wrote no mkway/.gitignore"
    lines = ignore.read_text(encoding="utf-8").splitlines()
    for line in ("state/", "locks/", "__pycache__/"):  # MW-027: run-time folders ignored
        assert line in lines, lines
    assert "engine/" not in lines  # MW-027: the engine copy is tracked, so a fresh worktree needs no install


def test_the_first_status_offers_no_runtime_file_and_the_settings_hold_the_hooks(live):
    """E9 (MW-027): after install and the whole flow, `git status --porcelain` in the linked worktree lists no run-time
    file under `mkway/state`, `mkway/locks`, no bytecode or check temp folder; the committed `.claude/settings.json`
    holds the hook entries and install wrote no `settings.local.json`."""
    assert "install" not in dict(live.problems), live.message()
    for bad in ("/state/", "/locks/", "__pycache__", ".pyc", ".pytest_tmp", ".pytest_cache", "settings.local.json"):
        assert bad not in live.status, f"{bad} offered for commit:\n{live.status}"
    assert f"task/{TASK}/.claude/settings.json" in live.status  # offered, not ignored
    settings = json.loads((live.root / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert {"SessionStart", "PreToolUse", "PostToolUse"} <= set(settings["hooks"]), list(settings["hooks"])
    assert not (live.root / ".claude" / "settings.local.json").exists()


def test_a_second_worktree_of_the_install_commit_starts_with_no_install(live):
    """E10 (MW-027): the install committed in the fixture, a second linked worktree added from that commit: its start
    hook, run from the committed `settings.json` with no install, exits 0, prints the start block, and the block shows
    no drift and no logged error."""
    second = live.second
    assert second is not None, live.message()
    assert not second.problems, second.message()
    assert (second.root / "mkway" / "engine" / "mkway.py").is_file(), "the engine copy is not in the commit"
    block = live.outputs["start-second"]
    assert "mkway v" in block, block
    text = json.dumps(block)
    assert "drift-machine" not in text and "mkway dispatcher-error:" not in text and "profile-invalid" not in text, block


def test_the_start_block_has_no_error_line(live):
    """E6: the start block of a session in the installed task root names no profile error, no dispatcher error and no
    logged gate error."""
    for session in (LEAD, BUILDER):
        block = live.outputs[f"start-{session}"]
        assert block.strip(), f"no start block for {session}: {live.message()}"
        text = json.dumps(block)
        assert "profile-invalid" not in text and "mkway dispatcher-error:" not in text, block
        for line in re.findall(r"errors logged: gate-error (\d+), dispatcher-error (\d+)", block):
            assert line == ("0", "0"), block


def test_the_run_stays_inside_the_time_limit(live):
    """E7: the whole flow, fixture to close, takes about a minute; past the limit it fails."""
    assert live.seconds < TIME_LIMIT_SECONDS, f"{live.seconds:.0f} s (limit {TIME_LIMIT_SECONDS} s)"


def test_register_changelog_and_card_name_the_card():
    """E8 (changed by MW-027): the register row, the changelog line, under the release that names the card, saying this
    test is the release gate, the card."""
    register = (REPO / "cards" / "REGISTER.md").read_text(encoding="utf-8")
    assert re.search(r"^\| MW-030 \|.*`cards/MW-030-[a-z0-9-]+`", register, re.M)
    text = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    version = (REPO / "VERSION").read_text(encoding="utf-8").strip()
    assert f"\n## {version}\n" in text
    # MW-027: a newer release may sit on top; the line is under the release that names the card
    section = next(s for s in text.split("\n## ")[1:] if "MW-030" in s)
    line = next(x for x in section.splitlines() if "MW-030" in x)
    assert "release gate" in line
    assert list((REPO / "cards").glob("MW-030-*/CARD.md"))
