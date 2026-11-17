"""Card MW-062, the real shape on a real small repository: card CARD-002's red-first test file is committed and
parametrizes over the files of a folder that card CARD-001 creates. At HEAD those cases do not exist; CARD-001's commit
makes them appear, red, because CARD-002's code is not in. The gate runs the real suite on the staged tree and on HEAD's
tree (a real git repository, a real pytest run, about a second per run). Synthetic names only."""
from _commit_project import git, make_project, run_gate, rows, set_profile, stage, write
from _engine import cli
from test_mw056_head import commit_file, head_rows, new_card

COMMIT = "git commit -m x -- items/a.txt items/b.txt"
TEST_B = (
    "from pathlib import Path\n\nimport pytest\n\n"
    "ITEMS = Path(__file__).resolve().parent.parent / 'items'\n"
    "FOUND = sorted(p.name for p in ITEMS.glob('*.txt'))\n\n\n"
    "def test_item(entry):\n"
    "    assert (ITEMS / entry).read_text(encoding='utf-8').strip() == 'done'\n\n\n"
    "test_item = pytest.mark.parametrize('entry', FOUND)(test_item)\n")
TEST_B_STRICT = TEST_B.replace("sorted(p.name for p in ITEMS.glob('*.txt'))",
                               "sorted(n for n in __import__('os').listdir(ITEMS) if n.endswith('.txt'))")


def project(tmp_path, *, a_paths="`items/`", b_paths="`tests/test_b.py`", test_b=TEST_B):
    """CARD-001 (held by the session) creates `items/`; CARD-002 (open) owns `tests/test_b.py`, committed at HEAD."""
    root = make_project(tmp_path)
    assert new_card(root, "Creator", a_paths, take=True) == "CARD-001"
    assert new_card(root, "Checker", b_paths) == "CARD-002"
    commit_file(root, "tests/test_b.py", test_b)
    return root


def make_items(root):
    stage(root, "items/a.txt", "todo\n")
    stage(root, "items/b.txt", "todo\n")


def test_cases_absent_at_head_that_another_open_card_owns_pass_and_are_listed_with_their_count(tmp_path):
    """Checks: the commit of the creating card is allowed with a warn, its line counts the 2 cases absent at HEAD owned by CARD-002, and the staged tree is run once (E8)."""
    root = project(tmp_path)
    make_items(root)
    verdict = run_gate(root, COMMIT)
    assert verdict.kind == "warn", (verdict.kind, verdict.message)
    assert verdict.reason_id == "commit-tests-still-red"
    assert "2 cases absent at HEAD, owned by CARD-002" in verdict.message
    assert [r["result"] for r in rows(root)] == ["fail"]
    assert sorted(rows(root)[0]["failed_ids"]) == ["tests/test_b.py::test_item[a.txt]",
                                                   "tests/test_b.py::test_item[b.txt]"]


def test_a_file_that_failed_at_collection_at_head_makes_its_cases_red_there_owned_by_its_card(tmp_path):
    """Checks: a file that fails at collection at HEAD makes the cases that appear with the folder still red and owned by the card, allowed (E9, MW-069, R176)."""
    root = project(tmp_path, test_b=TEST_B_STRICT)
    make_items(root)
    verdict = run_gate(root, COMMIT)
    assert verdict.kind == "warn", (verdict.kind, verdict.message)
    assert "tests/test_b.py::test_item[a.txt] still red, owned by CARD-002" in verdict.message
    assert "absent at HEAD" not in verdict.message


def test_the_listing_of_head_writes_ids_the_way_the_failure_list_does_when_the_rootdir_is_above(tmp_path):
    """Catches: every id of the listing carrying a folder prefix the failing id does not, which makes every red case look absent at HEAD and lets a real new red through (E13)."""
    root = project(tmp_path)
    set_profile(root, tests={"command": "python -m pytest -q tests --rootdir=.."})
    write(root, "items/a.txt", "done\n")
    git(root, "add", "--", "items/a.txt")
    git(root, "commit", "-q", "-m", "item a done")
    stage(root, "items/a.txt", "todo\n")
    stage(root, "items/b.txt", "todo\n")
    verdict = run_gate(root, COMMIT)
    assert verdict.kind == "refuse"
    assert verdict.reason_id == "commit-tests-failed", (verdict.kind, verdict.message)
    assert "tests/test_b.py::test_item[a.txt]" in verdict.message
    assert "new red" in verdict.message
    assert "test_item[b.txt]" not in verdict.message.split("not blocking")[0]  # b.txt is absent at HEAD: not a new red
    assert "absent at HEAD and owned by another open card, not blocking: 1" in verdict.message


def test_a_collection_error_at_head_does_not_hide_the_red_tests_of_other_files_there(tmp_path):
    """Checks: a collection error at HEAD does not hide the red tests of other files there: each id is recorded and stays still red, owned by the card (E14)."""
    root = project(tmp_path, b_paths="`tests/test_b.py`, `tests/test_r.py`", test_b=TEST_B_STRICT)
    commit_file(root, "tests/test_r.py", "def test_r():\n    assert False\n")
    make_items(root)
    verdict = run_gate(root, COMMIT)
    assert verdict.kind == "warn", (verdict.kind, verdict.message)
    assert "tests/test_r.py::test_r still red, owned by CARD-002" in verdict.message
    assert "tests/test_b.py::test_item[b.txt] still red, owned by CARD-002" in verdict.message  # MW-069: red at HEAD, not absent
    (head,) = head_rows(root)
    assert "tests/test_r.py::test_r" in head["failed_ids"]
    assert "tests/test_b.py" in head["failed_ids"]


def test_the_same_cases_in_the_paths_of_the_committing_card_are_refused(tmp_path):
    """Catches: a card that passes its own red because HEAD never had the case, with the test file in its own Paths (E10, rule b)."""
    root = project(tmp_path, a_paths="`items/`, `tests/test_b.py`", b_paths="`other/`")
    make_items(root)
    verdict = run_gate(root, COMMIT)
    assert verdict.kind == "refuse"
    assert verdict.reason_id == "commit-tests-failed"
    assert "tests/test_b.py::test_item[a.txt]" in verdict.message
    assert "CARD-001" in verdict.message


def test_no_open_owner_and_a_case_that_was_green_at_head_stay_refused(tmp_path):
    """Catches: an absent-at-HEAD rule that opens the door for every red in another card's file, with the owner waiting or the case green at HEAD (E11)."""
    root = project(tmp_path)
    assert cli(root, "card", "set", "CARD-002", "waiting")[0] == 0
    make_items(root)
    verdict = run_gate(root, COMMIT)
    assert verdict.kind == "refuse"
    assert verdict.reason_id == "commit-tests-failed"
    assert "new red" in verdict.message
    assert "tests/test_b.py::test_item[a.txt]" in verdict.message
    git(root, "reset", "-q")
    assert cli(root, "card", "open", "CARD-002")[0] == 0
    write(root, "items/a.txt", "done\n")
    write(root, "items/b.txt", "done\n")
    git(root, "add", "--", "items/a.txt", "items/b.txt")
    git(root, "commit", "-q", "-m", "items done")
    stage(root, "items/a.txt", "todo\n")
    verdict = run_gate(root, "git commit -m x -- items/a.txt")
    assert verdict.kind == "refuse"
    assert verdict.reason_id == "commit-tests-failed"
    assert "new red" in verdict.message
    assert "tests/test_b.py::test_item[a.txt]" in verdict.message
