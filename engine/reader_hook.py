"""The reader's allowlist hook (card MW-116; rulings R272 G2, R287c): a PreToolUse hook of the reader agent's own frontmatter.

It is run as `python <bundle>/engine/reader_hook.py` by Claude Code, inside the subagent, with the hook input on stdin and
`CLAUDE_PROJECT_DIR` in the environment. It is no settings hook and no dispatcher gate (the manifest lists it with the kind
`frontmatter`): Claude Code removes a frontmatter hook when the subagent ends, and runs it only after the workspace trust
dialog for the folder of the agent file (sub-agents.md). Its fail-closed proof is the record, not `onFailure`: every call
leaves one row in `<state>/reader_runs.jsonl` together with its decision, and `mkway verdict add` refuses
`verdict-reader-unguarded` for a run with no row.

Exit 0 lets the call go ahead; exit 2 blocks it and the text on stderr goes to the reader. Anything that goes wrong (an
input that is no JSON object, no root, a record row that cannot be written, an import that fails) is exit 2 with the text of
the refusal `reader-read-refused` that names the crash: a script that dies with another exit code would not block.
"""
import os
import sys
from pathlib import Path

CRASH = ("reader-read-refused: crash of the allowlist hook ({cause}); the read is refused, because a hook that cannot "
         "judge never lets a read through. The way out: run `mkway reader start <card>` again from the spawning session "
         "and run the reader again; if it keeps happening, report the cause to the owner")


def main(stdin_text, env=None):
    """(exit code, text for stderr) of one hook call. The record row is written together with the decision."""
    import json
    import agents
    import logs
    import paths
    import profiles
    import reader_allow
    env = os.environ if env is None else env
    data = json.loads(stdin_text)
    if not isinstance(data, dict):
        raise TypeError("the hook input is not a JSON object")
    root = paths.find_root(env=env, cwd=Path(data["cwd"]) if isinstance(data.get("cwd"), str) else None)
    profile, _errors = profiles.load(paths.profile_path(root, None))
    state = profiles.state_dir(root, profile)
    session = data.get("session_id")
    allow = None
    sha = ""
    try:
        allow = reader_allow.read_allow(state, session)
        sha = reader_allow.sha_of(reader_allow.allow_file(state, session))
    except ValueError:  # a session id that is no plain name has no file
        pass
    decision = reader_allow.decide(data, allow)
    row = {"kind": "call", "session_id": session, "agent_id": data.get("agent_id"), "agent_type": data.get("agent_type"),
           "tool": data.get("tool_name"), "path": decision.path or _named(data), "decision": "allow" if decision.allowed
           else "refuse", "allow_sha256": sha, "time": logs.now().isoformat(timespec="milliseconds")}
    try:
        agents.append_reader(state, row)
    except Exception as exc:
        return 2, reader_allow.record_text(str(Path(state) / agents.READER_RUNS), exc.__class__.__name__)
    return (0, "") if decision.allowed else (2, decision.text)


def _named(data) -> str:
    """The path the call names, as written, for the record row of a refusal that resolved none."""
    tool_input = data.get("tool_input")
    if isinstance(tool_input, dict):
        for key in ("file_path", "path"):
            if isinstance(tool_input.get(key), str):
                return tool_input[key]
    return ""


def run() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent))  # `python -I` puts no script folder on the path
    try:
        code, text = main(sys.stdin.buffer.read().decode("utf-8", "replace"))
    except BaseException as exc:
        code, text = 2, CRASH.format(cause=exc.__class__.__name__)
    if text:
        sys.stderr.buffer.write((text + "\n").encode("utf-8", "replace"))
        sys.stderr.flush()
    return code


if __name__ == "__main__":
    sys.exit(run())
