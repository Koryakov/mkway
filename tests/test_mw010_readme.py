"""The README recipe «Owner hold» (card MW-010, part 2)."""
import re

import pytest

from _engine import REPO

README = REPO / "README.md"
HEADING = "## Owner hold"


def _section():
    text = README.read_text(encoding="utf-8")
    start = text.index(HEADING + "\n")
    rest = text[start + len(HEADING):]
    nxt = re.search(r"^## ", rest, re.M)
    return rest[:nxt.start()] if nxt else rest


@pytest.mark.engine_repo  # the README is not in an engine copy: `mkway check` leaves these out (as test_register does)
def test_the_readme_has_the_owner_hold_recipe():
    """E6 (part 2): one section `## Owner hold` of 3 to 4 lines: the profile line, the two commands, one sentence on
    what the hold stops (every session write and commit) and what it does not (reading, answering, a word in a
    message). Catches: a recipe with a wrong profile line, a missing command, or a missing limit."""
    text = README.read_text(encoding="utf-8")
    assert text.count("\n" + HEADING + "\n") == 1
    body = _section()
    lines = [line for line in body.splitlines() if line.strip()]
    assert 3 <= len(lines) <= 5, len(lines)  # changed by MW-022 (E9): one more line, the shared marker
    flat = " ".join(body.split())
    for needed in ('locks.targets: [{"name": "hold", "paths": ["**"], "open_by_default": true}]',
                   "`mkway lock close hold`", "`mkway lock open hold`", "every session write and commit",
                   "reading", "answering", "a word in a message", "`mkway hold`", "`mkway go`"):
        assert needed in flat, needed
    # part 3 (R123): the short forms come first, the long forms after
    assert flat.index("`mkway hold`") < flat.index("`mkway go`") < flat.index("`mkway lock close hold`")
