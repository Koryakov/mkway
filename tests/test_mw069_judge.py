"""Card MW-069, the decision about a test whose FILE failed at collection at HEAD, as table tests: failing ids of the
staged tree, failing ids of HEAD (a file that failed at collection is one bare file id there), the committing card's
Paths, the open cards and the closed cards -> which reds block and how the refusal reads. No git, no run:
`gate_commit_tests.judge` and `_refusal` are pure. Synthetic ids only."""
import pytest

from _engine import REPO  # noqa: F401  (puts the engine folder on the path)
import gate_commit_tests as gct

COMMITTING = ("CARD-001", frozenset({"newmod.py"}))
OTHER = ("CARD-002", frozenset({"tests/test_b.py"}))
OPEN = [COMMITTING, OTHER]
CLOSED_B = [("CARD-004", frozenset({"tests/test_b.py"}))]
FILE_B = "tests/test_b.py"
CASE_B = "tests/test_b.py::test_value"
CASE_MINE = "tests/test_mine.py::test_value"
GREEN_C = "tests/test_c.py::test_green"  # collected and green at HEAD, red now: file c did not fail at collection


def run(staged, head=(FILE_B,), card=COMMITTING, open_cards=OPEN, closed_cards=()):
    return gct.judge(list(staged), list(head), card, open_cards, closed_cards=closed_cards)


def test_a_case_of_a_file_that_failed_at_collection_at_head_and_is_held_by_another_open_card_does_not_block():
    """Catches: the real-install refusal «new red, not red at HEAD» of a case whose file only failed as a whole there. E1: the file is one bare id in HEAD's failures, so its cases are red at HEAD, owned by the other open card: no block, the case is in `owned`, not new and not absent."""
    got = run([CASE_B], head=[FILE_B])
    assert not got.blocked
    assert got.owned == {CASE_B: "CARD-002"}
    assert got.new == []
    assert got.absent == {}
    assert got.orphan == []


def test_a_case_of_a_file_that_failed_at_collection_at_head_with_only_a_closed_owner_blocks_naming_it():
    """Catches: a closed card's red test that is called new red, or that stops every later commit (MW108-D1, the name is kept for the cards that cite it). E2: no open card holds the file, a closed card does: rule c tail, red at HEAD (an orphan, never new) and not blocking, and the judgement and the allow line name the closed owner."""
    got = run([CASE_B], head=[FILE_B], open_cards=[COMMITTING], closed_cards=CLOSED_B)
    assert not got.blocked
    assert got.orphan == [CASE_B]
    assert got.new == []
    assert got.absent == {}
    assert got.file_red == {CASE_B: "CARD-004"}
    assert f"old red: {CASE_B}, owner none (its file failed at collection at HEAD, closed card CARD-004)" in gct._allow_line(got)


def test_a_case_of_a_file_that_failed_at_collection_at_head_with_no_owner_at_all_blocks_without_a_card():
    """Catches: a never-owned red called new red, or a card name invented for it (MW108-D1, the name is kept for the cards that cite it). E3: no open and no closed card holds the file: red at HEAD with no owner and not blocking; the judgement names no card and the allow line says `owner none`."""
    got = run([CASE_B], head=[FILE_B], open_cards=[COMMITTING], closed_cards=[])
    assert not got.blocked
    assert got.orphan == [CASE_B]
    assert got.new == []
    assert got.file_red == {CASE_B: None}
    assert f"old red: {CASE_B}, owner none (its file failed at collection at HEAD)" in gct._allow_line(got)


def test_a_case_of_a_file_that_failed_at_collection_at_head_in_the_committing_cards_paths_blocks_as_its_own():
    """Catches: a card that lets its own red through because HEAD saw the file only as a whole. E4: the committing card holds the file: rule b, own red, whatever the closed cards hold."""
    mine_file = CASE_MINE.split("::")[0]
    mine = ("CARD-001", frozenset({"newmod.py", mine_file}))
    got = run([CASE_MINE], head=[mine_file], card=mine, open_cards=[mine, OTHER], closed_cards=CLOSED_B)
    assert got.blocked
    assert got.own == [CASE_MINE]
    assert got.new == []
    assert got.orphan == []
    assert got.absent == {}


def test_a_case_of_a_file_that_did_not_fail_at_collection_at_head_stays_new_red():
    """Catches: the new rule swallowing rule a. E5: nearest allow/deny boundary: the same red case whose file is NOT in HEAD's failures was collected and green at HEAD, so it is new red whoever owns the file (rule a)."""
    green_file = GREEN_C.split("::")[0]
    got = run([GREEN_C], head=[FILE_B], open_cards=OPEN + [("CARD-003", frozenset({green_file}))])
    assert got.blocked
    assert got.new == [GREEN_C]
    assert got.owned == {}
    assert got.file_red == {}


def test_a_red_at_head_with_its_own_id_is_not_listed_as_a_collection_failure():
    """Catches: every old red being relabelled as a collection failure in the refusal. E6: a case that was red at HEAD by its own id (its file collected) keeps the MW-056 buckets and is not in `file_red`."""
    got = run([CASE_B], head=[CASE_B], open_cards=[COMMITTING], closed_cards=CLOSED_B)
    assert got.orphan == [CASE_B]
    assert got.file_red == {}


@pytest.mark.parametrize("closed, said, not_said", [
    (CLOSED_B, [f"old red: {CASE_B}", "owner none", "failed at collection at HEAD", "CARD-004", "closed card"], ["new red"]),
    ([], [f"old red: {CASE_B}", "owner none", "failed at collection at HEAD"], ["new red", "CARD-004"]),
    # MW108-D1: «new red» stays forbidden; only the allow line's own «no new red» is taken out first
])
def test_the_refusal_says_the_file_was_already_red_at_head_and_names_the_closed_owner(closed, said, not_said):
    """Catches: the message «new red, not red at HEAD» for a file that failed at HEAD (MW108-D1, the name is kept for the cards that cite it). E7: the allow line for such a case, which no longer refuses, says the file failed at collection at HEAD and names the closed owner card, or says it has no owner; it never says «new red, not red at HEAD»."""
    got = run([CASE_B], head=[FILE_B], open_cards=[COMMITTING], closed_cards=closed)
    text = gct._allow_line(got)
    assert CASE_B in text
    missing = [word for word in said if word not in text]
    assert missing == [], text
    claims = text.replace("no new red", "")
    present = [word for word in not_said if word in claims]
    assert present == [], text
