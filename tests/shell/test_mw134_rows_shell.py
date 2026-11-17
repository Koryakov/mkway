"""Card MW-134 (ruling R355 2), layer shell: a red row and a retirement row of the same git tree and the same card are two rows, in the
live write and in the migration, so the engine never loses a retirement row as a duplicate. Synthetic names only."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/: the shared helpers
import _mw134 as w  # noqa: E402
import _red_project as rp  # noqa: E402
import shared_records  # noqa: E402

KEY = ("tree", "card", "retired")  # the key the gate writes with (gate_commit_tests._write_record, _write_retirements)
TREE = "a" * 40
RED = {"time": "2026-11-17T10:00:00.000+00:00", "session": "s1", "card": w.CARD, "tree": TREE, "git_tree": TREE, "red": [w.NEW],
       "pins": [], "checks": [], "missing": {}, "would_refuse": [], "mode": "trip"}
RETIRED = {"time": "2026-11-17T10:00:01.000+00:00", "session": "s1", "card": w.CARD, "tree": TREE, "git_tree": TREE,
           "retired": w.OLD, "right": w.NEW, "decision": "D-1", "by": w.LEAD}


@pytest.fixture(autouse=True)
def _red_templates(template_copy):
    with rp.use_template_copy(template_copy):
        yield


def _root(tmp_path):
    return rp.red_project(tmp_path, name="main", state={"dir": "mkway/state", "shared_dir": str(tmp_path / "shared")})


def _rows(path) -> list:
    path = Path(path)
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()] if path.is_file() else []


def test_a_red_row_and_a_retirement_row_of_the_same_tree_and_card_are_both_kept_by_the_live_write(tmp_path):
    """Checks: append_row with the key the gate writes with keeps the red row and then the retirement row of one tree and card, and still drops a repeat of either."""
    root = _root(tmp_path)
    profile = w.profile_of(root)
    assert shared_records.append_row(root, profile, "red_proof.jsonl", RED, key=KEY) is True
    assert shared_records.append_row(root, profile, "red_proof.jsonl", RETIRED, key=KEY) is True
    assert shared_records.append_row(root, profile, "red_proof.jsonl", RETIRED, key=KEY) is False
    assert _rows(tmp_path / "shared" / "red_proof.jsonl") == [RED, RETIRED]


def test_the_migration_copies_a_red_row_and_a_retirement_row_of_the_same_tree_and_card(tmp_path):
    """Catches: a migration key that reads the retirement row as a duplicate of the red row of its tree and card and turns it away."""
    root = _root(tmp_path)
    state = Path(root) / "mkway" / "state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "red_proof.jsonl").write_text(json.dumps(RED) + "\n" + json.dumps(RETIRED) + "\n", encoding="utf-8")
    report = shared_records.migrate(root, w.profile_of(root), write=True)
    (counts,) = report["files"]
    assert (counts["copied"], counts["turnedAway"]) == (2, 0)
    assert _rows(tmp_path / "shared" / "red_proof.jsonl") == [RED, RETIRED]
