"""Term scan: behaviour on synthetic term files only (card MW-001, rows E1-E7).

Every assertion is on counts, paths, lines, groups and indexes. No test prints a term.
"""
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

import term_scan  # noqa: E402

# A synthetic planted term: a made-up word, not a real name.
PLANTED = "zorblaxquin"
# The Cyrillic block written as escapes, so this file stays English only.
CYRILLIC_GROUP = "re:[\\u0400-\\u04ff]"
CYRILLIC_LETTER = chr(0x0416)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _empty_config(tmp_path: Path) -> Path:
    return _write(tmp_path / "term_scan.json", json.dumps({"terms_file": None, "terms": []}))


def test_missing_term_list_fails(tmp_path, monkeypatch, capsys):
    """E1: no env, no config file, empty default list -> «term list missing», exit 2."""
    monkeypatch.delenv(term_scan.ENV_NAME, raising=False)
    target = _write(tmp_path / "a.txt", "plain text\n")
    code = term_scan.main(["--config", str(_empty_config(tmp_path)), "--files", str(target)])
    err = capsys.readouterr().err
    assert code == 2
    assert term_scan.MISSING_MESSAGE in err
    with pytest.raises(term_scan.TermListMissing):
        term_scan.resolve_entries(env={}, config_path=_empty_config(tmp_path))


def test_planted_literal_found(tmp_path):
    """E2: a planted literal is found at its file and line."""
    terms = _write(tmp_path / "terms.txt", "unusedword\n" + PLANTED + "\n")
    target = _write(tmp_path / "doc.md", "line one\nsome " + PLANTED.upper() + " here\nline three\n")
    entries = term_scan.load_terms(terms)
    result = term_scan.scan_files([target], entries, base=tmp_path)
    assert [(h.path, h.line, h.group, h.index) for h in result.hits] == [("doc.md", 2, "A", 2)]
    assert result.exceptions == []


def test_cyrillic_group_found(tmp_path):
    """E3: a re: group for the Cyrillic block finds one planted Cyrillic letter."""
    terms = _write(tmp_path / "terms.txt", CYRILLIC_GROUP + "\n")
    target = _write(tmp_path / "doc.md", "english\nenglish " + CYRILLIC_LETTER + " letter\n")
    result = term_scan.scan_files([target], term_scan.load_terms(terms), base=tmp_path)
    assert [(h.path, h.line, h.group, h.index) for h in result.hits] == [("doc.md", 2, "B", 1)]


def test_allow_marker_counts_exception(tmp_path):
    """E4: a hit on a line with the allow marker is an exception, not a hit."""
    terms = _write(tmp_path / "terms.txt", "re:[0-9a-f]{40}\n")
    sha = "0123456789abcdef0123456789abcdef01234567"
    target = _write(
        tmp_path / "doc.md",
        "pin " + sha + "  <!-- term-scan: allow sha -->\nother " + sha + "\n",
    )
    result = term_scan.scan_files([target], term_scan.load_terms(terms), base=tmp_path)
    assert [(h.path, h.line) for h in result.hits] == [("doc.md", 2)]
    assert [(e.path, e.line, e.reason) for e in result.exceptions] == [("doc.md", 1, "sha")]


def test_marker_needs_a_reason_and_never_hides_a_name(tmp_path):
    """E68 (card MW-002, fix check 3 M3): the allow marker needs a non-empty reason, and it never hides a group A
    term (a name): only a group B pattern hit on a marked line becomes an exception."""
    terms = _write(tmp_path / "terms.txt", PLANTED + "\nre:[0-9a-f]{40}\n")
    sha = "0123456789abcdef0123456789abcdef01234567"
    target = _write(tmp_path / "doc.md", "".join([
        "a " + PLANTED + " b  # term-scan: allow a name\n",  # 1: group A is never allowed
        "pin " + sha + "  # term-scan: allow\n",  # 2: no reason
        "pin " + sha + "  <!-- term-scan: allow -->\n",  # 3: an empty reason inside a comment
        "pin " + sha + " " + PLANTED + "  # term-scan: allow sha\n",  # 4: B allowed, A still a hit
        "pin " + sha + "  # term-scan: allow sha\n",  # 5: allowed
    ]))
    result = term_scan.scan_files([target], term_scan.load_terms(terms), base=tmp_path)
    assert [(h.path, h.line, h.group) for h in result.hits] == [
        ("doc.md", 1, "A"), ("doc.md", 2, "B"), ("doc.md", 3, "B"), ("doc.md", 4, "A")]
    assert [(e.path, e.line, e.group, e.reason) for e in result.exceptions] == [
        ("doc.md", 4, "B", "sha"), ("doc.md", 5, "B", "sha")]


def test_allow_list_pins_every_exception(tmp_path, monkeypatch, capsys):
    """E69 (card MW-002, fix check 3 M3): every exception is pinned in a tracked list, one row `<path> TAB <group>
    TAB <reason>`. The scan fails on an exception the list does not name, and on a list row whose file holds no
    marker with that reason, so a new exception always shows as a changed list in review. (Changed by blind round
    5: the group column; `main` on a row problem.)
    Catches: an `allow_problems` that ignores the group column; a `main` that prints row problems but returns 0 for
    them; a check in one direction only (unlisted exceptions, or rows without a marker)."""
    terms = _write(tmp_path / "terms.txt", "re:[0-9a-f]{40}\n")
    sha = "0123456789abcdef0123456789abcdef01234567"
    doc = _write(tmp_path / "doc.md", "pin " + sha + "  # term-scan: allow sha\n")
    result = term_scan.scan_files([doc], term_scan.load_terms(terms), base=tmp_path)
    problems = term_scan.allow_problems
    assert problems(result, [("doc.md", "B", "sha")], [doc], base=tmp_path) == []
    assert problems(result, [], [doc], base=tmp_path) == ["doc.md:1 exception not in the allow list"]
    assert problems(result, [("doc.md", "B", "sha"), ("other.md", "B", "x")], [doc], base=tmp_path) == [
        "other.md: allow-list row has no marker with its reason"]
    assert problems(result, [("doc.md", "B", "another")], [doc], base=tmp_path) == [
        "doc.md:1 exception not in the allow list", "doc.md: allow-list row has no marker with its reason"]
    allow = _write(tmp_path / "allow.txt", "# path\tgroup\treason\n")
    assert term_scan.load_allow_list(allow) == []
    monkeypatch.setenv(term_scan.ENV_NAME, str(terms))
    args = ["--config", str(_empty_config(tmp_path)), "--files", str(doc), "--base", str(tmp_path), "--allow",
            str(allow)]
    assert term_scan.main(args) == 1
    assert "doc.md:1 exception not in the allow list" in capsys.readouterr().out
    allow.write_text("doc.md\tB\tsha\n", encoding="utf-8")
    assert term_scan.load_allow_list(allow) == [("doc.md", "B", "sha")]
    assert term_scan.main(args) == 0
    # blind round 5: the group column counts, and `main` fails on a row with no marker too
    assert problems(result, [("doc.md", "A", "sha")], [doc], base=tmp_path) == [
        "doc.md:1 exception not in the allow list"]
    allow.write_text("doc.md\tB\tsha\nother.md\tB\tx\n", encoding="utf-8")
    capsys.readouterr()
    assert term_scan.main(args) == 1
    assert "other.md: allow-list row has no marker with its reason" in capsys.readouterr().out


def test_one_allow_row_per_marked_line(tmp_path):
    """E74 (card MW-002, fix check 4 F1): one allow-list row covers exactly one marked line. Two marked lines with
    the same path, group and reason need two rows; a third row with no third marker is a problem. So a new marked
    line in an already listed file always shows as a changed list.
    Catches: a set match (one row covers every same-reason marker in its file, so a second marker hides its hit and
    changes nothing in the list); a row check that only asks whether some marker exists."""
    terms = _write(tmp_path / "terms.txt", "re:[0-9a-f]{40}\n")
    sha = "0123456789abcdef0123456789abcdef01234567"
    doc = _write(tmp_path / "doc.md", ("pin " + sha + "  # term-scan: allow sha\n") * 2)
    result = term_scan.scan_files([doc], term_scan.load_terms(terms), base=tmp_path)
    row = ("doc.md", "B", "sha")
    problems = term_scan.allow_problems
    assert problems(result, [row], [doc], base=tmp_path) == ["doc.md:2 exception not in the allow list"]
    assert problems(result, [row, row], [doc], base=tmp_path) == []
    assert problems(result, [row, row, row], [doc], base=tmp_path) == [
        "doc.md: allow-list row has no marker with its reason"]


def test_hit_output_never_shows_term(tmp_path, monkeypatch, capsys):
    """E5: the printed report names path:line, group and index, never the term or the matched text."""
    terms = _write(tmp_path / "terms.txt", PLANTED + "\n")
    target = _write(tmp_path / "doc.md", "a " + PLANTED + " b\n")
    monkeypatch.setenv(term_scan.ENV_NAME, str(terms))
    code = term_scan.main(["--config", str(_empty_config(tmp_path)), "--files", str(target),
                           "--base", str(tmp_path)])
    out, err = capsys.readouterr()
    assert code == 1
    assert "doc.md:1 group A #1" in out
    assert PLANTED.lower() not in (out + err).lower()


def test_config_names_term_file_when_env_absent(tmp_path, monkeypatch):
    """E6: with no env variable, the config's terms_file is read."""
    monkeypatch.delenv(term_scan.ENV_NAME, raising=False)
    terms = _write(tmp_path / "terms.txt", PLANTED + "\n")
    config = _write(tmp_path / "term_scan.json", json.dumps({"terms_file": str(terms), "terms": []}))
    entries = term_scan.resolve_entries(env={}, config_path=config)
    assert len(entries) == 1
    assert (entries[0].group, entries[0].index) == ("A", 1)


@pytest.mark.engine_repo  # MW-002 (C14): needs the engine repository itself
def test_scan_covers_tracked_files_only(tmp_path):
    """E7: the repository walk lists tracked files and never an untracked one."""
    untracked = _write(tmp_path / "untracked_probe.md", "x\n")
    files = term_scan.tracked_files(REPO)
    rel = {p.relative_to(REPO).as_posix() for p in files}
    assert "CLAUDE.md" in rel
    assert untracked.resolve() not in {p.resolve() for p in files}
