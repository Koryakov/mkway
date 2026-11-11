"""Card MW-016, rows E1 to E6: the version in code (`VERSION`), the tag in git (the owner's). Synthetic roots and
scratch repositories under the pytest temp folder only; no test writes a tag in this repository."""
import json
import re

from _engine import REPO, make_profile, write_profile
from test_install import clean_env, git, make_source, make_task, mkway
import install
import startline

SEMVER = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)")


def _copy_task(tmp_path, *, version_text, lock):
    """A task root as an install leaves it, with a small copy that holds a `VERSION` file (or none)."""
    root = tmp_path / "task"
    write_profile(root, make_profile())
    copy = root / "mkway" / "engine"
    (copy / "engine").mkdir(parents=True)
    (copy / "engine" / "a.py").write_text("A = 1\n", encoding="utf-8")
    if version_text is not None:
        (copy / "VERSION").write_text(version_text, encoding="utf-8")
    (root / "mkway" / "mkway.lock").write_text(json.dumps(dict(lock, hash=install.copy_hash(copy))), encoding="utf-8")
    return root


def _first_line(root):
    profile = json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))
    return startline.render(root, root / "mkway" / "profile.json", profile, [], [], {}).splitlines()[0]


def test_the_version_file_is_semver():
    """E1: `VERSION` at the root holds `0.1.0`, one line."""
    text = (REPO / "VERSION").read_text(encoding="utf-8")
    assert text.strip() == "0.1.0" and SEMVER.fullmatch(text.strip())


def test_the_start_block_shows_the_copys_version(tmp_path):
    """E2: the first line is `mkway v<VERSION of the copy> (<sha or ref>)`; the version is the copy's own file, not
    the lock's tag; with no sha the ref (the lock's version text) stands in."""
    lock = {"version": "v9", "source_sha": "0123456789abcdef0123", "date": "2026-11-11"}
    root = _copy_task(tmp_path, version_text="7.8.9\n", lock=lock)
    assert _first_line(root).startswith("mkway v7.8.9 (0123456789ab); profile: mkway/profile.json")
    other = _copy_task(tmp_path / "b", version_text="0.1.0\n", lock=dict(lock, source_sha=None,
                                                                         version="unversioned"))
    assert _first_line(other).startswith("mkway v0.1.0 (unversioned); profile:")
    bare = _copy_task(tmp_path / "c", version_text=None, lock=lock)
    assert _first_line(bare).startswith("mkway (no VERSION file); profile:")


def test_the_lock_carries_the_version(tmp_path):
    """E3: install copies `VERSION` and writes its text into the lock as `semver`, beside the sha."""
    src = make_source(tmp_path, vcs="git")
    (src / "VERSION").write_text("3.4.5\n", encoding="utf-8")
    git(src, "add", "-A")
    git(src, "commit", "-q", "-m", "a newer version")
    task = make_task(tmp_path, vcs="none")
    proc = mkway(task, clean_env(tmp_path), "install", "--from", str(src), "--vcs", "none")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    lock = json.loads((task / "mkway" / "mkway.lock").read_text(encoding="utf-8"))
    assert lock["semver"] == "3.4.5" and lock["source_sha"] == git(src, "rev-parse", "HEAD").strip()
    assert (task / "mkway" / "engine" / "VERSION").read_text(encoding="utf-8").strip() == "3.4.5"


def _scratch_repo(tmp_path, version="0.1.0"):
    root = tmp_path / "scratch"
    root.mkdir(parents=True)
    git(root, "init", "-q")
    (root / "VERSION").write_text(version + "\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "scratch")
    return root


def test_check_warns_on_a_missing_or_a_different_tag(tmp_path):
    """E4: without a tag at HEAD, and with a tag that is not `v<version>`, the line is a warning that names the
    expected tag; with the right tag it says so; a tag is never written; no VERSION file, no line."""
    root = _scratch_repo(tmp_path)
    env = {}
    line = install.version_tag_line(root, env)
    assert line.startswith("version tag: warning") and "v0.1.0" in line and "missing" in line
    git(root, "tag", "v0.0.9")  # the test makes its own tag in its own scratch repo
    line = install.version_tag_line(root, env)
    assert line.startswith("version tag: warning") and "v0.1.0" in line and "v0.0.9" in line and "differs" in line
    git(root, "tag", "v0.1.0")
    assert install.version_tag_line(root, env) == "version tag: v0.1.0 at HEAD matches VERSION"
    assert sorted(git(root, "tag").split()) == ["v0.0.9", "v0.1.0"]  # the line itself wrote nothing
    (root / "VERSION").unlink()
    assert install.version_tag_line(root, env) is None
    chat = install.version_tag_line(_scratch_repo(tmp_path / "x"), {"CLAUDECODE": "1"})
    assert chat.startswith("version tag: not compared inside a Claude chat")


def test_check_prints_the_tag_line(tmp_path):
    """E4: `mkway check` prints the line (a task root with a `VERSION` file, in git, no tag)."""
    from test_install import make_light_source
    src = make_light_source(tmp_path)
    task = make_task(tmp_path, vcs="git")
    (task / "VERSION").write_text("0.1.0\n", encoding="utf-8")
    git(task, "add", "-A")
    git(task, "commit", "-q", "-m", "task")
    env = {k: v for k, v in clean_env(tmp_path).items() if k != "CLAUDECODE"}
    assert mkway(task, env, "install", "--from", str(src), "--vcs", "git").returncode == 0
    proc = mkway(task, env, "check")
    assert "version tag: warning" in proc.stdout and "v0.1.0" in proc.stdout, proc.stdout + proc.stderr
    assert git(task, "tag").strip() == ""


def _register_rows():
    rows = []
    for line in (REPO / "cards" / "REGISTER.md").read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and re.fullmatch(r"MW-\d{3}", cells[0]):
            rows.append((cells[0], cells[1], cells[2]))
    return rows


def test_the_changelog_covers_the_register():
    """E5: `## 0.1.0`, and each register card (every status: a register row exists once the card is in the tree) is
    one line with its id and its register title, so the file cannot drift from the register."""
    text = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    assert text.startswith("# Changelog") and "\n## 0.1.0\n" in text
    section = text.split("\n## 0.1.0\n", 1)[1].split("\n## ", 1)[0]
    lines = [x for x in section.splitlines() if x.startswith("- ")]
    rows = _register_rows()
    assert len(rows) >= 16
    for card_id, title, _status in rows:
        assert any(card_id in x and title in x for x in lines), f"{card_id} {title!r} is not in the changelog"
    assert len(lines) == len(rows)


def test_the_readme_has_the_versioning_section():
    """E6: a `## Versioning` section: the three bump rules and the owner's tags."""
    text = (REPO / "README.md").read_text(encoding="utf-8")
    assert "\n## Versioning\n" in text
    section = text.split("\n## Versioning\n", 1)[1].split("\n## ", 1)[0]
    for word in ("patch", "minor", "major", "`VERSION`", "`v<version>`", "owner"):
        assert word in section, word
    assert "never writes a tag" in section or "never writes a git tag" in section
