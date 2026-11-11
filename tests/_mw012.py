"""Helpers for the card MW-012 tests (not a test module): a dispatcher run over synthetic gate entries, and rows
written straight into the calls log. Synthetic task roots only."""
import datetime
import json

from _engine import FIXTURES, entry, jsonl, make_profile, write_profile
import dispatch

FUNCTION = "fixture_mw012:refuse_if_bad"


def form_entry(name="f1", **kw):
    e = entry(name, FUNCTION, **kw)
    e["class"] = "form"
    return e


def integrity_entry(name="i1", **kw):
    e = entry(name, FUNCTION, **kw)
    e["class"] = "integrity"
    return e


def unclassed_entry(name="u1", **kw):
    return entry(name, FUNCTION, **kw)  # no `class` key: it reads integrity


def make_root(tmp_path, **over):
    root = tmp_path / "task"
    root.mkdir(parents=True)
    write_profile(root, make_profile(**over))
    return root


def state(root):
    return root / "mkway" / "state"


def run(root, entries, target="src/a.py", *, event="PreToolUse", group="edit", tool="Edit", session="s1"):
    payload = {"session_id": session, "hook_event_name": event, "cwd": "."}
    if event in ("PreToolUse", "PostToolUse"):
        payload.update(tool_name=tool, tool_input={"file_path": target})
    return dispatch.run(event, group, json.dumps(payload), env={"CLAUDE_PROJECT_DIR": str(root), "CLAUDECODE": "1"},
                        manifest=entries, gate_paths=[FIXTURES])


def denied(result) -> bool:
    return bool(result.stdout) and json.loads(result.stdout)["hookSpecificOutput"].get(
        "permissionDecision") == "deny"


def calls(root):
    return jsonl(state(root) / "gate_calls.jsonl")


def refusals(root):
    return jsonl(state(root) / "refusals.jsonl")


def marker(root, gate):
    path = state(root) / "gate_mode" / f"{gate}.watch"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def write_marker(root, gate, cause="owner", time="2026-11-10T08:00:00.000+00:00", calls=0, refused=0):
    path = state(root) / "gate_mode" / f"{gate}.watch"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"gate": gate, "cause": cause, "time": time, "calls": calls, "refused": refused}),
                    encoding="utf-8")


def seed_calls(root, gate, *, allow=0, refuse=0, error=0, minutes_ago=30):
    """Append rows to the calls log, `minutes_ago` minutes before now (default well inside the last 24 hours)."""
    when = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=minutes_ago)).isoformat(
        timespec="milliseconds")
    rows = [{"time": when, "gate": gate, "verdict": v} for v, n in (("allow", allow), ("refuse", refuse),
                                                                      ("error", error)) for _ in range(n)]
    path = state(root) / "gate_calls.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
