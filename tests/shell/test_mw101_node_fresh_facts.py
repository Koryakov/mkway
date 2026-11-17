"""Card MW-101 (decisions: R196, R253), layer shell: the close-time proof of a verdict row on a real small git repository. A row
is proven when the record's own reader agent ended in the record's session, of a checker type, before the record, and the
node's meaning is unchanged since the record's file blob (the node's source and the file's non-test code, read from git),
never the file's mtime. Real files, real git, synthetic sessions. The deny rows set the file's mtime to `T0` first, so
the old rule (mtime) would prove them and only the new rule refuses."""
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/: the shared helpers and `_engine`
import _mw019 as o  # noqa: E402
import _mw080 as w  # noqa: E402
import logs  # noqa: E402
import proof  # noqa: E402
import verdict_add  # noqa: E402
import verdicts  # noqa: E402
from core_verdicts import Row  # noqa: E402

FIXTURE = chr(64) + "pytest.fixture"
SRC = ("import pytest" + "\n" * 3 + FIXTURE + chr(10) + "def box():\n    return 1\n\n\ndef test_one(box):\n    assert box == 1\n\n\n"
       "def test_two():\n    assert True\n\n\ndef test_three():\n    assert True\n")
LATER = 300  # seconds after T0: a commit after the record
AFTER_FIXTURE = SRC.replace("return 1", "return 2", 1).replace("box == 1", "box == 2", 1)


def _root(tmp_path):
    """The MW-080 git root with the test file replaced by `SRC` and committed before every reader run."""
    root = w.make_root(tmp_path)
    (root / w.FILE).write_text(SRC, encoding="utf-8")
    w.git(root, "add", "-f", "--", w.FILE)
    w.git(root, "commit", "-q", "-m", f"{w.CARD} the test file", when=-3500)
    return root


def _commit(root, text, when=LATER):
    (Path(root) / w.FILE).write_text(text, encoding="utf-8")
    w.git(root, "add", "-f", "--", w.FILE)
    w.git(root, "commit", "-q", "-m", f"{w.CARD} the file changes", when=when)


def _problems(root):
    return verdicts.proof_problems(root, w.state_of(root), [w.CHECKER], w.CARD, verdicts.rows_of(root, w.CARD))


def _added(root, monkeypatch):
    """One real `verdict add` of the first node by session `reader`, after a fresh reader run, its record at T0 plus 125 s."""
    w.reader(root, "reader", "agent-1")
    monkeypatch.setattr(logs, "now", lambda: w.at(125))
    assert w.apply(root, "reader", [w.N1]).allowed


def _hand(root, **over):
    """A row of the first node written by hand with an add record of the shape the command writes; a keyword replaces a key
    of the record, `None` drops it. The record's blob is the file's blob at HEAD now."""
    row = Row(w.N1, "true", "fine", "session:reader")
    verdict_add.put_rows(root, w.CARD, [row])
    record = {"kind": verdicts.PROOF_KIND, "doc": verdicts.verdict_file(w.CARD), "session": "reader",
              "rows": [verdicts.row_key(row)], "time": w.iso(125), "nodes": [w.N1],
              "tests": {w.FILE: w.git(root, "rev-parse", f"HEAD:{w.FILE}")}, "agent": "agent-1"}
    record.update(over)
    logs.append_jsonl(w.state_of(root) / w.PROOF, {k: v for k, v in record.items() if v is not None})


def _old_file(root):
    """The test file's mtime at T0: the old rule (mtime) would find every fresh reader run after it."""
    w.old(root, w.FILE)


def test_a_sibling_only_change_at_head_leaves_the_row_proven(tmp_path, monkeypatch):
    """Checks: R253, HEAD changed only in a sibling test since the record: the row of the first node is still proven."""
    root = _root(tmp_path)
    _added(root, monkeypatch)
    _commit(root, SRC.replace("def test_two():\n    assert True", "def test_two():\n    assert 1"))
    assert _problems(root) == {}


def test_a_fixture_change_at_head_is_unproven_and_names_both_blobs(tmp_path, monkeypatch):
    """Catches: R253, a fixture changed since the record and the row still proven; the text must name both blob shas."""
    root = _root(tmp_path)
    _added(root, monkeypatch)
    before = w.git(root, "rev-parse", f"HEAD:{w.FILE}")[:8]
    _commit(root, AFTER_FIXTURE.replace("box == 2", "box == 1"))
    after = w.git(root, "rev-parse", f"HEAD:{w.FILE}")[:8]
    _old_file(root)
    text = _problems(root).get(w.N1, "")
    assert (before in text, after in text, "non-test code" in text) == (True, True, True)


def test_a_node_body_change_at_head_is_unproven_and_names_the_node(tmp_path, monkeypatch):
    """Catches: the node's own assert changed since the record and the row still proven; the text must name the node."""
    root = _root(tmp_path)
    _added(root, monkeypatch)
    _commit(root, SRC.replace("assert box == 1", "assert box"))
    _old_file(root)
    text = _problems(root).get(w.N1, "")
    assert ("source of" in text, w.N1 in text) == (True, True)


def test_a_newer_mtime_with_equal_content_leaves_the_row_proven(tmp_path, monkeypatch):
    """Checks: R196, the file touched after the reader ran with no content change: the row is proven (it fails on the mtime rule)."""
    root = _root(tmp_path)
    _added(root, monkeypatch)
    later = o.at(10 ** 6).timestamp()
    os.utime(Path(root) / w.FILE, (later, later))
    assert _problems(root) == {}


def test_the_records_agent_ended_before_the_record_is_proven(tmp_path):
    """Checks: the nearest allow of the reader-proof denies below, the record's agent ended in its session before the record."""
    root = _root(tmp_path)
    w.reader(root, "reader", "agent-1")
    _hand(root)
    assert _problems(root) == {}


def test_an_agent_with_no_end_row_is_unproven(tmp_path):
    """Catches: a record that names an agent the hooks never saw end counted as a reader run."""
    root = _root(tmp_path)
    w.reader(root, "reader", "agent-other")
    _hand(root)
    _old_file(root)
    assert w.N1 in _problems(root)


def test_an_agent_that_ended_in_another_session_is_unproven(tmp_path):
    """Catches: the record's agent id found in the end rows of another session counted as proof."""
    root = _root(tmp_path)
    w.reader(root, "someone-else", "agent-1")
    w.reader(root, "reader", "agent-2")
    _hand(root)
    _old_file(root)
    assert w.N1 in _problems(root)


def test_an_agent_of_a_non_checker_type_is_unproven(tmp_path):
    """Catches: a run of an agent that is not a configured checker counted as a fresh reader."""
    root = _root(tmp_path)
    w.reader(root, "reader", "agent-1", agent_type="explorer")
    w.reader(root, "reader", "agent-2")  # a checker run in the session: the old rule would prove the row by it
    _hand(root)
    _old_file(root)
    assert w.N1 in _problems(root)


def test_an_agent_that_ended_after_the_record_is_unproven(tmp_path):
    """Catches: a reader that ended after the row was written counted as the row's reader."""
    root = _root(tmp_path)
    w.add_agent(root, session="reader", agent_type=w.CHECKER, agent_id="agent-1", started=60, ended=200, guard=w.CARD)
    w.reader(root, "reader", "agent-2")  # a run that ended before the record: the old rule would prove the row by it
    _hand(root)
    _old_file(root)
    assert w.N1 in _problems(root)


def test_a_record_with_no_agent_key_is_unproven(tmp_path):
    """Catches: a record with no `agent` key proven by any checker run of its session."""
    root = _root(tmp_path)
    w.reader(root, "reader", "agent-1")
    _hand(root, agent=None)
    _old_file(root)
    assert w.N1 in _problems(root)


def test_a_record_without_a_tests_blob_is_unproven(tmp_path):
    """Catches: a record with no blob of the file, so nothing to compare, guessed as unchanged."""
    root = _root(tmp_path)
    w.reader(root, "reader", "agent-1")
    _hand(root, tests=None)
    _old_file(root)
    assert w.N1 in _problems(root)


def test_a_blob_git_cannot_read_is_unproven(tmp_path):
    """Catches: a made-up blob sha, whose text git cannot give, guessed as unchanged."""
    root = _root(tmp_path)
    w.reader(root, "reader", "agent-1")
    _hand(root, tests={w.FILE: "0123456789abcdef0123456789abcdef01234567"})
    _old_file(root)
    assert w.N1 in _problems(root)


def test_a_file_missing_at_head_is_unproven(tmp_path):
    """Catches: a test file that is no longer in HEAD guessed as unchanged."""
    root = _root(tmp_path)
    w.reader(root, "reader", "agent-1")
    _hand(root)
    w.git(root, "rm", "-q", "--cached", "--", w.FILE)
    w.git(root, "commit", "-q", "-m", f"{w.CARD} the file leaves git", when=LATER)
    _old_file(root)
    assert w.N1 in _problems(root)


def test_a_blob_that_is_no_sha_is_unproven(tmp_path):
    """Catches: a `tests` value that is an option word handed to git, or read as a sha."""
    root = _root(tmp_path)
    w.reader(root, "reader", "agent-1")
    _hand(root, tests={w.FILE: "--help"})
    _old_file(root)
    assert w.N1 in _problems(root)


def test_the_outbox_still_judges_a_check_file_by_its_mtime(tmp_path):
    """Checks: the outbox path is unchanged, a document changed after the reader started is refused by its mtime, and the
    shared function with `changed=None` reads the same mtime."""
    root = o.make_root(tmp_path)
    rel = o.valid_file(root, doc_when=500, check_when=900)
    found = proof.fresh_reader_problem(o.state_dir(root), Path(root) / rel, "s1", o.iso(900), "critic", changed=None)
    assert ("after the last change of the document" in o.joined(o.inspect(root, rel)), found is not None) == (True, True)


def test_an_explicit_changed_time_replaces_the_mtime(tmp_path):
    """Checks: `fresh_reader_problem` with `changed` takes that time and not the file's mtime; without it the mtime rules."""
    root = o.make_root(tmp_path)
    rel = o.write_doc(root, "a.md", when=500)
    o.add_agent(root)
    args = (o.state_dir(root), Path(root) / rel, "s1", o.iso(180), "critic")
    explicit = proof.fresh_reader_problem(*args, changed=o.at(0))
    default = proof.fresh_reader_problem(*args)
    assert (explicit is None, default is None) == (True, False)


def _git_cannot_run(monkeypatch, word):
    """`git <word>` fails to start inside the engine's verdict module (the real command is used for every other call)."""
    real = subprocess.run

    def fake(args, *rest, **kw):
        if word in args:
            raise OSError("git cannot start")
        return real(args, *rest, **kw)
    monkeypatch.setattr(verdicts.subprocess, "run", fake)


def test_a_git_that_cannot_read_the_blob_leaves_the_row_unproven(tmp_path, monkeypatch):
    """Catches: a failed start of `git cat-file` raising out of the close, or the row guessed as unchanged."""
    root = _root(tmp_path)
    _added(root, monkeypatch)
    _commit(root, SRC.replace("assert True", "assert 1", 1))
    _git_cannot_run(monkeypatch, "cat-file")
    assert "cannot be read from git" in _problems(root).get(w.N1, "")


def test_a_git_that_cannot_name_the_head_blob_leaves_the_row_unproven(tmp_path, monkeypatch):
    """Catches: a failed start of `git rev-parse` raising out of the close, or the row guessed as unchanged."""
    root = _root(tmp_path)
    _added(root, monkeypatch)
    _git_cannot_run(monkeypatch, "rev-parse")
    assert "is not in HEAD" in _problems(root).get(w.N1, "")
