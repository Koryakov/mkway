"""Term scan: find terms that must never enter the engine repository.

Term file: one entry per line. A plain line is a literal term (group A, matched case-insensitively, not inside a
longer word). A line `re:<regex>` is a pattern (group B, matched as written). Blank lines are skipped. The index of an
entry is its 1-based position within its group.

Where the term file comes from, first found wins: `--terms`, env `ENGINE_TERMS_FILE`, the config's `terms_file`
(`tools/term_scan.json`). Without a file the config's `terms` list is used; the engine ships it EMPTY, and an empty
list is an error («term list missing»), never a silent pass.

A hit is printed as `path:line group <G> #<n>`. The term and the matched text are never printed.
A line holding `term-scan: allow <reason>` (a non-empty reason) turns its group B (pattern) hits into one
exception, counted and listed. It never hides a group A term (a name): that stays a hit. Every exception is pinned
in the tracked allow list `tools/term_scan_allow.txt`, one row `<path> TAB <group> TAB <reason>` per marked line
(no line number; two marked lines with the same reason need two rows);
the scan fails on an exception the list does not name and on a row whose file holds no marker with that reason, so
a new exception always shows as a changed list in review (card MW-002, fix check 3 M3).

Exit codes: 0 no hits, 1 hits, 2 term list missing or a bad entry.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

ENV_NAME = "ENGINE_TERMS_FILE"
MISSING_MESSAGE = "term list missing"
ALLOW_MARKER = re.compile(r"term-scan:\s*allow\b\s*(.*)$")
DEFAULT_CONFIG = Path(__file__).resolve().with_name("term_scan.json")
ALLOW_FILE = "tools/term_scan_allow.txt"  # relative to the scanned root


class TermListMissing(Exception):
    """No term file and an empty default list."""


class BadEntry(Exception):
    """A `re:` entry that does not compile. The message names the group and index only."""


@dataclass(frozen=True)
class Entry:
    group: str
    index: int
    pattern: "re.Pattern[str]"


@dataclass(frozen=True)
class Hit:
    path: str
    line: int
    group: str
    index: int


@dataclass(frozen=True)
class Allowed:
    path: str
    line: int
    reason: str
    group: str = "B"


@dataclass
class Result:
    hits: list
    exceptions: list


def _entries_from_lines(lines) -> list:
    entries, counts = [], {"A": 0, "B": 0}
    for raw in lines:
        text = raw.rstrip("\r\n")
        if not text.strip():
            continue
        if text.startswith("re:"):
            counts["B"] += 1
            try:
                pattern = re.compile(text[3:])
            except re.error:
                raise BadEntry(f"bad entry: group B #{counts['B']}") from None
            entries.append(Entry("B", counts["B"], pattern))
        else:
            counts["A"] += 1
            term = text.strip()
            left = r"(?<![0-9A-Za-z])" if term[0].isalnum() else ""
            right = r"(?![0-9A-Za-z])" if term[-1].isalnum() else ""
            entries.append(Entry("A", counts["A"], re.compile(left + re.escape(term) + right, re.IGNORECASE)))
    return entries


def load_terms(path) -> list:
    """Read a term file. The content is never printed."""
    with open(path, encoding="utf-8") as fh:
        return _entries_from_lines(fh)


def resolve_entries(env=None, config_path=None, terms_path=None) -> list:
    """Find the term entries: --terms, then env, then config file, then the config's (empty) list."""
    env = os.environ if env is None else env
    config_path = Path(config_path) if config_path else DEFAULT_CONFIG
    config = {}
    if config_path.is_file():
        config = json.loads(config_path.read_text(encoding="utf-8"))
    chosen = terms_path or env.get(ENV_NAME) or config.get("terms_file")
    if chosen:
        if not Path(chosen).is_file():
            raise TermListMissing(MISSING_MESSAGE)
        entries = load_terms(chosen)
    else:
        entries = _entries_from_lines(config.get("terms") or [])
    if not entries:
        raise TermListMissing(MISSING_MESSAGE)
    return entries


def tracked_files(root) -> list:
    """Every file git tracks (the index) under root, as absolute paths."""
    root = Path(root).resolve()
    out = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True).stdout
    return [root / p for p in out.decode("utf-8").split("\0") if p and (root / p).is_file()]


def scan_files(files, entries, base=None) -> Result:
    result = Result(hits=[], exceptions=[])
    base = Path(base).resolve() if base else None
    for path in files:
        path = Path(path)
        rel = path.resolve().relative_to(base).as_posix() if base else path.as_posix()
        text = path.read_bytes().decode("utf-8", errors="replace")
        for n, line in enumerate(text.splitlines(), 1):
            found = [e for e in entries if e.pattern.search(line)]
            if not found:
                continue
            reason = marker_reason(line)
            allowed = [e for e in found if reason and e.group == "B"]  # a name (group A) is never allowed
            if allowed:
                result.exceptions.append(Allowed(rel, n, reason, "B"))
            for e in found:
                if e not in allowed:
                    result.hits.append(Hit(rel, n, e.group, e.index))
    return result


def marker_reason(line: str):
    """The marker's reason on this line, or None when there is no marker or its reason is empty."""
    marker = ALLOW_MARKER.search(line)
    if not marker:
        return None
    reason = re.sub(r"\s*(-->|\*/)\s*$", "", marker.group(1)).strip()
    return reason or None


def load_allow_list(path) -> list:
    """Rows `(path, group, reason)` of the allow list; `#` lines and blank lines are skipped. A missing file is an
    empty list."""
    path = Path(path)
    if not path.is_file():
        return []
    rows = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.startswith("#"):
            continue
        parts = raw.split("\t")
        if len(parts) != 3:
            raise BadEntry(f"bad allow-list row: {parts[0]}")
        rows.append(tuple(part.strip() for part in parts))
    return rows


def allow_problems(result, rows, files, base=None) -> list:
    """The differences between the exceptions found and the allow list. One row covers exactly one marked line: two
    marked lines with the same path, group and reason need two rows (fix check 4 F1). Problems: an exception no row
    is left for, and a row with no marked line left for it."""
    left = Counter(rows)
    problems = []
    for e in result.exceptions:
        key = (e.path, e.group, e.reason)
        if left[key] > 0:
            left[key] -= 1
        else:
            problems.append(f"{e.path}:{e.line} exception not in the allow list")
    base = Path(base).resolve() if base else None
    by_rel = {}
    for path in files:
        path = Path(path)
        by_rel[path.resolve().relative_to(base).as_posix() if base else path.as_posix()] = path
    for (rel, _group, reason), wanted in Counter(rows).items():
        path = by_rel.get(rel)
        text = path.read_bytes().decode("utf-8", errors="replace") if path is not None else ""
        if sum(1 for line in text.splitlines() if marker_reason(line) == reason) < wanted:
            problems.append(f"{rel}: allow-list row has no marker with its reason")
    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Scan files for terms that must not enter the engine.")
    ap.add_argument("--root", default=str(Path(__file__).resolve().parents[1]), help="repository to scan")
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--terms", default=None, help="term file (overrides env and config)")
    ap.add_argument("--files", nargs="*", default=None, help="scan these files instead of the tracked files")
    ap.add_argument("--base", default=None, help="paths are printed relative to this folder")
    ap.add_argument("--allow", default=None, help="the allow list (default: <root>/" + ALLOW_FILE
                    + " for a repository scan; none with --files)")
    args = ap.parse_args(argv)
    try:
        entries = resolve_entries(config_path=args.config, terms_path=args.terms)
    except (TermListMissing, BadEntry) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.files is not None:
        files, base = [Path(f) for f in args.files], args.base
    else:
        files, base = tracked_files(args.root), args.root
    result = scan_files(files, entries, base=base)
    allow = args.allow or (None if args.files is not None else Path(args.root) / ALLOW_FILE)
    try:
        rows = load_allow_list(allow) if allow else []
    except BadEntry as exc:
        print(str(exc), file=sys.stderr)
        return 2
    problems = allow_problems(result, rows, files, base=base)
    for h in result.hits:
        print(f"{h.path}:{h.line} group {h.group} #{h.index}")
    for e in result.exceptions:
        print(f"{e.path}:{e.line} allowed ({e.reason})")
    for problem in problems:
        print(problem)
    print(f"term scan: {len(entries)} entries, {len(files)} files, {len(result.hits)} hits, "
          f"{len(result.exceptions)} exceptions")
    return 1 if result.hits or problems else 0


if __name__ == "__main__":
    sys.exit(main())
