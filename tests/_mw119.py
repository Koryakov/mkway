"""Shared helpers for the MW-119 tests (`mkway ask answered` runs only in the lead). Not a test module. Synthetic ids only."""
from _engine import cli
import cardtool
import leads
import profiles
import json


def _profile(root):
    return json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))


def make_lead(root, session):
    """Record the session as a registered lead (the file the lead role reads)."""
    leads.register_lead(profiles.shared_state_dir(root, _profile(root)), session)


def as_session(root, session, *args):
    """A session's mkway command: the lock gate's one-use permit names `session`, then the CLI runs in a session's shell."""
    cardtool.issue_by_permit(root / "mkway" / "state", session)
    return cli(root, *args, session=True)
