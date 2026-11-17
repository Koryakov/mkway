"""Card MW-034: one builder per task root (`take-root-busy`, the lock gate). The commit-check cases of this card (a staged
file outside the Paths, files a script wrote, what git takes) moved to the pure core and the fact reader in MW-052 (see
`cards/MW-052-commit-core/case_map.md`); the lock cases stay here until the lock gate's own migration card. Synthetic
task roots only, real throwaway git repositories."""
import json

from _commit_fixture import make_task, reason
from _engine import cli
import gate_lock
import register

CLI = "python mkway/engine/mkway.py card"


def _lock(root, command, session):
    from _engine import gate_call
    v = gate_call(gate_lock.check, root, tool="Bash", tool_input={"command": command}, session=session)
    return v


def _profile(root):
    return json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))


def test_a_second_session_cannot_take_a_card_in_a_busy_root(tmp_path):
    """Catches: two builders in one worktree and one index, a second session taking a card while another holds the root (E4)."""
    root = make_task(tmp_path, session="abcdefgh-1234")
    assert cli(root, "card", "new", "Second", session=True)[0] == 0
    v = _lock(root, f"{CLI} take CARD-002", "zzzzzzzz-9999")
    assert v.kind == "refuse"
    assert v.reason_id == "take-root-busy"
    assert "abcdefgh" in v.message
    assert "abcdefgh-1234" not in v.message
    assert "CARD-001" in v.message
    assert "own worktree" in v.message
    assert "hand" in v.message


def test_the_same_session_may_take_its_own_card_again(tmp_path):
    """Checks: the session that holds the open card takes it again without a refusal (E5)."""
    root = make_task(tmp_path, session="s1")
    assert reason(_lock(root, f"{CLI} take CARD-001", "s1")) == "allow"


def test_a_take_after_the_holders_card_closed_is_allowed(tmp_path):
    """Catches: a root that stays busy for good after the holder's card closed, a second session still refused (E6)."""
    root = make_task(tmp_path, session="s1")
    assert cli(root, "card", "new", "Second", session=True)[0] == 0
    assert reason(_lock(root, f"{CLI} take CARD-002", "s2")) == "take-root-busy"
    register.set_status(root, _profile(root), "CARD-001", "closed")
    assert reason(_lock(root, f"{CLI} take CARD-002", "s2")) == "allow"
