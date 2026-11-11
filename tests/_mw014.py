"""Shared helpers for the MW-014 tests (asks that do not stop the work). Not a test module. Synthetic values only."""
import datetime
import importlib
import json
import os
from pathlib import Path

from _engine import gate_call  # first: it puts the engine folder on the path
import records

ASK_DIR = "mkway/asks"
SOURCES = "kind: lock\nchecked: commit lock closed\n"  # the lightest sources file the edit gate accepts
FAR = "2099-01-01T10:00"
PAST = "2000-01-01T10:00"
SHAPES = {  # the line shapes the refusal names, one per field of an ask
    "default": "default: <text or none>",
    "deadline": "deadline: <ISO local time or none>",
    "blocked": "blocked: <what waits, or none>",
    "reversible": "reversible: yes|no",
    "status": "status: open",
}


def gate():
    return importlib.import_module("gate_owner_ask")


def ask_text(*, question="Which option?", omit=(), **fields) -> str:
    """The text of a complete ask; `omit` leaves named field lines out, a keyword replaces a field's value."""
    values = {"default": "keep option A", "deadline": FAR, "blocked": "the report part", "reversible": "yes",
              "status": "open"}
    values.update(fields)
    lines = [question] + [f"{k}: {v}" for k, v in values.items() if k not in omit]
    return "\n".join(lines) + "\n"


def asks_folder(root) -> Path:
    folder = Path(root) / ASK_DIR
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def write_ask(root, name, *, session=None, age_seconds=None, sources=True, **fields) -> Path:
    """An ask file on disk (and its sources file); with `session` the record the post step writes, so the session owns
    it; with `age_seconds` the file's time is set that far back."""
    folder = asks_folder(root)
    path = folder / f"{name}_ask.md"
    path.write_text(ask_text(**fields), encoding="utf-8", newline="")
    if sources:
        (folder / f"{name}_sources.md").write_text(SOURCES, encoding="utf-8", newline="")
    if age_seconds is not None:
        then = datetime.datetime.now().timestamp() - age_seconds
        os.utime(path, (then, then))
    if session:
        records.append(Path(root) / "mkway" / "state", session, "ask", name)
    return path


def write_sources(root, name, text=SOURCES):
    (asks_folder(root) / f"{name}_sources.md").write_text(text, encoding="utf-8", newline="")


def tool_input(root, rel, tool="Write", text=None):
    """The tool input of one write of an ask. Write carries the text; Edit and MultiEdit carry an edit that leaves the
    file as `text` says (the file is made on disk first, because the gate reads it)."""
    text = ask_text() if text is None else text
    if tool == "Write":
        return {"file_path": rel, "content": text}
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(text, encoding="utf-8", newline="")
    edit = {"old_string": "status: open", "new_string": "status: open"}
    return {"file_path": rel, "edits": [edit]} if tool == "MultiEdit" else {"file_path": rel, **edit}


def pre(root, name="t", *, tool="Write", text=None, session="s1", path=None, **extra):
    rel = path or f"{ASK_DIR}/{name}_ask.md"
    return gate_call(gate().check, root, tool=tool, tool_input=tool_input(root, rel, tool, text), session=session,
                     **extra)


def post(root, name="t", *, tool="Write", session="s1", path=None, profile=None):
    rel = path or f"{ASK_DIR}/{name}_ask.md"
    return gate_call(gate().check, root, tool=tool, event="PostToolUse", session=session, profile=profile,
                     tool_input={"file_path": rel, "content": "x"}, tool_response={"filePath": rel, "success": True})


def verdict_id(v) -> str:
    return v.reason_id if v.kind != "allow" else "allow"


def log_rows(root):
    path = Path(root) / "mkway" / "state" / "refusals.jsonl"
    if not path.is_file():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
