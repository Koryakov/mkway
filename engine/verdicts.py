"""The shell of the close-time verdict check (card MW-068): it reads the facts, `core_verdicts.decide` judges them.

- The verdict file of a card is `tests/verdicts/<card id>.md`: a table, one row per test node an Acceptance row names,
  `node | verdict | reason | by` (verdict true, weak or wrong; by the reader's caller id in the MW-049 form, `session:<id>`).
- The holder is the session `records.holders` gives for the card (the caller passes it); empty when nobody holds it.
- The authors of a test file are the names `git log --format=%an` gives for it in the task root. The engine keeps no
  record of which session wrote a file (its records hold card moves and sessions only), so git is the one source; with no
  git, or a file git does not know, the authors are none (nothing to compare: not established, never guessed).
- A configured checker (`outbox.checkers`) must be a read-only reader (card MW-071, ruling R180): its agent definition is
  `<task root>/.claude/agents/<name>.md`, else `<user folder>/.claude/agents/<name>.md` (the user folder from the
  environment, `Path.home()`); the `tools:` line of its frontmatter is read, `core_verdicts.decide` judges it.
- A recut (card MW-100, `engine/verdict_recut.py`) leaves a record of kind `verdict-recut` in the same proof file. The reader
  runs of a node are counted from the records of kind `verdict-written` that carry an `agent` key, per node, since the node's
  last recut record (`cuts`); a record counts for the nodes it names (`nodes`), else for the nodes of the files in its
  `tests`, else for every node of the card. A `recut` row is proved by its recut record; a true row must be later in the proof
  file than the node's last recut record (`before_recut`).
- Freshness at close (card MW-101, R196, R253): a row proven by `verdict add` stays fresh while its node's meaning is unchanged,
  read from git, never from a file's mtime. The record's own `agent` must have an end row of a checker type in the record's
  session before the record's time (`_reader_problem`); the node's own source and the non-test code of its file must equal
  those of the blob the record holds (`_meaning_problem`, the pure `core_node_fresh`); any other test function of the file may
  differ. A stale or unreadable row reads `verdict-unproven` (the same id), the cure a fresh reader and `verdict add`. Named
  gap: cross-file helpers (`tests/_*.py` kits, `conftest.py`) are not read.
- The check runs at every `card close` (the owner's and the orderer's) on a card whose Acceptance rows name a test node;
  `cards.verdicts: off` in the profile skips it.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import NamedTuple, Optional

import core_node_fresh
import core_verdicts
import logs
import profiles
import proof
from core_verdicts import Checker, Facts, Row

VERDICT_DIR = "tests/verdicts"
PROOF_KIND = "verdict-written"  # the post step's row for a write of a verdict file (ruling R173 item 2)
RECUT_KIND = "verdict-recut"  # the recut command's record (card MW-100, R251b B)
COMMIT_RECORDS = "commit_records.jsonl"  # the commit gate's rows (`core.COMMIT_RECORDS`; MW-068, R173 item 1)
GIT_SECONDS = 20
BLOB = re.compile(r"[0-9a-fA-F]{4,64}\Z")  # a git object name; anything else never reaches git (an option word)


def verdict_file(card_id: str) -> str:
    return f"{VERDICT_DIR}/{card_id}.md"


def _node(text: str) -> str:
    """A node id as the card writes it: backticks and spaces off, `\\` to `/`, a leading `./` or `/` off."""
    value = text.strip().strip("`").strip().replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    return value.lstrip("/")


def rows_of(root, card_id: str) -> list:
    """The rows of the card's verdict file, in file order; the header and the separator are skipped; [] with no file."""
    try:
        text = (Path(root) / verdict_file(card_id)).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    return parse_rows(text)


def parse_rows(text: str) -> list:
    """The rows of a verdict file's text, in file order; the header and the separator are skipped (card MW-102: the commit
    gate parses the staged blob or the working file, not only the file of the root). Pure."""
    rows = []
    for line in text.splitlines():
        if not line.startswith("|") or set(line) <= set("|-: "):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4 or cells[0].strip("`").strip().casefold() == "node":
            continue
        rows.append(Row(_node(cells[0]), cells[1].strip("`").strip().casefold(), cells[2], cells[3].strip("`").strip()))
    return rows


def authors_of(root, rel: str) -> frozenset:
    """Every name `git log --format=%an` gives for the file `rel` of the root; none when git cannot answer."""
    try:
        done = subprocess.run(["git", "--no-optional-locks", "log", "--format=%an", "--", rel], cwd=str(root),
                              capture_output=True, timeout=GIT_SECONDS)
    except (OSError, subprocess.SubprocessError):
        return frozenset()
    if done.returncode != 0:
        return frozenset()
    return frozenset(n.strip() for n in done.stdout.decode("utf-8", "replace").splitlines() if n.strip())


def _records(state) -> list:
    """The rows of `<state>/commit_records.jsonl` (the commit gate's records, MW-068); [] with no file."""
    try:
        text = (Path(state) / COMMIT_RECORDS).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    out = []
    for line in text.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("kind") == "commit":
            out.append(row)
    return out


def _trees_of(root, rel: str) -> frozenset:
    """The git tree ids of the commits that changed the file `rel` of the root (`git log --format=%T`); none when git
    cannot answer."""
    try:
        done = subprocess.run(["git", "--no-optional-locks", "log", "--format=%T", "--", rel], cwd=str(root),
                              capture_output=True, timeout=GIT_SECONDS)
    except (OSError, subprocess.SubprocessError):
        return frozenset()
    if done.returncode != 0:
        return frozenset()
    return frozenset(t.strip() for t in done.stdout.decode("utf-8", "replace").splitlines() if t.strip())


def committers_of(root, state, rel: str) -> frozenset:
    """The sessions that committed the file `rel` of the root (ruling R173 item 1): the session of every commit record
    whose tree sha is the tree of a commit that changed the file and whose paths hold the file. Matched by the tree sha,
    never by an author name. A file no record names (every legacy test) has none: the holder check alone judges it."""
    trees = _trees_of(root, rel)
    if not trees:
        return frozenset()
    return frozenset(r["session"].strip() for r in _records(state)
                     if r.get("tree") in trees and rel in (r.get("paths") or []) and isinstance(r.get("session"), str)
                     and r["session"].strip())


def is_verdict_file(rel: str) -> bool:
    """True for `tests/verdicts/<card id>.md` (a path from the task root, posix form)."""
    head, _, tail = (rel or "").partition(VERDICT_DIR + "/")
    return head == "" and tail.endswith(".md") and "/" not in tail and len(tail) > 3


def card_of_file(rel: str) -> str:
    """The card id a verdict file belongs to (its name without `.md`)."""
    return rel[len(VERDICT_DIR) + 1:-3]


def row_key(row: Row) -> str:
    """What a proof row holds for one verdict row: the digest of its node, verdict, reason and reader, the reader compared
    as the core compares it (case, spaces and the `session:` prefix ignored)."""
    text = "\x1f".join([row.node, row.verdict.strip().casefold(), row.reason.strip(), core_verdicts.who(row.by)])
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Cut(NamedTuple):
    """One node since the start of the card: its reader agent runs since its last recut, the recuts so far, the position of
    the last recut record in the proof file (-1: none) and its time text."""
    runs: tuple
    recuts: int
    pos: int
    time: str


def _counted(row: dict, nodes) -> list:
    """The nodes of `nodes` an add record counts for (R251b C): the nodes it names, else the nodes of the files in its
    `tests`, else every node."""
    named, tests = row.get("nodes"), row.get("tests")
    if isinstance(named, list):
        wanted = {_node(str(n)) for n in named}
        return [n for n in nodes if n in wanted]
    if isinstance(tests, dict):
        return [n for n in nodes if n.partition("::")[0] in tests]
    return list(nodes)


def cuts(state, card_id: str, nodes) -> dict:
    """{node: Cut} for `nodes`, from the proof records of the card in file order. A record counts as a reader run only with
    an `agent` key; a recut record is never a run, it ends the count of its node and starts the next cut."""
    runs = {n: [] for n in nodes}
    recuts, pos, when = dict.fromkeys(nodes, 0), dict.fromkeys(nodes, -1), dict.fromkeys(nodes, "")
    for row in _card_records(state, card_id):
        if row.get("kind") == RECUT_KIND:
            node = _node(str(row.get("node") or ""))
            if node in runs:
                runs[node], recuts[node], pos[node], when[node] = [], recuts[node] + 1, row["_pos"], str(row.get("time") or "")
            continue
        agent = row.get("agent")
        if isinstance(agent, str) and agent:
            for node in _counted(row, nodes):
                if agent not in runs[node]:
                    runs[node].append(agent)
    return {n: Cut(tuple(runs[n]), recuts[n], pos[n], when[n]) for n in nodes}


def changed_nodes(root, card_id: str, nodes):
    """The nodes whose test function is new or changed in the commits whose message names the card (ruling R181), as a
    frozenset; None when git cannot say (no git, or no commit names the card): then every named node needs a row. A node
    git cannot follow (the function is not found) counts as changed."""
    pattern = f"{card_id}([^0-9A-Za-z]|$)"
    try:
        done = subprocess.run(["git", "--no-optional-locks", "log", "--format=%H", "-E", f"--grep={pattern}"],
                              cwd=str(root), capture_output=True, timeout=GIT_SECONDS)
    except (OSError, subprocess.SubprocessError):
        return None
    commits = done.stdout.decode("utf-8", "replace").split() if done.returncode == 0 else []
    if not commits:
        return None
    return frozenset(n for n in nodes if any(_function_changed(root, sha, n) for sha in commits))


def _show(root, rev: str, rel: str):
    """The text of the file `rel` (from the root) at `rev`; None when git has no such file there."""
    try:
        done = subprocess.run(["git", "--no-optional-locks", "show", f"{rev}:./{rel}"], cwd=str(root),
                              capture_output=True, timeout=GIT_SECONDS)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.decode("utf-8", "replace") if done.returncode == 0 else None


def _function_source(text, name: str):
    """The source of the first function `name` in the Python text (decorators included); None when absent."""
    import ast
    tree = ast.parse(text)
    for item in ast.walk(tree):
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == name:
            first = min([item.lineno] + [d.lineno for d in item.decorator_list])
            return "\n".join(text.splitlines()[first - 1:item.end_lineno])
    return None


def _function_changed(root, sha: str, node: str) -> bool:
    """True when the test function of `node` is new or different in commit `sha` against its parent; True too when the
    text cannot be read or parsed (never guessed as unchanged)."""
    file, _, name = node.partition("::")
    name = name.rpartition("::")[2].partition("[")[0]
    after = _show(root, sha, file)
    if after is None:
        return False  # the commit has no such file: it did not add or change the test
    before = _show(root, f"{sha}^", file)
    try:
        now = _function_source(after, name)
        return now is not None and now != (None if before is None else _function_source(before, name))
    except (SyntaxError, ValueError):
        return True


def _card_records(state, card_id: str) -> list:
    """The records of the card's verdict file in the proof file, in file order (kinds `verdict-written` and `verdict-recut`),
    each with its line number as `_pos`."""
    path = Path(state) / proof.FILE
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    out = []
    for pos, line in enumerate(text.splitlines()):
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("kind") in (PROOF_KIND, RECUT_KIND) and row.get("doc") == verdict_file(card_id):
            row["_pos"] = pos
            out.append(row)
    return out


def _proof_rows(state, card_id: str) -> list:
    return [r for r in _card_records(state, card_id) if r.get("kind") == PROOF_KIND]


def _recut_rows(state, card_id: str) -> list:
    return [r for r in _card_records(state, card_id) if r.get("kind") == RECUT_KIND]


def _mine(row: Row, written: list) -> list:
    """The add records of the row's own reader session that hold the row's key."""
    who, key = core_verdicts.who(row.by), row_key(row)
    return [r for r in written if who and key in (r.get("rows") or []) and core_verdicts.who(str(r.get("session"))) == who]


def acceptance_extract(card_text: str, nodes) -> str:
    """The Acceptance rows of a card that name any of `nodes`, in card order, each as its cells trimmed (inner spaces
    collapsed) and joined by ` | `, the rows joined by a line break (MW-117, R287 Q4: the second input a reader judges, and
    the text whose sha256 a verdict record holds). Pure; empty when no row names a node."""
    wanted = {_node(str(n)) for n in nodes}
    part = card_text.split("## Acceptance examples", 1)
    if len(part) < 2:
        return ""
    out, index = [], None
    for line in part[1].splitlines():
        if line.startswith("## "):
            break
        if not line.startswith("|"):
            if index is not None:
                break
            continue
        cells = [" ".join(c.split()) for c in line.strip().strip("|").split("|")]
        if index is None:
            index = cells.index("Test") if "Test" in cells else len(cells) - 1
            continue
        if set(line) <= set("|-: "):
            continue
        cell = cells[index] if index < len(cells) else ""
        if any(_node(item) in wanted for item in cell.replace("`", "").split(";") if "::" in item):
            out.append(" | ".join(cells))
    return "\n".join(out)


def acceptance_sha(card_text: str, node: str) -> str:
    """The sha256 of the extract of one node (MW-117)."""
    return hashlib.sha256(acceptance_extract(card_text, [node]).encode("utf-8")).hexdigest()


def _acceptance_problem(row: Row, record: dict, card_text) -> Optional[str]:
    """None when the Acceptance rows of the node are what the reader judged: the extract of the current card text hashes to the
    `acceptance_sha` of the node in the add record (MW-117, R287 Q4). No card text, or a record with no sha for the node (written
    before MW-117: what it judged cannot be compared, never guessed), is not judged here. Else a why that begins with the id
    `verdict-stale:`, naming the node."""
    shas = record.get("acceptance_sha")
    old = shas.get(row.node) if isinstance(shas, dict) else None
    if card_text is None or not isinstance(old, str) or not old:
        return None
    new = acceptance_sha(card_text, row.node)
    if new == old:
        return None
    return (f"{core_verdicts.STALE}: the Acceptance rows of {row.node} changed after the verdict (the reader judged sha "
            f"{old[:8]}, the rows now hold {new[:8]}): run a fresh reader on the rows as they are now, then write the row "
            f"again with `mkway verdict add`")


def _row_problem(root, state, checkers, row: Row, written: list, recuts: list = (), card_text=None) -> Optional[str]:
    if row.verdict == core_verdicts.RECUT:  # the lead's row: its record proves it, no reader run does (R251b B)
        key = row_key(row)
        if any(r.get("row") == key and _node(str(r.get("node") or "")) == row.node for r in recuts):
            return None
        return ("no record of `mkway verdict recut` for this row (it was typed, copied, or changed after the command wrote "
                "it): the lead writes a recut row only with `mkway verdict recut <card> <node> <reason>`")
    mine = _mine(row, written)
    if not mine:
        return (f"no record of the session {row.by} writing this row with `mkway verdict add` (it was typed, copied, "
                f"changed after the command wrote it, or written by another session): the reader writes a verdict row "
                f"only with `mkway verdict add <card> <node> <true|weak|wrong> <reason>`")
    if not checkers:
        return ("the profile names no checker type (`outbox.checkers`), so no fresh reader can be proved: the owner sets "
                "that key")
    latest = mine[-1]
    return (_reader_problem(state, checkers, latest) or _meaning_problem(root, row, latest)
            or _acceptance_problem(row, latest, card_text))


def _reader_problem(state, checkers, record: dict) -> Optional[str]:
    """None when the record's own reader agent has an end row of a checker type in the record's session, ended before the
    record's time (card MW-101, R196: `verdict add` checked freshness against the file from git, the close does not read it
    again from the file's mtime).
    It asks `proof.fresh_reader_problem`, the one reader of the proof, for the record's own agent. No `agent` key, or no
    such end row, is unproven."""
    session, agent = record.get("session"), record.get("agent")
    for checker in checkers:
        if agent and proof.fresh_reader_problem(state, None, session, record.get("time"), checker, changed=proof.NEVER,
                                                agent=agent) is None:
            return None
    return (f"the add record names no reader agent of a checker type that ended before it in its session (agent "
            f"{agent or 'none'}, session {session or 'none'}): run a fresh reader on the file as it is now, then write the "
            f"row again with `mkway verdict add`")


def _blob_text(root, sha: str):
    """The text of the git blob `sha`; None when it is no sha (an option word never reaches git) or git cannot read it."""
    if not BLOB.match(sha):
        return None
    try:
        done = subprocess.run(["git", "--no-optional-locks", "cat-file", "blob", sha], cwd=str(root), capture_output=True,
                              timeout=GIT_SECONDS)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.decode("utf-8", "replace") if done.returncode == 0 else None


def _head_blob(root, rel: str) -> str:
    """The blob sha of the file `rel` at HEAD; empty when git has none."""
    try:
        done = subprocess.run(["git", "--no-optional-locks", "rev-parse", "--verify", "-q", f"HEAD:./{rel}"],
                              cwd=str(root), capture_output=True, timeout=GIT_SECONDS)
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout.decode("utf-8", "replace").strip() if done.returncode == 0 else ""


def _meaning_problem(root, row: Row, record: dict) -> Optional[str]:
    """None when the node's meaning is unchanged since the blob of its test file in the add record (card MW-101, R253): the
    blobs are equal, or `core_node_fresh` finds the node's own source and the file's non-test code equal. Else why not, with
    both blob shas; a blob git cannot read, a text that cannot be parsed or a node not found is never guessed as unchanged.
    Named gap: cross-file helpers (`tests/_*.py` kits, `conftest.py`) are not read."""
    rel = row.node.partition("::")[0]
    tests = record.get("tests")
    blob = tests.get(rel) if isinstance(tests, dict) else None
    cure = "run a fresh reader on the file as it is now, then write the row again with `mkway verdict add`"
    if not isinstance(blob, str) or not blob:
        return f"the add record holds no blob of {rel}, so what the reader judged cannot be compared: {cure}"
    head = _head_blob(root, rel)
    if not head:
        return f"{rel} is not in HEAD (the record's blob {blob[:8]}): {cure}"
    if blob.casefold() == head.casefold():
        return None
    old, new = _blob_text(root, blob), _show(root, "HEAD", rel)
    if old is None or new is None:
        return f"the record's blob {blob[:8]} of {rel} cannot be read from git, so it cannot be compared with HEAD {head[:8]}: {cure}"
    verdict = core_node_fresh.decide(old, new, row.node)
    if verdict.fresh:
        return None
    return f"{verdict.text}, from blob {blob[:8]} at the record to {head[:8]} at HEAD: {cure}"


def proof_problems(root, state, checkers, card_id: str, rows, card_text=None) -> dict:
    """{node: why} for the last row of each node in `rows` that has no proof of its reader (ruling R173 item 2): a record,
    by the reader's own session, of writing that row with `mkway verdict add` (`verdict_add.apply`, MW-080), and, through
    the shared `proof.fresh_reader_problem`, a fresh reader agent of a checker type (`outbox.checkers`) in that session. A
    row with none of true, weak, wrong is no verdict and is left to the core (`verdict-missing`)."""
    last = {}
    for row in rows:
        last[row.node] = row
    written, recuts = _proof_rows(state, card_id), _recut_rows(state, card_id)
    out = {}
    for node, row in last.items():
        if row.verdict in core_verdicts.WORDS + (core_verdicts.RECUT,):
            why = _row_problem(root, state, checkers, row, written, recuts, card_text)
            if why:
                out[node] = why
    return out


def before_recut(state, card_id: str, rows, found: dict) -> frozenset:
    """The nodes whose last row is true but older than the node's last recut record (R251b E): the row's own add record
    (the latest one that holds its key) sits earlier in the proof file than that recut record. `found` is `cuts`."""
    last = {}
    for row in rows:
        last[row.node] = row
    written = _proof_rows(state, card_id)
    old = set()
    for node, row in last.items():
        cut = found.get(node)
        mine = _mine(row, written) if row.verdict == core_verdicts.TRUE and cut is not None and cut.pos >= 0 else []
        if mine and mine[-1]["_pos"] < cut.pos:
            old.add(node)
    return frozenset(old)


AGENTS_DIR = ".claude/agents"


def parse_tools(text: str):
    """The tools the frontmatter of an agent definition lists, as a tuple; None when there is no frontmatter, no `tools:`
    line or no tool in it (an agent with no tools line has every tool). Reads `tools: A, B`, `tools: [A, B]` and a block
    list of `- A` lines under `tools:`."""
    lines = text.lstrip("﻿").splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    front = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        front.append(line)
    else:
        return None
    for at, line in enumerate(front):
        if not line.startswith("tools:"):
            continue
        value = line[len("tools:"):].strip()
        if not value:
            items = []
            for follow in front[at + 1:]:
                if not follow.strip().startswith("- "):
                    break
                items.append(follow.strip()[2:])
        else:
            items = value.strip("[]").split(",")
        tools = tuple(i.strip().strip("'\"") for i in items if i.strip().strip("'\""))
        return tools or None
    return None


def checker_facts(root, names) -> tuple:
    """One `Checker` per configured name: the definition in the task root first, else in the user folder (from the
    environment); `found` is False when neither file exists or the name is no plain file name."""
    try:
        home = Path.home()
    except (RuntimeError, KeyError):
        home = None
    out = []
    for name in names:
        plain = bool(name) and name not in (".", "..") and not any(c in name for c in "/\\:")
        places = [Path(root) / AGENTS_DIR / f"{name}.md"] + ([home / AGENTS_DIR / f"{name}.md"] if home else [])
        searched = " and ".join(str(p) for p in places)
        text = None
        for place in places if plain else []:
            try:
                text = place.read_text(encoding="utf-8", errors="replace")
                break
            except OSError:
                continue
        out.append(Checker(name, None if text is None else parse_tools(text), text is not None, searched))
    return tuple(out)


def build_facts(root, card_id: str, nodes, holder: str = "", state=None, checkers=None, card_text=None) -> Facts:
    """The facts of the check. `state` is the state folder that holds the commit records and the proof records; without it
    no committer and no proof is read. `checkers` is the profile's `outbox.checkers` (a list, possibly empty); without it
    no proof is read."""
    nodes = tuple(dict.fromkeys(nodes))
    files = dict.fromkeys(n.partition("::")[0] for n in nodes)
    rows = rows_of(root, card_id)
    proved = {} if state is None or not checkers else proof_problems(
        root, state, checkers, card_id, [r for r in rows if r.node in nodes], card_text)
    counted = state is not None and bool(checkers) and bool(nodes)
    found = cuts(state, card_id, nodes) if counted else {}
    return Facts(nodes=nodes, rows=tuple(rows), authors={f: authors_of(root, f) for f in files}, holder=holder or "",
                 committers={f: committers_of(root, state, f) for f in files} if state is not None else {},
                 unproven=proved, checkers_missing=checkers is not None and not checkers,
                 checkers=checker_facts(root, checkers) if checkers and nodes else (),
                 runs={n: c.runs for n, c in found.items()},
                 before_recut=before_recut(state, card_id, [r for r in rows if r.node in nodes], found) if counted
                 else frozenset(),
                 changed=changed_nodes(root, card_id, nodes) if nodes else None)


def warning(nodes, checkers) -> Optional[str]:
    """MW-068, ruling R179: the text that says the blind verdict was not enforced (a card that names a test node, a profile
    with no `outbox.checkers`), else None."""
    return core_verdicts.not_enforced(tuple(nodes), checkers is not None and not checkers)


def record_not_enforced(root, profile, card_id: str) -> dict:
    """Append the verdict record of a close that passed with the check not enforced (same file as the proof records)."""
    row = {"kind": "verdict-not-enforced", "card": card_id, "text": core_verdicts.NOT_ENFORCED,
           "time": logs.now().isoformat(timespec="milliseconds")}
    logs.append_jsonl(profiles.state_dir(Path(root), profile) / proof.FILE, row)
    return row


def problem(root, card_id: str, nodes, holder: str = "", state=None, checkers=None, card_text=None) -> Optional[tuple]:
    """None when the card may close; else (reason id of the first refusal, the refusal text naming every node and
    reason, and the way out)."""
    if not nodes:
        return None
    verdict = core_verdicts.decide(build_facts(root, card_id, nodes, holder, state, checkers, card_text))
    if verdict.allowed:
        return None
    text = (f"{card_id} cannot close: " + " | ".join(r.text for r in verdict.refusals)
            + f". A reader who did not write the test judges each named test against the criteria and writes one row "
              f"per node in {verdict_file(card_id)} (`node | true, weak or wrong | reason | by`); a weak or wrong "
              f"verdict is answered by a re-cut, never by an acceptance: the lead changes the row's words or the test, "
              f"commits, runs `mkway verdict recut <card> <node> <reason>`, and a fresh blind reader judges the new cut")
    return verdict.refusals[0].reason, text
