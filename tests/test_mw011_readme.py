"""Card MW-011, part 3: the README section «Closing cards», the KEYS lines and the usage texts."""
import json
import re

import pytest

from _engine import REPO
from _keys_md import section_rows, unquote
import mkway

README = REPO / "README.md"
HEADING = "## Closing cards"
NEEDLES = ("close-not-orderer", "close-by-holder", "close-tests-failing", "cards.approver", "orderer",
           "owner-only", "Ordered by", "mkway give <card> <who>", "mkway sessions",
           "card resync --add-ordered-by", "card set <id> closed", "owner", "open", "waiting",
           "give-ambiguous")


def _section():
    text = README.read_text(encoding="utf-8")
    start = text.index(HEADING + "\n")
    rest = text[start + len(HEADING):]
    nxt = re.search(r"^## ", rest, re.M)
    return " ".join((rest[:nxt.start()] if nxt else rest).split())


def _needle_id(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


@pytest.mark.engine_repo  # the README is not in an engine copy: `mkway check` leaves these out
def test_the_readme_has_one_section_closing_cards():
    """Catches: a second section or an empty heading (E21 rule 8)."""
    text = README.read_text(encoding="utf-8")
    assert text.count("\n" + HEADING + "\n") == 1
    assert len(_section()) > 600


@pytest.mark.engine_repo
@pytest.mark.parametrize("needle", [pytest.param(n, id=_needle_id(n)) for n in NEEDLES])
def test_the_section_states_who_may_close_the_commands_and_the_default(needle):
    """Checks: the section names who may close the commands, the refusals and the default (E22 rule 8)."""
    flat = _section()
    manifest = json.loads((REPO / "engine" / "manifest.json").read_text(encoding="utf-8"))["entries"]
    declared = {r for e in manifest if e["name"] == "lock.shell" for r in e["reason_ids"]}
    assert {"close-not-orderer", "close-by-holder"} <= declared
    assert f"`{needle}`" in flat


def test_keys_md_lines_state_the_orderer_and_the_sixth_column():
    """Catches: a profile value the keys list does not describe, such as the approver default or the sixth column name (E23 rule 8)."""
    rows = {unquote(r[0]): r for r in section_rows("Added keys")}
    approver, columns = rows["cards.approver"], rows["register.columns"]
    assert "`owner-only`" in approver[3]
    assert "`orderer`" in approver[3]
    assert "default" in approver[3]
    assert "`Ordered by`" in columns[3]
    assert "six" in columns[3]


def test_the_usage_texts_name_the_new_commands():
    """Catches: a command the usage text does not list (E24 rule 8)."""
    doc = mkway.__doc__
    assert "give <card> <who>" in doc
    assert "sessions" in doc
    assert "--add-ordered-by" in doc
    helptext = mkway._parser().format_help()
    assert "give" in helptext
    assert "sessions" in helptext
    card = [a for a in mkway._parser()._subparsers._group_actions[0].choices["card"]._subparsers._group_actions
            ][0].choices["resync"].format_help()
    assert "--add-ordered-by" in card
