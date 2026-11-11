"""The README section «Commit checks» (card MW-006, part 6)."""
import json
import re

import pytest

from _engine import REPO

README = REPO / "README.md"
HEADING = "## Commit checks"


def _text():
    return README.read_text(encoding="utf-8")


def _section():
    text = _text()
    start = text.index(HEADING + "\n")
    rest = text[start + len(HEADING):]
    nxt = re.search(r"^## ", rest, re.M)
    return rest[:nxt.start()] if nxt else rest


def _flat(text):
    return " ".join(text.split())


@pytest.mark.engine_repo  # the README is not in an engine copy: `mkway check` leaves these out (as test_register does)
def test_the_readme_has_one_section_commit_checks():
    """E24 (part 6): one heading `## Commit checks`, with a body, and no other heading about commits.
    Catches: a second section, or a heading with no text."""
    text = _text()
    assert text.count("\n" + HEADING + "\n") == 1
    assert len(_flat(_section())) > 800
    # changed by the port of MW-005: the section `## Tests before a commit` is the other card's own section, so it is
    # the one heading about commits that is not this card's
    assert len([h for h in re.findall(r"^## .*$", text, re.M)
                if "commit" in h.lower() and h != "## Tests before a commit"]) == 1


@pytest.mark.engine_repo
def test_the_section_states_the_rules_reasons_keys_and_ways_out():
    """E25 (part 6): the section names the rules in their order, every reason id of the entries on the gate
    `commit_files` (read from the manifest), the three profile keys with every default (read from the schema and the
    module), the switch and the message switch, `take-root-busy`, the always-allowed
    files, the way out of each refusal and the limits (staging in the commit's own
    call is refused; the ignore check is for new files; the owner's terminal is not gated).
    Catches: a section that describes a gate the engine does not have, or leaves out a refusal a session will meet."""
    import gate_commit
    flat = _flat(_section())
    manifest = json.loads((REPO / "engine" / "manifest.json").read_text(encoding="utf-8"))["entries"]
    reasons = {r for e in manifest if e["gate"] == "commit_files" for r in e["reason_ids"]}
    assert len(reasons) == 9  # MW-021 (E6) added `rule-without-test`; MW-034 removed `ride-in-file`
    for reason in reasons:
        assert f"`{reason}`" in flat, reason
    schema = json.loads((REPO / "engine" / "profile.schema.json").read_text(encoding="utf-8"))
    for key in schema["properties"]["commit"]["properties"]:
        assert f"`commit.{key}`" in flat, key
    for pattern in gate_commit.JUNK + gate_commit.DATA:
        assert f"`{pattern}`" in flat, pattern
    assert f"`{gate_commit.MAX_FILE_KB}`" in flat
    for needed in ("`commit_files`", "`gates.commit_files`", "`gates.commit_files.message_card.on`",
                   "`take-root-busy`", "`paths.exempt`", "`<bundle.root>/ledger/`", "`ids.card_prefix`", "`git restore --staged <file>`",
                   "`git add -f`", "`-a`", "a call of its own", "`card resync`", "owner's own terminal",
                   "Right files only", "One builder per task root", "No junk", "No data files"):
        assert needed in flat, needed
    order = [flat.index(x) for x in ("Right files only", "One builder per task root", "No junk", "No data files")]
    assert order == sorted(order)
