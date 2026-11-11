"""Card MW-019, part 2 (the write gate and the record) and the Stop reminder: a check file whose `sha256:` line is not
the document's is refused, the post step records who wrote a check, the Stop gate reminds. Synthetic roots only. The
gate module is imported inside each helper, so a missing module fails that test and not the collection of the file."""
import json
from pathlib import Path

import pytest

import dispatch
from _engine import jsonl
from _mw019 import (OUT, RECORDS, SUFFIX, check_text, make_root, post, pre, refusal_rows, set_outbox, sha_of,
                    state_dir, stop, valid_file, write_check, write_doc)


@pytest.fixture
def task(tmp_path):
    root = make_root(tmp_path)
    write_doc(root)  # outbox/a.md
    return root


def _good(root):
    return check_text(sha_of(Path(root) / f"{OUT}/a.md"))


def _manifest(name):
    entries = json.loads((dispatch.ENGINE_DIR / "manifest.json").read_text(encoding="utf-8"))["entries"]
    return [e for e in entries if e["name"] == name]


WRONG = "0" * 64


def test_a_check_whose_sha_line_is_not_the_documents_is_refused(task):
    """E10: a Write, Edit or MultiEdit that leaves a check file with a `sha256:` line that is not the sha256 of the
    document now is refused `check-sha-mismatch`; the text gives the line to write (the document's full sha) and names
    `mkway outbox`, and a stale check cannot be forged by hand. Catches: a check written for text that has changed."""
    rel = f"{OUT}/a.md{SUFFIX}"
    right = sha_of(Path(task) / f"{OUT}/a.md")
    v = pre(task, rel, check_text(WRONG))
    assert v.kind == "refuse" and v.reason_id == "check-sha-mismatch"
    assert f"sha256: {right}" in v.message and "mkway outbox" in v.message and "a.md" in v.message
    path = Path(task) / rel
    path.write_text(check_text(WRONG), encoding="utf-8", newline="")
    sha_line = f"sha256: {WRONG}"
    for tool, kwargs in (("Edit", {"old": "links: clean", "new": "links: clean"}),
                         ("MultiEdit", {"edits": [("links: clean", "links: clean")]})):
        v = pre(task, rel, tool=tool, **kwargs)
        assert v.kind == "refuse" and v.reason_id == "check-sha-mismatch", tool
    assert sha_line in path.read_text(encoding="utf-8")  # the gate wrote nothing


def test_a_check_with_the_right_sha_is_allowed_by_every_write_tool(task):
    """E10: the same write with the document's sha256 is allowed by Write, Edit and MultiEdit (a sha written in capitals
    is the same sha); the gate does not judge the other lines, which are the checker's attestations in a fixed form.
    Catches: a gate that refuses a good check or reads the case of the digits."""
    rel = f"{OUT}/a.md{SUFFIX}"
    assert pre(task, rel, _good(task)).kind == "allow"
    shout = check_text(sha_of(Path(task) / f"{OUT}/a.md").upper(), numbers="numbers: 1 checked, 5 contradictions")
    assert pre(task, rel, shout).kind == "allow"
    (Path(task) / rel).write_text(_good(task), encoding="utf-8", newline="")
    assert pre(task, rel, tool="Edit", old="links: clean", new="links: clean, 3 links").kind == "allow"
    assert pre(task, rel, tool="MultiEdit", edits=[("links: clean", "links: clean"), ("claims", "claims")]).kind == "allow"


def test_an_edit_is_judged_on_the_file_it_leaves(task):
    """E10: an Edit that changes the sha line to a wrong one is refused although the file on disk was right; an Edit
    that mends a wrong sha line is allowed although the file on disk was wrong; an edit whose old text is not found
    leaves the file as it is. Catches: a gate that judges the tool input instead of the resulting file."""
    rel = f"{OUT}/a.md{SUFFIX}"
    right = sha_of(Path(task) / f"{OUT}/a.md")
    path = Path(task) / rel
    path.write_text(_good(task), encoding="utf-8", newline="")
    v = pre(task, rel, tool="Edit", old=f"sha256: {right}", new=f"sha256: {WRONG}")
    assert v.kind == "refuse" and v.reason_id == "check-sha-mismatch"
    assert pre(task, rel, tool="Edit", old="no such text", new="x").kind == "allow"
    path.write_text(check_text(WRONG), encoding="utf-8", newline="")
    assert pre(task, rel, tool="Edit", old=f"sha256: {WRONG}", new=f"sha256: {right}").kind == "allow"
    assert pre(task, rel, tool="MultiEdit", edits=[(f"sha256: {WRONG}", f"sha256: {right}")]).kind == "allow"


def test_a_check_with_no_sha_line_or_a_second_wrong_one_is_refused(task):
    """E10: a check with no `sha256:` line, and a check with one right line and one wrong line, are refused; every sha
    line must be the document's. Catches: a forged check that hides a wrong digest next to a right one."""
    rel = f"{OUT}/a.md{SUFFIX}"
    none = pre(task, rel, check_text(WRONG, omit=("sha256",)))
    assert none.kind == "refuse" and none.reason_id == "check-sha-mismatch" and "sha256: " in none.message
    two = pre(task, rel, _good(task) + f"sha256: {WRONG}\n")
    assert two.kind == "refuse" and two.reason_id == "check-sha-mismatch"
    short = pre(task, rel, check_text("abc123"))
    assert short.kind == "refuse"


def test_a_check_of_a_missing_document_is_refused(task):
    """E10: a check file beside a document that does not exist is refused `check-sha-mismatch` and the text names the
    document; a check belongs to the text a reader read. Catches: a check written ahead of the text it will cover."""
    v = pre(task, f"{OUT}/none.md{SUFFIX}", check_text(WRONG))
    assert v.kind == "refuse" and v.reason_id == "check-sha-mismatch" and f"{OUT}/none.md" in v.message


def test_other_files_and_tools_are_not_this_gates(task, tmp_path):
    """E10: the document itself, a file in another folder with the check suffix, a file under the outbox folder that is
    not a check, a tool that is not a write tool, and a profile with no `outbox.dir` all pass. Catches: a gate that
    refuses writes it has no rule for."""
    assert pre(task, f"{OUT}/a.md", "new text\n").kind == "allow"
    assert pre(task, f"notes/a.md{SUFFIX}", check_text(WRONG)).kind == "allow"
    assert pre(task, f"{OUT}/readme.txt", "x").kind == "allow"
    assert pre(task, f"{OUT}/sub/b.md{SUFFIX}", check_text(WRONG)).kind == "refuse"  # nested: still the outbox
    from _engine import gate_call
    import gate_outbox
    v = gate_call(gate_outbox.check, task, tool="Bash", tool_input={"command": "echo x"})
    assert v.kind == "allow"
    bare = make_root(tmp_path / "bare", outbox=None)
    assert pre(bare, f"{OUT}/a.md{SUFFIX}", check_text(WRONG)).kind == "allow"


def _records(root):
    return jsonl(state_dir(root) / RECORDS)


def test_the_post_step_records_the_session_and_the_check_sha(task):
    """E11: after a write of a check file the post step appends one row to `outbox_checks.jsonl`: the kind, the document,
    the check file, the sha256 of the check file as it is on disk now, the hook's session id and the time; it never
    refuses. Catches: a proof that cannot tell which session wrote a check, or a sha taken from the tool input."""
    write_check(task, f"{OUT}/a.md", recorded=False)
    assert post(task, f"{OUT}/a.md{SUFFIX}", session="s7").kind == "allow"
    (row,) = _records(task)
    assert row["kind"] == "check-written" and row["doc"] == f"{OUT}/a.md" and row["check"] == f"{OUT}/a.md{SUFFIX}"
    assert row["check_sha"] == sha_of(Path(task) / f"{OUT}/a.md{SUFFIX}") and row["session"] == "s7"
    import datetime
    assert abs((datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(row["time"])
                ).total_seconds()) < 30
    post(task, f"{OUT}/a.md{SUFFIX}", tool="Edit", session="s8")
    assert [r["session"] for r in _records(task)] == ["s7", "s8"]


def test_the_post_step_ignores_other_files(task, tmp_path):
    """E11: the document, a file in another folder, a check file that was not written, another tool and a profile with
    no `outbox.dir` leave no row. Catches: a record for a write that never made a check."""
    write_check(task, f"{OUT}/a.md", recorded=False)
    post(task, f"{OUT}/a.md")
    post(task, f"notes/a.md{SUFFIX}")
    post(task, f"{OUT}/none.md{SUFFIX}")
    post(task, f"{OUT}/a.md{SUFFIX}", tool="Read")
    bare = make_root(tmp_path / "bare", outbox=None)
    write_doc(bare)
    (Path(bare) / f"{OUT}/a.md{SUFFIX}").write_text("x\n", encoding="utf-8")
    post(bare, f"{OUT}/a.md{SUFFIX}")
    assert _records(task) == [] and _records(bare) == []


def test_a_failed_record_is_a_warn_never_a_refusal(task, monkeypatch):
    """E11: when the record cannot be written the post step warns `check-record-failed` and says the check will read
    `unproven`; it never refuses, because the write already happened. Catches: a silent loss of the proof."""
    import outbox
    write_check(task, f"{OUT}/a.md", recorded=False)

    def boom(*args, **kwargs):
        raise OSError("disk")
    monkeypatch.setattr(outbox, "record_check", boom)
    v = post(task, f"{OUT}/a.md{SUFFIX}")
    assert v.kind == "warn" and v.reason_id == "check-record-failed" and "unproven" in v.message


def test_the_stop_reminder_names_a_file_changed_after_its_check(task):
    """E15: at Stop a file whose check is `stale` (the text changed after the check) gets a reminder line that names
    the file and `mkway outbox`; the verdict is a warn, never a refusal. Catches: a changed text that leaves the turn
    unremarked."""
    rel = valid_file(task, "b.md")
    write_doc(task, "b.md", "Changed after its check.\n", when=400)
    v = stop(task)
    assert v.kind == "warn" and v.reason_id == "outbox-changed-after-check"
    assert rel in v.message and "mkway outbox" in v.message and f"{OUT}/a.md" not in v.message


def test_the_stop_reminder_is_silent_and_never_blocks(task, tmp_path):
    """E15: a valid, a missing and an unproven file give no reminder; no `outbox.dir` gives none; a stale file gives a
    warn and never a refusal. Catches: a reminder that nags about files nobody has checked yet, or a Stop gate that
    traps the session."""
    valid_file(task, "ok.md")
    write_doc(task, "missing.md")
    valid_file(task, "unproven.md", agent=None, doc_when=500, check_when=900)
    assert stop(task).kind == "allow"
    bare = make_root(tmp_path / "bare", outbox=None)
    assert stop(bare).kind == "allow"
    write_doc(task, "ok.md", "Changed.\n", when=700)
    assert stop(task).kind == "warn"


def test_the_manifest_entries_of_the_outbox_check():
    """E16: `outbox_check.pre` (edit group, the three write tools, class form, reason `check-sha-mismatch`),
    `outbox_check.post` (post group, PostToolUse, `check-record-failed`, class integrity) and `outbox_check.stop` (stop
    group, `outbox-changed-after-check`, class integrity) are loaded entries on `gate_outbox:check`; the dispatcher
    only runs an entry with a function and reasons. Catches: a gate that is written but not wired."""
    (pre_e,), (post_e,), (stop_e,) = (_manifest(n) for n in ("outbox_check.pre", "outbox_check.post",
                                                              "outbox_check.stop"))
    for e in (pre_e, post_e, stop_e):
        assert e["function"] == "gate_outbox:check" and e["status"] == "on" and e["default_on"] is True
    assert (pre_e["group"], pre_e["event"], pre_e["matcher"], pre_e["class"]) == (
        "edit", "PreToolUse", "Edit|Write|MultiEdit", "form")
    assert pre_e["reason_ids"] == ["check-sha-mismatch"]
    assert (post_e["group"], post_e["event"], post_e["matcher"], post_e["class"]) == (
        "post", "PostToolUse", "Edit|Write|MultiEdit", "integrity")
    assert post_e["reason_ids"] == ["check-record-failed"]
    assert (stop_e["group"], stop_e["event"], stop_e["class"]) == ("stop", "Stop", "integrity")
    assert stop_e["reason_ids"] == ["outbox-changed-after-check"]
    names = [e["name"] for e in json.loads((dispatch.ENGINE_DIR / "manifest.json").read_text(encoding="utf-8"))[
        "entries"]]
    assert names.index("lock.edit") < names.index("outbox_check.pre")


def test_the_dispatcher_refuses_a_stale_check_write(task):
    """E16: through the dispatcher with the real entries, a Write of a check with a wrong sha is denied with
    `[mkway outbox_check.pre check-sha-mismatch]` and a row in the refusal log; the right sha passes; the Stop group
    reminds once for the session and the same set of files. Catches: a gate that works alone and not when wired."""
    manifest = _manifest("outbox_check.pre") + _manifest("outbox_check.stop")
    env = {"CLAUDE_PROJECT_DIR": str(task), "CLAUDECODE": "1"}
    rel = f"{OUT}/a.md{SUFFIX}"
    payload = {"session_id": "s1", "hook_event_name": "PreToolUse", "tool_name": "Write", "cwd": str(task),
               "tool_input": {"file_path": rel, "content": check_text(WRONG)}}
    res = dispatch.run("PreToolUse", "edit", json.dumps(payload), env=env, manifest=manifest)
    out = json.loads(res.stdout)["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny" and "[mkway outbox_check.pre check-sha-mismatch]" in (
        out["permissionDecisionReason"])
    assert [(r["gate"], r["reason_id"]) for r in refusal_rows(task)] == [("outbox_check.pre", "check-sha-mismatch")]
    payload["tool_input"]["content"] = _good(task)
    assert dispatch.run("PreToolUse", "edit", json.dumps(payload), env=env, manifest=manifest).stdout == ""
    valid_file(task, "b.md")
    write_doc(task, "b.md", "Changed after its check.\n", when=400)
    stop_payload = {"session_id": "s1", "hook_event_name": "Stop", "cwd": str(task)}
    first = dispatch.run("Stop", "stop", json.dumps(stop_payload), env=env, manifest=manifest)
    assert "outbox-changed-after-check" in first.stdout
    again = dispatch.run("Stop", "stop", json.dumps(stop_payload), env=env, manifest=manifest)
    assert "outbox-changed-after-check" not in again.stdout
