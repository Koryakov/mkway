"""Card MW-011, part 3: the README section «Closing cards», the KEYS lines and the usage texts."""
import json
import re

import pytest

from _engine import REPO
from _keys_md import section_rows, unquote
import mkway

README = REPO / "README.md"
HEADING = "## Closing cards"


def _section():
    text = README.read_text(encoding="utf-8")
    start = text.index(HEADING + "\n")
    rest = text[start + len(HEADING):]
    nxt = re.search(r"^## ", rest, re.M)
    return " ".join((rest[:nxt.start()] if nxt else rest).split())


@pytest.mark.engine_repo  # the README is not in an engine copy: `mkway check` leaves these out
def test_the_readme_has_one_section_closing_cards():
    """E21 (rule 8): one heading `## Closing cards`, with a body. Catches: a second section or an empty heading."""
    text = README.read_text(encoding="utf-8")
    assert text.count("\n" + HEADING + "\n") == 1
    assert len(_section()) > 600


@pytest.mark.engine_repo
def test_the_section_states_who_may_close_the_commands_and_the_default():
    """E22 (rule 8): the section says who may close a card (the owner's terminal; with `orderer` the session that
    ordered it, never the holder, when the card is open or waiting and every Acceptance row's test passes), the two
    owner commands (`give`, `sessions`), the sixth column and its resync, the three refusals read from the manifest
    and the code, and that the default stays `owner-only`. Catches: a section that leaves out a refusal a session
    will meet, or that no longer names the default."""
    flat = _section()
    manifest = json.loads((REPO / "engine" / "manifest.json").read_text(encoding="utf-8"))["entries"]
    declared = {r for e in manifest if e["name"] == "lock.shell" for r in e["reason_ids"]}
    for reason in ("close-not-orderer", "close-by-holder", "close-tests-failing"):
        assert f"`{reason}`" in flat, reason
    assert {"close-not-orderer", "close-by-holder"} <= declared
    for needed in ("`cards.approver`", "`orderer`", "`owner-only`", "`Ordered by`", "`mkway give <card> <who>`",
                   "`mkway sessions`", "`card resync --add-ordered-by`", "`card set <id> closed`", "`owner`",
                   "`open`", "`waiting`", "`give-ambiguous`"):
        assert needed in flat, needed


def test_keys_md_lines_state_the_orderer_and_the_sixth_column():
    """E23 (rule 8): the KEYS.md line of `cards.approver` names both values, `owner-only` as the default and `orderer`;
    the line of `register.columns` names the sixth column and its default `Ordered by`. Catches: a profile value the
    keys list does not describe."""
    rows = {unquote(r[0]): r for r in section_rows("Added keys")}
    approver, columns = rows["cards.approver"], rows["register.columns"]
    assert "`owner-only`" in approver[3] and "`orderer`" in approver[3] and "default" in approver[3]
    assert "`Ordered by`" in columns[3] and "six" in columns[3]


def test_the_usage_texts_name_the_new_commands():
    """E24 (rule 8): the module's usage lines and the parser's help name `give`, `sessions` and `card resync
    --add-ordered-by`. Catches: a command the usage text does not list."""
    doc = mkway.__doc__
    assert "give <card> <who>" in doc and "sessions" in doc and "--add-ordered-by" in doc
    helptext = mkway._parser().format_help()
    assert "give" in helptext and "sessions" in helptext
    card = [a for a in mkway._parser()._subparsers._group_actions[0].choices["card"]._subparsers._group_actions
            ][0].choices["resync"].format_help()
    assert "--add-ordered-by" in card
