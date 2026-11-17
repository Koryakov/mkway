"""Card MW-083, rows E1 to E10, layer core: the worker count of a parallel run and the hand-over of the run's seed to the
workers. Pure: no process, no disk."""
from types import SimpleNamespace

import pytest

import _hermetic
import _xdist_cfg

REFUSAL = "MKWAY_TEST_WORKERS must be a whole number above 0"


@pytest.mark.parametrize("cores, text, expected", [
    pytest.param(16, None, 8, id="sixteen_cores"),
    pytest.param(1, None, 1, id="one_core"),
    pytest.param(None, None, 1, id="no_core_count"),
])
def test_workers_default_to_half_the_cores(cores, text, expected):
    """Checks: with no variable the count is half the cores, never below one, and one when the machine names no count."""
    assert _xdist_cfg.worker_count(cores, text) == expected


@pytest.mark.parametrize("cores, text, expected", [
    pytest.param(16, "3", 3, id="three_of_sixteen"),
])
def test_the_variable_overrides_the_cores(cores, text, expected):
    """Checks: a whole number in `MKWAY_TEST_WORKERS` is the count, whatever the cores."""
    assert _xdist_cfg.worker_count(cores, text) == expected


@pytest.mark.parametrize("text", [
    pytest.param("0", id="zero"),
    pytest.param("x", id="letters"),
])
def test_a_bad_variable_is_refused_with_the_fixed_text(text):
    """Catches: a zero or a non-number in `MKWAY_TEST_WORKERS` that is taken as a count, or refused with another text."""
    with pytest.raises(ValueError) as refused:
        _xdist_cfg.worker_count(16, text)
    assert str(refused.value) == REFUSAL


def test_the_controller_seed_is_put_in_the_worker_input():
    """Catches: a controller that hands its seed to no worker, so each worker takes its own clock."""
    handed = {}
    _xdist_cfg.put_seed(handed, 4242)
    assert handed == {"hermetic_seed": 4242}


def test_run_seed_takes_the_seed_handed_to_a_worker():
    """Catches: a worker that takes the clock or its option when the controller handed it a seed."""
    config = SimpleNamespace(workerinput={"hermetic_seed": 4242}, getoption=lambda name: None)
    assert _hermetic.run_seed(config) == 4242


def test_run_seed_of_a_serial_run_is_the_given_option():
    """Checks: a serial run (no worker input) takes the seed of `--seed`, as before the card."""
    config = SimpleNamespace(getoption=lambda name: 7)
    assert _hermetic.run_seed(config) == 7


def test_a_worker_without_a_handed_seed_uses_the_option():
    """Checks: a worker whose input holds no seed (a controller without the hook) falls back to `--seed`."""
    config = SimpleNamespace(workerinput={"workerid": "gw0"}, getoption=lambda name: 9)
    assert _hermetic.run_seed(config) == 9
