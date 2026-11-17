"""Card MW-134 (rulings R347, R348, R348a): `core_red.decide(facts)` retires a recorded red id when a valid case_map.md line of
the committing card names it, in a tests-only commit, under a decision of the ledger that another session wrote. Pure table tests,
no disk, no git, no process: each test builds a `Facts` record and reads the verdict. One test id is one case; the expected
reason ids and the words of the texts are written from the card rows, never computed by the code under test. Synthetic values only."""
import pytest

import _engine  # noqa: F401  (puts the engine folder on the import path)
import core_red as R

PATHS = ("engine/core_red.py", "tests/test_a.py")
FILE = "tests/test_a.py"  # R217a: a test file name is a module constant, never a literal in a test body (S5)
LEFT = "tests/test_a.py::test_old"  # recorded red, the requirement changed
RIGHT = "tests/test_a.py::test_new"  # its replacement
OTHER = "tests/test_a.py::test_other"
NEVER = "tests/test_a.py::test_never"  # a test of no file at HEAD
NOWHERE = "tests/test_a.py::test_nowhere"  # a test of no file in the committed tree
MAP = f"{LEFT} -> {RIGHT}"
DROP = f"{LEFT} -> dropped: the requirement changed"
DECISION = "D-7"
LEAD = "lead-1"


def decision(**fields):
    return R.Decision(DECISION, by=LEAD, **fields)


def retire_facts(lines, *, red=(LEFT, RIGHT), decisions=None, head_ids=(RIGHT,), tree_ids=(RIGHT,), **over):
    """A commit that stages the card's case_map.md. The defaults are the real order of events (R348 1): the replacement is
    recorded red by an earlier commit, so it exists at HEAD; the left id is already gone from HEAD and from the tree."""
    base = dict(card="C1", paths=PATHS, code=False, record=R.Record(red=frozenset(red)),
                case_map="\n".join(lines) + "\n", case_map_head="", decisions=(decision(),) if decisions is None else decisions,
                test_roots=("tests",), head_ids=frozenset(head_ids), tree_ids=frozenset(tree_ids))
    base.update(over)
    return R.Facts(**base)


def reasons(verdict):
    return [r.reason for r in verdict.refusals]


def text(verdict):
    return " | ".join(r.text for r in verdict.refusals)


# ---- what retires ----------------------------------------------------------------------------------------------------------

def test_a_rename_line_retires_the_left_id_when_the_right_is_red_in_the_same_commit():
    """Checks: the classic order, the left was at HEAD and is gone, the right is a new failing test of this commit: the left is retired with its right, decision and the decision's by."""
    verdict = R.decide(retire_facts([MAP], red=(LEFT,), head_ids=(LEFT,), new_ids=(RIGHT,), failed=frozenset({RIGHT})))
    assert verdict.allowed
    assert verdict.red == (RIGHT,)
    assert verdict.retired == (R.Retirement(LEFT, RIGHT, DECISION, LEAD),)


def test_a_dropped_line_retires_the_left_id_with_no_replacement():
    """Checks: a dropped line needs no right side; the row says «dropped»."""
    verdict = R.decide(retire_facts([DROP], red=(LEFT,)))
    assert verdict.allowed
    assert verdict.retired == (R.Retirement(LEFT, "dropped", DECISION, LEAD),)


def test_a_commit_holding_only_the_case_map_line_is_the_retirement_commit_when_the_right_is_already_red():
    """Catches: the real order of events (R348 1), the replacement already recorded red and at HEAD, the left already gone: refused for «nothing proven red», case-map-merge or case-map-unknown-left."""
    verdict = R.decide(retire_facts([MAP]))
    assert reasons(verdict) == []
    assert verdict.retired == (R.Retirement(LEFT, RIGHT, DECISION, LEAD),)
    assert verdict.red == ()


def test_a_line_whose_left_is_not_in_the_record_retires_nothing_and_stays_a_plain_line():
    """Checks: MW-090's plain line (a left of no red record) is judged as before and retires nothing."""
    verdict = R.decide(retire_facts([MAP], red=(RIGHT,), head_ids=(LEFT,), tree_ids=(RIGHT,)))
    assert verdict.allowed
    assert verdict.retired == ()


# ---- the decision is an anchor (R347 2 d) -----------------------------------------------------------------------------------

def test_a_line_that_would_retire_with_no_decision_in_the_message_is_refused_as_retire_no_decision():
    """Catches: a retirement with no decision named, which would let a builder delete its own failing test."""
    verdict = R.decide(retire_facts([MAP], decisions=()))
    assert reasons(verdict) == ["retire-no-decision"]
    assert verdict.retired == ()


@pytest.mark.parametrize("fields, reason, said", [
    ({"in_ledger": False}, "retire-decision-not-in-ledger", f"{DECISION}: it is not a row of the ledger"),
    ({"closed": "withdrawn"}, "retire-decision-closed", f"{DECISION}: its status is withdrawn"),
    ({"by_self": True}, "retire-decision-by-self", f"{DECISION}: it is by this session")],
    ids=["not_in_ledger", "closed", "by_this_session"])
def test_a_decision_that_does_not_count_is_refused_under_its_own_reason_id(fields, reason, said):
    """Catches: a decision that is no row, closed, or written by the committing session, taken as the anchor of a retirement."""
    verdict = R.decide(retire_facts([MAP], decisions=(decision(**fields),)))
    assert reasons(verdict) == [reason]
    assert said in text(verdict)
    assert verdict.retired == ()


def test_a_decision_in_a_root_with_no_ledger_file_retires_nothing_and_is_refused_as_retire_no_ledger():
    """Catches: a root with no ledger, where the pattern alone decides for MW-090's plain lines, backing a retirement whose by cannot be checked."""
    verdict = R.decide(retire_facts([MAP], decisions=(decision(has_ledger=False),)))
    assert reasons(verdict) == ["retire-no-ledger"]
    assert verdict.retired == ()


def test_one_counting_decision_among_several_named_retires():
    """Checks: a message that names a closed decision and an open one is backed by the open one, and the row names the open one."""
    verdict = R.decide(retire_facts([MAP], decisions=(R.Decision("D-1", closed="withdrawn", by="x"), decision())))
    assert verdict.allowed
    assert verdict.retired == (R.Retirement(LEFT, RIGHT, DECISION, LEAD),)


# ---- the right side and the left side ---------------------------------------------------------------------------------------

def test_a_rename_whose_right_is_not_proven_red_is_refused_as_retire_right_not_red():
    """Catches: a rename into a new test that passes as a `Checks:` guard, so the left would be retired with no red replacement."""
    verdict = R.decide(retire_facts([MAP], red=(LEFT, OTHER), head_ids=(LEFT,), new_ids=(RIGHT, OTHER),
                                    failed=frozenset({OTHER}), checks_docstring=frozenset({RIGHT})))
    assert reasons(verdict) == ["retire-right-not-red"]
    assert RIGHT in text(verdict)
    assert verdict.retired == ()


def test_an_id_that_is_present_in_the_committed_tree_is_never_retired_by_a_line():
    """Catches: a present id (it exists and fails) retired by a line instead of being fixed."""
    verdict = R.decide(retire_facts([MAP], tree_ids=(RIGHT, LEFT)))
    assert reasons(verdict) == ["case-map-unknown-left"]
    assert verdict.retired == ()


def test_a_left_whose_file_fails_to_collect_is_failing_not_absent_and_is_refused_as_retire_left_failing():
    """Catches: a file that does not parse hides its ids from the static reader, so its failing ids look gone and would be retired."""
    verdict = R.decide(retire_facts([MAP], broken_files=frozenset({FILE})))
    assert reasons(verdict) == ["retire-left-failing"]
    assert FILE in text(verdict)
    assert verdict.retired == ()


# ---- only a tests-only commit retires (R347 2 b) ----------------------------------------------------------------------------

def test_the_same_line_in_a_code_commit_retires_nothing_and_the_gone_id_still_refuses():
    """Catches: a line staged in a code commit that changes the record the code commit is judged with."""
    verdict = R.decide(retire_facts([MAP], code=True, outcomes={LEFT: R.GONE, RIGHT: R.PASSED}))
    assert reasons(verdict) == ["red-ids-still-red"]
    assert LEFT in text(verdict)
    assert verdict.retired == ()


def test_a_retirement_is_dropped_when_the_commit_is_refused_for_another_reason():
    """Catches: a valid line retiring an id in a commit that is refused (and in watch mode allowed) for a new test that passes."""
    verdict = R.decide(retire_facts([MAP], red=(LEFT, RIGHT), new_ids=(OTHER,)))
    assert reasons(verdict) == ["red-not-proven"]
    assert verdict.retired == ()


def test_the_case_map_refusals_stand_before_the_retire_refusals():
    """Checks: MW-090's refusals keep their place at the head of the verdict (the reason id of the commit is a case_map one); a retire refusal follows."""
    verdict = R.decide(retire_facts([MAP, "this is no line"], decisions=()))
    assert reasons(verdict) == ["case-map-malformed", "retire-no-decision"]


def test_the_case_map_refusals_keep_their_order_among_themselves():
    """Checks: unknown-left, unknown-right, merge and malformed are listed in the order of CASE_MAP_REASONS."""
    lines = [f"{NEVER} -> {RIGHT}", f"{LEFT} -> {NOWHERE}", "no line"]
    verdict = R.decide(retire_facts(lines, red=(), head_ids=(LEFT,), tree_ids=(RIGHT,)))
    assert reasons(verdict) == ["case-map-unknown-left", "case-map-unknown-right", "case-map-malformed"]


# ---- the texts of red-ids-still-red (R347 2 f, R348 2) ----------------------------------------------------------------------

def test_the_still_red_text_of_an_absent_id_names_the_way_out():
    """Catches: a refusal that tells the builder its test is gone and not how to retire it: the case_map line, the decision by another session, the commit alone."""
    verdict = R.decide(retire_facts([], code=True, case_map=None, outcomes={LEFT: R.GONE, RIGHT: R.PASSED}))
    said = text(verdict)
    assert reasons(verdict) == ["red-ids-still-red"]
    assert f"{LEFT} -> <new test id>" in said and f"{LEFT} -> dropped: <why>" in said
    assert "case_map.md" in said and "another session" in said and "alone" in said


@pytest.mark.parametrize("outcome", [R.FAILED, R.SKIPPED], ids=["failing", "skipped"])
def test_the_still_red_text_of_a_failing_or_skipped_id_names_no_way_out(outcome):
    """Catches: the retirement way out offered for a test that exists and fails, which only a fix of the code answers."""
    verdict = R.decide(retire_facts([], code=True, case_map=None, outcomes={LEFT: outcome, RIGHT: R.PASSED}))
    assert reasons(verdict) == ["red-ids-still-red"]
    assert "case_map" not in text(verdict)


def test_the_notice_text_names_the_session_the_id_the_card_and_the_decision():
    """Checks: the inbox notice of a retirement is «<session> retired <left> of <card> under <decision>» (R348 3)."""
    assert R.retire_notice("build-1", LEFT, "C1", DECISION) == f"build-1 retired {LEFT} of C1 under {DECISION}"


# ---- what stays of MW-090 for a side the record does not hold (R355 1) ------------------------------------------------------

def test_a_left_the_record_does_not_hold_keeps_the_check_that_it_is_a_test_of_its_file_at_head():
    """Catches: the loosening for recorded ids reaching a left the record does not hold, which is gone from HEAD too and would pass as a rename of nothing."""
    verdict = R.decide(retire_facts([MAP], red=(RIGHT,), head_ids=(RIGHT,)))
    assert reasons(verdict)[0] == "case-map-unknown-left"
    assert verdict.retired == ()


def test_a_right_the_record_does_not_hold_keeps_the_check_that_it_is_not_a_test_at_head():
    """Catches: the loosening for recorded ids reaching a right the record does not hold, so a rename could merge into any green test at HEAD."""
    verdict = R.decide(retire_facts([MAP], red=(LEFT,), head_ids=(LEFT, RIGHT)))
    assert "case-map-merge" in reasons(verdict)
    assert verdict.retired == ()


def test_one_right_side_in_two_mapping_lines_is_refused_as_a_merge_even_when_the_record_holds_all_three():
    """Catches: two recorded lefts retired into one right side, which MW-090 allows in at most one mapping line (R225 2)."""
    verdict = R.decide(retire_facts([MAP, f"{OTHER} -> {RIGHT}"], red=(LEFT, OTHER, RIGHT)))
    assert "case-map-merge" in reasons(verdict)
    assert verdict.retired == ()
