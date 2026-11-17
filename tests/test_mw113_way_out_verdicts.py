"""Card MW-113, step 2 (way-out tests, K3, the blind verdict). One test for each verdict refusal that had no way-out
test: it runs the refusal, then runs exactly what the refusal text names as the fix, and asserts the same call or close
is allowed. In process, on synthetic roots built by the MW-080 and MW-100 helpers (a real small git repository, the
real command with a by-permit, the real close check); no task data. The one engine gap this lane shows (G11, no command
withdraws a card, R275) is marked xfail with the reason, and the engine is not changed."""
import re

import pytest

from _engine import agent_file, cli, task_root
from _mw019 import pre as outbox_pre
from _mw068 import prove
import _mw080 as w
import _mw100 as m
import _mw102 as v
import logs
import records
import verdict_add
import verdicts

ALL = [w.N1, w.N2, w.N3, w.B1]
WEAK_REASON = "row E4 says byte for byte, but the test replaces CRLF with LF"


def _add(root, caller, *items, session=True):
    """`mkway verdict add CARD-001 <items>` as a session (the by-permit names `caller`) or as the owner's terminal."""
    return w.run_cli(root, "verdict", "add", w.CARD, *items, session=session, caller=caller)


def _reasons(verdict):
    return [r.reason for r in verdict.refusals]


# ---- the caller: who may write a verdict row -----------------------------------------------------------------------------

def test_the_way_out_of_verdict_by_holder_is_a_session_that_never_held_the_card(tmp_path):
    """Checks: a session that took the card once (and released it) is refused verdict-by-holder; a reader session that
    never took the card writes the row through the same command."""
    root = w.make_root(tmp_path)
    w.took(root, "builder", release=True)
    w.reader(root, "builder", "a1")
    w.reader(root, "reader", "a2")
    code, _out, err = _add(root, "builder", w.N1, "true", "one clause, one case")
    assert (code, "verdict-by-holder" in err) == (1, True)
    code, _out, err = _add(root, "reader", w.N1, "true", "one clause, one case")
    assert code == 0, err
    assert f"| {w.N1} | true | one clause, one case | session:reader |" in w.verdict_text(root)
    # the close: a row by the session that holds the card is refused verdict-by-holder; once it released the card and a
    # reader wrote the rows, the close-time verdict check passes
    (root / w.VERDICT_REL).unlink()
    w.took(root, "builder")
    _typed_rows(root, "session:builder")
    assert m.close_reason(root)[0] == "verdict-by-holder"
    records.append(w.state_of(root), "builder", "release", w.CARD)
    (root / w.VERDICT_REL).unlink()
    assert w.apply(root, "reader", ALL, "true", "one clause, one case").allowed
    m.old_mtimes(root)
    assert m.close_reason(root)[0] == ""


def test_the_way_out_of_verdict_by_committer_is_a_session_that_did_not_commit_the_test(tmp_path):
    """Checks: a session the commit gate's record names as the committer of the test file is refused
    verdict-by-committer; a session that did not commit it writes the row through the same command."""
    root = w.make_root(tmp_path)
    tree = w.git(root, "rev-parse", "HEAD^{tree}")
    logs.append_jsonl(w.state_of(root) / "commit_records.jsonl",
                      {"kind": "commit", "session": "committer", "tree": tree, "paths": [w.FILE]})
    w.reader(root, "committer", "a1")
    w.reader(root, "reader", "a2")
    code, _out, err = _add(root, "committer", w.N1, "true", "one clause, one case")
    assert (code, "verdict-by-committer" in err) == (1, True)
    code, _out, err = _add(root, "reader", w.N1, "true", "one clause, one case")
    assert code == 0, err
    # the close: a row by the committer is refused verdict-by-committer; rows written by a reader pass the close check
    (root / w.VERDICT_REL).unlink()
    _typed_rows(root, "session:committer")
    assert m.close_reason(root)[0] == "verdict-by-committer"
    (root / w.VERDICT_REL).unlink()
    assert w.apply(root, "reader", ALL, "true", "one clause, one case").allowed
    m.old_mtimes(root)
    assert m.close_reason(root)[0] == ""


def test_the_way_out_of_verdict_by_owner_is_a_reader_session(tmp_path):
    """Checks: the owner's terminal is refused verdict-by-owner; a reader session that did not build or commit the
    tests runs the same command and the row is written."""
    root = w.make_root(tmp_path)
    w.reader(root, "reader", "a1")
    code, _out, err = _add(root, None, w.N1, "true", "one clause, one case", session=False)
    assert (code, "verdict-by-owner" in err) == (1, True)
    code, _out, err = _add(root, "reader", w.N1, "true", "one clause, one case")
    assert code == 0, err


def test_the_way_out_of_verdict_no_reader_run_is_a_fresh_checker_run(tmp_path):
    """Checks: a session that ran no checker agent is refused verdict-no-reader-run; after a fresh checker run in the
    session the same call writes the row."""
    root = w.make_root(tmp_path)
    code, _out, err = _add(root, "reader", w.N1, "true", "one clause, one case")
    assert (code, "verdict-no-reader-run" in err) == (1, True)
    w.reader(root, "reader", "a1")
    code, _out, err = _add(root, "reader", w.N1, "true", "one clause, one case")
    assert code == 0, err


def test_the_way_out_of_verdict_stale_is_a_fresh_reader_run_after_the_last_commit(tmp_path):
    """Checks: a session whose only checker run began before the last commit of the test file is refused
    verdict-stale; after a fresh run in the session the same call writes the row."""
    root = w.make_root(tmp_path)
    w.reader(root, "reader", "a1", fresh=False)
    code, _out, err = _add(root, "reader", w.N1, "true", "one clause, one case")
    assert (code, "verdict-stale" in err) == (1, True)
    w.reader(root, "reader", "a2")
    code, _out, err = _add(root, "reader", w.N1, "true", "one clause, one case")
    assert code == 0, err


# ---- the verdict file has one writer ---------------------------------------------------------------------------------------

def test_the_way_out_of_verdict_file_by_command_is_the_verdict_add_command(tmp_path):
    """Checks: a Write of the verdict file is refused verdict-file-by-command; the engine command `verdict add` that the
    refusal names writes the row."""
    root = w.make_root(tmp_path)
    w.reader(root, "reader", "a1")
    refused = outbox_pre(root, w.VERDICT_REL, "| Node | Verdict | Reason | By |\n", session="reader")
    assert (refused.kind, refused.reason_id) == ("refuse", "verdict-file-by-command")
    code, _out, err = _add(root, "reader", w.N1, "true", "one clause, one case")
    assert code == 0, err
    assert f"| {w.N1} | true |" in w.verdict_text(root)


# ---- the recut: the lead's answer to a weak or wrong verdict -------------------------------------------------------------

def test_the_way_out_of_verdict_recut_nothing_is_a_weak_verdict_to_answer(tmp_path, monkeypatch):
    """Checks: a recut of a node nobody judged is refused verdict-recut-nothing; once a reader run called the node weak
    and the cut changed, the same recut is allowed."""
    root = m.lead_root(tmp_path)
    assert _reasons(m.recut(root, monkeypatch, node=m.N2)) == ["verdict-recut-nothing"]
    m.weak_run(root, node=m.N2)
    m.change_cut(root, 130)
    assert m.recut(root, monkeypatch, node=m.N2).allowed


def test_the_way_out_of_verdict_recut_no_change_is_a_commit_that_changes_the_cut(tmp_path, monkeypatch):
    """Checks: a recut with no commit since the answered run is refused verdict-recut-no-change; after a commit that
    changes the test file the same recut is allowed."""
    root = m.lead_root(tmp_path)
    m.weak_run(root)
    assert _reasons(m.recut(root, monkeypatch)) == ["verdict-recut-no-change"]
    m.change_cut(root, 130)
    assert m.recut(root, monkeypatch).allowed


def test_the_way_out_of_verdict_recut_stale_is_to_commit_the_change(tmp_path, monkeypatch):
    """Checks: a recut over a test file that differs from HEAD is refused verdict-recut-stale; after the change is
    committed the same recut is allowed."""
    root = m.lead_root(tmp_path)
    m.weak_run(root)
    m.change_cut(root, 130)
    (root / w.FILE).write_text((root / w.FILE).read_text(encoding="utf-8") + "\n# an uncommitted line\n", encoding="utf-8")
    assert _reasons(m.recut(root, monkeypatch)) == ["verdict-recut-stale"]
    w.git(root, "add", "-f", "--", w.FILE)
    w.git(root, "commit", "-q", "-m", f"{w.CARD} the change is committed", when=140)
    assert m.recut(root, monkeypatch).allowed


def test_the_way_out_of_verdict_recut_not_lead_is_the_orderer(tmp_path, monkeypatch):
    """Checks: a recut by a session that did not order the card is refused verdict-recut-not-lead; the card's orderer
    runs the same recut and it is allowed."""
    root = m.lead_root(tmp_path)
    m.weak_run(root)
    m.change_cut(root, 130)
    assert _reasons(m.recut(root, monkeypatch, caller="other")) == ["verdict-recut-not-lead"]
    assert m.recut(root, monkeypatch, caller=m.LEAD).allowed


# ---- the close: the verdict check ------------------------------------------------------------------------------------------

def _judged(root, monkeypatch, word):
    """Run 1 (reader1): all four nodes true. The fix commit. Run 2 (reader2): the first node `word`."""
    w.add_agent(root, session="reader1", agent_type=w.CHECKER, agent_id="agent-1", started=60, ended=120, guard=w.CARD)
    m.clock(monkeypatch, 125)
    assert w.apply(root, "reader1", ALL, "true", "one clause, one case").allowed
    m.change_cut(root, 130)
    m.old_mtimes(root)
    w.add_agent(root, session="reader2", agent_type=w.CHECKER, agent_id="agent-2", started=140, ended=190, guard=w.CARD)
    m.clock(monkeypatch, 195)
    assert w.apply(root, "reader2", [w.N1], word, WEAK_REASON).allowed


def _recut_and_judge_again(root, monkeypatch):
    """The lead's recut after a commit that changes the cut, then a fresh reader that started after the recut says true."""
    m.change_cut(root, 192)
    assert m.recut(root, monkeypatch, at=200).allowed
    w.add_agent(root, session="reader3", agent_type=w.CHECKER, agent_id="agent-3", started=260, ended=300, guard=w.CARD)
    m.clock(monkeypatch, 320)
    assert w.apply(root, "reader3", [w.N1], "true", "the new cut reads fine").allowed
    m.old_mtimes(root)


def test_the_way_out_of_verdict_missing_is_a_verdict_row_for_every_node(tmp_path):
    """Checks: a close with no verdict row for a node is refused verdict-missing; after a reader writes the rows through
    `verdict add` the close-time verdict check passes."""
    root = m.lead_root(tmp_path)
    assert m.close_reason(root)[0] == "verdict-missing"
    w.reader(root, "reader", "a1")
    assert w.apply(root, "reader", ALL, "true", "one clause, one case").allowed
    m.old_mtimes(root)
    assert m.close_reason(root)[0] == ""


@pytest.mark.parametrize("word", ["weak", "wrong"])
def test_the_way_out_of_a_weak_or_wrong_verdict_is_a_recut_then_a_fresh_true(tmp_path, monkeypatch, word):
    """Checks: a close on a node whose last row is weak or wrong is refused (verdict-weak, verdict-wrong); the lead's
    recut after a changed cut and a fresh reader's true row let the close-time verdict check pass."""
    root = m.lead_root(tmp_path)
    _judged(root, monkeypatch, word)
    assert m.close_reason(root)[0] == f"verdict-{word}"
    _recut_and_judge_again(root, monkeypatch)
    assert m.close_reason(root)[0] == ""


def test_the_way_out_of_verdict_recut_pending_is_a_fresh_reader_after_the_recut(tmp_path, monkeypatch):
    """Checks: a close while the last row of a node is a recut is refused verdict-recut-pending; after a fresh blind
    reader that started after the recut says true, the close-time verdict check passes."""
    root = m.lead_root(tmp_path)
    _judged(root, monkeypatch, "weak")
    m.change_cut(root, 192)
    assert m.recut(root, monkeypatch, at=200).allowed
    assert m.close_reason(root)[0] == "verdict-recut-pending"
    w.add_agent(root, session="reader3", agent_type=w.CHECKER, agent_id="agent-3", started=260, ended=300, guard=w.CARD)
    m.clock(monkeypatch, 320)
    assert w.apply(root, "reader3", [w.N1], "true", "the new cut reads fine").allowed
    m.old_mtimes(root)
    assert m.close_reason(root)[0] == ""


def _typed_rows(root, by):
    """A verdict file typed by hand: a true row for each node, `by` as the reader."""
    verdict_add.put_rows(root, w.CARD, [verdicts.Row(node, "true", "typed", by) for node in ALL])


def test_the_way_out_of_verdict_unproven_is_a_row_written_by_the_command(tmp_path):
    """Checks: a verdict file typed by hand has no record of `verdict add` and the close is refused verdict-unproven;
    with the typed file removed and the rows written by the command the close-time verdict check passes."""
    root = m.lead_root(tmp_path)
    _typed_rows(root, "session:reader")
    assert m.close_reason(root)[0] == "verdict-unproven"
    (root / w.VERDICT_REL).unlink()
    w.reader(root, "reader", "a1")
    assert w.apply(root, "reader", ALL, "true", "one clause, one case").allowed
    m.old_mtimes(root)
    assert m.close_reason(root)[0] == ""


def test_the_way_out_of_verdict_unproven_at_the_commit_is_the_file_the_command_wrote(tmp_path):
    """Checks: the orderer's commit of a hand-typed verdict file is refused verdict-unproven by the commit gate; with the
    typed file removed and the file `verdict add` wrote staged, the same commit is allowed."""
    root = v.verdict_root(tmp_path)
    v.typed(root, v.N1)
    v.stage(root)
    reason, text = v.decide(root)
    assert (reason, v.N1 in text) == ("verdict-unproven", True)
    (root / v.REL).unlink()
    v.add(root, v.N1)
    v.stage(root)
    assert v.decide(root) == ("allow", "")


def test_the_way_out_of_verdict_by_author_is_a_caller_who_did_not_write_the_test(tmp_path):
    """Checks: a row whose `by` is the author of the test file is refused verdict-by-author at the close; with the typed
    file removed and the rows written by a reader who did not write the test the close-time verdict check passes."""
    root = m.lead_root(tmp_path)
    _typed_rows(root, "mkway-test")  # the git author of the test files in the MW-080 root
    assert m.close_reason(root)[0] == "verdict-by-author"
    (root / w.VERDICT_REL).unlink()
    w.reader(root, "reader", "a1")
    assert w.apply(root, "reader", ALL, "true", "one clause, one case").allowed
    m.old_mtimes(root)
    assert m.close_reason(root)[0] == ""


# ---- the close: the checker's definition -----------------------------------------------------------------------------------

NODE = "tests/test_a.py::test_one"
HEADER = "| Node | Verdict | Reason | By |\n|---|---|---|---|\n"


def _open_card(tmp_path, checker, tools, word="true"):
    """An open card whose one row names `NODE`, a true verdict row by `s2` with its proof; the checker's definition is
    written only when `tools` is not None."""
    root = task_root(tmp_path, cards={"verdicts": "required"}, outbox={"checkers": [checker]}, agent_tools=None)
    if tools is not None:
        agent_file(root, checker, tools)
    (root / "tests" / "verdicts").mkdir(parents=True)
    (root / "tests" / "test_a.py").write_text("def test_one():\n    pass\n", encoding="utf-8")
    assert cli(root, "card", "new", "First")[0] == 0
    (folder,) = [p for p in (root / "mkway" / "cards").iterdir() if p.name.startswith("CARD-001-")]
    text = (folder / "CARD.md").read_text(encoding="utf-8")
    text = re.sub(r"^\| \*\*Paths\*\* \|.*\|$", "| **Paths** | `src/a.py` |", text, flags=re.M)
    head = "| # | Item | Was | Must be | Test |\n|---|---|---|---|---|\n"
    start = text.index(head) + len(head)
    (folder / "CARD.md").write_text(text[:start] + f"| E1 | x | a | b | {NODE} |" + text[text.index("\n\n", start):],
                                    encoding="utf-8")
    assert cli(root, "card", "open", "CARD-001")[0] == 0
    (root / "tests" / "verdicts" / "CARD-001.md").write_text(HEADER + f"| {NODE} | {word} | fine | session:s2 |\n",
                                                             encoding="utf-8")
    prove(root, "CARD-001", "tests/test_a.py", "s2", agent_type=checker)
    return root


def test_the_way_out_of_checker_not_found_is_the_agent_definition_of_the_checker(tmp_path):
    """Checks: a real close with no agent definition of the configured checker is refused checker-not-found; after the
    definition (tools Read and Grep) is written the same close closes the card."""
    root = _open_card(tmp_path, "fresh-reader", None)
    code, _out, err = cli(root, "card", "close", "CARD-001")
    assert (code != 0, "checker-not-found" in err) == (True, True)
    agent_file(root, "fresh-reader", "Read, Grep")
    code, _out, err = cli(root, "card", "close", "CARD-001")
    assert code == 0, err


def test_the_way_out_of_checker_not_read_only_is_a_checker_that_lists_read_and_grep(tmp_path):
    """Checks: a real close whose checker lists Bash is refused checker-not-read-only; after the definition lists Read
    and Grep only, the same close closes the card."""
    root = _open_card(tmp_path, "critic", "Read, Grep, Bash")
    code, _out, err = cli(root, "card", "close", "CARD-001")
    assert (code != 0, "checker-not-read-only" in err) == (True, True)
    agent_file(root, "critic", "Read, Grep")
    code, _out, err = cli(root, "card", "close", "CARD-001")
    assert code == 0, err


def test_the_way_out_of_a_weak_verdict_at_the_real_close_is_a_true_row_of_another_reader(tmp_path):
    """Checks: through the real `card close`, a card whose node has a weak verdict row is refused verdict-weak and stays
    open; after a second reader writes a true row with its proof, the same close closes the card."""
    root = _open_card(tmp_path, "fresh-reader", "Read, Grep", word="weak")
    code, _out, err = cli(root, "card", "close", "CARD-001")
    assert (code != 0, "verdict-weak" in err) == (True, True)
    (root / "tests" / "verdicts" / "CARD-001.md").write_text(HEADER + f"| {NODE} | true | fine | session:s3 |\n",
                                                             encoding="utf-8")
    prove(root, "CARD-001", "tests/test_a.py", "s3", agent_type="fresh-reader")
    code, _out, err = cli(root, "card", "close", "CARD-001")
    assert code == 0, err


# ---- G11: the orderer's edit of the rows of an opened card ---------------------------------------------------------------

def _must(ok, what):
    """A harness step: a failure is a RuntimeError, so that only the gap itself fails as an AssertionError."""
    if not ok:
        raise RuntimeError(f"harness step failed: {what}")


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="engine gap G11: card withdraw missing, R275 (CARD.md is never edited after open; the way out "
                          "of verdict-recut-exceeded is a withdrawn card and a new card; closing card: not established, an engine card on the owner's word)")
def test_the_orderer_withdraws_the_card_and_opens_a_new_one(tmp_path, monkeypatch):
    """Catches: the refusal verdict-recut-exceeded says to split or withdraw the card, and no command withdraws a card.
    The way out (ruling R275) is `mkway card withdraw <card>`, then `mkway card new <title>`; the withdrawn card can
    be neither taken nor closed. First the harness proves verdict-recut-exceeded is refused (a RuntimeError if not).
    Today `card withdraw` does not exist, so this test fails and is marked xfail (engine gap G11, see the card
    MW-113 Log)."""
    root = m.lead_root(tmp_path)
    w.add_agent(root, session="r1", agent_type=w.CHECKER, agent_id="a1", started=60, ended=120, guard=w.CARD)
    m.clock(monkeypatch, 125)
    _must(w.apply(root, "r1", [w.N1], "weak", WEAK_REASON).allowed, "the first weak run")
    m.change_cut(root, 130)
    _must(m.recut(root, monkeypatch, at=200).allowed, "the first recut")
    w.add_agent(root, session="r2", agent_type=w.CHECKER, agent_id="a2", started=260, ended=300, guard=w.CARD)
    m.clock(monkeypatch, 310)
    _must(w.apply(root, "r2", [w.N1], "weak", "still weak").allowed, "the second weak run")
    m.change_cut(root, 320)
    exceeded = _reasons(m.recut(root, monkeypatch, at=400))
    _must(exceeded == ["verdict-recut-exceeded"], f"verdict-recut-exceeded is refused, got {exceeded}")
    code, _out, err = w.run_cli(root, "card", "withdraw", w.CARD, caller=m.LEAD)
    assert code == 0, err
    assert w.run_cli(root, "card", "take", w.CARD, caller="builder")[0] != 0
    assert cli(root, "card", "close", w.CARD)[0] != 0
    assert w.run_cli(root, "card", "new", "Split", caller=m.LEAD)[0] == 0
