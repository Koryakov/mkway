"""Engine manifest (card MW-001, rows E12-E16; changed by card MW-002, row E4).

Expected values are the port map's registration table (section 3.1): event, matcher, timeout, onFailure and mode
per registered engine command. `matcher: None` stands for the map's «(all)»; `onFailure: "none"` is the map's word.
MW-002 (E4): `script` is replaced by `function` (the gate's `module:function`; None until the gate is written, card
MW-003) and each entry gains `group` (the dispatcher group, decision C10) and `reason_ids` (empty until the gate is
written, so the dispatcher does not load it).
"""
import ast
import json
import re
from pathlib import Path

import _engine  # noqa: F401  (puts the engine on sys.path)
import dispatch

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / "engine" / "manifest.json"

FILES = "Edit|Write|MultiEdit|NotebookEdit|Bash|PowerShell"
EDITS = "Edit|Write|MultiEdit"
SHELL = "Bash|PowerShell"
NE = "not established"

# (name, gate, group, event, matcher, timeout, onFailure, mode)
# Changed by MW-003: the entries a written gate replaces leave the list (REPLACED), and the lock_notice entries are
# deleted (D-1: lock_notice joins the start line).
PLANNED = [
    ("session_start", "session_start", "start", "SessionStart", None, 10, "none", None),
    ("derived_files.edit", "derived_files.edit", "edit", "PreToolUse", EDITS, 60, "block", "edit"),
    ("row_file_guard", "row_file_guard", "edit", "PreToolUse", EDITS, 10, "block", None),
    ("commit_check", "commit_check", "shell", "PreToolUse", SHELL, 240, "block", None),
    ("downstream_gate", "downstream_gate", "shell", "PreToolUse", SHELL, 60, "block", None),
    ("bash_speed_guard", "bash_speed_guard", "shell", "PreToolUse", SHELL, 10, "none", None),
    ("blind_reader_gate", "blind_reader_gate", "shell", "PreToolUse", SHELL, 30, "block", None),
    ("st_tests", "st_tests", "shell", "PreToolUse", SHELL, 900, "block", None),
    ("plan_gate.commit", "plan_gate.commit", "shell", "PreToolUse", SHELL, 10, "none", "commit"),
    ("derived_files.shell", "derived_files.shell", "shell", "PreToolUse", SHELL, 60, "block", "shell"),
    ("derived_files.commit", "derived_files.commit", "shell", "PreToolUse", SHELL, 60, "block", "commit"),
    ("questionnaire_gate", "questionnaire_gate", "edit", "PreToolUse",
     "ArtifactData|" + EDITS, 30, "none", None),
    ("read_first_gate", "read_first_gate", "edit", "PreToolUse", EDITS + "|NotebookEdit", 10, "none", None),
    ("ask_gate.pre", "ask_gate.pre", "edit", "PreToolUse", "Write|Edit|MultiEdit|AskUserQuestion", 120, "block",
     "pre"),
    ("owner_message", "owner_message", "prompt", "UserPromptSubmit", None, 10, "none", None),
    ("own_files_stop", "own_files_stop", "stop", "Stop", None, 30, "none", None),
]
# MW-003: the map rows a written gate replaces, and the deleted lock_notice entries (D-1)
REPLACED = {"rule_lock": "lock", "card_test_lock": "lock", "rule_code_lock": "lock", "process_lock": "lock",
            "discussion_freeze": "lock", "subtask_gate": "subtask", "lock_notice.session_start": "start line",
            "lock_notice.post_tool_use": "start line", "lock_notice.user_prompt_submit": "start line"}
# MW-019: planned entries that a written gate took over under the same name (they are `on` now, see ON)
WRITTEN_IN_PLACE = ("outbox_check.pre", "outbox_check.stop")
# MW-003: the gates the engine runs (status on): (name, gate, group, event, matcher, function, onFailure)
ON = [
    # changed by MW-017 (E8): the lead gate (form) runs first in the edit and shell groups, so a lead's refusal names the
    # lead rule and not `no-open-card`; its prompt reminder runs before the other reminders
    ("lead.edit", "lead", "edit", "PreToolUse", "Edit|Write|MultiEdit|NotebookEdit", "gate_lead:edit", "block"),
    ("lead.shell", "lead", "shell", "PreToolUse", SHELL, "gate_lead:shell", "block"),
    ("lock.edit", "lock", "edit", "PreToolUse", "Edit|Write|MultiEdit|NotebookEdit", "gate_lock:check", "block"),
    ("subtask", "subtask", "edit", "PreToolUse", "Edit|Write|MultiEdit|NotebookEdit", "gate_subtask:check", "block"),
    # changed by MW-007 (E10): the owner-ask edit gate runs after the lock and subtask gates of the edit group
    # changed by MW-014 (E6): the same entry also gates the pop-up question tool (`ask-tool-off`)
    ("owner_ask.edit", "owner_ask", "edit", "PreToolUse", "Edit|Write|MultiEdit|AskUserQuestion",
     "gate_owner_ask:check", "block"),
    # changed by MW-008 (E16): the search gate; it fails open (`onFailure: none`) in the edit group, so a crash of its
    # own reading never blocks a question or a write
    ("search", "search", "edit", "PreToolUse", "AskUserQuestion|Write|Edit|MultiEdit", "gate_search:check", "none"),
    # changed by MW-034 (E8): the write record `touched.edit` and `touched.shell` is gone
    # changed by MW-019 (E16): the outbox write gate: a check file's `sha256:` line must be the document's
    ("outbox_check.pre", "outbox_check.pre", "edit", "PreToolUse", EDITS, "gate_outbox:check", "block"),
    ("lock.shell", "lock", "shell", "PreToolUse", SHELL, "gate_lock:check", "block"),
    # changed by MW-006 (E7-E23): the commit gate itself, after the lock gate of its group
    ("commit_files", "commit_files", "shell", "PreToolUse", SHELL, "gate_commit:check", "block"),
    # changed by MW-009 (E14): the delete gate, after the commit gate of the shell group
    ("delete", "delete", "shell", "PreToolUse", SHELL, "gate_delete:check", "block"),
    # changed by MW-005 (E18): the test run is the slow gate, so it runs after the cheap file checks of `commit_files`
    ("commit_tests", "commit_tests", "shell", "PreToolUse", SHELL, "gate_commit_tests:check", "block"),
    # changed by MW-018 (E12): the SendMessage gate has its own group `message`; it fails open (`onFailure: none`)
    ("message.send", "message", "message", "PreToolUse", "SendMessage", "gate_message:check", "none"),
    ("records", "records", "post", "PostToolUse", SHELL, "gate_records:record", "none"),
    # changed by MW-004 (E9): the agent records, one entry per event, both on the gate `agents`; no matcher (every agent)
    ("agent_start", "agents", "post", "SubagentStart", None, "gate_agents:start", "none"),
    ("agent_stop", "agents", "post", "SubagentStop", None, "gate_agents:stop", "none"),
    # changed by MW-003 list item 5 (R43 (c)): the reminder of unresolved write targets at the next prompt
    # changed by MW-014 (E7): the notify step after a write of an ask file; it never blocks
    ("owner_ask.notify", "owner_ask", "post", "PostToolUse", "Write|Edit|MultiEdit", "gate_owner_ask:check", "none"),
    # changed by MW-019 (E16): the record of a write of a check file, the proof of which session wrote it
    ("outbox_check.post", "outbox_check.post", "post", "PostToolUse", EDITS, "gate_outbox:check", "none"),
    ("lead.remind", "lead", "prompt", "UserPromptSubmit", None, "gate_lead:remind", "none"),
    ("unresolved", "unresolved", "prompt", "UserPromptSubmit", None, "gate_lock:remind", "none"),
    # changed by MW-014 (E12): the reminder of an ask past its deadline, at the next prompt
    ("owner_ask.remind", "owner_ask", "prompt", "UserPromptSubmit", None, "gate_owner_ask:check", "none"),
    # changed by MW-018 (E12): the reminder of a session's unacked inbox items at the next prompt
    ("message.remind", "message", "prompt", "UserPromptSubmit", None, "gate_message:remind", "none"),
    # changed by MW-007 (E15): the owner-ask stop gate, the same gate and function as `owner_ask.edit`
    ("owner_ask.stop", "owner_ask", "stop", "Stop", None, "gate_owner_ask:check", "none"),
    # changed by MW-018 (E8): the reminder of an old unacked order at a Stop; never a block
    ("message.stop", "message", "stop", "Stop", None, "gate_message:stop", "none"),
    # changed by MW-019 (E15): the reminder of a file changed after its check; it never blocks
    ("outbox_check.stop", "outbox_check.stop", "stop", "Stop", None, "gate_outbox:check", "none"),
]
OFF_TODAY = ["code_lock", "handback_gate", "quality_gate", "st_gate", "step_close", "subtask_lint",
             "test_verdict_gate"]
FIELDS = {"name", "gate", "group", "function", "reason_ids", "event", "matcher", "timeout", "onFailure", "mode",
          "status", "default_on", "class"}  # changed by MW-012 (E1): every entry names its class
ON_FIELDS = FIELDS | {"on_failure_reason"}  # MW-003 decision 5: one line per gate
GROUPS = {"start", "edit", "shell", "post", "prompt", "stop", "message"}  # changed by MW-018 (E12): `message`
HOME = re.compile(r"~[/\\]|[A-Za-z]:[/\\]+Users|/Users/|/home/|\$HOME|USERPROFILE|\.claude[/\\]projects", re.I)


def _entries():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["entries"]


def test_planned_entries_are_the_27_registered_engine_commands():
    """E12: the planned entries are the map's registered engine commands still without code, each with the map's
    event, matcher, timeout, onFailure and mode. Changed by MW-003: of the 27, the ones a written gate replaces and
    the deleted lock_notice entries (REPLACED) leave; none of them is left in the manifest."""
    planned = [e for e in _entries() if e["status"] == "planned"]
    got = [(e["name"], e["gate"], e["group"], e["event"], e["matcher"], e["timeout"], e["onFailure"], e["mode"])
           for e in planned]
    assert len(PLANNED) + len(REPLACED) + len(WRITTEN_IN_PLACE) == 27  # changed by MW-019
    assert got == PLANNED
    assert sum(1 for e in planned if e["onFailure"] == "block") == 14 - 5
    for e in planned:  # no gate code yet: nothing the dispatcher could load
        assert e["function"] is None and e["reason_ids"] == [], e["name"]
    assert not set(REPLACED) & {e["name"] for e in _entries()}


def test_on_entries_carry_function_reasons_and_on_failure_reason():
    """E20 (MW-003, decisions 1, 2 and 5): each gate the engine runs is `on`, with its group, `function`, declared
    `reason_ids` and a one-line `on_failure_reason`; every edit and shell gate is `onFailure: block`, the `post`
    group's is not (a block after the tool ran undoes nothing). A gate in two groups has two entries on one function.
    Catches: a gate wired with no reason ids (not loaded), a missing reason, or a `post` gate that blocks."""
    on = [e for e in _entries() if e["status"] == "on"]
    got = [(e["name"], e["gate"], e["group"], e["event"], e["matcher"], e["function"], e["onFailure"]) for e in on]
    assert got == ON
    for e in on:
        assert e["reason_ids"] and all(isinstance(r, str) and r for r in e["reason_ids"]), e["name"]
        reason = e["on_failure_reason"]
        assert isinstance(reason, str) and reason.strip() and "\n" not in reason, e["name"]
        # changed by MW-008 (E16): the one edit gate that fails open is `search` (its own entry says so)
        # changed by MW-018 (E12): the `message` entry fails open too (its own entry says so)
        assert (e["onFailure"] == "block") == (e["group"] in ("edit", "shell")
                                               and e["name"] not in ("search", "message.send")), e["name"]
        if e["name"] in ("search", "message.send"):
            assert "fails open" in e["on_failure_reason"], e["name"]
        assert e["default_on"] is True


def test_off_today_entries_are_the_7_unregistered_gates():
    """E13: 7 off-today entries; their event and matcher are «not established»."""
    off = [e for e in _entries() if e["status"] == "off-today"]
    assert [e["name"] for e in off] == OFF_TODAY
    for e in off:
        assert e["function"] is None and e["reason_ids"] == []
        assert e["event"] == NE and e["matcher"] == NE and e["group"] == NE
        assert e["default_on"] is False


def test_entries_carry_all_fields():
    """E14 (changed by MW-002 E4): every entry carries exactly the field set (with group, function and reason_ids,
    and no script); only the two statuses exist; a group is one of the six; names are unique."""
    entries = _entries()
    assert len(entries) == 34 - len(REPLACED) + len(ON) - len(WRITTEN_IN_PLACE)  # changed by MW-003; MW-019: two `on` entries were planned
    for e in entries:
        extra = {"note", "user_home_read"} if e["name"] == "own_files_stop" else set()
        assert set(e) - extra == (ON_FIELDS if e["status"] == "on" else FIELDS), e.get("name")
        assert "script" not in e
        assert e["status"] in ("planned", "off-today", "on")
        assert e["group"] in GROUPS | {NE}, e["name"]
        assert isinstance(e["reason_ids"], list)
        assert isinstance(e["default_on"], bool)
    assert len({e["name"] for e in entries}) == len(entries)


def test_manifest_names_no_product_check_and_no_home_path():
    """E15: only the engine commands and gates are named (no product check); no path under a user home
    folder, other than in `default_on: false` entries."""
    entries = _entries()
    assert {e["name"] for e in entries} == {p[0] for p in PLANNED} | set(OFF_TODAY) | {o[0] for o in ON}
    assert all(e.get("kind", "engine") == "engine" for e in entries)
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rest = {k: v for k, v in data.items() if k != "entries"}
    assert not HOME.search(json.dumps(rest))
    for e in entries:
        if e["default_on"]:
            assert not HOME.search(json.dumps(e)), e["name"]


def test_home_folder_reader_is_off_by_default():
    """E16: own_files_stop stays, off by default, with the note «platform store, undocumented»."""
    (e,) = [e for e in _entries() if e["name"] == "own_files_stop"]
    assert e["status"] == "planned"
    assert e["default_on"] is False
    assert "platform store, undocumented" in e["note"]
    assert [x["name"] for x in _entries() if x["status"] == "planned" and not x["default_on"]] == ["own_files_stop"]


def test_group_table_sets_on_failure():
    """E54 (R13c point 2): the manifest's group table is an engine constant: the six groups; `edit` and `shell`
    carry `"onFailure": "block"`, `start`, `post`, `prompt` and `stop` carry none. Every entry's group is in it."""
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    table = data["groups"]
    assert set(table) == GROUPS
    assert {g: v.get("onFailure") for g, v in table.items()} == {
        "start": None, "edit": "block", "shell": "block", "post": None, "prompt": None, "stop": None,
        "message": None}
    assert all(set(v) <= {"onFailure"} for v in table.values())
    assert {e["group"] for e in data["entries"]} - {NE} <= set(table)
    # fix check N4: the dispatcher's blocking groups are the table's `onFailure: block` groups
    blocking = {g for g, v in table.items() if v.get("onFailure") == "block"}
    assert set(dispatch.BLOCKING_GROUPS) == blocking
    # and the root launcher's copy (fix check N6; read, not imported: importing runs it)
    tree = ast.parse((REPO / "mkway.py").read_text(encoding="utf-8"))
    (value,) = [n.value for n in tree.body if isinstance(n, ast.Assign)
                and any(getattr(t, "id", None) == "BLOCKING_GROUPS" for t in n.targets)]
    assert set(ast.literal_eval(value)) == blocking
