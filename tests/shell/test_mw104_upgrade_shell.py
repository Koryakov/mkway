"""Card MW-104: the upgrade shell on real small git repositories (rows E43 to E74 carry the mkup case table of spec section 8;
E83 to E96 are release mode and the downgrade guard). Every test builds its own engine repository (a stub engine whose install
and ledger commands write small files and print the real line shapes) and its own customer repository under tmp_path;
`_mw104.hermetic` points the upgrade folder, the app data folders, the home and git's config there too. The real engine
is proven end to end in `tests/test_mw104_upgrade_e2e.py`. Synthetic files only."""
import json
import os
from pathlib import Path

import pytest

import _mw104
from _mw104 import World, git, out


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch, tmp_path):
    _mw104.hermetic(monkeypatch, tmp_path)


def standard(tmp_path, **kw):
    world = World(tmp_path)
    a, b = world.standard(**kw)
    return world, a, b


def refused(world, **kw):
    """Run the upgrade and return (code, result, state before, state after)."""
    before = world.tree_state()
    code, res = world.run(**kw)
    return code, res, before, world.tree_state()


def last_ledger_row(world, root="app"):
    rows = [json.loads(x) for x in (world.target / root / "mkway" / "ledger" / "ledger.md").read_text(encoding="utf-8")
            .splitlines() if x.startswith("{")]
    return rows[-1]


def narrow_world(tmp_path, *, narrow_files, extra=()):
    """Commit A (full-green, installed) and a narrow-merged commit on top that changes `narrow_files`."""
    world = World(tmp_path)
    a = world.commit("A", version="0.1.0", files={"cards/a.md": "a\n"}, tag=None)
    world.green(a)
    world.install_at("A")
    n1 = world.commit("N1", version="0.1.0", files=narrow_files)
    world.green(n1, kind="narrow", frm=a)
    world.grant()
    return world, a, n1


# ---- 8a: the update ----------------------------------------------------------------------------------------------------------

def test_a_proven_release_updates_with_one_commit(tmp_path):
    """Catches: an update that commits more or less than the printed paths and the ledger, loses a staged file of someone else, records no ledger row by the tool, leaks the session marker, or drops --shared."""
    world = World(tmp_path)
    a, b = world.standard(profile={"commit": {"message_prefix": "TT-1"}})
    world.grant(shared=str(tmp_path / "shared"))
    (world.target / "other.txt").write_text("other\n", encoding="utf-8")
    git(world.target, "add", "other.txt")
    before = world.customer_head()
    code, res = world.run()
    assert code == 0, res
    assert res["ok"] is True
    assert res["updated"] is True
    assert res["release"] == "v0.0.2"
    assert res["newSha"] == b
    assert res["message"] == "TT-1 mkway install " + b[:8]
    assert world.customer_subjects(2) == [res["message"], "customer install A"]
    assert out(world.target, "rev-parse", "HEAD~1") == before
    assert sorted(world.files_of("HEAD")) == ["app/.claude/settings.json", "app/mkway/engine/mkway.py",
                                              "app/mkway/ledger/ledger.md", "app/mkway/mkway.lock"]
    assert {".claude/settings.json", "mkway/.gitignore", "mkway/.gitattributes"} <= set(res["files"])
    assert out(world.target, "diff", "--cached", "--name-only") == "other.txt"
    assert world.lock()["source_sha"] == b
    row = last_ledger_row(world)
    assert row["by"] == "tool:mkway-upgrade"
    assert row["source"] == "mkway upgrade"
    assert row["topic"] == "engine update"
    assert row["claudecode"] is False
    assert row["quote"] == f"engine updated {a[:8]} -> {b[:8]}, grant policy.json, dry run ok, release v0.0.2, upgrade dir {world.cfg}"
    args = json.loads((world.root / "mkway" / "state" / "ARGS.json").read_text(encoding="utf-8"))
    assert args["claudecode"] is False
    assert args["argv"][0:2] == ["install", "--from"]
    assert Path(args["argv"][2]) == world.engine.resolve()
    assert args["argv"][3:6] == ["--ref", b, "--root"]
    assert Path(args["argv"][6]) == world.root.resolve()
    assert args["argv"][7:] == ["--shared", str(tmp_path / "shared")]
    assert Path(args["cwd"]) == world.root.resolve()


def test_no_commit_prefix_gives_a_plain_message(tmp_path):
    """Checks: a profile with no commit prefix gives the message `mkway install <sha8>` and the test command of release.json is a list (row 2)."""
    world, _a, b = standard(tmp_path)
    code, res = world.run()
    assert code == 0, res
    assert res["message"] == "mkway install " + b[:8]


@pytest.mark.parametrize("grant_text, part", [
    pytest.param(None, "There is no grant: ", id="03-no-grant-file"),
    pytest.param("{", "policy.json is invalid: not valid JSON (", id="03-unparseable-grant"),
    pytest.param('{"target": "TARGET", "root": "app", "targets": 1}', 'policy.json is invalid: unknown key "targets"',
                 id="03-unknown-key"),
])
def test_a_missing_or_bad_grant_is_refused_and_logged(tmp_path, grant_text, part):
    """Catches: a missing, unparseable or unknown-key grant that does not refuse before anything changes, or whose refusal is not logged."""
    world, _a, _b = standard(tmp_path)
    world.grant_file.unlink() if grant_text is None else world.grant_file.write_text(
        (grant_text or "").replace("TARGET", json.dumps(str(world.target))[1:-1]), encoding="utf-8")
    code, res, before, after = refused(world)
    assert code == 1
    assert res["ok"] is False
    assert part in res["error"]
    assert after == before if grant_text is not None else after[:2] == before[:2]
    assert world.log()[-1]["event"] == "refused"


@pytest.mark.parametrize("which, part", [
    pytest.param("", "target is required", id="04-empty"),
    pytest.param("relative/dir", "target must be a full path.", id="04-relative"),
    pytest.param("COPY", "is not the target the policy names", id="04-a-builder-copy"),
    pytest.param("SUB", "is not the target the policy names", id="04-a-subfolder"),
])
def test_a_target_that_is_not_the_grants_is_refused(tmp_path, which, part):
    """Catches: a target that is empty, relative, a copy or a subfolder of the granted one and is updated anyway."""
    world, _a, _b = standard(tmp_path)
    target = {"COPY": str(tmp_path / "customer-copy"), "SUB": str(world.root)}.get(which, which)
    code, res, before, after = refused(world, target=target)
    assert code == 1
    assert part in res["error"]
    assert after == before


def test_a_target_with_a_trailing_separator_is_accepted(tmp_path):
    """Checks: the nearest allow of the target refusals: the granted folder with a trailing separator is the same folder."""
    world, _a, _b = standard(tmp_path)
    code, res = world.run(target=str(world.target) + os.sep, dry_run=True)
    assert code == 0, res
    assert res["ok"] is True


@pytest.mark.parametrize("name", [pytest.param("ghost", id="05-root-folder-missing"), pytest.param("bare", id="05-no-lock")])
def test_a_missing_lock_or_root_is_refused(tmp_path, name):
    """Catches: a listed root that has no installed engine (no folder, or a folder with no mkway.lock) that is updated anyway."""
    world, _a, _b = standard(tmp_path)
    (world.target / "bare").mkdir()
    world.grant(roots=["app", "bare", "ghost"], root=None)
    code, res, before, after = refused(world, root=name)
    assert code == 1
    assert "mkway.lock" in res["error"]
    assert after == before


def _unproven(tmp_path, row_kwargs):
    """Commit A (green, installed) and HEAD commit B with the given green row only (None: no row at all)."""
    world = World(tmp_path)
    a = world.commit("A", version="0.1.0", tag="v0.0.1")
    world.green(a)
    world.install_at("A")
    b = world.commit("B", version="0.1.1")
    if row_kwargs is not None:
        world.green(b, **row_kwargs)
    world.grant()
    return world


@pytest.mark.parametrize("row_kwargs", [
    pytest.param(None, id="06-no-row"),
    pytest.param({"command": "python -m pytest -k fast"}, id="06-another-command"),
    pytest.param({"command": "python -m pytest --deselect tests/test_x.py"}, id="06-a-command-that-deselects-tests"),
    pytest.param({"repo": "ELSEWHERE"}, id="06-another-repository"),
    pytest.param({"into": "dev"}, id="06-another-branch"),
    pytest.param({"kind": "narrow", "frm": "1" * 40}, id="06-a-narrow-row-alone"),
])
def test_a_head_without_a_proving_green_row_is_refused(tmp_path, row_kwargs):
    """Catches: an engine head accepted on a green row that is another sha, repository, branch or command, or that is only narrow with no full-green head."""
    row_kwargs = None if row_kwargs is None else {**row_kwargs, **({"repo": str(tmp_path / "elsewhere")}
                                                                    if row_kwargs.get("repo") else {})}
    world = _unproven(tmp_path, row_kwargs)
    code, res, before, after = refused(world, from_head=True)
    assert code == 1
    assert res["error"].startswith("No green record in ")
    assert "Nothing was changed." in res["error"]
    assert after == before


@pytest.mark.parametrize("how, part", [
    pytest.param("dirty", "is not clean (1 changed or untracked files). Nothing was changed.", id="07-dirty"),
    pytest.param("branch", "is not on branch main (it is on other).", id="07-another-branch"),
])
def test_a_dirty_engine_or_another_branch_is_refused(tmp_path, how, part):
    """Catches: an engine repository with changes or on another branch than release.json names that is installed from."""
    world, _a, _b = standard(tmp_path)
    (world.engine / "junk.txt").write_text("x", encoding="utf-8") if how == "dirty" else git(world.engine, "checkout", "-q", "-b", "other")
    code, res, before, after = refused(world)
    assert code == 1
    assert part in res["error"]
    assert after == before


def test_a_lock_at_the_chosen_sha_is_up_to_date(tmp_path):
    """Checks: a lock whose source is the chosen release is up to date: the log has update and update-result and nothing changes (row 8)."""
    world = World(tmp_path)
    a = world.commit("A", version="0.1.0", tag="v0.0.1")
    world.green(a)
    world.install_at("A")
    world.grant()
    before = world.tree_state()
    code, res = world.run()
    assert code == 0, res
    assert res["upToDate"] is True
    assert res["updated"] is False
    assert res["summary"] == f"The engine in {Path(res['target'])} is up to date ({a[:8]})."
    assert [row["event"] for row in world.log()] == ["update", "update-result"]
    assert world.log()[-1]["upToDate"] is True
    assert world.tree_state() == before


def test_a_new_major_is_refused(tmp_path):
    """Catches: an engine release of a new major version that is installed over an older major."""
    world = World(tmp_path)
    a = world.commit("A", version="0.1.0", tag="v0.0.1")
    world.green(a)
    world.install_at("A")
    b = world.commit("B", version="1.0.0", tag="v1.0.0")
    world.green(b)
    world.grant()
    code, res, before, after = refused(world)
    assert code == 1
    assert res["error"] == "The engine is on major version 1 and the install is on 0. A new major is the owner's hand; nothing was changed."
    assert after == before


@pytest.mark.parametrize("how, part", [
    pytest.param("modified", "(1)", id="10-modified"),
    pytest.param("untracked", "?? app/mkway/engine/new.txt", id="10-untracked"),
])
def test_changes_in_an_install_path_are_refused_before_a_write(tmp_path, how, part):
    """Catches: an update over someone else's changes in an install path (modified or untracked), or one that writes before it checks."""
    world, a, _b = standard(tmp_path)
    (world.root / ".claude" / "settings.json").write_text("{}\n", encoding="utf-8") if how == "modified" else (
        world.root / "mkway" / "engine" / "new.txt").write_text("n\n", encoding="utf-8")
    before = world.tree_state()
    code, res = world.run()
    assert code == 1
    assert "The install paths already have changes that are not this update's " in res["error"]
    assert part in res["error"]
    assert world.tree_state() == before
    assert world.lock()["source_sha"] == a


def test_a_dry_run_changes_nothing_and_lists_checks_and_commands(tmp_path):
    """Checks: a dry run returns every check and the exact commands, writes only the plan line of the log, and leaves the customer repository, the grant and the temp folder as they were (row 11)."""
    world, _a, b = standard(tmp_path)
    before = world.tree_state()
    code, res = world.run(dry_run=True)
    assert code == 0, res
    assert res["updated"] is False
    assert res["newSha"] == b
    assert [c["check"][:6] for c in res["checks"]][:2] == ["policy", "target"]
    assert len(res["commands"]) == 4
    assert "install --from" in res["commands"][0]
    assert "--ref " + b in res["commands"][0]
    assert "ledger add" in res["commands"][1]
    assert "--by tool:mkway-upgrade" in res["commands"][1]
    assert world.tree_state() == before
    assert [row["event"] for row in world.log()] == ["update"]
    assert list((tmp_path / "hermetic" / "tmp").iterdir()) == []


def test_a_ledger_command_without_by_is_refused(tmp_path):
    """Catches: an update by a release whose ledger command has no --by option, found only after the install has written files (row 12)."""
    world = World(tmp_path)
    a = world.commit("A", version="0.1.0", tag="v0.0.1")
    world.green(a)
    world.install_at("A")
    b = world.commit("B", version="0.1.1", tag="v0.0.2", mode="nobyledger")
    world.green(b)
    world.grant()
    code, res, before, after = refused(world)
    assert code == 1
    assert "has no --by option" in res["error"]
    assert after == before


@pytest.mark.parametrize("mode, hook, part", [
    pytest.param("fail", False, "install failed (exit 3): install broke", id="13-install-fails"),
    pytest.param("hang", False, "install failed (timed out):", id="13-install-times-out"),
    pytest.param("unsafe", False, 'install printed an unsafe path ("../escape.txt"), so nothing was committed.', id="13-unsafe-path"),
    pytest.param("noline", False, "its commit line was not found in its output", id="13-no-commit-line"),
    pytest.param("badmsg", False, "has an unknown form, so the commit prefix is not known.", id="13-unknown-message"),
    pytest.param("ledgerfail", False, "the ledger row was not written (ledger broke).", id="ledger-fails"),
    pytest.param("ok", True, "git commit failed:", id="commit-fails"),
])
def test_a_failing_install_commits_nothing(tmp_path, monkeypatch, mode, hook, part):
    """Catches: a failed install, an unsafe or missing commit line, a failed ledger row or a failed commit that still leaves a commit, or an answer that does not say files may have been written."""
    import upgrade
    monkeypatch.setattr(upgrade, "INSTALL_TIMEOUT", 3)
    world = World(tmp_path)
    a = world.commit("A", version="0.1.0", tag="v0.0.1")
    world.green(a)
    world.install_at("A")
    b = world.commit("B", version="0.1.1", tag="v0.0.2", mode=mode)
    world.green(b)
    world.grant()
    (world.target / ".git" / "hooks" / "pre-commit").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8") if hook else None
    head = world.customer_head()
    code, res = world.run()
    assert code == 1
    assert part in res["error"]
    assert "The install may have written files in " in res["error"]
    assert world.customer_head() == head
    assert world.log()[-1]["event"] == "update-result"
    assert world.log()[-1]["updated"] is False


def test_a_log_that_cannot_be_written_is_refused(tmp_path):
    """Catches: an update that goes on when the log cannot be written (row 14), instead of refusing before the install."""
    world, _a, _b = standard(tmp_path)
    world.log_file.mkdir()
    before = world.tree_state()
    code, res = world.run()
    assert code == 1
    assert "Cannot write the log" in res["error"]
    assert world.tree_state() == before


def test_the_call_names_the_second_root(tmp_path):
    """Checks: with two listed roots, the call that names the second updates only that root, in one commit (row 24)."""
    world = World(tmp_path)
    a = world.commit("A", version="0.1.0", tag="v0.0.1")
    world.green(a)
    world.install_at("A", roots=("app", "app2"))
    b = world.commit("B", version="0.1.1", tag="v0.0.2")
    world.green(b)
    world.grant(roots=["app", "app2"], root=None)
    code, res = world.run(root="app2")
    assert code == 0, res
    assert world.lock("app2")["source_sha"] == b
    assert world.lock("app")["source_sha"] == a
    assert world.customer_subjects(2)[1] == "customer install A"
    assert Path(res["root"]) == (world.target / "app2").resolve()


@pytest.mark.parametrize("from_head", [pytest.param(False, id="release-route"), pytest.param(True, id="narrow-route")])
def test_the_grant_and_the_green_record_are_never_written(tmp_path, from_head):
    """Catches: an upgrade that rewrites the grant or the green record on either route (row 30)."""
    world, _a, b = standard(tmp_path)
    c = world.commit("C", version="0.1.1", mark="b", files={"cards/n.md": "n\n"})
    world.green(c, kind="narrow", frm=b)
    grant_bytes, green_bytes = world.grant_file.read_bytes(), world.green_file.read_bytes()
    code, res = world.run(from_head=from_head)
    assert code == 0, res
    assert world.grant_file.read_bytes() == grant_bytes
    assert world.green_file.read_bytes() == green_bytes


def test_the_checks_name_the_command_that_was_checked(tmp_path):
    """Checks: the answer's checks name the full test command that the green record was matched against (row 29)."""
    world, _a, _b = standard(tmp_path)
    code, res = world.run(dry_run=True)
    assert code == 0, res
    assert any(_mw104.CMD_TEXT in c.get("detail", "") for c in res["checks"])


def test_a_row_of_another_command_names_both_commands(tmp_path):
    """Catches: a refusal for a full run of another command that does not name both commands (row 27)."""
    world = _unproven(tmp_path, {"command": "python -m pytest -k fast"})
    code, res = world.run(from_head=True)
    assert code == 1
    assert 'ran "python -m pytest -k fast"' in res["error"]
    assert 'full_command in release.json is "python -m pytest"' in res["error"]
    assert "No green record in " in res["error"]


def test_a_head_no_merge_ended_at_has_the_plain_reason(tmp_path):
    """Catches: a head that no merge ended at that is given the changed-command text (row 28): the reason must have no ran-text."""
    world = _unproven(tmp_path, None)
    code, res = world.run(from_head=True)
    assert code == 1
    assert "was not produced by a mkcl merge with a passing narrow run" in res["error"]
    assert 'ran "' not in res["error"]


# ---- 8d: the narrow route (from head) -----------------------------------------------------------------------------------------

def test_one_narrow_merge_installs_from_head(tmp_path):
    """Checks: one narrow merge of a card file on top of the full-green head installs, and the lock is that commit (row 31)."""
    world, _a, n1 = narrow_world(tmp_path, narrow_files={"cards/b.md": "b\n"})
    code, res = world.run(from_head=True)
    assert code == 0, res
    assert res["updated"] is True
    assert world.lock()["source_sha"] == n1
    assert "release" not in res


def test_the_narrow_route_is_named_in_answer_ledger_and_log(tmp_path):
    """Checks: the answer, the ledger row and the log name the full-green head and the rule (row 32)."""
    world, a, _n1 = narrow_world(tmp_path, narrow_files={"cards/b.md": "b\n"})
    code, res = world.run(from_head=True)
    assert code == 0, res
    expected = {"fullGreenHead": a, "rule": 0, "patterns": ["cards/**", "cards/REGISTER.md", "CHANGELOG.md"], "mergeResults": 1,
                "changedPaths": 1}
    assert res["narrow"] == expected
    assert last_ledger_row(world)["quote"].endswith(f", narrow-tested head (full-green head {a[:8]}, narrow rule 0), upgrade dir {world.cfg}")
    assert world.log()[-1]["narrow"] == expected


def test_a_narrow_dry_run_names_the_rule_and_changes_nothing(tmp_path):
    """Checks: a dry run on the narrow route names the narrow runs and rule 0 in the checks and changes nothing (row 33)."""
    world, _a, _n1 = narrow_world(tmp_path, narrow_files={"cards/b.md": "b\n"})
    before = world.tree_state()
    code, res = world.run(from_head=True, dry_run=True)
    assert code == 0, res
    assert any("narrow test runs only" in c["check"] and "rule 0" in c["detail"] for c in res["checks"])
    assert world.tree_state() == before


def test_two_narrow_merges_install(tmp_path):
    """Checks: two narrow merges in a row install and count two merge results (row 34)."""
    world, _a, n1 = narrow_world(tmp_path, narrow_files={"cards/b.md": "b\n"})
    n2 = world.commit("N2", version="0.1.0", files={"cards/c.md": "c\n"})
    world.green(n2, kind="narrow", frm=n1)
    code, res = world.run(from_head=True)
    assert code == 0, res
    assert res["narrow"]["mergeResults"] == 2
    assert res["narrow"]["changedPaths"] == 2
    assert world.lock()["source_sha"] == n2


def test_a_batch_of_two_commits_in_one_row_installs(tmp_path):
    """Checks: a batch (one row, two commits, from the old head) installs as one merge result (row 35)."""
    world = World(tmp_path)
    a = world.commit("A", version="0.1.0")
    world.green(a)
    world.install_at("A")
    world.commit("N1", version="0.1.0", files={"cards/b.md": "b\n"})
    n2 = world.commit("N2", version="0.1.0", files={"cards/c.md": "c\n"})
    world.green(n2, kind="narrow", frm=a)
    world.grant()
    code, res = world.run(from_head=True)
    assert code == 0, res
    assert res["narrow"]["mergeResults"] == 1
    assert res["narrow"]["changedPaths"] == 2


def test_a_path_outside_the_patterns_is_refused(tmp_path):
    """Catches: a narrow merge that changed a path no rule covers (row 36) and is installed anyway."""
    world, _a, _n1 = narrow_world(tmp_path, narrow_files={"src/x.py": "x\n"})
    code, res, before, after = refused(world, from_head=True)
    assert code == 1
    assert "src/x.py (changed since the full-green head " in res["error"]
    assert "is not covered by the narrow_paths rule." in res["error"]
    assert after == before


def test_a_rename_out_of_a_covered_path_is_refused(tmp_path):
    """Catches: a rename out of a card path that is judged by its covered source only (row 37): the destination must be named."""
    world = World(tmp_path)
    a = world.commit("A", version="0.1.0", files={"cards/a.md": "same text\n"})
    world.green(a)
    world.install_at("A")
    n1 = world.commit("N1", version="0.1.0", files={"src/a.md": "same text\n"}, delete=("cards/a.md",))
    world.green(n1, kind="narrow", frm=a)
    world.grant()
    code, res = world.run(from_head=True)
    assert code == 1
    assert "src/a.md (changed since the full-green head " in res["error"]


@pytest.mark.parametrize("how", [pytest.param("no-row-at-the-head", id="38-no-row-at-the-head"),
                                 pytest.param("hand-made-commit-in-the-way", id="38-hand-made-commit-in-the-way")])
def test_a_broken_narrow_chain_is_refused(tmp_path, how):
    """Catches: a narrow chain with a commit no mkcl merge produced (no row, or a hand-made commit in the way) that is accepted (row 38)."""
    world = World(tmp_path)
    a = world.commit("A", version="0.1.0")
    world.green(a)
    world.install_at("A")
    hand = world.commit("H", version="0.1.0", files={"cards/h.md": "h\n"})
    n1 = world.commit("N1", version="0.1.0", files={"cards/n.md": "n\n"})
    world.green(n1, kind="narrow", frm=hand) if how == "hand-made-commit-in-the-way" else None
    world.grant()
    code, res, before, after = refused(world, from_head=True)
    assert code == 1
    assert "was not produced by a mkcl merge" in res["error"]
    assert after == before


def test_the_narrow_match_is_case_sensitive(tmp_path):
    """Catches: a narrow merge of `Cards/a.md` accepted against the rule `cards/**` (row 40)."""
    world = World(tmp_path)
    a = world.commit("A", version="0.1.0")
    world.green(a)
    world.install_at("A")
    n1 = world.commit("N1", version="0.1.0", files={"Cards/a.md": "a\n"})
    world.green(n1, kind="narrow", frm=a)
    world.grant()
    code, res = world.run(from_head=True)
    assert code == 1
    assert "Cards/a.md (changed since the full-green head " in res["error"]


def test_a_full_green_head_of_another_command_is_refused(tmp_path):
    """Catches: a narrow merge on top of a head whose full run was another command, accepted as if it were full-green (row 41)."""
    world = World(tmp_path)
    a = world.commit("A", version="0.1.0")
    world.green(a, command="python -m pytest -k fast")
    world.install_at("A")
    n1 = world.commit("N1", version="0.1.0", files={"cards/n.md": "n\n"})
    world.green(n1, kind="narrow", frm=a)
    world.grant()
    code, res = world.run(from_head=True)
    assert code == 1
    assert "shows a full, passing test run" in res["error"]
    assert 'ran "python -m pytest -k fast"' in res["error"]


def test_a_full_green_head_off_the_first_parent_chain_is_refused(tmp_path):
    """Catches: a full-green head that sits on a side branch merged with a merge commit (not on the first-parent chain) accepted as the base of a narrow route (row 42)."""
    world = World(tmp_path)
    r = world.commit("R", version="0.1.0")
    world.install_at("R")
    git(world.engine, "checkout", "-q", "-b", "side")
    s = world.commit("S", version="0.1.0", files={"side.txt": "s\n"})
    world.green(s)
    git(world.engine, "checkout", "-q", "main")
    world.commit("M", version="0.1.0", files={"main.txt": "m\n"})
    git(world.engine, "merge", "-q", "--no-ff", "side", "-m", "merge side")
    n1 = world.commit("N1", version="0.1.0", files={"cards/n.md": "n\n"})
    world.green(n1, kind="narrow", frm=s)
    world.grant()
    code, res = world.run(from_head=True)
    assert code == 1
    assert "is not on the first-parent chain of main" in res["error"]
    assert r != s


def test_a_full_green_head_installs_with_no_narrow_rule(tmp_path):
    """Checks: a head that is itself full-green installs, and the answer has no narrow part (row 43)."""
    world, _a, b = standard(tmp_path)
    code, res = world.run(from_head=True)
    assert code == 0, res
    assert "narrow" not in res
    assert world.lock()["source_sha"] == b


# ---- M1: release mode -----------------------------------------------------------------------------------------------------------

def test_the_newest_proven_tag_installs_over_a_newer_unproven_one(tmp_path):
    """Catches: a release choice that takes a newer tag no full green row proves, or does not say it skipped it."""
    world, _a, b = standard(tmp_path)
    world.commit("C", version="0.1.2", tag="v0.0.3")
    code, res = world.run()
    assert code == 0, res
    assert res["release"] == "v0.0.2"
    assert res["newSha"] == b
    assert any("v0.0.3" in c.get("detail", "") and "no full green record" in c.get("detail", "") for c in res["checks"])


def test_version_order_beats_tag_date(tmp_path):
    """Catches: a release choice by text order or tag date (v0.0.9 made later) instead of by version order (v0.0.10)."""
    world = World(tmp_path)
    a = world.commit("A", version="0.1.0", tag="v0.0.1")
    world.green(a)
    world.install_at("A")
    b = world.commit("B", version="0.1.1", tag="v0.0.10")
    world.green(b)
    c = world.commit("C", version="0.1.2", tag="v0.0.9")
    world.green(c)
    world.grant()
    code, res = world.run()
    assert code == 0, res
    assert res["release"] == "v0.0.10"
    assert res["newSha"] == b


def test_a_tag_off_the_first_parent_chain_is_skipped(tmp_path):
    """Catches: a tag on a side branch (merged by a merge commit) that is taken as the release though it is off the first-parent chain."""
    world = World(tmp_path)
    a = world.commit("A", version="0.1.0", tag="v0.0.1")
    world.green(a)
    world.install_at("A")
    git(world.engine, "checkout", "-q", "-b", "side")
    s = world.commit("S", version="0.1.0", mark="a", tag="v0.0.5", files={"side.txt": "s\n"})
    world.green(s)
    git(world.engine, "checkout", "-q", "main")
    b = world.commit("B", version="0.1.1", tag="v0.0.2", files={"main.txt": "m\n"})
    world.green(b)
    git(world.engine, "merge", "-q", "--no-ff", "side", "-m", "merge side")
    world.grant()
    code, res = world.run()
    assert code == 0, res
    assert res["release"] == "v0.0.2"
    assert any("v0.0.5" in c.get("detail", "") and "not on the first-parent chain of main" in c.get("detail", "")
               for c in res["checks"])


def test_no_proven_tag_is_refused(tmp_path):
    """Catches: a release install when tags exist but none is proven by a full green row."""
    world = World(tmp_path)
    a = world.commit("A", version="0.1.0", tag="v0.0.1")
    world.install_at("A")
    world.commit("B", version="0.1.1", tag="v0.0.2")
    world.grant()
    code, res, before, after = refused(world)
    assert code == 1
    assert res["error"] == "no release tag is proven green; nothing was changed"
    assert after == before
    assert a != ""


def test_a_narrow_chain_does_not_prove_a_tag(tmp_path):
    """Catches: a tag proven by a narrow chain back to a full-green head (R257c: a narrow chain never proves a tag)."""
    world = World(tmp_path)
    a = world.commit("A", version="0.1.0")
    world.green(a)
    world.install_at("A")
    n1 = world.commit("N1", version="0.1.1", tag="v0.0.2", files={"cards/n.md": "n\n"})
    world.green(n1, kind="narrow", frm=a)
    world.grant()
    code, res, before, after = refused(world)
    assert code == 1
    assert res["error"] == "no release tag is proven green; nothing was changed"
    assert after == before


def test_release_mode_runs_the_releases_own_install_code(tmp_path):
    """Catches: an install run by the engine HEAD's code (or the working files) instead of the code of the release being installed."""
    world, _a, b = standard(tmp_path)
    world.commit("C", version="0.1.2", mark="head-code")
    code, res = world.run()
    assert code == 0, res
    assert (world.root / "mkway" / "MARK.txt").read_text(encoding="utf-8") == "b"
    assert world.lock()["semver"] == "0.1.1"
    assert res["newSha"] == b


def test_from_head_installs_the_head_commit(tmp_path):
    """Checks: the internal from-head mode installs the HEAD commit, with no release field (spec 7)."""
    world = World(tmp_path)
    a = world.commit("A", version="0.1.0", tag="v0.0.1")
    world.green(a)
    world.install_at("A")
    b = world.commit("B", version="0.1.1", mark="b-head")
    world.green(b)
    world.grant()
    code, res = world.run(from_head=True)
    assert code == 0, res
    assert "release" not in res
    assert world.lock()["source_sha"] == b
    assert (world.root / "mkway" / "MARK.txt").read_text(encoding="utf-8") == "b-head"


# ---- the downgrade guard ---------------------------------------------------------------------------------------------------------

def test_a_lock_with_no_source_commit_is_refused(tmp_path):
    """Catches: an upgrade over an install made from a plain folder (no source commit in its lock) (guard 7a)."""
    world, _a, _b = standard(tmp_path)
    world.set_lock(source_sha=None)
    code, res, before, after = refused(world)
    assert code == 1
    assert res["error"] == ("the installed engine has no source commit (installed from a plain folder); reinstall from the "
                            "engine repository. Nothing was changed.")
    assert after == before


def test_a_lock_source_not_in_the_engine_repository_is_refused(tmp_path):
    """Catches: an upgrade over an install whose source commit the engine repository does not hold (guard 7b)."""
    world, _a, _b = standard(tmp_path)
    world.set_lock(source_sha="d" * 40)
    code, res, before, after = refused(world)
    assert code == 1
    assert res["error"] == "the installed engine dddddddd is not in the engine repository. Nothing was changed."
    assert after == before


def test_a_release_older_than_the_install_is_refused(tmp_path):
    """Catches: a release that is an ancestor of the installed engine installed over it (guard 7c)."""
    world = World(tmp_path)
    a = world.commit("A", version="0.1.0", tag="v0.0.1")
    world.green(a)
    b = world.commit("B", version="0.1.1")
    world.install_at("B")
    world.grant()
    code, res, before, after = refused(world)
    assert code == 1
    assert res["error"] == f"the release v0.0.1 ({a[:8]}) is older than the installed engine {b[:8]}. Nothing was changed."
    assert after == before


def test_a_diverged_install_is_refused(tmp_path):
    """Catches: a release that is neither older nor newer than the installed engine (a side branch) installed over it (guard 7c)."""
    world = World(tmp_path)
    world.commit("R", version="0.1.0")
    git(world.engine, "checkout", "-q", "-b", "side")
    x = world.commit("X", version="0.1.0", files={"side.txt": "s\n"})
    git(world.engine, "checkout", "-q", "main")
    a = world.commit("A", version="0.1.1", tag="v0.0.1", files={"main.txt": "m\n"})
    world.green(a)
    world.install_at("X")
    world.grant()
    code, res, before, after = refused(world)
    assert code == 1
    assert res["error"] == f"the engine {a[:8]} and the installed engine {x[:8]} have diverged. Nothing was changed."
    assert after == before


def test_a_lower_version_is_refused(tmp_path):
    """Catches: a release whose VERSION is lower than the installed lock's version installed over it (guard 8a)."""
    world, _a, _b = standard(tmp_path)
    world.set_lock(semver="0.9.0")
    code, res, before, after = refused(world)
    assert code == 1
    assert res["error"] == "version 0.1.1 is lower than the installed 0.9.0. Nothing was changed."
    assert after == before


def test_a_newer_release_installs_over_an_older_install(tmp_path):
    """Checks: the nearest allow of the guard refusals: a newer release of the same major installs over an older install."""
    world, a, b = standard(tmp_path)
    code, res = world.run()
    assert code == 0, res
    assert res["oldSha"] == a
    assert res["newSha"] == b


def test_replay_the_newest_tag_older_than_the_install_never_downgrades(tmp_path):
    """Catches: the real shape (newest tag v0.2.1 while installs run 0.2.7 heads): the release is older than the install and must be refused, never installed."""
    world = World(tmp_path)
    r = world.commit("R", version="0.2.1", tag="v0.2.1")
    world.green(r)
    h = world.commit("H", version="0.2.7", files={"head.txt": "h\n"})
    world.green(h)
    world.install_at("H")
    world.grant()
    code, res, before, after = refused(world)
    assert code == 1
    assert "is older than the installed engine " + h[:8] in res["error"]
    assert after == before
    assert world.lock()["semver"] == "0.2.7"
