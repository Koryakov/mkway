"""Card records in the shared folder (card MW-129; rulings R307, R310, R312).

A card record file is a file whose rows belong to a card and are read later by a gate or command that may run in another
checkout (the audit is `cards/MW-129-shared-records/AUDIT.md`). One home per task: the shared folder, `profiles.shared_state_dir`
(`state.shared_dir` when set, else the state dir, so a task with one checkout sees no change). A gate reads a card record ONLY
from there, never from another checkout's state (R307 refuses a search across work trees at run time).

- `shared_path(root, profile, name)`: the one function that names the path of a card record file.
- `read_rows(root, profile, name)`: its rows; a line that is not JSON (a cut-off last line included) is skipped.
- `append_row(root, profile, name, row, key=None)`: one complete line under the append lock (`logs.append_jsonl_locked`); with
  a `key` (field names) a row whose key is already in the file is not written (the check and the append are one step).
- `migrate(root, profile, write=...)`: the upgrade's step that copies the card record rows of the main checkout and of every
  live work tree into the shared folder. Run only by `mkway upgrade` (no command of a session, no copy at run time: R312).

Session-run files (gate calls, timings, refusals) stay per checkout and are not here.
"""
from __future__ import annotations

import json
from pathlib import Path

import logs
import profiles
import runner

# The card record files that move, each with its own write key (R310 3 a): red proof is one row per tree and card.
CARD_FILES = {"red_proof.jsonl": ("tree", "card")}
NOOP_TEXT = "the shared folder is the state folder of the main checkout: nothing to migrate"
READ, NO_STATE, PRUNABLE = "read", "no state folder", "prunable"
GIT_SECONDS = 30

AppendBusy = logs.AppendBusy


class MigrationFailed(Exception):
    """The copy could not be completed (a folder that cannot be made, a file that cannot be read or written)."""


def shared_path(root, profile, name: str) -> Path:
    return profiles.shared_state_dir(Path(root), profile) / name


def parse(text: str) -> tuple:
    """(rows, skipped): the JSON objects of the text in order, and the number of non-empty lines that are not one."""
    rows, skipped = [], 0
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            skipped += 1
            continue
        if isinstance(row, dict):
            rows.append(row)
        else:
            skipped += 1
    return rows, skipped


def _text_of(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def read_rows(root, profile, name: str) -> list:
    return parse(_text_of(shared_path(root, profile, name)))[0]


def _key_of(row: dict, key) -> tuple:
    return tuple(row.get(k) for k in key)


def append_row(root, profile, name: str, row: dict, key=None) -> bool:
    """True when the row was written, False when its key was already in the file. Raises `logs.AppendBusy` when the lock
    stays busy beyond the bounded wait: nothing is written."""
    want = _key_of(row, key) if key else None

    def build(text):
        if want is not None and any(_key_of(r, key) == want for r in parse(text)[0]):
            return None
        return row
    return logs.append_jsonl_locked(shared_path(root, profile, name), build) is not None


# ---- the migration ----------------------------------------------------------------------------------------------------

def _worktrees(root: Path) -> list:
    """[(path, prunable)] of `git worktree list --porcelain` run in the root's repository, in git's order; [] when git cannot
    answer."""
    try:
        done = runner.git(root, "worktree", "list", "--porcelain", timeout=GIT_SECONDS)
    except Exception:
        return []
    if done.returncode != 0:
        return []
    out, block = [], []
    for line in done.stdout.splitlines() + [""]:
        if line.strip():
            block.append(line.strip())
            continue
        if block:
            first = block[0]
            if first.startswith("worktree "):
                out.append((first[len("worktree "):], any(b == "prunable" or b.startswith("prunable ") for b in block)))
            block = []
    return out


def _top_of(root: Path):
    try:
        done = runner.git(root, "rev-parse", "--show-toplevel", timeout=GIT_SECONDS)
    except Exception:
        return None
    return Path(done.stdout.strip()).resolve() if done.returncode == 0 and done.stdout.strip() else None


def _sources(root: Path, profile) -> tuple:
    """([(label path, state folder or None)], [report entry]) in the order main first, then the work trees in git's order."""
    root = Path(root).resolve()
    own = profiles.state_dir(root, profile).resolve()
    top = _top_of(root)
    below = own.relative_to(top) if top is not None and own.is_relative_to(top) else None
    entries = [(Path(p), pruned) for p, pruned in _worktrees(root)]
    entries.sort(key=lambda e: 0 if top is not None and e[0].resolve() == top else 1)  # the root's own checkout first (stable)
    if not entries:
        entries = [(root, False)]
    found, report = [], []
    for folder, pruned in entries:
        shown = folder.as_posix()
        if pruned or not folder.is_dir():
            report.append({"path": shown, "state": PRUNABLE})
            continue
        state = own if top is not None and folder.resolve() == top else (folder / below if below is not None else None)
        if state is None or not state.is_dir():
            report.append({"path": shown, "state": NO_STATE})
            continue
        found.append((folder, state))
        report.append({"path": shown, "state": READ})
    return found, report


def _in_time_order(rows: list) -> list:
    """R310 3 b: the rows that have a `time` are put in time order, ties in source order; a row with no `time` keeps its place
    in the source list (main first, then the work trees in git's order)."""
    slots = [i for i, r in enumerate(rows) if r.get("time")]
    timed = sorted((rows[i] for i in slots), key=lambda r: str(r["time"]))  # stable
    out = list(rows)
    for i, r in zip(slots, timed):
        out[i] = r
    return out


def _line(name: str, c: dict) -> str:
    return (f"{name}: rows found {c['found']}, copied {c['copied']}, already present {c['present']}, broken lines skipped "
            f"{c['skipped']}, turned away by the key {c['turnedAway']}")


def migrate(root, profile, *, write: bool) -> dict:
    """Copy the card record rows of the main checkout and of every live work tree into the shared folder of `profile` (the
    profile the task will have). Identity is the file's own write key; rows go in `time` order, ties and rows with no time in
    source order (main first, then the work trees in `git worktree list` order). A row equal to one already in the shared
    file is `present`; a row with the key of one already there but other content is `turnedAway`; a line that is not JSON is
    `skipped` (a cut-off last line included). Old files are never touched. `write=False` reports the same plan and writes
    nothing. Raises `MigrationFailed` when a file cannot be read or written."""
    root = Path(root)
    shared = profiles.shared_state_dir(root, profile)
    own = profiles.state_dir(root, profile)
    if shared.resolve() == own.resolve():
        return {"sharedDir": str(shared), "noop": True, "dryRun": not write, "message": NOOP_TEXT, "files": [], "worktrees": [],
                "lines": [NOOP_TEXT]}
    sources, worktrees = _sources(root, profile)
    files, lines = [], []
    for name, key in CARD_FILES.items():
        rows, skipped = [], 0
        for _folder, state in sources:
            path = Path(state) / name
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                raise MigrationFailed(f"{path} cannot be read ({exc.strerror or exc.__class__.__name__})")
            got, bad = parse(text)
            rows += got
            skipped += bad
        rows = _in_time_order(rows)
        target = shared / name
        have = parse(_text_of(target))[0]
        counts = {"file": name, "found": len(rows), "copied": 0, "present": 0, "skipped": skipped, "turnedAway": 0}
        for row in rows:
            if row in have:
                counts["present"] += 1
            elif key and any(_key_of(r, key) == _key_of(row, key) for r in have):
                counts["turnedAway"] += 1
            else:
                if write:
                    try:
                        wrote = append_row(root, profile, name, row, key=key)
                    except (OSError, logs.AppendBusy) as exc:
                        raise MigrationFailed(f"{target} cannot be written ({getattr(exc, 'strerror', None) or exc.__class__.__name__})")
                    if not wrote:  # another writer put the key there since the plan was made
                        counts["turnedAway"] += 1
                        have.append(row)
                        continue
                counts["copied"] += 1
            have.append(row)
        files.append(counts)
        lines.append(_line(name, counts))
    lines += [f"worktree {w['path']}: {w['state']}" for w in worktrees]
    return {"sharedDir": str(shared), "noop": False, "dryRun": not write, "files": files, "worktrees": worktrees, "lines": lines}
