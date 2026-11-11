"""Commit checks (card MW-006), part 5: the commit message names the open card, its profile switch, an unreadable
message, and the gate wired in the shell group. Synthetic task roots only, real throwaway git repositories. The
card has an empty Paths and the session wrote the staged file, so only the message rule can refuse."""
import json

from _commit_fixture import check, make_task, reason, stage, touch, work
from _engine import jsonl
import dispatch

REASONS = {"file-not-in-card", "junk-file-staged", "ignored-file-staged", "data-file-staged",
           "file-too-large", "commit-message-card", "commit-unreadable", "register-tampered",
           "rule-without-test"}  # changed by MW-021 (E6): the rule card needs its test


def _task(tmp_path, **over):
    root = make_task(tmp_path, card_paths="", **over)
    work(root, "src/a.py")
    touch(root, "src/a.py")
    stage(root, "src/a.py")
    return root


def test_the_message_must_name_the_open_card(tmp_path):
    """E20 (part 5): the message of a commit must name the open card's id, as a whole id (the profile's
    `ids.card_prefix` form): in any `-m`, in a `-F -` here-document or in a readable message file; no id, another
    card's id, a longer number or a lower-case id is refused `commit-message-card`, naming the open card. A
    session with no open card has none to name. Catches: a commit that cannot be traced to its card."""
    root = _task(tmp_path)
    for command in ("git commit -m 'CARD-001 add the thing'", "git commit -m 'add the thing' -m 'CARD-001'",
                    "git commit -m 'work (CARD-001): add the thing'",
                    "git commit -F - <<'EOF'\nCARD-001 add the thing\nEOF"):
        assert reason(check(root, command)) == "allow", command
    work(root, "msg_ok.txt", "CARD-001 from a file\n")
    work(root, "msg_no.txt", "no card here\n")
    assert reason(check(root, "git commit -F msg_ok.txt")) == "allow"
    for command in ("git commit -m 'add the thing'", "git commit -m 'CARD-002 add the thing'",
                    "git commit -m 'CARD-0011 add the thing'", "git commit -m 'card-001 add the thing'",
                    "git commit -m 'XCARD-001 add the thing'", "git commit -F msg_no.txt",
                    "git commit -F - <<'EOF'\nno card\nEOF"):
        v = check(root, command)
        assert v.kind == "refuse" and v.reason_id == "commit-message-card", command
        assert "CARD-001" in v.message and "-m" in v.message, command
    assert reason(check(root, "git commit -m 'add the thing'", session="s2")) == "file-not-in-card"  # no card: rule 1
    exempt = make_task(tmp_path, card_paths="", name="exempt", paths={"exempt": ["notes/**"]})
    work(exempt, "notes/n.md")
    stage(exempt, "notes/n.md")
    assert reason(check(exempt, "git commit -m 'add the note'", session="s2")) == "allow"  # no open card: none to name


def test_the_switch_turns_the_message_rule_off(tmp_path):
    """E21 (part 5): `gates.commit_files.message_card.on: false` turns the message rule off and nothing else: a
    message with no card id passes, a junk file still refuses; `on: true` and no switch leave it on.
    Catches: a switch that disables the whole gate, or a rule that cannot be turned off."""
    off = _task(tmp_path, name="off", gates={"commit_files": {"message_card": {"on": False}}})
    assert reason(check(off, "git commit -m 'add the thing'")) == "allow"
    work(off, "junk.pyc")
    touch(off, "junk.pyc")
    stage(off, "junk.pyc")
    assert check(off, "git commit -m 'add the thing'").reason_id == "junk-file-staged"
    on = _task(tmp_path, name="on", gates={"commit_files": {"message_card": {"on": True}}})
    assert check(on, "git commit -m 'add the thing'").reason_id == "commit-message-card"


def test_an_unreadable_message_refuses(tmp_path):
    """E22 (part 5): a message the gate cannot read (no `-m`, a message file that does not exist, a reused message
    with `-C`, a `-F -` with no here-document) refuses `commit-unreadable` while the message rule is on, naming
    `-m`; with the rule off it passes. Catches: a commit whose message was never checked because it was hidden."""
    root = _task(tmp_path)
    for command in ("git commit", "git commit -F missing.txt", "git commit -C HEAD", "git commit --amend",
                    "git commit -F -"):
        v = check(root, command)
        assert v.kind == "refuse" and v.reason_id == "commit-unreadable", command
        assert "message" in v.message and "-m" in v.message, command
    off = _task(tmp_path, name="off", gates={"commit_files": {"message_card": {"on": False}}})
    assert reason(check(off, "git commit -C HEAD")) == "allow"


def _run(root, tool, tool_input, session="s1"):
    payload = {"session_id": session, "hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input,
               "cwd": str(root)}
    return dispatch.run("PreToolUse", "shell", json.dumps(payload), env={"CLAUDE_PROJECT_DIR": str(root)})


def test_the_gate_runs_in_the_shell_group_with_its_tag_and_a_switch(tmp_path):
    """E23 (part 5): the manifest entry `commit_files` (gate `commit_files`, shell group, PreToolUse, Bash and
    PowerShell, function `gate_commit:check`, `onFailure: block`, an `on_failure_reason`) declares every reason id of
    the gate; the dispatcher refuses through it with the tag `[mkway commit_files <reason>]` and writes a row; an
    allowed commit passes silently; `gates.commit_files.on: false` turns the gate off.
    Catches: a reason the gate returns that the entry does not declare (the dispatcher would log it as undeclared)."""
    entries = {e["name"]: e for e in dispatch.load_manifest(dispatch.ENGINE_DIR)}
    e = entries["commit_files"]
    assert (e["gate"], e["group"], e["event"], e["matcher"], e["function"], e["onFailure"], e["status"],
            e["default_on"]) == ("commit_files", "shell", "PreToolUse", "Bash|PowerShell", "gate_commit:check",
                                 "block", "on", True)
    assert set(e["reason_ids"]) == REASONS and e["on_failure_reason"].strip() and "\n" not in e["on_failure_reason"]

    # changed by the port of MW-005: the test gate `commit_tests` runs after `commit_files` in the same group; this test
    # is about `commit_files`, so it switches the test gate off (the fixture project has no test folder to run)
    tests_off = {"commit_tests": {"on": False}}
    root = _task(tmp_path, gates=tests_off)
    res = _run(root, "Bash", {"command": "git commit -m 'add the thing'"})
    out = json.loads(res.stdout)["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny"
    assert out["permissionDecisionReason"].startswith("[mkway commit_files commit-message-card] ")
    rows = [r for r in jsonl(root / "mkway" / "state" / "refusals.jsonl") if r["gate"] == "commit_files"]
    assert [(r["reason_id"], r["kind"]) for r in rows] == [("commit-message-card", "refuse")]
    res = _run(root, "Bash", {"command": "git commit -m 'CARD-001 add the thing'"})
    assert res.exit_code == 0 and res.stdout == ""
    res = _run(root, "PowerShell", {"command": "git commit -m 'add the thing'"})
    assert json.loads(res.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"

    off = _task(tmp_path, name="off", gates={"commit_files": {"on": False}, **tests_off})
    assert _run(off, "Bash", {"command": "git commit -m 'add the thing'"}).stdout == ""
