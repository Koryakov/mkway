"""Card MW-065: shell tests of the owner-ask and search gates. The shell reads the facts (the path as the engine reads it,
the sources file, the ask file, the transcript, the files that exist, the records, the profile's settings) from real files
in a synthetic task root and hands them to the pure decisions of `engine/core_ask.py`. One test id is one case. Each test
runs under the 20 s cap of the ruling of 2026-11-12. Everything is written under the test's temp root; no task data. The
decisions themselves are table tests in `tests/core/test_ask_decide.py`."""
import datetime
import json
import time

import pytest

from _engine import gate_call, task_root  # first: it puts the engine folder on the path
import gate_owner_ask
import gate_search
import records

CAP_SECONDS = 20.0
ASK = "mkway/asks/t_ask.md"
LOCK = "kind: lock\nchecked: commit lock closed\n"
REVIEW = "kind: substance\nreview: 0 contradictions\n> review: :27 «a verbatim line of the source»\n"
CANON = "canon: 1 contradictions\n> canon: D-1 «a verbatim line»\n"
COMPLETE = ("Which option?\ndefault: keep option A\ndeadline: 2099-01-01T10:00\nblocked: the report part\n"
            "reversible: yes\nstatus: open\n")


@pytest.fixture(autouse=True)
def _a_shell_test_takes_under_20_seconds():
    started = time.perf_counter()
    yield
    took = time.perf_counter() - started
    assert took < CAP_SECONDS, f"a shell test must run under {CAP_SECONDS:g} s; this one took {took:.1f} s"


def put(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="")
    return path


def verdict_id(v):
    return v.reason_id if v.kind != "allow" else "allow"


def write_ask(root, path=ASK, *, tool="Write", session="s1", text=COMPLETE):
    """The edit gate on one write of an ask; an Edit or a MultiEdit needs the file on disk, so it is made first."""
    if tool == "Write":
        tool_input = {"file_path": path, "content": text}
    else:
        if not (root / path).exists():
            put(root, path, text)
        edit = {"old_string": "status: open", "new_string": "status: open"}
        tool_input = {"file_path": path, "edits": [edit]} if tool == "MultiEdit" else {"file_path": path, **edit}
    return gate_call(gate_owner_ask.check, root, tool=tool, tool_input=tool_input, session=session)


def post_ask(root, path=ASK, *, tool="Write", session="s1"):
    return gate_call(gate_owner_ask.check, root, tool=tool, event="PostToolUse", session=session,
                     tool_input={"file_path": path, "content": "x"}, tool_response={"filePath": path, "success": True})


def rows_of_asks(root):
    return [(r["session_id"], r["value"]) for r in records.rows(root / "mkway" / "state") if r.get("kind") == "ask"]


@pytest.fixture
def task(tmp_path):
    root = task_root(tmp_path, owner_ask={"sources": ["review"]})
    return root


# ---- the edit gate: the path, the sources file, the profile -----------------------------------------------------------

@pytest.mark.parametrize("tool", ["Write", "Edit", "MultiEdit"])
def test_a_sources_file_that_is_not_on_disk_reads_as_missing(task, tool):
    """Catches: a session that asks without writing down what it checked. E5: an ask with no t_sources.md beside it on disk is refused ask-sources-missing by each write tool, and the text names the file."""
    v = write_ask(task, tool=tool)
    assert v.kind == "refuse"
    assert v.reason_id == "ask-sources-missing"
    assert "t_sources.md" in v.message


@pytest.mark.parametrize("tool", ["Write", "Edit", "MultiEdit"])
def test_a_sources_file_on_disk_of_a_kind_lets_the_ask_through(task, tool):
    """Checks: the same ask with its sources file on disk goes through. E5: the nearest allow, against a gate that cannot read a file it asked for."""
    put(task, "mkway/asks/t_sources.md", LOCK)
    assert write_ask(task, tool=tool).kind == "allow"


@pytest.mark.parametrize("spelling", [
    pytest.param(lambda root: str(root / "mkway" / "asks" / "t_ask.md"), id="absolute-path"),
    pytest.param(lambda root: "./mkway/asks/t_ask.md", id="dot-slash"),
    pytest.param(lambda root: "mkway\\asks\\t_ask.md", id="backslashes"),
    pytest.param(lambda root: "mkway/asks/t_ASK.MD", id="upper-case")])
def test_every_spelling_of_an_ask_path_is_found(task, spelling):
    """Catches: a gate bypassed by a path spelling. E5: the ask is found by every spelling of its path, and the sources file with no kind line is refused ask-sources-kind whatever the spelling."""
    put(task, "mkway/asks/t_sources.md", "no kind here\n")
    assert verdict_id(write_ask(task, spelling(task))) == "ask-sources-kind"


def test_a_path_outside_the_root_is_not_an_ask_path(task, tmp_path):
    """Checks: an ask-shaped path outside the task root is not the gate's, so it goes through. E4: a gate that reads it as an ask and blocks it is what this guards against."""
    assert verdict_id(write_ask(task, str(tmp_path / "elsewhere" / "mkway" / "asks" / "t_ask.md"))) == "allow"


def test_a_tool_that_does_not_write_is_not_the_edit_gates(task):
    """Checks: a Read of an ask with no sources file passes, so reads are never refused. E4: a gate that refuses reads is the failure."""
    v = gate_call(gate_owner_ask.check, task, tool="Read", tool_input={"file_path": ASK})
    assert v.kind == "allow"


def test_a_write_with_no_path_is_not_the_edit_gates(task):
    """Checks: a Write whose tool input carries no path passes. E4: a gate that crashes on a call with no path is the failure this guards against."""
    assert gate_call(gate_owner_ask.check, task, tool="Write", tool_input={"content": "x"}).kind == "allow"


def test_the_default_folder_is_not_gated_when_the_profile_moves_it(tmp_path):
    """Checks: with owner_ask.dir set in the profile, an ask in the default folder passes. E8: a folder hard-coded in the gate would refuse it."""
    root = task_root(tmp_path, owner_ask={"dir": "notes/asks", "sources": ["review", "canon"]})
    assert verdict_id(write_ask(root, "mkway/asks/t_ask.md")) == "allow"


def test_the_folder_of_the_profile_is_gated(tmp_path):
    """Catches: a profile key the gate does not read. E8: with owner_ask.dir set in the profile, an ask in that folder with no sources file is refused."""
    root = task_root(tmp_path, owner_ask={"dir": "notes/asks", "sources": ["review", "canon"]})
    assert verdict_id(write_ask(root, "notes/asks/t_ask.md")) == "ask-sources-missing"


def test_a_source_the_profile_lists_is_named_when_missing(tmp_path):
    """Catches: a source name that is hard-coded in the gate. E8: with sources review and canon in the profile and only review present on disk, the refusal names canon."""
    root = task_root(tmp_path, owner_ask={"dir": "notes/asks", "sources": ["review", "canon"]})
    put(root, "notes/asks/t_sources.md", REVIEW)
    v = write_ask(root, "notes/asks/t_ask.md")
    assert v.reason_id == "ask-sources-lines"
    assert "canon: N contradictions" in v.message


def test_every_source_the_profile_lists_present_lets_the_ask_through(tmp_path):
    """Checks: both listed sources on disk let the ask through. E8: the nearest allow, against a gate that asks for more than the profile lists."""
    root = task_root(tmp_path, owner_ask={"dir": "notes/asks", "sources": ["review", "canon"]})
    put(root, "notes/asks/t_sources.md", REVIEW + CANON)
    assert verdict_id(write_ask(root, "notes/asks/t_ask.md")) == "allow"


def test_a_folder_in_place_of_the_sources_file_is_refused_missing(task):
    """Catches: a gate that crashes on a hostile path, which would block every edit in the group. E9: a sources path that is a folder cannot be read and is refused ask-sources-missing, never an exception and never an allow."""
    (task / "mkway" / "asks" / "t_sources.md").mkdir(parents=True)
    assert verdict_id(write_ask(task)) == "ask-sources-missing"


def test_a_sources_file_that_is_not_utf8_text_is_refused_kind(task):
    """Catches: a gate that lets the ask through when it cannot read the proof. E9: a sources file whose bytes are not text decodes with replacement characters, so no kind line starts a line, and it is refused ask-sources-kind."""
    (task / "mkway" / "asks").mkdir(parents=True)
    (task / "mkway" / "asks" / "t_sources.md").write_bytes(b"\xff\xfe\x00kind: substance\n")
    assert verdict_id(write_ask(task)) == "ask-sources-kind"


# ---- the open asks of a session, the post step, the pop-up switch -----------------------------------------------------

def open_ask(root, name, *, session="s1", status="open"):
    put(root, f"mkway/asks/{name}_sources.md", LOCK)
    put(root, f"mkway/asks/{name}_ask.md", COMPLETE.replace("status: open", f"status: {status}"))
    if session:
        records.append(root / "mkway" / "state", session, "ask", name)


@pytest.fixture
def open_task(tmp_path):
    root = task_root(tmp_path)
    put(root, "mkway/asks/u_sources.md", LOCK)
    return root


def test_a_session_with_an_open_ask_is_refused_a_second_one(open_task):
    """Catches: one session that leaves five asks open and repeats one. E4: the session's ask record and its file with status open make a new ask by that session refused ask-already-open."""
    open_ask(open_task, "t")
    assert verdict_id(write_ask(open_task, "mkway/asks/u_ask.md")) == "ask-already-open"


def test_another_session_may_ask_while_one_has_an_open_ask(open_task):
    """Checks: another session may ask while one session has an open ask. E4: the nearest allow, the same new ask by another session, and a session blocked by another's ask is the failure."""
    open_ask(open_task, "t")
    assert verdict_id(write_ask(open_task, "mkway/asks/u_ask.md", session="s2")) == "allow"


def test_a_write_to_the_open_ask_itself_is_allowed(open_task):
    """Checks: an Edit of the ask already on disk is an addition, not a second ask, and is allowed. E4: a session that cannot add to its own open ask is the failure."""
    open_ask(open_task, "t")
    assert verdict_id(write_ask(open_task, ASK, tool="Edit")) == "allow"


@pytest.mark.parametrize("status", ["answered", "default-taken", "withdrawn"])
def test_an_ask_that_is_no_longer_open_frees_the_session(open_task, status):
    """Checks: a later status closes the ask and frees the session for its next ask. E4: the owner or a command sets answered, default-taken or withdrawn; a session blocked for good by an answered ask is the failure."""
    open_ask(open_task, "t", status=status)
    assert verdict_id(write_ask(open_task, "mkway/asks/u_ask.md")) == "allow"


def test_the_profile_allows_a_second_open_ask(tmp_path):
    """Checks: with owner_ask.max_open 2 a session with one open ask may write a second. E4: a limit that is hard-coded would refuse it."""
    root = task_root(tmp_path, owner_ask={"max_open": 2})
    put(root, "mkway/asks/u_sources.md", LOCK)
    open_ask(root, "t")
    assert verdict_id(write_ask(root, "mkway/asks/u_ask.md")) == "allow"


def test_the_profile_refuses_a_third_open_ask(tmp_path):
    """Catches: a limit that is hard-coded. E4: with owner_ask.max_open 2 a session with two open asks is refused a third."""
    root = task_root(tmp_path, owner_ask={"max_open": 2})
    put(root, "mkway/asks/v_sources.md", LOCK)
    open_ask(root, "t")
    open_ask(root, "u")
    assert verdict_id(write_ask(root, "mkway/asks/v_ask.md")) == "ask-already-open"


def test_a_call_with_no_session_id_is_never_refused_by_the_open_rule(open_task):
    """Checks: with no session id the one-open rule does not apply, so the write is allowed. E4: a crash or a refusal on a call with no session is the failure."""
    open_ask(open_task, "t")
    assert verdict_id(write_ask(open_task, "mkway/asks/u_ask.md", session=None)) == "allow"


def test_a_record_whose_ask_file_is_gone_counts_for_nothing(open_task):
    """Checks: a record of an ask whose file was deleted does not keep the session blocked. E4: a stale record that blocks the session for good is the failure."""
    open_ask(open_task, "t")
    (open_task / ASK).unlink()
    assert verdict_id(write_ask(open_task, "mkway/asks/u_ask.md")) == "allow"


def test_the_post_step_records_the_session_that_wrote_an_ask(open_task):
    """Checks: after an ask file is written the post step records the ask for the session. E4: an ask that nobody can name, so the one-open rule and the deadline reminder never find the session, is the failure."""
    put(open_task, ASK, COMPLETE)
    post_ask(open_task, session="s7")
    assert rows_of_asks(open_task) == [("s7", "t")]


@pytest.mark.parametrize("path", ["mkway/asks/t_sources.md", "work/x.md"])
def test_the_post_step_ignores_a_file_that_is_not_an_ask(open_task, path):
    """Checks: a write of the sources file or of another file leaves no ask record. E4: a record for a file that is not an ask is the failure."""
    put(open_task, path, "x")
    post_ask(open_task, path, session="s7")
    assert rows_of_asks(open_task) == []


def test_the_post_step_ignores_a_tool_that_does_not_write(open_task):
    """Checks: a Read of an ask leaves no record. E4: a record for a read is the failure."""
    put(open_task, ASK, COMPLETE)
    post_ask(open_task, tool="Read", session="s7")
    assert rows_of_asks(open_task) == []


@pytest.mark.parametrize("owner_ask, kind", [
    pytest.param({"tool_allowed": True}, "allow", id="allowed-by-the-profile"),
    pytest.param({"tool_allowed": False}, "refuse", id="off-by-the-profile"),
    pytest.param({}, "refuse", id="no-key-is-off")])
def test_the_pop_up_question_tool_follows_the_profile(tmp_path, owner_ask, kind):
    """Checks: owner_ask.tool_allowed true allows the pop-up tool, and false or a missing key refuses it. E5: a switch that does nothing is the failure this guards against."""
    root = task_root(tmp_path, owner_ask=owner_ask)
    assert gate_call(gate_owner_ask.check, root, tool="AskUserQuestion", tool_input={}).kind == kind


# ---- the stop gate: the transcript, the files on disk, the profile ----------------------------------------------------

USER = {"type": "user", "message": {"content": "a question"}}
ASKED = {"type": "assistant", "message": {"content": [{"type": "text", "text": "Request: x"}]}}


def tool_use(name, path):
    return {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": name,
                                                          "input": {"file_path": path, "content": "x"}}]}}


def transcript(tmp_path, entries):
    path = tmp_path / "transcript.jsonl"
    path.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n", encoding="utf-8")
    return str(path)


def stop(root, tmp_path, entries, last=None):
    hook_input = {"hook_event_name": "Stop", "stop_hook_active": False, "transcript_path": transcript(tmp_path, entries)}
    if last is not None:
        hook_input["last_assistant_message"] = last
    return gate_call(gate_owner_ask.check, root, tool=None, event="Stop", hook_input=hook_input)


@pytest.fixture
def stop_task(tmp_path):
    root = task_root(tmp_path / "t")
    put(root, ASK, "an ask\n")
    return root


@pytest.mark.parametrize("spelling", [
    pytest.param(lambda root: str(root / "mkway" / "asks" / "t_ask.md"), id="absolute-path"),
    pytest.param(lambda root: "mkway\\asks\\t_ask.md", id="backslashes")])
def test_an_ask_file_on_disk_counts_as_written_in_any_spelling(stop_task, tmp_path, spelling):
    """Checks: a write of an ask file counts when the file is on disk now, whatever the spelling of the path in the transcript. E12: a session blocked although it wrote its ask is the failure."""
    assert verdict_id(stop(stop_task, tmp_path, [USER, tool_use("Write", spelling(stop_task)), ASKED])) == "allow"


def test_a_write_whose_file_is_not_on_disk_does_not_count(stop_task, tmp_path):
    """Catches: a session that passes the stop gate with a refused write. E12: a write of an ask file that is not on disk, because the edit gate refused it, does not count and gives ask-not-written."""
    gone = str(stop_task / "mkway" / "asks" / "gone_ask.md")
    assert verdict_id(stop(stop_task, tmp_path, [USER, tool_use("Write", gone), ASKED])) == "ask-not-written"


@pytest.mark.parametrize("other", ["notes/t_ask.md", "mkway/asks/t_check.md", "mkway/asks/sub/t_ask.md"])
def test_a_write_to_a_look_alike_path_does_not_count(stop_task, tmp_path, other):
    """Catches: a session that passes the stop gate with a write to another path. E12: a write of a look-alike file that is on disk does not count."""
    put(stop_task, other, "x")
    assert verdict_id(stop(stop_task, tmp_path, [USER, tool_use("Write", str(stop_task / other)), ASKED])) \
        == "ask-not-written"


@pytest.fixture
def notes_task(tmp_path):
    root = task_root(tmp_path / "t", owner_ask={"dir": "notes/asks", "markers": ["Ask:", "Q:"]})
    put(root, "notes/asks/t_ask.md", "an ask\n")
    return root


def test_the_default_marker_is_no_marker_when_the_profile_lists_others(notes_task, tmp_path):
    """Catches: a marker hard-coded in the gate. E13: owner_ask.markers replaces the marker, so Request is then no marker."""
    assert verdict_id(stop(notes_task, tmp_path, [USER], last="Request: x")) == "allow"


@pytest.mark.parametrize("last", ["Ask: x", "Q: x"])
def test_a_marker_the_profile_lists_needs_an_ask_file(notes_task, tmp_path, last):
    """Catches: a marker or a folder hard-coded in the gate. E13: every listed marker is a marker, and the refusal names the profile's folder."""
    v = stop(notes_task, tmp_path, [USER], last=last)
    assert v.reason_id == "ask-not-written"
    assert "notes/asks/<name>_ask.md" in v.message


def test_an_ask_written_in_the_profiles_folder_counts(notes_task, tmp_path):
    """Checks: an ask written in the profile's folder counts, the nearest allow. E13: a folder hard-coded in the gate would refuse it."""
    written = tool_use("Write", str(notes_task / "notes" / "asks" / "t_ask.md"))
    assert verdict_id(stop(notes_task, tmp_path, [USER, written], last="Q: x")) == "allow"


def test_an_ask_written_in_the_default_folder_does_not_count_when_the_profile_moves_it(notes_task, tmp_path):
    """Catches: a folder hard-coded in the gate. E13: with the folder moved, an ask file in the default folder does not count."""
    put(notes_task, ASK, "an ask\n")
    elsewhere = tool_use("Write", str(notes_task / "mkway" / "asks" / "t_ask.md"))
    assert verdict_id(stop(notes_task, tmp_path, [USER, elsewhere], last="Q: x")) == "ask-not-written"


def hook(tmp_path, **extra):
    return {"hook_event_name": "Stop", "stop_hook_active": False, "transcript_path": str(tmp_path / "gone.jsonl"), **extra}


def test_a_transcript_that_is_not_there_blocks_a_marker_and_says_so(stop_task, tmp_path):
    """Catches: a gate that crashes on a missing transcript, or hides why. E14: with no transcript file the gate still reads last_assistant_message: a marker line is blocked and the text says the transcript could not be read."""
    v = gate_call(gate_owner_ask.check, stop_task, tool=None, event="Stop",
                  hook_input=hook(tmp_path, last_assistant_message="Request: x"))
    assert v.reason_id == "ask-not-written"
    assert "transcript could not be read" in v.message


def test_a_transcript_that_is_not_there_allows_a_reply_with_no_marker(stop_task, tmp_path):
    """Checks: with no marker and no transcript a reply is allowed. E14: the nearest allow, against a gate that blocks a reply that has no marker."""
    v = gate_call(gate_owner_ask.check, stop_task, tool=None, event="Stop",
                  hook_input=hook(tmp_path, last_assistant_message="Info: x"))
    assert v.kind == "allow"


def test_no_message_and_no_transcript_leaves_nothing_to_check(stop_task, tmp_path):
    """Checks: with neither a message nor a transcript there is nothing to check. E14: a gate that crashes with no input is the failure."""
    assert gate_call(gate_owner_ask.check, stop_task, tool=None, event="Stop", hook_input=hook(tmp_path)).kind == "allow"


def test_a_hook_input_that_is_not_a_record_leaves_nothing_to_check(stop_task):
    """Checks: a hook input that is not a record is read as empty and allowed. E14: a gate that crashes on a hostile hook input is the failure."""
    assert gate_call(gate_owner_ask.check, stop_task, tool=None, event="Stop", hook_input=None).kind == "allow"


def test_lines_of_a_transcript_that_are_not_json_are_skipped(stop_task, tmp_path):
    """Checks: a transcript with bad lines is read from its good lines, and the ask written after the user message counts. E14: a gate that crashes on, or gives up at, one bad line is the failure."""
    path = tmp_path / "bad.jsonl"
    wrote = tool_use("Write", str(stop_task / "mkway" / "asks" / "t_ask.md"))
    path.write_text("not json\n" + json.dumps(USER) + "\n{broken\n" + json.dumps(wrote) + "\n" + json.dumps(ASKED) + "\n",
                    encoding="utf-8")
    v = gate_call(gate_owner_ask.check, stop_task, tool=None, event="Stop",
                  hook_input={"stop_hook_active": False, "transcript_path": str(path)})
    assert v.kind == "allow"


# ---- the search gate: the transcript, the records, the paths ----------------------------------------------------------

BASE = datetime.datetime(2026, 11, 10, 12, 0, 0, tzinfo=datetime.timezone.utc)
QUESTION = "notes/questions/q1.md"


def at(seconds):
    return (BASE + datetime.timedelta(seconds=seconds)).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def user_at(seconds):
    return {"type": "user", "message": {"content": "a question"}, "timestamp": at(seconds)}


def record_at(root, seconds, session="s1"):
    row = {"session_id": session, "kind": "search", "value": "S-1", "time": at(seconds).replace("Z", "+00:00"),
           "by": "session"}
    with open(root / "mkway" / "state" / "records.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def ask_user(root, tmp_path, entries, tool="AskUserQuestion", tool_input=None, session="s1"):
    hook_input = {"hook_event_name": "PreToolUse", "transcript_path": transcript(tmp_path, entries)}
    return gate_call(gate_search.check, root, tool=tool, tool_input=tool_input or {"questions": []}, session=session,
                     hook_input=hook_input)


@pytest.fixture
def search_task(tmp_path):
    return task_root(tmp_path / "t", questions={"files": ["notes/questions/**", "mkway/q_*.md"]})


def test_a_question_with_no_record_on_disk_is_refused(search_task, tmp_path):
    """Catches: a question that goes to the owner before any search. E12: with a transcript file and no search record in the state folder the question is refused search-missing."""
    assert verdict_id(ask_user(search_task, tmp_path, [user_at(0)])) == "search-missing"


def test_a_record_on_disk_after_the_user_message_lets_the_question_through(search_task, tmp_path):
    """Checks: a search record of this session after the last user message lets the question through. E12: the nearest allow, against a gate that cannot read the records it asks for."""
    record_at(search_task, 30)
    assert verdict_id(ask_user(search_task, tmp_path, [user_at(0)])) == "allow"


def test_a_record_on_disk_before_the_user_message_does_not_count(search_task, tmp_path):
    """Catches: a search of an earlier turn that lets this turn's question through. E13: a record older than the last real user message in the transcript does not count."""
    record_at(search_task, -30)
    assert verdict_id(ask_user(search_task, tmp_path, [user_at(0)])) == "search-missing"


def test_a_record_of_another_session_on_disk_does_not_count(search_task, tmp_path):
    """Catches: one session's search that covers another session's question. E13: another session's record in the state folder does not count."""
    record_at(search_task, 30, session="other")
    assert verdict_id(ask_user(search_task, tmp_path, [user_at(0)])) == "search-missing"


@pytest.mark.parametrize("tool", ["Write", "Edit", "MultiEdit"])
@pytest.mark.parametrize("spelling", [
    pytest.param(lambda root: QUESTION, id="relative"),
    pytest.param(lambda root: "./notes/questions/sub/q1.md", id="dot-slash-nested"),
    pytest.param(lambda root: "mkway/q_a.md", id="second-glob"),
    pytest.param(lambda root: str(root / QUESTION), id="absolute-path"),
    pytest.param(lambda root: "notes\\questions\\q1.md", id="backslashes")])
def test_a_write_to_a_question_file_is_gated_in_every_spelling(search_task, tmp_path, spelling, tool):
    """Catches: a question file written with no search because of a path spelling. E14: a Write, Edit or MultiEdit of a path that matches a glob of questions.files is gated in any spelling of the path."""
    path = spelling(search_task)
    v = ask_user(search_task, tmp_path, [user_at(0)], tool=tool, tool_input={"file_path": path, "content": "x"})
    assert v.kind == "refuse"
    assert v.reason_id == "search-missing"


def test_a_question_file_path_outside_the_root_is_not_gated(search_task, tmp_path):
    """Checks: a path outside the root that looks like a question file is not gated. E14: a gate that reads it as a question file is the failure."""
    outside = str(tmp_path / "elsewhere" / QUESTION)
    assert verdict_id(ask_user(search_task, tmp_path, [user_at(0)], tool="Write",
                               tool_input={"file_path": outside})) == "allow"


def test_with_no_question_files_in_the_profile_a_write_is_not_gated(tmp_path):
    """Checks: a profile with no questions.files gates no write. E14: a gate that invents a path of its own is the failure."""
    bare = task_root(tmp_path / "bare")
    assert verdict_id(ask_user(bare, tmp_path, [user_at(0)], tool="Write", tool_input={"file_path": QUESTION})) == "allow"


def test_with_no_question_files_in_the_profile_the_question_tool_is_still_gated(tmp_path):
    """Catches: a profile with no files that turns the search gate off for questions. E14: AskUserQuestion is gated whatever the profile lists."""
    bare = task_root(tmp_path / "bare")
    assert verdict_id(ask_user(bare, tmp_path, [user_at(0)])) == "search-missing"


@pytest.mark.parametrize("hook_input", [
    pytest.param(lambda tmp: {"hook_event_name": "PreToolUse"}, id="no-transcript-path"),
    pytest.param(lambda tmp: {"transcript_path": str(tmp)}, id="a-folder-in-place-of-the-transcript"),
    pytest.param(lambda tmp: {"transcript_path": str(tmp / "none.jsonl")}, id="a-transcript-that-is-not-there")])
def test_a_transcript_that_cannot_be_read_is_a_log_row_never_a_refusal(search_task, tmp_path, hook_input):
    """Catches: a gate that blocks every question when its own reading fails. E15: when the transcript cannot be read the gate allows and returns a log verdict search-unverified."""
    record_at(search_task, 30)
    v = gate_call(gate_search.check, search_task, tool="AskUserQuestion", tool_input={}, session="s1",
                  hook_input=hook_input(tmp_path))
    assert v.kind == "log"
    assert v.reason_id == "search-unverified"


def test_a_user_message_with_no_time_is_a_log_row_never_a_refusal(search_task, tmp_path):
    """Catches: a gate that blocks a question because the transcript has no time. E15: a last user message with no time leaves no turn boundary, so search-unverified."""
    record_at(search_task, 30)
    v = ask_user(search_task, tmp_path, [{"type": "user", "message": {"content": "a question"}}])
    assert v.kind == "log"
    assert v.reason_id == "search-unverified"


def test_a_call_with_no_session_id_is_a_log_row_never_a_refusal(search_task, tmp_path):
    """Catches: a gate that blocks a question because the hook gave no session. E15: with no session id no record can be matched, so search-unverified."""
    v = ask_user(search_task, tmp_path, [user_at(0)], session=None)
    assert v.kind == "log"
    assert v.reason_id == "search-unverified"
