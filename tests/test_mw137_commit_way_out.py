"""Card MW-137 (R358 3), through the REAL hook command: one engine install (module fixture, a scratch git repository, the task
folder below the git top). CARD-001 is ordered by the registered lead `lead1`, opened with Paths `src/a.py` and held by
`holder1`, which stages `src/b.py`. The commit gate's refusal `file-not-in-card` used to say «ask the owner to `card open <id>`
again», which records no Paths; it now names the lead's `card paths`, and the test runs that way out. Synthetic names only."""
import json
import re

import pytest

from _hook_driver import decision, install_project
import register

pytestmark = [pytest.mark.engine_repo, pytest.mark.xdist_group("test_mw137_commit_way_out")]

LEAD, HOLDER = "lead1", "holder1"
CLI = "python mkway/engine/mkway.py"
COMMIT = 'git commit -m "CARD-001 add b"'


def _set_paths(text, value):
    return re.sub(r"^\| \*\*Paths\*\* \|.*\|$", f"| **Paths** | {value} |", text, flags=re.M)


@pytest.fixture(scope="module")
def proj(tmp_path_factory):
    p = install_project(tmp_path_factory.mktemp("commitwayout"))
    p.profile(**{"tests.command": "python green.py", "cards": {"approver": "orderer"}})
    p.write("green.py", "raise SystemExit(0)\n")
    p.write("src/a.py", "VALUE = 1\n")
    p.git("add", "-f", "--", "green.py", "src/a.py")
    p.git("commit", "-q", "-m", "baseline")
    p.owner("card", "new", "Work")
    card = next((p.root / "mkway" / "cards").glob("CARD-001-*")) / "CARD.md"
    card.write_text(_set_paths(card.read_text(encoding="utf-8"), "`src/a.py`"), encoding="utf-8", newline="\n")
    p.owner("card", "resync", "--add-ordered-by", check=False)
    profile = json.loads((p.root / "mkway" / "profile.json").read_text(encoding="utf-8"))
    register.set_ordered(p.root, profile, "CARD-001", LEAD)
    for session in (LEAD, HOLDER):
        decision(p.fire("SessionStart", session))
    p.session_shell(LEAD, f"{CLI} lead register")
    p.owner("card", "open", "CARD-001")
    p.session_shell(HOLDER, f"{CLI} card take CARD-001")
    p.write("src/b.py", "VALUE = 2\n")
    p.git("add", "-f", "--", "src/b.py")
    p.card_file = card
    return p


def _commit(p):
    return decision(p.fire("PreToolUse", HOLDER, "Bash", {"command": COMMIT}))


def test_the_commit_refusal_no_longer_sends_the_owner_to_a_reopen(proj):
    """Catches: a refusal that says a re-open records the added files, when a re-open of an open card records nothing. E37"""
    got = _commit(proj)
    assert (got.kind, got.reason_id) == ("deny", "file-not-in-card"), f"{got}: {got.text}"
    assert "ask the owner to `card open" not in got.text and "again, or write a new card" not in got.text, got.text
    assert "write a new card" in got.text, got.text


def test_the_way_out_of_the_commit_refusal_is_the_leads_card_paths_and_the_same_commit_passes(proj):
    """Catches: a named route that does not make the same commit pass: the lead that ordered the card adds the entry. E38"""
    got = _commit(proj)
    found = re.search(r"`python mkway/engine/mkway\.py (card paths (\S+) --add <entry>)`", got.text)
    assert found and found.group(2) == "CARD-001", got.text
    proj.session_write(HOLDER, "mkway/cards/" + proj.card_file.parent.name + "/CARD.md",
                       _set_paths(proj.card_file.read_text(encoding="utf-8"), "`src/a.py`, `src/b.py`"))
    proj.session_shell(LEAD, f"{CLI} " + found.group(1).replace("<entry>", "src/b.py"))
    again = _commit(proj)
    assert (again.kind, again.reason_id) == ("allow", None), f"{again}: {again.text}"
