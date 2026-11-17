"""Card MW-113, step 2 (audit G10): way-out rows through the REAL command and the REAL hooks for four verdict refusals that
only core and shell rows showed: verdict-node-unknown, verdict-no-caller, verdict-card-state, verdict-runs-exceeded. One engine
install (a scratch git repository, the task folder below the git top), a test file committed by a builder session through
the real commit hook (dated an hour before the reader rows), the card committed, released and given to `s-lead` as its
orderer. Each test is a refusal, then what the refusal text names as the fix, then the allow, through the same real command
as a session's Bash call (the real PreToolUse hook leaves the by-permit, the real command reads it). Each test starts with
empty agent and proof records and no verdict file. The last test commits a change to the test file, so it stays last in the
file (the module runs on one worker). Synthetic names only."""
import datetime
import os
import subprocess
import sys

import pytest

from _hook_driver import decision, install_project
from _mw019 import T0, add_agent, at
from _red_project import commit_red_first
import records

pytestmark = [pytest.mark.engine_repo, pytest.mark.xdist_group("test_mw113_command_e2e")]

CLI = "python mkway/engine/mkway.py"
BUILDER, LEAD, HOLDER = "s-builder", "s-lead", "s-holder"
READERS = ("s-unknown", "s-nocaller", "s-state", "s-r1", "s-r2", "s-r3", "s-r4")
SESSIONS = (BUILDER, LEAD, HOLDER) + READERS
CARD = "CARD-001"
FILE = "tests/test_first.py"
CODE_FILE = "src/first.py"
N1, N2 = (f"{FILE}::test_{name}" for name in ("one", "two"))
TEST = ('from src.first import ONE\n\n\n'
        'def test_one():\n    """Catches: the first value is missing."""\n    assert ONE + 1 == 2\n\n\n'
        'def test_two():\n    """Catches: the first value is missing."""\n    assert ONE + 1 == 2\n')
CODE = "ONE = 1\n"
FRESH = {"started": 60, "ended": 120}
REASON = "the row now says LF line ends"
GOOD = "one clause, one case"


def _card_text(template):
    text = template.replace("| **Paths** | |", f"| **Paths** | `{FILE}`, `{CODE_FILE}` |")
    text = text.replace("«the owner's words, quoted» — owner, YYYY-MM-DD.", "A synthetic goal for the way-out rows.")
    rows = "\n".join(f"| E{n} | the test | absent | there | {node} |" for n, node in enumerate((N1, N2), 1))
    return text.replace("| E1 | item id | value today | value after the change | tests/test_x.py::test_y |", rows)


def _git_at(p, seconds, *args):
    """A git command in the project root with author and committer dates `seconds` after T0."""
    when = at(seconds).isoformat(timespec="seconds")
    env = {**os.environ, "GIT_COMMITTER_DATE": when, "GIT_AUTHOR_DATE": when}
    subprocess.run(["git", "-c", "user.name=hook-driver", "-c", "user.email=hook-driver", "-c", "commit.gpgsign=false",
                    *args], cwd=str(p.root), check=True, capture_output=True, timeout=60, env=env)


@pytest.fixture(scope="module")
def proj(tmp_path_factory):
    """A card the builder took and committed its test for through the real hooks, then released and gave to the lead."""
    p = install_project(tmp_path_factory.mktemp("way-out"))
    p.profile(**{"python.command": sys.executable, "gates.trip": {"min_calls": 100000},
                 "paths.exempt": ["tests/verdicts/*.md"]})
    from _engine import agent_file
    agent_file(p.root, "fresh-reader", "Read, Grep")
    p.owner("card", "new", "Way-out card")
    card_file = next((p.root / "mkway" / "cards").glob(f"{CARD}-*")) / "CARD.md"
    card_file.write_text(_card_text(card_file.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    p.owner("card", "open", CARD)
    for session in SESSIONS:
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
                     (f"{CARD} the tests of the way-out rows", [FILE]), (f"{CARD} the code of the tests", [CODE_FILE]))
    rel = card_file.relative_to(p.root).as_posix()
    p.git("add", "-f", "--", rel)
    _git_at(p, -3000, "commit", "-q", "-m", f"{CARD} the card")
    records.append(p.root / "mkway" / "state", BUILDER, "release", CARD)
    p.owner("card", "resync", "--add-ordered-by", check=False)
    p.owner("give", CARD, LEAD)
    return p


@pytest.fixture(autouse=True)
def _empty_records(proj):
    """Each test starts with no agent rows, no proof records and no verdict file."""
    for name in ("agents.jsonl", "outbox_checks.jsonl"):
        (proj.root / "mkway" / "state" / name).write_text("", encoding="utf-8")
    for old in (proj.root / "tests" / "verdicts").glob("*.md"):
        old.unlink()
    yield


def _set_status(p, status):
    """The register row of the card in `status` (a proposed card is what the way-out row starts from)."""
    import json
    import register
    profile = json.loads((p.root / "mkway" / "profile.json").read_text(encoding="utf-8"))

    def mutate(table):
        register.find(table, CARD)["status"] = status
        return table
    register.write(p.root, profile, mutate)


def _quoted(items):
    return " ".join(f'"{i}"' if " " in i else i for i in items)


def _command(*items):
    return f"{CLI} verdict add {CARD} {_quoted(items)}"


def _add(p, session, *items):
    return p.session_shell(session, _command(*items), expect_ok=False)


def _reader(p, session, agent_id, **times):
    add_agent(p.root, session=session, agent_type="fresh-reader", agent_id=agent_id, guard=CARD, **(times or FRESH))


def _verdict_file(p):
    path = p.root / "tests" / "verdicts" / f"{CARD}.md"
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def test_the_way_out_of_verdict_node_unknown_is_a_node_the_card_names(proj):
    """Checks: through the real command a node the card's Acceptance rows do not name is refused verdict-node-unknown;
    a node the card names, from the same session, writes the row."""
    _reader(proj, "s-unknown", "a1")
    refused = _add(proj, "s-unknown", f"{FILE}::test_nope", "true", GOOD)
    assert (refused.returncode != 0, "verdict-node-unknown" in refused.stderr) == (True, True)
    allowed = _add(proj, "s-unknown", N1, "true", GOOD)
    assert allowed.returncode == 0, allowed.stderr
    assert f"| {N1} | true | {GOOD} | session:s-unknown |" in _verdict_file(proj)


def test_the_way_out_of_verdict_no_caller_is_the_plain_form_in_a_session_with_the_hooks(proj):
    """Checks: the command run with no hook check before it (no by-permit) is refused verdict-no-caller; the same command
    in its plain form as a session's Bash call, with the engine hooks, writes the row."""
    _reader(proj, "s-nocaller", "a1")
    bare = subprocess.run([proj.bash, "-c", _command(N1, "true", GOOD)], capture_output=True, text=True,
                          encoding="utf-8", cwd=str(proj.root), env=proj.env(session=True), timeout=120)
    assert (bare.returncode != 0, "verdict-no-caller" in bare.stderr) == (True, True)
    allowed = _add(proj, "s-nocaller", N1, "true", GOOD)
    assert allowed.returncode == 0, allowed.stderr
    assert f"| {N1} | true | {GOOD} | session:s-nocaller |" in _verdict_file(proj)


def test_the_way_out_of_verdict_card_state_is_opening_a_proposed_card(proj):
    """Checks: MW117-D1, a proposed card is refused verdict-card-state; once the owner opens the card the same call writes the
    row (a builder may hold the open card: R272 G3)."""
    _set_status(proj, "proposed")
    _reader(proj, "s-state", "a1")
    refused = _add(proj, "s-state", N1, "true", GOOD)
    assert (refused.returncode != 0, "verdict-card-state" in refused.stderr) == (True, True)
    _set_status(proj, "open")
    proj.session_shell(HOLDER, f"{CLI} card take {CARD}")
    allowed = _add(proj, "s-state", N1, "true", GOOD)
    proj.session_shell(HOLDER, f"{CLI} card release {CARD}")
    assert allowed.returncode == 0, allowed.stderr
    assert f"| {N1} | true | {GOOD} | session:s-state |" in _verdict_file(proj)


def test_the_way_out_of_verdict_runs_exceeded_is_a_recut_then_a_fresh_reader(proj):
    """Checks: two reader runs call a node weak and a third run is refused verdict-runs-exceeded; the orderer changes the
    test, commits, runs `verdict recut` as the text says, and a fresh reader that started after the recut writes the row.
    Last in the file: it commits a change to the test file."""
    for session, agent in (("s-r1", "a1"), ("s-r2", "a2")):
        _reader(proj, session, agent)
        done = _add(proj, session, N1, "weak", "row E1 says byte for byte, but the test replaces CRLF with LF")
        assert done.returncode == 0, done.stderr
    _reader(proj, "s-r3", "a3")
    refused = _add(proj, "s-r3", N1, "weak", "still weak")
    assert (refused.returncode != 0, "verdict-runs-exceeded" in refused.stderr) == (True, True)
    proj.write(FILE, (proj.root / FILE).read_text(encoding="utf-8") + "\n# the test was reworked\n")
    proj.git("add", "-f", "--", FILE)
    _git_at(proj, 130, "commit", "-q", "-m", f"{CARD} the cut changes")
    recut = proj.session_shell(LEAD, f'{CLI} verdict recut {CARD} {N1} "{REASON}"', expect_ok=False)
    assert recut.returncode == 0, recut.stderr
    late = int((datetime.datetime.now(datetime.timezone.utc) - T0).total_seconds()) + 600
    _reader(proj, "s-r4", "a4", started=late, ended=late + 60)
    allowed = _add(proj, "s-r4", N1, "true", "the new cut reads fine")
    assert allowed.returncode == 0, allowed.stderr
    assert f"| {N1} | true | the new cut reads fine | session:s-r4 |" in _verdict_file(proj)
