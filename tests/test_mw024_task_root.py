"""Card MW-024: the commands find the task root below the git top. Synthetic scratch repositories only."""
import re
import subprocess

import pytest

import _docs as docs
from _engine import REPO, cli
import paths


def _repo(tmp_path, with_profile=True):
    top = tmp_path / "top"
    task = top / "task" / "T"
    (task / "sub" / "deep").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(top)], cwd=tmp_path, check=True)
    if with_profile:
        (task / "mkway").mkdir()
        (task / "mkway" / "profile.json").write_text("{}", encoding="utf-8")
    return top, task


def test_find_root_takes_the_nearest_folder_with_a_profile_below_the_git_top(tmp_path):
    """Checks: a task root two levels below the git top, run from that root, is the root and not the top (E1)."""
    top, task = _repo(tmp_path)
    assert paths.find_root(env={}, cwd=task) == task.resolve()


def test_find_root_walks_up_from_a_subfolder_of_the_task_root(tmp_path):
    """Checks: run from a folder inside the task root, the nearest folder up that holds mkway/profile.json wins (E2)."""
    top, task = _repo(tmp_path)
    assert paths.find_root(env={}, cwd=task / "sub" / "deep") == task.resolve()


def test_find_root_keeps_the_git_top_when_no_profile_exists(tmp_path):
    """Checks: with no mkway/profile.json up to the git top, the answer is the git top, as today (E3)."""
    top, task = _repo(tmp_path, with_profile=False)
    assert paths.find_root(env={}, cwd=task / "sub") == top.resolve()


def test_root_arg_and_project_dir_still_win(tmp_path):
    """Checks: --root and $CLAUDE_PROJECT_DIR beat the walk (E4)."""
    top, task = _repo(tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    assert paths.find_root(env={}, root_arg=str(other), cwd=task) == other.resolve()
    assert paths.find_root(env={"CLAUDE_PROJECT_DIR": str(top)}, cwd=task) == top.resolve()


def test_commands_at_a_root_without_an_install_say_so_in_one_line(tmp_path):
    """Catches: a command at a root with no install that prints more than one line, a traceback or no fix (E5)."""
    # check at a root with no install: exit 1, one line naming the root and the fix, no traceback; a command that needs
    # the profile names the root and the fix too
    root = tmp_path / "bare"
    root.mkdir()
    code, out, err = cli(root, "check")
    assert code == 1
    text = (out + err).strip()
    assert len(text.splitlines()) == 1
    assert "Traceback" not in text
    assert str(root.resolve()) in text
    assert "--root <task folder>" in text
    code, out, err = cli(root, "board")
    assert code != 0
    assert str(root.resolve()) in (out + err)
    assert "--root <task folder>" in (out + err)


@pytest.mark.engine_repo  # MW-025: the register, changelog and README are not in an installed copy
def test_register_changelog_version_and_readme_name_the_card(tmp_path):
    """Checks: the register row, the changelog section, VERSION and the README line name the card (E6)."""
    register = (REPO / "cards" / "REGISTER.md").read_text(encoding="utf-8")
    assert re.search(r"^\| MW-024 \|.*`cards/MW-024-[a-z0-9-]+`", register, re.M)
    text = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "MW-024" in docs.changelog_section(text, "MW-024")
    assert list((REPO / "cards").glob("MW-024-*/CARD.md"))
    docs.assert_version_file()
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    # the register row, the `## 0.2.1` section above `## 0.2.0`, VERSION 0.2.1 and the README line
    assert "below the repository top" in readme
    assert "CLAUDE_PROJECT_DIR" in readme
