"""Card MW-074 (decision: R177), rows E25 to E28: the profile key `tests.hermetic_dirs`. Synthetic profile only."""
import copy
import json
import sys

from _engine import REPO
from _keys_md import section_rows, unquote

sys.path.insert(0, str(REPO / "engine"))

import schema_check  # noqa: E402

BASE = json.loads((REPO / "fixtures" / "synthetic" / "profile_depth2.json").read_text(encoding="utf-8"))


def _with(value):
    profile = copy.deepcopy(BASE)
    profile["tests"] = {"hermetic_dirs": value}
    return schema_check.check(profile)


def test_a_list_of_folders_is_a_valid_hermetic_dirs():
    """Checks: a list of folder paths is accepted."""
    assert _with(["tests/core", "tests/small"]) == []


def test_an_empty_list_is_a_valid_hermetic_dirs():
    """Checks: an empty list (a task that has not decided) is accepted."""
    assert _with([]) == []


def test_a_string_is_not_a_valid_hermetic_dirs():
    """Catches: a single string where a list of folders is required; the error names the key."""
    assert _with("tests/core") == ["tests.hermetic_dirs: expected array"]


def test_keys_md_names_the_default_folder():
    """Checks: the key has a row in the added keys with the default `["tests/core"]`."""
    row = [r for r in section_rows("Added keys") if unquote(r[0]) == "tests.hermetic_dirs"][0]
    assert '["tests/core"]' in row[3]
