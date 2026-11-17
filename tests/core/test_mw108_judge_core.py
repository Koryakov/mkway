"""Card MW-108, the this-commit judgement as table tests: failing ids of the staged tree and of HEAD, the committing card's
Paths and its inherited red (recorded at take) -> which reds block, the allow line, the refusal text, the old red list of the
commit row, and the inherited red of a card read from its take and release rows. No git, no run: the functions are pure.
Synthetic ids only."""
import pytest

from _engine import REPO  # noqa: F401  (puts the engine folder on the path)
import cardtool
import gate_commit_tests as gct

ONE = ("CARD-001", frozenset({"app.py", "tests/test_one.py"}))
TWO = ("CARD-002", frozenset({"tests/test_two.py"}))
OPEN = [ONE, TWO]

T_ONE = "tests/test_one.py::test_one"
T_TWO = "tests/test_two.py::test_two"
T_NONE = "tests/test_none.py::test_none"
T_NEW = "tests/test_new.py::test_new"
CASE_ONE = "tests/test_one.py::test_one[a]"
GREEN_TWO = "tests/test_two.py::test_two_green"

# what the take and release rows of CARD-001 came to: (taken, established, red, green, released)
INHERITED = (True, True, (T_ONE,), (), {})
RELEASED = (True, True, (), (), {T_ONE: "CARD-002"})
NOT_ESTABLISHED = (True, False, (), (), {})
RECORDED_GREEN = (True, True, (), (T_ONE,), {})
NO_RECORD_OF_IT = (True, True, (T_TWO,), (), {})


def inh(spec):
    """The `Inherited` of a spec above."""
    taken, established, red, green, released = spec
    return cardtool.Inherited(taken, established, frozenset(red), frozenset(green), dict(released))

WAY_OUT = "the next merge writes the row; until then every red counts as new for this card"


@pytest.mark.parametrize("staged, head", [
    pytest.param([T_NEW, T_ONE], [T_ONE], id="beside an old red of the committing card"),
    pytest.param([T_NEW, T_NONE], [T_NONE], id="beside an old red that no card owns"),
    pytest.param([T_NEW, T_TWO], [T_TWO], id="beside an old red of another open card"),
])
def test_a_new_red_still_blocks_beside_an_old_red(staged, head):
    """Catches: an old red that lets a new red through; the nearest deny of the old-red allowance (E1)."""
    got = gct.judge(staged, head, ONE, OPEN, inherited=inh(INHERITED))
    assert got.blocked
    assert got.new == [T_NEW]


def test_an_old_red_in_the_committing_cards_paths_does_not_block():
    """Catches: a card that cannot commit while the red it inherited at its take is still red (E2, DD-010)."""
    got = gct.judge([T_ONE], [T_ONE], ONE, OPEN, inherited=inh(INHERITED))
    assert not got.blocked
    assert got.old_own == [T_ONE]
    assert got.own == []
    assert got.new == []


@pytest.mark.parametrize("card, open_cards", [
    pytest.param(ONE, OPEN, id="a card is committing"),
    pytest.param(None, [], id="no card is taken"),
])
def test_an_old_red_that_no_open_card_owns_does_not_block(card, open_cards):
    """Catches: a red nobody owns that every commit then fails on (E3, DD-001)."""
    got = gct.judge([T_NONE], [T_NONE], card, open_cards)
    assert not got.blocked
    assert got.orphan == [T_NONE]
    assert got.new == []


@pytest.mark.parametrize("inherited", [
    pytest.param(INHERITED, id="the card inherited another test"),
    pytest.param((True, True, (CASE_ONE,), (), {}), id="the case is in the record"),
])
def test_a_case_absent_at_head_in_the_committing_cards_file_still_blocks(inherited):
    """Catches: a new red case of the card's own file excused as inherited because the card inherited something (E4)."""
    got = gct.judge([CASE_ONE], [], ONE, OPEN, head_seen={GREEN_TWO}, inherited=inh(inherited))
    assert got.blocked
    assert got.own == [CASE_ONE]
    assert got.old_own == []


def test_the_allow_line_names_each_old_red_with_its_owner():
    """Checks: the allow line shows the card's own old red with its card, an orphan with no owner, and the red of another
    open card as before (E5)."""
    got = gct.judge([T_ONE, T_NONE, T_TWO], [T_ONE, T_NONE, T_TWO], ONE, OPEN, inherited=inh(INHERITED))
    line = gct._allow_line(got)
    assert line.startswith("the commit is allowed: no new red")
    assert "old red: tests/test_one.py::test_one, owner CARD-001" in line
    assert "old red: tests/test_none.py::test_none, owner none" in line
    assert "tests/test_two.py::test_two still red, owned by CARD-002" in line


def test_an_old_red_file_that_failed_at_collection_does_not_block():
    """Catches: the DD-001 trap, a file that failed at collection at HEAD with only a closed owner, blocking every commit
    (E6)."""
    closed = [("CARD-004", frozenset({"tests/test_old.py"}))]
    got = gct.judge(["tests/test_old.py::test_a"], ["tests/test_old.py"], ONE, OPEN, closed_cards=closed)
    assert not got.blocked
    line = gct._allow_line(got)
    assert "old red: tests/test_old.py::test_a, owner none" in line
    assert "failed at collection at HEAD" in line
    assert "closed card CARD-004" in line


@pytest.mark.parametrize("card_id, fragment", [
    pytest.param("CARD-001", 'git commit -m "CARD-001 tests only: <what>" -- <test files>', id="a card is taken"),
    pytest.param(None, 'git commit -m "<card id> tests only: <what>" -- <test files>', id="no card is taken"),
])
def test_the_refusal_of_a_new_red_names_the_way_out_in_plain_form(card_id, fragment):
    """Catches: a refusal whose way out cannot be typed: the red-first commit in the plain form the lock gate reads (E7)."""
    got = gct.judge([T_NEW], [], ONE, OPEN)
    text = gct._refusal(got, card_id, ["tests"])
    assert fragment in text
    assert "an old red does not block" in text


@pytest.mark.parametrize("inherited, want", [
    pytest.param(INHERITED, [{"test": T_NONE, "card": None}, {"test": T_ONE, "card": "CARD-001"},
                             {"test": T_TWO, "card": "CARD-002"}], id="inherited, orphan and another card"),
    pytest.param(RELEASED, [{"test": T_NONE, "card": None}, {"test": T_ONE, "card": "CARD-002"},
                            {"test": T_TWO, "card": "CARD-002"}], id="the inherited id released to another card"),
])
def test_the_old_red_list_of_a_commit_names_every_old_red_with_its_card(inherited, want):
    """Checks: the `old_red` field of the commit row, one object per old red in the order of the run, card null for an
    orphan, the card the id was released to (E8)."""
    run = [T_NONE, T_ONE, T_TWO]
    got = gct.judge(run, run, ONE, OPEN, inherited=inh(inherited))
    assert not got.blocked
    assert gct.old_red_list(got, "CARD-001", run) == want


@pytest.mark.parametrize("rows, card, want", [
    pytest.param([{"kind": "take", "card": "CARD-001", "established": True, "red": ["a", "b"], "green": ["c"]}],
                 "CARD-001", (True, True, {"a", "b"}, {"c"}, {}), id="a take that is established"),
    pytest.param([], "CARD-001", (False, False, set(), set(), {}), id="no row: a card taken before the record"),
    pytest.param([{"kind": "take", "card": "CARD-001", "established": False, "red": [], "green": []}],
                 "CARD-001", (True, False, set(), set(), {}), id="a take that is not established"),
    pytest.param([{"kind": "take", "card": "CARD-002", "established": True, "red": ["a"], "green": []}],
                 "CARD-001", (False, False, set(), set(), {}), id="the take of another card"),
    pytest.param([{"kind": "take", "card": "CARD-001", "established": True, "red": ["a", "b"], "green": []},
                  {"kind": "release-red", "card": "CARD-001", "to": "CARD-002", "test": "a"}],
                 "CARD-001", (True, True, {"b"}, set(), {"a": "CARD-002"}), id="a release moves the id away"),
    pytest.param([{"kind": "take", "card": "CARD-001", "established": True, "red": ["a", "b"], "green": []},
                  {"kind": "release-red", "card": "CARD-001", "to": "CARD-002", "test": "a"}],
                 "CARD-002", (False, False, {"a"}, set(), {}), id="a release moves the id to the other card"),
    pytest.param([{"kind": "take", "card": "CARD-001", "established": True, "red": ["a", "b"], "green": []},
                  {"kind": "release-red", "card": "CARD-001", "to": "CARD-002", "test": "a"},
                  {"kind": "take", "card": "CARD-001", "established": True, "red": ["a", "b"], "green": []}],
                 "CARD-001", (True, True, {"b"}, set(), {"a": "CARD-002"}), id="a take after the release does not bring it back"),
])
def test_the_inherited_red_of_a_card_follows_takes_and_releases(rows, card, want):
    """Checks: the red a card inherited is its take rows plus what was released to it, minus what was released away; a
    take that is not established adds none (E9)."""
    assert tuple(cardtool.inherited_from_rows(rows, card)) == want


def test_a_red_in_the_cards_paths_is_new_when_its_take_is_not_established():
    """Catches: fail-open when the take could not be established: every red in the card's Paths counts as new, and the
    text says so and names the way out (E10, R283 conditions 1 and 3)."""
    got = gct.judge([T_ONE], [T_ONE], ONE, OPEN, inherited=inh(NOT_ESTABLISHED))
    assert got.blocked
    assert got.own == [T_ONE]
    text = gct._refusal(got, "CARD-001", ["tests"])
    assert "take record of CARD-001 is not established" in text
    assert WAY_OUT in text


def test_a_red_in_the_cards_paths_that_was_recorded_green_at_take_is_new():
    """Catches: a red the card made itself after its take passed as inherited (E11, R283 condition 2)."""
    got = gct.judge([T_ONE], [T_ONE], ONE, OPEN, inherited=inh(RECORDED_GREEN))
    assert got.blocked
    assert got.own == [T_ONE]
    text = gct._refusal(got, "CARD-001", ["tests"])
    assert "recorded green when CARD-001 was taken" in text


def test_a_red_in_the_cards_paths_that_the_take_record_does_not_hold_is_new():
    """Catches: a red with no record at take passed as old: no record is new, with the way out in the text (E12, R283
    condition 2 and 3)."""
    got = gct.judge([T_ONE], [T_ONE], ONE, OPEN, inherited=inh(NO_RECORD_OF_IT))
    assert got.blocked
    assert got.own == [T_ONE]
    text = gct._refusal(got, "CARD-001", ["tests"])
    assert "holds no record of it" in text
    assert WAY_OUT in text
