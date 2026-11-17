"""Card MW-054, rows E3 to E5: the register's seal in a fresh git worktree copy, on real git (a scratch product
repository and linked worktrees under the pytest temp folder). Facts, not hooks: `register.seal_problem` is what every
gate and the start line read. Synthetic names only; each test stays well under 20 s."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import _engine  # noqa: F401  (puts the engine folder on the path)
import register
from _hook_driver import GIT_ID

PROFILE = {"vcs": "git", "bundle": {"root": "mkway"}, "state": {"dir": "mkway/state"}}
TASK = Path("task") / "T1"
ADOPTED = "register-seal-adopted"


def _git(cwd, *args):
    proc = subprocess.run(["git", *GIT_ID, *args], cwd=str(cwd), capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, f"git {' '.join(args)}: {proc.stdout}{proc.stderr}"
    return proc.stdout


def _row(card_id, status="open"):
    return {"id": card_id, "title": f"title {card_id}", "status": status, "paths": "`src/`",
            "folder": f"`mkway/cards/{card_id}-x`"}


def _write_register(root, rows):
    target = register.path(root, PROFILE)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(register.render(rows, PROFILE, False).encode("utf-8"))
    return target


def _product(base):
    """A product repository whose task folder holds a committed register; (top, root). The owner's install has sealed
    the main root (the seal and the copy of the register are untracked state)."""
    top = base / "product"
    root = top / TASK
    top.mkdir(parents=True)
    _git(top, "init", "-q")
    _write_register(root, [_row("MW-900")])
    _git(top, "add", "-A")
    _git(top, "commit", "-q", "-m", "the register")
    register.reseal(root, PROFILE)
    return top, root


def _copy(top, base, name, source=None):
    """A linked worktree of the product repository (of `source`, a branch, when given); the root inside it."""
    folder = base / name
    args = ["worktree", "add", "-q", str(folder), "-b", name] + ([source] if source else [])
    _git(top, *args)
    return folder / TASK


def _refusal_rows(root):
    log = register.sha_path(root, PROFILE).parent / "refusals.jsonl"
    if not log.is_file():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]


def _listing(folder):
    return sorted((p.relative_to(folder).as_posix(), p.stat().st_size, p.stat().st_mtime_ns)
                  for p in Path(folder).rglob("*") if p.is_file())


def test_a_fresh_copy_seals_from_its_committed_register(tmp_path):
    """Checks: a new copy has no seal, its register equals the committed bytes, the seal is made from them with one Log row, and the main root is not touched (E3)."""
    top, main = _product(tmp_path)
    before = _listing(main / "mkway" / "state")
    copy = _copy(top, tmp_path, "copy1")
    assert not register.sha_path(copy, PROFILE).exists(), "a new copy must start with no seal"
    working = register.path(copy, PROFILE).read_bytes()  # a checkout may have converted the line ends: seal THESE bytes
    committed = _git(top, "show", "copy1:task/T1/mkway/cards/REGISTER.md").encode("utf-8")
    assert working.replace(b"\r\n", b"\n") == committed.replace(b"\r\n", b"\n")

    assert register.seal_problem(copy, PROFILE) is None
    assert register.sha_path(copy, PROFILE).read_text(encoding="utf-8").strip() == register.digest(working)
    assert register.last_path(copy, PROFILE).read_bytes() == working
    rows = [r for r in _refusal_rows(copy) if r.get("reason_id") == ADOPTED]
    assert len(rows) == 1
    assert rows[0]["kind"] == "log"
    assert rows[0]["gate"] == "register", rows
    register.check(copy, PROFILE)  # the engine's own check agrees
    assert register.seal_problem(copy, PROFILE) is None
    assert len([r for r in _refusal_rows(copy) if r.get("reason_id") == ADOPTED]) == 1, "a second look wrote a row"
    assert _listing(main / "mkway" / "state") == before, "the main root's state was touched"


def test_a_seal_that_differs_and_a_register_that_differs_from_head_stay_refused(tmp_path):
    """Catches: a seal that differs or a register edited after the commit being overwritten or sealed instead of staying refused (E4)."""
    top, _main = _product(tmp_path)

    differs = _copy(top, tmp_path, "differs")
    seal = register.sha_path(differs, PROFILE)
    seal.parent.mkdir(parents=True, exist_ok=True)
    seal.write_text(register.digest(b"another register") + "\n", encoding="utf-8")
    assert register.seal_problem(differs, PROFILE) == "the register differs from its seal"
    assert seal.read_text(encoding="utf-8").strip() == register.digest(b"another register")
    assert not [r for r in _refusal_rows(differs) if r.get("reason_id") == ADOPTED]

    edited = _copy(top, tmp_path, "edited")
    _write_register(edited, [_row("MW-900", "closed"), _row("MW-901")])  # edited by hand after the commit
    assert register.seal_problem(edited, PROFILE) == "register.sha is missing"
    assert not register.sha_path(edited, PROFILE).exists()
    assert not [r for r in _refusal_rows(edited) if r.get("reason_id") == ADOPTED]

    lone = tmp_path / "lone"
    lone_root = lone / TASK
    _write_register(lone_root, [_row("MW-900")])
    _git(lone, "init", "-q")  # a git repository with no commit: HEAD holds no register
    assert register.seal_problem(lone_root, PROFILE) == "register.sha is missing"
    assert not register.sha_path(lone_root, PROFILE).exists()


def test_a_copy_of_a_branch_with_its_own_register_seals_from_that_branch(tmp_path):
    """Checks: a copy made from a branch seals from that branch's HEAD register, and a copy of master beside it keeps master's (E5 step 3b, the chief's ruling)."""
    top, _main = _product(tmp_path)
    master = _git(top, "rev-parse", "--abbrev-ref", "HEAD").strip()
    _git(top, "branch", "lead")
    lead_tree = _copy(top, tmp_path, "lead-work", source="lead")
    _write_register(lead_tree, [_row("MW-900"), _row("MW-901", "proposed")])
    _git(lead_tree, "add", "-A")
    _git(lead_tree, "commit", "-q", "-m", "a new card row")
    from_lead = _copy(top, tmp_path, "from-lead", source="lead-work")
    from_master = _copy(top, tmp_path, "from-master", source=master)
    lead_bytes = register.path(from_lead, PROFILE).read_bytes()  # what the checkout of each branch put on disk
    master_bytes = register.path(from_master, PROFILE).read_bytes()
    assert lead_bytes != master_bytes

    assert register.seal_problem(from_lead, PROFILE) is None
    assert register.seal_problem(from_master, PROFILE) is None
    assert register.sha_path(from_lead, PROFILE).read_text(encoding="utf-8").strip() == register.digest(lead_bytes)
    assert register.sha_path(from_master, PROFILE).read_text(encoding="utf-8").strip() == register.digest(master_bytes)
    assert [r["id"] for r in register.read(from_lead, PROFILE)] == ["MW-900", "MW-901"]
    assert [r["id"] for r in register.read(from_master, PROFILE)] == ["MW-900"]
