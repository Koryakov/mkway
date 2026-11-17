"""Card MW-116: the reader-start step writes the allow file of the spawning session, one run at a time per session, and the end
of the reader's run (the SubagentStop record, or `mkway reader end`) empties it. A real small task root (synthetic sessions,
agents and files under tmp_path); the end of a run goes through the real dispatcher."""
import hashlib
import json

import pytest

import _engine  # noqa: F401  (puts the engine folder on the import path)
import dispatch
import reader_allow
import verdicts
from _mw116 import CARD, CHECKER, FILE, OTHER_FILE, SESSION, allow_doc, card_text, make_world, profile_of, runs_rows, start
from _mw116 import state_of
from _mw080 import N1, N2, N3, B1


@pytest.fixture
def world(tmp_path):
    return make_world(tmp_path)


def _names(doc):
    return sorted(p.replace("\\", "/").rpartition("/")[2] for p in doc["files"])


def test_the_allow_file_lists_the_test_files_and_the_extract_and_never_the_card(world):
    """Catches: the card file (or any other path) on the list: the reader reads the test files of the card's nodes and the
    engine-written extract, nothing else."""
    doc = start(world)
    assert _names(doc) == sorted(["test_a.py", "test_b.py", f"{SESSION}.extract.md"])
    assert not any(p.replace("\\", "/").endswith("CARD.md") for p in doc["files"])
    assert doc == allow_doc(world)
    assert (doc["session_id"], doc["card"], doc["checkers"]) == (SESSION, CARD, [CHECKER])


def test_the_extract_holds_the_acceptance_rows_of_the_named_nodes_only(world):
    """Catches: the card's goal, its log or a row that names no test node reaching the reader through the extract."""
    import cardtool
    path = cardtool.card_file(world, profile_of(world), CARD)
    text = path.read_text(encoding="utf-8")
    text = text.replace("## Acceptance examples", "## 1. Goal\n\nGOAL-MARKER words of the owner\n\n## Acceptance examples")
    text = text.replace("| E4 |", "| E5 | item five | was | must | checked by reading: README.md |\n| E4 |")
    text += "| 2026-11-16 | step | none | LOG-MARKER result |\n"
    path.write_text(text, encoding="utf-8")
    doc = start(world)
    extract = next(p for p in doc["files"] if p.endswith(".extract.md"))
    body = open(extract, encoding="utf-8").read()
    for node in (N1, N2, N3, B1):
        assert node in body
    assert "GOAL-MARKER" not in body and "LOG-MARKER" not in body and "README.md" not in body


def test_the_extract_is_the_one_function_of_the_verdicts_module(world):
    """Catches: a second copy of the extract: the file holds what `verdicts.acceptance_extract` gives for the card."""
    doc = start(world)
    extract = next(p for p in doc["files"] if p.endswith(".extract.md"))
    assert open(extract, encoding="utf-8").read() == verdicts.acceptance_extract(card_text(world), [N1, N2, N3, B1])


def test_the_start_row_holds_the_listed_files_and_the_sha256_of_the_allow_file(world):
    """Catches: no record of what the list held: the verdict command compares it with the card's two inputs."""
    doc = start(world)
    rows = [r for r in runs_rows(world) if r.get("kind") == "start"]
    assert len(rows) == 1
    sha = hashlib.sha256((state_of(world) / "reader_allow" / f"{SESSION}.json").read_bytes()).hexdigest()
    assert (rows[0]["session_id"], rows[0]["card"], rows[0]["allow_sha256"]) == (SESSION, CARD, sha)
    assert rows[0]["files"] == doc["files"]
    assert len(rows[0]["extract_sha256"]) == 64


def test_a_second_start_in_the_same_session_is_refused_reader_busy(world):
    """Catches: a second reader run widening or replacing the list of the first; the way out is named."""
    start(world)
    with pytest.raises(reader_allow.ReaderError) as seen:
        start(world)
    assert seen.value.reason == "reader-busy"
    assert "wait for your own run or the orderer's release" in seen.value.text


def test_another_session_starts_its_own_run_and_never_shares_a_file(world):
    """Checks: the nearest allow of reader-busy: a different session gets its own file, the first one is unchanged."""
    first = start(world)
    second = start(world, session="s-other")
    assert first == allow_doc(world) and second["session_id"] == "s-other"
    assert (state_of(world) / "reader_allow" / "s-other.json").is_file()


def test_the_end_of_the_run_empties_the_list_and_a_new_start_is_allowed(world):
    """Checks: `reader_allow.end` empties the list of the session, then a start of the same session passes."""
    start(world)
    assert reader_allow.end(state_of(world), SESSION) is True
    assert allow_doc(world)["files"] == []
    assert _names(start(world)) == sorted(["test_a.py", "test_b.py", f"{SESSION}.extract.md"])


def _stop(root, agent_type, session=SESSION):
    data = {"session_id": session, "hook_event_name": "SubagentStop", "cwd": str(root), "transcript_path": "unused.jsonl",
            "agent_id": "a-reader-1", "agent_type": agent_type, "last_assistant_message": "done"}
    return dispatch.run("SubagentStop", "post", json.dumps(data), env={"CLAUDE_PROJECT_DIR": str(root)})


def test_the_end_of_a_checker_run_empties_the_list(world):
    """Catches: the list left full after the run: the SubagentStop of the checker type empties it."""
    start(world)
    _stop(world, CHECKER)
    assert allow_doc(world)["files"] == []


def test_the_end_of_another_agent_does_not_empty_the_list(world):
    """Catches: an unrelated helper agent of the same session ending the reader's list while the reader still runs."""
    doc = start(world)
    _stop(world, "worker")
    assert allow_doc(world)["files"] == doc["files"]


def test_the_end_of_a_run_in_another_session_does_not_empty_the_list(world):
    """Catches: one session's reader ending another session's list."""
    doc = start(world)
    _stop(world, CHECKER, session="s-other")
    assert allow_doc(world)["files"] == doc["files"]


def test_a_session_id_that_is_not_a_plain_name_is_refused(world):
    """Catches: a session id such as `..\\x` building a path outside the allow folder."""
    with pytest.raises(reader_allow.ReaderError):
        start(world, session="..\\x")
