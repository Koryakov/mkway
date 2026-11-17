"""Shared helper of the MW-110 tests (the send tool and the session id). Not a test module. Synthetic roots and ids only."""
import json

import _engine  # noqa: F401  (puts the engine folder on the import path)
import dispatch

NAME = "MKWAY_SESSION_ID"


def hook_shell(root, command, session, env=None, tool="Bash"):
    """One shell call through the REAL dispatcher: every entry of the `shell` group (the lock gate, the session-id gate and
    the others) in the order of the manifest, with the hook's environment `env`. Returns what the hook printed."""
    payload = {"session_id": session, "hook_event_name": "PreToolUse", "tool_name": tool,
               "tool_input": {"command": command}, "cwd": str(root)}
    return dispatch.run("PreToolUse", "shell", json.dumps(payload),
                        env={"CLAUDE_PROJECT_DIR": str(root), **(env or {})})


def denied(out):
    """(reason tag, text) of the deny the hook printed, or None when it let the call go ahead."""
    if not out.stdout:
        return None
    body = json.loads(out.stdout)["hookSpecificOutput"]
    if body.get("permissionDecision") != "deny":
        return None
    return body["permissionDecisionReason"]


def context_of(out) -> str:
    """The warn text the hook added for the session, or an empty text."""
    if not out.stdout:
        return ""
    return json.loads(out.stdout)["hookSpecificOutput"].get("additionalContext", "")
