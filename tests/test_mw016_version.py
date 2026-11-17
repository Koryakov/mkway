"""Card MW-016, rows E1 to E6: the version in code (`VERSION`), the tag in git (the owner's). Synthetic roots and
scratch repositories under the pytest temp folder only; no test writes a tag in this repository."""
import json
import re

import pytest

from _engine import REPO, make_profile, write_profile
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


def test_the_start_block_shows_the_copys_version(tmp_path):
    """Checks: the start line shows the copy's own VERSION file, the ref when there is no sha, and no VERSION file as such. E2"""
    # the first line is mkway v<VERSION of the copy> (<sha or ref>); the version is the copy's own file, not the lock's
    # tag; with no sha the ref (the lock's version text) stands in.
    lock = {"version": "v9", "source_sha": "0123456789abcdef0123", "date": "2026-11-11"}
    root = _copy_task(tmp_path, version_text="7.8.9\n", lock=lock)
    assert _first_line(root).startswith("mkway v7.8.9 (0123456789ab); profile: mkway/profile.json")
    other = _copy_task(tmp_path / "b", version_text="0.1.0\n", lock=dict(lock, source_sha=None,
                                                                         version="unversioned"))
    assert _first_line(other).startswith("mkway v0.1.0 (unversioned); profile:")
    bare = _copy_task(tmp_path / "c", version_text=None, lock=lock)
    assert _first_line(bare).startswith("mkway (no VERSION file); profile:")


def _register_rows():
    rows = []
    for line in (REPO / "cards" / "REGISTER.md").read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and re.fullmatch(r"MW-\d{3}", cells[0]):
            rows.append((cells[0], cells[1], cells[2]))
    return rows


@pytest.mark.engine_repo  # MW-025: the changelog and the register are not in an installed copy
def test_the_changelog_covers_the_register():
    """Checks: every register card is one line in exactly one release section of the changelog, and the top heading is VERSION. E5"""
    # the top release heading is the VERSION text; each register card is one line with its id and its register title in
    # exactly one release section, so the file cannot drift from the register. Changed by MW-017 (E21): releases 0.2.0 and
    # 0.1.0; the sections together carry every register row once.
    text = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    version = (REPO / "VERSION").read_text(encoding="utf-8").strip()
    top, old = f"\n## {version}\n", "\n## 0.1.0\n"
    assert text.startswith("# Changelog")
    assert top in text
    assert old in text
    assert text.index(top) < text.index(old)
    lines = [x for x in text.splitlines() if x.startswith("- ")]
    rows = _register_rows()
    assert len(rows) >= 16
    missing = [card_id for card_id, title, _status in rows if sum(1 for x in lines if card_id in x and title in x) != 1]
    assert missing == [], f"{missing} is not in the changelog"
    assert len(lines) == len(rows)


@pytest.mark.engine_repo  # MW-025: the README is not in an installed copy
@pytest.mark.parametrize("word", [
    pytest.param("patch", id="patch"),
    pytest.param("minor", id="minor"),
    pytest.param("major", id="major"),
    pytest.param("`VERSION`", id="version-file"),
    pytest.param("`v<version>`", id="tag-form"),
    pytest.param("owner", id="owner"),
])
def test_the_readme_has_the_versioning_section(word):
    """Checks: the README has a Versioning section that names each bump rule, the tag form and the owner. E6"""
    text = (REPO / "README.md").read_text(encoding="utf-8")
    assert "\n## Versioning\n" in text
    section = text.split("\n## Versioning\n", 1)[1].split("\n## ", 1)[0]
    assert word in section
    assert "never writes a tag" in section or "never writes a git tag" in section
