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
    """E18 (rule 9): one heading `## Watch mode and trip`, with a body. Catches: a second section or an empty
    heading."""
    text = README.read_text(encoding="utf-8")
    assert text.count("\n" + HEADING + "\n") == 1
    assert len(_section()) > 800


@pytest.mark.engine_repo
def test_the_section_states_what_trips_who_resets_and_why():
    """E19 (rule 9): the section says what trips (a form gate, the calls and share keys with their defaults, the last
    24 hours, errors not counted, the tripping call stays refused), what watch does (`would-refuse`, the calls log, the
    marker folder, a first install starts in watch), who resets (the owner's `mkway gate on <name>`; never automatic)
    and why integrity gates never degrade (`integrity gates never watch`). Catches: a mode that a session meets and
    the README does not explain."""
    flat = _section()
    for needed in ("`form`", "`integrity`", "`gates.trip.min_calls`", "`gates.trip.share`", "`20`", "`0.34`",
                   "24 hours", "`error`", "`would-refuse`", "`gate_calls.jsonl`", "`gate_mode/<gate>.watch`",
                   "`gate-tripped`", "first install", "`mkway gate on <name>`", "`mkway gate watch <name>`",
                   "integrity gates never watch", "no automatic return"):
        assert needed in flat, needed


def test_keys_md_lines_state_the_two_trip_keys():
    """E20 (rule 9): the «Added keys» table has a line for `gates.trip.min_calls` and one for `gates.trip.share`, «in
    schema now» with the schema path `gates` and the default named. Catches: a key the gate reads that the keys list
    does not describe."""
    rows = {unquote(r[0]): r for r in section_rows("Added keys")}
    for key, default in (("gates.trip.min_calls", "`20`"), ("gates.trip.share", "`0.34`")):
        assert rows[key][1:3] == [NOW, "`gates`"], key
        assert default in rows[key][3], key
