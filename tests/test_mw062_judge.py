"""Card MW-062, the decision about a test that is absent at HEAD, as table tests: failing ids of the staged tree, failing
ids of HEAD, the ids HEAD collected, the committing card's Paths and the open cards -> which reds block. No git, no run:
`gate_commit_tests.judge`, `_allow_line`, `collect_argv` and `collected_ids` are pure. Synthetic ids only."""
from _engine import REPO  # noqa: F401  (puts the engine folder on the path)
import gate_commit_tests as gct

ONE = ("CARD-001", frozenset({"items/", "tests/test_one.py"}))
TWO = ("CARD-002", frozenset({"tests/test_two.py"}))
THREE = ("CARD-003", frozenset({"tests/three"}))
OPEN = [ONE, TWO, THREE]

CASE_ONE = "tests/test_one.py::test_one[a]"
CASE_TWO = "tests/test_two.py::test_two[a]"
CASE_TWO_B = "tests/test_two.py::test_two[b]"
CASE_THREE = "tests/three/test_deep.py::test_deep[a]"
CASE_NONE = "tests/test_none.py::test_none[a]"
GREEN_TWO = "tests/test_two.py::test_two_green"  # collected at HEAD, green there


def run(staged, head=(), seen=(), card=ONE, open_cards=OPEN):
    """`seen`: the ids HEAD collected (red or green); the ids of `head` are red at HEAD and were collected too."""
    return gct.judge(list(staged), list(head), card, open_cards, head_seen=set(seen) | set(head))


def test_a_case_absent_at_head_is_judged_by_the_open_card_that_owns_its_file():
    """Catches: the real-install refusal of a card whose new files make another card's red-first cases appear. E1: red now, not collected at HEAD, file in another open card's Paths: no block; the judgement names the owner, by the file, never by the id (a folder entry owns the files below it)."""
    got = run([CASE_TWO, CASE_TWO_B, CASE_THREE], seen=[GREEN_TWO])
    assert not got.blocked
    assert got.absent == {CASE_TWO: "CARD-002", CASE_TWO_B: "CARD-002", CASE_THREE: "CARD-003"}
    assert got.new == got.own == got.orphan == []
    assert got.owned == {}


def test_a_case_absent_at_head_in_the_file_of_the_committing_card_blocks():
    """Catches: a card that lets its own new red through because HEAD never saw it. E2: the owner is the committing card: rule b, the commit is refused, whatever other cards also hold the file."""
    got = run([CASE_ONE], seen=[GREEN_TWO])
    assert got.blocked
    assert got.own == [CASE_ONE]
    assert got.absent == {}
    assert got.new == []
    twin = ("CARD-004", frozenset({CASE_ONE.split("::")[0]}))
    got = run([CASE_ONE], seen=[GREEN_TWO], open_cards=[twin, ONE])
    assert got.own == [CASE_ONE]
    assert got.absent == {}


def test_a_case_absent_at_head_that_no_open_card_owns_blocks():
    """Catches: a red nobody is working on that every commit then passes. E3: no open card holds the file: rule c, no owner, the commit is refused and the case is named as new red. A card that is not open (`waiting`, closed) is not in the open list and owns nothing; no card taken owns nothing."""
    got = run([CASE_NONE], seen=[GREEN_TWO])
    assert got.blocked
    assert got.new == [CASE_NONE]
    assert got.absent == {}
    waiting_only = [ONE, THREE]  # CARD-002 is waiting: the register lists it as not open
    got = run([CASE_TWO], seen=[GREEN_TWO], open_cards=waiting_only)
    assert got.blocked
    assert got.new == [CASE_TWO]
    assert got.absent == {}
    got = run([CASE_TWO], seen=[GREEN_TWO], card=None, open_cards=[])
    assert got.blocked
    assert got.new == [CASE_TWO]


def test_rules_a_and_c_stay_as_they_were_for_a_test_that_exists_at_head():
    """Catches: the new rule swallowing the old ones. E4: green at HEAD (collected there) and red now is rule a, new red, even in another open card's file; red at HEAD and still red keeps MW-056 (owned by another open card does not block, the committing card's own does, no owner does); an id with no `::` (a file that now fails at collection) is never absent; when HEAD's ids are not known (`head_seen` None) nothing is absent."""
    got = run([GREEN_TWO], seen=[GREEN_TWO])
    assert got.blocked
    assert got.new == [GREEN_TWO]
    assert got.absent == {}
    got = run([CASE_TWO, CASE_ONE, CASE_NONE], head=[CASE_TWO, CASE_ONE, CASE_NONE])
    assert got.owned == {CASE_TWO: "CARD-002"}
    assert got.own == [CASE_ONE]
    assert got.orphan == [CASE_NONE]
    assert got.new == []
    assert got.absent == {}
    bare_file = CASE_TWO.split("::")[0]
    got = run([bare_file], seen=[GREEN_TWO])
    assert got.blocked
    assert got.new == [bare_file]
    assert got.absent == {}
    old = gct.judge([CASE_TWO], [], ONE, OPEN)  # the call of MW-056: no `head_seen`
    assert old.blocked
    assert old.new == [CASE_TWO]
    assert old.absent == {}
    unknown = gct.judge([CASE_TWO], [], ONE, OPEN, head_seen=None)
    assert unknown.blocked
    assert unknown.new == [CASE_TWO]
    assert unknown.absent == {}


def test_every_branch_at_once_buckets_in_the_order_of_the_run_and_the_owners_in_register_order():
    """Catches: a set ordered bucket or an owner that changes between two attempts. E5: one run with a case of each kind: each lands in its own bucket, in the order the run printed them; two open cards that hold a file: the first in register order owns it; the same inputs give the same answer."""
    twin = ("CARD-005", frozenset({CASE_TWO.split("::")[0]}))
    staged = [CASE_NONE, CASE_THREE, CASE_ONE, CASE_TWO, GREEN_TWO, CASE_TWO_B]
    first = run(staged, seen=[GREEN_TWO], open_cards=[ONE, twin, TWO, THREE])
    assert first == run(staged, seen=[GREEN_TWO], open_cards=[ONE, twin, TWO, THREE])
    assert first.new == [CASE_NONE, GREEN_TWO]
    assert first.own == [CASE_ONE]
    assert list(first.absent.items()) == [(CASE_THREE, "CARD-003"), (CASE_TWO, "CARD-005"), (CASE_TWO_B, "CARD-005")]
    assert first.blocked


def test_the_allow_line_counts_the_absent_cases_per_owner():
    """Catches: a line that hides how many cases the commit left to another card. E6: the allow line lists the absent cases with a count per owner (`40 cases absent at HEAD, owned by CARD-002`), one phrase per owner in the order of first appearance, `1 case` in the singular; beside old reds it keeps the MW-056 text."""
    many = [f"tests/test_two.py::test_two[c{n}]" for n in range(40)]
    line = gct._allow_line(run(many, seen=[GREEN_TWO]))
    assert "40 cases absent at HEAD, owned by CARD-002" in line
    assert line.startswith("the commit is allowed: no new red")
    mixed = run([CASE_THREE, CASE_TWO, CASE_TWO_B], seen=[GREEN_TWO])
    line = gct._allow_line(mixed)
    assert "1 case absent at HEAD, owned by CARD-003" in line
    assert "2 cases absent at HEAD, owned by CARD-002" in line
    assert line.index("CARD-003") < line.index("CARD-002")
    both = run([CASE_TWO, CASE_THREE], head=[CASE_THREE], seen=[GREEN_TWO])
    line = gct._allow_line(both)
    assert f"{CASE_THREE} still red, owned by CARD-003" in line
    assert "1 case absent at HEAD, owned by CARD-002" in line
    assert "absent" not in gct._allow_line(run([CASE_THREE], head=[CASE_THREE]))


def test_the_refusal_says_how_many_absent_cases_another_card_owns():
    """Catches: a refusal that leaves the builder to guess which of the red cases are theirs. E6 (refusal): a refusal for another reason says that the absent cases of other open cards are not blocking, with their count."""
    got = run([CASE_NONE, CASE_TWO, CASE_TWO_B], seen=[GREEN_TWO])
    text = gct._refusal(got, "CARD-001", ["tests"])
    assert CASE_NONE in text
    assert "absent at HEAD and owned by another open card, not blocking: 2" in text


def test_the_collect_command_is_the_tests_command_asked_for_names_only():
    """Catches: `-qq`, which prints a count per file and no id. E7: the command that lists the ids of HEAD is the tests command with its quiet flags removed and one `-q` and `--collect-only` added, so the output is one id per line whatever the profile's command says."""
    py = "python"
    assert gct.collect_argv([py, "-m", "pytest", "-q", "tests"]) == \
        [py, "-m", "pytest", "tests", "--collect-only", "-q", "--continue-on-collection-errors"]
    assert gct.collect_argv([py, "-m", "pytest", "-qq", "--tb=short", "tests"]) == \
        [py, "-m", "pytest", "--tb=short", "tests", "--collect-only", "-q", "--continue-on-collection-errors"]
    assert gct.collect_argv([py, "-m", "pytest", "--quiet", "-x"])[:4] == [py, "-m", "pytest", "-x"]
    assert gct.collect_argv([py, "-m", "unittest"]) is None  # not pytest: HEAD's ids cannot be listed, nothing is absent


def test_the_collected_ids_are_read_from_the_listing_one_per_line():
    """Catches: a count line read as a test, and an id that never matches the one the failure list prints. E7: the ids are the lines that name a test (`<file>::<name>`), `/` in the file part, whole, trailing spaces removed; counts, warnings, errors and blank lines are not ids; no id and no sign of a collection run is None."""
    text = ("tests\\test_b.py::test_item[a.txt]\n"
            "tests/test_b.py::test_item[b c]\n"
            "tests/sub/test_c.py::TestK::test_m\n"
            "\n"
            "ERROR tests/test_bad.py\n"
            "==== warnings summary ====\n"
            "  tests/not_an_id.py:1: Warning\n"
            "3 tests collected in 0.02s\n")
    assert gct.collected_ids(text) == {"tests/test_b.py::test_item[a.txt]", "tests/test_b.py::test_item[b c]",
                                       "tests/sub/test_c.py::TestK::test_m"}
    assert gct.collected_ids("no tests collected in 0.01s\n") == set()
    assert gct.collected_ids("") is None
    assert gct.collected_ids("Traceback (most recent call last):\nValueError: x\n") is None
