"""The engine's CI checks on its own tracked files (card MW-001, rows E8-E9).

Run before every commit: `python -m pytest`. Failures name path:line and group/index only.
"""
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

import term_scan  # noqa: E402
from _mw096_repo_scan import cyrillic_hits  # noqa: E402


@pytest.mark.engine_repo  # MW-002 (C14): needs the engine repository itself
def test_repository_has_no_term_hits():
    """Checks: no term hit in a tracked file, the term list is present and every exception is pinned in the allow list (E8)."""
    try:
        entries = term_scan.resolve_entries(env=os.environ, config_path=REPO / "tools" / "term_scan.json")
    except term_scan.TermListMissing:
        pytest.fail(term_scan.MISSING_MESSAGE)
    files = term_scan.tracked_files(REPO)
    result = term_scan.scan_files(files, entries, base=REPO)
    print(f"term scan: {len(entries)} entries, {len(result.hits)} hits, {len(result.exceptions)} exceptions")
    print("\n".join(f"exception {e.path}:{e.line} ({e.reason})" for e in result.exceptions))
    assert not result.hits, "\n".join(f"{h.path}:{h.line} group {h.group} #{h.index}" for h in result.hits)
    # MW-002 fix check 3 M3: every exception is pinned in the tracked allow list, and every row has its marker
    rows = term_scan.load_allow_list(REPO / "tools" / "term_scan_allow.txt")
    problems = term_scan.allow_problems(result, rows, files, base=REPO)
    assert not problems, "\n".join(problems)


@pytest.mark.engine_repo  # MW-002 (C14): needs the engine repository itself
def test_repository_is_english_only():
    """Checks: no tracked file holds a Cyrillic letter (E9)."""
    bad = cyrillic_hits(term_scan.tracked_files(REPO), REPO)
    assert not bad, "\n".join(bad)
