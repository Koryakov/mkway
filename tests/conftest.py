"""One fixture for every test (MW-003 close-fix item 1): the suite may run inside a Claude chat, whose shell carries
`CLAUDECODE`; the CLI refuses the owner's commands there. A test that needs a session's shell passes the variable
itself (`_engine.cli(..., session=True)` or an explicit env).

MW-017 (addition 1), kept by MW-026: `profiles.shared_state_dir` may name a folder outside the task root only when a
profile sets `state.shared_dir`. A test that sets it must name a folder inside this repository (the pytest temp folder
lies there), or the guard fails the test: a write outside the repository."""
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _no_session_variable(monkeypatch):
    monkeypatch.delenv("CLAUDECODE", raising=False)


@pytest.fixture(autouse=True)
def _git_discovery_stops_at_the_temp_folder(request, monkeypatch):
    """MW-028: `install.detect_vcs` answers git for any folder inside a git work tree, and the temp folder of the suite
    lies inside this repository. Git stops looking for a repository at the temp folder, so a scratch folder with no
    `git init` of its own is in no work tree, as a task folder on a plain disk is."""
    base = request.config.option.basetemp
    if base is not None:
        from pathlib import Path
        monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(Path(base).resolve()))


@pytest.fixture(autouse=True)
def _shared_state_stays_inside_the_repository(monkeypatch):
    try:
        import profiles  # a test that never imports the engine (the check's fixture test) has nothing to guard
    except ImportError:
        return
    real = profiles.shared_state_dir

    def guarded(root, profile):
        answer = real(root, profile)
        resolved = Path(answer).resolve()
        if REPO not in resolved.parents and resolved != REPO:
            raise AssertionError(f"MW-017 guard: shared state dir {resolved} is outside the repository {REPO}")
        return answer

    monkeypatch.setattr(profiles, "shared_state_dir", guarded)
