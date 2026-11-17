"""Card MW-056, the decision of the commit gate as table tests: failing ids of the staged tree, failing ids of HEAD, the
committing card's Paths and the open cards -> which reds block. No git, no run: `gate_commit_tests.judge` is a pure
function. Synthetic ids only."""
import pytest

from _engine import REPO  # noqa: F401  (puts the engine folder on the path)
import gate_commit_tests as gct

ONE = ("CARD-001", frozenset({"app.py", "tests/test_one.py"}))
TWO = ("CARD-002", frozenset({"tests/test_two.py"}))
THREE = ("CARD-003", frozenset({"tests/three"}))
OPEN = [ONE, TWO, THREE]

T_ONE = "tests/test_one.py::test_one"
T_TWO = "tests/test_two.py::test_two"
T_NONE = "tests/test_none.py::test_none"
T_THREE = "tests/three/test_deep.py::test_deep"


def run(staged, head, card=ONE, open_cards=OPEN):
    return gct.judge(staged, head, card, open_cards)


@pytest.mark.parametrize("staged, head", [
    pytest.param([T_NONE], [], id="new, in no card's Paths"),
    pytest.param([T_TWO], [], id="new, in another open card's Paths"),
    pytest.param([T_ONE], [], id="new, in the committing card's Paths"),
    pytest.param([T_TWO, T_NONE], [T_TWO], id="new beside an old red of another card"),
])
def test_a_new_red_blocks_whoever_owns_it(staged, head):
    """Catches: a gate that lets a new red through because its file belongs to someone else. E1: a test red in the staged tree and green at HEAD is new breakage: it blocks, in the Paths of the committing card, of another open card, or of none."""
    got = run(staged, head)
    assert got.blocked
    assert got.new
    assert run([T_NONE], []).new == [T_NONE]
    assert run([T_TWO, T_NONE], [T_TWO]).new == [T_NONE]
    assert run([T_TWO, T_NONE], [T_TWO]).owned == {T_TWO: "CARD-002"}


def test_a_red_test_of_the_committing_card_blocks():
    """Catches: a card that commits code while its own test is red. E2: a test of the committing card's own Paths that is red in the staged tree blocks even when it was already red at HEAD."""
    got = run([T_ONE], [T_ONE])
    assert got.blocked
    assert got.own == [T_ONE]
    assert got.new == []
    assert got.owned == {}
    # the card's own Paths win over another card's: the test is the committing card's before it is anyone else's
    both = ("CARD-004", frozenset({T_ONE.split("::")[0]}))
    got = run([T_ONE], [T_ONE], open_cards=[ONE, both])
    assert got.own == [T_ONE]
    assert got.owned == {}
    # a committing card that is not known (no card taken) owns nothing
    got = run([T_ONE], [T_ONE], card=None, open_cards=[])
    assert got.own == []
    assert got.orphan == [T_ONE]
    assert not got.blocked  # MW108-D1: no card taken, so the red has no owner: shown, never blocking
    assert "old red: tests/test_one.py::test_one, owner none" in gct._allow_line(got)


def test_an_old_red_of_an_open_card_does_not_block_and_names_its_owner():
    """Catches: the real-install bug, where two cards mid-way blocked every other card. E3: a test red at HEAD and red in the staged tree, inside the Paths of another open card, does not block; the judgement names that card."""
    got = run([T_TWO, T_THREE], [T_TWO, T_THREE])
    assert not got.blocked
    assert got.owned == {T_TWO: "CARD-002", T_THREE: "CARD-003"}
    assert got.new == got.own == got.orphan == []


def test_an_old_red_that_no_open_card_owns_blocks():
    """Catches: a red nobody owns that stops every commit (MW108-D1, the name is kept for the cards that cite it). E4: a test red at HEAD, in no open card's Paths, has no owner and does not block; the judgement names it as an orphan and the allow line shows `owner none`."""
    got = run([T_NONE, T_TWO], [T_NONE, T_TWO])
    assert not got.blocked
    assert got.orphan == [T_NONE]
    assert got.owned == {T_TWO: "CARD-002"}
    assert "old red: tests/test_none.py::test_none, owner none" in gct._allow_line(got)
    got = run([T_NONE], [T_NONE], open_cards=[])
    assert not got.blocked
    assert got.orphan == [T_NONE]
    assert "old red: tests/test_none.py::test_none, owner none" in gct._allow_line(got)


@pytest.mark.parametrize("head", [
    pytest.param([], id="nothing red at HEAD"),
    pytest.param([T_TWO], id="one red at HEAD, fixed"),
    pytest.param([T_ONE, T_NONE], id="two reds at HEAD, both fixed"),
])
def test_green_tests_and_fixed_tests_never_block(head):
    """Checks: a verdict that holds HEAD's red against a commit that fixes it. E5: no red in the staged tree is allowed whatever HEAD was; a test red at HEAD and green now is a fix."""
    got = run([], head)
    assert not got.blocked
    assert got.owned == {}
    got = run([T_TWO], [T_TWO, T_NONE])
    assert not got.blocked


@pytest.mark.parametrize("ident", [
    pytest.param(T_TWO.split("::")[0], id="file only"),
    pytest.param(T_TWO + "[a-1]", id="parametrised id"),
    pytest.param(T_TWO.replace("/", "\\"), id="backslashes"),
    pytest.param(T_THREE, id="folder entry"),
])
def test_the_owner_is_read_from_the_file_of_the_id_and_a_folder_entry_counts(ident):
    """Catches: ownership by exact string, which no real id would ever match. E6: an id is judged by its file (the part before `::`; a collection error names the file alone, a parametrised id keeps its brackets); a Paths entry that names a folder owns every file below it; backslashes read as slashes."""
    got = run([ident], [ident])
    assert not got.blocked
    assert list(got.owned) == [ident.replace("\\", "/")]  # the id is kept with `/`, as it is shown and compared
    assert run([T_THREE], [T_THREE]).owned == {T_THREE: "CARD-003"}
    # a folder entry does not own a sibling folder that only starts with the same letters
    got = run(["tests/three_more/test_x.py::test_x"], ["tests/three_more/test_x.py::test_x"])
    assert not got.blocked  # MW108-D1: owned by no open card, so an orphan: shown, never blocking
    assert got.orphan == ["tests/three_more/test_x.py::test_x"]
    assert "old red: tests/three_more/test_x.py::test_x, owner none" in gct._allow_line(got)


def test_the_first_open_card_in_register_order_is_named_when_two_own_a_file():
    """Catches: an unstable owner that changes between two attempts. E7: when two open cards both name the file, the judgement names the first in the order given (the register's)."""
    twin = ("CARD-005", frozenset({T_TWO.split("::")[0]}))
    assert run([T_TWO], [T_TWO], open_cards=[ONE, TWO, twin]).owned == {T_TWO: "CARD-002"}
    assert run([T_TWO], [T_TWO], open_cards=[ONE, twin, TWO]).owned == {T_TWO: "CARD-005"}


@pytest.mark.parametrize("head", [
    pytest.param([], id="nothing red at HEAD"),
    pytest.param([T_TWO], id="one red at HEAD"),
    pytest.param([T_ONE, T_TWO], id="two reds at HEAD"),
])
def test_the_buckets_keep_the_order_of_the_staged_run_and_repeat_exactly(head):
    """Checks: a set-ordered list, whose refusal text would change between two attempts. E7 (stability): the buckets list the ids in the order the run printed them, and the same inputs give the same buckets."""
    staged = [T_NONE, T_TWO, T_ONE, T_THREE, "tests/test_aaa.py::test_aaa"]
    first = run(staged, head)
    assert first == run(staged, head)
    assert first.new == [t for t in staged if t not in head]
    assert run(staged, []).new == staged
