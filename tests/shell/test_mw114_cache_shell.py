"""Card MW-114 (fix list of the merge reader): a row the gate kept for a tree of HEAD (the listing of the ids HEAD collects, a
failing run with its failed ids) was written by the reader of its day; a row of an older reader holds ids cut at the first
space, so it must not be reused by the reader that reads them whole: a case that is green at HEAD would look absent there and
a new red would be let through. Real small git repository for the scenario (setup copied from `tests/test_mw062_shell.py` and
`tests/test_mw056_head.py`, helpers of `tests/_red_project.py`); a state folder in tmp_path for the cache rule. Synthetic
names only."""
import json
from pathlib import Path

from _commit_project import git, make_project, reason, run_gate, stage, write
from _engine import cli, jsonl
from _red_project import edit_card, seed_record
import gate_commit_tests as gct  # after _red_project, which puts the engine folder on the path
import records

ITEM = "items/a_b.txt"
COMMIT = f"git commit -m x -- {ITEM}"
TEST_B = ("from pathlib import Path\n\nimport pytest\n\n"
          "ITEMS = Path(__file__).resolve().parent.parent / 'items'\n\n\n"
          "CASES = ['a b']\n\n\n"
          "def test_item(case):\n"
          "    assert (ITEMS / (case.replace(' ', '_') + '.txt')).read_text(encoding='utf-8').strip() == 'done'\n\n\n"
          "test_item = pytest.mark.parametrize('case', CASES)(test_item)\n")
WHOLE = ["tests/test_b.py::test_item[a b]", "tests/test_ok.py::test_add"]
ROW = {"tree": "t", "command": "c", "profile": "p", "result": "fail", "failed_ids": ["tests/x.py::t[a b]"]}


def open_card(root, number, title, paths, take=False):
    """A card written by the card command, given its Paths and opened by the owner's command; `take` makes session s1 hold it."""
    card_id = f"CARD-{number:03d}"
    assert cli(root, "card", "new", title, session=True)[0] == 0
    edit_card(next((Path(root) / "mkway" / "cards").glob(f"{card_id}-*")) / "CARD.md", paths=paths)
    assert cli(root, "card", "open", card_id)[0] == 0
    if take:
        records.append(Path(root) / "mkway" / "state", "s1", "take", card_id)
        seed_record(root, card_id)  # the fixture commits with git directly, so the card has a record
    return card_id


def project(tmp_path):
    """CARD-001 (held) owns `items/`; CARD-002 (open) owns `tests/test_b.py`, committed with its case green at HEAD."""
    root = make_project(tmp_path)
    open_card(root, 1, "Creator", "`items/`", take=True)
    open_card(root, 2, "Checker", "`tests/test_b.py`")
    write(root, "tests/test_b.py", TEST_B)
    write(root, ITEM, "done\n")
    git(root, "add", "-f", "--", "tests/test_b.py", ITEM)
    git(root, "commit", "-q", "-m", "tests and item")
    return root


def collect_path(root):
    return Path(root) / "mkway" / "state" / gct.COLLECT_FILE


def make_rows_old(root):
    """The kept listings as the reader before MW-114 wrote them: each id cut at its first space, no reader version."""
    old = []
    for row in jsonl(collect_path(root)):
        row.pop("reader", None)
        row["collected"] = [i.split(" ")[0] for i in row["collected"]]
        old.append(json.dumps(row) + "\n")
    collect_path(root).write_text("".join(old), encoding="utf-8")


def test_a_kept_listing_of_head_made_by_an_older_reader_is_not_reused(tmp_path):
    """Catches: a kept listing with ids cut at a space reused, so a case green at HEAD looks absent and a new red is allowed."""
    root = project(tmp_path)
    stage(root, ITEM, "todo\n")
    assert reason(run_gate(root, COMMIT)) == "commit-tests-failed"
    make_rows_old(root)
    verdict = run_gate(root, COMMIT)
    assert reason(verdict) == "commit-tests-failed"
    assert "tests/test_b.py::test_item[a b]" in verdict.message
    last = jsonl(collect_path(root))[-1]
    assert last["collected"] == WHOLE
    assert last["reader"] == 2


def test_a_kept_fail_row_without_the_reader_version_is_not_reused(tmp_path):
    """Catches: a kept failing run whose failed ids an older reader cut, reused as the answer for its tree."""
    (tmp_path / gct.STATE_FILE).write_text(json.dumps(ROW) + "\n", encoding="utf-8")
    assert gct._cached(tmp_path, "t", "c", 600, "p") is None


def test_a_kept_fail_row_with_the_current_reader_version_is_reused(tmp_path):
    """Checks: a failing run written by the current reader is still the answer for its tree (nearest allow of the row above)."""
    row = dict(ROW, reader=gct.READER)
    (tmp_path / gct.STATE_FILE).write_text(json.dumps(row) + "\n", encoding="utf-8")
    assert gct._cached(tmp_path, "t", "c", 600, "p") == row
