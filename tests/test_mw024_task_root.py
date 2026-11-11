"""Card MW-024: the commands find the task root below the git top. Synthetic scratch repositories only."""
import re
import subprocess

import pytest

from _engine import REPO, cli
import paths


def _repo(tmp_path, with_profile=True):
    top = tmp_path / "top"
    task = top / "task" / "T"
    (task / "sub" / "deep").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(top)], check=True)
    if with_profile:
        (task / "mkway").mkdir()
        (task / "mkway" / "profile.json").write_text("{}", encoding="utf-8")
    return top, task


def test_find_root_takes_the_nearest_folder_with_a_profile_below_the_git_top(tmp_path):
    """E1: a task root two levels below the git top, run from that root: the root, not the top."""
    top, task = _repo(tmp_path)
    assert paths.find_root(env={}, cwd=task) == task.resolve()


def test_find_root_walks_up_from_a_subfolder_of_the_task_root(tmp_path):
    """E2: run from a folder inside the task root: the nearest folder up that holds mkway/profile.json."""
    top, task = _repo(tmp_path)
    assert paths.find_root(env={}, cwd=task / "sub" / "deep") == task.resolve()


def test_find_root_keeps_the_git_top_when_no_profile_exists(tmp_path):
    """E3: no mkway/profile.json up to the git top: today's answer, the git top."""
    top, task = _repo(tmp_path, with_profile=False)
    assert paths.find_root(env={}, cwd=task / "sub") == top.resolve()


def test_root_arg_and_project_dir_still_win(tmp_path):
    """E4: --root and $CLAUDE_PROJECT_DIR beat the walk."""
    top, task = _repo(tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    assert paths.find_root(env={}, root_arg=str(other), cwd=task) == other.resolve()
    assert paths.find_root(env={"CLAUDE_PROJECT_DIR": str(top)}, cwd=task) == top.resolve()


def test_commands_at_a_root_without_an_install_say_so_in_one_line(tmp_path):
    """E5: `check` at a root with no install: exit 1, one line naming the root and the fix, no traceback; a command
    that needs the profile names the root and the fix too."""
    root = tmp_path / "bare"
    root.mkdir()
    code, out, err = cli(root, "check")
    assert code == 1
    text = (out + err).strip()
    assert len(text.splitlines()) == 1 and "Traceback" not in text
    assert str(root.resolve()) in text and "--root <task folder>" in text
    code, out, err = cli(root, "board")
    assert code != 0 and str(root.resolve()) in (out + err) and "--root <task folder>" in (out + err)


@pytest.mark.engine_repo  # MW-025: the register, changelog and README are not in an installed copy
def test_register_changelog_version_and_readme_name_the_card(tmp_path):
    """E6: the register row, `## 0.2.1` above `## 0.2.0` with the card, VERSION 0.2.1, the README line."""
    register = (REPO / "cards" / "REGISTER.md").read_text(encoding="utf-8")
    assert re.search(r"^\| MW-024 \|.*`cards/MW-024-[a-z0-9-]+`", register, re.M)
    text = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    assert text.index("\n## 0.2.1\n") < text.index("\n## 0.2.0\n")
    assert "MW-024" in text.split("\n## 0.2.1\n", 1)[1].split("\n## ", 1)[0]
    assert list((REPO / "cards").glob("MW-024-*/CARD.md"))
    assert (REPO / "VERSION").read_text(encoding="utf-8").strip() == "0.2.7"  # changed by MW-027: 0.2.7
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    assert "below the repository top" in readme and "CLAUDE_PROJECT_DIR" in readme
