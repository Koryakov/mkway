"""Card MW-140: git names a file from the TOP of the repository; a file outside the task root is OUTSIDE. The task root here
lies below the git top (`<top>/task/x`), so a file of the top (`README.md`, `scripts/x.py`, `.claude/settings.json`) used to
be judged under the made-up in-root name of the same text. Each test builds a real repository and calls the real reader
or gate. One test id is one case; the expected values are written from the card rows, not computed by the code under test.
Synthetic values only."""
import json
import re
import subprocess

import pytest

from _engine import cli, gate_call, jsonl
from _mw140 import COMMIT, check, git, make_world, put, reason, run_in, stage_top, way_out_command
import board
import dispatch
import gate_commit
import gate_lock
import helpers
import install
import rules
import startline

REASON = "file-outside-root"


def refused_text(verdict):
    assert (verdict.kind, verdict.reason_id) == ("refuse", REASON), (verdict.kind, verdict.reason_id, verdict.message)
    return verdict.message


@pytest.fixture
def world(tmp_path):
    return make_world(tmp_path)


# ==== the commit gate: each collision of the survey, now refused with the true name ============================================

def test_a_top_readme_is_outside_though_a_card_path_is_readme(world):
    """Catches: `<top>/README.md` judged as the in-root `README.md` a card Path names, and committed."""
    top, root = world
    put(top, "README.md")
    stage_top(top, "README.md")
    text = refused_text(check(root, COMMIT))
    assert text.startswith("README.md lies outside the task root")


def test_an_in_root_readme_is_still_committed(world):
    """Catches: the new check refusing the in-root `README.md` that the card Paths name (nearest allow of the row above)."""
    top, root = world
    put(root, "README.md")
    stage_top(top, "task/x/README.md")
    assert reason(check(root, COMMIT)) == "allow"


def test_a_top_scripts_file_is_outside_though_a_card_path_is_scripts(world):
    """Catches: `<top>/scripts/x.py` judged as the in-root `scripts/x.py` and committed."""
    top, root = world
    put(top, "scripts/x.py")
    stage_top(top, "scripts/x.py")
    assert refused_text(check(root, COMMIT)).startswith("scripts/x.py lies outside the task root")


def test_a_top_verdict_file_is_outside_not_a_card_verdict(world):
    """Catches: `<top>/tests/verdicts/CARD-002.md` read as the verdict file of card CARD-002 of this root."""
    top, root = world
    put(top, "tests/verdicts/CARD-002.md")
    stage_top(top, "tests/verdicts/CARD-002.md")
    assert refused_text(check(root, COMMIT)).startswith("tests/verdicts/CARD-002.md lies outside the task root")


def test_a_top_file_is_outside_though_an_exempt_entry_names_it(tmp_path):
    """Catches: `<top>/notes/n.md` passed because `paths.exempt` names the in-root `notes/`."""
    top, root = make_world(tmp_path, paths={"exempt": ["notes/**"]})
    put(top, "notes/n.md")
    stage_top(top, "notes/n.md")
    assert refused_text(check(root, COMMIT)).startswith("notes/n.md lies outside the task root")


def test_an_in_root_exempt_file_is_still_committed(tmp_path):
    """Catches: the new check refusing an exempt in-root file (nearest allow of the row above)."""
    top, root = make_world(tmp_path, paths={"exempt": ["notes/**"]})
    put(root, "notes/n.md")
    stage_top(top, "task/x/notes/n.md")
    assert reason(check(root, COMMIT)) == "allow"


def test_a_top_file_is_outside_when_the_open_card_has_no_paths(tmp_path):
    """Catches: an open card with no Paths (which restricts nothing) letting `<top>/docs/n.md` through."""
    top, root = make_world(tmp_path, card_paths="")
    put(top, "docs/n.md")
    stage_top(top, "docs/n.md")
    assert refused_text(check(root, COMMIT)).startswith("docs/n.md lies outside the task root")


def test_a_top_file_named_like_an_own_writable_file_is_outside(tmp_path):
    """Catches: `<top>/mkway/asks/q.md`, equal in text to the in-root asks folder an orderer may write, passed as its own."""
    from _mw017 import new_card
    top, root = make_world(tmp_path, cards={"approver": "orderer"})
    new_card(root, "lead-a", "Two")
    put(top, "mkway/asks/q.md")
    stage_top(top, "mkway/asks/q.md")
    verdict = check(root, "git commit -m 'CARD-002 q'", session="lead-a")
    assert refused_text(verdict).startswith("mkway/asks/q.md lies outside the task root")


def test_a_sibling_folder_that_starts_with_the_roots_name_is_outside(world):
    """Catches: `<top>/task/x2/f` (a sibling of the root) read as inside because its text starts with `task/x`."""
    top, root = world
    put(top, "task/x2/f")
    stage_top(top, "task/x2/f")
    assert refused_text(check(root, COMMIT)).startswith("task/x2/f lies outside the task root")


# ---- the other forms a commit takes: `-a`, `-- <path>` ----------------------------------------------------------------------

def test_dash_a_takes_a_modified_tracked_file_of_the_top_and_it_is_outside(world):
    """Catches: `git commit -a` taking a changed tracked file of the top unseen, under a made-up in-root name."""
    top, root = world
    put(top, "other/b.py", "b = 2\n")
    text = refused_text(check(root, "git commit -a -m 'CARD-001 work'"))
    assert "other/b.py lies outside the task root" in text and "commit without `-a`" in text


def test_a_named_path_of_the_top_is_outside(world):
    """Catches: `git commit -- ../../other/b.py` taking a file of the top, judged as the in-root `other/b.py`."""
    top, root = world
    put(top, "other/b.py", "b = 2\n")
    text = refused_text(check(root, "git commit -m 'CARD-001 work' -- ../../other/b.py"))
    assert "leave it out of the paths after `--`" in text


def test_a_deleted_tracked_file_of_the_top_is_outside(world):
    """Catches: the removal of a file of the top committed as `removing the mess`."""
    top, root = world
    git(top, "rm", "-q", "--", "other/b.py")
    assert refused_text(check(root, COMMIT)).startswith("other/b.py lies outside the task root")


# ---- a rename across the border: both names are read, either side outside refuses --------------------------------------------

def test_a_rename_out_of_the_root_is_refused_by_its_outside_name(world):
    """Catches: a move to the top judged by its in-root half only (the deletion), so the outside file rides in."""
    top, root = world
    git(top, "mv", "task/x/src/a.py", "other/a.py")
    assert refused_text(check(root, COMMIT)).startswith("other/a.py lies outside the task root")


def test_a_rename_into_the_root_is_refused_by_its_outside_name(world):
    """Catches: a move from the top judged by its in-root half only (the addition), so the removal of the top file rides in."""
    top, root = world
    git(top, "mv", "other/b.py", "task/x/src/b.py")
    assert refused_text(check(root, COMMIT)).startswith("other/b.py lies outside the task root")


# ---- the ways out the text names work ------------------------------------------------------------------------------------------

def test_the_text_names_the_way_out_and_no_ruling_id(world):
    """Catches: a refusal that says nothing of how to go on, or names a ruling id or a way (`move it later`) that is refused."""
    top, root = world
    put(top, "README.md")
    stage_top(top, "README.md")
    text = check(root, COMMIT).message
    assert ("keep the file inside the task root" in text, "git restore --staged :/README.md" in text,
            "in their own terminal" in text, re.search(r"\bR\d{2,}", text), "move it later" in text) == (
        True, True, True, None, False)


def test_way_out_one_keeping_the_file_inside_the_root_passes(world):
    """Catches: the first way out of the text not working: the same file kept inside the task root is committed."""
    top, root = world
    put(top, "README.md")
    stage_top(top, "README.md")
    assert reason(check(root, COMMIT)) == REASON
    git(top, "reset", "-q")
    put(root, "README.md")
    stage_top(top, "task/x/README.md")
    assert reason(check(root, COMMIT)) == "allow"


def test_way_out_two_the_restore_command_of_the_text_passes_the_commit(world):
    """Catches: a `git restore --staged` the text names that does not unstage the file from the root (a name read from the
    root instead of the top), so the commit stays refused."""
    top, root = world
    put(top, "README.md")
    put(root, "src/b.py")
    stage_top(top, "README.md", "task/x/src/b.py")
    argv = way_out_command(check(root, COMMIT).message)
    assert argv is not None
    run_in(root, argv)
    assert (reason(check(root, COMMIT)), git(top, "diff", "--cached", "--name-only").split()) == (
        "allow", ["task/x/src/b.py"])


# ---- a root at the top: nothing changes ------------------------------------------------------------------------------------------

def test_a_root_at_the_top_judges_every_name_as_before(tmp_path):
    """Catches: the new check refusing a file in a repository whose top is the task root, or changing the old reason."""
    from _commit_fixture import make_task, work
    root = make_task(tmp_path, card_paths="`README.md`", name="plain")
    work(root, "README.md")
    work(root, "other.txt")
    stage_top(root, "README.md")
    first = reason(check(root, COMMIT))
    stage_top(root, "other.txt")
    assert (first, reason(check(root, COMMIT))) == ("allow", "file-not-in-card")


# ---- names git would quote stay inside --------------------------------------------------------------------------------------------

def test_in_root_names_with_a_space_and_a_non_ascii_letter_are_read_as_they_are(world):
    """Catches: a name read through a locale decode (`cafÃ©.py`) or left quoted, so it matches no card Path."""
    top, root = world
    put(root, "src/café.py")
    put(root, "src/my file.py")
    stage_top(top, "task/x/src/café.py", "task/x/src/my file.py")
    facts = gate_call(gate_commit.read_facts, root, tool="Bash", tool_input={"command": COMMIT}, session="s1",
                      gate="commit_files")
    assert sorted(rel for _s, rel, _src in facts.commits[0].taken) == ["src/café.py", "src/my file.py"]


def test_a_commit_of_in_root_names_with_a_space_and_a_non_ascii_letter_is_allowed(world):
    """Catches: the new check refusing an in-root file because git would quote its name."""
    top, root = world
    put(root, "src/café.py")
    put(root, "src/my file.py")
    stage_top(top, "task/x/src/café.py", "task/x/src/my file.py")
    assert reason(check(root, COMMIT)) == "allow"


# ---- the ignore and size checks never run on an outside name -------------------------------------------------------------------------

def test_the_ignore_and_size_reads_never_see_an_outside_name(world, monkeypatch):
    """Catches: `check-ignore` and the size read asked about the made-up in-root `README.md` for a file of the top."""
    top, root = world
    put(top, "README.md")
    stage_top(top, "README.md")
    seen = []
    real_ignored, real_sizes = gate_commit._ignored, gate_commit._sizes
    monkeypatch.setattr(gate_commit, "_ignored", lambda ctx, rels: (seen.append(list(rels)), real_ignored(ctx, rels))[1])
    monkeypatch.setattr(gate_commit, "_sizes", lambda ctx, rows: (seen.append([r for r, _s in rows]), real_sizes(ctx, rows))[1])
    check(root, COMMIT)
    assert [name for names in seen for name in names if name == "README.md"] == []


# ==== the lock gate: an outside file is never matched against a lock target ======================================================

def lock_ctx(root, command=COMMIT):
    profile = json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))
    return dispatch.make_context(profile=profile, root=root, session_id="s1", event="PreToolUse", gate="g",
                                 tool_name="Bash", tool_input={"command": command}, budget_seconds=None,
                                 once=lambda t: True, tool_response=None, env={}), profile


def lock_verdict(root, command=COMMIT):
    return gate_call(gate_lock.check, root, tool="Bash", tool_input={"command": command})


def test_a_top_hooks_file_is_not_the_closed_lock_target_of_the_task(world):
    """Catches: `<top>/.claude/settings.json` judged as the task's own closed lock target: a false `lock-closed-commit`."""
    top, root = world
    put(top, ".claude/settings.json", "{}\n")
    stage_top(top, ".claude/settings.json")
    assert lock_verdict(root).kind == "allow"


def test_the_commit_gate_refuses_the_top_hooks_file_as_outside(world):
    """Catches: the file the lock gate leaves to the commit gate passing the commit gate too."""
    top, root = world
    put(top, ".claude/settings.json", "{}\n")
    stage_top(top, ".claude/settings.json")
    assert refused_text(check(root, COMMIT)).startswith(".claude/settings.json lies outside the task root")


def test_the_in_root_hooks_file_is_still_a_closed_lock_target(world):
    """Catches: the lock gate losing the in-root `.claude/settings.json` (nearest deny of the row above)."""
    top, root = world
    put(root, ".claude/settings.json", "{}\n")
    stage_top(top, "task/x/.claude/settings.json")
    assert lock_verdict(root).reason_id == "lock-closed-commit"


def test_a_pathspec_of_the_top_hooks_file_is_not_a_lock_target_of_the_task(world):
    """Catches: `git commit -- ../../.claude/settings.json` expanded to the made-up in-root name of a closed target."""
    top, root = world
    put(top, ".claude/settings.json", "{}\n")
    stage_top(top, ".claude/settings.json")
    git(top, "commit", "-q", "-m", "hooks")
    put(top, ".claude/settings.json", "{\"a\": 1}\n")
    assert lock_verdict(root, "git commit -m 'CARD-001 x' -- ../../.claude/settings.json").kind == "allow"


def test_the_expansion_of_a_pathspec_drops_the_outside_names_and_keeps_the_inside_ones(world):
    """Catches: `_expand` returning a top file under a made-up in-root name, or dropping an in-root one."""
    top, root = world
    put(top, "other/b.py", "b = 2\n")
    put(root, "src/a.py", "a = 2\n")
    ctx, _profile = lock_ctx(root)
    assert gate_lock._expand(ctx, root, ["../../other", "src"]) == (["src/a.py"], None)


def test_the_index_names_drop_the_outside_names_and_keep_the_inside_ones(world):
    """Catches: `_index_names` returning a top file under a made-up in-root name."""
    top, root = world
    put(top, "README.md")
    put(root, "src/b.py")
    stage_top(top, "README.md", "task/x/src/b.py")
    ctx, _profile = lock_ctx(root)
    assert gate_lock._index_names(ctx, False) == (["src/b.py"], None)


def test_the_index_names_under_dash_a_drop_the_outside_names(world):
    """Catches: `-a` tracked changes of the top returned under made-up in-root names."""
    top, root = world
    put(top, "other/b.py", "b = 2\n")
    put(root, "src/a.py", "a = 2\n")
    ctx, _profile = lock_ctx(root)
    assert gate_lock._index_names(ctx, True) == (["src/a.py"], None)


def test_the_staged_names_of_the_include_form_drop_the_outside_names(world):
    """Catches: `fact_staged` returning a top file under a made-up in-root name."""
    top, root = world
    put(top, "README.md")
    put(root, "src/b.py")
    stage_top(top, "README.md", "task/x/src/b.py")
    ctx, profile = lock_ctx(root)
    names = gate_lock.Reader(ctx, profile, COMMIT).fact_staged(0)
    assert tuple(names.paths) == ("src/b.py",)


def test_the_index_names_keep_a_non_ascii_in_root_name_as_it_is(world):
    """Catches: `-z` left off, so git quotes the name (`"task/x/src/caf\\303\\251.py"`) and it is read as another file."""
    top, root = world
    put(root, "src/café.py")
    stage_top(top, "task/x/src/café.py")
    ctx, _profile = lock_ctx(root)
    assert gate_lock._index_names(ctx, False) == (["src/café.py"], None)


# ==== the start line, `mkway check` and the board: an outside file is shown as outside ========================================

def profile_of(root):
    return json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))


def test_the_start_line_shows_a_staged_top_file_as_outside_and_counts_only_the_card_files(world):
    """Catches: a staged top file counted as outside the card (made-up name) or hidden as inside the card's Paths."""
    top, root = world
    put(top, "README.md")
    put(top, "other/n.md")
    put(root, "notes/n.md")
    stage_top(top, "README.md", "other/n.md", "task/x/notes/n.md")
    lines = startline._staged_lines(root, profile_of(root), "s1")
    assert (lines[0], sorted(lines[1:])) == ("staged outside your card: 1", ["outside the task root: README.md",
                                                                           "outside the task root: other/n.md"])


def test_mkway_check_shows_a_staged_top_file_as_outside(world):
    """Catches: `mkway check` counting or hiding a staged top file as a file of the root."""
    top, root = world
    put(top, "README.md")
    put(root, "notes/n.md")
    stage_top(top, "README.md", "task/x/notes/n.md")
    lines = install.staged_outside_lines(root, profile_of(root))
    assert (lines[0], lines[1:]) == ("staged files: 1 outside every open card's Paths",
                                     ["outside the task root: README.md"])


def test_a_root_at_the_top_has_no_outside_line_in_the_start_line(tmp_path):
    """Catches: an outside line shown for a repository whose top is the root (nothing changes there)."""
    from _commit_fixture import make_task, work
    root = make_task(tmp_path, card_paths="`src/`", name="plain")
    work(root, "notes/n.md")
    stage_top(root, "notes/n.md")
    assert startline._staged_lines(root, profile_of(root), "s1") == ["staged outside your card: 1"]


def test_the_board_lists_an_uncommitted_top_file_as_outside_and_not_as_a_card_file(world):
    """Catches: an untracked `<top>/README.md` listed as an uncommitted file of the card because a Path is `README.md`."""
    top, root = world
    put(top, "README.md")
    put(root, "src/new.py")
    lines = board.lines(root, profile_of(root))
    assert [l for l in lines if "README.md" in l] == ["outside the task root: README.md"]
    assert [l for l in lines if l.startswith("uncommitted files of CARD-001")][0].endswith(": src/new.py")


def test_the_board_reader_gives_an_outside_value_for_a_top_file(world):
    """Catches: a top file dropped from the reader (hidden) or given as an in-root name."""
    top, root = world
    put(top, "README.md")
    put(root, "src/new.py")
    got = board.uncommitted_files(root)
    assert ([g for g in got if isinstance(g, str)], [g.name for g in got if isinstance(g, helpers.Outside)]) == (
        ["src/new.py"], ["README.md"])


# ==== `mkway rules`: the last green tree is read with the top-relative form ======================================================

def test_the_last_green_tree_of_a_test_is_found_when_the_root_lies_below_the_top(world):
    """Catches: `cat-file -e <tree>:<in-root path>` against a tree of the top, which names no file: the test shows no green tree."""
    top, root = world
    put(root, "tests/test_demo.py", "def test_x():\n    assert True\n")
    stage_top(top, "task/x/tests/test_demo.py")
    git(top, "commit", "-q", "-m", "demo")
    tree = git(top, "rev-parse", "HEAD^{tree}").strip()
    state = root / "mkway" / "state"
    state.mkdir(parents=True, exist_ok=True)
    (state / rules.STATE_FILE).write_text(json.dumps({"result": "pass", "tree": tree}) + "\n", encoding="utf-8")
    assert rules.last_green_tree(root, profile_of(root), "tests/test_demo.py") == tree


# ==== through the real dispatcher ======================================================================================

def test_the_real_dispatcher_denies_a_top_file_with_the_tag_of_the_new_reason_and_writes_a_row(tmp_path):
    """Catches: a refusal that never reaches the dispatcher with its tag (`[mkway commit_files file-outside-root]`) or leaves no
    row in the refusal log, so the reason is undeclared in the manifest."""
    top, root = make_world(tmp_path, gates={"commit_tests": {"on": False}})
    put(top, "README.md")
    stage_top(top, "README.md")
    payload = {"session_id": "s1", "hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": COMMIT},
               "cwd": str(root)}
    out = json.loads(dispatch.run("PreToolUse", "shell", json.dumps(payload),
                                  env={"CLAUDE_PROJECT_DIR": str(root), "MKWAY_SESSION_ID": "s1"}).stdout)["hookSpecificOutput"]
    rows = [r for r in jsonl(root / "mkway" / "state" / "refusals.jsonl") if r["gate"] == "commit_files"]
    assert (out["permissionDecision"], out["permissionDecisionReason"].startswith(
        "[mkway commit_files file-outside-root] README.md lies outside the task root"),
            [(r["reason_id"], r["kind"]) for r in rows]) == ("deny", True, [(REASON, "refuse")])


# ==== the way-out test of the registry ============================================================================================

def test_the_way_out_of_file_outside_root_is_to_unstage_the_file(world):
    """The registry's way-out test of `file-outside-root` (concept.py): the `git restore --staged` the text names, run from
    the task root, takes the outside file out of the commit and the same commit then passes."""
    top, root = world
    put(top, "docs/n.md")
    put(root, "docs/m.md")
    stage_top(top, "docs/n.md", "task/x/docs/m.md")
    argv = way_out_command(check(root, COMMIT).message)
    run_in(root, argv)
    assert reason(check(root, COMMIT)) == "allow"
