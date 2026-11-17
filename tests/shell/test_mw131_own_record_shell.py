"""Card MW-131 (decisions: R314, R316, R317, R320, R322, R323), layer shell, on real git repositories: how the commit gate finds a
card's OWN red record in the history of HEAD however many unrelated commits followed the red commit. The gate is the real
`gate_commit_tests.check` (`run_gate`); rows tied to synthetic commit dates are written by hand (`_seed`), as MW-130's tests do;
the long histories are built with one `git fast-import` (`_mw130.chain`). The helpers of MW-130 (`_mw130`) are reused, not
copied. Synthetic names only."""
import itertools
import json
import sys
import time
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/: the shared helpers and `_engine`
import _mw080 as w  # noqa: E402
import _mw130 as m  # noqa: E402
from _commit_project import reason, run_gate, stage  # noqa: E402
import core_red  # noqa: E402
import gate_commit_tests as gct  # noqa: E402
import runner  # noqa: E402
import verdict_add  # noqa: E402

CAP = 3  # the patched limit of the search, in ticks of the fake clock; it is also the value of OWN_RECORD_SEARCH_SECONDS (R323)
OTHER = "tests/test_other.py::test_x"
TAIL = ". A refused commit changes nothing: the index and the working tree stay as they are."
TEXT_I = ("red-not-recorded: CARD-001 has no red record: no tests-only commit of the card was recorded as red; commit the "
          "failing tests first, alone (the gate runs them and records the red), then commit the code; if they were committed in "
          "another checkout, commit the code there")
TEXT_II = ("red-not-recorded: CARD-001 has red record rows, but none of them belongs to a commit in the history of HEAD: the "
           "red commit was not made, or it sits on a branch that is not merged here; commit the code where the red tests were "
           "committed, or, if they were never committed, commit a failing test of the card first, alone (the gate runs it and "
           "records the red), then commit the code")
TEXT_IV = ("red-not-recorded: the git history of HEAD could not be read, so the red record of CARD-001 could not be checked; "
           "repeat the call")


def partial_line(times) -> str:
    """The warn `red-record-partial` for legacy rows left out, at the limit of the fake clock (R322, the wording of R324)."""
    return (f"red-record-partial: the red record of CARD-001 was read without {len(times)} older row(s) written with no git "
            f"tree (times {', '.join(times)}) because the search for them ran out of time (limit {CAP} s); the check goes on "
            "with the rows that were found; this line needs no action")


def text_iii(checked: int) -> str:
    return (f"red-not-recorded: the search for the older red record rows of CARD-001 (written with no git tree) ran out of "
            f"time (limit {CAP} s) after {checked} git trees checked, and no row was found; commit a failing test of the card, "
            "alone (the gate runs it and records the red; a further tests-only red commit renews the record), then commit "
            "the code")


# ---- the setup helpers -----------------------------------------------------------------------------------------------------

def _root(tmp_path):
    """A task root with one open card CARD-001 held by session s1, whose red test file (`m.NEW_FILE`) is committed with plain
    git, so no gate made a record: the rows of a test are written by hand."""
    root = m.red_project(tmp_path, row=f"| E1 | item | was | must | {m.NEW} |")
    stage(root, m.NEW_FILE, m.RED_MUL)
    w.git(root, "commit", "-q", "-m", "CARD-001 red", when=m.RED_AT)
    return root


def _tree(root, rev) -> str:
    return w.git(root, "rev-parse", f"{rev}^{{tree}}")


def _seed(root, *, tree, git_tree=None, time=None, red=(m.NEW,), card=w.CARD) -> None:
    """One red-proof row written by hand into the shared folder; `git_tree` None: a legacy row, digest only."""
    row = {"time": time or m.iso_at(int(w.at(0).timestamp())), "session": "s1", "card": card, "tree": tree, "red": list(red),
           "pins": [], "checks": [], "missing": {}, "would_refuse": [], "mode": "trip"}
    if git_tree is not None:
        row["git_tree"] = git_tree
    path = m.red_file(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def _new_row(root, rev, **kw) -> None:
    """A new row of the commit `rev`, as the gate writes it: the digest of its tree and its git tree id."""
    _seed(root, tree=m.digest_of(root, rev), git_tree=_tree(root, rev), **kw)


def _code(root):
    """The card's own code commit, judged by the real gate: the verdict."""
    stage(root, "app.py", m.APP_MUL)
    return run_gate(root)


def _fake_clock(monkeypatch):
    """The clock of the search ticks once per reading, and the limit is patched to `CAP` ticks."""
    ticks = itertools.count()
    monkeypatch.setattr(gct, "_clock", lambda: next(ticks))
    monkeypatch.setattr(gct, "OWN_RECORD_SEARCH_SECONDS", CAP)


def _fail_history(monkeypatch, state=None):
    """Every git read of the history of HEAD (`log`, `rev-list`) raises a timeout while `state["down"]` is true."""
    real = runner.git
    state = {"down": True} if state is None else state

    def git(root, *args, **kw):
        if state["down"] and args and args[0] in ("log", "rev-list"):
            raise runner.TimeoutExpired("git", 1)
        return real(root, *args, **kw)
    monkeypatch.setattr(runner, "git", git)
    return state


def _spy_decide(monkeypatch) -> list:
    """The facts the gate hands to `core_red.decide`, in order."""
    seen, real = [], core_red.decide

    def decide(facts):
        seen.append(facts)
        return real(facts)
    monkeypatch.setattr(core_red, "decide", decide)
    return seen


def _time_search(monkeypatch) -> list:
    """The seconds of every call of the one search `find_red_rows`."""
    spent, real = [], gct.find_red_rows

    def timed(*args, **kw):
        began = time.perf_counter()
        try:
            return real(*args, **kw)
        finally:
            spent.append(time.perf_counter() - began)
    monkeypatch.setattr(gct, "find_red_rows", timed)
    return spent


def _git_calls(monkeypatch) -> list:
    """The (first word, timeout) of every `runner.git` call."""
    seen, real = [], runner.git

    def git(root, *args, **kw):
        seen.append((args[:1], kw.get("timeout")))
        return real(root, *args, **kw)
    monkeypatch.setattr(runner, "git", git)
    return seen


def _red_commit(root) -> None:
    """The way out: the staged code is put aside, the red test is committed alone through the real gate."""
    w.git(root, "restore", "--staged", "--", "app.py")
    stage(root, m.NEW_FILE, m.RED_MUL)
    assert reason(run_gate(root)) == "allow"
    w.git(root, "commit", "-q", "-m", "CARD-001 red again")


# ---- the card's own code commit after many unrelated commits -----------------------------------------------------------------
# E1 and E3 are MW-130's tests (tests/shell/test_mw130_tree_search_shell.py), cited in the card, not copied.

def test_a_legacy_row_is_found_after_61_unrelated_commits_by_the_code_commit(tmp_path):
    """Catches: a row with no git_tree (written before MW-130) lost by the gate after 61 commits; the row time is the 5 s
    before the red commit that the gate writes it at."""
    root = m.gated(tmp_path)
    red_time = m.committer_time(root, "HEAD")
    m.chain(root, 61)

    def legacy(row):
        row.pop("git_tree", None)
        row["time"] = m.iso_at(red_time - 5)
    m.rewrite(root, legacy)
    assert all("git_tree" not in r for r in m.rows(root))
    assert reason(_code(root)) == "allow"


def test_guard_two_new_rows_one_found_and_one_never_committed_give_the_record_of_the_found_row(tmp_path, monkeypatch):
    """Checks: GUARD (green today): under 60 commits the record is exactly the found row's ids; the row of a commit that was
    never made adds nothing to it, and an unfound NEW row prints nothing (DESIGN 5): the verdict is an allow, not a warn."""
    root = _root(tmp_path)
    _new_row(root, "HEAD")
    _seed(root, tree="1" * 64, git_tree=m.FAR, red=(OTHER,))
    m.chain(root, 3)
    seen = _spy_decide(monkeypatch)
    verdict = _code(root)
    assert verdict.kind == "allow" and "red-record-partial" not in verdict.message
    record = seen[-1].record
    assert (record.red, record.pins, record.files) == (frozenset({m.NEW}), frozenset(), frozenset())


def test_a_found_new_row_and_a_never_committed_new_row_after_61_commits_allow_with_no_digest(tmp_path, monkeypatch):
    """Catches: the 60-commit window of the gate, and a digest computed for a new row: the two new rows need none."""
    root = _root(tmp_path)
    _new_row(root, "HEAD")
    _seed(root, tree="1" * 64, git_tree=m.FAR, red=(OTHER,))
    m.chain(root, 61)
    calls = m.count_digests(monkeypatch)
    verdict = _code(root)
    assert verdict.kind == "allow" and "red-record-partial" not in verdict.message  # an unfound new row prints nothing
    assert calls == []


def test_a_new_row_4900_commits_back_is_found_by_the_gate_in_less_than_the_git_seconds(tmp_path, monkeypatch):
    """Catches: a new row lost, or a search that takes longer than one git call may, on a history of 5 000 commits."""
    root = _root(tmp_path)
    shas = m.chain(root, 5000)
    target = shas[99]  # 4 900 commits back from HEAD
    assert int(w.git(root, "rev-list", "--count", f"{target}..HEAD")) == 4900
    _new_row(root, target)
    calls = m.count_digests(monkeypatch)
    spent = _time_search(monkeypatch)
    verdict = _code(root)
    print(f"MW131 SECONDS the gate's search, new row 4900 back of 5000: {spent[0]:.2f}")
    assert reason(verdict) == "allow"
    assert calls == []
    assert len(spent) == 1 and spent[0] < gct.GIT_SECONDS


def test_a_legacy_row_4900_commits_back_is_found_by_the_gate_with_one_digest(tmp_path, monkeypatch):
    """Catches: the nearest-first order lost: a legacy row 5 s before its commit must cost exactly one digest, not a walk from
    HEAD (every commit has its own tree, so a newest-first walk needs 4 900)."""
    root = _root(tmp_path)
    shas = m.chain(root, 5000)
    target = shas[99]
    _seed(root, tree=m.digest_of(root, target), time=m.iso_at(m.committer_time(root, target) - 5))
    calls = m.count_digests(monkeypatch)
    spent = _time_search(monkeypatch)
    verdict = _code(root)
    print(f"MW131 SECONDS the gate's search, legacy row 4900 back of 5000: {spent[0]:.2f}")
    assert reason(verdict) == "allow"
    assert calls == [_tree(root, target)]


# ---- the limit, the queue and the digests ------------------------------------------------------------------------------------

def test_a_never_committed_legacy_row_meets_the_limit_and_the_gate_refuses_with_text_iii(tmp_path, monkeypatch):
    """Catches: a search with no limit, or at the limit the answer «no row»: the text names the git trees checked (2: the fake
    clock ticks once per reading and the limit is 3 ticks)."""
    root = _root(tmp_path)
    m.chain(root, 3)
    _seed(root, tree="a" * 64)
    _fake_clock(monkeypatch)
    verdict = _code(root)
    assert (verdict.kind, verdict.reason_id) == ("refuse", "red-not-recorded")
    assert verdict.message == text_iii(2) + TAIL


def test_a_real_legacy_row_is_found_before_a_never_committed_row_with_a_newer_time(tmp_path, monkeypatch):
    """Catches: one queue per row, searched one after the other: the never-committed row, whose time is the newest, must not
    take the limit away from a real row that sits near its own commit (68 commits back; the limit allows two digests)."""
    root = _root(tmp_path)
    shas = m.chain(root, 70)
    _seed(root, tree=m.digest_of(root, shas[2]), time=m.iso_at(m.committer_time(root, shas[2]) - 5))
    _seed(root, tree="a" * 64, time=m.iso_at(m.committer_time(root, shas[-1]) + 1), red=(OTHER,))
    _fake_clock(monkeypatch)
    calls = m.count_digests(monkeypatch)
    assert reason(_code(root)) == "allow"
    assert calls == [_tree(root, shas[-1]), _tree(root, shas[2])]


def test_two_legacy_rows_of_the_same_tree_cost_one_digest(tmp_path, monkeypatch):
    """Catches: a digest computed once per row: two rows of the same tree are compared with one digest."""
    root = _root(tmp_path)
    shas = m.chain(root, 5)
    digest, stamp = m.digest_of(root, shas[1]), m.committer_time(root, shas[1])
    _seed(root, tree=digest, time=m.iso_at(stamp - 5))
    _seed(root, tree=digest, time=m.iso_at(stamp - 9))
    calls = m.count_digests(monkeypatch)
    assert reason(_code(root)) == "allow"
    assert calls == [_tree(root, shas[1])]


def test_two_never_committed_legacy_rows_stop_at_one_limit_in_total(tmp_path, monkeypatch):
    """Catches: a limit per row: two legacy rows that were never committed stop at the same 2 git trees checked as one row
    does (a limit per row would check 4)."""
    root = _root(tmp_path)
    m.chain(root, 3)
    _seed(root, tree="a" * 64)
    _seed(root, tree="b" * 64)
    _fake_clock(monkeypatch)
    calls = m.count_digests(monkeypatch)
    verdict = _code(root)
    assert len(calls) == 2
    assert verdict.message == text_iii(2) + TAIL


def test_a_row_whose_tree_is_a_git_tree_id_is_found_by_the_listing_with_no_digest(tmp_path, monkeypatch):
    """Catches: a row whose `tree` has the 40 hex of a git tree id lost after 61 commits, or matched by a digest."""
    root = _root(tmp_path)
    shas = m.chain(root, 70)
    _seed(root, tree=_tree(root, shas[2]))
    calls = m.count_digests(monkeypatch)
    assert reason(_code(root)) == "allow"
    assert calls == []


def test_a_legacy_row_with_no_readable_time_is_found_and_searched_newest_first(tmp_path, monkeypatch):
    """Catches: a legacy row whose time cannot be read searched oldest first or in no order: the trees are digested from the
    commit with the newest committer time down until the row is found on the oldest chain commit. The times are read from
    `git log` (the fixture's first commits carry the date of the day, so HEAD is not the newest) and the check does not depend
    on how commits of the same second are ordered: the committer times of the digested trees never rise, the last tree digested
    is the row's, and the digested trees are exactly those of the commits not older than it (the chain times are distinct)."""
    root = _root(tmp_path)
    shas = m.chain(root, 3)
    target = _tree(root, shas[0])
    _seed(root, tree=m.digest_of(root, shas[0]), time="not a time")
    stamp_of = {}
    for line in w.git(root, "log", "--format=%ct %T", "HEAD").splitlines():
        stamp, tree = line.split()
        stamp_of[tree] = max(int(stamp), stamp_of.get(tree, 0))
    calls = m.count_digests(monkeypatch)
    assert reason(_code(root)) == "allow"
    assert calls[-1] == target and len(calls) > 1
    assert [stamp_of[t] for t in calls] == sorted((stamp_of[t] for t in calls), reverse=True)
    assert sorted(calls) == sorted(t for t, stamp in stamp_of.items() if stamp >= stamp_of[target])


def test_a_distance_tie_digests_the_newer_commit_first(tmp_path, monkeypatch):
    """Catches: a tie between two commits at the same distance from the row time broken in favour of the older commit."""
    root = _root(tmp_path)
    shas = m.chain(root, 3)
    _seed(root, tree="a" * 64, time=m.iso_at(m.committer_time(root, shas[1]) + 30))  # 30 s from commit 1 and from commit 2
    calls = m.count_digests(monkeypatch)
    _code(root)
    assert calls[:2] == [_tree(root, shas[2]), _tree(root, shas[1])]


# ---- the partial find ------------------------------------------------------------------------------------------------------

def test_the_limit_running_out_after_a_found_row_allows_with_the_found_rows_and_one_line(tmp_path, monkeypatch):
    """Catches: a found row thrown away because another row was not found, or a row dropped silently: the call is allowed
    with the found row's ids and one warn line names the count and the time of the legacy row that was left out (R322)."""
    root = _root(tmp_path)
    _new_row(root, "HEAD")
    _seed(root, tree="a" * 64, time="2026-11-16T10:00:00.000+00:00", red=(OTHER,))
    m.chain(root, 3)
    _fake_clock(monkeypatch)
    seen = _spy_decide(monkeypatch)
    verdict = _code(root)
    assert (verdict.kind, verdict.reason_id) == ("warn", "red-record-partial")
    assert verdict.message == ("red-record-partial: the red record of CARD-001 was read without 1 older row(s) written with no "
                               "git tree (times 2026-11-16T10:00:00.000+00:00) because the search for them ran out of time "
                               f"(limit {CAP} s); the check goes on with the rows that were found; this line needs no action")
    assert seen[-1].record.red == frozenset({m.NEW})


# ---- the four texts ----------------------------------------------------------------------------------------------------------

def test_a_card_with_no_row_is_refused_with_text_i(tmp_path):
    """Catches: «no row» told with the way out «commit the code where the red tests were committed», which no session can
    run when no red commit exists: the text tells to commit the failing tests first, alone, then the code."""
    root = _root(tmp_path)
    verdict = _code(root)
    assert (verdict.kind, verdict.reason_id) == ("refuse", "red-not-recorded")
    assert verdict.message == TEXT_I + TAIL


def test_a_new_row_that_no_commit_has_is_refused_with_text_ii(tmp_path):
    """Catches: rows that exist but whose trees no commit has, told as «no row»: text (ii) names both causes (the red commit was
    not made, or it sits on a branch not merged here) and starts with the way out for the second."""
    root = _root(tmp_path)
    _seed(root, tree="0" * 64, git_tree=m.FAR)
    verdict = _code(root)
    assert (verdict.kind, verdict.reason_id) == ("refuse", "red-not-recorded")
    assert verdict.message == TEXT_II + TAIL


def test_a_legacy_row_that_no_commit_has_is_refused_with_text_ii_not_iii(tmp_path):
    """Catches: a legacy row that was never committed, in a short history that the search walks to its end inside the limit,
    told as «ran out of time»: the history was searched whole, so it is text (ii)."""
    root = _root(tmp_path)
    m.chain(root, 3)
    _seed(root, tree="a" * 64)
    verdict = _code(root)
    assert (verdict.kind, verdict.reason_id) == ("refuse", "red-not-recorded")
    assert verdict.message == TEXT_II + TAIL


def test_a_git_history_that_cannot_be_read_is_refused_with_text_iv(tmp_path, monkeypatch):
    """Catches: a git that does not answer told as «no row» or as «out of time»: text (iv), way out «repeat the call»."""
    root = _root(tmp_path)
    _new_row(root, "HEAD")
    _fail_history(monkeypatch)
    verdict = _code(root)
    assert (verdict.kind, verdict.reason_id) == ("refuse", "red-not-recorded")
    assert verdict.message == TEXT_IV + TAIL


def test_a_history_listing_with_a_non_zero_exit_is_refused_with_text_iv(tmp_path, monkeypatch):
    """Catches: a `git log` that exits non-zero read as an empty history («no commit has it») or as found: text (iv)."""
    root = _root(tmp_path)
    _new_row(root, "HEAD")
    real = runner.git

    def git(root_, *args, **kw):
        if args and args[0] == "log":
            return types.SimpleNamespace(returncode=128, stdout="", stderr="fatal: bad object HEAD")
        return real(root_, *args, **kw)
    monkeypatch.setattr(runner, "git", git)
    verdict = _code(root)
    assert (verdict.kind, verdict.reason_id) == ("refuse", "red-not-recorded")
    assert verdict.message == TEXT_IV + TAIL


def test_guard_a_row_whose_tree_is_in_no_commit_of_head_is_refused_as_not_recorded(tmp_path):
    """Checks: GUARD (green today): never weaker: a row of a commit that was never made, with a git_tree and a digest that no commit
    has, in a history of 5 commits, counts for nothing."""
    root = _root(tmp_path)
    m.chain(root, 3)
    _seed(root, tree="0" * 64, git_tree=m.FAR)
    assert reason(_code(root)) == "red-not-recorded"


def test_a_tree_the_digest_step_cannot_list_does_not_match_and_the_gate_finds_the_row_on_a_later_one(tmp_path, monkeypatch):
    """Catches: an `ls-tree` error for the nearest commit that ends the search: that commit does not match, the next one is
    digested and matches."""
    root = _root(tmp_path)
    shas = m.chain(root, 3)
    broken = _tree(root, shas[1])
    # the row is 5 s before commit 1 (the nearest, 5 s), then commit 0 (55 s), then commit 2 (65 s)
    _seed(root, tree=m.digest_of(root, shas[0]), time=m.iso_at(m.committer_time(root, shas[1]) - 5))
    real = gct._listing
    monkeypatch.setattr(gct, "_listing", lambda root_, rev: None if rev == broken else real(root_, rev))
    calls = m.count_digests(monkeypatch)
    assert reason(_code(root)) == "allow"
    assert calls == [broken, _tree(root, shas[0])]


# ---- the way outs ------------------------------------------------------------------------------------------------------------

def test_the_way_out_of_text_i_is_a_tests_only_red_commit_then_the_code(tmp_path):
    """Checks: text (i) names a way out a session can run with no owner: the failing test committed alone, then the code."""
    root = m.red_project(tmp_path, row=f"| E1 | item | was | must | {m.NEW} |")
    assert _code(root).message == TEXT_I + TAIL
    _red_commit(root)
    assert reason(_code(root)) == "allow"


def test_the_way_out_of_text_ii_is_a_further_tests_only_red_commit(tmp_path):
    """Checks: text (ii): a further tests-only red commit of the card renews the record, then the code commit is allowed."""
    root = m.red_project(tmp_path, row=f"| E1 | item | was | must | {m.NEW} |")
    _seed(root, tree="0" * 64, git_tree=m.FAR)
    assert _code(root).message == TEXT_II + TAIL
    _red_commit(root)
    assert reason(_code(root)) == "allow"


def test_the_way_out_of_text_iii_is_a_further_tests_only_red_commit_with_the_old_row_present(tmp_path, monkeypatch):
    """Checks: text (iii): with the never-committed legacy row still in the file, a further tests-only red commit gives a row
    the listing finds, and the code commit is allowed (the old row is left out, with the partial line)."""
    root = m.red_project(tmp_path, row=f"| E1 | item | was | must | {m.NEW} |")
    m.chain(root, 3)  # distinct trees enough for the limit, not the end of the history, to stop the search
    _seed(root, tree="a" * 64, time="2026-11-16T10:00:00.000+00:00")
    _fake_clock(monkeypatch)
    assert _code(root).message == text_iii(2) + TAIL
    _red_commit(root)
    verdict = _code(root)
    assert (verdict.kind, verdict.reason_id) == ("warn", "red-record-partial")
    assert verdict.message == partial_line(["2026-11-16T10:00:00.000+00:00"])


def test_the_way_out_of_text_iv_is_to_repeat_the_call(tmp_path, monkeypatch):
    """Checks: text (iv): the same call repeated with git answering again is allowed."""
    root = _root(tmp_path)
    _new_row(root, "HEAD")
    state = _fail_history(monkeypatch)
    assert _code(root).message == TEXT_IV + TAIL
    state["down"] = False
    assert reason(run_gate(root)) == "allow"


# ---- scope and the rest of the design ----------------------------------------------------------------------------------------

def test_guard_others_red_still_stops_at_the_tree_limit(tmp_path):
    """Checks: GUARD (green today): `_others_red` keeps TREE_LIMIT (60 commits): another card's row 61 commits back is not in its
    result, a row inside the window is."""
    root = _root(tmp_path)
    shas = m.chain(root, 61)
    _seed(root, tree=_tree(root, shas[0]), red=("tests/test_far.py::test_old",), card="CARD-008")
    _seed(root, tree=_tree(root, shas[2]), red=("tests/test_near.py::test_new",), card="CARD-009")
    run = types.SimpleNamespace(ctx=types.SimpleNamespace(root=root), profile=w.profile_of(root), folder=root)
    assert gct._others_red(run, "CARD-001") == {"tests/test_near.py::test_new": "CARD-009"}


def test_guard_a_new_test_id_committed_with_code_still_gets_test_without_red_proof(tmp_path):
    """Checks: GUARD (green today): the branch of a new test id committed with its code is unchanged: none of the four causes
    fires (no row at all: cause (i))."""
    root = _root(tmp_path)
    stage(root, "tests/test_fresh.py", m.RED_MUL.replace("test_mul", "test_fresh_mul"))
    stage(root, "app.py", m.APP_MUL)
    verdict = run_gate(root)
    assert (verdict.kind, verdict.reason_id) == ("refuse", "test-without-red-proof")
    assert "red-not-recorded" not in verdict.message


def test_guard_a_new_test_id_committed_with_code_and_rows_that_no_commit_has_still_gets_test_without_red_proof(tmp_path):
    """Checks: GUARD (green today): the same with a row that exists and that no commit of HEAD has (cause (ii)): the branch of a
    new test id wins, and `red-not-recorded` does not appear."""
    root = _root(tmp_path)
    _seed(root, tree="0" * 64, git_tree=m.FAR)
    stage(root, "tests/test_fresh.py", m.RED_MUL.replace("test_mul", "test_fresh_mul"))
    stage(root, "app.py", m.APP_MUL)
    verdict = run_gate(root)
    assert (verdict.kind, verdict.reason_id) == ("refuse", "test-without-red-proof")
    assert "red-not-recorded" not in verdict.message


def test_guard_a_card_with_no_row_makes_no_git_log_call(tmp_path, monkeypatch):
    """Checks: GUARD (green today): DESIGN 1: no listing is read when the card has no row."""
    root = _root(tmp_path)
    seen = _git_calls(monkeypatch)
    _code(root)
    assert [call for call, _timeout in seen].count(("log",)) == 0


def test_a_card_with_rows_makes_exactly_one_git_log_call(tmp_path, monkeypatch):
    """Catches: DESIGN 1: the whole history is listed by ONE `log` call per gate call, however many rows there are."""
    root = _root(tmp_path)
    _new_row(root, "HEAD")
    _seed(root, tree="1" * 64, git_tree=m.FAR, red=(OTHER,))
    seen = _git_calls(monkeypatch)
    assert reason(_code(root)) == "allow"
    assert [call for call, _timeout in seen].count(("log",)) == 1


def test_verdict_add_and_the_gate_call_the_same_search(tmp_path, monkeypatch):
    """Catches: R317 4: a second copy of the search: both callers reach the one function `find_red_rows` (patched here), each
    with its own limit, `verdict add` the 60 s cap and the gate its own."""
    root = m.gated(tmp_path)
    real, calls = gct.find_red_rows, []

    def spy(root_, rows, limit, clock, *args, **kw):
        calls.append(limit)
        return real(root_, rows, limit, clock, *args, **kw)
    monkeypatch.setattr(gct, "find_red_rows", spy)
    code, _out, err = m.add(root)
    assert (code, "verdict-no-red-proof" in err) == (0, False), err
    assert reason(_code(root)) == "allow"
    assert calls == [60, 3]


def test_each_ls_tree_of_the_search_gets_the_time_left_as_its_timeout(tmp_path, monkeypatch):
    """Catches: DESIGN 4: an `ls-tree` of the search with the full GIT_SECONDS, so one slow git can run past the limit: with a
    limit of 3 ticks the two digests get 2 and 1 (the time left at their start)."""
    root = _root(tmp_path)
    m.chain(root, 3)
    _seed(root, tree="a" * 64)
    _fake_clock(monkeypatch)
    seen = _git_calls(monkeypatch)
    _code(root)
    assert [timeout for call, timeout in seen if call == ("ls-tree",)] == [2, 1]


def test_guard_a_limit_above_git_seconds_gives_the_listing_and_each_ls_tree_the_git_seconds(tmp_path, monkeypatch):
    """Checks: GUARD (green today): DESIGN 4, min(GIT_SECONDS, time left): with a limit of 1000 ticks the time left is far
    above 30, so every `ls-tree` of the search and the listing (`log`) get 30 s, never more."""
    root = _root(tmp_path)
    m.chain(root, 3)
    _seed(root, tree="a" * 64)
    ticks = itertools.count()
    monkeypatch.setattr(gct, "_clock", lambda: next(ticks))
    monkeypatch.setattr(gct, "OWN_RECORD_SEARCH_SECONDS", 1000)
    seen = _git_calls(monkeypatch)
    _code(root)
    walked = [timeout for call, timeout in seen if call == ("ls-tree",)]
    assert len(walked) > 1 and set(walked) == {30}
    assert [timeout for call, timeout in seen if call == ("log",)] == [30]


def test_guard_a_found_row_leaves_the_queue_and_the_next_digest_follows_the_rows_that_remain(tmp_path, monkeypatch):
    """Checks: GUARD (green today): DESIGN 3: one queue, ranked again when a row is found. Row A (digest of commit 1) sits 5 s
    before its commit, row B (never committed) 20 s after commit 4. Ranked by the nearest row the order is 1, 4, 5, 0, 2, 3;
    once A is found at the first digest the ranking follows B alone: 4, 5, 3 (commit 3 is 100 s from B, commit 0 would still
    be 55 s from A)."""
    root = _root(tmp_path)
    shas = m.chain(root, 6)
    stamp = [m.committer_time(root, sha) for sha in shas]
    _seed(root, tree=m.digest_of(root, shas[1]), time=m.iso_at(stamp[1] - 5))
    _seed(root, tree="b" * 64, time=m.iso_at(stamp[4] + 20), red=(OTHER,))
    calls = m.count_digests(monkeypatch)
    assert reason(_code(root)) == "allow"
    assert calls[:4] == [_tree(root, shas[1]), _tree(root, shas[4]), _tree(root, shas[5]), _tree(root, shas[3])]


def test_guard_a_row_with_no_readable_time_ranks_after_every_timed_row(tmp_path, monkeypatch):
    """Checks: GUARD (green today): DESIGN 3: with a timed row and an untimed row still to find, the queue follows the timed
    row (commit 1 is 5 s from it, then 0 at 55 s, then 2 at 65 s), not the newest commit that an untimed row alone would
    give."""
    root = _root(tmp_path)
    shas = m.chain(root, 6)
    _seed(root, tree="a" * 64, time=m.iso_at(m.committer_time(root, shas[1]) - 5))
    _seed(root, tree="b" * 64, time="not a time", red=(OTHER,))
    calls = m.count_digests(monkeypatch)
    _code(root)
    assert calls[:3] == [_tree(root, shas[1]), _tree(root, shas[0]), _tree(root, shas[2])]


def test_guard_two_commits_sharing_one_tree_are_digested_once(tmp_path, monkeypatch):
    """Checks: GUARD (green today): DESIGN 3: each DISTINCT tree is digested once, not once per commit: two empty commits on top
    of the chain share the tree of the last chain commit, and every distinct tree of the history is digested exactly once."""
    root = _root(tmp_path)
    m.chain(root, 3)
    for n in (1, 2):
        w.git(root, "commit", "-q", "--allow-empty", "-m", f"same tree {n}")
    _seed(root, tree="a" * 64)
    calls = m.count_digests(monkeypatch)
    _code(root)
    distinct = set(w.git(root, "log", "--format=%T", "HEAD").split())
    assert len(calls) == len(set(calls))
    assert set(calls) == distinct
