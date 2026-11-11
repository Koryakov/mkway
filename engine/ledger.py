"""The decision ledger (card MW-008): one markdown table at `<bundle.root>/ledger/ledger.md`.

The format is `defaults.json` `decision_search.formats`: the heading `## Ledger`, the columns (id, date, card, topic,
quote, by, source, asked, replaces, status, note), the closed statuses (`superseded`, `withdrawn`) and `owner_who`
(the `by` of a row that quotes the owner). A row whose status is not closed is in force.

`add` appends one row (`mkway ledger add`); `read` returns the rows; `parse` reads the ledger-shaped tables of any
text, which is how the search reads the knowledge files too. The id of a new row is `D-<n>`, or, when the profile sets
`ids.decision_row`, the next number in the form of the file's own ids. No word of a task is in this file.
"""
from __future__ import annotations

import datetime
import json
import os
import re
from pathlib import Path
from typing import Optional

import profiles

LEDGER_DIR = "ledger"
LEDGER_FILE = "ledger.md"
IN_FORCE = "in force"
DEFAULT_ID = r"D-\d+"
_UNESCAPED_PIPE = re.compile(r"(?<!\\)\|")
_LITERAL_STOP = re.compile(r"[\\\[\](){}.+*?|$^]")


def formats() -> dict:
    """`decision_search.formats` of the engine defaults (an engine constant: the profile cannot set it)."""
    return json.loads(profiles.DEFAULTS_FILE.read_text(encoding="utf-8"))["decision_search"]["formats"]


def path(root, profile) -> Path:
    return Path(root) / profiles.bundle_root(profile) / LEDGER_DIR / LEDGER_FILE


def is_closed(status: str) -> bool:
    return status.strip().lower() in {s.lower() for s in formats()["closed_statuses"]}


def _split_row(line: str) -> list:
    body = line.strip()
    body = body[1:] if body.startswith("|") else body
    body = body[:-1] if body.endswith("|") and not body.endswith("\\|") else body
    return [cell.strip().replace("\\|", "|") for cell in _UNESCAPED_PIPE.split(body)]


def _is_separator(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and set(stripped) <= set("|-: ")


def _tables(lines: list):
    """(header line index, header cells, end index) of each markdown table that has an `id` and a `quote` column; the
    end index is one past its last row line."""
    i = 0
    while i < len(lines):
        if lines[i].strip().startswith("|") and i + 1 < len(lines) and _is_separator(lines[i + 1]):
            header = [c.lower() for c in _split_row(lines[i])]
            end = i + 2
            while end < len(lines) and lines[end].strip().startswith("|"):
                end += 1
            if "id" in header and "quote" in header:
                yield i, header, end
            i = end
        else:
            i += 1


def parse(text: str) -> list:
    """[(line number from 1, row dict of the format's columns)] for the rows of every ledger-shaped table of `text`."""
    columns = formats()["ledger_columns"]
    lines = text.splitlines()
    out = []
    for head, header, end in _tables(lines):
        for n in range(head + 2, end):
            cells = _split_row(lines[n])
            out.append((n + 1, {col: (cells[header.index(col)] if col in header and header.index(col) < len(cells)
                                      else "") for col in columns}))
    return out


def read(root, profile) -> list:
    """The rows of the ledger file; [] when there is no file."""
    target = path(root, profile)
    if not target.is_file():
        return []
    return [row for _n, row in parse(target.read_text(encoding="utf-8", errors="replace"))]


def counts(root, profile):
    """(rows, rows in force) of the ledger file, or None when the file does not exist."""
    target = path(root, profile)
    if not target.is_file():
        return None
    rows = read(root, profile)
    return len(rows), sum(1 for r in rows if not is_closed(r["status"]))


def _pattern(profile) -> str:
    value = profile.get("ids", {}).get("decision_row") if isinstance(profile, dict) and isinstance(
        profile.get("ids"), dict) else None
    try:
        if isinstance(value, str) and value:
            re.compile(value)
            return value
    except re.error:
        pass
    return DEFAULT_ID


def _literal_start(pattern: str) -> str:
    body = pattern[1:] if pattern.startswith("^") else pattern
    stop = _LITERAL_STOP.search(body)
    return body[:stop.start()] if stop else body


def next_id(ids: list, pattern: str) -> str:
    """The next id: one above the highest number among the ids that fully match `pattern`, written in that id's form
    (its text around the number, its digit width); with none, the pattern's literal start and the number 1. Zero
    padding is tried until the pattern matches; when nothing matches, `D-<n>`."""
    rx = re.compile(pattern)
    best = None
    for item in ids:
        if rx.fullmatch(item):
            runs = list(re.finditer(r"\d+", item))
            if runs and (best is None or int(runs[-1].group()) > best[0]):
                best = (int(runs[-1].group()), item, runs[-1])
    if best is None:
        number, before, after, width = 1, _literal_start(pattern), "", 1
    else:
        number, item, run = best[0] + 1, best[1], best[2]
        before, after, width = item[:run.start()], item[run.end():], len(run.group())
    for pad in range(width, width + 6):
        candidate = f"{before}{str(number).zfill(pad)}{after}"
        if rx.fullmatch(candidate):
            return candidate
    return f"D-{number}"


def quote_from_file(name: str) -> str:
    """The quote a `--quote-file` names (R120): the file's text with one trailing line break stripped. The file is only
    read, never removed. A missing or unreadable file raises OSError."""
    with open(name, "rb") as fh:
        text = fh.read().decode("utf-8", errors="replace")
    if text.endswith("\r\n"):
        return text[:-2]
    return text[:-1] if text.endswith("\n") else text


def _cell(value) -> str:
    return re.sub(r"\s*[\r\n]+\s*", " ", str(value)).strip().replace("|", "\\|")


def add(root, profile, *, card: str, topic: str, quote: str, source: str, status: str = IN_FORCE,
        today: Optional[str] = None, by: Optional[str] = None) -> dict:
    """Append one row to the ledger file (created, with its heading and header, when missing): today's date, the next
    id, `by` (MW-015; with none, `owner_who`). The row is returned. A row goes at the end of its table; text after the
    table stays."""
    fmt = formats()
    columns = fmt["ledger_columns"]
    target = path(root, profile)
    text = target.read_text(encoding="utf-8", errors="replace") if target.is_file() else ""
    lines = text.splitlines()
    tables = list(_tables(lines))
    ids = [row["id"] for _n, row in parse(text)]
    row = {"id": next_id(ids, _pattern(profile)),
           "date": today or datetime.date.today().isoformat(), "card": card, "topic": topic, "quote": quote,
           "by": by or fmt["owner_who"], "source": source, "asked": "", "replaces": "", "status": status, "note": ""}
    line = "| " + " | ".join(_cell(row[c]) for c in columns) + " |"
    target.parent.mkdir(parents=True, exist_ok=True)
    if not tables:
        block = [fmt["ledger_heading"], "", "| " + " | ".join(columns) + " |", "|" + "---|" * len(columns), line]
        prefix = "" if not text else ("\n" if text.endswith("\n") else "\n\n")
        with open(target, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(prefix + "\n".join(block) + "\n")
        return row
    end = tables[-1][2]
    if end >= len(lines):
        with open(target, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(("" if text.endswith("\n") else "\n") + line + "\n")
        return row
    lines.insert(end, line)
    temp = target.with_name(target.name + ".tmp")
    with open(temp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    os.replace(temp, target)
    return row
