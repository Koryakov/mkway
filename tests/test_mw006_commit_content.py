"""Commit checks (card MW-006), part 4: the commit gate's rules «no junk» and «no data files»: junk patterns, a
force-added ignored file, data patterns, the size limit, the profile's overrides, and deletions. Synthetic task roots
only, real throwaway git repositories. The card has an empty Paths and the session wrote each file, so only these
rules can refuse."""
from _commit_fixture import COMMIT, check, git, make_task, reason, save, stage, touch, work


def _task(tmp_path, **over):
    return make_task(tmp_path, card_paths="", **over)


def _staged(root, rel, text="x\n"):
    work(root, rel, text)
    touch(root, rel)
    stage(root, rel)


def _alone(root, rel, text="x\n"):
    """The verdict for a commit that holds this one file."""
    _staged(root, rel, text)
    verdict = check(root, COMMIT)
    git(root, "restore", "--staged", "--", rel)
    return verdict


def test_junk_files_are_refused_at_any_depth(tmp_path):
    """E14 (part 4): a staged file matching `commit.junk` is refused `junk-file-staged`, naming the file and the
    key: a name or glob at any depth, a folder pattern (a trailing `/`) at any depth; an ordinary file passes.
    Junk is judged before data, so `Thumbs.db` is junk. Catches: a pattern that matches only at the root, a folder
    pattern that misses a nested folder, or a junk file that rides in because it is also a data extension."""
    root = _task(tmp_path)
    junk = ["src/__pycache__/mod.cpython-312.pyc", "mod.pyc", "tests/.pytest_cache/CACHEDIR.TAG",
            "deep/er/.pytest_tmp/x.txt", "build/run.log", "a.tmp", "src/a.orig", "src/a.rej", "x/.DS_Store",
            "img/Thumbs.db"]
    for rel in junk:
        v = _alone(root, rel)
        assert v.kind == "refuse" and v.reason_id == "junk-file-staged", rel
        assert rel in v.message and "commit.junk" in v.message and "git restore --staged" in v.message, rel
    for rel in ("src/pycache_notes.md", "logs.md", "src/pytest_cache.py", "docs/Thumbs.md"):
        assert reason(_alone(root, rel)) == "allow", rel
    _staged(root, "a.tmp")
    _staged(root, "keep/b.rej")
    _staged(root, "src/ok.py")
    v = check(root, COMMIT)
    assert v.reason_id == "junk-file-staged" and v.message.split(" are ")[0] == "a.tmp, keep/b.rej"


def test_a_force_added_ignored_file_is_refused(tmp_path):
    """E15 (part 4): a new staged file that git ignores (it was added with `git add -f`) is refused
    `ignored-file-staged`, naming it, with the way out; a file that was already committed stays editable, and a
    file the ignore rules do not match passes. Catches: the hand-off defect, «never commit real data» guarded by
    the ignore file alone, which `git add -f` passes."""
    root = _task(tmp_path)
    save(root, ".gitignore", "secret_notes/\n*.keep\n")
    save(root, "secret_notes/old.txt", "old\n")  # committed earlier, by hand
    v = _alone(root, "secret_notes/new.txt")
    assert v.kind == "refuse" and v.reason_id == "ignored-file-staged"
    assert "secret_notes/new.txt" in v.message and "git restore --staged" in v.message
    assert "add -f" in v.message
    assert _alone(root, "notes/today.keep").reason_id == "ignored-file-staged"
    assert reason(_alone(root, "notes/today.md")) == "allow"
    work(root, "secret_notes/old.txt", "changed\n")
    touch(root, "secret_notes/old.txt")
    stage(root, "secret_notes/old.txt")
    assert reason(check(root, COMMIT)) == "allow"  # already in the repository: not a new force-add


def test_data_files_are_refused_by_extension(tmp_path):
    """E16 (part 4): a staged file matching `commit.data_patterns` is refused `data-file-staged`, naming it and the
    key, by extension only: a name that merely contains the extension, or a source file that handles such data, passes.
    Catches: real data committed because it is not in the ignore file."""
    root = _task(tmp_path)
    data = ["data/a.csv", "x.tsv", "out/book.xlsx", "old.xls", "t/p.parquet", "app.db", "s/lite.sqlite",
            "s/lite3.sqlite3", "notes.bak", "d/state.dump"]
    for rel in data:
        v = _alone(root, rel)
        assert v.kind == "refuse" and v.reason_id == "data-file-staged", rel
        assert rel in v.message and "commit.data_patterns" in v.message and "git restore --staged" in v.message, rel
    for rel in ("docs/data.csv.md", "src/csv_tools.py", "csv/readme.txt", "src/db.py"):
        assert reason(_alone(root, rel)) == "allow", rel


def test_a_file_over_the_size_limit_is_refused(tmp_path):
    """E17 (part 4): a staged file over `commit.max_file_kb` (1024 by default) is refused `file-too-large`, naming
    it, its size and the limit; the size is that of the staged blob for a commit of the index and that of the working
    file for `-- <paths>`. Catches: a big file that passes because it is not a known data extension, or a size read
    from the wrong copy."""
    root = _task(tmp_path)
    assert reason(_alone(root, "src/just_under.txt", "a" * (1000 * 1024))) == "allow"
    v = _alone(root, "src/big.txt", "a" * (1100 * 1024))
    assert v.kind == "refuse" and v.reason_id == "file-too-large"
    assert "src/big.txt" in v.message and "1100 KB" in v.message and "1024" in v.message
    assert "commit.max_file_kb" in v.message and "git restore --staged" in v.message
    _staged(root, "src/shrunk.txt", "a" * (1100 * 1024))
    work(root, "src/shrunk.txt", "small\n")  # the working file is small, the staged blob is big
    assert check(root, COMMIT).reason_id == "file-too-large"
    assert reason(check(root, "git commit -m 'CARD-001 x' -- src/shrunk.txt")) == "allow"


def test_the_profile_overrides_junk_data_and_size(tmp_path):
    """E18 (part 4): the profile's `commit.junk`, `commit.data_patterns` and `commit.max_file_kb` replace the defaults,
    each alone: a pattern the profile drops is no longer refused, a pattern it adds is; the limit moves.
    Catches: defaults that stay in force behind an override."""
    root = _task(tmp_path, commit={"junk": ["*.swp"], "data_patterns": ["*.json.gz"], "max_file_kb": 1})
    assert reason(_alone(root, "a.pyc")) == "allow"
    assert reason(_alone(root, "d.csv")) == "allow"
    assert _alone(root, "x.swp").reason_id == "junk-file-staged"
    assert _alone(root, "d.json.gz").reason_id == "data-file-staged"
    assert reason(_alone(root, "src/small.txt", "a" * 900)) == "allow"
    assert _alone(root, "src/two.txt", "a" * 2048).reason_id == "file-too-large"
    only = _task(tmp_path, name="only", commit={"max_file_kb": 0.5})
    assert _alone(only, "a.pyc").reason_id == "junk-file-staged"  # the junk default stays: the key was not set
    assert _alone(only, "d.csv").reason_id == "data-file-staged"
    assert _alone(only, "src/one.txt", "a" * 600).reason_id == "file-too-large"


def test_deleting_a_junk_or_data_file_is_allowed(tmp_path):
    """E19 (part 4): removing a junk, data or oversized file that was committed earlier is not refused (it is the way
    out), while a change to such a file that stays is. Catches: a gate that blocks the clean-up of the mess it guards
    against."""
    root = _task(tmp_path)
    save(root, "old/cache.pyc")
    save(root, "old/dump.csv")
    save(root, "old/big.bin", "a" * (1100 * 1024))
    save(root, "old/keep.csv")
    git(root, "rm", "-q", "--", "old/cache.pyc", "old/dump.csv", "old/big.bin")
    touch(root, "old/cache.pyc", "old/dump.csv", "old/big.bin")
    assert reason(check(root, COMMIT)) == "allow"
    work(root, "old/keep.csv", "changed\n")
    touch(root, "old/keep.csv")
    stage(root, "old/keep.csv")
    assert check(root, COMMIT).reason_id == "data-file-staged"
