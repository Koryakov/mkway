"""Card MW-072: the red proof on a real small git repository with real pytest (the shell reads the facts, the core in
`engine/core_red.py` decides). Each test builds the tiny synthetic project of `tests/_red_project.py` (a pytest project
and one open card held by the session); the engine's own suite is never run here. Synthetic files only."""
import json
from pathlib import Path

import pytest  # noqa: F401

from _commit_project import git, make_project, reason, rows, run_gate, stage, write
from _red_project import (APP2, APP_MUL, BROKEN_OLD, GREEN, MISSING, OUTSIDE, PIN, PIN_ROW, RED_AND_CATCHES,
                          RED_AND_CHECKS, RED_MUL, REPLAY, SKIPPED, card_file, recorded, record_rows, red_project,
                          use_template_copy)
import gate_commit_tests as gct  # after _red_project, which puts the engine folder on the path
import ledger  # card MW-090: a root's ledger, for the decisions a commit message names

NEW_FILE = "tests/test_new.py"  # R217a: a test file name is a module constant, never a literal in a test body (S5)
OK_FILE = "tests/test_ok.py"
NEW = "tests/test_new.py::test_mul"


@pytest.fixture(autouse=True)
def _red_templates(template_copy):
    """R217b: `red_project` builds each variant of the project once per worker in MW-085's template folder and gives each
    test a copy in its own tmp_path, so no test writes beside its tmp_path."""
    with use_template_copy(template_copy):
        yield


def red_commit(root, text=RED_MUL):
    stage(root, NEW_FILE,text)
    assert reason(run_gate(root)) == "allow"
    git(root, "commit", "-q", "-m", "CARD-001 red")
    return recorded(root)


def test_a_tests_only_commit_of_a_failing_new_test_runs_the_suite_and_records_the_id(tmp_path):
    """Checks: the red-first commit now runs the suite, and the failing new test is recorded as red."""
    root = red_project(tmp_path)
    stage(root, NEW_FILE,RED_MUL)
    assert reason(run_gate(root)) == "allow"
    assert [r["result"] for r in rows(root)] == ["fail"]
    assert recorded(root) == [NEW]


def test_replay_a_tests_only_commit_of_a_passing_new_test_is_refused(tmp_path):
    """Catches: the real case of gate_commit_tests.py line 354, a tests-only commit let through with no run."""
    root = red_project(tmp_path)
    stage(root, NEW_FILE,GREEN)
    verdict = run_gate(root)
    assert reason(verdict) == "red-not-proven"
    assert "tests/test_new.py::test_add_again" in verdict.message
    assert [r["result"] for r in rows(root)] == ["pass"]


def test_a_new_test_file_importing_a_missing_module_of_the_card_paths_is_red_by_missing(tmp_path):
    """Checks: a test file that imports a module the card will create is red by missing it, and is recorded."""
    root = red_project(tmp_path)
    stage(root, NEW_FILE,MISSING)
    assert reason(run_gate(root)) == "allow"
    assert recorded(root) == [NEW]
    assert record_rows(root)[0]["missing"] == {NEW_FILE: "app2"}


def test_a_new_test_file_importing_a_missing_module_outside_the_card_paths_is_refused(tmp_path):
    """Catches: a test file that fails to import a package the card does not own, taken as red."""
    root = red_project(tmp_path)
    stage(root, NEW_FILE,OUTSIDE)
    verdict = run_gate(root)
    assert reason(verdict) == "red-not-proven"
    assert "nopkg" in verdict.message
    assert recorded(root) == []


def test_the_code_commit_after_the_red_commit_is_allowed(tmp_path):
    """Checks: the code that makes the recorded red test pass is allowed."""
    root = red_project(tmp_path)
    assert red_commit(root) == [NEW]
    stage(root, "app.py", APP_MUL)
    assert reason(run_gate(root)) == "allow"


def test_a_green_code_commit_that_deletes_the_recorded_test_is_refused(tmp_path):
    """Catches: a green suite made by deleting the recorded red test in the code commit."""
    root = red_project(tmp_path)
    red_commit(root)
    git(root, "rm", "-q", "--", NEW_FILE)
    stage(root, "app.py", APP_MUL)
    verdict = run_gate(root)
    assert reason(verdict) == "red-ids-still-red"
    assert NEW in verdict.message


def test_a_green_code_commit_that_skips_the_recorded_test_is_refused(tmp_path):
    """Catches: a green suite made by skipping the recorded red test in the code commit."""
    root = red_project(tmp_path)
    red_commit(root)
    stage(root, NEW_FILE,SKIPPED)
    stage(root, "app.py", APP_MUL)
    assert reason(run_gate(root)) == "red-ids-still-red"


def test_a_code_commit_in_a_root_with_no_record_is_refused(tmp_path):
    """Catches: code committed in a root where the card's red tests were never committed and proven."""
    root = red_project(tmp_path)
    stage(root, "app.py", APP_MUL)
    verdict = run_gate(root)
    assert reason(verdict) == "red-not-recorded"
    assert "commit the failing tests first, alone (the gate runs them and records the red), then commit the code" in verdict.message


def test_replay_a_test_and_its_code_in_one_commit_is_refused(tmp_path):
    """Catches: the test-after case, a green test committed together with its code."""
    root = red_project(tmp_path)
    stage(root, NEW_FILE,GREEN)
    stage(root, "app.py", APP_MUL)
    assert reason(run_gate(root)) == "test-without-red-proof"


def test_the_code_commit_that_creates_the_missing_module_is_allowed(tmp_path):
    """Checks: the ids of a red-by-missing file appear when the module is created, and they are in the record."""
    root = red_project(tmp_path)
    assert red_commit(root, MISSING) == [NEW]
    stage(root, "app2.py", APP2)
    assert reason(run_gate(root)) == "allow"


def test_in_watch_mode_the_gate_allows_with_the_reason_line_and_writes_the_record(tmp_path):
    """Checks: in watch mode a refusal becomes a warning with its reason id, and the record row is still written."""
    root = red_project(tmp_path, tests={"red_proof": {"mode": "watch"}})
    stage(root, NEW_FILE,GREEN)
    verdict = run_gate(root)
    assert (verdict.kind, verdict.reason_id) == ("warn", "red-not-proven")
    assert record_rows(root)[0]["would_refuse"] == ["red-not-proven"]


def test_a_declared_pin_of_a_refactor_card_is_allowed(tmp_path):
    """Checks: a passing new test with the Pins docstring and its Acceptance row, on a refactor card."""
    root = red_project(tmp_path, kind="refactor", row=PIN_ROW)
    stage(root, NEW_FILE,PIN)
    assert reason(run_gate(root)) == "allow"
    assert record_rows(root)[0]["pins"] == ["tests/test_new.py::test_add_again"]


def test_a_pin_without_the_pins_docstring_is_refused_on_real_files(tmp_path):
    """Catches: a passing test of a refactor card with no Pins docstring."""
    root = red_project(tmp_path, kind="refactor", row=PIN_ROW)
    stage(root, NEW_FILE,GREEN)
    assert reason(run_gate(root)) == "red-not-proven"


def test_a_command_that_is_not_pytest_keeps_the_old_red_first_path(tmp_path):
    """Checks: with a tests command that is not pytest nothing can be told, so a tests-only commit runs nothing."""
    root = red_project(tmp_path, tests={"command": "python -c pass"})
    stage(root, NEW_FILE,GREEN)
    assert reason(run_gate(root)) == "allow"
    assert rows(root) == []


def test_a_docs_only_commit_is_not_judged(tmp_path):
    """Checks: a commit of documents alone runs nothing and records nothing."""
    root = red_project(tmp_path)
    stage(root, "notes.md", "text\n")
    assert reason(run_gate(root)) == "allow"
    assert rows(root) == []
    assert record_rows(root) == []


def test_a_tests_only_commit_that_breaks_an_old_test_is_still_refused(tmp_path):
    """Catches: a tests-only commit that makes an old test fail, which only the new ids may do."""
    root = red_project(tmp_path)
    stage(root, OK_FILE, BROKEN_OLD)
    verdict = run_gate(root)
    assert reason(verdict) == "commit-tests-failed"
    assert "tests/test_ok.py::test_add" in verdict.message


def test_a_checks_test_that_passes_next_to_a_red_test_is_allowed_and_listed(tmp_path):
    """Checks: a passing Checks guard beside a red test is allowed (ruling R183) and the record lists it."""
    root = red_project(tmp_path)
    stage(root, NEW_FILE,RED_AND_CHECKS)
    assert reason(run_gate(root)) == "allow"
    assert recorded(root) == [NEW]
    assert record_rows(root)[0]["checks"] == ["tests/test_new.py::test_add_again"]


def test_a_catches_test_that_passes_next_to_a_red_test_is_refused(tmp_path):
    """Catches: a passing test whose docstring is Catches, which must have been red (ruling R183)."""
    root = red_project(tmp_path)
    stage(root, NEW_FILE,RED_AND_CATCHES)
    verdict = run_gate(root)
    assert reason(verdict) == "red-not-proven"
    assert "test_add_again" in verdict.message


def test_replay_a_red_commit_of_nine_red_ids_and_four_checks_green_ids_is_allowed(tmp_path):
    """Checks: the shape of a real red commit, 9 red ids and 4 passing Checks guards, on real pytest."""
    root = red_project(tmp_path)
    stage(root, NEW_FILE,REPLAY)
    assert reason(run_gate(root)) == "allow"
    assert len(recorded(root)) == 9
    assert len(record_rows(root)[0]["checks"]) == 4


def write_record(root, *lines):
    path = Path(root) / "mkway" / "state" / "red_proof.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(line + "\n" for line in lines), encoding="utf-8")


def test_a_tests_command_that_cannot_be_read_keeps_the_old_red_first_path(tmp_path):
    """Checks: when the tests command cannot be run by the engine, a tests-only commit runs nothing, as before."""
    root = red_project(tmp_path, tests={"command": "notpython -m pytest -q"})
    stage(root, NEW_FILE,RED_MUL)
    assert reason(run_gate(root)) == "allow"
    assert rows(root) == []


def test_a_tests_command_that_cannot_be_read_refuses_a_code_commit(tmp_path):
    """Checks: a code commit is refused when the tests command cannot be read, as the old gate already does (R183 guard)."""
    root = red_project(tmp_path, tests={"command": "notpython -m pytest -q"})
    stage(root, "app.py", APP_MUL)
    assert reason(run_gate(root)) == "commit-tests-not-run"


def test_a_record_row_of_another_card_and_a_broken_line_are_no_record(tmp_path):
    """Catches: a red record read from another card's row, or a gate that stops at a broken line."""
    root = red_project(tmp_path)
    write_record(root, "not json", json.dumps({"card": "CARD-009", "tree": "0" * 40, "red": [NEW]}))
    stage(root, "app.py", APP_MUL)
    assert reason(run_gate(root)) == "red-not-recorded"


def test_a_record_row_of_a_commit_that_was_never_made_is_no_record(tmp_path):
    """Catches: a record written for a commit that the gate allowed and that was then never made."""
    root = red_project(tmp_path)
    write_record(root, json.dumps({"card": "CARD-001", "tree": "0" * 40, "red": [NEW]}))
    stage(root, "app.py", APP_MUL)
    assert reason(run_gate(root)) == "red-not-recorded"


def test_a_code_commit_that_leaves_the_recorded_test_failing_is_refused_as_red_suite(tmp_path):
    """Catches: a code commit that does not make the recorded red test pass; the red suite is refused first."""
    root = red_project(tmp_path)
    assert red_commit(root) == [NEW]
    stage(root, "app.py", "def add(a, b):\n    return a + b + 0\n")
    verdict = run_gate(root)
    assert reason(verdict) == "commit-tests-failed"
    assert NEW in verdict.message


def test_recorded_tests_that_do_not_finish_refuse_the_commit(tmp_path, monkeypatch):
    """Catches: a code commit passed because the check of the recorded tests did not finish."""
    root = red_project(tmp_path)
    assert red_commit(root) == [NEW]
    real = gct.runner.run_tree
    monkeypatch.setattr(gct.runner, "run_tree", lambda argv, **kw: (None, "", "") if "-v" in argv else real(argv, **kw))
    stage(root, "app.py", APP_MUL)
    assert reason(run_gate(root)) == "commit-tests-not-run"


def test_a_suite_over_budget_is_refused_before_the_red_proof(tmp_path):
    """Checks: a suite over budget is refused before any red proof, as the old gate already does (R183 guard)."""
    root = red_project(tmp_path, gates={"commit_tests": {"budget_seconds": 0.01}})
    stage(root, "app.py", APP_MUL)
    assert reason(run_gate(root)) == "commit-tests-over-budget"


def test_a_card_file_that_cannot_be_read_gives_no_pin(tmp_path):
    """Catches: a pin allowed with no card text to say that it is one."""
    root = red_project(tmp_path, kind="refactor", row=PIN_ROW)
    card_file(root).unlink()
    stage(root, NEW_FILE,PIN)
    assert reason(run_gate(root)) == "red-not-proven"


def test_the_test_ids_of_a_source_come_with_their_docstrings():
    """Checks: module functions and methods of Test classes are read by name with the first docstring, not collected."""
    source = ('def test_a():\n    """Pins: a."""\n\n\ndef helper():\n    pass\n\n\nclass TestB:\n'
              '    def test_b(self):\n        """Checks: b."""\n\n    def other(self):\n        pass\n')
    assert gct.static_ids(source, "tests/t.py") == {"tests/t.py::test_a": "Pins: a.",
                                                    "tests/t.py::TestB::test_b": "Checks: b."}


def test_the_test_ids_of_a_source_that_does_not_parse_are_none():
    """Checks: a source with a syntax error has no readable test ids, so none are invented for it."""
    assert gct.static_ids("def test_a(:\n", "tests/t.py") == {}


def test_the_same_staged_tree_is_run_and_recorded_once(tmp_path):
    """Checks: a repeated call on the same staged tree reads the kept run and writes no second record row."""
    root = red_project(tmp_path)
    stage(root, NEW_FILE,RED_MUL)
    assert reason(run_gate(root)) == "allow"
    assert reason(run_gate(root)) == "allow"
    assert len(rows(root)) == 1
    assert len(record_rows(root)) == 1


def test_a_session_that_holds_no_card_is_not_judged_on_real_files(tmp_path):
    """Checks: with no card held the code commit is judged by the suite alone, and nothing is recorded."""
    root = make_project(tmp_path)
    stage(root, "app.py", APP_MUL)
    assert reason(run_gate(root)) == "allow"
    assert record_rows(root) == []


# ---- card MW-090: the card's case_map.md judged under a named decision (decisions R219, R222, R223, R225) -------------------

OLD = "tests/test_ok.py::test_add"  # the one test of the project at HEAD
PATTERN = "DEC-[0-9]+"
LEDGER_PATTERN = r"\bD-[0-9]+\b"  # word boundaries: the tail of the card id would match a bare pattern
EMPTY = "# no test is left in this file\n"
MAP_LINE = f"{OLD} -> {NEW}"
UNKNOWN_LINE = f"tests/test_ok.py::test_never_existed -> {NEW}"
BAD_TEXT = "no match of tests.red_proof.decision_pattern"


def map_rel(root):
    """The card's case_map.md, relative to the task root."""
    return card_file(root).parent.relative_to(Path(root)).as_posix() + "/case_map.md"


def commit_with(*words):
    return 'git commit -m "CARD-001 ' + " ".join(words) + '"'


def decided(tmp_path, pattern=PATTERN, **more):
    return red_project(tmp_path, tests={"red_proof": {"decision_pattern": pattern, **more}})


def stage_rename(root, line=MAP_LINE):
    """The commit of a rename: the old test leaves its file, the new red test arrives, the case_map says so."""
    stage(root, NEW_FILE, RED_MUL)
    stage(root, OK_FILE, EMPTY)
    stage(root, map_rel(root), line + "\n")


def add_decision(root, by, status="in force"):
    profile = json.loads((Path(root) / "mkway" / "profile.json").read_text(encoding="utf-8"))
    return ledger.add(root, profile, card="C", topic="t", quote="q", source="s", by=by, status=status)["id"]


def head_tree(root, use_head):
    return gct.tree_keys(root, "HEAD")[0] if use_head else "0" * 40


def test_a_new_case_map_line_with_no_decision_in_the_message_is_refused(tmp_path):
    """Catches: a rename line that carries a status in a commit whose message names no decision (R225 4)."""
    root = red_project(tmp_path)
    stage_rename(root)
    verdict = run_gate(root, commit_with("rename"))
    assert reason(verdict) == "case-map-no-decision"
    assert BAD_TEXT in verdict.message


def test_a_decision_in_the_message_counts_by_the_pattern_alone_when_the_root_has_no_ledger(tmp_path):
    """Checks: the commit message reaches the core, the pattern matches, the root has no ledger, the valid rename is allowed (R222 1)."""
    root = decided(tmp_path)
    stage_rename(root)
    assert reason(run_gate(root, commit_with("DEC-1", "rename"))) == "allow"
    assert recorded(root) == [NEW]


def test_the_committed_case_map_is_judged_and_not_the_working_copy(tmp_path):
    """Catches: a gate that reads the case_map from the working folder, where a bad staged line was fixed after staging."""
    root = decided(tmp_path)
    stage_rename(root, UNKNOWN_LINE)
    write(root, map_rel(root), MAP_LINE + "\n")
    assert reason(run_gate(root, commit_with("DEC-1", "rename"))) == "case-map-unknown-left"


def test_an_unstaged_left_file_is_read_at_head_and_its_id_still_exists_in_the_tree(tmp_path):
    """Catches: a left file read from the working folder, where its test is gone, while the committed tree still holds it."""
    root = decided(tmp_path)
    stage(root, NEW_FILE, RED_MUL)
    stage(root, map_rel(root), MAP_LINE + "\n")
    write(root, OK_FILE, EMPTY)
    verdict = run_gate(root, commit_with("DEC-1", "rename"))
    assert reason(verdict) == "case-map-unknown-left"
    assert "still exists in the committed tree" in verdict.message


def test_a_left_in_the_red_record_of_another_card_is_refused(tmp_path):
    """Catches: a card that renames a test the red record of another card holds (R225 6)."""
    root = decided(tmp_path)
    write_record(root, json.dumps({"card": "CARD-009", "tree": head_tree(root, True), "red": [OLD]}))
    stage_rename(root)
    verdict = run_gate(root, commit_with("DEC-1", "rename"))
    assert reason(verdict) == "case-map-unknown-left"
    assert "is in the red record of CARD-009" in verdict.message


@pytest.mark.parametrize("card, use_head", [("CARD-001", True), ("CARD-009", False)], ids=["same_card", "commit_never_made"])
def test_a_red_record_of_the_same_card_or_of_a_commit_never_made_is_not_another_cards(tmp_path, card, use_head):
    """Checks: the record of the committing card, and a row whose tree is no commit of HEAD, do not hold a left back.
    Changed by MW-134 (R347, R348): a left the committing card's own record holds is retired by the line, and a retirement needs
    a ledger decision of another session, so the root has a ledger and the message names its row."""
    root = decided(tmp_path, LEDGER_PATTERN)
    decision = add_decision(root, "session:other")
    write_record(root, json.dumps({"card": card, "tree": head_tree(root, use_head), "red": [OLD]}))
    stage_rename(root)
    assert reason(run_gate(root, commit_with(decision, "rename"))) == "allow"


def test_a_ledger_decision_that_is_in_force_and_not_by_the_session_counts(tmp_path):
    """Checks: in a root with a ledger a matched id counts when its row is in force and its by is another session (R222 1)."""
    root = decided(tmp_path, LEDGER_PATTERN)
    decision = add_decision(root, "session:other")
    stage_rename(root)
    assert reason(run_gate(root, commit_with(decision, "rename"))) == "allow"


@pytest.mark.parametrize("by, status, number, said", [
    ("session:other", "withdrawn", 1, "its status is withdrawn"),
    ("session:other", "superseded", 1, "its status is superseded"),
    ("session:s1", "in force", 1, "it is by this session"),
    ("session:other", "in force", 7, "it is not a row of the ledger")], ids=["withdrawn", "superseded", "by_self", "no_row"])
def test_a_ledger_decision_that_does_not_count_is_refused_with_its_why(tmp_path, by, status, number, said):
    """Catches: a decision that is closed, written by the committing session, or not a row, taken as the decision a line needs."""
    root = decided(tmp_path, LEDGER_PATTERN)
    add_decision(root, by, status)
    stage_rename(root)
    verdict = run_gate(root, commit_with(f"D-{number}", "rename"))
    assert reason(verdict) == "case-map-no-decision"
    assert said in verdict.message


def test_a_docs_only_commit_that_stages_a_bad_case_map_line_is_refused(tmp_path):
    """Catches: a docs-only commit that lands a mapping line unjudged, which later commits would trust as judged (R225 4)."""
    root = decided(tmp_path)
    stage(root, map_rel(root), MAP_LINE + "\n")
    assert reason(run_gate(root, commit_with("DEC-1", "rename"))) == "case-map-unknown-left"
    assert rows(root) == []


def test_a_docs_only_commit_of_comment_lines_is_allowed_and_runs_no_suite(tmp_path):
    """Checks: comment and blank lines are never judged, and the docs-only commit runs no suite."""
    root = decided(tmp_path)
    stage(root, map_rel(root), "# kept: tests/test_ok.py::test_add - stays\n\n")
    assert reason(run_gate(root, commit_with("note"))) == "allow"
    assert rows(root) == []


def test_a_case_map_that_is_not_staged_is_not_judged(tmp_path):
    """Checks: a commit that does not stage the card's case_map.md is judged as today, whatever the working folder holds."""
    root = decided(tmp_path)
    stage(root, NEW_FILE, RED_MUL)
    write(root, map_rel(root), UNKNOWN_LINE + "\n")
    assert reason(run_gate(root, commit_with("tests"))) == "allow"


def test_in_watch_mode_a_case_map_refusal_is_a_warning_with_the_same_reason(tmp_path):
    """Checks: in watch mode the five case_map refusals become a warning with the same reason id and text (one row for all)."""
    root = decided(tmp_path, mode="watch")
    stage_rename(root)
    verdict = run_gate(root, commit_with("rename"))
    assert (verdict.kind, verdict.reason_id) == ("warn", "case-map-no-decision")
    assert BAD_TEXT in verdict.message


def test_a_decision_pattern_that_does_not_compile_is_no_decision(tmp_path):
    """Catches: an unusable pattern that is read as matching everything, which would back every line."""
    root = decided(tmp_path, pattern="(")
    stage_rename(root)
    verdict = run_gate(root, commit_with("DEC-1", "rename"))
    assert reason(verdict) == "case-map-no-decision"
    assert BAD_TEXT in verdict.message
