"""One fixture for every test (MW-003 close-fix item 1): the suite may run inside a Claude chat, whose shell carries
`CLAUDECODE`; the CLI refuses the owner's commands there. A test that needs a session's shell passes the variable
itself (`_engine.cli(..., session=True)` or an explicit env)."""
import pytest


@pytest.fixture(autouse=True)
def _no_session_variable(monkeypatch):
    monkeypatch.delenv("CLAUDECODE", raising=False)
