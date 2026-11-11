"""One fixture for every test (MW-003 close-fix item 1): the suite may run inside a Claude chat, whose shell carries
`CLAUDECODE`; the CLI refuses the owner's commands there. A test that needs a session's shell passes the variable
itself (`_engine.cli(..., session=True)` or an explicit env).

MW-017 (addition 1): the temp folder of the suite lies inside this repository, which may be a linked git work tree, and
`profiles.shared_state_dir` would then name a folder in the main work tree: a write outside the repository. So the
lookup answers `state_dir` in every test, except a test marked `real_shared_state`, which makes its own scratch
repositories."""
import pytest


@pytest.fixture(autouse=True)
def _no_session_variable(monkeypatch):
    monkeypatch.delenv("CLAUDECODE", raising=False)


@pytest.fixture(autouse=True)
def _shared_state_stays_inside_the_repository(request, monkeypatch):
    if request.node.get_closest_marker("real_shared_state") is None:
        try:
            import profiles  # a test that never imports the engine (the check's fixture test) has nothing to guard
        except ImportError:
            return
        monkeypatch.setattr(profiles, "_linked_main_state", lambda root, own: own)
