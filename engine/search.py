"""`mkway search <words>` (card MW-008): a search of the past decisions before a question to the owner.

It reads the ledger (`<bundle.root>/ledger/ledger.md`) and then each file of `knowledge.files` (a literal path or a
glob; a file that does not exist is skipped). A file that holds a ledger-shaped table gives its rows; any other file
gives each line, with the nearest heading above it as the topic and `<path>:<line>` as the id. The match is plain
text, case-insensitive; a hit holds any of the words. There is no ranking: hits keep the order of the files and of the
lines, and are printed grouped by file and by status (in force, then withdrawn, then superseded).

Every run appends one row to `<state.dir>/searches.jsonl` (`id` S-<n>, `session`, `time`, `words`, `hits`, `hit_ids`),
also when there is no profile, no ledger or no hit: the record is what the `search` gate and an ask's
`search: <record id>` line point to.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import ledger
import logs
import profiles

SEARCHES = "searches.jsonl"
SESSION_VAR = "CLAUDE_CODE_SESSION_ID"
_HEADING = re.compile(r"^#+\s*(.*?)\s*$")


def _rel(root, target: Path) -> str:
    try:
        return target.resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return target.as_posix()


def files(root, profile) -> list:
    """[(shown path, file)]: the ledger when it exists, then each existing file of `knowledge.files`, once each."""
    out, seen = [], set()

    def take(target: Path):
        key = str(target.resolve())
        if target.is_file() and key not in seen:
            seen.add(key)
            out.append((_rel(root, target), target))

    take(ledger.path(root, profile))
    knowledge = profile.get("knowledge") if isinstance(profile, dict) else None
    listed = knowledge.get("files") if isinstance(knowledge, dict) else None
    for item in listed if isinstance(listed, list) else []:
        if not isinstance(item, str) or not item.strip():
            continue
        pattern = item.strip().replace("\\", "/")
        if any(ch in pattern for ch in "*?["):
            for found in sorted(Path(root).glob(pattern)):
                take(found)
        else:
            take(Path(root) / pattern)
    return out


def _hits_of(shown: str, text: str, words: list) -> list:
    rows = ledger.parse(text)
    found = []
    if rows:
        for line_no, row in rows:
            haystack = " ".join(row.values()).lower()
            if any(w in haystack for w in words):
                found.append({"file": shown, "id": row["id"] or f"{shown}:{line_no}", "date": row["date"],
                              "topic": row["topic"], "quote": row["quote"], "status": row["status"]})
        return found
    heading = ""
    for line_no, line in enumerate(text.splitlines(), 1):
        match = _HEADING.match(line)
        if match:
            heading = match.group(1)
        if line.strip() and any(w in line.lower() for w in words):
            found.append({"file": shown, "id": f"{shown}:{line_no}", "date": "", "topic": heading,
                          "quote": line.strip(), "status": ledger.IN_FORCE})
    return found


def find(root, profile, words: list) -> list:
    """The hits, in the order of the files and of the rows or lines. A file that cannot be read is skipped."""
    lowered = [w.lower() for w in words if w.strip()]
    hits = []
    for shown, target in files(root, profile):
        try:
            text = target.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        hits += _hits_of(shown, text, lowered)
    return hits


def _group(status: str) -> str:
    return status.strip().lower() if ledger.is_closed(status) else ledger.IN_FORCE


def render(record_id: str, words: list, hits: list) -> list:
    """The printed lines: the run, then for each file its path and its groups, then `hits: N`."""
    order = [ledger.IN_FORCE] + list(reversed(ledger.formats()["closed_statuses"]))
    lines = [f"search {record_id}: {' '.join(words)}"]
    for shown in dict.fromkeys(h["file"] for h in hits):
        lines.append(shown)
        mine = [h for h in hits if h["file"] == shown]
        for group in order:
            chosen = [h for h in mine if _group(h["status"]) == group]
            if chosen:
                lines.append(f"  {group}")
                lines += [f"    {h['id']}  {h['date']}  {h['topic']}  {h['quote']}" for h in chosen]
    lines.append(f"hits: {len(hits)}")
    return lines


def record(state_dir, words: list, hits: list, env) -> dict:
    """Append this run to `searches.jsonl` and return the row. The id is one above the count of rows."""
    target = Path(state_dir) / SEARCHES
    count = 0
    if target.is_file():
        count = sum(1 for line in target.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip())
    row = {"id": f"S-{count + 1}", "session": (env or {}).get(SESSION_VAR) or None,
           "time": logs.now().isoformat(timespec="milliseconds"), "words": list(words), "hits": len(hits),
           "hit_ids": [h["id"] for h in hits]}
    logs.append_jsonl(target, row)
    return row


def run(root, profile, words: list, env) -> tuple:
    """(printed lines, record row) of one search."""
    profile = profile if isinstance(profile, dict) else {}
    hits = find(root, profile, words)
    row = record(profiles.state_dir(root, profile), words, hits, env)
    return render(row["id"], words, hits), row


def rows(state_dir) -> list:
    target = Path(state_dir) / SEARCHES
    if not target.is_file():
        return []
    out = []
    for line in target.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            item = json.loads(line)
        except ValueError:
            continue
        if isinstance(item, dict):
            out.append(item)
    return out
