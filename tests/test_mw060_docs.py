"""Card MW-060: the README, the register and the changelog state the rule «commit_tests tests the tree git will commit».
Synthetic text only."""
import pytest

from _engine import REPO

pytestmark = pytest.mark.engine_repo

TITLE = "commit_tests tests the tree git will commit"
TREE_NEEDLES = ("the tree git will commit", "HEAD plus the named paths", "the index plus the named paths",
                "every modified tracked file", "untracked", "`gate_commit`", "tree it built")


@pytest.mark.parametrize("needle", [pytest.param(n, id=n.replace(" ", "-").replace("`", "")) for n in TREE_NEEDLES])
def test_the_readme_states_which_tree_each_commit_form_tests(needle):
    """Checks: each commit form's tree rule is written in the README section on tests before a commit (E12)."""
    text = (REPO / "README.md").read_text(encoding="utf-8")
    body = text.split("## Tests before a commit", 1)[1].split("\n## ", 1)[0]
    assert needle in body


def test_register_changelog_and_card_name_the_card():
    """Checks: a register row, a CHANGELOG line under the top section, the card folder; VERSION is not changed here (E13)."""
    register = (REPO / "cards" / "REGISTER.md").read_text(encoding="utf-8")
    assert f"| MW-060 | {TITLE} |" in register
    assert (REPO / "cards" / "MW-060-taken-tree" / "CARD.md").is_file()
    changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    top = changelog.split("\n## ")[1]
    assert f"MW-060: {TITLE}" in top
    assert top.split("\n")[0].strip() == (REPO / "VERSION").read_text(encoding="utf-8").strip()
