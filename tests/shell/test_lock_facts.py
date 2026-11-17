"""Card MW-063: the facts the lock gate's shell reads, on real files and real git. Each test builds its scratch repository
under the pytest temp folder (a copy of one prepared repository, so no test depends on another) and reads one fact: the
lock markers, the files and folders git says a commit takes, the staged register, the seal, the records and the register.
The decisions on these facts are `tests/core/test_lock_decide.py`. Synthetic values only."""
import hashlib
import json
import shutil
import subprocess

import pytest

from _engine import cli, task_root
import core_lock as core
import dispatch
import gate_lock
import locks
import records
import runner

GIT_ID = ["-c", "user.name=mkway-test", "-c", "user.email=mkway-test"]
PROFILE_REL, SRC_REL, REGISTER_REL = "mkway/profile.json", "src/a.py", "mkway/cards/REGISTER.md"


def git(cwd, *args):
    return subprocess.run(["git", *GIT_ID, *args], cwd=str(cwd), capture_output=True, text=True, check=True).stdout


def read_profile(root):
    return json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))


def write_profile(root, profile):
    (root / "mkway" / "profile.json").write_text(json.dumps(profile, indent=2), encoding="utf-8")


def ctx_of(root, *, tool="Bash", command="x", session="s1", **payload):
    """The context the dispatcher builds for a gate call, and the profile it carries."""
    profile = read_profile(root)
    tool_input = {"command": command} if tool in ("Bash", "PowerShell") else {"file_path": command}
    return dispatch.make_context(profile=profile, root=root, session_id=session, event="PreToolUse", gate="g",
                                 tool_name=tool, tool_input=tool_input, budget_seconds=None, once=lambda t: True,
                                 tool_response=None, env={}, **payload), profile


def reader_of(root, command="x", **kw):
    ctx, profile = ctx_of(root, command=command, **kw)
    return gate_lock.Reader(ctx, profile, command)


@pytest.fixture(scope="module")
def prepared(tmp_path_factory):
    """One task root under git: the register sealed with CARD-001, `src/a.py` and everything committed."""
    root = task_root(tmp_path_factory.mktemp("prepared"), vcs="git", name="task")
    (root / "mkway" / ".gitignore").write_text("engine/\nlocks/\nstate/\n", encoding="utf-8")
    (root / "src").mkdir()
    (root / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    git(root, "init", "-q")
    assert cli(root, "card", "new", "First")[0] == 0
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "start")
    return root


@pytest.fixture
def repo(prepared, tmp_path):
    """A private copy of the prepared repository."""
    target = tmp_path / "task"
    shutil.copytree(prepared, target)
    return target


@pytest.fixture
def dirty(repo):
    """The profile and the source file have a tracked change that is not staged."""
    (repo / "mkway" / "profile.json").write_bytes((repo / "mkway" / "profile.json").read_bytes() + b"\n")
    (repo / "src" / "a.py").write_text("x = 2\n", encoding="utf-8")
    return repo


# ==== the lock markers: is a target closed =====================================================================================

DOCS_PROFILE = {"locks": {"targets": [{"name": "docs", "paths": ["notes/"]}]}}


def closed_flags(root):
    return {t.name: t.closed for t in locks.core_targets(root, read_profile(root))}


def write_docs_marker(root, marker):
    """The `docs` marker as the test gives it: nothing, text as it is, or a dict written as JSON."""
    folder = root / "mkway" / "state" / "locks"
    folder.mkdir(parents=True, exist_ok=True)
    if marker is not None:
        (folder / "docs.json").write_text(marker if isinstance(marker, str) else json.dumps(marker), encoding="utf-8")


def write_hold_marker(root, exists):
    """The owner's `hold` marker, closed, when the test asks for one."""
    if exists:
        folder = root / "mkway" / "state" / "locks"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "hold.json").write_text('{"name": "hold", "state": "closed"}', encoding="utf-8")


def test_the_built_in_targets_stay_closed_when_the_profile_lists_none(repo):
    """Catches: a profile (`locks.targets: []`) that empties the built-in list, so the engine and the register open."""
    profile = read_profile(repo)
    profile["locks"] = {"targets": []}
    write_profile(repo, profile)
    assert closed_flags(repo) == {name: True for name in (
        "engine", "lock", "profile", "hooks", "locks", "gitignore", "gitattributes", "register", "state", "upgrade")} | {
        "inbox": True}


MARKER = [
    pytest.param(None, True, id="no-marker"),
    pytest.param({"state": "open", "until": "2999-01-01T00:00:00+00:00"}, False, id="open-and-not-expired"),
    pytest.param({"state": "open", "until": "2000-01-01T00:00:00+00:00"}, True, id="open-but-expired"),
    pytest.param({"state": "closed", "until": "2999-01-01T00:00:00+00:00"}, True, id="marked-closed"),
    pytest.param({"state": "open"}, True, id="open-with-no-end-time"),
    pytest.param("not json", True, id="marker-text-unreadable"),
]


@pytest.mark.parametrize("marker, closed", MARKER)
def test_a_profile_target_is_closed_unless_its_marker_is_open_and_not_expired(repo, marker, closed):
    """Catches: a lock that never expires, or one that opens on a marker it cannot read."""
    profile = read_profile(repo) | DOCS_PROFILE
    write_profile(repo, profile)
    write_docs_marker(repo, marker)
    assert closed_flags(repo)["docs"] is closed


def test_a_target_that_is_never_open_stays_closed_under_an_open_marker(repo):
    """Catches: an open marker that opens the `locks` folder, which only the engine writes."""
    folder = repo / "mkway" / "state" / "locks"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "locks.json").write_text(json.dumps({"state": "open", "until": "2999-01-01T00:00:00+00:00"}), encoding="utf-8")
    assert closed_flags(repo)["locks"] is True


HOLD_PROFILE = {"locks": {"targets": [{"name": "hold", "paths": ["**"], "open_by_default": True}]}}


@pytest.mark.parametrize("marker_exists, closed", [
    pytest.param(False, False, id="no-marker-the-hold-is-open"),
    pytest.param(True, True, id="the-owner-marker-closes-it"),
])
def test_the_owner_hold_is_open_until_the_owner_marker_exists(repo, marker_exists, closed):
    """Catches: a hold that blocks every write with no marker, or one that ignores the owner's marker."""
    write_profile(repo, read_profile(repo) | HOLD_PROFILE)
    write_hold_marker(repo, marker_exists)
    assert closed_flags(repo)["hold"] is closed


@pytest.mark.parametrize("name", [
    pytest.param("locks", id="a-target-that-is-never-open"),
    pytest.param("nosuch", id="a-name-no-target-has"),
])
def test_the_owner_cannot_open_a_lock_that_is_never_open_or_does_not_exist(repo, name):
    """Catches: `lock open locks` writing a marker for a folder only the engine writes, or `lock open nosuch` making a lock."""
    with pytest.raises(locks.LockError):
        locks.set_lock(repo, read_profile(repo), name, "open")


def test_the_gate_refuses_an_edit_by_an_absolute_path_inside_the_root(repo):
    """Catches: an absolute path to the profile that is read as outside the root and so allowed."""
    ctx, _profile = ctx_of(repo, tool="Edit", command=str(repo / "mkway" / "profile.json"))
    v = gate_lock.check("PreToolUse", ctx)
    assert (v.kind, v.reason_id) == ("refuse", "lock-closed-edit")


# ==== the markers are shared by every work tree of a repository ================================================================

HOLD = {"name": "hold", "paths": ["**"], "open_by_default": True}
DOCS = {"name": "docs", "paths": ["notes/"]}


@pytest.fixture(scope="module")
def pair(tmp_path_factory):
    """A main work tree and a linked one, both holding the committed profile with the hold and `docs` targets; the
    owner opted into sharing (`state.shared_dir` names the main state folder)."""
    base = tmp_path_factory.mktemp("pair")
    top = base / "main"
    top.mkdir()
    git(top, "init", "-q")
    shared = str((top / "mkway" / "state").resolve())
    seed = task_root(base, name="seed", locks={"targets": [HOLD, DOCS]}, state={"dir": "mkway/state", "shared_dir": shared})
    (top / "mkway").mkdir()
    (top / "mkway" / "profile.json").write_bytes((seed / "mkway" / "profile.json").read_bytes())
    git(top, "add", "-A")
    git(top, "commit", "-q", "-m", "profile")
    linked = base / "linked"
    git(top, "worktree", "add", "-q", str(linked), "-b", "wt")
    return top, linked


@pytest.fixture
def trees(pair):
    """The pair with no marker anywhere before the test and the linked profile as committed after it."""
    main, linked = pair
    committed = (linked / "mkway" / "profile.json").read_bytes()

    def clean():
        for folder in (main / "mkway" / "state" / "locks", main / "mkway" / "locks", linked / "mkway" / "locks"):
            shutil.rmtree(folder, ignore_errors=True)
        (linked / "mkway" / "profile.json").write_bytes(committed)
    clean()
    yield main, linked
    clean()


def flags(root):
    return closed_flags(root)


def shared_folder(main):
    return main / "mkway" / "state" / "locks"


@pytest.mark.real_shared_state
def test_a_hold_marker_written_in_the_main_tree_closes_the_hold_in_the_linked_tree(trees):
    """Catches: a marker that stays per work tree, so a hold typed in one tree stops nothing in the other."""
    main, linked = trees
    locks.set_lock(main, read_profile(main), "hold", "closed")
    assert (shared_folder(main) / "hold.json").is_file()
    assert flags(linked)["hold"] is True


@pytest.mark.real_shared_state
def test_a_hold_marker_written_in_the_linked_tree_closes_the_hold_in_the_main_tree(trees):
    """Catches: a hold that reaches only where it was typed."""
    main, linked = trees
    locks.set_lock(linked, read_profile(linked), "hold", "closed")
    assert (shared_folder(main) / "hold.json").is_file()
    assert flags(main)["hold"] is True


@pytest.mark.real_shared_state
def test_a_hold_marker_is_written_into_the_shared_folder_and_nowhere_else(trees):
    """Catches: a hold marker written into the linked tree's own folder or outside the shared folder, so the other tree never sees it."""
    main, linked = trees
    locks.set_lock(linked, read_profile(linked), "hold", "closed")
    assert ([p.name for p in shared_folder(main).iterdir()], (linked / "mkway" / "locks" / "hold.json").exists(),
            sorted(p.name for p in (main / "mkway" / "state").iterdir())) == (["hold.json"], False, ["locks"])


@pytest.mark.real_shared_state
def test_the_owner_go_in_one_tree_lifts_the_hold_in_the_other(trees):
    """Catches: a `go` that removes only the marker of the tree it ran in."""
    main, linked = trees
    locks.set_lock(main, read_profile(main), "hold", "closed")
    locks.set_lock(linked, read_profile(linked), "hold", "open")
    assert (flags(main)["hold"], flags(linked)["hold"]) == (False, False)


@pytest.mark.real_shared_state
def test_a_lock_target_opened_in_one_tree_is_open_in_the_other(trees):
    """Catches: a `lock open` that opens the target in the tree it ran in only."""
    main, linked = trees
    locks.set_lock(main, read_profile(main), "docs", "open", minutes=5)
    assert flags(linked)["docs"] is False


@pytest.mark.real_shared_state
def test_a_lock_target_closed_in_one_tree_is_closed_in_the_other(trees):
    """Catches: a lock close that closes the target in the tree it ran in only, leaving the other tree open."""
    main, linked = trees
    locks.set_lock(main, read_profile(main), "docs", "open", minutes=5)
    locks.set_lock(linked, read_profile(linked), "docs", "closed")
    assert (flags(main)["docs"], flags(linked)["docs"]) == (True, True)


def test_a_repository_with_no_linked_tree_keeps_its_markers_in_its_own_state_folder(tmp_path, monkeypatch):
    """Catches: a marker written outside the state folder when there is no second work tree."""
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    root = task_root(tmp_path, name="plain", locks={"targets": [HOLD, DOCS]})
    locks.set_lock(root, read_profile(root), "hold", "closed")
    assert ((root / "mkway" / "state" / "locks" / "hold.json").is_file(), list((root / "mkway" / "locks").iterdir()),
            closed_flags(root)["hold"]) == (True, [], True)


@pytest.mark.real_shared_state
def test_a_tree_whose_profile_has_no_target_of_that_name_ignores_the_marker(trees):
    """Catches: a marker read by name for a target the profile does not know."""
    main, linked = trees
    profile = read_profile(linked)
    profile["locks"] = {"targets": [DOCS]}
    write_profile(linked, profile)
    locks.set_lock(main, read_profile(main), "hold", "closed")
    assert "hold" not in closed_flags(linked)


def local_marker(linked, name, body):
    folder = linked / "mkway" / "locks"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.json").write_text(json.dumps(body), encoding="utf-8")


@pytest.mark.real_shared_state
def test_an_older_local_marker_still_closes_the_hold_in_its_own_tree_only(trees):
    """Catches: a hold dropped silently on the upgrade to the shared folder."""
    main, linked = trees
    local_marker(linked, "hold", {"name": "hold", "state": "closed"})
    assert (flags(linked)["hold"], flags(main)["hold"]) == (True, False)


@pytest.mark.real_shared_state
def test_an_older_local_marker_is_named_in_the_listing_and_the_warning(trees):
    """Catches: an older marker that closes a gate and that no list or check names."""
    main, linked = trees
    local_marker(linked, "hold", {"name": "hold", "state": "closed"})
    profile = read_profile(linked)
    assert ([name for name, _path in locks.local_markers(linked, profile)], locks.local_markers(main, read_profile(main)),
            any("lock-marker-local" in line for line in locks.marker_warnings(linked, profile))) == (["hold"], [], True)


@pytest.mark.real_shared_state
def test_closed_wins_when_the_local_marker_is_closed_and_the_shared_one_is_open(trees):
    """Catches: a shared open marker that overrules an older closed one."""
    main, linked = trees
    locks.set_lock(main, read_profile(main), "docs", "open", minutes=5)
    local_marker(linked, "docs", {"name": "docs", "state": "closed"})
    assert flags(linked)["docs"] is True


@pytest.mark.real_shared_state
def test_a_local_open_marker_alone_still_opens_the_target(trees):
    """Catches: the one-version fallback dropped, so an older open marker stops working at once."""
    _main, linked = trees
    local_marker(linked, "docs", {"name": "docs", "state": "open", "until": "2999-01-01T00:00:00+00:00"})
    assert flags(linked)["docs"] is False


@pytest.mark.real_shared_state
def test_the_owner_go_removes_an_older_local_marker(trees):
    """Catches: the owner's word overruled by a file nobody writes any more."""
    _main, linked = trees
    local_marker(linked, "hold", {"name": "hold", "state": "closed"})
    locks.set_lock(linked, read_profile(linked), "hold", "open")
    assert not (linked / "mkway" / "locks" / "hold.json").exists()


@pytest.mark.real_shared_state
def test_the_lock_list_prints_the_shared_folder_the_hold_and_the_open_lock(trees):
    """Catches: a list that shows the work tree's own folder only."""
    main, linked = trees
    locks.set_lock(main, read_profile(main), "hold", "closed")
    locks.set_lock(main, read_profile(main), "docs", "open", minutes=5)
    code, out, _err = cli(linked, "lock", "list")
    shown = out.replace("\\", "/")
    assert (code, str(shared_folder(main)).replace("\\", "/") in shown, "hold: closed by the owner" in out,
            "docs open until" in out) == (0, True, True, True)


# ==== what git says a commit takes =============================================================================================

def expand(root, specs, folder=None):
    ctx, _profile = ctx_of(root)
    return gate_lock._expand(ctx, folder or root, specs)


@pytest.mark.parametrize("specs, names", [
    pytest.param(["mkway"], ["mkway/profile.json"], id="folder-of-the-profile"),
    pytest.param(["."], ["mkway/profile.json", "src/a.py"], id="dot-takes-every-changed-tracked-file"),
    pytest.param(["mkway/*.json"], ["mkway/profile.json"], id="glob"),
    pytest.param([":(glob)mkway/**"], ["mkway/profile.json"], id="glob-magic"),
    pytest.param(["src"], ["src/a.py"], id="source-folder"),
])
def test_a_pathspec_expands_to_the_changed_tracked_files_it_matches(dirty, specs, names):
    """Catches: `git commit -- mkway` committing a changed profile because only the folder name was read."""
    assert expand(dirty, specs) == (names, None)


def test_a_pathspec_from_a_subfolder_is_expanded_from_that_folder(dirty):
    """Catches: `git -C mkway commit -- .` read from the root, so the profile is never seen."""
    assert expand(dirty, ["."], folder=dirty / "mkway") == (["mkway/profile.json"], None)


def test_a_folder_with_no_changed_tracked_file_expands_to_nothing(repo):
    """Catches: a folder with no changed tracked file expanding to some file, so an empty commit is judged as taking one."""
    assert expand(repo, ["mkway"]) == ([], None)


def test_a_pathspec_git_refuses_is_a_problem_never_an_empty_list(repo):
    """Catches: a refused pathspec read as «no files», so the commit passes unchecked."""
    names, problem = expand(repo, [":(bogus)x"])
    assert (names, problem.startswith("git exit")) == ([], True)


@pytest.fixture
def fresh(tmp_path):
    """A repository with no commit yet and the bundle staged."""
    root = task_root(tmp_path, vcs="git", name="fresh")
    (root / "mkway" / ".gitignore").write_text("engine/\nlocks/\nstate/\n", encoding="utf-8")
    (root / "src").mkdir()
    (root / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    git(root, "init", "-q")
    git(root, "add", "-A")
    return root


def test_before_the_first_commit_a_pathspec_expands_over_the_index(fresh):
    """Catches: an expansion that fails open when there is no HEAD."""
    names, problem = expand(fresh, ["mkway"])
    assert ("mkway/.gitignore" in names, problem) == (True, None)


def test_before_the_first_commit_a_pathspec_outside_the_bundle_expands_to_its_own_files(fresh):
    """Catches: a source-folder pathspec before the first commit expanding to nothing, so its file is not judged."""
    assert expand(fresh, ["src"]) == (["src/a.py"], None)


def index_names(root, every):
    ctx, _profile = ctx_of(root)
    return gate_lock._index_names(ctx, every)


def test_a_bare_commit_takes_the_staged_names(dirty):
    """Checks: a bare commit takes the staged names of the index, here the profile."""
    git(dirty, "add", PROFILE_REL)
    assert index_names(dirty, False) == ([PROFILE_REL], None)


def test_a_bare_commit_does_not_take_a_change_that_is_not_staged(dirty):
    """Catches: a bare commit judged by changes it does not take, refusing lawful commits."""
    assert index_names(dirty, False) == ([], None)


def test_a_commit_with_dash_a_takes_the_staged_names_and_the_tracked_changes(dirty):
    """Catches: `git commit -a` committing a changed locked file nobody staged."""
    assert index_names(dirty, True) == ([PROFILE_REL, SRC_REL], None)


@pytest.mark.parametrize("every", [
    pytest.param(False, id="bare-commit"),
    pytest.param(True, id="dash-a"),
])
def test_before_the_first_commit_the_index_names_are_read(fresh, every):
    """Catches: a check that fails open when HEAD is missing."""
    names, problem = index_names(fresh, every)
    assert ("mkway/.gitignore" in names, problem) == (True, None)


def fake_git(diff_head_exit, head_exists):
    """A git whose `diff ... HEAD` fails with the given exit code and whose `rev-parse --verify HEAD` says whether a HEAD exists."""
    def fake(cwd, *args, **kwargs):
        if args[0] == "diff" and "HEAD" in args:
            return subprocess.CompletedProcess(args, diff_head_exit, "mkway/profile.json\n" if diff_head_exit == 0 else "", "")
        if args[0] == "rev-parse":
            return subprocess.CompletedProcess(args, 0 if head_exists else 1, "", "")
        return subprocess.CompletedProcess(args, 0, "", "")
    return fake


def test_a_failed_diff_with_a_head_is_a_problem_under_dash_a(repo, monkeypatch):
    """Catches: any failure of `git diff HEAD` taken as «no HEAD», so the tracked changes `-a` commits are missed."""
    monkeypatch.setattr(runner, "git", fake_git(128, head_exists=True))
    assert index_names(repo, True) == ([], "git exit 128")


def test_a_failed_diff_without_a_head_falls_back_to_the_index_under_dash_a(repo, monkeypatch):
    """Catches: a failed diff with no HEAD refused instead of falling back to the index under dash a."""
    monkeypatch.setattr(runner, "git", fake_git(128, head_exists=False))
    assert index_names(repo, True) == ([], None)


# ==== the staged register, the seal, the files on disk =========================================================================

def reader_blob(root, rel):
    return reader_of(root).fact_blob(rel)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_the_staged_register_is_read_as_a_blob_from_the_root(repo):
    """Catches: a staged forgery behind a restored working tree that the check never reads."""
    path = repo / REGISTER_REL
    good = path.read_bytes()
    forged = good.replace(b"proposed", b"open", 1)
    path.write_bytes(forged)
    git(repo, "add", REGISTER_REL)
    path.write_bytes(good)
    assert reader_blob(repo, REGISTER_REL) == core.Blob(sha(forged), 0)


def test_the_staged_register_is_found_when_the_root_lies_below_the_git_top(tmp_path):
    """Catches: `:<path>` read from the git top, which names no file, so the check passes."""
    top = tmp_path / "top"
    top.mkdir()
    git(top, "init", "-q")
    root = task_root(top, vcs="git", name="task")
    assert cli(root, "card", "new", "First")[0] == 0
    git(top, "add", "-A")
    git(top, "commit", "-q", "-m", "start")
    assert reader_blob(root, REGISTER_REL) == core.Blob(sha((root / REGISTER_REL).read_bytes()), 0)


def test_a_register_that_is_not_in_the_index_reads_as_a_git_failure(repo):
    """Catches: a failed staged read taken as a match."""
    git(repo, "rm", "-q", "--cached", REGISTER_REL)
    blob = reader_blob(repo, REGISTER_REL)
    assert (blob.sha, blob.exit_code != 0) == (None, True)


def test_a_git_read_that_does_not_answer_in_time_is_a_timeout_fact(repo, monkeypatch):
    """Catches: a hung git read that crashes the gate or passes the commit."""
    def hung(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="git", timeout=10)
    monkeypatch.setattr(runner, "git", hung)
    assert reader_blob(repo, REGISTER_REL) == core.Timeout(10)


def test_a_timeout_in_an_expansion_is_a_timeout_fact(dirty, monkeypatch):
    """Catches: a hung expansion that crashes the gate instead of reading as a timeout fact."""
    def hung(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="git", timeout=10)
    monkeypatch.setattr(runner, "git", hung)
    reader = reader_of(dirty, "git commit -m x -- mkway")
    reader.fact_commits()
    assert reader.fact_expanded(0) == core.Timeout(10)


def seal_of(root):
    return reader_of(root).fact_seal()


def test_a_register_equal_to_its_seal_reads_as_equal(repo):
    """Checks: a register equal to its seal reads as equal in both the seal and the working tree hash."""
    assert seal_of(repo).seal == seal_of(repo).work == sha((repo / REGISTER_REL).read_bytes())


def test_a_register_changed_after_its_seal_reads_as_different(repo):
    """Catches: a changed register read as sealed, so a forged register commits."""
    path = repo / REGISTER_REL
    sealed = seal_of(repo).seal
    path.write_bytes(path.read_bytes().replace(b"proposed", b"open", 1))
    seal = seal_of(repo)
    assert (seal.seal, seal.work == sealed) == (sealed, False)


def test_a_missing_seal_file_reads_as_missing(repo):
    """Catches: a missing seal read as a match."""
    (repo / "mkway" / "state" / "register.sha").unlink()
    assert seal_of(repo) == core.Seal("register.sha", False)


def test_a_missing_register_file_reads_as_no_working_tree_hash(repo):
    """Catches: a missing register file read as a hash, so a deleted register passes the seal."""
    (repo / REGISTER_REL).unlink()
    assert seal_of(repo).work is None


def test_a_folder_holding_a_file_a_glob_matches_names_that_file(repo):
    """Checks: a folder holding a file the glob matches names that file as its disk fact."""
    (repo / "data").mkdir()
    (repo / "data" / "x.seed").write_text("x\n", encoding="utf-8")
    assert reader_of(repo).fact_disk("data", "*.seed") == "data/x.seed"


def test_a_folder_with_no_matching_file_names_none(repo):
    """Checks: a folder with no file the glob matches reads as none."""
    assert reader_of(repo).fact_disk("src", "*.seed") is None


# ==== the records, the register, the command ====================================================================================

def test_the_holders_and_the_held_card_come_from_the_session_records(repo):
    """Checks: the holders and the held card are read from the session records that take writes."""
    records.append(repo / "mkway" / "state", "s1", "take", "CARD-001")
    reader = reader_of(repo)
    assert (reader.fact_holders(), reader.fact_mine()) == ({"CARD-001": "s1"}, "CARD-001")


def test_the_register_facts_carry_each_row_s_status_and_orderer(repo):
    """Checks: the register facts carry the status and the orderer of each row."""
    facts = reader_of(repo).fact_register()
    row = facts.rows["CARD-001"]
    assert (facts.problem, row.status, row.ordered_by) == (None, "proposed", "owner")


def test_a_register_that_fails_its_seal_is_a_problem_fact(repo):
    """Catches: a tampered register read as sound by the gate's own register read."""
    path = repo / REGISTER_REL
    path.write_bytes(path.read_bytes().replace(b"proposed", b"open", 1))
    assert reader_of(repo).fact_register().problem[0] == "register-tampered"


@pytest.mark.parametrize("command, args", [
    pytest.param("python mkway/engine/mkway.py card open CARD-001", ("card", "open", "CARD-001"), id="plain"),
    pytest.param("py -3 mkway/engine/mkway.py card open CARD-001", ("card", "open", "CARD-001"), id="py-launcher"),
    pytest.param("cd mkway/engine && python mkway.py card close CARD-001", ("card", "close", "CARD-001"),
                 id="after-a-cd-into-the-engine-folder"),
    pytest.param("python mkway/engine/mkway.py card release CARD-001 --force=yes",
                 ("card", "release", "CARD-001", "--force=yes"), id="release-with-a-force-value"),
    pytest.param("python mkway/engine/mkway.py lock open rules --minutes 5", ("lock", "open", "rules", "--minutes", "5"),
                 id="lock-open-with-minutes"),
])
def test_the_engine_call_is_read_from_each_spelling(repo, command, args):
    """Catches: an owner command run in a spelling the reader does not read, so the owner rules never apply."""
    assert reader_of(repo, command).fact_calls() == (args,)


def test_a_command_with_no_engine_call_reads_as_no_calls(repo):
    """Catches: a command with no engine call read as an engine call, so an owner rule applies to git status."""
    assert reader_of(repo, "git status").fact_calls() == ()


def test_the_write_paths_come_with_their_repo_paths(repo):
    """Checks: a redirect write to a repository path comes with that path as its repo path."""
    writes = reader_of(repo, "echo x > src/a.txt").fact_writes()
    assert (writes.reason, writes.paths) == (None, (("src/a.txt", "src/a.txt"),))


def test_a_path_with_a_variable_has_no_repo_path(repo):
    """Catches: a path with a shell variable read as a repository path, so it is judged as a file."""
    writes = reader_of(repo, 'echo x > "$OUT/a.txt"').fact_writes()
    assert [rel for _text, rel in writes.paths] == [None]


def test_the_pathspecs_of_a_commit_come_with_their_repo_paths(repo):
    """Checks: the pathspecs of a commit come with their repository paths and no include flag."""
    (commit,) = reader_of(repo, "git commit -m x -- src/a.py").fact_commits()
    assert (commit.paths, commit.rels, commit.include) == (("src/a.py",), ("src/a.py",), False)


# ==== the shell: asks until the core has what it needs, then leaves the permits ================================================

def test_the_gate_refuses_a_commit_of_a_changed_profile_by_reading_git_when_the_core_asks(dirty):
    """Catches: a shell that answers before the core has the files the commit takes."""
    ctx, _profile = ctx_of(dirty, command="git commit -m 'CARD-001 x' -- mkway")
    v = gate_lock.check("PreToolUse", ctx)
    assert (v.kind, v.reason_id, PROFILE_REL in v.message) == ("refuse", "lock-closed-commit", True)


def test_the_gate_allows_a_commit_of_a_source_file_by_reading_git_when_the_core_asks(dirty):
    """Checks: a commit of a source file is allowed when the core asks for the git read."""
    ctx, _profile = ctx_of(dirty, command="git commit -m 'CARD-001 x' -- src/a.py")
    assert gate_lock.check("PreToolUse", ctx).kind == "allow"


def test_a_one_use_permit_the_core_names_is_left_in_the_state_folder(repo):
    """Catches: a gate that decides a ledger call may pass but leaves no permit, so the CLI cannot name the session."""
    import cardtool
    ctx, profile = ctx_of(repo, session="s7")
    gate_lock._finish(ctx, profile, core.Verdict(core.ALLOW, permits=(core.Permit("by"),)))
    assert cardtool.take_by_permit(repo / "mkway" / "state") == "s7"


def test_a_permit_that_cannot_be_written_returns_the_verdict_the_core_named(repo):
    """Catches: a close that passes the gate although its permit was never left."""
    ctx, profile = ctx_of(repo, session="s7")
    named = core.refuse("close-not-orderer", "the permit could not be written")
    v = gate_lock._finish(ctx, profile, core.Verdict(core.ALLOW, permits=(core.Permit("close", "bad card id", named),)))
    assert (v.kind, v.reason_id) == ("refuse", "close-not-orderer")
