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
- removes the exact line `engine/` an earlier install wrote into that `.gitignore` (MW-035);
- with vcs git it ends by printing ONE line, `git add <paths>; git commit -m "<message>" -- <paths>` (the commit takes
  only install's paths, MW-035), or with `--commit` (the owner's terminal only) runs it; the message starts with
  `commit.message_prefix` when the profile sets it.
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

SET_FILES = ("mkway.py", "VERSION", "cards/_TEMPLATE/CARD.md",  # MW-016: the version travels with the copy
             "cards/_TEMPLATE/ORDER.md")  # MW-017: the order file of a lead's card
SET_DIRS = ("engine/", "tools/", "tests/", "fixtures/synthetic/")
SKIP_PARTS = {".git", "__pycache__", ".pytest_tmp", ".pytest_cache"}
BUNDLE_FOLDERS = ("cards", "ledger", "locks", "state")  # created by install
IGNORED_FOLDERS = ("locks", "state")  # R18: cards/ and ledger/ are tracked; MW-027: so is the engine copy
RUNTIME_IGNORES = ("__pycache__/", "*.pyc", ".pytest_tmp/", ".pytest_cache/")  # written when the copy runs or is checked
IGNORE_HEAD = ("# mkway install: locks, state and what the copy writes at run time are not tracked; the engine copy, "
               "profile.json, mkway.lock, cards and ledger are")
SETTINGS_FILE = ".claude/settings.json"  # MW-027: the committed hook entries
LOCAL_SETTINGS_FILE = ".claude/settings.local.json"  # the owner's own per-machine file; mkway keeps no entry in it
EVENT_ORDER = ("SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "SubagentStart", "SubagentStop",
               "Stop")  # MW-004: the two agent events, no matcher (every agent), so not in MATCHER_EVENTS
MATCHER_EVENTS = ("PreToolUse", "PostToolUse")
FLOOR_SECONDS = 10   # the least timeout of an entry
MARGIN_SECONDS = 15  # added to every entry's timeout (R13c)
ENGINE_DIR = Path(__file__).resolve().parent  # the engine's own files (the group table); never the task root
MACHINE_FILE = "machine.json"  # <state.dir>/machine.json: the per-machine interpreter, untracked (C27)
GIT = ["git", "--no-optional-locks"]


class InstallError(Exception):
    pass


# ---- the file set and the hash ----------------------------------------------------------------------------------

def _skipped(rel: str) -> bool:
    return rel.endswith(".pyc") or any(part in SKIP_PARTS for part in rel.split("/"))


def in_set(rel: str) -> bool:
    rel = rel.replace("\\", "/")
    return not _skipped(rel) and (rel in SET_FILES or rel.startswith(SET_DIRS))


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
    """sha256 over the sorted paths and bytes of the copy (C26: caches and test temp files left out)."""
    digest = hashlib.sha256()
    for rel, path in sorted((r, p) for r, p in _walk(copy) if not _skipped(r)):
        data = path.read_bytes()
        digest.update(rel.encode("utf-8") + b"\0" + str(len(data)).encode("ascii") + b"\0")
        digest.update(data)
    return "sha256:" + digest.hexdigest()


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

def owned_marker(bundle_root: str) -> str:
    return f'"${{CLAUDE_PROJECT_DIR}}/{bundle_root}/engine/mkway.py" hook'


def _loadable_on(profile, e) -> bool:
    return bool(e.get("function")) and bool(e.get("reason_ids")) and e.get("event") in EVENT_ORDER and \
        profiles.gate_on(profile, e.get("gate", e.get("name", "")), e.get("default_on", False))


def group_table(engine_dir: Path = ENGINE_DIR) -> dict:
    """The manifest's group table (R13c): group -> {"onFailure": ...}; an engine constant."""
    return json.loads((Path(engine_dir) / "manifest.json").read_text(encoding="utf-8")).get("groups", {})


PY_FLAGS = "-I -X utf8"  # R111 (a): no per-user Python folder, no PYTHONPATH; UTF-8 text


def generate_entries(profile, manifest, *, profile_rel=None, python=None, groups_table=None) -> list:
    """One entry per event and group with a gate on, plus the start entry (C23): event, group, matcher (the union
    of the group's gate matchers; None = every tool), command, timeout and on_failure (the group table's).
    Timeout (C23, R13c): the sum over the group's gates of (the profile's budget_seconds, else the manifest timeout)
    + 15 s, at least 10 s, so the dispatcher's own stop comes before the platform's."""
    python = python or ((profile.get("python") or {}).get("command") if isinstance(profile, dict) else None) \
        or "python"
    table = group_table() if groups_table is None else groups_table
    bundle = profiles.bundle_root(profile)
    groups = {("SessionStart", "start"): []}
    for e in manifest:
        if _loadable_on(profile, e):
            groups.setdefault((e["event"], e.get("group")), []).append(e)
    keys = sorted(groups, key=lambda k: EVENT_ORDER.index(k[0]))
    out = []
    for event, group in keys:
        gates = groups[(event, group)]
        matcher = None
        if event in MATCHER_EVENTS and gates and all(g.get("matcher") not in (None, "", "*") for g in gates):
            parts = []
            for g in gates:
                parts += [p for p in g["matcher"].split("|") if p not in parts]
            matcher = "|".join(parts)
        seconds = 0
        for g in gates:
            budget = profiles.budget_seconds(profile, g.get("gate", g.get("name", "")))
            if budget is not None:
                seconds += budget
            elif isinstance(g.get("timeout"), (int, float)) and not isinstance(g.get("timeout"), bool):
                seconds += g["timeout"]
        timeout = max(FLOOR_SECONDS, math.ceil(seconds + MARGIN_SECONDS))
        command = f'{python} {PY_FLAGS} "${{CLAUDE_PROJECT_DIR}}/{bundle}/engine/mkway.py" hook {event} --group {group}'
        if profile_rel:
            command += f' --profile "${{CLAUDE_PROJECT_DIR}}/{profile_rel}"'
        on_failure = (table.get(group) or {}).get("onFailure")
        out.append({"event": event, "group": group, "matcher": matcher, "command": command, "timeout": timeout,
                    "on_failure": on_failure})
    return out


def _value_span(text: str, key: str):
    """(start, end) of a top-level key's value in a JSON object text, or None."""
    decoder = json.JSONDecoder()
    ws = re.compile(r"\s*")
    i = ws.match(text, 0).end()
    if text[i:i + 1] != "{":
        return None
    i = ws.match(text, i + 1).end()
    while i < len(text) and text[i] != "}":
        name, i = json.decoder.scanstring(text, i + 1)
        i = ws.match(text, i).end() + 1  # the colon
        i = ws.match(text, i).end()
        _value, end = decoder.raw_decode(text, i)
        if name == key:
            return i, end
        i = ws.match(text, end).end()
        if text[i:i + 1] == ",":
            i = ws.match(text, i + 1).end()
    return None


def _is_owned(handler, marker) -> bool:
    return isinstance(handler, dict) and isinstance(handler.get("command"), str) and marker in handler["command"]


def write_settings(path: Path, entries: list, bundle_root: str) -> None:
    """Replace the owned entries; keep every other top-level key byte for byte and every handler mkway does not
    own (C24). Only documented fields: matcher, hooks, type, command, timeout, onFailure (R13c)."""
    path = Path(path)
    marker = owned_marker(bundle_root)
    text = path.read_text(encoding="utf-8") if path.is_file() else None
    try:
        data = json.loads(text) if text is not None else {}
    except json.JSONDecodeError as exc:
        raise InstallError(f"{path.name} is not valid JSON (line {exc.lineno}); it was not changed") from None
    hooks = data.get("hooks", {}) if isinstance(data, dict) else None
    if not isinstance(hooks, dict):
        raise InstallError(f"{path.name}: `hooks` is not an object; it was not changed")
    new: dict = {}
    for event, groups in hooks.items():
        kept = []
        for group in groups if isinstance(groups, list) else []:
            handlers = group.get("hooks") if isinstance(group, dict) else None
            if not isinstance(handlers, list):
                kept.append(group)
                continue
            rest = [h for h in handlers if not _is_owned(h, marker)]
            if rest:
                kept.append(dict(group, hooks=rest) if len(rest) != len(handlers) else group)
        if kept:
            new[event] = kept
    for e in entries:
        group = {"matcher": e["matcher"]} if e["matcher"] else {}
        handler = {"type": "command", "command": e["command"], "timeout": e["timeout"]}
        if e.get("on_failure"):
            handler["onFailure"] = e["on_failure"]  # R13c: a documented handler key
        group["hooks"] = [handler]
        new.setdefault(e["event"], []).append(group)
    value = json.dumps(new, indent=2).replace("\n", "\n  ")
    if text is None:
        out = '{\n  "hooks": ' + value + "\n}\n"
    else:
        span = _value_span(text, "hooks")
        if span:
            out = text[:span[0]] + value + text[span[1]:]
        else:
            close = text.rstrip().rindex("}")
            head = text[:close].rstrip()
            sep = "" if head.endswith("{") else ","
            out = head + sep + '\n  "hooks": ' + value + "\n" + text[close:]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(out, encoding="utf-8")


def live_entries(path: Path, bundle_root: str) -> list:
    """The owned entries in a settings file, as whole entries: event, matcher, command, timeout, onFailure."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    marker = owned_marker(bundle_root)
    out = []
    hooks = data.get("hooks") if isinstance(data, dict) else None
    for event, groups in (hooks or {}).items():
        for group in groups if isinstance(groups, list) else []:
            for h in (group.get("hooks") or []) if isinstance(group, dict) else []:
                if _is_owned(h, marker):
                    out.append({"event": event, "matcher": group.get("matcher"), "command": h["command"],
                                "timeout": h.get("timeout"), "on_failure": h.get("onFailure")})
    return out


# ---- install --------------------------------------------------------------------------------------------------------

def detect_vcs(root: Path) -> str:
    """`git` when the root is the top of a git work tree or any folder inside one (MW-028: a task root below the top,
    in a linked or sparse work tree, is git; the top answers for a folder git has not tracked yet), else `none`."""
    top = git_top(root)
    return "git" if top is not None and Path(root).resolve().is_relative_to(top) else "none"


def starter_profile(vcs: str) -> dict:
    bundle = profiles.DEFAULT_BUNDLE_ROOT
    return {
        "vcs": vcs,
        "bundle": {"root": bundle},
        "ids": {"card_prefix": "CARD"},
        "gates": {},
        "state": {"dir": profiles.DEFAULT_STATE_DIR},
        "python": {"command": "python"},
    }


def _ensure_lines(path: Path, head: str, lines: list) -> None:
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    have = set(text.splitlines())
    missing = [line for line in lines if line not in have]
    if not missing:
        return
    if text and not text.endswith("\n"):
        text += "\n"
    if head not in have:
        missing.insert(0, head)
    path.write_text(text + "\n".join(missing) + "\n", encoding="utf-8")


def _inside(path: Path, root: Path) -> bool:
    """True when the path, with every link and junction on it resolved, is inside the root."""
    return Path(path).resolve().is_relative_to(Path(root).resolve())


UNQUOTED_EXE = re.compile(r"[A-Za-z0-9_./:-]+")  # no space, no backslash, no shell character
QUOTED_EXE = re.compile(r'"([^"$`%!\n\r]*[^"$`%!\n\r\\])"')  # inside double quotes: no `"`, `$`, backtick, `%`, `!`
VERSION_FLAG = re.compile(r"-[0-9]+(\.[0-9]+)?")
LAUNCHER_NAMES = ("py", "py.exe")  # the Windows launcher: the only program that takes the version flag (C34)
MIN_PYTHON = (3, 9)
VERSION_PROBE = "import sys; print(sys.version_info[:2])"


def plain_interpreter(text, timeout=30) -> bool:
    """True when `text` is an existing executable (a name found on PATH, or a path; quoted when it holds a space)
    with no shell characters, followed by one version flag (`-3`, `-3.12`) only when the program is the `py`
    launcher (C34), and when it runs `-c "import sys; print(sys.version_info[:2])"` and reports Python 3.9 or later
    (fix checks N2, M1, L3)."""
    return interpreter_problem(text, timeout) is None


def interpreter_problem(text, timeout=30):
    """None when `text` passes the interpreter rule (see `plain_interpreter`); else "timeout" when the program did
    not answer within `timeout` seconds (it and its children are stopped), or "invalid" (fix check 3 L5)."""
    if not isinstance(text, str):
        return "invalid"
    m = re.fullmatch(r'("[^"]*"|\S+)(?: (\S+))?', text)
    if not m:
        return "invalid"
    exe, flag = m.group(1), m.group(2)
    q = QUOTED_EXE.fullmatch(exe)
    if q:
        path = q.group(1)
    elif UNQUOTED_EXE.fullmatch(exe):
        path = exe
    else:
        return "invalid"
    if flag is not None and (not VERSION_FLAG.fullmatch(flag)
                             or re.split(r"[\\/]", path)[-1].lower() not in LAUNCHER_NAMES):
        return "invalid"
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
    version = re.fullmatch(r"\((\d+), (\d+)\)", (out or "").strip())
    ok = proc.returncode == 0 and version is not None and (int(version[1]), int(version[2])) >= MIN_PYTHON
    return None if ok else "invalid"


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


def commit_message(profile, version: str) -> str:
    """MW-035: the install commit message: `<commit.message_prefix> mkway <version>: install`, no prefix when unset."""
    prefix = ((profile.get("commit") or {}).get("message_prefix") or "") if isinstance(profile, dict) else ""
    return (f"{prefix} " if prefix else "") + f"mkway {version}: install"


def commit_lines(profile, version: str) -> list:
    """MW-027, MW-035: the ONE line the owner pastes in the task root (PowerShell and bash): add the committed settings
    file and the bundle, then commit only those paths, so files staged by anyone else stay out of the commit."""
    paths = f"{SETTINGS_FILE} {profiles.bundle_root(profile)}"
    return [f'git add {paths}; git commit -m "{commit_message(profile, version)}" -- {paths}']


def run_commit(root: Path, profile, version: str) -> str:
    """Run the line of `commit_lines` in the root (the owner's terminal only; the CLI tripwire guards it)."""
    paths = [SETTINGS_FILE, profiles.bundle_root(profile)]
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


def install(root: Path, src: Path, *, ref=None, profile_arg=None, vcs=None, python=None, shared=None,
            commit=False) -> list:
    root = Path(root).resolve()
    report = []
    if shared is not None and schema_check._format_error("absolute-path", shared) is not None:
        raise InstallError("--shared must be an absolute path (for example C:/work/shared-state); nothing was written")
    ppath = paths.profile_path(root, profile_arg)
    if not _inside(ppath, root):
        raise InstallError("the profile path leads outside the root; nothing was written")
    profile, errors = profiles.load(ppath)
    starter = profile is None and errors == ["(profile): not found"]
    set_shared = False  # MW-026: `--shared` writes `state.shared_dir` into a profile that is already there
    if starter:
        profile = starter_profile(vcs or detect_vcs(root))
        if shared is not None:
            profile["state"]["shared_dir"] = shared  # MW-026: the owner's opt-in
        errors = profiles.validate(profile)
        if errors:  # C53 (R64): an engine writer never writes a profile the schema refuses
            raise InstallError("the starter profile would be invalid: " + "; ".join(errors[:5]) + "; nothing was "
                               "written")
    elif errors:
        if shared is not None:
            raise InstallError("the profile is invalid, so --shared cannot be written into it: " + "; ".join(errors[:5])
                               + "; nothing was written")
        report.append("profile: invalid, kept as it is: " + "; ".join(errors[:5]))
    elif shared is not None and (profile.get("state") or {}).get("shared_dir") != shared:
        profile = json.loads(json.dumps(profile))
        profile.setdefault("state", {})["shared_dir"] = shared
        errors = profiles.validate(profile)
        if errors:  # C53 (R64): an engine writer never writes a profile the schema refuses
            raise InstallError("the profile with --shared would be invalid: " + "; ".join(errors[:5]) + "; nothing "
                               "was written")
        set_shared = True
    profile = profile if isinstance(profile, dict) else {}
    vcs_now = profile.get("vcs") if profile.get("vcs") in ("git", "none") else (vcs or detect_vcs(root))
    if commit and vcs_now != "git":
        raise InstallError("--commit needs vcs git (the profile says none); nothing was written")
    bundle = profiles.bundle_root(profile)
    bdir = root / bundle
    copy = bdir / "engine"
    state = profiles.state_dir(root, profile)
    first_install = not state.exists()  # MW-012: shadow by default, only on a first install
    copy_is_link = copy.is_symlink() or (copy.exists() and not _inside(copy, root))
    if not _inside(bdir, root) or not _inside(state, root) or copy_is_link:
        raise InstallError(f"{bundle} leads outside the root (a link or a junction); nothing was written")
    used = python or (profile.get("python") or {}).get("command") or "python"
    if not plain_interpreter(used):
        raise InstallError("--python must name an existing Python 3.9 or later: a name found on PATH or a path "
                           "(quoted if it holds a space), no shell characters, and a version flag like -3 only "
                           "after the py launcher; nothing was written")
    files, version, sha = source_files(Path(src), ref)
    if not files:
        raise InstallError("the source holds none of the engine's files")
    if starter or set_shared:
        ppath.parent.mkdir(parents=True, exist_ok=True)
        tmp = ppath.with_name(ppath.name + ".tmp")  # a temp file, then replace: never a half-written profile
        tmp.write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, ppath)
        report.append(f"profile: starter written ({ppath.relative_to(root).as_posix()})" if starter else
                      f"profile: state.shared_dir set to {shared} ({ppath.relative_to(root).as_posix()})")
    if copy.exists() and not (bdir / "mkway.lock").is_file():  # checked above: inside the root, and no link
        raise InstallError(f"{bundle}/engine exists and has no mkway.lock beside it; it was not changed")
    leftover = _replace_copy(bdir, copy, files, bundle)  # MW-032: build beside, swap by rename, never half-deleted
    semver = files.get("VERSION", b"").decode("utf-8", "replace").strip() or None  # MW-016: beside the pinned sha
    lock = {"version": version, "semver": semver, "source_sha": sha, "date": datetime.date.today().isoformat(),
            "hash": copy_hash(copy)}
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
    _ensure_lines(bdir / ".gitignore", IGNORE_HEAD, [f"{name}/" for name in IGNORED_FOLDERS] + list(RUNTIME_IGNORES))
    have = (bdir / ".gitignore").read_text(encoding="utf-8").splitlines()
    old = [f"{name}/" for name in ("cards", "ledger") if f"{name}/" in have]
    if old:  # fix check 3 L7: an earlier install's lines; removing them is the upgrade card's (C36)
        report.append(f"ignore: {bundle}/.gitignore still ignores {', '.join(old)} from an earlier install; "
                      "remove those lines: cards and ledger are tracked (R18)")
    if "engine/" in have:  # MW-035: the copy is tracked now; only that exact line of an earlier install goes
        kept = [line for line in (bdir / ".gitignore").read_text(encoding="utf-8").splitlines() if line != "engine/"]
        (bdir / ".gitignore").write_text("\n".join(kept) + "\n", encoding="utf-8")
        report.append("ignore: removed engine/ (from an earlier install)")
    copied = json.loads((copy / "engine" / "manifest.json").read_text(encoding="utf-8"))
    manifest = copied["entries"]
    default = paths.profile_path(root)
    rel = None if ppath.resolve() == default.resolve() else ppath.resolve().relative_to(root).as_posix()
    committed_python = (profile.get("python") or {}).get("command") or "python"  # MW-027: the committed entries never
    entries = generate_entries(profile, manifest, profile_rel=rel, python=committed_python,  # carry a machine's own
                               groups_table=copied.get("groups", {}))                       # interpreter
    write_settings(root / SETTINGS_FILE, entries, bundle)
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
        if commit:
            report.append(run_commit(root, profile, version_text))
        else:
            report.append("commit: paste this one line in the task folder (or run install again with --commit):")
            report += commit_lines(profile, version_text)
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
    A warning, never a failure; it only reads tags, the owner makes them. None when the root has no `VERSION` file."""
    import runner
    path = Path(root) / "VERSION"
    if not path.is_file():
        return None
    if "CLAUDECODE" in (os.environ if env is None else env):  # the owner's terminal only, as for the git builtins
        return "version tag: not compared inside a Claude chat (run `mkway check` in your own terminal)"
    want = "v" + path.read_text(encoding="utf-8").strip()
    try:
        proc = runner.git(root, "tag", "--points-at", "HEAD")
    except (OSError, subprocess.SubprocessError):
        return "version tag: not compared (git did not answer)"
    tags = proc.stdout.split() if proc.returncode == 0 else []
    if want in tags:
        return f"version tag: {want} at HEAD matches VERSION"
    if tags:
        return (f"version tag: warning: HEAD is tagged {', '.join(sorted(tags))}, which differs from VERSION "
                f"({want}); the owner tags the release")
    return f"version tag: warning: the tag {want} is missing at HEAD; the owner tags the release (check never writes one)"


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


FAILED_NAMES_MAX = 10  # MW-025: the check line names at most this many failing tests


def failed_names(output: str) -> str:
    """MW-025: `; failed: <node>, ...` for the `FAILED`/`ERROR` rows of pytest's short summary: up to ten names, then
    `and N more`; empty when the output has none (a crash before collection)."""
    names = []
    for m in re.finditer(r"^(?:FAILED|ERROR) (\S+)", output or "", re.M):
        if m.group(1) not in names:
            names.append(m.group(1))
    if not names:
        return ""
    text = "; failed: " + ", ".join(names[:FAILED_NAMES_MAX])
    if len(names) > FAILED_NAMES_MAX:
        text += f" and {len(names) - FAILED_NAMES_MAX} more"
    return text


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
    try:
        lock = json.loads((bdir / "mkway.lock").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        lock = None
    if lock is None:
        lines.append("copy hash: no lock (fix: mkway install)")
        ok = False
    elif lock.get("hash") == copy_hash(copy):
        lines.append("copy hash: matches the lock")
    else:
        lines.append("copy hash: differs from the lock (fix: mkway install)")
        ok = False
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
    summary = (proc.stdout.strip().splitlines() or ["no output"])[-1]
    if proc.returncode == 0:
        passed = re.search(r"(\d+) passed", summary)
        lines.append(f"tests: {passed.group(1) if passed else 0} passed")
    else:
        lines.append(f"tests: not green ({summary})" + failed_names(proc.stdout))
        ok = False
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
