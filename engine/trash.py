"""The delete backup and its record (card MW-009, the owner's order of 2026-11-10).

Before a delete runs, every target is copied into `<state.dir>/trash/<timestamp>/<repo path>` (the state folder is
ignored by git and is a lock target nobody opens) and one row is appended to `<state.dir>/deletes.jsonl`: session,
time, via (`gate` or `list`), targets, the backup folder (a repo path; none for a delete git itself keeps). The size of
all targets is limited by `delete.max_backup_mb`; a failed copy or record is a refusal, never a delete without its
backup. The engine never empties the trash by itself: only the owner's `mkway trash empty` does.
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import sys
from pathlib import Path

import core_delete as core
import helpers
import locks
import logs
import profiles

STAMP = core.STAMP
TRASH = "trash"
RECORDS = "deletes.jsonl"
MB = core.MB


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
    row = core.record_row(logs.now().isoformat(timespec="milliseconds"), session, via, rels,
                          None if backup is None else Path(os.path.relpath(backup, root)).as_posix(), by)
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
    too_large = core.too_large(total, max_mb, rels)
    if too_large:
        raise BackupError(too_large.reason, too_large.message)
    try:
        folder = _new_folder(state / TRASH)
    except OSError as exc:
        raise BackupError("delete-backup-failed", f"the trash folder could not be made ({exc}), so the delete is "
                                                  "refused; nothing was deleted") from None
    for rel in core.outermost(list(rels)):
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
    prefix = helpers.top_prefix(root)
    facts = core.Facts(state=helpers.norm(str(profiles.state_dir(root, profile)), root))
    while True:
        try:
            return core.list_problems(text, facts)
        except core.Need as need:
            if need.kind == "lnorm":
                answer = helpers.norm(need.key, root, top_prefix=prefix)
            elif need.kind == "lexists":
                answer = os.path.lexists(root / need.key)
            else:  # `locks`: the closed lock the path is in, else a path it holds in a closed lock
                closed = locks.closed_target(root, profile, need.key, profile_file)
                held = None if closed else locks.held_target(root, profile, need.key, profile_file)
                answer = (closed.name if closed else None, (held[0].name, held[1]) if held else None)
            facts.answers[(need.kind, need.key)] = answer


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
    for rel in core.outermost(rels):
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
    removed, freed = [], 0
    names = sorted(os.listdir(base)) if base.is_dir() else []
    for name in core.stale_folders(names, logs.now().timestamp(), days):
        freed += _folder_info(base / name)[1]
        remove(base / name)
        removed.append(name)
    if removed:
        record(root, state, removed, session=None, backup=None, via="trash-empty", by=by)
    return removed, freed
