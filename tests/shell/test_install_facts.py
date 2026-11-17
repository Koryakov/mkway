"""Card MW-067: install and check on real folders and real git, the shell around `engine/core_install.py`. One real
install per kind runs once per session (the session fixtures below); each test reads one fact of it. Every test is under
20 s. Synthetic roots and engine sources under the pytest temp folder only; the engine source is this repository's own
files with its tests cut to the one fixture test, so `mkway check` runs that one test (MW-013)."""
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from _engine import FIXTURES, REPO, fake_program
import install

pytestmark = pytest.mark.engine_repo  # the engine source is built from this repository's tree, so a task's copy skips it

GIT_ID = ["-c", "user.name=mkway-test", "-c", "user.email=mkway-test"]
COMMIT_ENV = {"GIT_AUTHOR_NAME": "mkway-test", "GIT_AUTHOR_EMAIL": "mkway-test", "GIT_COMMITTER_NAME": "mkway-test",
              "GIT_COMMITTER_EMAIL": "mkway-test"}
FIRST_PATHS = (".claude/settings.json mkway/.gitignore mkway/.gitattributes mkway/mkway.lock mkway/engine "
               "mkway/profile.json")
SKIP = (".git", "__pycache__", ".pytest_tmp", ".pytest_cache")


def _git(cwd, *args):
    return subprocess.run(["git", *GIT_ID, *args], cwd=str(cwd), capture_output=True, text=True, check=True).stdout


def _env(base, **extra):
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_PROJECT_DIR", "ENGINE_TERMS_FILE", "CLAUDECODE")}
    home = Path(base) / "home"
    home.mkdir(exist_ok=True)
    env.update(HOME=str(home), USERPROFILE=str(home), GIT_CEILING_DIRECTORIES=str(Path(base).resolve()))
    env.update(extra)
    return env


def _mkway(root, env, *args):
    return subprocess.run([sys.executable, str(REPO / "mkway.py"), *args, "--root", str(root)], capture_output=True,
                          text=True, env=env, timeout=300)


def _task(base, name="task", *, git=False):
    root = Path(base) / name
    root.mkdir(parents=True)
    if git:
        _git(root, "init", "-q")
    return root


def _files(folder):
    return sorted(p.relative_to(folder).as_posix() for p in Path(folder).rglob("*") if p.is_file())


def _disk_hash(copy):
    """The lock's hash, written from the card: sha256 over path, NUL, length, NUL, bytes, in path order; caches left out."""
    digest = hashlib.sha256()
    for rel in _files(copy):
        if rel.endswith(".pyc") or any(part in SKIP for part in rel.split("/")):
            continue
        data = (Path(copy) / rel).read_bytes()
        digest.update(rel.encode("utf-8") + b"\0" + str(len(data)).encode("ascii") + b"\0")
        digest.update(data)
    return "sha256:" + digest.hexdigest()


def _lock(root):
    return json.loads((Path(root) / "mkway" / "mkway.lock").read_text(encoding="utf-8"))


def _settings(root):
    return json.loads((Path(root) / ".claude" / "settings.json").read_text(encoding="utf-8"))


def _owned(root):
    return [h["command"] for groups in _settings(root)["hooks"].values() for g in groups for h in g["hooks"]
            if "/mkway/engine/mkway.py" in h["command"]]


# ---- the session fixtures: each real install runs once -----------------------------------------------------------

@pytest.fixture(scope="session")
def light_src(tmp_path_factory):
    """An engine source: the fixed set of this repository's files, its `tests/` cut to the one fixture test."""
    src = tmp_path_factory.mktemp("install-src") / "src"
    names = ["mkway.py", "VERSION", "cards/_TEMPLATE/CARD.md", "cards/_TEMPLATE/ORDER.md"]
    for top in ("engine", "tools", "fixtures/synthetic"):
        names += [p.relative_to(REPO).as_posix() for p in (REPO / top).rglob("*") if p.is_file()]
    names += [p.relative_to(REPO).as_posix() for p in (REPO / "tests").glob("*.py") if not p.name.startswith("test_")]
    for rel in names:
        if rel.endswith(".pyc") or "__pycache__" in rel:
            continue
        target = src / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((REPO / rel).read_bytes())
    (src / "tests" / "test_fixture_pass.py").write_bytes((FIXTURES / "check_set_pass.py").read_bytes())
    return src


@pytest.fixture(scope="session")
def git_src(light_src, tmp_path_factory):
    """The same source as a git repository with one commit tagged v0.1.0, and one untracked file."""
    src = tmp_path_factory.mktemp("install-git-src") / "src"
    shutil.copytree(light_src, src)
    _git(src, "init", "-q")
    _git(src, "add", "-A")
    _git(src, "commit", "-q", "-m", "synthetic engine source")
    _git(src, "tag", "v0.1.0")
    (src / "engine" / "untracked.py").write_text("x = 1\n", encoding="utf-8")
    return src


@pytest.fixture(scope="session")
def first(git_src, tmp_path_factory):
    """A git task root after `install --from <git source> --ref v0.1.0`, the home folder holding a planted file."""
    base = tmp_path_factory.mktemp("install-first")
    root = _task(base, git=True)
    home = base / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "settings.json").write_text('{"hooks": {}}', encoding="utf-8")
    before = {p: p.stat().st_mtime_ns for p in home.rglob("*")}
    env = _env(base)
    proc = _mkway(root, env, "install", "--from", str(git_src), "--ref", "v0.1.0")
    assert proc.returncode == 0, proc.stderr + proc.stdout
    return SimpleNamespace(root=root, proc=proc, env=env, src=git_src, home=home, home_before=before, base=base)


@pytest.fixture(scope="session")
def checked(first):
    """`mkway check` on the first install, run once."""
    return _mkway(first.root, first.env, "check")


@pytest.fixture(scope="session")
def plain(light_src, tmp_path_factory):
    """A task root with no git after an install from a plain folder that holds junk the copy must leave out."""
    base = tmp_path_factory.mktemp("install-plain")
    src = base / "src"
    shutil.copytree(light_src, src)
    (src / "engine" / "__pycache__").mkdir()
    (src / "engine" / "__pycache__" / "x.pyc").write_bytes(b"\0")
    (src / ".pytest_tmp" / "junk").mkdir(parents=True)
    (src / "mkway" / "engine").mkdir(parents=True)
    (src / "mkway" / "engine" / "stray.py").write_text("y = 2\n", encoding="utf-8")
    root = _task(base)
    env = _env(base)
    proc = _mkway(root, env, "install", "--from", str(src), "--vcs", "none")
    assert proc.returncode == 0, proc.stderr + proc.stdout
    return SimpleNamespace(root=root, proc=proc, env=env, src=src, base=base)


# ---- E29, E30: what the first install wrote ------------------------------------------------------------------

def test_the_copy_holds_the_files_the_source_tracks(first):
    """E29. Catches: a file of the tracked set missing from, or an extra file in, the copy."""
    tracked = sorted(_git(first.src, "ls-files").split())
    assert _files(first.root / "mkway" / "engine") == tracked


def test_an_untracked_source_file_is_not_copied(first):
    """E29. Catches: a git source read as a plain folder, so an untracked file rides in."""
    assert not (first.root / "mkway" / "engine" / "engine" / "untracked.py").exists()


@pytest.mark.parametrize("rel", ["cards/REGISTER.md", "pytest.ini"])
def test_the_repository_register_and_config_are_not_copied(first, rel):
    """E29. Catches: this repository's own register or config copied into a task."""
    assert not (first.root / "mkway" / "engine" / rel).exists()


def test_the_copy_keeps_the_repository_tree(first):
    """E29 (C12). Catches: files flattened out of their folders."""
    copy = first.root / "mkway" / "engine"
    assert (copy / "mkway.py").is_file() and (copy / "engine" / "mkway.py").is_file()
    assert (copy / "cards" / "_TEMPLATE" / "CARD.md").is_file()


def test_the_lock_names_the_tag_as_the_version(first):
    """E29. Catches: `unversioned` for a source read at a tag."""
    assert _lock(first.root)["version"] == "v0.1.0"


def test_the_lock_names_the_source_commit(first):
    """E29. Catches: a lock that cannot be traced to the commit it was copied from."""
    assert _lock(first.root)["source_sha"] == _git(first.src, "rev-parse", "v0.1.0^{commit}").strip()


def test_the_lock_hash_is_the_hash_of_the_copy_on_disk(first):
    """E29, MW-051 E1. Catches: a recorded hash that differs from the bytes written."""
    assert _lock(first.root)["hash"] == _disk_hash(first.root / "mkway" / "engine")


def test_the_lock_has_exactly_the_five_keys(first):
    """E29, MW-016 E3. Catches: a path or a machine detail added to the lock."""
    assert set(_lock(first.root)) == {"version", "semver", "source_sha", "date", "hash"}


def test_the_lock_holds_the_semver_of_the_sources_version_file(first):
    """MW-016 E3. Catches: `semver` taken from the tag or left null."""
    assert _lock(first.root)["semver"] == (first.src / "VERSION").read_text(encoding="utf-8").strip()


def test_the_lock_holds_no_path_of_this_machine(first):
    """E29. Catches: a machine path in a tracked file."""
    text = (first.root / "mkway" / "mkway.lock").read_text(encoding="utf-8")
    assert str(first.root) not in text and first.root.as_posix() not in text


@pytest.mark.parametrize("name", ["cards", "ledger", "locks", "state"])
def test_install_creates_the_bundle_folders(first, name):
    """E30. Catches: a folder the gates write into that does not exist."""
    assert (first.root / "mkway" / name).is_dir()


def test_the_card_template_stays_in_the_copy_not_in_cards(first):
    """E30. Catches: the template copied into the live cards folder."""
    assert not (first.root / "mkway" / "cards" / "_TEMPLATE").exists()


def test_the_starter_profile_says_git_and_the_default_folders(first):
    """E30. Catches: a starter that has the wrong vcs, prefix or folders."""
    profile = json.loads((first.root / "mkway" / "profile.json").read_text(encoding="utf-8"))
    assert profile["vcs"] == "git" and profile["ids"]["card_prefix"] == "CARD"
    assert (profile["bundle"]["root"], profile["state"]["dir"]) == ("mkway", "mkway/state")


@pytest.mark.parametrize("rel", ["mkway/locks/x", "mkway/state/x", "mkway/engine/__pycache__/x.pyc"])
def test_git_ignores_the_runtime_files(first, rel):
    """E30, E67, MW-027 E1. Catches: a lock, a state file or bytecode offered to the first `git add`."""
    assert subprocess.run(["git", "check-ignore", "-q", rel], cwd=str(first.root)).returncode == 0


@pytest.mark.parametrize("rel", ["mkway/engine/mkway.py", "mkway/profile.json", "mkway/mkway.lock", "mkway/cards/x.md",
                                 "mkway/ledger/x.md", "mkway/.gitignore", "mkway/cards/", "mkway/ledger/"])
def test_git_does_not_ignore_what_the_task_tracks(first, rel):
    """E67 (R18), MW-027. Catches: the copy, the profile, the lock, a card or the ledger ignored, so a fresh worktree
    has no install."""
    assert subprocess.run(["git", "check-ignore", "-q", rel], cwd=str(first.root)).returncode == 1


def test_the_bundle_ignore_file_names_the_runtime_lines_only(first):
    """E67. Catches: an ignore file that holds `engine/`, `cards/` or `ledger/`."""
    lines = [x for x in (first.root / "mkway" / ".gitignore").read_text(encoding="utf-8").splitlines()
             if x and not x.startswith("#")]
    assert lines == ["locks/", "state/", "__pycache__/", "*.pyc", ".pytest_tmp/", ".pytest_cache/"]


def test_the_engine_copy_is_never_converted_by_git(first):
    """MW-027 E8. Catches: a checkout with autocrlf changing the copy's bytes and so its hash."""
    out = _git(first.root, "check-attr", "text", "mkway/engine/mkway.py")
    assert out.strip().endswith("text: unset")


def test_the_register_is_never_converted_by_git(first):
    """MW-003 E19 (R19c). Catches: the sealed register changing its line ends on a Windows clone."""
    out = _git(first.root, "check-attr", "text", "mkway/cards/REGISTER.md")
    assert out.strip().endswith("text: unset")


def test_the_committed_settings_hold_each_owned_command_once(first):
    """E31, MW-027 E2. Catches: a hook that runs twice."""
    owned = _owned(first.root)
    assert owned and len(owned) == len(set(owned))


def test_the_committed_settings_carry_the_profiles_interpreter(first):
    """MW-027. Catches: the machine's own interpreter committed for every clone."""
    command = _settings(first.root)["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    assert command.startswith('python -I -X utf8 "${CLAUDE_PROJECT_DIR}/mkway/engine/mkway.py" hook SessionStart')


def test_no_local_settings_file_is_written(first):
    """MW-027 E2. Catches: entries written into the owner's per-machine file."""
    assert not (first.root / ".claude" / "settings.local.json").exists()


def test_the_machine_file_holds_the_interpreter_used(first):
    """E47 (C27). Catches: the per-machine interpreter missing from the untracked state folder."""
    machine = json.loads((first.root / "mkway" / "state" / "machine.json").read_text(encoding="utf-8"))
    assert machine == {"python": "python"}


def test_install_leaves_the_home_folder_alone(first):
    """E32. Catches: a read-modify-write of the user's own settings under their home."""
    assert {p: p.stat().st_mtime_ns for p in first.home.rglob("*")} == first.home_before


# ---- MW-027 E5, MW-035 E3, MW-036 E2: the printed line ------------------------------------------------------------

def test_the_last_line_is_the_one_commit_line_with_the_root_and_the_first_runs_paths(first):
    """MW-027 E5, MW-035 E3, MW-036 E2, MW-041 E1. Catches: a line that needs the task folder as the current folder, or
    one that takes the whole bundle folder."""
    version = (first.src / "VERSION").read_text(encoding="utf-8").strip()
    root = f'git -C "{first.root.resolve().as_posix()}"'
    paths = FIRST_PATHS + " .claude/agents/fresh-reader.md"  # MW116-D3: the reader agent file is an install path
    expected = f'{root} add {paths}; {root} commit -m "mkway {version}: install" -- {paths}'
    assert first.proc.stdout.splitlines()[-1] == expected


def test_no_printed_line_starts_with_a_space(first):
    """MW-035 E3. Catches: a leading space that breaks the line pasted into PowerShell."""
    lines = first.proc.stdout.splitlines()
    assert [x for x in lines if x != x.lstrip()] == []


def test_a_vcs_none_install_prints_no_commit_line(plain):
    """MW-027 E5. Catches: a commit line printed for a task with no repository."""
    assert " commit " not in plain.proc.stdout and " add " not in plain.proc.stdout


# ---- E29, E30, MW-027 E1: the install of a plain folder -------------------------------------------------------------

def test_a_plain_folder_copy_leaves_bytecode_caches_and_a_stray_copy_out(plain):
    """E29. Catches: `__pycache__`, `.pytest_tmp` or a nested `mkway/` folder of the source copied."""
    files = _files(plain.root / "mkway" / "engine")
    assert [f for f in files if "__pycache__" in f or f.startswith((".pytest_tmp/", "mkway/"))] == []


def test_a_plain_folder_copy_holds_every_other_source_file(plain):
    """E29. Catches: a file of the set missing from the copy of a folder source."""
    wanted = [f for f in _files(plain.src) if not f.startswith(("mkway/", ".pytest_tmp/")) and "__pycache__" not in f]
    assert _files(plain.root / "mkway" / "engine") == wanted


def test_a_plain_folder_source_is_unversioned_with_no_sha(plain):
    """E29. Catches: a made-up version or sha for a folder."""
    lock = _lock(plain.root)
    assert (lock["version"], lock["source_sha"]) == ("unversioned", None)


def test_the_bundle_ignore_file_is_written_whatever_the_profiles_vcs(plain):
    """E30, MW-027 E1. Catches: a task with vcs none that offers its run-time files to a `git add`."""
    lines = (plain.root / "mkway" / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert {"state/", "locks/", "__pycache__/", ".pytest_tmp/"} <= set(lines) and "engine/" not in lines


def test_no_ignore_file_is_written_at_the_task_root(plain):
    """E30. Catches: a `.gitignore` written outside the bundle."""
    assert not (plain.root / ".gitignore").exists()


def test_the_vcs_none_profile_says_none(plain):
    """E30. Catches: the argument `--vcs none` ignored."""
    assert json.loads((plain.root / "mkway" / "profile.json").read_text(encoding="utf-8"))["vcs"] == "none"


# ---- E33, E51, E53, MW-016 E4, MW-025 E3: check ---------------------------------------------------------------------

def test_check_of_a_fresh_install_exits_zero(checked):
    """E33. Catches: a clean install that fails its own check."""
    assert checked.returncode == 0, checked.stdout + checked.stderr


def test_check_says_the_hash_matches_the_lock(checked):
    """E33. Catches: a check that does not compare the copy with the lock."""
    assert "copy hash: matches the lock" in checked.stdout


def test_check_runs_exactly_the_copys_one_test(checked):
    """E33, MW-013. Catches: a check that runs the engine repository's whole suite, or none."""
    assert "tests: 1 passed" in checked.stdout


def test_check_without_a_term_file_says_the_scan_was_skipped(checked):
    """E33. Catches: a silent pass of the term scan."""
    assert "term scan: skipped, no term list set" in checked.stdout


def _copy_of(first, tmp_path):
    target = tmp_path / "task"
    shutil.copytree(first.root, target)
    return target


def test_check_with_one_changed_byte_fails_and_names_the_fix(first, tmp_path):
    """E33, MW-051 E4. Catches: a copy changed after install that still passes."""
    root = _copy_of(first, tmp_path)
    keys = root / "mkway" / "engine" / "engine" / "KEYS.md"
    keys.write_bytes(keys.read_bytes() + b" ")
    proc = _mkway(root, first.env, "check")
    assert proc.returncode == 1
    assert "copy hash: differs from the lock (fix: mkway install)" in proc.stdout


def test_check_with_a_missing_term_file_fails_with_a_clean_line(first, tmp_path):
    """E51. Catches: a traceback, or a pass, when `ENGINE_TERMS_FILE` names a missing file."""
    root = _copy_of(first, tmp_path)
    proc = _mkway(root, dict(first.env, ENGINE_TERMS_FILE=str(tmp_path / "missing.txt")), "check")
    assert proc.returncode == 1
    assert "term scan: term list missing (ENGINE_TERMS_FILE)" in proc.stdout and "Traceback" not in proc.stderr


def test_check_with_a_term_file_reports_the_counts(first, tmp_path):
    """E53. Catches: the scan path raising when a term list is set (found by E51)."""
    terms = tmp_path / "terms.txt"
    terms.write_text("re:zzqq-no-such-text-zzqq\n", encoding="utf-8")
    root = _copy_of(first, tmp_path)
    proc = _mkway(root, dict(first.env, ENGINE_TERMS_FILE=str(terms)), "check")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert re.search(r"term scan: 1 entries, 0 hits, \d+ exceptions", proc.stdout)


def test_check_names_the_tests_of_the_copy_that_fail(first, tmp_path):
    """MW-025 E3. Catches: a red run reported as a count with no test names."""
    root = _copy_of(first, tmp_path)
    (root / "mkway" / "engine" / "tests" / "test_fixture_fail.py").write_text(
        "def test_one_fails():\n    assert False\n\n\ndef test_two_fails():\n    assert False\n", encoding="utf-8")
    proc = _mkway(root, first.env, "check")
    line = next(x for x in proc.stdout.splitlines() if x.startswith("tests:"))
    assert "test_fixture_fail.py::test_one_fails" in line and "test_fixture_fail.py::test_two_fails" in line


def test_check_leaves_the_copy_as_it_found_it(first, tmp_path):
    """MW-032 E1. Catches: test scratch written into the copy, which a reinstall then cannot remove."""
    root = _copy_of(first, tmp_path)
    before = _files(root / "mkway" / "engine")
    assert _mkway(root, first.env, "check").returncode == 0
    assert _files(root / "mkway" / "engine") == before


def test_the_scratch_of_the_copys_tests_lives_under_the_state_folder(first, tmp_path):
    """MW-032 E2. Catches: test scratch written under the copy, where a reinstall cannot remove a read-only file."""
    root = _copy_of(first, tmp_path)
    (root / "mkway" / "engine" / "tests" / "test_fixture_scratch.py").write_text(
        "def test_leaves_a_file(tmp_path):\n    (tmp_path / 'scratch-marker.txt').write_text('x')\n", encoding="utf-8")
    _mkway(root, first.env, "check")
    assert len(list((root / "mkway" / "state" / "check" / "tmp").rglob("scratch-marker.txt"))) == 1
    assert list((root / "mkway" / "engine").rglob("scratch-marker.txt")) == []


def _scratch_repo(base, tags):
    root = Path(base) / "scratch"
    root.mkdir()
    _git(root, "init", "-q")
    (root / "VERSION").write_text("0.1.0\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "scratch")
    for tag in tags:
        _git(root, "tag", tag)
    return root


@pytest.mark.parametrize("tags,words", [([], ("warning", "v0.1.0", "missing")),
                                        (["v0.0.9"], ("warning", "v0.1.0", "v0.0.9", "differs")),
                                        (["v0.1.0"], ("v0.1.0 at HEAD matches VERSION",))])
def test_the_tag_line_reads_the_tags_at_head(tmp_path, tags, words):
    """MW-016 E4. Catches: tags read from the wrong place, or a tag that is not `v<version>` accepted."""
    line = install.version_tag_line(_scratch_repo(tmp_path, tags), {})
    assert all(w in line for w in words)


def test_the_tag_line_writes_no_tag(tmp_path):
    """MW-016 E4. Catches: a check that tags the release itself."""
    root = _scratch_repo(tmp_path, [])
    install.version_tag_line(root, {})
    assert _git(root, "tag").split() == []


def test_a_root_without_a_version_file_has_no_tag_line(tmp_path):
    """MW-016 E4. Catches: a tag line for a root with no VERSION."""
    root = _scratch_repo(tmp_path, [])
    (root / "VERSION").unlink()
    assert install.version_tag_line(root, {}) is None


def test_in_a_claude_chat_the_tag_line_does_not_read_git(tmp_path):
    """MW-016 E4. Catches: a tag read in a chat shell."""
    line = install.version_tag_line(_scratch_repo(tmp_path, []), {"CLAUDECODE": "1"})
    assert line.startswith("version tag: not compared inside a Claude chat")


def test_check_prints_the_tag_warning_for_a_task_with_a_version_file(light_src, tmp_path):
    """MW-016 E4. Catches: a check that never calls the tag comparison."""
    root = _task(tmp_path, git=True)
    (root / "VERSION").write_text("0.1.0\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "task")
    env = _env(tmp_path)
    assert _mkway(root, env, "install", "--from", str(light_src), "--vcs", "git").returncode == 0
    proc = _mkway(root, env, "check")
    assert "version tag: warning" in proc.stdout and "v0.1.0" in proc.stdout, proc.stdout + proc.stderr
    assert _git(root, "tag").strip() == ""


# ---- E49, E50, E52, E59: the refusals through the real command -----------------------------------------------------

def test_a_profile_outside_the_root_is_refused_before_any_write(light_src, tmp_path):
    """E49. Catches: a profile written outside the task folder, or a traceback."""
    root = _task(tmp_path)
    outside = tmp_path / "outside" / "p.json"
    proc = _mkway(root, _env(tmp_path), "install", "--from", str(light_src), "--vcs", "none", "--profile", str(outside))
    assert proc.returncode == 1 and "outside the root" in proc.stderr and "Traceback" not in proc.stderr
    assert not outside.parent.exists() and not (root / "mkway").exists() and not (root / ".claude").exists()


def _link(link, target):
    try:
        os.symlink(str(target), str(link), target_is_directory=True)
        return
    except (OSError, NotImplementedError):
        pass
    try:
        import _winapi
        _winapi.CreateJunction(str(target), str(link))
    except (ImportError, AttributeError, OSError):
        pytest.skip("neither a symlink nor a junction can be made here")


def test_a_bundle_that_is_a_link_out_of_the_root_is_refused(light_src, tmp_path):
    """E50. Catches: a copy written through a link into a folder outside the root."""
    outside = tmp_path / "outside"
    outside.mkdir()
    root = _task(tmp_path)
    _link(root / "mkway", outside)
    proc = _mkway(root, _env(tmp_path), "install", "--from", str(light_src), "--vcs", "none")
    assert proc.returncode == 1 and "outside the root" in proc.stderr and "Traceback" not in proc.stderr
    assert list(outside.iterdir()) == []


def test_an_engine_copy_that_is_a_link_out_of_the_root_is_not_replaced(light_src, plain, tmp_path):
    """E50. Catches: the re-install delete following a link, so a folder outside the root is emptied."""
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")
    root = tmp_path / "task"
    (root / "mkway").mkdir(parents=True)
    shutil.copy(plain.root / "mkway" / "profile.json", root / "mkway" / "profile.json")
    (root / "mkway" / "mkway.lock").write_text("{}", encoding="utf-8")
    _link(root / "mkway" / "engine", outside)
    proc = _mkway(root, _env(tmp_path), "install", "--from", str(light_src), "--vcs", "none")
    assert proc.returncode == 1 and "outside the root" in proc.stderr
    assert [p.name for p in outside.iterdir()] == ["keep.txt"]


def test_a_profile_that_says_git_in_a_folder_with_no_work_tree_still_installs(light_src, tmp_path):
    """E52. Catches: an install that fails when git cannot answer about the folder."""
    root = _task(tmp_path)
    (root / "mkway").mkdir()
    (root / "mkway" / "profile.json").write_text(json.dumps({
        "vcs": "git", "bundle": {"root": "mkway"}, "gates": {}, "state": {"dir": "mkway/state"},
        "python": {"command": "python"}}), encoding="utf-8")
    proc = _mkway(root, _env(tmp_path), "install", "--from", str(light_src))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (root / "mkway" / ".gitignore").is_file() and "Traceback" not in proc.stderr


def _refused_python(light_src, tmp_path, value, env=None):
    root = _task(tmp_path)
    proc = _mkway(root, env or _env(tmp_path), "install", "--from", str(light_src), "--vcs", "none", "--python", value)
    return root, proc


def test_a_python_with_a_shell_character_is_refused_and_nothing_is_written(light_src, tmp_path):
    """E59. Catches: shell text accepted as an interpreter, or a half-written task folder."""
    root, proc = _refused_python(light_src, tmp_path, "exit 0 || python")
    assert proc.returncode == 1 and proc.stderr.startswith("mkway: --python") and "Traceback" not in proc.stderr
    assert list(root.iterdir()) == []


def test_a_program_that_is_not_a_python_is_refused(light_src, tmp_path):
    """E59 (M1). Catches: any executable accepted, not only one that reports a Python version."""
    other = '"' + str(fake_program(tmp_path / "bin", "notpython", prints="hello")) + '"'
    root, proc = _refused_python(light_src, tmp_path, other)
    assert proc.returncode == 1 and list(root.iterdir()) == []


def test_a_python_older_than_3_9_is_refused(light_src, tmp_path):
    """E59 (M1). Catches: Python 3.8 accepted."""
    old = '"' + str(fake_program(tmp_path / "bin", "oldpython", prints="(3, 8)")) + '"'
    root, proc = _refused_python(light_src, tmp_path, old)
    assert proc.returncode == 1 and list(root.iterdir()) == []


def test_a_program_that_does_not_exist_is_refused(light_src, tmp_path):
    """E59. Catches: a missing program written into every hook command."""
    root, proc = _refused_python(light_src, tmp_path, '"' + str(tmp_path / "none" / "python.exe") + '"')
    assert proc.returncode == 1 and list(root.iterdir()) == []


def test_python_3_9_is_accepted(light_src, tmp_path):
    """E59 (the boundary, the nearest allow). Catches: the lowest supported Python refused."""
    ok = '"' + str(fake_program(tmp_path / "bin", "py39", prints="(3, 9)")) + '"'
    root, proc = _refused_python(light_src, tmp_path, ok)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_the_launcher_with_a_minor_version_flag_is_accepted(light_src, tmp_path):
    """E59 (C34, the nearest allow). Catches: `py -3.12` refused."""
    fake = fake_program(tmp_path / "launcher", "py", forward_after_first=True)
    env = _env(tmp_path, PATH=str(fake.parent) + os.pathsep + os.environ.get("PATH", ""))
    _root, proc = _refused_python(light_src, tmp_path, "py -3.12", env)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_the_interpreter_used_is_recorded_in_the_machine_file(light_src, tmp_path):
    """E59, E47. Catches: the machine file naming another interpreter than the one the install ran with."""
    quoted = '"' + sys.executable + '"'
    root, proc = _refused_python(light_src, tmp_path, quoted)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert json.loads((root / "mkway" / "state" / "machine.json").read_text(encoding="utf-8")) == {"python": quoted}


# ---- MW-003 E19: the register seal ---------------------------------------------------------------------------------

REG = "mkway/cards/REGISTER.md"
ROW = "| CARD-001 | First | open |  | `mkway/cards/CARD-001-first` |\n"
HEAD_TEXT = "# Card register\n\n| Id | Title | Status | Paths | Folder |\n|---|---|---|---|---|\n"


def _task_with_register(light_src, tmp_path, *, git):
    root = _task(tmp_path, git=git)
    (root / "mkway" / "cards").mkdir(parents=True)
    (root / REG).write_bytes((HEAD_TEXT + ROW).encode("utf-8"))
    if git:
        (root / "mkway" / ".gitattributes").write_text("*.png binary\n", encoding="utf-8")
        _git(root, "add", "-A")
        _git(root, "commit", "-q", "-m", "start")
    return root


def test_install_seals_a_register_that_equals_the_head_blob(light_src, tmp_path):
    """MW-003 E19 (R19a). Catches: a committed register left unsealed, so the first card command is refused."""
    root = _task_with_register(light_src, tmp_path, git=True)
    assert _mkway(root, _env(tmp_path), "install", "--from", str(light_src)).returncode == 0
    assert (root / "mkway" / "state" / "register.sha").is_file()


def test_install_does_not_seal_a_register_that_differs_from_head(light_src, tmp_path):
    """MW-003 E19 (R19a). Catches: a seal written over an uncommitted (possibly forged) register."""
    root = _task_with_register(light_src, tmp_path, git=True)
    (root / REG).write_bytes((HEAD_TEXT + ROW.replace("open", "closed")).encode("utf-8"))
    proc = _mkway(root, _env(tmp_path), "install", "--from", str(light_src))
    assert proc.returncode == 0 and "differs from HEAD" in proc.stdout
    assert not (root / "mkway" / "state" / "register.sha").exists()


def test_install_keeps_the_other_lines_of_the_attributes_file(light_src, tmp_path):
    """MW-003 E19 (R19c). Catches: an attributes file rewritten, so the owner's own lines are lost."""
    root = _task_with_register(light_src, tmp_path, git=True)
    assert _mkway(root, _env(tmp_path), "install", "--from", str(light_src)).returncode == 0
    lines = (root / "mkway" / ".gitattributes").read_text(encoding="utf-8").splitlines()
    assert "*.png binary" in lines and "cards/REGISTER.md -text" in lines


def test_install_without_git_seals_the_register_as_it_is(light_src, tmp_path):
    """MW-003 E19 (C45). Catches: a task with vcs none whose first card command is refused as tampered."""
    root = _task_with_register(light_src, tmp_path, git=False)
    assert _mkway(root, _env(tmp_path), "install", "--from", str(light_src), "--vcs", "none").returncode == 0
    assert (root / "mkway" / "state" / "register.sha").is_file()


# ---- the commit step on a real repository (MW-027 E6, MW-035, MW-036, MW-041) -----------------------------------------

def _version(src):
    return (src / "VERSION").read_text(encoding="utf-8").strip()


def test_install_commit_takes_only_install_paths_and_leaves_a_staged_file(light_src, tmp_path):
    """MW-035 E2. Catches: a plain `git commit` that takes the whole index, a builder's staged file included."""
    root = _task(tmp_path, git=True)
    (root / "base.txt").write_text("b\n", encoding="utf-8")
    _git(root, "add", "base.txt")
    _git(root, "commit", "-q", "-m", "base")
    (root / "foreign.txt").write_text("f\n", encoding="utf-8")
    _git(root, "add", "foreign.txt")
    done = _mkway(root, _env(tmp_path, **COMMIT_ENV), "install", "--from", str(light_src), "--commit")
    assert done.returncode == 0, done.stderr + done.stdout
    taken = _git(root, "show", "--name-only", "--format=", "HEAD").split()
    assert "foreign.txt" not in taken and ".claude/settings.json" in taken and "mkway/engine/mkway.py" in taken
    assert _git(root, "diff", "--cached", "--name-only").split() == ["foreign.txt"]


def test_install_commit_has_the_message_and_leaves_the_tree_clean(light_src, tmp_path):
    """MW-027 E6. Catches: a commit with another message, or files of install left out of it."""
    root = _task(tmp_path, git=True)
    done = _mkway(root, _env(tmp_path, **COMMIT_ENV), "install", "--from", str(light_src), "--commit")
    assert done.returncode == 0, done.stderr + done.stdout
    assert _git(root, "log", "-1", "--format=%s").strip() == f"mkway {_version(light_src)}: install"
    assert _git(root, "status", "--porcelain").strip() == ""


def test_install_commit_in_a_claude_chat_is_refused_and_commits_nothing(light_src, tmp_path):
    """MW-027 E6. Catches: a session that commits as the owner."""
    root = _task(tmp_path, git=True)
    chat = _mkway(root, _env(tmp_path, CLAUDECODE="1", **COMMIT_ENV), "install", "--from", str(light_src), "--commit")
    assert chat.returncode != 0 and "owner-only-command" in chat.stderr + chat.stdout
    assert subprocess.run(["git", "rev-parse", "--verify", "-q", "HEAD"], cwd=str(root)).returncode != 0


def test_install_commit_with_vcs_none_is_refused(light_src, tmp_path):
    """MW-027 E6. Catches: `--commit` run in a task whose profile says none."""
    root = _task(tmp_path)
    bad = _mkway(root, _env(tmp_path, **COMMIT_ENV), "install", "--from", str(light_src), "--vcs", "none", "--commit")
    assert bad.returncode != 0 and "--commit needs vcs git" in bad.stderr + bad.stdout


def test_the_message_prefix_starts_the_commit_message(light_src, tmp_path):
    """MW-035 E4. Catches: a profile prefix ignored by the commit the install makes."""
    root = _task(tmp_path, git=True)
    (root / "mkway").mkdir()
    (root / "mkway" / "profile.json").write_text(json.dumps({
        "vcs": "git", "bundle": {"root": "mkway"}, "gates": {}, "state": {"dir": "mkway/state"},
        "python": {"command": "python"}, "commit": {"message_prefix": "#10536"}}), encoding="utf-8")
    done = _mkway(root, _env(tmp_path, **COMMIT_ENV), "install", "--from", str(light_src), "--commit")
    assert done.returncode == 0, done.stderr + done.stdout
    assert _git(root, "log", "-1", "--format=%s").strip() == f"#10536 mkway {_version(light_src)}: install"


def test_a_reinstall_commit_leaves_the_session_files_of_the_bundle_out(light_src, tmp_path):
    """MW-036 E1. Catches: a lead's untracked ask or an edited card riding into the install commit."""
    root = _task(tmp_path, git=True)
    env = _env(tmp_path, **COMMIT_ENV)
    assert _mkway(root, env, "install", "--from", str(light_src), "--commit").returncode == 0
    lock = root / "mkway" / "mkway.lock"  # an older date, committed, so the reinstall has a change to take
    lock.write_text(re.sub(r'"date": "[^"]*"', '"date": "2000-01-01"', lock.read_text(encoding="utf-8")),
                    encoding="utf-8")
    _git(root, "commit", "-q", "-m", "older lock", "--", "mkway/mkway.lock")
    card = root / "mkway" / "cards" / "T-1" / "CARD.md"
    card.parent.mkdir(parents=True)
    card.write_text("one\n", encoding="utf-8")
    _git(root, "add", "-f", "mkway/cards/T-1/CARD.md")
    _git(root, "commit", "-q", "-m", "card", "--", "mkway/cards/T-1/CARD.md")
    card.write_text("one\ntwo\n", encoding="utf-8")
    (root / "mkway" / "asks").mkdir()
    (root / "mkway" / "asks" / "x.md").write_text("ask\n", encoding="utf-8")
    assert _mkway(root, env, "install", "--from", str(light_src), "--commit").returncode == 0
    assert _git(root, "show", "--name-only", "--format=", "HEAD").split() == ["mkway/mkway.lock"]
    status = _git(root, "status", "--porcelain").splitlines()
    assert " M mkway/cards/T-1/CARD.md" in status and any(x.startswith("??") and x.endswith("mkway/asks/") for x in status)


def test_a_stale_engine_ignore_line_is_removed_and_the_copy_is_then_tracked(light_src, tmp_path):
    """MW-035 E1, MW-027 E9. Catches: an earlier install's `engine/` line leaving the copy untracked."""
    root = _task(tmp_path, git=True)
    (root / "mkway").mkdir()
    (root / "mkway" / ".gitignore").write_text("engine/\nlocks/\nmine.tmp\nengine/cache/\nengine.log\n", encoding="utf-8")
    proc = _mkway(root, _env(tmp_path), "install", "--from", str(light_src))
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "ignore: removed engine/ (from an earlier install)" in proc.stdout.splitlines()
    _git(root, "add", "-A")
    assert "mkway/engine/mkway.py" in _git(root, "diff", "--cached", "--name-only").split()


def test_an_earlier_cards_and_ledger_ignore_line_is_named_not_removed(light_src, tmp_path):
    """E72 (C36). Catches: an old `cards/` line deleted, or left unreported."""
    root = _task(tmp_path, git=True)
    (root / "mkway").mkdir()
    (root / "mkway" / ".gitignore").write_text("cards/\nledger/\nlocks/\nstate/\n", encoding="utf-8")
    proc = _mkway(root, _env(tmp_path), "install", "--from", str(light_src))
    (line,) = [x for x in proc.stdout.splitlines() if x.startswith("ignore:") and "R18" in x]
    assert "cards/" in line and "ledger/" in line
    assert {"cards/", "ledger/"} <= set((root / "mkway" / ".gitignore").read_text(encoding="utf-8").splitlines())


def _bash():
    exe = shutil.which("git")
    if exe:  # on Windows the plain `bash` on the path may be the WSL one; Git's own is beside `git`
        beside = Path(exe).resolve().parent.parent / "bin" / "bash.exe"
        if beside.is_file():
            return [str(beside), "-c"]
    found = shutil.which("bash")
    return [found, "-c"] if found else None


def _powershell():
    found = shutil.which("pwsh") or shutil.which("powershell")
    return [found, "-NoProfile", "-NonInteractive", "-Command"] if found else None


def _run_printed_line(shell, light_src, tmp_path, name):
    command = shell()
    if command is None:
        pytest.skip("shell not available")
    root = _task(tmp_path, name, git=True)
    env = _env(tmp_path, **COMMIT_ENV)
    proc = _mkway(root, env, "install", "--from", str(light_src))
    assert proc.returncode == 0, proc.stderr + proc.stdout
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    done = subprocess.run([*command, proc.stdout.splitlines()[-1]], cwd=str(elsewhere), capture_output=True, text=True,
                          env=env, timeout=300)
    assert done.returncode == 0, done.stderr + done.stdout
    return root


@pytest.mark.parametrize("shell", [pytest.param(_bash, id="bash"), pytest.param(_powershell, id="powershell")])
def test_the_printed_line_commits_install_paths_when_run_from_another_folder(light_src, tmp_path, shell):
    """MW-041 E1. Catches: a printed line that works only from the task folder."""
    root = _run_printed_line(shell, light_src, tmp_path, "task")
    taken = _git(root, "show", "--name-only", "--format=", "HEAD").split()
    assert ".claude/settings.json" in taken and "mkway/mkway.lock" in taken and "mkway/engine/mkway.py" in taken
    assert _git(root, "log", "-1", "--format=%s").strip() == f"mkway {_version(light_src)}: install"


@pytest.mark.parametrize("shell", [pytest.param(_bash, id="bash"), pytest.param(_powershell, id="powershell")])
def test_the_printed_line_commits_when_the_root_holds_a_space(light_src, tmp_path, shell):
    """MW-041 E2. Catches: a root with a space split into two words by the shell."""
    root = _run_printed_line(shell, light_src, tmp_path, "my task")
    assert ".claude/settings.json" in _git(root, "show", "--name-only", "--format=", "HEAD").split()


# ---- reinstall (MW-032 E3 to E6) and the hash written once (MW-051 E1 to E3) ----------------------------------------

@pytest.fixture
def again(plain, tmp_path):
    """A private copy of the plain install, to be installed over again."""
    root = tmp_path / "task"
    shutil.copytree(plain.root, root)
    return root


def test_a_reinstall_leaves_the_lock_matching_the_copy_and_one_engine_folder(again, plain):
    """MW-032 E3. Catches: a leftover `engine.old` or `engine.new` folder, or a lock that no longer matches."""
    assert _mkway(again, plain.env, "install", "--from", str(plain.src), "--vcs", "none").returncode == 0
    assert _lock(again)["hash"] == _disk_hash(again / "mkway" / "engine")
    assert sorted(p.name for p in (again / "mkway").iterdir() if p.name.startswith("engine")) == ["engine"]


def test_a_reinstall_replaces_a_copy_that_holds_a_read_only_file(again, plain):
    """MW-032 E4. Catches: a traceback on Windows when the old copy holds a read-only file, as the object files of a
    test repository are."""
    folder = again / "mkway" / "engine" / ".pytest_tmp" / "t0" / ".git" / "objects" / "03"
    folder.mkdir(parents=True)
    planted = folder / "3e8f"
    planted.write_text("x", encoding="utf-8")
    os.chmod(planted, stat.S_IREAD)
    proc = _mkway(again, plain.env, "install", "--from", str(plain.src), "--vcs", "none")
    assert proc.returncode == 0 and "Traceback" not in proc.stdout + proc.stderr
    assert not planted.exists() and (again / "mkway" / "engine" / "engine" / "mkway.py").is_file()


def test_a_failed_removal_leaves_the_new_copy_and_names_the_leftover(again, plain, monkeypatch):
    """MW-032 E5. Catches: an install that fails, or stays silent, when the old copy cannot be removed."""
    bundle = again / "mkway"
    (bundle / "engine" / "OLD-MARKER.txt").write_text("old\n", encoding="utf-8")

    def refuse(*_args, **_kwargs):
        raise PermissionError(5, "Access is denied")
    monkeypatch.setattr(install.shutil, "rmtree", refuse)
    report = install.install(again, plain.src, vcs="none")
    monkeypatch.undo()
    (left,) = [p for p in bundle.iterdir() if p.name.startswith("engine") and p.name != "engine"]
    assert (left / "OLD-MARKER.txt").is_file() and not (bundle / "engine" / "OLD-MARKER.txt").exists()
    assert len([x for x in report if left.name in x and "leftover" in x]) == 1


def test_a_failed_swap_puts_the_old_copy_back_and_refuses_in_one_line(again, plain, monkeypatch):
    """MW-032 E6. Catches: a half-replaced copy after a failed rename."""
    bundle = again / "mkway"
    (bundle / "engine" / "OLD-MARKER.txt").write_text("old\n", encoding="utf-8")
    before, lock_text = _files(bundle / "engine"), (bundle / "mkway.lock").read_text(encoding="utf-8")
    real = os.replace

    def failing(source, target, *args, **kwargs):
        if os.path.basename(os.fspath(source)) == "engine.new":
            raise PermissionError(5, "Access is denied")
        return real(source, target, *args, **kwargs)
    monkeypatch.setattr(install.os, "replace", failing)
    with pytest.raises(install.InstallError) as info:
        install.install(again, plain.src, vcs="none")
    monkeypatch.undo()
    assert "\n" not in str(info.value) and _files(bundle / "engine") == before
    assert (bundle / "mkway.lock").read_text(encoding="utf-8") == lock_text
    assert sorted(p.name for p in bundle.iterdir() if p.name.startswith("engine")) == ["engine"]


def _no_second_read(monkeypatch):
    def refuse(copy):
        raise AssertionError(f"install read the copy again: copy_hash({copy})")
    monkeypatch.setattr(install, "copy_hash", refuse)


def test_install_records_the_hash_of_the_disk_without_reading_the_copy_back(tmp_path, light_src, monkeypatch):
    """MW-051 E1. Catches: a second pass over the fresh copy, or a recorded hash that is not the disk's."""
    _no_second_read(monkeypatch)
    root = _task(tmp_path)
    install.install(root, light_src, vcs="none")
    assert _lock(root)["hash"] == _disk_hash(root / "mkway" / "engine")


def test_a_reinstall_from_a_changed_source_records_the_new_disk_hash(tmp_path, light_src, monkeypatch):
    """MW-051 E2. Catches: the old hash kept, or the copy read back."""
    src = tmp_path / "src"
    shutil.copytree(light_src, src)
    root = _task(tmp_path)
    install.install(root, src, vcs="none")
    first_hash = _lock(root)["hash"]
    (src / "engine" / "helpers.py").write_bytes((src / "engine" / "helpers.py").read_bytes() + b"\n# changed\n")
    _no_second_read(monkeypatch)
    install.install(root, src, vcs="none")
    assert _lock(root)["hash"] != first_hash and _lock(root)["hash"] == _disk_hash(root / "mkway" / "engine")


def test_a_copy_with_crlf_files_records_the_hash_of_those_bytes(tmp_path, light_src, monkeypatch):
    """MW-051 E3. Catches: a file written with converted line ends, so the lock hashes other bytes than the disk."""
    src = tmp_path / "src"
    shutil.copytree(light_src, src)
    (src / "fixtures" / "synthetic" / "crlf_sample.txt").write_bytes(b"one\r\ntwo\r\nthree\r\n")
    _no_second_read(monkeypatch)
    root = _task(tmp_path)
    install.install(root, src, vcs="none")
    copy = root / "mkway" / "engine"
    assert (copy / "fixtures" / "synthetic" / "crlf_sample.txt").read_bytes() == b"one\r\ntwo\r\nthree\r\n"
    assert _lock(root)["hash"] == _disk_hash(copy)
