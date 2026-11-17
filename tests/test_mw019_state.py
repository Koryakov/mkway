"""Card MW-019, part 1 (state of a check): valid, stale, unproven, missing, and the bypass set the order lists: a
document edited after the check, a check copied from another file, a checker type not on the list, no agent row, a
pattern present while the line says clean, the sha line of an older version. Synthetic roots only; the engine holds no
pattern: every pattern here is made up."""
import pytest

from _mw019 import (DOC_TEXT, FORMS, OUT, SUFFIX, add_agent, check_text, inspect, joined, make_root, profile_of,
                    record, set_outbox, sha_of, valid_file, write_check, write_doc)
from pathlib import Path


@pytest.fixture
def task(tmp_path):
    return make_root(tmp_path)


def test_a_check_with_every_line_and_a_proof_is_valid(task):
    """Checks: a state that is never valid is not the case, and one good agent among bad ones is enough. E3: a document whose check file holds the five lines and an equal sha256, names a listed checker, has a record of a session's write, and has an agent of that type that started and ended in that session after the document's last change and before the check was written, is valid."""
    rel = valid_file(task)
    status = inspect(task, rel)
    assert status.state == "valid"
    assert status.problems == []
    assert status.checker == "critic"
    assert status.rel == rel
    assert status.sha == sha_of(Path(task) / rel)
    assert status.time == "2026-11-11T10:03:00Z"
    other = valid_file(task, "b.md", agent=None, doc_when=130, check_when=400)  # the first agent ended before 130
    assert inspect(task, other).state == "unproven"
    add_agent(task, agent_id="late", started=500, ended=600)  # after the check: not a proof
    add_agent(task, agent_id="wrong", agent_type="verifier", started=140, ended=300)  # not the named type
    assert inspect(task, other).state == "unproven"
    add_agent(task, agent_id="good", started=141, ended=299)
    assert inspect(task, other).state == "valid"


def test_a_file_with_no_check_file_is_missing(task):
    """Catches: a file that counts as checked because nobody checked it. E3: a file under the outbox folder with no check file is missing, with no checker and no time, and the problem names the check file to write."""
    rel = write_doc(task)
    status = inspect(task, rel)
    assert status.state == "missing"
    assert status.checker is None
    assert status.time is None
    assert f"{rel}{SUFFIX}" in joined(status)


def test_a_document_edited_after_the_check_is_stale(task):
    """Catches: a check that outlives the text it checked. E4: the document changes after a valid check: its sha256 is not the check's, so the state is stale and the problem says the text changed since the check; writing the document back to the checked text makes it valid again."""
    rel = valid_file(task)
    assert inspect(task, rel).state == "valid"
    write_doc(task, "a.md", DOC_TEXT + "One more sentence.\n", when=300)
    status = inspect(task, rel)
    assert status.state == "stale"
    assert "changed" in joined(status)
    write_doc(task, "a.md", DOC_TEXT, when=0)
    assert inspect(task, rel).state == "valid"


def test_a_check_with_the_sha_of_an_older_version_is_stale(task):
    """Catches: a check written for version 1 and kept for version 2. E4: a check whose sha256 line is the sha of an earlier version is stale, however complete its other lines are and however good its agent."""
    rel = write_doc(task, "a.md", "Version one.\n")
    older = sha_of(Path(task) / rel)
    write_doc(task, "a.md", "Version two.\n")
    add_agent(task)
    write_check(task, rel, doc_sha=older)
    assert inspect(task, rel).state == "stale"


def test_a_check_copied_from_another_file_is_stale_or_unproven(task):
    """Catches: one check that stands for two files. E4: the check text of file A written beside file B: with different text its sha is not B's, so stale; with the same text the sha fits, but no session wrote B's check file through the write tools, so unproven and the problem names the missing record."""
    a = valid_file(task, "a.md", text="Text of file A.\n")
    other = write_doc(task, "b.md", "Text of file B.\n")
    (Path(task) / f"{other}{SUFFIX}").write_text((Path(task) / f"{a}{SUFFIX}").read_text(encoding="utf-8"),
                                                 encoding="utf-8", newline="")
    assert inspect(task, other).state == "stale"
    same = write_doc(task, "c.md", "Text of file A.\n")
    (Path(task) / f"{same}{SUFFIX}").write_text((Path(task) / f"{a}{SUFFIX}").read_text(encoding="utf-8"),
                                                encoding="utf-8", newline="")
    status = inspect(task, same)
    assert status.state == "unproven"
    assert "record" in joined(status)


def test_a_checker_type_outside_the_list_is_unproven(tmp_path):
    """Catches: any agent type signing a check. E5: a checker type not in outbox.checkers is unproven, the problem names the type and the key; a profile with no checkers at all has no valid check; the checker line names the agent type the proof looks for."""
    root = make_root(tmp_path)
    rel = valid_file(root, checker="checker: stranger", agent={"agent_type": "stranger"})
    status = inspect(root, rel)
    assert status.state == "unproven"
    assert "stranger" in joined(status)
    assert "outbox.checkers" in joined(status)
    own = valid_file(root, "b.md")
    assert inspect(root, own).state == "valid"
    set_outbox(root, dir=OUT)
    status = inspect(root, own)
    assert status.state == "unproven"
    assert "outbox.checkers" in joined(status)


@pytest.mark.parametrize("case, kwargs, word", [
    ("no agent row", {"agent": None}, "agent"),
    ("agent of another type", {"agent": {"agent_type": "verifier"}}, "critic"),
    ("agent of another session", {"agent": {"session": "s2"}}, "session"),
    ("no start row", {"agent": {"start_row": False}}, "start"),
    ("agent started before the last change", {"agent": {"started": 60, "ended": 220}, "doc_when": 100,
                                              "check_when": 300}, "after the last change"),
    ("agent ended before the last change", {"agent": {"started": 60, "ended": 120}, "doc_when": 150,
                                            "check_when": 300}, "after the last change"),
    ("agent ended after the check was written", {"agent": {"started": 60, "ended": 200}, "check_when": 180},
     "before the check"),
])
def test_a_check_with_no_matching_agent_row_is_unproven(task, case, kwargs, word):
    """Catches: a check that names a fresh reader nobody ran. E6: no agent row of the checker type in the writing session with a start and an end, an agent of another type or another session, a missing start row, an agent that started or ended before the document's last change, or one that ended after the check was written: unproven, and the problem says what was not found."""
    rel = valid_file(task, **kwargs)
    status = inspect(task, rel)
    assert status.state == "unproven", case
    assert word in joined(status), (case, status.problems)


def test_the_agent_must_have_started_and_ended_after_the_last_change_and_before_the_check(task):
    """Catches: an off-by-one that accepts an agent that read the old text. E6: the window is strict: an agent that ended at the very second the check was written, or started at the document's last change, is not inside it; one second inside on each side is."""
    edge = valid_file(task, "e.md", agent={"started": 0, "ended": 100}, doc_when=0, check_when=180)
    assert inspect(task, edge).state == "unproven"
    edge2 = valid_file(task, "f.md", agent={"started": 10, "ended": 180}, check_when=180)
    assert inspect(task, edge2).state == "unproven"
    inside = valid_file(task, "g.md", agent={"started": 1, "ended": 179}, check_when=180)
    assert inspect(task, inside).state == "valid"


def _patterns(root, text, name="ids.txt"):
    (Path(root) / "tools").mkdir(exist_ok=True)
    (Path(root) / "tools" / name).write_text(text, encoding="utf-8", newline="")
    set_outbox(root, dir=OUT, checkers=["critic"], id_patterns_file=f"tools/{name}")


def test_a_pattern_in_the_document_beats_a_clean_line(task):
    """Catches: an id that a fresh reader overlooked going out because the check said clean. E7: the engine scans the document with the regexes of outbox.id_patterns_file (blank lines and lines that start with a hash mark skipped); a hit makes the check unproven although the check says patterns: clean; the problem gives the line of the document and the number of the pattern, never the matched text; a document with no hit stays valid."""
    _patterns(task, "# made-up patterns\n\nZQX-\\d{4}\nplum\\d+\n")
    clean = valid_file(task, "clean.md", text="Nothing to see here.\n")
    assert inspect(task, clean).state == "valid"
    first = valid_file(task, "first.md", text="Line one.\nSee ZQX-1234 for details.\n")
    status = inspect(task, first)
    assert status.state == "unproven"
    assert "line 2" in joined(status)
    assert "pattern 1" in joined(status)
    assert "ZQX-1234" not in joined(status)
    second = valid_file(task, "second.md", text="plum77 appears here.\n")
    status = inspect(task, second)
    assert status.state == "unproven"
    assert "line 1" in joined(status)
    assert "pattern 2" in joined(status)
    assert "plum77" not in joined(status)


def test_a_missing_or_broken_patterns_file_is_unproven(task):
    """Catches: a scan that quietly does nothing when its patterns are gone. E7: a key that names a patterns file the engine cannot read, or a file with a line that is not a regex, makes every check unproven and the problem names the file (and the line); with no key there is no scan."""
    rel = valid_file(task, "a.md", text="ZQX-1234 is in here.\n")
    assert inspect(task, rel).state == "valid"  # no key: no scan
    set_outbox(task, dir=OUT, checkers=["critic"], id_patterns_file="tools/none.txt")
    status = inspect(task, rel)
    assert status.state == "unproven"
    assert "tools/none.txt" in joined(status)
    _patterns(task, "fine\\d\n([unclosed\n", name="broken.txt")
    status = inspect(task, rel)
    assert status.state == "unproven"
    assert "tools/broken.txt" in joined(status)
    assert "line 2" in joined(status)


@pytest.mark.parametrize("name, line", [
    ("numbers", "numbers: 12 checked, 2 contradictions"), ("numbers", "numbers: twelve checked, 0 contradictions"),
    ("claims", "claims: 7 checked, 1 overstated, 0 without basis"),
    ("claims", "claims: 7 checked, 0 overstated, 3 without basis"),
    ("patterns", "patterns: found 2"), ("links", "links: broken"), ("checker", "checker:")])
def test_a_line_in_the_wrong_form_is_named(task, name, line):
    """Catches: a check that says what it found but is read as a pass. E8: a line with a contradiction, an overstatement or a missing basis counted, a line that is not the fixed form, and a line that is left out are each unproven; the problem names the form of that line and of no other."""
    wrong = valid_file(task, "w.md", **{name: line})
    status = inspect(task, wrong)
    assert status.state == "unproven"
    assert FORMS[name] in joined(status), status.problems
    assert not any(form in joined(status) for other, form in FORMS.items() if other != name), (name, status.problems)
    left_out = valid_file(task, "o.md", omit=(name,))
    status = inspect(task, left_out)
    assert status.state == "unproven"
    assert FORMS[name] in joined(status)


def test_a_check_with_no_sha_line_names_it(task):
    """Catches: a check that fits any text because it names none. E8: a check file with no sha256 line is unproven and the problem gives the line's form; the line is the only one that can make a check stale."""
    rel = valid_file(task, omit=("sha256",))
    status = inspect(task, rel)
    assert status.state == "unproven"
    assert "sha256: " in joined(status)


def test_a_check_made_outside_the_write_tools_is_unproven(task):
    """Catches: a check forged by the shell, which the write gate cannot see. E9: a check file with every line and an equal sha, but no record that a session wrote it through a write tool (it was made by a shell or copied), is unproven; a record for another document does not count either."""
    rel = valid_file(task, "a.md")
    forged = write_doc(task, "b.md", "Forged text.\n")
    add_agent(task, agent_id="a2", started=70, ended=130)
    write_check(task, forged, recorded=False)
    status = inspect(task, forged)
    assert status.state == "unproven"
    assert "record" in joined(status)
    record(task, rel, check_sha=sha_of(Path(task) / f"{forged}{SUFFIX}"))  # a row of A with B's check sha
    assert inspect(task, forged).state == "unproven"


def test_a_check_edited_after_its_recorded_write_is_unproven(task):
    """Catches: a hand edit of an attestation that keeps the sha line right. E9: the check file is changed after the post step recorded its write (the record holds its sha): the file no longer is what a session wrote through the tools, so unproven; the change is the shell's or an editor's."""
    rel = valid_file(task)
    assert inspect(task, rel).state == "valid"
    path = Path(task) / f"{rel}{SUFFIX}"
    path.write_text(path.read_text(encoding="utf-8") + "extra note\n", encoding="utf-8", newline="")
    status = inspect(task, rel)
    assert status.state == "unproven"
    assert "record" in joined(status)
