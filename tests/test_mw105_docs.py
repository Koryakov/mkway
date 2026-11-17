"""Card MW-105: the register, the changelog and the README name what the card changes. Documents are read here only (a
doc-consistency check); a test checks that its line or row is present, never that it is the last one (R256); no behaviour is
judged from them."""
import re

import pytest

import _docs as docs
from _engine import REPO

pytestmark = pytest.mark.engine_repo

TITLE = "the lock gate guards the upgrade folder outside the repository"
PARAGRAPH_MARK = "The `upgrade` target (MW-105)"
PARAGRAPH_WORDS = ["never-open", "`MKWAY_UPGRADE_DIR`", "outside the repository", "`lock-closed-edit`", "`lock-closed-shell`",
                   "separator boundary", "parent", "literal head", "UNC", "network path", "`/upgrade/`", "named gap",
                   "OS file permissions", "real boundary"]


def _paragraphs(path):
    """The paragraphs of a document, each with its white space made single."""
    text = (REPO / path).read_text(encoding="utf-8")
    return [" ".join(part.split()) for part in re.split(r"\n\s*\n", text)]


def test_the_register_changelog_and_gap_line_carry_mw105():
    """Checks: the register row, one changelog line in one release section, the card folder, and the README gap line of MW-104 keeps its phrases and gains `MW-105 closes this gap.`"""
    register = (REPO / "cards" / "REGISTER.md").read_text(encoding="utf-8")
    row = re.search(r"^\| MW-105 \| (.+?) \| proposed \| `cards/MW-105-[a-z0-9-]+` \|$", register, re.M)
    assert row is not None, "no register row of MW-105"
    section = docs.changelog_section((REPO / "CHANGELOG.md").read_text(encoding="utf-8"), "MW-105")
    gap = [p for p in _paragraphs("README.md") if "Gap H7 (R257h)" in p]
    assert len(gap) == 1, "the README must hold the gap H7 paragraph once"
    assert (row.group(1), f"- MW-105: {TITLE}" in section.splitlines(), bool(list((REPO / "cards").glob("MW-105-*/CARD.md"))),
            "the lock gate cannot yet hold" in gap[0], "outside the repository" in gap[0],
            "MW-105 closes this gap." in gap[0]) == (TITLE, True, True, True, True, True)


def test_the_readme_paragraph_names_the_upgrade_target_and_its_rules():
    """Checks: one README paragraph names the `upgrade` target, its folders, the refusal ids, the separator boundary, the parent rule, the glob head, UNC, the variable shape and the OS boundary."""
    found = [p for p in _paragraphs("README.md") if PARAGRAPH_MARK in p]
    assert len(found) == 1, "the README must hold the paragraph of the `upgrade` target once"
    assert [w for w in PARAGRAPH_WORDS if w not in found[0]] == []


GAP_MARK = "Named gaps of the upgrade guard (MW-105 review)"
GAP_WORDS = ["`Move-Item -LiteralPath`", "`cmd /c`", "`rd`", "`del`", "`erase`", "follow-up card", "two-step symlink", "hard link",
             "`FileSystem::`", "`git switch feature/upgrade`", "`feature/state`", "base name", "`cp x ~`", "`mkdir -p ~/.config`",
             "root globs", "`//tmp`", "relative `MKWAY_UPGRADE_DIR`"]


def test_the_readme_names_the_corrected_claims_of_the_upgrade_paragraph():
    """Checks: E76 (R260d C3 to C7), in the one README paragraph of the `upgrade` target: a mapped drive's real path may touch its share, case folded on Windows only, a home that cannot be found, only an absolute override, `~` read from HOME first."""
    found = [p for p in _paragraphs("README.md") if PARAGRAPH_MARK in p]
    words = ["names no network path", "mapped drive", "on Windows only", "cannot be found", "only an absolute", "`HOME`, then `USERPROFILE`"]
    assert (len(found), [w for w in words if w not in found[0]], "case resolved" in found[0]) == (1, [], False)


def test_the_readme_names_the_gaps_found_in_review():
    """Checks: E77 (R260d), one README paragraph names the gaps of the guard that the review found and the card does not close: unread forms, links, provider paths, base names, over-refusals, a `//` path on POSIX, a relative override."""
    found = [p for p in _paragraphs("README.md") if GAP_MARK in p]
    assert len(found) == 1, "the README must hold the paragraph of the review gaps once"
    assert [w for w in GAP_WORDS if w not in found[0]] == []


GAP_WORDS_2 = ["inside a subshell", "a bare `cd`", "`cd \"$VAR\"`", "prefix assignment", "`%APPDATA%` is literal text", "script variable",
               "fail-closed", "on a network share", "refused as a network path"]


def test_the_readme_names_the_gaps_found_in_the_second_review():
    """Checks: E89 (F6, R260e), the same README paragraph also names: a `cd` in a subshell, a group or a substitution, a bare `cd`, `cd "$VAR"`, a prefix assignment, the PowerShell over-refusals, and a home or APPDATA on a network share."""
    found = [p for p in _paragraphs("README.md") if GAP_MARK in p]
    assert len(found) == 1, "the README must hold the paragraph of the review gaps once"
    assert [w for w in GAP_WORDS_2 if w not in found[0]] == []


def test_the_readme_names_the_always_expanded_variables_and_the_raw_text_network_paths():
    """Checks: E91 (G1, G4, R260f), the paragraph of the `upgrade` target says the five variables are always expanded (a command that re-points one is refused on the real folder, the way out is the literal path), drops the assigned check, and says a repo path written as `//` or backslash text stays a network path."""
    found = [p for p in _paragraphs("README.md") if PARAGRAPH_MARK in p]
    words = ["always expanded", "re-points", "write the literal path", "stays a network path"]
    assert (len(found), [w for w in words if w not in found[0]], "unless the command assigns" in found[0]) == (1, [], False)


def test_the_readme_names_the_forms_and_the_named_gaps_of_the_expansion():
    """Checks: E113 (H4, R260g), the paragraph of the `upgrade` target names the prefix in any case, the default and alternative forms, PowerShell `$HOME`; the gap paragraph names the operators that stay unexpanded, the re-point and the missing name, the built paths; the stale prefix-assignment sentence is gone."""
    main = [p for p in _paragraphs("README.md") if PARAGRAPH_MARK in p]
    gaps = [p for p in _paragraphs("README.md") if GAP_MARK in p]
    main_words = ["in any case", "`${X:-d}`", "expanded once more", "else `USERPROFILE`"]
    gap_words = ["operators `%`", "is logged only", "a name missing from the environment", "`Join-Path`",
                 "`[Environment]::GetEnvironmentVariable`"]
    assert (len(main), len(gaps), [w for w in main_words if w not in main[0]], [w for w in gap_words if w not in gaps[0]],
            "does not change this" in gaps[0]) == (1, 1, [], [], False)
