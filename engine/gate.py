"""The gate interface (card MW-002, deliverable 1).

A gate is a function `(event, ctx) -> Verdict`. It decides; the dispatcher does everything else (hook I/O, logs,
timing, onFailure). A gate does no hook I/O (no print, no stdin) and never exits the process.

A Verdict is allow, refuse, warn or log. A refuse, a warn or a log carries a `reason_id` (one of the ids its manifest
entry declares in `reason_ids`) and a message. A log blocks nothing and shows nothing at that call: the dispatcher
writes a `log` row (card MW-003, list item 5, R43).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Optional, Union

ALLOW = "allow"
REFUSE = "refuse"
WARN = "warn"
LOG = "log"
KINDS = (ALLOW, REFUSE, WARN, LOG)


@dataclass(frozen=True)
class Verdict:
    kind: str
    reason_id: Optional[str] = None
    message: str = ""

    def __post_init__(self):
        if self.kind not in KINDS:
            raise ValueError(f"unknown verdict kind: {self.kind!r}")
        if self.kind != ALLOW and not (self.reason_id and self.message):
            raise ValueError("a refuse or a warn needs a reason id and a message")


# MW-055: one short clause that a refusal adds so a session that cannot write a file still finds how to tell its lead
REPORT_ROUTE = ('To report with no file: `mkway send --to <id-prefix> --kind result --text "<message>"`, then send the '
                "ping line it prints.")


def allow() -> Verdict:
    return Verdict(ALLOW)


def refuse(reason_id: str, message: str) -> Verdict:
    return Verdict(REFUSE, reason_id, message)


def warn(reason_id: str, message: str) -> Verdict:
    return Verdict(WARN, reason_id, message)


def log(reason_id: str, message: str) -> Verdict:
    return Verdict(LOG, reason_id, message)


@dataclass(frozen=True)
class Context:
    """What a gate may read. `once(targets)` is true only the first time in this session for this gate and this
    set of targets (a string or an iterable of strings). `budget_seconds` is `gates.<name>.budget_seconds` from the
    profile, or None.

    The shared helpers (card MW-003, deliverable 1), bound to this root and tool by `dispatch.make_context`:
    `norm(path, cwd=None)` the repo-relative form or None; `commit_cmd(cmd)` the commits of a shell command;
    `shell_writes(cmd)` the paths it may write; `mkway_calls(cmd)` its engine command calls; `records` this
    session's records (deliverable 2). `tool_response` is the PostToolUse response."""
    profile: dict
    root: Path
    session_id: str
    event: str
    gate: str
    tool_name: Optional[str]
    tool_input: Any
    budget_seconds: Optional[float]
    once: Callable[[Union[str, Iterable[str]]], bool]
    tool_response: Any = None
    profile_file: Optional[Path] = None
    norm: Optional[Callable] = None
    commit_cmd: Optional[Callable] = None
    shell_writes: Optional[Callable] = None
    mkway_calls: Optional[Callable] = None
    records: Any = None
    env: Any = None
    cwd: Optional[str] = None  # the hook input's `cwd` (batch 3, item 15); writes are read from it
    hook_input: Any = None  # the whole hook input as sent (MW-007): a Stop gate reads `last_assistant_message`,
    # `transcript_path` and `stop_hook_active` from it
    payload: Any = None  # the whole hook input as sent (MW-004: the SubagentStart and SubagentStop fields)
