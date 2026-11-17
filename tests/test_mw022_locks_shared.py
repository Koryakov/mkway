"""Moved by MW-063; see cards/MW-063-lock-core/case_map.md. One documentation check stays here: `test_mw025_copy_check` reads its
name and its `engine_repo` marker from this file."""
import pytest

import _docs as docs


@pytest.mark.engine_repo  # MW-025: the README, changelog and register are not in an installed copy
def test_the_readme_changelog_register_and_keys_name_the_card(tmp_path):
    """Checks: the README hold section, the changelog, the register and KEYS.md name the card, and VERSION is valid (E9, E10)."""
    from _engine import REPO
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    assert "a hold reaches every worktree of the repository" in readme
    changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "- MW-022: Locks reach every worktree" in docs.changelog_section(changelog, "MW-022").splitlines()
    register = (REPO / "cards" / "REGISTER.md").read_text(encoding="utf-8")
    assert "| MW-022 | Locks reach every worktree |" in register
    keys = (REPO / "engine" / "KEYS.md").read_text(encoding="utf-8")
    assert "lock marker folder" in keys
    assert "MW-022" in keys
    docs.assert_version_file()
