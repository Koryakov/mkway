"""Card MW-112 part (iii) (record R3, rulings R270a and R271c), layer shell: `mkway board` and the start line read their facts
from real files of a synthetic task root (the state folder, the shared inbox, a real git repository for the uncommitted files).
Files only under tmp_path; synthetic ids."""
import datetime
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/: the shared helpers and `_engine`
from _engine import cli, task_root  # noqa: E402
import board  # noqa: E402
import leads  # noqa: E402
import profiles  # noqa: E402
import startline  # noqa: E402
import dispatch  # noqa: E402


def _profile(root):
    return json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))


def _state(root):
    return root / "mkway" / "state"


def _rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def _put(root, session, number, hours_old):
    moment = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours_old)
    leads.write_row(profiles.shared_state_dir(root, _profile(root)),
                    {"id": f"m-{number}", "from": "lead-x", "to": session, "kind": "notice", "reply_to": None,
                     "ts": moment.isoformat(timespec="milliseconds"), "ack_ts": None, "body": f"item {number}"})


def _board(root):
    code, out, err = cli(root, "board")
    assert (code, err) == (0, "")
    return out.splitlines()


def test_the_board_lists_every_unacked_item_with_its_age(tmp_path):
    """Catches: R270a: an unacked item cut off after the tenth, or listed with no age while it waits to be acked."""
    root = task_root(tmp_path)
    for number in range(12):
        _put(root, "b-1", number, hours_old=3)
    shown = [x for x in _board(root) if x.startswith("    unacked m-")]
    assert len(shown) == 12 and all("age 3 h" in x for x in shown)


def test_an_acked_item_leaves_the_board(tmp_path):
    """Checks: the nearest allow of the test above: an item is listed until it is acked, and not after."""
    root = task_root(tmp_path)
    _put(root, "b-1", 1, hours_old=1)
    assert len([x for x in _board(root) if x.startswith("    unacked m-")]) == 1
    rows = leads.inbox_rows(profiles.shared_state_dir(root, _profile(root)), "b-1")
    leads.ack(profiles.shared_state_dir(root, _profile(root)), "b-1", rows[0]["id"])
    assert [x for x in _board(root) if x.startswith("    unacked m-")] == []


def test_the_board_shows_the_old_red_of_the_last_commit_with_its_owner(tmp_path):
    """Catches: R3: the old red of the last commit record not on the board, or shown without the card that owns it."""
    root = task_root(tmp_path)
    _rows(_state(root) / "commit_tests.jsonl", [{"tree": "t1", "old_red": [{"test": "tests/a.py::test_one", "card": "CARD-001"}]}])
    assert "  old red: tests/a.py::test_one (owner card CARD-001)" in _board(root)


def test_the_board_names_a_failed_agent_record_until_a_row_is_written_again(tmp_path):
    """Catches: R271c: the failed agent record only said once, on SubagentStop, and never again on the board."""
    root = task_root(tmp_path)
    _rows(_state(root) / "refusals.jsonl", [{"reason_id": "agent-record-failed", "kind": "warn",
                                              "time": "2031-05-06T10:00:00.000+00:00"}])
    assert any(x.startswith("  agent record failed at 2031-05-06T10:00:00.000+00:00") for x in _board(root))
    _rows(_state(root) / "agents.jsonl", [{"kind": "end", "ended": "2031-05-06T10:05:00.000+00:00"}])
    assert not any("agent record failed" in x for x in _board(root))


def test_the_start_line_names_a_failed_agent_record(tmp_path):
    """Catches: R271c: the next start line does not carry the failed agent record."""
    root = task_root(tmp_path)
    _rows(_state(root) / "refusals.jsonl", [{"reason_id": "agent-record-failed", "kind": "warn",
                                              "time": "2031-05-06T10:00:00.000+00:00"}])
    block = startline.render(root, root / "mkway" / "profile.json", _profile(root), [],
                             dispatch.load_manifest(dispatch.ENGINE_DIR), {"CLAUDECODE": "1"}, session="s1")
    assert "agent record failed at 2031-05-06T10:00:00.000+00:00" in block


def test_the_start_line_counts_the_unreadable_writes_that_named_the_state_folder(tmp_path):
    """Catches: R279d: unreadable shell writes naming the state folder that passed are not on the start line."""
    root = task_root(tmp_path)
    _rows(_state(root) / "refusals.jsonl", [{"reason_id": "write-target-unread", "kind": "log",
                                              "target": "run x > mkway/state/commit_tests.jsonl"}])
    block = startline.render(root, root / "mkway" / "profile.json", _profile(root), [],
                             dispatch.load_manifest(dispatch.ENGINE_DIR), {"CLAUDECODE": "1"}, session="s1")
    assert "unreadable writes that passed and named the state folder: 1" in block


def test_the_start_line_has_no_unread_line_when_the_count_is_zero(tmp_path):
    """Checks: the nearest allow of the test above: a count of zero adds no line."""
    root = task_root(tmp_path)
    block = startline.render(root, root / "mkway" / "profile.json", _profile(root), [],
                             dispatch.load_manifest(dispatch.ENGINE_DIR), {"CLAUDECODE": "1"}, session="s1")
    assert "unreadable writes" not in block


def test_git_status_gives_the_uncommitted_files(tmp_path):
    """Catches: the uncommitted files read from the wrong place: a committed file listed, or an untracked file missed."""
    root = task_root(tmp_path, vcs="git")
    for args in (("init", "-q"), ("config", "user.email", "tester"), ("config", "user.name", "t")):
        subprocess.run(["git", *args], cwd=root, check=True)
    (root / "kept.txt").write_text("a", encoding="utf-8")
    subprocess.run(["git", "add", "kept.txt"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "first"], cwd=root, check=True)
    (root / "kept.txt").write_text("b", encoding="utf-8")
    (root / "new.txt").write_text("c", encoding="utf-8")
    assert [p for p in board.uncommitted_files(root) if p in ("kept.txt", "new.txt")] == ["kept.txt", "new.txt"]
