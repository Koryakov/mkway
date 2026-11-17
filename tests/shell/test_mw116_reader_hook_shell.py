"""Card MW-116: the reader's allowlist hook as a real process (`engine/reader_hook.py`, run from the agent's frontmatter):
the hook input on stdin, the project folder in the environment, the allow file written by the reader-start step. The
verdict is the exit code (2 blocks) and the record row the hook leaves. Synthetic task root, sessions and agents."""
import hashlib
import json

import pytest

from _mw116 import AGENT, CARD, CHECKER, FILE, OTHER_FILE, SESSION, allow_doc, calls, make_world, payload, run_hook, start
from _mw116 import runs_rows, state_of


@pytest.fixture
def world(tmp_path):
    root = make_world(tmp_path)
    start(root)
    return root


def _test_file(root):
    return str(root / FILE)


def test_an_allowed_read_passes_and_writes_one_record_row(world):
    """Catches: an allowed Read blocked, or passing with no record row: the row names the run (session, agent id and type),
    the tool, the path read, the decision and the sha256 of the allow file the decision used."""
    done = run_hook(world, payload(world, "Read", {"file_path": _test_file(world)}))
    assert done.returncode == 0
    sha = hashlib.sha256((state_of(world) / "reader_allow" / f"{SESSION}.json").read_bytes()).hexdigest()
    rows = calls(world)
    assert len(rows) == 1
    row = rows[0]
    assert (row["session_id"], row["agent_id"], row["agent_type"], row["tool"], row["decision"]) == (
        SESSION, AGENT, CHECKER, "Read", "allow")
    assert row["path"].replace("\\", "/").endswith(FILE) and row["allow_sha256"] == sha


@pytest.mark.parametrize("tool, tool_input", [
    pytest.param("Read", {"file_path": "tests/test_nowhere.py"}, id="read-unlisted"),
    pytest.param("Grep", {"pattern": "x", "path": "mkway"}, id="grep-unlisted"),
    pytest.param("Grep", {"pattern": "x"}, id="grep-no-path"),
    pytest.param("Bash", {"command": "cat tests/test_a.py"}, id="bash"),
    pytest.param("Edit", {"file_path": "tests/test_a.py", "old_string": "a", "new_string": "b"}, id="edit"),
    pytest.param("Glob", {"pattern": "**/*"}, id="glob"),
])
def test_an_unlisted_read_or_search_and_any_other_tool_are_blocked_with_a_record(world, tool, tool_input):
    """Catches: an unlisted Read, an unlisted Grep or any other tool passing the real hook; the block is exit 2, stderr
    holds the id and the way out, and the record row says refuse."""
    done = run_hook(world, payload(world, tool, tool_input))
    assert done.returncode == 2
    assert "reader-read-refused" in done.stderr and "the listed files" in done.stderr
    assert [(r["tool"], r["decision"]) for r in calls(world)] == [(tool, "refuse")]


def test_the_card_file_is_never_readable(world):
    """Catches: CARD.md readable by the reader; whatever the card says, its folder is not on the list."""
    import cardtool
    from _mw116 import profile_of
    card = cardtool.card_file(world, profile_of(world), CARD)
    done = run_hook(world, payload(world, "Read", {"file_path": str(card)}))
    assert done.returncode == 2
    assert calls(world)[0]["path"].replace("\\", "/").endswith("CARD.md")


def test_the_handback_is_allowed_and_leaves_a_row(world):
    """Checks: the nearest allow of the tool rows: the report tool passes, so the reader can always answer."""
    done = run_hook(world, payload(world, "SubagentHandback", {"message": "true"}))
    assert (done.returncode, [r["tool"] for r in calls(world)]) == (0, ["SubagentHandback"])


def test_no_allow_file_for_the_session_blocks_and_another_sessions_file_is_not_used(world):
    """Catches: a read passing for a session that has no allow file because another session has one; sessions never
    share a file."""
    done = run_hook(world, payload(world, "Read", {"file_path": _test_file(world)}, session="s-other"))
    assert done.returncode == 2
    assert "no allow file" in done.stderr
    assert [r["decision"] for r in calls(world)] == ["refuse"]


@pytest.mark.parametrize("stdin_text", ["not json", "[]", ""])
def test_a_hook_input_it_cannot_read_blocks_and_writes_no_row(world, stdin_text):
    """Catches: a crash of the hook exiting with a code other than 2 (Claude Code then goes on, fail open), or leaving a
    row with no decision."""
    done = run_hook(world, None, stdin_text=stdin_text)
    assert done.returncode == 2
    assert "reader-read-refused" in done.stderr and "crash" in done.stderr
    assert runs_rows(world) == [r for r in runs_rows(world) if r.get("kind") == "start"]


def test_a_record_the_hook_cannot_write_blocks_the_read(world):
    """Catches: an allowed read with no record row: the row is written together with the decision, so a record file that
    cannot be written (here: a folder in its place) blocks the call."""
    path = state_of(world) / "reader_runs.jsonl"
    path.unlink()
    path.mkdir()
    done = run_hook(world, payload(world, "Read", {"file_path": _test_file(world)}))
    assert done.returncode == 2
    assert "reader-read-refused" in done.stderr and "record" in done.stderr


def test_the_hook_runs_with_a_broken_import_path_and_still_blocks(world, tmp_path):
    """Catches: the hook failing before its own handler (an import error ends a script with exit 1, which does not block):
    run from a folder with no engine beside it, it still exits 2."""
    import shutil
    import subprocess
    import sys
    from _mw116 import HOOK
    alone = tmp_path / "alone"
    alone.mkdir()
    shutil.copy(HOOK, alone / "reader_hook.py")
    done = subprocess.run([sys.executable, str(alone / "reader_hook.py")], input=json.dumps(payload(world, "Read", {})),
                          capture_output=True, text=True, encoding="utf-8", cwd=str(alone), timeout=30)
    assert done.returncode == 2
    assert "reader-read-refused" in done.stderr


def test_the_allow_file_lists_exactly_the_test_files_and_the_extract(world):
    """Checks: the two inputs of the card: both test files its Acceptance rows name and the extract, nothing else."""
    doc = allow_doc(world)
    names = sorted(p.replace("\\", "/").rpartition("/")[2] for p in doc["files"])
    assert names == sorted([FILE.rpartition("/")[2], OTHER_FILE.rpartition("/")[2], f"{SESSION}.extract.md"])
