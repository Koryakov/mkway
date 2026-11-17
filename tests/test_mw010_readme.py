"""The README recipe «Owner hold» (card MW-010, part 2)."""
import re

import pytest

from _engine import REPO

README = REPO / "README.md"
HEADING = "## Owner hold"
NEEDED = [
    pytest.param('locks.targets: [{"name": "hold", "paths": ["**"], "open_by_default": true}]', id="lock-targets-line"),
    pytest.param("`mkway lock close hold`", id="lock-close-command"),
    pytest.param("`mkway lock open hold`", id="lock-open-command"),
    pytest.param("every session write and commit", id="what-it-stops"),
    pytest.param("reading", id="reading-not-stopped"),
    pytest.param("answering", id="answering-not-stopped"),
    pytest.param("a word in a message", id="word-not-stopped"),
    pytest.param("`mkway hold`", id="short-hold"),
    pytest.param("`mkway go`", id="short-go"),
]


def _section():
    text = README.read_text(encoding="utf-8")
    start = text.index(HEADING + "\n")
    rest = text[start + len(HEADING):]
    nxt = re.search(r"^## ", rest, re.M)
    return rest[:nxt.start()] if nxt else rest


@pytest.mark.engine_repo  # the README is not in an engine copy: `mkway check` leaves these out (as test_register does)
@pytest.mark.parametrize("needed", NEEDED)
def test_the_readme_has_the_owner_hold_recipe(needed):
    """Checks: the README holds the owner hold recipe with its profile line, its commands and its limit (E6 part 2: one section `## Owner hold` of 3 to 5 lines)."""
    # a recipe with a wrong profile line, a missing command, or a missing limit fails here
    text = README.read_text(encoding="utf-8")
    assert text.count("\n" + HEADING + "\n") == 1
    body = _section()
    lines = [line for line in body.splitlines() if line.strip()]
    assert 3 <= len(lines) <= 5, len(lines)  # changed by MW-022 (E9): one more line, the shared marker
    flat = " ".join(body.split())
    assert needed in flat, needed
    # part 3 (R123): the short forms come first, the long forms after
    assert flat.index("`mkway hold`") < flat.index("`mkway go`") < flat.index("`mkway lock close hold`")
