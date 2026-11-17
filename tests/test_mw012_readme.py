"""Card MW-012, part 5: the README section «Watch mode and trip» and the KEYS lines of the two trip keys."""
import re

import pytest

from _engine import REPO
from _keys_md import section_rows, unquote

README = REPO / "README.md"
HEADING = "## Watch mode and trip"
NOW = "in schema now"


def _section():
    text = README.read_text(encoding="utf-8")
    start = text.index(HEADING + "\n")
    rest = text[start + len(HEADING):]
    nxt = re.search(r"^## ", rest, re.M)
    return " ".join((rest[:nxt.start()] if nxt else rest).split())


@pytest.mark.engine_repo  # the README is not in an engine copy: `mkway check` leaves these out
def test_the_readme_has_one_section_watch_mode_and_trip():
    """Catches: a second watch-mode section, or an empty heading. E18 (rule 9)."""
    text = README.read_text(encoding="utf-8")
    assert text.count("\n" + HEADING + "\n") == 1
    assert len(_section()) > 800


@pytest.mark.engine_repo
@pytest.mark.engine_repo
@pytest.mark.parametrize("needed", [
    "`form`", "`integrity`", "`gates.trip.min_calls`", "`gates.trip.share`", "`20`", "`0.34`",
    "24 hours", "`error`", "`would-refuse`", "`gate_calls.jsonl`", "`gate_mode/<gate>.watch`",
    "`gate-tripped`", "first install", "`mkway gate on <name>`", "`mkway gate watch <name>`",
    "integrity gates never watch", "no automatic return",
])
def test_the_section_states_what_trips_who_resets_and_why(needed):
    """Checks: the section names what trips, what watch does, who resets it, and why integrity gates never watch. E19 (rule 9)."""
    assert needed in _section(), needed


@pytest.mark.parametrize("key,default", [("gates.trip.min_calls", "`20`"), ("gates.trip.share", "`0.34`")],
                         ids=["min_calls", "share"])
def test_keys_md_lines_state_the_two_trip_keys(key, default):
    """Checks: the keys list describes each trip key in schema now, with its schema path and its default. E20 (rule 9)."""
    rows = {unquote(r[0]): r for r in section_rows("Added keys")}
    assert rows[key][1:3] == [NOW, "`gates`"], key
    assert default in rows[key][3], key
