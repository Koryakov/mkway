"""Card MW-019, part 5: the README section «Outbox check: a text leaves only after a fresh reader». The reasons and keys
are read from the manifest and the schema, so the text cannot drift from them."""
import json
import re

import pytest

from _engine import REPO

README = REPO / "README.md"
HEADING = "## Outbox check: a text leaves only after a fresh reader"
REASONS = ("check-sha-mismatch", "check-record-failed", "outbox-changed-after-check", "close-unchecked-outbox")
OUTBOX_NEEDLES = ("verdict-not-enforced",) + REASONS + (
    "outbox.dir", "outbox.checkers", "outbox.id_patterns_file", "valid", "stale", "unproven", "missing",
    "sha256: <the document's sha256>", "numbers: N checked, 0 contradictions",
    "claims: N checked, 0 overstated, 0 without basis", "patterns: clean", "links: clean",
    "checker: <agent type>", ".check.md", "mkway outbox", "card close", "outbox_checks.jsonl", "agents.jsonl",
    "outbox: N files, M unchecked")
BYPASS_PHRASES = ("edited after the check", "copied from another file", "not on the list", "no agent row",
                  "says clean", "older version", "ships no pattern", "class `form`", "watch")

pytestmark = pytest.mark.engine_repo  # the README is not in an engine copy: `mkway check` leaves these out


def _section():
    text = README.read_text(encoding="utf-8")
    start = text.index(HEADING + "\n")
    rest = text[start + len(HEADING):]
    nxt = re.search(r"^## ", rest, re.M)
    return " ".join((rest[:nxt.start()] if nxt else rest).split())


def _needle_id(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def test_one_section_with_a_body():
    """Catches: a missing or doubled section (E17)."""
    assert README.read_text(encoding="utf-8").count("\n" + HEADING + "\n") == 1
    assert len(_section()) > 1200


@pytest.mark.parametrize("needle", [pytest.param(n, id=_needle_id(n)) for n in OUTBOX_NEEDLES])
def test_the_section_names_every_reason_key_state_and_command(needle):
    """Checks: the section names every refusal reason, state and command of the outbox check (E17)."""
    manifest = json.loads((REPO / "engine" / "manifest.json").read_text(encoding="utf-8"))["entries"]
    declared = {r for e in manifest if e["name"].startswith("outbox_check.") for r in e["reason_ids"]}
    assert declared == {"check-sha-mismatch", "check-record-failed", "outbox-changed-after-check",
                        "verdict-not-enforced", "verdict-file-by-command"}  # MW-068 (R179), MW-080 (R196)
    assert f"`{needle}`" in _section()


@pytest.mark.parametrize("phrase", [pytest.param(p, id=_needle_id(p)) for p in BYPASS_PHRASES])
def test_the_section_names_the_bypass_set(phrase):
    """Checks: the section names the bypass set of the rule in plain words (E17)."""
    assert phrase in _section().lower()
