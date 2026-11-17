"""Card MW-108: `card take` records the red a card inherits, the orderer's close needs it green, and `card release-red`
moves an inherited red to another named card. Each test builds the tiny synthetic project of `_mw108.py` (a real git
repository, real pytest runs, the real card commands run in process). The take never runs the suite: it reads the rows
the gate kept. Synthetic names only."""
from _mw108 import (GREEN, KEYS, ORD, RED, THIRD, close_result, commit_file, hold_both, inherited_rows, make_head_row,
                    open_card, project, reason_of, release_red, remove_file, seed_row, set_status, state, take,
                    two_cards)


def _keys_red_at_head(tmp_path, paths="`app.py`, `tests/test_keys.py`"):
    """A project whose HEAD has a red test in tests/test_keys.py and a row for HEAD's tree, and the card that holds it."""
    root = project(tmp_path)
    card = open_card(root, "Keys", paths)
    commit_file(root, "tests/test_keys.py", RED.format(name="keys"))
    make_head_row(root)
    return root, card


def test_take_records_the_red_at_head_inside_the_cards_paths(tmp_path):
    """Checks: a take with a red at HEAD in the card's Paths and a row for HEAD's tree writes a take row in
    `inherited_red.jsonl` that holds that id as red (E19)."""
    root, card = _keys_red_at_head(tmp_path)
    code, out, err = take(root, card)
    assert code == 0, err
    (row,) = inherited_rows(root)
    assert (row["kind"], row["card"], row["established"], row["red"], row["green"]) == ("take", card, True, [KEYS], [])
    assert "inherited red: 1" in out


def test_take_does_not_record_a_red_outside_the_cards_paths(tmp_path):
    """Checks: the nearest allow of E19: a red at HEAD in a file the card's Paths do not hold is not the card's inherited
    red, the row is established and holds no id (E20)."""
    root = project(tmp_path)
    card = open_card(root, "Green", "`app.py`")
    commit_file(root, "tests/test_orphan.py", RED.format(name="orphan"))
    make_head_row(root)
    assert take(root, card)[0] == 0
    (row,) = inherited_rows(root)
    assert (row["established"], row["red"]) == (True, [])


def test_take_without_a_head_row_records_not_established_and_runs_nothing(tmp_path):
    """Catches: a take that stays silent when it cannot tell the red at HEAD, or one that runs the suite to find out: the
    row says not established, the take goes on, no run row is written (E21, R283 condition 1)."""
    root = project(tmp_path)
    card = open_card(root, "Keys", "`app.py`, `tests/test_keys.py`")
    commit_file(root, "tests/test_keys.py", RED.format(name="keys"))
    code, out, err = take(root, card)
    assert code == 0, err
    (row,) = inherited_rows(root)
    assert (row["kind"], row["established"], row["red"]) == ("take", False, [])
    assert "not established" in out
    assert not (state(root) / "commit_tests_head.jsonl").exists()
    assert not (state(root) / "commit_tests.jsonl").exists()


def test_take_reads_the_nearest_older_record_when_head_has_none(tmp_path):
    """Checks: HEAD's tree has no row, an older commit of HEAD's history has one that holds the id red: the id is recorded
    red (E22, R283 condition 2)."""
    root, card = _keys_red_at_head(tmp_path)
    commit_file(root, "extra.txt", "x\n")
    assert take(root, card)[0] == 0
    (row,) = inherited_rows(root)
    assert (row["established"], row["red"]) == (True, [KEYS])


def test_take_reads_a_nearer_green_record_over_an_older_red_one(tmp_path):
    """Catches: an id fixed since an older record still counted as inherited red: the nearer row of HEAD's tree is a pass,
    so the id is recorded green and is not inherited (E23, R283 condition 2)."""
    root, card = _keys_red_at_head(tmp_path)
    commit_file(root, "tests/test_keys.py", GREEN.format(name="keys"))
    seed_row(root, "pass")
    assert take(root, card)[0] == 0
    (row,) = inherited_rows(root)
    assert (row["established"], row["red"], row["green"]) == (True, [], [KEYS])


def _taken_and_held(tmp_path):
    """CARD-001 holds a red at HEAD in its Paths, recorded at its take; CARD-002 is open; both held, both ordered by ORD."""
    root = project(tmp_path)
    first, second = two_cards(root)
    commit_file(root, "tests/test_keys.py", RED.format(name="keys"))
    make_head_row(root)
    assert take(root, first)[0] == 0
    hold_both(root, first, second)
    return root, first, second


def test_close_is_refused_while_an_inherited_red_is_still_red(tmp_path):
    """Catches: a card closed on its Acceptance rows while the red it inherited is still red; the text names the id and the
    way out, the release to another card (E24)."""
    root, first, _second = _taken_and_held(tmp_path)
    reason, text = close_result(root, first)
    assert reason == "close-tests-failing", text
    assert KEYS in text
    assert "card release-red" in text


def test_way_out_of_close_tests_failing_the_close_passes_when_the_inherited_red_is_green(tmp_path):
    """Checks: the way out of the close refusal works: once the inherited test is green at HEAD the same close passes
    (E25)."""
    root, first, _second = _taken_and_held(tmp_path)
    assert close_result(root, first)[0] == "close-tests-failing"
    commit_file(root, "tests/test_keys.py", GREEN.format(name="keys"))
    assert close_result(root, first) == ("ok", "closed")


def test_a_deleted_inherited_red_test_still_blocks_the_close(tmp_path):
    """Catches: an inherited red hidden by deleting or renaming its test: a missing test counts as red at the close
    (E26)."""
    root, first, _second = _taken_and_held(tmp_path)
    remove_file(root, "tests/test_keys.py")
    reason, text = close_result(root, first)
    assert reason == "close-tests-failing", text


def test_a_close_with_a_take_that_is_not_established_refuses_a_red_in_the_cards_paths(tmp_path):
    """Catches: fail-open at the close when the take could not be established: any red test file in the card's Paths
    refuses (E27, R283 condition 1)."""
    root = project(tmp_path)
    first, second = two_cards(root)
    commit_file(root, "tests/test_keys.py", RED.format(name="keys"))
    assert take(root, first)[0] == 0
    hold_both(root, first, second)
    reason, text = close_result(root, first)
    assert reason == "close-tests-failing", text
    assert "tests/test_keys.py" in text


def test_a_close_with_a_take_that_is_not_established_passes_when_the_cards_paths_are_green(tmp_path):
    """Checks: the nearest allow of E27: a take that is not established does not block a card whose test files in its Paths
    are green (E28)."""
    root = project(tmp_path)
    first, second = two_cards(root)
    commit_file(root, "tests/test_keys.py", GREEN.format(name="keys"))
    assert take(root, first)[0] == 0
    assert [r["established"] for r in inherited_rows(root)] == [False]
    hold_both(root, first, second)
    assert close_result(root, first) == ("ok", "closed")


def test_release_red_moves_the_id_to_the_other_card_and_the_close_follows(tmp_path):
    """Checks: after the orderer releases the inherited id to another card, the first card closes with the test still
    red and the other card's close needs it green (E29)."""
    root, first, second = _taken_and_held(tmp_path)
    code, out, err = release_red(root, KEYS, second)
    assert code == 0, err
    assert close_result(root, first) == ("ok", "closed")
    reason, text = close_result(root, second, closer=ORD)
    assert reason == "close-tests-failing", text
    assert KEYS in text


def test_release_red_row_names_the_orderer(tmp_path):
    """Checks: the release is one row in `inherited_red.jsonl` with the from card, the to card, the test id and the session
    of the orderer as `by` (E30, R283 condition 4)."""
    root, first, second = _taken_and_held(tmp_path)
    assert release_red(root, KEYS, second)[0] == 0
    row = inherited_rows(root)[-1]
    assert (row["kind"], row["card"], row["to"], row["test"], row["by"], row["session"]) == (
        "release-red", first, second, KEYS, ORD, ORD)


def test_release_red_by_a_session_that_did_not_order_the_card_is_refused(tmp_path):
    """Catches: any session moving a red off a card it did not order; refused `close-not-orderer`, nothing written
    (E31)."""
    root, first, second = _taken_and_held(tmp_path)
    code, out, err = release_red(root, KEYS, second, session=THIRD)
    assert code != 0
    assert reason_of(err) == "close-not-orderer", err
    assert [r["kind"] for r in inherited_rows(root)] == ["take"]


def test_release_red_of_an_id_no_card_inherited_is_refused(tmp_path):
    """Catches: a release of a test no open card inherited; refused `card-bad-move`, nothing written (E32)."""
    root, first, second = _taken_and_held(tmp_path)
    code, out, err = release_red(root, "tests/test_keys.py::test_other", second)
    assert code != 0
    assert reason_of(err) == "card-bad-move", err
    assert [r["kind"] for r in inherited_rows(root)] == ["take"]


def test_release_red_to_a_card_not_in_the_register_is_refused(tmp_path):
    """Catches: a red moved to a card that does not exist; refused `card-unknown`, nothing written (E33)."""
    root, first, second = _taken_and_held(tmp_path)
    code, out, err = release_red(root, KEYS, "CARD-099")
    assert code != 0
    assert reason_of(err) == "card-unknown", err
    assert [r["kind"] for r in inherited_rows(root)] == ["take"]


def test_release_red_to_a_card_that_is_not_open_is_refused(tmp_path):
    """Catches: a red moved to a card that cannot own it: the named owner must be an open card (E34, R283 condition 4)."""
    root, first, second = _taken_and_held(tmp_path)
    assert set_status(root, second, "waiting") == 0
    code, out, err = release_red(root, KEYS, second)
    assert code != 0
    assert reason_of(err) == "card-bad-move", err
    assert [r["kind"] for r in inherited_rows(root)] == ["take"]


def test_release_red_without_a_named_card_is_refused(tmp_path):
    """Catches: a red released to nobody: `--to` is required (E35, R283 condition 4)."""
    root, first, second = _taken_and_held(tmp_path)
    code, out, err = release_red(root, KEYS, None)
    assert code == 2
    assert "--to" in err
    assert [r["kind"] for r in inherited_rows(root)] == ["take"]

