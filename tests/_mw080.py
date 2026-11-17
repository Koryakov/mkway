"""Shared helpers for the MW-080 tests (a verdict row is written only by the engine command). Not a test module. Synthetic
sessions, agents, files and names only.

`make_root` builds a real small git repository that is also a task root: the test files committed at `COMMIT_AT` (an hour
before `_mw019.T0`), a card `CARD-001` whose Acceptance rows name the nodes, the card's register status. A reader run is an
end row of `agents.jsonl`: fresh (started at T0 plus 60 s, after the commit) or old (before the commit)."""
import json
import os
import subprocess
from pathlib import Path

from _engine import cli, task_root  # first: it puts the engine folder on the path
from _mw019 import T0, add_agent, at, iso  # noqa: F401
import cardtool
import logs
import records
import register
import verdicts

CARD = "CARD-001"
CHECKER = "fresh-reader"
FILE, OTHER_FILE = "tests/test_a.py", "tests/test_b.py"
N1, N2, N3 = (f"{FILE}::test_{name}" for name in ("one", "two", "three"))
B1 = f"{OTHER_FILE}::test_b"
SRC = "def test_one():\n    assert True\n\n\ndef test_two():\n    assert True\n\n\ndef test_three():\n    assert True\n"
SRC_B = "def test_b():\n    assert True\n"
COMMIT_AT = -3600  # seconds after T0: the test files are committed before every fresh reader run
FRESH = {"started": 60, "ended": 120}
OLD = {"started": -7200, "ended": -7100}
PROOF = "outbox_checks.jsonl"
VERDICT_REL = f"tests/verdicts/{CARD}.md"


def git(root, *args, when=None):
    """A git command in `root`; `when` (seconds after T0) fixes the author and committer dates."""
    env = dict(os.environ)
    env.update(GIT_AUTHOR_NAME="mkway-test", GIT_AUTHOR_EMAIL="mkway-test", GIT_COMMITTER_NAME="mkway-test",
               GIT_COMMITTER_EMAIL="mkway-test")
    if when is not None:
        env.update(GIT_AUTHOR_DATE=at(when).isoformat(timespec="seconds"),
                   GIT_COMMITTER_DATE=at(when).isoformat(timespec="seconds"))
    done = subprocess.run(["git", "-c", "commit.gpgsign=false", *args], cwd=str(root), check=True, capture_output=True,
                          text=True, env=env, timeout=20)
    return done.stdout.strip()


def profile_of(root) -> dict:
    return json.loads((Path(root) / "mkway" / "profile.json").read_text(encoding="utf-8"))


def state_of(root) -> Path:
    return Path(root) / "mkway" / "state"


def make_root(tmp_path, *, status="waiting", mode=None, checkers=(CHECKER,), verdicts_off=False, name="vroot", red=True):
    """A git task root with the two test files committed, the card CARD-001 naming N1, N2, N3 and B1, in `status`. MW-117:
    `red` seeds the card's red-proof row (the red commit is made); `red=False` leaves none."""
    over = {"outbox": {"checkers": list(checkers)}}
    if mode:
        over["tests"] = {"verdict_add": {"mode": mode}}
    if verdicts_off:
        over["cards"] = {"verdicts": "off"}
    root = task_root(tmp_path, vcs="git", name=name, **over)
    (root / "mkway" / ".gitignore").write_text("engine/\nlocks/\nstate/\n", encoding="utf-8")
    git(root, "init", "-q")
    (root / "tests").mkdir()
    (root / FILE).write_text(SRC, encoding="utf-8")
    (root / OTHER_FILE).write_text(SRC_B, encoding="utf-8")
    git(root, "add", "-f", "--", FILE, OTHER_FILE)
    git(root, "commit", "-q", "-m", f"{CARD} add the tests", when=COMMIT_AT)
    if red:
        seed_red(root)
    assert cli(root, "card", "new", "First", session=True)[0] == 0
    profile = profile_of(root)
    rows = "".join(f"| E{n} | item | was | must | {node} |\n" for n, node in enumerate((N1, N2, N3, B1), 1))
    text = ("# CARD-001: First\n\n## Acceptance examples\n\n| # | Item | Was | Must be | Test |\n|---|---|---|---|---|\n"
            + rows + "\n## 8. Log\n\n| Date | Step | Commit | Result |\n|---|---|---|---|\n")
    cardtool.card_file(root, profile, CARD).write_text(text, encoding="utf-8")

    def mutate(table):
        register.find(table, CARD)["status"] = status
        return table
    register.write(root, profile, mutate)
    return root


def seed_red(root):
    """MW-117 (R271c, MW117-D1): the red-proof row of CARD-001 for the tests committed at HEAD (a precondition of a verdict,
    never the subject of the test that calls it)."""
    from _red_project import seed_record_at
    seed_record_at(root, CARD, lambda *args: git(root, *args))


def lose_card_file(root):
    """The card's register row points to a folder that holds no card file."""
    profile = profile_of(root)

    def mutate(table):
        register.find(table, CARD)["folder"] = "mkway/cards/nowhere"
        return table
    register.write(root, profile, mutate)


def reader(root, session, agent_id, *, fresh=True, agent_type=CHECKER):
    """One checker end row of `session`: fresh (after the last commit of the test files) or old (before it)."""
    add_agent(root, session=session, agent_type=agent_type, agent_id=agent_id, **(FRESH if fresh else OLD))
    if agent_type == CHECKER:  # MW116-D1: a checker run is a guarded run (setup only)
        from _mw116 import guarded
        guarded(root, session, agent_id)


def took(root, session, *, release=False):
    """A take row of CARD-001 by `session`, then its release row when `release`."""
    records.append(state_of(root), session, "take", CARD)
    if release:
        records.append(state_of(root), session, "release", CARD)


def old(root, rel=FILE):
    """The test file's mtime at T0, before every fresh reader run (the close check reads it)."""
    stamp = T0.timestamp()
    os.utime(Path(root) / rel, (stamp, stamp))


def read(root, caller, nodes, *, owner=False):
    """The facts the shell reads for a call of `caller` on `nodes` of CARD-001."""
    import verdict_add  # late: a test that needs no part of it fails for its own reason, not for this import
    return verdict_add.read_facts(root, profile_of(root), state_of(root), CARD, list(nodes), caller, owner)


def apply(root, caller, nodes, word="true", reason="one clause, one case", *, owner=False):
    """The whole call in process: facts, decision, and the writes when allowed. Returns the verdict."""
    import verdict_add
    return verdict_add.apply(root, profile_of(root), state_of(root), CARD, list(nodes), word, reason, caller, owner)


def verdict_text(root) -> str:
    path = Path(root) / VERDICT_REL
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def proof_rows(root) -> list:
    path = state_of(root) / PROOF
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def written(root) -> list:
    """The `verdict-written` records of the proof file."""
    return [r for r in proof_rows(root) if r.get("kind") == verdicts.PROOF_KIND]


def record(root, doc, agent, session="reader"):
    """A `verdict-written` record of the proof file for the verdict file `doc`, naming the agent run `agent`."""
    logs.append_jsonl(state_of(root) / PROOF, {"kind": "verdict-written", "doc": doc, "session": session, "rows": ["k"],
                                               "agent": agent})


def refusal_rows(root) -> list:
    path = state_of(root) / logs.REFUSALS
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def permit(root, session):
    """What the lock gate leaves before a session's `verdict add`: the one-use by-permit that names the session."""
    assert cardtool.issue_by_permit(state_of(root), session)


def run_cli(root, *args, session=True, caller=None):
    """`mkway <args>` in process; a session's call carries the by-permit of `caller` when one is named."""
    if session and caller:
        permit(root, caller)
    return cli(root, *args, session=session)
