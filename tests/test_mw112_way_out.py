"""Card MW-112 part (v) (ruling R284): the way out of every tool-validation id and of `close-log-failed`. One id, one test: the
command fails with the id, the text names the correct form, and the corrected command works. Synthetic roots under tmp_path;
the install cases use this repository as the install source (marker engine_repo)."""
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))  # tests/: the shared helpers
from _engine import cli, task_root  # noqa: E402
from _mw020 import OUT, deliverable, green, make_root  # noqa: E402
import _mw020  # noqa: E402
import cardtool  # noqa: E402
import records  # noqa: E402


def _reason(err):
    found = re.search(r"mkway: ([a-z-]+):", err)
    return found.group(1) if found else None


def _task(tmp_path, column=True):
    root = task_root(tmp_path, cards={"verdicts": "off"})
    assert cli(root, "card", "new", "First", session=True)[0] == 0
    if column:
        assert cli(root, "card", "resync", "--add-ordered-by")[0] == 0
    return root


def _seen(root, *ids):
    for sid in ids:
        records.append(root / "mkway" / "state", sid, "search", "x")


def test_the_way_out_of_card_unknown_is_a_register_id(tmp_path):
    """Catches: an unknown card refused with no word on how to name one, or a register id that is refused too."""
    root = _task(tmp_path)
    code, _out, err = cli(root, "card", "open", "CARD-009")
    assert (code != 0, _reason(err), "register id" in err and "`mkway card list`" in err) == (True, "card-unknown", True)
    assert cli(root, "card", "open", "CARD-001")[0] == 0


def test_the_way_out_of_card_bad_move_is_the_next_move_the_form_shows(tmp_path):
    """Catches: a move the form does not allow refused with no word on the allowed moves, or the allowed move refused."""
    root = _task(tmp_path)
    code, _out, err = cli(root, "card", "set", "CARD-001", "finished")
    assert (code != 0, _reason(err), "allowed moves: open, closed" in err) == (True, "card-bad-move", True)
    assert cli(root, "card", "set", "CARD-001", "open")[0] == 0


def test_the_way_out_of_card_bad_move_of_a_lead_is_the_next_move_the_form_shows(tmp_path):
    """Catches: a lead's move the form does not allow refused with no word on where the allowed move is shown."""
    import cardtool
    root = _task(tmp_path)
    profile = json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))
    with pytest.raises(cardtool.CardError) as caught:
        cardtool.move(root, profile, "CARD-001", "closed", session=True, record_paths=False, opener="lead-1")
    assert caught.value.reason == "card-bad-move" and "`mkway card list`" in str(caught.value)


def test_the_way_out_of_give_unknown_is_a_session_id_that_mkway_sessions_lists(tmp_path):
    """Catches: an id that starts no session refused with no word on where the ids are listed, or a listed id refused."""
    root = _task(tmp_path)
    _seen(root, "s-aaa1")
    code, _out, err = cli(root, "give", "CARD-001", "zz")
    assert (code != 0, _reason(err), "`mkway sessions`" in err) == (True, "give-unknown", True)
    assert cli(root, "give", "CARD-001", "s-aa")[0] == 0


def test_the_way_out_of_give_ambiguous_is_more_of_the_id(tmp_path):
    """Catches: a prefix of two sessions refused with no word on giving more of the id, or the longer id refused."""
    root = _task(tmp_path)
    _seen(root, "s-aaa1", "s-aaa2")
    code, _out, err = cli(root, "give", "CARD-001", "s-aa")
    assert (code != 0, _reason(err), "give more of the id" in err) == (True, "give-ambiguous", True)
    assert cli(root, "give", "CARD-001", "s-aaa1")[0] == 0


def test_the_way_out_of_give_no_column_is_the_owners_resync(tmp_path):
    """Catches: a register with no Ordered by column refused with no word on the resync, or a give after the resync refused."""
    root = _task(tmp_path, column=False)
    code, _out, err = cli(root, "give", "CARD-001", "owner")
    assert (code != 0, _reason(err), "card resync --add-ordered-by" in err) == (True, "give-no-column", True)
    assert cli(root, "card", "resync", "--add-ordered-by")[0] == 0
    assert cli(root, "give", "CARD-001", "owner")[0] == 0


def test_the_way_out_of_built_no_file_is_the_built_file(tmp_path):
    """Catches: `built` of a path with no file refused with no word on the form, or a file that is there refused."""
    root = make_root(tmp_path)
    green(root)
    code, _out, err = _mw020.built(root, f"{OUT}/none.md")
    assert (code != 0, _reason(err), f"`mkway built {OUT}/none.md`" in err) == (True, "built-no-file", True)
    rel = deliverable(root)
    green(root, tree=_mw020.index_digest(root))
    assert _mw020.built(root, rel)[0] == 0


def test_the_way_out_of_delivered_no_file_is_the_file_that_went_out(tmp_path):
    """Catches: `delivered` of a path with no file refused with no word on the form, or a file that is there refused."""
    root = make_root(tmp_path)
    code, _out, err = cli(root, "delivered", f"{OUT}/none.md")
    assert (code != 0, _reason(err), "`mkway delivered <path>`" in err) == (True, "delivered-no-file", True)
    assert cli(root, "delivered", deliverable(root))[0] == 0


def test_the_way_out_of_close_log_failed_is_a_writable_card_file(tmp_path, monkeypatch):
    """Catches: R284b (K8): a Log row that can not be written passing quietly, or an error that does not name the path."""
    import leads
    import profiles
    root = _task(tmp_path)
    profile = json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))
    _seen(root, "lead-1")
    leads.register_lead(profiles.shared_state_dir(root, profile), "lead-1")
    assert cli(root, "card", "new", "Second", session=True)[0] == 0
    assert cli(root, "give", "CARD-001", "lead-1")[0] == 0
    assert cli(root, "give", "CARD-002", "lead-1")[0] == 0

    def broken(*_args, **_kwargs):
        raise OSError("denied")
    monkeypatch.setattr(cardtool, "append_log_row", broken)
    with pytest.raises(cardtool.CardError) as caught:
        cardtool.move(root, profile, "CARD-001", "open", session=True, record_paths=False, opener="lead-1")
    text = str(caught.value).replace("\\", "/")
    assert (caught.value.reason, str(root / "mkway" / "cards").replace("\\", "/") in text and "CARD.md" in text) == (
        "close-log-failed", True)
    monkeypatch.undo()
    assert cardtool.move(root, profile, "CARD-002", "open", session=True, record_paths=False, opener="lead-1") == "open"


# ---- install: the real install on this repository as the source ---------------------------------------------------------

pytestmark_install = pytest.mark.engine_repo


def _install_parts(tmp_path):
    from test_install import make_source, make_task
    import install
    return install, make_source(tmp_path, vcs="none"), make_task(tmp_path, vcs="none")


@pytest.mark.engine_repo
def test_the_way_out_of_shared_not_absolute_is_an_absolute_folder(tmp_path):
    """Catches: a relative --shared refused with no example of the form, or an absolute folder refused."""
    install, src, task = _install_parts(tmp_path)
    with pytest.raises(install.InstallError) as caught:
        install.install(task, src, vcs="none", shared="rel/dir")
    assert "absolute path (for example" in str(caught.value)
    install.install(task, src, vcs="none", shared=(tmp_path / "shared").as_posix())


@pytest.mark.engine_repo
def test_the_way_out_of_starter_invalid_is_a_vcs_the_schema_takes(tmp_path):
    """Catches: a starter profile the schema refuses with no word on the repair, or a starter with a good vcs refused."""
    install, src, task = _install_parts(tmp_path)
    with pytest.raises(install.InstallError) as caught:
        install.install(task, src, vcs="svn")
    assert "starter profile would be invalid" in str(caught.value) and "--vcs of git or none" in str(caught.value)
    install.install(task, src, vcs="none")


@pytest.mark.engine_repo
def test_the_way_out_of_profile_invalid_shared_is_a_profile_the_owner_fixed(tmp_path):
    """Catches: --shared into a broken profile refused with no word on who fixes it and how, or a fixed profile refused."""
    import json
    install, src, task = _install_parts(tmp_path)
    profile = task / "mkway" / "profile.json"
    profile.parent.mkdir(parents=True)
    profile.write_text(json.dumps({"vcs": "bogus"}), encoding="utf-8")
    with pytest.raises(install.InstallError) as caught:
        install.install(task, src, shared=(tmp_path / "shared").as_posix())
    assert "cannot be written into it" in str(caught.value) and "fixes the profile in their own editor" in str(caught.value)
    profile.write_text(json.dumps({"vcs": "none", "bundle": {"root": "mkway"}, "gates": {}, "state": {"dir": "mkway/state"},
                                   "python": {"command": "python"}}), encoding="utf-8")
    install.install(task, src, shared=(tmp_path / "shared").as_posix())


def test_the_way_out_of_shared_profile_invalid_is_a_shared_folder_the_schema_takes(tmp_path):
    """Catches: a profile that --shared would make invalid refused with no word on the repair, or the valid result refused."""
    import core_install
    import install
    facts = dict(kind="shared", shared=(tmp_path / "s").as_posix())
    with pytest.raises(install.InstallError) as caught:
        install._decide(core_install.InstallFacts(candidate_errors=("state.shared_dir: bad",), **facts))
    assert "would be invalid" in str(caught.value) and "absolute folder the schema accepts" in str(caught.value)
    install._decide(core_install.InstallFacts(candidate_errors=(), **facts))


@pytest.mark.engine_repo
def test_the_way_out_of_commit_needs_git_is_an_install_without_commit(tmp_path):
    """Catches: --commit with no git refused with no word on the repair, or the install without --commit refused."""
    install, src, task = _install_parts(tmp_path)
    with pytest.raises(install.InstallError) as caught:
        install.install(task, src, vcs="none", commit=True)
    assert "--commit needs vcs git" in str(caught.value) and "without --commit" in str(caught.value)
    install.install(task, src, vcs="none")


@pytest.mark.engine_repo
def test_the_way_out_of_python_not_interpreter_is_a_named_interpreter(tmp_path):
    """Catches: a --python that is no interpreter refused with no word on the form, or a real interpreter refused."""
    install, src, task = _install_parts(tmp_path)
    with pytest.raises(install.InstallError) as caught:
        install.install(task, src, vcs="none", python="no-such-program-xyz")
    assert "--python must name an existing Python 3.9 or later" in str(caught.value)
    install.install(task, src, vcs="none", python="python")


@pytest.mark.engine_repo
def test_the_way_out_of_source_empty_is_the_engine_repository(tmp_path):
    """Catches: an empty install source refused with no word on where the engine is, or the engine source refused."""
    install, src, task = _install_parts(tmp_path)
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(install.InstallError) as caught:
        install.install(task, empty, vcs="none")
    assert "holds none of the engine's files" in str(caught.value) and "--from <engine repository>" in str(caught.value)
    install.install(task, src, vcs="none")
