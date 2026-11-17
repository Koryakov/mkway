"""The shell of `mkway verdict add <card> <node>... <true|weak|wrong> <reason>` (card MW-080; rulings R194, R196, R196a).

A verdict row of a card is written only by this command: no Write, Edit or MultiEdit path exists for
`tests/verdicts/<card>.md` (the pre step of the outbox gate refuses `verdict-file-by-command`), and the post step records
nothing for that file, so a row typed by hand has no proof and reads `verdict-unproven` at `card close` in every gate mode.
The command writes the table row and one record of the same shape the close check reads (`verdicts.proof_problems`): kind
`verdict-written`, `doc`, `session`, `rows` (the keys of the rows of this call), `time`, plus `agent` (the checker agent run
the call used), `run` (its number for the node, 1 or 2), `nodes` (the nodes of the call; card MW-100, R251b C: older records
have none), `tests` (the blob of each test file the verdict is about) and `acceptance_sha` ({node: sha256 of the node's
Acceptance extract, `verdicts.acceptance_extract`}; card MW-117, R287 Q4: the close recomputes it from the current card rows).

The facts (`read_facts`): the register's status of the card and its holder now; every session that ever took the card
(`records.jsonl`); the card's Acceptance nodes; the profile's `outbox.checkers`, `cards.verdicts` and
`tests.verdict_add.mode`; per node the committers of its test file (the commit gate's records), its last commit and the blob
at HEAD and now (git, never the file's mtime: ruling R196), the checker runs of the caller's session (`proof.reader_ends`)
and those that started after that last commit; per node the runs already used for it since its last recut and, for a recut
node, the readers that started after the recut record (the proof file, `verdicts.cuts`; card MW-100). The decision is the pure
`core_verdict_add.decide`. The caller is the lock gate's one-use by-permit; the owner's terminal has none and is refused.

Refusal ids of the command (documented here and in the README, as the close ids are; only `verdict-file-by-command` is a
manifest reason, of the entry `outbox_check.pre`):
  verdict-not-enforced   no `outbox.checkers`, or `cards.verdicts` off: names the key
  verdict-by-owner       the owner's terminal (refused in both modes)
  verdict-no-caller      no by-permit: the session id is not established (refused in both modes)
  verdict-by-holder      the caller ever took the card (refused in both modes)
  verdict-card-state     the card is not waiting or open (closed, proposed, waiting for the owner); a builder may hold an open
                         card (MW-117, R272 G3 supersedes R194)
  verdict-no-red-proof   the card has no red-proof row of a commit of HEAD (MW-117); the way out is the red commit of its tests.
                         MW-130: the whole history of HEAD is searched (no commit count); four true texts under this one id:
                         (i) no row, (ii) rows that no commit has, (iii) the legacy search ran out of `LEGACY_SEARCH_SECONDS`,
                         (iv) git could not read the history (way out: repeat the call)
  verdict-node-unknown   the card's Acceptance rows do not name the node
  verdict-by-committer   the caller committed the node's test file (refused in both modes)
  verdict-stale          the file is not HEAD's text (the two blob shas), or no checker run started after its last commit
                         (refused in both modes)
  verdict-no-reader-run  no checker run in the caller's session
  verdict-runs-exceeded  a third distinct reader run for a node since its last recut (at most two per node per cut)
  verdict-run-before-recut  a recut node and no run of the call started after the recut record (card MW-100, R251a point 3)
  verdict-reader-unguarded  the reader run the call uses has no record row of the allowlist hook, or its allow list was not
                         exactly the card's two inputs (card MW-116; refused in both modes)
`tests.verdict_add.mode` is `trip` or `watch` (a missing key is trip): in watch mode a refusal outside the "both modes" ones
is logged as a `would-refuse` row and the call goes ahead.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import time
from pathlib import Path
from typing import NamedTuple

import cardtool
import core_verdict_add as core
import logs
import profiles
import proof
import reader_allow
import records
import register
import shared_records
import verdicts
from core_verdicts import Row

WORDS = ("true", "weak", "wrong")
GIT_SECONDS = verdicts.GIT_SECONDS
# MW-130 (R313 4): the wall-time cap of the legacy search for a red-proof row with no git_tree, BELOW the 120 s default of a
# foreground Bash tool command (Claude Code docs, env-vars: BASH_DEFAULT_TIMEOUT_MS, default 120000), so the refusal arrives
# before the tool gives up
LEGACY_SEARCH_SECONDS = 60
_clock = time.monotonic  # the clock of that cap (a test replaces it)
HEADER = ("| Node | Verdict | Reason | By |", "|---|---|---|---|")
node_of = verdicts._node  # a node as the verdict file and the card write it


def _git(root, *args) -> str:
    """The stripped output of one git command in `root`; empty when git cannot answer."""
    try:
        done = subprocess.run(["git", "--no-optional-locks", *args], cwd=str(root), capture_output=True,
                              timeout=GIT_SECONDS)
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout.decode("utf-8", "replace").strip() if done.returncode == 0 else ""


def last_commit(root, rel: str):
    """(sha, committer time) of the last commit that touched `rel`; `("", None)` when there is none or git cannot say."""
    sha, _, when = _git(root, "log", "-1", "--format=%H %cI", "--", rel).partition(" ")
    return (sha, proof.moment(when)) if sha else ("", None)


def _since_recut(ends: list, cut):
    """None when the node was never recut; else the readers that started after the recut record (never one when its time
    cannot be read)."""
    if not cut.recuts:
        return None
    at = proof.moment(cut.time)
    return tuple(dict.fromkeys(agent for agent, began, _ended in ends if at is not None and began > at))


class RedProof(NamedTuple):
    """The answer of `red_proven`: `case` is one of the `core.RED_*` constants; `checked` the commits digested by the legacy
    search."""
    case: str
    checked: int = 0


def red_proven(root, profile, card_id: str) -> RedProof:
    """Which case of the red proof holds for the card (MW-117, R272 G3; MW-130, R313): `core.RED_PROVEN` when
    `red_proof.jsonl` of the SHARED folder (MW-129; the state folder when `state.shared_dir` is unset) holds a row of the card
    (a red id, a pin or a red-by-missing file) whose tree is in a commit of the WHOLE history of HEAD, however many commits
    followed it. A row with a `git_tree` is proven when that id is among the tree ids of the one listing; a row whose `tree`
    is a git tree id likewise; the rest by the digest, `gate_commit_tests.find_red_rows`. A row of a commit that was never made counts for nothing.
    Otherwise (i) no row, (ii) rows that no commit has, (iii) the legacy search ran out of time, (iv) git could not read the
    history: a git error is never «found». A line that is not JSON is skipped."""
    import gate_commit_tests as red
    rows = [row for row in shared_records.read_rows(root, profile, red.RED_FILE)
            if row.get("card") == card_id and isinstance(row.get("tree"), str)
            and (row.get("red") or row.get("pins") or row.get("missing"))]
    if not rows:
        return RedProof(core.RED_NO_ROW)
    # R317 4, R320: the one search is `gate_commit_tests.find_red_rows`; this command gives it the cap and its clock
    found = red.find_red_rows(root, rows, LEGACY_SEARCH_SECONDS, _clock)
    case = {red.FOUND: core.RED_PROVEN, red.NOT_IN_HISTORY: core.RED_NOT_IN_HEAD, red.OUT_OF_TIME: core.RED_OUT_OF_TIME,
            red.UNREADABLE: core.RED_UNREADABLE}[found.case]
    return RedProof(case, found.checked)


def _node(root, state, name: str, known: bool, ends: list, cut, card_text: str = "") -> core.Node:
    rel = name.partition("::")[0]
    commit, when = last_commit(root, rel)
    file_blob = _git(root, "hash-object", "--", rel) if (Path(root) / rel).is_file() else ""
    return core.Node(name, known, verdicts.committers_of(root, state, rel), commit,
                     _git(root, "rev-parse", "--verify", "-q", f"HEAD:./{rel}"), file_blob,
                     tuple(dict.fromkeys(agent for agent, _began, _ended in ends)),
                     tuple(dict.fromkeys(agent for agent, began, _ended in ends if when is not None and began > when)),
                     cut.runs, _since_recut(ends, cut), verdicts.acceptance_extract(card_text, [name]))


def took_by(state, card_id: str) -> frozenset:
    """Every session that ever took the card (`records.jsonl`), not only the holder now."""
    return frozenset(r["session_id"] for r in records.rows(state) if r.get("kind") == "take" and r.get("value") == card_id
                     and isinstance(r.get("session_id"), str) and r["session_id"])


def read_facts(root, profile, state, card_id: str, nodes, caller: str, owner: bool = False) -> core.Facts:
    """The facts of one call (see the module docstring); `card-unknown` when the register or the card file lacks the card."""
    row = register.find(register.read(root, profile), card_id)
    if row is None:
        raise cardtool.CardError(f"{card_id} is not in the register", reason="card-unknown")
    try:
        card_text = cardtool.card_file(root, profile, card_id).read_text(encoding="utf-8")
        named = set(cardtool.test_nodes(card_text))
    except OSError:
        raise cardtool.CardError(f"{card_id} has no card file", reason="card-unknown")
    checkers = profiles.outbox_settings(profile)["checkers"]
    ends = proof.reader_ends(state, caller, tuple(checkers)) if caller else []
    found = verdicts.cuts(state, card_id, list(nodes))
    guard, guard_sha = guard_facts(root, profile, state, card_id, caller, ends)
    red = red_proven(root, profile, card_id)
    return core.Facts(caller=caller or "", owner=owner, status=row.get("status", ""),
                      holder=records.holders(state, register.closed_ids(root, profile)).get(card_id, ""), ever_held=took_by(state, card_id),
                      nodes=tuple(_node(root, state, n, n in named, ends, found[n], card_text) for n in nodes),
                      checkers_missing=not checkers,
                      verdicts_off=not cardtool.verdicts_required(profile), mode=profiles.verdict_add_mode(profile),
                      red_proven=red.case == core.RED_PROVEN, red_case=red.case, red_checked=red.checked,
                      red_seconds=LEGACY_SEARCH_SECONDS, guard=guard, guard_sha=guard_sha)


def guard_facts(root, profile, state, card_id: str, caller: str, ends: list):
    """({reader run: why it is unguarded, empty when guarded}, {reader run: sha256 of the allow file it read under}) for every
    checker run of the caller's session (card MW-116, R287c): the one reader is `proof.reader_guard_problem`, the card's two
    inputs are `reader_allow.expected_inputs`. A card or session the inputs cannot be built for leaves every run unguarded."""
    if not caller or not ends:
        return {}, {}
    try:
        files, extract_sha = reader_allow.expected_inputs(root, profile, state, caller, card_id)
    except (cardtool.CardError, OSError) as exc:
        return {agent: f"the card's two inputs cannot be built ({exc}), so no run can be proved guarded"
                for agent, _began, _ended in ends}, {}
    guard, shas = {}, {}
    for agent, _began, _ended in ends:
        problem, sha = proof.reader_guard_problem(state, caller, agent, card_id, files, extract_sha)
        guard[agent] = problem or ""
        shas[agent] = sha
    return guard, shas


def clean(reason: str) -> str:
    """A reason as a table cell: a pipe becomes a slash, a line break a space (as `cardtool.append_log_row` does)."""
    return " ".join(reason.replace("|", "/").split())


def _node_of_line(line: str):
    """The node of a table row line of a verdict file (the reader's own rule: a header and a separator are no row)."""
    if not line.startswith("|") or set(line) <= set("|-: "):
        return None
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    if len(cells) < 4 or cells[0].strip("`").strip().casefold() == "node":
        return None
    return node_of(cells[0])


def put_rows(root, card_id: str, rows) -> None:
    """Write the rows into the card's verdict file: the row of the same node is replaced, else the row is appended; a new
    file gets the header the reader skips. The file keeps its own line ends; the write is a temp file, then a replace."""
    path = Path(root) / verdicts.verdict_file(card_id)
    try:
        raw = path.read_bytes().decode("utf-8")
    except FileNotFoundError:
        raw = ""
    except UnicodeDecodeError:
        raise OSError(f"{path.name} is not UTF-8 text; nothing was changed")
    eol = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.splitlines() if raw.strip() else list(HEADER)
    for row in rows:
        line = f"| {row.node} | {row.verdict} | {row.reason} | {row.by} |"
        at = [i for i, existing in enumerate(lines) if _node_of_line(existing) == row.node]
        if at:
            lines[at[-1]] = line
        else:
            lines.append(line)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes((eol.join(lines) + eol).encode("utf-8"))
    os.replace(tmp, path)


def record(state, card_id: str, caller: str, rows, verdict: core.Verdict, facts: core.Facts) -> dict:
    """Append the record of the call to the proof file: the keys of its rows, the checker run it used and its number, the
    blob of each test file the verdict is about, and the refusals watch mode let through."""
    row = {"kind": verdicts.PROOF_KIND, "doc": verdicts.verdict_file(card_id), "session": caller,
           "rows": [verdicts.row_key(r) for r in rows], "time": logs.now().isoformat(timespec="milliseconds"),
           "nodes": [n.name for n in facts.nodes], "tests": {n.name.partition("::")[0]: n.file_blob for n in facts.nodes},
           "acceptance_sha": {n.name: hashlib.sha256(n.acceptance.encode("utf-8")).hexdigest()
                              for n in facts.nodes if n.acceptance}}  # MW-117, R287 Q4: what the reader judged of the rows
    if verdict.run:
        row["agent"], row["run"] = verdict.run, verdict.number
        if facts.guard_sha.get(verdict.run):
            row["allow_sha256"] = facts.guard_sha[verdict.run]  # card MW-116: the list the run read under
    if verdict.watched:
        row["watched"] = [r.reason for r in verdict.watched]
    logs.append_jsonl(Path(state) / proof.FILE, row)
    return row


def apply(root, profile, state, card_id: str, nodes, word: str, reason: str, caller: str,
          owner: bool = False) -> core.Verdict:
    """One whole call: read the facts, decide, and when allowed write the rows and the record. Returns the verdict."""
    facts = read_facts(root, profile, state, card_id, nodes, caller, owner)
    verdict = core.decide(facts)
    if verdict.allowed:
        rows = [Row(node, word, clean(reason), f"session:{caller}") for node in nodes]
        put_rows(root, card_id, rows)
        record(state, card_id, caller, rows, verdict, facts)
    return verdict


def report(card_id: str, nodes, word: str, verdict: core.Verdict) -> list:
    """The lines a successful call prints."""
    lines = [f"{card_id} {node} {word}" for node in nodes]
    lines.append(f"reader run {verdict.number} of {core.MAX_RUNS} ({verdict.run})" if verdict.run
                 else "reader run: none established (watch mode)")
    lines.append(f"rows written to {verdicts.verdict_file(card_id)}")
    return lines
