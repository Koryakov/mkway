"""Lock targets and lock files (card MW-003, deliverable 3; spec section 1).

A target is a name and repo paths or globs. The built-in targets cannot be removed by the profile: the engine copy,
`mkway.lock`, the profile, the hook entries (`.claude/settings.json`, committed; MW-027, and the owner's `.claude/settings.local.json`),`<bundle.root>/locks/`, the
bundle `.gitignore` (R18) and `.gitattributes` (R19a), the register and `<state.dir>/`. `locks/`, the register and
the state folder are never open: their only writers are the engine's own commands. The profile adds targets in
`locks.targets[]`. A target in a user home folder needs a per-machine list and is off (R4).

A lock is `<shared state dir>/locks/<name>.json`: `{name, state, opened_at, until}` (MW-022: the shared state folder of
`profiles.shared_state_dir`, so a lock typed in any work tree of a repository reaches every session of it). Only the
owner's commands write it (`mkway lock open|close`, from their own terminal). A target is closed unless its lock is open
and not expired. For one version a marker of the older place, `<bundle.root>/locks/<name>.json` of the work tree, is
still read: closed wins. `mkway lock open` and `mkway go` remove it.

MW-063: this module reads and writes the markers (disk, clock). The matching of a path or a command text against the
targets is the pure core's (`core_lock`); `closed_target`, `held_target`, `glob_target` and `named_target` here read
the markers into a `closed` flag per target and ask the core.
"""
from __future__ import annotations

import dataclasses
import datetime
import json
import os
from pathlib import Path
from typing import Optional

import core_lock
import core_upgrade
import helpers
import logs
import profiles

NEVER_OPEN = core_lock.NEVER_OPEN
Target = core_lock.Target  # the target record is the pure core's; `closed` is read from the markers by `core_targets`


HOME_MARK = "<home>"  # stands for a home that cannot be found; a folder that still holds it is not resolved


def upgrade_resolution(env=None) -> tuple:
    """(entries, problems) of the `upgrade` target (MW-105, R260 a, R260d C6 and C7): the folder entries of the upgrade folder as
    `mkway upgrade` resolves it from this environment (`core_upgrade.upgrade_folder`, the same inputs as `upgrade.py`: home is
    HOME, else USERPROFILE, else the home folder) and, when MKWAY_UPGRADE_DIR names another folder, the default resolution too,
    so an owner-wide override never unguards the real folder. Each entry is an absolute folder in slashes with a trailing `/`.
    A folder that cannot be guarded is left out and named in `problems`, one text each: the home cannot be found (the default
    folder needs it), or the folder is not an absolute path (a relative override is accepted by the command, but a relative entry
    would be read as a folder of the repository). `env` None is the process environment."""
    env = os.environ if env is None else env
    windows = os.name == "nt"
    try:
        home = env.get("HOME") or env.get("USERPROFILE") or str(Path.home())
    except (RuntimeError, OSError, KeyError):  # no home: Path.home() raises RuntimeError, or KeyError for a user with no entry
        home = None
    plain = {k: v for k, v in env.items() if k != "MKWAY_UPGRADE_DIR"}
    first, override = core_upgrade.upgrade_folder(env, windows, home or HOME_MARK)
    second = core_upgrade.upgrade_folder(plain, windows, home or HOME_MARK)[0]
    entries, problems = [], []
    for folder, name in ((first, "MKWAY_UPGRADE_DIR" if override else "the default upgrade folder"),
                         (second, "the default upgrade folder")):
        if home is None and HOME_MARK in folder:
            problems.append(f"the home folder cannot be found (HOME and USERPROFILE are not set), so {name} is not guarded")
        elif not core_upgrade.is_full_path(folder, windows):
            problems.append(f"{name} is not an absolute path ({folder}), so it is not guarded")
        else:
            entry = folder.replace("\\", "/").rstrip("/") + "/"
            if entry not in entries:
                entries.append(entry)
        if not override:
            break  # one folder: the default is the first
    return entries, problems


def upgrade_entries(env=None) -> list:
    """The folder entries of the `upgrade` target (`upgrade_resolution`); a folder that cannot be guarded is left out."""
    return upgrade_resolution(env)[0]


def built_in(root, profile, profile_file=None, env=None, resolve=True) -> list:
    b = profiles.bundle_root(profile)
    state = profiles.state_dir(root, profile)
    state_rel = helpers.norm(str(state), root) or profiles.DEFAULT_STATE_DIR
    pfile = helpers.norm(str(profile_file), root) if profile_file else f"{b}/profile.json"
    return [
        Target("engine", [f"{b}/engine/"], True),
        Target("lock", [f"{b}/mkway.lock"], True),
        Target("profile", [pfile or f"{b}/profile.json"], True),
        Target("hooks", [".claude/settings.json", ".claude/settings.local.json"], True),  # MW-027: the committed file
        Target("locks", [f"{b}/locks/"], True),
        Target("gitignore", [f"{b}/.gitignore"], True),
        Target("gitattributes", [f"{b}/.gitattributes"], True),
        Target("register", [f"{b}/cards/REGISTER.md"], True),
        Target("state", [state_rel + "/"], True),
        Target("upgrade", upgrade_entries(env) if resolve else [], True),  # last: the first closed target names a refusal (MW-105)
    ]


STATE_PLACEHOLDER = "<state.dir>"  # in an engine default target's paths: the profile's own state folder (MW-018)


def _default_raw() -> list:
    """`locks.targets` of `defaults.json`: the engine's own targets (MW-018: `inbox`); [] when unreadable."""
    try:
        data = json.loads(profiles.DEFAULTS_FILE.read_text(encoding="utf-8"))
        raw = data["locks"]["targets"]
    except (OSError, ValueError, KeyError, TypeError):
        return []
    return raw if isinstance(raw, list) else []


def engine_targets(root, profile) -> list:
    """The engine default targets, with `<state.dir>` taken at this profile's state folder. They cannot be removed by
    the profile; a profile target of the same name is ignored."""
    state = profiles.state_dir(root, profile)
    state_rel = helpers.norm(str(state), root) or profiles.DEFAULT_STATE_DIR
    taken = {t.name for t in built_in(root, profile, resolve=False)}  # names only: no folder is resolved (R260d C6)
    out = []
    for t in _default_raw():
        if not isinstance(t, dict) or not isinstance(t.get("name"), str) or t["name"] in taken:
            continue
        entries = []
        for p in t.get("paths") or []:
            if not isinstance(p, str):
                continue
            rel = helpers.norm(p.replace(STATE_PLACEHOLDER, state_rel), root)
            if rel is not None:
                entries.append(rel + ("/" if p.rstrip().endswith("/") else ""))
        if entries:
            out.append(Target(t["name"], entries, False, t.get("open_by_default") is True))
    return out


def profile_targets(root, profile) -> list:
    """`locks.targets[]` entries inside the root; an entry outside it (a user home folder) is off (R4). The engine's
    own default targets come first (MW-018)."""
    raw = (profile.get("locks") or {}).get("targets") if isinstance(profile, dict) and isinstance(
        profile.get("locks"), dict) else None
    defaults = engine_targets(root, profile)
    out = list(defaults)
    taken = {t.name for t in built_in(root, profile, resolve=False)} | {t.name for t in defaults}
    for t in raw if isinstance(raw, list) else []:
        if not isinstance(t, dict) or not isinstance(t.get("name"), str) or t["name"] in taken:
            continue
        entries = []
        for p in t.get("paths") or []:
            if not isinstance(p, str) or p.strip().startswith("~"):
                continue
            rel = helpers.norm(p, root)
            if rel is not None:
                entries.append(rel + ("/" if p.rstrip().endswith("/") else ""))
        if entries:
            out.append(Target(t["name"], entries, False, t.get("open_by_default") is True))
    return out


def targets(root, profile, profile_file=None, env=None, resolve=True) -> list:
    return built_in(root, profile, profile_file, env, resolve) + profile_targets(root, profile)


def lock_folder(root, profile) -> Path:
    """The folder of the lock markers: the shared state folder's `locks/` (MW-022)."""
    return profiles.shared_state_dir(root, profile) / "locks"


def local_folder(root, profile) -> Path:
    """The older, per-work-tree folder `<bundle.root>/locks/`: read for one version as a fallback (MW-022)."""
    return Path(root) / profiles.bundle_root(profile) / "locks"


def lock_file(root, profile, name: str) -> Path:
    return lock_folder(root, profile) / f"{name}.json"


def local_file(root, profile, name: str) -> Path:
    return local_folder(root, profile) / f"{name}.json"


def _same(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except OSError:
        return a == b


def _marker_files(root, profile, name: str) -> list:
    """The marker paths of a target: the shared one, then the older local one when it is another file."""
    shared, local = lock_file(root, profile, name), local_file(root, profile, name)
    return [shared] if _same(shared, local) else [shared, local]


def local_markers(root, profile) -> list:
    """(name, path) of every marker file in the older per-work-tree folder (MW-022, `lock-marker-local`)."""
    folder = local_folder(root, profile)
    if _same(folder, lock_folder(root, profile)) or not folder.is_dir():
        return []
    return [(f.stem, f) for f in sorted(folder.glob("*.json"))]


def marker_warnings(root, profile) -> list:
    """One `lock-marker-local` line per older per-work-tree marker; the fix is the owner's `lock open` or `go`."""
    return [f"lock-marker-local: {path} is an older per-work-tree marker of {name!r}; the gates still read it for one "
            f"version (closed wins); the owner removes it with `mkway lock open {name}` or by deleting the file"
            for name, path in local_markers(root, profile)]


def _parse_time(text):
    try:
        t = datetime.datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=datetime.timezone.utc)


def default_open_names(root, profile) -> list:
    """Names of the profile targets that are open by default (the owner hold, MW-010)."""
    return [t.name for t in profile_targets(root, profile) if t.open_by_default]


def hold_closed(root, profile, name: str) -> bool:
    """True when the owner's marker of an open-by-default target exists, in the shared folder or in the older local
    one (MW-022: closed wins)."""
    return any(p.exists() for p in _marker_files(root, profile, name))


def _marker_state(path: Path, now) -> Optional[str]:
    """`open` for an open, unexpired marker; `closed` for any other marker file; None for no file."""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "closed"
    until = _parse_time(data.get("until")) if isinstance(data, dict) else None
    ok = isinstance(data, dict) and data.get("state") == "open" and until is not None and until > now
    return "open" if ok else "closed"


def _is_open(root, profile, name: str, defaults, now) -> bool:
    if name in NEVER_OPEN:
        return False
    if name in defaults:
        return not hold_closed(root, profile, name)  # the marker is the owner's close; no expiry
    states = [_marker_state(p, now) for p in _marker_files(root, profile, name)]
    return "closed" not in states and "open" in states  # MW-022: closed wins between the shared and the local marker


def is_open(root, profile, name: str, now=None) -> bool:
    return _is_open(root, profile, name, default_open_names(root, profile), now or logs.now())


def core_targets(root, profile, profile_file=None, env=None, resolve=True) -> tuple:
    """Every target with its `closed` flag read from the markers and the clock: the facts the pure core decides on.
    `env` is the environment of the call (the upgrade folder is read from it; None is the process environment). `resolve`
    False leaves the `upgrade` target with no entry: a caller that reads repo paths only (an absolute entry never matches one)."""
    defaults, now = default_open_names(root, profile), logs.now()
    return tuple(dataclasses.replace(t, closed=not _is_open(root, profile, t.name, defaults, now))
                 for t in targets(root, profile, profile_file, env, resolve))


def closed_target(root, profile, rel: Optional[str], profile_file=None) -> Optional[Target]:
    """The closed target that holds the repo path, or None."""
    if rel is None:
        return None
    return core_lock.closed_target(core_targets(root, profile, profile_file, resolve=False), rel)


def _file_in(root, rel: str, entry: str) -> Optional[str]:
    """The first file on disk inside the folder `rel` that the entry matches, or None (the git folder is not read)."""
    base = Path(root) / rel
    if not base.is_dir():
        return None
    for folder, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d != ".git"]
        for name in files:
            frel = Path(folder, name).relative_to(root).as_posix()
            if helpers.matches(frel, entry):
                return frel
    return None


def held_target(root, profile, rel: Optional[str], profile_file=None):
    """(closed target, what shows it) when the path `rel` holds a closed target (`core_lock.held_target`); the disk
    read for a glob entry is `_file_in`."""
    return core_lock.held_target(core_targets(root, profile, profile_file, resolve=False), rel, lambda r, e: _file_in(root, r, e))


def glob_target(root, profile, rel: Optional[str], profile_file=None):
    """(closed target, the path) when the glob path `rel` reaches a closed target (`core_lock.glob_target`)."""
    return core_lock.glob_target(core_targets(root, profile, profile_file, resolve=False), rel)


def named_target(root, profile, text: str, profile_file=None):
    """(closed target, the literal) when the command text names a closed target literally (`core_lock.named_target`)."""
    return core_lock.named_target(core_targets(root, profile, profile_file), text)


def open_locks(root, profile) -> list:
    """(name, until) of every open, unexpired lock, read from the shared folder and the older local one."""
    names = set()
    for folder in (lock_folder(root, profile), local_folder(root, profile)):
        names |= {f.stem for f in folder.glob("*.json")} if folder.is_dir() else set()
    out = []
    for name in sorted(names):
        if name in default_open_names(root, profile) or not is_open(root, profile, name):
            continue
        until = None
        for path in _marker_files(root, profile, name):
            try:
                until = json.loads(path.read_text(encoding="utf-8")).get("until")
                break
            except (OSError, ValueError, AttributeError):
                continue
        out.append((name, until))
    return out


class LockError(Exception):
    pass


def _drop_local(root, profile, name: str) -> None:
    """The owner's word replaces an older per-work-tree marker of the target (MW-022)."""
    shared, local = lock_file(root, profile, name), local_file(root, profile, name)
    if not _same(shared, local):
        local.unlink(missing_ok=True)


def set_lock(root, profile, name: str, state: str, minutes: float = 60) -> dict:
    """The owner's `mkway lock open|close <name>`."""
    names = {t.name for t in targets(root, profile, resolve=False)}
    if name in NEVER_OPEN:
        raise LockError(f"{name} is never open: only the engine's own commands write it")
    if name not in names:
        raise LockError(f"no lock target named {name!r} (built-in or locks.targets[] in the profile)")
    now = logs.now()
    if name in default_open_names(root, profile):  # the owner hold: a marker file closes it, no marker opens it
        path = lock_file(root, profile, name)
        if state == "open":
            path.unlink(missing_ok=True)
            _drop_local(root, profile, name)
            return {"name": name, "state": "open", "until": "no end: open by default"}
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {"name": name, "state": "closed", "opened_at": now.isoformat(timespec="seconds"),
                "until": now.isoformat(timespec="seconds")}
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(data, indent=2) + "\n")
        return data
    data = {"name": name, "state": state, "opened_at": now.isoformat(timespec="seconds"),
            "until": (now + datetime.timedelta(minutes=minutes)).isoformat(timespec="seconds")
            if state == "open" else now.isoformat(timespec="seconds")}
    path = lock_file(root, profile, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(data, indent=2) + "\n")
    _drop_local(root, profile, name)
    return data


def hold_lines(root, profile) -> list:
    """One line for each target that is open by default: `<name>: open (default)` or `<name>: closed by the owner`."""
    return [f"{n}: " + ("closed by the owner" if hold_closed(root, profile, n) else "open (default)")
            for n in default_open_names(root, profile)]
