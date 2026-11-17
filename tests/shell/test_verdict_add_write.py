"""Card MW-080 (decisions: R194, R196), layer shell: what an allowed call writes (the table row and the record in the proof
file), what the close check then reads, and what the Write path no longer does (no proof row from the post step; a helpful
refusal from the pre step). Real files, a real small git repository, synthetic sessions."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/: the shared helpers and `_engine`
import _mw080 as w  # noqa: E402
from _engine import gate_call  # noqa: E402
import gate_outbox  # noqa: E402
import verdicts  # noqa: E402

HEADER = "| Node | Verdict | Reason | By |\n|---|---|---|---|\n"


def _reader_root(tmp_path, **kw):
    """A root where the session `reader` has one fresh checker run (agent a1)."""
    root = w.make_root(tmp_path, **kw)
    w.reader(root, "reader", "a1")
    return root


def _problems(root):
    return verdicts.proof_problems(root, w.state_of(root), [w.CHECKER], w.CARD, verdicts.rows_of(root, w.CARD))


def test_an_allowed_call_writes_the_row_and_the_record(tmp_path):
    """Checks: the table row of the call, and a `verdict-written` record that holds the key of that row."""
    root = _reader_root(tmp_path)
    assert w.apply(root, "reader", [w.N1], "true", "one clause, one case").allowed
    (row,) = verdicts.rows_of(root, w.CARD)
    assert (row.node, row.verdict, row.reason, row.by) == (w.N1, "true", "one clause, one case", "session:reader")
    assert w.written(root)[0]["rows"] == [verdicts.row_key(row)]


def test_the_record_holds_the_agent_run_number_and_the_test_blob(tmp_path):
    """Checks: the record names the agent run, its number for the card, and the blob of the test file the verdict is about."""
    root = _reader_root(tmp_path)
    w.apply(root, "reader", [w.N1])
    record = w.written(root)[0]
    assert (record["session"], record["doc"], record["agent"], record["run"]) == ("reader", w.VERDICT_REL, "a1", 1)
    assert record["tests"] == {w.FILE: w.git(root, "rev-parse", f"HEAD:{w.FILE}")}


def test_a_second_call_with_the_same_run_keeps_run_one(tmp_path):
    """Checks: the second call of one reader run (a true, then a weak) is run 1 again and the first row stays."""
    root = _reader_root(tmp_path)
    w.apply(root, "reader", [w.N1], "true")
    w.apply(root, "reader", [w.N2], "weak", "the test names no case")
    assert [r["run"] for r in w.written(root)] == [1, 1]
    assert [(r.node, r.verdict) for r in verdicts.rows_of(root, w.CARD)] == [(w.N1, "true"), (w.N2, "weak")]


def test_a_refused_call_writes_nothing(tmp_path):
    """Catches: a refused call that still leaves a row or a record behind."""
    root = w.make_root(tmp_path)
    found = w.apply(root, "reader", [w.N1])
    assert found.allowed is False
    assert (w.verdict_text(root), w.proof_rows(root)) == ("", [])


def test_the_row_of_the_same_node_is_replaced(tmp_path):
    """Checks: a second verdict for the same node replaces its row; the file never holds two rows of one node."""
    root = _reader_root(tmp_path)
    w.apply(root, "reader", [w.N1], "weak", "first look")
    w.apply(root, "reader", [w.N1], "true", "second look")
    assert [(r.node, r.verdict) for r in verdicts.rows_of(root, w.CARD)] == [(w.N1, "true")]


def test_a_row_of_another_node_is_kept_and_a_new_node_is_appended(tmp_path):
    """Checks: a call for a second node leaves the first node's row where it was and adds the new row after it."""
    root = _reader_root(tmp_path)
    w.apply(root, "reader", [w.N1])
    w.apply(root, "reader", [w.N2])
    assert [r.node for r in verdicts.rows_of(root, w.CARD)] == [w.N1, w.N2]


def test_a_new_verdict_file_gets_the_header_the_reader_skips(tmp_path):
    """Checks: a new file starts with the table header, which the reader of the close check does not count as a row."""
    root = _reader_root(tmp_path)
    w.apply(root, "reader", [w.N1])
    assert w.verdict_text(root).startswith(HEADER)
    assert len(verdicts.rows_of(root, w.CARD)) == 1


def test_a_pipe_and_a_newline_in_a_reason_are_replaced(tmp_path):
    """Catches: a reason whose pipe splits the table row, or whose newline breaks it in two."""
    root = _reader_root(tmp_path)
    w.apply(root, "reader", [w.N1], "true", "one | two\nthree")
    assert verdicts.rows_of(root, w.CARD)[0].reason == "one / two three"


def test_the_run_number_is_in_the_record_and_never_in_the_table(tmp_path):
    """Catches: the run number written into the table, where the reader of the close check would take it for text."""
    root = _reader_root(tmp_path)
    w.apply(root, "reader", [w.N1], "true", "fine")
    assert w.written(root)[0]["run"] == 1
    assert w.verdict_text(root) == HEADER + f"| {w.N1} | true | fine | session:reader |\n"


def test_a_row_written_by_the_command_is_proven_at_close(tmp_path):
    """Checks: the close check's proof reader accepts the row the command wrote and its record."""
    root = _reader_root(tmp_path)
    w.old(root)
    w.apply(root, "reader", [w.N1])
    assert _problems(root) == {}


def test_a_typed_row_reads_verdict_unproven_at_close(tmp_path):
    """Catches: a row changed by hand after the command wrote it still counted as the reader's proven verdict."""
    root = _reader_root(tmp_path)
    w.old(root)
    w.apply(root, "reader", [w.N1], "weak", "the test names no case")
    path = root / w.VERDICT_REL
    path.write_text(path.read_text(encoding="utf-8").replace("| weak |", "| true |"), encoding="utf-8")
    assert "no record" in _problems(root)[w.N1]


def test_node_a_recorded_and_node_b_typed_leaves_b_unproven(tmp_path):
    """Catches: one recorded row lending its proof to a row typed beside it by the same session."""
    root = _reader_root(tmp_path)
    w.old(root)
    w.apply(root, "reader", [w.N1])
    path = root / w.VERDICT_REL
    path.write_text(path.read_text(encoding="utf-8") + f"| {w.N2} | true | typed | session:reader |\n", encoding="utf-8")
    assert set(_problems(root)) == {w.N2}


# ---- the Write path ----------------------------------------------------------------------------------------------------

def _post_write(root, session, rel):
    return gate_call(gate_outbox.check, root, tool="Write", event="PostToolUse", session=session,
                     tool_input={"file_path": rel, "content": "x"}, tool_response={"filePath": rel, "success": True})


def test_a_post_step_write_of_a_verdict_file_leaves_no_proof_row(tmp_path):
    """Catches: the post step still turning a write of a verdict file into a proof row, so a typed row would be proven."""
    root = _reader_root(tmp_path)
    (root / "tests" / "verdicts").mkdir()
    (root / w.VERDICT_REL).write_text(HEADER + f"| {w.N1} | true | typed | session:reader |\n", encoding="utf-8")
    _post_write(root, "reader", w.VERDICT_REL)
    assert w.written(root) == []


def test_a_row_typed_with_the_write_tool_reads_verdict_unproven_at_close(tmp_path):
    """Catches: a row typed with the Write tool, with a fresh reader run behind it, proven by the post step's record."""
    root = _reader_root(tmp_path)
    w.old(root)
    (root / "tests" / "verdicts").mkdir()
    (root / w.VERDICT_REL).write_text(HEADER + f"| {w.N1} | true | typed | session:reader |\n", encoding="utf-8")
    _post_write(root, "reader", w.VERDICT_REL)
    assert "no record" in _problems(root)[w.N1]


def _pre_write(root, rel):
    return gate_call(gate_outbox.check, root, tool="Write", event="PreToolUse", session="reader",
                     tool_input={"file_path": str(root / rel), "content": "x"})


def test_the_pre_step_refuses_a_write_of_a_verdict_file(tmp_path):
    """Catches: a Write of tests/verdicts/<card>.md let through, so a verdict row has a second writer."""
    found = _pre_write(w.make_root(tmp_path), w.VERDICT_REL)
    assert (found.kind, found.reason_id) == ("refuse", "verdict-file-by-command")


def test_the_pre_step_allows_a_write_of_another_test_file(tmp_path):
    """Checks: the nearest allow of the refusal above, the same call with only the path changed: an ordinary test file is allowed."""
    root = w.make_root(tmp_path)
    assert (_pre_write(root, w.VERDICT_REL).kind, _pre_write(root, w.FILE).kind) == ("refuse", "allow")


def _cannot_read(_ctx):
    raise RuntimeError("the path cannot be read")


def test_a_pre_step_that_cannot_read_the_path_allows_the_write(tmp_path, monkeypatch):
    """Checks: a path the gate cannot read is not provably a verdict file, so the write is allowed (the same call is refused while the path reads)."""
    root = w.make_root(tmp_path)
    refused = _pre_write(root, w.VERDICT_REL).kind
    monkeypatch.setattr(gate_outbox, "_verdict_rel", _cannot_read)
    assert (refused, _pre_write(root, w.VERDICT_REL).kind) == ("refuse", "allow")
