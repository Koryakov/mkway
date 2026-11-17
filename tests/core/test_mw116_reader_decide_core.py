"""Card MW-116: the decision of the reader's allowlist hook (`reader_allow.decide`) and the guard fact of `verdict add`
(`core_verdict_add`). Pure: no file, no process, no clock. Synthetic paths, sessions and agents only."""
import os

import pytest

import _engine  # noqa: F401  (puts the engine folder on the import path)
import core_verdict_add as add
import reader_allow

BASE = os.path.abspath(os.sep + "work")
TEST_FILE = os.path.join(BASE, "tests", "test_a.py")
EXTRACT = os.path.join(BASE, "state", "reader_allow", "s1.extract.md")
CARD_FILE = os.path.join(BASE, "cards", "CARD-001", "CARD.md")
DOC = {"session_id": "s1", "card": "CARD-001", "files": [TEST_FILE, EXTRACT], "checkers": ["fresh-reader"]}


def call(tool, tool_input, *, session="s1", cwd=BASE):
    return {"session_id": session, "agent_id": "a1", "agent_type": "fresh-reader", "tool_name": tool,
            "tool_input": tool_input, "cwd": cwd}


def test_a_listed_file_is_read():
    """Catches: a Read of a file on the list refused, so the reader cannot read its two inputs."""
    for path in (TEST_FILE, EXTRACT):
        got = reader_allow.decide(call("Read", {"file_path": path}), DOC)
        assert (got.allowed, got.path) == (True, path)


def test_a_relative_path_is_judged_against_the_hook_cwd():
    """Catches: a relative path compared as written, so a listed file named with `..` or a relative form is refused."""
    got = reader_allow.decide(call("Read", {"file_path": os.path.join("tests", "..", "tests", "test_a.py")}), DOC)
    assert (got.allowed, got.path) == (True, TEST_FILE)


def test_a_search_of_a_listed_file_is_allowed():
    """Catches: Grep refused although its path is a listed file (nearest allow of the unlisted Grep rows)."""
    got = reader_allow.decide(call("Grep", {"pattern": "x", "path": TEST_FILE}), DOC)
    assert got.allowed is True


@pytest.mark.parametrize("path", [
    pytest.param(os.path.join(BASE, "tests", "test_b.py"), id="other-test-file"),
    pytest.param(CARD_FILE, id="card-file"),
    pytest.param(os.path.join(BASE, "tests", "..", "engine", "core.py"), id="parent-escape"),
    pytest.param(os.path.join(BASE, "tests"), id="folder-of-a-listed-file"),
    pytest.param(TEST_FILE + ".bak", id="name-with-a-suffix"),
])
def test_an_unlisted_read_is_refused(path):
    """Catches: a Read of an unlisted path, the card file included, going through; the refusal names the cause and
    the listed files as the way out."""
    got = reader_allow.decide(call("Read", {"file_path": path}), DOC)
    assert got.allowed is False
    assert "reader-read-refused" in got.text
    assert "unlisted path" in got.text
    assert TEST_FILE in got.text and EXTRACT in got.text


@pytest.mark.parametrize("tool_input", [
    pytest.param({"pattern": "x", "path": os.path.join(BASE, "tests", "test_b.py")}, id="other-file"),
    pytest.param({"pattern": "x"}, id="no-path"),
    pytest.param({"pattern": "x", "path": os.path.join(BASE, "tests")}, id="folder"),
    pytest.param({"pattern": "x", "path": CARD_FILE}, id="card-file"),
])
def test_an_unlisted_search_is_refused(tool_input):
    """Catches: a Grep with no path (it would search the whole working folder) or with an unlisted path going through."""
    got = reader_allow.decide(call("Grep", tool_input), DOC)
    assert got.allowed is False
    assert "reader-read-refused" in got.text and "unlisted path" in got.text


@pytest.mark.parametrize("tool", ["Bash", "PowerShell", "Edit", "Write", "MultiEdit", "Glob", "WebFetch", "Agent",
                                  "mcp__x__y"])
def test_any_other_tool_is_refused(tool):
    """Catches: a tool other than Read, Grep and the handback going through, e.g. Glob listing the folder."""
    got = reader_allow.decide(call(tool, {"file_path": TEST_FILE}), DOC)
    assert got.allowed is False
    assert "unlisted tool" in got.text and "reader-read-refused" in got.text


def test_the_handback_is_always_allowed():
    """Catches: the reader unable to answer because its report tool is refused (SubagentHandback, hooks.md)."""
    assert reader_allow.decide(call("SubagentHandback", {"message": "true"}), DOC).allowed is True
    assert reader_allow.decide(call("SubagentHandback", {"message": "true"}), None).allowed is True


@pytest.mark.parametrize("doc, session", [
    pytest.param(None, "s1", id="no-file"),
    pytest.param({**DOC, "files": []}, "s1", id="list-emptied"),
    pytest.param(DOC, "s2", id="file-of-another-session"),
    pytest.param({"files": [TEST_FILE]}, "s1", id="file-with-no-session"),
])
def test_no_usable_allow_file_for_the_session_refuses_every_read(doc, session):
    """Catches: a read passing when the session has no allow file, an emptied one or another session's (fail closed);
    the way out is the reader-start command."""
    got = reader_allow.decide(call("Read", {"file_path": TEST_FILE}, session=session), doc)
    assert got.allowed is False
    assert "no allow file" in got.text and "reader-read-refused" in got.text and "mkway reader start" in got.text


def test_the_crash_text_names_the_cause():
    """Catches: a crash refusal with no cause or no way out."""
    text = reader_allow.crash_text("ValueError")
    assert "reader-read-refused" in text and "crash" in text and "ValueError" in text and "mkway reader start" in text


def _facts(**over):
    node = add.Node("tests/test_a.py::test_one", True, frozenset(), "c1", "b1", "b1", ("r1",), ("r1",), (), None)
    over.setdefault("red_proven", True)  # MW-117 sync: a card with no red-proof row is refused first; these rows are about the guard
    return add.Facts(caller="s1", status="waiting", nodes=(node,), mode=over.pop("mode", ""), **over)


def test_a_run_with_no_guard_record_is_refused_unguarded():
    """Catches: a verdict row written for a reader run the guard never saw."""
    got = add.decide(_facts(guard={"r1": "no record row of the allowlist hook"}))
    assert [r.reason for r in got.refusals] == ["verdict-reader-unguarded"]
    assert "no record row of the allowlist hook" in got.refusals[0].text


def test_a_guarded_run_passes():
    """Checks: the nearest allow: the same facts with no guard problem for the run give the verdict its run."""
    got = add.decide(_facts(guard={"r1": ""}, guard_sha={"r1": "ab" * 32}))
    assert (got.allowed, got.run) == (True, "r1")


def test_the_unguarded_refusal_holds_in_watch_mode_too():
    """Catches: watch mode letting an unguarded reader through (it decides the independence of the verdict)."""
    got = add.decide(_facts(guard={"r1": "no record"}, mode="watch"))
    assert [r.reason for r in got.refusals] == ["verdict-reader-unguarded"]
