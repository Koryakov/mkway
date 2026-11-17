"""Card MW-052: `core.decide_commit(facts) -> Verdict` as table tests. No disk, no git: each row builds a `Facts` record
and reads the verdict; every call runs under a guard that fails on any file, process or clock access. One test id is one
case (a `parametrize` row has its own id); the expected reason and the words of the text are written from the card rows,
never computed. The old case ids stay in the pytest ids (`mw006_e7_...`). The map of old tests is
`cards/MW-052-commit-core/case_map.md`. Synthetic values only."""
import builtins
import contextlib
import io
import os
import pathlib
import subprocess
import time

import pytest

import _engine  # noqa: F401  (puts the engine folder on the import path)
import core
import helpers
from _no_io import no_io

BUILTINS = frozenset(helpers.git_builtins())  # read here, before any guard: the shell hands it over as a fact
CARD_RE = r"(?<![A-Za-z0-9_-])CARD-[0-9]{3,}(?![0-9A-Za-z_])"
COMMIT = "git commit -m 'CARD-001 work'"
OWNER_FIX = "run `python mkway/engine/mkway.py card resync` in your own terminal"
EXEMPT = ("mkway/cards/REGISTER.md", "mkway/ledger")
FOLDER = "mkway/cards/CARD-001-first"


def A(rel):
    return ("A", rel, "index")


def M(rel):
    return ("M", rel, "index")


def D(rel):
    return ("D", rel, "index")


def W(rel, status="M"):
    return (status, rel, "work")


def commit(*taken, message="CARD-001 work", sizes=None, **kw):
    """One commit record. `taken` rows as arguments, or `taken=core.Unread(...)` for a read that failed."""
    if "taken" in kw:
        taken = kw.pop("taken")
        live = []
    else:
        live = [rel for status, rel, _source in taken if status != "D"]
        taken = tuple(taken)
    kw.setdefault("ignored", frozenset())
    return core.CommitFacts(message=message, taken=taken,
                            sizes={rel: 1 for rel in live} if sizes is None else sizes, **kw)


def facts(*commits, **kw):
    base = dict(command=COMMIT, git_builtins=BUILTINS, commits=tuple(commits), card_id="CARD-001", card_found=True,
                card_status="open", card_paths=frozenset({"src", "lib/a.py"}), card_folder=FOLDER, exempt=EXEMPT,
                card_id_pattern=CARD_RE, owner_fix=OWNER_FIX)
    base.update(kw)
    return core.Facts(**base)


def no_card(*commits, **kw):
    """A session that holds no card (the register has no row for it)."""
    return facts(*commits, card_id=None, card_found=False, card_status=None, card_paths=frozenset(),
                 card_folder=None, **kw)


def decide(f):
    with no_io():
        return core.decide_commit(f)


def check(f, reason, *has, hasnot=()):
    """The verdict is `reason` (None: allow); its text holds each of `has` and none of `hasnot`."""
    v = decide(f)
    assert (v.reason if v.kind == core.REFUSE else None) == reason, (v, reason)
    for part in has:
        assert part in v.text, (part, v.text)
    for part in hasnot:
        assert part not in v.text, (part, v.text)
    return v


def _misses(f, reason, *has, hasnot=()):
    """What the verdict gets wrong: its reason (None: allow), the words its text lacks and the words it holds that it must not. Empty when it is as written."""
    v = decide(f)
    got = v.reason if v.kind == core.REFUSE else None
    wrong = [("reason", got, reason)] if got != reason else []
    return wrong + [("missing", part, v.text) for part in has if part not in v.text] + [("unwanted", part, v.text) for part in hasnot if part in v.text]


def row(f, reason, *has, hasnot=(), id):
    """One case of a table: the facts, the reason (None: allow), the words the text holds, the words it does not."""
    return pytest.param(f, reason, has, hasnot, id=id)


def _warm():
    core.decide_commit(facts(commit(A("src/a.py"))))  # first calls import lazily: keep that out of the guard


_warm()

CASE = "f, reason, has, hasnot"
CARDLESS = dict(card_paths=frozenset())  # an empty Paths: only the content rules can refuse


# ---- the verdict and the shape of the record --------------------------------------------------------------------------

def test_an_allow_verdict_is_data_with_no_rows():
    """Checks: an allow verdict is data of kind allow with no reason and no rows."""
    assert (core.allow().kind, core.allow().reason, core.allow().records) == ("allow", None, ())


def test_a_refusal_carries_its_reason_its_text_and_its_rows():
    """Checks: a refusal carries its reason, its text and its rows."""
    v = core.refuse("junk-file-staged", "x is junk", records=(("rows.jsonl", {"a": 1}),))
    assert (v.kind, v.reason, v.text, v.records) == ("refuse", "junk-file-staged", "x is junk",
                                                     (("rows.jsonl", {"a": 1}),))


def test_an_allow_with_line_is_its_own_kind():
    """Checks: an allow with a line is its own kind and carries its reason and its text."""
    v = core.allow_with_line("note", "a line")
    assert (v.kind, v.reason, v.text) == ("allow-with-line", "note", "a line")


def test_a_refusal_with_no_reason_is_a_value_error():
    """Catches: a refusal the dispatcher could not tag with a reason."""
    with pytest.raises(ValueError):
        core.refuse("", "no reason")


def test_an_unknown_verdict_kind_is_a_value_error():
    """Catches: a verdict the shell would not know how to map."""
    with pytest.raises(ValueError):
        core.Verdict("deny", "r", "t")


REASON_FACTS = [
    pytest.param(facts(commit(A("docs/c.md"))), "file-not-in-card", id="file-not-in-card"),
    pytest.param(facts(commit(A("a.tmp")), **CARDLESS), "junk-file-staged", id="junk-file-staged"),
    pytest.param(facts(commit(A("d.csv")), **CARDLESS), "data-file-staged", id="data-file-staged"),
    pytest.param(facts(commit(taken=core.Unread())), "commit-unreadable", id="commit-unreadable"),
    pytest.param(facts(commit(A("src/a.py")), register_problem="x"), "register-tampered", id="register-tampered"),
    pytest.param(facts(commit(A("src/a.py"), message="no id"), card_paths=frozenset()), "commit-message-card",
                 id="commit-message-card"),
]


@pytest.mark.parametrize("f, reason", REASON_FACTS)
def test_every_refusal_names_a_reason_the_core_declares(f, reason):
    """Catches: a refusal whose reason the dispatcher would log as undeclared"""
    # The reason is one of `core.REASONS`, the set the manifest declares (the wiring test)
    assert decide(f).reason == reason
    assert reason in core.REASONS


# ---- MW-006 E7..E13: the files, the card, the fail-closed reads ---------------------------------------------------------

OUTSIDE = [
    row(facts(commit(A("docs/c.md"), A("lib/a.py"), A("other/b.py"), A("src/a.py"))), "file-not-in-card", "CARD-001",
        "(lib/a.py; src)", "git restore --staged", id="mw006_e7_outside_files_listed"),
    row(facts(commit(A("lib/a.py"), A("src/a.py"))), None, id="mw006_e7_after_unstage_allowed"),
    row(facts(commit(A("src/a.py"), *[A(f"extra/f{i}.py") for i in range(12)])), "file-not-in-card", "and 4 more",
        id="mw006_e7_twelve_outside_counted"),
]


@pytest.mark.parametrize(CASE, OUTSIDE)
def test_outside_files(f, reason, has, hasnot):
    """Catches: a staged file outside the card's Paths that is committed, or a refusal that does not name it."""
    assert _misses(f, reason, *has, hasnot=hasnot) == []


def test_outside_files_lists_only_the_outside_ones():
    """Catches: a refusal that lists the files inside the Paths too (mw006_e7)"""
    # the files named before `are not in` are the two outside ones and no other
    v = check(facts(commit(A("docs/c.md"), A("lib/a.py"), A("other/b.py"), A("src/a.py"))), "file-not-in-card")
    assert v.text.split(" are not in")[0] == "docs/c.md, other/b.py"


def test_always_allowed_files_pass_whatever_the_paths_say():
    """Checks: the card's own folder, the register, the ledger folder and `paths.exempt` pass (mw006_e8)"""
    f = facts(commit(M("mkway/cards/CARD-001-first/CARD.md"), M("mkway/cards/REGISTER.md"), A("mkway/ledger/rows.md"),
                     A("notes/n.md")), card_paths=frozenset({"src"}), exempt=(*EXEMPT, "notes/**"))
    assert _misses(f, None) == []


NO_CARD = [
    row(no_card(commit(A("mkway/cards/CARD-001-first/CARD.md"), A("src/a.py")), exempt=(*EXEMPT, "notes/**")),
        "file-not-in-card", "src/a.py", "no open card", "no card is taken", "mkway/cards/CARD-001-first/CARD.md",
        id="mw006_e8_a_file_and_a_card_folder_not_held"),
    row(no_card(commit(M("mkway/cards/REGISTER.md"), A("mkway/ledger/rows.md"), A("notes/n.md")),
                exempt=(*EXEMPT, "notes/**")), None, id="mw006_e8_only_the_always_allowed"),
]


@pytest.mark.parametrize(CASE, NO_CARD)
def test_a_session_with_no_card_commits_only_the_always_allowed_files(f, reason, has, hasnot):
    """Catches: a session with no card that commits a file (mw006_e8)"""
    # no card taken: any file but the register, the ledger and `paths.exempt` is refused, the folder of a card the session does not hold included
    assert _misses(f, reason, *has, hasnot=hasnot) == []


def test_a_card_that_is_not_open_holds_no_commit():
    """Catches: a commit under a card the owner has not opened (mw006_e8)"""
    # the held card is `waiting`: the commit of src/a.py is refused and the text says which status
    assert _misses(facts(commit(A("src/a.py")), card_status="waiting"), "file-not-in-card", "CARD-001 is waiting", "no open card") == []


def test_an_empty_paths_is_no_file_rule():
    """Checks: the card has no Paths: any file passes (mw006_e8)"""
    assert _misses(facts(commit(A("anything/at/all.py")), card_paths=frozenset()), None) == []


NO_RECORD = [
    row(facts(commit(A("src/x.py"))), None, id="mw006_e11_a_file_in_the_paths_passes_whoever_wrote_it"),
    row(no_card(commit(A("src/x.py"))), "file-not-in-card", id="mw006_e11_a_session_with_no_card_still_meets_rule_1"),
]


@pytest.mark.parametrize(CASE, NO_RECORD)
def test_no_session_record_decides_a_commit(f, reason, has, hasnot):
    """Catches: a file refused (or passed) by a record of its writer (mw006_e11 (mw034 e8))"""
    # the Paths and the card decide, not who wrote the file
    assert _misses(f, reason, *has, hasnot=hasnot) == []


FORMS = [
    row(facts(commit(W("src/a.py"), paths=("src/a.py",))), None, id="mw006_e9_paths_form_allowed"),
    row(facts(commit(W("src/a.py"), W("other/b.py", "A"), paths=("src/a.py", "other/b.py"))), "file-not-in-card",
        "other/b.py", "`--`", hasnot=("src/a.py",), id="mw006_e9_named_outside_refused"),
    row(facts(commit(W("src/a.py", "A"), A("other/b.py"), paths=("src/a.py",), include=True),
              command="git commit -i -m 'CARD-001 x' -- src/a.py"), "file-not-in-card",
        "git restore --staged other/b.py", id="mw006_e9_include_with_staged_outside"),
    row(facts(commit(A("other/b.py"), A("src/a.py"))), "file-not-in-card", "other/b.py",
        id="mw006_e9_plain_with_staged_outside"),
    row(facts(commit(A("other/b.py"), A("src/a.py")), command="git commit --amend -m 'CARD-001 x'"),
        "file-not-in-card", "other/b.py", id="mw006_e9_amend_with_staged_outside"),
    row(facts(commit(A("src/a.py"))), None, id="mw006_e9_plain_after_unstage"),
    row(facts(commit(W("src/a.py", "A"), paths=("src/a.py",), include=True)), None, id="mw006_e9_include_after_unstage"),
    row(facts(commit(A("src/a.py")), command="git commit --amend -m 'CARD-001 x'"), None,
        id="mw006_e9_amend_after_unstage"),
    row(facts(commit(W("other/t.py"), A("src/a.py"), all=True), command="git commit -a -m 'CARD-001 x'"),
        "file-not-in-card", "other/t.py", "-a", id="mw006_e9_all_takes_tracked_changes"),
    row(facts(commit(D("src/old.py"), A("src/mine.py"), A("src/glob1.txt"), A("other/other_session.py"),
                     D("other/theirs_old.py"))),
        "file-not-in-card", "other/other_session.py", "other/theirs_old.py",
        "git restore --staged other/other_session.py other/theirs_old.py",
        hasnot=("src/mine.py", "src/old.py", "src/glob1.txt"), id="mw006_e10_ride_in_by_paths_alone"),
    row(facts(commit(W("other/theirs_old.py"), all=True), command="git commit -a -m 'CARD-001 x'"),
        "file-not-in-card", "-a", id="mw006_e10_all_way_out_is_no_dash_a"),
]


@pytest.mark.parametrize(CASE, FORMS)
def test_each_commit_form_is_judged_by_what_it_takes(f, reason, has, hasnot):
    """Catches: a commit form judged by files it does not take, or a foreign staged file carried in."""
    assert _misses(f, reason, *has, hasnot=hasnot) == []


STAGING = ["git add src/b.py && " + COMMIT, "git add -f src/b.py; " + COMMIT, "git rm -q src/a.py && " + COMMIT,
           "git restore --staged src/a.py && " + COMMIT, "git reset -q && " + COMMIT,
           "git mv src/a.py src/c.py && " + COMMIT, COMMIT + " && git add -A", "git add . ; " + COMMIT]


@pytest.mark.parametrize("command", STAGING)
def test_staging_in_the_same_command_is_refused(command):
    """Catches: a commit judged by an index that the same command then changes (mw006_e12 (mw033 e4))"""
    # the hook reads the index before the command runs; the text names the way out
    assert _misses(facts(commit(A("src/a.py")), command=command), "commit-unreadable", "call of its own") == []


@pytest.mark.parametrize("join", ["&&", ";"])
def test_a_chained_add_and_commit_says_to_use_two_calls(join):
    """Catches: a refusal that does not say how to go on (mw033 e4)"""
    # the refusal names the fix: git add and git commit as two separate calls
    assert _misses(facts(commit(A("src/a.py")), command=f"git add src/a.py {join} git commit -m 'CARD-001 add the thing'"),
                   "commit-unreadable", "run git add and git commit as two separate calls") == []


def test_staging_in_the_same_powershell_command_is_refused():
    """Catches: PowerShell left out of the staging rule."""
    assert _misses(facts(commit(A("src/a.py")), command="git add src/b.py ; " + COMMIT, tool_name="PowerShell",
                         shell="powershell"), "commit-unreadable") == []


READ_ONLY = [("git status && " + COMMIT, "Bash", "bash"), (COMMIT + " && git log --oneline -1", "Bash", "bash"),
             ("git diff --cached --stat && " + COMMIT + " && git show --stat HEAD", "Bash", "bash"),
             (COMMIT, "PowerShell", "powershell")]


@pytest.mark.parametrize("command, tool, shell", READ_ONLY)
def test_a_read_only_git_call_beside_the_commit_is_fine(command, tool, shell):
    """Checks: the nearest allow of the staging rule: a read-only git call beside the commit changes no index"""
    assert _misses(facts(commit(A("src/a.py")), command=command, tool_name=tool, shell=shell), None) == []


UNREADABLE = ["cd $WHERE && " + COMMIT, "bash -c \"" + COMMIT + "\"", "git commit --inc -m 'CARD-001 x'",
              "git commit --pathspec-from-file=list.txt -m 'CARD-001 x'", "git commit -m 'CARD-001 x",
              "git -c alias.ci=commit ci -m x"]


@pytest.mark.parametrize("command", UNREADABLE)
def test_a_commit_the_reader_cannot_read_fails_closed(command):
    """Catches: a commit the gate could not read that is allowed through (mw006_e13)"""
    # a folder from a variable, a carried command, an unknown option, a path list in a file, a text that does not parse, an alias: refused `commit-unreadable` with a text
    v = check(facts(commit(A("src/a.py"), folder_unreadable="$WHERE" in command), command=command), "commit-unreadable")
    assert v.text.strip()


@pytest.mark.parametrize("command", ["git status", "git log --grep commit", "echo done", "python -m pytest", "ls -la", ""])
def test_a_command_that_is_no_commit_passes(command):
    """Checks: the reader found no commit in the text (mw006_e13)"""
    assert _misses(facts(command=command), None) == []


NOT_GATED = [pytest.param(facts(commit(A("src/a.py")), command="git commit", tool_name="Read"), id="a_tool_that_is_no_shell"),
             pytest.param(facts(commit(A("src/a.py")), vcs="none"), id="a_project_with_no_git")]


@pytest.mark.parametrize("f", NOT_GATED)
def test_a_tool_that_is_no_shell_and_a_project_with_no_git_pass(f):
    """Checks: `Read` is no shell tool; `vcs: none` is not gated (mw006_e13)"""
    assert _misses(f, None) == []


GIT_FAILED = [
    row(facts(commit(taken=core.Unread("a git read did not answer within 10 s, so the commit could not be checked; "
                                      "run it again"))), "commit-unreadable", "a git read did not answer", "run it again",
        id="the_shells_text_when_git_timed_out"),
    row(facts(commit(taken=core.Unread())), "commit-unreadable", "could not be read from git", "run it again",
        id="the_cores_text_when_git_answered_non_zero"),
    row(facts(commits=core.Unread("boom, run it again")), "commit-unreadable", "boom", id="the_commits_could_not_be_read"),
]


@pytest.mark.parametrize(CASE, GIT_FAILED)
def test_a_git_read_that_failed_refuses_with_its_text_or_the_default(f, reason, has, hasnot):
    """Catches: a commit allowed because git could not say what it takes (mw006_e13)"""
    # git did not answer in time (the shell's text) or answered non-zero (the core's text): both fail closed
    assert _misses(f, reason, *has, hasnot=hasnot) == []


TAMPERED = [
    row(facts(commit(A("src/a.py")), register_problem="the register changed outside the engine"), "register-tampered",
        "card resync", "no commit is checked until the owner checks it", id="the_register_is_not_what_the_engine_wrote"),
    row(facts(commit(A("src/a.py")), register_problem=core.Unread()), "commit-unreadable", "run it again",
        id="the_register_could_not_be_read"),
    row(no_card(commit(A("mkway/ledger/x.md")), register_problem="ignored: no card is held, no register read"), None,
        id="a_session_with_no_card_reads_no_register"),
]


@pytest.mark.parametrize(CASE, TAMPERED)
def test_a_tampered_register_refuses_and_names_the_owners_way_out(f, reason, has, hasnot):
    """Catches: a commit judged by a card row nobody can trust (mw006_e13)"""
    # the sealed register is not what the engine wrote
    assert _misses(f, reason, *has, hasnot=hasnot) == []


# ---- MW-006 E14..E19: junk, ignored, data, size -----------------------------------------------------------------------

JUNK_FILES = ["src/__pycache__/mod.cpython-312.pyc", "mod.pyc", "tests/.pytest_cache/CACHEDIR.TAG",
              "deep/er/.pytest_tmp/x.txt", "build/run.log", "a.tmp", "src/a.orig", "src/a.rej", "x/.DS_Store",
              "img/Thumbs.db"]


@pytest.mark.parametrize("rel", JUNK_FILES)
def test_junk_files_are_refused_at_any_depth(rel):
    """Catches: junk committed (mw006_e14)"""
    # junk is judged before data (`Thumbs.db` is junk), by name or glob at any depth, a folder pattern at any depth; the text names the file, the key and the way out
    assert _misses(facts(commit(A(rel)), **CARDLESS), "junk-file-staged", rel, "commit.junk", "git restore --staged") == []


@pytest.mark.parametrize("rel", ["src/pycache_notes.md", "logs.md", "src/pytest_cache.py", "docs/Thumbs.md"])
def test_names_that_only_look_like_junk_pass(rel):
    """Checks: the nearest allow of the junk rule: a name that only contains a junk word"""
    assert _misses(facts(commit(A(rel)), **CARDLESS), None) == []


def test_two_junk_files_are_named_together():
    """Catches: a refusal that names one junk file and hides the other."""
    v = check(facts(commit(A("a.tmp"), A("keep/b.rej"), A("src/ok.py")), **CARDLESS), "junk-file-staged")
    assert v.text.split(" are ")[0] == "a.tmp, keep/b.rej"


IGNORED = [
    row(facts(commit(A("secret_notes/new.txt"), ignored=frozenset({"secret_notes/new.txt"})), **CARDLESS),
        "ignored-file-staged", "secret_notes/new.txt", "git restore --staged", "add -f", id="mw006_e15_folder_pattern"),
    row(facts(commit(A("notes/today.keep"), ignored=frozenset({"notes/today.keep"})), **CARDLESS),
        "ignored-file-staged", id="mw006_e15_name_pattern"),
    row(facts(commit(A("notes/today.md")), **CARDLESS), None, id="mw006_e15_not_ignored_passes"),
]


@pytest.mark.parametrize(CASE, IGNORED)
def test_a_force_added_ignored_file_is_refused(f, reason, has, hasnot):
    """Catches: the ignore file overridden by a commit (mw006_e15)"""
    # a new staged file that git ignores; the text names it and `add -f`
    assert _misses(f, reason, *has, hasnot=hasnot) == []


def test_an_ignored_file_already_in_the_repository_stays_editable():
    """Checks: a changed (not added) file is not a new force-add, even when the ignore rules match it (mw006_e15)"""
    assert _misses(facts(commit(M("secret_notes/old.txt"), ignored=frozenset()), **CARDLESS), None) == []


def test_ignore_rules_that_could_not_be_read_fail_closed():
    """Catches: a new file allowed because git's ignore answer is missing."""
    assert _misses(facts(commit(A("src/a.py"), ignored=core.Unread()), **CARDLESS), "commit-unreadable", "ignore rules") == []


DATA_FILES = ["data/a.csv", "x.tsv", "out/book.xlsx", "old.xls", "t/p.parquet", "app.db", "s/lite.sqlite",
              "s/lite3.sqlite3", "notes.bak", "d/state.dump"]


@pytest.mark.parametrize("rel", DATA_FILES)
def test_data_files_are_refused_by_extension(rel):
    """Catches: a data file committed into the repository (mw006_e16)"""
    assert _misses(facts(commit(A(rel)), **CARDLESS), "data-file-staged", rel, "commit.data_patterns", "git restore --staged") == []


@pytest.mark.parametrize("rel", ["docs/data.csv.md", "src/csv_tools.py", "csv/readme.txt", "src/db.py"])
def test_names_that_only_contain_a_data_extension_pass(rel):
    """Checks: the nearest allow of the data rule: the extension is only part of the name"""
    assert _misses(facts(commit(A(rel)), **CARDLESS), None) == []


SIZES = [
    row(facts(commit(A("src/just_under.txt"), sizes={"src/just_under.txt": 1000 * 1024}), **CARDLESS), None,
        id="mw006_e17_under_the_limit"),
    row(facts(commit(A("src/big.txt"), sizes={"src/big.txt": 1100 * 1024}), **CARDLESS), "file-too-large", "src/big.txt",
        "1100 KB", "1024", "commit.max_file_kb", "git restore --staged", id="mw006_e17_over_the_limit"),
]


@pytest.mark.parametrize(CASE, SIZES)
def test_a_file_over_the_size_limit_is_refused_and_one_under_passes(f, reason, has, hasnot):
    """Catches: a file over the limit committed (mw006_e17)"""
    # over `max_file_kb` (1024 by default): the text names the file, its size and the limit
    assert _misses(f, reason, *has, hasnot=hasnot) == []


def test_sizes_that_could_not_be_read_fail_closed():
    """Catches: a file allowed because its size is unknown."""
    assert _misses(facts(commit(A("src/a.py"), sizes=core.Unread()), **CARDLESS), "commit-unreadable", "file sizes") == []


OWN = dict(junk=("*.swp",), data_patterns=("*.json.gz",), max_file_kb=1, **CARDLESS)  # the profile replaces all three
LIMIT_ONLY = dict(max_file_kb=0.5, **CARDLESS)  # the limit alone set: the junk and data defaults stay
OVERRIDES = [
    row(facts(commit(A("a.pyc")), **OWN), None, id="mw006_e18_default_junk_is_replaced"),
    row(facts(commit(A("d.csv")), **OWN), None, id="mw006_e18_default_data_is_replaced"),
    row(facts(commit(A("x.swp")), **OWN), "junk-file-staged", id="mw006_e18_own_junk"),
    row(facts(commit(A("d.json.gz")), **OWN), "data-file-staged", id="mw006_e18_own_data"),
    row(facts(commit(A("src/small.txt"), sizes={"src/small.txt": 900}), **OWN), None, id="mw006_e18_under_own_limit"),
    row(facts(commit(A("src/two.txt"), sizes={"src/two.txt": 2048}), **OWN), "file-too-large", id="mw006_e18_over_own_limit"),
    row(facts(commit(A("a.pyc")), **LIMIT_ONLY), "junk-file-staged", id="mw006_e18_limit_alone_keeps_default_junk"),
    row(facts(commit(A("d.csv")), **LIMIT_ONLY), "data-file-staged", id="mw006_e18_limit_alone_keeps_default_data"),
    row(facts(commit(A("src/one.txt"), sizes={"src/one.txt": 600}), **LIMIT_ONLY), "file-too-large",
        id="mw006_e18_limit_alone_applies"),
]


@pytest.mark.parametrize(CASE, OVERRIDES)
def test_the_profile_overrides_replace_the_defaults_each_alone(f, reason, has, hasnot):
    """Catches: a profile key that replaces another key's default, or is ignored (mw006_e18)"""
    # junk `*.swp` only: `a.pyc` passes, `x.swp` is junk; data `*.json.gz` only: `d.csv` passes; limit 1 KB
    assert _misses(f, reason, *has, hasnot=hasnot) == []


DELETIONS = [
    row(facts(commit(D("old/cache.pyc"), D("old/dump.csv"), D("old/big.bin"), sizes={}), **CARDLESS), None,
        id="mw006_e19_deleting_the_mess_is_allowed"),
    row(facts(commit(M("old/keep.csv")), **CARDLESS), "data-file-staged", id="mw006_e19_a_data_file_that_stays_is_refused"),
]


@pytest.mark.parametrize(CASE, DELETIONS)
def test_deleting_a_junk_data_or_big_file_is_allowed_and_changing_one_is_not(f, reason, has, hasnot):
    """Catches: a deletion of junk refused, or a changed data file allowed (mw006_e19)"""
    # removing the mess is the way out
    assert _misses(f, reason, *has, hasnot=hasnot) == []


# ---- MW-006 E20..E22, MW-033: the message -----------------------------------------------------------------------------

def _msg(message, **kw):
    return facts(commit(A("src/a.py"), message=message), **{"card_paths": frozenset(), **kw})


GOOD = ["CARD-001 add the thing", "add the thing\n\nCARD-001", "work (CARD-001): add the thing",
        "CARD-001 add the thing\n", "CARD-001 from a file\n", "#10536 CARD-001 add the thing",
        "CARD-001 #10536 add the thing", "#10536 (CARD-001) add"]
BAD = ["add the thing", "CARD-002 add the thing", "CARD-0011 add the thing", "card-001 add the thing",
       "XCARD-001 add the thing", "no card here\n", "no card\n", "#10536 add the thing",
       "#10536 CARD-0011 add the thing", "#10536 CARD-002 add the thing"]


@pytest.mark.parametrize("message", GOOD)
def test_a_message_that_names_the_open_card_passes(message):
    """Checks: the id as a whole id anywhere (any -m, a here-document, a message file's text) (mw006_e20, mw033 e1)"""
    assert _misses(_msg(message), None) == []


@pytest.mark.parametrize("message", BAD)
def test_a_message_that_does_not_name_the_open_card_is_refused(message):
    """Catches: a commit that does not name its card (mw006_e20, mw033 e1)"""
    # no id, another card's id, a longer number, a lower-case id
    assert _misses(_msg(message), "commit-message-card", "CARD-001", "-m") == []


def test_the_refusal_names_the_card_that_was_named_and_the_way_out():
    """Catches: a refusal that does not say how to go on (mw033 e3)"""
    # the text says to put the id anywhere in the first line, with an example
    assert _misses(_msg("CARD-002 add"), "commit-message-card", "the message names CARD-002, not the open card CARD-001",
                   'put the card id anywhere in the first line, for example -m "CARD-001 <what changed>"') == []


DD = r"(?<![A-Za-z0-9_-])DD-[0-9]{3,}(?![0-9A-Za-z_])"
PREFIX = [
    row(_msg("#10536 CARD-001 add the thing", card_id_pattern=DD), None, id="mw033_e2_the_open_cards_own_id_passes"),
    row(_msg("DD-007 add the thing", card_id_pattern=DD), "commit-message-card", "DD-007",
        id="mw033_e2_another_card_in_the_new_form_is_refused"),
    row(_msg("#10536 add the thing", card_id_pattern=DD), "commit-message-card", "no card", id="mw033_e2_no_id_is_refused"),
    row(_msg("#10536 CARD-0011 add the thing", card_id_pattern=DD), "commit-message-card",
        id="mw033_e2_a_longer_number_is_refused"),
]


@pytest.mark.parametrize(CASE, PREFIX)
def test_the_open_card_id_passes_whatever_the_prefix_is_now(f, reason, has, hasnot):
    """Catches: a card refused for the id it was made with (mw033 e2)"""
    # the profile prefix is now DD, the open card CARD-001 made before
    assert _misses(f, reason, *has, hasnot=hasnot) == []


def test_with_no_prefix_set_only_the_open_cards_own_id_counts():
    """Catches: another card's id accepted when the profile has no prefix."""
    assert _misses(_msg("CARD-002 add", card_id_pattern=None), "commit-message-card", "no card") == []


NO_OPEN = [
    row(no_card(commit(A("notes/n.md"), message="add the note"), exempt=(*EXEMPT, "notes/**")), None,
        id="mw006_e20_no_card_needs_no_id"),
    row(no_card(commit(A("src/a.py"), message="add the thing")), "file-not-in-card", id="mw006_e20_a_file_outside_is_rule_1"),
]


@pytest.mark.parametrize(CASE, NO_OPEN)
def test_a_session_with_no_open_card_has_none_to_name(f, reason, has, hasnot):
    """Catches: a message refused for naming a card nobody holds (mw006_e20)"""
    # no card held: the message needs no id (the always-allowed file passes); with a file outside, rule 1
    assert _misses(f, reason, *has, hasnot=hasnot) == []


SWITCH = [
    row(_msg("add the thing", message_card_on=False), None, id="mw006_e21_off_needs_no_id"),
    row(facts(commit(A("junk.pyc"), message="add the thing"), card_paths=frozenset(), message_card_on=False),
        "junk-file-staged", id="mw006_e21_off_still_refuses_junk"),
    row(_msg("add the thing", message_card_on=True), "commit-message-card", id="mw006_e21_on_needs_the_id"),
]


@pytest.mark.parametrize(CASE, SWITCH)
def test_the_switch_turns_the_message_rule_off_and_nothing_else(f, reason, has, hasnot):
    """Catches: a switch that turns off more than the message rule, or less (mw006_e21)"""
    # `message_card_on` false: no id needed; a junk file still refuses
    assert _misses(f, reason, *has, hasnot=hasnot) == []


NO_MESSAGE = ["git commit", "git commit -F missing.txt", "git commit -C HEAD", "git commit --amend", "git commit -F -"]


@pytest.mark.parametrize("command", NO_MESSAGE)
def test_an_unreadable_message_refuses_while_the_rule_is_on(command):
    """Catches: a commit allowed whose message the gate could not read (mw006_e22)"""
    # the reader found no message (None): `commit-unreadable`, naming `-m`
    assert _misses(facts(commit(A("src/a.py"), message=None), command=command, card_paths=frozenset()), "commit-unreadable",
                   "message", "-m") == []


@pytest.mark.parametrize("command", NO_MESSAGE)
def test_an_unreadable_message_passes_while_the_rule_is_off(command):
    """Checks: the nearest allow: the same unreadable message with the rule off (mw006_e22)"""
    assert _misses(facts(commit(A("src/a.py"), message=None), command=command, card_paths=frozenset(), message_card_on=False), None) == []


# every combination of the three facts of the message rule (T3): the card is open, the message names it, the rule is on;
# the expected verdict of each is written from the rule: a refusal only for an open card, the rule on, no id in the message
def _open(message, on):
    return facts(commit(A("notes/n.md"), message=message), card_paths=frozenset(), message_card_on=on)


def _no_card(message, on):
    return no_card(commit(A("notes/n.md"), message=message), exempt=(*EXEMPT, "notes/**"), message_card_on=on)


NAMED, UNNAMED = "CARD-001 add the thing", "add the thing"
EVERY_COMBINATION = [
    row(_open(NAMED, True), None, id="open_names_on"),
    row(_open(NAMED, False), None, id="open_names_off"),
    row(_open(UNNAMED, True), "commit-message-card", id="open_unnamed_on"),
    row(_open(UNNAMED, False), None, id="open_unnamed_off"),
    row(_no_card(NAMED, True), None, id="no_card_names_on"),
    row(_no_card(NAMED, False), None, id="no_card_names_off"),
    row(_no_card(UNNAMED, True), None, id="no_card_unnamed_on"),
    row(_no_card(UNNAMED, False), None, id="no_card_unnamed_off"),
]


@pytest.mark.parametrize(CASE, EVERY_COMBINATION)
def test_the_message_rule_in_every_combination_of_its_facts(f, reason, has, hasnot):
    """Catches: a refusal for a message that names the card, for a session with no open card, or with the rule off (mw006_e20, e21)"""
    # a refusal only when the card is open, the rule is on and the message does not name it
    assert _misses(f, reason, *has, hasnot=hasnot) == []


# ---- MW-034 E1..E3, MW-043 E2..E6: what the card's Paths say about what git takes ---------------------------------------

PATHS_INSIDE = [
    row(facts(commit(A("other/b.py"), A("src/a.py"))), "file-not-in-card", "other/b.py", hasnot=("src/a.py",),
        id="mw034_e1_a_staged_file_outside"),
    row(facts(commit(A("src/a.py"))), None, id="mw034_e1_a_staged_file_inside"),
]


@pytest.mark.parametrize(CASE, PATHS_INSIDE)
def test_a_staged_file_outside_the_paths_is_refused_and_one_inside_passes(f, reason, has, hasnot):
    """Checks: a staged file outside the Paths is refused and a staged file inside the Paths passes (mw034 e1)"""
    assert _misses(f, reason, *has, hasnot=hasnot) == []


SCRIPT = [f"src/gen{i}.py" for i in range(12)]
GENERATED = [
    row(facts(commit(*[A(rel) for rel in SCRIPT])), None, id="mw034_e2_twelve_files_staged"),
    row(facts(commit(W(SCRIPT[0]), paths=(SCRIPT[0],)), command="git commit -m 'CARD-001 x' -- src/gen0.py"), None,
        id="mw034_e2_one_named"),
]


@pytest.mark.parametrize(CASE, GENERATED)
def test_files_a_script_wrote_inside_the_paths_are_allowed(f, reason, has, hasnot):
    """Checks: twelve generated files inside the Paths; there is no `ride-in-file` rule (mw034 e2)"""
    # guards against: files refused for how they were written
    assert _misses(f, reason, *has, hasnot=hasnot) == []


STAGED_FOREIGN = (A("other/b.py"), A("src/a.py"))
EARLIER = [
    row(facts(commit(*STAGED_FOREIGN, include=True, paths=("src/a.py",)),
              command="git commit -i -m 'CARD-001 x' -- src/a.py"), "file-not-in-card", "other/b.py", id="include"),
    row(facts(commit(*STAGED_FOREIGN, all=True), command="git commit -a -m 'CARD-001 x'"), "file-not-in-card",
        "other/b.py", id="all"),
    row(facts(commit(*STAGED_FOREIGN), command="git commit --amend -m 'CARD-001 x'"), "file-not-in-card", "other/b.py",
        id="amend"),
    row(facts(commit(*STAGED_FOREIGN), command=COMMIT), "file-not-in-card", "other/b.py", id="plain"),
    row(facts(commit(W("src/a.py"), paths=("src/a.py",)), command="git commit -m 'CARD-001 x' -- src/a.py"), None,
        id="paths_takes_the_named_path_alone"),
]


@pytest.mark.parametrize(CASE, EARLIER)
def test_a_file_staged_earlier_outside_the_paths_is_refused_in_the_forms_that_take_the_staged_list(f, reason, has, hasnot):
    """Catches: a foreign staged file carried into a commit that takes the staged list (mw034 e3)"""
    # plain, `-i`, `-a`, `--amend` take the staged list; `-- <paths>` with its own path takes the named path alone
    assert _misses(f, reason, *has, hasnot=hasnot) == []


PLAIN = [
    row(facts(commit(A("other/b.py"), A("src/a.py"))), "file-not-in-card", "other/b.py", "git restore --staged other/b.py",
        hasnot=("src/a.py",), id="mw043_e2_foreign_staged_file"),
    row(facts(commit(A("src/a.py"))), None, id="mw043_e2_after_unstage"),
]


@pytest.mark.parametrize(CASE, PLAIN)
def test_a_plain_commit_takes_the_staged_list_and_names_the_way_out(f, reason, has, hasnot):
    """Catches: a plain commit with a foreign staged file allowed, or refused with no way out (mw043 e2)"""
    assert _misses(f, reason, *has, hasnot=hasnot) == []


INCLUDE = [
    row(facts(commit(W("src/a.py"), A("other/b.py"), include=True, paths=("src/a.py",)),
              command="git commit -i -m 'CARD-001 x' -- src/a.py"), "file-not-in-card", "other/b.py",
        hasnot=("src/a.py",), id="mw043_e3_short_flag"),
    row(facts(commit(W("src/a.py"), A("other/b.py"), include=True, paths=("src/a.py",)),
              command="git commit --include -m 'CARD-001 x' -- src/a.py"), "file-not-in-card", "other/b.py",
        hasnot=("src/a.py",), id="mw043_e3_long_flag"),
    row(facts(commit(W("src/a.py"), include=True, paths=("src/a.py",))), None, id="mw043_e3_nothing_foreign"),
]


@pytest.mark.parametrize(CASE, INCLUDE)
def test_an_include_commit_takes_the_staged_list_plus_the_named_paths(f, reason, has, hasnot):
    """Catches: an `-i` commit judged by the named paths alone (mw043 e3)"""
    # `-i` and `--include` alike
    assert _misses(f, reason, *has, hasnot=hasnot) == []


ALL = [
    row(facts(commit(W("other/c.py"), W("src/a.py"), all=True), command="git commit -a -m 'CARD-001 x'"),
        "file-not-in-card", "other/c.py", hasnot=("src/a.py",), id="mw043_e4_short_flag_tracked_change"),
    row(facts(commit(W("other/c.py"), W("src/a.py"), all=True), command="git commit --all -m 'CARD-001 x'"),
        "file-not-in-card", "other/c.py", hasnot=("src/a.py",), id="mw043_e4_long_flag_tracked_change"),
    row(facts(commit(W("src/a.py"), all=True), command="git commit -a -m 'CARD-001 x'"), None,
        id="mw043_e4_tracked_change_inside"),
    row(facts(commit(W("src/a.py"), A("other/b.py"), all=True)), "file-not-in-card", "other/b.py",
        id="mw043_e4_staged_file_outside"),
]


@pytest.mark.parametrize(CASE, ALL)
def test_an_all_commit_takes_the_staged_list_plus_every_modified_tracked_file(f, reason, has, hasnot):
    """Catches: an `-a` commit that carries a tracked change outside the Paths (mw043 e4)"""
    # `-a` and `--all` alike
    assert _misses(f, reason, *has, hasnot=hasnot) == []


AMEND = "git commit --amend -m 'CARD-001 x'"
AMENDS = [
    row(facts(commit(W("src/a.py"), paths=("src/a.py",)), command=AMEND + " -- src/a.py"), None,
        id="mw043_e5_with_an_inside_path"),
    row(facts(commit(A("other/b.py"), A("src/a.py")), command=AMEND), "file-not-in-card", "other/b.py",
        id="mw043_e5_plain_with_a_foreign_file_staged"),
    row(facts(commit(), command=AMEND), None, id="mw043_e5_plain_with_nothing_staged"),
]


@pytest.mark.parametrize(CASE, AMENDS)
def test_an_amend_follows_the_form_it_is_given_and_judges_nothing_else(f, reason, has, hasnot):
    """Catches: an amend judged by files its form does not take (mw043 e5)"""
    assert _misses(f, reason, *has, hasnot=hasnot) == []


def test_a_named_path_outside_the_card_is_refused_with_the_way_out_for_a_named_path():
    """Catches: a named path outside the card committed, or a way out that points to the staged list (mw043 e6)"""
    assert _misses(facts(commit(W("other/b.py", "A"), paths=("other/b.py",)), command=COMMIT + " -- other/b.py"),
                   "file-not-in-card", "other/b.py", "leave them out of the paths after `--`", hasnot=("src/a.py",)) == []


# ---- MW-021 E4..E6: rule cards and their tests ---------------------------------------------------------------------------

CARD_FILE, TEST_FILE = "rules/K01.md", "tests/rules/K01/test_K01.py"
RULES_PATHS = frozenset({"rules", "tests/rules", "notes"})
CARDS = {CARD_FILE: TEST_FILE}
ON_DISK = frozenset({TEST_FILE})


def _rules(*taken, **kw):
    kw.setdefault("rule_cards", CARDS)
    return facts(commit(*taken, **kw), card_paths=RULES_PATHS)


NEW_CARD = [
    row(_rules(A(CARD_FILE)), "rule-without-test", CARD_FILE, TEST_FILE, "does not exist", f"git add {TEST_FILE}",
        id="mw021_e4_card_alone"),
    row(_rules(A(CARD_FILE), A(TEST_FILE)), None, id="mw021_e4_card_and_its_test"),
]


@pytest.mark.parametrize(CASE, NEW_CARD)
def test_a_new_rule_card_with_no_test_file_is_refused_and_with_its_test_allowed(f, reason, has, hasnot):
    """Catches: a rule card committed without its test (mw021 e4)"""
    # the text names the card, the test path, says the file does not exist, names `git add`
    assert _misses(f, reason, *has, hasnot=hasnot) == []


CHANGED_CARD = [
    row(_rules(M(CARD_FILE), tests_on_disk=ON_DISK), "rule-without-test", "not staged", f"git add {TEST_FILE}",
        id="mw021_e5_card_alone"),
    row(_rules(M(CARD_FILE), M(TEST_FILE), tests_on_disk=ON_DISK), None, id="mw021_e5_card_and_its_test"),
]


@pytest.mark.parametrize(CASE, CHANGED_CARD)
def test_a_changed_card_needs_its_test_staged_too(f, reason, has, hasnot):
    """Catches: a changed rule card committed without its test (mw021 e5)"""
    # the test exists in the tree but is not staged: the text says `not staged`
    assert _misses(f, reason, *has, hasnot=hasnot) == []


NAMED_PATHS = [
    row(_rules(W(CARD_FILE), paths=(CARD_FILE,), tests_on_disk=ON_DISK), "rule-without-test", "name it after `--`",
        id="mw021_e5_card_named_alone"),
    row(_rules(W(CARD_FILE), W(TEST_FILE), paths=(CARD_FILE, TEST_FILE), tests_on_disk=ON_DISK), None,
        id="mw021_e5_card_and_test_named"),
]


@pytest.mark.parametrize(CASE, NAMED_PATHS)
def test_the_named_paths_form_is_read_too(f, reason, has, hasnot):
    """Catches: the rule skipped for the named-paths form (mw021 e5)"""
    # with `-- <paths>` the files taken are the named ones; the card alone is refused (and told to name the test after `--`), the card and its test pass
    assert _misses(f, reason, *has, hasnot=hasnot) == []


NOT_A_RULE_CARD_COMMIT = [
    row(_rules(M(TEST_FILE), tests_on_disk=ON_DISK), None, id="mw021_e6_a_test_changed_without_its_card"),
    row(_rules(D(CARD_FILE), tests_on_disk=ON_DISK), None, id="mw021_e6_a_deleted_card"),
    row(_rules(A("notes/K01.md"), A("rules/notes.md")), None, id="mw021_e6_files_that_are_no_rule_card"),
]


@pytest.mark.parametrize(CASE, NOT_A_RULE_CARD_COMMIT)
def test_what_a_rule_card_check_allows(f, reason, has, hasnot):
    """Checks: the nearest allows of the rule: a test changed without its card, a deleted card, files that are no rule card (the shell found no id or no glob match, so they are not in `rule_cards`) (mw021 e6)"""
    assert _misses(f, reason, *has, hasnot=hasnot) == []


def test_a_rule_card_check_that_is_off_refuses_nothing():
    """Checks: no `rule_cards` (the keys are not both set, or no `ids.rule_card` form): a card file commits as any other (mw021 e6)"""
    assert _misses(_rules(A(CARD_FILE), rule_cards={}), None) == []


# ---- MW-053: the orderer commits the folder of a card it ordered ----------------------------------------------------------

F2 = "mkway/cards/CARD-002-second"
FA = "mkway/cards/CARD-003-alien"
FM = "mkway/cards/CARD-004-mine"
REGISTER = "mkway/cards/REGISTER.md"
CARD1, ORDER1 = f"{FOLDER}/CARD.md", f"{FOLDER}/ORDER.md"
NOTES1 = f"{FOLDER}/notes/n.txt"
SENTENCE = "an orderer may commit only the folders of cards it ordered plus REGISTER.md"
ONE = core.Ordered("CARD-001", FOLDER, frozenset({"src", f"{FOLDER}/notes"}))
TWO = core.Ordered("CARD-002", F2, frozenset({"src/two"}))
ALIEN = core.Ordered("CARD-003", FA, frozenset())
ORDERED_MSG = "CARD-001 card and order"
UNREAD_HOLDERS = core.Unread("the session records could not be read, so the commit could not be checked; run it again")


def orderer(*commits, **kw):
    """A session that holds no card and ordered CARD-001 and CARD-002; CARD-001 is held by session `b1`."""
    base = dict(ordered=(ONE, TWO), holders={"CARD-001": "b1"})
    base.update(kw)
    return no_card(*commits, **base)


ORDERER_OWN = [
    row(orderer(commit(W(CARD1), W(REGISTER), message=ORDERED_MSG)), None, id="mw053_e1_card_md_and_register"),
    row(orderer(commit(W(CARD1), W(ORDER1), W(REGISTER), message=ORDERED_MSG)), None, id="mw053_e1_card_order_register"),
    row(orderer(commit(W(f"{F2}/CARD.md"), W(REGISTER), message="CARD-002 card and order")), None,
        id="mw053_e1_the_second_ordered_card"),
    row(orderer(commit(W(f"{F2}/CARD.md"), W(REGISTER), message=ORDERED_MSG)), "commit-message-card", "CARD-002",
        id="mw053_e1_a_message_that_names_no_card_of_the_files"),
]


@pytest.mark.parametrize(CASE, ORDERER_OWN)
def test_the_orderer_commits_card_md_order_md_and_the_register_without_holding_the_card(f, reason, has, hasnot):
    """Catches: a lead that cannot commit its own order, or one whose message names another card (mw053 e1)"""
    # `CARD.md`, `ORDER.md` and the register of a card it ordered, the message naming a card whose files go in
    assert _misses(f, reason, *has, hasnot=hasnot) == []


PLAIN_ORDERER = [
    row(orderer(commit(M(CARD1), M(ORDER1), M(REGISTER), message=ORDERED_MSG)), None, id="mw053_e2_staged_card_files"),
    row(orderer(commit(M(CARD1), M(ORDER1), M(REGISTER), M("src/a.py"), message=ORDERED_MSG)), "file-not-in-card",
        "src/a.py", SENTENCE, hasnot=(CARD1,), id="mw053_e2_a_foreign_staged_file"),
]


@pytest.mark.parametrize(CASE, PLAIN_ORDERER)
def test_the_plain_form_of_the_orderer_takes_the_staged_list(f, reason, has, hasnot):
    """Catches: a plain commit that carries a ride-in file (mw053 e2)"""
    # a foreign staged file beside the card files is refused, named, with the orderer sentence
    assert _misses(f, reason, *has, hasnot=hasnot) == []


INCLUDE_ORDERER = dict(include=True, paths=(CARD1,), message=ORDERED_MSG)
INCLUDE_ORD = [
    row(orderer(commit(W(CARD1), M(REGISTER), **INCLUDE_ORDERER)), None, id="mw053_e3_register_staged_card_named"),
    row(orderer(commit(W(CARD1), M(REGISTER), M("src/a.py"), **INCLUDE_ORDERER)), "file-not-in-card", "src/a.py",
        hasnot=(CARD1,), id="mw053_e3_a_foreign_staged_file"),
]


@pytest.mark.parametrize(CASE, INCLUDE_ORD)
def test_the_include_form_of_the_orderer_takes_the_staged_list_plus_the_named(f, reason, has, hasnot):
    """Catches: an `-i` commit of the orderer judged by the named paths alone (mw053 e3)"""
    assert _misses(f, reason, *has, hasnot=hasnot) == []


TWO_CARDS = (W(CARD1), W(f"{F2}/CARD.md"), W(REGISTER))


@pytest.mark.parametrize("message", ["CARD-001 card and order", "CARD-002 card and order"])
def test_two_ordered_cards_in_one_commit_are_allowed(message):
    """Checks: the files of two cards the session ordered and the register in one commit; the message names either (mw053 e4)"""
    # guards against: a rule that reads one card per commit
    assert _misses(orderer(commit(*TWO_CARDS, message=message)), None) == []


def test_the_register_alone_is_allowed_for_the_orderer():
    """Checks: no card id is needed in the message of a register-only commit (mw053 e5)"""
    assert _misses(orderer(commit(W(REGISTER), message="register")), None) == []


NOT_ORDERED = [
    row(no_card(commit(W(CARD1), W(REGISTER), message=ORDERED_MSG)), "file-not-in-card", CARD1, "holds no open card",
        hasnot=(SENTENCE,), id="mw053_e6_a_session_that_orders_no_card"),
    row(no_card(commit(W(f"{FA}/CARD.md"), W(CARD1), W(REGISTER), message="CARD-003 card and order"), ordered=(ALIEN,)),
        "file-not-in-card", CARD1, SENTENCE, hasnot=(f"{FA}/CARD.md",), id="mw053_e6_a_session_that_orders_another_card"),
]


@pytest.mark.parametrize(CASE, NOT_ORDERED)
def test_a_session_that_did_not_order_the_card_is_refused_as_today(f, reason, has, hasnot):
    """Catches: any session committing any card folder (mw053 e6)"""
    # no card ordered: refused, the files named, the old text; a session that orders another card: only the files of cards it did not order are named, with the orderer sentence
    assert _misses(f, reason, *has, hasnot=hasnot) == []


OWNER_ORDERED = [
    row(no_card(commit(W(f"{FM}/CARD.md"), W(REGISTER), message="CARD-004 card"), ordered=()), "file-not-in-card",
        f"{FM}/CARD.md", hasnot=(SENTENCE,), id="mw053_e7_a_session_with_no_ordered_card"),
    row(orderer(commit(W(f"{FM}/CARD.md"), W(REGISTER), message="CARD-001 card")), "file-not-in-card", f"{FM}/CARD.md",
        SENTENCE, id="mw053_e7_a_card_the_owner_ordered"),
]


@pytest.mark.parametrize(CASE, OWNER_ORDERED)
def test_a_card_ordered_by_the_owner_is_no_ordered_card_of_a_session(f, reason, has, hasnot):
    """Catches: an owner-ordered card committed by a lead (mw053 e7 (the core half))"""
    # a card the owner ordered, or a call with no session id, is not in `ordered` (the shell leaves it out), so its folder is refused
    assert _misses(f, reason, *has, hasnot=hasnot) == []


def test_a_mixed_commit_is_refused_naming_the_files_that_do_not_belong():
    """Catches: a rider carried in on the orderer's allowance (mw053 e8)"""
    # its own card folder, a file outside the cards and the folder of another's card: the last two named
    taken = (W(CARD1), W("src/a.py"), W(f"{FA}/CARD.md"), W(REGISTER))
    assert _misses(orderer(commit(*taken, message=ORDERED_MSG)), "file-not-in-card", "src/a.py", f"{FA}/CARD.md", SENTENCE,
                   hasnot=(CARD1,)) == []


HOLDER = [
    row(facts(commit(W("src/a.py"), paths=("src/a.py",))), None, id="mw053_e9_a_file_inside_the_paths"),
    row(facts(commit(W(f"{F2}/CARD.md"), paths=(f"{F2}/CARD.md",))), "file-not-in-card", "not in the Paths of CARD-001",
        hasnot=(SENTENCE,), id="mw053_e9_a_file_outside_the_paths"),
]


@pytest.mark.parametrize(CASE, HOLDER)
def test_a_holder_keeps_its_rules(f, reason, has, hasnot):
    """Catches: a change to the holder's rules (mw053 e9)"""
    # the holder commits inside its Paths; a file outside is refused with the old text (no orderer sentence)
    assert _misses(f, reason, *has, hasnot=hasnot) == []


HOLDERS_FILES = [
    row(orderer(commit(W(NOTES1), W(CARD1), W(REGISTER), message=ORDERED_MSG)), "file-not-in-card", NOTES1,
        "held by session b1", SENTENCE, hasnot=(CARD1,), id="mw053_e10_a_file_the_paths_cover_names_the_holder"),
    row(orderer(commit(W(NOTES1), W(CARD1), message=ORDERED_MSG), holders={}), "file-not-in-card",
        "held by no session now", id="mw053_e10_a_card_nobody_holds"),
    row(orderer(commit(W(CARD1), W(ORDER1), W(REGISTER), message=ORDERED_MSG)), None,
        id="mw053_e10_card_md_and_order_md_are_the_orderers"),
]


@pytest.mark.parametrize(CASE, HOLDERS_FILES)
def test_a_file_under_the_holders_paths_is_the_holders_and_names_the_holder(f, reason, has, hasnot):
    """Catches: an orderer that commits the holder's work (mw053 e10)"""
    # a file the card's Paths cover is the holder's; `CARD.md` and `ORDER.md` beside it are the orderer's
    assert _misses(f, reason, *has, hasnot=hasnot) == []


def test_a_refusal_for_the_holders_file_starts_with_the_file():
    """Catches: a refusal that names the files the orderer may commit (mw053 e10)"""
    # the text leads with the holder's file, not the orderer's own files
    v = check(orderer(commit(W(NOTES1), W(CARD1), W(REGISTER), message=ORDERED_MSG)), "file-not-in-card")
    assert v.text.startswith(NOTES1)


HOLDERS_UNREAD = [
    row(orderer(commit(W(REGISTER), message="register"), holders=UNREAD_HOLDERS), None, id="no_file_outside_needs_no_holder"),
    row(orderer(commit(W(CARD1), message=ORDERED_MSG), holders=UNREAD_HOLDERS), "commit-unreadable", "session records",
        id="a_file_outside_needs_the_holders"),
    row(orderer(commit(W(CARD1), W("src/a.py"), message=ORDERED_MSG), holders=UNREAD_HOLDERS), "commit-unreadable",
        "session records", id="a_foreign_file_needs_the_holders"),
    row(orderer(commit(W(CARD1), message=ORDERED_MSG), holders=core.Unread()), "commit-unreadable", "run it again",
        id="the_cores_own_text"),
]


@pytest.mark.parametrize(CASE, HOLDERS_UNREAD)
def test_holders_that_could_not_be_read_fail_closed_only_when_they_are_needed(f, reason, has, hasnot):
    """Catches: an orderer's commit allowed without knowing who holds the file, or refused for a read it does not need (mw053)"""
    # the holders are needed by an orderer's commit with a file outside the held card's Paths; unread, that commit is `commit-unreadable`; a commit with no file outside (the register alone is exempt) is not asked
    assert _misses(f, reason, *has, hasnot=hasnot) == []


OTHER_CHECKS = [
    row(orderer(commit(A(f"{F2}/x.pyc"), message="CARD-002 card and order")), "junk-file-staged", id="junk"),
    row(orderer(commit(A(f"{F2}/d.csv"), message="CARD-002 card and order")), "data-file-staged", id="data"),
    row(orderer(commit(W(f"{F2}/CARD.md"), W(REGISTER), message="CARD-999 card and order")), "commit-message-card",
        "CARD-002", id="a_message_that_names_no_ordered_card"),
]


@pytest.mark.parametrize(CASE, OTHER_CHECKS)
def test_the_other_checks_still_run_on_the_orderer_files(f, reason, has, hasnot):
    """Catches: an allowance that skips the content and message checks (mw053 e11)"""
    # junk, a data file and a message that names no ordered card are refused, each with its own reason
    assert _misses(f, reason, *has, hasnot=hasnot) == []


# ---- MW-058: a message-only amend takes no files --------------------------------------------------------------------------

def parsed(command, *taken, **kw):
    """The commit record the reader would make of `command` (the real parser: it is pure), with the files `taken` that
    git was asked about."""
    (c,) = helpers.commit_cmd(command)
    kw.setdefault("message", "CARD-001 reworded")
    return commit(*taken, paths=tuple(c.paths), all=c.all, include=c.include, amend=c.amend, only=c.only, **kw)


MESSAGE_ONLY = [  # (command, is it a message-only amend: the tree does not change), written from the card row of MW-058
    ("git commit --amend --only -m x", True), ("git commit --amend -o -m x", True), ("git commit --amend -om x", True),
    ("git commit -o --amend -m x", True), ("git commit --amend -m x --only", True),
    ("git commit --amend -m x -o", True), ("git commit -m x --amend --only", True),
    ("git commit --amend -m x", False),  # takes the index
    ("git commit --amend --only -m x -- b.py", False),  # takes the named path
    ("git commit --amend -o -m x b.py", False), ("git commit --amend -a -m x", False),
    ("git commit --amend -o -a -m x", False),  # a form git refuses: the wider reading stays
    ("git commit --amend -i -m x", False), ("git commit --amend -i -m x -- b.py", False),
    ("git commit --only -m x", False),  # not an amend: git refuses `--only` with no paths, the gate reads the index
]


@pytest.mark.parametrize("command, expected", MESSAGE_ONLY, ids=[m[0] for m in MESSAGE_ONLY])
def test_a_message_only_amend_takes_no_files(command, expected):
    """Checks: `--amend` with `--only` or `-o` and no paths (also in the group `-om`) rewrites the message and takes nothing from the index (mw058 e1, mw060 e14)"""
    # guards against: a message fix judged by an index it does not read
    (c,) = helpers.commit_cmd(command)
    with no_io():
        assert core.message_only_amend(c) is expected


@pytest.mark.parametrize("command", [m[0] for m in MESSAGE_ONLY if m[1]])
def test_the_files_the_shell_read_for_a_message_only_amend_are_not_judged(command):
    """Checks: whatever the shell read (a foreign file staged), a message-only amend takes none: a session with no card is allowed it (mw058 e1)"""
    # guards against: the false refusal of a message fix for files it does not take
    assert _misses(no_card(parsed(command, A("other/b.py"), A("src/a.py"), ignored=core.Unread(), sizes=core.Unread())), None) == []


TAKING_AMENDS = [
    row(no_card(parsed("git commit --amend --only -m x -- src/a.py", W("src/a.py", "A"))), "file-not-in-card", "src/a.py",
        id="mw058_e1_with_paths_the_named_path"),
    row(no_card(parsed("git commit --amend -m x", A("other/b.py"), A("src/a.py"))), "file-not-in-card", "other/b.py",
        "src/a.py", id="mw058_e1_amend_alone_the_staged_list"),
    row(no_card(parsed("git commit --amend -a -m x", W("other/c.py"), A("src/a.py"))), "file-not-in-card", "other/c.py",
        "src/a.py", id="mw058_e1_amend_all_the_tracked_changes"),
]


@pytest.mark.parametrize(CASE, TAKING_AMENDS)
def test_the_forms_that_take_files_are_judged_by_them(f, reason, has, hasnot):
    """Catches: an amend that takes files and is not judged (mw058 e1)"""
    # with paths the named paths alone; `--amend` alone the staged list; `-a` and `-i` as without `--amend`
    assert _misses(f, reason, *has, hasnot=hasnot) == []


STAGED_BOTH = (A("other/b.py"), A("src/a.py"))
AMEND_MESSAGES = [
    row(facts(parsed("git commit --amend --only -m x", *STAGED_BOTH)), None, id="mw058_e3_long_flag_names_the_card"),
    row(facts(parsed("git commit --amend -om x", *STAGED_BOTH)), None, id="mw058_e3_group_flag_names_the_card"),
    row(facts(parsed("git commit --amend --only -m x", *STAGED_BOTH, message="no id here")), "commit-message-card",
        id="mw058_e3_a_message_that_names_no_card"),
    row(facts(parsed("git commit --amend --only -m x -- other/b.py", W("other/b.py", "A"))), "file-not-in-card",
        "other/b.py", id="mw058_e3_a_named_path_outside_the_card"),
]


@pytest.mark.parametrize(CASE, AMEND_MESSAGES)
def test_the_message_checks_still_run_on_a_message_only_amend(f, reason, has, hasnot):
    """Catches: an amend that skips the checks of the new message (mw058 e3)"""
    # the card holder is allowed a message-only amend with other files staged when the new message names the card, refused `commit-message-card` when it does not; a named path outside the card is still refused
    assert _misses(f, reason, *has, hasnot=hasnot) == []


# ---- MW-060: the one table of what a commit takes ---------------------------------------------------------------------------

STAGED_LIST = [("M", "a.py"), ("A", "new3.py")]
COMBINE = [  # (command, named: git's list for the named paths or for -a, staged list) -> [(status, path, source)]
    ("git commit -m x", [], STAGED_LIST, [("M", "a.py", "index"), ("A", "new3.py", "index")]),
    ("git commit -m x --amend", [], STAGED_LIST, [("M", "a.py", "index"), ("A", "new3.py", "index")]),
    ("git commit -m x -a", [("M", "a.py"), ("M", "b.py"), ("A", "new3.py")], STAGED_LIST,
     [("M", "a.py", "work"), ("M", "b.py", "work"), ("A", "new3.py", "work")]),
    ("git commit -m x -- b.py", [("M", "b.py")], STAGED_LIST, [("M", "b.py", "work")]),
    ("git commit -m x -o b.py", [("M", "b.py")], STAGED_LIST, [("M", "b.py", "work")]),
    ("git commit -m x --only b.py", [("M", "b.py")], STAGED_LIST, [("M", "b.py", "work")]),
    ("git commit -m x -i -- b.py", [("M", "b.py")], STAGED_LIST,
     [("M", "b.py", "work"), ("M", "a.py", "index"), ("A", "new3.py", "index")]),
    ("git commit -m x --include b.py a.py", [("M", "b.py"), ("M", "a.py")], STAGED_LIST,
     [("M", "b.py", "work"), ("M", "a.py", "work"), ("A", "new3.py", "index")]),
]


@pytest.mark.parametrize("command, named, staged, expected", COMBINE, ids=[c[0] for c in COMBINE])
def test_the_reader_combines_the_lists_as_git_takes_them(command, named, staged, expected):
    """Checks: `-- paths`, `-o`, `--only` take the named paths alone from the working tree; `-i` the staged list plus the named paths; a plain commit and `--amend` the staged list; `-a` the staged list plus every modified tracked file (mw060 e1, e2, e3)"""
    # guards against: a staged file of another card riding into a `--` commit, or a named file left out
    (c,) = helpers.commit_cmd(command)
    with no_io():
        assert core.combine(c, named, staged) == expected


# ---- the guard of this file ---------------------------------------------------------------------------------------------------

GUARDED = [pytest.param(lambda: open(__file__), id="open"),
           pytest.param(lambda: pathlib.Path(__file__).read_text(), id="read_text"),
           pytest.param(lambda: time.time(), id="clock")]


@pytest.mark.parametrize("access", GUARDED)
def test_the_guard_fails_on_disk_access(access):
    """Catches: a guard that guards nothing, so a core that read a file or the clock could pass every row"""
    # The guard of this file works: a read or a clock call inside it raises
    with no_io():
        with pytest.raises(AssertionError):
            access()


def stat_under_the_guard():
    with no_io():
        os.stat(".")


def test_a_coverage_frame_below_the_test_does_not_pass_a_call_through():
    """Catches: a coverage frame below the test turns the guard off."""
    namespace = {"__name__": "coverage.fake"}
    exec(compile("def caller(function):\n    function()\n", "fake_coverage.py", "exec"), namespace)
    with pytest.raises(AssertionError):
        namespace["caller"](stat_under_the_guard)
