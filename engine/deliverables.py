"""Deliverables (card MW-020): a result file made for others is built from tested code and compared with a named base.

A deliverable is a file that matches a glob of `deliverables.paths`. The records, all under the state folder:
- `deliverables.jsonl`: the provenance rows {path, sha256, head, tree, time, session} that `mkway built <path>` appends.
  The command refuses `built-dirty` (a tracked file has uncommitted changes) and `built-untested` (no green row of
  `commit_tests.jsonl` for HEAD's tree). The keys that name HEAD's tree come from `gate_commit_tests.tree_keys` (the
  git tree id, and the digest the commit gate writes, MW-023).
- `delivered.jsonl` and `delivered/<name>.<sha8>`: the owner's `mkway delivered <path>`: what went out, and a copy of it.
  A delivered file is the only base a comparison may name; an internal run never is.
- the optional line `base: <sha8>` of a check file (MW-019, parsed in `outbox.py` from `defaults.json`): equal to the
  first eight digits of a delivered row, required for the paths of `deliverables.require_base` (`base-unknown`).

`card close` refuses `close-deliverable-unbuilt` while an Acceptance row names a deliverable whose current sha256 has no
provenance row whose head is HEAD or an ancestor of HEAD, and `base-unknown` for a path that needs a base and has none.
No task name and no natural-language word is in this file.
"""
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Optional

import gate_commit_tests
import helpers
import logs
import outbox
import profiles
import rules
import runner

BUILT_FILE = "deliverables.jsonl"
DELIVERED_FILE = "delivered.jsonl"
COPIES = "delivered"
BUILT, CHANGED, UNBUILT = "built", "changed", "unbuilt"
HOW = "README, «Deliverables: built from tested code, compared with a named base»"
NOT_SET = "deliverables: not set; add `deliverables.paths` (globs of the result files made for others) to the profile"
_HEX40 = re.compile(r"^[0-9a-f]{40,64}$")
_BASE_LINE = re.compile(r"(?m)^[ \t]*base:")


class Refused(Exception):
    """A command refusal: `reason` is the reason id, the message names the command that fixes it."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason
        self.message = message


def paths(profile) -> list:
    return profiles.deliverable_settings(profile)["paths"]


def active(profile) -> bool:
    return bool(paths(profile))


def is_deliverable(profile, rel) -> bool:
    return isinstance(rel, str) and any(helpers.matches(rel, glob) for glob in paths(profile))


def requires_base(profile, rel) -> bool:
    return isinstance(rel, str) and any(helpers.matches(rel, glob)
                                        for glob in profiles.deliverable_settings(profile)["require_base"])


def _state(root, profile) -> Path:
    return profiles.state_dir(Path(root), profile)


def _rows(root, profile, name: str) -> list:
    import json
    path = _state(root, profile) / name
    out = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return out
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def rel_of(root, arg) -> Optional[str]:
    """The repo-relative posix form of a path argument (a relative one is read from the root), or None outside it."""
    return helpers.norm(arg, str(root))


def files(root, profile) -> list:
    """The existing files that match `deliverables.paths` (check files of MW-019 are not deliverables), sorted."""
    if not active(profile):
        return []
    root = Path(root)
    state = _state(root, profile).resolve()
    end = helpers._fold(outbox.suffix())
    found = []
    for folder, names, names_files in os.walk(root):
        names[:] = [n for n in names if n not in rules.SKIP_FOLDERS and (Path(folder) / n).resolve() != state]
        for name in names_files:
            rel = (Path(folder) / name).relative_to(root).as_posix()
            if is_deliverable(profile, rel) and not helpers._fold(rel).endswith(end):
                found.append(rel)
    return sorted(found)


# ---- built --------------------------------------------------------------------------------------------------------

def _git(root, *args, text=True):
    try:
        return runner.git(root, *args, text=text, timeout=30)
    except (OSError, runner.TimeoutExpired, ValueError, runner.Refused):
        return None


def build(root, profile, arg: str, session: str) -> dict:
    """The provenance row of `mkway built <arg>`, appended and returned; `Refused` when the file is missing, a tracked
    file is dirty, or no green row names HEAD's tree."""
    root = Path(root)
    rel = rel_of(root, arg)
    shown = rel or str(arg)
    if rel is None or not (root / rel).is_file():
        raise Refused("built-no-file", f"{shown} is not a file under the task root: build the file first, then run "
                                       f"`mkway built {shown}` ({HOW})")
    proc = _git(root, "status", "--porcelain", "--untracked-files=no")
    if proc is None or proc.returncode != 0:
        raise Refused("built-dirty", f"the state of the tracked files could not be read (is the task root a git work "
                                     f"tree?): `mkway built {rel}` needs a clean tree of a commit")
    dirty = [line[3:] for line in proc.stdout.splitlines() if line.strip()]
    if dirty:
        raise Refused("built-dirty", f"tracked files have uncommitted changes ({', '.join(dirty[:5])}"
                                     f"{', ...' if len(dirty) > 5 else ''}): a result is built on the final HEAD. "
                                     f"Commit the changes (the commit check runs the tests), then run "
                                     f"`mkway built {rel}` again")
    head = _git(root, "rev-parse", "HEAD")
    if head is None or head.returncode != 0 or not head.stdout.strip():
        raise Refused("built-untested", f"there is no commit yet: commit the work (the commit check runs the tests and "
                                        f"records a green row), then run `mkway built {rel}`")
    head = head.stdout.strip()
    trees = gate_commit_tests.tree_keys(root, "HEAD")  # MW-023: the one definition, beside the gate's own key
    green = [r for r in _rows(root, profile, "commit_tests.jsonl") if r.get("result") == "pass"
             and r.get("tree") in trees]
    if not green:
        raise Refused("built-untested", (
            f"no green row of `commit_tests.jsonl` names the tree of HEAD {head[:8]}: the tests have not passed on this "
            f"code. Commit a change outside the test roots (the commit check runs the whole suite and writes the row), "
            f"or fix the red tests, then run `mkway built {rel}` again"))
    row = {"path": rel, "sha256": outbox.sha_of(root / rel), "head": head, "tree": green[-1]["tree"],
           "time": logs.now().isoformat(timespec="milliseconds"), "session": session}
    logs.append_jsonl(_state(root, profile) / BUILT_FILE, row)
    return row


def built_text(row: dict) -> str:
    return f"built {row['path']} {row['sha256'][:8]} at {row['head'][:8]}"


# ---- delivered ----------------------------------------------------------------------------------------------------

def deliver(root, profile, arg: str) -> dict:
    """The owner's `mkway delivered <arg>`: the row {path, sha256, time} and a copy at `<state>/delivered/<name>.<sha8>`
    (an existing copy is kept, never overwritten)."""
    root = Path(root)
    rel = rel_of(root, arg)
    if rel is None or not (root / rel).is_file():
        raise Refused("delivered-no-file", f"{rel or arg} is not a file under the task root: nothing was delivered; "
                                           f"run `mkway delivered <path>` on the file that went out ({HOW})")
    sha = outbox.sha_of(root / rel)
    row = {"path": rel, "sha256": sha, "time": logs.now().isoformat(timespec="milliseconds")}
    copy = _state(root, profile) / COPIES / f"{Path(rel).name}.{sha[:8]}"
    copy.parent.mkdir(parents=True, exist_ok=True)
    if not copy.exists():
        shutil.copyfile(root / rel, copy)
    logs.append_jsonl(_state(root, profile) / DELIVERED_FILE, row)
    return row


def delivered_sha8(root, profile) -> set:
    return {str(r.get("sha256", ""))[:8].lower() for r in _rows(root, profile, DELIVERED_FILE) if r.get("sha256")}


# ---- the base line ------------------------------------------------------------------------------------------------

def base_problems(root, profile, rel: str, check_text: Optional[str]) -> list:
    """The problems of the `base:` line of the check of `rel`: none when the line is absent and not required; else the
    texts (each names `base-unknown`, the line and `mkway delivered`). `check_text` is None for no check file."""
    required = requires_base(profile, rel)
    values = outbox.base_values(check_text or "")
    form = outbox.form("base")
    fix = (f"`mkway delivered <path>` (the owner's command) keeps the file that went out, then the check names it with "
           f"`{form}`")
    if not values:
        if check_text is not None and _BASE_LINE.search(check_text):
            return [f"base-unknown: the line `base:` of the check is not in the form `{form}` (eight hex digits): {fix}"]
        if required:
            return [f"base-unknown: {rel} is in `deliverables.require_base`, so its check needs the line `{form}`, the "
                    f"first eight digits of the sha256 of the file that was delivered before: {fix}"]
        return []
    known = delivered_sha8(root, profile)
    unknown = [v for v in values if v not in known]
    if unknown:
        return [f"base-unknown: the base {', '.join(unknown)} named by the check of {rel} is no delivered file (no row "
                f"of `delivered.jsonl` starts with it): a comparison names a file that went out, never an internal "
                f"run: {fix}"]
    return []


# ---- the close ----------------------------------------------------------------------------------------------------

def named_files(profile, card_text: str) -> list:
    """(row id, path) for each path of `deliverables.paths` that an Acceptance row names, in any cell, with or without
    backticks, with either slash."""
    part = card_text.split("## Acceptance examples", 1)
    if not active(profile) or len(part) < 2:
        return []
    found, seen = [], set()
    for line in part[1].splitlines():
        if line.startswith("## "):
            break
        if not line.startswith("|") or set(line) <= set("|-: "):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        for token in re.findall(r"[^\s`|;,()\"'<>]+", line.replace("\\", "/")):
            rel = token[2:] if token.startswith("./") else token
            rel = rel.rstrip(".:")
            if rel not in seen and is_deliverable(profile, rel) and "*" not in rel:
                seen.add(rel)
                found.append((cells[0] if cells else "?", rel))
    return found


def _ancestor(root, head) -> bool:
    if not isinstance(head, str) or not _HEX40.match(head):
        return False
    proc = _git(root, "merge-base", "--is-ancestor", head, "HEAD")
    return proc is not None and proc.returncode == 0


def is_built(root, profile, rel: str) -> bool:
    """A provenance row holds the file's current sha256 and its head is HEAD or an ancestor of HEAD."""
    sha = outbox.sha_of(Path(root) / rel)
    return sha is not None and any(r.get("path") == rel and r.get("sha256") == sha and _ancestor(root, r.get("head"))
                                   for r in _rows(root, profile, BUILT_FILE))


def close_problem(root, profile, card_id: str, card_text: str):
    """None when every deliverable an Acceptance row names is built (and has its base where one is required), else
    (reason id, refusal text): `close-deliverable-unbuilt` first, then `base-unknown`."""
    named = named_files(profile, card_text)
    unbuilt = [f"row {row} names {rel}, which was not built from its current text: run `mkway built {rel}`"
               for row, rel in named if not is_built(root, profile, rel)]
    if unbuilt:
        return ("close-deliverable-unbuilt", f"{card_id} cannot close: " + " | ".join(unbuilt) + f". A deliverable is "
                f"ready when it was built on a clean HEAD whose tests passed; `mkway deliverables` shows the state of "
                f"every file ({HOW})")
    bases = []
    for row, rel in named:
        if requires_base(profile, rel):
            check = Path(root) / (rel + outbox.suffix())
            text = check.read_text(encoding="utf-8", errors="replace") if check.is_file() else None
            bases += [f"row {row}: {p}" for p in base_problems(root, profile, rel, text)]
    if bases:
        return ("base-unknown", f"{card_id} cannot close: " + " | ".join(bases) + f" ({HOW})")
    return None


# ---- the board ----------------------------------------------------------------------------------------------------

def board(root, profile) -> list:
    """[(path, sha, state, delivered sha8 or None)] for each deliverable file."""
    built = _rows(root, profile, BUILT_FILE)
    delivered = _rows(root, profile, DELIVERED_FILE)
    out = []
    for rel in files(root, profile):
        sha = outbox.sha_of(Path(root) / rel) or ""
        mine = [r for r in built if r.get("path") == rel]
        state = BUILT if any(r.get("sha256") == sha for r in mine) else (CHANGED if mine else UNBUILT)
        sent = [r for r in delivered if r.get("path") == rel and r.get("sha256")]
        out.append((rel, sha, state, sent[-1]["sha256"][:8] if sent else None))
    return out


def lines(root, profile) -> list:
    if not active(profile):
        return [NOT_SET]
    found = board(root, profile)
    if not found:
        return ["no files match `deliverables.paths`"]
    return ["  ".join([rel, sha[:8], state, sent or "-"]) for rel, sha, state, sent in found]


def start_line(root, profile) -> Optional[str]:
    """`deliverables: N built, M changed since built, K delivered`, or None when `deliverables.paths` is not set."""
    if not active(profile):
        return None
    found = board(root, profile)
    return (f"deliverables: {sum(1 for r in found if r[2] == BUILT)} built, "
            f"{sum(1 for r in found if r[2] == CHANGED)} changed since built, {sum(1 for r in found if r[3])} delivered")
