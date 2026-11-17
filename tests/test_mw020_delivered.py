"""Card MW-020, rows E8 to E10: the owner's `mkway delivered <path>` (the base of every later comparison) and the
check file's optional line `base: <sha8>`, read by the parser of MW-019. Synthetic roots only."""
import re
import shutil

import cardtool
import gate_lock
from _engine import cli, gate_call, task_root
import _mw019 as m19
from _mw020 import OUT, deliverable, make_root, rows, sha_of, state


def _reason(err):
    m = re.search(r"mkway: ([a-z-]+):", err)
    return m.group(1) if m else None


def test_delivered_records_the_hash_and_keeps_a_copy(tmp_path):
    """Checks: a delivered row keeps the path, the hash and the time of the base, so a later edit cannot overwrite it. E8"""
    # the owner's mkway delivered <path> appends {path, sha256, time} to delivered.jsonl and keeps a copy of the file at
    # <state>/delivered/<name>.<sha8>; a changed file keeps a second copy next to the first (the first is never
    # overwritten); a path with no file is refused delivered-no-file.
    root = make_root(tmp_path)
    rel = deliverable(root, "a.md", "First text.\n")
    first = sha_of(root / rel)
    code, out, err = cli(root, "delivered", rel)
    assert code == 0, err
    row = rows(root, "delivered.jsonl")[0]
    assert (row["path"], row["sha256"]) == (rel, first)
    assert row["time"]
    copy = state(root) / "delivered" / f"a.md.{first[:8]}"
    assert copy.read_bytes() == (root / rel).read_bytes()
    assert first[:8] in out
    assert rel in out
    deliverable(root, "a.md", "Second text.\n")
    second = sha_of(root / rel)
    assert cli(root, "delivered", rel)[0] == 0
    assert copy.read_bytes() == b"First text.\n"
    assert (state(root) / "delivered" / f"a.md.{second[:8]}").read_bytes() == b"Second text.\n"
    assert [r["sha256"] for r in rows(root, "delivered.jsonl")] == [first, second]
    code, out, err = cli(root, "delivered", f"{OUT}/none.md")
    assert code != 0, err
    assert _reason(err) == "delivered-no-file", err
    assert f"{OUT}/none.md" in err, err


def test_a_session_never_delivers(tmp_path):
    """Catches: a session that marks its own result as delivered and so chooses its own base. E8"""
    # delivered is the owner's command: a session's CLI run and the lock gate's look at its shell command both refuse
    # owner-only-command, and nothing is recorded or copied.
    root = make_root(tmp_path)
    rel = deliverable(root)
    code, out, err = cli(root, "delivered", rel, session=True)
    assert code != 0, err
    assert _reason(err) == "owner-only-command", err
    verdict = gate_call(gate_lock.check, root, tool="Bash", session="s1",
                        tool_input={"command": f"python mkway/engine/mkway.py delivered {rel}"})
    assert verdict.kind == "refuse"
    assert verdict.reason_id == "owner-only-command"
    assert rows(root, "delivered.jsonl") == []
    assert not (state(root) / "delivered").exists()


# ---- the `base:` line of the check file ----------------------------------------------------------------------------

def _outbox_root(tmp_path):
    return task_root(tmp_path, outbox={"dir": "outbox", "checkers": ["critic"]},
                     deliverables={"paths": ["outbox/*.md"], "require_base": ["outbox/base-*.md"]})


def _deliver(root, text="The delivered text.\n"):
    """A delivered file: the base some later text is compared with; returns its sha8."""
    (root / "outbox").mkdir(exist_ok=True)
    path = root / "outbox" / "previous.md"
    path.write_text(text, encoding="utf-8", newline="")
    code, out, err = cli(root, "delivered", "outbox/previous.md")
    assert code == 0, err
    return sha_of(path)[:8]


def test_the_optional_base_line_is_read_by_the_outbox_parser(tmp_path):
    """Catches: a second parser for the check file, or a base that nobody delivered accepted. E9"""
    # a check with an extra line base: <sha8> stays valid for an ordinary outbox file when the sha8 is the prefix of a
    # delivered.jsonl row, and a check with no such line stays valid too; a base: line in a wrong form, or a sha8 no
    # delivered row holds, is unproven and the problem names base-unknown, the line and mkway delivered.
    root = _outbox_root(tmp_path)
    sha8 = _deliver(root)
    plain = m19.valid_file(root, "a.md")
    assert m19.inspect(root, plain).state == "valid"
    with_base = m19.valid_file(root, "b.md", extra=f"base: {sha8}\n")
    assert m19.inspect(root, with_base).state == "valid"
    unknown = m19.valid_file(root, "c.md", extra="base: deadbeef\n")
    status = m19.inspect(root, unknown)
    assert status.state == "unproven"
    text = m19.joined(status)
    assert "base-unknown" in text, text
    assert "deadbeef" in text, text
    assert "mkway delivered" in text, text
    wrong = m19.valid_file(root, "d.md", extra="base: not-a-sha\n")
    status = m19.inspect(root, wrong)
    assert status.state == "unproven"
    assert "base: <sha8>" in m19.joined(status)


def test_a_path_that_requires_a_base_is_unproven_without_one(tmp_path):
    """Catches: a comparison with no named base, the second thing the owner said never to do. E10"""
    # a file of deliverables.require_base under the outbox is unproven while its check lacks the base: line (the problem
    # names base-unknown and the line to write) and valid when the line names a delivered base.
    root = _outbox_root(tmp_path)
    sha8 = _deliver(root)
    bare = m19.valid_file(root, "base-a.md")
    status = m19.inspect(root, bare)
    assert status.state == "unproven"
    assert "base-unknown" in m19.joined(status)
    assert "base: <sha8>" in m19.joined(status)
    good = m19.valid_file(root, "base-b.md", extra=f"base: {sha8}\n")
    assert m19.inspect(root, good).state == "valid"
