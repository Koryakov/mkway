"""Card MW-129 (rulings R307, R310, R312), layer shell, on real small git repositories with real linked work trees: a card
record (the red proof) is written and read through the shared folder, so a record written in one checkout is read by
`verdict add` in another and survives the removal of the work tree. Synthetic names only.

`_ready` is the setup of `verdict add`'s other proof steps (P7): it reuses `_mw080.reader` (the checker run and its guard
rows) and `_mw080.apply` (the whole call in process), the helpers the MW-117 and MW-116 shell tests use."""
import json
import shutil
from pathlib import Path

import pytest

import _mw080 as w
import _red_project as rp
from _commit_project import git as plain_git, reason, run_gate, stage
import logs
import profiles
import records

NEW_FILE = "tests/test_new.py"
NODE = "tests/test_new.py::test_mul"
ROW = f"| E1 | mul | none | mul | {NODE} |"
RED_FILE = "red_proof.jsonl"
BRANCH = "card-branch"


def shared():
    """The module under test, imported late so a test that needs none of it fails for its own reason."""
    import shared_records
    return shared_records


def root_of(tmp_path, *, shared=True):
    """The main checkout: a git task root with a pytest project, the open card CARD-001 held by s1, one checker type; with
    `shared` the profile names the shared folder `<tmp>/shared` (committed, so a work tree inherits it)."""
    over = {"outbox": {"checkers": [w.CHECKER]}}
    if shared:
        over["state"] = {"dir": "mkway/state", "shared_dir": str(tmp_path / "shared")}
    return rp.red_project(tmp_path, row=ROW, name="main", **over)


def shared_file(tmp_path) -> Path:
    return tmp_path / "shared" / RED_FILE


def rows_of(path) -> list:
    path = Path(path)
    if not path.is_file():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def worktree(root, tmp_path, name="wt", branch=BRANCH) -> Path:
    """A linked work tree of the main checkout on a new branch; the session s1 holds the card there too."""
    folder = tmp_path / name
    plain_git(root, "worktree", "add", "-q", "-b", branch, str(folder))
    records.append(folder / "mkway" / "state", "s1", "take", rp.CARD)
    return folder


def red_commit(checkout):
    """The red-first commit of the card's new test in `checkout`: the gate allows it, then git makes the commit (dated before
    every reader run). Returns the keys the commit's tree may have in a row (`gate_commit_tests.tree_keys`)."""
    stage(checkout, NEW_FILE, rp.RED_MUL)
    assert reason(run_gate(checkout)) == "allow"
    w.git(checkout, "commit", "-q", "-m", "CARD-001 red", when=w.COMMIT_AT)
    return keys_of(checkout)


def keys_of(checkout) -> list:
    import gate_commit_tests
    return gate_commit_tests.tree_keys(checkout, "HEAD")


def staged_key_of(checkout) -> str:
    """The key a gate row carries for the staged tree: the digest of the staged listing (`gate_commit_tests.staged_key`)."""
    import gate_commit_tests as gct
    return gct.staged_key(gct._read(checkout, "ls-files", "-s", "-z", text=False))


def merge(root, branch=BRANCH):
    w.git(root, "merge", "--no-ff", "-q", "-m", f"merge {branch}", branch, when=w.COMMIT_AT)


def _ready(root):
    """The other proof steps of `verdict add`: one fresh guarded checker run of the session `reader` (helper `_mw080.reader`)."""
    w.reader(root, "reader", "agent-1")


def verdict_of(root):
    """The whole `verdict add` call in process (helper `_mw080.apply`) for the new node; returns (allowed, reasons)."""
    got = w.apply(root, "reader", [NODE])
    return got.allowed, [r.reason for r in got.refusals]


def seed(path, tree, *, newline=True):
    row = {"card": rp.CARD, "tree": tree, "red": [NODE], "pins": [], "checks": [], "missing": {}, "would_refuse": [],
           "mode": "trip"}
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(row) + ("\n" if newline else ""))


def committed_test(root):
    """The test file committed in the main checkout (dated before every reader run); returns the tree key of HEAD for a row."""
    stage(root, NEW_FILE, rp.RED_MUL)
    w.git(root, "commit", "-q", "-m", "CARD-001 the tests", when=w.COMMIT_AT)
    return keys_of(root)[0]


# ---- the live case and the merge order --------------------------------------------------------------------------------

def test_a_red_commit_made_in_a_worktree_lets_verdict_add_in_main_through_after_the_merge(tmp_path):
    """Catches: the red-proof row written into the work tree's own state, so `verdict add` in main refuses
    verdict-no-red-proof for a red commit that was made and merged (the live case)."""
    root = root_of(tmp_path)
    wt = worktree(root, tmp_path)
    red_commit(wt)
    merge(root)
    _ready(root)
    assert verdict_of(root) == (True, [])


def test_the_row_written_in_the_worktree_is_read_in_main_by_the_tree_of_the_merged_head(tmp_path):
    """Catches: a row read from the wrong folder, or a tree test that no longer finds the red commit once main has moved on
    and the branch is merged: main commits other work first, then the merge; the only row is the one the work tree wrote."""
    root = root_of(tmp_path)
    wt = worktree(root, tmp_path)
    keys = red_commit(wt)
    stage(root, "notes.txt", "other work\n")
    w.git(root, "commit", "-q", "-m", "other work", when=w.COMMIT_AT)
    merge(root)
    _ready(root)
    assert w.read(root, "reader", [NODE]).red_proven is True
    assert [r["tree"] for r in rows_of(shared_file(tmp_path))] == [keys[1]]
    assert rows_of(w.state_of(wt) / RED_FILE) == [] and rows_of(w.state_of(root) / RED_FILE) == []


def test_the_red_proof_survives_the_removal_of_the_worktree(tmp_path):
    """Catches: a record that dies with the work tree's folder (git worktree remove deletes it with its state)."""
    root = root_of(tmp_path)
    wt = worktree(root, tmp_path)
    red_commit(wt)
    merge(root)
    plain_git(root, "worktree", "remove", "--force", str(wt))
    _ready(root)
    assert verdict_of(root) == (True, [])


# ---- never weaker, and the readers ignore another checkout ------------------------------------------------------------

def test_guard_a_card_with_no_red_row_anywhere_is_refused_verdict_no_red_proof(tmp_path):
    """GUARD (green from the start, by design): the refusal does not weaken. Catches: a read of the shared folder that
    counts a missing file as proof."""
    root = root_of(tmp_path)
    committed_test(root)
    _ready(root)
    assert verdict_of(root) == (False, ["verdict-no-red-proof"])


def test_guard_a_red_row_only_in_a_worktrees_old_checkout_state_is_not_read_by_main(tmp_path):
    """GUARD (P5; green from the start: today's reader reads only its own state). The row sits in the work tree's own state
    folder, never migrated; the run-time reader never goes looking in another checkout (R307)."""
    root = root_of(tmp_path)
    wt = worktree(root, tmp_path)
    tree = red_commit(wt)[0]
    merge(root)
    shutil.rmtree(tmp_path / "shared", ignore_errors=True)
    seed(w.state_of(wt) / RED_FILE, tree)
    _ready(root)
    assert verdict_of(root) == (False, ["verdict-no-red-proof"])


def test_guard_with_the_shared_folder_unset_one_checkout_behaves_as_before(tmp_path):
    """GUARD (green from the start): no `state.shared_dir`, one checkout: the row lands in the state folder and the verdict
    is allowed."""
    root = root_of(tmp_path, shared=False)
    keys = red_commit(root)
    assert [r["tree"] for r in rows_of(w.state_of(root) / RED_FILE)] == [keys[1]]
    _ready(root)
    assert verdict_of(root) == (True, [])


def test_a_line_that_is_cut_off_at_the_end_of_the_shared_file_is_skipped_and_the_rows_before_it_count(tmp_path):
    """Catches: a half-written last line (no newline, not JSON) that makes the reader drop the earlier rows."""
    root = root_of(tmp_path)
    tree = committed_test(root)
    seed(shared_file(tmp_path), tree)
    with open(shared_file(tmp_path), "a", encoding="utf-8", newline="\n") as fh:
        fh.write('{"card": "CARD-001", "tre')
    _ready(root)
    assert verdict_of(root) == (True, [])


def test_a_last_line_with_no_newline_that_parses_counts(tmp_path):
    """Catches: a complete row that lacks only its final newline thrown away as if it were partial."""
    root = root_of(tmp_path)
    tree = committed_test(root)
    seed(shared_file(tmp_path), tree, newline=False)
    _ready(root)
    assert verdict_of(root) == (True, [])


# ---- the append lock --------------------------------------------------------------------------------------------------

def test_the_writer_refuses_shared_record_busy_when_the_append_lock_stays_held(tmp_path, monkeypatch):
    """Catches: a red row dropped silently, or written without the lock, while another writer holds the marker."""
    monkeypatch.setattr(logs, "APPEND_WAIT_SECONDS", 0.3)
    root = root_of(tmp_path)
    marker = logs.append_lock_path(shared_file(tmp_path))
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("another-writer", encoding="utf-8")
    stage(root, NEW_FILE, rp.RED_MUL)
    verdict = run_gate(root)
    assert reason(verdict) == "shared-record-busy"
    assert verdict.message == (f"another writer holds the append lock of {shared_file(tmp_path)}, so the red record of "
                               f"{rp.CARD} was not written and the commit is refused: repeat the call")
    assert rows_of(shared_file(tmp_path)) == []


def test_the_way_out_of_shared_record_busy_is_to_repeat_the_call(tmp_path, monkeypatch):
    """Checks: the way out: hold the marker, see the refusal, release it, repeat the same call: allowed, exactly one row."""
    monkeypatch.setattr(logs, "APPEND_WAIT_SECONDS", 0.3)
    root = root_of(tmp_path)
    marker = logs.append_lock_path(shared_file(tmp_path))
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("another-writer", encoding="utf-8")
    stage(root, NEW_FILE, rp.RED_MUL)
    assert reason(run_gate(root)) == "shared-record-busy"
    marker.unlink()
    assert reason(run_gate(root)) == "allow"
    assert [r["card"] for r in rows_of(shared_file(tmp_path))] == [rp.CARD]


def test_the_lock_marker_is_removed_after_a_write(tmp_path):
    """Catches: a marker left behind by a finished write, which would block every later writer for the stale time."""
    root = root_of(tmp_path)
    red_commit(root)
    assert not logs.append_lock_path(shared_file(tmp_path)).exists()
    assert len(rows_of(shared_file(tmp_path))) == 1


def test_a_second_call_for_the_same_tree_and_card_writes_no_second_row(tmp_path):
    """Checks: one row per tree and card (the check runs inside the lock with the append, P1)."""
    root = root_of(tmp_path)
    stage(root, NEW_FILE, rp.RED_MUL)
    assert reason(run_gate(root)) == "allow"
    assert reason(run_gate(root)) == "allow"
    got = [{k: v for k, v in r.items() if k != "time"} for r in rows_of(shared_file(tmp_path))]
    assert got == [{"session": "s1", "card": rp.CARD, "tree": staged_key_of(root), "red": [NODE], "pins": [], "checks": [],
                    "missing": {}, "would_refuse": [], "mode": "trip", "git_tree": plain_git(root, "write-tree").strip()}]


# ---- the shared access functions --------------------------------------------------------------------------------------

def test_the_shared_path_is_the_shared_folder_of_the_profile_and_the_state_folder_when_it_is_unset(tmp_path):
    """Checks: one function gives the path of a card record file: shared_dir when set, else the state dir."""
    root = root_of(tmp_path)
    profile = w.profile_of(root)
    assert shared().shared_path(root, profile, RED_FILE) == tmp_path / "shared" / RED_FILE
    del profile["state"]["shared_dir"]
    assert shared().shared_path(root, profile, RED_FILE) == root / "mkway" / "state" / RED_FILE


def test_append_row_with_a_key_writes_a_row_once(tmp_path):
    """Catches: a second row for a key that is already in the file."""
    root = root_of(tmp_path)
    profile = w.profile_of(root)
    row = {"card": "C-1", "tree": "t1", "time": "2026-01-01T00:00:00.000+00:00"}
    first = shared().append_row(root, profile, RED_FILE, row, key=("tree", "card"))
    second = shared().append_row(root, profile, RED_FILE, {**row, "time": "2026-01-02T00:00:00.000+00:00"},
                                       key=("tree", "card"))
    assert (first, second) == (True, False)
    assert rows_of(shared_file(tmp_path)) == [row]


# ---- the migration ----------------------------------------------------------------------------------------------------

T1, T2, T3, T4 = (f"2026-11-1{n}T10:00:00.000+00:00" for n in (1, 2, 3, 4))


def mrow(card, tree, time, **extra):
    return {"time": time, "session": "s", "card": card, "tree": tree, "red": ["x::y"], "pins": [], "checks": [],
            "missing": {}, "would_refuse": [], "mode": "trip", **extra}


def put(path, rows, tail=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(("".join(json.dumps(r) + "\n" for r in rows) + tail).encode("utf-8"))


def migration_world(tmp_path):
    """Main (state with two rows and a cut-off last line), a live work tree `wt-a` (a row equal to one of main's, a new row,
    a row with the same key as another of main's but other content), a live work tree `wt-c` with no state folder, and a
    work tree `wt-b` whose folder was deleted (prunable), whose state is never read."""
    root = root_of(tmp_path)
    a, b = mrow("C-1", "t-a", T1), mrow("C-1", "t-b", T3)
    d, e = mrow("C-2", "t-d", T2), mrow("C-1", "t-b", T4, session="other")
    put(w.state_of(root) / RED_FILE, [a, b], tail='{"card": "C-1", "tr')
    wt_a = worktree(root, tmp_path, "wt-a", "b-a")
    put(w.state_of(wt_a) / RED_FILE, [a, d, e])
    wt_b = worktree(root, tmp_path, "wt-b", "b-b")
    put(w.state_of(wt_b) / RED_FILE, [mrow("C-9", "t-z", T1)])
    (wt_b / ".git").unlink()  # its folder and its state stay, but git no longer finds its link: prunable (W4)
    wt_c = tmp_path / "wt-c"
    plain_git(root, "worktree", "add", "-q", "-b", "b-c", str(wt_c))
    return root, wt_a, wt_c, (a, b, d, e)


def test_the_migration_copies_each_row_once_in_time_order_and_counts_exactly(tmp_path):
    """Checks: main and every live work tree are read; rows are ordered by time; a row equal to one already there is
    present, a row with the same key and other content is turned away, a cut-off line is skipped, a prunable work tree and a
    work tree with no state folder are named and not read."""
    root, wt_a, wt_c, (a, b, d, _e) = migration_world(tmp_path)
    report = shared().migrate(root, w.profile_of(root), write=True)
    assert rows_of(shared_file(tmp_path)) == [a, d, b]
    assert report["files"] == [{"file": RED_FILE, "found": 5, "copied": 3, "present": 1, "skipped": 1, "turnedAway": 1}]
    assert report["lines"][0] == (f"{RED_FILE}: rows found 5, copied 3, already present 1, broken lines skipped 1, "
                                  f"turned away by the key 1")
    assert [(Path(x["path"]).resolve(), x["state"]) for x in report["worktrees"]] == [
        (root.resolve(), "read"), (wt_a.resolve(), "read"), (tmp_path.resolve() / "wt-b", "prunable"),
        (wt_c.resolve(), "no state folder")]
    assert report["noop"] is False


def test_a_second_migration_copies_nothing_and_the_old_files_stay_byte_for_byte(tmp_path):
    """Catches: a migration that is not idempotent, or that touches the old files."""
    root, wt_a, _wt_c, _rows = migration_world(tmp_path)
    old = {p: p.read_bytes() for p in (w.state_of(root) / RED_FILE, w.state_of(wt_a) / RED_FILE)}
    shared().migrate(root, w.profile_of(root), write=True)
    after_first = shared_file(tmp_path).read_bytes()
    report = shared().migrate(root, w.profile_of(root), write=True)
    assert report["files"] == [{"file": RED_FILE, "found": 5, "copied": 0, "present": 4, "skipped": 1, "turnedAway": 1}]
    assert shared_file(tmp_path).read_bytes() == after_first
    assert {p: p.read_bytes() for p in old} == old


def test_a_dry_run_reports_the_same_counts_and_writes_nothing(tmp_path):
    """Catches: a dry run that writes, or whose plan differs from the real run (R310 3d)."""
    root, _wt_a, _wt_c, _rows = migration_world(tmp_path)
    plan = shared().migrate(root, w.profile_of(root), write=False)
    assert not shared_file(tmp_path).exists()
    real = shared().migrate(root, w.profile_of(root), write=True)
    assert plan["files"] == real["files"]
    assert plan["lines"] == real["lines"]


def test_with_the_shared_folder_unset_the_migration_is_a_no_op_and_says_so(tmp_path):
    """Checks: the shared folder is the main checkout's state folder: nothing to copy, and the report says so."""
    root = root_of(tmp_path, shared=False)
    put(w.state_of(root) / RED_FILE, [mrow("C-1", "t-a", T1)])
    before = (w.state_of(root) / RED_FILE).read_bytes()
    report = shared().migrate(root, w.profile_of(root), write=True)
    assert report["noop"] is True
    assert report["message"] == "the shared folder is the state folder of the main checkout: nothing to migrate"
    assert report["files"] == [] and report["lines"] == [report["message"]]
    assert (w.state_of(root) / RED_FILE).read_bytes() == before


def test_a_shared_folder_that_cannot_be_written_fails_the_migration_with_the_error(tmp_path):
    """Catches: a migration that reports success when the shared folder is a file and nothing could be written."""
    root, _wt_a, _wt_c, _rows = migration_world(tmp_path)
    (tmp_path / "shared").write_text("not a folder", encoding="utf-8")
    with pytest.raises(shared().MigrationFailed):
        shared().migrate(root, w.profile_of(root), write=True)


def test_the_profile_helper_agrees_with_the_shared_path(tmp_path):
    """Checks: the shared folder the migration writes is the folder `profiles.shared_state_dir` names."""
    root, *_rest = migration_world(tmp_path)
    shared().migrate(root, w.profile_of(root), write=True)
    assert profiles.shared_state_dir(root, w.profile_of(root)) == tmp_path / "shared"
    assert shared_file(tmp_path).is_file()


# ---- the round of the blind reader (items 1 to 8 and the weak rows) ---------------------------------------------------

def code_commit_is(root) -> str:
    """The verdict reason of the code commit that follows the red commit."""
    stage(root, "app.py", rp.APP_MUL)
    return reason(run_gate(root))


def red_committed_without_the_gate(root):
    """The card's test committed with git directly (no gate, so no row): the code commit then needs a record. Returns HEAD's keys."""
    stage(root, NEW_FILE, rp.RED_MUL)
    w.git(root, "commit", "-q", "-m", "CARD-001 red", when=w.COMMIT_AT)
    return keys_of(root)


def test_a_bad_line_in_the_middle_of_the_shared_file_is_skipped_and_the_rows_around_it_count(tmp_path):
    """Item 1 (R310 2): a line in the middle that is not JSON keeps today's reader behaviour: skipped, the others count."""
    root = root_of(tmp_path)
    tree = committed_test(root)
    seed(shared_file(tmp_path), "0" * 40)
    with open(shared_file(tmp_path), "a", encoding="utf-8", newline="\n") as fh:
        fh.write("this is not json\n")
    seed(shared_file(tmp_path), tree)
    _ready(root)
    assert verdict_of(root) == (True, [])


def test_the_gate_reader_counts_the_rows_before_a_cut_off_last_line(tmp_path):
    """Item 2 (R310 2, both readers): `_record_rows` skips a last line with no newline that is not JSON; the earlier row is the
    card's red record, so the code commit is allowed."""
    root = root_of(tmp_path)
    keys = red_committed_without_the_gate(root)
    seed(shared_file(tmp_path), keys[0])
    with open(shared_file(tmp_path), "a", encoding="utf-8", newline="\n") as fh:
        fh.write('{"card": "CARD-001", "tre')
    assert code_commit_is(root) == "allow"


def test_the_gate_reader_counts_a_last_line_with_no_newline_that_parses(tmp_path):
    """Item 2 (R310 2): the last line lacks only its newline and parses: it is the record."""
    root = root_of(tmp_path)
    keys = red_committed_without_the_gate(root)
    seed(shared_file(tmp_path), keys[0], newline=False)
    assert code_commit_is(root) == "allow"


def test_guard_the_gate_without_a_record_refuses_the_code_commit(tmp_path):
    """GUARD (item 2's nearest deny, green from the start): with no row in the shared folder the same code commit is refused."""
    root = root_of(tmp_path)
    red_committed_without_the_gate(root)
    assert code_commit_is(root) == "red-not-recorded"


def test_guard_a_shared_row_whose_tree_is_in_no_commit_of_head_is_not_a_red_commit(tmp_path):
    """GUARD (item 3, D4, green from the start): the tree test stays: a row of a commit that was never made proves nothing."""
    root = root_of(tmp_path)
    committed_test(root)
    seed(shared_file(tmp_path), "0" * 40)
    _ready(root)
    assert verdict_of(root) == (False, ["verdict-no-red-proof"])


def test_a_busy_refusal_changes_nothing_else_so_the_repeat_is_clean(tmp_path, monkeypatch):
    """Item 4 (R310 1 d): the refused commit leaves HEAD, the index and the working tree as they were, and no row; the marker
    is the other writer's still."""
    monkeypatch.setattr(logs, "APPEND_WAIT_SECONDS", 0.3)
    root = root_of(tmp_path)
    marker = logs.append_lock_path(shared_file(tmp_path))
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("another-writer", encoding="utf-8")
    stage(root, NEW_FILE, rp.RED_MUL)

    def state():
        return (w.git(root, "rev-parse", "HEAD"), w.git(root, "status", "--porcelain"), w.git(root, "diff", "--cached", "--name-only"))
    before = state()
    assert reason(run_gate(root)) == "shared-record-busy"
    assert state() == before
    assert before[2] == NEW_FILE
    assert rows_of(shared_file(tmp_path)) == []
    assert marker.read_text(encoding="utf-8") == "another-writer"


def locked_calls(monkeypatch) -> list:
    """The names of the files the locked writer is called for, from now on (the locked writer still does its work)."""
    calls = []
    real = logs.append_jsonl_locked

    def spy(path, build):
        calls.append(Path(path).name)
        return real(path, build)
    monkeypatch.setattr(logs, "append_jsonl_locked", spy)
    return calls


def test_guard_a_session_run_file_keeps_the_plain_append_and_never_calls_the_locked_writer(tmp_path, monkeypatch):
    """GUARD (item 5, R310 1 g, green from the start): the plain append, the refusal log and the timing log of a session never
    call the locked writer; in a whole red commit and verdict add the locked writer is called for the red proof file only."""
    calls = locked_calls(monkeypatch)
    plain = tmp_path / "plain-run"
    logs.append_jsonl(plain / "gate_calls.jsonl", {"a": 1})
    logs.write_refusal(plain, {"a": 2})
    logs.write_timing(plain, {"a": 3})
    assert calls == []
    root = root_of(tmp_path, shared=False)
    red_commit(root)
    _ready(root)
    assert verdict_of(root) == (True, [])
    assert calls == [RED_FILE]


def test_guard_the_other_card_files_stay_in_their_checkout_state(tmp_path):
    """GUARD (R310 5, green from the start): the take record (`inherited_red.jsonl`), the commit records and the proof rows
    are written into the checkout state; the shared folder holds the red proof and nothing else."""
    import types
    import cardtool
    import gate_commit
    root = root_of(tmp_path)
    profile = w.profile_of(root)
    seed(shared_file(tmp_path), committed_test(root))
    cardtool.record_inherited_red(root, profile, rp.CARD)
    gate_commit.write_records(types.SimpleNamespace(root=root, profile=profile),
                              [("commit_records.jsonl", {"kind": "commit", "session": "s1", "tree": "t", "paths": []})])
    _ready(root)
    assert verdict_of(root) == (True, [])
    assert sorted(p.name for p in (tmp_path / "shared").iterdir()) == [RED_FILE]
    assert {"records.jsonl", "outbox_checks.jsonl", "inherited_red.jsonl", "commit_records.jsonl"} <= {
        p.name for p in w.state_of(root).iterdir()}


def release_at_first_wait(monkeypatch, marker):
    """The holder finishes during the writer's first wait: the wait step deletes the marker, so no timer, no thread and no
    wall clock are involved. Returns the list of wait calls."""
    waits = []

    def wait_step(seconds):
        waits.append(seconds)
        if marker.exists():
            marker.unlink()

    monkeypatch.setattr(logs.time, "sleep", wait_step)
    return waits


def test_a_marker_released_during_the_wait_lets_the_write_through(tmp_path, monkeypatch):
    """Item W3: the other writer finishes while ours waits: the same call writes its row (a writer that never waits fails)."""
    monkeypatch.setattr(logs, "APPEND_WAIT_SECONDS", 5)
    root = root_of(tmp_path)
    marker = logs.append_lock_path(shared_file(tmp_path))
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("another-writer", encoding="utf-8")
    waits = release_at_first_wait(monkeypatch, marker)
    stage(root, NEW_FILE, rp.RED_MUL)
    assert reason(run_gate(root)) == "allow"
    assert len(waits) == 1  # the writer waited once; a writer that never waits fails here
    assert [r["card"] for r in rows_of(shared_file(tmp_path))] == [rp.CARD]


def test_the_check_of_the_key_and_the_append_run_inside_one_lock(tmp_path, monkeypatch):
    """Item W1 (P1): while the check of the key runs, a second writer tries the same file and is kept out by the lock; a check
    outside the lock would let it in between the check and the append."""
    monkeypatch.setattr(logs, "APPEND_WAIT_SECONDS", 0.2)
    root = root_of(tmp_path)
    profile = w.profile_of(root)
    outcome = []
    real_parse = shared().parse

    def parse_with_a_rival(text):
        if not outcome:
            try:
                logs.append_jsonl_locked(shared_file(tmp_path), lambda _t: {"rival": 1})
                outcome.append("written")
            except logs.AppendBusy:
                outcome.append("kept out")
        return real_parse(text)
    monkeypatch.setattr(shared(), "parse", parse_with_a_rival)
    row = {"card": "C-1", "tree": "t1"}
    assert shared().append_row(root, profile, RED_FILE, row, key=("tree", "card")) is True
    assert outcome == ["kept out"]
    assert rows_of(shared_file(tmp_path)) == [row]


# ---- the migration, the rest of R310 3 --------------------------------------------------------------------------------

def test_a_file_with_no_write_key_is_matched_by_equal_rows_and_a_row_with_the_same_id_is_copied(tmp_path, monkeypatch):
    """Item 6 a (R310 3 a): no key means parsed-JSON equality; two rows with the same `id` and other content are two rows, never
    turned away by id; an equal row is present."""
    monkeypatch.setitem(shared().CARD_FILES, "plain.jsonl", None)
    root = root_of(tmp_path)
    wt = worktree(root, tmp_path, "wt-a", "b-a")
    one, other = {"id": 1, "v": "a", "time": T1}, {"id": 1, "v": "b", "time": T2}
    put(w.state_of(root) / "plain.jsonl", [one])
    put(w.state_of(wt) / "plain.jsonl", [one, other])
    report = shared().migrate(root, w.profile_of(root), write=True)
    plain = [f for f in report["files"] if f["file"] == "plain.jsonl"]
    assert plain == [{"file": "plain.jsonl", "found": 3, "copied": 2, "present": 1, "skipped": 0, "turnedAway": 0}]
    assert rows_of(tmp_path / "shared" / "plain.jsonl") == [one, other]


def test_the_migration_writes_through_the_locked_writer_and_never_past_a_held_marker(tmp_path, monkeypatch):
    """Item 6 b (R310 3 a): with the marker of the shared file held the migration fails and writes nothing."""
    monkeypatch.setattr(logs, "APPEND_WAIT_SECONDS", 0.3)
    root, _wt_a, _wt_c, _rows = migration_world(tmp_path)
    marker = logs.append_lock_path(shared_file(tmp_path))
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("another-writer", encoding="utf-8")
    with pytest.raises(shared().MigrationFailed):
        shared().migrate(root, w.profile_of(root), write=True)
    assert not shared_file(tmp_path).exists()
    assert marker.read_text(encoding="utf-8") == "another-writer"


def test_the_migration_waits_for_a_marker_released_during_the_wait(tmp_path, monkeypatch):
    """Item 6 b (W3): the other writer finishes during the wait: the migration then writes all its rows."""
    monkeypatch.setattr(logs, "APPEND_WAIT_SECONDS", 5)
    root, _wt_a, _wt_c, (a, b, d, _e) = migration_world(tmp_path)
    marker = logs.append_lock_path(shared_file(tmp_path))
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("another-writer", encoding="utf-8")
    waits = release_at_first_wait(monkeypatch, marker)
    shared().migrate(root, w.profile_of(root), write=True)
    assert len(waits) == 1  # the migration waited once; a writer that never waits fails here
    assert rows_of(shared_file(tmp_path)) == [a, d, b]


def test_ties_and_rows_with_no_time_keep_source_order_main_first_then_the_worktrees_in_git_order(tmp_path):
    """Item 7 (R310 3 b): rows with a time are ordered by it, ties in source order; a row with no time keeps its place in the
    source list. Source list: main a(T3), n1, b(T1); wt-a n2, c(T1); wt-b d(T1). The tied rows b, c, d have the trees z, m, a, so
    name order is d, c, b; their files are written wt-b, wt-a, main, so creation order is d, c, b too: only source order gives
    b, c, d."""
    root = root_of(tmp_path)
    wt_a = worktree(root, tmp_path, "wt-a", "b-a")
    wt_b = worktree(root, tmp_path, "wt-b", "b-b")
    a = mrow("C-1", "t-top", T3)
    b, c, d = (mrow("C-1", f"t-{x}", T1) for x in ("z", "m", "a"))
    n1, n2 = ({k: v for k, v in mrow("C-1", f"t-{x}", T1).items() if k != "time"} for x in ("n1", "n2"))
    put(w.state_of(wt_b) / RED_FILE, [d])
    put(w.state_of(wt_a) / RED_FILE, [n2, c])
    put(w.state_of(root) / RED_FILE, [a, n1, b])
    shared().migrate(root, w.profile_of(root), write=True)
    assert rows_of(shared_file(tmp_path)) == [b, n1, c, n2, d, a]


def test_the_worktree_with_a_state_file_but_a_broken_link_is_prunable_and_its_rows_are_not_read(tmp_path):
    """Item W4: the folder and the state file exist, git reports the entry prunable: its row is never copied."""
    root, _wt_a, _wt_c, _rows = migration_world(tmp_path)
    assert (w.state_of(tmp_path / "wt-b") / RED_FILE).is_file()
    shared().migrate(root, w.profile_of(root), write=True)
    assert "C-9" not in {r["card"] for r in rows_of(shared_file(tmp_path))}


# ---- R317 7: `_others_red` reads the shared folder, so it sees the red rows of other checkouts ------------------------------

OLD_TEST = "tests/test_ok.py::test_add"  # the one test of the project at HEAD
EMPTY = "# no test is left in this file\n"
MAP_LINE = f"{OLD_TEST} -> {NODE}"


def decided_root(tmp_path):
    """The main checkout with a decision pattern for case-map lines and the shared folder set."""
    return rp.red_project(tmp_path, name="main", tests={"red_proof": {"decision_pattern": "DEC-[0-9]+"}},
                          state={"dir": "mkway/state", "shared_dir": str(tmp_path / "shared")})


def map_rel(root) -> str:
    return rp.card_file(root).parent.relative_to(Path(root)).as_posix() + "/case_map.md"


def stage_rename(root):
    stage(root, NEW_FILE, rp.RED_MUL)
    stage(root, "tests/test_ok.py", EMPTY)
    stage(root, map_rel(root), MAP_LINE + "\n")


def rename_gate(root):
    return run_gate(root, 'git commit -m "CARD-001 DEC-1 rename"')


def red_row_from_a_worktree(root, tmp_path, card, merged=True):
    """A worktree makes a commit, its gate leaves the red row of `card` for the existing test in the shared folder, and the
    branch is merged into main (the row is written the way the gate writes it: `shared_records.append_row`)."""
    wt = worktree(root, tmp_path)
    stage(wt, "notes.txt", "work of the other card\n")
    w.git(wt, "commit", "-q", "-m", "other card work", when=w.COMMIT_AT)
    row = {"time": T1, "session": "s9", "card": card, "tree": keys_of(wt)[1], "red": [OLD_TEST], "pins": [], "checks": [],
           "missing": {}, "would_refuse": [], "mode": "trip"}
    assert shared().append_row(root, w.profile_of(root), RED_FILE, row, key=("tree", "card")) is True
    if merged:
        merge(root)


def test_a_red_row_of_another_card_written_in_a_worktree_holds_back_a_case_map_line_in_main(tmp_path):
    """Catches: R317 7, the intended rule across checkouts: once the other card's commit is merged into this HEAD, a case-map
    line that moves its red test is refused `case-map-unknown-left` (the line is in the red record of that card)."""
    root = decided_root(tmp_path)
    red_row_from_a_worktree(root, tmp_path, "CARD-009")
    stage_rename(root)
    verdict = rename_gate(root)
    assert reason(verdict) == "case-map-unknown-left"
    assert verdict.message == (f"case_map.md line 1 `{MAP_LINE}`: case-map-unknown-left: {OLD_TEST} is in the red record of "
                               f"CARD-009, which belongs to that card. A refused commit changes nothing: the index and the "
                               f"working tree stay as they are.")


def test_the_same_case_map_line_before_the_merge_is_allowed_so_the_merge_makes_the_row_visible(tmp_path):
    """Checks: R317 7, the nearest allow: the other card's row is in the shared folder but its commit is not yet a commit of
    this HEAD, so the same line is allowed; the merge is what makes the other row visible."""
    root = decided_root(tmp_path)
    red_row_from_a_worktree(root, tmp_path, "CARD-009", merged=False)
    stage_rename(root)
    assert reason(rename_gate(root)) == "allow"


def test_the_way_out_of_the_held_back_line_is_the_commit_without_it_and_it_needs_no_owner(tmp_path):
    """Checks: the way out a session can use: leave the other card's test where it is and commit only this card's own red test;
    the rename is the work of the card whose red record holds the test."""
    root = decided_root(tmp_path)
    red_row_from_a_worktree(root, tmp_path, "CARD-009")
    stage_rename(root)
    assert reason(rename_gate(root)) == "case-map-unknown-left"
    plain_git(root, "reset", "-q", "--", "tests/test_ok.py", map_rel(root))
    plain_git(root, "checkout", "--", "tests/test_ok.py")
    assert plain_git(root, "diff", "--cached", "--name-only").split() == [NEW_FILE]
    assert reason(run_gate(root)) == "allow"


def test_the_red_row_of_the_committing_card_itself_from_a_worktree_does_not_hold_the_line_back(tmp_path):
    """Checks: the other way out, the rename by the card that holds the record: a row of CARD-001 (this card) from a worktree
    is no other card's red, so the same line is allowed."""
    root = decided_root(tmp_path)
    red_row_from_a_worktree(root, tmp_path, rp.CARD)
    stage_rename(root)
    assert reason(rename_gate(root)) == "allow"
