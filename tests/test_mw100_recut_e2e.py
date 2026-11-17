"""Card MW-100 (decisions: R251, R251a, R251b), through the REAL command and the REAL hooks: one engine install per test (a
scratch git repository, the task folder below the git top), a test file committed by a builder session through the real commit
hook (dated an hour before the reader rows), the card file committed, the card released and given to the session `s-lead` as
its orderer. The command runs as a session's Bash call (the real PreToolUse hook leaves the by-permit, the real command reads
it). One deny for each new refusal id, and one allow. Synthetic names only."""
import datetime
import os
import subprocess
import sys

import pytest

from _hook_driver import install_project
from _mw019 import T0, add_agent, at
from _red_project import commit_red_first
import records

pytestmark = [pytest.mark.engine_repo, pytest.mark.xdist_group("test_mw100_recut_e2e")]

CLI = "python mkway/engine/mkway.py"
BUILDER, LEAD, READER, OTHER, LATE = "s-builder", "s-lead", "s-reader", "s-other", "s-late"
SESSIONS = (BUILDER, LEAD, READER, OTHER, LATE)
CARD = "CARD-001"
FILE = "tests/test_first.py"
CODE_FILE = "src/first.py"
N1, N2 = (f"{FILE}::test_{name}" for name in ("one", "two"))
TEST = ('from src.first import ONE\n\n\n'
        'def test_one():\n    """Catches: the first value is missing."""\n    assert ONE + 1 == 2\n\n\n'
        'def test_two():\n    """Catches: the first value is missing."""\n    assert ONE + 1 == 2\n')
CODE = "ONE = 1\n"
REASON = "the row now says LF line ends"
FRESH = {"started": 60, "ended": 120}


def _card_text(template):
    text = template.replace("| **Paths** | |", f"| **Paths** | `{FILE}`, `{CODE_FILE}` |")
    text = text.replace("«the owner's words, quoted» — owner, YYYY-MM-DD.", "A synthetic goal for the recut.")
    rows = "\n".join(f"| E{n} | the test | absent | there | {node} |" for n, node in enumerate((N1, N2), 1))
    return text.replace("| E1 | item id | value today | value after the change | tests/test_x.py::test_y |", rows)


def _git_at(p, seconds, *args):
    """A git command in the project root with author and committer dates `seconds` after T0."""
    when = at(seconds).isoformat(timespec="seconds")
    env = {**os.environ, "GIT_COMMITTER_DATE": when, "GIT_AUTHOR_DATE": when}
    subprocess.run(["git", "-c", "user.name=hook-driver", "-c", "user.email=hook-driver", "-c", "commit.gpgsign=false",
                    *args], cwd=str(p.root), check=True, capture_output=True, timeout=60, env=env)


@pytest.fixture
def proj(tmp_path):
    """A card the builder took and committed its test for through the real hooks, then released and gave to the lead."""
    p = install_project(tmp_path)
    p.profile(**{"python.command": sys.executable, "gates.trip": {"min_calls": 100000},
                 "paths.exempt": ["tests/verdicts/*.md"]})
    from _engine import agent_file
    agent_file(p.root, "fresh-reader", "Read, Grep")
    p.owner("card", "new", "Recut card")
    card_file = next((p.root / "mkway" / "cards").glob(f"{CARD}-*")) / "CARD.md"
    card_file.write_text(_card_text(card_file.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    p.owner("card", "open", CARD)
    for session in SESSIONS:
        from _hook_driver import decision
        decision(p.fire("SessionStart", session))
    p.session_shell(BUILDER, f"{CLI} card take {CARD}")
    p.write(FILE, TEST)
    p.write(CODE_FILE, CODE)
    when = at(-3600).isoformat(timespec="seconds")

    def commit(message, paths):
        p.session_shell(BUILDER, f"git commit -m '{message}'")
        if FILE in paths:
            subprocess.run(["git", "-c", "user.name=hook-driver", "-c", "user.email=hook-driver", "commit", "-q", "--amend",
                            "--no-edit", "--date", when], cwd=str(p.root), check=True, capture_output=True, timeout=60,
                           env={**os.environ, "GIT_COMMITTER_DATE": when})

    commit_red_first(p.git, lambda paths: p.session_shell(BUILDER, "git add -f -- " + " ".join(paths)), commit,
                     (f"{CARD} the tests of the command", [FILE]), (f"{CARD} the code of the tests", [CODE_FILE]))
    rel = card_file.relative_to(p.root).as_posix()
    p.git("add", "-f", "--", rel)
    _git_at(p, -3000, "commit", "-q", "-m", f"{CARD} the card")
    records.append(p.root / "mkway" / "state", BUILDER, "release", CARD)
    p.owner("card", "resync", "--add-ordered-by", check=False)
    p.owner("give", CARD, LEAD)
    for name in ("agents.jsonl", "outbox_checks.jsonl"):
        (p.root / "mkway" / "state" / name).write_text("", encoding="utf-8")
    return p


def _quoted(items):
    return " ".join(f'"{i}"' if " " in i else i for i in items)


def _add(p, session, *items):
    return p.session_shell(session, f"{CLI} verdict add {CARD} {_quoted(items)}", expect_ok=False)


def _recut(p, session=LEAD, node=N1):
    return p.session_shell(session, f"{CLI} verdict recut {CARD} {node} \"{REASON}\"", expect_ok=False)


def _weak(p, node=N1):
    """A fresh reader run (agent a1, session s-reader) and its weak verdict row through the real command."""
    add_agent(p.root, session=READER, agent_type="fresh-reader", agent_id="a1", guard=CARD, **FRESH)
    done = _add(p, READER, node, "weak", "row E1 says byte for byte, but the test replaces CRLF with LF")
    assert done.returncode == 0, done.stderr


def _change(p, seconds=130):
    """A commit that changes the test file, dated after the weak run ended (no commit hook: a plain git commit)."""
    p.write(FILE, (p.root / FILE).read_text(encoding="utf-8") + "\n# the test was reworked\n")
    p.git("add", "-f", "--", FILE)
    _git_at(p, seconds, "commit", "-q", "-m", f"{CARD} the cut changes")


def _verdict_file(p):
    path = p.root / "tests" / "verdicts" / f"{CARD}.md"
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def test_the_real_command_refuses_a_recut_with_nothing_to_answer(proj):
    """Catches: a recut of a node nobody judged, through the real command."""
    done = _recut(proj, node=N2)
    assert done.returncode != 0
    assert "verdict-recut-nothing" in done.stderr


def test_the_real_command_refuses_a_recut_with_no_change(proj):
    """Catches: a recut with no commit since the answered run ended, through the real command."""
    _weak(proj)
    done = _recut(proj)
    assert done.returncode != 0
    assert "verdict-recut-no-change" in done.stderr


def test_the_real_command_refuses_a_recut_on_a_stale_file(proj):
    """Catches: a recut over a test file that differs from HEAD, through the real command."""
    _weak(proj)
    _change(proj)
    proj.write(FILE, "def test_one():\n    assert 1 == 1\n")
    done = _recut(proj)
    assert done.returncode != 0
    assert "verdict-recut-stale" in done.stderr


def test_the_real_command_refuses_a_second_recut(proj):
    """Catches: a second recut of a node, through the real command; the text says to split or withdraw the card."""
    _weak(proj)
    _change(proj)
    assert _recut(proj).returncode == 0
    late = int((datetime.datetime.now(datetime.timezone.utc) - T0).total_seconds()) + 600
    add_agent(proj.root, session=LATE, agent_type="fresh-reader", agent_id="a-late", started=late, ended=late + 60, guard=CARD)
    assert _add(proj, LATE, N1, "weak", "still weak").returncode == 0
    _change(proj, seconds=late + 120)
    done = _recut(proj)
    assert done.returncode != 0
    assert "verdict-recut-exceeded" in done.stderr


def test_the_real_command_refuses_a_session_that_did_not_order_the_card(proj):
    """Catches: any session but the card's orderer recutting, through the real command."""
    _weak(proj)
    _change(proj)
    done = _recut(proj, session=OTHER)
    assert done.returncode != 0
    assert "verdict-recut-not-lead" in done.stderr


def test_the_real_close_refuses_a_last_row_recut(proj):
    """Catches: the real `card close` passing while the last row of a node is a recut with no fresh verdict after it."""
    _weak(proj)
    _change(proj)
    assert _recut(proj).returncode == 0
    done = proj.owner("card", "close", CARD, check=False)
    assert done.returncode != 0
    assert "verdict-recut-pending" in done.stderr


def test_the_real_command_refuses_a_run_that_started_before_the_recut(proj):
    """Catches: a reader that started after the cut changed but before the recut record judging the new cut."""
    _weak(proj)
    _change(proj)
    assert _recut(proj).returncode == 0
    add_agent(proj.root, session=OTHER, agent_type="fresh-reader", agent_id="a-early", started=150, ended=190, guard=CARD)
    done = _add(proj, OTHER, N1, "true", "the new cut reads fine")
    assert done.returncode != 0
    assert "verdict-run-before-recut" in done.stderr


def test_the_real_command_allows_the_orderers_recut(proj):
    """Checks: the nearest allow of the denies above: the orderer, a weak row, a commit after the run: exit 0 and the row written."""
    _weak(proj)
    _change(proj)
    done = _recut(proj)
    assert done.returncode == 0, done.stderr
    assert f"| {N1} | recut | answers a1: {REASON} | session:{LEAD} |" in _verdict_file(proj)
