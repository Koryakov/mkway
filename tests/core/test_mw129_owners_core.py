"""Card MW-129 (R310 6, P2): a moved card record file is owned by the engine `state` kind, by its shared path. A shared folder
OUTSIDE the root goes through the outside branch of `owners.kind_of` (path None plus the absolute form); a shared folder INSIDE
the root goes through the row patterns. Built like tests/core/test_mw107_owners_core.py. Synthetic values only."""
import _engine  # noqa: F401  (puts the engine folder on the import path)
import core_session
import owners
from _no_io import no_io

OUTSIDE_SHARED = "/shared-folder/records"
INSIDE_SHARED = "mkway/state/shared"
BASE = {"bundle": {"root": "mkway"}, "state": {"dir": "mkway/state"}}


def test_a_card_record_file_in_a_shared_folder_outside_the_root_is_an_engine_state_file():
    """Catches: a moved card record file in an outside shared folder that no owner row covers (a session could write it)."""
    profile = {**BASE, "state": {"dir": "mkway/state", "shared_dir": OUTSIDE_SHARED}}
    record = core_session.OutsideRecord(raw=f"{OUTSIDE_SHARED}/red_proof.jsonl", abs=f"{OUTSIDE_SHARED}/red_proof.jsonl",
                                        matched=False)
    with no_io():
        row = owners.kind_of(None, profile, outside=record)
    assert (row.name, row.role) == ("state", "engine")


def test_a_card_record_file_in_a_shared_folder_inside_the_state_folder_is_an_engine_state_file():
    """Catches: the inside case answered by the outside branch, or by no row."""
    profile = {**BASE, "state": {"dir": "mkway/state", "shared_dir": f"/repo/{INSIDE_SHARED}"}}
    with no_io():
        row = owners.kind_of(f"{INSIDE_SHARED}/red_proof.jsonl", profile)
    assert (row.name, row.role) == ("state", "engine")


ROOT = "/repo"


def test_a_shared_folder_inside_the_root_but_outside_the_state_folder_is_an_engine_state_path():
    """Catches: R316 6, a shared folder `mkway/shared` that no owner row covers, so a session that may write it could write a
    red-proof row by hand. The path under the resolved shared folder maps to the `state` kind."""
    profile = {**BASE, "state": {"dir": "mkway/state", "shared_dir": f"{ROOT}/mkway/shared"}}
    with no_io():
        row = owners.kind_of("mkway/shared/red_proof.jsonl", profile, root=ROOT)
    assert (row.name, row.role) == ("state", "engine")


def test_the_new_mapping_names_the_engine_owner_in_the_refusal_sentence():
    """Catches: R316 6, a refusal sentence that says the shared path has no owner row."""
    profile = {**BASE, "state": {"dir": "mkway/state", "shared_dir": f"{ROOT}/mkway/shared"}}
    with no_io():
        text = owners.describe("mkway/shared/red_proof.jsonl", profile, root=ROOT)
    assert text == ("`mkway/shared/red_proof.jsonl` is the engine's (state): written by the engine's own commands and hooks")


def test_a_shared_folder_equal_to_the_root_does_not_make_every_path_an_engine_state_path():
    """Catches: R316 6, the edge case: the shared folder is the root itself, which is not a proper subfolder: a work file keeps
    its own rule (no owner row)."""
    profile = {**BASE, "state": {"dir": "mkway/state", "shared_dir": ROOT}}
    with no_io():
        row = owners.kind_of("src/app.py", profile, root=ROOT)
    assert row is None


def test_a_shared_folder_that_is_a_parent_of_the_root_does_not_make_a_root_path_an_engine_state_path():
    """Catches: R316 6, the edge case: the shared folder is a parent of the root: a path of the root keeps its own rule."""
    profile = {**BASE, "state": {"dir": "mkway/state", "shared_dir": "/"}}
    with no_io():
        row = owners.kind_of("src/app.py", profile, root=ROOT)
    assert row is None


def test_a_path_beside_the_shared_folder_inside_the_root_keeps_its_own_rule():
    """Catches: R316 6, a prefix match on the folder name: `mkway/shared-notes` is no path under the shared folder `mkway/shared`."""
    profile = {**BASE, "state": {"dir": "mkway/state", "shared_dir": f"{ROOT}/mkway/shared"}}
    with no_io():
        row = owners.kind_of("mkway/shared-notes/a.md", profile, root=ROOT)
    assert row is None
