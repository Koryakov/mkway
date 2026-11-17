"""The reader's allowlist (card MW-116; rulings R272 G2, R287, R287c, R287d; concept K3).

The reader that judges a test reads two inputs only: the test files of the card's nodes and the engine-written extract of
the Acceptance rows of the named nodes (never the card file). Three parts:

- `start` (the command `mkway reader start <card>`, run by the spawning session) writes the allow file
  `<state>/reader_allow/<session id>.json` and the extract `<session id>.extract.md` beside it, and one start row into
  `<state>/reader_runs.jsonl` (the files listed, the sha256 of the allow file and of the extract). One run at a time per
  session: a file that still lists files refuses `reader-busy` while its run is younger than `LEASE_MINUTES` (30, R295; the
  file carries the start time); an older lock is taken over by the next start, with a record row `reader-lease-expired` that
  names the old run; a start time that cannot be read is never taken over. `end` (the command `mkway reader end`, or the end of a
  checker agent's run, `release`) empties the list; the file stays, with no files.
- `decide` (pure) is the judgement of the frontmatter hook `engine/reader_hook.py` on one tool call: Read and Grep on a listed
  file pass, the report tool `SubagentHandback` passes, every other path and tool is refused `reader-read-refused`, and so
  is every call of a session that has no usable allow file (fail closed). The text of a refusal names the cause (unlisted
  path, unlisted tool, no allow file for the session, crash) and the way out (the listed files, or the start command).
- `expected_inputs` is the list the card's two inputs make now; `mkway verdict add` compares it with the start row of the
  run (`proof.reader_guard_problem`).

The allow file is keyed by the hook input's `session_id`, which inside a subagent is the spawning session's id (hooks.md,
common fields; tool events inside a subagent carry `agent_id` and `agent_type` too). Different sessions never share a file.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
from pathlib import Path
from typing import NamedTuple, Optional

import agents
import cardtool
import logs
import register
import verdicts

ALLOW_DIR = "reader_allow"
REFUSED = "reader-read-refused"
BUSY = "reader-busy"
REASONS = (REFUSED, BUSY)  # the ids of this module (the concept scan reads this tuple)
HANDBACK = "SubagentHandback"  # hooks.md: the tool that delivers a subagent's report; it always passes
READ_TOOLS = ("Read", "Grep")
PATH_KEY = {"Read": "file_path", "Grep": "path"}
SAFE_SESSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
START_COMMAND = "mkway reader start <card>"
BUSY_WAY_OUT = "wait for your own run or the orderer's release"
LEASE_MINUTES = 30  # R295: `reader start` takes over a lock older than this; an engine constant, no profile key
LEASE_ID = "reader-lease-expired"  # the record row of a takeover; it names the old run


class ReaderError(Exception):
    """A refusal of the start step: `reason` is the id, `text` the whole message (it names the way out)."""

    def __init__(self, reason: str, text: str):
        super().__init__(text)
        self.reason = reason
        self.text = text


class Decision(NamedTuple):
    allowed: bool
    text: str = ""
    path: str = ""


# ---- the pure judgement ----------------------------------------------------------------------------------------------

def _resolve(raw, cwd) -> str:
    """The path a tool names, as one normal form: joined with the hook's cwd when relative, `..` and `.` folded."""
    text = str(raw)
    return os.path.normpath(text if os.path.isabs(text) else os.path.join(str(cwd or ""), text))


def _key(path: str) -> str:
    return os.path.normcase(path)


def _files(allow, session):
    """The listed files of an allow file that belongs to `session`; None when there is no usable list."""
    if not isinstance(allow, dict) or not isinstance(session, str) or not session or allow.get("session_id") != session:
        return None
    files = allow.get("files")
    if not isinstance(files, list):
        return None
    names = [f for f in files if isinstance(f, str) and f]
    return names or None


def crash_text(cause: str) -> str:
    return (f"{REFUSED}: crash of the allowlist hook ({cause}); the read is refused, because a hook that cannot judge never "
            f"lets a read through. The way out: run `{START_COMMAND}` again from the spawning session and run the reader "
            f"again; if it keeps happening, report the cause to the owner")


def record_text(path: str, cause: str) -> str:
    return (f"{REFUSED}: the hook cannot write its record row ({cause}: {path}); the read is refused, because a read with no "
            f"record would count as unguarded. The way out: make the record file writable, then run the reader again")


def decide(payload, allow) -> Decision:
    """The judgement of one tool call of the reader (see the module docstring). Pure."""
    payload = payload if isinstance(payload, dict) else {}
    tool = payload.get("tool_name")
    if tool == HANDBACK:
        return Decision(True)
    session = payload.get("session_id")
    files = _files(allow, session)
    if files is None:
        return Decision(False, f"{REFUSED}: no allow file for the session {session or 'not established'} (none, or its list "
                               f"is empty); the spawning session runs `{START_COMMAND}`, then the reader runs again")
    listed = ", ".join(files)
    if tool not in READ_TOOLS:
        return Decision(False, f"{REFUSED}: unlisted tool {tool}; the reader uses Read and Grep on the listed files only: "
                               f"the listed files: {listed}")
    tool_input = payload.get("tool_input")
    raw = tool_input.get(PATH_KEY[tool]) if isinstance(tool_input, dict) else None
    if not isinstance(raw, str) or not raw.strip():
        return Decision(False, f"{REFUSED}: unlisted path: the {tool} call names no file; the reader names one of the "
                               f"listed files: {listed}")
    path = _resolve(raw, payload.get("cwd"))
    if _key(path) in {_key(_resolve(f, payload.get("cwd"))) for f in files}:
        return Decision(True, "", path)
    return Decision(False, f"{REFUSED}: unlisted path {path}; the reader reads the listed files only, the test file and the "
                           f"Acceptance rows of the named nodes: the listed files: {listed}", path)


# ---- the files -------------------------------------------------------------------------------------------------------

def _folder(state) -> Path:
    return Path(state) / ALLOW_DIR


def allow_file(state, session: str) -> Path:
    if not isinstance(session, str) or not SAFE_SESSION.match(session):
        raise ValueError("the session id is not a plain name")
    return _folder(state) / f"{session}.json"


def extract_file(state, session: str) -> Path:
    return _folder(state) / f"{session}.extract.md"


def read_allow(state, session):
    """The allow file of `session` as a dict; None when there is none or it cannot be read."""
    try:
        data = json.loads(allow_file(state, session).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def sha_of(path) -> str:
    """The sha256 hex of a file's bytes; empty when it cannot be read."""
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return ""


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def _normal(path) -> str:
    return os.path.normpath(os.path.abspath(str(path)))


def _inputs(root, profile, state, session: str, card_id: str):
    """(the card's two inputs as a list of files, the extract text): the test files of the nodes the card's Acceptance rows
    name, in order of the nodes, then the extract file of the session."""
    row = register.find(register.read(root, profile), card_id)
    if row is None:
        raise cardtool.CardError(f"{card_id} is not in the register", reason="card-unknown")
    try:
        text = cardtool.card_file(root, profile, card_id).read_text(encoding="utf-8")
    except OSError:
        raise cardtool.CardError(f"{card_id} has no card file", reason="card-unknown")
    nodes = list(dict.fromkeys(verdicts._node(n) for n in cardtool.test_nodes(text)))
    if not nodes:
        raise cardtool.CardError(f"{card_id} names no test node in its Acceptance rows, so there is nothing for a reader "
                                 f"to judge")
    files = list(dict.fromkeys(_normal(Path(root) / n.partition("::")[0]) for n in nodes))
    return files + [_normal(extract_file(state, session))], verdicts.acceptance_extract(text, nodes)


def expected_inputs(root, profile, state, session: str, card_id: str):
    """(the card's two inputs now as a list of normal paths, the sha256 hex of the extract text)."""
    files, extract = _inputs(root, profile, state, session, card_id)
    return files, hashlib.sha256(extract.encode("utf-8")).hexdigest()


# ---- the steps --------------------------------------------------------------------------------------------------------

def start(root, profile, state, session: str, card_id: str) -> dict:
    """The reader-start step: the allow file of `session` for `card_id`. `reader-busy` when the session's list is not
    empty; the card errors of `cardtool.CardError` when the card or a test file is missing."""
    try:
        path = allow_file(state, session)
    except ValueError:
        raise ReaderError("message-no-session", f"message-no-session: the session id {session!r} is not a plain name; the "
                                                f"allow file is keyed by the id of the spawning session")
    now = read_allow(state, session)
    expired = None
    if _files(now, session):
        age = _age_minutes(now)
        held = f"{BUSY}: session {session} has a reader run that holds a list ({now.get('card', 'a card')}); {BUSY_WAY_OUT}"
        if age is None:
            raise ReaderError(BUSY, f"{held}: its start time cannot be read, so the lock is not taken over; `mkway reader end` "
                                    f"empties your own list, and the owner's terminal `mkway reader end --session {session}`")
        if age < LEASE_MINUTES:
            raise ReaderError(BUSY, f"{held}: wait, the end of the reader's run empties the list (this lock is {age:.0f} "
                                    f"minutes old; a lock older than {LEASE_MINUTES} minutes is taken over by the next "
                                    f"start); `mkway reader end` empties your own list")
        expired = {"kind": LEASE_ID, "session_id": session, "card": now.get("card"), "old_started": now.get("started"),
                   "old_allow_sha256": sha_of(path), "new_card": card_id}
    files, extract = _inputs(root, profile, state, session, card_id)
    missing = [f for f in files[:-1] if not Path(f).is_file()]
    if missing:
        raise cardtool.CardError(f"the test file {missing[0]} does not exist, so the reader has nothing to read")
    if expired is not None:  # R295: the takeover of a lock older than the lease leaves a record that names the old run
        agents.append_reader(state, {**expired, "time": logs.now().isoformat(timespec="milliseconds")})
    body = extract.encode("utf-8")
    _write(Path(files[-1]), body)
    doc = {"session_id": session, "card": card_id, "files": files, "checkers": list(profile_checkers(profile)),
           "started": logs.now().isoformat(timespec="milliseconds")}
    _write(path, (json.dumps(doc, indent=1) + "\n").encode("utf-8"))
    agents.append_reader(state, {"kind": "start", "session_id": session, "card": card_id, "files": files,
                                 "allow_sha256": sha_of(path), "extract_sha256": hashlib.sha256(body).hexdigest(),
                                 "time": doc["started"]})
    return doc


def _age_minutes(doc):
    """The age of an allow file's run in minutes, from its `started` time; None when the time cannot be read."""
    try:
        began = datetime.datetime.fromisoformat(doc.get("started"))
    except (TypeError, ValueError):
        return None
    if began.tzinfo is None:
        began = began.replace(tzinfo=datetime.timezone.utc)
    return (logs.now() - began).total_seconds() / 60


def profile_checkers(profile) -> tuple:
    group = profile.get("outbox") if isinstance(profile, dict) else None
    names = group.get("checkers") if isinstance(group, dict) else None
    return tuple(n for n in names or () if isinstance(n, str) and n)


def end(state, session: str) -> bool:
    """Empty the list of `session`'s allow file (the file stays, with no files). False when the session has no file."""
    doc = read_allow(state, session)
    if doc is None:
        return False
    doc["files"] = []
    doc["ended"] = logs.now().isoformat(timespec="milliseconds")
    _write(allow_file(state, session), (json.dumps(doc, indent=1) + "\n").encode("utf-8"))
    return True


def release(state, payload) -> bool:
    """The end of a run (a `SubagentStop` payload): empties the list of the payload's session when the agent is of a checker
    type the file names. Another agent type, or another session, leaves the list as it is."""
    payload = payload if isinstance(payload, dict) else {}
    session = payload.get("session_id")
    if not isinstance(session, str) or not SAFE_SESSION.match(session):
        return False
    doc = read_allow(state, session)
    if doc is None or not _files(doc, session) or payload.get("agent_type") not in (doc.get("checkers") or []):
        return False
    return end(state, session)
