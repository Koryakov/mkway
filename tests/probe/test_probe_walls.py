"""Probe (not a card; order of retro-oper10, 16.11, chief ruling R282a): does a wall (K1, protected targets) leak today?

Case A: an edit with a relative path against a closed target, resolved from a hook cwd that differs from the root.
Case B: the shared state folder (`state.shared_dir`, outside the task root) reached by an edit and by a literal shell write.
Synthetic names only."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _engine import make_profile, write_profile  # noqa: E402  (also puts the engine on the path)
import dispatch  # noqa: E402

ENGINE_EDIT = ["lock.edit", "outside.edit", "lead.edit", "owner_ask.edit", "search", "outbox_check.pre", "read_first_gate"]
ENGINE_SHELL = ["lock.shell", "outside.shell", "lead.shell"]


def _entries(names):
    wanted = {e["name"]: e for e in dispatch.load_manifest(dispatch.ENGINE_DIR)}
    return [wanted[n] for n in names]


def _root(tmp_path, **over):
    root = tmp_path / "task"
    for sub in ("cards", "ledger", "locks", "state"):
        (root / "mkway" / sub).mkdir(parents=True, exist_ok=True)
    profile = make_profile(None, vcs="none", ids={"card_prefix": "CARD"})
    profile.update(over)
    write_profile(root, profile)
    return root


def _hook(root, group, tool, tool_input, cwd, names):
    payload = {"session_id": "s1", "hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input,
               "cwd": str(cwd)}
    out = dispatch.run("PreToolUse", group, json.dumps(payload),
                       env={"CLAUDE_PROJECT_DIR": str(root), "CLAUDECODE": "1"}, manifest=_entries(names))
    try:
        decision = json.loads(out.stdout)["hookSpecificOutput"]["permissionDecision"]
    except (ValueError, KeyError, TypeError):
        decision = "allow"
    return decision, out.stdout


def test_case_a_relative_edit_path_from_a_cwd_inside_a_closed_target_is_refused(tmp_path):
    """Case A. The target `notes/` is closed. The hook cwd is `<root>/notes`; the edit path is `f.txt`: from the cwd it lands in
    `notes/f.txt` (closed), from the root it would be `f.txt` (open). The edit group runs the lock gate and the gates that read
    a relative path from the root (owner_ask, search, outbox_check.pre; read_first is `planned`, no function)."""
    root = _root(tmp_path, locks={"targets": [{"name": "docs", "paths": ["notes/"]}]})
    (root / "notes").mkdir()
    control, _ = _hook(root, "edit", "Write", {"file_path": str(root / "notes" / "f.txt"), "content": "x"}, root, ENGINE_EDIT[:1])
    assert control == "deny", "the control: an absolute path into the closed target must be refused, or the setup is wrong"
    names = [n for n in ENGINE_EDIT if n != "read_first_gate"]
    decision, text = _hook(root, "edit", "Write", {"file_path": "f.txt", "content": "x"}, root / "notes", names)
    assert decision == "deny", f"a relative edit path from cwd=notes reached a closed target: {text!r}"


def test_case_b_shared_state_folder_is_refused_for_an_edit_and_for_a_shell_write(tmp_path):
    """Case B. `state.shared_dir` names a folder outside the task root (in tmp_path). An edit and a literal shell write into
    it must both be refused."""
    shared = tmp_path / "shared"
    shared.mkdir()
    root = _root(tmp_path, state={"dir": "mkway/state", "shared_dir": str(shared)})
    edit, edit_text = _hook(root, "edit", "Write", {"file_path": str(shared / "leads.json"), "content": "x"}, root,
                            ["lock.edit", "outside.edit", "lead.edit"])
    shell, shell_text = _hook(root, "shell", "Bash", {"command": f'echo x > "{(shared / "leads.json").as_posix()}"'}, root,
                              ENGINE_SHELL)
    leaks = [k for k, v in (("edit", edit), ("shell", shell)) if v != "deny"]
    assert not leaks, f"the shared state folder is writable by: {leaks}; edit={edit_text!r} shell={shell_text!r}"
