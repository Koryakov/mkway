"""Card MW-022, rows E1 to E10: the lock markers (the hold, every `locks.targets` entry) live in the shared state folder
(`profiles.shared_state_dir`, MW-017), so a hold or a lock typed in any work tree of a repository reaches every session of
it. Scratch repositories with a linked work tree under the pytest temp folder only (the `real_shared_state` mark)."""
import json

import pytest

from _engine import cli, gate_call, task_root
from test_install import git
import gate_lock
import locks
import profiles

pytestmark = pytest.mark.real_shared_state  # scratch repositories under the temp folder; see conftest.py

HOLD = {"name": "hold", "paths": ["**"], "open_by_default": True}
DOCS = {"name": "docs", "paths": ["notes/"]}
GIT_PROFILE_KEYS = {"locks": {"targets": [HOLD, DOCS]}}


def _profile(root):
    return json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))


def _pair(tmp_path, *, targets=(HOLD, DOCS), linked_targets=None):
    """(main root, linked root): a main work tree and a linked one, both holding the committed profile. With
    `linked_targets` the linked work tree's profile has its own `locks.targets` (committed there)."""
    top = tmp_path / "main"
    top.mkdir(parents=True)
    git(top, "init", "-q")
    src = task_root(tmp_path, name="src", locks={"targets": list(targets)})
    (top / "mkway").mkdir()
    (top / "mkway" / "profile.json").write_bytes((src / "mkway" / "profile.json").read_bytes())
    git(top, "add", "-A")
    git(top, "commit", "-q", "-m", "profile")
    linked = tmp_path / "linked"
    git(top, "worktree", "add", "-q", str(linked), "-b", "wt")
    if linked_targets is not None:
        prof = _profile(linked)
        prof["locks"] = {"targets": list(linked_targets)}
        (linked / "mkway" / "profile.json").write_text(json.dumps(prof, indent=2), encoding="utf-8")
    return top, linked


@pytest.fixture(autouse=True)
def _fresh_cache():
    profiles._SHARED.clear()
    yield
    profiles._SHARED.clear()


def _edit(root, path):
    return gate_call(gate_lock.check, root, tool="Edit", tool_input={"file_path": path}, session="s1")


def _shell(root, command):
    return gate_call(gate_lock.check, root, tool="Bash", tool_input={"command": command}, session="s1")


def _reason(v):
    return v.reason_id if v.kind == "refuse" else "allow"


def _shared(main):
    return main / "mkway" / "state" / "locks"


def test_a_hold_set_in_the_main_folder_stops_a_write_in_a_linked_work_tree(tmp_path):
    """E1, E2: `mkway hold` in the main work tree writes the marker into the shared folder; the edit gate and the shell
    gate of the linked work tree refuse a write; `mkway go` there lifts it. Catches: a marker that stays per work tree."""
    main, linked = _pair(tmp_path)
    assert _reason(_edit(linked, "src/a.py")) == "allow"
    assert cli(main, "hold")[0] == 0
    assert (_shared(main) / "hold.json").is_file()
    assert not (linked / "mkway" / "locks" / "hold.json").exists()
    assert _reason(_edit(linked, "src/a.py")) == "lock-closed-edit"
    assert _reason(_shell(linked, "echo x > src/a.py")) == "lock-closed-shell"
    assert _reason(_edit(main, "src/a.py")) == "lock-closed-edit"
    assert cli(linked, "go")[0] == 0
    assert not (_shared(main) / "hold.json").exists()
    assert _reason(_edit(main, "src/a.py")) == "allow" and _reason(_edit(linked, "src/a.py")) == "allow"


def test_a_hold_set_in_a_linked_work_tree_stops_the_main_folder(tmp_path):
    """E1, E2: `mkway hold` typed in the linked work tree writes into the main work tree's state folder and nothing
    into its own; the main folder's gates refuse a write. Catches: a hold that reaches only where it was typed."""
    main, linked = _pair(tmp_path)
    code, out, _err = cli(linked, "hold")
    assert code == 0
    assert (_shared(main) / "hold.json").is_file()
    assert not (linked / "mkway" / "state" / "locks").exists() and not (linked / "mkway" / "locks" / "hold.json").exists()
    assert _reason(_edit(main, "src/a.py")) == "lock-closed-edit"
    assert _reason(_shell(main, "echo x > src/a.py")) == "lock-closed-shell"
    assert _reason(_edit(linked, "src/a.py")) == "lock-closed-edit"


def test_a_lock_target_opened_in_one_work_tree_is_open_in_the_other(tmp_path):
    """E3: a `locks.targets` entry (not the hold) opens and closes through the shared folder too: `lock open docs` in
    the main work tree lets a linked work tree write `notes/x.md`; `lock close docs` shuts it again."""
    main, linked = _pair(tmp_path)
    assert _reason(_edit(linked, "notes/x.md")) == "lock-closed-edit"
    assert cli(main, "lock", "open", "docs")[0] == 0
    assert (_shared(main) / "docs.json").is_file()
    assert _reason(_edit(linked, "notes/x.md")) == "allow"
    assert cli(linked, "lock", "close", "docs")[0] == 0
    assert _reason(_edit(main, "notes/x.md")) == "lock-closed-edit"
    assert _reason(_edit(linked, "notes/x.md")) == "lock-closed-edit"


def test_a_repository_with_no_linked_work_tree_behaves_as_before(tmp_path, monkeypatch):
    """E4: with no git (or the main work tree alone) the shared folder is the state folder: the marker is
    `<state>/locks/<name>.json`, the gates read it, `go` removes it, and `mkway/locks` stays empty."""
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    root = task_root(tmp_path, name="plain", locks={"targets": [HOLD, DOCS]})
    assert cli(root, "hold")[0] == 0
    assert (root / "mkway" / "state" / "locks" / "hold.json").is_file()
    assert not list((root / "mkway" / "locks").iterdir())
    assert _reason(_edit(root, "src/a.py")) == "lock-closed-edit"
    assert cli(root, "go")[0] == 0
    assert _reason(_edit(root, "src/a.py")) == "allow"
    assert cli(root, "lock", "open", "docs")[0] == 0
    assert _reason(_edit(root, "notes/x.md")) == "allow"


def test_a_work_tree_whose_profile_has_no_target_of_that_name_ignores_the_marker(tmp_path):
    """E5: the hold marker in the shared folder closes nothing in a work tree whose profile has no `hold` target.
    Catches: a marker read by name for a target the profile does not know."""
    main, linked = _pair(tmp_path, linked_targets=[DOCS])
    assert cli(main, "hold")[0] == 0
    assert _reason(_edit(main, "src/a.py")) == "lock-closed-edit"
    assert _reason(_edit(linked, "src/a.py")) == "allow"


def test_a_stale_local_marker_still_closes_and_is_reported(tmp_path):
    """E6, E7: an older per-work-tree marker `<bundle>/locks/hold.json` still closes the gates for one version (the
    fallback); `mkway lock list` and `locks.local_markers` name it, and `mkway check` carries the warning
    `lock-marker-local`. Catches: a hold dropped silently on the upgrade."""
    main, linked = _pair(tmp_path)
    (linked / "mkway" / "locks").mkdir(parents=True, exist_ok=True)
    (linked / "mkway" / "locks" / "hold.json").write_text('{"name": "hold", "state": "closed"}', encoding="utf-8")
    assert _reason(_edit(linked, "src/a.py")) == "lock-closed-edit"
    assert _reason(_edit(main, "src/a.py")) == "allow"  # the stale marker is per work tree
    assert [name for name, _path in locks.local_markers(linked, _profile(linked))] == ["hold"]
    assert locks.local_markers(main, _profile(main)) == []
    code, out, _err = cli(linked, "lock", "list")
    assert code == 0 and "lock-marker-local" in out and "hold" in out
    assert any("lock-marker-local" in line for line in locks.marker_warnings(linked, _profile(linked)))


def test_closed_wins_between_the_local_and_the_shared_marker(tmp_path):
    """E6: for a `locks.targets` entry the shared folder says open while an older local marker says closed (or is
    expired): the gate closes. The shared open alone opens; a local open alone still opens (the fallback)."""
    main, linked = _pair(tmp_path)
    assert cli(main, "lock", "open", "docs")[0] == 0
    assert _reason(_edit(linked, "notes/x.md")) == "allow"
    (linked / "mkway" / "locks").mkdir(parents=True, exist_ok=True)
    local = linked / "mkway" / "locks" / "docs.json"
    local.write_text('{"name": "docs", "state": "closed"}', encoding="utf-8")
    assert _reason(_edit(linked, "notes/x.md")) == "lock-closed-edit"
    assert _reason(_edit(main, "notes/x.md")) == "allow"
    local.write_text(json.dumps({"name": "docs", "state": "open", "until": "2999-01-01T00:00:00+00:00"}),
                     encoding="utf-8")
    assert _reason(_edit(linked, "notes/x.md")) == "allow"
    (_shared(main) / "docs.json").unlink()
    assert _reason(_edit(linked, "notes/x.md")) == "allow"  # the fallback for one version


def test_the_owner_open_and_go_also_clear_a_stale_local_marker(tmp_path):
    """E6: `mkway go` and `lock open` remove the older local marker of the target, so the owner's word is not
    overruled by a file nobody writes any more."""
    main, linked = _pair(tmp_path)
    (linked / "mkway" / "locks").mkdir(parents=True, exist_ok=True)
    (linked / "mkway" / "locks" / "hold.json").write_text('{"name": "hold", "state": "closed"}', encoding="utf-8")
    assert cli(linked, "go")[0] == 0
    assert not (linked / "mkway" / "locks" / "hold.json").exists()
    assert _reason(_edit(linked, "src/a.py")) == "allow"


def test_lock_list_shows_the_shared_state_and_its_folder(tmp_path):
    """E7: `mkway lock list` prints the folder it reads from and the shared hold and open locks. Catches: a list
    that shows the work tree's own folder only."""
    main, linked = _pair(tmp_path)
    assert cli(main, "hold")[0] == 0
    assert cli(main, "lock", "open", "docs")[0] == 0
    code, out, _err = cli(linked, "lock", "list")
    assert code == 0
    assert str(_shared(main).resolve()).replace("\\", "/") in out.replace("\\", "/") or \
        str(_shared(main)).replace("\\", "/") in out.replace("\\", "/")
    assert "hold: closed by the owner" in out and "docs open until" in out


def test_everything_else_stays_in_the_work_trees_own_state_folder(tmp_path):
    """E8: a hold writes only `locks/` into the shared folder; the shared folder gets no other file from it."""
    main, linked = _pair(tmp_path)
    assert cli(linked, "hold")[0] == 0
    names = sorted(p.name for p in (main / "mkway" / "state").iterdir())
    assert names == ["locks"]


def test_the_readme_changelog_register_and_keys_name_the_card(tmp_path):
    """E9, E10: the README hold section says a hold reaches every work tree; the changelog has the card under
    `## 0.2.0`; the register has the row; KEYS.md has the marker folder line; VERSION is not changed by this card."""
    from _engine import REPO
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    assert "a hold reaches every worktree of the repository" in readme
    changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    head = changelog.split("## 0.1.0")[0]
    assert "## 0.2.0" in head and "- MW-022: Locks reach every worktree" in head
    register = (REPO / "cards" / "REGISTER.md").read_text(encoding="utf-8")
    assert "| MW-022 | Locks reach every worktree |" in register
    keys = (REPO / "engine" / "KEYS.md").read_text(encoding="utf-8")
    assert "lock marker folder" in keys and "MW-022" in keys
    assert (REPO / "VERSION").read_text(encoding="utf-8").strip() == "0.2.0"
