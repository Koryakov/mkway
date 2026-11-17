"""Shared helpers of the MW-116 tests (the reader's allowlist hook). Not a test module. Synthetic roots, sessions and agents
only. `make_world` is the small git task root of MW-080 (card CARD-001 names four nodes in two test files)."""
import json
import os
import subprocess
import sys
from pathlib import Path

from _engine import ENGINE
from _mw080 import CARD, CHECKER, FILE, OTHER_FILE, make_root, profile_of, state_of  # noqa: F401

SESSION = "s-spawn"
AGENT = "a-reader-1"
RUNS = "reader_runs.jsonl"
HOOK = ENGINE / "reader_hook.py"


def make_world(tmp_path, **kwargs):
    return make_root(tmp_path, **kwargs)


def card_text(root) -> str:
    import cardtool
    return cardtool.card_file(root, profile_of(root), CARD).read_text(encoding="utf-8")


def start(root, session=SESSION, card=CARD):
    """The reader-start step in process: the allow file of `session` for `card`."""
    import reader_allow
    return reader_allow.start(root, profile_of(root), state_of(root), session, card)


def allow_doc(root, session=SESSION):
    import reader_allow
    return reader_allow.read_allow(state_of(root), session)


def payload(root, tool, tool_input, *, session=SESSION, agent=AGENT, agent_type=CHECKER):
    """The hook input of one tool call inside the reader (common fields plus agent_id and agent_type, hooks.md)."""
    return {"session_id": session, "hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input,
            "cwd": str(root), "agent_id": agent, "agent_type": agent_type}


def run_hook(root, data, stdin_text=None, env_extra=None):
    """The hook script as a process, the way a frontmatter hook runs it: the payload on stdin, the project folder in the
    environment. Returns the completed process (exit code, stdout, stderr)."""
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(root), **(env_extra or {})}
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(data) if stdin_text is None else stdin_text,
                          capture_output=True, text=True, encoding="utf-8", cwd=str(root), env=env, timeout=30)


def runs_rows(root) -> list:
    path = state_of(root) / RUNS
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def calls(root) -> list:
    return [r for r in runs_rows(root) if r.get("kind") == "call"]


def reader(root, session, agent_id):
    """A checker end row (fresh, after the last commit of the test files) and NO record row of the hook: an unguarded run, as
    every reader run was before MW-116 (`_mw080.reader` now adds the record rows, see `guarded`)."""
    from _mw019 import add_agent
    from _mw080 import FRESH
    add_agent(root, session=session, agent_type=CHECKER, agent_id=agent_id, **FRESH)


def guarded(root, session, agent, card=CARD):
    """SETUP (decision MW116-D1): the record rows a guarded reader run leaves, in the form `mkway reader start` and the
    allowlist hook write them: one start row that lists the card's two inputs now, and one allowed Read row of `agent`. The
    allow file itself is not written, so no reader run stays open. Call it after the card and the test files are in place."""
    import hashlib
    import agents
    import reader_allow
    state = state_of(root)
    files, extract_sha = reader_allow.expected_inputs(root, profile_of(root), state, session, card)
    sha = hashlib.sha256(f"{session}|{card}|{agent}".encode("utf-8")).hexdigest()
    agents.append_reader(state, {"kind": "start", "session_id": session, "card": card, "files": files,
                                 "allow_sha256": sha, "extract_sha256": extract_sha, "time": "2026-11-10T08:00:00.000+00:00"})
    agents.append_reader(state, {"kind": "call", "session_id": session, "agent_id": agent, "agent_type": CHECKER,
                                 "tool": "Read", "path": files[0], "decision": "allow", "allow_sha256": sha,
                                 "time": "2026-11-10T08:00:01.000+00:00"})
