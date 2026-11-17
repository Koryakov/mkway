"""Card MW-116: the install writes the reader agent file `.claude/agents/fresh-reader.md` from the shipped template, with the
frontmatter hook that runs the allowlist script of the installed engine copy, and wires nothing of it into settings. One
engine install (module fixture, a scratch git repository); the hook command is run the way Claude Code runs it: through
the shell, the hook input on stdin, the project folder in the environment. Synthetic sessions only."""
import json
import re
import subprocess

import pytest

import _engine  # noqa: F401  (puts the engine folder on the import path)
from _hook_driver import install_project
import verdicts

pytestmark = pytest.mark.engine_repo


@pytest.fixture(scope="module")
def proj(tmp_path_factory):
    return install_project(tmp_path_factory.mktemp("mw116"))


def _agent_text(p):
    return (p.root / ".claude" / "agents" / "fresh-reader.md").read_text(encoding="utf-8")


def test_the_install_writes_the_reader_agent_with_read_and_grep_only(proj):
    """Catches: an install that ships no reader (the checker then reads as not found), or one with more tools than Read and
    Grep, or with a placeholder left in the file."""
    text = _agent_text(proj)
    assert verdicts.parse_tools(text) == ("Read", "Grep")
    assert "name: fresh-reader" in text and "{{" not in text


def test_the_frontmatter_hook_runs_the_script_of_the_installed_engine_copy(proj):
    """Catches: a hook line that points at the source repository or at a path the project does not have."""
    text = _agent_text(proj)
    assert "${CLAUDE_PROJECT_DIR}/mkway/engine/engine/reader_hook.py" in text
    assert (proj.root / "mkway" / "engine" / "engine" / "reader_hook.py").is_file()


def test_the_script_is_not_a_settings_hook(proj):
    """Catches: the frontmatter hook also wired into settings, where it would judge the tools of every session."""
    settings = (proj.root / ".claude" / "settings.json").read_text(encoding="utf-8")
    assert "reader_hook" not in settings


def test_the_hook_command_of_the_agent_file_blocks_a_session_with_no_allow_file(proj):
    """Catches: a frontmatter hook command that does not run (wrong quoting, wrong path): run as written, a read by a session
    that has no allow file exits 2 with the refusal id."""
    command = re.search(r"command:\s*(.+)", _agent_text(proj)).group(1).strip()
    data = {"session_id": "s-none", "hook_event_name": "PreToolUse", "tool_name": "Read", "cwd": str(proj.root),
            "tool_input": {"file_path": "tests/test_a.py"}, "agent_id": "a1", "agent_type": "fresh-reader"}
    done = subprocess.run([proj.bash, "-c", command], input=json.dumps(data), capture_output=True, text=True,
                          encoding="utf-8", cwd=str(proj.root), env=proj.env(session=True), timeout=60)
    assert done.returncode == 2
    assert "reader-read-refused" in done.stderr

