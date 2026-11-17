"""Card MW-140: git names a file from the TOP of the repository; a file outside the task root is OUTSIDE, never judged under
a made-up in-root name. Two pure parts: `helpers.from_top(name, root, prefix)` (the one reader of a git name against the
top) and `core.decide_commit` for a commit whose facts carry outside files (refusal `file-outside-root`). No disk, no git:
every call runs under the guard. One test id is one case; the expected values are written from the card rows. Synthetic
values only."""
import re

import pytest

import _engine  # noqa: F401  (puts the engine folder on the import path)
import core
import helpers
from _no_io import no_io

ROOT = "C:/top/task/x"  # a fictional root; from_top reads no disk when the prefix is given
PREFIX = "task/x"
REASON = "file-outside-root"
COMMIT = "git commit -m 'CARD-001 work'"
BUILTINS = frozenset(helpers.git_builtins())  # read before any guard: the shell hands it over as a fact
CARD_RE = r"(?<![A-Za-z0-9_-])CARD-[0-9]{3,}(?![0-9A-Za-z_])"
FOLDER = "mkway/cards/CARD-001-first"
EXEMPT = ("mkway/cards/REGISTER.md", "mkway/ledger")


def top(name, prefix=PREFIX):
    return helpers.from_top(name, ROOT, prefix)


def is_outside(value, name):
    return isinstance(value, helpers.Outside) and value.name == name


# ==== the helper: a name git gave, read against the top ==========================================================================

def test_a_name_under_the_root_is_the_root_relative_name():
    """Catches: an in-root file whose name keeps the root's folders, so no card Path matches it."""
    assert top("task/x/src/a.py") == "src/a.py"


def test_a_file_of_the_top_is_outside_with_its_true_name():
    """Catches: `README.md` of the top read as the in-root `README.md` (the made-up name)."""
    assert is_outside(top("README.md"), "README.md")


def test_a_folder_of_the_top_is_outside_with_its_true_name():
    """Catches: `scripts/x.py` of the top read as the in-root `scripts/x.py`."""
    assert is_outside(top("scripts/x.py"), "scripts/x.py")


def test_a_sibling_folder_that_starts_with_the_roots_name_is_outside():
    """Catches: a prefix compare on text (`task/x2/f` starts with `task/x`): the sibling folder read as inside."""
    assert is_outside(top("task/x2/f"), "task/x2/f")


def test_a_file_named_like_the_root_itself_is_outside():
    """Catches: the root's own folder name read as a file inside the root."""
    assert is_outside(top("task/x"), "task/x")


def test_the_root_name_in_another_letter_case_is_inside_on_windows(monkeypatch):
    """Catches: a case-sensitive compare on Windows, where `Task/X` is the same folder as `task/x`."""
    monkeypatch.setattr(helpers, "CASE_FOLD", True)
    assert top("Task/X/f.txt") == "f.txt"


def test_the_root_name_in_another_letter_case_is_outside_where_case_counts(monkeypatch):
    """Catches: a case-folded compare on a case-sensitive file system, where `Task/X` is another folder."""
    monkeypatch.setattr(helpers, "CASE_FOLD", False)
    assert is_outside(top("Task/X/f.txt"), "Task/X/f.txt")


def test_a_name_that_folds_to_the_root_only_by_a_longer_fold_is_outside_on_windows(monkeypatch):
    """Catches: `casefold` turning the one letter `ß` into `ss`, so the folder `task/straße` reads as `task/strasse`."""
    monkeypatch.setattr(helpers, "CASE_FOLD", True)
    assert is_outside(top("task/straße/f", prefix="task/strasse"), "task/straße/f")


def test_a_name_with_a_space_stays_inside():
    """Catches: a name git would quote (a space) read as unplaceable and refused."""
    assert top("task/x/my file.py") == "my file.py"


def test_a_name_with_a_non_ascii_letter_stays_inside():
    """Catches: a name git would quote (a non-ASCII letter) read as unplaceable and refused."""
    assert top("task/x/caf\u00e9.py") == "caf\u00e9.py"


def test_a_name_git_quoted_is_outside():
    """Catches: a quoted name (`"task/x/caf\\303\\251.txt"`, the form git prints without `-z`) placed as an in-root file."""
    assert is_outside(top('"task/x/caf\\303\\251.txt"'), '"task/x/caf\\303\\251.txt"')


UNPLACEABLE = [
    pytest.param("task/x/../README.md", id="a_dot_dot_segment"),
    pytest.param("task/x/./a.py", id="a_dot_segment"),
    pytest.param("task/x//a.py", id="an_empty_segment"),
    pytest.param("task/x/a/", id="a_trailing_slash"),
    pytest.param("/task/x/a.py", id="an_absolute_name"),
    pytest.param("task/x/a\0b", id="a_nul"),
    pytest.param("", id="an_empty_name"),
    pytest.param("task/x/\udcff.txt", id="bytes_that_are_not_utf_8"),
]


@pytest.mark.parametrize("name", UNPLACEABLE)
def test_a_name_that_cannot_be_placed_is_outside(name):
    """Catches: a name that cannot be placed treated as inside (a fail-open gate); it is outside, refused."""
    assert isinstance(top(name), helpers.Outside)


def test_a_name_that_is_not_text_is_outside():
    """Catches: a non-text name that raises or passes."""
    assert isinstance(top(None), helpers.Outside)


def test_a_backslash_name_is_outside_on_windows(monkeypatch):
    """Catches: `task/x\\..\\..\\README.md`, which Windows reads as a path above the root, placed inside by its first segments."""
    monkeypatch.setattr(helpers, "CASE_FOLD", True)
    assert isinstance(top("task/x/..\\..\\README.md"), helpers.Outside)


def test_a_drive_name_is_outside_on_windows(monkeypatch):
    """Catches: `C:evil` placed as a name below the root."""
    monkeypatch.setattr(helpers, "CASE_FOLD", True)
    assert isinstance(top("C:task/x/a.py"), helpers.Outside)


def test_a_root_that_is_the_top_changes_nothing():
    """Catches: a root at the top reading a name under it as outside or rewriting it: every name is inside as git gave it."""
    names = ["README.md", "task/x/f", "src/a.py", "mkway/cards/REGISTER.md"]
    assert [top(n, prefix="") for n in names] == names


def test_an_outside_name_never_equals_an_in_root_name():
    """Catches: an outside `README.md` equal to the in-root `README.md`, so a set or a dict of names merges the two files."""
    outside = top("README.md")
    assert (outside == "README.md", "README.md" == outside, outside in {"README.md"}, outside in ["README.md"]) == (
        False, False, False, False)


def test_two_outside_names_of_one_file_are_equal_and_hashable():
    """Catches: an outside value that cannot sit in a set, so a file named twice is counted twice."""
    assert len({top("README.md"), top("README.md")}) == 1


def test_the_text_of_an_outside_name_says_where_it_lies():
    """Catches: a display that shows the made-up in-root name instead of git's top-relative one."""
    assert top("docs/n.md").text == "outside the task root: docs/n.md"


def test_git_bytes_that_are_not_utf_8_are_kept_apart_from_text_names():
    """Catches: a name decoded with a lossy fold, so the bytes of one file read as the name of another."""
    got = helpers.decode_git(b"task/x/\xff.txt\0")
    assert (isinstance(got, str), isinstance(top(got.split("\0")[0]), helpers.Outside)) == (True, True)


def test_git_text_that_is_already_text_is_returned_as_it_is():
    """Catches: a decode of a value that is text already (a fake reader), which raises."""
    assert helpers.decode_git("task/x/a.py\0") == "task/x/a.py\0"


def test_the_printed_name_of_an_outside_file_is_printable():
    """Catches: an outside name with a lone surrogate that raises when a refusal text is printed."""
    shown = top("task/x/\udcff.txt").name
    assert shown.encode("utf-8")  # raises on a surrogate


# ==== the commit decision for outside files =====================================================================================

def facts(commit, **kw):
    base = dict(command=COMMIT, git_builtins=BUILTINS, commits=(commit,), card_id="CARD-001", card_found=True,
                card_status="open", card_paths=frozenset({"README.md", "scripts", "src"}), card_folder=FOLDER,
                exempt=EXEMPT, card_id_pattern=CARD_RE, owner_fix="the owner fixes it")
    base.update(kw)
    return core.Facts(**base)


def commit(outside, *taken, **kw):
    live = [rel for status, rel, _source in taken if status != "D"]
    return core.CommitFacts(message="CARD-001 work", taken=tuple(taken), ignored=frozenset(),
                            sizes={rel: 1 for rel in live}, outside=tuple(outside), **kw)


def decide(f):
    with no_io():
        return core.decide_commit(f)


def staged(*names, status="A"):
    return [(status, name, "index") for name in names]


def test_an_outside_file_is_refused_with_the_new_reason_and_its_true_name():
    """Catches: an outside file judged by the card Paths (here `README.md` is a Path) and passed."""
    v = decide(facts(commit(staged("README.md"))))
    assert (v.kind, v.reason) == ("refuse", REASON)
    assert v.text.startswith("README.md lies outside the task root")


def test_the_new_reason_is_a_reason_of_the_core():
    """Catches: a reason the registry does not know, so the concept table and the manifest never list it."""
    assert REASON in core.REASONS


def test_the_refusal_names_the_ways_out_that_work_and_no_ruling_id():
    """Catches: a way out that does not exist (`move it later` is refused too), or a ruling id in an engine text."""
    v = decide(facts(commit(staged("README.md"))))
    text = v.text
    assert ("keep the file inside the task root" in text, "git restore --staged :/README.md" in text,
            "in their own terminal" in text, re.search(r"\bR\d{2,}", text), "move it later" in text,
            "MW-140" in text) == (True, True, True, None, False, False)


def test_a_named_path_has_the_leave_it_out_way_out_and_no_restore():
    """Catches: `git restore --staged` offered for a file that is not staged (a `--` commit takes the named path alone)."""
    v = decide(facts(commit([("M", "other/b.py", "work")], paths=("../../other/b.py",))))
    assert ("leave it out of the paths after `--`" in v.text, "git restore" in v.text) == (True, False)


def test_a_dash_a_commit_has_the_without_dash_a_way_out():
    """Catches: a way out that keeps `-a`, which takes the same outside file again."""
    v = decide(facts(commit([("M", "other/b.py", "work")], all=True)))
    assert "commit without `-a` and name your own files after `--`" in v.text


def test_a_deleted_outside_file_is_refused_too():
    """Catches: a deletion of an outside file let through as «removing the mess»: the commit still takes a file of the top."""
    v = decide(facts(commit([("D", "other/b.py", "index")])))
    assert (v.kind, v.reason) == ("refuse", REASON)


def test_the_refusal_lists_only_the_outside_files():
    """Catches: a refusal that lists the in-root files of the commit as outside."""
    v = decide(facts(commit(staged("docs/n.md", "README.md"), *staged("src/a.py"))))
    assert v.text.split(" lie outside")[0] == "docs/n.md, README.md"


def test_several_outside_files_are_counted_after_the_shown_ones():
    """Catches: a refusal text with no end for a commit of hundreds of outside files."""
    names = [f"d/f{n}.txt" for n in range(core.SHOWN + 3)]
    v = decide(facts(commit(staged(*names))))
    assert "and 3 more" in v.text


OUTSIDE_ROWS = [
    pytest.param(dict(), id="the_card_paths_name_it"),
    pytest.param(dict(exempt=("README.md",)), id="an_exempt_entry_names_it"),
    pytest.param(dict(card_paths=frozenset()), id="an_open_card_with_no_paths"),
    pytest.param(dict(card_id=None, card_found=False, card_status=None, card_paths=frozenset(), card_folder=None),
                 id="no_card_is_held"),
    pytest.param(dict(card_status="closed"), id="the_card_is_closed"),
]


@pytest.mark.parametrize("over", OUTSIDE_ROWS)
def test_an_outside_file_is_refused_whatever_the_card_or_the_exempt_entries_say(over):
    """Catches: an outside file matched against the card Paths, the exempt entries or the card state, then passed."""
    v = decide(facts(commit(staged("README.md")), **over))
    assert (v.kind, v.reason) == ("refuse", REASON)


def test_an_outside_file_is_refused_though_the_session_own_set_holds_the_name():
    """Catches: an outside file whose name equals a name of the session's own writable set, passed as the session's own."""
    c = commit(staged("mkway/asks/q.md"), own=frozenset({"mkway/asks/q.md"}))
    assert decide(facts(c)).reason == REASON


def test_an_in_root_file_beside_an_outside_one_is_not_judged_before_the_outside_refusal():
    """Catches: an in-root refusal (file-not-in-card) that hides the outside file the commit also takes."""
    v = decide(facts(commit(staged("README.md"), *staged("notes/n.md"))))
    assert v.reason == REASON


def test_a_commit_with_no_outside_file_is_judged_as_before():
    """Catches: the new check refusing a commit that takes in-root files only."""
    v = decide(facts(commit([], *staged("src/a.py"))))
    assert v.kind == "allow"


def test_an_in_root_file_outside_the_paths_is_still_file_not_in_card():
    """Catches: the old refusal for an in-root file outside the card Paths replaced by the new reason."""
    v = decide(facts(commit([], *staged("notes/n.md"))))
    assert (v.kind, v.reason) == ("refuse", "file-not-in-card")


def test_a_register_that_cannot_be_trusted_is_refused_before_the_outside_check():
    """Catches: the outside refusal answering where the register is tampered with, hiding the owner's fix."""
    v = decide(facts(commit(staged("README.md")), register_problem="the register differs from its seal"))
    assert v.reason == "register-tampered"
