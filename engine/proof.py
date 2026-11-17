"""The one reader of the fresh-reader proof (card MW-068, ruling R173 item 2): `fresh_reader_problem`.

A check or a verdict counts only when the session that wrote it ran a fresh reader first: an agent of a checker type that
started after the document's last change and ended after it and before the write was recorded (the start and end rows of
`agents.jsonl`, written by the agent hooks). The outbox (`outbox.inspect`, a check file beside a document) and the verdict
check at card close (`verdicts.proof_problems`, a verdict row beside a test file) both call this function: no copy of the read.
`reader_ends` is that read of the checker runs; `mkway verdict add` (card MW-080) uses it with the time of the last commit of
the test file in place of the file's mtime (ruling R196). The close-time check of a verdict row (card MW-101) uses
`reader_ends` for the record's own agent and judges the node's meaning from git, not the file's mtime.

`FILE` is the state-folder file the records of the proof go to: the post step of the outbox gate records the write of a check
file (`outbox`); the command `mkway verdict add` records the verdict rows it wrote (`verdict_add`; the Write path records no
verdict file since MW-080). The reader here reads `agents.jsonl` only.
"""
from __future__ import annotations

import datetime
import os
from pathlib import Path
from typing import Optional

import agents

NEVER = datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)  # a `changed` time before every run (card MW-101)
FILE = "outbox_checks.jsonl"  # the post step's records of the writes of check files and verdict files


def moment(value) -> Optional[datetime.datetime]:
    try:
        found = datetime.datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return found if found.tzinfo else found.replace(tzinfo=datetime.timezone.utc)


def mtime(path) -> datetime.datetime:
    return datetime.datetime.fromtimestamp(Path(path).stat().st_mtime, tz=datetime.timezone.utc)


def reader_ends(state, session, checkers) -> list:
    """The end rows of `agents.jsonl` of agents of a checker type (a name in `checkers`) in `session`, as
    `(agent id, started, ended)` with both times parsed, in order of their end; a row with no readable start or end is left
    out. The one read of the checker runs: the outbox, the close check and `mkway verdict add` (card MW-080) all use it."""
    found = []
    for entry in agents.rows(state):
        if entry.get("kind") != "end" or entry.get("session_id") != session or entry.get("agent_type") not in checkers:
            continue
        began, ended = moment(entry.get("started")), moment(entry.get("ended"))
        if began is not None and ended is not None:
            found.append((entry.get("agent_id"), began, ended))
    return sorted(found, key=lambda item: item[2])


def fresh_reader_problem(state, doc, session, written, checker: str, changed=None, agent=None) -> Optional[str]:
    """None when an agent of type `checker` ran in `session`, started after the last change of the document `doc` and ended
    after it and before the write (`written`, the time text of the record of the write); else the problem. `state` is the
    state folder that holds `agents.jsonl`. `changed` (card MW-101) is the time of the last change when the caller knows it
    from elsewhere; by default it is the mtime of `doc` (the outbox's use, unchanged). `agent` (card MW-101) limits the runs
    that count to the agent with that id; by default every agent of the type counts."""
    written_at = moment(written)
    if not isinstance(session, str) or session in ("", agents.NE) or written_at is None:
        return "the record of the check's write names no session or no time: write the check again with a write tool"
    changed = mtime(doc) if changed is None else changed
    for found, began, ended in reader_ends(state, session, (checker,)):
        if (agent is None or found == agent) and began > changed and changed < ended < written_at:
            return None
    return (f"no agent of type `{checker}` started and ended in session {session} after the last change of the "
            f"document and before the check was written (a start and an end row in agents.jsonl): run a fresh reader "
            f"of that type on the file as it is now, then write the check")


GUARD_TOOLS = ("Read", "Grep")


def _norm(path) -> str:
    return os.path.normcase(os.path.normpath(str(path)))


def reader_guard_problem(state, session, agent, card_id, expected_files, extract_sha):
    """(problem, allow sha): None and the sha256 of the allow file when the reader run `agent` of `session` is guarded for the
    card `card_id` (card MW-116, R287c): it has at least one record row of the allowlist hook with an allowed Read or Grep,
    every such row carries the same allow sha, a start row of the same session holds that sha for this card, and the list
    that start row names is exactly `expected_files` (the card's two inputs now) with the extract of `extract_sha`. Else the
    problem as text and an empty sha. The one reader of the guard records: `verdict add` calls it."""
    rows = agents.reader_rows(state)
    calls = [r for r in rows if r.get("kind") == "call" and r.get("session_id") == session and r.get("agent_id") == agent
             and r.get("decision") == "allow" and r.get("tool") in GUARD_TOOLS]
    cure = ("trust the folder of the agent file (the workspace trust dialog), run `mkway reader start <card>`, run a fresh "
            "reader, then call again")
    if not calls:
        return (f"no record row of the allowlist hook for the reader run {agent or 'none'} in session {session or 'none'} "
                f"(the frontmatter hook did not run, or the reader read nothing it was allowed to): {cure}"), ""
    shas = {r.get("allow_sha256") for r in calls}
    sha = next(iter(shas))
    if len(shas) != 1 or not sha:
        return f"the record rows of the reader run {agent} name more than one allow file, or none: {cure}", ""
    starts = [r for r in rows if r.get("kind") == "start" and r.get("session_id") == session and r.get("allow_sha256") == sha]
    if not starts:
        return f"no start row of `mkway reader start` holds the allow file {sha[:12]} the run {agent} read under: {cure}", ""
    start = starts[-1]
    if start.get("card") != card_id:
        return (f"the allow file of the run {agent} was started for {start.get('card') or 'no card'}, not for {card_id}: "
                f"{cure}"), ""
    listed = {_norm(f): str(f) for f in start.get("files") or []}
    wanted = {_norm(f): str(f) for f in expected_files}
    if listed.keys() != wanted.keys():
        extra = sorted(listed[k] for k in listed.keys() - wanted.keys())
        missing = sorted(wanted[k] for k in wanted.keys() - listed.keys())
        return (f"the allow file of the run {agent} did not list exactly the card's two inputs (the test files of its nodes "
                f"and the extract): extra {', '.join(extra) or 'none'}; missing {', '.join(missing) or 'none'}: {cure}"), ""
    if start.get("extract_sha256") != extract_sha:
        return (f"the extract the run {agent} read is not the Acceptance rows of the card as they are now (the card changed "
                f"after `mkway reader start`): {cure}"), ""
    return None, sha
