"""Card MW-020, row E11: `mkway deliverables` and the start-block line. Synthetic git task roots only."""
import json
import re

import startline
from _engine import cli
from _mw020 import deliverable, make_root, ready, sha_of, state


def _cols(out):
    rows = {}
    for line in out.splitlines():
        if line.strip():
            cols = re.split(r"\s{2,}", line.strip())
            rows[cols[0]] = cols
    return rows


def _mixed(root):
    never = deliverable(root, "never.md")
    ok = deliverable(root, "ok.md")
    ready(root, ok)
    moved = deliverable(root, "moved.md")
    ready(root, moved)
    deliverable(root, "moved.md", "Edited after it was built.\n")
    gone = deliverable(root, "gone.md")
    ready(root, gone)
    assert cli(root, "delivered", gone)[0] == 0
    deliverable(root, "gone.md.check.md", "base: 00000000\n")  # a check file is not a deliverable
    return never, ok, moved, gone


def test_the_deliverables_command_prints_a_row_per_file(tmp_path):
    """E11: `mkway deliverables` prints one row per existing file that matches `deliverables.paths` (check files are
    not rows), sorted by path: path, the first eight digits of its sha256, the state (`built`: a provenance row has
    this hash; `changed`: it was built, but the file is different now; `unbuilt`), and the sha8 of its newest delivered
    row or `-`; a session may run it. Catches: a board that hides a result changed after it was built."""
    root = make_root(tmp_path)
    never, ok, moved, gone = _mixed(root)
    code, out, err = cli(root, "deliverables")
    assert code == 0, err
    rows = _cols(out)
    assert list(rows) == sorted([never, ok, moved, gone])
    assert rows[never] == [never, sha_of(root / never)[:8], "unbuilt", "-"]
    assert rows[ok] == [ok, sha_of(root / ok)[:8], "built", "-"]
    assert rows[moved][2] == "changed" and rows[moved][3] == "-"
    assert rows[gone] == [gone, sha_of(root / gone)[:8], "built", sha_of(root / gone)[:8]]
    assert cli(root, "deliverables", session=True)[1] == out


def test_the_deliverables_command_without_keys_or_files(tmp_path):
    """E11: with no `deliverables.paths` the command exits 0 and names the key; with the key and no file it says so.
    Catches: a command that fails where the feature is simply not set up."""
    bare = make_root(tmp_path / "bare", deliverables=None)
    code, out, err = cli(bare, "deliverables")
    assert code == 0 and "deliverables.paths" in out
    empty = make_root(tmp_path / "empty")
    code, out, err = cli(empty, "deliverables")
    assert code == 0 and "no files" in out


def test_the_start_block_counts_built_changed_and_delivered(tmp_path):
    """E11: `deliverables: N built, M changed since built, K delivered` when `deliverables.paths` is set (N: files whose
    current hash has a provenance row, M: files built once and different now, K: files with a delivered row), `0, 0, 0`
    with no file, and no line when the key is not set. Catches: a start block that hides a result changed after it was
    built."""
    root = make_root(tmp_path)
    profile = json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))
    pfile = root / "mkway" / "profile.json"

    def lines(p):
        return [x for x in startline.render(root, pfile, p, [], [], {}).splitlines() if x.startswith("deliverables:")]
    assert lines(profile) == ["deliverables: 0 built, 0 changed since built, 0 delivered"]
    _mixed(root)
    assert lines(profile) == ["deliverables: 2 built, 1 changed since built, 1 delivered"]
    assert lines(dict(profile, deliverables={})) == []
