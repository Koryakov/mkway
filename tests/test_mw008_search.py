"""`mkway search` over the ledger and the knowledge files, and its record (card MW-008, part 2). Synthetic task roots
only; no task data. Modules are imported inside each test, so a missing module fails that test and not the collection."""
import datetime
import importlib
import json

import pytest

from _engine import cli, gate_call, jsonl, task_root

TODAY = datetime.date.today().isoformat()


def _ledger():
    return importlib.import_module("ledger")


def _profile(root):
    return json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))


def _add(root, topic, quote, status="in force", card="CARD-001"):
    _ledger().add(root, _profile(root), card=card, topic=topic, quote=quote, source="chat", status=status)


def _searches(root):
    return jsonl(root / "mkway" / "state" / "searches.jsonl")


def _search(root, *words, session=False, env=None):
    code, out, err = cli(root, "search", *words, session=session, env=env)
    assert code == 0, err
    return out


@pytest.fixture
def task(tmp_path):
    root = task_root(tmp_path)
    _add(root, "folder naming", "use short names for the folder")
    _add(root, "folder layout", "keep the old layout", status="superseded")
    _add(root, "cache cleanup", "clean the cache nightly")
    _add(root, "folder depth", "one level only", status="withdrawn")
    return root


def test_search_groups_hits_by_file_and_status(task):
    """E5 (part 2): a hit is printed as `id  date  topic  quote`; the hits of one file come under that file's path and
    are grouped by status: in force first, then withdrawn, then superseded; a row that does not hold the word is not
    printed; the run ends with the hit count. Catches: a superseded decision shown as if it were in force, or a
    hit with a missing field."""
    out = _search(task, "folder")
    lines = [l.strip() for l in out.splitlines()]
    assert "mkway/ledger/ledger.md" in lines
    want = [f"D-1  {TODAY}  folder naming  use short names for the folder", f"D-4  {TODAY}  folder depth  one level only",
            f"D-2  {TODAY}  folder layout  keep the old layout"]
    for line in want:
        assert line in lines, line
    assert [lines.index(l) for l in want] == sorted(lines.index(l) for l in want)
    assert lines.index("in force") < lines.index(want[0]) < lines.index("withdrawn") < lines.index(want[1]) \
        < lines.index("superseded") < lines.index(want[2])
    assert not any("D-3" in l for l in lines)
    assert lines[-1] == "hits: 3"


def test_search_reads_the_ledger_and_every_knowledge_file(tmp_path):
    """E6 (part 2): with `knowledge.files` naming two files (one more is missing and is skipped), the search reads the
    ledger and both: a file in ledger form gives its rows (their own ids), a plain file gives each matching line (id
    `<path>:<line>`, topic the heading above it). The files come in order: the ledger, then the list. Catches: a
    knowledge file that is never read, or a plain file that is ignored."""
    task = task_root(tmp_path, knowledge={"files": ["notes/facts.md", "notes/more.md", "notes/missing.md"]})
    _add(task, "cache cleanup", "clean the cache nightly")
    (task / "notes").mkdir()
    (task / "notes" / "facts.md").write_text("# Facts\n\nThe cache folder is cleaned nightly.\nunrelated line\n",
                                             encoding="utf-8")
    (task / "notes" / "more.md").write_text(
        "## Ledger\n\n| id | date | card | topic | quote | by | source | asked | replaces | status | note |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|\n"
        "| K-1 | 2026-01-02 | C | cache rule | never cache secrets | owner | s |  |  | in force |  |\n"
        "| K-2 | 2026-01-03 | C | other | nothing here | owner | s |  |  | in force |  |\n", encoding="utf-8")
    out = _search(task, "cache")
    lines = [l.strip() for l in out.splitlines()]
    assert lines[-1] == "hits: 3"
    assert f"D-1  {TODAY}  cache cleanup  clean the cache nightly" in lines
    assert "notes/facts.md:3    Facts  The cache folder is cleaned nightly." in lines
    assert "K-1  2026-01-02  cache rule  never cache secrets" in lines
    assert not any("unrelated" in l or "K-2" in l or "missing" in l for l in lines)
    paths = [l for l in lines if l in ("mkway/ledger/ledger.md", "notes/facts.md", "notes/more.md")]
    assert paths == ["mkway/ledger/ledger.md", "notes/facts.md", "notes/more.md"]
    assert _searches(task)[-1]["hit_ids"] == ["D-1", "notes/facts.md:3", "K-1"]


def test_search_reads_the_ledger_only_by_default(task):
    """E7 (part 2): with no `knowledge.files` in the profile only the ledger is read, though a notes file holds the
    word. Catches: a default that scans the whole repository."""
    (task / "notes").mkdir()
    (task / "notes" / "facts.md").write_text("the cache is cleaned nightly\n", encoding="utf-8")
    out = _search(task, "cache")
    assert "notes/facts.md" not in out and out.splitlines()[-1] == "hits: 1"


def test_search_is_a_plain_case_insensitive_word_match(task):
    """E8 (part 2): the match is plain text and ignores case; a row is a hit when it holds any of the words; the hits
    come in file order, not ranked; a word that is nowhere gives `hits: 0` and exit 0.
    Catches: a case-sensitive match, a match that needs every word, or a ranking."""
    upper = _search(task, "CACHE")
    assert "D-3" in upper and upper.splitlines()[-1] == "hits: 1"
    any_word = _search(task, "nightly", "LAYOUT")
    assert "D-2" in any_word and "D-3" in any_word and "D-1" not in any_word
    assert any_word.splitlines()[-1] == "hits: 2"
    none = _search(task, "zzzz")
    assert none.splitlines()[-1] == "hits: 0" and "D-" not in none


def test_every_search_appends_a_record(task):
    """E9 (part 2): each run appends one row to `<state>/searches.jsonl`: id `S-<n>`, the session (from
    `CLAUDE_CODE_SESSION_ID`, else null), the time, the words, the hit count and the hit ids; two runs give two rows.
    Catches: a run that leaves no proof, or a row with no hit ids."""
    _search(task, "folder", "cache", env={"CLAUDE_CODE_SESSION_ID": "abc"})
    _search(task, "zzzz")
    first, second = _searches(task)
    assert first["id"] == "S-1" and second["id"] == "S-2"
    assert first["session"] == "abc" and second["session"] is None
    assert first["words"] == ["folder", "cache"] and first["hits"] == 4
    assert first["hit_ids"] == ["D-1", "D-2", "D-3", "D-4"]
    assert second["hits"] == 0 and second["hit_ids"] == []
    assert datetime.datetime.fromisoformat(first["time"]) <= datetime.datetime.now(datetime.timezone.utc)


def test_search_without_a_profile_or_a_ledger_still_records(tmp_path):
    """E10 (part 2): a root with no profile, and a root with a profile but no ledger file, both end with exit 0, 0
    hits and a record (the state folder is the default one when there is no profile).
    Catches: a search that fails when there is nothing to find, so no record exists and the gate can never pass."""
    bare = tmp_path / "bare"
    bare.mkdir()
    assert _search(bare, "x").splitlines()[-1] == "hits: 0"
    assert [(r["id"], r["hits"]) for r in jsonl(bare / "mkway" / "state" / "searches.jsonl")] == [("S-1", 0)]
    no_ledger = task_root(tmp_path, name="noledger")
    assert _search(no_ledger, "x").splitlines()[-1] == "hits: 0"
    assert [(r["id"], r["hits"]) for r in _searches(no_ledger)] == [("S-1", 0)]


def test_a_session_search_is_recorded_for_its_session(task):
    """E11 (part 2): a session's run prints `mkway-ok search <id> <nonce>`; the `post` group's gate turns it into a
    `search` record with that session's id (the owner's terminal writes its own record, `by: owner`). Catches: a
    search the session ran that the gate cannot tell from none."""
    import records
    state = task / "mkway" / "state"
    out = _search(task, "folder", session=True)
    ok = [l for l in out.splitlines() if l.startswith("mkway-ok search S-1 ")]
    assert len(ok) == 1
    import gate_records
    verdict = gate_call(gate_records.record, task, tool="Bash", event="PostToolUse", session="s-77",
                        tool_input={"command": "mkway search folder"}, tool_response={"stdout": out})
    assert verdict.kind == "allow"
    rows = [r for r in records.rows(state) if r["kind"] == "search"]
    assert [(r["session_id"], r["value"], r["by"]) for r in rows] == [("s-77", "S-1", "session")]
    _search(task, "folder", session=False)
    owner = [r for r in records.rows(state) if r["kind"] == "search"][-1]
    assert (owner["session_id"], owner["value"], owner["by"]) == (None, "S-2", "owner")
