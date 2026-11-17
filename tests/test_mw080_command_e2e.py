"""Card MW-080 (decisions: R194, R196), through the REAL command and the REAL hooks: one engine install (a scratch git
repository, the task folder below the git top), a test file committed by a builder session through the real commit hook (its
commit dated an hour before the reader rows, so the git timing is deterministic), the card released. The command runs as a
session's Bash call (the real PreToolUse hook leaves the by-permit, the real command reads it) or in the owner's terminal;
the PreToolUse refusal is read from the hook's JSON. Synthetic names only. Each test starts from an empty verdict folder and
empty agent and proof records."""
import os
import re
import subprocess
import sys

import pytest

from _hook_driver import decision, install_project
from _mw019 import add_agent, at
from _red_project import commit_red_first
import records

pytestmark = pytest.mark.engine_repo

CLI = "python mkway/engine/mkway.py"
BUILDER = "s-builder"
SESSIONS = (BUILDER, "s-former", "s-none", "s-stale", "s-ok", "s-typed", "s-lead", "s-hook")
CARD = "CARD-001"
FILE = "tests/test_first.py"
CODE_FILE = "src/first.py"
N1, N2, N3 = (f"{FILE}::test_{name}" for name in ("one", "two", "three"))
# R217b route 1: the card owns a code file; the three tests fail first for the missing module, then the code commit makes
# the same tests pass (the verdict command, this file's subject, reads the commit of the test file as before)
TEST = ('from src.first import ONE\n\n\n'
        'def test_one():\n    """Catches: the first value is missing."""\n    assert ONE + 1 == 2\n\n\n'
        'def test_two():\n    """Catches: the first value is missing."""\n    assert ONE + 1 == 2\n\n\n'
        'def test_three():\n    """Catches: the first value is missing."""\n    assert ONE + 1 == 2\n')
CODE = "ONE = 1\n"
VERDICT_REL = f"tests/verdicts/{CARD}.md"
FRESH = {"started": 60, "ended": 120}
OLD = {"started": -7200, "ended": -7100}
COMMIT_AT = -3600


def _card_text(template):
    text = template.replace("| **Paths** | |", f"| **Paths** | `{FILE}`, `{CODE_FILE}` |")
    text = text.replace("«the owner's words, quoted» — owner, YYYY-MM-DD.", "A synthetic goal for the command.")
    rows = "\n".join(f"| E{n} | the test | absent | there | {node} |" for n, node in enumerate((N1, N2, N3), 1))
    return text.replace("| E1 | item id | value today | value after the change | tests/test_x.py::test_y |", rows)


@pytest.fixture(scope="module")
def proj(tmp_path_factory):
    """A card the builder took and committed its test for through the real hooks, then released: open, nobody holds it."""
    p = install_project(tmp_path_factory.mktemp("verdict-add"))
    p.profile(**{"python.command": sys.executable, "gates.trip": {"min_calls": 100000},
                 "paths.exempt": ["tests/verdicts/*.md"]})
    from _engine import agent_file
    agent_file(p.root, "fresh-reader", "Read, Grep")
    p.owner("card", "new", "Verdict card")
    card_file = next((p.root / "mkway" / "cards").glob(f"{CARD}-*")) / "CARD.md"
    card_file.write_text(_card_text(card_file.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    p.owner("card", "open", CARD)
    for session in SESSIONS:
        decision(p.fire("SessionStart", session))
    p.session_shell(BUILDER, f"{CLI} card take {CARD}")
    p.write(FILE, TEST)
    p.write(CODE_FILE, CODE)
    when = at(COMMIT_AT).isoformat(timespec="seconds")

    def commit(message, paths):
        p.session_shell(BUILDER, f"git commit -m '{message}'")
        if FILE in paths:  # the commit of the test file is dated an hour before the reader rows
            subprocess.run(["git", "-c", "user.name=hook-driver", "-c", "user.email=hook-driver", "commit", "-q", "--amend",
                            "--no-edit", "--date", when], cwd=str(p.root), check=True, capture_output=True, timeout=60,
                           env={**os.environ, "GIT_COMMITTER_DATE": when})

    commit_red_first(p.git, lambda paths: p.session_shell(BUILDER, "git add -f -- " + " ".join(paths)), commit,
                     (f"{CARD} the tests of the command", [FILE]), (f"{CARD} the code of the tests", [CODE_FILE]))
    records.append(p.root / "mkway" / "state", BUILDER, "release", CARD)
    p.owner("card", "resync", check=False)
    return p


@pytest.fixture(autouse=True)
def _empty_records(proj):
    """Each test starts with no verdict file, no agent rows and no proof records."""
    for name in ("agents.jsonl", "outbox_checks.jsonl"):
        (proj.root / "mkway" / "state" / name).write_text("", encoding="utf-8")
    for old in (proj.root / "tests" / "verdicts").glob("*.md"):
        old.unlink()
    yield


def _reader(p, session, agent_id, **times):
    add_agent(p.root, session=session, agent_type="fresh-reader", agent_id=agent_id, guard=CARD, **(times or FRESH))


def _add(p, session, *items):
    quoted = " ".join(f'"{i}"' if " " in i else i for i in items)
    return p.session_shell(session, f"{CLI} verdict add {CARD} {quoted}", expect_ok=False)


def _file_text(p):
    path = p.root / VERDICT_REL
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def test_the_real_command_refuses_a_former_holder(proj):
    """Catches: the session that held the card once, and released it, writing a verdict row through the real command."""
    proj.session_shell("s-former", f"{CLI} card take {CARD}")
    proj.session_shell("s-former", f"{CLI} card release {CARD}")
    _reader(proj, "s-former", "a1")
    done = _add(proj, "s-former", N1, "true", "one clause, one case")
    assert done.returncode != 0
    assert "verdict-by-holder" in done.stderr


def test_the_real_command_refuses_a_session_with_no_reader_run(proj):
    """Catches: a session that never ran a checker agent writing a verdict row."""
    done = _add(proj, "s-none", N1, "true", "one clause, one case")
    assert done.returncode != 0
    assert "verdict-no-reader-run" in done.stderr


def test_the_real_command_refuses_a_reader_run_that_began_before_the_last_commit(proj):
    """Catches: a reader that read the text before its last commit giving a verdict about the committed text."""
    _reader(proj, "s-stale", "a1", **OLD)
    done = _add(proj, "s-stale", N1, "true", "one clause, one case")
    assert done.returncode != 0
    assert "verdict-stale" in done.stderr


def test_the_real_command_allows_a_fresh_reader_run_and_writes_the_row(proj):
    """Checks: the nearest allow of the three denies above: a session that never held the card, a fresh reader run."""
    _reader(proj, "s-ok", "a1")
    done = _add(proj, "s-ok", N1, "true", "one clause, one case")
    assert done.returncode == 0, done.stderr
    assert f"| {N1} | true | one clause, one case | session:s-ok |" in _file_text(proj)


def test_the_real_command_refuses_the_owners_terminal(proj):
    """Catches: the owner's terminal writing a verdict row (the verdict is never the owner's)."""
    done = proj.owner("verdict", "add", CARD, N1, "true", "one clause, one case", check=False)
    assert done.returncode != 0
    assert "verdict-by-owner" in done.stderr


def _hook(proj, tool, tool_input):
    return decision(proj.fire("PreToolUse", "s-hook", tool, tool_input))


def test_the_real_hook_refuses_a_write_of_a_verdict_file(proj):
    """Catches: a Write of tests/verdicts/<card>.md let through, so a verdict row has a second writer."""
    got = _hook(proj, "Write", {"file_path": proj.path(VERDICT_REL), "content": "x\n"})
    assert (got.kind, got.reason_id, got.gate) == ("deny", "verdict-file-by-command", "outbox_check.pre")


def test_the_real_hook_refuses_an_edit_of_a_verdict_file(proj):
    """Catches: an Edit of a verdict file let through."""
    got = _hook(proj, "Edit", {"file_path": proj.path(VERDICT_REL), "old_string": "a", "new_string": "b"})
    assert (got.kind, got.reason_id) == ("deny", "verdict-file-by-command")


def test_the_real_hook_refuses_a_multiedit_of_a_verdict_file(proj):
    """Catches: a MultiEdit of a verdict file let through."""
    got = _hook(proj, "MultiEdit", {"file_path": proj.path(VERDICT_REL), "edits": [{"old_string": "a", "new_string": "b"}]})
    assert (got.kind, got.reason_id) == ("deny", "verdict-file-by-command")


def test_the_real_hook_allows_a_write_of_another_test_file(proj):
    """Checks: the nearest allow of the three refusals above, the same hook with only the path changed: a Write of a card
    file (the one kind of file every session may write) is allowed while the verdict file is refused."""
    refused = _hook(proj, "Write", {"file_path": proj.path(VERDICT_REL), "content": "x\n"})
    allowed = _hook(proj, "Write", {"file_path": proj.path("mkway/cards/CARD-009-other/CARD.md"), "content": "x\n"})
    assert (refused.reason_id, allowed.kind) == ("verdict-file-by-command", "allow")


def _status(p):
    register = (p.root / "mkway" / "cards" / "REGISTER.md").read_text(encoding="utf-8")
    return re.search(rf"^\| {CARD} \|.*\| (open|closed) \|", register, re.M).group(1)


def test_a_row_typed_through_the_real_write_hooks_is_unproven_at_the_close(proj):
    """Catches: the post hook still turning a Write of a verdict file into a proof row, so a typed row with a reader run
    behind it closes the card. Changed by MW-115 (decision: MW115-D2): the pre gate is hard in the default mode and
    cannot be put in watch (gate-watch-integrity, the text names a form gate), so the typed Write is refused, and the
    file is then put on disk without the tool and the post hook runs on it."""
    watched = proj.owner("gate", "watch", "outbox_check.pre", check=False)
    assert watched.returncode != 0
    assert "gate-watch-integrity" in watched.stderr
    assert "mkway gate watch message" in watched.stderr
    _reader(proj, "s-typed", "a1")
    stamp = at(0).timestamp()
    os.utime(proj.root / FILE, (stamp, stamp))
    text = ("| Node | Verdict | Reason | By |\n|---|---|---|---|\n"
            f"| {N1} | true | typed | session:s-typed |\n")
    tool_input = {"file_path": proj.path(VERDICT_REL), "content": text}
    assert decision(proj.fire("PreToolUse", "s-typed", "Write", tool_input)).reason_id == "verdict-file-by-command"
    proj.write(VERDICT_REL, text)
    proj.fire("PostToolUse", "s-typed", "Write", tool_input, tool_response={"filePath": proj.path(VERDICT_REL)})
    done = proj.owner("card", "close", CARD, check=False)
    assert done.returncode != 0
    assert "verdict-unproven" in done.stderr
    assert _status(proj) == "open"


def test_the_first_real_close_shape_two_calls_then_the_close_reports_the_weak_node(proj):
    """Replay of the first close under the blind verdict: a lead session that is neither the holder nor a committer runs
    one fresh reader and writes through the command, twice (two nodes true, then one node weak). Both calls are allowed,
    and the real close then reports the weak node, not a missing or an unproven one."""
    _reader(proj, "s-lead", "a1")
    stamp = at(0).timestamp()
    os.utime(proj.root / FILE, (stamp, stamp))
    first = _add(proj, "s-lead", N1, N2, "true", "one clause, one case")
    second = _add(proj, "s-lead", N3, "weak", "the test names no case")
    assert (first.returncode, second.returncode) == (0, 0), first.stderr + second.stderr
    done = proj.owner("card", "close", CARD, check=False)
    assert done.returncode != 0
    assert f"{N3}: verdict-weak" in done.stderr
