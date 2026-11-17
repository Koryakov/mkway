"""Card MW-035: install finishes its own commit in one correct step. A stale `engine/` ignore line of an earlier install
is removed; the commit step takes only install's own paths, whatever else is staged; without `--commit` install prints
one line to paste; the profile key `commit.message_prefix` starts the message. Synthetic scratch repositories under the
pytest temp folder only."""
import json
import re

import pytest

import _docs as docs
from _engine import REPO
import profiles

pytestmark = pytest.mark.engine_repo

COMMIT_ENV = {"GIT_AUTHOR_NAME": "mkway-test", "GIT_AUTHOR_EMAIL": "mkway-test", "GIT_COMMITTER_NAME": "mkway-test",
              "GIT_COMMITTER_EMAIL": "mkway-test"}
# changed by MW-036: install's own paths, not the bundle folder; the profile only on the run that created it
PATHS = ".claude/settings.json mkway/.gitignore mkway/.gitattributes mkway/mkway.lock mkway/engine"
FIRST_PATHS = PATHS + " mkway/profile.json"


@pytest.mark.parametrize(
    "bad",
    [
        pytest.param("a b", id="space"),
        pytest.param('a"b', id="double-quote"),
        pytest.param("a`b", id="backtick"),
        pytest.param("a$b", id="dollar"),
        pytest.param("a\nb", id="newline"),
        pytest.param("", id="empty"),
    ],
)
def test_the_message_prefix_key_is_in_the_schema_and_keys(bad):
    """Catches: a message prefix with a space or a shell character that the schema accepts, or a key with no KEYS.md line (E5)."""
    base = {"commit": {"message_prefix": "#10536"}}
    assert not any("message_prefix" in e for e in profiles.validate(base)), profiles.validate(base)
    errors = profiles.validate({"commit": {"message_prefix": bad}})
    assert any("message_prefix" in e for e in errors), (bad, errors)
    keys = (REPO / "engine" / "KEYS.md").read_text(encoding="utf-8")
    assert re.search(r"^\| `commit\.message_prefix` \| in schema now \| `commit\.message_prefix` \|", keys, re.M)


