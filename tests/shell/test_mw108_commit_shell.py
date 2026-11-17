"""Card MW-108: the commit gate judges only the new red of this commit. Each test builds the tiny synthetic project of
`_commit_project.py` (a real git repository, a real pytest run, about a second per run) through `_mw108.py`, opens cards
with the real card commands and drives the gate in process. Two tests replay the real cases of the dedup task (DD-001,
DD-010) with made-up files. The engine's own suite is never run here. Synthetic names only."""
from pathlib import Path

from _commit_project import git, reason, rows, run_gate, stage
from _mw108 import (APP, COLLECT_FAIL, KEYS, ORPHAN, RED, TWO, commit_file, hold, make_head_row, open_card, project,
                    take)


def test_replay_dd010_a_red_first_commit_beside_an_old_own_red_is_allowed(tmp_path):
    """Catches: the DD-010 trap, a red-first commit refused for a red of the card's own Paths that was already red when the
    card was taken, with advice (commit the tests alone) that the same gate then refused (E14)."""
    root = project(tmp_path)
    card = open_card(root, "Keys", "`app.py`, `tests/test_keys.py`")
    commit_file(root, "tests/test_keys.py", RED.format(name="keys"))
    make_head_row(root)
    assert take(root, card)[0] == 0
    hold(root, card)
    stage(root, "tests/test_new.py", RED.format(name="new"))
    verdict = run_gate(root)
    assert verdict.kind == "warn", (verdict.kind, verdict.message)
    assert verdict.reason_id == "commit-tests-still-red"
    assert f"old red: {KEYS}, owner CARD-001" in verdict.message


def test_replay_dd001_a_green_commit_beside_the_old_red_of_a_closed_card_is_allowed(tmp_path):
    """Catches: the DD-001 trap, a green commit refused for 14.5 hours because a file that fails at collection at HEAD
    belongs to a card that is gone (E15)."""
    root = project(tmp_path)
    card = open_card(root, "Green", "`app.py`")
    commit_file(root, "tests/test_synth.py", COLLECT_FAIL)
    hold(root, card)
    stage(root, "app.py", APP.format(n=1))
    verdict = run_gate(root)
    assert verdict.kind == "warn", (verdict.kind, verdict.message)
    assert verdict.reason_id == "commit-tests-still-red"
    assert "old red: tests/test_synth.py, owner none" in verdict.message


def test_the_commit_row_holds_the_old_red_with_its_owner(tmp_path):
    """Checks: the row of the run in `commit_tests.jsonl` gets the key `old_red`, a list of `{test, card}`, the card null
    for an orphan and the owner card for the red of another open card (E16)."""
    root = project(tmp_path)
    open_card(root, "Green", "`app.py`")
    other = open_card(root, "Two", "`tests/test_two.py`")
    commit_file(root, "tests/test_orphan.py", RED.format(name="orphan"))
    commit_file(root, "tests/test_two.py", RED.format(name="two"))
    hold(root, "CARD-001")
    stage(root, "app.py", APP.format(n=2))
    assert run_gate(root).kind == "warn"
    assert rows(root)[-1]["old_red"] == [{"test": ORPHAN, "card": None}, {"test": TWO, "card": other}]


def test_a_new_red_is_still_refused_beside_an_old_red(tmp_path):
    """Catches: an old red that lets a new red of the same commit through, on a real repository (E17)."""
    root = project(tmp_path)
    card = open_card(root, "Green", "`app.py`")
    commit_file(root, "tests/test_orphan.py", RED.format(name="orphan"))
    hold(root, card)
    stage(root, "app.py", APP.format(n=3))
    stage(root, "tests/test_new.py", RED.format(name="new"))
    verdict = run_gate(root)
    assert reason(verdict) == "commit-tests-failed"
    assert "tests/test_new.py::test_new" in verdict.message
    assert "new red" in verdict.message
    assert ORPHAN not in verdict.message


def test_way_out_of_commit_tests_failed_the_tests_alone_in_the_plain_form_pass(tmp_path):
    """Checks: the way out the refusal names works: after a commit with a new red is refused, the tests alone in the plain
    form `git commit -m ... -- <test files>` are allowed, the old red beside them is only shown (E18)."""
    root = project(tmp_path)
    card = open_card(root, "Green", "`app.py`, `tests/test_new.py`")
    commit_file(root, "tests/test_orphan.py", RED.format(name="orphan"))
    hold(root, card)
    stage(root, "app.py", APP.format(n=4))
    stage(root, "tests/test_new.py", RED.format(name="new"))
    refused = run_gate(root)
    assert reason(refused) == "commit-tests-failed"
    assert 'git commit -m "CARD-001 tests only: <what>" -- <test files>' in refused.message
    git(root, "reset", "-q", "--", "app.py")
    git(root, "checkout", "-q", "--", "app.py")
    allowed = run_gate(root, "git commit -m 'CARD-001 tests only: new red' -- tests/test_new.py")
    assert reason(allowed) == "allow"
    assert Path(root, "tests", "test_new.py").is_file()
