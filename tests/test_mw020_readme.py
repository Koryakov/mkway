"""Card MW-020, row E12: the README section «Deliverables: built from tested code, compared with a named base». Keys
are read from the schema, so the text cannot drift from them."""
import json
import re

import pytest

from _engine import REPO

README = REPO / "README.md"
HEADING = "## Deliverables: built from tested code, compared with a named base"
REASONS = ("built-dirty", "built-untested", "built-no-file", "close-deliverable-unbuilt", "base-unknown",
           "delivered-no-file", "owner-only-command")

pytestmark = pytest.mark.engine_repo  # the README is not in an engine copy: `mkway check` leaves these out


def _section():
    text = README.read_text(encoding="utf-8")
    start = text.index(HEADING + "\n")
    rest = text[start + len(HEADING):]
    nxt = re.search(r"^## ", rest, re.M)
    return " ".join((rest[:nxt.start()] if nxt else rest).split())


def test_one_section_with_a_body():
    """Checks: one heading `## Deliverables: built from tested code, compared with a named base`, with a body (E12)."""
    # Catches: a missing or doubled section
    assert README.read_text(encoding="utf-8").count("\n" + HEADING + "\n") == 1
    assert len(_section()) > 1200


def test_the_section_names_every_reason_key_command_and_file():
    """Checks: every refusal reason, both profile keys, the commands, state files, check and start lines are in the text (E12)."""
    # Catches: a refusal a session will meet that the README does not explain
    flat = _section()
    schema = json.loads((REPO / "engine" / "profile.schema.json").read_text(encoding="utf-8"))
    assert set(schema["properties"]["deliverables"]["properties"]) == {"paths", "require_base"}
    missing_reasons = [r for r in REASONS if f"`{r}`" not in flat]
    assert not missing_reasons, missing_reasons
    missing_words = [word for word in (
        "`deliverables.paths`", "`deliverables.require_base`", "`mkway built <path>`",
        "`mkway delivered <path>`", "`mkway deliverables`", "`deliverables.jsonl`", "`delivered.jsonl`",
        "`commit_tests.jsonl`", "`base: <sha8>`", "`.check.md`", "`card close`",
        "`deliverables: N built, M changed since built, K delivered`") if word not in flat]
    assert not missing_words, missing_words


def test_the_section_names_the_rules_behind_the_gates():
    """Checks: the section says what a deliverable and its base are, and the bypass cases and the class stay refused (E12)."""
    # what a deliverable is: a file at a named path with its sha256, built on the final HEAD, past its gates and the
    # fresh-reader check; the base is a delivered file, never an internal run; Catches: a rule whose edges the reader
    # must find in the code
    flat = _section().lower()
    missing_phrases = [phrase for phrase in (
        "named path", "sha256", "final head", "fresh-reader", "never an internal run", "delivered file",
        "changed after it was built", "owner's command", "uncommitted", "ancestor", "command check") if phrase not in flat]
    assert not missing_phrases, missing_phrases
