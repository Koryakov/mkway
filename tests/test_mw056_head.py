"""Card MW-056: the commit gate refuses only new red. Each test builds the tiny synthetic project of
`_commit_project.py` (a real git repository, a real pytest run, about a second per run), opens cards through the real
card commands, and drives the gate in process. The engine's own suite is never run here. Synthetic names only."""
from pathlib import Path

import pytest

from _commit_project import git, make_project, rows, run_gate, set_profile, stage, write
from _engine import cli, jsonl
from _red_project import seed_record
from test_cardmoves import set_paths
import gate_commit_tests as gct
import records

RED = "def test_{name}():\n    assert False\n"
STILL_RED = "tests/test_two.py::test_two still red, owned by CARD-002"
COUNTING_RED = ("import os\n\n\ndef test_two():\n    with open(os.environ['COUNT_FILE'], 'a') as fh:\n"
                "        fh.write('run\\n')\n    assert False\n")


def head_rows(root):
    return jsonl(Path(root) / "mkway" / "state" / gct.HEAD_FILE)


def new_card(root, title, paths, *, take=False):
    """A card written by the card command, given its Paths and opened by the owner's command; `take` makes the session
    `s1` hold it."""
    number = len(list((Path(root) / "mkway" / "cards").glob("CARD-*"))) + 1
    card_id = f"CARD-{number:03d}"
    assert cli(root, "card", "new", title, session=True)[0] == 0
    set_paths(root, card_id, paths)
    code, _out, err = cli(root, "card", "open", card_id)
    assert code == 0, err
    if take:
        records.append(Path(root) / "mkway" / "state", "s1", "take", card_id)
        seed_record(root, card_id)  # MW-072: this fixture commits its red tests with git, so the card has a record
    return card_id


def commit_file(root, rel, text):
    """A file written, staged and committed with git directly (the test's own step, no gate)."""
    write(root, rel, text)
    git(root, "add", "-f", "--", rel)
    git(root, "commit", "-q", "-m", f"add {rel}")


def project(tmp_path):
    """CARD-001, held by the session, owns `app.py` and `tests/test_one.py`; CARD-002, open, owns `tests/test_two.py`."""
    root = make_project(tmp_path)
    assert new_card(root, "First", "`app.py`, `tests/test_one.py`", take=True) == "CARD-001"
    assert new_card(root, "Second", "`tests/test_two.py`") == "CARD-002"
    return root


def app(n):
    return f"def add(a, b):\n    return a + b + {n} - {n}\n"


def test_an_old_red_of_another_open_card_passes_and_the_allow_line_names_the_owner(tmp_path):
    """E7: a test red at HEAD and red in the staged tree, in the Paths of another open card, does not refuse the
    commit; the gate answers with a warn (`commit-tests-still-red`) whose text reads `<test id> still red, owned by
    <card id>`. Catches: the real-install bug (a card cannot commit while two other cards are mid-way) and an allow
    that hides what is still red."""
    root = project(tmp_path)
    commit_file(root, "tests/test_two.py", RED.format(name="two"))
    stage(root, "app.py", app(1))
    verdict = run_gate(root)
    assert verdict.kind == "warn", (verdict.kind, verdict.message)
    assert verdict.reason_id == "commit-tests-still-red"
    assert STILL_RED in verdict.message
    assert [r["result"] for r in rows(root)] == ["fail"]


def test_the_refusal_names_each_kind_of_red_and_the_way_out(tmp_path):
    """E6: a new red is named as new, not red at HEAD; a red of the committing card is named with its card; a red at HEAD in no
    open card's Paths is named as having no owner, with the words that a card must take it. Each refusal is
    `commit-tests-failed` and keeps the way out of MW-005. Catches: one undifferentiated list of red tests."""
    root = project(tmp_path)
    stage(root, "app.py", app(1))
    stage(root, "tests/test_new.py", RED.format(name="new"))
    verdict = run_gate(root)
    assert verdict.kind == "refuse" and verdict.reason_id == "commit-tests-failed"
    assert "tests/test_new.py::test_new" in verdict.message and "new red" in verdict.message
    assert "not red at HEAD" in verdict.message
    assert "red-first" in verdict.message and "fix" in verdict.message.lower()
    git(root, "reset", "-q")
    (root / "tests" / "test_new.py").unlink()
    commit_file(root, "tests/test_one.py", RED.format(name="one"))
    commit_file(root, "tests/test_orphan.py", RED.format(name="orphan"))
    commit_file(root, "tests/test_two.py", RED.format(name="two"))
    stage(root, "app.py", app(2))
    verdict = run_gate(root)
    assert verdict.kind == "refuse" and verdict.reason_id == "commit-tests-failed"
    text = verdict.message
    assert "tests/test_one.py::test_one" in text and "CARD-001" in text
    assert "tests/test_orphan.py::test_orphan" not in text and "a card must take it" not in text  # MW108-D1: an old red no card owns does not block
    assert "red-first" in text
    commit_file(root, "tests/test_one.py", "def test_one():\n    assert True\n")
    stage(root, "app.py", app(3))
    verdict = run_gate(root)  # MW108-D1: the orphan is shown in the allow line, with no owner
    assert verdict.kind == "warn" and verdict.reason_id == "commit-tests-still-red"
    assert "old red: tests/test_orphan.py::test_orphan, owner none" in verdict.message


def test_only_an_open_card_owns_a_red_test(tmp_path):
    """E8 (MW108-D1): a card that is `waiting` owns nothing; the red it holds at HEAD is shown as an orphan, «owner none»,
    and does not block, until the owner opens the card again and the line names the card. Catches: a closed or waiting
    card whose red tests are shown under a card that does not own them."""
    root = project(tmp_path)
    commit_file(root, "tests/test_two.py", RED.format(name="two"))
    assert cli(root, "card", "set", "CARD-002", "waiting")[0] == 0
    stage(root, "app.py", app(1))
    verdict = run_gate(root)
    assert verdict.kind == "warn" and "old red: tests/test_two.py::test_two, owner none" in verdict.message
    assert cli(root, "card", "open", "CARD-002")[0] == 0
    stage(root, "app.py", app(2))
    verdict = run_gate(root)
    assert verdict.kind == "warn" and STILL_RED in verdict.message


def test_a_red_first_commit_runs_nothing_even_at_head(tmp_path):
    """E9, changed by MW-072 (ruling R177): the commit of tests alone is no longer run-free. The staged suite runs once
    (the red proof), the new red test is the red the commit must show and does not block, and the old red of another open
    card is still told from new red by HEAD's run, so the allow line names its owner.
    Catches: a red-first commit that blocks on its own new red test, or on the old red of another card."""
    root = project(tmp_path)
    commit_file(root, "tests/test_two.py", RED.format(name="two"))
    stage(root, "tests/test_new.py", RED.format(name="new"))
    verdict = run_gate(root)
    assert verdict.kind == "warn" and STILL_RED in verdict.message
    assert len(rows(root)) == 1 and len(head_rows(root)) == 1


def _counted(tmp_path, monkeypatch):
    count = tmp_path / "count.txt"
    monkeypatch.setenv("COUNT_FILE", str(count))
    root = project(tmp_path)
    set_profile(root, test_env=["COUNT_FILE"])
    commit_file(root, "tests/test_two.py", COUNTING_RED)
    return root, count


def runs(count):
    return len(count.read_text(encoding="utf-8").splitlines()) if count.is_file() else 0


def test_head_results_are_cached_by_the_tree_of_head(tmp_path, monkeypatch):
    """E10: the first commit with a red staged tree runs the suite twice (the staged tree, HEAD's tree) and keeps HEAD's
    result in the root state under HEAD's tree; a second commit on the same HEAD runs the staged tree only. Catches: a
    HEAD run for every attempt, the cost the rule must not add."""
    root, count = _counted(tmp_path, monkeypatch)
    stage(root, "app.py", app(1))
    assert run_gate(root).kind == "warn"
    assert runs(count) == 2
    (row,) = head_rows(root)
    assert row["result"] == "fail" and row["failed_ids"] == ["tests/test_two.py::test_two"]
    assert row["tree"] == gct.tree_keys(root, "HEAD")[-1]
    stage(root, "app.py", app(2))
    assert run_gate(root).kind == "warn"
    assert runs(count) == 3, "the second attempt must not run HEAD again"
    assert len(head_rows(root)) == 1 and len(rows(root)) == 2


def test_the_head_cache_is_ignored_when_the_tests_command_or_the_profile_changes(tmp_path, monkeypatch):
    """E11: a changed `tests.command` or a changed profile makes the cached HEAD result stale: HEAD runs again and a
    fresh row is kept. Catches: a HEAD verdict that outlives the command or the environment it was made under."""
    root, count = _counted(tmp_path, monkeypatch)
    stage(root, "app.py", app(1))
    assert run_gate(root).kind == "warn"
    assert runs(count) == 2
    set_profile(root, tests={"command": "python -m pytest -q tests --tb=short"})
    stage(root, "app.py", app(2))
    assert run_gate(root).kind == "warn"
    assert runs(count) == 4 and len(head_rows(root)) == 2
    set_profile(root, paths={"docs": ["notes/**"]})
    stage(root, "app.py", app(3))
    assert run_gate(root).kind == "warn"
    assert runs(count) == 6 and len(head_rows(root)) == 3
    stage(root, "app.py", app(4))
    assert run_gate(root).kind == "warn"
    assert runs(count) == 7 and len(head_rows(root)) == 3


def test_a_repository_with_no_head_treats_every_red_as_new(tmp_path):
    """E12: with no HEAD there is no old red: a red staged test refuses as new and no HEAD run is made. Catches: a crash
    on the first commit of a repository, or a red that slips through because HEAD is empty."""
    root = make_project(tmp_path, commit=False)
    stage(root, "tests/test_bad.py", RED.format(name="bad"))
    verdict = run_gate(root)
    assert verdict.kind == "refuse" and verdict.reason_id == "commit-tests-failed"
    assert "tests/test_bad.py::test_bad" in verdict.message and "new red" in verdict.message
    assert head_rows(root) == []
