"""Hermetic small tests (card MW-074, decision: R177): every test in this folder runs with the guard of `_hermetic.py` on
(no process, no socket, no sleep, no file write outside its tmp_path), and the tests of this folder run in a shuffled
order. The seed is chosen and printed by `tests/conftest.py` (`--seed N` repeats an order)."""
import os
from pathlib import Path

import pytest

import _hermetic

HERE = Path(__file__).resolve().parent


def _label(config):
    return Path(os.path.relpath(HERE, config.rootpath)).as_posix()


@pytest.fixture(autouse=True)
def _hermetic_test(request, tmp_path, monkeypatch):
    _hermetic.install(monkeypatch, tmp_path, _label(request.config))


def pytest_collection_modifyitems(config, items):
    items[:] = _hermetic.shuffle_under(items, HERE, _hermetic.run_seed(config))
