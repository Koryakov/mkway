"""Card MW-035: install finishes its own commit in one correct step. A stale `engine/` ignore line of an earlier install
is removed; the commit step takes only install's own paths, whatever else is staged; without `--commit` install prints
one line to paste; the profile key `commit.message_prefix` starts the message. Synthetic scratch repositories under the
pytest temp folder only."""
import json
import re

import pytest

from _engine import REPO
from test_install import clean_env, git, make_source, make_task, mkway
import profiles

pytestmark = pytest.mark.engine_repo

COMMIT_ENV = {"GIT_AUTHOR_NAME": "mkway-test", "GIT_AUTHOR_EMAIL": "mkway-test", "GIT_COMMITTER_NAME": "mkway-test",
              "GIT_COMMITTER_EMAIL": "mkway-test"}
PATHS = ".claude/settings.json mkway"


def _version():
    return (REPO / "VERSION").read_text(encoding="utf-8").strip()


def _set_prefix(task, prefix):
    path = task / "mkway" / "profile.json"
    profile = json.loads(path.read_text(encoding="utf-8"))
    profile["commit"] = {"message_prefix": prefix}
    path.write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")


def test_a_stale_engine_ignore_line_is_removed_and_the_others_stay(tmp_path):
    """E1: the exact line `engine/` goes, one report line says so; `locks/`, a custom line and lines that only look
    like it (`engine/cache/`, `engine.log`) stay. Catches: a copy left untracked by an earlier install's line."""
    src = make_source(tmp_path, vcs="none")
    task = make_task(tmp_path, vcs="git")
    (task / "mkway").mkdir()
    (task / "mkway" / ".gitignore").write_text("engine/\nlocks/\nmine.tmp\nengine/cache/\nengine.log\n",
                                               encoding="utf-8")
    proc = mkway(task, clean_env(tmp_path), "install", "--from", str(src))
    assert proc.returncode == 0, proc.stderr + proc.stdout
    lines = (task / "mkway" / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "engine/" not in lines
    for kept in ("locks/", "mine.tmp", "engine/cache/", "engine.log", "state/"):
        assert kept in lines, (kept, lines)
    out = proc.stdout.splitlines()
    assert "ignore: removed engine/ (from an earlier install)" in out
    assert not [line for line in out if "still ignores engine/" in line]
    git(task, "add", "-A")
    assert "mkway/engine/mkway.py" in git(task, "diff", "--cached", "--name-only").split()


def test_install_commit_takes_only_its_own_paths(tmp_path):
    """E2: another file is staged (as a builder's files are); `install --commit` commits only the settings file and
    the bundle and leaves the other file staged. Catches: a plain `git commit` taking the whole index."""
    src = make_source(tmp_path, vcs="none")
    task = make_task(tmp_path, vcs="git")
    (task / "base.txt").write_text("b\n", encoding="utf-8")
    git(task, "add", "base.txt")
    git(task, "commit", "-q", "-m", "base")
    (task / "foreign.txt").write_text("f\n", encoding="utf-8")
    git(task, "add", "foreign.txt")
    done = mkway(task, clean_env(tmp_path, **COMMIT_ENV), "install", "--from", str(src), "--commit")
    assert done.returncode == 0, done.stderr + done.stdout
    taken = git(task, "show", "--name-only", "--format=", "HEAD").split()
    assert "foreign.txt" not in taken
    assert ".claude/settings.json" in taken and "mkway/engine/mkway.py" in taken and "mkway/.gitignore" in taken
    assert git(task, "diff", "--cached", "--name-only").split() == ["foreign.txt"]


def test_the_printed_commit_step_is_one_line_without_a_leading_space(tmp_path):
    """E3: without `--commit` install prints ONE line to paste: add and commit joined with `;`, the commit limited to
    install's paths, no leading space (the owner pastes it into PowerShell or bash)."""
    src = make_source(tmp_path, vcs="none")
    task = make_task(tmp_path, vcs="git")
    proc = mkway(task, clean_env(tmp_path), "install", "--from", str(src))
    assert proc.returncode == 0, proc.stderr + proc.stdout
    lines = proc.stdout.splitlines()
    mine = [line for line in lines if "git commit" in line or "git add" in line]
    assert mine == [f'git add {PATHS}; git commit -m "mkway {_version()}: install" -- {PATHS}'], mine
    assert all(line == line.lstrip() for line in lines), lines
    assert lines[-1] == mine[0]


def test_the_message_prefix_starts_the_install_message(tmp_path):
    """E4: with `commit.message_prefix` `#10536` the printed line and the commit read `#10536 mkway <version>:
    install`; with the key unset the message is as before."""
    src = make_source(tmp_path, vcs="none")
    task = make_task(tmp_path, vcs="git")
    env = clean_env(tmp_path, **COMMIT_ENV)
    assert mkway(task, env, "install", "--from", str(src)).returncode == 0
    _set_prefix(task, "#10536")
    shown = mkway(task, env, "install", "--from", str(src))
    assert shown.returncode == 0, shown.stderr + shown.stdout
    assert f'git commit -m "#10536 mkway {_version()}: install" -- {PATHS}' in shown.stdout.splitlines()[-1]
    done = mkway(task, env, "install", "--from", str(src), "--commit")
    assert done.returncode == 0, done.stderr + done.stdout
    assert git(task, "log", "-1", "--format=%s").strip() == f"#10536 mkway {_version()}: install"


def test_the_message_prefix_key_is_in_the_schema_and_keys():
    """E5: `commit.message_prefix` is a string key of the schema that refuses spaces and shell characters (the prefix
    is printed into a line the owner pastes) and has a line of KEYS.md."""
    base = {"commit": {"message_prefix": "#10536"}}
    assert not any("message_prefix" in e for e in profiles.validate(base)), profiles.validate(base)
    for bad in ("a b", 'a"b', "a`b", "a$b", "a\nb", ""):
        errors = profiles.validate({"commit": {"message_prefix": bad}})
        assert any("message_prefix" in e for e in errors), (bad, errors)
    keys = (REPO / "engine" / "KEYS.md").read_text(encoding="utf-8")
    assert re.search(r"^\| `commit\.message_prefix` \| in schema now \| `commit\.message_prefix` \|", keys, re.M)


def test_readme_register_changelog_and_card_name_the_card():
    """E7: the README install section shows `--commit` as the one-step way; register row; a line under `## 0.2.7`;
    the card; VERSION still 0.2.7."""
    text = (REPO / "README.md").read_text(encoding="utf-8")
    section = text.split("\n## Use in a task\n", 1)[1].split("\n## ", 1)[0]
    numbered = [line for line in section.splitlines() if re.match(r"^[1-9]\. ", line)]
    assert len(numbered) == 5, numbered
    assert "--commit" in numbered[1] and "one step" in numbered[1].lower(), numbered[1]
    assert "commit.message_prefix" in section
    register = (REPO / "cards" / "REGISTER.md").read_text(encoding="utf-8")
    assert re.search(r"^\| MW-035 \|.*`cards/MW-035-[a-z0-9-]+`", register, re.M)
    log = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "MW-035" in log.split("\n## 0.2.7\n", 1)[1].split("\n## ", 1)[0]
    assert list((REPO / "cards").glob("MW-035-*/CARD.md"))
    assert _version() == "0.2.7"
