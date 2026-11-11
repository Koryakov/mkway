"""Shared helpers for the MW-019 tests (the outbox check). Not a test module. Synthetic values only.

Times are seconds after `T0`. The default valid case: the document's last change at 0, the checker agent started at 60
and ended at 120, the check file written at 180 (the time of the record the post step writes)."""
import datetime
import hashlib
import json
import os
from pathlib import Path

from _engine import gate_call, task_root  # first: it puts the engine folder on the path
import agents

T0 = datetime.datetime(2026, 11, 11, 10, 0, 0, tzinfo=datetime.timezone.utc)
OUT = "outbox"
SUFFIX = ".check.md"
RECORDS = "outbox_checks.jsonl"
DOC_TEXT = "Alpha beta gamma. Twelve items, seven claims.\n"
FORMS = {  # the line forms a refusal or a state names (engine/defaults.json `outbox_check.lines`)
    "numbers": "numbers: N checked, 0 contradictions",
    "claims": "claims: N checked, 0 overstated, 0 without basis",
    "patterns": "patterns: clean",
    "links": "links: clean",
    "checker": "checker: <agent type>",
}


def at(seconds) -> datetime.datetime:
    return T0 + datetime.timedelta(seconds=seconds)


def iso(seconds) -> str:
    return at(seconds).isoformat(timespec="milliseconds")


def make_root(tmp_path, *, outbox="default", name="task"):
    """A task root whose profile names the outbox folder and one checker type; `outbox=None` leaves the key out."""
    if outbox == "default":
        outbox = {"dir": OUT, "checkers": ["critic"]}
    over = {"outbox": outbox} if outbox is not None else {}
    root = task_root(tmp_path, name=name, **over)
    (root / OUT).mkdir(exist_ok=True)
    return root


def profile_of(root) -> dict:
    return json.loads((Path(root) / "mkway" / "profile.json").read_text(encoding="utf-8"))


def set_outbox(root, **keys):
    profile = profile_of(root)
    profile["outbox"] = keys
    (Path(root) / "mkway" / "profile.json").write_text(json.dumps(profile), encoding="utf-8")


def state_dir(root) -> Path:
    return Path(root) / "mkway" / "state"


def sha_of(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_doc(root, name="a.md", text=DOC_TEXT, when=0) -> str:
    """A document under the outbox folder, its last change `when` seconds after T0; returns its repo-relative path."""
    rel = f"{OUT}/{name}"
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="")
    os.utime(path, (at(when).timestamp(), at(when).timestamp()))
    return rel


def check_text(doc_sha, *, omit=(), extra="", **lines) -> str:
    """The text of a complete check file; `omit` leaves named lines out, a keyword replaces a line's whole text."""
    values = {"sha256": f"sha256: {doc_sha}", "numbers": "numbers: 12 checked, 0 contradictions",
              "claims": "claims: 7 checked, 0 overstated, 0 without basis", "patterns": "patterns: clean",
              "links": "links: clean", "checker": "checker: critic"}
    values.update(lines)
    return "\n".join(v for k, v in values.items() if k not in omit) + "\n" + extra


def record(root, rel, *, session="s1", when=180, check_sha=None):
    """The row the post step writes after a write of a check file; the sha is the check file's now by default."""
    check = Path(root) / (rel + SUFFIX)
    row = {"kind": "check-written", "doc": rel, "check": rel + SUFFIX,
           "check_sha": check_sha or sha_of(check), "session": session, "time": iso(when)}
    path = state_dir(root) / RECORDS
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def write_check(root, rel, text=None, *, doc_sha=None, session="s1", when=180, recorded=True, **lines) -> Path:
    """The check file beside `rel` (the document's sha now by default) and, when `recorded`, the post step's row."""
    path = Path(root) / (rel + SUFFIX)
    path.write_text(text if text is not None else check_text(doc_sha or sha_of(Path(root) / rel), **lines),
                    encoding="utf-8", newline="")
    if recorded:
        record(root, rel, session=session, when=when)
    return path


def add_agent(root, *, session="s1", agent_type="critic", agent_id="a1", started=60, ended=120, start_row=True):
    """The rows the two agent hooks write (a start row, then an end row that carries the start time)."""
    state = state_dir(root)
    if start_row:
        agents.append(state, {"kind": "start", "session_id": session, "agent_id": agent_id, "agent_type": agent_type,
                              "started": iso(started)})
    agents.append(state, {"kind": "end", "session_id": session, "agent_id": agent_id, "agent_type": agent_type,
                          "started": iso(started) if start_row else agents.NE, "ended": iso(ended),
                          "elapsed_seconds": ended - started if start_row else agents.NE, "result": "no findings",
                          "result_source": "payload"})


def valid_file(root, name="a.md", *, text=DOC_TEXT, agent="default", doc_when=0, check_when=180, session="s1",
               **lines) -> str:
    """A document with a complete check, a record of its write and one fresh reader: valid unless a keyword breaks it.
    `agent` is a dict of `add_agent` arguments, or None for no agent row at all."""
    rel = write_doc(root, name, text, when=doc_when)
    if agent is not None:
        add_agent(root, **({} if agent == "default" else agent))
    write_check(root, rel, session=session, when=check_when, **lines)
    return rel


def inspect(root, rel):
    import outbox
    return outbox.inspect(Path(root), profile_of(root), rel)


def joined(status) -> str:
    return " | ".join(status.problems)


def refusal_rows(root):
    path = state_dir(root) / "refusals.jsonl"
    if not path.is_file():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def pre(root, rel, content=None, *, tool="Write", session="s1", edits=None, old=None, new=None):
    """The edit gate on one write of a check file. Write carries `content`; Edit carries `old` and `new`; MultiEdit
    carries `edits` (a list of (old, new)). The file must exist on disk first for an Edit or a MultiEdit."""
    import gate_outbox
    if tool == "Write":
        tool_input = {"file_path": rel, "content": content}
    elif tool == "Edit":
        tool_input = {"file_path": rel, "old_string": old, "new_string": new}
    else:
        tool_input = {"file_path": rel, "edits": [{"old_string": o, "new_string": n} for o, n in (edits or [])]}
    return gate_call(gate_outbox.check, root, tool=tool, tool_input=tool_input, session=session)


def post(root, rel, *, tool="Write", session="s1"):
    import gate_outbox
    return gate_call(gate_outbox.check, root, tool=tool, event="PostToolUse", session=session,
                     tool_input={"file_path": rel, "content": "x"}, tool_response={"filePath": rel, "success": True})


def stop(root, *, session="s1"):
    import gate_outbox
    return gate_call(gate_outbox.check, root, tool=None, event="Stop", session=session, tool_input=None)
