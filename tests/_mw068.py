"""Shared helpers for the MW-068 proof tests (ruling R173 item 2): what a real reader leaves behind. Not a test module.
Synthetic sessions only.

A verdict row counts only with its proof: a record of the engine command `verdict add` for the row (decision: R196; the
Write path leaves none) and a fresh reader agent of a checker type after the test file's last change and before that
record (`agents.jsonl`). `prove` leaves both: the agent rows at `_mw019.T0` plus 60 and 120 seconds, the test file's last
change at `T0`, and the record, in the shape the command writes, at the real time now."""
import os
import subprocess
from pathlib import Path

from _engine import REPO, gate_call
from _mw019 import add_agent, at
import core_verdicts
import logs
import proof
import verdicts

CHECKER = "critic"
GIT_ENV = {"GIT_AUTHOR_NAME": "mkway-test", "GIT_AUTHOR_EMAIL": "mkway-test", "GIT_COMMITTER_NAME": "mkway-test",
           "GIT_COMMITTER_EMAIL": "mkway-test"}


def _git(root, *args):
    return subprocess.run(["git", "-c", "commit.gpgsign=false", *args], cwd=str(root), capture_output=True, text=True,
                          env={**os.environ, **GIT_ENV}, timeout=20)


def head_blobs(root, files) -> dict:
    """{file: blob sha at HEAD} for the test `files`, as the engine command records them (card MW-101: the close reads the
    blob from git, never the file's mtime). A root with no git of its own is made one, and a file that HEAD does not hold as
    it is now is committed, so the blob is the one `verdict add` would have seen."""
    top = _git(root, "rev-parse", "--show-toplevel")
    if top.returncode != 0 or Path(top.stdout.strip()).resolve() == REPO.resolve():  # no repo of its own: not the engine's
        _git(root, "init", "-q")
    out = {}
    for rel in files:
        _git(root, "add", "-f", "--", rel)
        if _git(root, "diff", "--cached", "--quiet", "--", rel).returncode != 0:
            _git(root, "commit", "-q", "-m", f"the test file {rel}")
        out[rel] = _git(root, "rev-parse", f"HEAD:./{rel}").stdout.strip()
    return out


def old(path) -> None:
    """The test file's last change: `T0`, before any agent row of the default case."""
    stamp = at(0).timestamp()
    os.utime(path, (stamp, stamp))


def post(root, rel: str, session: str):
    """The post step of the outbox gate on a Write of `rel` by `session`, through the context the dispatcher builds."""
    import gate_outbox
    return gate_call(gate_outbox.check, root, tool="Write", event="PostToolUse", session=session,
                     tool_input={"file_path": rel, "content": "x"}, tool_response={"filePath": rel, "success": True})


def record(root, rel: str, session: str, agent=None):
    """The record the engine command leaves in the proof file for the verdict file `rel` (decision: R196): a
    `verdict-written` row with the keys of the rows whose reader is `session`, the time now and the run number. Written
    here directly, as the Write path no longer records a verdict write."""
    state = Path(root) / "mkway" / "state"
    card_id, who = verdicts.card_of_file(rel), core_verdicts.who(session)
    keys = [verdicts.row_key(r) for r in verdicts.rows_of(root, card_id) if who and core_verdicts.who(r.by) == who]
    files = sorted({r.node.partition("::")[0] for r in verdicts.rows_of(root, card_id) if who and core_verdicts.who(r.by) == who})
    row = {"kind": verdicts.PROOF_KIND, "doc": rel, "session": session, "rows": keys,
           "time": logs.now().isoformat(timespec="milliseconds"), "tests": head_blobs(root, files)}
    if keys:
        runs = tuple(dict.fromkeys(core_verdicts.who(str(r.get("session"))) for r in verdicts._proof_rows(state, card_id)
                                   if r.get("rows")))  # the reader sessions that wrote rows, in order (R251b: the count of runs moved)
        row["run"] = (runs.index(who) if who in runs else len(runs)) + 1
    if agent:
        row["agent"] = agent  # R251b: only a record with an `agent` key is a reader run
    logs.append_jsonl(state / proof.FILE, row)
    return row


def prove(root, card_id: str, test_file: str, session: str, *, agent_type: str = CHECKER, agent: bool = True):
    """The proof of `session` for the verdict file of `card_id`: a fresh reader agent in the session (when `agent`) and the
    command's record of its rows. The verdict file and the test file must exist."""
    old(Path(root) / test_file)
    if agent:
        add_agent(root, session=session, agent_type=agent_type, agent_id=f"agent-{session}")
    return record(root, f"tests/verdicts/{card_id}.md", session, f"agent-{session}" if agent else None)
