"""Card MW-116: `verdict add` refuses a verdict for a reader run the allowlist hook never recorded
(`verdict-reader-unguarded`), and checks that the list of the run held exactly the card's two inputs. A real small git task
root; the reader run is an end row (as the agent hook writes it) and the guard rows come from the real hook process.
Synthetic sessions and agents."""
import json

import pytest

import _engine  # noqa: F401  (puts the engine folder on the import path)
import agents
import reader_allow
from _mw080 import N1, N2, N3, B1, FILE, apply, written
from _mw116 import AGENT, CARD, SESSION, allow_doc, make_world, payload, reader, run_hook, runs_rows, start, state_of

NODES = [N1, N2, N3, B1]


@pytest.fixture
def world(tmp_path):
    return make_world(tmp_path)


def _guarded_run(root, agent, files=None):
    """The reader-start step, one allowed read of the first listed file by `agent` through the real hook process, the end
    of the run (the list is emptied), and the checker's end row the agent hook writes."""
    doc = start(root)
    done = run_hook(root, payload(root, "Read", {"file_path": (files or doc["files"])[0]}, agent=agent))
    assert done.returncode == 0
    reader_allow.end(state_of(root), SESSION)
    reader(root, SESSION, agent)


def test_a_verdict_for_a_run_with_no_record_row_is_refused_unguarded(world):
    """Catches: a verdict row for a reader run that the allowlist hook never recorded (the folder was not trusted, so the
    frontmatter hook did not run); nothing is written."""
    reader(world, SESSION, AGENT)
    verdict = apply(world, SESSION, NODES)
    assert [r.reason for r in verdict.refusals] == ["verdict-reader-unguarded"]
    assert "trust" in verdict.refusals[0].text and "mkway reader start" in verdict.refusals[0].text
    assert written(world) == []


def test_after_a_guarded_rerun_the_verdict_passes_and_its_record_names_the_run_and_the_list(world):
    """Catches: the guarded re-run still refused, or the verdict record holding no agent id and no sha256 of the allow file."""
    reader(world, SESSION, AGENT)
    assert apply(world, SESSION, NODES).allowed is False
    _guarded_run(world, "a-reader-2")
    verdict = apply(world, SESSION, NODES)
    assert (verdict.allowed, verdict.run) == (True, "a-reader-2")
    record = written(world)[-1]
    start_row = [r for r in runs_rows(world) if r.get("kind") == "start"][-1]
    assert record["agent"] == "a-reader-2" and record["allow_sha256"] == start_row["allow_sha256"]


def test_a_run_whose_list_held_another_file_is_refused(world):
    """Catches: a run that read more than the card's two inputs being accepted: the start row names the list; a list with
    the card file on it is not the card's two inputs."""
    import cardtool
    from _mw116 import profile_of
    reader_allow.start(world, profile_of(world), state_of(world), SESSION, CARD)
    path = state_of(world) / "reader_allow" / f"{SESSION}.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["files"].append(str(cardtool.card_file(world, profile_of(world), CARD)))
    path.write_text(json.dumps(doc), encoding="utf-8")
    import hashlib
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    rows = [r for r in runs_rows(world) if r.get("kind") == "start"]
    agents.append_reader(state_of(world), {**rows[-1], "files": doc["files"], "allow_sha256": sha})
    done = run_hook(world, payload(world, "Read", {"file_path": str(world / FILE)}, agent="a-reader-3"))
    assert done.returncode == 0
    reader(world, SESSION, "a-reader-3")
    verdict = apply(world, SESSION, NODES)
    assert [r.reason for r in verdict.refusals] == ["verdict-reader-unguarded"]
    assert "CARD.md" in verdict.refusals[0].text


def test_a_run_started_for_another_card_is_refused(world):
    """Catches: a guard record of a run started for a different card counting for this card's verdict."""
    _guarded_run(world, "a-reader-4")
    path = state_of(world) / "reader_runs.jsonl"
    lines = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    for row in lines:
        if row.get("kind") == "start":
            row["card"] = "CARD-999"
    path.write_text("".join(json.dumps(r) + "\n" for r in lines), encoding="utf-8")
    verdict = apply(world, SESSION, NODES)
    assert [r.reason for r in verdict.refusals] == ["verdict-reader-unguarded"]
