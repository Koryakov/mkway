"""Card MW-019, part 4: `mkway outbox` (one row per file), the start-block line, from any terminal. Synthetic task roots
only; no task data."""
import json
import re

import pytest

from _engine import cli
from _mw019 import OUT, SUFFIX, make_root, sha_of, valid_file, write_doc
import dispatch
from pathlib import Path


def _rows(out):
    """{file: columns} for the rows (not the indented problem lines), and the problem lines under each file."""
    rows, problems, last = {}, {}, None
    for line in out.splitlines():
        if not line.strip():
            continue
        if line.startswith(" "):
            problems.setdefault(last, []).append(line.strip())
        else:
            cols = re.split(r"\s{2,}", line.strip())
            rows[cols[0]] = cols
            last = cols[0]
    return rows, problems


def _mixed(root):
    ok = valid_file(root, "a.md")
    missing = write_doc(root, "b.md")
    stale = valid_file(root, "c.md")
    write_doc(root, "c.md", "Changed after its check.\n", when=400)
    unproven = valid_file(root, "d.md", agent=None, doc_when=500, check_when=900)
    return ok, missing, stale, unproven


def test_the_outbox_command_prints_a_row_per_file(tmp_path):
    """Checks: `mkway outbox` prints one row per file under outbox.dir, sorted by path, with its sha, state and checker (E13)."""
    # check files are not rows; a file that is not valid has indented problem lines under its row, and a valid one has
    # none; Catches: a board that lists check files, hides the state or never says why
    root = make_root(tmp_path)
    ok, missing, stale, unproven = _mixed(root)
    code, out, err = cli(root, "outbox")
    assert code == 0, err
    rows, problems = _rows(out)
    assert list(rows) == [ok, missing, stale, unproven]
    assert rows[ok] == [ok, sha_of(Path(root) / ok)[:8], "valid", "critic", "2026-11-11T10:03:00Z"]
    assert rows[missing] == [missing, sha_of(Path(root) / missing)[:8], "missing", "-", "-"]
    assert rows[stale][1:4] == [sha_of(Path(root) / stale)[:8], "stale", "critic"]
    assert rows[unproven][2] == "unproven"
    assert rows[unproven][3] == "critic"
    assert ok not in problems
    assert any(f"{missing}{SUFFIX}" in p for p in problems[missing])
    assert any("changed" in p for p in problems[stale])
    assert any("agent" in p for p in problems[unproven])


def test_the_outbox_command_without_a_folder(tmp_path):
    """Checks: with no outbox.dir the command exits 0 and names the key; with an empty folder it says so (E13)."""
    # Catches: a command that fails or prints nothing where the feature is simply not set up
    bare = make_root(tmp_path / "bare", outbox=None)
    code, out, err = cli(bare, "outbox")
    assert code == 0
    assert "outbox.dir" in out
    empty = make_root(tmp_path / "empty")
    code, out, err = cli(empty, "outbox")
    assert code == 0
    assert "no files" in out
    assert OUT in out


def test_a_session_may_run_the_outbox_command(tmp_path):
    """Checks: a session's shell prints the same rows as the owner's terminal and writes no record (E13)."""
    # Catches: a read-only board made owner-only
    root = make_root(tmp_path)
    _mixed(root)
    own = cli(root, "outbox")
    session = cli(root, "outbox", session=True)
    assert session[0] == 0
    assert session[1] == own[1]
    assert "mkway-ok" not in session[1]


def _context(root, session="s1"):
    payload = {"session_id": session, "hook_event_name": "SessionStart"}
    res = dispatch.run("SessionStart", "start", json.dumps(payload),
                       env={"CLAUDE_PROJECT_DIR": str(root), "CLAUDECODE": "1"})
    return json.loads(res.stdout)["hookSpecificOutput"]["additionalContext"]


def test_the_start_block_counts_files_and_unchecked(tmp_path):
    """Checks: with outbox.dir set the start block counts files and unchecked ones, 0 and 0 when empty, no line without it (E14)."""
    # N the files that are not check files, M those whose state is not valid; Catches: a count that includes check
    # files, or a line in a task that has no outbox
    root = make_root(tmp_path)
    assert "outbox: 0 files, 0 unchecked" in _context(root).splitlines()
    _mixed(root)
    assert "outbox: 4 files, 3 unchecked" in _context(root).splitlines()
    bare = make_root(tmp_path / "bare", outbox=None)
    assert not [x for x in _context(bare).splitlines() if x.startswith("outbox:")]
