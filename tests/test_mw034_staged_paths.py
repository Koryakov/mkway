"""Card MW-034: the commit check reads what the commit takes (the staged list always, plus the files a `--`, `-a` or
`-i` form names); there is no per-file write record; one builder per task root (`take-root-busy`). Synthetic task
roots only, real throwaway git repositories."""
import re

import pytest

from _commit_fixture import COMMIT, check, git, make_task, reason, stage, work
from _engine import cli
import gate_lock
import records
import register
import json

CLI = "python mkway/engine/mkway.py card"


def _lock(root, command, session):
    from _engine import gate_call
    v = gate_call(gate_lock.check, root, tool="Bash", tool_input={"command": command}, session=session)
    return v


def _profile(root):
    return json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))


def test_a_staged_file_outside_the_paths_is_refused(tmp_path):
    """E1: a file staged outside the held card's Paths is refused `file-not-in-card`, naming it; a plain commit of
    files inside passes. Catches: a commit that takes a file the card was never opened for."""
    root = make_task(tmp_path, card_paths="`src/`")
    work(root, "src/a.py")
    work(root, "other/b.py")
    stage(root, "src/a.py", "other/b.py")
    v = check(root, COMMIT)
    assert v.reason_id == "file-not-in-card" and "other/b.py" in v.message and "src/a.py" not in v.message
    git(root, "restore", "--staged", "--", "other/b.py")
    assert reason(check(root, COMMIT)) == "allow"


def test_files_a_script_wrote_inside_the_paths_are_allowed(tmp_path):
    """E2: files written with no Write or Edit record at all (a script's `python x.py` writes) commit when they lie
    inside the Paths: there is no `ride-in-file` rule. Catches: a refusal of a builder's own script output."""
    root = make_task(tmp_path, card_paths="`src/`")
    many = [f"src/gen{i}.py" for i in range(12)]
    for rel in many:
        work(root, rel)
    stage(root, *many)
    assert reason(check(root, COMMIT)) == "allow"
    assert reason(check(root, "git commit -m 'CARD-001 x' -- src/gen0.py")) == "allow"


def test_a_file_staged_earlier_outside_the_paths_is_refused_in_every_form(tmp_path):
    """E3: the staged list is read for every commit form: a file outside the Paths staged by an earlier `git add`
    is refused even when the commit names only inside files after `--` (and under `-i`, `-a`, `--amend`); a plain
    commit after a separate `git add -A` is refused too. Catches: a gate that trusts the paths typed in the command."""
    root = make_task(tmp_path, card_paths="`src/`")
    work(root, "src/a.py")
    work(root, "other/b.py")
    stage(root, "src/a.py", "other/b.py")
    for command in ("git commit -m 'CARD-001 x' -- src/a.py", "git commit -i -m 'CARD-001 x' -- src/a.py",
                    "git commit -a -m 'CARD-001 x'", "git commit --amend -m 'CARD-001 x'", COMMIT):
        v = check(root, command)
        assert v.reason_id == "file-not-in-card" and "other/b.py" in v.message, command
    git(root, "restore", "--staged", "--", "other/b.py")
    assert reason(check(root, "git commit -m 'CARD-001 x' -- src/a.py")) == "allow"
    git(root, "add", "-A")  # a separate `git add -A` sweeps the unstaged outside file in
    assert reason(check(root, COMMIT)) == "file-not-in-card"


def test_a_second_session_cannot_take_a_card_in_a_busy_root(tmp_path):
    """E4: while another session holds a card (open) in the task root, a `card take` of any other card by a second
    session is refused `take-root-busy`, naming the holder (8-char prefix), its card and the way out. Catches: two
    builders in one worktree and one index."""
    root = make_task(tmp_path, session="abcdefgh-1234")
    assert cli(root, "card", "new", "Second", session=True)[0] == 0
    v = _lock(root, f"{CLI} take CARD-002", "zzzzzzzz-9999")
    assert v.kind == "refuse" and v.reason_id == "take-root-busy"
    assert "abcdefgh" in v.message and "abcdefgh-1234" not in v.message and "CARD-001" in v.message
    assert "own worktree" in v.message and "hand" in v.message


def test_the_same_session_may_take_its_own_card_again(tmp_path):
    """E5: the session that holds the open card takes it again without a refusal. Catches: a busy-root rule that
    locks the holder out of its own card."""
    root = make_task(tmp_path, session="s1")
    assert reason(_lock(root, f"{CLI} take CARD-001", "s1")) == "allow"


def test_a_take_after_the_holders_card_closed_is_allowed(tmp_path):
    """E6: once the holder's card is closed (or released) the root is free: a second session takes a card.
    Catches: a root that stays busy for good."""
    root = make_task(tmp_path, session="s1")
    assert cli(root, "card", "new", "Second", session=True)[0] == 0
    assert reason(_lock(root, f"{CLI} take CARD-002", "s2")) == "take-root-busy"
    register.set_status(root, _profile(root), "CARD-001", "closed")
    assert reason(_lock(root, f"{CLI} take CARD-002", "s2")) == "allow"


@pytest.mark.engine_repo  # reads the repository's own README, register and changelog
def test_readme_register_changelog_and_card_name_the_card():
    """E7: the README no longer names the write record or `ride-in-file`; register row, a line under `## 0.2.7`, the
    card folder; VERSION is untouched (0.2.7)."""
    from _engine import REPO
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    assert "ride-in-file" not in readme and "touched.jsonl" not in readme and "touched.edit" not in readme
    assert "take-root-busy" in readme
    register_text = (REPO / "cards" / "REGISTER.md").read_text(encoding="utf-8")
    assert re.search(r"^\| MW-034 \| .*\|.*`cards/MW-034-[a-z0-9-]+`", register_text, re.M)
    changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    top = changelog.split("\n## 0.2.7\n", 1)[1].split("\n## ", 1)[0]
    assert re.search(r"^- MW-034: ", top, re.M)
    assert list((REPO / "cards").glob("MW-034-*/CARD.md"))
    assert (REPO / "VERSION").read_text(encoding="utf-8").strip() == "0.2.7"
