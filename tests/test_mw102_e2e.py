"""Card MW-102 (decision: R254), through the REAL hook command: one engine install (module fixture, a scratch git repository, the
task folder below the git top). CARD-001 is ordered by the session `lead` and its verdict rows are written by the real
`verdict add` (in process); CARD-002 is open and held by the session `holder1`, whose Paths cover `tests/verdicts/`. The verdict is read
from the hook's JSON (`tests/_hook_driver.py::decision`). Synthetic names only."""
import re

import pytest

import _mw080 as w
from _engine import agent_file
from _hook_driver import decision, install_project
import register

pytestmark = [pytest.mark.engine_repo, pytest.mark.xdist_group("test_mw102_e2e")]

LEAD, HOLDER, READER = "lead1", "holder1", "reader"
REL1, REL2 = "tests/verdicts/CARD-001.md", "tests/verdicts/CARD-002.md"
CLI = "python mkway/engine/mkway.py"
ROW = "| tests/test_a.py::test_one | true | typed by hand | session:reader |\n"
HEADER = "| Node | Verdict | Reason | By |\n|---|---|---|---|\n"


def _card_two(text):
    text = text.replace("| **Paths** | |", "| **Paths** | `tests/verdicts/` |")
    text = text.replace("«the owner's words, quoted» — owner, YYYY-MM-DD.", "A synthetic goal for the hook rows.")
    return text.replace("| E1 | item id | value today | value after the change | tests/test_x.py::test_y |",
                        "| E1 | the thing | absent | present | tests/test_a.py::test_one |")


@pytest.fixture(scope="module")
def proj(tmp_path_factory):
    p = install_project(tmp_path_factory.mktemp("verdictcommit"))
    p.profile(**{"tests.command": "python green.py", "outbox.checkers": [w.CHECKER]})
    agent_file(p.root, w.CHECKER, "Read, Grep")
    p.write("green.py", "raise SystemExit(0)\n")
    p.write(w.FILE, w.SRC)
    p.write(w.OTHER_FILE, w.SRC_B)
    w.git(p.root, "add", "-f", "--", "green.py", w.FILE, w.OTHER_FILE)
    w.git(p.root, "commit", "-q", "-m", "CARD-001 the tests", when=w.COMMIT_AT)
    p.owner("card", "new", "First")
    p.owner("card", "new", "Second")
    cards = p.root / "mkway" / "cards"
    one = next(cards.glob("CARD-001-*")) / "CARD.md"
    two = next(cards.glob("CARD-002-*")) / "CARD.md"
    rows = "".join(f"| E{n} | item | was | must | {node} |\n" for n, node in enumerate((w.N1, w.N2), 1))
    one.write_text("# CARD-001: First\n\n## Acceptance examples\n\n| # | Item | Was | Must be | Test |\n|---|---|---|---|---|\n"
                   + rows + "\n## 8. Log\n\n| Date | Step | Commit | Result |\n|---|---|---|---|\n", encoding="utf-8")
    two.write_text(_card_two(two.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    p.owner("card", "resync", "--add-ordered-by", check=False)
    profile = w.profile_of(p.root)
    register.set_ordered(p.root, profile, "CARD-001", LEAD)

    def waiting(table):
        register.find(table, "CARD-001")["status"] = "waiting"
        return table
    register.write(p.root, profile, waiting)
    p.owner("card", "open", "CARD-002")
    for session in (LEAD, HOLDER):
        decision(p.fire("SessionStart", session))
    p.session_shell(HOLDER, f"{CLI} card take CARD-002")
    w.reader(p.root, READER, "a1")
    w.seed_red(p.root)  # MW117-D1: the card has its red-proof row before a verdict is written
    assert w.apply(p.root, READER, [w.N1, w.N2], "true", "one clause, one case").allowed
    return p


class staged:
    """The verdict file of a card staged with `git add -f`, unstaged again after the row."""

    def __init__(self, p, rel, content=None):
        self.p, self.rel, self.content = p, rel, content

    def __enter__(self):
        if self.content is not None:
            self.p.write(self.rel, self.content)
        self.p.git("add", "-f", "--", self.rel)
        return self

    def __exit__(self, *_):
        self.p.git("rm", "--cached", "-q", "-f", "--", self.rel, check=False)


def _commit(p, session, card):
    return decision(p.fire("PreToolUse", session, "Bash", {"command": f'git commit -m "{card} the verdict file"'}))


def test_the_holder_commits_its_own_verdict_file_and_the_real_hook_denies(proj):
    """Catches: the holder of CARD-002 committing its own card's verdict file because its Paths cover `tests/`."""
    with staged(proj, REL2, HEADER + ROW):
        got = _commit(proj, HOLDER, "CARD-002")
    assert (got.kind, got.reason_id, "the holder never commits" in got.text) == ("deny", "file-not-in-card", True), got.text


def test_the_orderer_commits_a_typed_row_and_the_real_hook_denies(proj):
    """Catches: the orderer of CARD-001 committing a verdict row typed by hand, with no `verdict add` record behind it."""
    real = (proj.root / REL1).read_text(encoding="utf-8")
    try:
        with staged(proj, REL1, HEADER + ROW):
            got = _commit(proj, LEAD, "CARD-001")
    finally:
        proj.write(REL1, real)
    assert (got.kind, got.reason_id, "tests/test_a.py::test_one" in got.text) == ("deny", "verdict-unproven", True), got.text


def test_the_orderer_commits_rows_written_by_verdict_add_and_the_real_hook_allows(proj):
    """Checks: the nearest allow: the orderer of CARD-001 commits the rows the real `verdict add` wrote, through the real hook."""
    with staged(proj, REL1):
        got = _commit(proj, LEAD, "CARD-001")
    assert (got.kind, got.reason_id) == ("allow", None), f"{got}: {got.text}"


def test_the_orderer_commits_a_verdict_whose_acceptance_row_changed_and_the_real_hook_denies_verdict_stale(proj):
    """Catches: MW-117 (R287 Q4), the Acceptance row of the node reworded after the reader judged it and the orderer still
    committing the verdict file; the refusal id is verdict-stale and names the node."""
    card = next((proj.root / "mkway" / "cards").glob("CARD-001-*")) / "CARD.md"
    real = card.read_text(encoding="utf-8")
    try:
        card.write_text(real.replace("| item | was | must |", "| item | was | must differ |", 1), encoding="utf-8", newline="\n")
        with staged(proj, REL1):
            got = _commit(proj, LEAD, "CARD-001")
    finally:
        card.write_text(real, encoding="utf-8", newline="\n")
    assert (got.kind, got.reason_id, "tests/test_a.py::test_one" in got.text) == ("deny", "verdict-stale", True), got.text
