"""Card MW-072: `core_red.decide(facts) -> Verdict` as table tests. No disk, no git, no process: each test builds a `Facts`
record and reads the verdict. One test id is one case; the expected reason, the recorded ids and the words of the text
are written from the card rows, never computed by the code under test. Synthetic values only."""
import pytest

import _engine  # noqa: F401  (puts the engine folder on the import path)
import core_red as R

PATHS = ("engine/core_red.py", "engine/core.py", "tests/test_b.py")
ONE = "tests/test_a.py::test_one"
TWO = "tests/test_a.py::test_two"
OTHER = "tests/test_z.py::test_z"
FILE_A = "tests/test_a.py"  # R217a: a test file name is a module constant, never a literal in a test body (S5)
FILE_B = "tests/test_b.py"
BOTH_B = ("tests/test_b.py::test_b1", "tests/test_b.py::test_b2")


def facts(**over):
    base = dict(card="C1", kind="", paths=PATHS, code=False, new_ids=(), failed=frozenset(), errored={},
                file_errors={}, file_new={}, pin_docstring=frozenset(), pin_rows=frozenset(),
                checks_docstring=frozenset(), record=None, outcomes={})
    base.update(over)
    return R.Facts(**base)


def record(red=(), pins=(), files=()):
    return R.Record(red=frozenset(red), pins=frozenset(pins), files=frozenset(files))


def reasons(verdict):
    return [r.reason for r in verdict.refusals]


def text(verdict):
    return " | ".join(r.text for r in verdict.refusals)


# ---- a tests-only commit: every new id must be red -------------------------------------------------------------------

def test_a_new_failing_test_in_a_tests_only_commit_is_allowed_and_recorded_red():
    """Checks: a new test that fails is the red the commit must show; the id goes to the red record."""
    verdict = R.decide(facts(new_ids=(ONE,), failed=frozenset({ONE})))
    assert verdict.allowed
    assert verdict.red == (ONE,)


def test_a_new_test_that_passes_in_a_tests_only_commit_is_refused_as_red_not_proven():
    """Catches: a test written after the code, which passes before any change and proves nothing."""
    verdict = R.decide(facts(new_ids=(ONE,)))
    assert reasons(verdict) == ["red-not-proven"]
    assert verdict.red == ()


def test_a_new_test_that_errors_at_setup_is_refused_as_red_not_proven():
    """Catches: a new test that errors in its fixture, which is broken, not red for the behaviour it names."""
    verdict = R.decide(facts(new_ids=(ONE,), errored={ONE: "fixture 'tmp_thing' not found"}))
    assert reasons(verdict) == ["red-not-proven"]
    assert "fixture 'tmp_thing' not found" in text(verdict)


def test_a_collection_error_for_a_module_in_the_card_paths_is_red_by_missing():
    """Checks: a test file that cannot import a module the card itself will create is red by missing that module."""
    verdict = R.decide(facts(file_errors={FILE_B: "ModuleNotFoundError: No module named 'core_red'"},
                             file_new={FILE_B: BOTH_B}))
    assert verdict.allowed
    assert verdict.red == BOTH_B
    assert verdict.missing == {FILE_B: "core_red"}


def test_an_attribute_error_for_a_module_in_the_card_paths_is_red_by_missing():
    """Checks: an AttributeError naming a module of the card Paths is red by missing that module."""
    verdict = R.decide(facts(file_errors={FILE_B: "AttributeError: module 'core' has no attribute 'decide'"},
                             file_new={FILE_B: BOTH_B}))
    assert verdict.allowed
    assert verdict.missing == {FILE_B: "core"}


def test_an_import_error_for_a_name_of_a_module_in_the_card_paths_is_red_by_missing():
    """Checks: an ImportError for a name of a module of the card Paths is red by missing that module."""
    line = "ImportError: cannot import name 'decide' from 'core_red' (C:\\x\\core_red.py)"
    verdict = R.decide(facts(file_errors={FILE_B: line}, file_new={FILE_B: BOTH_B}))
    assert verdict.allowed
    assert verdict.missing == {FILE_B: "core_red"}


def test_a_collection_error_for_a_module_outside_the_card_paths_is_refused_as_red_not_proven():
    """Catches: a test file that fails to import a package the card does not own, which is a broken file, not a red one."""
    verdict = R.decide(facts(file_errors={FILE_B: "ModuleNotFoundError: No module named 'numpy'"},
                             file_new={FILE_B: BOTH_B}))
    assert reasons(verdict) == ["red-not-proven"]
    assert "No module named 'numpy'" in text(verdict)


def test_a_syntax_error_in_a_new_test_file_is_refused_as_red_not_proven():
    """Catches: a new test file with a syntax error, which fails for a reason that is not the missing behaviour."""
    verdict = R.decide(facts(file_errors={FILE_B: "SyntaxError: invalid syntax"}, file_new={FILE_B: BOTH_B}))
    assert reasons(verdict) == ["red-not-proven"]
    assert "SyntaxError: invalid syntax" in text(verdict)


def test_a_collection_error_in_a_file_with_no_new_test_is_refused_as_red_not_proven():
    """Catches: an edit that breaks the import of a file whose tests all existed at HEAD, so no new test is red."""
    verdict = R.decide(facts(file_errors={FILE_B: "ModuleNotFoundError: No module named 'core_red'"},
                             file_new={FILE_B: ()}))
    assert reasons(verdict) == ["red-not-proven"]
    assert FILE_B in text(verdict)


# ---- pinning tests (G2b) -----------------------------------------------------------------------------------------

def test_a_pinning_test_of_a_refactor_card_is_allowed():
    """Checks: a passing new test of a refactor card with the Pins docstring and its Acceptance row is a declared pin."""
    verdict = R.decide(facts(kind="refactor", new_ids=(ONE,), pin_docstring=frozenset({ONE}),
                             pin_rows=frozenset({ONE})))
    assert verdict.allowed
    assert verdict.pins == (ONE,)
    assert verdict.red == ()


def test_a_passing_test_of_a_feature_card_is_not_a_pin():
    """Catches: a feature card that declares a passing test a pin to get past the red proof."""
    verdict = R.decide(facts(kind="", new_ids=(ONE,), pin_docstring=frozenset({ONE}), pin_rows=frozenset({ONE})))
    assert reasons(verdict) == ["red-not-proven"]


def test_a_pin_without_the_pins_docstring_is_refused():
    """Catches: a passing test of a refactor card that does not say in its docstring what behaviour it pins."""
    verdict = R.decide(facts(kind="refactor", new_ids=(ONE,), pin_rows=frozenset({ONE})))
    assert reasons(verdict) == ["red-not-proven"]
    assert "Pins:" in text(verdict)


def test_a_pin_without_an_acceptance_row_is_refused():
    """Catches: a passing test of a refactor card that no Acceptance row names as pinning."""
    verdict = R.decide(facts(kind="refactor", new_ids=(ONE,), pin_docstring=frozenset({ONE})))
    assert reasons(verdict) == ["red-not-proven"]
    assert "Acceptance" in text(verdict)


def test_a_pinning_test_of_a_migration_card_is_allowed():
    """Checks: the kind migration opens the same door as refactor."""
    verdict = R.decide(facts(kind="migration", new_ids=(ONE,), pin_docstring=frozenset({ONE}),
                             pin_rows=frozenset({ONE})))
    assert verdict.allowed
    assert verdict.pins == (ONE,)


# ---- a code commit: the recorded ids must pass -----------------------------------------------------------------------

def test_a_code_commit_where_every_recorded_id_passes_is_allowed():
    """Checks: the code that makes every recorded red id pass is the commit the record waits for."""
    verdict = R.decide(facts(code=True, record=record(red=(ONE,)), outcomes={ONE: "passed"}))
    assert verdict.allowed


def test_a_recorded_id_that_still_fails_is_refused_as_still_red():
    """Catches: a code commit that does not make the recorded red test pass."""
    verdict = R.decide(facts(code=True, record=record(red=(ONE,)), outcomes={ONE: "failed"}))
    assert reasons(verdict) == ["red-ids-still-red"]


def test_a_recorded_id_that_is_gone_is_refused_as_still_red():
    """Catches: a green suite made by deleting or renaming the recorded red test."""
    verdict = R.decide(facts(code=True, record=record(red=(ONE,)), outcomes={ONE: "gone"}))
    assert reasons(verdict) == ["red-ids-still-red"]


def test_a_recorded_id_that_is_skipped_is_refused_as_still_red():
    """Catches: a green suite made by skipping the recorded red test."""
    verdict = R.decide(facts(code=True, record=record(red=(ONE,)), outcomes={ONE: "skipped"}))
    assert reasons(verdict) == ["red-ids-still-red"]


def test_a_code_commit_with_no_record_is_refused_as_not_recorded():
    """Catches: code committed in a root where the card's red tests were never committed and proven."""
    verdict = R.decide(facts(code=True))
    assert reasons(verdict) == ["red-not-recorded"]
    assert "commit the failing tests first, alone (the gate runs them and records the red), then commit the code" in text(verdict)


def test_a_code_commit_with_a_record_of_pins_only_is_allowed():
    """Checks: a refactor card that committed only pins has a record, so its code commit is not refused."""
    verdict = R.decide(facts(code=True, record=record(pins=(ONE,))))
    assert verdict.allowed


def test_a_session_with_no_card_is_not_judged():
    """Checks: with no card held there is no record to key, so the red proof leaves the commit to the other gates."""
    verdict = R.decide(facts(card="", code=True, new_ids=(ONE,)))
    assert verdict.allowed
    assert verdict.red == ()


# ---- a new test together with code -----------------------------------------------------------------------------------

def test_a_new_test_with_code_and_no_red_record_is_refused():
    """Catches: the test-after path, a new test committed with its code that was never seen to fail."""
    verdict = R.decide(facts(code=True, new_ids=(ONE,), record=record(red=(OTHER,)), outcomes={OTHER: "passed"}))
    assert reasons(verdict) == ["test-without-red-proof"]


def test_a_new_test_with_code_that_is_in_the_red_record_is_allowed():
    """Checks: a new id the red record holds (a red-by-missing file that now collects) may come with its code."""
    verdict = R.decide(facts(code=True, new_ids=(ONE,), record=record(red=(ONE,)), outcomes={ONE: "passed"}))
    assert verdict.allowed


def test_a_new_test_with_code_that_is_a_declared_pin_is_allowed():
    """Checks: a declared pinning id of a refactor card may come with its code."""
    verdict = R.decide(facts(kind="refactor", code=True, new_ids=(ONE,), pin_docstring=frozenset({ONE}),
                             pin_rows=frozenset({ONE}), record=record()))
    assert verdict.allowed


def test_the_refusal_for_two_new_tests_names_only_the_unrecorded_one():
    """Catches: a refusal that blames a new test the red record does hold."""
    verdict = R.decide(facts(code=True, new_ids=(ONE, TWO), record=record(red=(ONE,)), outcomes={ONE: "passed"}))
    assert reasons(verdict) == ["test-without-red-proof"]
    assert "test_two" in text(verdict)
    assert "test_one" not in text(verdict)


def test_a_new_test_with_code_and_no_record_at_all_is_test_without_red_proof():
    """Catches: the wrong reason for a test-after commit: the missing test proof, not the missing record, is named."""
    verdict = R.decide(facts(code=True, new_ids=(ONE,)))
    assert reasons(verdict) == ["test-without-red-proof"]


# ---- the texts ---------------------------------------------------------------------------------------------------

def test_the_not_proven_text_names_the_test_and_why():
    """Checks: the refusal names the test id and says that it passes before any code change."""
    verdict = R.decide(facts(new_ids=(ONE,)))
    assert ONE in text(verdict)
    assert "passes" in text(verdict)


def test_the_still_red_text_names_the_id_and_what_became_of_it():
    """Checks: the refusal names the recorded id and says it was deleted or renamed."""
    verdict = R.decide(facts(code=True, record=record(red=(ONE,)), outcomes={ONE: "gone"}))
    assert ONE in text(verdict)
    assert "deleted or renamed" in text(verdict)


def test_a_tests_only_commit_with_no_new_id_is_allowed():
    """Checks: a tests-only commit that adds no test has nothing to prove and records nothing."""
    verdict = R.decide(facts())
    assert verdict.allowed
    assert verdict.red == ()


# ---- ruling R183: a green "Checks:" test next to a red id of the same commit -----------------------------------------

def test_a_checks_green_test_with_a_red_id_in_the_same_commit_is_allowed():
    """Checks: a passing guard of unchanged behaviour is allowed beside a red id, and the record lists it."""
    verdict = R.decide(facts(new_ids=(ONE, TWO), failed=frozenset({ONE}), checks_docstring=frozenset({TWO})))
    assert verdict.allowed
    assert verdict.red == (ONE,)
    assert verdict.checks == (TWO,)


def test_a_checks_green_test_with_no_red_id_on_a_feature_card_is_refused():
    """Catches: a commit of only passing tests that call themselves Checks, which is the test-after door."""
    verdict = R.decide(facts(new_ids=(ONE,), checks_docstring=frozenset({ONE})))
    assert reasons(verdict) == ["red-not-proven"]
    assert verdict.checks == ()


def test_a_catches_green_test_next_to_a_red_id_is_refused():
    """Catches: a passing test whose docstring is not Checks, which must have been red."""
    verdict = R.decide(facts(new_ids=(ONE, TWO), failed=frozenset({ONE})))
    assert reasons(verdict) == ["red-not-proven"]
    assert "test_two" in text(verdict)
    assert "test_one" not in text(verdict)


def test_a_checks_green_test_next_to_a_red_by_missing_file_is_allowed():
    """Checks: a red-by-missing file counts as a red id of the commit for the guard beside it."""
    verdict = R.decide(facts(new_ids=(TWO,), checks_docstring=frozenset({TWO}),
                             file_errors={FILE_B: "ModuleNotFoundError: No module named 'core_red'"},
                             file_new={FILE_B: BOTH_B}))
    assert verdict.allowed
    assert verdict.checks == (TWO,)


def test_a_checks_green_test_in_a_code_commit_is_not_a_door():
    """Catches: a new Checks test committed with its code, where no red id of the commit stands beside it."""
    verdict = R.decide(facts(code=True, new_ids=(ONE,), checks_docstring=frozenset({ONE}),
                             record=record(red=(OTHER,)), outcomes={OTHER: "passed"}))
    assert reasons(verdict) == ["test-without-red-proof"]


NINE = tuple(f"tests/test_mw075.py::test_red{n}" for n in range(1, 10))
FOUR = tuple(f"tests/test_mw075.py::test_guard{n}" for n in range(1, 5))


def test_replay_a_red_commit_of_nine_red_ids_and_four_checks_green_ids_is_allowed():
    """Checks: the shape of a real red commit, 9 red ids and 4 passing guards, is allowed and recorded as such."""
    verdict = R.decide(facts(new_ids=NINE + FOUR, failed=frozenset(NINE), checks_docstring=frozenset(FOUR)))
    assert verdict.allowed
    assert verdict.red == NINE
    assert verdict.checks == FOUR


def test_a_setup_error_for_a_module_in_the_card_paths_is_red_by_missing():
    """Checks: a test that errors at setup because a module of the card Paths lacks a name is red by missing it."""
    verdict = R.decide(facts(new_ids=(ONE,), errored={ONE: "AttributeError: module 'core' has no attribute 'decide'"}))
    assert verdict.allowed
    assert verdict.red == (ONE,)
    assert verdict.missing == {FILE_A: "core"}


def test_a_missing_package_whose_folder_holds_a_paths_entry_is_red_by_missing():
    """Catches: a missing package refused as red-not-proven because only its own file names were matched to the Paths (R217a)."""
    verdict = R.decide(facts(paths=("src/feature.py",), file_errors={FILE_B: "ModuleNotFoundError: No module named 'src'"},
                             file_new={FILE_B: BOTH_B}))
    assert verdict.allowed
    assert verdict.red == BOTH_B
    assert verdict.missing == {FILE_B: "src"}


# ---- card MW-090: the lines of the card's case_map.md, judged under a named decision (refusals only) ----------------------
# Decisions R219, R222, R223, R225. A valid line changes nothing yet; a bad line, or a new line with no counting decision, is refused.

LEFT = "tests/test_a.py::test_old"  # a test at HEAD that the commit removes from the tree
LEFT2 = "tests/test_a.py::test_old2"
RIGHT = "tests/test_b.py::test_new"  # a test the committed tree defines and HEAD does not
RIGHT2 = "tests/test_b.py::test_new2"
GONE = "tests/test_a.py::test_never_existed"
OUTSIDE_ID = "src/x.py::test_old"  # a file outside the test roots
MAP = f"{LEFT} -> {RIGHT}"
DROP = f"{LEFT} -> dropped: covered by the parametrize of the new test"
UNKNOWN_LEFT_LINE = f"{GONE} -> {RIGHT}"
BROKEN_LINES = [f"broken line {n}" for n in range(12)]
FACT_NOT_AT_HEAD = "is not a test id of its file at HEAD under a test root"
FACT_STILL_THERE = "still exists in the committed tree"
FACT_NOT_IN_TREE = "is not a test id of its file in the committed tree under a test root"


def decs(*kwargs):
    """The decisions of a commit: one `Decision` per dict of fields, ids R1, R2, ..."""
    return tuple(R.Decision(f"R{n}", **kw) for n, kw in enumerate(kwargs, 1))


def cmfacts(lines, head=(), decisions=({},), head_ids=(LEFT, LEFT2), tree_ids=(RIGHT, RIGHT2), other_red=None, **over):
    """Facts of a commit that stages the case_map: its committed lines, HEAD's lines, the decisions (dicts of Decision
    fields; the default is one that counts), the static ids at HEAD and in the committed tree of the sides' files."""
    return facts(case_map="\n".join(lines) + "\n", case_map_head="\n".join(head) + "\n" if head else "",
                 decisions=decs(*decisions), test_roots=("tests",), head_ids=frozenset(head_ids),
                 tree_ids=frozenset(tree_ids), other_red=other_red or {}, **over)


@pytest.mark.parametrize("line", [MAP, DROP], ids=["mapping", "dropped"])
def test_a_new_mapping_or_dropped_line_with_no_decision_is_refused_as_case_map_no_decision(line):
    """Catches: a new case_map line that no decision of the commit message backs, which would carry a status silently (R225 4)."""
    verdict = R.decide(cmfacts([line], decisions=()))
    assert reasons(verdict) == ["case-map-no-decision"]
    assert "no match of tests.red_proof.decision_pattern" in text(verdict)


@pytest.mark.parametrize("fields, said", [
    ({"closed": "withdrawn"}, "R1: its status is withdrawn"),
    ({"closed": "superseded"}, "R1: its status is superseded"),
    ({"by_self": True}, "R1: it is by this session"),
    ({"in_ledger": False}, "R1: it is not a row of the ledger")], ids=["withdrawn", "superseded", "by_self", "no_row"])
def test_a_named_decision_that_does_not_count_is_refused_with_its_why(fields, said):
    """Catches: a decision that is closed, written by the committing session or not in the ledger, which backs a line."""
    verdict = R.decide(cmfacts([MAP], decisions=(fields,)))
    assert reasons(verdict) == ["case-map-no-decision"]
    assert said in text(verdict)


def test_a_valid_mapping_under_a_counting_decision_is_allowed():
    """Checks: a rename whose left was at HEAD and is gone and whose right is in the tree changes nothing yet (R225 1)."""
    verdict = R.decide(cmfacts([MAP]))
    assert verdict.allowed


def test_one_counting_decision_among_several_named_is_enough():
    """Checks: a message that names a closed decision and an open one is backed by the open one."""
    verdict = R.decide(cmfacts([MAP], decisions=({"closed": "withdrawn"}, {})))
    assert verdict.allowed


@pytest.mark.parametrize("lines, head", [
    ([UNKNOWN_LEFT_LINE], [UNKNOWN_LEFT_LINE]),
    ([UNKNOWN_LEFT_LINE, "broken"], [f"  {UNKNOWN_LEFT_LINE}  ", "broken"]),
    ([], [UNKNOWN_LEFT_LINE]),
    (["# kept: tests/test_a.py::test_one - still a test", "", "> a note"], []),
    (["broken", "broken"], ["broken"])], ids=["old_line", "old_line_spaces", "removed_line", "comment_and_blank", "old_malformed"])
def test_only_new_mapping_and_dropped_lines_are_judged(lines, head):
    """Checks: a line already at HEAD (set difference on the stripped text), a removed line, a comment and a blank line are never judged."""
    verdict = R.decide(cmfacts(lines, head, decisions=()))
    assert verdict.allowed


def test_a_commit_that_does_not_stage_the_case_map_is_judged_as_before():
    """Catches: case_map rules that run in a commit that does not stage the card's case_map.md (R225 4)."""
    verdict = R.decide(facts(case_map=None, case_map_head="broken\n", new_ids=(ONE,)))
    assert reasons(verdict) == ["red-not-proven"]


@pytest.mark.parametrize("line, head_ids", [
    (UNKNOWN_LEFT_LINE, (LEFT,)),
    (f"{GONE} -> dropped: obsolete", (LEFT,)),
    (f"./{LEFT} -> {RIGHT}", (LEFT,)),
    (f"{OUTSIDE_ID} -> {RIGHT}", (OUTSIDE_ID,))], ids=["mapping", "dropped", "path_form", "outside_test_roots"])
def test_a_left_that_is_not_a_test_id_at_head_is_refused_as_unknown_left(line, head_ids):
    """Catches: a mapping or a dropped line from nowhere: its left is no static id of its file at HEAD, or no test file."""
    verdict = R.decide(cmfacts([line], head_ids=head_ids))
    assert reasons(verdict) == ["case-map-unknown-left"]
    assert FACT_NOT_AT_HEAD in text(verdict)


@pytest.mark.parametrize("line", [MAP, DROP], ids=["mapping", "dropped"])
def test_a_left_that_still_exists_in_the_committed_tree_is_refused_as_unknown_left(line):
    """Catches: a copy written as a rename or a drop, which would let a new green test skip the red proof (R223 4)."""
    verdict = R.decide(cmfacts([line], tree_ids=(RIGHT, LEFT)))
    assert reasons(verdict) == ["case-map-unknown-left"]
    assert FACT_STILL_THERE in text(verdict)


@pytest.mark.parametrize("line", [MAP, DROP], ids=["mapping", "dropped"])
def test_a_left_in_another_cards_red_record_is_refused_as_unknown_left(line):
    """Catches: a card that renames or drops a test the red record of another card holds (R223 4, R225 6)."""
    verdict = R.decide(cmfacts([line], other_red={LEFT: "C2"}))
    assert reasons(verdict) == ["case-map-unknown-left"]
    assert "is in the red record of C2" in text(verdict)


def test_a_dropped_line_whose_left_is_gone_from_the_tree_is_allowed():
    """Checks: a dropped line for a test that was at HEAD and is no longer in the committed tree changes nothing yet."""
    verdict = R.decide(cmfacts([DROP]))
    assert verdict.allowed


@pytest.mark.parametrize("line, tree_ids", [
    (MAP, ()),
    (f"{LEFT} -> {OUTSIDE_ID}", (OUTSIDE_ID,))], ids=["not_in_tree", "outside_test_roots"])
def test_a_right_that_is_not_a_test_id_in_the_committed_tree_is_refused_as_unknown_right(line, tree_ids):
    """Catches: a rename to a test that the committed tree does not define, or to a file that is no test file."""
    verdict = R.decide(cmfacts([line], tree_ids=tree_ids))
    assert reasons(verdict) == ["case-map-unknown-right"]
    assert FACT_NOT_IN_TREE in text(verdict)


def test_two_lefts_with_one_right_are_refused_as_a_merge_with_the_dropped_form():
    """Catches: two old tests mapped to one new test, which loses cases unless each merged one says so (R225 2, R225a)."""
    verdict = R.decide(cmfacts([MAP, f"{LEFT2} -> {RIGHT}"]))
    assert reasons(verdict) == ["case-map-merge"]
    assert f"{LEFT} -> {RIGHT}" in text(verdict)
    assert f"-> dropped: merged into {RIGHT}, <why>" in text(verdict)


def test_a_right_that_already_exists_at_head_is_refused_as_a_merge_into_an_existing_test():
    """Catches: a rename onto a test that exists at HEAD, which is a merge into an existing test."""
    verdict = R.decide(cmfacts([MAP], head_ids=(LEFT, RIGHT), tree_ids=(RIGHT,)))
    assert reasons(verdict) == ["case-map-merge"]
    assert "already exists at HEAD" in text(verdict)
    assert f"{LEFT} -> dropped: merged into {RIGHT}, <why>" in text(verdict)


def test_a_new_line_that_shares_its_right_with_an_old_line_is_refused_as_a_merge():
    """Catches: a new line whose right side is the right side of a line at HEAD, which the new lines alone do not show."""
    old = f"{LEFT2} -> {RIGHT}"
    verdict = R.decide(cmfacts([old, MAP], [old]))
    assert reasons(verdict) == ["case-map-merge"]


def test_the_merge_written_with_the_dropped_form_is_allowed():
    """Checks: A -> N plus B -> dropped: merged into N, why is the accepted form of a merge."""
    verdict = R.decide(cmfacts([MAP, f"{LEFT2} -> dropped: merged into {RIGHT}, the same case"]))
    assert verdict.allowed


@pytest.mark.parametrize("lines", [[MAP, MAP], [DROP, f"  {DROP}  "]], ids=["mapping", "dropped"])
def test_the_same_line_twice_counts_as_one_and_is_not_a_duplicate_right_side(lines):
    """Checks: two identical lines are one line (set semantics on the stripped text), never two lefts for one right."""
    verdict = R.decide(cmfacts(lines))
    assert verdict.allowed


@pytest.mark.parametrize("line", ["no arrow here", f"{LEFT} -> dropped:", f"{LEFT} => {RIGHT}"],
                         ids=["no_arrow", "dropped_without_why", "wrong_arrow"])
def test_a_new_line_the_parser_calls_malformed_is_refused_as_case_map_malformed(line):
    """Catches: a new line that is neither a mapping nor a dropped line, which no reader can act on."""
    verdict = R.decide(cmfacts([line]))
    assert reasons(verdict) == ["case-map-malformed"]
    assert line in text(verdict)


@pytest.mark.parametrize("line", [f"{LEFT}[a] -> {RIGHT}", f"{LEFT} -> {RIGHT}[a]"], ids=["left", "right"])
def test_a_side_with_a_case_suffix_is_refused_as_case_map_malformed(line):
    """Catches: a side that names one case of a parametrized test; sides are function-level base ids (R223 7)."""
    verdict = R.decide(cmfacts([line], head_ids=(LEFT, f"{LEFT}[a]"), tree_ids=(RIGHT, f"{RIGHT}[a]")))
    assert reasons(verdict) == ["case-map-malformed"]
    assert "[case]" in text(verdict)


def test_a_left_with_a_mapping_and_a_dropped_line_is_refused_as_malformed():
    """Catches: one old test both renamed and dropped (R225a: one left side appears in exactly one kind of line)."""
    verdict = R.decide(cmfacts([MAP, DROP]))
    assert reasons(verdict) == ["case-map-malformed"]
    assert "a mapping line and a dropped line" in text(verdict)


def test_a_left_with_two_dropped_lines_is_refused_as_malformed():
    """Catches: one old test dropped twice with two reasons (R225a: exactly one dropped line)."""
    verdict = R.decide(cmfacts([DROP, f"{LEFT} -> dropped: another reason"]))
    assert reasons(verdict) == ["case-map-malformed"]
    assert "2 dropped lines" in text(verdict)


@pytest.mark.parametrize("old, new", [(DROP, MAP), (MAP, DROP)], ids=["dropped_then_mapping", "mapping_then_dropped"])
def test_a_new_line_whose_left_clashes_with_an_old_line_is_refused_as_malformed(old, new):
    """Catches: a new line that makes a left side appear in two kinds of line together with a line at HEAD."""
    verdict = R.decide(cmfacts([old, new], [old]))
    assert reasons(verdict) == ["case-map-malformed"]


def test_a_split_of_one_left_into_several_rights_is_allowed():
    """Checks: A -> N1 and A -> N2 is a split (a loop that became a parametrize), allowed."""
    verdict = R.decide(cmfacts([MAP, f"{LEFT} -> {RIGHT2}"]))
    assert verdict.allowed


@pytest.mark.parametrize("lines, want", [
    (["broken"], ["case-map-malformed"]),
    (["broken", MAP], ["case-map-no-decision", "case-map-malformed"])], ids=["alone", "with_a_mapping"])
def test_a_malformed_line_is_refused_even_when_no_decision_counts(lines, want):
    """Catches: a malformed new line that passes because the commit names no decision."""
    verdict = R.decide(cmfacts(lines, decisions=()))
    assert reasons(verdict) == want


def test_the_case_map_refusal_comes_before_red_not_proven():
    """Catches: the reason id of the commit taken from the red proof when the case_map is bad too (the first reason decides)."""
    verdict = R.decide(cmfacts(["broken"], new_ids=(ONE,)))
    assert reasons(verdict) == ["case-map-malformed", "red-not-proven"]


def test_a_code_commit_is_judged_by_the_case_map_rules_too():
    """Catches: case_map rules that only run in tests-only commits, so a code commit lands an unjudged line."""
    verdict = R.decide(cmfacts(["broken"], code=True, record=record(red=(ONE,)), outcomes={ONE: "passed"}))
    assert reasons(verdict) == ["case-map-malformed"]


def test_more_than_ten_refusals_of_one_reason_are_capped_with_a_count():
    """Catches: a refusal text with a line for every bad case_map line; ten are named and the rest are counted (R220)."""
    verdict = R.decide(cmfacts(BROKEN_LINES))
    assert reasons(verdict) == ["case-map-malformed"] * 11
    assert "2 more" in verdict.refusals[-1].text
    assert "broken line 11" not in text(verdict)


def test_the_files_to_read_are_the_sides_files_of_the_new_lines_under_a_test_root():
    """Checks: the shell reads the files of the sides of new lines only, and only those under a test root, sorted."""
    old = "tests/test_c.py::test_c -> tests/test_d.py::test_d"
    lines = [MAP, f"{OUTSIDE_ID} -> dropped: x", old, "# a note", "broken"]
    assert R.case_map_files("\n".join(lines) + "\n", old + "\n", ("tests",)) == [FILE_A, FILE_B]
