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
"""
from __future__ import annotations

import datetime
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import helpers
import logs
import profiles

NEVER_OPEN = ("locks", "register", "state")


@dataclass
class Target:
    name: str
    entries: list
    built_in: bool
    open_by_default: bool = False  # a profile target open until the owner's marker (MW-010)


def built_in(root, profile, profile_file=None) -> list:
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
    taken = {t.name for t in built_in(root, profile)}
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
    taken = {t.name for t in built_in(root, profile)} | {t.name for t in defaults}
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


def targets(root, profile, profile_file=None) -> list:
    return built_in(root, profile, profile_file) + profile_targets(root, profile)


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


def is_open(root, profile, name: str, now=None) -> bool:
    if name in NEVER_OPEN:
        return False
    if name in default_open_names(root, profile):
        return not hold_closed(root, profile, name)  # the marker is the owner's close; no expiry
    now = now or logs.now()
    states = [_marker_state(p, now) for p in _marker_files(root, profile, name)]
    return "closed" not in states and "open" in states  # MW-022: closed wins between the shared and the local marker


def closed_target(root, profile, rel: Optional[str], profile_file=None) -> Optional[Target]:
    """The closed target that holds the repo path, or None."""
    if rel is None:
        return None
    for t in targets(root, profile, profile_file):
        if any(helpers.matches(rel, e) for e in t.entries) and not is_open(root, profile, t.name):
            return t
    return None


def _glob_folder(entry: str) -> Optional[str]:
    """The literal folder in front of a glob entry's first wildcard (`docs` for `docs/**/*.md`), "" for a glob at
    the root, None for a slash-free glob (it matches in any folder)."""
    if "/" not in entry.rstrip("/"):
        return None
    head = entry[:min(i for i, ch in enumerate(entry) if ch in "*?[")]
    return head.rsplit("/", 1)[0] if "/" in head else ""


def _file_in(root, rel: str, entry: str) -> Optional[str]:
    """The first file on disk inside the folder `rel` that the entry matches, or None (`.git` is not read)."""
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
    """(closed target, what shows it) when the path `rel` holds a closed target: the root holds every target; a
    folder holds a literal entry below it, a glob whose literal folder is below it or is it, or a file on disk that
    a glob entry matches. None otherwise (list item 2, R37 (a) H2)."""
    if rel is None:
        return None
    fold = helpers._fold
    for t in targets(root, profile, profile_file):
        if is_open(root, profile, t.name):
            continue
        for raw in t.entries:
            e = raw.strip().replace("\\", "/")
            e = e[2:] if e.startswith("./") else e
            if rel == ".":
                return t, e.rstrip("/")
            if not any(ch in e for ch in "*?["):
                if fold(e.rstrip("/")).startswith(fold(rel) + "/"):
                    return t, e.rstrip("/")
                continue
            folder = _glob_folder(e)
            if folder is not None and (fold(folder) == fold(rel) or fold(folder).startswith(fold(rel) + "/")):
                return t, e
            hit = _file_in(root, rel, e)
            if hit:
                return t, hit
    return None


def _literal_of(entry: str) -> Optional[str]:
    """The literal repo path an entry names: the entry itself, or a glob's literal folder; None for a slash-free
    glob or a glob at the root."""
    e = entry.strip().replace("\\", "/")
    e = e[2:] if e.startswith("./") else e
    if any(ch in e for ch in "*?["):
        return _glob_folder(e) or None
    return e.rstrip("/") or None


def _reaches(glob_parts: list, parts: list) -> bool:
    """True when a glob path's leading segments match a literal path's segments one by one (`mkway/engin?/x`
    reaches `mkway/engine`); a `**` segment reaches anything below where it stands (remainder item 4, H14)."""
    fold = helpers._fold
    for k, seg in enumerate(parts):
        if k >= len(glob_parts):
            return False
        if glob_parts[k] == "**":
            return True
        if not helpers.glob_re(fold(glob_parts[k])).fullmatch(fold(seg)):
            return False
    return True


def glob_target(root, profile, rel: Optional[str], profile_file=None):
    """(closed target, the path) when the glob path `rel` matches a closed target's literal path or one of its parent
    folders (`mkway/*` matches `mkway/engine`; list item 5), or its leading segments match the target's segments one
    by one, so it writes inside it (`mkway/engin?/gate_lock.py`; remainder item 4, R95 (4a)); None otherwise."""
    if rel is None:
        return None
    for t in targets(root, profile, profile_file):
        if is_open(root, profile, t.name):
            continue
        for entry in t.entries:
            lit = _literal_of(entry)
            parts = lit.split("/") if lit else []
            for k in range(len(parts), 0, -1):
                candidate = "/".join(parts[:k])
                if helpers.matches(candidate, rel):
                    return t, candidate
            if parts and _reaches(rel.split("/"), parts):
                return t, lit
    return None


_BEFORE = r"(?:^|(?<=[\s'\"/=:;,(\[{|&<>`]))"
_AFTER = r"(?=$|[\s'\"/;,)\]}|&<>`*?\[])"  # a glob character is a boundary too (remainder item 4, M1)


def named_target(root, profile, text: str, profile_file=None):
    """(closed target, the literal) when the command text names a closed target literally (list item 5, R43 (b);
    R81, R81a; close-fix 5, R84): its repo path of two or more segments with a path boundary on both sides; or its
    base name in a path position. A folder target's base name (`state`, `locks`, `engine`), a leading-dot file's
    (`.gitignore`), an undotted file's (`run`) and a one-segment literal (`docs`) count only right after `/` or
    `\\`, so a plain word never names a target; a dotted file's base name (`mkway.lock`) also counts after the start,
    a quote or a space. The base name ends before a quote, a space, a separator (folders only) or the end. None
    otherwise."""
    flat = (text or "").replace("\\", "/")
    flags = re.IGNORECASE if helpers.CASE_FOLD else 0
    for t in targets(root, profile, profile_file):
        if is_open(root, profile, t.name):
            continue
        for entry in t.entries:
            lit = _literal_of(entry)
            if not lit:
                continue
            if "/" in lit and re.search(_BEFORE + re.escape(lit) + _AFTER, flat, flags):  # close-fix 5: boundaries
                return t, lit
            base = lit.rsplit("/", 1)[-1]
            folder = entry.rstrip().endswith("/") or any(ch in entry for ch in "*?[")
            dotted = "." in base and not base.startswith(".")
            if folder or not dotted or "/" not in lit:  # R81, R84: right after a separator only
                pattern = r"/" + re.escape(base) + (r"(?=$|['\"\s/])" if folder else r"(?=$|['\"\s])")
            else:
                pattern = r"(?:^|[/'\"\s])" + re.escape(base) + r"(?=$|['\"\s])"
            if re.search(pattern, flat, flags):
                return t, lit
    return None


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
    names = {t.name for t in targets(root, profile)}
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
