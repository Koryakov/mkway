"""Shared helpers for the core tests (card MW-002). Not a test module. Synthetic values only."""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ENGINE = REPO / "engine"
FIXTURES = REPO / "fixtures" / "synthetic"
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))
if str(FIXTURES) not in sys.path:
    sys.path.insert(0, str(FIXTURES))


def make_profile(gates=None, **over):
    """A valid synthetic profile at bundle depth 1 (the default bundle root). Changed by MW-003 (D-8): no `items`."""
    profile = {
        "vcs": "none",
        "bundle": {"root": "mkway"},
        "gates": gates or {},
        "state": {"dir": "mkway/state"},
        "python": {"command": "python"},
    }
    profile.update(over)
    return profile


def write_profile(root: Path, profile) -> Path:
    path = root / "mkway" / "profile.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    return path


def entry(name, function, *, event="PreToolUse", group="edit", matcher=None, reason_ids=("fixture-refuse",),
          on_failure="block", timeout=10, default_on=True):
    """A manifest entry for a synthetic gate; reason_ids=None leaves the key out."""
    e = {"name": name, "gate": name, "group": group, "function": function, "event": event, "matcher": matcher,
         "timeout": timeout, "onFailure": on_failure, "mode": None, "status": "planned", "default_on": default_on}
    if reason_ids is not None:
        e["reason_ids"] = list(reason_ids)
    return e


def jsonl(path: Path):
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


SESSION_ENV = {"CLAUDECODE": "1"}  # what a session's shell carries (card MW-003, C44); the owner's terminal has none


def cli(root: Path, *args, session=False, env=None):
    """Run `mkway <args> --root <root>` in process (card MW-003): (exit code, stdout, stderr). `session=True` runs
    it as a session's shell does; else as the owner's own terminal."""
    import contextlib
    import io
    import mkway as engine_cli
    base = {k: v for k, v in (env or {}).items()}
    if session:
        base.update(SESSION_ENV)
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = engine_cli.main([*args, "--root", str(root)], env=base)
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


def gate_call(function, root: Path, *, tool="Edit", tool_input=None, session="s1", event="PreToolUse", gate="g",
              profile=None, tool_response=None, budget=None, **payload):
    """Call one gate function with the context the dispatcher builds (card MW-003). `payload` passes hook-input
    fields such as `cwd` (batch 3, item 15) only when a test gives them."""
    import dispatch
    if profile is None:
        profile = json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))
    ctx = dispatch.make_context(profile=profile, root=root, session_id=session, event=event, gate=gate,
                                tool_name=tool, tool_input=tool_input, budget_seconds=budget,
                                once=lambda targets: True, tool_response=tool_response, env={}, **payload)
    return function(event, ctx)


def agent_file(base: Path, name: str, tools_line=None) -> Path:
    """`<base>/.claude/agents/<name>.md`, a synthetic agent definition (card MW-071); `tools_line` is the text after
    `tools:`, or None for a definition with no tools line."""
    path = base / ".claude" / "agents" / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    tools = "" if tools_line is None else f"tools: {tools_line}\n"
    path.write_text(f"---\nname: {name}\ndescription: synthetic\n{tools}---\nA synthetic agent.\n", encoding="utf-8")
    return path


def task_root(tmp_path: Path, *, vcs="none", gates=None, name="task", agent_tools="Read, Grep", **over) -> Path:
    """A synthetic task root with a valid profile (prefix CARD) and the bundle folders (card MW-003). Each type the profile
    names in `outbox.checkers` gets an agent definition in the root's `.claude/agents` listing `agent_tools` (card
    MW-071, decision: R180); `agent_tools=None` writes none."""
    root = tmp_path / name
    for sub in ("cards", "ledger", "locks", "state"):
        (root / "mkway" / sub).mkdir(parents=True, exist_ok=True)
    profile = make_profile(gates, vcs=vcs, ids={"card_prefix": "CARD"})
    profile.update(over)
    write_profile(root, profile)
    if agent_tools is not None:
        for checker in (profile.get("outbox") or {}).get("checkers") or []:
            agent_file(root, checker, agent_tools)
    return root


def fake_program(folder: Path, name: str, *, prints=None, forward_after_first=False, sleeps=None,
                 touches=None, spawns=None) -> Path:
    """A synthetic program on disk (card MW-002, fix check 2 L4). `prints`: it prints that text and exits 0.
    `forward_after_first`: it drops its first argument (the launcher's `-3`) and runs this Python with the rest,
    like the Windows `py` launcher. `sleeps`: it waits that many seconds, printing nothing (fix check 3 L5).
    `touches`: it creates that file, so a test can tell whether it ran (L5). `spawns`: it starts this Python on that
    script in the background and exits at once, leaving an orphan that holds its output (fix check 4 F5). Returns
    the program's path (`<name>.cmd` on Windows)."""
    import os
    import stat
    folder.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        path = folder / f"{name}.cmd"
        body = (f'@"{sys.executable}" %2 %3 %4 %5 %6 %7 %8 %9\r\n' if forward_after_first  # term-scan: allow cmd no-echo marker, not an NDA term
                else f"@echo {prints}\r\n")
        if sleeps is not None:
            body = f"@ping -n {int(sleeps) + 1} 127.0.0.1 >nul\r\n"
        if touches is not None:
            body = f"@echo x> {touches}\r\n"
        if spawns is not None:
            body = f'@start "" /b "{sys.executable}" "{spawns}"\r\n'
        path.write_text(body, encoding="utf-8")
    else:
        path = folder / name
        body = (f'#!/bin/sh\nshift\nexec "{sys.executable}" "$@"\n' if forward_after_first
                else f"#!/bin/sh\necho '{prints}'\n")
        if sleeps is not None:
            body = f"#!/bin/sh\nsleep {int(sleeps)}\n"
        if touches is not None:
            body = f"#!/bin/sh\necho x > '{touches}'\n"
        if spawns is not None:
            body = f'#!/bin/sh\n"{sys.executable}" "{spawns}" &\n'
        path.write_text(body, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path
