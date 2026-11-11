"""The task root and the profile location (card MW-002, deliverable 5; defects 21-22, R8).

The root is `--root <path>`, else `$CLAUDE_PROJECT_DIR`, else (vcs git) `git rev-parse --show-toplevel` run from
the current folder; below that top, the nearest folder up from the current folder that holds `mkway/profile.json`
wins (MW-024), and without one the top stays the answer. With vcs none and neither given there is no root. The root is never computed from the engine's
own location.

The profile is `--profile <path>` (a relative path is read from the root), else `<root>/mkway/profile.json`. No
profile key holds the profile's location.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Mapping, Optional

ROOT_ENV = "CLAUDE_PROJECT_DIR"
PROFILE_FOLDER = "mkway"
PROFILE_NAME = "profile.json"


class RootNotFound(Exception):
    """No --root, no $CLAUDE_PROJECT_DIR, and no git work tree to ask (or vcs none)."""


def find_root(env: Optional[Mapping[str, str]] = None, root_arg: Optional[str] = None, vcs: Optional[str] = None,
              cwd: Optional[Path] = None) -> Path:
    env = os.environ if env is None else env
    if root_arg:
        return Path(root_arg).resolve()
    if env.get(ROOT_ENV):
        return Path(env[ROOT_ENV]).resolve()
    if vcs == "none":
        raise RootNotFound("no --root and no $CLAUDE_PROJECT_DIR; vcs is none, so git is not asked")
    try:
        proc = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=str(cwd) if cwd else None,
                              capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        raise RootNotFound(f"git could not be run: {exc.__class__.__name__}") from None
    top = proc.stdout.strip()
    if proc.returncode != 0 or not top:
        raise RootNotFound("no --root, no $CLAUDE_PROJECT_DIR, and not inside a git work tree")
    top = Path(top).resolve()
    here = Path(cwd).resolve() if cwd else Path.cwd().resolve()  # MW-024: the task root may sit below the git top
    for folder in (here, *here.parents):
        if (folder / PROFILE_FOLDER / PROFILE_NAME).is_file():
            return folder
        if folder == top:
            break
    return top


def profile_path(root: Path, profile_arg: Optional[str] = None) -> Path:
    if profile_arg:
        p = Path(profile_arg)
        return p if p.is_absolute() else Path(root) / p
    return Path(root) / PROFILE_FOLDER / PROFILE_NAME
