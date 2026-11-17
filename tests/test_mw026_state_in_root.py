"""Card MW-026: the engine never writes state outside the mkway root by its own path logic. Synthetic scratch
repositories under the pytest temp folder only (the `real_shared_state` mark: these tests ask git for real)."""
import json
import re
import subprocess

import pytest

import _docs as docs
from _engine import REPO, cli, task_root
from _mw017 import session_run
from test_install import clean_env, git, make_light_source, make_source, make_task, mkway
import dispatch
import install
import profiles
import sessions

pytestmark = pytest.mark.real_shared_state

HOLD = {"name": "hold", "paths": ["**"], "open_by_default": True}


def _files_outside(world, root):
    """Every file under `world` that is not below `root` and not inside a `.git` entry: what an engine write above the
    root would add."""
    root = root.resolve()
    found = set()
    for path in world.rglob("*"):
        resolved = path.resolve()
        if not path.is_file() or ".git" in path.relative_to(world).parts:
            continue
        if root == resolved or root in resolved.parents:
            continue
        found.add(path.relative_to(world).as_posix())
    return found


def _session(root, tmp_path):
    """Install, a session start, `lead register`, `send` and `hold` at `root`."""
    src = make_source(tmp_path / "engine-src", vcs="none")
    install.install(root, src, vcs="none")
    payload = json.dumps({"session_id": "s-1", "hook_event_name": "SessionStart", "cwd": str(root), "prompt": "hi"})
    dispatch.run("SessionStart", "start", payload, env={"CLAUDE_PROJECT_DIR": str(root), "CLAUDECODE": "1"})
    code, _out, err = session_run(root, "lead-a", "lead", "register")
    assert code == 0, err
    for sid in ("lead-a", "free-1"):  # the sessions file the engine itself reads
        sessions.append(profiles.shared_state_dir(root, _profile(root)), sid, root)
    (root / "body.txt").write_text("text", encoding="utf-8")
    code, _out, err = session_run(root, "free-1", "send", "--to", "lead-a", "--kind", "question", "--file", "body.txt")
    assert code == 0, err
    assert cli(root, "hold")[0] == 0


def _profile(root):
    return json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))


def _root(top, sub=""):
    root = top / sub if sub else top
    task_root(root.parent, name=root.name, cards={"approver": "orderer"}, locks={"targets": [HOLD]})
    return root


def test_a_root_below_a_linked_worktree_writes_nothing_above_itself(tmp_path):
    """E1: the root is a subfolder of a linked worktree (sparse checkout when git allows it); after install, a
    session start, `lead register`, `send` and `hold`, no file exists above the root."""
    main = tmp_path / "world" / "main"
    main.mkdir(parents=True)
    git(main, "init", "-q")
    (main / "task" / "T").mkdir(parents=True)
    (main / "task" / "T" / "keep.txt").write_text("x", encoding="utf-8")
    git(main, "add", "-A")
    git(main, "commit", "-q", "-m", "base")
    linked = tmp_path / "world" / "linked"
    git(main, "worktree", "add", "-q", str(linked), "-b", "wt")
    subprocess.run(["git", "-C", str(linked), "sparse-checkout", "set", "task/T"], capture_output=True)  # if allowed
    root = linked / "task" / "T"
    task_root(root.parent, name="T", cards={"approver": "orderer"}, locks={"targets": [HOLD]})
    before = _files_outside(tmp_path / "world", root)
    _session(root, tmp_path)
    assert _files_outside(tmp_path / "world", root) == before
    assert (root / "mkway" / "state" / "leads.json").is_file()
    assert (root / "mkway" / "state" / "sessions.jsonl").is_file()


def test_a_root_at_the_repository_top_writes_nothing_above_itself(tmp_path):
    """E2: the root is the top of a git repository: nothing exists outside it after the same steps."""
    root = tmp_path / "world" / "top"
    root.mkdir(parents=True)
    git(root, "init", "-q")
    _root(root)
    before = _files_outside(tmp_path / "world", root)
    _session(root, tmp_path)
    assert _files_outside(tmp_path / "world", root) == before
    assert (root / "mkway" / "state" / "leads.json").is_file()


def test_a_root_with_no_git_writes_nothing_above_itself(tmp_path, monkeypatch):
    """E3: no git at all: nothing exists outside the root after the same steps."""
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    root = tmp_path / "world" / "plain"
    root.mkdir(parents=True)
    _root(root)
    before = _files_outside(tmp_path / "world", root)
    _session(root, tmp_path)
    assert _files_outside(tmp_path / "world", root) == before
    assert (root / "mkway" / "state" / "leads.json").is_file()


def test_the_shared_dir_is_the_state_dir_unless_the_profile_names_an_absolute_path(tmp_path):
    """E4: no key: `state_dir`, also in a linked worktree; an absolute `state.shared_dir`: that path; a relative or
    empty value is a schema error and the lookup takes `state_dir`."""
    main = tmp_path / "main"
    main.mkdir()
    git(main, "init", "-q")
    (main / "f.txt").write_text("x", encoding="utf-8")
    git(main, "add", "-A")
    git(main, "commit", "-q", "-m", "base")
    linked = tmp_path / "linked"
    git(main, "worktree", "add", "-q", str(linked), "-b", "wt")
    profile = {"state": {"dir": "mkway/state"}}
    assert profiles.shared_state_dir(linked, profile) == profiles.state_dir(linked, profile)
    outside = (tmp_path / "elsewhere" / "state").resolve()
    profile = {"state": {"dir": "mkway/state", "shared_dir": str(outside)}}
    assert profiles.shared_state_dir(linked, profile) == outside
    for bad in ("shared", "", "../x"):
        profile = {"state": {"dir": "mkway/state", "shared_dir": bad}}
        assert profiles.shared_state_dir(linked, profile) == profiles.state_dir(linked, profile)
    full = {"vcs": "none", "bundle": {"root": "mkway"}, "gates": {}, "python": {"command": "python"},
            "state": {"dir": "mkway/state", "shared_dir": "relative/x"}}
    assert any("state.shared_dir" in e for e in profiles.validate(full))
    full["state"]["shared_dir"] = str(outside)
    assert profiles.validate(full) == []


def test_with_the_key_set_the_shared_files_live_there_and_the_rest_stays_in_the_root(tmp_path):
    """E5: `state.shared_dir` set: leads.json, inbox/, sessions.jsonl and the hold marker live there; records stay
    under the root's own state folder."""
    shared = (tmp_path / "shared").resolve()
    root = tmp_path / "world" / "plain"
    root.mkdir(parents=True)
    task_root(root.parent, name="plain", cards={"approver": "orderer"}, locks={"targets": [HOLD]},
              state={"dir": "mkway/state", "shared_dir": str(shared)})
    _session(root, tmp_path)
    assert (shared / "leads.json").is_file() and (shared / "sessions.jsonl").is_file()
    assert (shared / "inbox" / "lead-a.jsonl").is_file() and (shared / "locks" / "hold.json").is_file()
    own = root / "mkway" / "state"
    assert not (own / "leads.json").exists() and not (own / "sessions.jsonl").exists()
    assert (own / "records.jsonl").is_file()


def test_install_shared_writes_the_key_into_the_profile(tmp_path):
    """E6: `mkway install --shared <abs path>` writes `state.shared_dir` into a new starter profile and into an
    existing valid one (other keys kept); a relative path is refused and nothing is written."""
    src = make_source(tmp_path, vcs="none")
    env = clean_env(tmp_path)
    shared = (tmp_path / "shared").resolve()
    fresh = make_task(tmp_path, vcs="none", name="fresh")
    proc = mkway(fresh, env, "install", "--from", str(src), "--vcs", "none", "--shared", str(shared))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert _profile(fresh)["state"] == {"dir": "mkway/state", "shared_dir": str(shared)}
    old = make_task(tmp_path, vcs="none", name="old")
    task_root(tmp_path, name="old", ids={"card_prefix": "ZZ"})
    proc = mkway(old, env, "install", "--from", str(src), "--vcs", "none", "--shared", str(shared))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert _profile(old)["state"]["shared_dir"] == str(shared) and _profile(old)["ids"] == {"card_prefix": "ZZ"}
    bare = make_task(tmp_path, vcs="none", name="bare")
    proc = mkway(bare, env, "install", "--from", str(src), "--vcs", "none", "--shared", "relative/x")
    assert proc.returncode != 0 and "--shared" in proc.stdout + proc.stderr
    assert not (bare / "mkway").exists()


def test_check_warns_state_outside_root_for_files_in_the_main_worktrees_mirror(tmp_path):
    """E7: files that 0.2.0/0.2.1 wrote into the main worktree's mirror of the root make `check` print
    `state-outside-root` with that folder; nothing is removed; no files, no warning."""
    main = tmp_path / "main"
    (main / "task" / "T").mkdir(parents=True)
    git(main, "init", "-q")
    (main / "task" / "T" / "keep.txt").write_text("x", encoding="utf-8")
    git(main, "add", "-A")
    git(main, "commit", "-q", "-m", "base")
    linked = tmp_path / "linked"
    git(main, "worktree", "add", "-q", str(linked), "-b", "wt")
    root = _root(linked, "task/T")
    profile = _profile(root)
    assert install.state_outside_root_lines(root, profile) == []
    mirror = main / "task" / "T" / "mkway" / "state"
    mirror.mkdir(parents=True)
    (mirror / "leads.json").write_text("{}", encoding="utf-8")
    (mirror / "sessions.jsonl").write_text("", encoding="utf-8")
    (mirror / "unrelated.txt").write_text("keep", encoding="utf-8")
    (line,) = install.state_outside_root_lines(root, profile)
    assert line.startswith("state-outside-root") and str(mirror.resolve()) in line
    assert (mirror / "leads.json").is_file() and (mirror / "unrelated.txt").is_file()
    profile["state"]["shared_dir"] = str(mirror.resolve())  # the owner chose it: no warning
    assert install.state_outside_root_lines(root, profile) == []


def test_check_prints_the_state_outside_root_line(tmp_path):
    """E7: the full `mkway check` carries the warning line and still exits 0 (a warning, never a failure)."""
    src = make_light_source(tmp_path)
    main = tmp_path / "main"
    (main / "task" / "T").mkdir(parents=True)
    git(main, "init", "-q")
    (main / "task" / "T" / "keep.txt").write_text("x", encoding="utf-8")
    git(main, "add", "-A")
    git(main, "commit", "-q", "-m", "base")
    linked = tmp_path / "linked"
    git(main, "worktree", "add", "-q", str(linked), "-b", "wt")
    root = linked / "task" / "T"
    env = clean_env(tmp_path)
    assert mkway(root, env, "install", "--from", str(src), "--vcs", "none").returncode == 0
    mirror = main / "task" / "T" / "mkway" / "state"
    mirror.mkdir(parents=True)
    (mirror / "leads.json").write_text("{}", encoding="utf-8")
    proc = mkway(root, env, "check")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "state-outside-root" in proc.stdout


@pytest.mark.engine_repo  # MW-025: the register, changelog, README and KEYS are not in an installed copy
def test_register_changelog_version_keys_and_readme_name_the_card():
    """E8: the register row, `## 0.2.6` on top of the changelog with the card, VERSION 0.2.6, the KEYS.md row with the
    default (unset), the README opt-in sentences and none of the old mapping."""
    register = (REPO / "cards" / "REGISTER.md").read_text(encoding="utf-8")
    assert re.search(r"^\| MW-026 \|.*`cards/MW-026-[a-z0-9-]+`", register, re.M)
    text = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "MW-026" in docs.changelog_section(text, "MW-026")
    assert list((REPO / "cards").glob("MW-026-*/CARD.md"))
    docs.assert_version_file()
    keys = (REPO / "engine" / "KEYS.md").read_text(encoding="utf-8")
    assert re.search(r"^\| `state\.shared_dir` \|.*unset", keys, re.M)
    readme = " ".join((REPO / "README.md").read_text(encoding="utf-8").split())
    assert "`state.shared_dir`" in readme and "`mkway install --shared <path>`" in readme and "state-outside-root" in readme
    assert "in a linked work tree it is the main work tree's state folder" not in readme
