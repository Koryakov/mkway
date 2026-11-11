"""The delete backup and its record (card MW-009, the owner's order of 2026-11-10).

Before a delete runs, every target is copied into `<state.dir>/trash/<timestamp>/<repo path>` (the state folder is
ignored by git and is a lock target nobody opens) and one row is appended to `<state.dir>/deletes.jsonl`: session,
time, via (`gate` or `list`), targets, the backup folder (a repo path; none for a delete git itself keeps). The size of
all targets is limited by `delete.max_backup_mb`; a failed copy or record is a refusal, never a delete without its
backup. The engine never empties the trash by itself: only the owner's `mkway trash empty` does.
"""
from __future__ import annotations

import datetime
import json
import os
import re
import shutil
import stat
import sys
from pathlib import Path

import helpers
import locks
import logs
import profiles

STAMP = re.compile(r"^(\d{8}T\d{6}-\d{6})(?:-\d+)?$")
TRASH = "trash"
RECORDS = "deletes.jsonl"
MB = 1024 * 1024


class BackupError(Exception):
    """A refusal: `reason` is the reason id (`delete-too-large` or `delete-backup-failed`), `message` its text."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason, self.message = reason, message


def size_of(root, rels) -> int:
    """The bytes of the targets: a file by its size, a folder by the files under it (links are not followed)."""
    total = 0
    for rel in rels:
        path = Path(root) / rel
        if path.is_dir() and not path.is_symlink():
            for here, _dirs, files in os.walk(path):
                total += sum(os.lstat(os.path.join(here, name)).st_size for name in files)
        else:
            total += os.lstat(path).st_size
    return total


def _outermost(rels) -> list:
    """The targets that lie inside no other target: copying `d` copies `d/b.txt` too."""
    return [r for r in rels if not any(o != r and r.startswith(o + "/") for o in rels)]


def _new_folder(base: Path) -> Path:
    now = logs.now()
    stamp = f"{now:%Y%m%dT%H%M%S}-{now:%f}"
    base.mkdir(parents=True, exist_ok=True)
    for n in range(1, 1000):
        folder = base / (stamp if n == 1 else f"{stamp}-{n}")
        try:
            folder.mkdir()
            return folder
        except FileExistsError:
            continue
    raise OSError("no free backup folder name")


def record(root, state, rels, *, session, backup, via, by=None) -> dict:
    """Append the record row; a row that cannot be written is `delete-backup-failed`. `backup` is the backup folder
    or None; `by` (`session` or `owner`) is set by the commands, which know no session id."""
    row = {"time": logs.now().isoformat(timespec="milliseconds"), "session": session, "via": via,
           "targets": list(rels),
           "backup": None if backup is None else Path(os.path.relpath(backup, root)).as_posix()}
    if by is not None:
        row["by"] = by
    try:
        logs.append_jsonl(Path(state) / RECORDS, row)
    except OSError as exc:
        raise BackupError("delete-backup-failed", f"the record row of this delete could not be written ({exc}), so "
                                                  "the delete is refused; nothing was deleted") from None
    return row


def backup(root, state, rels, *, session, max_mb, via="gate", kept=(), order=None, by=None) -> dict:
    """Copy the targets into a new trash folder and write the record row; returns the row. Raises BackupError.
    `kept` are targets git itself keeps (a clean tracked file removed by `git rm`): they are recorded, never copied;
    `order` is the row's target list (the command's order), by default the copied targets then the kept ones. With
    nothing to copy there is no folder and the row's backup is None."""
    root, state = Path(root), Path(state)
    listed = list(order) if order is not None else list(rels) + list(kept)
    if not rels:
        return record(root, state, listed, session=session, backup=None, via=via, by=by)
    try:
        total = size_of(root, rels)
    except OSError as exc:
        raise BackupError("delete-backup-failed", f"the size of {', '.join(rels)} could not be read ({exc}), so "
                                                  "the delete is refused; nothing was deleted") from None
    if total > max_mb * MB:
        raise BackupError("delete-too-large", f"the backup of {', '.join(rels)} is {total / MB:.1f} MB, above "
                                              f"`delete.max_backup_mb` ({max_mb:g}); this delete needs the owner's "
                                              "terminal")
    try:
        folder = _new_folder(state / TRASH)
    except OSError as exc:
        raise BackupError("delete-backup-failed", f"the trash folder could not be made ({exc}), so the delete is "
                                                  "refused; nothing was deleted") from None
    for rel in _outermost(list(rels)):
        src, dest = root / rel, folder / rel
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir() and not src.is_symlink():
                shutil.copytree(src, dest, symlinks=True)
            else:
                shutil.copy2(src, dest, follow_symlinks=False)
        except (OSError, shutil.Error) as exc:
            raise BackupError("delete-backup-failed", f"copying {rel} into the trash failed ({exc}), so the delete "
                                                      "is refused; nothing was deleted") from None
    return record(root, state, listed, session=session, backup=folder, via=via, by=by)


# ---- the commands: `mkway delete --list`, `mkway trash list`, `mkway trash empty` ------------------------------------

def _writable(func, path, _exc):
    os.chmod(path, stat.S_IWRITE)  # a read-only file on Windows
    func(path)


def remove(path: Path) -> None:
    """Remove a file, a link or a folder with its content."""
    path = Path(path)
    if path.is_dir() and not path.is_symlink():
        if sys.version_info >= (3, 12):
            shutil.rmtree(path, onexc=_writable)
        else:
            shutil.rmtree(path, onerror=_writable)
    else:
        try:
            os.remove(path)
        except PermissionError:
            os.chmod(path, stat.S_IWRITE)
            os.remove(path)


def read_list(root, profile, profile_file, text: str):
    """(repo paths, problems) of a list file: one exact repo path per line; each must exist, lie inside the root, hold
    no wildcard, and lie in or hold neither a closed lock target nor the engine's state folder. A problem names the
    line number, the line and the reason."""
    root = Path(root)
    state = helpers.norm(str(profiles.state_dir(root, profile)), root)
    prefix = helpers.top_prefix(root)
    rels, problems = [], []
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        why = None
        rel = None if any(ch in line for ch in "*?[") else helpers.norm(line, root, top_prefix=prefix)
        if any(ch in line for ch in "*?["):
            why = "is a wildcard: list exact paths"
        elif rel is None:
            why = "lies outside the root"
        elif rel == ".":
            why = "is the root itself"
        elif state and (rel == state or state.startswith(rel + "/") or rel.startswith(state + "/")):
            why = "is or holds the engine's state folder"
        elif not os.path.lexists(root / rel):
            why = "does not exist"
        else:
            closed = locks.closed_target(root, profile, rel, profile_file)
            held = None if closed else locks.held_target(root, profile, rel, profile_file)
            if closed:
                why = f"is inside the closed lock {closed.name!r}"
            elif held:
                why = f"holds {held[1]}, which is inside the closed lock {held[0].name!r}"
        if why:
            problems.append(f"line {number}: {line} {why}")
        elif rel not in rels:
            rels.append(rel)
    if not rels and not problems:
        problems.append("the list holds no path")
    return rels, problems


def delete_list(root, profile, profile_file, text: str, *, max_mb, by):
    """`mkway delete --list`: (exit code, lines to print or the problems). Any bad line deletes nothing; else the
    targets are backed up, recorded (`via: list`) and deleted."""
    root = Path(root)
    rels, problems = read_list(root, profile, profile_file, text)
    if problems:
        return 1, problems
    state = profiles.state_dir(root, profile)
    try:
        row = backup(root, state, rels, session=None, max_mb=max_mb, via="list", by=by)
    except BackupError as exc:
        return 1, [exc.message]
    failed = []
    for rel in _outermost(rels):
        try:
            remove(root / rel)
        except OSError as exc:
            failed.append(f"{rel} could not be deleted ({exc.__class__.__name__}); its backup is in {row['backup']}")
    if failed:
        return 1, failed
    return 0, [f"deleted {len(rels)} paths; backup in {row['backup']}"]


def _folder_info(folder: Path):
    files = size = 0
    for here, _dirs, names in os.walk(folder):
        files += len(names)
        size += sum(os.lstat(os.path.join(here, name)).st_size for name in names)
    return files, size


def _rows(state):
    try:
        lines = (Path(state) / RECORDS).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def listing(root, state) -> list:
    """One line per trash folder: name, files, size, and the targets of its record row."""
    base = Path(state) / TRASH
    names = sorted(os.listdir(base)) if base.is_dir() else []
    backups = {str(r.get("backup")).rsplit("/", 1)[-1]: r for r in _rows(state) if r.get("backup")}
    lines = []
    for name in names:
        files, size = _folder_info(base / name)
        row = backups.get(name)
        targets = ", ".join(row.get("targets", [])) if row else "no record row"
        lines.append(f"{name}  {files} files  {size / MB:.2f} MB  {targets}")
    return lines or ["the trash is empty"]


def empty(root, state, days: float, *, by="owner"):
    """Remove the trash folders older than `days` by the stamp in their name; a folder whose name is no stamp is never
    touched. Returns (names removed, bytes freed); one record row (`via: trash-empty`) when anything was removed."""
    base = Path(state) / TRASH
    now = logs.now()
    removed, freed = [], 0
    for name in sorted(os.listdir(base)) if base.is_dir() else []:
        m = STAMP.match(name)
        if not m:
            continue
        stamp = datetime.datetime.strptime(m.group(1), "%Y%m%dT%H%M%S-%f").replace(tzinfo=datetime.timezone.utc)
        if now - stamp > datetime.timedelta(days=days):
            freed += _folder_info(base / name)[1]
            remove(base / name)
            removed.append(name)
    if removed:
        record(root, state, removed, session=None, backup=None, via="trash-empty", by=by)
    return removed, freed
