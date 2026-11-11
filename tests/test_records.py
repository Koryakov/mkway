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


def test_post_group_records_a_session_command(tmp_path):
    """E5: a session's `card new` prints `mkway-ok new <id> <nonce>` and writes the nonce; the `post` group matches
    the line and the nonce and appends `{session_id, kind, value, time, by: session}`; the command itself writes no
    row. Catches: a record written from the command line alone (before or without the run), or by the command."""
    root = task_root(tmp_path)
    code, out, _err = cli(root, "card", "new", "First", session=True)
    assert code == 0
    assert _records(root) == []
    (m,) = OK_LINE.findall(out)
    assert m[:2] == ("new", "CARD-001")
    res = _post(root, out)
    assert res.exit_code == 0
    (row,) = _records(root)
    assert {k: row[k] for k in ("session_id", "kind", "value", "by")} == {
        "session_id": "s1", "kind": "new", "value": "CARD-001", "by": "session"}
    assert row["time"]


def test_forged_or_replayed_line_writes_no_record(tmp_path):
    """E5: a `mkway-ok` line with no nonce file, with a nonce issued for another kind or value, or a nonce used
    twice, writes no record. Catches: a post group that trusts the stdout text, or does not consume the nonce."""
    root = task_root(tmp_path)
    _post(root, "mkway-ok search anything " + "0" * 32 + "\n")
    assert _records(root) == []
    code, out, _ = cli(root, "card", "new", "First", session=True)
    (kind, value, nonce) = OK_LINE.findall(out)[0]
    _post(root, f"mkway-ok take {value} {nonce}\n")
    _post(root, f"mkway-ok new CARD-009 {nonce}\n")
    assert _records(root) == []
    _post(root, out)
    _post(root, out)
    assert len(_records(root)) == 1


def test_owner_terminal_appends_its_own_row(tmp_path):
    """E6: run from the owner's terminal (no hook, no session marker) the command appends one `by: owner` row with
    no session id, and prints no `mkway-ok` line. Catches: an owner command that leaves no record, or a session
    command that writes an owner row."""
    root = task_root(tmp_path)
    code, out, _ = cli(root, "card", "new", "First")
    assert code == 0
    assert not OK_LINE.search(out)
    (row,) = _records(root)
    assert (row["session_id"], row["kind"], row["value"], row["by"]) == (None, "new", "CARD-001", "owner")
    code, out, _ = cli(root, "card", "new", "Second", session=True)
    assert len(_records(root)) == 1


def test_records_are_append_only_lines(tmp_path):
    """E6: each record is one appended JSON line; earlier lines stay byte for byte.
    Catches: a read-modify-write of the records file."""
    root = task_root(tmp_path)
    cli(root, "card", "new", "One")
    path = root / "mkway" / "state" / "records.jsonl"
    first = path.read_bytes()
    cli(root, "card", "new", "Two")
    assert path.read_bytes().startswith(first)
    assert len(path.read_text(encoding="utf-8").splitlines()) == 2


def test_post_failure_allows_with_a_warn_row(tmp_path):
    """E7: when the record cannot be written, the `post` group allows (the tool already ran) and writes a warn row
    `post-record-failed`. Catches: a post group that blocks, or that fails silently."""
    root = task_root(tmp_path)
    code, out, _ = cli(root, "card", "new", "First", session=True)
    (root / "mkway" / "state" / "records.jsonl").mkdir()  # the append fails
    res = _post(root, out)
    assert res.exit_code == 0
    assert "deny" not in res.stdout and '"block"' not in res.stdout
    rows = jsonl(root / "mkway" / "state" / "refusals.jsonl")
    assert [(r["gate"], r["reason_id"], r["kind"]) for r in rows] == [("records", "post-record-failed", "warn")]


def test_post_reads_a_powershell_string_response(tmp_path):
    """E5: a PowerShell call's `tool_response` may be a plain string; the line is found there too.
    Catches: a post group that reads only the Bash `stdout` key."""
    root = task_root(tmp_path)
    code, out, _ = cli(root, "card", "new", "First", session=True)
    _post(root, None, tool="PowerShell", response=out)
    assert [r["kind"] for r in _records(root)] == ["new"]
