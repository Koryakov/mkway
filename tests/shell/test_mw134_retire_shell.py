"""Card MW-134 (rulings R347, R348, R348a), layer shell, on real git repositories with the real gate (`gate_commit_tests.check`): a
recorded red id is retired by a valid case_map.md line of the card, in a tests-only (or documents-only) commit, under a decision of
the ledger that another session wrote. The decision is proven by `tests/core/test_mw134_retire_core.py`; here each test proves one
fact is read right or one wire is connected. The red rows of the history are written by hand (`_mw134.seed`) as the gate would
have written them; the commit under test is always judged by the real gate. Synthetic names only."""
import json
import sys
import time
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/: the shared helpers
import _mw134 as w  # noqa: E402
from _commit_project import git, reason, run_gate, stage  # noqa: E402
from _engine import jsonl  # noqa: E402
from _mw018 import seen  # noqa: E402
from _red_project import APP_MUL  # noqa: E402
import gate_commit_tests as gct  # noqa: E402
import register  # noqa: E402
import scorecard  # noqa: E402


@pytest.fixture(autouse=True)
def _red_templates(template_copy):
    """R217b: `red_project` builds each variant of the project once per worker and gives each test a copy."""
    from _red_project import use_template_copy
    with use_template_copy(template_copy):
        yield


def _state(root) -> Path:
    return Path(root) / "mkway" / "state"


def _errors(root, reason_id="retire-notice-failed") -> list:
    path = _state(root) / "gate_calls.jsonl"
    return [r for r in jsonl(path) if r.get("reason_id") == reason_id and r.get("verdict") == "error"] if path.is_file() else []


def _ordered(root, who="lead-a"):
    """The orderer of the card is `who`, a session the engine has seen."""
    register.set_ordered(root, w.profile_of(root), w.CARD, who)
    seen(root, who)


# ---- the way out of red-ids-still-red, end to end (R347 2 f) -------------------------------------------------------------

def test_the_way_out_of_red_ids_still_red_for_an_absent_id_is_a_case_map_line_under_a_decision_by_another_session(tmp_path):
    """Catches: a refusal that names the way out, which the gate then does not honour: the code commit refused for the id that is gone, the case_map line committed alone under a decision of another session, the code commit allowed."""
    root = w.world(tmp_path)
    w.add_decision(root)
    refused = w.code_gate(root)
    assert reason(refused) == "red-ids-still-red"
    assert w.OLD in refused.message and "case_map.md" in refused.message and "another session" in refused.message
    w.unstage(root, "app.py")
    assert reason(w.retire(root)) == "allow"
    w.made(root, w.SAY)
    assert reason(w.code_gate(root)) == "allow"


# ---- the retirement row and the facts it is made of ---------------------------------------------------------------------------

def test_the_retirement_commit_writes_one_record_row_per_retired_id_with_the_decisions_by(tmp_path):
    """Checks: the row names the card, the left id, the right id, the decision, the by of the ledger row, the session and the git tree the commit then has (R347 2 e)."""
    root = w.world(tmp_path)
    decision = w.add_decision(root)
    assert reason(w.retire(root)) == "allow"
    w.made(root, w.SAY)
    (row,) = w.retire_rows(root)
    assert (row["card"], row["retired"], row["right"], row["decision"], row["by"], row["session"]) == (
        w.CARD, w.OLD, w.NEW, decision, w.LEAD, w.SESSION)
    assert row["git_tree"] == git(root, "rev-parse", "HEAD^{tree}").strip()


def test_a_dropped_line_writes_a_row_that_says_dropped(tmp_path):
    """Checks: the row of a dropped line holds «dropped» where a rename holds the right id."""
    root = w.world(tmp_path)
    w.add_decision(root)
    assert reason(w.retire(root, line=w.DROPPED)) == "allow"
    (row,) = w.retire_rows(root)
    assert (row["retired"], row["right"]) == (w.OLD, "dropped")


def test_the_retirement_row_holds_no_red_pins_or_missing_key_so_the_reader_before_this_card_skips_it(tmp_path):
    """Catches: a new row kind that the reader of the commit before this card (which keeps rows with a red, pins or missing key, and others' rows with a red key) would take for a red record (R348 5)."""
    root = w.world(tmp_path)
    w.add_decision(root)
    assert reason(w.retire(root)) == "allow"
    (row,) = w.retire_rows(root)
    assert not {"red", "pins", "missing"} & set(row)
    assert isinstance(row["tree"], str) and row["tree"]


def test_a_rename_in_one_tests_only_commit_retires_the_left_and_records_the_right_red(tmp_path):
    """Checks: the classic order, the left id leaves its file, the new failing right arrives and the case_map says so, all in one commit."""
    root = w.red_project(tmp_path)
    w.plain_commit(root, "app.py", APP_MUL, "CARD-001 code")
    w.plain_commit(root, w.NEW_FILE, w.V1, "CARD-001 red one")
    w.seed(root, [w.OLD])
    w.add_decision(root)
    stage(root, w.NEW_FILE, w.V2_RED)
    w.stage_line(root)
    assert reason(run_gate(root, w.commit(w.SAY))) == "allow"
    assert [r["retired"] for r in w.retire_rows(root)] == [w.OLD]
    assert w.NEW in [i for r in w.record_rows(root) for i in r.get("red", [])]


def test_the_same_line_in_a_code_commit_retires_nothing(tmp_path):
    """Catches: a case_map line staged with the code, which would change the record that very commit is judged with (R347 2 b)."""
    root = w.world(tmp_path)
    w.add_decision(root)
    w.stage_line(root)
    stage(root, "app.py", w.CODE2)
    verdict = run_gate(root, w.commit(w.SAY))  # the message names the decision, so the line itself is judged valid
    assert reason(verdict) == "red-ids-still-red"
    assert w.OLD in verdict.message
    assert w.retire_rows(root) == []


def test_a_present_and_failing_id_is_never_retired_by_a_line(tmp_path):
    """Catches: a line that retires an id that is still in the tree and fails, instead of the code being fixed."""
    root = w.world(tmp_path)
    w.plain_commit(root, w.NEW_FILE, w.BOTH)  # test_mul is back in the file and fails
    w.add_decision(root)
    verdict = w.retire(root)
    assert reason(verdict) == "case-map-unknown-left"
    assert w.retire_rows(root) == []


def test_a_retirement_row_from_a_commit_not_in_the_history_of_head_counts_for_nothing(tmp_path):
    """Catches: a row written for a commit that was never made (or sits on another branch) that drops an id from the record."""
    root = w.world(tmp_path)
    ghost = "0" * 40
    row = {"time": "2026-11-17T10:00:00.000+00:00", "session": w.SESSION, "card": w.CARD, "tree": ghost, "git_tree": ghost,
           "retired": w.OLD, "right": w.NEW, "decision": "D-1", "by": w.LEAD}
    with w.red_file(root).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")
    assert reason(w.code_gate(root)) == "red-ids-still-red"


def test_a_retired_id_that_a_later_tests_only_commit_records_red_again_is_in_the_record_again(tmp_path):
    """Catches: a retirement that outlives a later red commit of the same id, which would leave that test unenforced: the code commit that deletes it again is allowed."""
    root = w.world(tmp_path)
    w.add_decision(root)
    assert reason(w.retire(root)) == "allow"
    w.made(root, w.SAY)
    stage(root, w.NEW_FILE, w.BOTH)
    assert reason(run_gate(root, w.commit("CARD-001 red again"))) == "allow"
    w.made(root, "CARD-001 red again")
    stage(root, w.NEW_FILE, w.V2)  # the id is deleted again, with a code change
    stage(root, "app.py", w.CODE2)
    verdict = run_gate(root, w.commit("CARD-001 code"))
    assert reason(verdict) == "red-ids-still-red"
    assert w.OLD in verdict.message


# ---- absent is not «not collected» (R348 2) -----------------------------------------------------------------------------------

def _outcomes(tmp_path, files, ids):
    """`gate_commit_tests._outcomes` on a small exported tree holding `files`: {id: passed | failed | skipped | gone}."""
    for rel, text in files.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    run = types.SimpleNamespace(argv=[sys.executable, "-m", "pytest", "-q", "tests"], limit=120.0, started=time.perf_counter(),
                                profile={"python": {"command": sys.executable}}, ctx=types.SimpleNamespace(env={}))
    return gct._outcomes(run, tmp_path, ids, ["tests"])


@pytest.mark.parametrize("text", [w.BROKEN, w.IMPORT_ERROR], ids=["syntax_error", "import_error"])
def test_an_id_in_a_file_that_fails_to_collect_is_failing_not_absent(tmp_path, text):
    """Catches: the ids of a file that fails to collect (a syntax or import error) read as «deleted or renamed», which would offer them the retirement way out (R348 2)."""
    got = _outcomes(tmp_path, {"tests/test_new.py": text}, [w.OLD, w.NEW])
    assert got == {w.OLD: "failed", w.NEW: "failed"}


def test_an_id_that_a_clean_collection_does_not_hold_is_absent(tmp_path):
    """Checks: the contrast of R348 2: the collection ran clean and the id is not in it (or its file is gone), so it is absent and the retirement way out is named."""
    clean = "def test_mul_v2():\n    pass\n"
    got = _outcomes(tmp_path, {"tests/test_new.py": clean}, [w.OLD, w.NEW, "tests/test_deleted.py::test_y"])
    assert got == {w.OLD: "gone", w.NEW: "passed", "tests/test_deleted.py::test_y": "gone"}


# ---- the refusal ids of a retirement, each with its way out ------------------------------------------------------------------

def test_the_way_out_of_retire_no_decision_is_a_message_that_names_a_decision(tmp_path):
    """Catches: a retirement commit whose message names no decision, which would be allowed with no anchor; the way out is to name one."""
    root = w.world(tmp_path)
    w.add_decision(root)
    verdict = w.retire(root, message="CARD-001 retire the old test")
    assert reason(verdict) == "retire-no-decision"
    assert "decision" in verdict.message and "another session" in verdict.message
    assert reason(run_gate(root, w.commit(w.SAY))) == "allow"


def test_the_way_out_of_retire_decision_not_in_ledger_is_a_decision_that_is_a_row_of_the_ledger(tmp_path):
    """Catches: a decision id that is no row of the ledger taken as the anchor; the way out is to name a row."""
    root = w.world(tmp_path)
    w.add_decision(root)
    verdict = w.retire(root, message="CARD-001 retire the old test under D-9")
    assert reason(verdict) == "retire-decision-not-in-ledger"
    assert "D-9: it is not a row of the ledger" in verdict.message
    assert reason(run_gate(root, w.commit(w.SAY))) == "allow"


def test_the_way_out_of_retire_decision_closed_is_a_decision_that_is_in_force(tmp_path):
    """Catches: a withdrawn or superseded decision taken as the anchor; the way out is a decision in force."""
    root = w.world(tmp_path)
    w.add_decision(root, status="withdrawn")
    second = w.add_decision(root)
    verdict = w.retire(root)
    assert reason(verdict) == "retire-decision-closed"
    assert "D-1: its status is withdrawn" in verdict.message
    assert reason(run_gate(root, w.commit(f"CARD-001 retire the old test under {second}"))) == "allow"


def test_the_way_out_of_retire_decision_by_self_is_a_decision_another_session_wrote(tmp_path):
    """Catches: a builder that retires its own failing test under a decision it wrote itself (the GitHub rule: someone other than the person who pushed it)."""
    root = w.world(tmp_path)
    w.add_decision(root, by=f"session:{w.SESSION}")
    second = w.add_decision(root)
    verdict = w.retire(root)
    assert reason(verdict) == "retire-decision-by-self"
    assert "D-1: it is by this session" in verdict.message
    assert reason(run_gate(root, w.commit(f"CARD-001 retire the old test under {second}"))) == "allow"


def test_the_way_out_of_retire_no_ledger_is_a_ledger_row_of_another_session(tmp_path):
    """Catches: a root with no ledger file, where the pattern alone names a decision whose by cannot be checked, taken as an anchor; the way out is a ledger with the row."""
    root = w.world(tmp_path, tests={"red_proof": {"decision_pattern": r"\bD-[0-9]+\b"}})
    verdict = w.retire(root)
    assert reason(verdict) == "retire-no-ledger"
    assert "ledger" in verdict.message
    w.add_decision(root)
    assert reason(run_gate(root, w.commit(w.SAY))) == "allow"


def test_the_way_out_of_retire_right_not_red_is_a_right_side_that_was_seen_red(tmp_path):
    """Catches: a rename into a test that passes as a `Checks:` guard, so the left is retired with no red replacement; the way out is the right side that failed."""
    root = w.world(tmp_path)
    w.add_decision(root)
    guard = ('\n\ndef test_guard():\n    """Checks: add sums."""\n    from app import add\n    assert add(1, 1) == 2\n'
             '\n\ndef test_red_two():\n    """Catches: mul is wrong."""\n    assert __import__("app").mul(2, 2) == 5\n')
    stage(root, w.NEW_FILE, w.V2 + guard)
    w.stage_line(root, f"{w.OLD} -> {w.NEW_FILE}::test_guard")
    verdict = run_gate(root, w.commit(w.SAY))
    assert reason(verdict) == "retire-right-not-red"
    assert f"{w.NEW_FILE}::test_guard" in verdict.message
    w.stage_line(root, f"{w.OLD} -> {w.NEW_FILE}::test_red_two")
    assert reason(run_gate(root, w.commit(w.SAY))) == "allow"


def test_the_way_out_of_retire_left_failing_is_a_file_that_collects(tmp_path):
    """Catches: an id of a file that does not parse, which the static reader sees as gone, retired as if it were absent; the way out is a file that collects."""
    root = w.world(tmp_path)
    w.add_decision(root)
    w.plain_commit(root, w.NEW_FILE, w.BROKEN, "CARD-001 broken by hand")
    verdict = w.retire(root, line=w.DROPPED)
    assert reason(verdict) == "retire-left-failing"
    assert w.NEW_FILE in verdict.message
    w.unstage(root, w.map_rel(root))
    w.plain_commit(root, w.NEW_FILE, w.V2, "CARD-001 repaired")
    assert reason(w.retire(root, line=w.DROPPED)) == "allow"


# ---- the notice (R348 3) ------------------------------------------------------------------------------------------------------

def test_each_retirement_writes_one_notice_to_the_orderer_of_the_card(tmp_path):
    """Checks: one `notice` inbox row to the card's orderer, «<session> retired <left> of <card> under <decision>»."""
    root = w.world(tmp_path, cards={"approver": "orderer"})
    _ordered(root)
    decision = w.add_decision(root)
    assert reason(w.retire(root)) == "allow"
    inbox = jsonl(_state(root) / "inbox" / "lead-a.jsonl")
    assert [(r["from"], r["kind"], r["body"]) for r in inbox] == [
        (w.SESSION, "notice", f"{w.SESSION} retired {w.OLD} of {w.CARD} under {decision}")]


def test_a_failed_notice_never_refuses_the_commit_and_writes_an_error_row(tmp_path):
    """Catches: a notice that cannot be delivered (the orderer is no live session) that refuses the retirement or leaves no trace; the retirement stands and the error row tells the builder to write to its orderer itself."""
    root = w.world(tmp_path, cards={"approver": "orderer"})
    register.set_ordered(root, w.profile_of(root), w.CARD, "lead-gone")
    w.add_decision(root)
    assert reason(w.retire(root)) == "allow"
    assert [r["retired"] for r in w.retire_rows(root)] == [w.OLD]
    (error,) = _errors(root)
    assert error["session"] == w.SESSION and error["error"]


def test_the_way_out_of_retire_notice_failed_is_that_the_retirement_stands_and_the_builder_writes_itself(tmp_path):
    """Checks: after a failed notice the retirement is in the record: the code commit that needed it is allowed."""
    root = w.world(tmp_path, cards={"approver": "orderer"})
    register.set_ordered(root, w.profile_of(root), w.CARD, "lead-gone")
    w.add_decision(root)
    assert reason(w.retire(root)) == "allow"
    w.made(root, w.SAY)
    assert reason(w.code_gate(root)) == "allow"
    assert len(_errors(root)) == 1


# ---- the scorecard (R347 2 e) -------------------------------------------------------------------------------------------------

def test_the_scorecard_counts_the_retirements_per_card(tmp_path):
    """Checks: a line `retirements <card>: <n>` counts the retirement rows of the card."""
    root = w.world(tmp_path)
    w.add_decision(root)
    assert reason(w.retire(root)) == "allow"
    assert f"retirements {w.CARD}: 1" in scorecard.lines(root, w.profile_of(root))


# ---- the default decision pattern (R348a) -------------------------------------------------------------------------------------

def test_a_decision_id_inside_a_longer_token_names_no_decision(tmp_path):
    """Catches: a pattern hit inside a longer token (`D-1x`, the tail of a card id) taken as the decision D-1."""
    root = w.world(tmp_path)
    w.add_decision(root)
    verdict = w.retire(root, message="CARD-001 retire the old test under D-1x")
    assert reason(verdict) == "retire-no-decision"


def test_in_watch_mode_a_retire_refusal_is_a_warning_and_retires_nothing(tmp_path):
    """Catches: a retirement written in watch mode for a commit whose refusal was only a warning."""
    root = w.world(tmp_path, tests={"red_proof": {"mode": "watch"}})
    w.add_decision(root)
    verdict = w.retire(root, message="CARD-001 retire the old test")
    assert (verdict.kind, verdict.reason_id) == ("warn", "retire-no-decision")
    assert w.retire_rows(root) == []
