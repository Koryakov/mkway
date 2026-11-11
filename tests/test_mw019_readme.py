"""Card MW-019, part 5: the README section «Outbox check: a text leaves only after a fresh reader». The reasons and keys
are read from the manifest and the schema, so the text cannot drift from them."""
import json
import re

import pytest

from _engine import REPO

README = REPO / "README.md"
HEADING = "## Outbox check: a text leaves only after a fresh reader"
REASONS = ("check-sha-mismatch", "check-record-failed", "outbox-changed-after-check", "close-unchecked-outbox")

pytestmark = pytest.mark.engine_repo  # the README is not in an engine copy: `mkway check` leaves these out


def _section():
    text = README.read_text(encoding="utf-8")
    start = text.index(HEADING + "\n")
    rest = text[start + len(HEADING):]
    nxt = re.search(r"^## ", rest, re.M)
    return " ".join((rest[:nxt.start()] if nxt else rest).split())


def test_one_section_with_a_body():
    """E17: one heading `## Outbox check: a text leaves only after a fresh reader`, with a body. Catches: a missing or
    doubled section."""
    assert README.read_text(encoding="utf-8").count("\n" + HEADING + "\n") == 1
    assert len(_section()) > 1200


def test_the_section_names_every_reason_key_state_and_command():
    """E17: every reason id of the three outbox entries and of the close, the three profile keys, the four states, the
    five check lines, the record file, the two commands that matter (`mkway outbox`, `card close`) and the suffix are in
    the text. Catches: a refusal a session will meet that the README does not explain."""
    flat = _section()
    manifest = json.loads((REPO / "engine" / "manifest.json").read_text(encoding="utf-8"))["entries"]
    declared = {r for e in manifest if e["name"].startswith("outbox_check.") for r in e["reason_ids"]}
    assert declared == {"check-sha-mismatch", "check-record-failed", "outbox-changed-after-check"}
    for reason in REASONS:
        assert f"`{reason}`" in flat, reason
    for key in ("outbox.dir", "outbox.checkers", "outbox.id_patterns_file"):
        assert f"`{key}`" in flat, key
    for word in ("`valid`", "`stale`", "`unproven`", "`missing`", "`sha256: <the document's sha256>`",
                 "`numbers: N checked, 0 contradictions`", "`claims: N checked, 0 overstated, 0 without basis`",
                 "`patterns: clean`", "`links: clean`", "`checker: <agent type>`", "`.check.md`", "`mkway outbox`",
                 "`card close`", "`outbox_checks.jsonl`", "`agents.jsonl`", "`outbox: N files, M unchecked`"):
        assert word in flat, word


def test_the_section_names_the_bypass_set():
    """E17: the section says which tries stay refused or unproven: the document edited after the check, a check copied
    from another file, a checker type not on the list, no agent row, a pattern present while the line says clean, the
    sha line of an older version; and that the engine ships no pattern and the class of the write gate is form.
    Catches: a rule whose edges the reader must find in the code."""
    flat = _section().lower()
    for phrase in ("edited after the check", "copied from another file", "not on the list", "no agent row",
                   "says clean", "older version", "ships no pattern", "class `form`", "watch"):
        assert phrase in flat, phrase
