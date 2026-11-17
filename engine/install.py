"""`mkway install` and `mkway check` (card MW-002, deliverable 7; R9).

install --from <engine repo> [--ref <sha or tag>] into a task root:
- copies the fixed file set into `<root>/<bundle.root>/engine/`, keeping the repository tree (decision C12).
  Set: `mkway.py`, `engine/`, `tools/`, `tests/`, `fixtures/synthetic/`, `cards/_TEMPLATE/CARD.md` (C13, C21).
  From a git source: the files tracked at the ref. From a plain folder: its set files, without `.git`,
  `__pycache__`, `.pytest_tmp` and `mkway/`;
- writes `<root>/<bundle.root>/mkway.lock`: version (the tag, or `unversioned`), `semver` (the source's `VERSION`
  file, MW-016), source sha, date and the copy's content hash. No path;
- creates `cards/`, `ledger/`, `locks/`, `state/` and a starter profile when none exists (no path in it);
- writes ignore lines for the run-time folders and files in `<root>/<bundle.root>/.gitignore`, whatever the profile's
  vcs (MW-027): the engine copy, the profile, the lock, cards and ledger are tracked, so a fresh worktree of the
  committed task folder has the copy and its hooks with no install;
- generates the hook entries into the committed `<root>/.claude/settings.json` (C23, C24; MW-027) and strips mkway's
  own entries from an older `settings.local.json`;
- removes the line `engine/` (also `/engine/` and `engine`, after stripping spaces and `\r`) an earlier install wrote
  into that `.gitignore` (MW-035, MW-041), keeping every other line and the file's own line ending style;
- with vcs git it ends by printing ONE line, `git -C "<root>" add <paths>; git -C "<root>" commit -m "<message>" --
  <paths>` (the commit takes only install's paths, MW-035; the root is named, so the line works from any folder,
  MW-041), or with `--commit` (the owner's terminal only) runs it; the message starts with
  `commit.message_prefix` when the profile sets it; MW-036: the paths are only what install writes (settings file,
  bundle `.gitignore`, `.gitattributes`, `mkway.lock`, `engine`, and the profile when this run created it).
It never reads or writes the user's home folder.

check: compares the copy's hash with the lock, runs the copy's tests (without `engine_repo`), and runs the term
scan when env `ENGINE_TERMS_FILE` names a term file (C14, C22).
"""
from __future__ import annotations

import datetime
import hashlib
import importlib.util
import io
import json
import math
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
from pathlib import Path

import gatemode
import logs
import paths
import profiles
import schema_check

import core_install as core
from core_install import (ATTRIBUTES_HEAD, BUNDLE_FOLDERS, ENGINE_ATTRIBUTE, EVENT_ORDER, FAILED_NAMES_MAX,  # noqa: F401
                          FLOOR_SECONDS, IGNORE_HEAD, IGNORED_FOLDERS, LAUNCHER_NAMES, MARGIN_SECONDS,
                          MATCHER_EVENTS, MIN_PYTHON, PY_FLAGS, QUOTED_EXE, REGISTER_ATTRIBUTE, RUNTIME_IGNORES,
                          SET_DIRS, SET_FILES, SETTINGS_FILE, SKIP_PARTS, STALE_ENGINE_IGNORES, UNQUOTED_EXE,
                          VERSION_FLAG, failed_names, files_hash, in_set, owned_marker, starter_profile)

LOCAL_SETTINGS_FILE = ".claude/settings.local.json"  # the owner's own per-machine file; mkway keeps no entry in it
ENGINE_DIR = Path(__file__).resolve().parent  # the engine's own files (the group table); never the task root
MACHINE_FILE = "machine.json"  # <state.dir>/machine.json: the per-machine interpreter, untracked (C27)
GIT = ["git", "--no-optional-locks"]


class InstallError(Exception):
    pass


# ---- the file set and the hash ----------------------------------------------------------------------------------

_skipped = core.skipped


def _walk(folder: Path):
    folder = Path(folder)
    for dirpath, dirnames, filenames in os.walk(folder):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_PARTS)
        for name in filenames:
            path = Path(dirpath) / name
            yield path.relative_to(folder).as_posix(), path


def folder_files(src: Path) -> dict:
    """The set files of a plain folder: relative posix path -> bytes."""
    return {rel: path.read_bytes() for rel, path in _walk(src) if in_set(rel) and not rel.startswith("mkway/")}


def copy_hash(copy: Path) -> str:
    """sha256 over the sorted paths and bytes of the copy (C26: caches and test temp files left out). Reads the disk:
    `mkway check` and the start line use it to verify what is there."""
    return core.hash_entries((rel, path.read_bytes())
                             for rel, path in sorted((r, p) for r, p in _walk(copy) if not _skipped(r)))


def _writable(func, path, _exc):
    os.chmod(path, stat.S_IWRITE)  # a read-only file on Windows (the object files of a git repository)
    func(path)


def remove_tree(path: Path) -> bool:
    """MW-032: remove a folder with its content, clearing the read-only bit of what refuses and trying again. True
    when nothing is left; False when something still is (never an exception)."""
    path = Path(path)
    for _ in range(3):
        if not os.path.lexists(path):
            return True
        try:
            if sys.version_info >= (3, 12):
                shutil.rmtree(path, onexc=_writable)
            else:
                shutil.rmtree(path, onerror=_writable)
        except OSError:
            continue
    return not os.path.lexists(path)


def _one_line(exc) -> str:
    return " ".join(str(exc).split())


def git_top(path: Path):
    try:
        proc = subprocess.run(GIT + ["-C", str(path), "rev-parse", "--show-toplevel"], capture_output=True,
                              text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return Path(proc.stdout.strip()).resolve() if proc.returncode == 0 and proc.stdout.strip() else None


def _git(src: Path, *args, text=True):
    proc = subprocess.run(GIT + ["-C", str(src), *args], capture_output=True, text=text, timeout=120)
    if proc.returncode != 0:
        err = proc.stderr if text else proc.stderr.decode("utf-8", "replace")
        raise InstallError(f"git {args[0]} failed in the source: {err.strip()}")
    return proc.stdout


def source_files(src: Path, ref=None):
    """(files, version, source sha). A source that is the top of its own git work tree is read at the ref (HEAD
    by default) with git; any other folder is read as plain files."""
    src = Path(src).resolve()
    if git_top(src) == src:
        sha = _git(src, "rev-parse", "--verify", f"{ref or 'HEAD'}^{{commit}}").strip()
        tag = subprocess.run(GIT + ["-C", str(src), "describe", "--tags", "--exact-match", sha],
                             capture_output=True, text=True, timeout=30)
        version = tag.stdout.strip() if tag.returncode == 0 and tag.stdout.strip() else "unversioned"
        archive = _git(src, "archive", "--format=tar", sha, text=False)
        files = {}
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            for member in tar.getmembers():
                if member.isfile() and in_set(member.name):
                    files[member.name] = tar.extractfile(member).read()
        return files, version, sha
    if ref:
        raise InstallError("--ref needs a git source (the top of a git work tree)")
    return folder_files(src), "unversioned", None


# ---- hook entries -------------------------------------------------------------------------------------------------

_loadable_on = core.loadable_on


def group_table(engine_dir: Path = ENGINE_DIR) -> dict:
    """The manifest's group table (R13c): group -> {"onFailure": ...}; an engine constant."""
    return json.loads((Path(engine_dir) / "manifest.json").read_text(encoding="utf-8")).get("groups", {})


def generate_entries(profile, manifest, *, profile_rel=None, python=None, groups_table=None) -> list:
    """The hook entries of the profile and manifest (the decision is `core_install.generate_entries`); the group table
    is read from the engine's manifest unless given."""
    table = group_table() if groups_table is None else groups_table
    return core.generate_entries(profile, manifest, table, profile_rel=profile_rel, python=python)


def write_settings(path: Path, entries: list, bundle_root: str) -> None:
    """Write the settings file the core decided on (owned entries replaced, everything else kept byte for byte)."""
    path = Path(path)
    text = path.read_text(encoding="utf-8") if path.is_file() else None
    verdict = core.settings_text(text, entries, bundle_root, path.name)
    if verdict.kind == core.REFUSE:
        raise InstallError(verdict.text)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(verdict.out, encoding="utf-8")


def live_entries(path: Path, bundle_root: str) -> list:
    """The owned entries in a settings file, as whole entries: event, matcher, command, timeout, onFailure."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return []
    return core.owned_entries(text, bundle_root)


# ---- install --------------------------------------------------------------------------------------------------------

def detect_vcs(root: Path) -> str:
    """`git` when the root is the top of a git work tree or any folder inside one (MW-028: a task root below the top,
    in a linked or sparse work tree, is git; the top answers for a folder git has not tracked yet), else `none`."""
    top = git_top(root)
    return "git" if top is not None and Path(root).resolve().is_relative_to(top) else "none"


def _read_text_raw(path: Path) -> str:
    """The file's text with its line ends untouched (MW-041): a CRLF file stays CRLF."""
    return path.read_bytes().decode("utf-8") if path.is_file() else ""


def _ensure_lines(path: Path, head: str, lines: list) -> None:
    text = _read_text_raw(path)
    out = core.ensure_lines(text, head, lines)
    if out != text:
        _write_text_raw(path, out)


def _write_text_raw(path: Path, text: str) -> None:
    path.write_bytes(text.encode("utf-8"))


def _inside(path: Path, root: Path) -> bool:
    """True when the path, with every link and junction on it resolved, is inside the root."""
    return Path(path).resolve().is_relative_to(Path(root).resolve())


VERSION_PROBE = "import sys; print(sys.version_info[:2])"


def plain_interpreter(text, timeout=30) -> bool:
    """True when `text` is an existing executable (a name found on PATH, or a path; quoted when it holds a space)
    with no shell characters, followed by one version flag (`-3`, `-3.12`) only when the program is the `py`
    launcher (C34), and when it runs `-c "import sys; print(sys.version_info[:2])"` and reports Python 3.9 or later
    (fix checks N2, M1, L3)."""
    return interpreter_problem(text, timeout) is None


def interpreter_problem(text, timeout=30):
    """None when `text` passes the interpreter rule (see `plain_interpreter`); else "timeout" when the program did
    not answer within `timeout` seconds (it and its children are stopped), or "invalid" (fix check 3 L5). The syntax and
    the answer are judged by the core; this reads PATH and runs the probe."""
    parsed = core.interpreter_syntax(text)
    if parsed is None:
        return "invalid"
    path, flag = parsed
    found = shutil.which(path)
    if found is None:
        return "invalid"
    try:
        proc = subprocess.Popen([found] + ([flag] if flag else []) + ["-c", VERSION_PROBE], stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                                start_new_session=(os.name != "nt"))
    except (OSError, ValueError):
        return "invalid"
    job = _windows_job(proc)  # every process the probe starts joins it, orphans included (fix check 4 F5)
    try:
        try:
            out, _ = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            _stop_tree(proc, job)
            return "timeout"
    finally:
        _close_job(job)
    return None if core.version_answer_ok(proc.returncode, out) else "invalid"


KILL_SECONDS = 4   # the kill step's own limit; probe 5 + kill 4 + drain 2 = 11 s, under the start entry's 15 s
DRAIN_SECONDS = 2


def _kernel32():
    import ctypes
    from ctypes import wintypes
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.CreateJobObjectW.restype = wintypes.HANDLE
    k.CreateJobObjectW.argtypes = (ctypes.c_void_p, ctypes.c_wchar_p)
    k.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
    k.TerminateJobObject.argtypes = (wintypes.HANDLE, wintypes.UINT)
    k.CloseHandle.argtypes = (wintypes.HANDLE,)
    return k


def _windows_job(proc):
    """On Windows, a job object holding the probe, so a stop reaches every process it started, a grandchild whose
    parent already exited included. None elsewhere, or when the job cannot be made (then `taskkill /T`)."""
    if os.name != "nt":
        return None
    try:
        k = _kernel32()
        job = k.CreateJobObjectW(None, None)
        if not job:
            return None
        if not k.AssignProcessToJobObject(job, int(proc._handle)):
            k.CloseHandle(job)
            return None
        return job
    except (OSError, AttributeError, ValueError):
        return None


def _close_job(job) -> None:
    if job:
        try:
            _kernel32().CloseHandle(job)
        except (OSError, AttributeError):
            pass


def _stop_tree(proc, job=None) -> None:
    """Stop a timed-out probe and every process it started, so none keeps the output pipe open (fix check 4 F5):
    the job object on Windows (else `taskkill /T`, checked, else `proc.kill()`), the process group elsewhere."""
    stopped = False
    try:
        if job:
            stopped = bool(_kernel32().TerminateJobObject(job, 1))
        elif os.name == "nt":
            done = subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True,
                                  timeout=KILL_SECONDS)
            stopped = done.returncode == 0
        else:
            import signal
            os.killpg(proc.pid, signal.SIGKILL)
            stopped = True
    except (OSError, subprocess.SubprocessError, AttributeError):
        stopped = False
    if not stopped:
        try:
            proc.kill()
        except OSError:
            pass
    try:
        proc.communicate(timeout=DRAIN_SECONDS)
    except (subprocess.TimeoutExpired, OSError, ValueError):
        pass


def entry_interpreter(command: str, bundle: str):
    """The interpreter part of an owned entry's command (the text before `-I -X utf8` and the launcher path), or None;
    an entry without the flags gives None, so the start line reports it as drift (R111 (a))."""
    marker = f' {PY_FLAGS} "${{CLAUDE_PROJECT_DIR}}/{bundle}/engine/mkway.py" hook'
    head, found, _ = (command or "").partition(marker)
    return head if found else None


ATTRIBUTES_HEAD = ("# mkway install: the register is written with \\n line ends, and the engine copy keeps its bytes; "
                   "git must not convert either")
REGISTER_ATTRIBUTE = "cards/REGISTER.md -text"
ENGINE_ATTRIBUTE = "engine/** -text"  # MW-027: the copy's hash must survive a checkout with autocrlf


def _seal(root: Path, profile, vcs_now: str) -> list:
    """R19a: the seal is written only when the register equals HEAD's blob (with git); otherwise it stays missing
    and the owner checks the register with `card resync`. With vcs none there is no HEAD: install, the owner's
    command, seals the register as it is (C45)."""
    import register
    import runner
    reg = register.path(root, profile)
    if not reg.is_file():
        return []
    if vcs_now == "git":
        rel = reg.relative_to(root).as_posix()
        proc = runner.git(root, "show", f"HEAD:./{rel}", text=False)  # list item 3: read from the root
        if proc.returncode != 0 or proc.stdout != reg.read_bytes():
            return [f"register: {rel} differs from HEAD (or is not committed); the seal is left missing. Check it, "
                    "then run `python mkway/engine/mkway.py card resync` in your own terminal"]
    register.reseal(root, profile)
    return ["register: sealed"]


def _replace_copy(bdir: Path, copy: Path, files: dict, bundle: str):
    """MW-032: the new copy is written into `engine.new` beside the old one, the old one is renamed aside, the new
    one renamed into place, and the old one removed. A failure before the swap changes nothing; a failed swap puts the
    old copy back. Returns the folder that still holds the old copy when it could not be removed, else None; a
    problem that leaves no new copy is an InstallError (one line), never a traceback."""
    new = bdir / "engine.new"
    if not remove_tree(new):
        raise InstallError(f"{bundle}/{new.name} is left from an earlier install and cannot be removed; remove that "
                           "folder and run install again; nothing was changed")
    old = bdir / "engine.old"
    number = 1
    while os.path.lexists(old) and not remove_tree(old):  # an earlier leftover the owner has not removed yet
        number += 1
        old = bdir / f"engine.old-{number}"
    try:
        for rel, data in files.items():
            target = new / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    except OSError as exc:
        remove_tree(new)
        raise InstallError(f"the new copy could not be written ({_one_line(exc)}); the existing copy was not changed")
    moved = False
    if copy.exists():
        try:
            os.replace(copy, old)
        except OSError as exc:
            remove_tree(new)
            raise InstallError(f"{bundle}/engine could not be moved aside ({_one_line(exc)}); the existing copy was "
                               "not changed")
        moved = True
    try:
        os.replace(new, copy)
    except OSError as exc:
        restored = True
        if moved:
            try:
                os.replace(old, copy)
            except OSError:
                restored = False
        remove_tree(new)
        raise InstallError(f"the new copy could not be put in place ({_one_line(exc)}); " +
                           ("the old copy is back and was not changed" if restored else
                            f"the old copy is in {bundle}/{old.name}: rename it back to engine"))
    return old if moved and not remove_tree(old) else None


def _prefix(profile):
    return ((profile.get("commit") or {}).get("message_prefix") or "") if isinstance(profile, dict) else ""


def commit_message(profile, version: str) -> str:
    """MW-035: the install commit message: `<commit.message_prefix> mkway <version>: install`, no prefix when unset."""
    return core.commit_message(_prefix(profile), version)


def install_paths(root: Path, profile, profile_rel=None) -> list:
    """MW-036: the paths install itself writes, relative to the root (the decision is `core_install.install_paths`)."""
    bundle = profiles.bundle_root(profile)
    present = {name for name in core.OWN_NAMES if (root / bundle / name).exists()}
    return core.install_paths(bundle, present, profile_rel)


def commit_lines(profile, version: str, paths: list, root: Path) -> list:
    """MW-027, MW-035, MW-036, MW-041: the ONE line the owner pastes, from any folder (see `core_install.commit_line`)."""
    return [core.commit_line(_prefix(profile), version, paths, Path(root).resolve().as_posix())]


def run_commit(root: Path, profile, version: str, paths: list) -> str:
    """Run the line of `commit_lines` in the root (the owner's terminal only; the CLI tripwire guards it)."""
    add = subprocess.run(GIT + ["-C", str(root), "add", *paths], capture_output=True, text=True, timeout=120)
    if add.returncode != 0:
        raise InstallError("install is written, but `git add` failed: " + add.stderr.strip())
    message = commit_message(profile, version)
    done = subprocess.run(GIT + ["-C", str(root), "commit", "-q", "-m", message, "--", *paths], capture_output=True,
                          text=True, timeout=120)
    if done.returncode != 0:
        raise InstallError("install is written and added, but `git commit` failed: "
                           + (done.stderr or done.stdout).strip())
    return f"commit: {message}"


INSTALL_HINTS = {  # MW-112 (R284): the tool-validation ids say the correct form; the pure text of core_install stays as it is
    "starter-invalid": ". Give install a --vcs of git or none: the starter profile is written from it",
    "profile-invalid-shared": ". The owner fixes the profile in their own editor (`mkway check` names each error), then "
                              "runs install with --shared again",
    "shared-profile-invalid": ". Give --shared an absolute folder the schema accepts, or the owner fixes the profile in "
                              "their own editor",
    "commit-needs-git": ". Run install without --commit, or set vcs git in the profile in your own editor",
    "source-empty": ". Install from the engine repository: `mkway install --from <engine repository>`",
}


def _decide(facts) -> None:
    """Ask the core about the facts read so far; a refusal is an InstallError (one line, nothing written yet)."""
    verdict = core.decide_install(facts)
    if verdict.kind == core.REFUSE:
        raise InstallError(verdict.text + INSTALL_HINTS.get(verdict.reason, ""))


def _reader_agent(root: Path, copy: Path, python: str, bundle: str) -> list:
    """MW-116 (R287c): write the reader agent file `.claude/agents/fresh-reader.md` from the template of the engine copy, unless
    the file exists (a reinstall keeps the owner's edit). The report names the workspace trust dialog: Claude Code runs a
    project agent's frontmatter hooks only after the dialog for the agent file's folder was accepted."""
    template = copy / core.AGENT_TEMPLATE
    if not template.is_file():
        return [f"reader agent: the engine copy has no {core.AGENT_TEMPLATE}; no reader agent file was written"]
    rendered = core.render_reader_agent(template.read_text(encoding="utf-8"), python, bundle)
    path = root / core.AGENT_FILE
    existing = path.read_text(encoding="utf-8") if path.is_file() else None
    if core.reader_agent_action(existing, rendered) == "write":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8")
        said = f"reader agent: {core.AGENT_FILE} written"
    else:
        said = f"reader agent: {core.AGENT_FILE} exists and is kept"
    return [said + "; its frontmatter hook runs only after the workspace trust dialog for this folder was accepted once "
                   "(sub-agents.md, Hooks in subagent frontmatter): accept it, or the reader runs unguarded and "
                   "`verdict-reader-unguarded` refuses its verdict"]


def install(root: Path, src: Path, *, ref=None, profile_arg=None, vcs=None, python=None, shared=None,
            commit=False) -> list:
    root = Path(root).resolve()
    report = []
    if shared is not None and schema_check._format_error("absolute-path", shared) is not None:
        raise InstallError("--shared must be an absolute path (for example C:/work/shared-state); nothing was written")
    ppath = paths.profile_path(root, profile_arg)
    _decide(core.InstallFacts(shared=shared, profile_inside_root=_inside(ppath, root)))
    profile, errors = profiles.load(ppath)
    detected = detect_vcs(root) if vcs is None else None
    plan = core.plan_profile(profile, errors, shared, vcs, detected)
    candidate = profiles.validate(plan.profile) if plan.kind in ("starter", "shared") else None
    _decide(core.InstallFacts(shared=shared, profile_inside_root=True, kind=plan.kind, load_errors=tuple(errors),
                              candidate_errors=tuple(candidate) if candidate is not None else None))
    starter, set_shared, profile = plan.kind == "starter", plan.kind == "shared", plan.profile
    if plan.kind == "invalid":
        report.append(core.profile_report(plan, errors, shared, ""))
    profile = profile if isinstance(profile, dict) else {}
    vcs_now = core.choose_vcs(profile, vcs, detected if detected is not None else detect_vcs(root))
    _decide(core.InstallFacts(commit=commit, vcs_now=vcs_now))
    bundle = profiles.bundle_root(profile)
    bdir = root / bundle
    copy = bdir / "engine"
    state = profiles.state_dir(root, profile)
    first_install = not state.exists()  # MW-012: shadow by default, only on a first install
    copy_is_link = copy.is_symlink() or (copy.exists() and not _inside(copy, root))
    _decide(core.InstallFacts(bundle=bundle, bundle_inside_root=not (
        not _inside(bdir, root) or not _inside(state, root) or copy_is_link)))
    used = python or (profile.get("python") or {}).get("command") or "python"
    _decide(core.InstallFacts(python_ok=plain_interpreter(used)))
    files, version, sha = source_files(Path(src), ref)
    _decide(core.InstallFacts(source_files=len(files)))
    if starter or set_shared:
        ppath.parent.mkdir(parents=True, exist_ok=True)
        tmp = ppath.with_name(ppath.name + ".tmp")  # a temp file, then replace: never a half-written profile
        tmp.write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, ppath)
        report.append(core.profile_report(plan, errors, shared, ppath.relative_to(root).as_posix()))
    _decide(core.InstallFacts(bundle=bundle, copy_exists=copy.exists(), lock_exists=(bdir / "mkway.lock").is_file()))
    leftover = _replace_copy(bdir, copy, files, bundle)  # MW-032: build beside, swap by rename, never half-deleted
    lock = core.lock_record(files, version, sha, datetime.date.today().isoformat())  # MW-051: no second read
    semver = lock["semver"]
    (bdir / "mkway.lock").write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    report.append(f"copy: {len(files)} files, version {version}, {lock['hash'][:19]}")
    if leftover is not None:
        report.append(f"copy: the old copy could not be removed; the leftover folder {bundle}/{leftover.name} holds it "
                      "(remove that folder by hand)")
    for name in BUNDLE_FOLDERS:
        (bdir / name).mkdir(parents=True, exist_ok=True)
    state.mkdir(parents=True, exist_ok=True)
    # R19c: the register keeps its `\n` line ends on a clone with autocrlf; MW-027: so does the engine copy
    _ensure_lines(bdir / ".gitattributes", ATTRIBUTES_HEAD, [REGISTER_ATTRIBUTE, ENGINE_ATTRIBUTE])
    report += _seal(root, profile, vcs_now)
    ignore = bdir / ".gitignore"
    raw = _read_text_raw(ignore)
    text, lines = core.ignore_plan(raw, bundle)
    if text != raw:
        _write_text_raw(ignore, text)
    report += lines
    copied = json.loads((copy / "engine" / "manifest.json").read_text(encoding="utf-8"))
    manifest = copied["entries"]
    default = paths.profile_path(root)
    rel = None if ppath.resolve() == default.resolve() else ppath.resolve().relative_to(root).as_posix()
    committed_python = (profile.get("python") or {}).get("command") or "python"  # MW-027: the committed entries never
    entries = generate_entries(profile, manifest, profile_rel=rel, python=committed_python,  # carry a machine's own
                               groups_table=copied.get("groups", {}))                       # interpreter
    write_settings(root / SETTINGS_FILE, entries, bundle)
    report += _reader_agent(root, copy, committed_python, bundle)
    local = root / LOCAL_SETTINGS_FILE
    if live_entries(local, bundle):  # MW-027: an older install put the entries here; they would run twice otherwise
        write_settings(local, [], bundle)
    (state / MACHINE_FILE).write_text(json.dumps({"python": used}) + "\n", encoding="utf-8")  # untracked (C27)
    report.append("hook entries: " + ", ".join(f"{e['event']}/{e['group']}" for e in entries))
    if first_install:  # MW-012, rule 5: every form gate that is on starts in watch; a re-install keeps the modes
        watched = sorted({e.get("gate", e["name"]) for e in manifest if _loadable_on(profile, e)
                          and gatemode.gate_class(manifest, e.get("gate", e["name"])) == gatemode.FORM})
        for gate in watched:
            gatemode.write_marker(state, gate, "installed")
            logs.write_refusal(state, gatemode.transition_row(gate, "gate-watch-installed", cause="installed",
                                                              event="install"))
        if watched:
            report.append("watch: " + ", ".join(watched) + " start in watch mode (first install); "
                          "`mkway gate on <name>` turns one to blocking")
    if vcs_now == "git":
        version_text = semver or version
        own = install_paths(root, profile, ppath.relative_to(root).as_posix() if starter else None)
        if (root / core.AGENT_FILE).is_file():
            own = own + [core.AGENT_FILE]  # MW-116
        if commit:
            report.append(run_commit(root, profile, version_text, own))
        else:
            report.append("commit: paste this one line in the task folder (or run install again with --commit):")
            report += commit_lines(profile, version_text, own, root)
    return report


# ---- check ----------------------------------------------------------------------------------------------------------

def _load_term_scan(copy: Path):
    spec = importlib.util.spec_from_file_location("mkway_copy_term_scan", copy / "tools" / "term_scan.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # its dataclasses look the module up by name
    spec.loader.exec_module(module)
    return module


def git_builtins_line(root: Path, run=None, extra=frozenset()) -> str:
    """The `mkway check` line that compares the static built-in list (`lock_gate.git_builtins`, R90, plus the
    profile's `lock_gate.git_builtins_extra`) with `git --list-cmds=builtins`; `run` returns git's output (a fake in
    tests). MW-031: only a name in the list and not in git is a warning (the gate would trust it as a built-in; the
    fix is to update mkway); a name only in git is an info part of the line (an over-refusal, the safe side; the
    profile key `lock_gate.git_builtins_extra` allows it). Never an edit of an engine file."""
    import helpers
    import runner
    if run is None:
        def run():
            proc = runner.git(root, "--list-cmds=builtins")
            return proc.stdout if proc.returncode == 0 else None
    try:
        out = run()
    except (OSError, subprocess.SubprocessError):
        out = None
    if out is None:
        return "git builtins: not compared (git did not answer)"
    actual = {line.strip() for line in out.splitlines() if line.strip()}
    key = helpers.git_builtins() | set(extra)
    only_git, only_key = sorted(actual - key), sorted(key - actual)
    info = (f"info: this git has built-ins the engine list lacks: {', '.join(only_git)}; the lock gate refuses "
            f"`git <name>` for them as command-unparsed, safe; to allow them add the names to the profile key "
            f"`lock_gate.git_builtins_extra`") if only_git else ""
    if only_key:
        return (f"git builtins: warning: the engine list has names this git does not know: {', '.join(only_key)}; the "
                f"lock gate would trust `git <name>` as a built-in although git may run an alias or an external "
                f"command (fix: update mkway)" + (f"; {info}" if info else ""))
    if only_git:
        return f"git builtins: the engine list is safe for this git ({len(key)} commands; {info})"
    return f"git builtins: the engine list matches git ({len(key)} commands)"


def version_tag_line(root: Path, env=None):
    """MW-016: the `mkway check` line that compares the root's `VERSION` file with the git tag at HEAD (`v<version>`).
    The shell reads the file and the tags; `core_install.version_tag_line` words the line. None when the root has no
    `VERSION` file."""
    import runner
    path = Path(root) / "VERSION"
    if not path.is_file():
        return None
    in_chat = "CLAUDECODE" in (os.environ if env is None else env)  # the owner's terminal only, as for the builtins
    tags = []
    if not in_chat:
        try:
            proc = runner.git(root, "tag", "--points-at", "HEAD")
            tags = proc.stdout.split() if proc.returncode == 0 else []
        except (OSError, subprocess.SubprocessError):
            tags = None
    return core.version_tag_line(path.read_text(encoding="utf-8"), in_chat, tags)


def _copy_manifest(copy: Path):
    """The manifest of the installed copy (the one the hook entries were generated from); None when unreadable."""
    try:
        return json.loads((Path(copy) / "engine" / "manifest.json").read_text(encoding="utf-8"))["entries"]
    except (OSError, ValueError, KeyError):
        return None


def message_gate_line(root: Path, profile, manifest=None):
    """MW-018: the `mkway check` line on the SendMessage hook entry. A warning, never a failure, when the owned hook
    entries of the settings file lack it while the gate `message` is on; None when the gate is off or the manifest has
    no entry for it."""
    manifest = manifest if manifest is not None else _copy_manifest(ENGINE_DIR.parent) or []
    entries = [e for e in manifest if e.get("gate") == "message" and _loadable_on(profile, e)
               and e.get("matcher") == "SendMessage"]
    if not entries:
        return None
    live = live_entries(Path(root) / SETTINGS_FILE, profiles.bundle_root(profile))
    if any(e.get("event") == "PreToolUse" and "SendMessage" in (e.get("matcher") or "").split("|")
           and "--group message" in (e.get("command") or "") for e in live):
        return "message gate: the SendMessage hook entry is present"
    return ("message gate: warning: .claude/settings.json has no SendMessage hook entry, so messages are not "
            "checked against the inbox (fix: the owner runs `mkway install`)")


def no_install_line(root) -> str:
    return (f"no mkway install at {Path(root).resolve()} (fix: pass `--root <task folder>`, or run the command from "
            f"the task folder)")


STATE_FILES = ("leads.json", "sessions.jsonl", "pings.jsonl", "dead-letter.jsonl", "inbox", "locks")  # MW-017/018/022


def state_outside_root_lines(root: Path, profile) -> list:
    """MW-026: `state-outside-root` when the main worktree's mirror of the root's state folder holds mkway state files
    that 0.2.0 and 0.2.1 wrote there. It names the folder so the owner can remove it; nothing is ever removed. No line
    when the owner chose that very folder as `state.shared_dir`, or when the root is not in a linked worktree."""
    own = profiles.state_dir(root, profile)
    mirror = profiles.main_mirror_state(Path(root), own)
    if mirror is None or not mirror.is_dir() or mirror.resolve() == own.resolve():
        return []
    if profiles.shared_state_dir(root, profile).resolve() == mirror.resolve():
        return []
    found = sorted(name for name in STATE_FILES if (mirror / name).exists())
    if not found:
        return []
    return [f"state-outside-root: {mirror.resolve()} holds mkway state of this root ({', '.join(found)}) written by "
            "0.2.0 or 0.2.1 outside the root (fix: the owner removes that folder's state files; check never removes "
            "anything)"]


def staged_outside_lines(root: Path, profile) -> list:
    """MW-043: `staged files: N outside every open card's Paths` for a git root with N > 0 staged files outside the
    Paths of every open card; no line otherwise, and none when git or the register cannot be read."""
    if profiles.vcs(profile) != "git":
        return []
    import gate_commit
    try:
        found = gate_commit.staged_outside(root, profile)
    except Exception:
        return []
    return [f"staged files: {len(found)} outside every open card's Paths"] if found else []


def check(root: Path, *, profile_arg=None, env=None) -> tuple:
    """(exit code, lines)."""
    env = dict(os.environ if env is None else env)
    root = Path(root).resolve()
    if not (root / profiles.bundle_root({}) / "engine").is_dir() and not paths.profile_path(root, profile_arg).is_file():
        return 1, [no_install_line(root)]  # MW-024: one clear line, never a traceback
    profile, errors = profiles.load(paths.profile_path(root, profile_arg))
    profile = profile if isinstance(profile, dict) else {}
    bdir = root / profiles.bundle_root(profile)
    copy = bdir / "engine"
    lines, ok = [], True
    if errors:  # C53 (R64): the same schema error the refusal carries (key path and message)
        lines.append("profile: invalid: " + "; ".join(errors[:5]) + " (fix: the owner edits the profile in their "
                     "own editor)")
        ok = False
    bad_watch = profiles.session_id_watch_unreadable(profile)  # MW-110, R279c Q2
    if bad_watch:
        lines.append(f"profile: messaging.session_id_watch_until is {bad_watch!r}, not a date (YYYY-MM-DD): it counts as "
                     f"passed (fix: the owner sets a date or empties it in their own editor)")
        ok = False
    try:
        lock = json.loads((bdir / "mkway.lock").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        lock = None
    line, hash_ok = core.hash_line(lock, copy_hash(copy) if lock is not None else None)
    lines.append(line)
    ok = ok and hash_ok
    if profiles.vcs(profile) == "git":  # close-fix 8 (R90): the static built-in list against git's own
        if "CLAUDECODE" in env:  # the owner's terminal only (R90)
            lines.append("git builtins: not compared inside a Claude chat (run `mkway check` in your own terminal)")
        else:
            lines.append(git_builtins_line(root, extra=profiles.git_builtins_extra(profile)))
        tag_line = version_tag_line(root, env)
        if tag_line:
            lines.append(tag_line)
    gate_line = message_gate_line(root, profile, _copy_manifest(copy))
    if gate_line:
        lines.append(gate_line)
    try:  # MW-022: an older per-work-tree lock marker is still read for one version; a warning, never a failure
        import locks
        lines += locks.marker_warnings(root, profile)
    except (OSError, ValueError, ImportError):
        pass
    lines += state_outside_root_lines(root, profile)  # MW-026: a warning, never a failure
    lines += staged_outside_lines(root, profile)  # MW-043: a line, never a failure
    ini =profiles.state_dir(root, profile) / "check" / "pytest.ini"
    ini.parent.mkdir(parents=True, exist_ok=True)
    ini.write_text("[pytest]\nmarkers =\n    engine_repo: needs the engine repository itself\n", encoding="utf-8")
    run_env = {k: v for k, v in env.items() if k != "CLAUDE_PROJECT_DIR"}
    run_env["PYTHONDONTWRITEBYTECODE"] = "1"  # MW-032: the run leaves no file in the copy
    scratch = ini.parent / "tmp"  # MW-032: test scratch is state, never part of the copy
    proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "-c", str(ini), "--rootdir", str(copy),
                           "-p", "no:cacheprovider", "--basetemp", str(scratch), "-m", "not engine_repo",
                           str(copy / "tests")], cwd=str(copy), capture_output=True, text=True, env=run_env,
                          timeout=900)
    line, tests_ok = core.tests_line(proc.returncode, proc.stdout)
    lines.append(line)
    ok = ok and tests_ok
    if env.get("ENGINE_TERMS_FILE"):
        scan = _load_term_scan(copy)
        try:
            entries = scan.resolve_entries(env=env, config_path=copy / "tools" / "term_scan.json")
        except (scan.TermListMissing, OSError):
            lines.append("term scan: term list missing (ENGINE_TERMS_FILE)")
            return 1, lines
        files = [p for r, p in _walk(copy) if not _skipped(r)]
        result = scan.scan_files(files, entries, base=copy)
        problems = scan.allow_problems(result, scan.load_allow_list(copy / scan.ALLOW_FILE), files, base=copy)
        lines.append(f"term scan: {len(entries)} entries, {len(result.hits)} hits, {len(result.exceptions)} "
                     "exceptions")
        lines += [f"  {h.path}:{h.line} group {h.group} #{h.index}" for h in result.hits]
        lines += [f"term scan exception: {e.path}:{e.line} ({e.reason})" for e in result.exceptions]
        lines += [f"term scan: {p}" for p in problems]  # fix check 3 M3: the copy's allow list pins them
        ok = ok and not result.hits and not problems
    else:
        lines.append("term scan: skipped, no term list set")
    return (0 if ok else 1), lines
