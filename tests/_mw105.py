"""Card MW-105 helpers for the lock-gate tests of the upgrade folder (shell rows and Windows rules). Not a test module.

`make_world` is the body of the `world` fixture of both test modules: a synthetic task root, and a hermetic environment whose
APPDATA and XDG_CONFIG_HOME are one folder under tmp_path, so the guarded folder `<base>/mkway/upgrade` is the same on every OS
(owner 13.11: no reading of a real folder; the real home is read only by the one 8.3 row, which creates nothing). The gate is
asked as the hook asks it: `ask` builds the context the dispatcher builds, with the environment of the call in `ctx.env`."""
import json
import os
from collections import namedtuple

from _engine import task_root
from _mw104 import hermetic
import dispatch
import gate_lock

World = namedtuple("World", "root profile base dir home env")
DENY_EDIT, DENY_SHELL, ALLOW = ("refuse", "lock-closed-edit"), ("refuse", "lock-closed-shell"), ("allow", None)
LOGGED = ("log", "write-target-unresolved")
ENGINE_ONLY = "only the engine's own commands write it"


def win(text):
    """A Windows path text from the `|` mark, so no backslash is written by hand."""
    return text.replace("|", chr(92))


def make_world(tmp_path, monkeypatch):
    """A task root and the hermetic environment (no override): `<dir>` is `<base>/mkway/upgrade` under tmp_path."""
    hermetic(monkeypatch, tmp_path)
    base = tmp_path / "cfg"
    base.mkdir()
    for name in ("APPDATA", "XDG_CONFIG_HOME"):
        monkeypatch.setenv(name, str(base))
    monkeypatch.delenv("MKWAY_UPGRADE_DIR", raising=False)
    root = task_root(tmp_path, vcs="none")
    profile = json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))
    return World(root, profile, base, base / "mkway" / "upgrade", tmp_path / "hermetic" / "home", dict(os.environ))


def context(world, tool, tool_input, env=None):
    """The context the dispatcher builds for one hook call; `env` replaces the world's environment for this call."""
    return dispatch.make_context(profile=world.profile, root=world.root, session_id="s1", event="PreToolUse", gate="g",
                                 tool_name=tool, tool_input=tool_input, budget_seconds=None, once=lambda t: True,
                                 tool_response=None, env=world.env if env is None else env)


def ask(world, tool, tool_input, env=None):
    return gate_lock.check("PreToolUse", context(world, tool, tool_input, env))


def write(world, path, tool="Write", env=None):
    """One edit-tool write of `path` (text), judged by the real lock gate."""
    key = "notebook_path" if tool == "NotebookEdit" else "file_path"
    return ask(world, tool, {key: str(path), "content": "x"}, env)


def shell(world, command, tool="Bash", env=None):
    return ask(world, tool, {"command": command}, env)


def seen(verdict):
    """(kind, reason id) of a gate verdict."""
    return (verdict.kind, verdict.reason_id)


def by_class(verdict):
    """(kind, reason id, `'upgrade'` is named, the engine-only text is in the message, `write literal paths` is in it): a refusal
    by the class compare is DENY plus (True, True, False); a refusal by literal reach (core_lock, rule b) names the target too,
    but says `write literal paths`, so it cannot pass for the new compare (reader B 1, fix list T1, ruling R183)."""
    text = verdict.message
    return seen(verdict) + ("'upgrade'" in text, ENGINE_ONLY in text, "write literal paths" in text)


CLASS_ONLY = (True, True, False)


def by_tool(world, tool, text, env=None):
    """The gate's verdict for `text` as one edit-tool path (`Write`) or as one Bash append to it, quoted."""
    return write(world, text, env=env) if tool == "Write" else shell(world, f"echo x >> '{text}'", env=env)


def expected(tool):
    """The refusal a tool gets: the edit gate's for `Write`, the shell gate's for `Bash`."""
    return {"Write": DENY_EDIT, "Bash": DENY_SHELL}[tool]
