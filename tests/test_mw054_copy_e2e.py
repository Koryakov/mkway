"""Card MW-054, rows E6 and E7, end to end through the REAL hook command lines (`_hook_driver`): a builder in a git
worktree copy starts, takes its card and writes a path of the card's Paths. One scratch product repository with the
engine installed and committed, shared state on (`state.shared_dir`), a card opened in the main root and committed.
Synthetic names only."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from _hook_driver import Project, decision, install_project
from test_e2e_gates import CARD, _card_text

pytestmark = pytest.mark.engine_repo

CLI = "python mkway/engine/mkway.py"
IN_PATHS, OUT_OF_PATHS = "src/a.py", "elsewhere/b.py"


def _listing(folder):
    return sorted((p.relative_to(folder).as_posix(), p.stat().st_size, p.stat().st_mtime_ns)
                  for p in Path(folder).rglob("*") if p.is_file())


def _records(project):
    log = project.root / "mkway" / "state" / "records.jsonl"
    if not log.is_file():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]


class Scenario:
    def __init__(self, base: Path):
        started = time.perf_counter()
        self.base = base
        self.main = main = install_project(base / "main")
        main.owner("card", "new", "Copy card")
        folder = next((main.root / "mkway" / "cards").glob(f"{CARD}-*"))
        card_file = folder / "CARD.md"
        card_file.write_text(_card_text(card_file.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
        main.owner("card", "open", CARD)
        shared = (base / "shared").resolve()
        shared.mkdir(parents=True, exist_ok=True)
        main.profile(**{"state.shared_dir": str(shared)})  # shared state is on, as in the real install
        main.git("add", "-A", "mkway/cards", "mkway/profile.json")
        main.git("commit", "-q", "-m", "the card")
        self.seconds_build = time.perf_counter() - started

    def copy(self, name: str) -> Project:
        wt = self.base / name
        self.main.git("worktree", "add", "-q", str(wt), "-b", name)
        return Project(self.base / "main", wt, wt / self.main.root.relative_to(self.main.top))

    def write_decision(self, project, session, rel):
        return decision(project.fire("PreToolUse", session, "Write", {"file_path": project.path(rel), "content": "x\n"}))


@pytest.fixture(scope="module")
def scenario(tmp_path_factory):
    return Scenario(tmp_path_factory.mktemp("copy"))


def test_a_builder_in_a_fresh_copy_takes_its_card_and_writes_in_its_paths(scenario):
    """Catches: a fresh copy that starts tampered or lets a Write outside the card's Paths through, or one that touches the main root or another copy (E6)."""
    # the copy has no seal; the start line does not say register-tampered; card take prints its ok line and the copy's records hold the take;
    # a Write in the card's Paths is allowed and one outside them is refused file-not-in-card; the main root (state, seal, records) is untouched; a second copy is independent
    main = scenario.main
    main_state = main.root / "mkway" / "state"
    before = _listing(main_state)
    copy = scenario.copy("copy-a")
    assert not (copy.root / "mkway" / "state" / "register.sha").exists(), "a new copy must start with no seal"

    start = copy.fire("SessionStart", "builder-a")
    text = "\n".join(run.stdout for run in start.runs)
    assert "register-tampered" not in text, text
    assert f"cards: this session holds no card; not closed: {CARD} open" in text.replace('\\"', '"'), text

    taken = copy.session_shell("builder-a", f"{CLI} card take {CARD}")
    assert taken.stdout.startswith(f"mkway-ok take {CARD} ")
    assert [(r["kind"], r["value"], r["session_id"]) for r in _records(copy)] == [("take", CARD, "builder-a")]

    allowed = scenario.write_decision(copy, "builder-a", IN_PATHS)
    assert allowed.kind == "allow", f"{allowed}: {allowed.text}"
    outside = scenario.write_decision(copy, "builder-a", OUT_OF_PATHS)
    assert (outside.kind, outside.reason_id) == ("deny", "file-not-in-card"), f"{outside}: {outside.text}"

    assert _listing(main_state) == before, "the main root's state was touched by the copy"
    assert [r for r in _records(main) if r["session_id"]] == [], "a session's record reached the main root"

    other = scenario.copy("copy-b")  # holders are per root: another copy takes the same card by another session
    decision(other.fire("SessionStart", "builder-b"))
    other.session_shell("builder-b", f"{CLI} card take {CARD}")
    assert scenario.write_decision(other, "builder-b", IN_PATHS).kind == "allow"
    assert [(r["session_id"]) for r in _records(copy)] == ["builder-a"], "the first copy's holders changed"


def test_a_session_started_from_another_root_still_takes_in_its_own_copy(scenario):
    """Checks: a builder whose shell inherited the main root's project dir still takes in its own copy, with a Write in the Paths allowed and no nonce or record in the main root (E7)."""
    # the hooks carry the copy's own project dir; the CLI works in the folder it runs in: the nonce and the take land in the copy and the post step records it
    main = scenario.main
    main_state = main.root / "mkway" / "state"
    before = _listing(main_state)
    copy = scenario.copy("copy-c")
    decision(copy.fire("SessionStart", "builder-c"))

    taken = copy.session_shell("builder-c", f"{CLI} card take {CARD}", shell_project_dir=main.root)
    assert taken.stdout.startswith(f"mkway-ok take {CARD} ")
    assert [(r["kind"], r["value"], r["session_id"]) for r in _records(copy)] == [("take", CARD, "builder-c")]
    assert not list((main_state / "nonces").glob("*")) if (main_state / "nonces").is_dir() else True
    allowed = scenario.write_decision(copy, "builder-c", IN_PATHS)
    assert allowed.kind == "allow", f"{allowed}: {allowed.text}"
    assert _listing(main_state) == before, "the CLI of the copy wrote into the main root"
    assert [r for r in _records(main) if r["session_id"]] == []
