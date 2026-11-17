"""Card MW-039: a shared driver that runs the REAL hook command lines of an installed engine, the way Claude Code does.

Not a test module. What it does, and why each part is not simplified:
- `install_project` installs the engine into a scratch git repository (the task folder lies below the git top, as in a
  real task) and commits the install; tests share one install per module.
- `Project.fire` reads the generated `.claude/settings.json`, picks the hook entries of an event whose matcher fits the
  tool, and runs each command line THROUGH THE SHELL (Git Bash on Windows, as Claude Code does), with
  `CLAUDE_PROJECT_DIR` in the process environment (never substituted by the test), the task folder as the working
  folder, the JSON of a real hook payload on stdin (`session_id`, `transcript_path`, `cwd`, `hook_event_name`,
  `tool_name`, `tool_input`; file tools carry ABSOLUTE paths).
- `decision` reads the hook's JSON, never only the exit code: a PreToolUse refusal is exit 0 plus
  `hookSpecificOutput.permissionDecision: "deny"`; a Stop (or PostToolUse, UserPromptSubmit) refusal is exit 0 plus a
  top-level `decision: "block"`. The reason id is read from the `[mkway <gate> <reason id>]` tag of the reason text.

Synthetic names and ids only.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple, Optional

from _engine import REPO

GIT_ID = ["-c", "user.name=hook-driver", "-c", "user.email=hook-driver"]
TAG = re.compile(r"\[mkway (\S+) (\S+)\]")
SESSION_ENV = {"CLAUDECODE": "1"}  # what a session's shell and its hooks carry; the owner's terminal has none
_DROP = ("CLAUDE_PROJECT_DIR", "ENGINE_TERMS_FILE", "CLAUDECODE", "MKWAY_SESSION_ID")  # MW-110: the launcher's variable


class Decision(NamedTuple):
    kind: str                 # allow | deny | block | error
    reason_id: Optional[str]  # the id of the `[mkway <gate> <reason id>]` tag, or None
    gate: Optional[str]       # the manifest entry name in the tag
    text: str = ""

    def __str__(self):
        return self.kind if self.kind == "allow" else f"{self.kind}:{self.reason_id}"


@dataclass
class HookRun:
    """One real hook process: the command line as generated, what it returned."""
    group: str
    command: str
    exit_code: int
    stdout: str
    stderr: str
    seconds: float
    json: Optional[dict] = None

    def __post_init__(self):
        try:
            data = json.loads(self.stdout) if self.stdout.strip() else None
        except ValueError:
            data = None
        self.json = data if isinstance(data, dict) else None


@dataclass
class Fired:
    """Every hook process one event of one tool call started."""
    event: str
    runs: list = field(default_factory=list)

    @property
    def exit_code(self) -> int:
        return max((r.exit_code for r in self.runs), default=0)

    @property
    def stdout(self) -> str:
        return "\n".join(r.stdout for r in self.runs)

    @property
    def stderr(self) -> str:
        return "\n".join(r.stderr for r in self.runs)


def _decide_one(run: HookRun) -> Decision:
    if run.exit_code != 0:  # exit 2 is a blocking error of the dispatcher itself (R13c); anything else is a crash
        return Decision("error", None, None, f"exit {run.exit_code}: {run.stderr or run.stdout}")
    data = run.json or {}
    if "mkway dispatcher-error:" in run.stdout + run.stderr:
        return Decision("error", None, None, run.stdout + run.stderr)
    specific = data.get("hookSpecificOutput") if isinstance(data.get("hookSpecificOutput"), dict) else {}
    if specific.get("permissionDecision") in ("deny", "ask"):  # PreToolUse
        text = str(specific.get("permissionDecisionReason") or "")
        found = TAG.search(text)
        return Decision("deny", found.group(2) if found else None, found.group(1) if found else None, text)
    if data.get("decision") == "block":  # Stop, PostToolUse, UserPromptSubmit
        text = str(data.get("reason") or "")
        found = TAG.search(text)
        return Decision("block", found.group(2) if found else None, found.group(1) if found else None, text)
    return Decision("allow", None, None)


def decision(result) -> Decision:
    """allow, deny (PreToolUse) or block (Stop and the other block events), with the reason id; read from the hook's
    JSON, never only the exit code. `result` is a `Fired` or one `HookRun`. A dispatcher error is `error`; the first
    error or refusal of the processes wins."""
    runs = result.runs if isinstance(result, Fired) else [result]
    decisions = [_decide_one(r) for r in runs]
    for kind in ("error", "deny", "block"):
        for d in decisions:
            if d.kind == kind:
                return d
    return Decision("allow", None, None)


def find_bash() -> str:
    """The shell Claude Code runs a hook command in: Git Bash on Windows, `bash` elsewhere."""
    given = os.environ.get("CLAUDE_CODE_GIT_BASH_PATH")
    if given and Path(given).is_file():
        return given
    if os.name != "nt":
        found = shutil.which("bash") or shutil.which("sh")
        if found:
            return found
        raise RuntimeError("no bash on this machine: the hook commands cannot be run the way Claude Code runs them")
    git = shutil.which("git")
    if git:
        here = Path(git).resolve()
        for top in (here.parents[1], here.parents[2] if len(here.parents) > 2 else here.parents[1]):
            for candidate in (top / "bin" / "bash.exe", top / "usr" / "bin" / "bash.exe"):
                if candidate.is_file():
                    return str(candidate)
    raise RuntimeError("Git Bash not found (set CLAUDE_CODE_GIT_BASH_PATH): the hook commands cannot be run the way "
                       "Claude Code runs them")


def _rmtree(path: Path) -> None:
    import stat

    def writable(func, target, _info):
        os.chmod(target, stat.S_IWRITE)
        func(target)
    shutil.rmtree(path, onerror=writable)


class Project:
    """An installed task folder and everything a test needs to drive its hooks as a session."""

    def __init__(self, base: Path, top: Path, root: Path):
        self.base, self.top, self.root = Path(base), Path(top), Path(root)
        self.bash = find_bash()
        self.transcripts = self.base / "transcripts"
        self.transcripts.mkdir(exist_ok=True)
        self.entries = self._read_entries()

    # ---- environment ---------------------------------------------------------------------------------------------
    def env(self, *, session: bool) -> dict:
        env = {k: v for k, v in os.environ.items() if k not in _DROP}
        home = self.base / "home"
        home.mkdir(exist_ok=True)
        env.update(HOME=str(home), USERPROFILE=str(home), GIT_CEILING_DIRECTORIES=str(self.base.resolve()),
                   GIT_AUTHOR_NAME="hook-driver", GIT_AUTHOR_EMAIL="hook-driver", GIT_COMMITTER_NAME="hook-driver",
                   GIT_COMMITTER_EMAIL="hook-driver", PYTHONDONTWRITEBYTECODE="1")
        if session:
            env.update(SESSION_ENV)
            env["CLAUDE_PROJECT_DIR"] = str(self.root)
        return env

    def _read_entries(self) -> list:
        settings = json.loads((self.root / ".claude" / "settings.json").read_text(encoding="utf-8"))
        return [(event, group.get("matcher"), handler["command"], handler.get("timeout", 60))
                for event, groups in settings["hooks"].items() for group in groups for handler in group["hooks"]
                if not handler.get("asyncRewake")]  # MW-078: Claude Code runs it in the background; `fire` never waits for it

    def path(self, rel: str) -> str:
        """The absolute Windows (or POSIX) path a file tool carries."""
        return str(self.root / rel)

    # ---- git and the owner's terminal --------------------------------------------------------------------------------
    def git(self, *args, check=True, cwd=None):
        proc = subprocess.run(["git", *GIT_ID, *args], cwd=str(cwd or self.root), capture_output=True, text=True,
                              env=self.env(session=False), timeout=120)
        if check and proc.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)}: {proc.stdout}{proc.stderr}")
        return proc.stdout

    def owner(self, *args, check=True):
        """`mkway <args>` in the owner's own terminal: no CLAUDECODE, no hook."""
        proc = subprocess.run([sys.executable, str(self.root / "mkway" / "engine" / "mkway.py"), *args],
                              cwd=str(self.root), capture_output=True, text=True, env=self.env(session=False),
                              timeout=300)
        if check and proc.returncode != 0:
            raise RuntimeError(f"mkway {' '.join(args)}: {proc.stdout}{proc.stderr}")
        return proc

    def write(self, rel: str, text: str = "", *, binary: bytes = None) -> Path:
        """A file written directly (the owner's, or the fixture's own): no hook."""
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if binary is not None:
            path.write_bytes(binary)
        else:
            path.write_text(text, encoding="utf-8", newline="\n")
        return path

    def profile(self, **changes) -> dict:
        """The profile as the owner would edit it: merge `changes` (dotted keys, `None` deletes); returns the old
        profile so a test can put it back with `restore_profile`."""
        path = self.root / "mkway" / "profile.json"
        old = json.loads(path.read_text(encoding="utf-8"))
        new = json.loads(json.dumps(old))
        for dotted, value in changes.items():
            node = new
            *parents, last = dotted.split(".")
            for part in parents:
                node = node.setdefault(part, {})
            if value is None:
                node.pop(last, None)
            else:
                node[last] = value
        path.write_text(json.dumps(new, indent=2) + "\n", encoding="utf-8")
        return old

    def restore_profile(self, old: dict) -> None:
        (self.root / "mkway" / "profile.json").write_text(json.dumps(old, indent=2) + "\n", encoding="utf-8")

    # ---- the hooks ---------------------------------------------------------------------------------------------------
    def transcript(self, session: str, *, user_at: str = "2026-01-01T00:00:00Z", assistant: str = "ok") -> str:
        """A transcript file as Claude Code keeps it: one real user message with a time, one assistant message."""
        path = self.transcripts / f"{session}.jsonl"
        rows = [{"type": "user", "timestamp": user_at, "message": {"role": "user", "content": "do the work"}},
                {"type": "assistant", "timestamp": user_at,
                 "message": {"role": "assistant", "content": [{"type": "text", "text": assistant}]}}]
        path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        return str(path)

    def payload(self, event, session, tool=None, tool_input=None, **extra) -> dict:
        data = {"session_id": session, "transcript_path": extra.pop("transcript_path", None) or self.transcript(session),
                "cwd": str(self.root), "hook_event_name": event}
        if tool is not None:
            data["tool_name"] = tool
            data["tool_input"] = tool_input
        data.update(extra)
        return data

    def run_command(self, command: str, payload: dict, timeout) -> HookRun:
        """One hook command line, as generated: through the shell, `CLAUDE_PROJECT_DIR` in the environment, JSON on stdin."""
        started = time.monotonic()
        proc = subprocess.run([self.bash, "-c", command], input=json.dumps(payload), capture_output=True, text=True,
                              encoding="utf-8", cwd=str(self.root), env=self.env(session=True), timeout=timeout)
        group = command.split("--group ")[1].split()[0] if "--group " in command else "?"
        return HookRun(group, command, proc.returncode, proc.stdout, proc.stderr, time.monotonic() - started)

    def fire(self, event, session, tool=None, tool_input=None, **extra) -> Fired:
        """Every hook entry of `event` whose matcher fits `tool`: one real process each."""
        data = self.payload(event, session, tool, tool_input, **extra)
        fired = Fired(event)
        for entry_event, matcher, command, timeout in self.entries:
            if entry_event != event:
                continue
            if tool is not None and matcher and not re.fullmatch(matcher, tool):
                continue
            fired.runs.append(self.run_command(command, data, timeout))
        return fired

    def session_shell(self, session, command, *, expect_ok=True, shell_project_dir=None):
        """A session's Bash call: PreToolUse hooks (must allow), the command in a shell with `CLAUDECODE` and
        `CLAUDE_PROJECT_DIR`, PostToolUse hooks. Returns the command's process. MW-054: `shell_project_dir` is the
        `CLAUDE_PROJECT_DIR` of the shell only (the hooks keep the real one): a session started from another root
        inherits the launcher's value in its Bash tool, while Claude Code sets the right one for the hooks."""
        pre = self.fire("PreToolUse", session, "Bash", {"command": command})
        got = decision(pre)
        if got.kind != "allow":
            raise RuntimeError(f"`{command}` was refused: {got}: {got.text}")
        shell_env = self.env(session=True)
        if shell_project_dir is not None:
            shell_env["CLAUDE_PROJECT_DIR"] = str(shell_project_dir)
        proc = subprocess.run([self.bash, "-c", command], capture_output=True, text=True, encoding="utf-8",
                              cwd=str(self.root), env=shell_env, timeout=300)
        if expect_ok and proc.returncode != 0:
            raise RuntimeError(f"`{command}` exit {proc.returncode}: {proc.stdout}{proc.stderr}")
        post = self.fire("PostToolUse", session, "Bash", {"command": command},
                         tool_response={"stdout": proc.stdout, "stderr": proc.stderr, "exit_code": proc.returncode})
        if decision(post).kind == "error":
            raise RuntimeError(f"PostToolUse after `{command}`: {decision(post).text}")
        return proc

    def session_write(self, session, rel, content):
        """A session's Write: PreToolUse hooks (must allow), the file, PostToolUse hooks."""
        tool_input = {"file_path": self.path(rel), "content": content}
        got = decision(self.fire("PreToolUse", session, "Write", tool_input))
        if got.kind != "allow":
            raise RuntimeError(f"Write {rel} was refused: {got}: {got.text}")
        self.write(rel, content)
        self.fire("PostToolUse", session, "Write", tool_input, tool_response={"filePath": self.path(rel)})


def make_source(base: Path) -> Path:
    """An engine source for install: this repository's engine files, `tests/` cut to the one fixture test (as the live
    install test does); a git repository with one commit."""
    from test_install import make_light_source
    src = make_light_source(base)
    for args in (("init", "-q"), ("add", "-A"), ("commit", "-q", "-m", "engine source")):
        subprocess.run(["git", *GIT_ID, *args], cwd=str(src), capture_output=True, text=True, check=True)
    return src


def install_project(base: Path, *, task: str = "task/T1", gates_on=("lead", "message", "outbox_check.pre",
                                                                    "owner_ask", "search")) -> Project:
    """Install the engine into a scratch git repository (the task folder below the git top), commit the install, turn
    the form gates on (a first install starts them in watch mode, where a refusal is only logged), and return the
    project."""
    base = Path(base)
    top = base / "repo"
    root = top / task
    root.mkdir(parents=True)
    (top / "README.md").write_text("synthetic\n", encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k not in _DROP}
    env.update(HOME=str(base / "home"), USERPROFILE=str(base / "home"), GIT_CEILING_DIRECTORIES=str(base.resolve()))
    (base / "home").mkdir(exist_ok=True)
    for args in (("init", "-q"), ("add", "-A"), ("commit", "-q", "-m", "base")):
        subprocess.run(["git", *GIT_ID, *args], cwd=str(top), capture_output=True, text=True, check=True, env=env)
    src = make_source(base)
    proc = subprocess.run([sys.executable, str(REPO / "mkway.py"), "install", "--from", str(src), "--ref", "HEAD",
                           "--root", str(root)], capture_output=True, text=True, env=env, timeout=900)
    if proc.returncode != 0:
        raise RuntimeError(f"install failed: {proc.stdout}{proc.stderr}")
    project = Project(base, top, root)
    for gate in gates_on:
        project.owner("gate", "on", gate)
    project.git("add", "-A", ".")
    project.git("commit", "-q", "-m", "mkway install")
    return project
