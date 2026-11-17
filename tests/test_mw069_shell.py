"""Card MW-069, the real shape on a real small repository: card CARD-002's test file is committed and imports a module
that card CARD-001 adds, so at HEAD that file fails at collection. CARD-001 commits the module with `--`, and the file's
test is then red per id (the module is in, its value is not what the test wants). The gate runs the real suite on the
staged tree and on HEAD's tree (a real git repository, a real pytest run, about a second per run). Synthetic names only."""
import json

from _commit_project import make_project, run_gate, write
from test_mw056_head import commit_file, new_card
import register

COMMIT = "git commit -m x -- newmod.py"
TEST_B = "import newmod\n\n\ndef test_value():\n    assert newmod.VALUE == 2\n"


def project(tmp_path):
    """CARD-001 (held by the session) adds `newmod.py`; CARD-002 owns `tests/test_b.py`, committed at HEAD, red there
    at collection."""
    root = make_project(tmp_path)
    assert new_card(root, "Adds the module", "`newmod.py`", take=True) == "CARD-001"
    assert new_card(root, "Checks the module", "`tests/test_b.py`") == "CARD-002"
    commit_file(root, "tests/test_b.py", TEST_B)
    write(root, "newmod.py", "VALUE = 1\n")
    return root


def close(root, card_id):
    profile = json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))
    register.set_status(root, profile, card_id, "closed")


def stage_module(root):
    from _commit_project import git
    git(root, "add", "--", "newmod.py")


def test_a_file_that_failed_at_collection_at_head_with_a_closed_owner_is_refused_as_red_at_head(tmp_path):
    """Catches: the real-install refusal «new red, not red at HEAD» for a test whose file failed at collection at HEAD (E8, MW108-D1: the name is kept for the cards that cite it; the commit is now allowed with the old-red line)."""
    root = project(tmp_path)
    close(root, "CARD-002")
    stage_module(root)
    verdict = run_gate(root, COMMIT)
    assert verdict.kind == "warn", (verdict.kind, verdict.message)
    assert verdict.reason_id == "commit-tests-still-red", (verdict.kind, verdict.message)
    assert "old red: tests/test_b.py::test_value, owner none" in verdict.message
    assert "failed at collection at HEAD" in verdict.message
    assert "closed card CARD-002" in verdict.message
    assert "new red, not red at HEAD" not in verdict.message
    assert "absent at HEAD" not in verdict.message


def test_a_file_that_failed_at_collection_at_head_with_an_open_owner_is_allowed_and_listed(tmp_path):
    """Checks: the same commit is allowed as a warn while another open card's file is mid-way, and the allow line does not call a red-at-HEAD case absent (E9)."""
    root = project(tmp_path)
    stage_module(root)
    verdict = run_gate(root, COMMIT)
    assert verdict.kind == "warn", (verdict.kind, verdict.message)
    assert verdict.reason_id == "commit-tests-still-red", (verdict.kind, verdict.message)
    assert "tests/test_b.py::test_value still red, owned by CARD-002" in verdict.message
    assert "absent at HEAD" not in verdict.message
