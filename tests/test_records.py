"""Session records and the `post` group (card MW-003, deliverable 2). Synthetic task roots only.

A session's card and search commands are recorded by the `post` group (PostToolUse), which carries the session id;
the command itself proves its success with a `mkway-ok <kind> <value> <nonce>` line and a nonce under state (the
docs give PostToolUse no exit status). The owner's terminal runs no hook, so there each command appends its own
`by: owner` row.
"""
import json
import re

from _engine import cli, jsonl, task_root
import dispatch

OK_LINE = re.compile(r"^mkway-ok (\S+) (.+) ([0-9a-f]{32})$", re.M)


def _records(root):
    return jsonl(root / "mkway" / "state" / "records.jsonl")


def _post(root, stdout, session="s1", tool="Bash", response=None):
    payload = {"session_id": session, "hook_event_name": "PostToolUse", "tool_name": tool,
               "tool_input": {"command": "python mkway/engine/mkway.py card new x"},
               "tool_response": response if response is not None else {"stdout": stdout, "stderr": "",
                                                                        "interrupted": False}}
    return dispatch.run("PostToolUse", "post", json.dumps(payload), env={"CLAUDE_PROJECT_DIR": str(root)})


def test_owner_terminal_appends_its_own_row(tmp_path):
    """Checks: an owner command appends one `by: owner` row with no session id (E6)."""
    root = task_root(tmp_path)
    # run from the owner's terminal (no hook, no session marker)
    code, out, _ = cli(root, "card", "new", "First")
    assert code == 0
    # prints no mkway-ok line
    assert not OK_LINE.search(out)
    (row,) = _records(root)
    assert (row["session_id"], row["kind"], row["value"], row["by"]) == (None, "new", "CARD-001", "owner")
    code, out, _ = cli(root, "card", "new", "Second", session=True)
    assert len(_records(root)) == 1


def test_records_are_append_only_lines(tmp_path):
    """Checks: each new command adds one record line and the earlier lines stay byte for byte (E6)."""
    root = task_root(tmp_path)
    cli(root, "card", "new", "One")
    path = root / "mkway" / "state" / "records.jsonl"
    first = path.read_bytes()
    cli(root, "card", "new", "Two")
    # each record is one appended JSON line; earlier lines stay byte for byte
    assert path.read_bytes().startswith(first)
    assert len(path.read_text(encoding="utf-8").splitlines()) == 2
