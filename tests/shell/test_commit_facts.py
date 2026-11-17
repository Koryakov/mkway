"""Card MW-052: the fact reader of the commit gate (`gate_commit.read_facts`) on prepared real repositories: a plain one,
a linked worktree and a sparse checkout, all built once per session with the same staged and modified files. The
reader's answers are the `Facts` the pure core decides on; these tests prove they are what git says. One test id is one
case; the expected values are written from the card rows and from what real git commits, not from the reader. Each test
stays under 20 s (`tests/shell/conftest.py`). Synthetic task roots only."""
import json
import re
import shutil
import subprocess
import types

import pytest

from _commit_fixture import git, make_task, save, stage, work
from _engine import gate_call, jsonl, write_profile
import core
import gate
import gate_commit
import register
import runner

CARD_COMMIT = "git commit -m 'CARD-001 x'"
IN_TREE = ("docs/d.md", "old/gone.txt", "src/m.py", "other/c.py")
DEFAULT_JUNK = ["__pycache__/", "*.pyc", ".pytest_cache/", ".pytest_tmp/", "*.log", "*.tmp", "*.orig", "*.rej",
                ".DS_Store", "Thumbs.db"]
DEFAULT_DATA = ["*.csv", "*.tsv", "*.xlsx", "*.xls", "*.parquet", "*.db", "*.sqlite", "*.sqlite3", "*.bak", "*.dump"]


def _prepare(root, docs=True):
    """The same state in every variant: committed src/m.py, other/c.py, old/gone.txt (and docs/d.md); then staged
    additions src/a.py and other/b.py, a staged deletion of old/gone.txt, a staged change of docs/d.md, and unstaged
    changes of src/m.py and other/c.py."""
    for rel in IN_TREE:
        if docs or rel != "docs/d.md":
            save(root, rel, "old\n")


def _dirty(root, docs=True):
    work(root, "src/a.py")
    work(root, "other/b.py")
    stage(root, "src/a.py", "other/b.py")
    git(root, "rm", "-q", "--", "old/gone.txt")
    if docs:
        work(root, "docs/d.md", "staged change\n")
        stage(root, "docs/d.md")
    work(root, "src/m.py", "unstaged change\n")
    work(root, "other/c.py", "unstaged change\n")


@pytest.fixture(scope="session", params=["plain", "linked", "sparse"])
def variant(request, tmp_path_factory):
    """(kind, task root) of a prepared repository; read-only for the tests that use it."""
    kind = request.param
    base = tmp_path_factory.mktemp(f"facts-{kind}")
    root = make_task(base, name="task")
    if kind == "sparse":
        _prepare(root)
        git(root, "sparse-checkout", "set", "--cone", "mkway", "src", "other", "old", "lib")
        assert not (root / "docs").exists()  # the folder is out of the checkout
        _dirty(root, docs=False)
        return kind, root
    _prepare(root)
    if kind == "linked":
        linked = base / "linked"
        git(root, "worktree", "add", "-q", "-b", "linked", str(linked))
        for sub in ("state", "locks"):  # the session's own hold lives in the ignored folders
            shutil.copytree(root / "mkway" / sub, linked / "mkway" / sub, dirs_exist_ok=True)
        # a checkout may rewrite line endings (autocrlf); the register must stay the bytes its seal was made from
        shutil.copyfile(root / "mkway" / "cards" / "REGISTER.md", linked / "mkway" / "cards" / "REGISTER.md")
        root = linked
    _dirty(root)
    return kind, root


def read(root, command, *, session="s1", tool="Bash", **kw):
    return gate_call(gate_commit.read_facts, root, tool=tool, tool_input={"command": command}, session=session,
                     gate="commit_files", **kw)


def rows(facts):
    return list(facts.commits[0].taken)


PLAIN = [("M", "docs/d.md", "index"), ("D", "old/gone.txt", "index"), ("A", "other/b.py", "index"),
         ("A", "src/a.py", "index")]
ALL = [("M", "docs/d.md", "work"), ("D", "old/gone.txt", "work"), ("A", "other/b.py", "work"),
       ("M", "other/c.py", "work"), ("A", "src/a.py", "work"), ("M", "src/m.py", "work")]
FORMS = [
    pytest.param(CARD_COMMIT, PLAIN, id="plain_takes_the_staged_list"),
    pytest.param("git commit --amend -m 'CARD-001 x'", PLAIN, id="amend_follows_the_same_rule"),
    pytest.param(CARD_COMMIT + " -- src/m.py", [("M", "src/m.py", "work")], id="paths_take_the_named_alone"),
    pytest.param(CARD_COMMIT + " -- src/a.py", [("A", "src/a.py", "work")], id="paths_name_a_staged_file"),
    pytest.param(CARD_COMMIT + " -- other/c.py src/m.py", [("M", "other/c.py", "work"), ("M", "src/m.py", "work")],
                 id="several_named_paths"),
    pytest.param("git commit -i -m 'CARD-001 x' -- src/m.py", [("M", "src/m.py", "work")] + PLAIN,
                 id="include_takes_the_staged_list_plus_the_named"),
    pytest.param("git commit -a -m 'CARD-001 x'", ALL, id="all_takes_every_tracked_change"),
]


@pytest.mark.parametrize("command, expected", FORMS)
def test_the_taken_list_of_each_form_on_each_kind_of_repository(variant, command, expected):
    """mw043 e1..e5 (the reading half): each form's list as git takes it, with its source. In the sparse checkout the
    folder that is out of the checkout is no deletion: its file is in none of the lists.
    Catches: a list that holds a file git would not commit, or lacks one it would."""
    kind, root = variant
    if kind == "sparse":
        expected = [row for row in expected if row[1] != "docs/d.md"]
    assert rows(read(root, command)) == expected


def test_a_commit_in_a_folder_the_gate_cannot_read_is_flagged_and_reads_nothing(variant, monkeypatch):
    """mw006_e13: a `cd` to a variable: the commit record says so and no git read is made for it.
    Catches: a git read in a folder nobody can name, or a commit read as if it ran in the root."""
    _kind, root = variant

    def forbidden(*_a, **_k):
        raise AssertionError("git was read for a commit whose folder is unreadable")
    monkeypatch.setattr(runner, "git", forbidden)
    commit = read(root, "cd $WHERE && " + CARD_COMMIT).commits[0]
    assert commit.folder_unreadable and commit.taken == ()


CARD_FACTS = [
    pytest.param("s1", ("CARD-001", True, "open", None, frozenset({"src", "lib/a.py"}), "mkway/cards/CARD-001-first"),
                 id="the_session_that_holds_the_card"),
    pytest.param("s2", (None, False, None, None, frozenset(), None), id="a_session_that_holds_none"),
]


@pytest.mark.parametrize("session, expected", CARD_FACTS)
def test_the_card_the_session_holds_and_the_files_no_rule_applies_to(variant, session, expected):
    """mw006_e7, e8: the facts of the held card: its id, status, parsed Paths and folder; a session that holds none has no
    card. Catches: a card read for the wrong session, or Paths read unparsed."""
    _kind, root = variant
    f = read(root, CARD_COMMIT, session=session)
    assert (f.card_id, f.card_found, f.card_status, f.register_problem, f.card_paths, f.card_folder) == expected


@pytest.mark.parametrize("entry", ["mkway/cards/REGISTER.md", "mkway/ledger"])
def test_the_files_no_card_rule_applies_to_are_facts(variant, entry):
    """mw006_e8: the register and the ledger folder are exempt entries of the facts.
    Catches: a register commit refused because the shell left its entry out."""
    _kind, root = variant
    assert entry in read(root, CARD_COMMIT).exempt


COMMAND_FACTS = [
    pytest.param("Read", {"command": "git commit"}, "git commit", "bash", id="a_tool_that_is_no_shell"),
    pytest.param("PowerShell", {"command": "git status"}, "git status", "powershell", id="powershell"),
    pytest.param("Bash", None, "", "bash", id="no_tool_input"),
]


@pytest.mark.parametrize("tool, tool_input, command, shell", COMMAND_FACTS)
def test_the_commands_text_and_the_tool_are_facts(tool, tool_input, command, shell):
    """The event as the dispatcher gives it: tool name, command text, shell kind (no root is needed to build them).
    Catches: a PowerShell command read by the Bash reader, or a missing input that raises."""
    f = gate_commit.facts_of_event(tool, tool_input, {"vcs": "git"})
    assert (f.tool_name, f.command, f.shell, f.commits) == (tool, command, shell, ())


# ---- reads that need their own repository: ignore rules, sizes, messages, switches ------------------------------------------

@pytest.fixture(scope="session")
def lab(tmp_path_factory):
    """One task root with an ignore file, an already committed ignored file, and the files the tests below stage."""
    root = make_task(tmp_path_factory.mktemp("facts-lab"), card_paths="", name="lab")
    save(root, ".gitignore", "secret_notes/\n*.keep\n")
    save(root, "secret_notes/old.txt", "old\n")
    work(root, "secret_notes/old.txt", "changed\n")
    stage(root, "secret_notes/old.txt")  # changed, not added: never a new force-add
    for rel in ("secret_notes/new.txt", "notes/today.keep", "notes/today.md"):
        work(root, rel)
    stage(root, "secret_notes/new.txt", "notes/today.keep", "notes/today.md")
    work(root, "src/big.txt", "a" * (1100 * 1024))
    stage(root, "src/big.txt")
    (root / "src" / "big.txt").write_bytes(b"small\n")  # the staged blob is big, the working file is six bytes
    work(root, "src/just_under.txt", "a" * (1000 * 1024))
    stage(root, "src/just_under.txt")
    work(root, "msg_ok.txt", "CARD-001 from a file\n")
    return root


def test_the_ignore_answer_covers_the_added_paths_only(lab):
    """mw006_e15: git's ignore rules answer for each ADDED path, tracked or not; a changed file that was committed
    before is not asked about. Catches: a changed file reported as a force-added ignored one."""
    commit = read(lab, CARD_COMMIT).commits[0]
    assert commit.ignored == frozenset({"secret_notes/new.txt", "notes/today.keep"})


SIZES = [
    pytest.param(CARD_COMMIT, {"src/big.txt": 1100 * 1024, "src/just_under.txt": 1000 * 1024}, id="the_staged_blob"),
    pytest.param(CARD_COMMIT + " -- src/big.txt", {"src/big.txt": len("small\n")}, id="the_working_file"),
]


@pytest.mark.parametrize("command, expected", SIZES)
def test_the_size_is_that_of_the_staged_blob_or_of_the_working_file(lab, command, expected):
    """mw006_e17: the staged blob for a commit of the index, the working file for `-- <paths>` (the file holds six bytes).
    Catches: a big staged blob passed because the small working file was measured."""
    sizes = read(lab, command).commits[0].sizes
    assert {rel: sizes[rel] for rel in expected} == expected


def test_a_deleted_file_has_no_size(variant):
    """mw006_e19: the deletion of old/gone.txt is taken but has no size.
    Catches: a deletion refused as a file over the limit."""
    _kind, root = variant
    commit = read(root, CARD_COMMIT).commits[0]
    assert ("D", "old/gone.txt", "index") in commit.taken and "old/gone.txt" not in commit.sizes


@pytest.mark.parametrize("command, message", [
    ("git commit -m 'CARD-001 add the thing'", "CARD-001 add the thing"),
    ("git commit -m 'add the thing' -m 'CARD-001'", "add the thing\n\nCARD-001"),
    ("git commit -F msg_ok.txt", "CARD-001 from a file\n"),
    ("git commit -F - <<'EOF'\nCARD-001 add the thing\nEOF", "CARD-001 add the thing"),
    ("git commit -F missing.txt", None), ("git commit", None), ("git commit -C HEAD", None),
    ("git commit --amend", None), ("git commit -F -", None)],
    ids=["one_m", "two_m", "message_file", "here_document", "missing_file", "no_message", "reuse", "amend_alone",
         "stdin_without_text"])
def test_the_message_is_read_as_text_or_as_none(lab, command, message):
    """mw006_e20, e22: any `-m`, a here-document, a message file that exists give text; the rest give None.
    Catches: a message the gate could not read taken for an empty one."""
    assert read(lab, command).commits[0].message == message


def test_the_flags_of_the_commit_are_facts(lab):
    """mw043: `-a`/`--all`, `-i`/`--include`, `--amend` and the named paths as the reader parsed them."""
    c = read(lab, "git commit -a -i --amend -m x -- p q").commits[0]
    assert (c.all, c.include, c.amend, c.paths) == (True, True, True, ("p", "q"))


def test_two_commits_in_one_command_are_two_records(lab):
    """Catches: the second commit of a command left unjudged."""
    f = read(lab, CARD_COMMIT + " ; " + CARD_COMMIT)
    assert len(f.commits) == 2


# ---- the profile -------------------------------------------------------------------------------------------------------

SETTINGS = [
    pytest.param({}, (DEFAULT_JUNK, DEFAULT_DATA, 1024), id="a_missing_value_takes_its_default"),
    pytest.param({"commit": {"junk": ["*.swp"], "data_patterns": ["*.json.gz"], "max_file_kb": 1}},
                 (["*.swp"], ["*.json.gz"], 1), id="each_key_overrides"),
    pytest.param({"commit": {"max_file_kb": 0.5}}, (DEFAULT_JUNK, DEFAULT_DATA, 0.5), id="the_limit_alone"),
    pytest.param({"commit": {"junk": [], "data_patterns": [1], "max_file_kb": -3}}, (DEFAULT_JUNK, DEFAULT_DATA, 1024),
                 id="an_unusable_value_takes_its_default"),
]


@pytest.mark.parametrize("profile, expected", SETTINGS)
def test_the_profile_settings_default_and_override_each_alone(profile, expected):
    """mw006_e18: a missing or unusable value takes its default; each key replaces its own default alone.
    Catches: a bad profile key that breaks the gate, or one key that replaces another's default."""
    s = gate_commit.settings(profile)
    assert (s["junk"], s["data_patterns"], s["max_file_kb"]) == expected


def test_the_facts_carry_the_profile_values(tmp_path):
    """mw006_e18, e21 and mw033 e2: the settings, the message switch and the card id form reach the facts.
    Catches: a profile switch that the core never sees."""
    root = make_task(tmp_path, card_paths="", name="own", commit={"junk": ["*.swp"], "max_file_kb": 1},
                     gates={"commit_files": {"message_card": {"on": False}}})
    path = root / "mkway" / "profile.json"  # the prefix changes after the card was made, as MW-033 E2
    profile = json.loads(path.read_text(encoding="utf-8"))
    write_profile(root, dict(profile, ids={"card_prefix": "DD"}))
    f = read(root, CARD_COMMIT)
    assert (f.junk, list(f.data_patterns), f.max_file_kb, f.message_card_on) == (("*.swp",), DEFAULT_DATA, 1, False)
    assert f.card_id_pattern and "DD" in f.card_id_pattern


def test_the_facts_of_a_profile_with_no_keys_are_the_defaults(tmp_path):
    """mw006_e18, e21: no `commit` keys, no switch: the defaults, the message rule on, the `CARD` prefix.
    Catches: a default that is not applied when the profile is silent."""
    f = read(make_task(tmp_path, card_paths="", name="plain"), CARD_COMMIT)
    assert (list(f.junk), list(f.data_patterns), f.max_file_kb, f.message_card_on) == (DEFAULT_JUNK, DEFAULT_DATA, 1024, True)
    assert f.card_id_pattern and "CARD" in f.card_id_pattern


RULES = {"cards": ["rules/*.md"], "test_for": "tests/rules/{id}/test_{id}.py"}
IDS = {"card_prefix": "CARD", "rule_card": "^K[0-9]{2}$"}


def _rules_root(tmp_path, name, **over):
    root = make_task(tmp_path, card_paths="`rules/`, `tests/rules/`", name=name, **{"rules": RULES, "ids": IDS, **over})
    save(root, "tests/rules/K02/test_K02.py")
    work(root, "rules/K01.md")
    work(root, "rules/K02.md")
    work(root, "rules/notes.md")
    work(root, "notes/K01.md")
    stage(root, "rules/K01.md", "rules/K02.md", "rules/notes.md", "notes/K01.md")
    return root


def test_rule_cards_and_their_tests_are_read_from_the_profile(tmp_path):
    """mw021 e4..e6: a taken path that is a rule card maps to its test path; the test that exists on disk is named.
    Catches: a rule card with no test that the core cannot see."""
    c = read(_rules_root(tmp_path, "rules"), CARD_COMMIT).commits[0]
    assert dict(c.rule_cards) == {"rules/K01.md": "tests/rules/K01/test_K01.py",
                                  "rules/K02.md": "tests/rules/K02/test_K02.py"}
    assert c.tests_on_disk == frozenset({"tests/rules/K02/test_K02.py"})


RULES_OFF = [pytest.param({"rules": {}}, id="no_rules_keys"),
             pytest.param({"rules": {"cards": RULES["cards"]}}, id="cards_only"),
             pytest.param({"rules": {"test_for": RULES["test_for"]}}, id="test_only"),
             pytest.param({"ids": {"card_prefix": "CARD"}}, id="no_id_form")]


@pytest.mark.parametrize("over", RULES_OFF)
def test_the_rule_card_check_is_off_without_both_keys_and_the_id_form(tmp_path, over):
    """mw021 e6: with the keys not both set, or no `ids.rule_card` form, the check is off (no mapping).
    Catches: a card file refused as a rule card when the check is not configured."""
    assert dict(read(_rules_root(tmp_path, "off", **over), CARD_COMMIT).commits[0].rule_cards) == {}


def test_a_card_that_is_not_open_is_a_fact(tmp_path):
    """mw006_e8: the status of the held card as the register says; its Paths as written (the core reads them only if open).
    Catches: a card the owner did not open that the core reads as open."""
    root = make_task(tmp_path, name="reg")
    profile = json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))
    register.set_status(root, profile, "CARD-001", "waiting")
    f = read(root, CARD_COMMIT)
    assert (f.card_found, f.card_status, f.register_problem, f.card_paths) == (
        True, "waiting", None, frozenset({"src", "lib/a.py"}))


def test_a_tampered_register_is_a_fact_with_the_owners_way_out(tmp_path):
    """mw006_e13: a register changed outside the engine is a `register_problem` with the owner's way out.
    Catches: a commit judged by a register nobody can trust."""
    root = make_task(tmp_path, name="seal")
    reg = root / "mkway" / "cards" / "REGISTER.md"
    reg.write_bytes(reg.read_bytes() + b"\n")
    f = read(root, CARD_COMMIT)
    assert isinstance(f.register_problem, str) and f.register_problem and "card resync" in f.owner_fix



# ---- a read that fails is a fact, not an exception ----------------------------------------------------------------------

def test_a_git_read_that_times_out_is_an_unread_fact_with_the_way_out(lab, monkeypatch):
    """mw006_e13: git did not answer: the commit's `taken` is an Unread whose text says to run it again.
    Catches: a timeout that escapes as an exception, or a commit allowed after it."""
    def boom(*_a, **_k):
        raise runner.TimeoutExpired("git", 10)
    monkeypatch.setattr(runner, "git", boom)
    taken = read(lab, CARD_COMMIT).commits[0].taken
    assert isinstance(taken, core.Unread) and "10 s" in taken.text and "run it again" in taken.text


def test_a_git_read_that_answers_non_zero_is_an_empty_unread(lab, monkeypatch):
    """mw006_e13: git's own answer in a folder with no repository.
    Catches: a failed git read taken for an empty list of files."""
    monkeypatch.setattr(runner, "git", lambda *_a, **_k: subprocess.CompletedProcess([], 128, "", "fatal"))
    taken = read(lab, CARD_COMMIT).commits[0].taken
    assert taken == core.Unread("")


@pytest.mark.parametrize("command, tool", [("git status", "Bash"), ("echo done", "Bash"), ("ls -la", "Bash"), ("", "Bash"),
                                           (CARD_COMMIT, "Read")])
def test_a_command_with_no_commit_and_a_non_shell_tool_read_no_git(lab, monkeypatch, command, tool):
    """The gate reads git only for a commit of a shell command in a git project.
    Catches: a git read, and its cost, for every command of a session."""
    def forbidden(*_a, **_k):
        raise AssertionError("git was read")
    monkeypatch.setattr(runner, "git", forbidden)
    assert read(lab, command, tool=tool).commits == ()


# ---- the shell writes what the verdict says -------------------------------------------------------------------------------

def test_the_shell_writes_the_records_of_a_verdict_and_maps_the_kinds(lab):
    """The ruling: the verdict is data, the shell writes it. Rows go to the state folder, in order.
    Catches: a verdict whose rows are lost or written out of order."""
    ctx = gate_call(lambda event, ctx: ctx, lab, tool="Bash", tool_input={"command": "x"}, gate="commit_files")
    verdict = core.refuse("junk-file-staged", "x is junk", records=(("mw052_rows.jsonl", {"n": 1}),
                                                                      ("mw052_rows.jsonl", {"n": 2})))
    gate_commit.write_records(ctx, verdict.records)
    assert [r["n"] for r in jsonl(lab / "mkway" / "state" / "mw052_rows.jsonl")] == [1, 2]


KINDS = [pytest.param(core.allow(), (gate.ALLOW,), id="allow"),
         pytest.param(core.refuse("junk-file-staged", "x is junk"), (gate.REFUSE, "junk-file-staged", "x is junk"),
                      id="refuse"),
         pytest.param(core.allow_with_line("note", "a line"), (gate.LOG, "note", "a line"), id="allow_with_line")]


@pytest.mark.parametrize("verdict, expected", KINDS)
def test_a_verdict_maps_to_the_gates_kind(verdict, expected):
    """allow, refuse and allow-with-line map to the gate's allow, refuse and log.
    Catches: a refusal that reaches the dispatcher as an allow."""
    g = gate_commit.to_gate(verdict)
    assert (g.kind, g.reason_id, g.message)[:len(expected)] == expected


GATE_CASES = [pytest.param(CARD_COMMIT, gate.REFUSE, "ignored-file-staged", id="a_force_added_ignored_file_is_refused"),
              pytest.param("git status", gate.ALLOW, None, id="a_command_that_is_no_commit_passes")]


@pytest.mark.parametrize("command, kind, reason", GATE_CASES)
def test_the_gate_is_the_reader_plus_the_core(lab, command, kind, reason):
    """The entry `gate_commit:check` = `read_facts` then `decide_commit` through the real context: the lab's index holds a
    force-added ignored file. Catches: a gate that reads facts and then ignores the core's verdict."""
    v = gate_call(gate_commit.check, lab, tool="Bash", tool_input={"command": command}, gate="commit_files")
    assert (v.kind, v.reason_id) == (kind, reason)


# ---- the reader agrees with real git ------------------------------------------------------------------------------------

def _committed(root):
    return sorted(git(root, "show", "--name-only", "--format=", "HEAD").split())


def test_the_paths_form_agrees_with_what_real_git_commits(tmp_path):
    """mw043 e1: `-- <path>` with a foreign file staged: the reader's list is the named path alone, and real git puts
    in that path alone and leaves the foreign file staged. Catches: a foreign staged file judged as part of a `--` commit."""
    root = make_task(tmp_path, name="agree1")
    save(root, "src/m.py", "old\n")
    work(root, "src/m.py", "new\n")
    work(root, "other/b.py")
    stage(root, "other/b.py")
    taken = [rel for _s, rel, _src in read(root, CARD_COMMIT + " -- src/m.py").commits[0].taken]
    git(root, "commit", "-q", "-m", "CARD-001 x", "--", "src/m.py")
    assert taken == _committed(root) == ["src/m.py"]
    assert git(root, "diff", "--cached", "--name-only").split() == ["other/b.py"]


def test_the_all_form_agrees_with_what_real_git_commits(tmp_path):
    """mw043 e4: `-a` takes the staged list plus every modified tracked file; the reader's set is what git commits.
    Catches: a tracked change that git commits and the gate does not see."""
    root = make_task(tmp_path, name="agree2")
    save(root, "src/m.py", "old\n")
    save(root, "other/c.py", "old\n")
    work(root, "src/m.py", "new\n")
    work(root, "other/c.py", "new\n")
    work(root, "other/b.py")
    stage(root, "other/b.py")
    taken = sorted(rel for _s, rel, _src in read(root, "git commit -a -m 'CARD-001 x'").commits[0].taken)
    git(root, "commit", "-q", "-a", "-m", "CARD-001 x")
    assert taken == _committed(root) == ["other/b.py", "other/c.py", "src/m.py"]


# ---- MW-053: the facts of the orderer, from a real register --------------------------------------------------------------

LEAD, OTHER, BUILDER = "lead-a", "lead-b", "b1"
REGISTER_FILE = "mkway/cards/REGISTER.md"


def _set_paths(root, card_id, value):
    """The Paths cell of the card file, as the owner writes it before `card open` records it."""
    (folder,) = [p for p in (root / "mkway" / "cards").iterdir() if p.name.startswith(card_id + "-")]
    text = re.sub(r"^\| \*\*Paths\*\* \|.*\|$", f"| **Paths** | {value} |",
                  (folder / "CARD.md").read_text(encoding="utf-8"), flags=re.M)
    (folder / "CARD.md").write_text(text, encoding="utf-8")


@pytest.fixture(scope="session")
def orderer_root(tmp_path_factory):
    """A git task root: two cards ordered by LEAD (the first open and held by BUILDER, Paths `src/` and the folder's
    `notes/`; the second open), one ordered by OTHER, one by the owner. Read-only for the tests that use it."""
    import records
    from _engine import cli
    from _mw017 import lead_root, new_card, row_of

    root = lead_root(tmp_path_factory.mktemp("facts-orderer"), vcs="git", name="otask")
    (root / "mkway" / ".gitignore").write_text("engine/\nlocks/\nstate/\n", encoding="utf-8")
    git(root, "init", "-q")
    s = types.SimpleNamespace(root=root)
    s.one = new_card(root, LEAD, "One")
    s.two = new_card(root, LEAD, "Two")
    s.alien = new_card(root, OTHER, "Alien")
    code, out, err = cli(root, "card", "new", "Mine")
    assert code == 0, err
    s.mine = re.search(r"(CARD-\d{3})", out).group(1)
    s.f1, s.f2, s.fa, s.fm = (row_of(root, c)["folder"].strip().strip("`") for c in (s.one, s.two, s.alien, s.mine))
    _set_paths(root, s.one, f"`src/`, `{s.f1}/notes/`")
    _set_paths(root, s.two, "`src/two/`")
    assert cli(root, "card", "open", s.one)[0] == 0
    records.append(root / "mkway" / "state", BUILDER, "take", s.one)
    save(root, "src/a.py")
    for folder in (s.f1, s.f2, s.fa, s.fm):
        work(root, f"{folder}/ORDER.md", "an order\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "start")
    assert cli(root, "card", "open", s.two)[0] == 0  # the register changes, sealed
    for folder in (s.f1, s.f2, s.fa, s.fm):
        work(root, f"{folder}/CARD.md", "changed\n")
    work(root, "src/a.py", "changed\n")
    return s


def _own_card_commit(s, folder=None):
    return f"git commit -m '{s.one} card and order' -- {folder or s.f1}/CARD.md {REGISTER_FILE}"


def test_the_orderer_facts_are_the_cards_the_session_ordered_and_who_holds_them(orderer_root):
    """mw053 e1, e10: the register rows whose `Ordered by` is the session: id, folder, parsed Paths; the holders of the
    cards by the session records. Catches: an orderer that the core cannot tell from a stranger."""
    s = orderer_root
    f = read(s.root, _own_card_commit(s), session=LEAD)
    by = {o.id: o for o in f.ordered}
    assert set(by) == {s.one, s.two}
    assert by[s.one].folder == s.f1 and by[s.one].paths == frozenset({"src", f"{s.f1}/notes"})
    assert by[s.two].folder == s.f2 and by[s.two].paths == frozenset({"src/two"})
    assert f.holders.get(s.one) == BUILDER and s.two not in f.holders
    assert f.card_id is None  # the orderer holds no card


@pytest.mark.parametrize("session", ["stranger", "", register.OWNER], ids=["a_stranger", "no_session_id", "the_owner"])
def test_a_session_that_orders_nothing_has_no_ordered_cards(orderer_root, session):
    """mw053 e6, e7: another session, a session with no id and the owner's id order no card.
    Catches: any session committing a card folder it did not order."""
    s = orderer_root
    assert read(s.root, _own_card_commit(s), session=session).ordered == ()


def test_a_session_has_only_the_cards_it_ordered(orderer_root):
    """mw053 e6: the other lead orders the one card it ordered and none of the first lead's.
    Catches: the cards of one lead in the facts of another."""
    s = orderer_root
    assert [o.id for o in read(s.root, _own_card_commit(s, s.fa), session=OTHER).ordered] == [s.alien]


def test_a_card_the_owner_ordered_is_not_in_a_sessions_facts(orderer_root):
    """mw053 e7: a card the owner ordered is not a session's to commit.
    Catches: an owner-ordered card committed by a lead."""
    s = orderer_root
    assert s.mine not in {o.id for o in read(s.root, _own_card_commit(s), session=LEAD).ordered}


def test_a_register_that_cannot_be_read_gives_no_ordered_cards(orderer_root, monkeypatch):
    """mw053: the commit is then judged as before (no orderer).
    Catches: a commit refused or allowed on an orderer read from a register nobody could read."""
    def boom(*_a, **_k):
        raise register.RegisterError("unreadable", "the register cannot be read")
    monkeypatch.setattr(register, "closed_ids", lambda *_a, **_k: set())  # the records view asks the register too
    monkeypatch.setattr(register, "read", boom)
    assert read(orderer_root.root, _own_card_commit(orderer_root), session=LEAD).ordered == ()


def test_holders_that_cannot_be_read_are_an_unread_fact(orderer_root, monkeypatch):
    """mw053: the session records did not answer: `holders` is an Unread whose text says to run it again.
    Catches: a read error that escapes as an exception, or holders taken for empty."""
    import records

    def boom(self):
        raise OSError("no records")
    monkeypatch.setattr(records.View, "holders", boom)
    f = read(orderer_root.root, _own_card_commit(orderer_root), session=LEAD)
    assert isinstance(f.holders, core.Unread) and "run it again" in f.holders.text


GATE_ORDERER = [
    pytest.param(LEAD, lambda s: _own_card_commit(s), gate.ALLOW, None, id="the_orderer_commits_its_card_folder"),
    pytest.param("stranger", lambda s: _own_card_commit(s), gate.REFUSE, "holds no open card",
                 id="a_stranger_is_refused"),
    pytest.param(LEAD, lambda s: f"git commit -m '{s.one} x' -- {s.f1}/CARD.md src/a.py {s.fa}/CARD.md", gate.REFUSE,
                 "src/a.py", id="a_mixed_commit_is_refused"),
]


@pytest.mark.parametrize("session, command, kind, word", GATE_ORDERER)
def test_the_gate_lets_the_orderer_commit_its_card_folder_and_refuses_the_stranger(orderer_root, session, command, kind, word):
    """mw053 e1, e6, e8: the real register and the real index through the entry `check`.
    Catches: an orderer refused its own card folder, or a stranger allowed it."""
    s = orderer_root
    v = gate_call(gate_commit.check, s.root, tool="Bash", tool_input={"command": command(s)}, session=session,
                  gate="commit_files")
    assert v.kind == kind and (word is None or word in v.message)


# ---- MW-058: the files a message-only amend takes, on real git -------------------------------------------------------------

FILES = ("other/b.py", "other/c.py", "src/a.py")
AMEND_FORMS = [
    ("git commit --amend --only -m 'x'", []), ("git commit --amend -o -m 'x'", []),
    ("git commit --amend -om 'x'", []), ("git commit -o --amend -m 'x'", []),
    ("git commit --amend -m 'x' --only", []), ("git commit --amend -m 'x' -o", []),
    ("git commit --amend --only -m 'x' -- src/a.py", ["src/a.py"]),
    ("git commit --amend -o -m 'x' src/a.py", ["src/a.py"]),
    ("git commit --amend -om 'x' -- src/a.py", ["src/a.py"]),
    ("git commit --amend -m 'x'", ["other/b.py", "src/a.py"]),
    ("git commit --amend -a -m 'x'", list(FILES)),
    ("git commit --amend -i -m 'x' -- src/a.py", ["other/b.py", "src/a.py"]),
    ("git commit --amend --only -a -m 'x'", list(FILES)),
    ("git commit --only -m 'x'", ["other/b.py", "src/a.py"]),
]


@pytest.fixture(scope="session")
def amend_root(tmp_path_factory):
    """`src/a.py` and `other/b.py` staged (new), `other/c.py` committed and then modified in the tree. Read-only."""
    root = make_task(tmp_path_factory.mktemp("facts-amend"), card_paths="`src/`", name="amend")
    save(root, "other/c.py")
    work(root, "other/c.py", "changed\n")
    work(root, "src/a.py")
    work(root, "other/b.py")
    stage(root, "src/a.py", "other/b.py")
    return root


@pytest.mark.parametrize("command, expected", AMEND_FORMS, ids=[c for c, _e in AMEND_FORMS])
def test_the_files_an_amend_takes_follow_its_form(amend_root, command, expected):
    """mw058 e1: `--amend --only` or `-o` with no paths (also the group `-om`) takes none; with paths exactly the named;
    `--amend` alone the staged list (`-a`: plus modified tracked files; `-i`: plus the named).
    Catches: a message-only amend that is judged by the index it does not read."""
    taken = read(amend_root, command).commits[0].taken
    assert sorted(rel for _status, rel, _source in taken) == expected


@pytest.mark.parametrize("command", ["git commit --amend --only -m x", "git commit --amend -o -m x",
                                     "git commit --amend -om x"])
def test_a_message_only_amend_reads_no_git_and_takes_no_files(amend_root, tmp_path, monkeypatch, command):
    """mw058 e1, mw060 e14: the reader returns no file for a message-only amend without a git call, in a folder with no
    repository too; the ignore answer and the sizes of nothing are empty, not unread.
    Catches: a git read, and a possible failure, for a commit that takes nothing."""
    import helpers

    def forbidden(*_a, **_k):
        raise AssertionError("git was read for a message-only amend")
    monkeypatch.setattr(runner, "git", forbidden)
    monkeypatch.setattr(runner, "run", forbidden)
    (commit,) = helpers.commit_cmd(command)
    assert gate_commit.taken(lambda path: path, tmp_path / "no-repository-here", commit) == []
    c = read(amend_root, command).commits[0]
    assert (c.taken, c.ignored, dict(c.sizes), c.only) == ((), frozenset(), {}, True)


AMEND_GATE = [pytest.param("git commit --amend --only -m 'CARD-001 reworded'", None, id="the_new_message_names_the_card"),
              pytest.param("git commit --amend --only -m 'no id here'", "commit-message-card", id="it_does_not")]


@pytest.mark.parametrize("command, reason", AMEND_GATE)
def test_the_message_checks_still_run_on_a_message_only_amend_through_the_gate(amend_root, command, reason):
    """mw058 e3: the holder of the open card: allowed with a new message that names the card, `commit-message-card`
    when it does not. Catches: an amend that skips the checks of the new message."""
    v = gate_call(gate_commit.check, amend_root, tool="Bash", tool_input={"command": command}, session="s1",
                  gate="commit_files")
    assert v.reason_id == reason
