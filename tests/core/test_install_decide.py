"""Card MW-067: the decisions of install and check, table tests of the pure core (`engine/core_install.py`). No disk, no
git, no process: every row is one case with the verdict written by hand from the card row (T1-T4). The shell that reads
the facts is proven in `tests/shell/test_install_facts.py`."""
import hashlib
import json

import pytest

from _engine import make_profile
import core_install as core

BUNDLE = "mkway"
ROOT = "C:/work/task"
LAUNCH = 'python -I -X utf8 "${CLAUDE_PROJECT_DIR}/mkway/engine/mkway.py" hook '


def _gate(name, group="edit", event="PreToolUse", matcher="Edit|Write", timeout=10, **over):
    e = {"name": name, "gate": name, "group": group, "function": "fixture_gates:always_refuse",
         "reason_ids": ["fixture-refuse"], "event": event, "matcher": matcher, "timeout": timeout, "default_on": True}
    e.update(over)
    return e


TABLE = {"edit": {"onFailure": "block"}, "shell": {"onFailure": "block"}, "start": {}, "stop": {}, "post": {}}


def _entries(gates, profile=None, **kw):
    return core.generate_entries(profile or make_profile(), gates, TABLE, **kw)


# ---- the file set and the hash (E29) ---------------------------------------------------------------------------

@pytest.mark.parametrize("rel", ["mkway.py", "VERSION", "engine/gate.py", "tools/term_scan.py", "tests/_engine.py",
                                 "fixtures/synthetic/fixture_gates.py", "cards/_TEMPLATE/CARD.md",
                                 "cards/_TEMPLATE/ORDER.md", "engine\\gate.py"])
def test_a_set_file_is_copied(rel):
    """E29. Catches: a file of the fixed set (or a backslash spelling of it) left out of the copy."""
    assert core.in_set(rel) is True


@pytest.mark.parametrize("rel", ["cards/REGISTER.md", "pytest.ini", "README.md", ".git/config",
                                 "engine/__pycache__/x.pyc", "engine/a.pyc", ".pytest_tmp/junk/f", "tests/.pytest_cache/v",
                                 "mkway/engine/stray.py"])
def test_a_file_outside_the_set_or_a_cache_is_not_copied(rel):
    """E29. Catches: the repository's register, config, a cache folder or a stray copy riding into the install."""
    assert core.in_set(rel) is False


def test_the_hash_is_sha256_over_path_length_and_bytes_in_path_order():
    """E29, MW-051 E1. Catches: a hash that depends on the order the files were given, or one that ignores length."""
    expected = "sha256:a8eca051b64510e4f82137f9f52c62dddab848d342c5f128657243481396f973"  # a, 1 byte; b, 1 byte
    assert core.files_hash({"b": b"2", "a": b"1"}) == expected


def test_the_hash_leaves_bytecode_and_caches_out():
    """E29 (C26). Catches: a stale bytecode file or a cache folder changing the recorded hash."""
    only_a = "sha256:" + hashlib.sha256(b"a\x001\x001").hexdigest()
    assert core.files_hash({"a": b"1", "engine/x.pyc": b"zz", ".pytest_tmp/t": b"q"}) == only_a


def test_the_hash_of_crlf_bytes_is_of_those_bytes():
    """MW-051 E3. Catches: line ends normalised before hashing, so the lock differs from the disk."""
    crlf = "sha256:" + hashlib.sha256(b"f\x004\x00a\r\nb").hexdigest()
    assert core.files_hash({"f": b"a\r\nb"}) == crlf


def test_the_lock_names_version_semver_sha_date_and_hash_and_no_path():
    """E29, MW-016 E3. Catches: a lock that gains a path or loses `semver`."""
    lock = core.lock_record({"VERSION": b"3.4.5\n", "a": b"1"}, "v0.1.0", "abc123", "2026-11-12")
    assert set(lock) == {"version", "semver", "source_sha", "date", "hash"}
    assert (lock["version"], lock["semver"], lock["source_sha"], lock["date"]) == ("v0.1.0", "3.4.5", "abc123",
                                                                                 "2026-11-12")


def test_the_lock_of_a_folder_source_is_unversioned_with_no_sha():
    """E29. Catches: a made-up tag or sha for a source that has none; a semver for a copy without `VERSION`."""
    lock = core.lock_record({"a": b"1"}, "unversioned", None, "2026-11-12")
    assert (lock["version"], lock["source_sha"], lock["semver"]) == ("unversioned", None, None)


def test_the_lock_hash_is_the_hash_of_the_files():
    """MW-051 E1. Catches: a lock hash computed from anything but the bytes install wrote."""
    lock = core.lock_record({"a": b"1"}, "unversioned", None, "2026-11-12")
    assert lock["hash"] == "sha256:df1190f7f39ade60e708c3d6899036b2e33ada6fed5aa8b54bb4a22e9466f11d"


# ---- hook entries (E31, E63, MW-004 E17 and E18) ------------------------------------------------------------------

def test_the_matcher_of_a_group_is_the_union_of_its_gates_matchers():
    """E31. Catches: the matcher of the first gate only."""
    gates = [_gate("a", matcher="Edit|Write"), _gate("b", matcher="Write|MultiEdit")]
    (edit,) = [e for e in _entries(gates) if e["group"] == "edit"]
    assert edit["matcher"] == "Edit|Write|MultiEdit"


def test_the_timeout_is_the_sum_of_the_gates_timeouts_plus_fifteen():
    """E31 (R13c). Catches: a timeout of the longest gate only, or no margin."""
    gates = [_gate("a", timeout=10), _gate("b", timeout=30)]
    (edit,) = [e for e in _entries(gates) if e["group"] == "edit"]
    assert edit["timeout"] == 55


def test_a_profile_budget_replaces_the_manifest_timeout_of_that_gate():
    """E31. Catches: a budget that is added to the manifest timeout instead of replacing it."""
    gates = [_gate("a", timeout=10), _gate("b", timeout=30)]
    profile = make_profile({"a": {"on": True, "budget_seconds": 3}})
    (edit,) = [e for e in _entries(gates, profile) if e["group"] == "edit"]
    assert edit["timeout"] == 3 + 30 + 15


@pytest.mark.parametrize("budget,seconds", [(-100, 10), (-5, 10), (-4, 11)])
def test_the_timeout_is_never_under_ten_seconds(budget, seconds):
    """E63 (fix check N7); the row (-4, 11) is the nearest allow: 15 - 4 = 11 stands. Catches: a timeout of 0 or a
    negative number written to the settings file."""
    gates = [_gate("a", timeout=10)]
    profile = make_profile({"a": {"on": True, "budget_seconds": budget}})
    (edit,) = [e for e in _entries(gates, profile) if e["group"] == "edit"]
    assert edit["timeout"] == seconds


@pytest.mark.parametrize("group,expected", [("start", None), ("edit", "block"), ("shell", "block"), ("stop", None)])
def test_on_failure_comes_from_the_group_table(group, expected):
    """E31 (R13c). Catches: `onFailure` on a group the table leaves without it, or missing on edit and shell."""
    gates = [_gate("a", group="edit"), _gate("c", group="shell", matcher="Bash"),
             _gate("d", group="stop", event="Stop", matcher=None)]
    found = {e["group"]: e["on_failure"] for e in _entries(gates)}
    assert found[group] == expected


def test_the_start_entry_exists_with_no_gate_on():
    """E31. Catches: no SessionStart entry when only the table's other groups are empty."""
    (start,) = _entries([])
    assert (start["event"], start["group"], start["matcher"], start["timeout"]) == ("SessionStart", "start", None, 15)


def test_the_command_runs_the_copy_through_the_root_launcher():
    """E31 (R111). Catches: a command that needs the user's Python folder or a path not under the project dir."""
    (start,) = _entries([])
    assert start["command"] == LAUNCH + "SessionStart --group start"


def test_a_profile_path_is_appended_to_every_command():
    """E48. Catches: a second install of `--profile conf/p.json` generating entries that drift from the first."""
    (start,) = _entries([], profile_rel="conf/p.json")
    assert start["command"].endswith(' --profile "${CLAUDE_PROJECT_DIR}/conf/p.json"')


def test_the_interpreter_of_the_profile_starts_the_command():
    """MW-027. Catches: the machine's own interpreter written into the committed entries."""
    (start,) = _entries([], make_profile(python={"command": "py -3"}))
    assert start["command"].startswith('py -3 -I -X utf8 "${CLAUDE_PROJECT_DIR}/')


def _agent_gates():
    return [_gate("agent_start", group="post", event="SubagentStart", matcher=None, timeout=10),
            _gate("agent_stop", group="post", event="SubagentStop", matcher=None, timeout=10)]


@pytest.mark.parametrize("event", ["SubagentStart", "SubagentStop"])
def test_each_agent_event_has_a_whole_entry_with_no_matcher_and_no_block(event):
    """MW-004 E17. Catches: an event missing from the install's event order (no entry), a matcher that limits the record
    to one agent type, a `block`."""
    entries = {e["event"]: e for e in _entries(_agent_gates())}
    assert entries[event] == {"event": event, "group": "post", "matcher": None,
                              "command": LAUNCH + f"{event} --group post", "timeout": 25, "on_failure": None}


def test_the_agent_events_come_after_post_tool_use_and_before_stop():
    """MW-004 E17. Catches: an agent entry written before the events it must follow."""
    gates = _agent_gates() + [_gate("p", group="post", event="PostToolUse", matcher="Bash"),
                              _gate("s", group="stop", event="Stop", matcher=None)]
    assert [e["event"] for e in _entries(gates)] == ["SessionStart", "PostToolUse", "SubagentStart", "SubagentStop",
                                                     "Stop"]


@pytest.mark.parametrize("off", ["agent_start", "agent_stop"])
def test_the_gate_switch_drops_that_agent_entry_and_no_other(off):
    """MW-004 E18. Catches: a switch that does one event only, or one that drops the whole `post` group."""
    gates = _agent_gates() + [_gate("p", group="post", event="PostToolUse", matcher="Bash")]
    profile = make_profile({off: {"on": False}})
    other = {"agent_start": "SubagentStop", "agent_stop": "SubagentStart"}[off]
    events = [e["event"] for e in _entries(gates, profile)]
    assert events == ["SessionStart", "PostToolUse", other]


def test_a_gate_that_is_off_by_default_makes_no_entry():
    """E31. Catches: an entry for a gate the manifest leaves off."""
    gates = [_gate("a", default_on=False)]
    assert [e["event"] for e in _entries(gates)] == ["SessionStart"]


# ---- the settings text (E31, MW-004 E19, MW-027 E2 and E3) ----------------------------------------------------------

FOREIGN = {"matcher": "Bash", "hooks": [{"type": "command", "command": "python other_hook.py", "timeout": 5}]}


def _one_entry():
    return [{"event": "SessionStart", "group": "start", "matcher": None, "command": LAUNCH + "SessionStart --group "
             "start", "timeout": 15, "on_failure": None}]


def test_no_settings_file_gives_a_new_one_with_the_hooks_key_only():
    """E31. Catches: a new file that holds anything but the hooks."""
    verdict = core.settings_text(None, _one_entry(), BUNDLE)
    assert json.loads(verdict.out) == {"hooks": {"SessionStart": [
        {"hooks": [{"type": "command", "command": LAUNCH + "SessionStart --group start", "timeout": 15}]}]}}


def test_other_keys_keep_their_bytes_and_a_foreign_hook_stays():
    """E31, MW-027 E2. Catches: a rewrite that reformats `env` or drops a hook mkway does not own."""
    head = '{\n  "env": {"A":   "1"},\n  "permissions": {"allow": ["Read(x)"]},\n'
    text = head + '  "hooks": ' + json.dumps({"PreToolUse": [FOREIGN]}) + "\n}\n"
    out = core.settings_text(text, _one_entry(), BUNDLE).out
    assert out.startswith(head) and FOREIGN in json.loads(out)["hooks"]["PreToolUse"]


def test_a_second_write_changes_nothing():
    """E31, MW-004 E19, MW-027 E2. Catches: a duplicate entry after a reinstall."""
    first = core.settings_text(None, _one_entry(), BUNDLE).out
    assert core.settings_text(first, _one_entry(), BUNDLE).out == first


def test_a_foreign_hook_under_the_same_event_is_kept_beside_the_owned_one():
    """MW-004 E19. Catches: a foreign hook removed, or the owned group written with a `matcher` key."""
    text = json.dumps({"hooks": {"SessionStart": [{"hooks": FOREIGN["hooks"]}]}})
    groups = json.loads(core.settings_text(text, _one_entry(), BUNDLE).out)["hooks"]["SessionStart"]
    assert groups == [{"hooks": FOREIGN["hooks"]}, {"hooks": [{"type": "command", "timeout": 15, "command":
                                                               LAUNCH + "SessionStart --group start"}]}]


def test_a_file_with_no_hooks_key_gets_one_after_the_other_keys():
    """E31. Catches: a file with other keys and no `hooks` refused or its keys lost."""
    out = core.settings_text('{\n  "env": {"A": "1"}\n}\n', _one_entry(), BUNDLE).out
    assert json.loads(out)["env"] == {"A": "1"} and "SessionStart" in json.loads(out)["hooks"]


def test_on_failure_is_written_as_on_failure_key():
    """E31 (R13c). Catches: a documented handler key lost."""
    entry = dict(_one_entry()[0], on_failure="block")
    handler = json.loads(core.settings_text(None, [entry], BUNDLE).out)["hooks"]["SessionStart"][0]["hooks"][0]
    assert handler["onFailure"] == "block"


def test_a_group_carries_only_documented_fields():
    """E31. Catches: an entry key that Claude Code does not document leaking into the file."""
    entry = dict(_one_entry()[0], matcher="Bash", event="PreToolUse", on_failure="block")
    group = json.loads(core.settings_text(None, [entry], BUNDLE).out)["hooks"]["PreToolUse"][0]
    assert set(group) == {"matcher", "hooks"} and set(group["hooks"][0]) == {"type", "command", "timeout", "onFailure"}


def test_no_entries_strips_the_owned_ones_and_keeps_the_owners():
    """MW-027 E3. Catches: the owner's own local hook or key removed by the strip, or an owned entry left to run twice."""
    own = {"matcher": "Bash", "hooks": [{"type": "command", "command": "python mine.py", "timeout": 5}]}
    text = core.settings_text(json.dumps({"permissions": {"allow": ["Read(x)"]}, "hooks": {"PreToolUse": [own]}}),
                              _one_entry(), BUNDLE).out
    data = json.loads(core.settings_text(text, [], BUNDLE).out)
    assert data["permissions"] == {"allow": ["Read(x)"]} and data["hooks"] == {"PreToolUse": [own]}


def test_a_file_that_is_not_json_is_refused_and_named():
    """E31 (C24). Catches: a settings file overwritten when it cannot be read."""
    verdict = core.settings_text("{not json", _one_entry(), BUNDLE)
    assert (verdict.kind, verdict.reason) == ("refuse", "settings-not-json")
    assert verdict.text == "settings.json is not valid JSON (line 1); it was not changed"


def test_hooks_that_is_not_an_object_is_refused():
    """E31 (C24). Catches: a settings file whose `hooks` is a list overwritten."""
    verdict = core.settings_text('{"hooks": []}', _one_entry(), BUNDLE)
    assert (verdict.kind, verdict.reason) == ("refuse", "settings-hooks-not-object")


def test_the_owned_entries_of_a_text_are_read_whole():
    """MW-027 E3. Catches: a read that returns the foreign hook as owned, or loses a field."""
    text = json.dumps({"hooks": {"PreToolUse": [FOREIGN, {"matcher": "Edit", "hooks": [{
        "type": "command", "command": LAUNCH + "PreToolUse --group edit", "timeout": 25, "onFailure": "block"}]}]}})
    assert core.owned_entries(text, BUNDLE) == [{"event": "PreToolUse", "matcher": "Edit", "timeout": 25,
                                                 "command": LAUNCH + "PreToolUse --group edit",
                                                 "on_failure": "block"}]


@pytest.mark.parametrize("text", [None, "{bad", "[]"])
def test_a_text_that_cannot_hold_entries_has_none(text):
    """MW-027 E3. Catches: an exception from a missing or damaged settings file."""
    assert core.owned_entries(text, BUNDLE) == []


# ---- the profile (E30, MW-026) ------------------------------------------------------------------------------------

def test_no_profile_gives_the_starter_with_the_card_prefix_and_no_path():
    """E30. Catches: a starter that names a machine path or another card prefix."""
    plan = core.plan_profile(None, ["(profile): not found"], None, "git", None)
    assert plan.kind == "starter" and plan.profile == {
        "vcs": "git", "bundle": {"root": "mkway"}, "ids": {"card_prefix": "CARD"}, "gates": {},
        "state": {"dir": "mkway/state"}, "python": {"command": "python"},
        "outbox": {"checkers": ["fresh-reader"]}}  # MW-071 E18 (decision: R180): the default checker is the read-only reader


@pytest.mark.parametrize("arg,found,vcs", [("none", "git", "none"), (None, "git", "git"), (None, "none", "none")])
def test_the_starter_vcs_is_the_argument_else_what_the_folder_is(arg, found, vcs):
    """E30. Catches: a folder inside a work tree installed as `none`, or the argument ignored."""
    assert core.plan_profile(None, ["(profile): not found"], None, arg, found).profile["vcs"] == vcs


def test_a_shared_folder_goes_into_a_new_starter():
    """MW-026. Catches: `--shared` dropped when the profile is created."""
    plan = core.plan_profile(None, ["(profile): not found"], "C:/work/shared", "none", None)
    assert plan.profile["state"]["shared_dir"] == "C:/work/shared"


def test_an_existing_valid_profile_stays_as_it_is():
    """E30. Catches: a custom profile overwritten by the starter."""
    custom = make_profile(gates={"x": {"on": False}}, vcs="git", ids={"card_prefix": "QQ"})
    plan = core.plan_profile(custom, [], None, None, "git")
    assert (plan.kind, plan.profile) == ("keep", custom)


def test_an_invalid_profile_is_kept_and_reported():
    """E30 (R64). Catches: an invalid profile rewritten by the engine."""
    plan = core.plan_profile({"vcs": 5}, ["vcs: expected string"], None, None, "git")
    assert plan.kind == "invalid"
    assert core.profile_report(plan, ["vcs: expected string"], None, "mkway/profile.json") == \
        "profile: invalid, kept as it is: vcs: expected string"


def test_a_shared_folder_that_differs_is_written_into_a_copy_of_the_profile():
    """MW-026. Catches: the loaded profile object changed in place, or `--shared` not written."""
    loaded = make_profile()
    plan = core.plan_profile(loaded, [], "C:/work/shared", None, "git")
    assert plan.kind == "shared" and plan.profile["state"]["shared_dir"] == "C:/work/shared"
    assert "shared_dir" not in loaded["state"]


def test_the_same_shared_folder_changes_nothing():
    """MW-026 (the nearest allow). Catches: a rewrite of an unchanged profile."""
    loaded = make_profile(state={"dir": "mkway/state", "shared_dir": "C:/work/shared"})
    assert core.plan_profile(loaded, [], "C:/work/shared", None, "git").kind == "keep"


@pytest.mark.parametrize("kind,line", [("starter", "profile: starter written (mkway/profile.json)"),
                                       ("shared", "profile: state.shared_dir set to D:/s (mkway/profile.json)"),
                                       ("keep", None)])
def test_the_profile_step_reports_what_it_wrote(kind, line):
    """MW-026, E30. Catches: a silent profile write, or a line for a profile that stood."""
    assert core.profile_report(core.ProfilePlan(kind, {}), [], "D:/s", "mkway/profile.json") == line


@pytest.mark.parametrize("profile,arg,found,vcs", [({"vcs": "git"}, "none", "none", "git"),
                                                   ({"vcs": "none"}, "git", "git", "none"),
                                                   ({"vcs": "x"}, "none", "git", "none"),
                                                   ({}, None, "git", "git")])
def test_the_vcs_of_install_is_the_profiles_when_valid(profile, arg, found, vcs):
    """MW-028. Catches: the argument or the folder overriding the profile's own `vcs`."""
    assert core.choose_vcs(profile, arg, found) == vcs


# ---- the refusals (T3: one deny, the nearest allow) ----------------------------------------------------------------

def _decide(**facts):
    return core.decide_install(core.InstallFacts(**facts))


def test_with_no_fact_read_install_is_allowed():
    """The shell asks after each cheap read: an unread fact refuses nothing. Catches: a refusal on a fact never read."""
    assert _decide().kind == "allow"


@pytest.mark.parametrize("shared", ["relative/dir", "state", "C:/work/../shared", "C:rel"])
def test_shared_that_is_not_absolute_is_refused(shared):
    """MW-026. Catches: a relative or climbing `--shared` written into the profile."""
    verdict = _decide(shared=shared)
    assert (verdict.kind, verdict.reason) == ("refuse", "shared-not-absolute")
    assert verdict.text == "--shared must be an absolute path (for example C:/work/shared-state); nothing was written"


@pytest.mark.parametrize("shared", ["C:/work/shared-state", "C:\\work\\shared", "/srv/shared", None])
def test_shared_that_is_absolute_or_unset_is_allowed(shared):
    """MW-026 (the nearest allow). Catches: a valid drive or root path refused."""
    assert _decide(shared=shared).kind == "allow"


def test_a_profile_outside_the_root_is_refused():
    """E49. Catches: a write of the profile outside the task folder."""
    verdict = _decide(profile_inside_root=False)
    assert (verdict.reason, verdict.text) == ("profile-outside-root",
                                              "the profile path leads outside the root; nothing was written")


def test_a_profile_inside_the_root_is_allowed():
    """E49 (the nearest allow). Catches: every profile path refused."""
    assert _decide(profile_inside_root=True).kind == "allow"


def test_the_shared_check_comes_before_the_profile_path_check():
    """E49. Catches: the order of the first two refusals changed (the owner sees the shared error first)."""
    assert _decide(shared="rel", profile_inside_root=False).reason == "shared-not-absolute"


def test_a_starter_the_schema_refuses_is_not_written():
    """E30 (C53, R64). Catches: an engine that writes a profile its own schema refuses."""
    verdict = _decide(kind="starter", candidate_errors=("vcs: expected string",))
    assert (verdict.reason, verdict.text) == ("starter-invalid", "the starter profile would be invalid: vcs: "
                                              "expected string; nothing was written")


def test_a_starter_the_schema_takes_is_allowed():
    """E30 (the nearest allow). Catches: every starter refused."""
    assert _decide(kind="starter", candidate_errors=()).kind == "allow"


def test_shared_into_an_invalid_profile_is_refused():
    """MW-026. Catches: `--shared` written into a profile that is already broken."""
    verdict = _decide(kind="invalid", shared="C:/s", load_errors=("a: x", "b: y"))
    assert (verdict.reason, verdict.text) == ("profile-invalid-shared", "the profile is invalid, so --shared cannot be "
                                              "written into it: a: x; b: y; nothing was written")


def test_an_invalid_profile_without_shared_is_allowed_and_kept():
    """MW-026 (the nearest allow). Catches: an invalid profile blocking an install that does not touch it."""
    assert _decide(kind="invalid", shared=None, load_errors=("a: x",)).kind == "allow"


def test_shared_that_makes_the_profile_invalid_is_refused():
    """MW-026 (C53). Catches: a profile with `--shared` written although the schema refuses it."""
    verdict = _decide(kind="shared", shared="C:/s", candidate_errors=("state.shared_dir: bad",))
    assert (verdict.reason, verdict.text) == ("shared-profile-invalid", "the profile with --shared would be invalid: "
                                              "state.shared_dir: bad; nothing was written")


def test_shared_that_keeps_the_profile_valid_is_allowed():
    """MW-026 (the nearest allow). Catches: every `--shared` refused."""
    assert _decide(kind="shared", shared="C:/s", candidate_errors=()).kind == "allow"


def test_only_five_errors_are_named():
    """E30. Catches: a refusal line that lists every error of a large profile."""
    errors = tuple(f"e{n}: x" for n in range(8))
    assert _decide(kind="starter", candidate_errors=errors).text.count(": x") == 5


def test_commit_without_git_is_refused():
    """MW-027 E6. Catches: `--commit` run in a folder with no repository."""
    verdict = _decide(commit=True, vcs_now="none")
    assert (verdict.reason, verdict.text) == ("commit-needs-git",
                                              "--commit needs vcs git (the profile says none); nothing was written")


@pytest.mark.parametrize("commit,vcs", [(True, "git"), (False, "none"), (False, "git")])
def test_commit_with_git_or_no_commit_is_allowed(commit, vcs):
    """MW-027 E6 (the nearest allow). Catches: `--commit` refused with git, or an install without it refused."""
    assert _decide(commit=commit, vcs_now=vcs).kind == "allow"


def test_a_bundle_that_leads_outside_the_root_is_refused_by_name():
    """E50. Catches: a copy written through a link or junction to a folder outside the root."""
    verdict = _decide(bundle="mkway", bundle_inside_root=False)
    assert (verdict.reason, verdict.text) == ("bundle-outside-root", "mkway leads outside the root (a link or a "
                                              "junction); nothing was written")


def test_a_bundle_inside_the_root_is_allowed():
    """E50 (the nearest allow). Catches: every bundle refused."""
    assert _decide(bundle_inside_root=True).kind == "allow"


def test_a_python_that_is_not_an_interpreter_is_refused():
    """E59. Catches: a shell character or a missing program written into every hook command."""
    verdict = _decide(python_ok=False)
    assert verdict.reason == "python-not-interpreter" and verdict.text.endswith("nothing was written")
    assert verdict.text.startswith("--python must name an existing Python 3.9 or later")


def test_a_python_that_answered_is_allowed():
    """E59 (the nearest allow). Catches: every interpreter refused."""
    assert _decide(python_ok=True).kind == "allow"


def test_a_source_with_no_engine_file_is_refused():
    """E29. Catches: an install that writes an empty copy and a lock for it."""
    verdict = _decide(source_files=0)
    assert (verdict.reason, verdict.text) == ("source-empty", "the source holds none of the engine's files")


def test_a_source_with_one_file_is_allowed():
    """E29 (the nearest allow). Catches: a one-file source refused."""
    assert _decide(source_files=1).kind == "allow"


def test_a_copy_with_no_lock_is_not_replaced():
    """E50. Catches: a folder that is not an install of ours deleted by a re-install."""
    verdict = _decide(bundle="mkway", copy_exists=True, lock_exists=False)
    assert (verdict.reason, verdict.text) == ("copy-without-lock", "mkway/engine exists and has no mkway.lock beside "
                                              "it; it was not changed")


@pytest.mark.parametrize("copy,lock", [(True, True), (False, False)])
def test_a_copy_with_its_lock_or_no_copy_is_allowed(copy, lock):
    """E50 (the nearest allow). Catches: a reinstall refused, or a first install refused."""
    assert _decide(copy_exists=copy, lock_exists=lock).kind == "allow"


@pytest.mark.parametrize("bad", ["x", 5])
def test_a_verdict_kind_must_be_known(bad):
    """The verdict is data. Catches: a misspelt kind passing as an allow."""
    with pytest.raises(ValueError):
        core.Verdict(kind=bad)


def test_a_refusal_needs_a_reason_and_a_text():
    """The verdict is data. Catches: a refusal the shell cannot show."""
    with pytest.raises(ValueError):
        core.Verdict(kind="refuse")


# ---- the interpreter (E59) -------------------------------------------------------------------------------------

@pytest.mark.parametrize("text,parsed", [("python", ("python", None)), ("py -3", ("py", "-3")),
                                         ("py -3.12", ("py", "-3.12")), ("py.exe -3", ("py.exe", "-3")),
                                         ('"C:/Program Files/Py/python.exe"', ("C:/Program Files/Py/python.exe", None)),
                                         ("C:/Py/python.exe", ("C:/Py/python.exe", None)),
                                         ('"C:/Windows/py.exe" -3', ("C:/Windows/py.exe", "-3"))])
def test_an_interpreter_text_that_is_one_program_and_maybe_a_launcher_flag_parses(text, parsed):
    """E59, MW-063 (the nearest allows). Catches: a quoted path with a space, or the launcher's version flag, refused."""
    assert core.interpreter_syntax(text) == parsed


@pytest.mark.parametrize("text", ["exit 0 || python", "python; echo x", "$(python)", "python -c 1", "py -c 1",
                                  "py -3 -3", "py -3 -c 1", "py --3", '"C:/x/python.exe" -3', "", "a b c", None, 7])
def test_an_interpreter_text_with_a_shell_character_or_a_stray_flag_is_invalid(text):
    """E59 (fix checks N2, L3). Catches: shell text, a second flag or a flag after a program that is not the launcher
    written into every hook command."""
    assert core.interpreter_syntax(text) is None


@pytest.mark.parametrize("text", ['"C:/a$b/python"', '"C:/a`b/python"', '"C:/a%b/python"', '"C:/a!b/python"',
                                  '"C:/a\\"'])
def test_a_quoted_program_with_a_shell_character_is_invalid(text):
    """E59 (fix check 3). Catches: a quoted path that still carries `$`, a backtick, `%`, `!` or a trailing backslash."""
    assert core.interpreter_syntax(text) is None


@pytest.mark.parametrize("code,out", [(0, "(3, 9)\n"), (0, "(3, 10)"), (0, "(4, 0)")])
def test_a_probe_that_reports_python_3_9_or_later_is_accepted(code, out):
    """E59 (M1), the boundary (3, 9) and a later one. Catches: the lowest supported Python refused."""
    assert core.version_answer_ok(code, out) is True


@pytest.mark.parametrize("code,out", [(0, "(3, 8)"), (0, "hello"), (0, ""), (1, "(3, 12)"), (0, None)])
def test_a_probe_that_is_older_silent_or_failed_is_rejected(code, out):
    """E59 (M1). Catches: a program that prints something else, an older Python, or a failing one, accepted."""
    assert core.version_answer_ok(code, out) is False


# ---- the ignore and attributes files (E30, E67, E72, MW-027, MW-035, MW-041) --------------------------------------------

def _lines(text):
    return [x for x in text.splitlines() if x and not x.startswith("#")]


def test_a_new_ignore_file_names_exactly_the_runtime_lines():
    """E67, MW-027 E1. Catches: `engine/`, `cards/`, `ledger/` or the profile ignored, or a run-time line missing."""
    text, report = core.ignore_plan("", BUNDLE)
    assert _lines(text) == ["locks/", "state/", "__pycache__/", "*.pyc", ".pytest_tmp/", ".pytest_cache/"]
    assert report == []


def test_a_second_pass_over_the_ignore_file_changes_nothing():
    """E67. Catches: a duplicated line on every reinstall."""
    text, _ = core.ignore_plan("", BUNDLE)
    assert core.ignore_plan(text, BUNDLE) == (text, [])


def test_the_stale_engine_line_goes_and_lookalikes_stay():
    """MW-035 E1. Catches: `engine/cache/` or `engine.log` removed with it, a copy left untracked."""
    text, report = core.ignore_plan("engine/\nlocks/\nmine.tmp\nengine/cache/\nengine.log\n", BUNDLE)
    assert "engine/" not in text.splitlines()
    assert {"locks/", "mine.tmp", "engine/cache/", "engine.log", "state/"} <= set(text.splitlines())
    assert report == ["ignore: removed engine/ (from an earlier install)"]


@pytest.mark.parametrize("stale", ["/engine/\r\n", "engine\r\n", "  engine/ \r\n"])
def test_every_crlf_spelling_of_the_engine_line_is_removed_and_the_file_stays_crlf(stale):
    """MW-041 E4. Catches: a spelling the removal misses; bare LF lines written into a Windows file."""
    text, _report = core.ignore_plan(stale + "mine.tmp\r\n", BUNDLE)
    assert [x for x in text.splitlines() if x.strip(" /") == "engine"] == []
    assert "mine.tmp" in text.splitlines() and text.count("\n") == text.count("\r\n")


@pytest.mark.parametrize("stale", ["/engine/\n", "engine\n"])
def test_every_lf_spelling_of_the_engine_line_is_removed_and_the_file_stays_lf(stale):
    """MW-041 E4. Catches: a spelling the removal misses; CR written into a Unix file."""
    text, _report = core.ignore_plan(stale + "mine.tmp\n", BUNDLE)
    assert [x for x in text.splitlines() if x.strip(" /") == "engine"] == []
    assert "mine.tmp" in text.splitlines() and "\r" not in text


def test_a_crlf_file_loses_the_engine_line_and_keeps_every_crlf():
    """MW-041 E3. Catches: bare LF lines written into a Windows `.gitignore`."""
    text, report = core.ignore_plan("engine/\r\nlocks/\r\nmine.tmp\r\nengine/cache/\r\nengine.log\r\n", BUNDLE)
    assert text.count("\n") == text.count("\r\n") and "engine/" not in text.splitlines()
    assert report == ["ignore: removed engine/ (from an earlier install)"]


@pytest.mark.parametrize("old,named", [("cards/\nledger/\n", "cards/, ledger/"), ("ledger/\n", "ledger/"),
                                       ("cards/\n", "cards/")])
def test_an_earlier_installs_cards_and_ledger_lines_are_named_not_removed(old, named):
    """E72 (C36). Catches: a check that fires only when `cards/` is present, or only when both are; a line deleted."""
    text, report = core.ignore_plan(old, BUNDLE)
    assert report == [f"ignore: mkway/.gitignore still ignores {named} from an earlier install; remove those lines: "
                      "cards and ledger are tracked (R18)"]
    assert set(old.splitlines()) <= set(text.splitlines())


def test_a_clean_ignore_file_has_no_line_about_cards_or_ledger():
    """E72 (the nearest allow). Catches: a report line on a fresh install."""
    assert core.ignore_plan("locks/\nstate/\n", BUNDLE)[1] == []


def test_an_ignore_file_without_a_last_line_end_keeps_its_last_line():
    """E30. Catches: the last line glued to the first added one."""
    text, _ = core.ignore_plan("mine.tmp", BUNDLE)
    assert text.splitlines()[0] == "mine.tmp"


def test_the_attributes_file_gets_the_register_and_engine_lines_and_keeps_others():
    """MW-003 E19, MW-027 E8. Catches: a register converted on a Windows clone, or a copy hash changed by autocrlf."""
    text = core.attributes_text("*.png binary\n")
    assert text.splitlines()[0] == "*.png binary"
    assert {"cards/REGISTER.md -text", "engine/** -text"} <= set(text.splitlines())


# ---- the commit step (MW-027 E5, MW-035, MW-036, MW-041) -----------------------------------------------------------

@pytest.mark.parametrize("prefix,message", [("", "mkway 0.3.1: install"), (None, "mkway 0.3.1: install"),
                                            ("#10536", "#10536 mkway 0.3.1: install")])
def test_the_install_message_starts_with_the_prefix_when_set(prefix, message):
    """MW-035 E4. Catches: a prefix lost, or a leading space when none is set."""
    assert core.commit_message(prefix, "0.3.1") == message


def test_the_install_paths_of_a_first_run_end_with_the_profile():
    """MW-036 E2, MW-035 E3. Catches: the profile left out of the commit of the run that created it."""
    present = {".gitignore", ".gitattributes", "mkway.lock", "engine"}
    assert core.install_paths(BUNDLE, present, "mkway/profile.json") == [
        ".claude/settings.json", "mkway/.gitignore", "mkway/.gitattributes", "mkway/mkway.lock", "mkway/engine",
        "mkway/profile.json"]


def test_the_install_paths_of_a_reinstall_leave_the_profile_out():
    """MW-036 E2. Catches: the owner's profile committed by every reinstall."""
    present = {".gitignore", ".gitattributes", "mkway.lock", "engine"}
    assert core.install_paths(BUNDLE, present, None) == [
        ".claude/settings.json", "mkway/.gitignore", "mkway/.gitattributes", "mkway/mkway.lock", "mkway/engine"]


def test_the_install_paths_never_name_the_bundle_folder():
    """MW-036 E1. Catches: a plain `mkway` path that takes a lead's ask or an edited card into the commit."""
    present = {".gitignore", ".gitattributes", "mkway.lock", "engine"}
    assert "mkway" not in core.install_paths(BUNDLE, present, "mkway/profile.json")


def test_a_file_install_did_not_write_is_not_named():
    """MW-036. Catches: a pathspec for a missing file, which makes git refuse the whole commit."""
    assert core.install_paths(BUNDLE, {"mkway.lock"}, None) == [".claude/settings.json", "mkway/mkway.lock"]


def test_the_printed_line_is_one_line_with_the_root_in_both_commands():
    """MW-041 E1, MW-035 E3. Catches: a line that works only from the task folder, or one that starts with a space."""
    line = core.commit_line("", "0.3.1", [".claude/settings.json", "mkway/engine"], ROOT)
    assert line == ('git -C "C:/work/task" add .claude/settings.json mkway/engine; git -C "C:/work/task" commit -m '
                    '"mkway 0.3.1: install" -- .claude/settings.json mkway/engine')


def test_the_printed_line_keeps_a_root_with_a_space_in_quotes():
    """MW-041 E2. Catches: a root with a space split into two words by the shell."""
    line = core.commit_line("", "0.3.1", ["a"], "C:/my work/task")
    assert line.count('git -C "C:/my work/task" ') == 2 and "\n" not in line


def test_the_printed_line_carries_the_message_prefix():
    """MW-035 E4. Catches: a prefix missing from the pasted line while the `--commit` message has it."""
    assert ' commit -m "#10536 mkway 0.3.1: install" -- a' in core.commit_line("#10536", "0.3.1", ["a"], ROOT)


# ---- check (MW-025, MW-016, MW-051 E4) ---------------------------------------------------------------------------

FAIL = "FAILED t/test_a.py::test_one - assert False\nFAILED t/test_a.py::test_two - assert False\n"


def test_the_failing_tests_are_named():
    """MW-025 E3. Catches: a count with no names."""
    assert core.failed_names(FAIL) == "; failed: t/test_a.py::test_one, t/test_a.py::test_two"


def test_errors_are_named_like_failures():
    """MW-025 E3. Catches: a collection error that leaves the line without a name."""
    assert core.failed_names("ERROR t/test_b.py::test_x - boom\n") == "; failed: t/test_b.py::test_x"


def test_a_name_listed_twice_is_named_once():
    """MW-025 E3. Catches: a name repeated for a FAILED and an ERROR row."""
    assert core.failed_names("FAILED a::t - x\nERROR a::t - y\n") == "; failed: a::t"


def test_twelve_failures_name_ten_and_count_the_rest():
    """MW-025 E4. Catches: a line with all twelve, or without how many more."""
    out = "".join(f"FAILED f.py::test_f{n:02d} - x\n" for n in range(12))
    text = core.failed_names(out)
    assert text.endswith("test_f09 and 2 more") and "test_f10" not in text


def test_exactly_ten_failures_have_no_more_clause():
    """MW-025 E4 (the nearest allow). Catches: `and 0 more` or a cut at nine."""
    out = "".join(f"FAILED f.py::test_f{n:02d} - x\n" for n in range(10))
    assert core.failed_names(out).endswith("test_f09")


@pytest.mark.parametrize("out", ["", "no tests ran", None])
def test_a_run_with_no_failed_row_names_nothing(out):
    """MW-025. Catches: a stray `; failed: ` for a crash before collection."""
    assert core.failed_names(out) == ""


def test_the_tests_line_counts_a_green_run():
    """E33. Catches: a green run reported as not green, or with the wrong count."""
    assert core.tests_line(0, "...\n1 passed in 0.2s\n") == ("tests: 1 passed", True)


def test_the_tests_line_of_a_red_run_names_the_summary_and_the_tests():
    """MW-025 E3. Catches: a red run that does not fail the check, or that hides which tests failed."""
    out = FAIL + "2 failed in 0.1s\n"
    assert core.tests_line(1, out) == ("tests: not green (2 failed in 0.1s); failed: t/test_a.py::test_one, "
                                      "t/test_a.py::test_two", False)


def test_a_run_with_no_output_is_not_green():
    """MW-025. Catches: an exception on empty output."""
    assert core.tests_line(2, "") == ("tests: not green (no output)", False)


def test_a_matching_hash_passes_the_check():
    """E33, MW-051 E4. Catches: a matching copy reported as drift."""
    assert core.hash_line({"hash": "h1"}, "h1") == ("copy hash: matches the lock", True)


def test_a_changed_copy_fails_the_check_and_names_the_fix():
    """E33, MW-051 E4. Catches: one changed byte that goes unseen."""
    assert core.hash_line({"hash": "h1"}, "h2") == ("copy hash: differs from the lock (fix: mkway install)", False)


def test_no_lock_fails_the_check_and_names_the_fix():
    """E33. Catches: a missing lock treated as a match."""
    assert core.hash_line(None, None) == ("copy hash: no lock (fix: mkway install)", False)


def test_no_version_file_gives_no_tag_line():
    """MW-016 E4. Catches: a line for a root that has no `VERSION`."""
    assert core.version_tag_line(None, False, ["v1"]) is None


def test_a_missing_tag_is_a_warning_naming_the_expected_tag():
    """MW-016 E4. Catches: a missing tag passing silently, or a check that writes the tag."""
    assert core.version_tag_line("0.1.0\n", False, []) == (
        "version tag: warning: the tag v0.1.0 is missing at HEAD; the owner tags the release (check never writes "
        "one)")


def test_a_different_tag_is_a_warning_naming_both():
    """MW-016 E4. Catches: a tag that is not `v<version>` accepted."""
    assert core.version_tag_line("0.1.0\n", False, ["v0.0.9"]) == (
        "version tag: warning: HEAD is tagged v0.0.9, which differs from VERSION (v0.1.0); the owner tags the release")


def test_the_right_tag_among_others_matches():
    """MW-016 E4 (the nearest allow). Catches: the right tag refused when another tag sits at HEAD too."""
    assert core.version_tag_line("0.1.0\n", False, ["v0.0.9", "v0.1.0"]) == \
        "version tag: v0.1.0 at HEAD matches VERSION"


def test_inside_a_claude_chat_the_tags_are_not_compared():
    """MW-016 E4. Catches: a tag read in a chat shell, where the owner's terminal is the only place."""
    assert core.version_tag_line("0.1.0\n", True, None) == (
        "version tag: not compared inside a Claude chat (run `mkway check` in your own terminal)")


def test_a_git_that_did_not_answer_is_said_so():
    """MW-016 E4. Catches: a silent line, or a missing-tag warning when git never answered."""
    assert core.version_tag_line("0.1.0\n", False, None) == "version tag: not compared (git did not answer)"
