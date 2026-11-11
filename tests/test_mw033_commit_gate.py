"""Card MW-033: the commit gate takes the open card's id anywhere in the message, whatever the prefix is now, and its
refusals name the way out. Synthetic task roots only, real throwaway git repositories."""
import json

import pytest

from _commit_fixture import check, make_task, reason, stage, touch, work
from _engine import write_profile


def _task(tmp_path, prefix=None, **over):
    root = make_task(tmp_path, card_paths="", **over)
    if prefix:  # the prefix changed after the card was made: CARD-001 stays the open card
        path = root / "mkway" / "profile.json"
        profile = json.loads(path.read_text(encoding="utf-8"))
        profile["ids"] = {"card_prefix": prefix}
        write_profile(root, profile)
    work(root, "src/a.py")
    touch(root, "src/a.py")
    stage(root, "src/a.py")
    return root


def test_the_id_may_stand_anywhere_in_the_subject(tmp_path):
    """E1: the open card's id as a whole word anywhere in the subject passes (`#10536 CARD-001 text`,
    `CARD-001 #10536 text`); no id, a longer number, or another card's id is refused `commit-message-card`.
    Catches: a rule that wants the id first, or that lets CARD-0011 pass for CARD-001."""
    root = _task(tmp_path)
    for message in ("#10536 CARD-001 add the thing", "CARD-001 #10536 add the thing", "#10536 (CARD-001) add"):
        assert reason(check(root, f"git commit -m '{message}'")) == "allow", message
    for message in ("#10536 add the thing", "#10536 CARD-0011 add the thing", "#10536 CARD-002 add the thing"):
        assert reason(check(root, f"git commit -m '{message}'")) == "commit-message-card", message


def test_the_open_card_id_passes_whatever_the_prefix_is_now(tmp_path):
    """E2: the profile prefix is now DD, the open card is CARD-001, made before the change: the message
    `#10536 CARD-001 text` is allowed; a message with no id, or with another card's id, is still refused.
    Catches: cards made under an earlier prefix that can never commit."""
    root = _task(tmp_path, prefix="DD")
    assert reason(check(root, "git commit -m '#10536 CARD-001 add the thing'")) == "allow"
    assert reason(check(root, "git commit -m 'DD-007 add the thing'")) == "commit-message-card"
    assert reason(check(root, "git commit -m '#10536 add the thing'")) == "commit-message-card"
    assert reason(check(root, "git commit -m '#10536 CARD-0011 add the thing'")) == "commit-message-card"


def test_the_refusal_says_the_id_may_stand_anywhere_in_the_first_line(tmp_path):
    """E3: the `commit-message-card` refusal says to put the card id anywhere in the first line, with an example.
    Catches: a refusal that tells the author to start the message with the id."""
    v = check(_task(tmp_path), "git commit -m '#10536 add the thing'")
    assert v.reason_id == "commit-message-card"
    assert 'put the card id anywhere in the first line, for example -m "CARD-001 <what changed>"' in v.message


def test_a_chained_add_and_commit_says_to_use_two_calls(tmp_path):
    """E4: a chained add and commit (`&&` or `;`) refuses `commit-unreadable` and names the fix: run git add and
    git commit as two separate calls. Catches: a refusal that leaves the author guessing."""
    root = _task(tmp_path)
    for join in ("&&", ";"):
        v = check(root, f"git add src/a.py {join} git commit -m 'CARD-001 add the thing'")
        assert v.kind == "refuse" and v.reason_id == "commit-unreadable", join
        assert "run git add and git commit as two separate calls" in v.message, join


@pytest.mark.engine_repo  # reads the repository's own README, register and changelog
def test_readme_register_changelog_and_card_name_the_card():
    """E5: the README says each of the two rules in a line; register row, a line under the top changelog section
    (`## 0.2.7` on master, moved from 0.2.6 when ported), the card folder; VERSION is untouched (0.2.7)."""
    import re
    from _engine import REPO
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    assert "anywhere in the first line" in readme and "two separate calls" in readme
    register = (REPO / "cards" / "REGISTER.md").read_text(encoding="utf-8")
    assert re.search(r"^\| MW-033 \| .*\|.*`cards/MW-033-[a-z0-9-]+`", register, re.M)
    changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    top = changelog.split("\n## 0.2.7\n", 1)[1].split("\n## ", 1)[0]
    assert re.search(r"^- MW-033: ", top, re.M)
    assert list((REPO / "cards").glob("MW-033-*/CARD.md"))
    assert (REPO / "VERSION").read_text(encoding="utf-8").strip() == "0.2.7"
