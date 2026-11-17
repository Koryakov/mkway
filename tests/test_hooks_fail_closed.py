"""Card MW-109: fail-closed wiring and the start line (line 1, kind K8), and the way-out row of every refusal the card
touches. MATCHER LEVEL ONLY: these tests read the hook entries the install generates (event, matcher, timeout,
onFailure) and the dispatcher's answer for a planted failure; they do not scan the code of any hook. The Claude Code
documentation (hooks page) says a timed-out or crashing command hook does not block unless its entry carries
`onFailure: block`, so the entries of the two blocking groups must carry it and a timeout above what their gates may use.

Part 1: the wiring (a pin of what install generates). Part 2: the failed hook's refusal (names the hook, the error line
and the repair). Part 3: the way-out rows: for each id one test whose parameter id is the reason id: the refusal, then
the call that passes after the way out (the owner's lock open, the literal path, the repaired file). Synthetic values only.
"""
import json

import pytest

from _engine import ENGINE, FIXTURES, entry, gate_call, jsonl, make_profile, task_root, write_profile  # first: the path
import asks
import core_delete
import core_install
import core_lock
import dispatch
import gate_owner_ask
import outbox
import trash
from _delete_world import judge, reason
from _mw020 import built, deliverable, green, make_root as make_deliverable_root
from _commit_fixture import git, work

MANIFEST = json.loads((ENGINE / "manifest.json").read_text(encoding="utf-8"))
TABLE = MANIFEST["groups"]
ON = [e for e in MANIFEST["entries"] if e.get("status") == "on" and e.get("default_on") and e.get("function")]
TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit", "Bash", "PowerShell", "AskUserQuestion", "SendMessage",
         "ArtifactData"}
MARGIN = 15  # the margin the install adds to a hook entry's timeout (R13c)
COMMIT_TESTS_BUDGET = 780  # the declared budget of the commit-tests gate, in seconds
MIB = 1024 * 1024


def generated(profile=None):
    return core_install.generate_entries(profile or make_profile(), ON, TABLE)


# ==== part 1: the wiring ====================================================================================================

@pytest.mark.parametrize("group", ["edit", "shell"])
def test_the_entry_of_a_blocking_group_carries_on_failure_block(group):
    """Catches: a hook entry of the edit or shell group without `onFailure: block`, so a crash or a timeout of the dispatcher lets the tool call through (K8)."""
    assert [e["on_failure"] for e in generated() if e["group"] == group] == ["block"]


@pytest.mark.parametrize("group", ["edit", "shell"])
def test_the_timeout_of_a_blocking_entry_covers_every_gate_it_runs(group):
    """Catches: a hook timeout below the budgets its gates declare, which would kill a gate mid-run (R270a: every hook's timeout is at least its gates' declared budget)."""
    declared = sum(e["timeout"] for e in ON if e["group"] == group)
    (hook,) = [e for e in generated() if e["group"] == group]
    assert hook["timeout"] >= declared + MARGIN


def test_the_shell_entry_leaves_the_commit_tests_budget_and_a_margin():
    """Catches: a shell hook timeout under the 780 s commit-tests budget plus a margin, which refuses a green commit as a timeout."""
    (hook,) = [e for e in generated() if e["group"] == "shell"]
    assert hook["timeout"] >= COMMIT_TESTS_BUDGET + MARGIN


def test_every_hook_the_manifest_turns_on_is_registered_in_the_settings_file():
    """Catches: a gate in the manifest whose hook entry is missing from the settings text install writes, so the gate never runs."""
    text = core_install.settings_text(None, generated(), "mkway").out
    owned = core_install.owned_entries(text, "mkway")
    have = {(e["event"], e["command"].split("--group ")[1].split(" ")[0]) for e in owned if "--group" in e["command"]}
    want = {(e["event"], e["group"]) for e in ON if e["group"] != "wake" and not e.get("frontmatter")}  # MW116-D2
    assert want - have == set()


def test_every_matcher_is_a_tool_name_and_no_hook_keys_on_a_word():
    """Catches: a matcher that names a word or a pattern instead of tool names, which Claude Code reads as a regular expression."""
    words = {p for e in generated() + ON for p in (e.get("matcher") or "").split("|") if p} - TOOLS
    assert words == set()


# ==== part 2: a failed hook (R270a) =========================================================================================

def _run(root, entries, *, stdin=None, event="PreToolUse", group="edit"):
    payload = {"session_id": "s1", "hook_event_name": event, "cwd": ".", "tool_name": "Edit",
               "tool_input": {"file_path": "src/a.py"}}
    return dispatch.run(event, group, stdin if stdin is not None else json.dumps(payload),
                        env={"CLAUDE_PROJECT_DIR": str(root), "CLAUDECODE": "1"}, engine_dir=ENGINE, manifest=entries,
                        gate_paths=[FIXTURES])


@pytest.fixture
def root(tmp_path):
    folder = tmp_path / "task"
    folder.mkdir()
    write_profile(folder, make_profile())
    return folder


def _reason(res):
    return json.loads(res.stdout)["hookSpecificOutput"]["permissionDecisionReason"]


@pytest.mark.parametrize("needle", ["b1", "RuntimeError", "fixture gate: planted failure", "mkway check", "operator",
                                    "owner repairs"],
                         ids=["names-the-hook", "names-the-error-class", "names-the-error-line", "names-the-self-check",
                              "report-to-the-operator", "the-owner-repairs-settings"])
def test_a_failed_hook_refusal_names_the_hook_the_error_line_and_the_repair(root, needle):
    """Catches: a gate-error refusal that says only that something failed: the session cannot tell which hook, what error, or what to do (R270a)."""
    res = _run(root, [entry("b1", "fixture_gates:raises", on_failure="block")])
    assert needle in _reason(res)


@pytest.mark.parametrize("needle", ["blocked", "JSONDecodeError", "mkway check", "operator", "owner repairs"],
                         ids=["says-blocked", "names-the-error-class", "names-the-self-check", "report-to-the-operator",
                              "the-owner-repairs-settings"])
def test_a_dispatcher_failure_line_names_the_error_and_the_repair(root, needle):
    """Catches: a dispatcher-error line with no repair named (R270a); it stays one stderr line."""
    res = _run(root, [entry("b1", "fixture_gates:raises", on_failure="block")], stdin="not json")
    assert (res.exit_code, needle in res.stderr, len(res.stderr.splitlines())) == (2, True, 1)


# ==== part 3: the way-out rows ==============================================================================================

# ---- gate-error and dispatcher-error: the call passes after the repair --------------------------------------------------

def test_a_gate_error_way_out(root):
    """Catches: a failed hook that keeps refusing after the repair; the same call passes once the gate runs again (way out of gate-error)."""
    failed = _run(root, [entry("b1", "fixture_gates:raises", on_failure="block")])
    repaired = _run(root, [entry("b1", "fixture_gates:always_log", on_failure="block", reason_ids=("fixture-log",))])
    assert ("gate-error" in _reason(failed), repaired.exit_code, repaired.stdout) == (True, 0, "")


def test_a_dispatcher_error_way_out(root):
    """Catches: a dispatcher failure that keeps blocking after the repair; a readable input passes again (way out of dispatcher-error)."""
    failed = _run(root, [entry("b1", "fixture_gates:always_log", reason_ids=("fixture-log",))], stdin="not json")
    repaired = _run(root, [entry("b1", "fixture_gates:always_log", reason_ids=("fixture-log",))])
    assert (failed.exit_code, repaired.exit_code, repaired.stdout) == (2, 0, "")


def test_a_profile_invalid_way_out(root):
    """Catches: an invalid profile that keeps refusing after the owner repairs it (way out of profile-invalid)."""
    gate = [entry("b1", "fixture_gates:always_log", reason_ids=("fixture-log",))]
    (root / "mkway" / "profile.json").write_text("{ broken", encoding="utf-8")
    refused = _run(root, gate)
    write_profile(root, make_profile())
    repaired = _run(root, gate)
    assert ("profile-invalid" in _reason(refused), repaired.exit_code, repaired.stdout) == (True, 0, "")


# ---- the four record failures: refuse with the path; after the repair the record is written ------------------------------

def _post(root, stdout):
    payload = {"session_id": "s1", "hook_event_name": "PostToolUse", "tool_name": "Bash",
               "tool_input": {"command": "python mkway/engine/mkway.py card new x"},
               "tool_response": {"stdout": stdout, "stderr": "", "interrupted": False}}
    return dispatch.run("PostToolUse", "post", json.dumps(payload), env={"CLAUDE_PROJECT_DIR": str(root)})


def test_a_post_record_failed_way_out(tmp_path):
    """Catches: a failed session record that keeps refusing after the folder in its place is repaired (way out of post-record-failed)."""
    import cardtool  # noqa: F401  (the engine command the session ran)
    from _engine import cli
    folder = task_root(tmp_path)
    code, out, _err = cli(folder, "card", "new", "First", session=True)
    blocker = folder / "mkway" / "state" / "records.jsonl"
    blocker.mkdir()
    refused = _post(folder, out)
    blocker.rmdir()
    _code, again, _err = cli(folder, "card", "new", "Second", session=True)  # the call is repeated: a new nonce
    repaired = _post(folder, again)
    assert (code, "records.jsonl" in refused.stdout, repaired.stdout, len(jsonl(blocker))) == (0, True, "", 1)


def test_an_agent_record_failed_way_out(tmp_path):
    """Catches: a failed agent record that keeps refusing a subagent start after the folder in its place is repaired (way out of agent-record-failed)."""
    folder = task_root(tmp_path)
    blocker = folder / "mkway" / "state" / "agents.jsonl"
    blocker.mkdir()
    payload = json.dumps({"session_id": "s1", "hook_event_name": "SubagentStart", "cwd": str(folder),
                          "agent_id": "a1", "agent_type": "worker", "transcript_path": "unused.jsonl"})
    env = {"CLAUDE_PROJECT_DIR": str(folder)}
    refused = dispatch.run("SubagentStart", "post", payload, env=env)
    blocker.rmdir()
    repaired = dispatch.run("SubagentStart", "post", payload, env=env)
    assert (refused.exit_code, "agents.jsonl" in refused.stderr, repaired.exit_code) == (2, True, 0)


def _boom(*args, **kwargs):
    raise OSError("disk")


def test_a_check_record_failed_way_out(tmp_path, monkeypatch):
    """Catches: a failed check record that keeps refusing after the writer works again (way out of check-record-failed)."""
    from _mw019 import OUT, SUFFIX, make_root, post, write_check, write_doc
    folder = make_root(tmp_path)
    write_doc(folder)
    write_check(folder, f"{OUT}/a.md", recorded=False)
    check, real = f"{OUT}/a.md{SUFFIX}", outbox.record_check
    monkeypatch.setattr(outbox, "record_check", _boom)
    refused = post(folder, check)
    monkeypatch.setattr(outbox, "record_check", real)
    repaired = post(folder, check)
    assert (refused.kind, outbox.RECORDS in refused.message, repaired.kind) == ("refuse", True, "allow")


def test_an_ask_record_failed_way_out(tmp_path, monkeypatch):
    """Catches: a failed ask record that keeps refusing after the writer works again (way out of ask-record-failed)."""
    folder = task_root(tmp_path, owner_ask={"sources": ["review"]})
    ask = "mkway/asks/t_ask.md"
    (folder / ask).parent.mkdir(parents=True, exist_ok=True)
    (folder / ask).write_text("Which option?\nstatus: open\n", encoding="utf-8")

    def post_ask():
        return gate_call(gate_owner_ask.check, folder, tool="Write", event="PostToolUse", session="s1",
                         tool_input={"file_path": ask, "content": "x"}, tool_response={"filePath": ask, "success": True})
    real = asks.record_owner
    monkeypatch.setattr(asks, "record_owner", _boom)
    refused = post_ask()
    monkeypatch.setattr(asks, "record_owner", real)
    repaired = post_ask()
    assert (refused.kind, "owner record" in refused.message, repaired.kind != "refuse") == ("refuse", True, True)


# ---- the delete family: the literal path inside the root, or the owner's terminal ---------------------------------------

DONE_TEXT = "name the path in your DONE line; the owner removes it"  # card 2, R270c: the sentence the merged engine carries


@pytest.mark.parametrize("bad, bad_kw, want, text, good, good_kw", [
    pytest.param("rm nothere.txt", {}, "delete-target-unknown", "mkway delete --list", "rm a.txt", {},
                 id="delete-target-unknown"),
    pytest.param("rm *.txt", {}, "delete-wildcard", "mkway delete --list", "rm a.txt", {}, id="delete-wildcard"),
    pytest.param('psql -c "drop table t"', {}, "delete-sql", "delete.sql_allowed", 'psql -c "drop table t"',
                 {"sql_allowed": True}, id="delete-sql"),
    pytest.param("git reset --hard", {"vcs_git": True, "changed": {"src/a.py": " M"}}, "delete-uncommitted", "src/a.py",
                 "git reset --hard", {"vcs_git": True}, id="delete-uncommitted"),
    pytest.param("rm ../elsewhere.txt", {}, "delete-outside-root", DONE_TEXT, "rm a.txt", {}, id="delete-outside-root"),
])
def test_a_delete_way_out(bad, bad_kw, want, text, good, good_kw):
    """Catches: a delete refusal with no way out in its text, or one that still refuses after the way out: the literal path inside the root, the profile key, or the committed tree."""
    refused = judge(bad, **bad_kw)
    assert (reason(refused), text in refused.verdict.message, reason(judge(good, **good_kw))) == (want, True, "allow")


def test_a_delete_too_large_way_out():
    """Catches: a size refusal that does not send the delete to the owner's terminal, or one that still refuses under a limit the owner raised (way out of delete-too-large)."""
    refused = core_delete.too_large(6 * MIB, 5, ["d"])
    assert (refused.reason, "owner's terminal" in refused.message, core_delete.too_large(6 * MIB, 10, ["d"])) == (
        "delete-too-large", True, None)


def test_a_delete_backup_failed_way_out(tmp_path):
    """Catches: a backup that fails open (the delete runs with no copy), or one that keeps failing after the trash folder is repaired (way out of delete-backup-failed)."""
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    broken, mended = tmp_path / "broken", tmp_path / "mended"
    broken.mkdir()
    mended.mkdir()
    (broken / trash.TRASH).write_text("a file where the trash folder belongs", encoding="utf-8")
    with pytest.raises(trash.BackupError) as raised:
        trash.backup(tmp_path, broken, ["a.txt"], session="s1", max_mb=5)
    row = trash.backup(tmp_path, mended, ["a.txt"], session="s1", max_mb=5)
    assert (raised.value.reason, row["targets"]) == ("delete-backup-failed", ["a.txt"])


@pytest.mark.parametrize("command, want", [
    pytest.param("cat > notes.md <<'EOF'\nplease delete the old file\nEOF", "allow", id="the-word-delete-in-a-heredoc-body"),
    pytest.param("cat > notes.md <<'EOF'\nrm -rf old\nEOF", "allow", id="rm-inside-a-heredoc-body"),
    pytest.param("echo 'delete rm x'", "allow", id="quoted-words-are-not-commands"),
    pytest.param("cat <<'EOF'\nrm a.txt\nEOF\nrm nothere.txt", "delete-target-unknown", id="rm-as-a-command-is-judged"),
])
def test_the_delete_anchors_are_command_names_only(command, want):
    """Catches: a delete gate that refuses a heredoc body or a quoted string for the word delete or rm (DD-013), or one that lets an rm command through behind a heredoc (R270d)."""
    assert reason(judge(command)) == want


# ---- the lock family: the owner's lock open, or the literal path -------------------------------------------------------

def _t(name, *entries, built_in=True):
    return core_lock.Target(name, entries, built_in)


REGISTER = "mkway/cards/REGISTER.md"
PROFILE, SRC = "mkway/profile.json", "src/a.py"
CLOSED = (_t("engine", "mkway/engine/"), _t("lock", "mkway/mkway.lock"), _t("profile", PROFILE),
          _t("locks", "mkway/locks/"), _t("register", REGISTER))
OPENED = tuple(t for t in CLOSED if t.name != "profile")  # the owner ran `lock open profile`


class _Reads(dict):
    """The facts of a case; a disk fact not named is "no file"."""

    def __contains__(self, key):
        return key[0] == "disk" or dict.__contains__(self, key)

    def __getitem__(self, key):
        return None if key[0] == "disk" else dict.__getitem__(self, key)


QUIET = {("engine_call",): None, ("calls",): (), ("parse_ok",): True, ("names_commit",): False, ("carrier",): None,
         ("form",): None, ("env",): None, ("cdpath",): False, ("writes",): core_lock.WriteFacts(), ("expanded_text",): "",
         ("commits",): (), ("unknown_shape",): ""}


def _edit(rel, targets):
    return core_lock.Facts(tool_name="Edit", targets=targets, session_id="s1", edit_rels=(rel,), reads=_Reads({}))


def _shell(targets, writes):
    return core_lock.Facts(tool_name="Bash", command="", targets=targets, vcs_git=False, register_rel=REGISTER,
                           owner_terminal="OWNER-TERMINAL", owner_fix="OWNER-FIX", stale_hours=2, session_id="s1",
                           reads=_Reads({**QUIET, ("writes",): writes}))


def _commit(path, targets):
    commit = core_lock.CommitFacts(paths=(path,), rels=(path,))
    return core_lock.Facts(
        tool_name="Bash", command="", targets=targets, vcs_git=True, register_rel=REGISTER, owner_terminal="OWNER-TERMINAL",
        owner_fix="OWNER-FIX", stale_hours=2, session_id="s1",
        reads=_Reads({**QUIET, ("commits",): (commit,), ("expanded", 0): core_lock.Names((path,), None)}))


def _outcome(facts):
    verdict = core_lock.decide(facts)
    return verdict.reason if verdict.kind == core_lock.REFUSE else verdict.kind


@pytest.mark.parametrize("closed, opened, want", [
    pytest.param(_edit(PROFILE, CLOSED), _edit(PROFILE, OPENED), "lock-closed-edit", id="lock-closed-edit"),
    pytest.param(_shell(CLOSED, writes=core_lock.WriteFacts(None, ((PROFILE, PROFILE),))),
                 _shell(OPENED, writes=core_lock.WriteFacts(None, ((PROFILE, PROFILE),))), "lock-closed-shell",
                 id="lock-closed-shell"),
    pytest.param(_commit(PROFILE, CLOSED), _commit(PROFILE, OPENED), "lock-closed-commit", id="lock-closed-commit"),
])
def test_a_closed_lock_way_out(closed, opened, want):
    """Catches: a refusal inside a closed lock that does not name the owner's `lock open`, or one that still refuses after the owner opened the target."""
    assert (_outcome(closed), "lock open profile" in core_lock.decide(closed).text, _outcome(opened)) == (want, True, "allow")


def test_a_lock_file_by_session_way_out():
    """Catches: a refusal for a lock file that does not name the owner's `lock open|close`, or one that blocks the session's own source file (way out of lock-file-by-session)."""
    refused = core_lock.decide(_edit("mkway/locks/x.json", CLOSED))
    assert (refused.reason, "lock open|close" in refused.text, _outcome(_edit(SRC, CLOSED))) == (
        "lock-file-by-session", True, "allow")


# ---- the install inputs: the literal path inside the root ----------------------------------------------------------------

@pytest.mark.parametrize("bad, good, want", [
    pytest.param({"profile_inside_root": False}, {"profile_inside_root": True}, "profile-outside-root",
                 id="profile-outside-root"),
    pytest.param({"bundle_inside_root": False}, {"bundle_inside_root": True}, "bundle-outside-root",
                 id="bundle-outside-root"),
    pytest.param({"copy_exists": True, "lock_exists": False}, {"copy_exists": True, "lock_exists": True},
                 "copy-without-lock", id="copy-without-lock"),
])
def test_an_install_input_way_out(bad, good, want):
    """Catches: an install input refused with nothing written that still refuses once the path lies inside the root or the lock sits beside the copy."""
    refused = core_install.decide_install(core_install.InstallFacts(**bad))
    assert (refused.reason, core_install.decide_install(core_install.InstallFacts(**good)).kind) == (want, "allow")


# ---- the build: a committed tree and a green run --------------------------------------------------------------------------

def test_a_built_dirty_way_out(tmp_path):
    """Catches: a build refused for uncommitted changes that still refuses after the commit (way out of built-dirty)."""
    from _mw020 import index_digest
    folder = make_deliverable_root(tmp_path)
    rel = deliverable(folder)
    green(folder)
    work(folder, "src/a.py", "x = 2\n")
    refused = built(folder, rel)
    git(folder, "add", "src/a.py")
    git(folder, "commit", "-q", "-m", "x2")
    green(folder, tree=index_digest(folder))
    assert ("built-dirty" in refused[2], built(folder, rel)[0]) == (True, 0)


def test_a_built_untested_way_out(tmp_path):
    """Catches: a build refused for no green run that still refuses after the tests passed on the tree (way out of built-untested)."""
    from _mw020 import index_digest
    folder = make_deliverable_root(tmp_path)
    rel = deliverable(folder)
    refused = built(folder, rel)
    green(folder, tree=index_digest(folder))
    assert ("built-untested" in refused[2], built(folder, rel)[0]) == (True, 0)
