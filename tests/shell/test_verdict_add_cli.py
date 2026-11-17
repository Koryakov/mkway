"""Card MW-080 (decisions: R194, R196, R196a), layer shell: the command `mkway verdict add <card> <node>... <true|weak|wrong>
<reason>` run in process (`_engine.cli`) on a real small git repository: who the caller is (the lock gate's by-permit, the
owner's terminal), the usage errors, the output, the refusal log, the watch mode. Synthetic sessions and names only."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/: the shared helpers and `_engine`
import _mw080 as w  # noqa: E402
import verdicts  # noqa: E402


def _add(root, *items, card=w.CARD, caller="reader", session=True):
    return w.run_cli(root, "verdict", "add", card, *items, session=session, caller=caller)


def _root(tmp_path, **kw):
    root = w.make_root(tmp_path, **kw)
    w.reader(root, "reader", "a1")
    return root


def test_the_owners_terminal_is_refused_as_by_owner(tmp_path):
    """Catches: the owner's terminal writing a verdict row (the verdict is never the owner's)."""
    code, _out, err = _add(_root(tmp_path), w.N1, "true", "fine", session=False)
    assert code == 1
    assert "verdict-by-owner" in err


def test_a_session_with_no_permit_is_refused_as_no_caller(tmp_path):
    """Catches: a session whose id the gate did not leave writing a row with an invented `by`."""
    code, _out, err = _add(_root(tmp_path), w.N1, "true", "fine", caller=None)
    assert code == 1
    assert "verdict-no-caller" in err


def test_an_unknown_card_is_refused(tmp_path):
    """Catches: a verdict file written for a card that is not in the register."""
    code, _out, err = _add(_root(tmp_path), w.N1, "true", "fine", card="CARD-099")
    assert code == 1
    assert "card-unknown" in err


def test_a_call_with_no_reason_is_a_usage_error(tmp_path):
    """Catches: a call with a node and a word but no reason taking the word for the reason."""
    code, _out, err = _add(_root(tmp_path), w.N1, "true")
    assert code == 2
    assert "verdict add <card> <node>... <true|weak|wrong> <reason>" in err


def test_a_word_that_is_none_of_true_weak_wrong_is_a_usage_error(tmp_path):
    """Catches: a verdict word that the close check would read as a missing verdict written into the table."""
    code, _out, err = _add(_root(tmp_path), w.N1, "maybe", "fine")
    assert code == 2
    assert "true, weak or wrong" in err


def test_an_allowed_call_prints_the_rows_and_exits_zero(tmp_path):
    """Checks: an allowed call exits 0 and names the node, the word and the reader run it used."""
    code, out, _err = _add(_root(tmp_path), w.N1, "true", "one clause, one case")
    assert code == 0
    assert (w.N1 in out, "a1" in out) == (True, True)


def test_several_nodes_in_one_call_write_one_row_each(tmp_path):
    """Checks: the node argument repeated: one row per node, all with the call's word and reason."""
    root = _root(tmp_path)
    _add(root, w.N1, w.N2, "true", "one clause, one case")
    assert [(r.node, r.verdict, r.reason) for r in verdicts.rows_of(root, w.CARD)] == [
        (w.N1, "true", "one clause, one case"), (w.N2, "true", "one clause, one case")]


def test_in_watch_mode_a_watched_refusal_is_logged_and_the_row_is_written(tmp_path):
    """Checks: watch mode with no reader run writes the row, and the refusal log holds a would-refuse row with the reason id."""
    root = w.make_root(tmp_path, mode="watch")
    code, _out, _err = _add(root, w.N1, "true", "fine")
    assert code == 0
    assert [(r["reason_id"], r["kind"]) for r in w.refusal_rows(root)] == [("verdict-no-reader-run", "would-refuse")]
    assert len(verdicts.rows_of(root, w.CARD)) == 1


def test_a_profile_with_no_mode_refuses_the_same_call(tmp_path):
    """Catches: a profile without `tests.verdict_add.mode` letting a call with no reader run through (ruling R196a)."""
    root = w.make_root(tmp_path)
    code, _out, err = _add(root, w.N1, "true", "fine")
    assert code == 1
    assert "verdict-no-reader-run" in err


def test_a_bare_card_number_takes_the_card_prefix(tmp_path):
    """Checks: `1` names CARD-001, as in the other card commands."""
    root = _root(tmp_path)
    code, _out, _err = _add(root, w.N1, "true", "fine", card="1")
    assert code == 0
    assert len(verdicts.rows_of(root, w.CARD)) == 1


def test_a_refusal_leaves_a_row_in_the_refusal_log(tmp_path):
    """Checks: a refusal leaves one row with its reason id and the card as target."""
    root = _root(tmp_path)
    _add(root, w.N1, "true", "fine", session=False)
    assert [(r["reason_id"], r["target"], r["kind"]) for r in w.refusal_rows(root)] == [
        ("verdict-by-owner", w.CARD, "refuse")]


def test_a_verdict_file_that_is_not_utf8_is_refused_and_left_alone(tmp_path):
    """Catches: a verdict file the command cannot read overwritten with a new table, losing what it held."""
    root = _root(tmp_path)
    (root / "tests" / "verdicts").mkdir()
    (root / w.VERDICT_REL).write_bytes(b"\xff\xfe\x00bad")
    code, _out, err = _add(root, w.N1, "true", "fine")
    assert code == 1
    assert "not written" in err
    assert (root / w.VERDICT_REL).read_bytes() == b"\xff\xfe\x00bad"
