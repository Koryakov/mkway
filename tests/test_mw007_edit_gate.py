"""The owner-ask edit gate (card MW-007, part 1): writing `<asks dir>/<name>_ask.md` needs `<name>_sources.md` beside
it. Synthetic task roots only; no task data. The gate module is imported inside each test, so a missing module fails
that test and not the collection of the file."""
import importlib
import json

import pytest

from _engine import gate_call, jsonl, task_root
import _mw014
import dispatch

SUBSTANCE = "kind: substance\nreview: 0 contradictions\n> review: :27 «a verbatim line of the source»\n"


def _gate():
    return importlib.import_module("gate_owner_ask")


def _pre(root, path, tool="Write"):
    # changed by MW-014 (E3): the write carries a complete ask (the fields of the card), so these rows stay about sources
    return gate_call(_gate().check, root, tool=tool, tool_input=_mw014.tool_input(root, path, tool))


def _id(verdict):
    return verdict.reason_id if verdict.kind == "refuse" else "allow"


def _sources(root, name, text, folder="mkway/asks"):
    d = root / folder
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}_sources.md").write_text(text, encoding="utf-8", newline="")


@pytest.fixture
def task(tmp_path):
    # MW-008 (E17): the default source is now `ledger`; these tests are about the `review` lines, so they name it
    return task_root(tmp_path, owner_ask={"sources": ["review"]})


def test_edit_gate_leaves_other_writes_alone(task, tmp_path):
    """E4 (part 1): only a write to `<asks dir>/<name>_ask.md` by Write, Edit or MultiEdit is the gate's; every other
    write is allowed: another folder, a nested folder, a file of the folder that is not an ask, the sources file
    itself, a path outside the root, a tool that does not write, a tool input with no path.
    Catches: a gate that blocks the sources file (so it could never be written first) or other files."""
    for path in ("work/x.md", "mkway/asks/t_check.md", "mkway/asks/t_sources.md", "notes/t_ask.md",
                 "mkway/asks/sub/t_ask.md", "mkway/asks/_ask.txt", "mkway/t_ask.md",
                 str(tmp_path / "elsewhere" / "mkway" / "asks" / "t_ask.md")):
        assert _id(_pre(task, path)) == "allow", path
    assert _id(gate_call(_gate().check, task, tool="Read", tool_input={"file_path": "mkway/asks/t_ask.md"})) == "allow"
    assert _id(gate_call(_gate().check, task, tool="NotebookEdit",
                         tool_input={"notebook_path": "mkway/asks/t_ask.md"})) == "allow"
    assert _id(gate_call(_gate().check, task, tool="Write", tool_input={"content": "x"})) == "allow"
    assert _id(gate_call(_gate().check, task, tool="Write", tool_input=None)) == "allow"


def test_an_ask_needs_a_sources_file_with_a_kind(task):
    """E5 (part 1): writing an ask with no `<name>_sources.md` beside it is refused `ask-sources-missing`, and the
    text names the file; a sources file with no `kind:` line is refused `ask-sources-kind`, and the text names the
    three kinds; the three write tools are gated, and the ask is found by every spelling of its path.
    Catches: a session that asks without writing down what it checked, or a gate bypassed by a path spelling."""
    for tool in ("Write", "Edit", "MultiEdit"):
        v = _pre(task, "mkway/asks/t_ask.md", tool=tool)
        assert v.kind == "refuse" and v.reason_id == "ask-sources-missing", tool
        assert "t_sources.md" in v.message
    _sources(task, "t", "no kind here\n")
    v = _pre(task, "mkway/asks/t_ask.md")
    assert v.kind == "refuse" and v.reason_id == "ask-sources-kind"
    assert "kind: substance|session|lock" in v.message
    _sources(task, "t", "kind: other\n")
    assert _id(_pre(task, "mkway/asks/t_ask.md")) == "ask-sources-kind"
    for spelling in (str(task / "mkway" / "asks" / "t_ask.md"), "./mkway/asks/t_ask.md", "mkway\\asks\\t_ask.md",
                     "mkway/asks/t_ASK.MD"):
        assert _id(_pre(task, spelling)) == "ask-sources-kind", spelling


@pytest.mark.parametrize("text, missing, present", [
    ("kind: substance\n", ["review: N contradictions", "> review: <verbatim quote>"], []),
    ("kind: substance\nreview: 2 contradictions\n", ["> review: <verbatim quote>"], ["review: N contradictions"]),
    ("kind: substance\n> review: :27 «a line»\n", ["review: N contradictions"], ["> review: <verbatim quote>"]),
    ("kind: substance\nreview: 0 contradictions\n> review:\n", ["> review: <verbatim quote>"], []),
    ("kind: substance\nreview: many contradictions\n> review: x\n", ["review: N contradictions"], []),
    ("kind: substance\nreview: 0 contradictions\n review: x\n", ["> review: <verbatim quote>"], []),
    ("kind: substance\nchecked: ListAgents\n", ["review: N contradictions"], []),
])
def test_substance_needs_a_count_line_and_a_quote_line(task, text, missing, present):
    """E6 (part 1): `kind: substance` needs `review: N contradictions` and at least one `> review: <verbatim>` line
    (`> review:` with nothing after the colon is no quote); the refusal `ask-sources-lines` names each missing line
    and no line that is there. Catches: a count with no quote, a quote with no count, or an empty quote."""
    _sources(task, "t", text)
    v = _pre(task, "mkway/asks/t_ask.md")
    assert v.kind == "refuse" and v.reason_id == "ask-sources-lines"
    for line in missing:
        assert line in v.message, line
    for line in present:
        assert line not in v.message, line


def test_a_full_substance_sources_file_lets_the_ask_through(task):
    """E6 (part 1): the full substance file allows the ask by every write tool; one contradiction counts as well as
    none; a CRLF file and a differently cased `Kind:` line count. Catches: a gate that refuses a complete file."""
    for text in (SUBSTANCE, SUBSTANCE.replace("0 contradictions", "1 contradiction"),
                 SUBSTANCE.replace("\n", "\r\n"), SUBSTANCE.replace("kind: substance", "Kind:  Substance")):
        _sources(task, "t", text)
        for tool in ("Write", "Edit", "MultiEdit"):
            assert _id(_pre(task, "mkway/asks/t_ask.md", tool=tool)) == "allow", (text, tool)


def test_session_and_lock_kinds_each_need_their_checked_line(task):
    """E7 (part 1): `kind: session` needs `checked: ListAgents` (any case, anything after it); `kind: lock` needs
    `checked:` and a lock state after it. The refusal names the missing line. Catches: a session ask that says it
    checked nothing, or a lock ask with an empty `checked:` line."""
    agents, state = "checked: ListAgents", "checked: <lock state>"
    cases = [("kind: session\n", agents, False), ("kind: session\nchecked: Other\n", agents, False),
             ("kind: session\nchecked: ListAgents\n", None, True),
             ("kind: session\nchecked: listagents 10:20\n", None, True),
             ("kind: lock\n", state, False), ("kind: lock\nchecked:\n", state, False),
             ("kind: lock\nchecked:   \nnext line\n", state, False),
             ("kind: lock\nchecked: commit lock closed since 10:00\n", None, True)]
    for text, line, ok in cases:
        _sources(task, "t", text)
        v = _pre(task, "mkway/asks/t_ask.md")
        if ok:
            assert v.kind == "allow", text
        else:
            assert v.kind == "refuse" and v.reason_id == "ask-sources-lines" and line in v.message, text


def test_folder_and_sources_come_from_the_profile(tmp_path):
    """E8 (part 1): `owner_ask.dir` moves the gated folder (the default folder is then not gated); with
    `sources: [review, canon]` the substance file needs a count line and a quote line for each, and the refusal names
    only the missing ones. Catches: a folder or a source name that is hard-coded in the gate."""
    task = task_root(tmp_path, owner_ask={"dir": "notes/asks", "sources": ["review", "canon"]})
    assert _id(_pre(task, "mkway/asks/t_ask.md")) == "allow"
    assert _id(_pre(task, "notes/asks/t_ask.md")) == "ask-sources-missing"
    _sources(task, "t", SUBSTANCE, folder="notes/asks")
    v = _pre(task, "notes/asks/t_ask.md")
    assert v.reason_id == "ask-sources-lines"
    assert "canon: N contradictions" in v.message and "> canon: <verbatim quote>" in v.message
    assert "review: N contradictions" not in v.message and "> review: <verbatim quote>" not in v.message
    _sources(task, "t", SUBSTANCE + "canon: 1 contradictions\n> canon: D-1 «a verbatim line»\n", folder="notes/asks")
    assert _id(_pre(task, "notes/asks/t_ask.md")) == "allow"
    _sources(task, "t", SUBSTANCE + "canon: 1 contradictions\n> review: again\n", folder="notes/asks")
    assert _id(_pre(task, "notes/asks/t_ask.md")) == "ask-sources-lines"


def test_an_unreadable_sources_file_refuses_and_never_crashes(task):
    """E9 (part 1): a sources path that is a folder, or a file that is not UTF-8 text, is refused (never an
    exception, never an allow). Catches: a gate that crashes on a hostile file, which would block every edit in the
    group, or one that lets the ask through when it cannot read the proof."""
    (task / "mkway" / "asks" / "t_sources.md").mkdir(parents=True)
    assert _id(_pre(task, "mkway/asks/t_ask.md")) in ("ask-sources-missing", "ask-sources-kind")
    (task / "mkway" / "asks" / "t_sources.md").rmdir()
    (task / "mkway" / "asks" / "t_sources.md").write_bytes(b"\xff\xfe\x00kind: substance\n")
    assert _id(_pre(task, "mkway/asks/t_ask.md")) in ("ask-sources-missing", "ask-sources-kind", "ask-sources-lines")


def test_the_edit_gate_runs_in_the_edit_group_and_has_a_switch(tmp_path):
    """E10 (part 1): through the dispatcher and the real manifest, the `edit` group refuses an ask with no sources
    (`[mkway owner_ask.edit ask-sources-missing]`, a row in the refusal log) and passes it with the sources; the
    profile's `gates.owner_ask.on: false` turns the gate off. Catches: a gate that is written but not wired, or has
    no switch."""
    task = task_root(tmp_path, paths={"exempt": ["mkway/asks/**"]}, owner_ask={"sources": ["review"]})  # MW-008
    payload = {"session_id": "s1", "hook_event_name": "PreToolUse", "tool_name": "Write",
               "tool_input": {"file_path": "mkway/asks/t_ask.md", "content": _mw014.ask_text()}}  # MW-014 (E3)
    env = {"CLAUDE_PROJECT_DIR": str(task), "CLAUDECODE": "1"}
    res = dispatch.run("PreToolUse", "edit", json.dumps(payload), env=env)
    assert res.exit_code == 0
    out = json.loads(res.stdout)["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny"
    assert "[mkway owner_ask.edit ask-sources-missing]" in out["permissionDecisionReason"]
    assert [(r["gate"], r["reason_id"]) for r in jsonl(task / "mkway" / "state" / "refusals.jsonl")] == [
        ("owner_ask.edit", "ask-sources-missing")]
    _sources(task, "t", SUBSTANCE)
    assert dispatch.run("PreToolUse", "edit", json.dumps(payload), env=env).stdout == ""
    (task / "mkway" / "asks" / "t_sources.md").unlink()
    profile = json.loads((task / "mkway" / "profile.json").read_text(encoding="utf-8"))
    profile["gates"] = {"owner_ask": {"on": False}}
    (task / "mkway" / "profile.json").write_text(json.dumps(profile), encoding="utf-8")
    assert dispatch.run("PreToolUse", "edit", json.dumps(payload), env=env).stdout == ""
