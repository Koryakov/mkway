"""Card MW-068 (ruling R173 items 1 and 2), through the REAL close command: one engine install (a scratch git repository,
the task folder below the git top), a test file committed by a session through the real hooks (the commit gate writes
its commit record), and the owner's `card close` run in the owner's terminal. Synthetic names only. The tests run in file
order: the last one closes the card."""
import re
import sys

import pytest

import os

from _hook_driver import decision, install_project
from _mw019 import add_agent, at
from _mw068 import record
from _red_project import commit_red_first
import records

# MW-085 (R213): engine_repo again (the install reads this repository), but not the shared lane; its module fixture builds once, on one worker
pytestmark = [pytest.mark.engine_repo, pytest.mark.xdist_group("test_mw068_records_e2e")]

CLI = "python mkway/engine/mkway.py"
BUILDER, READER = "s-builder", "s-reader"
ONE = "CARD-001"
TEST_FILE, CODE_FILE = "tests/test_rec.py", "src/rec.py"
NODE = "tests/test_rec.py::test_rec"
# R217: the card's test fails first, by the code file the card owns, and the code commit makes it pass
TEST = 'from src.rec import VALUE\n\n\ndef test_rec():\n    """Catches: the record is missing."""\n    assert VALUE == 1\n'
CODE = "VALUE = 1\n"
HEADER = "| Node | Verdict | Reason | By |\n|---|---|---|---|\n"


def _card_text(template):
    text = template.replace("| **Paths** | |", f"| **Paths** | `{TEST_FILE}`, `{CODE_FILE}` |")
    text = text.replace("«the owner's words, quoted» — owner, YYYY-MM-DD.", "A synthetic goal for the close.")
    return text.replace("| E1 | item id | value today | value after the change | tests/test_x.py::test_y |",
                        f"| E1 | the record | absent | there | {NODE} |")


@pytest.fixture(scope="module")
def proj(tmp_path_factory):
    """A card the builder session holds and commits its test for through the real hooks; the builder then releases it, so
    the holder rule is not what refuses a row by the builder."""
    p = install_project(tmp_path_factory.mktemp("records"))
    p.profile(**{"python.command": sys.executable, "gates.trip": {"min_calls": 100000}})  # the checker key is the install's
    from _engine import agent_file
    agent_file(p.root, "fresh-reader", "Read, Grep")  # MW-071: the default checker's definition (decision: R180)
    p.owner("card", "new", "Records card")
    card_file = next((p.root / "mkway" / "cards").glob(f"{ONE}-*")) / "CARD.md"
    card_file.write_text(_card_text(card_file.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    p.owner("card", "open", ONE)
    for session in (BUILDER, READER):
        decision(p.fire("SessionStart", session))
    p.session_shell(BUILDER, f"{CLI} card take {ONE}")
    p.write(TEST_FILE, TEST)
    p.write(CODE_FILE, CODE)
    # R217: red-first through the real hooks: the test alone (red by the missing module), then the code; the test file stays
    # in the first commit, made by BUILDER, which is the session the close rows rely on
    commit_red_first(p.git, lambda paths: p.session_shell(BUILDER, "git add -f -- " + " ".join(paths)),
                     lambda message, paths: p.session_shell(BUILDER, f"git commit -m '{message}'"),
                     (f"{ONE} the test of the record", [TEST_FILE]), (f"{ONE} the code of the record", [CODE_FILE]))
    records.append(p.root / "mkway" / "state", BUILDER, "release", ONE)
    p.owner("card", "resync", check=False)
    return p


def _verdicts(p, *rows):
    p.write("tests/verdicts/CARD-001.md", HEADER + "".join(f"| {r} |\n" for r in rows))


def _prove(p, session):
    """What a real reader leaves (ruling R173 item 2, decision: R196): a fresh checker agent in its session, after the test
    file's last change, and the record of the engine command for its rows (written here in the shape the command writes)."""
    stamp = at(0).timestamp()
    os.utime(p.root / TEST_FILE, (stamp, stamp))
    add_agent(p.root, session=session, agent_type="fresh-reader", agent_id=f"agent-{session}")
    record(p.root, "tests/verdicts/CARD-001.md", session, f"agent-{session}")


def _close(p):
    return p.owner("card", "close", ONE, check=False)


def _status(p):
    register = (p.root / "mkway" / "cards" / "REGISTER.md").read_text(encoding="utf-8")
    return re.search(rf"^\| {ONE} \|.*\| (open|closed) \|", register, re.M).group(1)


def test_a_real_install_writes_the_default_checker_into_the_profile(proj):
    """Checks: a real mkway install writes the default checker into the profile, so every new root starts with the blind verdict enforced (R179 condition 2)."""
    import json
    profile = json.loads((proj.root / "mkway" / "profile.json").read_text(encoding="utf-8"))
    assert profile["outbox"]["checkers"] == ["fresh-reader"]  # MW-071 E19, decision: R180


def test_close_is_refused_when_the_reader_is_a_session_that_committed_the_test(proj):
    """Catches: a card closed on a verdict by the session that committed the test, which the commit gate's record names although the repository history names another author."""
    _verdicts(proj, f"{NODE} | true | fine | session:{BUILDER}")
    _prove(proj, BUILDER)
    done = _close(proj)
    assert done.returncode != 0, done.stderr
    assert "verdict-by-committer" in done.stderr, done.stderr
    assert NODE in done.stderr, done.stderr
    assert _status(proj) == "open"


def test_close_is_refused_when_the_true_row_of_another_session_has_no_proof(proj):
    """Catches: a true row by a session that never wrote it, with no write record and no fresh reader, closing the card through the real close."""
    # the nearest allow is the test below, the same row with its proof
    _verdicts(proj, f"{NODE} | true | fine | session:{READER}")
    done = _close(proj)
    assert done.returncode != 0, done.stderr
    assert "verdict-unproven" in done.stderr, done.stderr
    assert NODE in done.stderr, done.stderr
    assert _status(proj) == "open"


def test_a_true_row_by_a_session_that_did_not_commit_the_test_with_proof_lets_the_close_pass(proj):
    """Checks: the nearest allow of the two denies above, a reader that did not commit the test and has its proof, a fresh reader agent and the real post hook's write record, lets the close pass."""
    # last in the file: it closes the card
    _verdicts(proj, f"{NODE} | true | fine | session:{READER}")
    _prove(proj, READER)
    done = _close(proj)
    assert done.returncode == 0, done.stdout + done.stderr
    assert _status(proj) == "closed"
