"""Card MW-014, part 1: the ask file carries its fields, one open ask per session, the pop-up question tool is off.
Synthetic task roots only; no task data. The gate module is imported inside each test, so a missing module fails that
test and not the collection of the file."""
import json

import pytest

import _mw014
from _engine import gate_call, jsonl, task_root
from _mw014 import FAR, PAST, SHAPES, ask_text, post, pre, verdict_id, write_ask, write_sources
import dispatch
import records


@pytest.fixture
def task(tmp_path):
    root = task_root(tmp_path)
    write_sources(root, "t")
    return root


@pytest.mark.parametrize("field", list(SHAPES))
def test_a_missing_field_line_is_refused_and_named(task, field):
    """E1: an ask with no `default:`, `deadline:`, `blocked:`, `reversible:` or `status:` line is refused
    `ask-fields-missing`, and the text names that line and no line that is there.
    Catches: an ask with no default or no deadline, which lets a session wait on the owner with nothing to fall back on."""
    for tool in ("Write", "Edit", "MultiEdit"):
        v = pre(task, text=ask_text(omit=(field,)), tool=tool)
        assert v.kind == "refuse" and v.reason_id == "ask-fields-missing", (field, tool)
        assert SHAPES[field] in v.message, (field, tool)
        for other, shape in SHAPES.items():
            if other != field:
                assert shape not in v.message, (field, other)


def test_an_ask_with_no_field_names_all_five(task):
    """E1: a bare question with no field line is refused and the text names the five lines.
    Catches: a gate that names only the first missing line, so the session fixes one line per refusal."""
    v = pre(task, text="Which option?\n")
    assert v.reason_id == "ask-fields-missing"
    for shape in SHAPES.values():
        assert shape in v.message


@pytest.mark.parametrize("line, field", [
    ("default:", "default"), ("default:   ", "default"), ("blocked:", "blocked"),
    ("deadline: tomorrow", "deadline"), ("deadline:", "deadline"), ("deadline: 2026-13-45T10:00", "deadline"),
    ("reversible: maybe", "reversible"), ("reversible:", "reversible"),
    ("status: answered", "status"), ("status: default-taken", "status"), ("status:", "status"),
])
def test_a_field_with_an_unusable_value_counts_as_missing(task, line, field):
    """E2: a field line with no value, a deadline that is not an ISO time (and not `none`), a `reversible` that is not
    yes or no, or a status other than `open` is as good as missing: the same refusal names the line's shape.
    Catches: a `deadline: tomorrow` that no board can compare, or an ask written as already answered."""
    key = line.split(":")[0]
    text = "\n".join(l for l in ask_text(omit=(field,)).splitlines()) + f"\n{line}\n"
    assert key == field
    v = pre(task, text=text)
    assert v.kind == "refuse" and v.reason_id == "ask-fields-missing"
    assert SHAPES[field] in v.message


@pytest.mark.parametrize("text", [
    ask_text(),
    ask_text(default="none", deadline="none", blocked="none"),
    ask_text(deadline="2099-01-01 10:00"),
    ask_text(deadline="2099-01-01T10:00:30"),
    ask_text(reversible="no"),
    ask_text().replace("\n", "\r\n"),
    ask_text().replace("default:", "Default:").replace("status:", "STATUS:"),
])
def test_a_complete_ask_is_allowed_by_every_write_tool(task, text):
    """E3: a complete ask passes by Write, Edit and MultiEdit: any text or `none` after `default:` and `blocked:`, a
    deadline that is `none` or an ISO local time (with `T` or a space), `reversible: yes|no`, `status: open`; a CRLF
    file and a differently cased line count. Catches: a gate that refuses a complete file."""
    for tool in ("Write", "Edit", "MultiEdit"):
        assert verdict_id(pre(task, text=text, tool=tool, session=None)) == "allow", (tool, text)


def test_an_edit_is_judged_on_the_file_it_leaves(task):
    """E3: an Edit or a MultiEdit of an ask already on disk is judged on the text after the change: an edit that adds
    the missing line passes, one that leaves it out is refused, an edit that turns `status: open` into another status is
    refused. Catches: a gate that reads only the replaced text, or only the old file."""
    path = write_ask(task, "t", omit=("blocked",))
    rel = "mkway/asks/t_ask.md"
    keep = {"file_path": rel, "old_string": "reversible: yes", "new_string": "reversible: no"}
    add = {"file_path": rel, "old_string": "reversible: yes", "new_string": "reversible: yes\nblocked: the part"}
    close = {"file_path": rel, "old_string": "status: open", "new_string": "status: answered"}
    run = lambda tool, inp: gate_call(_mw014.gate().check, task, tool=tool, tool_input=inp)  # noqa: E731
    assert run("Edit", keep).reason_id == "ask-fields-missing" and SHAPES["blocked"] in run("Edit", keep).message
    assert run("Edit", add).kind == "allow"
    assert run("MultiEdit", {"file_path": rel, "edits": [add]}).kind == "allow"
    assert run("MultiEdit", {"file_path": rel, "edits": [add, keep]}).kind == "allow"  # edits apply in order
    path.write_text(ask_text(), encoding="utf-8")
    assert run("Edit", close).reason_id == "ask-fields-missing" and SHAPES["status"] in run("Edit", close).message


def test_the_fields_come_after_the_sources_and_leave_other_files_alone(task):
    """E3: the sources check still decides first (no sources file: `ask-sources-missing`); a write that is not an ask
    path needs no fields. Catches: a fields check that hides the sources refusal or gates a sources file."""
    assert pre(task, "other", text="x").reason_id == "ask-sources-missing"
    for path in ("mkway/asks/t_sources.md", "mkway/asks/t_check.md", "work/x.md"):
        assert verdict_id(pre(task, path=path, text="x")) == "allow", path


def test_a_second_open_ask_by_the_same_session_is_refused(task):
    """E4: while one ask of the session has `status: open`, a new `<name>_ask.md` by that session is refused
    `ask-already-open` and the text says to add to the open ask or wait; another session may ask; a write to the open ask
    itself is allowed. Catches: one session that leaves five asks open and repeats one."""
    write_sources(task, "u")
    write_ask(task, "t", session="s1")
    v = pre(task, "u", session="s1")
    assert v.kind == "refuse" and v.reason_id == "ask-already-open"
    assert "add to the open ask" in v.message and "wait" in v.message and "t" in v.message
    assert verdict_id(pre(task, "u", session="s2")) == "allow"
    assert verdict_id(pre(task, "t", session="s1", tool="Edit")) == "allow"
    assert verdict_id(pre(task, "t", session="s1", tool="Write")) == "allow"


@pytest.mark.parametrize("status", ["answered", "default-taken", "withdrawn"])
def test_an_ask_that_is_no_longer_open_frees_the_session(task, status):
    """E4: the later statuses the owner (or a command) sets close the ask; the session may then write its next ask.
    Catches: a session that is blocked for good by an ask the owner already answered."""
    write_sources(task, "u")
    write_ask(task, "t", session="s1", status=status)
    assert verdict_id(pre(task, "u", session="s1")) == "allow"


def test_max_open_comes_from_the_profile(tmp_path):
    """E4: `owner_ask.max_open` (default 1) is how many open asks one session may have; a profile with 2 lets the
    second ask through and refuses the third. Catches: a limit that is hard-coded."""
    root = task_root(tmp_path, owner_ask={"max_open": 2})
    for name in "tuv":
        write_sources(root, name)
    write_ask(root, "t", session="s1")
    assert verdict_id(pre(root, "u", session="s1")) == "allow"
    write_ask(root, "u", session="s1")
    assert pre(root, "v", session="s1").reason_id == "ask-already-open"


def test_a_session_without_an_id_and_a_missing_file_do_not_count(task):
    """E4: a record whose ask file is gone counts for nothing; a call with no session id is never refused by the
    one-open rule. Catches: a stale record that blocks the session for good, or a crash with no session id."""
    write_sources(task, "u")
    write_ask(task, "t", session="s1").unlink()
    assert verdict_id(pre(task, "u", session="s1")) == "allow"
    write_ask(task, "t", session="s1")
    assert verdict_id(pre(task, "u", session=None)) == "allow"


def test_the_post_step_records_who_wrote_an_ask(task):
    """E4: after an ask file is written, the post step records `ask <name>` for the session; a file that is not an ask
    and a tool that is not a write leave no record. Catches: an owner of an ask that nobody can name, so the
    one-open rule and the deadline reminder never find the session."""
    write_ask(task, "t")
    assert post(task, "t", session="s7").kind in ("allow", "log")
    rows = [r for r in records.rows(task / "mkway" / "state") if r.get("kind") == "ask"]
    assert [(r["session_id"], r["value"]) for r in rows] == [("s7", "t")]
    post(task, path="mkway/asks/t_sources.md", session="s7")
    post(task, path="work/x.md", session="s7")
    gate_call(_mw014.gate().check, task, tool="Read", event="PostToolUse", session="s7",
              tool_input={"file_path": "mkway/asks/t_ask.md"})
    assert len([r for r in records.rows(task / "mkway" / "state") if r.get("kind") == "ask"]) == 1


def test_the_pop_up_question_tool_is_refused_with_the_file_route(task):
    """E5: `AskUserQuestion` is refused `ask-tool-off`, and the text names the file route (the asks folder, the
    `_ask.md` file and its fields); no other tool is touched. Catches: a session that stops the work on a pop-up
    nobody sees."""
    v = gate_call(_mw014.gate().check, task, tool="AskUserQuestion", tool_input={"questions": []})
    assert v.kind == "refuse" and v.reason_id == "ask-tool-off"
    assert "mkway/asks/<name>_ask.md" in v.message and "default" in v.message and "deadline" in v.message
    for tool in ("Bash", "Read", "Task"):
        assert gate_call(_mw014.gate().check, task, tool=tool, tool_input={"command": "x"}).kind == "allow", tool


def test_the_switch_lets_the_pop_up_question_tool_through(tmp_path):
    """E5: `owner_ask.tool_allowed: true` allows the tool; false or a missing key refuses it. Catches: a switch that
    does nothing."""
    for value, kind in ((True, "allow"), (False, "refuse")):
        root = task_root(tmp_path / str(value), owner_ask={"tool_allowed": value})
        assert gate_call(_mw014.gate().check, root, tool="AskUserQuestion", tool_input={}).kind == kind, value


def test_the_dispatcher_refuses_the_pop_up_tool_before_the_search_gate(tmp_path):
    """E6: through the real manifest, the `edit` group refuses `AskUserQuestion` with `[mkway owner_ask.edit
    ask-tool-off]` and a row in the refusal log (the search gate is not reached); the switch lets it through to the
    search gate. Catches: a gate that is written but not wired to the tool."""
    task = task_root(tmp_path)
    payload = {"session_id": "s1", "hook_event_name": "PreToolUse", "tool_name": "AskUserQuestion",
               "tool_input": {"questions": []}}
    env = {"CLAUDE_PROJECT_DIR": str(task), "CLAUDECODE": "1"}
    res = dispatch.run("PreToolUse", "edit", json.dumps(payload), env=env)
    out = json.loads(res.stdout)["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny" and "[mkway owner_ask.edit ask-tool-off]" in out["permissionDecisionReason"]
    assert [(r["gate"], r["reason_id"]) for r in jsonl(task / "mkway" / "state" / "refusals.jsonl")] == [
        ("owner_ask.edit", "ask-tool-off")]
    profile = json.loads((task / "mkway" / "profile.json").read_text(encoding="utf-8"))
    profile["owner_ask"] = {"tool_allowed": True}
    (task / "mkway" / "profile.json").write_text(json.dumps(profile), encoding="utf-8")
    res = dispatch.run("PreToolUse", "edit", json.dumps(payload), env=env)  # no transcript: the search gate only logs
    assert "ask-tool-off" not in res.stdout
    assert jsonl(task / "mkway" / "state" / "refusals.jsonl")[-1]["reason_id"] == "search-unverified"
