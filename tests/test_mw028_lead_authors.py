"""Card MW-028: a lead authors its own proposed cards, and a root below the git top reads vcs git. Synthetic roots and
scratch repositories only."""
import re
import subprocess

import pytest

import _docs as docs
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


def test_a_lead_opens_its_own_card_with_approver_orderer(world):
    """Catches: a lead card open refused where it should pass, or passed under the owner-only approver. E5"""
    # with cards.approver: orderer a registered lead's card open of a card it ordered passes (the hook, then the CLI): the
    # register says open and records the Paths; with the default owner-only approver it is refused owner-only-command by
    # the hook.
    root, mine, _theirs = world
    code, out, err = session_run(root, "lead-a", "card", "open", mine)
    assert code == 0, err
    assert row_of(root, mine)["status"] == "open"
    owner_only = lead_root(root.parent, name="owner-only", cards={})
    register_lead(owner_only, "lead-a")
    card = new_card(owner_only, "lead-a", "Mine")
    code, out, err = session_run(owner_only, "lead-a", "card", "open", card)
    assert code is None
    assert err.startswith("owner-only-command"), err
    assert row_of(owner_only, card)["status"] == "proposed"


def test_a_lead_never_opens_an_owner_ordered_card_or_another_leads(world):
    """Catches: a lead opening an owner-ordered or another lead's card, or a session that is no lead opening its own. E6"""
    # with cards.approver: orderer a lead's card open of an owner-ordered card or another lead's card is refused
    # owner-only-command; a session that is no lead is refused for its own card too. Nothing changes.
    root, _mine, theirs = world
    assert cli(root, "card", "new", "Owned")[0] == 0
    owned = "CARD-003"
    assert row_of(root, owned)["status"] == "proposed"
    results = [(session, card, session_run(root, session, "card", "open", card))
               for session, card in (("lead-a", owned), ("lead-a", theirs))]
    not_refused = [(s, c, code, e) for s, c, (code, _out, e) in results
                   if code is not None or not e.startswith("owner-only-command")]
    assert not_refused == [], not_refused
    built = new_card(root, "builder-1", "Builder card")
    code, out, err = session_run(root, "builder-1", "card", "open", built)
    assert code is None
    assert err.startswith("owner-only-command"), err
    assert {row_of(root, c)["status"] for c in (owned, theirs, built)} == {"proposed"}


def _worktree_root(tmp_path):
    """A linked worktree with a sparse cone and an untracked task folder below its top (the shape of the first real
    install): `main/` holds the commit, `wt/` the linked worktree, the root is `wt/task/T`."""
    main, wt = tmp_path / "main", tmp_path / "wt"
    (main / "task" / "other").mkdir(parents=True)
    (main / "task" / "other" / "a.txt").write_text("a\n", encoding="utf-8")
    (main / "top.txt").write_text("t\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(main)], check=True, cwd=tmp_path)
    subprocess.run(["git", *GIT_ID, "-C", str(main), "add", "-A"], check=True, cwd=tmp_path)
    subprocess.run(["git", *GIT_ID, "-C", str(main), "commit", "-q", "-m", "base"], check=True, cwd=tmp_path)
    subprocess.run(["git", "-C", str(main), "worktree", "add", "-q", str(wt), "-b", "work"], check=True, cwd=tmp_path)
    subprocess.run(["git", "-C", str(wt), "sparse-checkout", "set", "--cone", "task"], check=True, cwd=tmp_path)
    root = wt / "task" / "T"
    root.mkdir(parents=True)
    return wt, root


def test_detect_vcs_answers_git_for_a_root_below_the_top_of_a_sparse_linked_worktree(tmp_path):
    """Checks: a root under a sparse linked worktree reads as git, and a bare folder reads as none. E7"""
    # the root is an untracked folder two levels below the top of a linked worktree with a sparse cone: git, not none. A
    # folder that is in no git work tree is still none.
    top, root = _worktree_root(tmp_path)
    assert install.git_top(root) == top.resolve()
    assert install.detect_vcs(root) == "git"
    assert install.detect_vcs(top) == "git"
    bare = tmp_path / "bare-folder"
    bare.mkdir()
    assert install.detect_vcs(bare) == "none"


def test_a_first_install_below_the_top_writes_vcs_git_and_the_ignore_file(tmp_path):
    """Checks: mkway install at that root writes a starter profile with vcs git and the bundle .gitignore. E8"""
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
    """Checks: the vcs none line keeps its words and gives one reason on the same line, and vcs git shows a plain line. E9"""
    # vcs: none keeps its words and adds one reason on the same line: the root is inside a git work tree (the profile says
    # none: set vcs to git), or the root is in no git work tree.
    top, root = _worktree_root(tmp_path)
    inside = [x for x in _block(root, "none").splitlines() if x.startswith("vcs:")]
    assert len(inside) == 1
    assert inside[0].startswith("vcs: none, every git step is off")
    assert "inside a git work tree" in inside[0]
    assert "\"vcs\": \"git\"" in inside[0]
    bare = tmp_path / "bare-folder"
    bare.mkdir()
    outside = [x for x in _block(bare, "none").splitlines() if x.startswith("vcs:")]
    assert len(outside) == 1
    assert outside[0].startswith("vcs: none, every git step is off")
    assert "no git work tree" in outside[0]
    assert [x for x in _block(root, "git").splitlines() if x.startswith("vcs:")] == ["vcs: git"]
