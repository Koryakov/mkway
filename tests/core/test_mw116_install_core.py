"""Card MW-116: the install's pure decisions about the reader agent file: its rendering from the shipped template and whether
a file is written. No file, no process. Synthetic text only."""
import _engine  # noqa: F401  (puts the engine folder on the import path)
import core_install

TEMPLATE = "---\nname: fresh-reader\nhooks:\n  PreToolUse:\n    - hooks:\n        - type: command\n          command: {{PYTHON}} {{FLAGS}} \"${CLAUDE_PROJECT_DIR}/{{BUNDLE}}/engine/engine/reader_hook.py\"\n---\nbody\n"


def test_the_template_is_rendered_with_the_python_command_the_flags_and_the_bundle():
    """Catches: a hook line with a placeholder left, a bundle folder other than the profile's, or flags other than the ones
    of the settings hooks."""
    text = core_install.render_reader_agent(TEMPLATE, "python", "tool")
    assert 'command: python -I -X utf8 "${CLAUDE_PROJECT_DIR}/tool/engine/engine/reader_hook.py"' in text
    assert "{{" not in text


def test_a_missing_file_is_written():
    """Catches: an install that writes no reader agent file."""
    assert core_install.reader_agent_action(None, "text") == "write"


def test_a_file_equal_to_the_rendering_is_kept_as_it_is():
    """Checks: nothing is rewritten when nothing changed."""
    assert core_install.reader_agent_action("text", "text") == "keep"


def test_a_file_the_owner_changed_is_kept():
    """Catches: a reinstall overwriting the owner's edit of the reader agent file."""
    assert core_install.reader_agent_action("text and an owner line", "text") == "keep"
