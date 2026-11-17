"""Card MW-080 (decisions: R194, R196, R196a), layer shell: the facts the command reads, on a real small git repository and
real state files. The last commit of the test file and its blobs come from git (never from the file's mtime: ruling R196),
the checker runs from `agents.jsonl`, the committers from the commit gate's records, the sessions that held the card from
`records.jsonl`, the runs already used from the proof file. Synthetic sessions and names only."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/: the shared helpers and `_engine`
import _mw080 as w  # noqa: E402
import cardtool  # noqa: E402
import logs  # noqa: E402


def test_the_last_commit_of_the_test_file_and_its_blobs_are_read_from_git(tmp_path):
    """Checks: a committed, unchanged test file reads its last commit and one blob for HEAD and for the file."""
    root = w.make_root(tmp_path)
    found = w.read(root, "reader", [w.N1]).nodes[0]
    blob = w.git(root, "rev-parse", f"HEAD:{w.FILE}")
    assert found.commit == w.git(root, "rev-parse", "HEAD")
    assert (found.head_blob, found.file_blob) == (blob, blob)


def test_an_edited_test_file_reads_a_file_blob_that_differs_from_head(tmp_path):
    """Catches: a file edited after its commit read as the committed text, so a verdict about another text is let through."""
    root = w.make_root(tmp_path)
    (root / w.FILE).write_text(w.SRC + "\n# edited\n", encoding="utf-8")
    found = w.read(root, "reader", [w.N1]).nodes[0]
    assert found.head_blob == w.git(root, "rev-parse", f"HEAD:{w.FILE}")
    assert found.file_blob == w.git(root, "hash-object", w.FILE)
    assert found.file_blob != found.head_blob


def test_an_untracked_test_file_reads_no_commit(tmp_path):
    """Catches: a test file git does not know read as committed."""
    root = w.make_root(tmp_path)
    (root / "tests" / "test_c.py").write_text("def test_c():\n    assert True\n", encoding="utf-8")
    found = w.read(root, "reader", ["tests/test_c.py::test_c"]).nodes[0]
    assert (found.commit, found.head_blob) == ("", "")


def test_a_checker_run_that_started_after_the_last_commit_is_fresh(tmp_path):
    """Checks: a checker end row of the caller's session that started after the last commit of the test file is fresh."""
    root = w.make_root(tmp_path)
    w.reader(root, "reader", "a1")
    found = w.read(root, "reader", [w.N1]).nodes[0]
    assert (found.readers, found.fresh) == (("a1",), ("a1",))


def test_a_checker_run_that_started_before_the_last_commit_is_not_fresh(tmp_path):
    """Catches: a reader that read the text before its last commit counted as a reader of the committed text."""
    root = w.make_root(tmp_path)
    w.reader(root, "reader", "a1", fresh=False)
    found = w.read(root, "reader", [w.N1]).nodes[0]
    assert (found.readers, found.fresh) == (("a1",), ())


def test_a_run_of_another_session_or_another_agent_type_is_no_reader(tmp_path):
    """Catches: the end row of another session or of a non-checker agent type read as the caller's reader."""
    root = w.make_root(tmp_path)
    w.reader(root, "another-session", "a1")
    w.reader(root, "reader", "a2", agent_type="critic")
    assert w.read(root, "reader", [w.N1]).nodes[0].readers == ()


def test_the_committers_come_from_the_commit_records_by_tree(tmp_path):
    """Checks: the session of the commit record whose tree is the tree of the commit that changed the test file."""
    root = w.make_root(tmp_path)
    tree = w.git(root, "rev-parse", "HEAD^{tree}")
    logs.append_jsonl(w.state_of(root) / "commit_records.jsonl",
                      {"kind": "commit", "session": "builder", "tree": tree, "paths": [w.FILE]})
    assert w.read(root, "reader", [w.N1]).nodes[0].committers == frozenset({"builder"})


def test_every_session_that_ever_took_the_card_is_a_holder_ever(tmp_path):
    """Catches: only the current holder read as a holder, so a builder that released the card could judge its own tests."""
    root = w.make_root(tmp_path, status="open")
    w.took(root, "h1", release=True)
    w.took(root, "h2")
    facts = w.read(root, "reader", [w.N1])
    assert facts.ever_held == frozenset({"h1", "h2"})
    assert facts.holder == "h2"


def test_a_run_recorded_for_the_card_is_a_used_run(tmp_path):
    """Checks: the agent runs the proof file names for this card, in order, once each; another card's record is ignored."""
    root = w.make_root(tmp_path)
    w.record(root, w.VERDICT_REL, "a1")
    w.record(root, w.VERDICT_REL, "a1")
    w.record(root, w.VERDICT_REL, "a2")
    w.record(root, "tests/verdicts/CARD-009.md", "a9")
    assert w.read(root, "reader", [w.N1]).nodes[0].used == ("a1", "a2")


def test_a_profile_with_no_checkers_reads_checkers_missing(tmp_path):
    """Catches: a profile with no `outbox.checkers` read as enforced."""
    root = w.make_root(tmp_path, checkers=())
    assert w.read(root, "reader", [w.N1]).checkers_missing


def test_a_profile_with_verdicts_off_reads_verdicts_off(tmp_path):
    """Catches: `cards.verdicts: off` read as enforced."""
    root = w.make_root(tmp_path, verdicts_off=True)
    assert w.read(root, "reader", [w.N1]).verdicts_off


def test_the_mode_of_the_profile_is_read_and_a_missing_key_reads_empty(tmp_path):
    """Checks: `tests.verdict_add.mode` is read as written, and an absent key reads empty (the core takes it as trip)."""
    watch, plain = w.make_root(tmp_path, mode="watch", name="a"), w.make_root(tmp_path, name="b")
    assert (w.read(watch, "reader", [w.N1]).mode, w.read(plain, "reader", [w.N1]).mode) == ("watch", "")


def test_the_card_status_and_the_nodes_the_card_names_are_read(tmp_path):
    """Checks: the register's status of the card, and per node whether an Acceptance row names it."""
    root = w.make_root(tmp_path, status="waiting")
    facts = w.read(root, "reader", [w.N1, "tests/test_a.py::test_nope"])
    assert facts.status == "waiting"
    assert (facts.nodes[0].known, facts.nodes[1].known) == (True, False)


def test_the_facts_hold_the_caller_and_the_owner_flag_as_given(tmp_path):
    """Checks: the caller and the owner flag are the ones the command passes, never read from a file."""
    root = w.make_root(tmp_path)
    facts = w.read(root, "", [w.N1], owner=True)
    assert (facts.caller, facts.owner) == ("", True)
    assert facts.ever_held == frozenset()


def test_an_end_row_with_no_readable_time_is_left_out(tmp_path):
    """Catches: a checker end row whose start time is not established counted as a reader run."""
    root = w.make_root(tmp_path)
    w.add_agent(root, session="reader", agent_type=w.CHECKER, agent_id="a1", start_row=False)
    assert w.read(root, "reader", [w.N1]).nodes[0].readers == ()


def _no_git(*_args, **_kwargs):
    raise OSError("no git here")


def test_a_git_that_cannot_run_reads_no_commit_and_no_blobs(tmp_path, monkeypatch):
    """Catches: a failed git call read as an answer, so a verdict is judged on a commit or a blob nobody read."""
    root = w.make_root(tmp_path)
    monkeypatch.setattr("subprocess.run", _no_git)
    found = w.read(root, "reader", [w.N1]).nodes[0]
    assert (found.commit, found.head_blob, found.file_blob) == ("", "", "")


def test_a_card_whose_card_file_is_missing_is_unknown(tmp_path):
    """Catches: a verdict judged for a card whose card file cannot be read (no Acceptance nodes to compare)."""
    root = w.make_root(tmp_path)
    w.lose_card_file(root)
    with pytest.raises(cardtool.CardError) as caught:
        w.read(root, "reader", [w.N1])
    assert caught.value.reason == "card-unknown"
