"""Card MW-116: the way out of each refusal of the card, proved on the real hook, the start step and the verdict command. A
refusal is followed by the step its text names, and the same call then passes. Synthetic task root, sessions and agents."""
import _engine  # noqa: F401  (puts the engine folder on the import path)
import reader_allow
from _mw080 import N1, N2, N3, B1, apply
from _mw116 import AGENT, SESSION, make_world, payload, reader, run_hook, start, state_of

NODES = [N1, N2, N3, B1]


def test_the_way_out_of_reader_read_refused_is_a_listed_file(tmp_path):
    """Checks: an unlisted read is blocked, and a read of a file the refusal lists passes with the same hook."""
    root = make_world(tmp_path)
    doc = start(root)
    assert run_hook(root, payload(root, "Read", {"file_path": str(root / "README.md")})).returncode == 2
    assert run_hook(root, payload(root, "Read", {"file_path": doc["files"][0]})).returncode == 0


def test_the_way_out_of_reader_busy_is_to_end_the_run_and_start_again(tmp_path):
    """Checks: a second start is refused reader-busy; after the release the same start passes."""
    root = make_world(tmp_path)
    start(root)
    try:
        start(root)
        refused = False
    except reader_allow.ReaderError as seen:
        refused = seen.reason == "reader-busy"
    assert refused is True
    reader_allow.end(state_of(root), SESSION)
    assert start(root)["files"] != []


def test_the_way_out_of_verdict_reader_unguarded_is_a_guarded_rerun(tmp_path):
    """Checks: the verdict for an unrecorded run is refused; after the reader-start step, an allowed read by a new run and
    its end row, the same call passes."""
    root = make_world(tmp_path)
    reader(root, SESSION, AGENT)
    assert [r.reason for r in apply(root, SESSION, NODES).refusals] == ["verdict-reader-unguarded"]
    doc = start(root)
    assert run_hook(root, payload(root, "Read", {"file_path": doc["files"][0]}, agent="a-reader-2")).returncode == 0
    reader_allow.end(state_of(root), SESSION)
    reader(root, SESSION, "a-reader-2")
    assert apply(root, SESSION, NODES).allowed is True
