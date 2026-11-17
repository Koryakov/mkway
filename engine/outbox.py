"""The outbox check (card MW-019): a text leaves only after a fresh reader.

A file under `outbox.dir` is made for someone outside the session. It counts as checked only when `<file><suffix>`
(default `.check.md`) sits beside it and holds the lines of `engine/defaults.json` -> `outbox_check.lines`:
`sha256:` equal to the file's sha256 now, `numbers:`, `claims:`, `patterns:`, `links:`, and `checker: <agent type>` with
a type that is in `outbox.checkers`. The engine itself verifies the sha256 and the patterns (it scans the document with
the regexes of `outbox.id_patterns_file`, never holding a pattern of its own); the other lines are the checker's
attestations in a fixed form (form only).

A fresh reader is proved by the records, never by words: the post step of the write gate appends a row to
`<state>/outbox_checks.jsonl` (the document, the sha256 of the check file as written, the hook's session id, the time),
and the agent records (`<state>/agents.jsonl`) must hold an agent of the `checker:` type of that session that started
after the document's last change (its file time) and ended after it and before the check was written. A check file that
no session wrote through a write tool, or that was changed after, has no matching row: `unproven`.

States: `valid`; `stale` (a `sha256:` line that is not the file's now: the text changed, or the check is for another
file or an older version); `unproven` (equal sha256, but a line is missing or wrong, the checker is not listed, a
pattern matches, or there is no proof of a fresh reader); `missing` (no check file, or no document).

No task name, no pattern and no natural-language word is in this file: the line forms are read from `defaults.json`.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import agents
import core_ask
import helpers
import logs
import profiles
import proof

RECORDS = proof.FILE
RECORD_KIND = "check-written"
VALID, STALE, UNPROVEN, MISSING = "valid", "stale", "unproven", "missing"
STATES = (VALID, STALE, UNPROVEN, MISSING)
DEFAULTS = json.loads(profiles.DEFAULTS_FILE.read_text(encoding="utf-8"))["outbox_check"]
SHA_NAME = "sha256"
HOW = core_ask.OUTBOX_HOW  # the decisions that name it are `core_ask` (card MW-065)


def suffix() -> str:
    return DEFAULTS["check_suffix"]


def _spec(name: str) -> dict:
    return next(line for line in DEFAULTS["lines"] if line["name"] == name)


def form(name: str) -> str:
    """The line form a problem names, without the backticks of the defaults file."""
    return _spec(name)["example"].strip("`")


@dataclass
class Status:
    rel: str
    sha: Optional[str]
    state: str
    checker: Optional[str] = None
    time: Optional[str] = None
    problems: list = field(default_factory=list)


# ---- paths --------------------------------------------------------------------------------------------------------

def sha_of(path) -> Optional[str]:
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


def under_dir(settings: dict, rel) -> bool:
    return core_ask.under_dir(settings["dir"], rel)


def doc_of(settings: dict, rel) -> Optional[str]:
    """The document a check file belongs to: `rel` without the suffix, when `rel` is `<outbox.dir>/.../<name><suffix>`;
    else None (the rule is `core_ask.doc_of`)."""
    return core_ask.doc_of(settings["dir"], suffix(), rel)


def documents(root, profile) -> list:
    """The files under `outbox.dir` that are not check files, repo-relative, sorted; [] with no folder."""
    settings = profiles.outbox_settings(profile)
    folder = settings["dir"]
    base = Path(root) / folder if folder else None
    if base is None or not base.is_dir():
        return []
    end = helpers._fold(suffix())
    found = []
    for path in base.rglob("*"):
        rel = path.relative_to(Path(root)).as_posix()
        if path.is_file() and not helpers._fold(rel).endswith(end):
            found.append(rel)
    return sorted(found)


# ---- the records --------------------------------------------------------------------------------------------------

def _rows(root, profile) -> list:
    path = profiles.state_dir(Path(root), profile) / RECORDS
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def record_check(root, profile, session, check_rel: str) -> dict:
    """Append the row of a write of a check file: the post step calls it after the write, with the hook's session id."""
    settings = profiles.outbox_settings(profile)
    row = {"kind": RECORD_KIND, "doc": doc_of(settings, check_rel), "check": check_rel,
           "check_sha": sha_of(Path(root) / check_rel),
           "session": session if isinstance(session, str) and session else agents.NE,
           "time": logs.now().isoformat(timespec="milliseconds")}
    logs.append_jsonl(profiles.state_dir(Path(root), profile) / RECORDS, row)
    return row


_moment = proof.moment  # MW-068: the time and file-time readers are the shared proof helper's
_mtime = proof.mtime


def _shown(moment: Optional[datetime.datetime]) -> Optional[str]:
    return moment.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if moment else None


def _proof(root, profile, rel: str, doc: Path, row, checker: str) -> Optional[str]:
    """None when an agent of type `checker` ran in the session that wrote the check, started after the document's last
    change and ended after it and before the check was written; else the problem. The read is the shared
    `proof.fresh_reader_problem` (MW-068, R173 item 2): the verdict check at card close calls the same function."""
    return proof.fresh_reader_problem(profiles.state_dir(Path(root), profile), doc, row.get("session"), row.get("time"),
                                      checker)


# ---- the scan -----------------------------------------------------------------------------------------------------

def scan(root, settings: dict, doc: Path):
    """(hits, problem): the (line, pattern number) pairs where the document matches a regex of `outbox.id_patterns_file`
    (one regex per line; blank lines and lines that start with `#` are skipped), and a problem when the file cannot be
    read or holds a line that is not a regex. No file named: no scan. Never the matched text."""
    name = settings["patterns_file"]
    if not name:
        return [], None
    try:
        lines = (Path(root) / name).read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return [], f"the id patterns file {name} (`outbox.id_patterns_file`) cannot be read: a check cannot be proved without its scan"
    patterns = []
    for number, raw in enumerate(lines, 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        try:
            patterns.append(re.compile(raw))
        except re.error:
            return [], f"{name} line {number} is not a valid regex: fix the line, the scan cannot run without it"
    try:
        text = Path(doc).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return [], "the document cannot be read for the scan"
    hits = []
    for at, line in enumerate(text.splitlines(), 1):
        hits += [(at, n) for n, pattern in enumerate(patterns, 1) if pattern.search(line)]
    return hits, None


# ---- the state ----------------------------------------------------------------------------------------------------

def sha_values(text: str) -> list:
    """The digest after every `sha256:` in a check's text, lower case (empty for a form with no digest)."""
    return core_ask.sha_values(text)


def base_values(text: str) -> list:
    """The eight digits after every well-formed `base:` line of a check's text, lower case (MW-020; the line is the
    optional one of `defaults.json`)."""
    return [v.lower() for v in re.findall(_spec("base")["regex"], text or "")]


def inspect(root, profile, rel: str) -> Status:
    """The state of one file under the outbox folder."""
    root = Path(root)
    settings = profiles.outbox_settings(profile)
    doc, check = root / rel, root / (rel + suffix())
    sha = sha_of(doc)
    if sha is None:
        return Status(rel, None, MISSING, problems=[f"{rel} does not exist"])
    if not check.is_file():
        return Status(rel, sha, MISSING, problems=[
            f"no {rel}{suffix()}: have a fresh reader of a type in `outbox.checkers` check the file, then write that "
            f"check file ({HOW})"])
    text = check.read_text(encoding="utf-8", errors="replace")
    mine = [r for r in _rows(root, profile) if r.get("kind") == RECORD_KIND and r.get("doc") == rel
            and r.get("check_sha") == sha_of(check)]
    row = mine[-1] if mine else None
    when = _shown(_moment(row.get("time")) if row else _mtime(check))
    found = re.search(_spec("checker")["regex"], text)
    checker = found.group(1) if found else None
    values = sha_values(text)
    if values and any(v != sha for v in values):
        return Status(rel, sha, STALE, checker, when, [
            f"the sha256 of the check is not the file's now: the text changed since it was checked, or the check is for "
            f"another file or an older version; have a fresh reader check the file as it is now, then write the check "
            f"with `sha256: {sha}`"])
    problems = []
    if not values:
        problems.append(f"lacks the line `{form(SHA_NAME)}` (with `{sha}`)")
    for line in DEFAULTS["lines"]:
        if line["name"] == SHA_NAME or line.get("optional"):  # the optional `base:` line is judged below (MW-020)
            continue
        match = re.search(line["regex"], text)
        if match is None:
            problems.append(f"lacks the line `{form(line['name'])}`")
        elif line.get("one_of") == "checkers" and match.group(1) not in settings["checkers"]:
            listed = ", ".join(f"`{c}`" for c in settings["checkers"]) or "none listed"
            problems.append(f"checker `{match.group(1)}` is not in `outbox.checkers` ({listed}): the profile names who "
                            f"may sign a check")
    hits, trouble = scan(root, settings, doc)
    if trouble:
        problems.append(trouble)
    elif hits:
        where = ", ".join(f"line {at} pattern {n}" for at, n in hits[:10])
        problems.append(f"the document matches the id patterns of {settings['patterns_file']} ({where}"
                        f"{', ...' if len(hits) > 10 else ''}), whatever `patterns:` says: remove them, then have a "
                        f"fresh reader check the file again")
    import deliverables  # MW-020: the optional `base:` line names a delivered file (late import: it imports this module)
    problems += deliverables.base_problems(root, profile, rel, text)
    if checker in settings["checkers"]:
        if row is None:
            problems.append("no record of a session writing this check file through a write tool (it was made by a "
                            "shell, copied, or changed after it was written): write it with the Write or Edit tool")
        else:
            proof = _proof(root, profile, rel, doc, row, checker)
            if proof:
                problems.append(proof)
    return Status(rel, sha, UNPROVEN if problems else VALID, checker, when, problems)


def board(root, profile) -> list:
    return [inspect(root, profile, rel) for rel in documents(root, profile)]


def board_lines(root, profile) -> list:
    """`mkway outbox`: one row per file (file, sha prefix, state, checker, time; two spaces between columns), and an
    indented problem line under each file that is not valid."""
    settings = profiles.outbox_settings(profile)
    if not settings["dir"]:
        return [f"no outbox: set `outbox.dir` in the profile ({HOW})"]
    found = board(root, profile)
    if not found:
        return [f"no files in {settings['dir']}"]
    out = []
    for status in found:
        out.append("  ".join([status.rel, (status.sha or "-")[:8], status.state, status.checker or "-",
                              status.time or "-"]))
        out += [f"  - {problem}" for problem in status.problems]
    return out


def start_line(root, profile) -> Optional[str]:
    """`outbox: N files, M unchecked` when `outbox.dir` is set, else None."""
    if not profiles.outbox_settings(profile)["dir"]:
        return None
    found = board(root, profile)
    return f"outbox: {len(found)} files, {sum(1 for s in found if s.state != VALID)} unchecked"


def stale_files(root, profile) -> list:
    """The files whose check exists but whose text changed after it (state `stale`)."""
    return [s for s in board(root, profile) if s.state == STALE]


# ---- the close ----------------------------------------------------------------------------------------------------

def named_files(profile, card_text: str) -> list:
    """(row id, file) for each file under `outbox.dir` that an Acceptance row names, in any cell, with or without
    backticks, with either slash; a folder name that only starts like the outbox folder is not one."""
    folder = profiles.outbox_settings(profile)["dir"]
    part = card_text.split("## Acceptance examples", 1)
    if not folder or len(part) < 2:
        return []
    pattern = re.compile(r"(?<![\w./-])(?:\./)?(" + re.escape(folder) + r"/[^\s`|;,)\"'<>]+)",
                         re.I if helpers.CASE_FOLD else 0)
    found, seen = [], set()
    for line in part[1].splitlines():
        if line.startswith("## "):
            break
        if not line.startswith("|") or set(line) <= set("|-: "):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        for match in pattern.finditer(line.replace("\\", "/")):
            rel = match.group(1).rstrip(".:")
            if rel not in seen and rel.rstrip("/") != folder:
                seen.add(rel)
                found.append((cells[0] if cells else "?", rel))
    return found


def close_problem(root, profile, card_id: str, card_text: str) -> Optional[str]:
    """None when every file an Acceptance row names under `outbox.dir` has a valid check, else the refusal text of
    `close-unchecked-outbox`: file, state, problem, and the commands."""
    offenders = []
    for row, rel in named_files(profile, card_text):
        status = inspect(root, profile, rel)
        if status.state != VALID:
            offenders.append(f"row {row} names {rel}, whose check is {status.state}: " + "; ".join(status.problems))
    if not offenders:
        return None
    return (f"{card_id} cannot close: " + " | ".join(offenders) + ". Have a fresh reader of a type in "
            f"`outbox.checkers` check each file, write its check file with a write tool, then close again; "
            f"`mkway outbox` shows the state of every file ({HOW})")
