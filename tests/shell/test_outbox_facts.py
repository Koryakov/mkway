"""Card MW-065: shell tests of the outbox check gate. The shell reads the facts (the path as the engine reads it, the
document's sha256, the check file on disk, the state of every file under the outbox folder) from real files in a
synthetic task root, hands them to the pure decisions of `engine/core_ask.py`, and writes the record of a write. One test
id is one case. Each test runs under the 20 s cap of the ruling of 2026-11-12. Everything is written under the test's temp
root. The decisions themselves are table tests in `tests/core/test_ask_decide.py`. `_mw019` is the shared fixture builder
(roots, documents, checks, agent rows), not a test module."""
import datetime
import time
from pathlib import Path

import pytest

from _engine import gate_call, jsonl  # first: it puts the engine folder on the path
from _mw019 import (OUT, RECORDS, SUFFIX, check_text, make_root, post, pre, sha_of, state_dir, stop, valid_file,
                    write_check, write_doc)
import gate_outbox

CAP_SECONDS = 20.0
WRONG = "0" * 64
CHECK = f"{OUT}/a.md{SUFFIX}"


@pytest.fixture(autouse=True)
def _a_shell_test_takes_under_20_seconds():
    started = time.perf_counter()
    yield
    took = time.perf_counter() - started
    assert took < CAP_SECONDS, f"a shell test must run under {CAP_SECONDS:g} s; this one took {took:.1f} s"


@pytest.fixture
def task(tmp_path):
    root = make_root(tmp_path)
    write_doc(root)  # outbox/a.md
    return root


def right(root):
    return sha_of(Path(root) / f"{OUT}/a.md")


def on_disk(root, text):
    (Path(root) / CHECK).write_text(text, encoding="utf-8", newline="")


def records_of(root):
    return jsonl(state_dir(root) / RECORDS)


# ---- the write gate: the document's sha256 and the check file on disk -------------------------------------------------

def test_a_check_with_the_sha_of_the_document_on_disk_is_allowed(task):
    """Checks: a Write of a check with the document's sha256 passes; catches a gate that cannot hash it (E10)."""
    assert pre(task, CHECK, check_text(right(task))).kind == "allow"


def test_a_check_with_another_sha_is_refused_and_gives_the_line_to_write(task):
    """Catches: a check written for text that has changed; the refusal gives the real document's sha256 (E10)."""
    v = pre(task, CHECK, check_text(WRONG))
    assert v.kind == "refuse"
    assert v.reason_id == "check-sha-mismatch"
    assert f"sha256: {right(task)}" in v.message


def test_an_edit_that_keeps_the_right_sha_of_the_check_on_disk_is_allowed(task):
    """Checks: an Edit is judged on the check file on disk after the edit; catches a gate that judges the tool input (E10)."""
    on_disk(task, check_text(right(task)))
    assert pre(task, CHECK, tool="Edit", old="links: clean", new="links: clean, 3 links").kind == "allow"


def test_a_multiedit_that_keeps_the_right_sha_of_the_check_on_disk_is_allowed(task):
    """Checks: a MultiEdit is judged on the check file on disk after the edit; catches a gate that judges the tool input (E10)."""
    on_disk(task, check_text(right(task)))
    assert pre(task, CHECK, tool="MultiEdit", edits=[("links: clean", "links: clean")]).kind == "allow"


def test_an_edit_that_turns_the_sha_wrong_is_refused_although_the_file_on_disk_was_right(task):
    """Catches: an Edit judged on its result, not on the old file; a right file edited to a wrong sha is refused (E10)."""
    on_disk(task, check_text(right(task)))
    v = pre(task, CHECK, tool="Edit", old=f"sha256: {right(task)}", new=f"sha256: {WRONG}")
    assert v.kind == "refuse"
    assert v.reason_id == "check-sha-mismatch"


def test_an_edit_of_a_check_after_the_document_changed_is_refused(task):
    """Catches: a stale check, right for the old text, that can still be edited into a pass (E10)."""
    on_disk(task, check_text(right(task)))
    write_doc(task, "a.md", "Changed after the check.\n")
    assert pre(task, CHECK, tool="Edit", old="links: clean", new="links: clean").kind == "refuse"


def test_a_check_of_a_document_that_is_not_on_disk_is_refused_and_names_it(task):
    """Catches: a check written ahead of the text it covers; the refusal names the missing document (E10)."""
    v = pre(task, f"{OUT}/none.md{SUFFIX}", check_text(WRONG))
    assert v.kind == "refuse"
    assert v.reason_id == "check-sha-mismatch"
    assert f"{OUT}/none.md" in v.message


def test_a_nested_check_is_still_the_outboxs(task):
    """Catches: a nested folder under outbox.dir that escapes the gate (E10)."""
    assert pre(task, f"{OUT}/sub/b.md{SUFFIX}", check_text(WRONG)).kind == "refuse"


def test_the_document_itself_is_not_a_check(task):
    """Checks: a Write of the document itself passes; catches a gate that blocks the document it protects (E10)."""
    assert pre(task, f"{OUT}/a.md", "new text\n").kind == "allow"


def test_a_check_name_in_another_folder_is_not_the_outboxs(task):
    """Checks: a file with the check suffix outside outbox.dir passes; catches a gate that reads the suffix alone (E10)."""
    assert pre(task, f"notes/a.md{SUFFIX}", check_text(WRONG)).kind == "allow"


def test_a_tool_that_does_not_write_is_not_the_outbox_gates(task):
    """Checks: a shell tool passes the outbox gate; catches a gate that refuses calls it has no rule for (E10)."""
    assert gate_call(gate_outbox.check, task, tool="Bash", tool_input={"command": "echo x"}).kind == "allow"


def test_a_profile_with_no_outbox_dir_gates_nothing(tmp_path):
    """Checks: with no outbox.dir a check write passes; catches a folder invented by the engine (E10)."""
    bare = make_root(tmp_path / "bare", outbox=None)
    assert pre(bare, CHECK, check_text(WRONG)).kind == "allow"


# ---- the post step: the record of a write -----------------------------------------------------------------------------

def test_the_post_step_records_the_check_and_its_session(task):
    """Checks: the post step appends one row with kind, document, check, sha256 on disk, session and time; catches a proof that cannot tell which session wrote a check, or a sha taken from the tool input (E11)."""
    write_check(task, f"{OUT}/a.md", recorded=False)
    assert post(task, CHECK, session="s7").kind == "allow"
    (row,) = records_of(task)
    age = (datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(row["time"])).total_seconds()
    assert (row["kind"], row["doc"], row["check"], row["check_sha"], row["session"]) == (
        "check-written", f"{OUT}/a.md", CHECK, sha_of(Path(task) / CHECK), "s7")
    assert abs(age) < 30


def test_a_second_write_by_another_session_is_a_second_row(task):
    """Checks: each write of the check file is a row of its own with its own session; catches a row overwritten so the first writer is lost (E11)."""
    write_check(task, f"{OUT}/a.md", recorded=False)
    post(task, CHECK, session="s7")
    post(task, CHECK, tool="Edit", session="s8")
    assert [r["session"] for r in records_of(task)] == ["s7", "s8"]


@pytest.mark.parametrize("path", [f"{OUT}/a.md", f"notes/a.md{SUFFIX}", f"{OUT}/none.md{SUFFIX}"],
                         ids=["the-document", "a-check-name-in-another-folder", "a-check-that-was-not-written"])
def test_the_post_step_leaves_no_row_for_a_file_that_is_not_a_written_check(task, path):
    """Checks: the document, a check-suffixed file in another folder and a check not on disk leave no row; catches a record for a write that never made a check (E11)."""
    write_check(task, f"{OUT}/a.md", recorded=False)
    post(task, path)
    assert records_of(task) == []


def test_the_post_step_leaves_no_row_for_a_tool_that_does_not_write(task):
    """Checks: a Read of a check file leaves no row; catches a record for a read (E11)."""
    write_check(task, f"{OUT}/a.md", recorded=False)
    post(task, CHECK, tool="Read")
    assert records_of(task) == []


def test_the_post_step_leaves_no_row_when_the_profile_has_no_outbox_dir(tmp_path):
    """Checks: with no outbox.dir a check-shaped file leaves no row; catches a record under a folder the profile never named (E11)."""
    bare = make_root(tmp_path / "bare", outbox=None)
    write_doc(bare)
    (Path(bare) / CHECK).write_text("x\n", encoding="utf-8")
    post(bare, CHECK)
    assert records_of(bare) == []


def test_a_failed_record_is_a_warn_that_says_the_check_will_read_unproven(task, monkeypatch):
    """Catches: a silent loss of the proof; a failed record refuses check-record-failed, names the path the engine could not write and says the check reads unproven (E11, R271c-D1)."""
    import outbox
    write_check(task, f"{OUT}/a.md", recorded=False)

    def boom(*args, **kwargs):
        raise OSError("disk")
    monkeypatch.setattr(outbox, "record_check", boom)
    v = post(task, CHECK)
    assert v.kind == "refuse"
    assert v.reason_id == "check-record-failed"
    assert "unproven" in v.message
    assert RECORDS in v.message


# ---- the Stop reminder: the state of every file under the outbox folder -----------------------------------------------

def test_a_file_changed_after_its_check_gets_a_reminder_that_names_it(task):
    """Checks: a stale file is named with mkway outbox in a warn, never a refusal, so a changed text does not go unremarked (E15)."""
    rel = valid_file(task, "b.md")
    write_doc(task, "b.md", "Changed after its check.\n", when=400)
    v = stop(task)
    assert v.kind == "warn"
    assert v.reason_id == "outbox-changed-after-check"
    assert rel in v.message
    assert "mkway outbox" in v.message
    assert f"{OUT}/a.md" not in v.message


def test_a_valid_file_gives_no_reminder(task):
    """Checks: the nearest allow, a document with a valid check gives no reminder; catches a reminder that nags about a file that is fine (E15)."""
    valid_file(task, "ok.md")
    assert stop(task).kind == "allow"


def test_a_file_with_no_check_gives_no_reminder(task):
    """Checks: a document whose check is missing is not stale; catches a reminder about files nobody has checked yet (E15)."""
    write_doc(task, "missing.md")
    assert stop(task).kind == "allow"


def test_a_check_with_no_proof_of_a_fresh_reader_gives_no_reminder(task):
    """Checks: a check that reads unproven is not stale; catches a reminder about a file whose check has no proof, which is another state (E15)."""
    valid_file(task, "unproven.md", agent=None, doc_when=500, check_when=900)
    assert stop(task).kind == "allow"


def test_a_profile_with_no_outbox_dir_gives_no_reminder(tmp_path):
    """Checks: with no outbox.dir there is nothing to remind; catches a Stop gate that fails on a profile with no outbox (E15)."""
    assert stop(make_root(tmp_path / "bare", outbox=None)).kind == "allow"
