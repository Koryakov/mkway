"""Card MW-107 (ruling R274a points 5 and 10): the upgrade renames the profile key `leads.outside_writable` to
`paths.outside_writable` in the profile itself (engine-written, in the upgrade's own commit, one ledger row, shown in the dry
run), and its dry run prints the rule and the effective outside-writable list. Real small git repositories under tmp_path,
the stub engine of the MW-104 harness; every folder an upgrade could touch points under tmp_path. Synthetic files only."""
import json

import pytest

import _mw104
from _mw104 import World, out

OLD, NEW = "leads.outside_writable", "paths.outside_writable"
DEFAULTS = ["<home>/.claude/projects/*/memory/**", "<home>/.claude/plans/**", "<temp>/claude/**"]


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch, tmp_path):
    _mw104.hermetic(monkeypatch, tmp_path)


def profile_file(world):
    return world.target / "app" / "mkway" / "profile.json"


def profile_of(world):
    return json.loads(profile_file(world).read_text(encoding="utf-8"))


def ledger_rows(world):
    text = (world.target / "app" / "mkway" / "ledger" / "ledger.md").read_text(encoding="utf-8")
    return [json.loads(x) for x in text.splitlines() if x.startswith("{")]


def world_with(tmp_path, profile):
    world = World(tmp_path)
    world.standard(profile=profile)
    return world


def test_the_old_key_is_renamed_in_the_profile_in_the_upgrade_commit_with_one_ledger_row(tmp_path):
    """Catches: R274a 10, an upgrade that leaves the old key in the profile, drops the owner's folders, commits the profile outside the upgrade's commit, or writes more than one ledger row."""
    world = world_with(tmp_path, {"leads": {"outside_writable": ["/data/a/**", "/data/b/**"], "max_cards": 3}})
    rows_before = len(ledger_rows(world))
    code, res = world.run()
    assert code == 0, res
    profile = profile_of(world)
    assert profile["paths"]["outside_writable"] == ["/data/a/**", "/data/b/**"]
    assert profile["leads"] == {"max_cards": 3}
    assert "app/mkway/profile.json" in world.files_of("HEAD")
    assert "mkway/profile.json" in res["files"]
    rows = ledger_rows(world)
    assert len(rows) == rows_before + 1
    assert rows[-1]["quote"].endswith(f", profile key {OLD} renamed to {NEW}")


def test_an_emptied_leads_object_is_removed_and_a_list_in_both_keys_is_merged_once(tmp_path):
    """Catches: a rename that leaves an empty `leads` object, loses a folder of either key, or repeats a folder both keys name."""
    world = world_with(tmp_path, {"leads": {"outside_writable": ["/data/a/**", "/data/b/**"]},
                                  "paths": {"outside_writable": ["/data/b/**", "/data/c/**"], "exempt": ["notes/**"]}})
    code, res = world.run()
    assert code == 0, res
    profile = profile_of(world)
    assert profile["paths"] == {"outside_writable": ["/data/b/**", "/data/c/**", "/data/a/**"], "exempt": ["notes/**"]}
    assert "leads" not in profile


def test_a_profile_without_the_old_key_is_left_byte_for_byte_and_the_quote_is_unchanged(tmp_path):
    """Checks: R274a 10, a task without the key has nothing to migrate: no profile in the commit, no change to the ledger row."""
    world = world_with(tmp_path, {"leads": {"max_cards": 3}})
    before = profile_file(world).read_bytes()
    code, res = world.run()
    assert code == 0, res
    assert profile_file(world).read_bytes() == before
    assert "app/mkway/profile.json" not in world.files_of("HEAD")
    assert "renamed to" not in ledger_rows(world)[-1]["quote"]


def test_the_dry_run_shows_the_rename_the_rule_and_the_effective_list_and_changes_nothing(tmp_path):
    """Catches: R274a 5 and 10, a dry run that does not show the rename, the rule and the list the task will have, or that writes the profile."""
    world = world_with(tmp_path, {"leads": {"outside_writable": ["/data/a/**"]}})
    before = world.tree_state()
    profile_bytes = profile_file(world).read_bytes()
    code, res = world.run(dry_run=True)
    assert code == 0, res
    assert res["migrations"] == [f"{OLD} -> {NEW} (1 folder)"]
    assert res["outsideWritable"]["list"] == DEFAULTS + ["/data/a/**"]
    assert "a session writes only inside its root" in res["outsideWritable"]["rule"]
    assert "paths.outside_writable" in res["outsideWritable"]["rule"]
    assert profile_file(world).read_bytes() == profile_bytes
    assert world.tree_state() == before


def test_the_dry_run_of_a_profile_with_no_old_key_prints_the_rule_and_no_migration(tmp_path):
    """Checks: R274a 5, the list and the rule are printed whether or not there is a key to move; `migrations` is empty then."""
    world = world_with(tmp_path, {"paths": {"outside_writable": ["/data/c/**"]}})
    code, res = world.run(dry_run=True)
    assert code == 0, res
    assert (res["migrations"], res["outsideWritable"]["list"]) == ([], DEFAULTS + ["/data/c/**"])


def test_a_changed_profile_is_refused_before_any_write_when_a_rename_is_due(tmp_path):
    """Catches: an upgrade commit that sweeps the owner's other unsaved profile edits into its commit: the profile must be clean before the rename."""
    world = world_with(tmp_path, {"leads": {"outside_writable": ["/data/a/**"]}})
    profile_file(world).write_text(json.dumps({"leads": {"outside_writable": ["/data/a/**"]}, "note": "edited"}),
                                   encoding="utf-8")
    before = world.customer_head()
    code, res = world.run()
    assert code != 0
    assert "mkway/profile.json" in res["error"]
    assert world.customer_head() == before
    assert out(world.target, "log", "-1", "--format=%s") == "customer install A"
    assert json.loads(profile_file(world).read_text(encoding="utf-8"))["note"] == "edited"


@pytest.mark.parametrize("old_value, text, moved", [
    pytest.param(7, "the value is not a list and is ignored", [], id="a-value-that-is-no-list"),
    pytest.param(["/data/a/**", 7], "1 item that is no text is ignored", ["/data/a/**"], id="an-item-that-is-no-text"),
])
def test_the_dry_run_shows_a_malformed_old_value_as_ignored(tmp_path, old_value, text, moved):
    """Catches: R274e (W45), a dry run that shows a malformed old key as a plain rename (`0 folders`), so the owner never learns that the value does not count: the migration line says the value, or the item, is ignored, and the list is the one the task will have."""
    world = world_with(tmp_path, {"leads": {"outside_writable": old_value}})
    code, res = world.run(dry_run=True)
    assert code == 0, res
    assert (len(res["migrations"]), text in res["migrations"][0], res["outsideWritable"]["list"]) == (1, True, DEFAULTS + moved)


@pytest.mark.parametrize("old_value, moved", [
    pytest.param(7, [], id="a-value-that-is-no-list"),
    pytest.param(["/data/a/**", 7], ["/data/a/**"], id="an-item-that-is-no-text"),
])
def test_a_malformed_old_value_is_never_carried_to_the_new_key(tmp_path, old_value, moved):
    """Catches: R274e (W45), a malformed old value (a number, a non-text item) copied into `paths.outside_writable`, where the schema calls it an error."""
    world = world_with(tmp_path, {"leads": {"outside_writable": old_value}})
    code, res = world.run()
    assert code == 0, res
    assert profile_of(world)["paths"]["outside_writable"] == moved
