"""Card MW-017, part 6, rows E22 to E26 (the shared state of the order's addition 1): `profiles.shared_state_dir`, the
files that cross worktrees (`leads.json`, `inbox/<session id>.jsonl`, `sessions.jsonl`), and `mkway sessions` with the
root folder. A scratch repository with a linked worktree, and a folder with no git, under the pytest temp folder."""
import json
import re
from pathlib import Path

import pytest

from _engine import cli, gate_call, task_root
from _mw017 import inbox, session_run
from test_install import git
import dispatch
import gate_lead
import leads
import profiles
import runner


pytestmark = pytest.mark.real_shared_state  # scratch repositories under the temp folder; see conftest.py


def _profile(root):
    return json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))


def _pair(tmp_path, *, sub=""):
    """A main work tree and a linked one, both holding the committed profile; returns (main root, linked root).
    With `sub` the task root is that folder below the top of the work tree."""
    top = tmp_path / "main"
    top.mkdir(parents=True)
    git(top, "init", "-q")
    root = top / sub if sub else top
    (root / "mkway").mkdir(parents=True, exist_ok=True)
    shared = str((root / "mkway" / "state").resolve())  # MW-026: the sharing is opt-in, the owner names the folder
    task = task_root(tmp_path, name="src", state={"dir": "mkway/state", "shared_dir": shared})
    (root / "mkway" / "profile.json").write_bytes((task / "mkway" / "profile.json").read_bytes())
    git(top, "add", "-A")
    git(top, "commit", "-q", "-m", "profile")
    linked = tmp_path / "linked"
    git(top, "worktree", "add", "-q", str(linked), "-b", "wt")
    return root, (linked / sub if sub else linked)


def test_a_folder_with_no_git_and_a_main_work_tree_share_nothing_else(tmp_path, monkeypatch):
    """E22: with no git, and in the main work tree, the shared dir is the state dir itself. The temp folder lies in
    this repository, so git is told not to look above it (`GIT_CEILING_DIRECTORIES`)."""
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    plain = task_root(tmp_path / "plain")
    assert profiles.shared_state_dir(plain, _profile(plain)) == profiles.state_dir(plain, _profile(plain))
    main, _linked = _pair(tmp_path / "pair")
    assert profiles.shared_state_dir(main, _profile(main)) == profiles.state_dir(main, _profile(main))


def test_a_linked_work_tree_shares_the_main_work_trees_state_dir(tmp_path):
    """E22: in a linked work tree the shared dir is `<main work tree root>/<state.dir>`; also when the task root lies
    below the top of the work tree. Catches: leads that exist in one work tree only."""
    main, linked = _pair(tmp_path)
    shared = profiles.shared_state_dir(linked, _profile(linked))
    assert shared.resolve() == profiles.state_dir(main, _profile(main)).resolve()
    assert shared.resolve() != profiles.state_dir(linked, _profile(linked)).resolve()
    main2, linked2 = _pair(tmp_path / "deep", sub="tools/task")
    assert profiles.shared_state_dir(linked2, _profile(linked2)).resolve() == \
        profiles.state_dir(main2, _profile(main2)).resolve()


def test_the_lookup_never_asks_git(tmp_path, monkeypatch):
    """E22 (changed by MW-026): the shared dir is the key `state.shared_dir` or `state_dir`; the lookup starts no git,
    so there is nothing to resolve once or to fail."""
    main, linked = _pair(tmp_path)

    def forbidden(*args, **kwargs):
        raise AssertionError("the lookup asked git")

    monkeypatch.setattr(runner, "git", forbidden)
    assert profiles.shared_state_dir(linked, _profile(linked)) == Path(_profile(linked)["state"]["shared_dir"])
    assert profiles.shared_state_dir(linked, {"state": {"dir": "mkway/state"}}) == \
        profiles.state_dir(linked, {"state": {"dir": "mkway/state"}})


def test_leads_and_inbox_written_in_a_linked_work_tree_live_in_the_main_state(tmp_path):
    """E23: `lead register` run in the linked work tree writes `leads.json` into the main work tree's state folder and
    nothing into its own; the lead gate of the main work tree sees that lead; a notice goes to
    `inbox/<session id>.jsonl` there; the permit and the records stay per work tree."""
    main, linked = _pair(tmp_path)
    code, _out, err = session_run(linked, "lead-w", "lead", "register")
    assert code == 0, err
    main_state, own_state = main / "mkway" / "state", linked / "mkway" / "state"
    assert json.loads((main_state / "leads.json").read_text(encoding="utf-8"))["leads"][0]["session_id"] == "lead-w"
    assert not (own_state / "leads.json").exists()
    assert (own_state / "records.jsonl").is_file() and not (main_state / "records.jsonl").exists()
    verdict = gate_call(gate_lead.edit, main, tool="Write", tool_input={"file_path": "src/a.py"}, session="lead-w")
    assert verdict.kind == "refuse" and verdict.reason_id == "lead-no-edit"
    leads.append_notice(profiles.shared_state_dir(linked, _profile(linked)), "lead-w", "hello")
    assert [r["body"] for r in inbox(main, "lead-w")] == ["hello"] and inbox(linked, "lead-w") == []


def _payload(session, root, event):
    return json.dumps({"session_id": session, "hook_event_name": event, "cwd": str(root), "prompt": "hi"})


def _env(root):
    return {"CLAUDE_PROJECT_DIR": str(root), "CLAUDECODE": "1"}


def _sessions_rows(main):
    path = main / "mkway" / "state" / "sessions.jsonl"
    if not path.is_file():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def test_session_start_appends_a_row_to_the_shared_sessions_file(tmp_path):
    """E24: the SessionStart hook appends `{session_id, root, ts}` to `sessions.jsonl` of the shared state folder; the
    root is the folder the session runs in (the linked work tree here)."""
    main, linked = _pair(tmp_path)
    dispatch.run("SessionStart", "start", _payload("s-1", linked, "SessionStart"), env=_env(linked))
    (row,) = _sessions_rows(main)
    assert list(row) == ["session_id", "root", "ts"] and row["session_id"] == "s-1"
    assert row["root"].replace("\\", "/").rstrip("/").endswith("/linked") and row["ts"]
    assert not (linked / "mkway" / "state" / "sessions.jsonl").exists()


def test_the_prompt_hook_refreshes_last_seen_at_most_once_in_ten_minutes(tmp_path):
    """E24: a prompt right after the start adds no row; a prompt when the session's last row is older than 10 minutes
    adds one; a session with no row yet gets one."""
    import datetime
    main, linked = _pair(tmp_path)
    dispatch.run("SessionStart", "start", _payload("s-1", linked, "SessionStart"), env=_env(linked))
    dispatch.run("UserPromptSubmit", "prompt", _payload("s-1", linked, "UserPromptSubmit"), env=_env(linked))
    assert len(_sessions_rows(main)) == 1
    path = main / "mkway" / "state" / "sessions.jsonl"
    old = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=11)).isoformat(
        timespec="milliseconds")
    path.write_text(json.dumps({"session_id": "s-1", "root": str(linked), "ts": old}) + "\n", encoding="utf-8")
    dispatch.run("UserPromptSubmit", "prompt", _payload("s-1", linked, "UserPromptSubmit"), env=_env(linked))
    rows = _sessions_rows(main)
    assert len(rows) == 2 and rows[-1]["ts"] > old
    dispatch.run("UserPromptSubmit", "prompt", _payload("s-2", linked, "UserPromptSubmit"), env=_env(linked))
    assert [r["session_id"] for r in _sessions_rows(main)] == ["s-1", "s-1", "s-2"]


def test_mkway_sessions_lists_the_shared_file_with_each_root(tmp_path):
    """E25: `mkway sessions` keeps its lines and adds `root <folder>`; a session known only from the shared file is
    listed; one known only from the records reads `root not established`; the last seen is the latest of both."""
    main, linked = _pair(tmp_path)
    shared = main / "mkway" / "state"
    shared.mkdir(parents=True, exist_ok=True)
    (shared / "sessions.jsonl").write_text(
        json.dumps({"session_id": "s-file", "root": "/work/one", "ts": "2026-11-11T08:00:00.000+00:00"}) + "\n" +
        json.dumps({"session_id": "s-file", "root": "/work/one", "ts": "2026-11-11T09:30:00.000+00:00"}) + "\n",
        encoding="utf-8")
    import records
    records.append(linked / "mkway" / "state", "s-rec", "take", "CARD-001")
    code, out, err = cli(linked, "sessions")
    assert code == 0, err
    lines = {ln.split()[0]: ln for ln in out.splitlines() if ln.startswith("s-")}
    assert sorted(lines) == ["s-file", "s-rec"]
    assert "last seen 2026-11-11T09:30" in lines["s-file"] and "root /work/one" in lines["s-file"]
    assert "holds none" in lines["s-file"] and "ordered none" in lines["s-file"]
    assert re.search(r"last seen \d{4}-\d{2}-\d{2}T", lines["s-rec"]) and "root not established" in lines["s-rec"]


def test_lead_add_names_a_session_known_from_the_shared_file(tmp_path):
    """E25: the owner's `lead add <prefix>` and `give` resolve a prefix against the sessions of the shared file too,
    so a session of another work tree can be made a lead."""
    main, linked = _pair(tmp_path)
    shared = main / "mkway" / "state"
    shared.mkdir(parents=True, exist_ok=True)
    (shared / "sessions.jsonl").write_text(
        json.dumps({"session_id": "far-away-1", "root": "/work/two", "ts": "2026-11-11T08:00:00.000+00:00"}) + "\n",
        encoding="utf-8")
    assert cli(linked, "lead", "add", "far")[0] == 0
    assert leads.is_lead(profiles.shared_state_dir(main, _profile(main)), "far-away-1")
