"""Card MW-028: a lead authors its own proposed cards, and a root below the git top reads vcs git. Synthetic roots and
scratch repositories only."""
import re
import subprocess

import pytest

from _engine import REPO, cli, gate_call, make_profile
from _mw017 import lead_root, new_card, register_lead, row_of, session_run
from test_install import GIT_ID, make_light_source
import gate_lead
import gate_subtask
import install
import startline


def _file(root, card, name):
    return row_of(root, card)["folder"].strip("`") + "/" + name


def _lead_edit(root, session, path):
    return gate_call(gate_lead.edit, root, tool="Write", tool_input={"file_path": path, "content": "x"}, session=session)


def _subtask(root, session, path):
    return gate_call(gate_subtask.check, root, tool="Write", tool_input={"file_path": path}, session=session)


@pytest.fixture
def world(tmp_path):
    root = lead_root(tmp_path)
    register_lead(root, "lead-a")
    register_lead(root, "lead-b")
    mine = new_card(root, "lead-a", "Mine")
    theirs = new_card(root, "lead-b", "Theirs")
    return root, mine, theirs


def test_a_lead_writes_card_and_order_of_its_proposed_card(world):
    """E1: a registered lead writes `<folder>/CARD.md` and `<folder>/ORDER.md` of a card whose Ordered by is its own
    session id while the card is `proposed`, with no card held: the lead gate and the subtask gate both allow."""
    root, mine, _theirs = world
    assert row_of(root, mine)["status"] == "proposed"
    for name in ("CARD.md", "ORDER.md"):
        path = _file(root, mine, name)
        assert _lead_edit(root, "lead-a", path).kind == "allow", name
        assert _subtask(root, "lead-a", path).kind == "allow", name


def test_after_open_card_is_sealed_to_the_lead_and_order_stays_its_own(world):
    """E2: once the owner opens the card, the lead gate refuses `lead-no-edit` for CARD.md (the text names the card
    commands); ORDER.md stays the lead's in both gates."""
    root, mine, _theirs = world
    assert cli(root, "card", "open", mine)[0] == 0
    verdict = _lead_edit(root, "lead-a", _file(root, mine, "CARD.md"))
    assert verdict.kind == "refuse" and verdict.reason_id == "lead-no-edit"
    assert _lead_edit(root, "lead-a", _file(root, mine, "ORDER.md")).kind == "allow"
    assert _subtask(root, "lead-a", _file(root, mine, "ORDER.md")).kind == "allow"


def test_another_leads_proposed_card_stays_refused(world):
    """E3: the CARD.md and the ORDER.md of a proposed card another lead ordered: `lead-no-edit` in the lead gate, and
    `no-open-card` for the order file in the subtask gate."""
    root, _mine, theirs = world
    for name in ("CARD.md", "ORDER.md"):
        verdict = _lead_edit(root, "lead-a", _file(root, theirs, name))
        assert verdict.kind == "refuse" and verdict.reason_id == "lead-no-edit", name
    verdict = _subtask(root, "lead-a", _file(root, theirs, "ORDER.md"))
    assert verdict.kind == "refuse" and verdict.reason_id == "no-open-card"


def test_a_builder_on_a_proposed_card_is_unchanged(world):
    """E4: a session that is no lead and holds no card still gets `no-open-card` for the order file of a proposed card,
    and the lead gate does not judge it."""
    root, mine, _theirs = world
    path = _file(root, mine, "ORDER.md")
    verdict = _subtask(root, "builder-1", path)
    assert verdict.kind == "refuse" and verdict.reason_id == "no-open-card"
    assert _lead_edit(root, "builder-1", path).kind == "allow"


def test_a_lead_opens_its_own_card_with_approver_orderer(world):
    """E5: with `cards.approver: orderer` a registered lead's `card open` of a card it ordered passes (the hook, then
    the CLI): the register says open and records the Paths; with the default owner-only approver it is refused
    `owner-only-command` by the hook."""
    root, mine, _theirs = world
    code, out, err = session_run(root, "lead-a", "card", "open", mine)
    assert code == 0, err
    assert row_of(root, mine)["status"] == "open"
    owner_only = lead_root(root.parent, name="owner-only", cards={})
    register_lead(owner_only, "lead-a")
    card = new_card(owner_only, "lead-a", "Mine")
    code, out, err = session_run(owner_only, "lead-a", "card", "open", card)
    assert code is None and err.startswith("owner-only-command"), err
    assert row_of(owner_only, card)["status"] == "proposed"


def test_a_lead_never_opens_an_owner_ordered_card_or_another_leads(world):
    """E6: with `cards.approver: orderer` a lead's `card open` of an owner-ordered card or another lead's card is
    refused `owner-only-command`; a session that is no lead is refused for its own card too. Nothing changes."""
    root, _mine, theirs = world
    assert cli(root, "card", "new", "Owned")[0] == 0
    owned = "CARD-003"
    assert row_of(root, owned)["status"] == "proposed"
    for session, card in (("lead-a", owned), ("lead-a", theirs)):
        code, out, err = session_run(root, session, "card", "open", card)
        assert code is None and err.startswith("owner-only-command"), (session, card, err)
    built = new_card(root, "builder-1", "Builder card")
    code, out, err = session_run(root, "builder-1", "card", "open", built)
    assert code is None and err.startswith("owner-only-command"), err
    assert {row_of(root, c)["status"] for c in (owned, theirs, built)} == {"proposed"}


def _worktree_root(tmp_path):
    """A linked worktree with a sparse cone and an untracked task folder below its top (the shape of the first real
    install): `main/` holds the commit, `wt/` the linked worktree, the root is `wt/task/T`."""
    main, wt = tmp_path / "main", tmp_path / "wt"
    (main / "task" / "other").mkdir(parents=True)
    (main / "task" / "other" / "a.txt").write_text("a\n", encoding="utf-8")
    (main / "top.txt").write_text("t\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(main)], check=True)
    subprocess.run(["git", *GIT_ID, "-C", str(main), "add", "-A"], check=True)
    subprocess.run(["git", *GIT_ID, "-C", str(main), "commit", "-q", "-m", "base"], check=True)
    subprocess.run(["git", "-C", str(main), "worktree", "add", "-q", str(wt), "-b", "work"], check=True)
    subprocess.run(["git", "-C", str(wt), "sparse-checkout", "set", "--cone", "task"], check=True)
    root = wt / "task" / "T"
    root.mkdir(parents=True)
    return wt, root


def test_detect_vcs_answers_git_for_a_root_below_the_top_of_a_sparse_linked_worktree(tmp_path):
    """E7: the root is an untracked folder two levels below the top of a linked worktree with a sparse cone: git, not
    none. A folder that is in no git work tree is still none."""
    top, root = _worktree_root(tmp_path)
    assert install.git_top(root) == top.resolve()
    assert install.detect_vcs(root) == "git"
    assert install.detect_vcs(top) == "git"
    bare = tmp_path / "bare-folder"
    bare.mkdir()
    assert install.detect_vcs(bare) == "none"


def test_a_first_install_below_the_top_writes_vcs_git_and_the_ignore_file(tmp_path):
    """E8: `mkway install` at that root writes a starter profile with `vcs` git and the bundle `.gitignore`."""
    _top, root = _worktree_root(tmp_path)
    src = make_light_source(tmp_path)
    install.install(root, src)
    text = (root / "mkway" / "profile.json").read_text(encoding="utf-8")
    assert '"vcs": "git"' in text
    assert (root / "mkway" / ".gitignore").is_file()


def _block(root, vcs):
    profile = make_profile(vcs=vcs)
    return startline.render(root, root / "mkway" / "profile.json", profile, [], [], {})


def test_the_start_block_says_in_one_line_why_vcs_is_none(tmp_path):
    """E9: `vcs: none` keeps its words and adds one reason on the same line: the root is inside a git work tree (the
    profile says none: set `vcs` to `git`), or the root is in no git work tree."""
    top, root = _worktree_root(tmp_path)
    inside = [x for x in _block(root, "none").splitlines() if x.startswith("vcs:")]
    assert len(inside) == 1 and inside[0].startswith("vcs: none, every git step is off")
    assert "inside a git work tree" in inside[0] and "\"vcs\": \"git\"" in inside[0]
    bare = tmp_path / "bare-folder"
    bare.mkdir()
    outside = [x for x in _block(bare, "none").splitlines() if x.startswith("vcs:")]
    assert len(outside) == 1 and outside[0].startswith("vcs: none, every git step is off")
    assert "no git work tree" in outside[0]
    assert [x for x in _block(root, "git").splitlines() if x.startswith("vcs:")] == ["vcs: git"]


@pytest.mark.engine_repo  # the register, changelog, version file and card are not in an installed copy
def test_register_changelog_version_and_card_name_the_card():
    """E10: register row, `## 0.2.5` above `## 0.2.2`, VERSION 0.2.5, the card file."""
    register = (REPO / "cards" / "REGISTER.md").read_text(encoding="utf-8")
    assert re.search(r"^\| MW-028 \|.*`cards/MW-028-[a-z0-9-]+`", register, re.M)
    text = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    assert text.index("\n## 0.2.5\n") < text.index("\n## 0.2.2\n")
    assert "MW-028" in text.split("\n## 0.2.5\n", 1)[1].split("\n## ", 1)[0]
    assert (REPO / "VERSION").read_text(encoding="utf-8").strip() == "0.2.7"  # changed by MW-027: 0.2.7
    assert list((REPO / "cards").glob("MW-028-*/CARD.md"))
