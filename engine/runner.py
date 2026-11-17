"""The one helper that runs a program (card MW-003, deliverable 10; R15 A8).

Engine code runs a program only through this module, and this module runs only `git` or the configured Python (the
running interpreter, or the interpreter named by the caller: the profile's `python.command`, `machine.json`, the
owner's `--python`). Anything else is refused at run time (`Refused`), before it starts. A test scans every engine
code file and fails on a `subprocess` use anywhere else, and on a network or database import. When MW-005 adds
product checks, the only exception is one named runner module; the rule itself never widens (ruled 09.11).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from typing import Optional

PIPE = subprocess.PIPE
DEVNULL = subprocess.DEVNULL
TimeoutExpired = subprocess.TimeoutExpired
SubprocessError = subprocess.SubprocessError
GIT = ["git", "--no-optional-locks"]
KILL_SECONDS = 4
DRAIN_SECONDS = 2


class Refused(Exception):
    """A program that is neither git nor the configured Python."""


def _same(a: str, b: str) -> bool:
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def allowed(program: str, python: Optional[str] = None) -> bool:
    name = os.path.basename(str(program)).lower()
    if name in ("git", "git.exe"):
        return True
    found = shutil.which(str(program)) or str(program)
    for p in (sys.executable, python):
        if p and (_same(found, p) or _same(found, shutil.which(p) or p)):
            return True
    return False


def _check(argv, python):
    if not argv or not allowed(argv[0], python):
        raise Refused(f"the engine runs only git or the configured Python, not {argv[0] if argv else '(nothing)'!r}")


def run(argv: list, *, python: Optional[str] = None, **kwargs) -> subprocess.CompletedProcess:
    _check(argv, python)
    return subprocess.run(argv, **kwargs)


def popen(argv: list, *, python: Optional[str] = None, **kwargs) -> subprocess.Popen:
    _check(argv, python)
    return subprocess.Popen(argv, **kwargs)


GIT_TIMEOUT = 10  # list item 11 (R44 row 4): the default limit; new cards set per-call limits


DIFF_NAMES = ("diff.relative=false",)  # MW-140: the pin of a `git diff` that prints file names, see `git(config=...)`


def git(cwd, *args, timeout: float = 10, text: bool = True, config: tuple = ()) -> subprocess.CompletedProcess:
    """`git --no-optional-locks -C <cwd> [-c <key=value> ...] <args>`, output captured; `subprocess.TimeoutExpired` after
    `timeout` seconds (10 by default, GIT_TIMEOUT). `config` pins settings for this one call (`-c` wins over the repository's
    and the user's config): a `git diff` that prints names passes `DIFF_NAMES`, because `diff.relative=true` makes it print
    names relative to the current folder and leave out every file outside that folder (MW-140). The `-c` pairs come before
    the subcommand, so `args` keeps its first word."""
    pins = [word for setting in config for word in ("-c", setting)]
    return run(GIT + ["-C", str(cwd), *pins, *args], capture_output=True, text=text, timeout=timeout)


# ---- stopping a process tree -------------------------------------------------------------------------------------------

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


def windows_job(proc):
    """On Windows, a job object holding the process, so a stop reaches every process it started, a grandchild whose
    parent already exited included. None elsewhere, or when the job cannot be made."""
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


def close_job(job) -> None:
    if job:
        try:
            _kernel32().CloseHandle(job)
        except (OSError, AttributeError):
            pass


def stop_tree(proc, job=None) -> None:
    """Stop a process and every process it started: the job object on Windows, the process group elsewhere, else
    `proc.kill()` (no other program is run to do it, deliverable 10)."""
    stopped = False
    try:
        if job:
            stopped = bool(_kernel32().TerminateJobObject(job, 1))
        elif os.name != "nt":
            import signal
            os.killpg(proc.pid, signal.SIGKILL)
            stopped = True
    except (OSError, AttributeError):
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


def run_tree(argv: list, *, timeout: float, python: Optional[str] = None, **kwargs):
    """Run with a time limit; on timeout stop the whole tree. Returns (returncode or None on timeout, stdout,
    stderr)."""
    _check(argv, python)
    proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            start_new_session=(os.name != "nt"), **kwargs)
    job = windows_job(proc)
    try:
        try:
            out, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            stop_tree(proc, job)
            return None, "", ""
    finally:
        close_job(job)
    return proc.returncode, out, err
