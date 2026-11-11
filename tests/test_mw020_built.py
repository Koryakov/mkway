"""Card MW-020, rows E3 to E5: `mkway built <path>` refuses `built-dirty` and `built-untested`, and otherwise records
where a result file came from. Synthetic git task roots only."""
import json
import re

import cardtool
import ledger
from _commit_fixture import git, save, work
from _engine import cli
from _mw020 import (OUT, built, deliverable, green, head, head_tree, index_digest, make_root, ready, rows, sha_of,
                    state)


def _reason(err):
    m = re.search(r"mkway: ([a-z-]+):", err)
    return m.group(1) if m else None


def test_built_is_refused_while_a_tracked_file_has_uncommitted_changes(tmp_path):
    """E3: an uncommitted change in a tracked file (modified, or staged) refuses `built-dirty` and names the file and
    the commit that fixes it; an untracked file (the result itself) does not count; nothing is recorded.
    Catches: a result built from code that is not the code in git."""
    root = make_root(tmp_path)
    rel = deliverable(root)
    green(root)
    work(root, "src/a.py", "x = 2\n")
    code, out, err = built(root, rel)
    assert code != 0 and _reason(err) == "built-dirty", err
    assert "src/a.py" in err and "commit" in err and "mkway built" in err, err
    assert rows(root, "deliverables.jsonl") == []
    git(root, "add", "src/a.py")
    assert _reason(built(root, rel)[2]) == "built-dirty"
    git(root, "commit", "-q", "-m", "x2")
    green(root)
    assert built(root, rel)[0] == 0  # the commit cleaned it; the untracked result never counted


def test_built_is_refused_without_a_green_row_for_the_tree_of_head(tmp_path):
    """E4: with no row of `commit_tests.jsonl` that is green for HEAD's tree (none at all, a red row, a green row of
    another tree) the command refuses `built-untested`; the text names the way: a commit that carries a change outside
    the test roots runs the suite and writes the row, then `mkway built` again. Catches: a result built from code no
    test has passed."""
    root = make_root(tmp_path)
    rel = deliverable(root)
    code, out, err = built(root, rel)
    assert code != 0 and _reason(err) == "built-untested", err
    assert "mkway built" in err and "commit" in err, err
    green(root, result="fail")
    assert _reason(built(root, rel)[2]) == "built-untested"
    green(root, tree="0" * 40)
    assert _reason(built(root, rel)[2]) == "built-untested"
    save(root, "src/b.py")  # a new commit: the old green row is for an older tree
    assert _reason(built(root, rel)[2]) == "built-untested"
    assert rows(root, "deliverables.jsonl") == []


def test_built_records_the_provenance_and_a_ledger_row(tmp_path):
    """E5: with a clean tree and a green row for HEAD (either form of the tree: the git tree id, or the sha256 of the
    staged listing the commit gate writes) a session's `mkway built` appends {path, sha256, head, tree, time,
    session} to `deliverables.jsonl` (the session is the lock gate's permit, never a word), writes the ledger row
    `built <path> <sha8> at <head8>`, and prints the same. The owner's terminal records `owner`. Catches: a record
    with no hash, no head, or a name in place of the session id."""
    root = make_root(tmp_path)
    rel = deliverable(root)
    green(root, tree=index_digest(root))
    code, out, err = built(root, rel, session="s7")
    assert code == 0, err
    want = f"built {rel} {sha_of(root / rel)[:8]} at {head(root)[:8]}"
    assert want in out
    row = rows(root, "deliverables.jsonl")[0]
    assert {k: row[k] for k in ("path", "sha256", "head", "tree", "session")} == {
        "path": rel, "sha256": sha_of(root / rel), "head": head(root), "tree": index_digest(root), "session": "s7"}
    assert row["time"]
    profile = json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))
    assert want in ledger.path(root, profile).read_text(encoding="utf-8")
    green(root)
    code, out, err = cli(root, "built", rel)  # the owner's terminal
    assert code == 0, err
    assert rows(root, "deliverables.jsonl")[-1]["session"] == "owner"
    assert rows(root, "deliverables.jsonl")[-1]["tree"] in (head_tree(root), index_digest(root))


def test_a_file_that_is_not_there_is_refused_and_no_permit_is_left(tmp_path):
    """E5: a path with no file refuses `built-no-file` naming the path; the one-use permit that names the session is
    taken whatever the outcome. Catches: a provenance row for nothing, or a permit that outlives its call."""
    root = make_root(tmp_path)
    green(root)
    code, out, err = built(root, f"{OUT}/none.md")
    assert code != 0 and _reason(err) == "built-no-file" and f"{OUT}/none.md" in err, err
    assert cardtool.take_by_permit(state(root)) is None
    assert rows(root, "deliverables.jsonl") == []


def test_a_session_may_run_it_and_the_gate_issues_the_permit(tmp_path):
    """E5: `built` is no owner-only command: the lock gate lets a session's `python mkway/engine/mkway.py built <path>`
    through and leaves the one-use permit that names the session. Catches: an owner-only door on a command any session
    needs, or a record made with `session:unknown`."""
    import gate_lock
    from _engine import gate_call
    root = make_root(tmp_path)
    rel = deliverable(root)
    verdict = gate_call(gate_lock.check, root, tool="Bash", session="s9",
                        tool_input={"command": f"python mkway/engine/mkway.py built {rel}"})
    assert verdict.kind != "refuse", getattr(verdict, "reason_id", None)
    assert cardtool.take_by_permit(state(root)) == "s9"
