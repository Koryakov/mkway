"""Card MW-130 (decisions: R311, R313, R313a), layer shell, on real git repositories: how `verdict add` finds a card's red-proof
row in the history of HEAD however many unrelated commits followed it. The red commit is made through the real commit gate
where the order says so (`_mw130.gated`); the long histories are built with one `git fast-import`. Synthetic names only."""
import itertools
import sys
import time
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/: the shared helpers and `_engine`
import _mw080 as w  # noqa: E402
import _mw130 as m  # noqa: E402
from _commit_project import reason, run_gate, stage  # noqa: E402
import gate_commit_tests as gct  # noqa: E402
import runner  # noqa: E402
import verdict_add  # noqa: E402

CAP = 3  # the patched cap of the legacy search, in ticks of the fake clock
WAY_OUT = "commit the card's red tests (the commit gate records the row), then call again"
TEXT_I = ("verdict-no-red-proof: the card has no red-proof row, so its tests were never proved red; commit the card's red "
          "tests (the commit gate records the row), then call again")
TEXT_II = ("verdict-no-red-proof: the card's red-proof rows name trees that no commit of HEAD has, so the red commit was "
           f"never made on this branch; {WAY_OUT}")
TEXT_IV = ("verdict-no-red-proof: the git history of HEAD could not be read, so the card's red-proof rows could not be "
           "checked; repeat the call")


def text_iii(checked: int) -> str:
    return (f"verdict-no-red-proof: the search for the commit of the card's older red-proof row (no git tree) ran out of "
            f"time (limit {CAP:g} s) after {checked} commits checked; {WAY_OUT}")


def _fake_clock(monkeypatch):
    """A clock of the legacy search that ticks once per reading, and the cap patched to `CAP` ticks."""
    ticks = itertools.count()
    monkeypatch.setattr(verdict_add, "_clock", lambda: next(ticks))
    monkeypatch.setattr(verdict_add, "LEGACY_SEARCH_SECONDS", CAP)


def _fail_history(monkeypatch):
    """Every git read of the history of HEAD (`log`, `rev-list`) raises a timeout, as a git that does not answer."""
    real = runner.git

    def git(root, *args, **kw):
        if args and args[0] in ("log", "rev-list"):
            raise runner.TimeoutExpired("git", 1)
        return real(root, *args, **kw)
    monkeypatch.setattr(runner, "git", git)


def _four(root) -> list:
    """Three commits that each change one file, on top of the root's own: four distinct trees in the history."""
    return m.chain(root, 3)


# ---- the live case: the real gate makes the red commit, unrelated commits follow, the real command is called ----------------

def test_a_new_row_is_found_after_61_unrelated_commits_by_the_real_command(tmp_path):
    """Catches: the 60-commit bound, `verdict add` refused verdict-no-red-proof for a red commit that is 61 commits back."""
    root = m.gated(tmp_path)
    m.chain(root, 61)
    code, _out, err = m.add(root)
    assert (code, "verdict-no-red-proof" in err) == (0, False), err


def test_a_legacy_row_is_found_after_61_unrelated_commits_by_the_real_command(tmp_path):
    """Catches: a row with no git_tree (written before this card) lost after 61 commits; the row time is the 5 s before the
    red commit that the gate writes it at."""
    root = m.gated(tmp_path)
    red_time = m.committer_time(root, "HEAD")
    m.chain(root, 61)

    def legacy(row):
        row.pop("git_tree", None)
        row["time"] = m.iso_at(red_time - 5)
    m.rewrite(root, legacy)
    assert all("git_tree" not in r for r in m.rows(root))
    code, _out, err = m.add(root)
    assert (code, "verdict-no-red-proof" in err) == (0, False), err


def test_the_same_call_after_59_unrelated_commits_is_allowed(tmp_path):
    """GUARD (green today): with 59 commits behind the red commit the call is allowed; so the 60-commit bound is the only
    cause of the refusal of the 61 case."""
    root = m.gated(tmp_path)
    m.chain(root, 59)
    code, _out, err = m.add(root)
    assert (code, "verdict-no-red-proof" in err) == (0, False), err


def test_a_red_commit_on_a_side_branch_merged_with_no_ff_is_found(tmp_path):
    """GUARD (green today, against a --first-parent walk): the red commit is on a side branch, the merge commit's tree is not
    the red tree, and the row is still found."""
    root = m.gated(tmp_path, side=True)
    assert m.rows(root)[0]["tree"] != m.digest_of(root, "HEAD")  # the merge tree is not the red tree
    code, _out, err = m.add(root)
    assert (code, "verdict-no-red-proof" in err) == (0, False), err


# ---- the new field ---------------------------------------------------------------------------------------------------------

def test_the_row_git_tree_equals_the_tree_of_the_commit_just_made(tmp_path):
    """Catches: a red-proof row with no git_tree, or one that is not the tree id git committed."""
    root = m.gated(tmp_path)
    assert m.rows(root)[-1]["git_tree"] == w.git(root, "rev-parse", "HEAD^{tree}")


def test_a_gate_that_cannot_tell_the_tree_writes_a_row_with_no_git_tree(tmp_path, monkeypatch):
    """GUARD (green today): when `tree_id` is None the row is written without git_tree, a legacy row, and the digest stays."""
    monkeypatch.setattr(gct, "tree_id", lambda ctx, commit: None)
    root = m.gated(tmp_path)
    row = m.rows(root)[-1]
    assert ("git_tree" in row, len(row["tree"])) == (False, 64)


# ---- 5 000 commits ---------------------------------------------------------------------------------------------------------

def test_a_new_row_4900_commits_back_is_found_in_less_than_the_git_seconds(tmp_path, monkeypatch):
    """Catches: a new row lost, or a search that takes longer than one git call may, on a history of 5 000 commits."""
    root = m.light(tmp_path)
    shas = m.chain(root, 5000)
    target = shas[99]  # 4 900 commits back from HEAD
    assert int(w.git(root, "rev-list", "--count", f"{target}..HEAD")) == 4900
    m.seed(root, tree="0" * 64, git_tree=w.git(root, "rev-parse", f"{target}^{{tree}}"))
    calls = m.count_digests(monkeypatch)
    started = time.perf_counter()
    found = w.read(root, "reader", [w.N1]).red_proven
    seconds = time.perf_counter() - started
    print(f"MW130 SECONDS new row 4900 back of 5000: {seconds:.2f}")
    assert (found, calls) == (True, [])
    assert seconds < gct.GIT_SECONDS


def test_a_legacy_row_4900_commits_back_is_found_with_one_digest_call(tmp_path, monkeypatch):
    """Catches: the nearest-first order lost: a legacy row 5 s before its commit must cost exactly one digest, not a walk
    from HEAD (every commit has its own tree, so a newest-first walk needs 4 900)."""
    root = m.light(tmp_path)
    shas = m.chain(root, 5000)
    target = shas[99]
    m.seed(root, tree=m.digest_of(root, target), time=m.iso_at(m.committer_time(root, target) - 5))
    calls = m.count_digests(monkeypatch)
    started = time.perf_counter()
    found = w.read(root, "reader", [w.N1]).red_proven
    print(f"MW130 SECONDS legacy row 4900 back of 5000: {time.perf_counter() - started:.2f}")
    assert (found, len(calls)) == (True, 1)


# ---- the cap and the four texts --------------------------------------------------------------------------------------------

def test_a_legacy_row_never_committed_meets_the_cap_and_gets_text_iii(tmp_path, monkeypatch):
    """Catches: a search with no cap, or at the cap the answer «no row»: the text names the commits checked (2 of the 4
    distinct trees, the fake clock ticks once per reading and the cap is 3 ticks)."""
    root = m.light(tmp_path)
    _four(root)
    m.seed(root, tree="a" * 64)
    _fake_clock(monkeypatch)
    code, _out, err = m.add_n1(root)
    assert code == 1
    assert text_iii(2) in err


def test_a_card_with_no_red_proof_row_is_refused_with_text_i(tmp_path):
    """GUARD (green today): the text of case (i) is today's, word for word (core_verdict_add.py:214-216)."""
    root = m.light(tmp_path)
    code, _out, err = m.add_n1(root)
    assert code == 1
    assert TEXT_I in err


def test_rows_that_no_commit_of_head_has_are_refused_with_text_ii(tmp_path):
    """Catches: rows that exist but whose trees are in no commit told as «no row»: text (ii) says the commit was never made."""
    root = m.light(tmp_path)
    m.seed(root, tree="0" * 64, git_tree=m.FAR)
    code, _out, err = m.add_n1(root)
    assert code == 1
    assert TEXT_II in err


def test_a_git_history_that_cannot_be_read_is_refused_with_text_iv(tmp_path, monkeypatch):
    """Catches: a git that does not answer told as «no row» or as «out of time»: text (iv), way out «repeat the call»."""
    root = m.light(tmp_path)
    m.seed(root, tree="0" * 64, git_tree=m.FAR)
    _fail_history(monkeypatch)
    code, _out, err = m.add_n1(root)
    assert code == 1
    assert TEXT_IV in err


def test_a_git_error_is_not_found(tmp_path, monkeypatch):
    """GUARD (green today): a row of a real commit of HEAD is not proven while every git read of the history raises a timeout
    (monkeypatched runner.git)."""
    root = m.light(tmp_path)
    m.seed(root, tree=m.digest_of(root, "HEAD"), git_tree=w.git(root, "rev-parse", "HEAD^{tree}"))
    _fail_history(monkeypatch)
    assert w.read(root, "reader", [w.N1]).red_proven is False


def test_a_row_whose_tree_is_in_no_commit_of_head_is_refused(tmp_path):
    """GUARD (green today, overlaps tests/shell/test_mw117_verdict_window_shell.py::
    test_a_red_record_whose_tree_is_no_commit_of_head_reads_not_red_proven): a row of a commit that was never made, with a
    git_tree and a digest that no commit has, in a history of 5 commits, counts for nothing."""
    root = m.light(tmp_path)
    m.chain(root, 4)
    m.seed(root, tree="0" * 64, git_tree=m.FAR)
    assert w.read(root, "reader", [w.N1]).red_proven is False


# ---- the other rows of the design ------------------------------------------------------------------------------------------

def test_a_legacy_row_whose_tree_is_a_git_tree_id_matches_the_listing_with_no_digest(tmp_path, monkeypatch):
    """Checks: a legacy row whose `tree` has the 40 hex of a git tree id is matched by the listing itself (Q2)."""
    root = m.light(tmp_path)
    shas = _four(root)
    m.seed(root, tree=w.git(root, "rev-parse", f"{shas[0]}^{{tree}}"))
    calls = m.count_digests(monkeypatch)
    assert (w.read(root, "reader", [w.N1]).red_proven, calls) == (True, [])


def test_a_proven_new_row_ends_the_search_before_any_legacy_digest(tmp_path, monkeypatch):
    """Checks: R9, new rows first: a legacy row that was never committed, written first, costs no digest when a new row of the
    card is proven."""
    root = m.light(tmp_path)
    _four(root)
    m.seed(root, tree="a" * 64)
    m.seed(root, tree="0" * 64, git_tree=w.git(root, "rev-parse", "HEAD^{tree}"))
    calls = m.count_digests(monkeypatch)
    assert (w.read(root, "reader", [w.N1]).red_proven, calls) == (True, [])


def test_the_digest_of_a_tree_is_computed_once_for_all_the_rows(tmp_path, monkeypatch):
    """Catches: R9, one digest cache for the whole call: two legacy rows that were never committed walk the 4 distinct
    trees once, not twice, and a tree held by several commits (six commits here) once, not once per commit."""
    root = m.light(tmp_path)
    _four(root)
    for n in (1, 2):  # two more commits with the SAME tree as HEAD: six commits, four distinct trees
        w.git(root, "commit", "-q", "--allow-empty", "-m", f"same tree {n}")
    m.seed(root, tree="a" * 64)
    m.seed(root, tree="b" * 64)
    calls = m.count_digests(monkeypatch)
    assert w.read(root, "reader", [w.N1]).red_proven is False
    assert len(calls) == 4 == len(set(calls))


def test_a_new_row_whose_git_tree_is_not_listed_is_not_found_and_no_digest_is_computed(tmp_path, monkeypatch):
    """Catches: R317 4, a digest fallback for a new row: a row with a git_tree that no commit has is NOT found even when its
    digest is the digest of HEAD's tree, because the gate and `verdict add` call the same search; text (ii), no digest."""
    root = m.light(tmp_path)
    m.seed(root, tree=m.digest_of(root, "HEAD"), git_tree=m.FAR)
    calls = m.count_digests(monkeypatch)
    code, _out, err = m.add_n1(root)
    assert (code, calls) == (1, [])
    assert TEXT_II in err


# ---- the rows of the blind reader (round 2) ---------------------------------------------------------------------------------

def test_a_legacy_row_with_no_readable_time_is_searched_newest_first(tmp_path, monkeypatch):
    """Catches: D3c, a legacy row whose time cannot be read searched oldest first or in no order: the first tree digested is
    the tree of the newest commit."""
    root = m.light(tmp_path)
    _four(root)
    m.seed(root, tree="a" * 64, time="not a time")
    calls = m.count_digests(monkeypatch)
    assert w.read(root, "reader", [w.N1]).red_proven is False
    assert calls[0] == w.git(root, "rev-parse", "HEAD^{tree}")


def test_a_new_row_is_found_when_the_legacy_cap_is_spent(tmp_path, monkeypatch):
    """GUARD (green today): D4b, the cap is for the legacy path only: with the cap at 0 (spent at once) a new row whose
    git_tree is listed is still found."""
    root = m.light(tmp_path)
    m.seed(root, tree="0" * 64, git_tree=w.git(root, "rev-parse", "HEAD^{tree}"))
    monkeypatch.setattr(verdict_add, "LEGACY_SEARCH_SECONDS", 0)
    assert w.read(root, "reader", [w.N1]).red_proven is True


def test_two_never_committed_legacy_rows_stop_at_one_cap_in_total(tmp_path, monkeypatch):
    """GUARD (green today): R9b, the cap is one wall time for the whole call: two legacy rows that were never committed stop at
    the same 2 commits checked as one row does (a cap per row would check 4)."""
    root = m.light(tmp_path)
    _four(root)
    m.seed(root, tree="a" * 64)
    m.seed(root, tree="b" * 64)
    _fake_clock(monkeypatch)
    calls = m.count_digests(monkeypatch)
    code, _out, err = m.add_n1(root)
    assert (code, len(calls)) == (1, 2)
    assert text_iii(2) in err


def test_a_history_listing_with_a_non_zero_exit_is_refused_with_text_iv(tmp_path, monkeypatch):
    """Catches: D6 and R6, a `git log` that exits non-zero read as an empty history («no commit has it») or as found: text (iv)."""
    root = m.light(tmp_path)
    m.seed(root, tree="0" * 64, git_tree=m.FAR)
    real = runner.git

    def git(root_, *args, **kw):
        if args and args[0] == "log":
            return types.SimpleNamespace(returncode=128, stdout="", stderr="fatal: bad object HEAD")
        return real(root_, *args, **kw)
    monkeypatch.setattr(runner, "git", git)
    code, _out, err = m.add_n1(root)
    assert code == 1
    assert TEXT_IV in err


def test_a_tree_the_digest_step_cannot_list_does_not_match_and_the_search_goes_on(tmp_path, monkeypatch):
    """Catches: D6 and R6, an `ls-tree` error for the nearest commit that ends the search: that commit does not match, the
    next one is digested and matches."""
    root = m.light(tmp_path)
    shas = _four(root)
    broken = w.git(root, "rev-parse", f"{shas[1]}^{{tree}}")
    # the row is 5 s before commit 1 (the nearest, 5 s), then commit 0 (55 s), then commit 2 (65 s)
    m.seed(root, tree=m.digest_of(root, shas[0]), time=m.iso_at(m.committer_time(root, shas[1]) - 5))
    real = gct._listing
    monkeypatch.setattr(gct, "_listing", lambda root_, rev: None if rev == broken else real(root_, rev))
    calls = m.count_digests(monkeypatch)
    assert w.read(root, "reader", [w.N1]).red_proven is True
    assert calls == [broken, w.git(root, "rev-parse", f"{shas[0]}^{{tree}}")]


def test_the_only_candidate_tree_failing_in_the_digest_step_is_refused_with_text_iv_never_ii(tmp_path, monkeypatch):
    """Catches: R6, a search whose only candidate tree could not be listed ends «no commit has it» (ii): the history could not be
    read, so the text is (iv). The root has one commit, so one distinct tree, and its listing fails."""
    root = m.light(tmp_path)
    m.seed(root, tree="a" * 64)
    monkeypatch.setattr(gct, "_listing", lambda root_, rev: None)
    calls = m.count_digests(monkeypatch)
    code, _out, err = m.add_n1(root)
    assert (code, len(calls)) == (1, 1)
    assert TEXT_IV in err


def test_one_verdict_add_makes_exactly_one_git_log_call(tmp_path, monkeypatch):
    """GUARD (green today): D2, the whole history is listed by ONE `log` call per `verdict add`, however many rows there are."""
    root = m.light(tmp_path)
    _four(root)
    m.seed(root, tree="a" * 64)
    m.seed(root, tree="b" * 64, git_tree=m.FAR)
    real, seen = runner.git, []

    def git(root_, *args, **kw):
        seen.append(args[:1])
        return real(root_, *args, **kw)
    monkeypatch.setattr(runner, "git", git)
    m.add_n1(root)
    assert seen.count(("log",)) == 1


# ---- the audit: a card's own later commit (DESIGN 7) -----------------------------------------------------------------------

def test_a_code_commit_after_59_unrelated_commits_is_allowed(tmp_path):
    """GUARD (green today): the gate still knows the card's red record 59 commits later, so its own code commit is allowed."""
    root = m.gated(tmp_path)
    m.chain(root, 59)
    stage(root, "app.py", m.APP_MUL)
    assert reason(run_gate(root)) == "allow"


def test_a_code_commit_after_61_unrelated_commits_is_allowed(tmp_path):
    """Checks: the audit of DESIGN 7: the card's own code commit after 61 unrelated commits of a busy checkout is allowed."""
    root = m.gated(tmp_path)
    m.chain(root, 61)
    stage(root, "app.py", m.APP_MUL)
    assert reason(run_gate(root)) == "allow"
